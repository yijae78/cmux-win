"""Los Angeles Times adapter -- soft-metered paywall.

The Los Angeles Times has a metered paywall that allows a limited number
of free articles per month. This adapter extracts full article content
for free articles and detects paywall truncation for metered content.
Uses RSS as primary discovery with multiple section feeds.

Reference:
    sources.yaml key: latimes
    Primary method: RSS (5 section feeds)
    Paywall: soft-metered
    Bot block level: HIGH
    Difficulty: Medium
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter

logger = logging.getLogger(__name__)


class LATimesAdapter(BaseSiteAdapter):
    """Adapter for Los Angeles Times (latimes.com).

    LA Times uses a modern CMS with JSON-LD structured data and clean
    article markup. The site has a metered paywall -- free articles have
    full body text, while metered articles show truncated content with
    a subscription prompt.
    """

    # --- Site identity ---
    SITE_ID = "latimes"
    SITE_NAME = "Los Angeles Times"
    SITE_URL = "https://www.latimes.com"
    LANGUAGE = "en"
    REGION = "us"
    GROUP = "E"

    # --- URL discovery ---
    RSS_URL = "https://www.latimes.com/rss2.0.xml"
    RSS_URLS = [
        "https://www.latimes.com/world-nation/rss2.0.xml",
        "https://www.latimes.com/politics/rss2.0.xml",
        "https://www.latimes.com/california/rss2.0.xml",
        "https://www.latimes.com/business/rss2.0.xml",
        "https://www.latimes.com/entertainment-arts/rss2.0.xml",
    ]
    SITEMAP_URL = "/sitemap.xml"

    # --- Article extraction selectors ---
    TITLE_CSS = "h1.headline"
    TITLE_CSS_FALLBACK = "h1[class*='title'], h1.page-title"
    BODY_CSS = "div.page-article-body"
    BODY_CSS_FALLBACK = "div[class*='rich-text-article-body']"
    DATE_CSS = "time[datetime]"
    AUTHOR_CSS = "a.author-name, span[class*='author']"
    ARTICLE_LINK_CSS = "a.promo-title, a[class*='promo-link']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div[class*='enhancement'], div[class*='inline-ad'], "
        "div[class*='related'], div[class*='newsletter'], "
        "div[class*='social'], aside, nav, footer"
    )

    # --- Section/listing pages ---
    SECTION_URLS = [
        "https://www.latimes.com/world-nation",
        "https://www.latimes.com/politics",
        "https://www.latimes.com/california",
        "https://www.latimes.com/business",
        "https://www.latimes.com/entertainment-arts",
        "https://www.latimes.com/sports",
        "https://www.latimes.com/opinion",
        "https://www.latimes.com/science",
    ]
    PAGINATION_TYPE = "none"
    MAX_PAGES = 5

    # --- Rate limiting ---
    RATE_LIMIT_SECONDS = 5.0
    MAX_REQUESTS_PER_HOUR = 720
    JITTER_SECONDS = 0.0

    # --- Anti-block ---
    ANTI_BLOCK_TIER = 1
    UA_TIER = 2
    REQUIRES_PROXY = False
    BOT_BLOCK_LEVEL = "HIGH"

    # --- Extraction config ---
    PAYWALL_TYPE = "soft-metered"
    CHARSET = "utf-8"

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from LA Times HTML.

        Uses JSON-LD for metadata and CSS selectors for body text.
        Detects metered paywall truncation by checking body length
        and presence of subscription gate elements.

        Args:
            html: Raw HTML of the article page.
            url: Canonical article URL.

        Returns:
            Dict with title, body, published_at, author, category,
            is_paywall_truncated.
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        result: dict[str, Any] = {
            "title": "",
            "body": "",
            "published_at": None,
            "author": None,
            "category": None,
            "is_paywall_truncated": False,
        }

        # 1. JSON-LD extraction
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

        # 2. Title fallback
        if not result["title"]:
            title_el = (
                soup.select_one(self.TITLE_CSS)
                or soup.select_one(self.TITLE_CSS_FALLBACK)
            )
            if title_el:
                result["title"] = title_el.get_text(strip=True)

        if not result["title"]:
            result["title"] = self._extract_meta_content(soup, "og:title")

        # 3. Body extraction
        body_el = (
            soup.select_one(self.BODY_CSS)
            or soup.select_one(self.BODY_CSS_FALLBACK)
        )
        if body_el:
            result["body"] = self._clean_body_text(body_el)

        # 4. Date fallback
        if not result["published_at"]:
            time_el = soup.select_one(self.DATE_CSS)
            if time_el:
                dt_str = time_el.get("datetime", "")
                result["published_at"] = self.normalize_date(dt_str)

        # 5. Author fallback
        if not result["author"]:
            author_el = soup.select_one(self.AUTHOR_CSS)
            if author_el:
                result["author"] = author_el.get_text(strip=True)

        # 6. Category from URL
        if not result["category"]:
            result["category"] = self._extract_section_from_url(url)

        # 7. Paywall detection
        if self._detect_latimes_paywall(soup, html):
            if len(result["body"]) < 200:
                result["is_paywall_truncated"] = True

        return result

    def get_section_urls(self) -> list[str]:
        """Return LA Times section URLs for DOM-based discovery."""
        return list(self.SECTION_URLS)

    def _detect_latimes_paywall(self, soup: Any, html: str) -> bool:
        """Detect LA Times metered paywall indicators."""
        # Check for subscription/metered paywall gate
        if soup.select_one("div[class*='meter-flyout']"):
            return True
        if soup.select_one("div[class*='subscribe']"):
            return True
        if "regwall" in html.lower() or "paywall" in html.lower():
            return True
        return False

    @staticmethod
    def _extract_section_from_url(url: str) -> str | None:
        """Extract section from LA Times URL path."""
        from urllib.parse import urlparse
        path = urlparse(url).path.strip("/")
        segments = path.split("/")
        if segments:
            section = segments[0]
            if section in (
                "world-nation", "politics", "california", "business",
                "entertainment-arts", "sports", "opinion", "science",
                "environment", "food",
            ):
                return section.replace("-", " ").title()
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
