"""Bloomberg adapter -- hard paywall, title-only extraction.

Bloomberg has a hard paywall for most article content, allowing only a limited
number of free articles per month (with registration). For the purposes of
this crawler, Bloomberg is treated as a hard paywall site with title-only
extraction per sources.yaml configuration (title_only=true).

Reference:
    sources.yaml key: bloomberg
    Primary method: sitemap (multiple sitemaps from robots.txt)
    Paywall: hard (title_only=true)
    Bot block level: HIGH
    Difficulty: Extreme
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter

logger = logging.getLogger(__name__)


class BloombergAdapter(BaseSiteAdapter):
    """Adapter for Bloomberg (bloomberg.com).

    HARD PAYWALL: This adapter only extracts publicly accessible metadata.
    Full article body is NOT extracted. Every article is marked with
    ``is_paywall_truncated=True``.

    Bloomberg provides JSON-LD structured data and rich meta tags.
    The site also has structured market data, but this adapter focuses
    on news article metadata only.
    """

    # --- Site identity ---
    SITE_ID = "bloomberg"
    SITE_NAME = "Bloomberg"
    SITE_URL = "https://www.bloomberg.com"
    LANGUAGE = "en"
    REGION = "us"
    GROUP = "E"

    # --- URL discovery ---
    RSS_URL = ""  # No public RSS; requires account
    SITEMAP_URL = "/feeds/sitemap_news.xml"  # Direct sitemap, not /sitemap.xml (403)

    # --- Article extraction selectors ---
    TITLE_CSS = "h1.lede-text-v2__hed"
    TITLE_CSS_FALLBACK = "h1[class*='headline'], h1[data-testid='Heading']"
    BODY_CSS = ""  # Not used -- hard paywall
    DATE_CSS = "time[datetime]"
    AUTHOR_CSS = "div.byline-text, a[class*='author']"
    ARTICLE_LINK_CSS = "a[href*='/news/articles/']"

    BODY_EXCLUDE_CSS = ""  # Not applicable for title-only

    # --- Section/listing pages ---
    SECTION_URLS = [
        "https://www.bloomberg.com/markets",
        "https://www.bloomberg.com/technology",
        "https://www.bloomberg.com/politics",
        "https://www.bloomberg.com/wealth",
        "https://www.bloomberg.com/pursuits",
        "https://www.bloomberg.com/opinion",
        "https://www.bloomberg.com/businessweek",
    ]
    PAGINATION_TYPE = "none"
    MAX_PAGES = 3

    # --- Rate limiting ---
    RATE_LIMIT_SECONDS = 10.0
    MAX_REQUESTS_PER_HOUR = 240
    JITTER_SECONDS = 3.0

    # --- Anti-block ---
    ANTI_BLOCK_TIER = 3
    UA_TIER = 3
    REQUIRES_PROXY = False
    BOT_BLOCK_LEVEL = "HIGH"

    # --- Extraction config ---
    PAYWALL_TYPE = "hard"
    CHARSET = "utf-8"
    RENDERING_REQUIRED = False

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract publicly available metadata from Bloomberg article pages.

        HARD PAYWALL: Only title, author, date, category, and summary
        are extracted. Body is always empty or summary-only.
        is_paywall_truncated is always True.

        Args:
            html: Raw HTML of the article page.
            url: Canonical article URL.

        Returns:
            Dict with title, body (empty/summary), published_at, author,
            category, is_paywall_truncated (always True).
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        result: dict[str, Any] = {
            "title": "",
            "body": "",  # Will contain og:description summary only
            "published_at": None,
            "author": None,
            "category": None,
            "is_paywall_truncated": True,  # Always True for hard paywall
        }

        # 1. JSON-LD extraction (Bloomberg provides structured data)
        json_ld = self._extract_json_ld(soup)
        if json_ld:
            result["title"] = json_ld.get("headline", "")
            result["author"] = _extract_author_from_json_ld(json_ld)
            date_str = json_ld.get("datePublished", "")
            if date_str:
                result["published_at"] = self.normalize_date(date_str)
            section = json_ld.get("articleSection")
            if isinstance(section, str):
                result["category"] = section
            elif isinstance(section, list) and section:
                result["category"] = section[0]

        # 2. Title fallback: CSS selectors
        if not result["title"]:
            title_el = (
                soup.select_one(self.TITLE_CSS)
                or soup.select_one(self.TITLE_CSS_FALLBACK)
            )
            if title_el:
                result["title"] = title_el.get_text(strip=True)

        # 3. Title fallback: og:title
        if not result["title"]:
            result["title"] = self._extract_meta_content(soup, "og:title")

        # 4. Date fallback
        if not result["published_at"]:
            pub_time = self._extract_meta_content(soup, "article:published_time")
            if pub_time:
                result["published_at"] = self.normalize_date(pub_time)

        if not result["published_at"]:
            time_el = soup.select_one(self.DATE_CSS)
            if time_el:
                dt_str = time_el.get("datetime", "")
                result["published_at"] = self.normalize_date(dt_str)

        # 5. Author fallback
        if not result["author"]:
            author_el = soup.select_one(self.AUTHOR_CSS)
            if author_el:
                text = author_el.get_text(strip=True)
                # Bloomberg authors are often "By Author Name"
                result["author"] = text.replace("By ", "").strip()

        # 6. Category from URL path
        if not result["category"]:
            result["category"] = self._extract_section_from_url(url)

        # 7. Summary from og:description (publicly available)
        description = self._extract_meta_content(soup, "og:description")
        if description:
            result["body"] = description

        return result

    def get_section_urls(self) -> list[str]:
        """Return Bloomberg section URLs for DOM-based discovery."""
        return list(self.SECTION_URLS)

    def _is_article_url(self, url: str) -> bool:
        """Bloomberg article URLs contain /news/articles/ or /opinion/articles/."""
        if "/news/articles/" in url:
            return True
        if "/opinion/articles/" in url:
            return True
        if "/features/" in url:
            return True
        return super()._is_article_url(url)

    @staticmethod
    def _extract_section_from_url(url: str) -> str | None:
        """Extract section from Bloomberg URL path.

        Bloomberg URLs: /news/articles/SLUG, /opinion/articles/SLUG
        """
        from urllib.parse import urlparse
        path = urlparse(url).path.strip("/")
        segments = path.split("/")
        if segments:
            section = segments[0]
            if section in (
                "markets", "technology", "politics", "wealth",
                "pursuits", "opinion", "businessweek", "news",
                "features", "graphics",
            ):
                return section
        return None


def _extract_author_from_json_ld(json_ld: dict[str, Any]) -> str | None:
    """Extract author name from JSON-LD data."""
    author = json_ld.get("author")
    if isinstance(author, str):
        return author
    if isinstance(author, dict):
        return author.get("name")
    if isinstance(author, list):
        names = []
        for a in author:
            if isinstance(a, dict):
                names.append(a.get("name", ""))
            elif isinstance(a, str):
                names.append(a)
        return ", ".join(n for n in names if n) or None
    return None
