"""Dong-A Ilbo (donga.com) site adapter.

Group A — Korean Major Dailies.
Primary method: RSS. Fallback: Sitemap > DOM.
Bot block level: MEDIUM. Proxy: KR required.

Decision Rationale [trace:step-6:donga-strategy]:
    RSS at http://rss.donga.com/total.xml is hosted on a dedicated rss
    subdomain with category-specific feeds. PHP CMS with clean, predictable
    HTML structure. No paywall. Trafilatura extraction highly reliable.

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


class DongaAdapter(BaseSiteAdapter):
    """Adapter for Dong-A Ilbo (donga.com)."""

    # --- Site identity ---
    SITE_ID = "donga"
    SITE_NAME = "Dong-A Ilbo"
    SITE_URL = "https://www.donga.com"
    LANGUAGE = "ko"
    REGION = "kr"
    GROUP = "A"

    # --- URL discovery ---
    RSS_URL = "http://rss.donga.com/total.xml"
    RSS_URLS = [
        "http://rss.donga.com/total.xml",
        "http://rss.donga.com/politics.xml",
        "http://rss.donga.com/economy.xml",
        "http://rss.donga.com/society.xml",
        "http://rss.donga.com/international.xml",
        "http://rss.donga.com/sports.xml",
        "http://rss.donga.com/culture.xml",
    ]
    SITEMAP_URL = "https://www.donga.com/sitemap.xml"

    # --- Article extraction selectors ---
    # [trace:step-6:donga-selectors]
    TITLE_CSS = 'meta[property="og:title"]'
    TITLE_CSS_FALLBACK = "h1.title"
    BODY_CSS = "div.article_txt"
    BODY_CSS_FALLBACK = "div#content_body"
    DATE_CSS = 'meta[property="article:published_time"]'
    AUTHOR_CSS = "span.writer"
    ARTICLE_LINK_CSS = "a[href*='/news/']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div.ad-container, div.article-ad, "
        "div.related-articles, "
        "div.social-share, "
        "div.comment-area"
    )

    # --- Section URLs ---
    SECTION_URLS = [
        "https://www.donga.com/news/Politics",
        "https://www.donga.com/news/Economy",
        "https://www.donga.com/news/Society",
        "https://www.donga.com/news/Inter",
        "https://www.donga.com/news/Sports",
        "https://www.donga.com/news/Culture",
        "https://www.donga.com/news/Opinion",
    ]

    PAGINATION_TYPE = "page_number"
    PAGINATION_PARAM = "p"
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
        """Extract article fields from Dong-A Ilbo HTML.

        Notes:
            - PHP CMS: clean HTML structure.
            - Date format: ISO 8601 or "YYYY-MM-DD HH:MM:SS".
            - No paywall: full body always available.
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

        # Category: from URL or RSS <category> element
        result["category"] = extract_category_from_url(url, self.SITE_ID)

        return result

    def get_section_urls(self) -> list[str]:
        """Return Dong-A section page URLs."""
        return list(self.SECTION_URLS)
