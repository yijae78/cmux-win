"""Session and header management for the GlobalNews crawling system.

Implements per-UA cookie jars, session lifecycle (create -> use -> retire),
realistic referer chain generation, and UA-consistent header diversification.
Each UA identity gets its own isolated cookie storage to prevent cross-session
leakage and to simulate distinct browser profiles.

Architecture Reference: Step 5 Blueprint Section 2.2 (session_manager),
Step 6 Crawling Strategies — UA rotation pool and header diversification.

Key design decisions:
- Cookie jars are keyed by UA string (not by domain). This means each UA
  identity accumulates its own cookies, matching how a real browser behaves.
- Sessions have a random lifespan of 10-50 requests before retirement.
- Referer chains follow the Google Search -> site homepage -> section -> article
  pattern, with configurable probability of direct/social entry points.
- Sec-Fetch-* headers are only emitted for Chrome/Edge (modern Blink engine);
  Firefox sends them too but with slightly different values. Safari on macOS
  does NOT send Sec-Fetch-* headers. iOS Safari does not either.
- Accept-Language is weighted toward the site's target language with realistic
  quality (q=) factors matching browser defaults.

Usage:
    from src.crawling.ua_manager import UAManager
    from src.crawling.session_manager import SessionManager

    ua_mgr = UAManager()
    sess_mgr = SessionManager(ua_manager=ua_mgr)

    headers = sess_mgr.get_request_headers(
        site_url="https://www.chosun.com/national/2024/01/01/article/",
        ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...",
        site_id="chosun",
        site_language="ko",
    )
"""

from __future__ import annotations

import http.cookiejar
import io
import logging
import random
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse
from typing import Any

from src.crawling.ua_manager import UAEntry, UAManager, _T1_UA, _T2_UA, _T3_UA

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session state model
# ---------------------------------------------------------------------------

@dataclass
class CrawlSession:
    """State for a single crawl session tied to one UA identity.

    A session represents a single simulated browser instance. It holds the
    cookie jar for that UA identity, tracks request count, and records health
    metrics for automatic retirement decisions.

    Attributes:
        ua_string: The User-Agent string for this session.
        cookie_jar: In-memory cookie jar for this UA identity.
        created_at: Unix timestamp when the session was created.
        max_requests: Maximum number of requests before forced retirement.
        request_count: Total requests made in this session.
        success_count: Requests that returned HTTP 2xx/3xx.
        failure_count: Requests that failed (network error or 4xx/5xx).
        last_used_at: Unix timestamp of the most recent request.
        retired: True if this session has been retired and must not be reused.
        referer_chain: Current referer chain for realistic header building.
    """

    ua_string: str
    cookie_jar: http.cookiejar.CookieJar = field(
        default_factory=http.cookiejar.CookieJar
    )
    created_at: float = field(default_factory=time.time)
    max_requests: int = 30
    request_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_used_at: float = field(default_factory=time.time)
    retired: bool = False
    referer_chain: list[str] = field(default_factory=list)

    @property
    def failure_rate(self) -> float:
        """Fraction of requests that failed. Returns 0.0 if no requests yet."""
        total = self.request_count
        return self.failure_count / total if total > 0 else 0.0

    @property
    def is_healthy(self) -> bool:
        """True if failure rate is below 30% threshold."""
        return self.failure_rate < 0.30

    @property
    def is_exhausted(self) -> bool:
        """True if the session has reached its max_requests limit."""
        return self.request_count >= self.max_requests

    def record_request(self, success: bool) -> None:
        """Update request counters after a request completes.

        Args:
            success: True if the response was HTTP 2xx/3xx, False otherwise.
        """
        self.request_count += 1
        self.last_used_at = time.time()
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1

    def retire(self) -> None:
        """Mark session as retired. Must not be used after this call."""
        self.retired = True
        logger.debug(
            "session_retired",
            ua_prefix=self.ua_string[:60],
            requests=self.request_count,
            failure_rate=round(self.failure_rate, 3),
        )


# ---------------------------------------------------------------------------
# Language-to-Accept-Language mapping
# ---------------------------------------------------------------------------

