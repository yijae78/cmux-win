"""Financial News (fnnews.com) site adapter.

Group B — Korean Economy.
Primary method: RSS. Fallback: Sitemap > DOM.
Bot block level: MEDIUM. Proxy: KR required.

Decision Rationale [trace:step-6:fnnews-strategy]:
    RSS at http://www.fnnews.com/rss/fn_realnews_all.xml confirmed.
    Traditional PHP CMS with clean HTML. No paywall. Section URLs follow
    /section/NNNNNN numeric pattern. JSON-LD WebSite schema present.
    Date format: "YYYY년 MM월 DD일".

Selectors verified via Step 6 WebFetch verification.
"""

from __future__ import annotations

import logging
from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter
from src.crawling.adapters.kr_major._kr_utils import (
    extract_korean_author,
    parse_korean_date,
)

logger = logging.getLogger(__name__)


class FnnewsAdapter(BaseSiteAdapter):
    """Adapter for Financial News (fnnews.com)."""

    # --- Site identity ---
    SITE_ID = "fnnews"
    SITE_NAME = "Financial News"
    SITE_URL = "https://www.fnnews.com"
    LANGUAGE = "ko"
    REGION = "kr"
    GROUP = "B"

    # --- URL discovery ---
    RSS_URL = "http://www.fnnews.com/rss/fn_realnews_all.xml"
    SITEMAP_URL = "https://www.fnnews.com/sitemap.xml"

    # --- Article extraction selectors ---
    # [trace:step-6:fnnews-selectors]
    TITLE_CSS = 'meta[property="og:title"]'
    TITLE_CSS_FALLBACK = "h1.article_tit"
    BODY_CSS = "div.article_cont"
    BODY_CSS_FALLBACK = "div#article_content"
    DATE_CSS = 'meta[property="article:published_time"]'
    AUTHOR_CSS = "span.article_byline"
    ARTICLE_LINK_CSS = "a[href*='/news/']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div.ad-container, div.article-ad, "
        "div.related-articles, "
        "div.social-share, "
        "div.comment-area"
    )

    # --- Section URLs (numeric codes verified via WebFetch) ---
    SECTION_URLS = [
        "https://www.fnnews.com/section/002001002002",  # Finance/Securities
        "https://www.fnnews.com/section/002003000",     # Real Estate
        "https://www.fnnews.com/section/002004002005",  # Industry/IT
        "https://www.fnnews.com/section/001001000",     # Politics
        "https://www.fnnews.com/section/005000000",     # Lifestyle
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
        """Extract article fields from Financial News HTML.

        Notes:
            - Section URLs use numeric codes: /section/NNNNNN.
            - Korean date format in display: "YYYY년 MM월 DD일".
            - JSON-LD WebSite schema present for metadata extraction.
            - Category uses numeric section codes; prefer RSS <category>.
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
            el = soup.select_one("h1.article_tit")
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
            date_el = soup.select_one("span.article_date")
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

        # Category: try JSON-LD BreadcrumbList first, then meta tag
        json_ld = self._extract_json_ld(soup)
        if json_ld:
            section = json_ld.get("articleSection")
            if isinstance(section, str):
                result["category"] = section.lower()
            elif isinstance(section, list) and section:
                result["category"] = section[0].lower()

        if not result["category"]:
            meta_section = self._extract_meta_content(soup, "article:section")
            if meta_section:
                result["category"] = meta_section.lower()

        return result

    def get_section_urls(self) -> list[str]:
        """Return Financial News section page URLs."""
        return list(self.SECTION_URLS)

    def _is_article_url(self, url: str) -> bool:
        """Financial News article URLs contain /news/ path."""
        if "/news/" in url:
            return True
        return super()._is_article_url(url)
