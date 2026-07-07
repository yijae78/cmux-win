"""JoongAng Ilbo (joongang.co.kr) site adapter.

Group A — Korean Major Dailies.
Primary method: RSS. Fallback: Sitemap > DOM.
Bot block level: HIGH. Proxy: KR required.

Decision Rationale [trace:step-6:joongang-strategy]:
    RSS at http://rss.joinsmsn.com/joins_news_list.xml is on a legacy
    domain (joinsmsn.com). RSS avoids Cloudflare JS challenges that DOM
    crawling would face. Soft paywall (JoongAng Plus) may truncate body
    for premium articles.

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


class JoongAngAdapter(BaseSiteAdapter):
    """Adapter for JoongAng Ilbo (joongang.co.kr)."""

    # --- Site identity ---
    SITE_ID = "joongang"
    SITE_NAME = "JoongAng Ilbo"
    SITE_URL = "https://www.joongang.co.kr"
    LANGUAGE = "ko"
    REGION = "kr"
    GROUP = "A"

    # --- URL discovery ---
    # RSS discontinued (rss.joinsmsn.com returns anti-bot challenge, joins.com shows "서비스 종료")
    RSS_URL = ""
    SITEMAP_URL = "https://www.joongang.co.kr/sitemap.xml"

    # --- Article extraction selectors ---
    # [trace:step-6:joongang-selectors]
    TITLE_CSS = 'meta[property="og:title"]'
    TITLE_CSS_FALLBACK = "h1.headline"
    BODY_CSS = "div.article_body"
    BODY_CSS_FALLBACK = "div#article_body"
    DATE_CSS = 'meta[property="article:published_time"]'
    AUTHOR_CSS = "span.byline"
    ARTICLE_LINK_CSS = "a[href*='/article/']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div.ab_ad, div.ad_wrap, "
        "div.ab_related_article, "
        "div.social_share, "
        "div.reporter_info_area"
    )

    # --- Section URLs ---
    SECTION_URLS = [
        "https://www.joongang.co.kr/politics",
        "https://www.joongang.co.kr/economy",
        "https://www.joongang.co.kr/society",
        "https://www.joongang.co.kr/international",
        "https://www.joongang.co.kr/sports",
        "https://www.joongang.co.kr/culture",
        "https://www.joongang.co.kr/opinion",
    ]

    PAGINATION_TYPE = "page_number"
    PAGINATION_PARAM = "page"
    MAX_PAGES = 5

    # --- Rate limiting (HIGH block level — conservative) ---
    RATE_LIMIT_SECONDS = 10.0
    MAX_REQUESTS_PER_HOUR = 240
    JITTER_SECONDS = 3.0

    # --- Anti-block ---
    ANTI_BLOCK_TIER = 2
    UA_TIER = 3
    REQUIRES_PROXY = True
    PROXY_REGION = "kr"
    BOT_BLOCK_LEVEL = "HIGH"

    # --- Extraction config ---
    PAYWALL_TYPE = "soft-metered"
    CHARSET = "utf-8"
    RENDERING_REQUIRED = False

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from JoongAng Ilbo HTML.

        Notes:
            - Soft paywall: body may be truncated for JoongAng Plus articles.
            - Date display format: "입력 2026.02.26 10:30 | 수정 2026.02.26 11:45"
            - Cloudflare protection may serve challenge pages instead of content.
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
            el = soup.select_one("h1.headline")
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

        # Category
        result["category"] = extract_category_from_url(url, self.SITE_ID)
        if not result["category"]:
            meta_section = self._extract_meta_content(soup, "article:section")
            if meta_section:
                result["category"] = meta_section.lower()

        return result

    def get_section_urls(self) -> list[str]:
        """Return JoongAng section page URLs."""
        return list(self.SECTION_URLS)

    def _is_article_url(self, url: str) -> bool:
        """JoongAng article URLs: /article/ path pattern."""
        if "/article/" in url:
            return True
        return super()._is_article_url(url)
