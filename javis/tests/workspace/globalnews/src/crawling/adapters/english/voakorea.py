"""VOA Korea adapter -- Korean-language Voice of America service.

VOA Korea (Voice of America Korean Service) publishes Korean-language news
primarily covering North Korea, US-Korea relations, and international affairs.
Uses API-style feeds as the primary discovery method. No paywall.

Reference:
    sources.yaml key: voakorea
    Primary method: API (API-style feeds)
    Paywall: none
    Bot block level: LOW
    Difficulty: Easy
    Language: ko (Korean)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter

logger = logging.getLogger(__name__)


class VOAKoreaAdapter(BaseSiteAdapter):
    """Adapter for VOA Korea (voakorea.com).

    VOA Korea is a US government-funded Korean-language news service.
    The site uses a CMS common to all VOA language services with consistent
    HTML structure. Articles have clean semantic markup.
    """

    # --- Site identity ---
    SITE_ID = "voakorea"
    SITE_NAME = "VOA Korea"
    SITE_URL = "https://www.voakorea.com"
    LANGUAGE = "ko"
    REGION = "us"
    GROUP = "E"

    # --- URL discovery ---
    RSS_URL = ""  # API-style feeds, not standard RSS
    SITEMAP_URL = "/sitemap.xml"

    # --- Article extraction selectors ---
    # VOA uses a consistent CMS across language services
    TITLE_CSS = "h1.title"
    TITLE_CSS_FALLBACK = "h1[class*='page-header']"
    BODY_CSS = "div.body-container div.wsw"
    BODY_CSS_FALLBACK = "div[class*='article__content']"
    DATE_CSS = "time[datetime]"
    AUTHOR_CSS = "span.byline__text, div.authors span"
    ARTICLE_LINK_CSS = "a[href*='/a/']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div.media-block-wrap, div.related-content, "
        "div.share-tools, div.infographic, "
        "aside, nav, footer"
    )

    # --- Section/listing pages ---
    SECTION_URLS = [
        "https://www.voakorea.com/z/601",    # North Korea
        "https://www.voakorea.com/z/608",    # US-Korea
        "https://www.voakorea.com/z/609",    # International
        "https://www.voakorea.com/z/610",    # Economy
        "https://www.voakorea.com/z/611",    # Science/Tech
    ]
    PAGINATION_TYPE = "page_number"
    PAGINATION_PARAM = "p"
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
        """Extract article fields from VOA Korea HTML.

        VOA Korea uses clean semantic HTML. The main content is in a
        ``div.wsw`` container within the body. Publication dates are
        in ISO 8601 format in ``<time>`` elements.

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
            author_data = json_ld.get("author")
            if isinstance(author_data, dict):
                result["author"] = author_data.get("name")
            elif isinstance(author_data, str):
                result["author"] = author_data
            date_str = json_ld.get("datePublished", "")
            if date_str:
                result["published_at"] = self.normalize_date(date_str)

        # 2. Title from CSS
        if not result["title"]:
            title_el = soup.select_one(self.TITLE_CSS) or soup.select_one(self.TITLE_CSS_FALLBACK)
            if title_el:
                result["title"] = title_el.get_text(strip=True)

        # 3. og:title fallback
        if not result["title"]:
            result["title"] = self._extract_meta_content(soup, "og:title")

        # 4. Body extraction
        body_el = soup.select_one(self.BODY_CSS) or soup.select_one(self.BODY_CSS_FALLBACK)
        if body_el:
            result["body"] = self._clean_body_text(body_el)

        # 5. Date fallback
        if not result["published_at"]:
            time_el = soup.select_one(self.DATE_CSS)
            if time_el:
                dt_str = time_el.get("datetime", "")
                result["published_at"] = self.normalize_date(dt_str)

        # 6. Author fallback
        if not result["author"]:
            author_el = soup.select_one(self.AUTHOR_CSS)
            if author_el:
                result["author"] = author_el.get_text(strip=True)

        # 7. Category from breadcrumb or URL pattern
        if not result["category"]:
            breadcrumb = soup.select("ul.breadcrumb li a")
            if len(breadcrumb) > 1:
                result["category"] = breadcrumb[-1].get_text(strip=True)

        return result

    def get_section_urls(self) -> list[str]:
        """Return VOA Korea section URLs for DOM-based discovery."""
        return list(self.SECTION_URLS)

    def _is_article_url(self, url: str) -> bool:
        """VOA Korea article URLs contain /a/ followed by a numeric ID."""
        if "/a/" in url:
            return True
        return super()._is_article_url(url)
