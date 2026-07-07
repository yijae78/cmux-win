"""SQLite Builder: FTS5 full-text search + sqlite-vec vector index construction.

Builds the query interface database (data/output/index.sqlite) from Parquet data
as specified in PRD SS7.2. The SQLite database provides:

    articles_fts        -- FTS5 virtual table with unicode61 tokenizer (keyword search)
    article_embeddings  -- sqlite-vec virtual table (vector similarity search, 384-dim)
    signals_index       -- Indexed table for signal layer/date filtering
    topics_index        -- Topic summary table with trend direction
    crawl_status        -- Per-source crawling metadata

Design decisions:
    - FTS5 with unicode61 tokenizer: correct handling of Korean/Japanese/multilingual text
    - sqlite-vec: optional dependency; graceful degradation if not installed
    - Batch inserts (chunks of 1000): balances memory with SQLite write performance
    - Indexes created AFTER bulk inserts: avoids O(N log N) index maintenance during load
    - WAL mode: enables concurrent readers while writer is active
    - VACUUM + ANALYZE after build: optimal query planner statistics

Reference: PRD SS7.2 (SQLite schema), Step 7 pipeline design Section 3.8.
"""

from __future__ import annotations

import gc
import json
import logging
import sqlite3
import struct
import tempfile
import time
from pathlib import Path
from typing import Any, Iterator

import pyarrow as pa
import pyarrow.parquet as pq

from src.utils.error_handler import SQLiteError
from src.utils.logging_config import get_analysis_logger

logger = get_analysis_logger()

# =============================================================================
# Constants
# =============================================================================

BATCH_SIZE = 1_000          # Rows per executemany batch
FTS_TOKENIZER = "unicode61"  # unicode61 handles CJK, Arabic, RTL correctly

# Valid signal layers (for topics_index trend direction computation)
VALID_SIGNAL_LAYERS = {
    "L1_fad", "L2_short", "L3_mid", "L4_long", "L5_singularity"
}

# Embedding dimension (must match SBERT model)
EMBEDDING_DIM = 384


# =============================================================================
# Schema DDL statements (PRD SS7.2)
# =============================================================================

_DDL_FTS = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    article_id UNINDEXED,
    title,
    body,
    source UNINDEXED,
    category UNINDEXED,
    language UNINDEXED,
    published_at UNINDEXED,
    tokenize='{FTS_TOKENIZER}'
);
"""

_DDL_VEC = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS article_embeddings USING vec0(
    article_id TEXT PRIMARY KEY,
    embedding FLOAT[{EMBEDDING_DIM}]
);
"""

_DDL_SIGNALS_INDEX = """
CREATE TABLE IF NOT EXISTS signals_index (
    signal_id    TEXT PRIMARY KEY,
    signal_layer TEXT NOT NULL,
    signal_label TEXT NOT NULL,
    detected_at  TEXT NOT NULL,
    confidence   REAL,
    article_count INTEGER
);
"""

_DDL_TOPICS_INDEX = """
CREATE TABLE IF NOT EXISTS topics_index (
    topic_id        INTEGER PRIMARY KEY,
    label           TEXT,
    article_count   INTEGER,
    first_seen      TEXT,
    last_seen       TEXT,
    trend_direction TEXT
);
"""

_DDL_CRAWL_STATUS = """
CREATE TABLE IF NOT EXISTS crawl_status (
    source         TEXT NOT NULL,
    last_crawled   TEXT NOT NULL,
    articles_count INTEGER,
    success_rate   REAL,
    current_tier   INTEGER DEFAULT 1
);
"""

_DDL_SIGNALS_IDX_LAYER = "CREATE INDEX IF NOT EXISTS idx_signals_layer ON signals_index(signal_layer);"
_DDL_SIGNALS_IDX_DATE  = "CREATE INDEX IF NOT EXISTS idx_signals_date ON signals_index(detected_at);"


# =============================================================================
# SQLiteBuilder class
# =============================================================================