# Maps ISO 639-1 language code to the Accept-Language header value that a real
# browser configured for that language would send. Quality factors (q=) match
# real browser defaults. A secondary fallback of en-US is appended for all
# non-English sites to match real browser behavior.
_LANG_ACCEPT_MAP: dict[str, list[str]] = {
    "ko": [
        "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "ko-KR,ko;q=0.9,en;q=0.8",
        "ko,en-US;q=0.9,en;q=0.8",
    ],
    "en": [
        "en-US,en;q=0.9",
        "en-US,en;q=0.9,en-GB;q=0.8",
        "en-GB,en;q=0.9,en-US;q=0.8",
    ],
    "zh": [
        "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "zh-TW,zh;q=0.9,en;q=0.8",
        "zh,en-US;q=0.9,en;q=0.8",
    ],
    "ja": [
        "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
        "ja,en-US;q=0.8,en;q=0.7",
    ],
    "de": [
        "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        "de,en-US;q=0.9,en;q=0.8",
    ],
    "fr": [
        "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "fr,en;q=0.9",
    ],
    "ar": [
        "ar-SA,ar;q=0.9,en-US;q=0.8,en;q=0.7",
        "ar,en;q=0.8",
    ],
    "he": [
        "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
    ],
    "es": [
        "es-MX,es;q=0.9,en-US;q=0.8,en;q=0.7",
        "es-ES,es;q=0.9,en;q=0.8",
    ],
}
_LANG_ACCEPT_DEFAULT = [
    "en-US,en;q=0.9",
    "en-US,en;q=0.9,en-GB;q=0.8",
]

# ---------------------------------------------------------------------------
# Referer pool — plausible entry points for organic traffic
# ---------------------------------------------------------------------------

# Google Search referrers (most common organic source)
_GOOGLE_REFERRERS: list[str] = [
    "https://www.google.com/",
    "https://www.google.com/search?q=news",
    "https://www.google.co.kr/",
    "https://www.google.co.uk/",
    "https://www.google.de/",
    "https://www.google.co.jp/",
    "https://www.google.fr/",
]

# Social media referrers
_SOCIAL_REFERRERS: list[str] = [
    "https://www.facebook.com/",
    "https://twitter.com/",
    "https://www.reddit.com/",
    "https://t.co/",
    "https://www.instagram.com/",
    "https://www.linkedin.com/",
    "https://news.ycombinator.com/",
]

# News aggregator referrers
_AGGREGATOR_REFERRERS: list[str] = [
    "https://news.google.com/",
    "https://flipboard.com/",
    "https://www.msn.com/",
    "https://www.yahoo.com/news/",
]


# ---------------------------------------------------------------------------
# Header builder helpers (browser-specific)
# ---------------------------------------------------------------------------

