"""NetworkGuard: Resilient HTTP client with retry logic and rate limiting.

Provides a unified ``fetch()`` interface that all crawling modules use for
HTTP requests. Integrates with:
    - ``src/utils/error_handler.py`` for retry decorator and circuit breaker
    - ``src/config/constants.py`` for timeout and retry constants
    - ``src/utils/logging_config.py`` for structured logging

Features:
    - 5-retry exponential backoff (base=2s, max=30s, jitter)
    - Per-site rate limiting respecting ``rate_limit_seconds`` from sources.yaml
    - Circuit Breaker pattern (per-site) for failing endpoints
    - Response validation (status codes, content type, empty body detection)
    - Structured logging of every request with timing
    - Error classification: retriable (5xx, timeout, connection) vs non-retriable (4xx)

Reference: Step 5 Architecture Blueprint, Section 4a.
"""

from __future__ import annotations

import random
import time
import threading
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

import httpx

from src.config.constants import (
    MAX_RETRIES,
    BACKOFF_BASE_SECONDS,
    BACKOFF_FACTOR,
    BACKOFF_MAX_SECONDS,
    RETRY_STATUS_CODES,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_RATE_LIMIT_SECONDS,
)
from src.utils.error_handler import (
    NetworkError,
    RateLimitError,
    BlockDetectedError,
    CircuitBreaker,
    CircuitState,
)
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response wrapper
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FetchResponse:
    """Wrapper for HTTP response data returned by NetworkGuard.fetch().

    Attributes:
        url: The final URL after redirects.
        status_code: HTTP status code.
        headers: Response headers as a dict.
        text: Decoded response body text.
        content: Raw response bytes.
        elapsed_seconds: Request duration in seconds.
        encoding: Detected character encoding.
        content_type: Content-Type header value.
    """

    url: str
    status_code: int
    headers: dict[str, str]
    text: str
    content: bytes
    elapsed_seconds: float
    encoding: str
    content_type: str


