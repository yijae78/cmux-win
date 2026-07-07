"""Chosun Ilbo (chosun.com) site adapter.

Group A — Korean Major Dailies.
Primary method: RSS. Fallback: Sitemap > DOM.
Bot block level: MEDIUM. Proxy: KR required.

Decision Rationale [trace:step-6:chosun-strategy]:
    RSS at http://www.chosun.com/site/data/rss/rss.xml is the primary
    discovery method. Homepage uses infinite scroll, making DOM-based
    discovery unreliable without Playwright. RSS bypasses this entirely.

Selectors verified via Step 6 WebFetch analysis.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter
from src.crawling.adapters.kr_major._kr_utils import (
    KST,
    extract_category_from_url,
    extract_korean_author,
    parse_korean_date,
)

logger = logging.getLogger(__name__)


class ChosunAdapter(BaseSiteAdapter):
    """Adapter for Chosun Ilbo (chosun.com)."""

    # --- Site identity ---
    SITE_ID = "chosun"
    SITE_NAME = "Chosun Ilbo"
    SITE_URL = "https://www.chosun.com"
    LANGUAGE = "ko"
    REGION = "kr"
    GROUP = "A"

    # --- URL discovery ---
    RSS_URL = "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"
    SITEMAP_URL = "https://www.chosun.com/sitemap.xml"

    # --- Article extraction selectors ---
    # [trace:step-6:chosun-selectors]
    TITLE_CSS = 'meta[property="og:title"]'
    TITLE_CSS_FALLBACK = "h1.article-header__title"
    BODY_CSS = "div.article-body"
    BODY_CSS_FALLBACK = "div#article-body-content"
    DATE_CSS = 'meta[property="article:published_time"]'
    AUTHOR_CSS = "span.article-header__journalist"
    ARTICLE_LINK_CSS = "a[href*='/article/']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div.article-ad, div.ad-container, "
        "div.related-articles, "
        "div.article-social, div.sns-share, "
        "div.article-comment"
    )

    # --- Section URLs for DOM fallback ---
    SECTION_URLS = [
        "https://www.chosun.com/politics/",
        "https://www.chosun.com/economy/",
        "https://www.chosun.com/national/",
        "https://www.chosun.com/international/",
        "https://www.chosun.com/sports/",
        "https://www.chosun.com/culture-life/",
        "https://www.chosun.com/opinion/",
    ]

    # --- Pagination ---
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
        """Extract article fields from Chosun Ilbo HTML.

        Extraction chain:
            1. og:title meta tag -> h1.article-header__title
            2. div.article-body -> div#article-body-content
            3. article:published_time meta -> time.article-header__date
            4. span.article-header__journalist -> meta[name=author]
            5. Category from URL path segment or nav.breadcrumb
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

        # Title: og:title -> h1.article-header__title -> first <h1>
        result["title"] = self._extract_meta_content(soup, "og:title")
        if not result["title"]:
            el = soup.select_one("h1.article-header__title")
            if el:
                result["title"] = el.get_text(strip=True)
        if not result["title"]:
            h1 = soup.find("h1")
            if h1:
                result["title"] = h1.get_text(strip=True)

        # Body: div.article-body -> div#article-body-content
        body_el = soup.select_one(self.BODY_CSS)
        if not body_el:
            body_el = soup.select_one(self.BODY_CSS_FALLBACK)
        if body_el:
            result["body"] = self._clean_body_text(body_el)

        # Date: article:published_time meta -> time element
        date_str = self._extract_meta_content(soup, "article:published_time")
        if not date_str:
            time_el = soup.select_one("time.article-header__date")
            if time_el:
                date_str = time_el.get("datetime", "") or time_el.get_text(strip=True)
        result["published_at"] = parse_korean_date(date_str) if date_str else None

        # Author: span.article-header__journalist -> meta[name=author]
        author_el = soup.select_one(self.AUTHOR_CSS)
        if author_el:
            result["author"] = extract_korean_author(author_el.get_text(strip=True))
        if not result["author"]:
            meta_author = self._extract_meta_content(soup, "author")
            if meta_author:
                result["author"] = extract_korean_author(meta_author)

        # Category: URL path or breadcrumb
        result["category"] = extract_category_from_url(url, self.SITE_ID)
        if not result["category"]:
            breadcrumb = soup.select_one("nav.breadcrumb a")
            if breadcrumb:
                result["category"] = breadcrumb.get_text(strip=True).lower()

        return result

    def get_section_urls(self) -> list[str]:
        """Return Chosun section page URLs."""
        return list(self.SECTION_URLS)

    def _is_article_url(self, url: str) -> bool:
        """Chosun article URLs contain /article/ with numeric IDs."""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        site_host = urlparse(self.SITE_URL).hostname or ""
        url_host = parsed.hostname or ""
        if site_host and url_host and site_host not in url_host:
            return False
        if "/article/" in url:
            return True
        return super()._is_article_url(url)
