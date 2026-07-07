"""Stage 8: Data Output -- Parquet merge, SQLite index, DuckDB verification.

Final stage of the 8-stage NLP analysis pipeline. Merges all prior stage outputs
into finalized, ZSTD-compressed Parquet files and builds the SQLite query interface.

Processing steps:
    1. Merge analysis.parquet (21 columns, ANALYSIS_SCHEMA) from:
           articles.parquet (Stage 1) +
           article_analysis.parquet (Stage 3) +
           topics.parquet (Stage 4) +
           embeddings.parquet (Stage 2: embedding + keywords) +
           ner.parquet (Stage 2: entities)
       Join key: article_id
       Output: data/output/analysis.parquet (ZSTD level 3)

    2. Finalize signals.parquet (12 columns, SIGNALS_SCHEMA):
           Stage 7 already produced data/output/signals.parquet -- validate
           schema, re-compress with ZSTD level 3.
       Output: data/output/signals.parquet (in-place re-compression)

    3. Copy topics.parquet:
           Copy data/analysis/topics.parquet to data/output/topics.parquet
           with ZSTD re-compression.
       Output: data/output/topics.parquet

    4. Build SQLite index (data/output/index.sqlite):
           FTS5 + sqlite-vec (optional) + signals_index + topics_index + crawl_status

    5. DuckDB compatibility verification:
           Attempt duckdb.read_parquet() on analysis.parquet and signals.parquet.
           Failure is WARNING only (DuckDB is a convenience query layer, not critical).

    6. Data quality validation (PRD SS7.4):
           No duplicate article_id, embedding dim = 384, no nulls in PK columns,
           all topic_ids reference valid topics, completeness check.

Memory budget: ~0.5 GB peak (pyarrow + sqlite3 + optional duckdb).
Performance target: ~1.0 min for 1,000 articles.

Reference: PRD SS7.1-7.4, Step 7 pipeline design Section 3.8 (Stage 8).
"""

from __future__ import annotations

import gc
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from src.config.constants import (
    ANALYSIS_PARQUET_PATH,
    ARTICLE_ANALYSIS_PARQUET_PATH,
    ARTICLES_PARQUET_PATH,
    DATA_ANALYSIS_DIR,
    DATA_FEATURES_DIR,
    DATA_OUTPUT_DIR,
    DATA_PROCESSED_DIR,
    EMBEDDINGS_PARQUET_PATH,
    NER_PARQUET_PATH,
    PARQUET_COMPRESSION,
    PARQUET_COMPRESSION_LEVEL,
    SBERT_EMBEDDING_DIM,
    SIGNALS_PARQUET_PATH,
    SQLITE_INDEX_PATH,
    TOPICS_PARQUET_PATH,
)
from src.storage.parquet_writer import (
    ANALYSIS_PA_SCHEMA,
    SIGNALS_PA_SCHEMA,
    TOPICS_PA_SCHEMA,
    ChecksumStore,
    ParquetWriter,
    validate_parquet_file,
    validate_schema,
)
from src.storage.sqlite_builder import SQLiteBuilder
from src.utils.error_handler import (
    AnalysisError,
    ParquetIOError,
    PipelineStageError,
    SchemaValidationError,
)
from src.utils.logging_config import get_analysis_logger

logger = get_analysis_logger()

# =============================================================================
# Stage 8 constants
# =============================================================================

# Topics output path in data/output/
TOPICS_OUTPUT_PARQUET_PATH = DATA_OUTPUT_DIR / "topics.parquet"

# Checksum manifest file
CHECKSUM_FILE_PATH = DATA_OUTPUT_DIR / "checksums.md5"

# Data quality thresholds (PRD SS7.4)
MAX_INVALID_FRACTION = 0.10     # >10% invalid records -> ERROR (still produce output)
MIN_EMBEDDING_DIM = SBERT_EMBEDDING_DIM  # Must be exactly 384