class SQLiteBuilder:
    """Builds the SQLite index database from Parquet output files.

    Usage:
        builder = SQLiteBuilder(sqlite_path)
        stats = builder.build(
            articles_parquet=Path("data/processed/articles.parquet"),
            analysis_parquet=Path("data/output/analysis.parquet"),
            signals_parquet=Path("data/output/signals.parquet"),
            topics_parquet=Path("data/analysis/topics.parquet"),
        )

    The builder:
        1. Creates all tables from PRD SS7.2 DDL.
        2. Populates articles_fts from articles.parquet + analysis.parquet.
        3. Populates article_embeddings from analysis.parquet embedding column
           (via sqlite-vec; skipped gracefully if not installed).
        4. Populates signals_index from signals.parquet.
        5. Populates topics_index (aggregated) from topics.parquet.
        6. Creates secondary indexes AFTER bulk load.
        7. Runs VACUUM + ANALYZE for optimal query performance.

    Raises:
        SQLiteError: On unrecoverable SQLite operation failure (3 retries).
    """

    def __init__(
        self,
        sqlite_path: Path | str,
        batch_size: int = BATCH_SIZE,
        max_retries: int = 3,
    ) -> None:
        self.sqlite_path = Path(sqlite_path)
        self.batch_size = batch_size
        self.max_retries = max_retries
        self._vec_available: bool | None = None  # lazily detected

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(
        self,
        articles_parquet: Path | str | None = None,
        analysis_parquet: Path | str | None = None,
        signals_parquet: Path | str | None = None,
        topics_parquet: Path | str | None = None,
        crawl_status_records: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build the SQLite index database.

        Any Parquet path that is None or does not exist is skipped with a
        WARNING log (partial builds are valid -- e.g., signals not yet produced).

        Args:
            articles_parquet:    Path to data/processed/articles.parquet.
            analysis_parquet:    Path to data/output/analysis.parquet (merged).
            signals_parquet:     Path to data/output/signals.parquet.
            topics_parquet:      Path to data/analysis/topics.parquet.
            crawl_status_records: Optional list of dicts for crawl_status table.
                                  Each dict: {source, last_crawled, articles_count,
                                  success_rate, current_tier}.

        Returns:
            dict with counts and timing information per table.
        """
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        t_start = time.perf_counter()
        stats: dict[str, Any] = {
            "sqlite_path": str(self.sqlite_path),
            "vec_available": False,
            "tables": {},
        }

        with self._connect() as conn:
            self._configure_connection(conn)
            self._create_schema(conn, stats)

            # Populate articles_fts
            if articles_parquet and Path(articles_parquet).exists():
                n = self._populate_fts(conn, Path(articles_parquet))
                stats["tables"]["articles_fts"] = n
            else:
                logger.warning("articles_parquet not found -- skipping FTS population")
                stats["tables"]["articles_fts"] = 0

            # Populate article_embeddings (requires analysis.parquet with embedding col)
            if analysis_parquet and Path(analysis_parquet).exists():
                vec_n = self._populate_vec(conn, Path(analysis_parquet), stats)
                stats["tables"]["article_embeddings"] = vec_n
            else:
                logger.warning("analysis_parquet not found -- skipping vector population")
                stats["tables"]["article_embeddings"] = 0

            # Populate signals_index
            if signals_parquet and Path(signals_parquet).exists():
                n = self._populate_signals(conn, Path(signals_parquet))
                stats["tables"]["signals_index"] = n
            else:
                logger.warning("signals_parquet not found -- skipping signals_index")
                stats["tables"]["signals_index"] = 0

            # Populate topics_index
            if topics_parquet and Path(topics_parquet).exists():
                n = self._populate_topics(conn, Path(topics_parquet))
                stats["tables"]["topics_index"] = n
            else:
                logger.warning("topics_parquet not found -- skipping topics_index")
                stats["tables"]["topics_index"] = 0

            # Populate crawl_status
            if crawl_status_records:
                n = self._populate_crawl_status(conn, crawl_status_records)
                stats["tables"]["crawl_status"] = n
            else:
                stats["tables"]["crawl_status"] = 0

            # Create secondary indexes AFTER bulk load
            self._create_indexes(conn)

            # Optimize
            conn.execute("VACUUM")
            conn.execute("ANALYZE")
            conn.commit()

        elapsed = time.perf_counter() - t_start
        stats["elapsed_seconds"] = round(elapsed, 2)
        db_size = self.sqlite_path.stat().st_size
        stats["size_bytes"] = db_size

        logger.info(
            "SQLite build complete",
            extra={
                "path": str(self.sqlite_path),
                "size_bytes": db_size,
                "elapsed_s": stats["elapsed_seconds"],
                "tables": stats["tables"],
            },
        )
        return stats

    def run_query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Run a SELECT query and return results as a list of dicts.

        Convenience method for verification / ad-hoc queries.

        Args:
            sql:    SQL SELECT statement.
            params: Query parameters (positional tuple).

        Returns:
            List of rows as dicts (column_name -> value).
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    # ------------------------------------------------------------------
    # Schema creation
    # ------------------------------------------------------------------

    def _create_schema(self, conn: sqlite3.Connection, stats: dict[str, Any]) -> None:
        """Create all tables defined in PRD SS7.2."""
        # FTS5 virtual table
        conn.execute(_DDL_FTS)

        # sqlite-vec virtual table (graceful degradation)
        vec_available = self._check_vec(conn)
        stats["vec_available"] = vec_available
        if vec_available:
            conn.execute(_DDL_VEC)
        else:
            logger.warning(
                "sqlite-vec not available -- article_embeddings table will be skipped. "
                "Install with: pip install sqlite-vec"
            )

        # Regular tables
        conn.execute(_DDL_SIGNALS_INDEX)
        conn.execute(_DDL_TOPICS_INDEX)
        conn.execute(_DDL_CRAWL_STATUS)
        conn.commit()

    def _create_indexes(self, conn: sqlite3.Connection) -> None:
        """Create secondary indexes AFTER bulk inserts for performance."""
        conn.execute(_DDL_SIGNALS_IDX_LAYER)
        conn.execute(_DDL_SIGNALS_IDX_DATE)
        conn.commit()

    # ------------------------------------------------------------------
    # FTS population (articles_fts)
    # ------------------------------------------------------------------

    def _populate_fts(self, conn: sqlite3.Connection, parquet_path: Path) -> int:
        """Populate articles_fts from articles.parquet.

        Reads article_id, title, body, source, category, language,
        published_at. Batch-inserts in chunks of *self.batch_size*.

        Args:
            conn:         SQLite connection.
            parquet_path: Path to articles.parquet.

        Returns:
            Number of rows inserted.
        """
        table = pq.read_table(
            str(parquet_path),
            columns=["article_id", "title", "body", "source",
                     "category", "language", "published_at"],
        )

        total = 0
        sql = (
            "INSERT OR IGNORE INTO articles_fts "
            "(article_id, title, body, source, category, language, published_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)"
        )

        for batch in _iter_batches(table, self.batch_size):
            rows = []
            for i in range(len(batch)):
                published_at = batch.column("published_at")[i].as_py()
                rows.append((
                    _str_or_empty(batch.column("article_id")[i]),
                    _str_or_empty(batch.column("title")[i]),
                    _str_or_empty(batch.column("body")[i]),
                    _str_or_empty(batch.column("source")[i]),
                    _str_or_empty(batch.column("category")[i]),
                    _str_or_empty(batch.column("language")[i]),
                    str(published_at) if published_at is not None else "",
                ))
            conn.executemany(sql, rows)
            total += len(rows)

        conn.commit()
        logger.info("FTS populated: %d rows", total)
        return total

    # ------------------------------------------------------------------
    # Vector population (article_embeddings via sqlite-vec)
    # ------------------------------------------------------------------

    def _populate_vec(
        self,
        conn: sqlite3.Connection,
        parquet_path: Path,
        stats: dict[str, Any],
    ) -> int:
        """Populate article_embeddings from analysis.parquet.

        Skips gracefully if sqlite-vec is unavailable or embedding column
        is missing.

        Args:
            conn:         SQLite connection.
            parquet_path: Path to analysis.parquet (must contain 'embedding' column).
            stats:        Mutable stats dict (updated in-place).

        Returns:
            Number of embedding rows inserted (0 if skipped).
        """
        if not stats.get("vec_available", False):
            return 0

        # Check embedding column exists
        meta = pq.read_metadata(str(parquet_path))
        schema = pq.read_schema(str(parquet_path))
        if "embedding" not in schema.names or "article_id" not in schema.names:
            logger.warning(
                "embedding or article_id column missing from %s -- skipping vec",
                parquet_path,
            )
            return 0

        table = pq.read_table(str(parquet_path), columns=["article_id", "embedding"])
        total = 0
        sql = "INSERT OR IGNORE INTO article_embeddings (article_id, embedding) VALUES (?, ?)"

        for batch in _iter_batches(table, self.batch_size):
            rows = []
            for i in range(len(batch)):
                article_id = _str_or_empty(batch.column("article_id")[i])
                emb_val = batch.column("embedding")[i].as_py()
                if emb_val is None:
                    continue
                # sqlite-vec expects bytes: 384 float32 values as little-endian binary
                emb_bytes = struct.pack(f"{len(emb_val)}f", *emb_val)
                rows.append((article_id, emb_bytes))

            if rows:
                conn.executemany(sql, rows)
                total += len(rows)

        conn.commit()
        logger.info("Vector index populated: %d rows", total)
        return total

    # ------------------------------------------------------------------
    # Signals population (signals_index)
    # ------------------------------------------------------------------

    def _populate_signals(self, conn: sqlite3.Connection, parquet_path: Path) -> int:
        """Populate signals_index from signals.parquet.

        article_count is derived from len(article_ids) list column.

        Args:
            conn:         SQLite connection.
            parquet_path: Path to signals.parquet.

        Returns:
            Number of rows inserted.
        """
        required_cols = ["signal_id", "signal_layer", "signal_label",
                         "detected_at", "confidence", "article_ids"]
        schema = pq.read_schema(str(parquet_path))
        available = set(schema.names)
        read_cols = [c for c in required_cols if c in available]

        table = pq.read_table(str(parquet_path), columns=read_cols)
        total = 0
        sql = (
            "INSERT OR REPLACE INTO signals_index "
            "(signal_id, signal_layer, signal_label, detected_at, confidence, article_count) "
            "VALUES (?, ?, ?, ?, ?, ?)"
        )

        for batch in _iter_batches(table, self.batch_size):
            rows = []
            for i in range(len(batch)):
                detected_at = (
                    batch.column("detected_at")[i].as_py()
                    if "detected_at" in available else None
                )
                article_ids_val = (
                    batch.column("article_ids")[i].as_py()
                    if "article_ids" in available else None
                )
                article_count = len(article_ids_val) if article_ids_val else 0
                confidence_val = (
                    batch.column("confidence")[i].as_py()
                    if "confidence" in available else None
                )
                rows.append((
                    _str_or_empty(batch.column("signal_id")[i])
                    if "signal_id" in available else "",
                    _str_or_empty(batch.column("signal_layer")[i])
                    if "signal_layer" in available else "",
                    _str_or_empty(batch.column("signal_label")[i])
                    if "signal_label" in available else "",
                    str(detected_at) if detected_at is not None else "",
                    float(confidence_val) if confidence_val is not None else None,
                    article_count,
                ))
            conn.executemany(sql, rows)
            total += len(rows)

        conn.commit()
        logger.info("signals_index populated: %d rows", total)
        return total

    # ------------------------------------------------------------------
    # Topics population (topics_index -- aggregated)
    # ------------------------------------------------------------------

    def _populate_topics(self, conn: sqlite3.Connection, parquet_path: Path) -> int:
        """Populate topics_index by aggregating topics.parquet.

        Groups by topic_id to compute:
            label:          Most common topic_label for this topic_id
            article_count:  Number of articles assigned to this topic
            first_seen:     Earliest published_at (if articles.parquet joined)
            last_seen:      Latest published_at
            trend_direction: Placeholder "stable" (time-series data not in topics.parquet)

        Args:
            conn:         SQLite connection.
            parquet_path: Path to topics.parquet.

        Returns:
            Number of distinct topics inserted.
        """
        schema = pq.read_schema(str(parquet_path))
        available = set(schema.names)
        read_cols = [c for c in ["article_id", "topic_id", "topic_label"] if c in available]
        table = pq.read_table(str(parquet_path), columns=read_cols)

        # Aggregate in Python (topics table is small enough)
        from collections import Counter, defaultdict
        topic_articles: dict[int, int] = defaultdict(int)
        topic_labels: dict[int, Counter] = defaultdict(Counter)  # type: ignore[type-arg]

        for i in range(len(table)):
            tid_val = table.column("topic_id")[i].as_py() if "topic_id" in available else None
            tlabel_val = table.column("topic_label")[i].as_py() if "topic_label" in available else None
            if tid_val is None:
                continue
            topic_articles[tid_val] += 1
            if tlabel_val:
                topic_labels[tid_val][tlabel_val] += 1

        sql = (
            "INSERT OR REPLACE INTO topics_index "
            "(topic_id, label, article_count, first_seen, last_seen, trend_direction) "
            "VALUES (?, ?, ?, ?, ?, ?)"
        )
        rows = []
        for tid, count in topic_articles.items():
            label = (
                topic_labels[tid].most_common(1)[0][0]
                if tid in topic_labels and topic_labels[tid]
                else None
            )
            rows.append((tid, label, count, None, None, "stable"))

        if rows:
            conn.executemany(sql, rows)
            conn.commit()

        logger.info("topics_index populated: %d topics", len(rows))
        return len(rows)

    # ------------------------------------------------------------------
    # Crawl status population
    # ------------------------------------------------------------------

    def _populate_crawl_status(
        self,
        conn: sqlite3.Connection,
        records: list[dict[str, Any]],
    ) -> int:
        """Insert crawl_status records.

        Args:
            conn:    SQLite connection.
            records: List of dicts with keys: source, last_crawled,
                     articles_count, success_rate, current_tier.

        Returns:
            Number of rows inserted.
        """
        sql = (
            "INSERT OR REPLACE INTO crawl_status "
            "(source, last_crawled, articles_count, success_rate, current_tier) "
            "VALUES (?, ?, ?, ?, ?)"
        )
        rows = [
            (
                r.get("source", ""),
                r.get("last_crawled", ""),
                r.get("articles_count"),
                r.get("success_rate"),
                r.get("current_tier", 1),
            )
            for r in records
        ]
        conn.executemany(sql, rows)
        conn.commit()
        return len(rows)

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection with error recovery.

        Retries up to *max_retries* times if the database is locked.

        Returns:
            Open sqlite3.Connection.

        Raises:
            SQLiteError: If connection fails after all retries.
        """
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                conn = sqlite3.connect(str(self.sqlite_path), timeout=30.0)
                return conn
            except sqlite3.Error as exc:
                last_exc = exc
                logger.warning(
                    "SQLite connect attempt %d/%d failed: %s",
                    attempt + 1, self.max_retries, exc,
                )
                time.sleep(0.5 * (attempt + 1))

        raise SQLiteError(
            f"Cannot connect to SQLite at {self.sqlite_path}: {last_exc}"
        )

    @staticmethod
    def _configure_connection(conn: sqlite3.Connection) -> None:
        """Apply performance-critical PRAGMAs.

        WAL mode: allows concurrent readers while writer is active.
        Cache: 64 MB page cache reduces I/O during bulk inserts.
        Sync: NORMAL balances durability with write speed.
        """
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA cache_size = -65536;")   # 64 MB
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA temp_store = MEMORY;")

    @staticmethod
    def _check_vec(conn: sqlite3.Connection) -> bool:
        """Return True if sqlite-vec extension is available.

        Attempts to load sqlite-vec. Falls back to False on any error.
        """
        try:
            import sqlite_vec  # type: ignore[import]
            sqlite_vec.load(conn)
            # Test that vec0 module is registered
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS _vec_probe USING vec0(x FLOAT[4])"
            )
            conn.execute("DROP TABLE IF EXISTS _vec_probe")
            return True
        except Exception:
            return False


