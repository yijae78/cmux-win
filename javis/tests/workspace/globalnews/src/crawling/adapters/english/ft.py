"""Financial Times adapter -- hard paywall, title-only extraction.

The Financial Times has a strict hard paywall for all article content.
This adapter extracts only publicly available metadata: title, author,
publication date, category, and summary from meta tags. No attempt
is made to circumvent the paywall.

Reference:
    sources.yaml key: ft
    Primary method: sitemap
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


class FTAdapter(BaseSiteAdapter):
    """Adapter for Financial Times (ft.com).

    HARD PAYWALL: This adapter only extracts publicly accessible metadata.
    Full article body is NOT extracted. Every article is marked with
    ``is_paywall_truncated=True``.

    FT provides JSON-LD structured data on article pages even behind the
    paywall, including headline, datePublished, and author information.
    """

    # --- Site identity ---
    SITE_ID = "ft"
    SITE_NAME = "Financial Times"
    SITE_URL = "https://www.ft.com"
    LANGUAGE = "en"
    REGION = "uk"
    GROUP = "E"

    # --- URL discovery ---
    RSS_URL = ""  # RSS requires FT subscription
    SITEMAP_URL = "/sitemap.xml"

    # --- Article extraction selectors ---
    TITLE_CSS = "h1.topper__headline"
    TITLE_CSS_FALLBACK = "h1[class*='article-headline']"
    BODY_CSS = ""  # Not used -- hard paywall
    DATE_CSS = "time[datetime]"
    AUTHOR_CSS = "a[class*='author'], span[class*='author']"
    ARTICLE_LINK_CSS = "a[href*='/content/']"

    BODY_EXCLUDE_CSS = ""  # Not applicable for title-only

    # --- Section/listing pages ---
    SECTION_URLS = [
        "https://www.ft.com/world",
        "https://www.ft.com/companies",
        "https://www.ft.com/markets",
        "https://www.ft.com/opinion",
        "https://www.ft.com/technology",
        "https://www.ft.com/climate-capital",
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
        """Extract publicly available metadata from FT article pages.

        HARD PAYWALL: Only title, author, date, category, and summary
        are extracted. Body is always empty. is_paywall_truncated is
        always True.

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

        # 1. JSON-LD extraction (FT provides structured data)
        json_ld = self._extract_json_ld(soup)
        if json_ld:
            result["title"] = json_ld.get("headline", "")
            result["author"] = self._extract_ft_author(json_ld)
            date_str = json_ld.get("datePublished", "")
            if date_str:
                result["published_at"] = self.normalize_date(date_str)

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
                result["author"] = author_el.get_text(strip=True)

        # 6. Category from URL path or metadata
        if not result["category"]:
            result["category"] = self._extract_section_from_url(url)

        # 7. Summary from og:description (publicly available)
        description = self._extract_meta_content(soup, "og:description")
        if description:
            result["body"] = description

        return result

    def get_section_urls(self) -> list[str]:
        """Return FT section URLs for DOM-based discovery."""
        return list(self.SECTION_URLS)

    def _is_article_url(self, url: str) -> bool:
        """FT article URLs contain /content/ followed by a UUID."""
        if "/content/" in url:
            return True
        return super()._is_article_url(url)

    @staticmethod
    def _extract_ft_author(json_ld: dict[str, Any]) -> str | None:
        """Extract author from FT JSON-LD."""
        author = json_ld.get("author")
        if isinstance(author, str):
            return author
        if isinstance(author, dict):
            return author.get("name")
        if isinstance(author, list):
            names = []
            for a in author:
                if isinstance(a, dict):
                    name = a.get("name", "")
                    if name:
                        names.append(name)
                elif isinstance(a, str):
                    names.append(a)
            return ", ".join(names) if names else None
        return None

    @staticmethod
    def _extract_section_from_url(url: str) -> str | None:
        """Extract section from FT URL path.

        FT section pages: /world, /companies, /markets, etc.
        """
        from urllib.parse import urlparse
        path = urlparse(url).path.strip("/")
        segments = path.split("/")
        # /content/UUID doesn't have section in URL
        if segments and segments[0] != "content":
            return segments[0]
        return None
