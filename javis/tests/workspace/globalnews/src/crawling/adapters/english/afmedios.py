"""AF Medios adapter -- Mexican news outlet, Spanish-language.

AF Medios (afmedios.com) is a Mexican digital news outlet that publishes
primarily in Spanish. Despite being in Group E (English), the site's
primary language is Spanish (es). This adapter handles Spanish-language
content with appropriate encoding and date format handling.

Reference:
    sources.yaml key: afmedios
    Primary method: RSS
    Paywall: none
    Bot block level: LOW
    Difficulty: Easy
    Language: es (Spanish)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter

logger = logging.getLogger(__name__)

# Spanish month names for date parsing
_SPANISH_MONTHS = {
    "enero": "01", "febrero": "02", "marzo": "03",
    "abril": "04", "mayo": "05", "junio": "06",
    "julio": "07", "agosto": "08", "septiembre": "09",
    "octubre": "10", "noviembre": "11", "diciembre": "12",
}


class AFMediosAdapter(BaseSiteAdapter):
    """Adapter for AF Medios (afmedios.com).

    AF Medios is a Mexican news outlet publishing in Spanish. The site
    uses a WordPress-based CMS with standard article markup and RSS feeds.
    No paywall.
    """

    # --- Site identity ---
    SITE_ID = "afmedios"
    SITE_NAME = "AF Medios"
    SITE_URL = "https://afmedios.com"
    LANGUAGE = "es"  # Spanish-language site
    REGION = "mx"
    GROUP = "E"

    # --- URL discovery ---
    RSS_URL = "https://afmedios.com/rss"
    SITEMAP_URL = "/sitemap_index.xml"

    # --- Article extraction selectors ---
    # WordPress-based structure
    TITLE_CSS = "h1.entry-title"
    TITLE_CSS_FALLBACK = "h1.post-title, h1[class*='single-title']"
    BODY_CSS = "div.entry-content"
    BODY_CSS_FALLBACK = "div.post-content, article .content"
    DATE_CSS = "time.entry-date[datetime]"
    AUTHOR_CSS = "span.author-name a, a.author-name"
    ARTICLE_LINK_CSS = "h2.entry-title a, a[rel='bookmark']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div[class*='sharedaddy'], div[class*='related'], "
        "div[class*='wp-block-embed'], div.yarpp-related, "
        "div[class*='ad-'], aside, nav, footer"
    )

    # --- Section/listing pages ---
    SECTION_URLS = [
        "https://afmedios.com/category/noticias/",
        "https://afmedios.com/category/politica/",
        "https://afmedios.com/category/deportes/",
        "https://afmedios.com/category/espectaculos/",
        "https://afmedios.com/category/economia/",
    ]
    PAGINATION_TYPE = "page_number"
    PAGINATION_PARAM = "page"
    MAX_PAGES = 5

    # --- Rate limiting ---
    RATE_LIMIT_SECONDS = 2.0
    MAX_REQUESTS_PER_HOUR = 1800
    JITTER_SECONDS = 0.0

    # --- Anti-block ---
    ANTI_BLOCK_TIER = 1
    UA_TIER = 1
    REQUIRES_PROXY = False
    BOT_BLOCK_LEVEL = "LOW"

    # --- Extraction config ---
    PAYWALL_TYPE = "none"
    CHARSET = "utf-8"

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from AF Medios HTML.

        Uses standard WordPress extraction patterns with JSON-LD metadata
        and CSS selectors. Handles Spanish-language date formats.

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

        # 1. JSON-LD extraction (WordPress typically provides this)
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

        # 2. Title from CSS
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

        # 5. Try Spanish date format if still no date
        if not result["published_at"]:
            date_el = soup.select_one("span.date, span.entry-date")
            if date_el:
                text = date_el.get_text(strip=True)
                result["published_at"] = self._parse_spanish_date(text)

        # 6. Author fallback
        if not result["author"]:
            author_el = soup.select_one(self.AUTHOR_CSS)
            if author_el:
                result["author"] = author_el.get_text(strip=True)

        # 7. Category from WordPress categories
        if not result["category"]:
            cat_el = soup.select_one("span.cat-links a, a[rel='category tag']")
            if cat_el:
                result["category"] = cat_el.get_text(strip=True)

        if not result["category"]:
            result["category"] = self._extract_section_from_url(url)

        return result

    def get_section_urls(self) -> list[str]:
        """Return AF Medios section URLs for DOM-based discovery."""
        return list(self.SECTION_URLS)

    @staticmethod
    def _parse_spanish_date(text: str) -> datetime | None:
        """Parse Spanish date format like '25 de febrero de 2026'.

        Args:
            text: Spanish date string.

        Returns:
            datetime in UTC, or None if parsing fails.
        """
        text = text.lower().strip()
        # Pattern: "DD de MONTH de YYYY" or "MONTH DD, YYYY"
        match = re.search(
            r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", text
        )
        if match:
            day = match.group(1).zfill(2)
            month_name = match.group(2)
            year = match.group(3)
            month = _SPANISH_MONTHS.get(month_name)
            if month:
                try:
                    dt = datetime.strptime(
                        f"{year}-{month}-{day}", "%Y-%m-%d"
                    )
                    return dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
        return None

    @staticmethod
    def _extract_section_from_url(url: str) -> str | None:
        """Extract section from AF Medios URL path."""
        from urllib.parse import urlparse
        path = urlparse(url).path.strip("/")
        segments = path.split("/")
        # /category/noticias/slug pattern
        if len(segments) >= 2 and segments[0] == "category":
            return segments[1]
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
