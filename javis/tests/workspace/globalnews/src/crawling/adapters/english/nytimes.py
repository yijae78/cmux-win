"""New York Times adapter -- hard paywall, title-only extraction.

The New York Times has a hard paywall for nearly all article content.
This adapter extracts only publicly available metadata: title, author,
publication date, category, and summary/lead from meta tags. No attempt
is made to circumvent the paywall.

Reference:
    sources.yaml key: nytimes
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


class NYTimesAdapter(BaseSiteAdapter):
    """Adapter for The New York Times (nytimes.com).

    HARD PAYWALL: This adapter only extracts publicly accessible metadata.
    Full article body is NOT extracted. Every article is marked with
    ``is_paywall_truncated=True``.

    Publicly available data:
        - Headline from og:title / JSON-LD
        - Author from meta tags / JSON-LD
        - Publication date from meta tags / JSON-LD
        - Category/section from URL path and meta tags
        - Summary/description from og:description
    """

    # --- Site identity ---
    SITE_ID = "nytimes"
    SITE_NAME = "The New York Times"
    SITE_URL = "https://www.nytimes.com"
    LANGUAGE = "en"
    REGION = "us"
    GROUP = "E"

    # --- URL discovery ---
    RSS_URL = ""  # RSS discontinued for general users ~2020
    SITEMAP_URL = "/sitemap.xml"

    # --- Article extraction selectors ---
    # These are used for metadata extraction only (hard paywall)
    TITLE_CSS = "h1[data-testid='headline']"
    TITLE_CSS_FALLBACK = "h1.e1h9p8200, h1[class*='StoryHeadline']"
    BODY_CSS = ""  # Not used -- hard paywall
    DATE_CSS = "time[datetime]"
    AUTHOR_CSS = "span[class*='byline'], p[class*='byline']"
    ARTICLE_LINK_CSS = "a[href*='/2']"  # NYT article URLs contain year

    BODY_EXCLUDE_CSS = ""  # Not applicable for title-only

    # --- Section/listing pages ---
    SECTION_URLS = [
        "https://www.nytimes.com/section/world",
        "https://www.nytimes.com/section/us",
        "https://www.nytimes.com/section/politics",
        "https://www.nytimes.com/section/business",
        "https://www.nytimes.com/section/technology",
        "https://www.nytimes.com/section/science",
        "https://www.nytimes.com/section/health",
        "https://www.nytimes.com/section/opinion",
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
        """Extract publicly available metadata from NYT article pages.

        HARD PAYWALL: Only title, author, date, category, and summary
        are extracted. Body is always empty. is_paywall_truncated is
        always True.

        Args:
            html: Raw HTML of the article page.
            url: Canonical article URL.

        Returns:
            Dict with title, body (empty), published_at, author, category,
            is_paywall_truncated (always True).
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        result: dict[str, Any] = {
            "title": "",
            "body": "",  # Always empty for hard paywall
            "published_at": None,
            "author": None,
            "category": None,
            "is_paywall_truncated": True,  # Always True for hard paywall
        }

        # 1. JSON-LD extraction (NYT provides rich JSON-LD)
        json_ld = self._extract_json_ld(soup)
        if json_ld:
            result["title"] = json_ld.get("headline", "")
            result["author"] = self._extract_nyt_author(json_ld)
            date_str = json_ld.get("datePublished", "")
            if date_str:
                result["published_at"] = self.normalize_date(date_str)
            # NYT puts section info in JSON-LD
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
            # article:published_time meta tag
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
                result["author"] = text.replace("By ", "").strip()

        # 6. Category from URL path
        if not result["category"]:
            result["category"] = self._extract_section_from_url(url)

        # 7. Store description as body hint (publicly available summary)
        # This is the og:description which is publicly accessible
        description = self._extract_meta_content(soup, "og:description")
        if description:
            result["body"] = description  # Summary only, not full article

        return result

    def get_section_urls(self) -> list[str]:
        """Return NYT section URLs for DOM-based discovery."""
        return list(self.SECTION_URLS)

    def _is_article_url(self, url: str) -> bool:
        """NYT article URLs follow: /YYYY/MM/DD/section/slug.html"""
        import re
        if re.search(r"/\d{4}/\d{2}/\d{2}/", url):
            return True
        return super()._is_article_url(url)

    @staticmethod
    def _extract_nyt_author(json_ld: dict[str, Any]) -> str | None:
        """Extract author from NYT JSON-LD.

        NYT uses a list of author objects with ``name`` fields.
        """
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
        """Extract section from NYT URL path.

        NYT URLs: /YYYY/MM/DD/section/slug.html or /section/...
        """
        from urllib.parse import urlparse
        import re
        path = urlparse(url).path.strip("/")

        # Match /YYYY/MM/DD/section/slug pattern
        match = re.match(r"\d{4}/\d{2}/\d{2}/([^/]+)", path)
        if match:
            section = match.group(1)
            if section not in ("interactive", "video"):
                return section

        # Match /section/... pattern
        segments = path.split("/")
        if segments and segments[0] == "section" and len(segments) > 1:
            return segments[1]

        return None
