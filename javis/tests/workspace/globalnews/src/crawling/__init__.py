"""Crawling Layer: URL discovery, content extraction, anti-block, deduplication.

Handles parallel crawling of 116 news sites across 10 groups (A-J)
using RSS, Sitemap, API, Playwright, and DOM strategies.

Modules:
    contracts         - Data contracts (RawArticle, DiscoveredURL, CrawlResult)
    network_guard     - 5-retry exponential backoff + rate limiting + circuit breaker
    url_discovery     - 3-Tier URL discovery (RSS/Sitemap/DOM/Playwright)
    article_extractor - Content extraction (Fundus/Trafilatura/CSS fallback)
    crawler           - Main crawl orchestrator (sequential per-site pipeline)
    pipeline          - End-to-end crawling pipeline with 4-level retry
    retry_manager     - 4-level hierarchical retry system (5x2x3x3=90 max)
    crawl_report      - Structured crawl report generation
    anti_block        - 6-Tier escalation coordinator
    block_detector    - 7-type block diagnosis
    circuit_breaker   - Circuit Breaker state machine
    stealth_browser   - Playwright/Patchright wrapper
    dedup             - URL normalization + SimHash/MinHash dedup
    ua_manager        - 4-tier UA pool (61+ agents)
    session_manager   - Cookie cycling, header diversification
    rate_limiter      - Per-site rate limiting
    proxy_manager     - Geographic proxy routing (20 sites)
"""

# ---------------------------------------------------------------------------
# Core crawling engine (crawler-core-dev)
# ---------------------------------------------------------------------------
from src.crawling.contracts import RawArticle, DiscoveredURL, CrawlResult, compute_content_hash
from src.crawling.network_guard import NetworkGuard, FetchResponse, RateLimiter
from src.crawling.url_discovery import (
    URLDiscovery, RSSParser, SitemapParser, DOMNavigator,
    GoogleNewsDiscovery, GDELTDiscovery, normalize_url,
)
from src.crawling.article_extractor import (
    ArticleExtractor, ExtractionResult, fetch_via_cache_proxies,
    EXTERNAL_DISCOVERY_METHODS,
)
from src.crawling.crawler import Crawler, JSONLWriter, CrawlState

# ---------------------------------------------------------------------------
# Pipeline integration (Step 12: pipeline-integrator)
# ---------------------------------------------------------------------------
from src.crawling.pipeline import CrawlingPipeline, run_crawl_pipeline
from src.crawling.retry_manager import RetryManager, SiteRetryState, StrategyMode
from src.crawling.crawl_report import generate_crawl_report, print_crawl_summary

# ---------------------------------------------------------------------------
# Anti-Block System (anti-block-dev) -- imported conditionally
# These modules may not exist yet if the anti-block-dev task has not completed.
# ---------------------------------------------------------------------------
try:
    from src.crawling.block_detector import (
        BlockDetector,
        BlockDiagnosis,
        BlockType,
        HttpResponse,
    )
    from src.crawling.anti_block import (
        AntiBlockEngine,
        EscalationDecision,
        EscalationTier,
        SiteProfile,
        TIER_STRATEGIES,
    )
    from src.crawling.circuit_breaker import (
        BlockAwareCircuitBreaker,
        CircuitBreakerCoordinator,
    )
    from src.crawling.stealth_browser import (
        StealthBrowser,
        BrowserProfile,
        generate_random_profile,
    )
    _HAS_ANTI_BLOCK = True
except ImportError:
    _HAS_ANTI_BLOCK = False

__all__ = [
    # Contracts
    "RawArticle",
    "DiscoveredURL",
    "CrawlResult",
    "compute_content_hash",
    # Network Guard
    "NetworkGuard",
    "FetchResponse",
    "RateLimiter",
    # URL Discovery
    "URLDiscovery",
    "RSSParser",
    "SitemapParser",
    "DOMNavigator",
    "GoogleNewsDiscovery",
    "GDELTDiscovery",
    "normalize_url",
    # Article Extraction
    "ArticleExtractor",
    "ExtractionResult",
    "fetch_via_cache_proxies",
    "EXTERNAL_DISCOVERY_METHODS",
    # Crawler
    "Crawler",
    "JSONLWriter",
    "CrawlState",
    # Pipeline integration
    "CrawlingPipeline",
    "run_crawl_pipeline",
    "RetryManager",
    "SiteRetryState",
    "StrategyMode",
    "generate_crawl_report",
    "print_crawl_summary",
]

# Conditionally extend __all__ with anti-block exports
if _HAS_ANTI_BLOCK:
    __all__.extend([
        "BlockDetector",
        "BlockDiagnosis",
        "BlockType",
        "HttpResponse",
        "AntiBlockEngine",
        "EscalationDecision",
        "EscalationTier",
        "SiteProfile",
        "TIER_STRATEGIES",
        "BlockAwareCircuitBreaker",
        "CircuitBreakerCoordinator",
        "StealthBrowser",
        "BrowserProfile",
        "generate_random_profile",
    ])