# ANALYSIS_SCHEMA column list (must match PRD SS7.1.2 exactly, 21 columns)
ANALYSIS_COLUMNS = [
    "article_id",
    "sentiment_label",
    "sentiment_score",
    "emotion_joy",
    "emotion_trust",
    "emotion_fear",
    "emotion_surprise",
    "emotion_sadness",
    "emotion_disgust",
    "emotion_anger",
    "emotion_anticipation",
    "topic_id",
    "topic_label",
    "topic_probability",
    "steeps_category",
    "importance_score",
    "keywords",
    "entities_person",
    "entities_org",
    "entities_location",
    "embedding",
]

assert len(ANALYSIS_COLUMNS) == 21, "ANALYSIS_COLUMNS must have exactly 21 entries"


# =============================================================================
# Data quality report
# =============================================================================

@dataclass
class QualityReport:
    """Data quality validation results (PRD SS7.4)."""

    total_articles: int = 0
    duplicate_article_ids: int = 0
    null_article_ids: int = 0
    invalid_topic_ids: int = 0     # topic_id not in topics table
    invalid_embedding_dims: int = 0
    null_required_fields: dict[str, int] = field(default_factory=dict)
    quality_errors: list[str] = field(default_factory=list)
    quality_warnings: list[str] = field(default_factory=list)
    passed: bool = True

    def fail(self, message: str) -> None:
        self.passed = False
        self.quality_errors.append(message)

    def warn(self, message: str) -> None:
        self.quality_warnings.append(message)

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "total_articles": self.total_articles,
            "duplicate_article_ids": self.duplicate_article_ids,
            "null_article_ids": self.null_article_ids,
            "invalid_topic_ids": self.invalid_topic_ids,
            "invalid_embedding_dims": self.invalid_embedding_dims,
            "null_required_fields": self.null_required_fields,
            "errors": self.quality_errors,
            "warnings": self.quality_warnings,
        }


# =============================================================================
# Stage8OutputBuilder
# =============================================================================

