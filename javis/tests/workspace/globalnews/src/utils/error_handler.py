"""Error handling: retry decorators, exception hierarchy, and Circuit Breaker.

Provides:
    - Custom exception hierarchy for crawling and analysis errors
    - Retry decorator with exponential backoff and jitter
    - Circuit Breaker pattern (Closed -> Open -> Half-Open states)

Reference: Step 5 Architecture Blueprint, Section 4a (Error Handling Contract).
"""

import enum
import functools
import logging
import random
import threading
import time
from typing import Any, Callable, TypeVar

from src.config.constants import (
    MAX_RETRIES,
    BACKOFF_FACTOR,
    BACKOFF_BASE_SECONDS,
    BACKOFF_MAX_SECONDS,
    RETRY_STATUS_CODES,
    CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS,
    CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS,
)

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


# =============================================================================
# Exception Hierarchy
# =============================================================================

class GlobalNewsError(Exception):
    """Base exception for all GlobalNews system errors."""

    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.context = context or {}


# Crawling Layer Errors
class CrawlError(GlobalNewsError):
    """Base exception for crawling operations."""
    pass


class NetworkError(CrawlError):
    """HTTP request failure (timeout, connection error, bad status)."""

    def __init__(self, message: str, status_code: int | None = None,
                 url: str = "", **kwargs: Any) -> None:
        super().__init__(message, context={"status_code": status_code, "url": url, **kwargs})
        self.status_code = status_code
        self.url = url


class RateLimitError(CrawlError):
    """Rate limit exceeded (HTTP 429 or Crawl-delay violation)."""

    def __init__(self, message: str, retry_after: float | None = None,
                 site_id: str = "", **kwargs: Any) -> None:
        super().__init__(message, context={"retry_after": retry_after, "site_id": site_id, **kwargs})
        self.retry_after = retry_after
        self.site_id = site_id


class BlockDetectedError(CrawlError):
    """Bot detection triggered (CAPTCHA, 403, fingerprint rejection)."""

    def __init__(self, message: str, block_type: str = "unknown",
                 site_id: str = "", **kwargs: Any) -> None:
        super().__init__(message, context={"block_type": block_type, "site_id": site_id, **kwargs})
        self.block_type = block_type
        self.site_id = site_id


class ParseError(CrawlError):
    """HTML/RSS/Sitemap parsing failure."""

    def __init__(self, message: str, url: str = "",
                 selector: str = "", **kwargs: Any) -> None:
        super().__init__(message, context={"url": url, "selector": selector, **kwargs})
        self.url = url
        self.selector = selector


class EncodingError(CrawlError):
    """Character encoding detection or conversion failure."""

    def __init__(self, message: str, detected_encoding: str = "",
                 target_encoding: str = "utf-8", **kwargs: Any) -> None:
        super().__init__(message, context={
            "detected_encoding": detected_encoding,
            "target_encoding": target_encoding,
            **kwargs,
        })
        self.detected_encoding = detected_encoding
        self.target_encoding = target_encoding


# Analysis Layer Errors
class AnalysisError(GlobalNewsError):
    """Base exception for analysis pipeline operations."""
    pass


class PipelineStageError(AnalysisError):
    """A pipeline stage failed to complete."""

    def __init__(self, message: str, stage_name: str = "",
                 stage_number: int = 0, **kwargs: Any) -> None:
        super().__init__(message, context={"stage_name": stage_name, "stage_number": stage_number, **kwargs})
        self.stage_name = stage_name
        self.stage_number = stage_number


class ModelLoadError(AnalysisError):
    """NLP model failed to load or initialize."""

    def __init__(self, message: str, model_name: str = "", **kwargs: Any) -> None:
        super().__init__(message, context={"model_name": model_name, **kwargs})
        self.model_name = model_name


class SchemaValidationError(AnalysisError):
    """Parquet or data schema validation failure."""

    def __init__(self, message: str, expected_columns: list[str] | None = None,
                 actual_columns: list[str] | None = None, **kwargs: Any) -> None:
        super().__init__(message, context={
            "expected_columns": expected_columns or [],
            "actual_columns": actual_columns or [],
            **kwargs,
        })


class MemoryLimitError(AnalysisError):
    """Memory usage exceeded the configured limit."""

    def __init__(self, message: str, current_gb: float = 0.0,
                 limit_gb: float = 0.0, **kwargs: Any) -> None:
        super().__init__(message, context={"current_gb": current_gb, "limit_gb": limit_gb, **kwargs})


# Storage Layer Errors
class StorageError(GlobalNewsError):
    """Base exception for storage operations."""
    pass


class ParquetIOError(StorageError):
    """Parquet read or write failure."""
    pass


class SQLiteError(StorageError):
    """SQLite operation failure."""
    pass


# =============================================================================
# Retry Decorator with Exponential Backoff
# =============================================================================

