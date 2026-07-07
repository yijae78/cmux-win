"""Maeil Business Newspaper (mk.co.kr) site adapter.

Group B — Korean Economy.
Primary method: RSS. Fallback: Sitemap > DOM.
Bot block level: MEDIUM. Proxy: KR required.

Decision Rationale [trace:step-6:mk-strategy]:
    RSS at http://file.mk.co.kr/news/rss/rss_30000001.xml is confirmed.
    One of Korea's largest economic dailies with ~300 articles/day.
    Traditional Korean CMS with clean HTML. RSS on dedicated file subdomain.
    No hard paywall (MK Plus exists but majority freely accessible).

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


class MkAdapter(BaseSiteAdapter):
    """Adapter for Maeil Business Newspaper (mk.co.kr)."""

    # --- Site identity ---
    SITE_ID = "mk"
    SITE_NAME = "Maeil Business Newspaper"
    SITE_URL = "https://www.mk.co.kr"
    LANGUAGE = "ko"
    REGION = "kr"
    GROUP = "B"

    # --- URL discovery ---
    RSS_URL = "http://file.mk.co.kr/news/rss/rss_30000001.xml"
    SITEMAP_URL = "https://www.mk.co.kr/sitemap.xml"

    # --- Article extraction selectors ---
    # [trace:step-6:mk-selectors]
    TITLE_CSS = 'meta[property="og:title"]'
    TITLE_CSS_FALLBACK = "h1.top_title"
    BODY_CSS = "div.news_cnt_detail_wrap"
    BODY_CSS_FALLBACK = "div#article_body"
    DATE_CSS = 'meta[property="article:published_time"]'
    AUTHOR_CSS = "span.author"
    ARTICLE_LINK_CSS = "a[href*='/news/']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div.ad-container, div.article-ad, "
        "div.related-articles, "
        "div.social-share, div.sns-share, "
        "div.comment-area, "
        "div.stock-info"  # Stock ticker widgets
    )

    # --- Section URLs ---
    SECTION_URLS = [
        "https://www.mk.co.kr/news/economy/",
        "https://www.mk.co.kr/news/stock/",
        "https://www.mk.co.kr/news/realestate/",
        "https://www.mk.co.kr/news/business/",
        "https://www.mk.co.kr/news/politics/",
        "https://www.mk.co.kr/news/society/",
        "https://www.mk.co.kr/news/world/",
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
        """Extract article fields from Maeil Business HTML.

        Notes:
            - High volume (~300/day). RSS may not capture all articles.
            - Stock market data articles are high volume during trading hours.
            - Category from URL: /news/{category}/ pattern.
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
            el = soup.select_one("h1.top_title")
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
        if not author_el:
            author_el = soup.select_one("div.byline")
        if author_el:
            result["author"] = extract_korean_author(author_el.get_text(strip=True))
        if not result["author"]:
            meta_author = self._extract_meta_content(soup, "author")
            if meta_author:
                result["author"] = extract_korean_author(meta_author)

        # Category
        result["category"] = extract_category_from_url(url, self.SITE_ID)

        return result

    def get_section_urls(self) -> list[str]:
        """Return MK section page URLs."""
        return list(self.SECTION_URLS)