# =============================================================================
# Standalone utility: build SQLite from directory
# =============================================================================

def build_sqlite(parquet_dir: Path | str, sqlite_path: Path | str) -> dict[str, Any]:
    """Build a SQLite index from a directory of Parquet files.

    Convention for file locations (matches PRD SS7.3 directory structure):
        {parquet_dir}/processed/articles.parquet
        {parquet_dir}/output/analysis.parquet
        {parquet_dir}/output/signals.parquet
        {parquet_dir}/analysis/topics.parquet

    Args:
        parquet_dir: Root data directory (e.g., Path("data")).
        sqlite_path: Output SQLite file path.

    Returns:
        Stats dict from SQLiteBuilder.build().
    """
    data = Path(parquet_dir)
    builder = SQLiteBuilder(sqlite_path)
    return builder.build(
        articles_parquet=data / "processed" / "articles.parquet",
        analysis_parquet=data / "output" / "analysis.parquet",
        signals_parquet=data / "output" / "signals.parquet",
        topics_parquet=data / "analysis" / "topics.parquet",
    )


# =============================================================================
# Internal helpers
# =============================================================================

def _iter_batches(table: pa.Table, batch_size: int) -> Iterator[pa.Table]:
    """Yield successive row slices of *table* of size *batch_size*."""
    n = len(table)
    for start in range(0, n, batch_size):
        yield table.slice(start, min(batch_size, n - start))


def _str_or_empty(scalar: Any) -> str:
    """Convert a PyArrow scalar or Python value to str, returning '' for None."""
    if scalar is None:
        return ""
    val = scalar.as_py() if hasattr(scalar, "as_py") else scalar
    return str(val) if val is not None else ""