# ---------------------------------------------------------------------------
# Per-site rate limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """Thread-safe per-site rate limiter.

    Ensures a minimum interval between requests to the same site.
    Supports jitter to avoid synchronized request patterns.

    Args:
        interval_seconds: Minimum seconds between requests.
        jitter_seconds: Random jitter added to interval (0 = no jitter).
    """

    def __init__(self, interval_seconds: float, jitter_seconds: float = 0.0) -> None:
        self._interval = max(interval_seconds, 0.1)
        self._jitter = max(jitter_seconds, 0.0)
        self._last_request_time: float = 0.0
        self._lock = threading.Lock()

    def wait(self) -> float:
        """Block until the rate limit interval has elapsed.

        H-5 fix: calculates wait time inside lock, then sleeps OUTSIDE lock
        to avoid blocking other threads during the sleep period.

        Returns:
            The actual wait time in seconds (0.0 if no wait was needed).
        """
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            required_wait = self._interval - elapsed

            if self._jitter > 0:
                required_wait += random.uniform(0, self._jitter)

            # Reserve the time slot by advancing last_request_time
            if required_wait > 0:
                self._last_request_time = now + required_wait
            else:
                self._last_request_time = now
                return 0.0

        # Sleep OUTSIDE the lock — other threads can compute their own slots
        time.sleep(required_wait)
        return required_wait


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

# Non-retriable HTTP status codes -- request will not be retried
NON_RETRIABLE_STATUS_CODES = frozenset({400, 401, 404, 405, 410, 451})

# Retriable status codes imported from constants: {429, 500, 502, 503, 504}
RETRIABLE_STATUS_CODES = RETRY_STATUS_CODES

# Status codes indicating bot detection
BOT_BLOCK_STATUS_CODES = frozenset({403, 406, 418, 429, 451, 503})


def classify_error(exc: Exception) -> str:
    """Classify an error as retriable or non-retriable.

    Args:
        exc: The exception to classify.

    Returns:
        One of: "retriable", "non_retriable", "rate_limited", "blocked", "unknown".
    """
    if isinstance(exc, RateLimitError):
        return "rate_limited"
    if isinstance(exc, BlockDetectedError):
        return "blocked"
    if isinstance(exc, NetworkError):
        if exc.status_code is not None:
            if exc.status_code in RETRIABLE_STATUS_CODES:
                return "retriable"
            if exc.status_code in NON_RETRIABLE_STATUS_CODES:
                return "non_retriable"
        return "retriable"  # connection errors are retriable
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, ConnectionError, TimeoutError)):
        return "retriable"
    if isinstance(exc, (httpx.HTTPStatusError,)):
        return "non_retriable"
    return "unknown"


def is_retriable_status(status_code: int) -> bool:
    """Check if an HTTP status code is retriable.

    Args:
        status_code: HTTP status code.

    Returns:
        True if the request should be retried.
    """
    return status_code in RETRIABLE_STATUS_CODES


# ---------------------------------------------------------------------------
# NetworkGuard
# ---------------------------------------------------------------------------

class NetworkGuard:
    """Resilient HTTP client with retry logic, rate limiting, and circuit breaker.

    All crawling modules should use this class for HTTP requests instead of
    making direct httpx/requests calls.

    Args:
        timeout_seconds: Default request timeout.
        max_retries: Maximum retry attempts for retriable errors.
        backoff_base: Base delay for exponential backoff.
        backoff_factor: Multiplier for exponential backoff.
        backoff_max: Maximum delay cap.
        default_headers: Headers applied to all requests.
        follow_redirects: Whether to follow HTTP redirects.

    Example::

        guard = NetworkGuard(timeout_seconds=30)
        guard.configure_site("chosun", rate_limit_seconds=5, jitter_seconds=0)
        response = guard.fetch("https://www.chosun.com/rss", site_id="chosun")
        print(response.text)
    """

    def __init__(
        self,
        timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
        max_retries: int = MAX_RETRIES,
        backoff_base: float = BACKOFF_BASE_SECONDS,
        backoff_factor: float = BACKOFF_FACTOR,
        backoff_max: float = BACKOFF_MAX_SECONDS,
        default_headers: dict[str, str] | None = None,
        follow_redirects: bool = True,
    ) -> None:
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._backoff_factor = backoff_factor
        self._backoff_max = backoff_max
        self._follow_redirects = follow_redirects
        self._default_headers = default_headers or {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

        # Per-site rate limiters: source_id -> RateLimiter
        self._rate_limiters: dict[str, RateLimiter] = {}

        # Per-site circuit breakers: source_id -> CircuitBreaker
        self._circuit_breakers: dict[str, CircuitBreaker] = {}

        # Shared httpx client -- lazily initialized
        self._client: httpx.Client | None = None
        self._client_lock = threading.Lock()

    def _get_client(self) -> httpx.Client:
        """Get or create the shared httpx Client.

        Returns:
            httpx.Client instance.
        """
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    self._client = httpx.Client(
                        timeout=httpx.Timeout(
                            connect=10.0,
                            read=self._timeout,
                            write=10.0,
                            pool=5.0,
                        ),
                        follow_redirects=self._follow_redirects,
                        limits=httpx.Limits(
                            max_connections=50,
                            max_keepalive_connections=25,
                        ),
                    )
        return self._client

    def configure_site(
        self,
        source_id: str,
        rate_limit_seconds: float = DEFAULT_RATE_LIMIT_SECONDS,
        jitter_seconds: float = 0.0,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 300.0,
    ) -> None:
        """Configure rate limiting and circuit breaker for a specific site.

        Should be called once per site before making requests.

        Args:
            source_id: Site identifier (e.g., "chosun").
            rate_limit_seconds: Minimum seconds between requests.
            jitter_seconds: Random jitter added to rate limit interval.
            circuit_breaker_threshold: Consecutive failures before circuit opens.
            circuit_breaker_timeout: Seconds before circuit attempts recovery.
        """
        self._rate_limiters[source_id] = RateLimiter(
            interval_seconds=rate_limit_seconds,
            jitter_seconds=jitter_seconds,
        )
        self._circuit_breakers[source_id] = CircuitBreaker(
            name=source_id,
            failure_threshold=circuit_breaker_threshold,
            recovery_timeout=circuit_breaker_timeout,
        )
        logger.info(
            "site_configured source_id=%s rate_limit=%s jitter=%s",
            source_id, rate_limit_seconds, jitter_seconds,
        )

    def get_circuit_state(self, source_id: str) -> CircuitState:
        """Get the current circuit breaker state for a site.

        Args:
            source_id: Site identifier.

        Returns:
            CircuitState enum value (CLOSED, OPEN, HALF_OPEN).
        """
        cb = self._circuit_breakers.get(source_id)
        if cb is None:
            return CircuitState.CLOSED
        return cb.state

    def fetch(
        self,
        url: str,
        site_id: str = "",
        method: str = "GET",
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        params: dict[str, str] | None = None,
    ) -> FetchResponse:
        """Fetch a URL with retry logic, rate limiting, and circuit breaker.

        This is the primary method that all crawling modules should use.

        Args:
            url: The URL to fetch.
            site_id: Site identifier for rate limiting and circuit breaker.
                Empty string disables per-site features.
            method: HTTP method (GET, POST, HEAD).
            headers: Request-specific headers (merged with defaults).
            timeout: Request-specific timeout override.
            params: URL query parameters.

        Returns:
            FetchResponse with the HTTP response data.

        Raises:
            NetworkError: On non-retriable HTTP errors or after max retries.
            RateLimitError: On HTTP 429 after retry exhaustion.
            BlockDetectedError: On bot detection (403 with suspicious patterns).
            ConnectionError: On connection failures after retry exhaustion.
        """
        # Check circuit breaker
        cb = self._circuit_breakers.get(site_id)
        if cb is not None and not cb.is_call_allowed():
            raise NetworkError(
                f"Circuit breaker OPEN for {site_id}. Requests blocked.",
                status_code=None,
                url=url,
            )

        # Merge headers
        merged_headers = dict(self._default_headers)
        if headers:
            merged_headers.update(headers)

        request_timeout = timeout or self._timeout
        last_exception: Exception | None = None

        for attempt in range(self._max_retries + 1):
            # Rate limiting
            rate_limiter = self._rate_limiters.get(site_id)
            if rate_limiter is not None:
                wait_time = rate_limiter.wait()
                if wait_time > 0 and attempt == 0:
                    logger.debug(
                        "rate_limit_wait site_id=%s wait_seconds=%s",
                        site_id, round(wait_time, 2),
                    )

            start_time = time.monotonic()
            try:
                client = self._get_client()
                response = client.request(
                    method=method,
                    url=url,
                    headers=merged_headers,
                    timeout=request_timeout,
                    params=params,
                )
                elapsed = time.monotonic() - start_time

                # Log the request
                logger.info(
                    "http_request url=%s site_id=%s method=%s status=%s elapsed=%s attempt=%s content_length=%s",
                    url, site_id, method, response.status_code,
                    round(elapsed, 3), attempt + 1, len(response.content),
                )

                # Validate response
                fetch_response = self._validate_response(response, url, elapsed)

                # Record success on circuit breaker
                if cb is not None:
                    cb.record_success()

                return fetch_response

            except httpx.TimeoutException as e:
                elapsed = time.monotonic() - start_time
                last_exception = NetworkError(
                    f"Request timeout after {elapsed:.1f}s: {url}",
                    status_code=None,
                    url=url,
                )
                logger.warning(
                    "request_timeout url=%s site_id=%s attempt=%s elapsed=%s",
                    url, site_id, attempt + 1, round(elapsed, 3),
                )
                if cb is not None:
                    cb.record_failure()

            except httpx.ConnectError as e:
                elapsed = time.monotonic() - start_time
                last_exception = NetworkError(
                    f"Connection error: {url} - {e}",
                    status_code=None,
                    url=url,
                )
                logger.warning(
                    "connection_error url=%s site_id=%s attempt=%s error=%s",
                    url, site_id, attempt + 1, str(e),
                )
                if cb is not None:
                    cb.record_failure()

            except NetworkError as e:
                last_exception = e
                if cb is not None:
                    cb.record_failure()

                # Non-retriable errors should not be retried
                if e.status_code is not None and e.status_code not in RETRIABLE_STATUS_CODES:
                    raise

            except RateLimitError as e:
                last_exception = e
                # Rate limit errors use special backoff
                if e.retry_after is not None:
                    delay = max(e.retry_after, self._backoff_base)
                else:
                    delay = self._backoff_base * (self._backoff_factor ** attempt)
                    delay = min(delay, self._backoff_max)
                    delay += random.uniform(0, delay * 0.2)

                if attempt < self._max_retries:
                    logger.warning(
                        "rate_limit_retry url=%s site_id=%s attempt=%s delay=%s",
                        url, site_id, attempt + 1, round(delay, 2),
                    )
                    time.sleep(delay)
                    continue
                else:
                    raise

            except BlockDetectedError:
                # Block detection is never retried at this level
                if cb is not None:
                    cb.record_failure()
                raise

            except Exception as e:
                elapsed = time.monotonic() - start_time
                last_exception = NetworkError(
                    f"Unexpected error fetching {url}: {e}",
                    status_code=None,
                    url=url,
                )
                logger.error(
                    "unexpected_fetch_error url=%s site_id=%s attempt=%s error=%s error_type=%s",
                    url, site_id, attempt + 1, str(e), type(e).__name__,
                )
                if cb is not None:
                    cb.record_failure()

            # Exponential backoff for retriable errors
            if attempt < self._max_retries:
                delay = self._backoff_base * (self._backoff_factor ** attempt)
                delay = min(delay, self._backoff_max)
                delay += random.uniform(0, delay * 0.2)  # 20% jitter

                logger.warning(
                    "retry_backoff url=%s site_id=%s attempt=%s max_retries=%s delay=%s",
                    url, site_id, attempt + 1, self._max_retries, round(delay, 2),
                )
                time.sleep(delay)

        # All retries exhausted
        logger.error(
            "max_retries_exhausted url=%s site_id=%s max_retries=%s",
            url, site_id, self._max_retries,
        )
        if last_exception is not None:
            raise last_exception
        raise NetworkError(f"Max retries exhausted for {url}", url=url)

    def _validate_response(
        self, response: httpx.Response, url: str, elapsed: float
    ) -> FetchResponse:
        """Validate an HTTP response and convert to FetchResponse.

        Checks for:
            - Error status codes (raises appropriate exceptions)
            - Empty response bodies
            - Bot detection patterns in 403/503 responses

        Args:
            response: httpx Response object.
            url: The requested URL.
            elapsed: Request duration in seconds.

        Returns:
            FetchResponse if validation passes.

        Raises:
            NetworkError: On error status codes.
            RateLimitError: On HTTP 429.
            BlockDetectedError: On bot detection patterns.
        """
        status = response.status_code

        # Build the FetchResponse early so we can return it for 2xx
        content_type = response.headers.get("content-type", "")
        fetch_resp = FetchResponse(
            url=str(response.url),
            status_code=status,
            headers=dict(response.headers),
            text=response.text,
            content=response.content,
            elapsed_seconds=elapsed,
            encoding=response.encoding or "utf-8",
            content_type=content_type,
        )

        # 2xx success
        if 200 <= status < 300:
            # Warn on empty response bodies (may indicate soft-block)
            if len(response.content) == 0:
                logger.warning(
                    "empty_response_body url=%s status=%s",
                    url, status,
                )
            return fetch_resp

        # 429 Rate Limit
        if status == 429:
            retry_after = response.headers.get("Retry-After")
            retry_seconds: float | None = None
            if retry_after:
                try:
                    retry_seconds = float(retry_after)
                except ValueError:
                    retry_seconds = 60.0  # default fallback
            raise RateLimitError(
                f"Rate limited (429) at {url}",
                retry_after=retry_seconds,
            )

        # 403 from news sites is always a bot block — route to escalation
        if status == 403:
            raise BlockDetectedError(
                f"HTTP 403 at {url} — likely bot block",
                block_type="ip_block",
            )

        # Bot detection patterns in 503
        if status == 503:
            body_lower = response.text.lower() if response.text else ""
            block_indicators = [
                "captcha", "cloudflare", "please verify",
                "access denied", "bot detected", "automated",
                "just a moment", "checking your browser",
                "ray id", "challenge-platform",
            ]
            if any(indicator in body_lower for indicator in block_indicators):
                raise BlockDetectedError(
                    f"Bot detection triggered at {url} (HTTP {status})",
                    block_type="captcha" if "captcha" in body_lower else "waf",
                )

        # Other error status codes
        if status >= 400:
            raise NetworkError(
                f"HTTP {status} at {url}",
                status_code=status,
                url=url,
            )

        # 3xx without redirect following (should not reach here with follow_redirects=True)
        return fetch_resp

    def fetch_with_encoding(
        self,
        url: str,
        site_id: str = "",
        charset: str = "utf-8",
        headers: dict[str, str] | None = None,
    ) -> FetchResponse:
        """Fetch a URL with explicit character encoding handling.

        Used for CJK sites (people.com.cn, yomiuri.co.jp) that may serve
        content in legacy encodings (GBK, Shift_JIS).

        Args:
            url: The URL to fetch.
            site_id: Site identifier.
            charset: Expected character encoding.
            headers: Additional request headers.

        Returns:
            FetchResponse with properly decoded text.
        """
        response = self.fetch(url, site_id=site_id, headers=headers)

        # If the response encoding differs from expected, re-decode
        if charset != "utf-8" and response.encoding != charset:
            try:
                text = response.content.decode(charset, errors="replace")
                return FetchResponse(
                    url=response.url,
                    status_code=response.status_code,
                    headers=response.headers,
                    text=text,
                    content=response.content,
                    elapsed_seconds=response.elapsed_seconds,
                    encoding=charset,
                    content_type=response.content_type,
                )
            except (UnicodeDecodeError, LookupError):
                logger.warning(
                    "encoding_fallback url=%s site_id=%s charset=%s",
                    url, site_id, charset,
                )
                # Return the original response as-is
                return response

        return response

    def head(
        self,
        url: str,
        site_id: str = "",
        headers: dict[str, str] | None = None,
    ) -> FetchResponse:
        """Perform a HEAD request to check URL availability.

        Args:
            url: The URL to check.
            site_id: Site identifier.
            headers: Additional request headers.

        Returns:
            FetchResponse with headers but no body.
        """
        return self.fetch(url, site_id=site_id, method="HEAD", headers=headers)

    def close(self) -> None:
        """Close the underlying httpx client and release resources."""
        if self._client is not None:
            with self._client_lock:
                if self._client is not None:
                    self._client.close()
                    self._client = None

    def __enter__(self) -> NetworkGuard:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()
