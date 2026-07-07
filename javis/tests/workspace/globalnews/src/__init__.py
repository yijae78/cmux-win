"""GlobalNews Crawling & Analysis System.

A staged monolith that crawls 116 international news sites,
processes articles through an 8-stage NLP analysis pipeline,
and produces structured Parquet/SQLite output for social trend research.

Architecture: Staged Monolith (Python 3.12)
Runtime: MacBook M2 Pro 16GB, 20GB memory budget
Output: Parquet (ZSTD) + SQLite (FTS5 + vec)
"""

__version__ = "0.1.0"
