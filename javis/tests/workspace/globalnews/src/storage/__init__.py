"""Storage Layer: Parquet/SQLite/DuckDB read-write abstraction.

Handles all persistent data operations:
    - Parquet I/O with ZSTD compression and schema validation
    - SQLite FTS5 full-text search index management
    - sqlite-vec vector similarity search
    - DuckDB query interface for ad-hoc analysis

Modules:
    parquet_io       - Parquet read/write with schema enforcement
    sqlite_manager   - SQLite FTS5 + vec index management
    duckdb_query     - DuckDB query interface
    schema_validator - Runtime schema validation for Parquet/SQLite
"""