def retry_with_backoff(
    max_retries: int = MAX_RETRIES,
    backoff_factor: float = BACKOFF_FACTOR,
    base_seconds: float = BACKOFF_BASE_SECONDS,
    max_seconds: float = BACKOFF_MAX_SECONDS,
    retryable_exceptions: tuple[type[Exception], ...] = (NetworkError, RateLimitError, ConnectionError, TimeoutError),
    retryable_status_codes: set[int] | None = None,
    jitter: bool = True,
) -> Callable[[F], F]:
    """Decorator for automatic retry with exponential backoff.

    Implements the retry strategy from Step 5, Section 4a:
    Level 1 network guard with 5-retry exponential backoff.

    Backoff formula: delay = min(base * factor^attempt + jitter, max_seconds)

    Args:
        max_retries: Maximum number of retry attempts.
        backoff_factor: Exponential factor for delay calculation.
        base_seconds: Base delay in seconds.
        max_seconds: Maximum delay cap in seconds.
        retryable_exceptions: Exception types that trigger retry.
        retryable_status_codes: HTTP status codes that trigger retry.
        jitter: Whether to add random jitter to prevent thundering herd.

    Returns:
        Decorated function with retry behavior.
    """
    if retryable_status_codes is None:
        retryable_status_codes = RETRY_STATUS_CODES

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    # Check if NetworkError with non-retryable status code
                    if isinstance(e, NetworkError) and e.status_code is not None:
                        if e.status_code not in retryable_status_codes:
                            raise

                    if attempt >= max_retries:
                        logger.error(
                            "Max retries exhausted",
                            extra={"function": func.__name__, "attempts": attempt + 1, "error": str(e)},
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(base_seconds * (backoff_factor ** attempt), max_seconds)
                    if jitter:
                        delay += random.uniform(0, delay * 0.25)

                    # Handle RateLimitError with explicit retry_after
                    if isinstance(e, RateLimitError) and e.retry_after is not None:
                        delay = max(delay, e.retry_after)

                    logger.warning(
                        "Retrying after error",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "delay_seconds": round(delay, 2),
                            "error": str(e),
                        },
                    )
                    time.sleep(delay)

            # Should not reach here, but just in case
            if last_exception is not None:
                raise last_exception
            raise RuntimeError(f"Retry logic error in {func.__name__}")

        return wrapper  # type: ignore[return-value]
    return decorator


# =============================================================================
# Circuit Breaker Pattern
# =============================================================================

class CircuitState(enum.Enum):
    """Circuit Breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject all calls
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit Breaker pattern implementation for crawling operations.

    State transitions:
        CLOSED -> OPEN: after failure_threshold consecutive failures
        OPEN -> HALF_OPEN: after recovery_timeout seconds
        HALF_OPEN -> CLOSED: after half_open_max_calls successes
        HALF_OPEN -> OPEN: on any failure

    Thread-safe: uses a lock for state transitions.

    Args:
        name: Identifier for this circuit breaker (e.g., site_id).
        failure_threshold: Failures before opening circuit.
        recovery_timeout: Seconds before attempting recovery.
        half_open_max_calls: Successes needed to close circuit.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        recovery_timeout: float = CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS,
        half_open_max_calls: int = CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Current circuit state, considering time-based transitions."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    logger.info(
                        "Circuit breaker half-open",
                        extra={"circuit_name": self.name, "elapsed_seconds": round(elapsed, 1)},
                    )
            return self._state

    def is_call_allowed(self) -> bool:
        """Check if a call should be allowed through the circuit.

        Returns:
            True if the call should proceed, False if circuit is open.
        """
        current_state = self.state
        if current_state == CircuitState.CLOSED:
            return True
        if current_state == CircuitState.HALF_OPEN:
            return True
        return False  # OPEN

    def _maybe_transition_to_half_open(self) -> None:
        """Check time-based OPEN -> HALF_OPEN transition (must hold lock)."""
        if self._state == CircuitState.OPEN:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0

    def record_success(self) -> None:
        """Record a successful call. May transition HALF_OPEN -> CLOSED."""
        with self._lock:
            self._maybe_transition_to_half_open()
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info("Circuit breaker closed (recovered)", extra={"circuit_name": self.name})
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call. May transition CLOSED -> OPEN or HALF_OPEN -> OPEN."""
        with self._lock:
            self._maybe_transition_to_half_open()
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning("Circuit breaker re-opened", extra={"circuit_name": self.name})
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    logger.warning(
                        "Circuit breaker opened",
                        extra={"circuit_name": self.name, "failures": self._failure_count},
                    )

    def reset(self) -> None:
        """Force reset circuit to CLOSED state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0

    def force_half_open(self) -> None:
        """Force circuit to HALF_OPEN state for immediate probe.

        Used by the Crawling Absolute Principle (크롤링 절대 원칙):
        when circuit is OPEN, bypass the recovery_timeout and immediately
        allow a probe request with escalated anti-block strategy.
        """
        with self._lock:
            if self._state == CircuitState.OPEN:
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
                logger.info(
                    "Circuit breaker force-half-opened (never-abandon policy)",
                    extra={"circuit_name": self.name},
                )

    def __repr__(self) -> str:
        return (f"CircuitBreaker(name={self.name!r}, state={self._state.value}, "
                f"failures={self._failure_count})")
