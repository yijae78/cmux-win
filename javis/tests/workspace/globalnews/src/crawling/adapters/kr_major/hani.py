"""Hankyoreh (hani.co.kr) site adapter.

Group A — Korean Major Dailies.
Primary method: RSS. Fallback: Sitemap > DOM.
Bot block level: MEDIUM. Proxy: KR required.

Decision Rationale [trace:step-6:hani-strategy]:
    RSS at https://www.hani.co.kr/rss/hani.rss is confirmed. Clean HTML
    structure. Soft paywall for heavy readers — fresh sessions with cleared
    cookies access most content. Author names use patterns like
    "홍길동 기자", "홍길동 선임기자", "홍길동 특파원".

Selectors verified via Step 6 analysis.
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


class HaniAdapter(BaseSiteAdapter):
    """Adapter for Hankyoreh (hani.co.kr)."""

    # --- Site identity ---
    SITE_ID = "hani"
    SITE_NAME = "Hankyoreh"
    SITE_URL = "https://www.hani.co.kr"
    LANGUAGE = "ko"
    REGION = "kr"
    GROUP = "A"

    # --- URL discovery ---
    RSS_URL = "https://www.hani.co.kr/rss/hani.rss"
    SITEMAP_URL = "https://www.hani.co.kr/sitemap.xml"

    # --- Article extraction selectors ---
    # [trace:step-6:hani-selectors]
    TITLE_CSS = 'meta[property="og:title"]'
    TITLE_CSS_FALLBACK = "h1.title"
    BODY_CSS = "div.article-text"
    BODY_CSS_FALLBACK = "div.text"
    DATE_CSS = 'meta[property="article:published_time"]'
    AUTHOR_CSS = "span.reporter-name"
    ARTICLE_LINK_CSS = "a[href*='/arti/']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div.ad-container, div.article-ad, "
        "div.related-articles, "
        "div.social-share, div.sns-share, "
        "div.article-comment"
    )

    # --- Section URLs ---
    # Hani uses /arti/{category}/ pattern
    SECTION_URLS = [
        "https://www.hani.co.kr/arti/politics/",
        "https://www.hani.co.kr/arti/economy/",
        "https://www.hani.co.kr/arti/society/",
        "https://www.hani.co.kr/arti/international/",
        "https://www.hani.co.kr/arti/culture/",
        "https://www.hani.co.kr/arti/opinion/",
        "https://www.hani.co.kr/arti/sports/",
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
    PAYWALL_TYPE = "soft-metered"
    CHARSET = "utf-8"
    RENDERING_REQUIRED = False

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from Hankyoreh HTML.

        Notes:
            - Soft paywall: clear cookies between crawl runs.
            - Category from URL: /arti/{category}/ pattern.
            - Author patterns: "홍길동 기자", "홍길동 선임기자", "홍길동 특파원".
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
            el = soup.select_one("h1.title")
            if el:
                result["title"] = el.get_text(strip=True)

        # Body
        body_el = soup.select_one(self.BODY_CSS)
        if not body_el:
            body_el = soup.select_one(self.BODY_CSS_FALLBACK)
        if body_el:
            result["body"] = self._clean_body_text(body_el)

        # Date
        date_str = self._extract_meta_content(soup, "article:published_time")
        if not date_str:
            date_el = soup.select_one("span.date-published")
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

        # Category: from URL /arti/{category}/ or meta tag
        result["category"] = extract_category_from_url(url, self.SITE_ID)
        if not result["category"]:
            meta_section = self._extract_meta_content(soup, "article:section")
            if meta_section:
                result["category"] = meta_section.lower()

        return result

    def get_section_urls(self) -> list[str]:
        """Return Hankyoreh section page URLs."""
        return list(self.SECTION_URLS)

    def _is_article_url(self, url: str) -> bool:
        """Hankyoreh articles use /arti/ path prefix."""
        if "/arti/" in url:
            return True
        return super()._is_article_url(url)