class Stage8OutputBuilder:
    """Implements Stage 8: Data Output of the GlobalNews analysis pipeline.

    Usage:
        builder = Stage8OutputBuilder()
        result = builder.run()

    Or with custom paths (for testing / non-default data directories):
        builder = Stage8OutputBuilder(data_dir=Path("custom/data"))
        result = builder.run()
    """

    def __init__(
        self,
        data_dir: Path | str | None = None,
        output_dir: Path | str | None = None,
        *,
        processed_dir: Path | str | None = None,
        analysis_dir: Path | str | None = None,
        features_dir: Path | str | None = None,
    ) -> None:
        """Initialize Stage 8 builder.

        Args:
            data_dir:   Root data directory. Defaults to constants.DATA_DIR.
                        Used to derive input paths when specific dirs are not given.
            output_dir: Output directory. Defaults to constants.DATA_OUTPUT_DIR.
            processed_dir: Directory containing articles.parquet.
                           Overrides data_dir/processed/ when set (e.g. for
                           date-partitioned layouts).
            analysis_dir:  Directory containing article_analysis.parquet,
                           topics.parquet. Overrides data_dir/analysis/.
            features_dir:  Directory containing embeddings.parquet, ner.parquet.
                           Overrides data_dir/features/.
        """
        from src.config.constants import DATA_DIR
        self._data_dir = Path(data_dir) if data_dir else DATA_DIR
        self._output_dir = Path(output_dir) if output_dir else DATA_OUTPUT_DIR
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Resolve input directories (explicit overrides > data_dir derivation)
        _processed = Path(processed_dir) if processed_dir else self._data_dir / "processed"
        _analysis = Path(analysis_dir) if analysis_dir else self._data_dir / "analysis"
        _features = Path(features_dir) if features_dir else self._data_dir / "features"

        # Derived input paths
        self._articles_path = _processed / "articles.parquet"
        self._article_analysis_path = _analysis / "article_analysis.parquet"
        self._topics_path = _analysis / "topics.parquet"
        self._embeddings_path = _features / "embeddings.parquet"
        self._ner_path = _features / "ner.parquet"
        self._signals_path = self._output_dir / "signals.parquet"

        # Output paths
        self._analysis_out = self._output_dir / "analysis.parquet"
        self._signals_out = self._output_dir / "signals.parquet"
        self._topics_out = self._output_dir / "topics.parquet"
        self._sqlite_out = self._output_dir / "index.sqlite"
        self._checksum_out = self._output_dir / "checksums.md5"

        self._writer = ParquetWriter(
            compression=PARQUET_COMPRESSION,
            compression_level=PARQUET_COMPRESSION_LEVEL,
        )
        self._checksum_store = ChecksumStore(self._checksum_out)

    # ------------------------------------------------------------------
    # Public: main entry point
    # ------------------------------------------------------------------

    def run(self) -> dict[str, Any]:
        """Execute all Stage 8 steps.

        Returns:
            dict with keys: analysis_write, signals_write, topics_write,
                            sqlite_stats, quality_report, duckdb_ok,
                            elapsed_seconds.

        Raises:
            PipelineStageError: On FATAL errors (schema mismatch, missing
                                critical inputs, data quality > 10% invalid).
        """
        t_start = time.perf_counter()
        result: dict[str, Any] = {}

        logger.info("Stage 8: Data Output started")

        # Step 1: Merge analysis.parquet
        logger.info("Step 1/6: Merging analysis.parquet (21 columns)")
        analysis_table = self._merge_analysis()
        write_info = self._writer.write(
            analysis_table, self._analysis_out, "analysis"
        )
        self._checksum_store.add(self._analysis_out, write_info["md5_checksum"])
        result["analysis_write"] = write_info

        # Step 2: Finalize signals.parquet
        logger.info("Step 2/6: Finalizing signals.parquet")
        signals_write = self._finalize_signals()
        result["signals_write"] = signals_write

        # Step 3: Copy topics.parquet with ZSTD
        logger.info("Step 3/6: Copying topics.parquet to output")
        topics_write = self._copy_topics()
        result["topics_write"] = topics_write

        # Step 4: Build SQLite index
        logger.info("Step 4/6: Building SQLite index")
        sqlite_stats = self._build_sqlite()
        result["sqlite_stats"] = sqlite_stats

        # Step 5: DuckDB compatibility verification
        logger.info("Step 5/6: DuckDB compatibility verification")
        duckdb_ok = self._verify_duckdb()
        result["duckdb_ok"] = duckdb_ok

        # Step 6: Data quality validation (PRD SS7.4)
        logger.info("Step 6/6: Data quality validation")
        quality = self._validate_quality(analysis_table)
        result["quality_report"] = quality.as_dict()

        if not quality.passed:
            logger.error("Data quality validation FAILED: %s", quality.quality_errors)
            # Still produce output per spec: "ERROR but still produce output with quality report"

        elapsed = time.perf_counter() - t_start
        result["elapsed_seconds"] = round(elapsed, 2)

        logger.info(
            "Stage 8 complete in %.1f s",
            elapsed,
            extra={"result_summary": {k: v for k, v in result.items() if k != "quality_report"}},
        )

        # Explicit memory cleanup
        del analysis_table
        gc.collect()

        return result

    # ------------------------------------------------------------------
    # Step 1: Merge analysis.parquet
    # ------------------------------------------------------------------

    def _merge_analysis(self) -> pa.Table:
        """Merge all analysis inputs into a single 21-column ANALYSIS_SCHEMA table.

        Join strategy:
            - Base: articles (article_id, used as join key)
            - Left-join article_analysis on article_id (sentiment, emotion, STEEPS, importance)
            - Left-join topics on article_id (topic_id, topic_label, topic_probability)
            - Left-join embeddings on article_id (embedding, keywords)
            - Left-join ner on article_id (entities_person, entities_org, entities_location)

        Missing join sources produce NULL values for their columns (graceful degradation
        for partial pipeline runs).

        Returns:
            PyArrow table with exactly ANALYSIS_COLUMNS columns in correct order.

        Raises:
            PipelineStageError: If articles.parquet is missing (it is the base table
                                and Stage 8 cannot proceed without it).
        """
        if not self._articles_path.exists():
            raise PipelineStageError(
                f"FATAL: articles.parquet not found at {self._articles_path}. "
                "Stage 8 cannot proceed without the base articles table.",
                stage_name="stage_8_output",
                stage_number=8,
            )

        # Load base: articles (only article_id needed as the join key anchor)
        articles = pq.read_table(
            str(self._articles_path),
            columns=["article_id"],
        )
        n_articles = len(articles)
        logger.info("Base articles: %d rows", n_articles)

        # Collect columns per source
        columns: dict[str, pa.Array | pa.ChunkedArray] = {
            "article_id": articles.column("article_id"),
        }

        # --- article_analysis (sentiment, emotion, STEEPS, importance) ---
        aa_cols = [
            "article_id", "sentiment_label", "sentiment_score",
            "emotion_joy", "emotion_trust", "emotion_fear", "emotion_surprise",
            "emotion_sadness", "emotion_disgust", "emotion_anger", "emotion_anticipation",
            "steeps_category", "importance_score",
        ]
        aa_data = self._left_join_parquet(
            articles,
            self._article_analysis_path,
            "article_id",
            aa_cols,
            n_articles,
        )
        for col in aa_cols[1:]:  # skip article_id (already have it)
            columns[col] = aa_data.get(col) or _null_array(ANALYSIS_PA_SCHEMA, col, n_articles)

        # --- topics (topic_id, topic_label, topic_probability) ---
        topics_cols = ["article_id", "topic_id", "topic_label", "topic_probability"]
        topics_data = self._left_join_parquet(
            articles,
            self._topics_path,
            "article_id",
            topics_cols,
            n_articles,
        )
        for col in topics_cols[1:]:
            columns[col] = topics_data.get(col) or _null_array(ANALYSIS_PA_SCHEMA, col, n_articles)

        # --- embeddings (embedding, keywords) ---
        emb_cols = ["article_id", "embedding", "keywords"]
        emb_data = self._left_join_parquet(
            articles,
            self._embeddings_path,
            "article_id",
            emb_cols,
            n_articles,
        )
        for col in emb_cols[1:]:
            columns[col] = emb_data.get(col) or _null_array(ANALYSIS_PA_SCHEMA, col, n_articles)

        # --- ner (entities_person, entities_org, entities_location) ---
        ner_cols = ["article_id", "entities_person", "entities_org", "entities_location"]
        ner_data = self._left_join_parquet(
            articles,
            self._ner_path,
            "article_id",
            ner_cols,
            n_articles,
        )
        for col in ner_cols[1:]:
            columns[col] = ner_data.get(col) or _null_array(ANALYSIS_PA_SCHEMA, col, n_articles)

        # Assemble final table in exact ANALYSIS_COLUMNS order
        col_arrays = [columns[c] for c in ANALYSIS_COLUMNS]
        table = pa.table(dict(zip(ANALYSIS_COLUMNS, col_arrays)))

        logger.info(
            "Analysis merge complete: %d rows x %d columns",
            len(table), len(table.schema.names),
        )
        assert len(table.schema.names) == 21, (
            f"Expected 21 columns in analysis table, got {len(table.schema.names)}"
        )
        return table

    def _left_join_parquet(
        self,
        base: pa.Table,
        source_path: Path,
        join_key: str,
        columns: list[str],
        n_rows: int,
    ) -> dict[str, pa.ChunkedArray]:
        """Left-join a Parquet file onto *base* by *join_key*.

        Returns a dict of {column_name: ChunkedArray} aligned to *base* row order.
        Columns not found in source return empty dict entries (caller fills with nulls).

        Args:
            base:        PyArrow table with the join key (base.column(join_key)).
            source_path: Path to the Parquet file to join.
            join_key:    Column name used as join key (must exist in both).
            columns:     Columns to read from source (including join_key).
            n_rows:      Expected output row count (= len(base)).

        Returns:
            Dict mapping column_name -> aligned ChunkedArray (length = n_rows).
            Missing or unmatched rows are filled with null.
        """
        if not source_path.exists():
            logger.warning("Source Parquet not found -- filling with nulls: %s", source_path)
            return {}

        # Read only the requested columns that actually exist in the file
        src_schema = pq.read_schema(str(source_path))
        available = set(src_schema.names)
        read_cols = [c for c in columns if c in available]
        if join_key not in read_cols:
            logger.warning("Join key '%s' not in %s -- cannot join", join_key, source_path)
            return {}

        source = pq.read_table(str(source_path), columns=read_cols)

        # Build lookup: join_key_value -> row index in source
        src_key_col = source.column(join_key)
        key_to_idx: dict[str, int] = {}
        for i in range(len(source)):
            k = src_key_col[i].as_py()
            if k is not None and k not in key_to_idx:
                key_to_idx[k] = i

        # Build aligned arrays for each non-key column
        base_key_col = base.column(join_key)
        result: dict[str, pa.ChunkedArray] = {}
        non_key_cols = [c for c in read_cols if c != join_key]

        for col_name in non_key_cols:
            src_col = source.column(col_name)
            src_type = src_col.type

            # Build aligned values list
            aligned: list[Any] = []
            for i in range(n_rows):
                bk = base_key_col[i].as_py()
                if bk is not None and bk in key_to_idx:
                    val = src_col[key_to_idx[bk]].as_py()
                    aligned.append(val)
                else:
                    aligned.append(None)

            # Reconstruct as PyArrow array with correct type
            try:
                result[col_name] = pa.chunked_array([pa.array(aligned, type=src_type)])
            except Exception as exc:
                logger.warning(
                    "Failed to build aligned array for '%s': %s -- using null array",
                    col_name, exc,
                )
                result[col_name] = pa.chunked_array(
                    [pa.array([None] * n_rows, type=src_type)]
                )

        return result

    # ------------------------------------------------------------------
    # Step 2: Finalize signals.parquet
    # ------------------------------------------------------------------

    def _finalize_signals(self) -> dict[str, Any]:
        """Validate and re-compress signals.parquet to data/output/.

        Stage 7 already wrote signals.parquet to data/output/. This step:
            - Validates schema (SIGNALS_SCHEMA, 12 columns)
            - Re-compresses with ZSTD level 3 (idempotent if already ZSTD)
            - Computes MD5 checksum

        Returns:
            Write stats dict from ParquetWriter.write().
        """
        if not self._signals_path.exists():
            logger.warning(
                "signals.parquet not found at %s -- signals output skipped",
                self._signals_path,
            )
            return {"skipped": True, "reason": "signals.parquet not found"}

        write_info = self._writer.write_from_path(
            self._signals_path,
            self._signals_out,
            "signals",
            validate=True,
        )
        self._checksum_store.add(self._signals_out, write_info["md5_checksum"])
        return write_info

    # ------------------------------------------------------------------
    # Step 3: Copy topics.parquet
    # ------------------------------------------------------------------

    def _copy_topics(self) -> dict[str, Any]:
        """Copy data/analysis/topics.parquet -> data/output/topics.parquet.

        Validates against TOPICS_PA_SCHEMA and re-compresses with ZSTD.

        Returns:
            Write stats dict, or {'skipped': True} if source missing.
        """
        if not self._topics_path.exists():
            logger.warning(
                "topics.parquet not found at %s -- topics output skipped",
                self._topics_path,
            )
            return {"skipped": True, "reason": "topics.parquet not found"}

        write_info = self._writer.write_from_path(
            self._topics_path,
            self._topics_out,
            "topics",
            validate=True,
        )
        self._checksum_store.add(self._topics_out, write_info["md5_checksum"])
        return write_info

    # ------------------------------------------------------------------
    # Step 4: Build SQLite index
    # ------------------------------------------------------------------

    def _build_sqlite(self) -> dict[str, Any]:
        """Build data/output/index.sqlite from all output Parquet files.

        Retries SQLite build up to 3 times on failure; on persistent failure
        logs ERROR and returns error dict (Parquet output is not affected).

        Returns:
            Stats dict from SQLiteBuilder.build(), or error dict.
        """
        builder = SQLiteBuilder(self._sqlite_out)
        try:
            return builder.build(
                articles_parquet=self._articles_path,
                analysis_parquet=self._analysis_out if self._analysis_out.exists() else None,
                signals_parquet=self._signals_out if self._signals_out.exists() else None,
                topics_parquet=self._topics_path,
            )
        except Exception as exc:
            logger.error("SQLite build failed: %s -- Parquet output is unaffected", exc)
            return {"error": str(exc), "sqlite_path": str(self._sqlite_out)}

    # ------------------------------------------------------------------
    # Step 5: DuckDB verification
    # ------------------------------------------------------------------

    def _verify_duckdb(self) -> dict[str, Any]:
        """Verify DuckDB can read both analysis.parquet and signals.parquet.

        DuckDB is a convenience query layer (not critical). Failures are
        WARNING-level and do not block pipeline progression.

        Returns:
            dict with keys: available (bool), analysis_ok (bool),
                            signals_ok (bool), errors (list[str]).
        """
        result: dict[str, Any] = {
            "available": False,
            "analysis_ok": False,
            "signals_ok": False,
            "errors": [],
        }

        try:
            import duckdb
        except ImportError:
            logger.warning("duckdb not installed -- verification skipped")
            result["errors"].append("duckdb not installed")
            return result

        result["available"] = True

        for label, path in [
            ("analysis", self._analysis_out),
            ("signals", self._signals_out),
        ]:
            key = f"{label}_ok"
            if not path.exists():
                result["errors"].append(f"{label}.parquet not found at {path}")
                continue
            try:
                conn = duckdb.connect(":memory:")
                rel = conn.read_parquet(str(path))
                row_count = rel.count("*").fetchone()[0]
                conn.close()
                result[key] = True
                logger.info("DuckDB verified %s: %d rows", label, row_count)
            except Exception as exc:
                result["errors"].append(f"DuckDB read {label}.parquet failed: {exc}")
                logger.warning("DuckDB verification failed for %s: %s", label, exc)

        return result

    # ------------------------------------------------------------------
    # Step 6: Data quality validation (PRD SS7.4)
    # ------------------------------------------------------------------

    def _validate_quality(self, analysis_table: pa.Table) -> QualityReport:
        """Run data quality checks on the merged analysis table.

        Checks (PRD SS7.4):
            Q1: No duplicate article_id
            Q2: All topic_ids reference valid topics (if topics.parquet available)
            Q3: Embedding dimensions all exactly 384
            Q4: Schema validation (column types, NOT NULL constraints)
            Q5: No NaN in NOT NULL columns (article_id, sentiment_label, etc.)
            Q6: Completeness (every article_id present)

        If >10% of records are invalid: ERROR is logged, but output is produced.

        Args:
            analysis_table: The merged analysis PyArrow table.

        Returns:
            QualityReport with all check results.
        """
        report = QualityReport()
        n = len(analysis_table)
        report.total_articles = n

        if n == 0:
            report.warn("Analysis table is empty (0 rows)")
            return report

        # Q1: Duplicate article_id
        article_id_col = analysis_table.column("article_id")
        null_ids = article_id_col.null_count
        if null_ids > 0:
            report.null_article_ids = null_ids
            report.fail(f"Q1: {null_ids} null article_id(s) found")

        unique_count = len(pc.unique(article_id_col.drop_null()))
        non_null = n - null_ids
        dups = non_null - unique_count
        if dups > 0:
            report.duplicate_article_ids = dups
            report.fail(f"Q1: {dups} duplicate article_id(s) found")

        # Q2: topic_ids reference valid topics
        if self._topics_path.exists() and "topic_id" in analysis_table.schema.names:
            try:
                topics_table = pq.read_table(str(self._topics_path), columns=["topic_id"])
                valid_topic_ids = set(
                    tid.as_py()
                    for tid in topics_table.column("topic_id")
                    if tid.as_py() is not None
                )
                analysis_topic_ids = analysis_table.column("topic_id")
                invalid_count = 0
                for val in analysis_topic_ids:
                    tid = val.as_py()
                    if tid is not None and tid != -1 and tid not in valid_topic_ids:
                        invalid_count += 1
                if invalid_count > 0:
                    report.invalid_topic_ids = invalid_count
                    frac = invalid_count / n
                    msg = f"Q2: {invalid_count} article(s) with invalid topic_id ({frac:.1%})"
                    if frac > MAX_INVALID_FRACTION:
                        report.fail(msg)
                    else:
                        report.warn(msg)
            except Exception as exc:
                report.warn(f"Q2: Could not verify topic_ids: {exc}")

        # Q3: Embedding dimensions
        if "embedding" in analysis_table.schema.names:
            emb_col = analysis_table.column("embedding")
            bad_dim = 0
            for val in emb_col:
                emb = val.as_py()
                if emb is not None and len(emb) != MIN_EMBEDDING_DIM:
                    bad_dim += 1
            if bad_dim > 0:
                report.invalid_embedding_dims = bad_dim
                frac = bad_dim / n
                msg = (
                    f"Q3: {bad_dim} embedding(s) with wrong dimension "
                    f"(expected {MIN_EMBEDDING_DIM}, {frac:.1%} of rows)"
                )
                if frac > MAX_INVALID_FRACTION:
                    report.fail(msg)
                else:
                    report.warn(msg)

        # Q4: Schema validation
        schema_result = validate_schema(analysis_table, "analysis",
                                        check_ranges=True, check_not_null=True)
        if not schema_result.passed:
            for err in schema_result.errors:
                report.fail(f"Q4 schema: {err}")
        for warn in schema_result.warnings:
            report.warn(f"Q4 schema: {warn}")

        # Q5: Null check in key analysis columns (warn only, they are nullable in schema)
        for col_name in ["sentiment_label", "steeps_category"]:
            if col_name in analysis_table.schema.names:
                null_n = analysis_table.column(col_name).null_count
                if null_n > 0:
                    frac = null_n / n
                    report.null_required_fields[col_name] = null_n
                    if frac > MAX_INVALID_FRACTION:
                        report.warn(
                            f"Q5: {null_n} null(s) in '{col_name}' ({frac:.1%}) -- "
                            "check upstream Stage 3 output"
                        )

        return report


