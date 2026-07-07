"""OfficeMonitor SQLite 데이터베이스"""

import sqlite3
import os
import logging
import threading
from datetime import datetime
from paths import DB_PATH

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    """스레드 안전한 DB 연결 반환"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # 동시 읽기/쓰기 성능
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_lock = threading.Lock()


def execute(sql: str, params: tuple = (), fetch: str = "none"):
    """스레드 안전한 쿼리 실행. fetch: none/one/all"""
    with _lock:
        conn = get_connection()
        try:
            cur = conn.execute(sql, params)
            if fetch == "one":
                result = cur.fetchone()
                conn.commit()
                return result
            elif fetch == "all":
                result = cur.fetchall()
                conn.commit()
                return result
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()


def init_db():
    """DB 스키마 초기화"""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS visitors (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            thumbnail_path  TEXT,
            created_at      TEXT DEFAULT (datetime('now','localtime')),
            updated_at      TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS face_embeddings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            visitor_id  INTEGER NOT NULL REFERENCES visitors(id) ON DELETE CASCADE,
            embedding   BLOB NOT NULL,
            quality     REAL DEFAULT 0.0,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS visit_logs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            visitor_id      INTEGER REFERENCES visitors(id) ON DELETE SET NULL,
            visitor_name    TEXT,
            timestamp       TEXT DEFAULT (datetime('now','localtime')),
            confidence      REAL,
            thumbnail_path  TEXT,
            is_registered   INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS pending_faces (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            image_path  TEXT NOT NULL,
            embedding   BLOB NOT NULL,
            captured_at TEXT DEFAULT (datetime('now','localtime')),
            status      TEXT DEFAULT 'pending'
        );

        CREATE TABLE IF NOT EXISTS snapshots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path   TEXT NOT NULL,
            timestamp   TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS recordings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path   TEXT NOT NULL,
            start_time  TEXT,
            end_time    TEXT,
            size_bytes  INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_visit_logs_timestamp ON visit_logs(timestamp);
        CREATE INDEX IF NOT EXISTS idx_visit_logs_visitor ON visit_logs(visitor_id);
        CREATE INDEX IF NOT EXISTS idx_embeddings_visitor ON face_embeddings(visitor_id);
    """)
    # 기존 DB 마이그레이션 (컬럼 존재 시 무시)
    migrations = [
        "ALTER TABLE visitors ADD COLUMN thumbnail_path TEXT",
        "ALTER TABLE face_embeddings ADD COLUMN quality REAL DEFAULT 0.0",
        "ALTER TABLE visitors ADD COLUMN status TEXT DEFAULT 'active'",
    ]
    for stmt in migrations:
        try:
            conn.execute(stmt)
            logger.info("마이그레이션 적용: %s", stmt)
        except Exception as e:
            if "duplicate column" not in str(e).lower():
                logger.warning("마이그레이션 실패: %s — %s", stmt, e)
    conn.commit()
    conn.close()


# ── 방문자 (known faces) ──

def add_visitor(name: str) -> int:
    return execute("INSERT INTO visitors (name) VALUES (?)", (name,))


def find_visitor_by_name(name: str):
    """이름으로 기존 방문자 검색 (정확히 일치)"""
    return execute("SELECT * FROM visitors WHERE name=?", (name,), fetch="one")


def get_visitor(visitor_id: int):
    return execute("SELECT * FROM visitors WHERE id=?", (visitor_id,), fetch="one")


def get_all_visitors():
    return execute("SELECT * FROM visitors WHERE COALESCE(status,'active')='active' ORDER BY name", fetch="all")


def get_deleted_visitors():
    return execute("SELECT * FROM visitors WHERE status='deleted' ORDER BY name", fetch="all")


def update_visitor_name(visitor_id: int, name: str):
    execute("UPDATE visitors SET name=?, updated_at=datetime('now','localtime') WHERE id=?",
            (name, visitor_id))


def update_visitor_thumbnail(visitor_id: int, path: str):
    execute("UPDATE visitors SET thumbnail_path=?, updated_at=datetime('now','localtime') WHERE id=?",
            (path, visitor_id))


def delete_visitor(visitor_id: int):
    """소프트 삭제 (휴지통으로 이동)"""
    execute("UPDATE visitors SET status='deleted', updated_at=datetime('now','localtime') WHERE id=?",
            (visitor_id,))


def restore_visitor(visitor_id: int):
    """휴지통에서 복구"""
    execute("UPDATE visitors SET status='active', updated_at=datetime('now','localtime') WHERE id=?",
            (visitor_id,))


def hard_delete_visitor(visitor_id: int):
    """완전 삭제 (DB에서 제거)"""
    execute("DELETE FROM visitors WHERE id=?", (visitor_id,))


# ── 얼굴 임베딩 ──

def add_embedding(visitor_id: int, embedding_bytes: bytes, quality: float = 0.0) -> int:
    return execute("INSERT INTO face_embeddings (visitor_id, embedding, quality) VALUES (?,?,?)",
                   (visitor_id, embedding_bytes, float(quality)))


def get_lowest_quality_embedding(visitor_id: int):
    """가장 품질이 낮은 임베딩 반환"""
    return execute(
        "SELECT id, quality FROM face_embeddings WHERE visitor_id=? ORDER BY quality ASC LIMIT 1",
        (visitor_id,), fetch="one")


