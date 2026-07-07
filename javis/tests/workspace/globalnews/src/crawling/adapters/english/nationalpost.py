"""National Post adapter -- Canadian news with soft-metered paywall.

The National Post is a Canadian English-language newspaper covering national
and international news, politics, business, and opinion. Uses RSS as primary
discovery with multiple section feeds. Has a soft-metered paywall (Postmedia
Network) that allows limited free articles.

Reference:
    sources.yaml key: nationalpost
    Primary method: RSS (3 section feeds)
    Paywall: soft-metered (Postmedia paywall)
    Bot block level: HIGH
    Difficulty: Hard
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter

logger = logging.getLogger(__name__)


class NationalPostAdapter(BaseSiteAdapter):
    """Adapter for National Post (nationalpost.com).

    National Post is part of Postmedia Network with a metered paywall.
    The site uses WordPress-based markup with JSON-LD structured data.
    Free articles have full body text; metered articles show truncated
    content with a subscription prompt.
    """

    # --- Site identity ---
    SITE_ID = "nationalpost"
    SITE_NAME = "National Post"
    SITE_URL = "https://nationalpost.com"
    LANGUAGE = "en"
    REGION = "us"  # Grouped with US/English per sources.yaml
    GROUP = "E"

    # --- URL discovery ---
    RSS_URL = "https://nationalpost.com/feed"
    RSS_URLS = [
        "https://nationalpost.com/category/news/feed",
        "https://nationalpost.com/category/opinion/feed",
        "https://nationalpost.com/category/politics/feed",
    ]
    SITEMAP_URL = "/sitemap.xml"

    # --- Article extraction selectors ---
    # National Post uses WordPress-based themes
    TITLE_CSS = "h1.article-title"
    TITLE_CSS_FALLBACK = "h1[class*='entry-title'], h1.headline"
    BODY_CSS = "div.article-content__content-group"
    BODY_CSS_FALLBACK = "div.article-content, div[class*='story-content']"
    DATE_CSS = "time[datetime]"
    AUTHOR_CSS = "span.published-by__author, a[class*='author']"
    ARTICLE_LINK_CSS = "a.article-card__link, a[class*='article-card']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div[class*='related-stories'], div[class*='advertisement'], "
        "div.story-comments, div[class*='newsletter'], "
        "div[class*='paywall'], div[class*='meter'], "
        "aside, nav, footer"
    )

    # --- Section/listing pages ---
    SECTION_URLS = [
        "https://nationalpost.com/category/news",
        "https://nationalpost.com/category/opinion",
        "https://nationalpost.com/category/politics",
        "https://nationalpost.com/category/news/canada",
        "https://nationalpost.com/category/news/world",
        "https://nationalpost.com/category/news/politics",
        "https://nationalpost.com/category/business",
    ]
    PAGINATION_TYPE = "page_number"
    PAGINATION_PARAM = "page"
    MAX_PAGES = 5

    # --- Rate limiting ---
    RATE_LIMIT_SECONDS = 10.0
    MAX_REQUESTS_PER_HOUR = 240
    JITTER_SECONDS = 3.0

    # --- Anti-block ---
    ANTI_BLOCK_TIER = 2
    UA_TIER = 3
    REQUIRES_PROXY = False
    BOT_BLOCK_LEVEL = "HIGH"

    # --- Extraction config ---
    PAYWALL_TYPE = "soft-metered"
    CHARSET = "utf-8"

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from National Post HTML.

        Uses JSON-LD for metadata and CSS selectors for body text.
        Detects Postmedia metered paywall truncation.

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

        # 7. Paywall detection (Postmedia metered paywall)
        if self._detect_postmedia_paywall(soup, html):
            if len(result["body"]) < 200:
                result["is_paywall_truncated"] = True

        return result

    def get_section_urls(self) -> list[str]:
        """Return National Post section URLs for DOM-based discovery."""
        return list(self.SECTION_URLS)

    def _detect_postmedia_paywall(self, soup: Any, html: str) -> bool:
        """Detect Postmedia metered paywall indicators."""
        if soup.select_one("div[class*='paywall']"):
            return True
        if soup.select_one("div[class*='subscriber-only']"):
            return True
        if "postmedia" in html.lower() and "paywall" in html.lower():
            return True
        return False

    @staticmethod
    def _extract_section_from_url(url: str) -> str | None:
        """Extract section from National Post URL path."""
        from urllib.parse import urlparse
        path = urlparse(url).path.strip("/")
        segments = path.split("/")
        # /category/news/world/article-slug
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
