"""Yonhap News Agency (yna.co.kr) site adapter.

Group A — Korean Major Dailies (Wire Service).
Primary method: RSS. Fallback: Sitemap (supplemental) > DOM.
Bot block level: MEDIUM. Proxy: KR required.

Decision Rationale [trace:step-6:yna-strategy]:
    Korea's national wire service producing ~500 articles/day. RSS is
    confirmed for Korean and English editions. RSS is likely truncated
    to 50-100 items; sitemap MUST be used as supplemental source for
    full daily coverage. No paywall. Wire service content freely distributed.

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


class YnaAdapter(BaseSiteAdapter):
    """Adapter for Yonhap News Agency (yna.co.kr)."""

    # --- Site identity ---
    SITE_ID = "yna"
    SITE_NAME = "Yonhap News Agency"
    SITE_URL = "https://www.yna.co.kr"
    LANGUAGE = "ko"
    REGION = "kr"
    GROUP = "A"

    # --- URL discovery ---
    RSS_URL = "https://www.yna.co.kr/rss/news.xml"
    RSS_URLS = [
        "https://www.yna.co.kr/rss/news.xml",
        "https://en.yna.co.kr/RSS/news.xml",
    ]
    SITEMAP_URL = "https://www.yna.co.kr/sitemap.xml"

    # --- Article extraction selectors ---
    # [trace:step-6:yna-selectors]
    TITLE_CSS = 'meta[property="og:title"]'
    TITLE_CSS_FALLBACK = "h1.tit"
    BODY_CSS = "div.article"
    BODY_CSS_FALLBACK = "div#articleWrap"
    DATE_CSS = 'meta[property="article:published_time"]'
    AUTHOR_CSS = "span.byline"
    ARTICLE_LINK_CSS = "a[href*='/view/']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div.ad-container, div.article-ad, "
        "div.related-articles, div.aside-area, "
        "div.social-share, div.sns-share, "
        "div.comment-section, "
        "div.reporter-info, "
        "figure.photo-group"  # Keep but strip: photo captions are separate
    )

    # --- Section URLs ---
    SECTION_URLS = [
        "https://www.yna.co.kr/politics/index",
        "https://www.yna.co.kr/economy/index",
        "https://www.yna.co.kr/society/index",
        "https://www.yna.co.kr/international/index",
        "https://www.yna.co.kr/nk/index",
        "https://www.yna.co.kr/sports/index",
        "https://www.yna.co.kr/culture/index",
        "https://www.yna.co.kr/science/index",
    ]

    PAGINATION_TYPE = "page_number"
    PAGINATION_PARAM = "page"
    MAX_PAGES = 10  # Higher due to very high article volume

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
        """Extract article fields from Yonhap News HTML.

        Notes:
            - Very high volume (~500/day). RSS truncated; sitemap supplemental.
            - Wire service: clean, structured HTML.
            - Published date is minute-level precise.
            - No paywall or login requirements.
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
            el = soup.select_one("h1.tit")
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
            date_el = soup.select_one("span.update-time")
            if date_el:
                date_str = date_el.get_text(strip=True)
        result["published_at"] = parse_korean_date(date_str) if date_str else None

        # Author: wire service bylines
        author_el = soup.select_one(self.AUTHOR_CSS)
        if author_el:
            result["author"] = extract_korean_author(author_el.get_text(strip=True))
        if not result["author"]:
            reporter_el = soup.select_one("p.reporter")
            if reporter_el:
                result["author"] = extract_korean_author(
                    reporter_el.get_text(strip=True)
                )

        # Category from URL
        result["category"] = extract_category_from_url(url, self.SITE_ID)
        if not result["category"]:
            meta_section = self._extract_meta_content(soup, "article:section")
            if meta_section:
                result["category"] = meta_section.lower()

        return result

    def get_section_urls(self) -> list[str]:
        """Return Yonhap section page URLs."""
        return list(self.SECTION_URLS)

    def _is_article_url(self, url: str) -> bool:
        """Yonhap article URLs contain /view/ path."""
        if "/view/" in url:
            return True
        return super()._is_article_url(url)
