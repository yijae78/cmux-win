"""Money Today (mt.co.kr) site adapter.

Group B — Korean Economy.
Primary method: RSS. Fallback: Sitemap > DOM.
Bot block level: MEDIUM. Proxy: KR required.

Decision Rationale [trace:step-6:mt-strategy]:
    RSS URL needs runtime verification (try /rss, /rss.xml, /rss/rss.xml).
    Traditional Korean CMS with clean HTML. No paywall. Sub-brands (the300,
    theL, thebio) have distinct section URLs. JSON-LD includes
    NewsMediaOrganization. Date format: "2026.02.26(수)".

Selectors verified via Step 6 WebFetch verification.
"""

from __future__ import annotations

import logging
from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter
from src.crawling.adapters.kr_major._kr_utils import (
    extract_category_from_url,
    extract_korean_author,
    parse_korean_date,
)

logger = logging.getLogger(__name__)


class MtAdapter(BaseSiteAdapter):
    """Adapter for Money Today (mt.co.kr)."""

    # --- Site identity ---
    SITE_ID = "mt"
    SITE_NAME = "Money Today"
    SITE_URL = "https://www.mt.co.kr"
    LANGUAGE = "ko"
    REGION = "kr"
    GROUP = "B"

    # --- URL discovery ---
    # RSS URL needs runtime verification. Primary guess, with fallback paths.
    RSS_URL = "https://www.mt.co.kr/rss/"
    RSS_URLS = [
        "https://www.mt.co.kr/rss/",
        "https://www.mt.co.kr/rss.xml",
        "https://www.mt.co.kr/rss/rss.xml",
    ]
    SITEMAP_URL = "https://www.mt.co.kr/sitemap.xml"

    # --- Article extraction selectors ---
    # [trace:step-6:mt-selectors]
    TITLE_CSS = 'meta[property="og:title"]'
    TITLE_CSS_FALLBACK = "h1.article_title"
    BODY_CSS = "div.article_content"
    BODY_CSS_FALLBACK = "div#textBody"
    DATE_CSS = 'meta[property="article:published_time"]'
    AUTHOR_CSS = "span.byline"
    ARTICLE_LINK_CSS = "a[href*='/view/']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div.ad-container, div.article-ad, "
        "div.related-articles, "
        "div.social-share, "
        "div.comment-area, "
        "div.stock-widget"
    )

    # --- Section URLs (verified via WebFetch) ---
    SECTION_URLS = [
        "https://www.mt.co.kr/stock",
        "https://www.mt.co.kr/politics",
        "https://www.mt.co.kr/law",
        "https://www.mt.co.kr/thebio",
        "https://www.mt.co.kr/estate",
        "https://www.mt.co.kr/economy",
        "https://www.mt.co.kr/industry",
        "https://www.mt.co.kr/tech",
        "https://www.mt.co.kr/world",
    ]

    PAGINATION_TYPE = "page_number"
    PAGINATION_PARAM = "page"
    MAX_PAGES = 5

    # --- Rate limiting ---
    RATE_LIMIT_SECONDS = 5.0
    MAX_REQUESTS_PER_HOUR = 720
    JITTER_SECONDS = 0.0

    # --- Anti-block ---
    ANTI_BLOCK_TIER = 1
    UA_TIER = 2
    REQUIRES_PROXY = True
    PROXY_REGION = "kr"
    BOT_BLOCK_LEVEL = "MEDIUM"

    # --- Extraction config ---
    PAYWALL_TYPE = "none"
    CHARSET = "utf-8"
    RENDERING_REQUIRED = False

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from Money Today HTML.

        Notes:
            - RSS URL needs runtime verification.
            - Sub-brands: the300, theL, thebio.
            - Date display: "2026.02.26(수)" with day-of-week.
            - JSON-LD BreadcrumbList available for category.
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        result: dict[str, Any] = {
            "title": "",
            "body": "",
            "published_at": None,
            "author": None,
            "category": None,
        }

        # Title
        result["title"] = self._extract_meta_content(soup, "og:title")
        if not result["title"]:
            el = soup.select_one("h1.article_title")
            if el:
                result["title"] = el.get_text(strip=True)

        # Body
        body_el = soup.select_one(self.BODY_CSS)
        if not body_el:
            body_el = soup.select_one(self.BODY_CSS_FALLBACK)
        if body_el:
            result["body"] = self._clean_body_text(body_el)

        # Date: Meta tag -> span.date
        date_str = self._extract_meta_content(soup, "article:published_time")
        if not date_str:
            date_el = soup.select_one("span.date")
            if date_el:
                date_str = date_el.get_text(strip=True)
        result["published_at"] = parse_korean_date(date_str) if date_str else None

        # Author
        author_el = soup.select_one(self.AUTHOR_CSS)
        if author_el:
            result["author"] = extract_korean_author(author_el.get_text(strip=True))
        if not result["author"]:
            meta_author = self._extract_meta_content(soup, "author")
            if meta_author:
                result["author"] = extract_korean_author(meta_author)

        # Category: URL path or JSON-LD BreadcrumbList
        result["category"] = extract_category_from_url(url, self.SITE_ID)
        if not result["category"]:
            json_ld = self._extract_json_ld(soup)
            if json_ld:
                section = json_ld.get("articleSection")
                if isinstance(section, str):
                    result["category"] = section.lower()

        return result

    def get_section_urls(self) -> list[str]:
        """Return Money Today section page URLs."""
        return list(self.SECTION_URLS)

    def _is_article_url(self, url: str) -> bool:
        """Money Today articles use /view/ or /article/ in URL."""
        if "/view/" in url or "/article/" in url:
            return True
        return super()._is_article_url(url)