def _build_chrome_headers(
    ua_entry: UAEntry,
    site_language: str,
    referer: str | None,
    rng: random.Random,
    is_navigation: bool = True,
) -> dict[str, str]:
    """Build Chrome-consistent request headers.

    Chrome sends Sec-Fetch-* headers on all navigation and sub-resource
    requests. The Accept header format and header ordering match Chrome's
    real behavior as of Chrome 120+.

    Args:
        ua_entry: Parsed UA metadata for field consistency checks.
        site_language: ISO 639-1 target language for Accept-Language weighting.
        referer: Referer URL to include, or None for no referer.
        rng: Random instance for variant selection.
        is_navigation: True for top-level page navigation (document fetch).

    Returns:
        Dictionary of HTTP request headers in Chrome-authentic order.
    """
    lang_variants = _LANG_ACCEPT_MAP.get(site_language, _LANG_ACCEPT_DEFAULT)
    accept_lang = rng.choice(lang_variants)

    headers: dict[str, str] = {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,image/apng,*/*;"
            "q=0.8,application/signed-exchange;v=b3;q=0.7"
        ),
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": accept_lang,
        "Cache-Control": rng.choice(["max-age=0", "no-cache"]),
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": ua_entry.ua_string,
    }

    if referer:
        headers["Referer"] = referer

    # Sec-Fetch-* headers — Chrome always sends these on document fetches
    if is_navigation:
        headers["Sec-Fetch-Dest"] = "document"
        headers["Sec-Fetch-Mode"] = "navigate"
        headers["Sec-Fetch-Site"] = "none" if not referer else "cross-site"
        headers["Sec-Fetch-User"] = "?1"
    else:
        # Sub-resource request (XHR/fetch)
        headers["Sec-Fetch-Dest"] = "empty"
        headers["Sec-Fetch-Mode"] = "cors"
        headers["Sec-Fetch-Site"] = "same-origin"

    # Sec-CH-UA headers (Client Hints) — Chrome 89+ sends these
    # Format: brand list with major version
    major_ver = ua_entry.browser_version
    headers["Sec-CH-UA"] = (
        f'"Chromium";v="{major_ver}", "Google Chrome";v="{major_ver}", '
        f'"Not-A.Brand";v="99"'
    )
    headers["Sec-CH-UA-Mobile"] = "?0"
    headers["Sec-CH-UA-Platform"] = f'"{ua_entry.os}"'

    return headers


def _build_edge_headers(
    ua_entry: UAEntry,
    site_language: str,
    referer: str | None,
    rng: random.Random,
    is_navigation: bool = True,
) -> dict[str, str]:
    """Build Edge-consistent request headers.

    Edge (Chromium-based) sends the same Sec-Fetch-* structure as Chrome,
    but its Sec-CH-UA includes the "Microsoft Edge" brand.

    Args:
        ua_entry: Parsed UA metadata.
        site_language: ISO 639-1 target language.
        referer: Referer URL or None.
        rng: Random instance for variant selection.
        is_navigation: True for top-level document navigation.

    Returns:
        Dictionary of HTTP request headers in Edge-authentic order.
    """
    # Build Chrome base headers first, then patch Edge-specific fields
    headers = _build_chrome_headers(ua_entry, site_language, referer, rng, is_navigation)

    major_ver = ua_entry.browser_version
    headers["Sec-CH-UA"] = (
        f'"Microsoft Edge";v="{major_ver}", "Chromium";v="{major_ver}", '
        f'"Not-A.Brand";v="99"'
    )
    # Edge Accept order differs slightly
    headers["Accept"] = (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/webp,image/apng,*/*;"
        "q=0.8,application/signed-exchange;v=b3;q=0.7"
    )
    return headers


