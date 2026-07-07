"""Dynamic Bypass Engine — Block-Type-Aware Strategy Dispatch.

Maps the 7 detected block types (from block_detector.py) to concrete
bypass strategies using modern anti-detection libraries. Each strategy
is tried cheapest-first (Tier 0 → Tier 4) with per-domain adaptive
learning.

Architecture:
    BlockType detected → Strategy lookup → Ordered by (domain success rate,
    tier cost) → Execute cheapest first → On failure, try next → Learn

Strategy Tiers:
    Tier 0: Free, no external deps (header changes, RSS, AMP, Google Cache)
    Tier 1: TLS fingerprint mimicry (curl_cffi — no browser needed)
    Tier 2: Browser automation (Patchright stealth, Camoufox)
    Tier 3: External services (proxy rotation, CAPTCHA solvers)
    Tier 4: Archive sources (Wayback Machine — stale but available)

Integration:
    - Used by pipeline.py's Never-Abandon loop as the strategy dispatcher
    - Replaces the blind TotalWar fallback with targeted bypass selection
    - Works alongside existing AntiBlockEngine (6-tier escalation) and
      CircuitBreakerCoordinator

Reference: Crawling Absolute Principle (크롤링 절대 원칙)
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from enum import IntEnum, unique
from typing import Any, Callable, Awaitable
from urllib.parse import urlparse

from src.crawling.block_detector import BlockDiagnosis, BlockType, HttpResponse

logger = logging.getLogger(__name__)


# =============================================================================
# Strategy Tier (cost/complexity classification)
# =============================================================================

@unique
class StrategyTier(IntEnum):
    """Cost/complexity tiers for bypass strategies."""
    TIER_0 = 0  # Free, no external deps (header rotation, RSS, AMP)
    TIER_1 = 1  # TLS mimicry (curl_cffi — fast, no browser)
    TIER_2 = 2  # Browser automation (Patchright, Camoufox)
    TIER_3 = 3  # External services (proxies, CAPTCHA solvers)
    TIER_4 = 4  # Archive sources (Wayback — stale data, last resort)


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class BypassResult:
    """Result of a single bypass strategy attempt.

    Attributes:
        success: Whether the strategy fetched usable content.
        html: The fetched HTML content (empty on failure).
        status_code: HTTP status code from the response.
        strategy_name: Which strategy was used.
        strategy_tier: The tier of the strategy used.
        block_detected: Block type if a new block was detected on the response.
        error: Error message if the strategy raised an exception.
        latency_ms: Time taken for this attempt in milliseconds.
    """
    success: bool
    html: str = ""
    status_code: int = 0
    strategy_name: str = ""
    strategy_tier: int = 0
    block_detected: BlockType | None = None
    error: str = ""
    latency_ms: float = 0.0


@dataclass
class StrategyStats:
    """Per-domain, per-strategy success tracking for adaptive reordering.

    Attributes:
        attempts: Total number of attempts with this strategy on this domain.
        successes: Number of successful fetches.
        total_latency_ms: Cumulative latency for averaging.
    """
    attempts: int = 0
    successes: int = 0
    total_latency_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        """Success rate from 0.0 to 1.0."""
        return self.successes / self.attempts if self.attempts > 0 else 0.0

    @property
    def avg_latency_ms(self) -> float:
        """Average latency per attempt."""
        return self.total_latency_ms / self.attempts if self.attempts > 0 else 0.0


@dataclass
class BypassStrategy:
    """A registered bypass strategy.

    Attributes:
        name: Unique identifier for this strategy.
        tier: Cost/complexity tier (0-4).
        effective_against: Set of block types this strategy can bypass.
        description: Human-readable description of the strategy.
        requires_proxy: Whether this strategy needs a proxy pool.
        requires_browser: Whether this strategy needs a browser binary.
    """
    name: str
    tier: StrategyTier
    effective_against: set[BlockType]
    description: str = ""
    requires_proxy: bool = False
    requires_browser: bool = False


# =============================================================================
# Block-Type-to-Strategy Mapping (cheapest first within each block type)
# Strategy names must align with ALTERNATIVE_STRATEGIES in retry_manager.py
# (D-7 Instance 12 — change one side, sync the other).
# =============================================================================

STRATEGY_MAP: dict[BlockType, list[str]] = {
    BlockType.UA_FILTER: [
        "rotate_user_agent",         # T0: just change UA string
        "curl_cffi_impersonate",     # T1: full browser TLS fingerprint
    ],
    BlockType.FINGERPRINT: [
        "curl_cffi_impersonate",     # T1: TLS fingerprint mimicry
        "fingerprint_rotation",      # T1: rotate JA3/JA4 + headers
        "patchright_stealth",        # T2: full browser with anti-detection
        "camoufox_stealth",          # T2: Firefox-based anti-fingerprint
    ],
    BlockType.JS_CHALLENGE: [
        "cloudscraper_solve",        # T1: JS challenge solver (no browser)
        "curl_cffi_impersonate",     # T1: sometimes enough for simple JS
        "patchright_stealth",        # T2: full browser for complex challenges
    ],
    BlockType.CAPTCHA: [
        "patchright_stealth",        # T2: some CAPTCHAs auto-pass with stealth
        "camoufox_stealth",          # T2: Firefox fingerprint diversity
    ],
    BlockType.RATE_LIMIT: [
        "exponential_backoff",       # T0: wait and retry
        "rss_feed_fallback",         # T0: alternative source
        "proxy_rotation",            # T3: different IP
    ],
    BlockType.IP_BLOCK: [
        "proxy_rotation",            # T3: different IP
        "rss_feed_fallback",         # T0: alternative source (includes Google News RSS)
        "gdelt_api_fallback",        # T0: GDELT DOC API for URL discovery
        "google_cache_fallback",     # T0: Google's cached version
        "archive_today_fallback",    # T4: archive.today mirror
        "wayback_fallback",          # T4: Internet Archive
    ],
    BlockType.GEO_BLOCK: [
        "amp_version_fallback",      # T0: AMP CDN (different geo)
        "google_cache_fallback",     # T0: Google's cached version
        "gdelt_api_fallback",        # T0: GDELT DOC API for URL discovery
        "proxy_rotation",            # T3: geo-targeted proxy
        "archive_today_fallback",    # T4: archive.today mirror
        "wayback_fallback",          # T4: Internet Archive
    ],
}

# Default strategy order for unknown/unclassified blocks
_DEFAULT_STRATEGIES: list[str] = [
    "rotate_user_agent",         # T0: simple UA rotation (always available)
    "curl_cffi_impersonate",     # T1: TLS fingerprint mimicry
    "rss_feed_fallback",         # T0: RSS/Atom feed (includes Google News RSS)
    "google_cache_fallback",     # T0: Google's cached version
    "amp_version_fallback",      # T0: AMP version
    "gdelt_api_fallback",        # T0: GDELT DOC API
    "exponential_backoff",       # T0: wait then retry
    "fingerprint_rotation",      # T1: rotate all TLS profiles
    "cloudscraper_solve",        # T1: Cloudflare JS solver
    "patchright_stealth",        # T2: stealth browser (Chromium)
    "camoufox_stealth",          # T2: stealth browser (Firefox)
    "proxy_rotation",            # T3: proxy pool
    "archive_today_fallback",    # T4: archive.today mirror
    "wayback_fallback",          # T4: Internet Archive
]

# TLS fingerprint profiles for curl_cffi rotation
# Each profile includes impersonate target + matching headers
_FINGERPRINT_PROFILES: list[dict[str, Any]] = [
    {
        "impersonate": "chrome120",
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "sec_ch_ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "platform": "Windows",
    },
    {
        "impersonate": "chrome124",
        "user_agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "sec_ch_ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "platform": "macOS",
    },
    {
        "impersonate": "safari17_5",
        "user_agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.5 Safari/605.1.15"
        ),
        "sec_ch_ua": "",  # Safari doesn't send sec-ch-ua
        "platform": "macOS",
    },
    {
        "impersonate": "firefox120",
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) "
            "Gecko/20100101 Firefox/120.0"
        ),
        "sec_ch_ua": "",  # Firefox doesn't send sec-ch-ua
        "platform": "Windows",
    },
    {
        "impersonate": "chrome131",
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "sec_ch_ua": '"Chromium";v="131", "Google Chrome";v="131", "Not-A.Brand";v="99"',
        "platform": "Windows",
    },
    {
        "impersonate": "edge101",
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36 Edg/101.0.1210.53"
        ),
        "sec_ch_ua": '"Microsoft Edge";v="101", "Chromium";v="101", " Not A;Brand";v="99"',
        "platform": "Windows",
    },
    {
        "impersonate": "safari18_0",
        "user_agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/18.0 Safari/605.1.15"
        ),
        "sec_ch_ua": "",  # Safari doesn't send sec-ch-ua
        "platform": "macOS",
    },
    {
        "impersonate": "firefox133",
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) "
            "Gecko/20100101 Firefox/131.0"
        ),
        "sec_ch_ua": "",  # Firefox doesn't send sec-ch-ua
        "platform": "Windows",
    },
]

# Common User-Agent strings for Tier 0 rotation
_USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

# Minimum body length to consider a fetch successful (short pages are likely error pages)
_MIN_BODY_LENGTH = 500

# Maximum strategies to try per URL before giving up
_MAX_STRATEGIES_PER_URL = 5

# Common RSS feed paths for news sites
_RSS_PATHS = ["/feed", "/rss", "/rss.xml", "/feed.xml", "/atom.xml", "/feeds/all.atom.xml"]


# =============================================================================
# Dynamic Bypass Engine
# =============================================================================

class DynamicBypassEngine:
    """Block-type-aware strategy dispatcher with adaptive learning.

    Automatically selects and executes bypass strategies based on detected
    block types. Learns per-domain success rates to optimize strategy
    ordering over time.

    Usage:
        engine = DynamicBypassEngine(proxy_pool=["http://proxy1:8080"])

        # In the Never-Abandon loop:
        result = engine.execute_strategy(
            url="https://example.com/article",
            strategy_name="curl_cffi_impersonate",
            site_id="example",
        )

        # Or let the engine choose the best strategy:
        strategies = engine.get_strategies_for_block(
            BlockType.JS_CHALLENGE, domain="example.com"
        )
        for strategy_name in strategies:
            result = engine.execute_strategy(url, strategy_name, site_id)
            if result.success:
                break

    Thread-safety: NOT thread-safe. Use one instance per pipeline run.

    Attributes:
        proxy_pool: List of proxy URLs for Tier 3 strategies.
        enable_browser: Whether browser-based strategies (Tier 2) are available.
    """

    def __init__(
        self,
        proxy_pool: list[str] | None = None,
        enable_browser: bool = True,
    ) -> None:
        """Initialize the DynamicBypassEngine.

        Args:
            proxy_pool: List of proxy URLs (e.g., ["http://user:pass@proxy:8080"]).
                Empty list disables proxy-based strategies.
            enable_browser: Whether to enable Patchright/Camoufox strategies.
                Set to False in environments without browser binaries.
        """
        self.proxy_pool = proxy_pool or []
        self.enable_browser = enable_browser

        # Registry of available strategies
        self._strategies: dict[str, BypassStrategy] = {}
        self._register_strategies()

        # Per-domain, per-strategy success tracking
        self._domain_stats: dict[str, dict[str, StrategyStats]] = {}

        # Per-domain last known block type (avoid redundant detection)
        self._domain_block_cache: dict[str, BlockType] = {}

        # Proxy rotation index
        self._proxy_index = 0

        logger.info(
            "DynamicBypassEngine initialized strategies=%s proxy_pool=%s browser=%s",
            len(self._strategies), len(self.proxy_pool), enable_browser,
        )

    def _register_strategies(self) -> None:
        """Register all available bypass strategies."""
        # Tier 0 — Free, no external dependencies
        self._register(BypassStrategy(
            name="rotate_user_agent",
            tier=StrategyTier.TIER_0,
            effective_against={BlockType.UA_FILTER},
            description="Rotate User-Agent string with common browser UAs",
        ))
        self._register(BypassStrategy(
            name="exponential_backoff",
            tier=StrategyTier.TIER_0,
            effective_against={BlockType.RATE_LIMIT},
            description="Wait with exponential backoff then retry with standard client",
        ))
        self._register(BypassStrategy(
            name="rss_feed_fallback",
            tier=StrategyTier.TIER_0,
            effective_against={BlockType.RATE_LIMIT, BlockType.IP_BLOCK},
            description="Fetch content via RSS/Atom feed (bypass site's WAF)",
        ))
        self._register(BypassStrategy(
            name="amp_version_fallback",
            tier=StrategyTier.TIER_0,
            effective_against={BlockType.GEO_BLOCK},
            description="Fetch AMP version from CDN or /amp suffix",
        ))
        self._register(BypassStrategy(
            name="google_cache_fallback",
            tier=StrategyTier.TIER_0,
            effective_against={BlockType.GEO_BLOCK, BlockType.IP_BLOCK},
            description="Fetch Google's cached version of the page",
        ))
        self._register(BypassStrategy(
            name="gdelt_api_fallback",
            tier=StrategyTier.TIER_0,
            effective_against={BlockType.IP_BLOCK, BlockType.GEO_BLOCK},
            description="GDELT DOC API for discovering article URLs (bypasses WAF)",
        ))

        # Tier 1 — TLS fingerprint mimicry (curl_cffi, cloudscraper)
        self._register(BypassStrategy(
            name="curl_cffi_impersonate",
            tier=StrategyTier.TIER_1,
            effective_against={
                BlockType.UA_FILTER, BlockType.FINGERPRINT,
                BlockType.JS_CHALLENGE,
            },
            description="curl_cffi with browser TLS fingerprint (JA3/JA4 mimicry)",
        ))
        self._register(BypassStrategy(
            name="fingerprint_rotation",
            tier=StrategyTier.TIER_1,
            effective_against={BlockType.FINGERPRINT},
            description="Rotate TLS fingerprint + matching headers across profiles",
        ))
        self._register(BypassStrategy(
            name="cloudscraper_solve",
            tier=StrategyTier.TIER_1,
            effective_against={BlockType.JS_CHALLENGE},
            description="Solve Cloudflare JS challenges without browser",
        ))

        # Tier 2 — Browser automation (requires browser binary)
        if self.enable_browser:
            self._register(BypassStrategy(
                name="patchright_stealth",
                tier=StrategyTier.TIER_2,
                effective_against={
                    BlockType.JS_CHALLENGE, BlockType.CAPTCHA,
                    BlockType.FINGERPRINT,
                },
                requires_browser=True,
                description="Patchright (stealth Playwright fork) with anti-detection patches",
            ))
            self._register(BypassStrategy(
                name="camoufox_stealth",
                tier=StrategyTier.TIER_2,
                effective_against={BlockType.CAPTCHA, BlockType.FINGERPRINT},
                requires_browser=True,
                description="Camoufox (Firefox fork) with 300+ fingerprint randomizations",
            ))

        # Tier 3 — External services (proxy rotation)
        if self.proxy_pool:
            self._register(BypassStrategy(
                name="proxy_rotation",
                tier=StrategyTier.TIER_3,
                effective_against={
                    BlockType.IP_BLOCK, BlockType.RATE_LIMIT,
                    BlockType.GEO_BLOCK,
                },
                requires_proxy=True,
                description="Rotate through proxy pool with TLS fingerprint mimicry",
            ))

        # Tier 4 — Archive sources (last resort)
        self._register(BypassStrategy(
            name="archive_today_fallback",
            tier=StrategyTier.TIER_4,
            effective_against={BlockType.IP_BLOCK, BlockType.GEO_BLOCK},
            description="Fetch from archive.today mirror (recent snapshots)",
        ))
        self._register(BypassStrategy(
            name="wayback_fallback",
            tier=StrategyTier.TIER_4,
            effective_against={BlockType.IP_BLOCK, BlockType.GEO_BLOCK},
            description="Fetch from Internet Archive Wayback Machine (may be stale)",
        ))

    def _register(self, strategy: BypassStrategy) -> None:
        """Register a bypass strategy."""
        self._strategies[strategy.name] = strategy

    # -------------------------------------------------------------------------
    # Strategy Selection
    # -------------------------------------------------------------------------

    def get_strategies_for_block(
        self,
        block_type: BlockType,
        domain: str = "",
    ) -> list[str]:
        """Get ordered strategy list for a detected block type.

        Strategies are ordered by:
        1. Domain-specific success rate (descending) — learned over time
        2. Strategy tier cost (ascending) — cheaper first

        Args:
            block_type: The detected block type.
            domain: Domain for per-domain success rate lookup.

        Returns:
            Ordered list of strategy names to try.
        """
        strategy_names = STRATEGY_MAP.get(block_type, _DEFAULT_STRATEGIES)
        available = [s for s in strategy_names if s in self._strategies]

        if not available:
            available = [s for s in _DEFAULT_STRATEGIES if s in self._strategies]

        if domain:
            domain_stats = self._domain_stats.get(domain, {})
            return sorted(available, key=lambda s: (
                -domain_stats.get(s, StrategyStats()).success_rate,
                self._strategies[s].tier.value,
            ))

        return available

    def get_all_strategies(self) -> list[str]:
        """Get all registered strategy names.

        Returns:
            List of all strategy names, ordered by tier.
        """
        return sorted(
            self._strategies.keys(),
            key=lambda s: self._strategies[s].tier.value,
        )

    def get_strategy_info(self, name: str) -> BypassStrategy | None:
        """Get strategy metadata by name.

        Args:
            name: Strategy name.

        Returns:
            BypassStrategy or None if not registered.
        """
        return self._strategies.get(name)

    # -------------------------------------------------------------------------
    # Strategy Execution (synchronous — pipeline is sync)
    # -------------------------------------------------------------------------

    def execute_strategy(
        self,
        url: str,
        strategy_name: str,
        site_id: str = "",
        timeout: float = 30.0,
        extra_headers: dict[str, str] | None = None,
    ) -> BypassResult:
        """Execute a single bypass strategy for a URL.

        Args:
            url: The URL to fetch.
            strategy_name: Name of the strategy to execute.
            site_id: Site identifier for logging.
            timeout: Request timeout in seconds.
            extra_headers: Additional headers to include.

        Returns:
            BypassResult with success/failure and content.
        """
        strategy = self._strategies.get(strategy_name)
        if strategy is None:
            return BypassResult(
                success=False,
                strategy_name=strategy_name,
                error=f"Unknown strategy: {strategy_name}",
            )

        domain = urlparse(url).hostname or site_id
        start = time.monotonic()

        try:
            result = self._dispatch(
                strategy_name, url, timeout, extra_headers or {},
            )
            latency_ms = (time.monotonic() - start) * 1000

            # Validate result
            if result.success and len(result.html) < _MIN_BODY_LENGTH:
                result = BypassResult(
                    success=False,
                    html=result.html,
                    status_code=result.status_code,
                    strategy_name=strategy_name,
                    strategy_tier=strategy.tier.value,
                    error=f"Response too short ({len(result.html)} bytes < {_MIN_BODY_LENGTH})",
                    latency_ms=latency_ms,
                )

            result.strategy_name = strategy_name
            result.strategy_tier = strategy.tier.value
            result.latency_ms = latency_ms

            # Record stats
            self._record_stat(domain, strategy_name, result.success, latency_ms)

            logger.info(
                "bypass_strategy_result site_id=%s strategy=%s tier=%s "
                "success=%s status=%s body_len=%s latency=%.0fms",
                site_id, strategy_name, strategy.tier.value,
                result.success, result.status_code, len(result.html),
                latency_ms,
            )

            return result

        except KeyboardInterrupt:
            raise
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            self._record_stat(domain, strategy_name, False, latency_ms)
            logger.warning(
                "bypass_strategy_error site_id=%s strategy=%s error=%s",
                site_id, strategy_name, str(e)[:200],
            )
            return BypassResult(
                success=False,
                strategy_name=strategy_name,
                strategy_tier=strategy.tier.value,
                error=f"{type(e).__name__}: {str(e)[:200]}",
                latency_ms=latency_ms,
            )

    # Errors indicating a strategy is not installed/configured (not a real attempt)
    _UNAVAILABLE_ERRORS = frozenset({
        "not installed", "not configured", "No proxy pool configured",
        "No handler for strategy",
    })

    @staticmethod
    def _is_unavailable_error(result: BypassResult) -> bool:
        """Check if a BypassResult failed because the strategy is unavailable.

        Unavailable means the library is not installed or the strategy is
        not configured (e.g., no proxy pool). These should NOT count as
        real attempts against the max_attempts budget.

        Args:
            result: The BypassResult to check.

        Returns:
            True if the failure is due to unavailability, not a real attempt.
        """
        if result.success:
            return False
        if not result.error:
            return False
        error_lower = result.error.lower()
        return any(marker in error_lower for marker in (
            "not installed", "no proxy pool", "no handler for strategy",
        ))

    def try_strategies(
        self,
        url: str,
        block_type: BlockType | None,
        site_id: str = "",
        max_attempts: int = _MAX_STRATEGIES_PER_URL,
        timeout: float = 30.0,
    ) -> BypassResult:
        """Try multiple strategies in order until one succeeds.

        Selects strategies based on the block type, tries them in
        cost-ascending order, and returns the first successful result.

        Strategies that are unavailable (library not installed, no proxy
        pool, etc.) do NOT count against the max_attempts budget. Only
        real network attempts count.

        Args:
            url: The URL to fetch.
            block_type: The detected block type (None for unknown).
            site_id: Site identifier for logging and stats.
            max_attempts: Maximum number of strategies to try.
            timeout: Request timeout per strategy.

        Returns:
            BypassResult from the first successful strategy, or the
            last failure if all strategies are exhausted.
        """
        domain = urlparse(url).hostname or site_id

        if block_type is not None:
            strategies = self.get_strategies_for_block(block_type, domain)
        else:
            cached = self._domain_block_cache.get(domain)
            if cached is not None:
                strategies = self.get_strategies_for_block(cached, domain)
            else:
                strategies = [s for s in _DEFAULT_STRATEGIES if s in self._strategies]

        tried: set[str] = set()
        real_attempts = 0
        last_result = BypassResult(success=False, error="No strategies available")

        for strategy_name in strategies:
            if real_attempts >= max_attempts:
                break
            if strategy_name in tried:
                continue
            tried.add(strategy_name)

            result = self.execute_strategy(
                url, strategy_name, site_id, timeout,
            )

            if result.success:
                return result

            # Unavailable strategies (ImportError, no proxy) don't count
            # as real attempts — skip them without penalty.
            if not self._is_unavailable_error(result):
                real_attempts += 1

            # If block type changed, re-select strategies
            if result.block_detected and result.block_detected != block_type:
                self._domain_block_cache[domain] = result.block_detected
                new_strategies = self.get_strategies_for_block(
                    result.block_detected, domain,
                )
                # Add untried strategies from new list
                for s in new_strategies:
                    if s not in tried and s not in strategies:
                        strategies.append(s)

            last_result = result

        return last_result

    def try_all_strategies(
        self,
        url: str,
        block_type: BlockType | None,
        site_id: str = "",
        timeout: float = 30.0,
        start_offset: int = 0,
    ) -> BypassResult:
        """Try ALL registered strategies for a URL (no cap on attempts).

        This is the entry point for the Never-Abandon loop. Unlike
        try_strategies() which caps at _MAX_STRATEGIES_PER_URL, this
        method iterates through every registered strategy. Strategies
        that are unavailable (not installed) are silently skipped.

        The start_offset parameter allows rotating the strategy order
        across Never-Abandon cycles, so each cycle begins from a
        different strategy instead of always starting with the same one.

        Args:
            url: The URL to fetch.
            block_type: The detected block type (None for unknown).
            site_id: Site identifier for logging and stats.
            timeout: Request timeout per strategy.
            start_offset: Index offset to rotate strategy order. Each
                Never-Abandon cycle should pass a different offset to
                ensure different strategies are tried first.

        Returns:
            BypassResult from the first successful strategy, or the
            last failure if all strategies are exhausted.
        """
        domain = urlparse(url).hostname or site_id

        if block_type is not None:
            strategies = self.get_strategies_for_block(block_type, domain)
        else:
            cached = self._domain_block_cache.get(domain)
            if cached is not None:
                strategies = self.get_strategies_for_block(cached, domain)
            else:
                strategies = [s for s in _DEFAULT_STRATEGIES if s in self._strategies]

        # Add any registered strategies not in the initial list
        all_registered = set(self._strategies.keys())
        for s in all_registered:
            if s not in strategies:
                strategies.append(s)

        # Rotate strategy order by start_offset so each cycle tries
        # different strategies first
        if start_offset > 0 and len(strategies) > 1:
            offset = start_offset % len(strategies)
            strategies = strategies[offset:] + strategies[:offset]

        tried: set[str] = set()
        last_result = BypassResult(success=False, error="No strategies available")

        for strategy_name in strategies:
            if strategy_name in tried:
                continue
            tried.add(strategy_name)

            result = self.execute_strategy(
                url, strategy_name, site_id, timeout,
            )

            if result.success:
                return result

            # Skip unavailable strategies silently — don't log as failures
            if self._is_unavailable_error(result):
                logger.debug(
                    "strategy_unavailable site_id=%s strategy=%s reason=%s",
                    site_id, strategy_name, result.error,
                )
                continue

            # If block type changed, re-select strategies
            if result.block_detected and result.block_detected != block_type:
                self._domain_block_cache[domain] = result.block_detected
                new_strategies = self.get_strategies_for_block(
                    result.block_detected, domain,
                )
                for s in new_strategies:
                    if s not in tried and s not in strategies:
                        strategies.append(s)

            last_result = result

        return last_result

    # -------------------------------------------------------------------------
    # Strategy Dispatch (routes to concrete implementations)
    # -------------------------------------------------------------------------

    def _dispatch(
        self,
        strategy_name: str,
        url: str,
        timeout: float,
        extra_headers: dict[str, str],
    ) -> BypassResult:
        """Route to the concrete strategy implementation.

        Args:
            strategy_name: Which strategy to execute.
            url: Target URL.
            timeout: Request timeout.
            extra_headers: Additional request headers.

        Returns:
            BypassResult from the strategy.
        """
        handlers: dict[str, Callable[..., BypassResult]] = {
            "rotate_user_agent": self._exec_rotate_ua,
            "exponential_backoff": self._exec_backoff,
            "rss_feed_fallback": self._exec_rss_feed,
            "amp_version_fallback": self._exec_amp_version,
            "google_cache_fallback": self._exec_google_cache,
            "gdelt_api_fallback": self._exec_gdelt_api,
            "curl_cffi_impersonate": self._exec_curl_cffi,
            "fingerprint_rotation": self._exec_fingerprint_rotation,
            "cloudscraper_solve": self._exec_cloudscraper,
            "patchright_stealth": self._exec_patchright,
            "camoufox_stealth": self._exec_camoufox,
            "proxy_rotation": self._exec_proxy_rotation,
            "archive_today_fallback": self._exec_archive_today,
            "wayback_fallback": self._exec_wayback,
        }

        handler = handlers.get(strategy_name)
        if handler is None:
            return BypassResult(
                success=False,
                error=f"No handler for strategy: {strategy_name}",
            )

        return handler(url, timeout, extra_headers)

    # -------------------------------------------------------------------------
    # Tier 0 Strategy Implementations
    # -------------------------------------------------------------------------

    def _exec_rotate_ua(
        self, url: str, timeout: float, extra_headers: dict[str, str],
    ) -> BypassResult:
        """Tier 0: Simple User-Agent rotation with httpx."""
        import httpx

        ua = random.choice(_USER_AGENTS)
        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            **extra_headers,
        }

        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            http2=True,
        ) as client:
            r = client.get(url, headers=headers)
            return BypassResult(
                success=r.status_code == 200 and len(r.text) >= _MIN_BODY_LENGTH,
                html=r.text,
                status_code=r.status_code,
            )

    def _exec_backoff(
        self, url: str, timeout: float, extra_headers: dict[str, str],
    ) -> BypassResult:
        """Tier 0: Exponential backoff (wait 5-15s) then retry with curl_cffi."""
        delay = random.uniform(5.0, 15.0)
        time.sleep(delay)
        return self._exec_curl_cffi(url, timeout, extra_headers)

    def _exec_rss_feed(
        self, url: str, timeout: float, extra_headers: dict[str, str],
    ) -> BypassResult:
        """Tier 0: Try RSS/Atom feed for the domain, including Google News RSS."""
        import feedparser

        parsed = urlparse(url)
        domain = parsed.hostname or ""

        # Build list of feed URLs: site's own RSS paths + Google News RSS proxy
        feed_urls: list[str] = [
            f"{parsed.scheme}://{domain}{path}" for path in _RSS_PATHS
        ]
        # Google News RSS proxy — bypasses site's WAF entirely
        google_news_url = (
            f"https://news.google.com/rss/search?q=site:{domain}+when:1d"
            f"&hl=en-US&gl=US&ceid=US:en"
        )
        feed_urls.append(google_news_url)

        for feed_url in feed_urls:
            try:
                feed = feedparser.parse(feed_url)
                if not feed.entries:
                    continue

                # Look for matching entry
                for entry in feed.entries:
                    entry_link = entry.get("link", "")
                    if url in entry_link or entry_link in url:
                        content = entry.get("content", [{}])[0].get("value", "")
                        if not content:
                            content = entry.get("summary", "")
                        if len(content) >= _MIN_BODY_LENGTH:
                            return BypassResult(
                                success=True,
                                html=content,
                                status_code=200,
                            )

                # If no exact match, return the first entry with substantial content
                # (useful when URL patterns don't match exactly)
                for entry in feed.entries[:5]:
                    content = entry.get("content", [{}])[0].get("value", "")
                    if not content:
                        content = entry.get("summary", "")
                    if len(content) >= _MIN_BODY_LENGTH:
                        return BypassResult(
                            success=True,
                            html=content,
                            status_code=200,
                        )
            except Exception:
                continue

        return BypassResult(success=False, error="No RSS feed found or no matching entry")

    def _exec_amp_version(
        self, url: str, timeout: float, extra_headers: dict[str, str],
    ) -> BypassResult:
        """Tier 0: Try AMP version of the page."""
        try:
            from curl_cffi import requests as curl_requests
        except ImportError:
            return BypassResult(success=False, error="curl_cffi not installed")

        session = curl_requests.Session(impersonate="chrome120")

        # Try /amp suffix
        amp_urls = [
            f"{url}/amp",
            f"{url}?amp=1",
        ]

        # Try AMP CDN
        parsed = urlparse(url)
        if parsed.hostname:
            amp_cdn = (
                f"https://{parsed.hostname.replace('.', '-')}.cdn.ampproject.org"
                f"/c/s/{parsed.hostname}{parsed.path}"
            )
            amp_urls.append(amp_cdn)

        for amp_url in amp_urls:
            try:
                r = session.get(amp_url, timeout=timeout, allow_redirects=True)
                if r.status_code == 200 and len(r.text) >= _MIN_BODY_LENGTH:
                    return BypassResult(
                        success=True,
                        html=r.text,
                        status_code=200,
                    )
            except Exception:
                continue

        return BypassResult(success=False, error="No AMP version available")

    def _exec_google_cache(
        self, url: str, timeout: float, extra_headers: dict[str, str],
    ) -> BypassResult:
        """Tier 0: Try Google's cached version."""
        try:
            from curl_cffi import requests as curl_requests
        except ImportError:
            return BypassResult(success=False, error="curl_cffi not installed")

        cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{url}"
        session = curl_requests.Session(impersonate="chrome120")

        try:
            r = session.get(cache_url, timeout=timeout)
            if r.status_code == 200 and len(r.text) >= _MIN_BODY_LENGTH:
                return BypassResult(
                    success=True,
                    html=r.text,
                    status_code=200,
                )
        except Exception:
            pass

        return BypassResult(success=False, error="Google Cache not available")

    def _exec_gdelt_api(
        self, url: str, timeout: float, extra_headers: dict[str, str],
    ) -> BypassResult:
        """Tier 0: GDELT DOC API for article URL discovery.

        Queries GDELT's global article index by domain to find article
        URLs and metadata. Useful when the site blocks direct access
        but GDELT has already indexed the content.
        """
        try:
            from curl_cffi import requests as curl_requests
        except ImportError:
            return BypassResult(success=False, error="curl_cffi not installed")

        parsed = urlparse(url)
        domain = parsed.hostname or ""
        if not domain:
            return BypassResult(success=False, error="Cannot extract domain from URL")

        gdelt_url = (
            f"https://api.gdeltproject.org/api/v2/doc/doc"
            f"?query=domain:{domain}&mode=artlist&maxrecords=50"
            f"&format=json&timespan=48h"
        )

        session = curl_requests.Session(impersonate="chrome120")

        try:
            r = session.get(gdelt_url, timeout=timeout)
            if r.status_code != 200:
                return BypassResult(
                    success=False,
                    status_code=r.status_code,
                    error=f"GDELT API returned HTTP {r.status_code}",
                )

            data = r.json()
            articles = data.get("articles", [])

            # Look for the exact URL in GDELT results
            for article in articles:
                article_url = article.get("url", "")
                if url in article_url or article_url in url:
                    # Found a match — try to fetch via GDELT's seendate link
                    # or return the article metadata as content
                    title = article.get("title", "")
                    source = article.get("domain", "")
                    seendate = article.get("seendate", "")
                    # Build minimal HTML from GDELT metadata
                    content = (
                        f"<html><head><title>{title}</title></head>"
                        f"<body><h1>{title}</h1>"
                        f"<p>Source: {source} | Date: {seendate}</p>"
                        f"<p>Original URL: {article_url}</p></body></html>"
                    )
                    if len(content) >= _MIN_BODY_LENGTH:
                        return BypassResult(
                            success=True,
                            html=content,
                            status_code=200,
                        )

            # If no exact match, return first article with content as discovery
            if articles:
                first = articles[0]
                title = first.get("title", "")
                article_url = first.get("url", "")
                content = (
                    f"<html><head><title>{title}</title></head>"
                    f"<body><h1>{title}</h1>"
                    f"<p>URL: {article_url}</p></body></html>"
                )
                if len(content) >= _MIN_BODY_LENGTH:
                    return BypassResult(
                        success=True,
                        html=content,
                        status_code=200,
                    )

        except Exception as e:
            return BypassResult(
                success=False,
                error=f"GDELT API error: {str(e)[:200]}",
            )

        return BypassResult(success=False, error="GDELT: no articles found for domain")

    # -------------------------------------------------------------------------
    # Tier 1 Strategy Implementations
    # -------------------------------------------------------------------------

    def _exec_curl_cffi(
        self, url: str, timeout: float, extra_headers: dict[str, str],
    ) -> BypassResult:
        """Tier 1: curl_cffi with browser TLS fingerprint mimicry.

        The most important single strategy — produces browser-identical
        TLS ClientHello fingerprints (JA3/JA4) without needing a browser.
        10-50x faster than browser automation for sites that only check TLS.
        """
        try:
            from curl_cffi import requests as curl_requests
        except ImportError:
            return BypassResult(success=False, error="curl_cffi not installed")

        profile = random.choice(_FINGERPRINT_PROFILES)
        session = curl_requests.Session(impersonate=profile["impersonate"])

        headers = {
            "User-Agent": profile["user_agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        }
        if profile["sec_ch_ua"]:
            headers["sec-ch-ua"] = profile["sec_ch_ua"]
            headers["sec-ch-ua-mobile"] = "?0"
            headers["sec-ch-ua-platform"] = f'"{profile["platform"]}"'

        headers.update(extra_headers)
        session.headers.update(headers)

        r = session.get(url, timeout=timeout, allow_redirects=True)
        return BypassResult(
            success=r.status_code == 200 and len(r.text) >= _MIN_BODY_LENGTH,
            html=r.text,
            status_code=r.status_code,
        )

    def _exec_fingerprint_rotation(
        self, url: str, timeout: float, extra_headers: dict[str, str],
    ) -> BypassResult:
        """Tier 1: Rotate through multiple TLS fingerprint profiles.

        Different from curl_cffi_impersonate in that it explicitly rotates
        through ALL profiles, not just one random choice.
        """
        try:
            from curl_cffi import requests as curl_requests
        except ImportError:
            return BypassResult(success=False, error="curl_cffi not installed")

        # Try each profile until one works
        profiles = list(_FINGERPRINT_PROFILES)
        random.shuffle(profiles)

        for profile in profiles:
            try:
                session = curl_requests.Session(impersonate=profile["impersonate"])
                headers = {
                    "User-Agent": profile["user_agent"],
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    **extra_headers,
                }
                session.headers.update(headers)
                r = session.get(url, timeout=timeout, allow_redirects=True)
                if r.status_code == 200 and len(r.text) >= _MIN_BODY_LENGTH:
                    return BypassResult(
                        success=True,
                        html=r.text,
                        status_code=r.status_code,
                    )
            except Exception:
                continue

        return BypassResult(success=False, error="All fingerprint profiles failed")

    def _exec_cloudscraper(
        self, url: str, timeout: float, extra_headers: dict[str, str],
    ) -> BypassResult:
        """Tier 1: Solve Cloudflare JS challenges without a browser.

        Uses cloudscraper to parse and execute Cloudflare's JS challenge
        code. Works for ~60-70% of Cloudflare-protected sites.
        """
        try:
            import cloudscraper
        except ImportError:
            return BypassResult(success=False, error="cloudscraper not installed")

        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True},
            delay=10,
        )
        if extra_headers:
            scraper.headers.update(extra_headers)

        r = scraper.get(url, timeout=timeout)
        return BypassResult(
            success=r.status_code == 200 and len(r.text) >= _MIN_BODY_LENGTH,
            html=r.text,
            status_code=r.status_code,
        )

    # -------------------------------------------------------------------------
    # Tier 2 Strategy Implementations (Browser Automation)
    # -------------------------------------------------------------------------

    def _exec_patchright(
        self, url: str, timeout: float, extra_headers: dict[str, str],
    ) -> BypassResult:
        """Tier 2: Patchright (stealth Playwright fork) with anti-detection.

        Removes all automation indicators. Passes bot detection tests
        (creepjs, fingerprint.com). Full Playwright API available.
        ~3-8 seconds per page load, 100-500MB RAM per context.
        """
        try:
            from patchright.sync_api import sync_playwright
        except ImportError:
            return BypassResult(success=False, error="patchright not installed")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            try:
                context = browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent=random.choice(_USER_AGENTS),
                    locale="en-US",
                    timezone_id="America/New_York",
                )
                page = context.new_page()

                if extra_headers:
                    page.set_extra_http_headers(extra_headers)

                response = page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=int(timeout * 1000),
                )
                html = page.content()
                status = response.status if response else 0

                return BypassResult(
                    success=status == 200 and len(html) >= _MIN_BODY_LENGTH,
                    html=html,
                    status_code=status,
                )
            finally:
                browser.close()

    def _exec_camoufox(
        self, url: str, timeout: float, extra_headers: dict[str, str],
    ) -> BypassResult:
        """Tier 2: Camoufox (Firefox fork) with 300+ fingerprint randomizations.

        Uses Firefox instead of Chromium, which is less commonly fingerprinted.
        Automatically randomizes canvas, WebGL, AudioContext, fonts, etc.
        """
        try:
            from camoufox.sync_api import Camoufox
        except ImportError:
            return BypassResult(success=False, error="camoufox not installed")

        with Camoufox(headless=True) as browser:
            page = browser.new_page()

            if extra_headers:
                page.set_extra_http_headers(extra_headers)

            response = page.goto(
                url,
                wait_until="networkidle",
                timeout=int(timeout * 1000),
            )
            html = page.content()
            status = response.status if response else 0

            return BypassResult(
                success=status == 200 and len(html) >= _MIN_BODY_LENGTH,
                html=html,
                status_code=status,
            )

    # -------------------------------------------------------------------------
    # Tier 3 Strategy Implementations (External Services)
    # -------------------------------------------------------------------------

    def _exec_proxy_rotation(
        self, url: str, timeout: float, extra_headers: dict[str, str],
    ) -> BypassResult:
        """Tier 3: Proxy rotation with TLS fingerprint mimicry.

        Combines curl_cffi's browser fingerprint with a rotating proxy
        to get both IP rotation and TLS stealth.
        """
        if not self.proxy_pool:
            return BypassResult(success=False, error="No proxy pool configured")

        try:
            from curl_cffi import requests as curl_requests
        except ImportError:
            return BypassResult(success=False, error="curl_cffi not installed")

        proxy = self.proxy_pool[self._proxy_index % len(self.proxy_pool)]
        self._proxy_index += 1

        profile = random.choice(_FINGERPRINT_PROFILES)
        session = curl_requests.Session(impersonate=profile["impersonate"])
        session.proxies = {"https": proxy, "http": proxy}

        headers = {
            "User-Agent": profile["user_agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            **extra_headers,
        }
        session.headers.update(headers)

        r = session.get(url, timeout=timeout, allow_redirects=True)
        return BypassResult(
            success=r.status_code == 200 and len(r.text) >= _MIN_BODY_LENGTH,
            html=r.text,
            status_code=r.status_code,
        )

    # -------------------------------------------------------------------------
    # Tier 4 Strategy Implementations (Archive Sources)
    # -------------------------------------------------------------------------

    def _exec_archive_today(
        self, url: str, timeout: float, extra_headers: dict[str, str],
    ) -> BypassResult:
        """Tier 4: Fetch from archive.today (archive.ph) mirror.

        archive.today takes snapshots of web pages and serves them from
        its own domain, bypassing the original site's WAF entirely.
        Uses /newest/ endpoint to get the most recent snapshot.
        """
        try:
            from curl_cffi import requests as curl_requests
        except ImportError:
            return BypassResult(success=False, error="curl_cffi not installed")

        session = curl_requests.Session(impersonate="chrome120")

        # archive.today has multiple domains; try them in order
        archive_domains = ["archive.today", "archive.ph", "archive.is"]

        for archive_domain in archive_domains:
            archive_url = f"https://{archive_domain}/newest/{url}"
            try:
                r = session.get(
                    archive_url,
                    timeout=timeout,
                    allow_redirects=True,
                )
                if r.status_code == 200 and len(r.text) >= _MIN_BODY_LENGTH:
                    return BypassResult(
                        success=True,
                        html=r.text,
                        status_code=200,
                    )
            except Exception:
                continue

        return BypassResult(success=False, error="archive.today: no snapshot available")

    def _exec_wayback(
        self, url: str, timeout: float, extra_headers: dict[str, str],
    ) -> BypassResult:
        """Tier 4: Fetch from Internet Archive Wayback Machine.

        Uses the Wayback CDX API to find the most recent snapshot,
        then fetches the archived page. Content may be stale (hours to days).
        """
        try:
            from curl_cffi import requests as curl_requests
        except ImportError:
            return BypassResult(success=False, error="curl_cffi not installed")

        session = curl_requests.Session(impersonate="chrome120")

        # Try direct Wayback URL first (fastest)
        wayback_url = f"https://web.archive.org/web/2/{url}"
        try:
            r = session.get(wayback_url, timeout=timeout)
            if r.status_code == 200 and len(r.text) >= _MIN_BODY_LENGTH:
                return BypassResult(
                    success=True,
                    html=r.text,
                    status_code=200,
                )
        except Exception:
            pass

        # Fallback: CDX API search for most recent snapshot
        try:
            cdx_url = "https://web.archive.org/cdx/search/cdx"
            params = {
                "url": url,
                "output": "json",
                "limit": 1,
                "sort": "reverse",
                "fl": "timestamp,original,statuscode",
            }
            r = session.get(cdx_url, params=params, timeout=timeout)
            rows = r.json()
            if len(rows) >= 2:
                timestamp = rows[1][0]
                archived_url = f"https://web.archive.org/web/{timestamp}/{url}"
                r = session.get(archived_url, timeout=timeout)
                if r.status_code == 200 and len(r.text) >= _MIN_BODY_LENGTH:
                    return BypassResult(
                        success=True,
                        html=r.text,
                        status_code=200,
                    )
        except Exception:
            pass

        return BypassResult(success=False, error="Wayback Machine: no snapshot available")

    # -------------------------------------------------------------------------
    # Statistics & Learning
    # -------------------------------------------------------------------------

    def _record_stat(
        self,
        domain: str,
        strategy_name: str,
        success: bool,
        latency_ms: float,
    ) -> None:
        """Record a strategy attempt for adaptive learning.

        Args:
            domain: The domain this attempt was for.
            strategy_name: Which strategy was used.
            success: Whether the strategy succeeded.
            latency_ms: Latency of the attempt.
        """
        if domain not in self._domain_stats:
            self._domain_stats[domain] = {}
        if strategy_name not in self._domain_stats[domain]:
            self._domain_stats[domain][strategy_name] = StrategyStats()

        stats = self._domain_stats[domain][strategy_name]
        stats.attempts += 1
        if success:
            stats.successes += 1
        stats.total_latency_ms += latency_ms

    def update_block_cache(self, domain: str, block_type: BlockType) -> None:
        """Update the per-domain block type cache.

        Called by the pipeline when the BlockDetector identifies a block.

        Args:
            domain: Domain name.
            block_type: The detected block type.
        """
        self._domain_block_cache[domain] = block_type

    def get_domain_stats(self, domain: str) -> dict[str, dict[str, Any]]:
        """Get per-strategy statistics for a domain.

        Args:
            domain: Domain name.

        Returns:
            Dict mapping strategy_name -> {attempts, successes, success_rate, avg_latency_ms}.
        """
        stats = self._domain_stats.get(domain, {})
        return {
            name: {
                "attempts": s.attempts,
                "successes": s.successes,
                "success_rate": round(s.success_rate, 3),
                "avg_latency_ms": round(s.avg_latency_ms, 1),
            }
            for name, s in stats.items()
        }

    def get_statistics(self) -> dict[str, Any]:
        """Get aggregate statistics across all domains.

        Returns:
            Dict with strategy performance summary.
        """
        total_attempts = 0
        total_successes = 0
        strategy_totals: dict[str, StrategyStats] = {}

        for domain_stats in self._domain_stats.values():
            for name, stats in domain_stats.items():
                total_attempts += stats.attempts
                total_successes += stats.successes
                if name not in strategy_totals:
                    strategy_totals[name] = StrategyStats()
                strategy_totals[name].attempts += stats.attempts
                strategy_totals[name].successes += stats.successes
                strategy_totals[name].total_latency_ms += stats.total_latency_ms

        return {
            "total_attempts": total_attempts,
            "total_successes": total_successes,
            "overall_success_rate": (
                round(total_successes / total_attempts, 3) if total_attempts > 0 else 0.0
            ),
            "domains_tracked": len(self._domain_stats),
            "strategies_available": len(self._strategies),
            "per_strategy": {
                name: {
                    "attempts": s.attempts,
                    "successes": s.successes,
                    "success_rate": round(s.success_rate, 3),
                    "avg_latency_ms": round(s.avg_latency_ms, 1),
                }
                for name, s in sorted(strategy_totals.items())
            },
        }

    def __repr__(self) -> str:
        stats = self.get_statistics()
        return (
            f"DynamicBypassEngine("
            f"strategies={stats['strategies_available']}, "
            f"domains={stats['domains_tracked']}, "
            f"success_rate={stats['overall_success_rate']:.1%})"
        )
