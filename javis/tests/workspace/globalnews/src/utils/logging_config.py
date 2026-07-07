"""Structured JSON logging with structlog for the GlobalNews pipeline.

Provides per-module loggers with both console (human-readable) and
file (structured JSON) output. All log entries include timestamps,
module names, and structured key-value pairs for grep-ability.

Usage:
    from src.utils.logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("crawling_started", site_id="chosun", method="rss")
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any

try:
    import structlog
    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False

from src.config.constants import DATA_LOGS_DIR, CRAWL_LOG_PATH, ANALYSIS_LOG_PATH, ERROR_LOG_PATH


class _KwargsLogger(logging.Logger):
    """Logger subclass that accepts structlog-style keyword arguments.

    Many modules use ``logger.info("event", key=value)`` (structlog style)
    but create loggers with ``logging.getLogger()`` (stdlib). Python 3.14's
    ``Logger._log()`` rejects unexpected kwargs. This subclass captures
    kwargs and appends them to the log message as ``key=value`` pairs.
    """

    def _log(
        self,
        level: int,
        msg: object,
        args: Any,
        exc_info: Any = None,
        extra: dict | None = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        **kwargs: Any,
    ) -> None:
        if kwargs:
            kv_str = " ".join(f"{k}={v}" for k, v in kwargs.items())
            msg = f"{msg} {kv_str}"
        super()._log(level, msg, args, exc_info=exc_info, extra=extra,
                      stack_info=stack_info, stacklevel=stacklevel)


# Register globally so logging.getLogger() returns kwargs-tolerant loggers
logging.setLoggerClass(_KwargsLogger)


def _ensure_log_dirs() -> None:
    """Create log directories if they do not exist."""
    DATA_LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _create_file_handler(
    log_path: Path,
    level: int = logging.DEBUG,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Handler:
    """Create a rotating file handler for structured JSON output.

    Args:
        log_path: Path to the log file.
        level: Minimum log level for this handler.
        max_bytes: Maximum file size before rotation (default 10MB).
        backup_count: Number of rotated files to keep.

    Returns:
        Configured RotatingFileHandler.
    """
    _ensure_log_dirs()
    handler = logging.handlers.RotatingFileHandler(
        str(log_path),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)
    formatter = logging.Formatter(
        '{"timestamp":"%(asctime)s","level":"%(levelname)s",'
        '"logger":"%(name)s","message":"%(message)s"}',
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    return handler


def _create_console_handler(level: int = logging.INFO) -> logging.Handler:
    """Create a console handler with human-readable output.

    Args:
        level: Minimum log level for console output.

    Returns:
        Configured StreamHandler.
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)
    return handler


def setup_logging(
    console_level: str = "INFO",
    file_level: str = "DEBUG",
) -> None:
    """Initialize the global logging configuration.

    Sets up both console and file logging. Call once at application startup.

    Args:
        console_level: Log level for console output (INFO, DEBUG, WARNING, ERROR).
        file_level: Log level for file output.
    """
    _ensure_log_dirs()

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Clear existing handlers to avoid duplicates on re-initialization
    root_logger.handlers.clear()

    # Console handler (human-readable)
    root_logger.addHandler(_create_console_handler(getattr(logging, console_level.upper())))

    # File handler for errors (all layers)
    root_logger.addHandler(_create_file_handler(ERROR_LOG_PATH, level=logging.WARNING))

    # Suppress noisy third-party loggers
    for noisy_logger in ("urllib3", "charset_normalizer", "filelock", "httpx"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    if HAS_STRUCTLOG:
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.StackInfoRenderer(),
                structlog.dev.set_exc_info,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.dev.ConsoleRenderer() if sys.stderr.isatty() else structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )


def get_logger(name: str) -> Any:
    """Get a logger for the given module name.

    If structlog is available, returns a structlog bound logger.
    Otherwise, returns a standard library logger.

    Args:
        name: Module name (typically __name__).

    Returns:
        Logger instance.
    """
    if HAS_STRUCTLOG:
        return structlog.get_logger(name)
    return logging.getLogger(name)


def get_crawl_logger() -> Any:
    """Get a logger configured for crawling operations.

    Adds a file handler specifically for crawl.log in addition
    to the global logging configuration.

    Returns:
        Logger for crawling operations.
    """
    logger = logging.getLogger("src.crawling")
    if not any(isinstance(h, logging.handlers.RotatingFileHandler)
               and str(CRAWL_LOG_PATH) in str(getattr(h, "baseFilename", ""))
               for h in logger.handlers):
        logger.addHandler(_create_file_handler(CRAWL_LOG_PATH))
    return get_logger("src.crawling")


def get_analysis_logger() -> Any:
    """Get a logger configured for analysis pipeline operations.

    Adds a file handler specifically for analysis.log.

    Returns:
        Logger for analysis operations.
    """
    logger = logging.getLogger("src.analysis")
    if not any(isinstance(h, logging.handlers.RotatingFileHandler)
               and str(ANALYSIS_LOG_PATH) in str(getattr(h, "baseFilename", ""))
               for h in logger.handlers):
        logger.addHandler(_create_file_handler(ANALYSIS_LOG_PATH))
    return get_logger("src.analysis")