def delete_embedding(emb_id: int):
    execute("DELETE FROM face_embeddings WHERE id=?", (emb_id,))


def get_embeddings_for_visitor(visitor_id: int):
    return execute("SELECT * FROM face_embeddings WHERE visitor_id=?",
                   (visitor_id,), fetch="all")


def get_all_embeddings():
    return execute("""
        SELECT e.id, e.visitor_id, e.embedding, v.name
        FROM face_embeddings e JOIN visitors v ON e.visitor_id = v.id
        WHERE COALESCE(v.status, 'active') = 'active'
    """, fetch="all")


# ── 방문 로그 ──

def add_visit_log(visitor_id, visitor_name: str, confidence: float,
                  thumbnail_path: str = None, is_registered: bool = True) -> int:
    return execute(
        "INSERT INTO visit_logs (visitor_id, visitor_name, confidence, thumbnail_path, is_registered) VALUES (?,?,?,?,?)",
        (visitor_id, visitor_name, confidence, thumbnail_path, 1 if is_registered else 0))


def clear_today_visits():
    """오늘 방문 로그 삭제"""
    today = datetime.now().strftime("%Y-%m-%d")
    return execute("DELETE FROM visit_logs WHERE timestamp LIKE ?", (f"{today}%",))


def get_today_visits():
    today = datetime.now().strftime("%Y-%m-%d")
    return execute(
        "SELECT * FROM visit_logs WHERE timestamp LIKE ? ORDER BY timestamp DESC",
        (f"{today}%",), fetch="all")


def get_visits_by_date(date_str: str):
    return execute(
        "SELECT * FROM visit_logs WHERE timestamp LIKE ? ORDER BY timestamp DESC",
        (f"{date_str}%",), fetch="all")


def get_visit_stats(days: int = 7):
    return execute("""
        SELECT date(timestamp) as day, COUNT(*) as cnt,
               SUM(is_registered) as registered,
               COUNT(*) - SUM(is_registered) as unregistered
        FROM visit_logs
        WHERE timestamp >= datetime('now','localtime',?)
        GROUP BY date(timestamp)
        ORDER BY day
    """, (f"-{days} days",), fetch="all")


def get_hourly_stats(date_str: str = None):
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    return execute("""
        SELECT strftime('%H', timestamp) as hour, COUNT(*) as cnt
        FROM visit_logs WHERE timestamp LIKE ?
        GROUP BY hour ORDER BY hour
    """, (f"{date_str}%",), fetch="all")


def get_top_visitors(limit: int = 10):
    return execute("""
        SELECT visitor_name, COUNT(*) as visit_count,
               MAX(timestamp) as last_visit
        FROM visit_logs WHERE is_registered=1
        GROUP BY visitor_id ORDER BY visit_count DESC LIMIT ?
    """, (limit,), fetch="all")


# ── 미등록 캡처 (pending_faces) ──

def add_pending_face(image_path: str, embedding_bytes: bytes) -> int:
    return execute(
        "INSERT INTO pending_faces (image_path, embedding) VALUES (?,?)",
        (image_path, embedding_bytes))


def get_pending_faces(status: str = "pending"):
    return execute(
        "SELECT * FROM pending_faces WHERE status=? ORDER BY captured_at DESC",
        (status,), fetch="all")


def get_pending_face(face_id: int):
    return execute("SELECT * FROM pending_faces WHERE id=?", (face_id,), fetch="one")


def soft_delete_pending_face(face_id: int):
    execute("UPDATE pending_faces SET status='deleted' WHERE id=?", (face_id,))


def restore_pending_face(face_id: int):
    execute("UPDATE pending_faces SET status='pending' WHERE id=?", (face_id,))


def hard_delete_pending_face(face_id: int):
    execute("DELETE FROM pending_faces WHERE id=?", (face_id,))


def remove_pending_face(face_id: int):
    """등록 완료 후 제거"""
    execute("DELETE FROM pending_faces WHERE id=?", (face_id,))


# ── 스냅샷 ──

def add_snapshot(file_path: str) -> int:
    return execute("INSERT INTO snapshots (file_path) VALUES (?)", (file_path,))


# ── 녹화 ──

def add_recording(file_path: str, start_time: str) -> int:
    return execute("INSERT INTO recordings (file_path, start_time) VALUES (?,?)",
                   (file_path, start_time))


def finish_recording(rec_id: int, size_bytes: int):
    execute("UPDATE recordings SET end_time=datetime('now','localtime'), size_bytes=? WHERE id=?",
            (size_bytes, rec_id))


# ── 정리 ──

_ALLOWED_TABLES = {"visit_logs", "snapshots", "recordings", "pending_faces"}


def get_old_records(table: str, days: int):
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"허용되지 않는 테이블: {table}")
    return execute(
        f"SELECT * FROM {table} WHERE timestamp < datetime('now','localtime',?)",
        (f"-{days} days",), fetch="all")


def delete_old_records(table: str, days: int):
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"허용되지 않는 테이블: {table}")
    execute(f"DELETE FROM {table} WHERE timestamp < datetime('now','localtime',?)",
            (f"-{days} days",))
