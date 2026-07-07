"""Abstract base class for site-specific crawling adapters.

Each news site in the GlobalNews system has a dedicated adapter that
inherits from BaseSiteAdapter. The adapter encapsulates:
  - Site metadata (domain, language, group).
  - CSS/XPath selectors for article field extraction.
  - URL discovery entry points (RSS, sitemap, section pages).
  - Pagination logic for listing pages.
  - Rate-limiting and anti-block configuration.
  - Encoding handling for legacy character sets.

Reference:
    Step 5 Architecture Blueprint, Section 4.2 (RawArticle contract).
    Step 6 Crawling Strategies (per-site selector tables).
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)


class BaseSiteAdapter(ABC):
    """Abstract base class for all site-specific crawling adapters.

    Subclasses MUST set all uppercase class attributes and implement
    the abstract methods ``extract_article`` and ``get_section_urls``.

    Class Attributes:
        SITE_ID: Unique key matching ``sources.yaml`` (e.g., "chosun").
        SITE_NAME: Human-readable name (e.g., "Chosun Ilbo").
        SITE_URL: Canonical base URL including scheme (e.g., "https://www.chosun.com").
        LANGUAGE: ISO 639-1 code, default "en".
        REGION: Geographic region code (e.g., "kr", "us").
        GROUP: Site group from workflow.md (e.g., "A", "B").

        RSS_URL: Primary RSS feed URL. Empty string if RSS unavailable.
        RSS_URLS: List of category RSS feed URLs (for sites with multiple feeds).
        SITEMAP_URL: Sitemap URL (relative or absolute). Empty string if unavailable.

        TITLE_CSS: Primary CSS selector for article title.
        TITLE_CSS_FALLBACK: Fallback CSS selector for title.
        BODY_CSS: Primary CSS selector for article body container.
        BODY_CSS_FALLBACK: Fallback CSS selector for body.
        DATE_CSS: CSS selector for publication date element.
        AUTHOR_CSS: CSS selector for author/byline element.
        ARTICLE_LINK_CSS: CSS selector for article links on listing pages.

        BODY_EXCLUDE_CSS: CSS selectors for elements to remove from body.

        SECTION_URLS: List of section/category page URLs for DOM discovery.
        PAGINATION_TYPE: One of "none", "page_number", "load_more", "infinite_scroll".
        PAGINATION_PARAM: URL parameter name for page number (e.g., "page").
        MAX_PAGES: Maximum pages to crawl per section.

        RATE_LIMIT_SECONDS: Minimum delay between requests to this site.
        MAX_REQUESTS_PER_HOUR: Upper bound on hourly request count.
        JITTER_SECONDS: Random jitter added to rate limit (0 = none).

        ANTI_BLOCK_TIER: Default escalation tier (1-6).
        UA_TIER: User-Agent rotation tier (1-4).
        REQUIRES_PROXY: Whether a regional proxy is required.
        PROXY_REGION: Required proxy region (e.g., "kr").
        BOT_BLOCK_LEVEL: Expected blocking aggressiveness ("LOW", "MEDIUM", "HIGH").

        PAYWALL_TYPE: "none", "soft-metered", "hard", "freemium".
        CHARSET: Expected character encoding ("utf-8", "euc-kr", etc.).
        RENDERING_REQUIRED: Whether JavaScript rendering is needed.
    """

    # --- Site identity ---
    SITE_ID: str = ""
    SITE_NAME: str = ""
    SITE_URL: str = ""
    LANGUAGE: str = "en"
    REGION: str = ""
    GROUP: str = ""

    # --- URL discovery ---
    RSS_URL: str = ""
    RSS_URLS: list[str] = []  # noqa: RUF012 — mutable default, intentional for subclass override
    SITEMAP_URL: str = ""

    # --- Article extraction selectors ---
    TITLE_CSS: str = ""
    TITLE_CSS_FALLBACK: str = ""
    BODY_CSS: str = ""
    BODY_CSS_FALLBACK: str = ""
    DATE_CSS: str = ""
    AUTHOR_CSS: str = ""
    ARTICLE_LINK_CSS: str = ""

    # Elements to strip from body
    BODY_EXCLUDE_CSS: str = (
        "script, style, iframe, "
        "div.ad-container, div.advertisement, "
        "div.related-articles, div.related, "
        "div.social-share, div.sns-share, "
        "div.comments, div.comment-section, "
        "nav, aside, footer"
    )

    # --- Section/listing pages ---
    SECTION_URLS: list[str] = []  # noqa: RUF012 — mutable default, intentional for subclass override
    PAGINATION_TYPE: str = "none"
    PAGINATION_PARAM: str = "page"
    MAX_PAGES: int = 5

    # --- Rate limiting ---
    RATE_LIMIT_SECONDS: float = 5.0
    MAX_REQUESTS_PER_HOUR: int = 720
    JITTER_SECONDS: float = 0.0

    # --- Anti-block ---
    ANTI_BLOCK_TIER: int = 1
    UA_TIER: int = 2
    REQUIRES_PROXY: bool = False
    PROXY_REGION: str = ""
    BOT_BLOCK_LEVEL: str = "MEDIUM"

    # --- Extraction config ---
    PAYWALL_TYPE: str = "none"
    CHARSET: str = "utf-8"
    RENDERING_REQUIRED: bool = False

    # -----------------------------------------------------------------------
    # Abstract methods
    # -----------------------------------------------------------------------

    @abstractmethod
    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from raw HTML.

        Implementations should use site-specific CSS selectors to extract
        title, body, date, author, and category. The returned dict feeds
        into ``ExtractionResult`` / ``RawArticle`` creation.

        Args:
            html: Raw HTML content of the article page.
            url: Canonical URL of the article.

        Returns:
            Dictionary with keys:
                title (str): Article headline.
                body (str): Full body text with ads/navigation stripped.
                published_at (datetime | None): Publication datetime in UTC.
                author (str | None): Author name.
                category (str | None): Section or category name.
        """
        ...

    @abstractmethod
    def get_section_urls(self) -> list[str]:
        """Return section/category page URLs for DOM-based article discovery.

        These URLs are used as the fallback when RSS and sitemap discovery
        fail. Each section URL should be a listing page containing article
        links.

        Returns:
            List of absolute section page URLs.
        """
        ...

    # -----------------------------------------------------------------------
    # Default implementations (override per site as needed)
    # -----------------------------------------------------------------------

    def get_article_links_from_page(self, html: str) -> list[str]:
        """Extract article URLs from a section/listing page.

        Uses ``ARTICLE_LINK_CSS`` to find article links. Falls back to
        generic ``a[href]`` filtering by URL pattern.

        Args:
            html: HTML content of the listing page.

        Returns:
            List of absolute article URLs (deduplicated).
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.warning("beautifulsoup4_not_available")
            return []

        soup = BeautifulSoup(html, "html.parser")
        links: list[str] = []
        seen: set[str] = set()

        # Try site-specific selector first
        if self.ARTICLE_LINK_CSS:
            for el in soup.select(self.ARTICLE_LINK_CSS):
                href = el.get("href", "")
                if href:
                    abs_url = urljoin(self.SITE_URL, href)
                    if abs_url not in seen and self._is_article_url(abs_url):
                        seen.add(abs_url)
                        links.append(abs_url)

        # Fallback: all <a> tags with href matching article URL pattern
        if not links:
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                abs_url = urljoin(self.SITE_URL, href)
                if abs_url not in seen and self._is_article_url(abs_url):
                    seen.add(abs_url)
                    links.append(abs_url)

        return links

    def normalize_date(self, date_str: str) -> datetime | None:
        """Parse a date string to a UTC datetime.

        Tries ISO 8601, common web date formats, and RFC 2822 in order.
        Subclasses should override for site-specific date patterns (e.g.,
        Korean date formats).

        Args:
            date_str: Raw date string from the page.

        Returns:
            datetime in UTC, or None if parsing fails.
        """
        if not date_str or not date_str.strip():
            return None

        date_str = date_str.strip()

        # ISO 8601
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (ValueError, TypeError):
            pass

        # Common patterns
        patterns = [
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%Y.%m.%d %H:%M:%S",
            "%Y.%m.%d %H:%M",
            "%Y.%m.%d",
        ]
        for fmt in patterns:
            try:
                dt = datetime.strptime(date_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except (ValueError, TypeError):
                continue

        # RFC 2822
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (ValueError, TypeError, IndexError):
            pass

        return None

    def handle_encoding(self, raw_bytes: bytes) -> str:
        """Decode raw bytes using the site's expected encoding.

        Default is UTF-8 with error replacement. Override for sites that
        use EUC-KR, CP949, or other legacy encodings.

        Args:
            raw_bytes: Raw response bytes.

        Returns:
            Decoded string.
        """
        return raw_bytes.decode(self.CHARSET, errors="replace")

    def get_rss_urls(self) -> list[str]:
        """Return all RSS feed URLs for this site.

        Returns both the primary RSS_URL and any category-specific RSS_URLS.

        Returns:
            List of RSS feed URLs (may be empty).
        """
        urls: list[str] = []
        if self.RSS_URL:
            urls.append(self.RSS_URL)
        for u in self.RSS_URLS:
            if u and u not in urls:
                urls.append(u)
        return urls

    def get_selectors(self) -> dict[str, str]:
        """Return a dictionary of CSS selectors for the article extractor.

        Returns:
            Dict with keys: title_css, body_css, date_css, author_css,
            article_link_css. Values are CSS selector strings.
        """
        return {
            "title_css": self.TITLE_CSS,
            "title_css_fallback": self.TITLE_CSS_FALLBACK,
            "body_css": self.BODY_CSS,
            "body_css_fallback": self.BODY_CSS_FALLBACK,
            "date_css": self.DATE_CSS,
            "author_css": self.AUTHOR_CSS,
            "article_link_css": self.ARTICLE_LINK_CSS,
            "body_exclude_css": self.BODY_EXCLUDE_CSS,
        }

    def get_anti_block_config(self) -> dict[str, Any]:
        """Return anti-block configuration for the HTTP client.

        Returns:
            Dict with keys: tier, ua_tier, requires_proxy, proxy_region,
            rate_limit, max_requests_per_hour, jitter, bot_block_level.
        """
        return {
            "tier": self.ANTI_BLOCK_TIER,
            "ua_tier": self.UA_TIER,
            "requires_proxy": self.REQUIRES_PROXY,
            "proxy_region": self.PROXY_REGION,
            "rate_limit": self.RATE_LIMIT_SECONDS,
            "max_requests_per_hour": self.MAX_REQUESTS_PER_HOUR,
            "jitter": self.JITTER_SECONDS,
            "bot_block_level": self.BOT_BLOCK_LEVEL,
        }

    def _is_article_url(self, url: str) -> bool:
        """Check if a URL looks like an article page (not a section or homepage).

        Default heuristic: URL path has at least 2 segments and does not end
        with a common listing page pattern. Subclasses should override for
        site-specific URL patterns.

        Args:
            url: Absolute URL to check.

        Returns:
            True if the URL is likely an article.
        """
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")

        # Must be on the same domain
        site_domain = urlparse(self.SITE_URL).hostname or ""
        url_domain = parsed.hostname or ""
        if site_domain and url_domain and site_domain not in url_domain:
            return False

        # Skip obviously non-article URLs
        skip_patterns = (
            "/tag/", "/tags/", "/author/", "/search",
            "/login", "/signup", "/subscribe", "/about",
            "/contact", "/privacy", "/terms", "/rss",
            "/sitemap", "/feed", ".xml", ".json",
        )
        for pattern in skip_patterns:
            if pattern in path.lower():
                return False

        # Require some depth in the path
        segments = [s for s in path.split("/") if s]
        return len(segments) >= 2

    def _extract_category_from_url(self, url: str, segment_index: int = 1) -> str | None:
        """Extract category/section name from URL path segments.

        Default implementation returns the first meaningful path segment.
        Subclasses should override for sites with non-standard URL structures
        (e.g., subdomain-based categories, nested paths).

        Args:
            url: Article URL.
            segment_index: Which path segment to use (1-based, default 1).

        Returns:
            Category string, or None if not extractable.
        """
        parsed = urlparse(url)
        segments = [s for s in parsed.path.split("/") if s]
        # Skip common non-category segments
        skip = {"article", "articles", "story", "stories", "page", "post", "posts"}
        for seg in segments:
            if seg.lower() not in skip and not seg.isdigit():
                return seg
        return None

    def _extract_meta_content(self, soup: Any, property_name: str) -> str:
        """Extract content from a <meta> tag by property or name attribute.

        Args:
            soup: BeautifulSoup object.
            property_name: Value of the property or name attribute.

        Returns:
            Content string, or empty string if not found.
        """
        tag = soup.find("meta", property=property_name)
        if tag and tag.get("content"):
            return tag["content"].strip()
        tag = soup.find("meta", attrs={"name": property_name})
        if tag and tag.get("content"):
            return tag["content"].strip()
        return ""

    def _extract_json_ld(self, soup: Any) -> dict[str, Any]:
        """Extract the first JSON-LD script from the page.

        Args:
            soup: BeautifulSoup object.

        Returns:
            Parsed JSON-LD dict, or empty dict if not found.
        """
        for script in soup.find_all("script", type="application/ld+json"):
            if script.string:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        # Find NewsArticle or Article type
                        for item in data:
                            if isinstance(item, dict):
                                item_type = item.get("@type", "")
                                if item_type in (
                                    "NewsArticle", "Article",
                                    "ReportageNewsArticle",
                                ):
                                    return item
                        return data[0] if data else {}
                    return data
                except (json.JSONDecodeError, TypeError):
                    continue
        return {}

    def _clean_body_text(self, soup_element: Any) -> str:
        """Remove unwanted elements from a body container and return text.

        Args:
            soup_element: BeautifulSoup Tag for the body container.

        Returns:
            Cleaned body text with paragraphs separated by newlines.
        """
        if not soup_element:
            return ""

        # Remove exclusion elements
        if self.BODY_EXCLUDE_CSS:
            for unwanted in soup_element.select(self.BODY_EXCLUDE_CSS):
                unwanted.decompose()

        return soup_element.get_text(separator="\n", strip=True)

    def _default_extract(self, html: str, url: str) -> dict[str, Any]:
        """Generic article extraction using class-level CSS selectors.

        Provides a working default for adapters that rely on standard
        HTML structure with JSON-LD metadata. Uses TITLE_CSS, BODY_CSS,
        DATE_CSS, AUTHOR_CSS selectors defined on the subclass.

        Subclasses with non-standard page structures should override
        ``extract_article`` directly (see CNNAdapter for an example).

        Args:
            html: Raw HTML content of the article page.
            url: Canonical URL of the article.

        Returns:
            Dictionary with title, body, published_at, author, category,
            is_paywall_truncated.
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.warning("beautifulsoup4 not available for extraction")
            return {
                "title": "", "body": "", "published_at": None,
                "author": None, "category": None, "is_paywall_truncated": False,
            }

        soup = BeautifulSoup(html, "html.parser")
        json_ld = self._extract_json_ld(soup)

        # --- Title ---
        title = ""
        if self.TITLE_CSS:
            el = soup.select_one(self.TITLE_CSS)
            if el:
                title = el.get_text(strip=True)
        if not title and self.TITLE_CSS_FALLBACK:
            el = soup.select_one(self.TITLE_CSS_FALLBACK)
            if el:
                title = el.get_text(strip=True)
        if not title:
            title = self._extract_meta_content(soup, "og:title")
        if not title:
            title = json_ld.get("headline", "")

        # --- Body ---
        body = ""
        body_el = None
        if self.BODY_CSS:
            body_el = soup.select_one(self.BODY_CSS)
        if not body_el and self.BODY_CSS_FALLBACK:
            body_el = soup.select_one(self.BODY_CSS_FALLBACK)
        if body_el:
            body = self._clean_body_text(body_el)

        # --- Date ---
        published_at = None
        date_str = json_ld.get("datePublished", "")
        if date_str:
            published_at = self.normalize_date(date_str)
        if not published_at and self.DATE_CSS:
            date_el = soup.select_one(self.DATE_CSS)
            if date_el:
                published_at = self.normalize_date(date_el.get_text(strip=True))
        if not published_at:
            meta_date = self._extract_meta_content(soup, "article:published_time")
            if meta_date:
                published_at = self.normalize_date(meta_date)

        # --- Author ---
        author = None
        author_data = json_ld.get("author")
        if isinstance(author_data, dict):
            author = author_data.get("name")
        elif isinstance(author_data, list):
            names = [a.get("name", "") for a in author_data if isinstance(a, dict)]
            author = ", ".join(n for n in names if n) or None
        if not author and self.AUTHOR_CSS:
            author_el = soup.select_one(self.AUTHOR_CSS)
            if author_el:
                author = author_el.get_text(strip=True)

        # --- Category ---
        category = self._extract_category_from_url(url)

        return {
            "title": title,
            "body": body,
            "published_at": published_at,
            "author": author,
            "category": category,
            "is_paywall_truncated": self.PAYWALL_TYPE in ("hard", "soft-metered"),
        }

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"site_id={self.SITE_ID!r} "
            f"site_url={self.SITE_URL!r}>"
        )