def _build_firefox_headers(
    ua_entry: UAEntry,
    site_language: str,
    referer: str | None,
    rng: random.Random,
    is_navigation: bool = True,
) -> dict[str, str]:
    """Build Firefox-consistent request headers.

    Firefox sends Sec-Fetch-* headers since Firefox 90. The Accept header
    format, header ordering, and DNT behavior differ from Chrome.
    Firefox does NOT send Client Hint (Sec-CH-UA) headers.

    Args:
        ua_entry: Parsed UA metadata.
        site_language: ISO 639-1 target language.
        referer: Referer URL or None.
        rng: Random instance for variant selection.
        is_navigation: True for top-level document navigation.

    Returns:
        Dictionary of HTTP request headers in Firefox-authentic order.
    """
    lang_variants = _LANG_ACCEPT_MAP.get(site_language, _LANG_ACCEPT_DEFAULT)
    accept_lang = rng.choice(lang_variants)

    headers: dict[str, str] = {
        "User-Agent": ua_entry.ua_string,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": accept_lang,
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    if referer:
        headers["Referer"] = referer

    # Firefox sends Sec-Fetch-* since v90
    if ua_entry.browser_version >= 90:
        if is_navigation:
            headers["Sec-Fetch-Dest"] = "document"
            headers["Sec-Fetch-Mode"] = "navigate"
            headers["Sec-Fetch-Site"] = "none" if not referer else "cross-site"
            headers["Sec-Fetch-User"] = "?1"
        else:
            headers["Sec-Fetch-Dest"] = "empty"
            headers["Sec-Fetch-Mode"] = "cors"
            headers["Sec-Fetch-Site"] = "same-origin"

    # Firefox randomly sends DNT (Do Not Track)
    if rng.random() < 0.30:
        headers["DNT"] = "1"

    # Firefox sends Priority header on navigation requests
    if is_navigation:
        headers["Priority"] = "u=0, i"

    return headers


def _build_safari_headers(
    ua_entry: UAEntry,
    site_language: str,
    referer: str | None,
    rng: random.Random,
    is_navigation: bool = True,
) -> dict[str, str]:
    """Build Safari-consistent request headers.

    Safari (macOS and iOS) does NOT send Sec-Fetch-* or Sec-CH-UA headers.
    The Accept header format differs from Chrome/Firefox.

    Args:
        ua_entry: Parsed UA metadata.
        site_language: ISO 639-1 target language.
        referer: Referer URL or None.
        rng: Random instance for variant selection.
        is_navigation: True for top-level document navigation.

    Returns:
        Dictionary of HTTP request headers in Safari-authentic order.
    """
    lang_variants = _LANG_ACCEPT_MAP.get(site_language, _LANG_ACCEPT_DEFAULT)
    accept_lang = rng.choice(lang_variants)

    headers: dict[str, str] = {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": accept_lang,
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "User-Agent": ua_entry.ua_string,
    }

    if is_navigation:
        headers["Upgrade-Insecure-Requests"] = "1"

    if referer:
        headers["Referer"] = referer

    # Safari does NOT send Sec-Fetch-* headers — intentional omission
    # Safari does NOT send Sec-CH-UA headers — intentional omission

    return headers


def _build_bot_headers(
    ua_entry: UAEntry,
    site_language: str,
    referer: str | None,
    rng: random.Random,
    is_navigation: bool = True,
) -> dict[str, str]:
    """Build minimal headers for Googlebot (T1 sites).

    Googlebot sends a very minimal header set. No Sec-Fetch, no Client Hints,
    no cookies, no Accept-Encoding beyond gzip.

    Args:
        ua_entry: Parsed UA metadata.
        site_language: ISO 639-1 target language (mostly ignored for bots).
        referer: Referer URL (mostly None for bots).
        rng: Random instance (unused for bots but kept for interface consistency).
        is_navigation: Navigation flag (ignored for bots).

    Returns:
        Dictionary of minimal HTTP request headers for bot behavior.
    """
    return {
        "User-Agent": ua_entry.ua_string,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Encoding": "gzip, deflate",
        "From": "googlebot(at)googlebot.com",
    }


# ---------------------------------------------------------------------------
# Build a UA-to-entry lookup once at module load (avoids repeated linear scans)
# ---------------------------------------------------------------------------
_UA_STRING_TO_ENTRY: dict[str, UAEntry] = {}
for _entry in _T1_UA + _T2_UA + _T3_UA:
    _UA_STRING_TO_ENTRY[_entry.ua_string] = _entry


# ---------------------------------------------------------------------------
# SessionManager
# ---------------------------------------------------------------------------

class SessionManager:
    """Per-UA session lifecycle and request header management.

    Each UA identity gets its own CrawlSession with an isolated cookie jar.
    Sessions are retired after a random number of requests (10-50) or when
    the failure rate exceeds 30%. New sessions replace retired ones.

    The `get_request_headers` method is the primary integration point for the
    NetworkGuard (Step 5, Section 2.2). It returns a complete header dict
    ready for injection into httpx or Playwright requests.

    Args:
        ua_manager: UAManager instance for UA selection and metadata lookup.
        min_requests_per_session: Minimum requests per session before retirement
            eligibility. Default 10.
        max_requests_per_session: Maximum requests per session. Default 50.
        failure_rate_threshold: Failure rate above which a session is retired.
            Default 0.30 (30%).
        seed: Optional random seed for reproducibility in tests.
    """

    def __init__(
        self,
        ua_manager: UAManager,
        min_requests_per_session: int = 10,
        max_requests_per_session: int = 50,
        failure_rate_threshold: float = 0.30,
        seed: int | None = None,
    ) -> None:
        self._ua_manager = ua_manager
        self._min_req = min_requests_per_session
        self._max_req = max_requests_per_session
        self._failure_threshold = failure_rate_threshold
        self._rng = random.Random(seed)

        # Active sessions keyed by UA string
        self._sessions: dict[str, CrawlSession] = {}

        # Per-domain referer state: domain -> last page URL visited
        self._domain_last_url: dict[str, str] = {}

        logger.info(
            "session_manager_initialized",
            min_requests=min_requests_per_session,
            max_requests=max_requests_per_session,
            failure_threshold=failure_rate_threshold,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_request_headers(
        self,
        site_url: str,
        ua: str,
        site_id: str = "",
        site_language: str = "en",
        is_navigation: bool = True,
    ) -> dict[str, str]:
        """Build a complete, UA-consistent HTTP request header dict.

        This is the primary integration point for NetworkGuard. Given a UA
        string and site context, it returns headers that:
        - Match the declared browser's real header behavior (Accept, Sec-Fetch,
          Client Hints, header ordering)
        - Weight Accept-Language toward the site's target language
        - Include a plausible Referer from the domain's browsing history or
          from a common organic traffic source (Google, social media)
        - Are internally consistent (no Chrome UA with Firefox headers)

        Args:
            site_url: The URL being requested. Used to build referer chain
                and extract domain for history tracking.
            ua: The User-Agent string to use for this request.
            site_id: The source_id for domain-history tracking. Optional;
                if empty, domain is extracted from site_url.
            site_language: ISO 639-1 language code of the target site.
                Weights Accept-Language accordingly.
            is_navigation: True for top-level document navigation (GET to an
                article URL). False for sub-resource fetches.

        Returns:
            Dictionary of HTTP request headers ready for injection.
        """
        session = self._get_or_create_session(ua)
        ua_entry = self._resolve_ua_entry(ua)
        domain = site_id or self._extract_domain(site_url)
        referer = self._build_referer(domain, site_url)

        # Dispatch to browser-specific header builder (no fingerprint contradictions)
        browser = ua_entry.browser.lower()
        if browser == "edge":
            headers = _build_edge_headers(ua_entry, site_language, referer, self._rng, is_navigation)
        elif browser == "firefox":
            headers = _build_firefox_headers(ua_entry, site_language, referer, self._rng, is_navigation)
        elif browser == "safari":
            headers = _build_safari_headers(ua_entry, site_language, referer, self._rng, is_navigation)
        elif browser == "googlebot":
            headers = _build_bot_headers(ua_entry, site_language, referer, self._rng, is_navigation)
        else:
            # Default: Chrome
            headers = _build_chrome_headers(ua_entry, site_language, referer, self._rng, is_navigation)

        # Track navigation URL for future referer chain building
        if is_navigation:
            self._advance_referer_chain(domain, session, site_url)

        logger.debug(
            "headers_built",
            site_id=domain,
            browser=ua_entry.browser,
            browser_version=ua_entry.browser_version,
            referer=referer,
            header_count=len(headers),
        )
        return headers

    def record_request_outcome(self, ua: str, success: bool) -> None:
        """Record whether a request with this UA succeeded.

        Updates failure rate tracking in the session. If the session becomes
        unhealthy (>30% failure rate) after this update, it is retired.

        Args:
            ua: The User-Agent string used for the request.
            success: True for HTTP 2xx/3xx responses, False for errors/4xx/5xx.
        """
        session = self._sessions.get(ua)
        if session is None:
            return

        session.record_request(success)

        # Retire if health threshold breached or max_requests reached
        if not session.is_healthy or session.is_exhausted:
            reason = "failure_rate" if not session.is_healthy else "max_requests"
            logger.info(
                "session_retiring",
                ua_prefix=ua[:60],
                reason=reason,
                request_count=session.request_count,
                failure_rate=round(session.failure_rate, 3),
            )
            session.retire()
            del self._sessions[ua]

    def get_session_cookies(self, ua: str) -> http.cookiejar.CookieJar:
        """Return the cookie jar for a UA identity.

        Cookie jars are isolated per UA string. Calling this on a new UA
        creates a fresh session automatically.

        Args:
            ua: The User-Agent string.

        Returns:
            The CookieJar associated with this UA identity.
        """
        return self._get_or_create_session(ua).cookie_jar

    def retire_session(self, ua: str) -> None:
        """Forcefully retire a session, discarding its cookie jar.

        Call this after a proxy rotation or after detecting a definitive block.

        Args:
            ua: The User-Agent string whose session should be retired.
        """
        session = self._sessions.pop(ua, None)
        if session:
            session.retire()

    def session_stats(self) -> dict[str, Any]:
        """Return summary statistics on active sessions.

        Returns:
            Dictionary with total active sessions and aggregate health metrics.
        """
        active = list(self._sessions.values())
        if not active:
            return {"active_sessions": 0}

        avg_failure_rate = sum(s.failure_rate for s in active) / len(active)
        return {
            "active_sessions": len(active),
            "avg_failure_rate": round(avg_failure_rate, 3),
            "total_requests": sum(s.request_count for s in active),
            "unhealthy_count": sum(1 for s in active if not s.is_healthy),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_session(self, ua: str) -> CrawlSession:
        """Retrieve the active session for a UA, creating one if absent.

        Args:
            ua: The User-Agent string.

        Returns:
            Active (non-retired) CrawlSession for this UA.
        """
        session = self._sessions.get(ua)
        if session is None or session.retired:
            max_req = self._rng.randint(self._min_req, self._max_req)
            session = CrawlSession(ua_string=ua, max_requests=max_req)
            self._sessions[ua] = session
            logger.debug(
                "session_created",
                ua_prefix=ua[:60],
                max_requests=max_req,
            )
        return session

    def _resolve_ua_entry(self, ua: str) -> UAEntry:
        """Look up full UAEntry metadata for a UA string.

        Falls back to a Chrome/Windows/desktop default if the UA is not in the
        static pool (e.g., dynamically generated Patchright UA).

        Args:
            ua: The User-Agent string.

        Returns:
            UAEntry with browser/os/version metadata.
        """
        entry = _UA_STRING_TO_ENTRY.get(ua)
        if entry is not None:
            return entry

        # Heuristic parsing for unknown UAs (Patchright dynamic fingerprints)
        ua_lower = ua.lower()
        if "edg/" in ua_lower:
            browser, ver = "Edge", 131
        elif "firefox/" in ua_lower:
            browser, ver = "Firefox", 133
        elif "safari/" in ua_lower and "chrome" not in ua_lower:
            browser, ver = "Safari", 17
        else:
            browser, ver = "Chrome", 131

        os_name = "Windows"
        os_version = "10.0"
        if "macintosh" in ua_lower or "mac os x" in ua_lower:
            os_name, os_version = "macOS", "10.15.7"
        elif "linux" in ua_lower:
            os_name, os_version = "Linux", "x86_64"
        elif "iphone" in ua_lower or "ipad" in ua_lower:
            os_name, os_version = "iOS", "17.0"

        return UAEntry(
            ua_string=ua,
            browser=browser,
            browser_version=ver,
            os=os_name,
            os_version=os_version,
            device_type="mobile" if os_name == "iOS" else "desktop",
            tier=3,
            weight=1.0,
        )

    def _extract_domain(self, url: str) -> str:
        """Extract the hostname from a URL as a domain key.

        Args:
            url: Full URL string.

        Returns:
            Hostname string (e.g., "www.chosun.com"), or the original url
            string if parsing fails.
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc or url
        except Exception:
            return url

    def _build_referer(self, domain: str, current_url: str) -> str | None:
        """Generate a plausible Referer header for the current request.

        Referer chain strategy:
        - 40% chance: Referer from Google Search (organic traffic)
        - 15% chance: Referer from social media
        - 10% chance: Referer from news aggregator
        - 15% chance: Referer from site's previous page (internal navigation)
        - 20% chance: No referer (direct navigation)

        If the domain already has a previous-page URL tracked, internal
        navigation referer is always preferred to build realistic session depth.

        Args:
            domain: Domain key for history lookup.
            current_url: The URL being requested right now.

        Returns:
            Referer URL string, or None for direct navigation.
        """
        last_url = self._domain_last_url.get(domain)

        if last_url:
            # Internal page-to-page navigation — most realistic for deep visits
            return last_url

        # First visit to domain: pick an organic entry point
        roll = self._rng.random()
        if roll < 0.40:
            return self._rng.choice(_GOOGLE_REFERRERS)
        elif roll < 0.55:
            return self._rng.choice(_SOCIAL_REFERRERS)
        elif roll < 0.65:
            return self._rng.choice(_AGGREGATOR_REFERRERS)
        else:
            return None  # Direct navigation — no referer

    def _advance_referer_chain(
        self, domain: str, session: CrawlSession, current_url: str
    ) -> None:
        """Update the referer chain state after a navigation request.

        Records current_url as the next referer for subsequent requests to the
        same domain. Also appends to the session's referer_chain log (for
        debugging and stealth browser handoff).

        Args:
            domain: Domain key for tracking.
            session: Active CrawlSession to update.
            current_url: URL that was just fetched (becomes future referer).
        """
        self._domain_last_url[domain] = current_url
        session.referer_chain.append(current_url)
        # Keep chain bounded to avoid unbounded memory growth
        if len(session.referer_chain) > 20:
            session.referer_chain.pop(0)
