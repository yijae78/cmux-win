"""NoCut News / CBS (nocutnews.co.kr) site adapter.

Group C — Korean Niche.
Primary method: RSS. Fallback: Sitemap > DOM.
Bot block level: LOW. Proxy: KR required (geo-IP).

Decision Rationale [trace:step-6:nocutnews-strategy]:
    RSS at http://rss.nocutnews.co.kr/nocutnews.xml verified via WebFetch.
    Feed contains 20 items with FULL article content in <description> (not
    just summaries). LOW bot-blocking makes this one of the easiest Korean
    sites. JSON-LD NewsArticle schema confirmed on article pages with
    structured datePublished and BreadcrumbList.

Selectors VERIFIED via Step 6 WebFetch:
    - JSON-LD: headline, author.name, datePublished (ISO 8601),
      articleSection array, mainEntityOfPage.
    - Author pattern: "CBS노컷뉴스 [name] 기자".
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter
from src.crawling.adapters.kr_major._kr_utils import (
    extract_korean_author,
    parse_korean_date,
)

logger = logging.getLogger(__name__)


class NocutNewsAdapter(BaseSiteAdapter):
    """Adapter for NoCut News / CBS (nocutnews.co.kr).

    Special feature: RSS <description> contains full article content,
    potentially eliminating the need to fetch individual article pages.
    """

    # --- Site identity ---
    SITE_ID = "nocutnews"
    SITE_NAME = "NoCut News"
    SITE_URL = "https://www.nocutnews.co.kr"
    LANGUAGE = "ko"
    REGION = "kr"
    GROUP = "C"

    # --- URL discovery ---
    RSS_URL = "http://rss.nocutnews.co.kr/nocutnews.xml"
    SITEMAP_URL = "https://www.nocutnews.co.kr/sitemap.xml"

    # --- Article extraction selectors ---
    # [trace:step-6:nocutnews-selectors] — VERIFIED via WebFetch
    # Primary: JSON-LD fields. Fallback: og:title meta + CSS.
    TITLE_CSS = 'meta[property="og:title"]'
    TITLE_CSS_FALLBACK = "h2.title"
    BODY_CSS = "div.article_txt"
    BODY_CSS_FALLBACK = "div#pnlContent"
    DATE_CSS = 'meta[property="article:published_time"]'
    AUTHOR_CSS = "span.reporter"
    ARTICLE_LINK_CSS = "a[href*='/news/']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div.ad-container, "
        "div.related-articles, "
        "div.social-share, "
        "div.comment-area"
    )

    # --- Section URLs (verified via WebFetch) ---
    SECTION_URLS = [
        "https://www.nocutnews.co.kr/news/politics",
        "https://www.nocutnews.co.kr/news/society",
        "https://www.nocutnews.co.kr/news/policy",
        "https://www.nocutnews.co.kr/news/economy",
        "https://www.nocutnews.co.kr/news/industry",
        "https://www.nocutnews.co.kr/news/world",
        "https://www.nocutnews.co.kr/news/opinion",
        "https://www.nocutnews.co.kr/news/entertainment",
        "https://www.nocutnews.co.kr/news/sports",
    ]

    PAGINATION_TYPE = "page_number"
    PAGINATION_PARAM = "page"
    MAX_PAGES = 5

    # --- Rate limiting (LOW blocking — aggressive OK) ---
    RATE_LIMIT_SECONDS = 2.0
    MAX_REQUESTS_PER_HOUR = 1800
    JITTER_SECONDS = 0.0

    # --- Anti-block ---
    ANTI_BLOCK_TIER = 1
    UA_TIER = 1
    REQUIRES_PROXY = True
    PROXY_REGION = "kr"
    BOT_BLOCK_LEVEL = "LOW"

    # --- Extraction config ---
    PAYWALL_TYPE = "none"
    CHARSET = "utf-8"
    RENDERING_REQUIRED = False

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from NoCut News HTML.

        Uses JSON-LD as the primary extraction source (verified accurate).
        Falls back to og:title meta and CSS selectors.

        Notes:
            - RSS <description> has full content: can skip page fetch.
            - JSON-LD has datePublished in ISO 8601: "2025-02-28T10:24:38".
            - articleSection is an array: ["포토", "정치"].
            - Author pattern: "CBS노컷뉴스 [name] 기자".
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

        # Try JSON-LD first (verified accurate)
        json_ld = self._extract_json_ld(soup)
        if json_ld:
            result["title"] = json_ld.get("headline", "")
            date_pub = json_ld.get("datePublished", "")
            if date_pub:
                result["published_at"] = parse_korean_date(date_pub)

            # Author from JSON-LD
            author_data = json_ld.get("author")
            if isinstance(author_data, dict):
                author_name = author_data.get("name", "")
                if author_name:
                    result["author"] = extract_korean_author(author_name)
            elif isinstance(author_data, list) and author_data:
                names = []
                for a in author_data:
                    if isinstance(a, dict):
                        n = a.get("name", "")
                        if n:
                            names.append(n)
                if names:
                    result["author"] = extract_korean_author(names[0])

            # Category from JSON-LD articleSection (array)
            section = json_ld.get("articleSection")
            if isinstance(section, list) and section:
                # Take last non-"포토" section (more specific)
                for s in reversed(section):
                    if s and s != "포토":
                        result["category"] = s
                        break
                if not result["category"] and section:
                    result["category"] = section[0]
            elif isinstance(section, str):
                result["category"] = section

        # Fallback: og:title meta tag
        if not result["title"]:
            result["title"] = self._extract_meta_content(soup, "og:title")
        if not result["title"]:
            el = soup.select_one("h2.title")
            if el:
                result["title"] = el.get_text(strip=True)

        # Body: always extract from page (RSS may have full content already)
        body_el = soup.select_one(self.BODY_CSS)
        if not body_el:
            body_el = soup.select_one(self.BODY_CSS_FALLBACK)
        if body_el:
            result["body"] = self._clean_body_text(body_el)

        # Date fallback
        if not result["published_at"]:
            date_str = self._extract_meta_content(soup, "article:published_time")
            if date_str:
                result["published_at"] = parse_korean_date(date_str)

        # Author fallback
        if not result["author"]:
            author_el = soup.select_one(self.AUTHOR_CSS)
            if author_el:
                result["author"] = extract_korean_author(
                    author_el.get_text(strip=True)
                )

        # Category fallback: URL path
        if not result["category"]:
            # URL: /news/{category}
            from urllib.parse import urlparse
            path_parts = urlparse(url).path.strip("/").split("/")
            if len(path_parts) >= 2 and path_parts[0] == "news":
                result["category"] = path_parts[1]

        return result

    def get_section_urls(self) -> list[str]:
        """Return NoCut News section page URLs."""
        return list(self.SECTION_URLS)

    def _is_article_url(self, url: str) -> bool:
        """NoCut News article URLs: /news/ path with numeric IDs."""
        if "/news/" in url:
            # Section pages are /news/{category}, articles are /news/{id}
            from urllib.parse import urlparse
            path_parts = urlparse(url).path.strip("/").split("/")
            if len(path_parts) >= 2:
                # If last segment is numeric, it is an article
                if path_parts[-1].isdigit():
                    return True
        return super()._is_article_url(url)