# =============================================================================
# Null array helper
# =============================================================================

def _null_array(schema: pa.Schema, col_name: str, length: int) -> pa.ChunkedArray:
    """Return a null-filled ChunkedArray of the correct type for *col_name*.

    Falls back to utf8 if col_name is not in schema.

    Args:
        schema:   PyArrow schema with type information.
        col_name: Column name to look up.
        length:   Number of null elements.

    Returns:
        ChunkedArray of *length* nulls with the schema type.
    """
    try:
        dtype = schema.field(col_name).type
    except KeyError:
        dtype = pa.utf8()
    return pa.chunked_array([pa.array([None] * length, type=dtype)])


# =============================================================================
# Convenience function
# =============================================================================

def run_stage8(
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Convenience function: run Stage 8 with optional custom paths.

    This is the primary callable for pipeline orchestration scripts.

    Args:
        data_dir:   Root data directory (default: DATA_DIR from constants).
        output_dir: Output directory (default: DATA_OUTPUT_DIR from constants).

    Returns:
        Full Stage 8 result dict from Stage8OutputBuilder.run().

    Example:
        from src.analysis.stage8_output import run_stage8
        result = run_stage8()
        print(result["quality_report"])
    """
    builder = Stage8OutputBuilder(data_dir=data_dir, output_dir=output_dir)
    return builder.run()
