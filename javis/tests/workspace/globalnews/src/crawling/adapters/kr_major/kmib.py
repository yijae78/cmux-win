"""Kookmin Ilbo (kmib.co.kr) site adapter.

Group C — Korean Niche.
Primary method: RSS. Fallback: Sitemap > DOM.
Bot block level: MEDIUM. Proxy: KR required.

Decision Rationale [trace:step-6:kmib-strategy]:
    RSS feeds confirmed via WebFetch at 9 category-specific URLs
    (kmibPolRss.xml, kmibEcoRss.xml, etc.). Article URLs follow
    ?arcid= pattern. UTF-8 charset confirmed. No paywall. Google
    Analytics dataLayer contains article metadata (author_name,
    first_published_date, article_category).

Selectors verified via Step 6 WebFetch verification.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter
from src.crawling.adapters.kr_major._kr_utils import (
    extract_korean_author,
    parse_korean_date,
)

logger = logging.getLogger(__name__)

# Regex to extract dataLayer values from inline script
_DATALAYER_RE = re.compile(
    r"dataLayer\s*=\s*\[\s*\{(.*?)\}\s*\]",
    re.DOTALL,
)


class KmibAdapter(BaseSiteAdapter):
    """Adapter for Kookmin Ilbo (kmib.co.kr).

    Special features:
        - 9 category-specific RSS feeds for comprehensive coverage.
        - Google Analytics dataLayer contains structured metadata.
        - Article URLs use ?arcid= query parameter pattern.
    """

    # --- Site identity ---
    SITE_ID = "kmib"
    SITE_NAME = "Kookmin Ilbo"
    SITE_URL = "https://www.kmib.co.kr"
    LANGUAGE = "ko"
    REGION = "kr"
    GROUP = "C"

    # --- URL discovery ---
    RSS_URL = "https://www.kmib.co.kr/rss/data/kmibPolRss.xml"
    RSS_URLS = [
        "https://www.kmib.co.kr/rss/data/kmibPolRss.xml",
        "https://www.kmib.co.kr/rss/data/kmibEcoRss.xml",
        "https://www.kmib.co.kr/rss/data/kmibSocRss.xml",
        "https://www.kmib.co.kr/rss/data/kmibIntRss.xml",
        "https://www.kmib.co.kr/rss/data/kmibEntRss.xml",
        "https://www.kmib.co.kr/rss/data/kmibSpoRss.xml",
        "https://www.kmib.co.kr/rss/data/kmibGolfRss.xml",
        "https://www.kmib.co.kr/rss/data/kmibLifeRss.xml",
        "https://www.kmib.co.kr/rss/data/kmibTraRss.xml",
    ]
    SITEMAP_URL = "https://www.kmib.co.kr/sitemap.xml"

    # --- Article extraction selectors ---
    # [trace:step-6:kmib-selectors]
    TITLE_CSS = 'meta[property="og:title"]'
    TITLE_CSS_FALLBACK = "h1.article-title"
    BODY_CSS = "div.article-body"
    BODY_CSS_FALLBACK = "div#article_content"
    DATE_CSS = 'meta[property="article:published_time"]'
    AUTHOR_CSS = "span.byline"
    ARTICLE_LINK_CSS = "a[href*='arcid=']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div.ad-container, "
        "div.related-articles, "
        "div.social-share, "
        "div.comment-area"
    )

    # --- Section URLs ---
    # Pattern: /article/listing.asp?sid1={category}
    SECTION_URLS = [
        "https://www.kmib.co.kr/article/listing.asp?sid1=pol",
        "https://www.kmib.co.kr/article/listing.asp?sid1=eco",
        "https://www.kmib.co.kr/article/listing.asp?sid1=soc",
        "https://www.kmib.co.kr/article/listing.asp?sid1=int",
        "https://www.kmib.co.kr/article/listing.asp?sid1=ens",
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

    # RSS feed name to category mapping
    _RSS_CATEGORY_MAP = {
        "kmibPolRss": "politics",
        "kmibEcoRss": "economy",
        "kmibSocRss": "society",
        "kmibIntRss": "international",
        "kmibEntRss": "entertainment",
        "kmibSpoRss": "sports",
        "kmibGolfRss": "golf",
        "kmibLifeRss": "lifestyle",
        "kmibTraRss": "travel",
    }

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from Kookmin Ilbo HTML.

        Extraction priority:
            1. Google Analytics dataLayer (author_name, first_published_date,
               article_category) — structured, high confidence.
            2. og:title meta + CSS selectors.
            3. article:published_time meta tag.

        Notes:
            - Article URLs use ?arcid= parameter.
            - Date display: "2026-02-26(수)" with day-of-week.
            - 9 category RSS feeds for comprehensive section coverage.
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

        # Try to extract from Google Analytics dataLayer
        datalayer = self._extract_datalayer(html)

        # Title
        result["title"] = self._extract_meta_content(soup, "og:title")
        if not result["title"]:
            el = soup.select_one("h1.article-title")
            if el:
                result["title"] = el.get_text(strip=True)

        # Body
        body_el = soup.select_one(self.BODY_CSS)
        if not body_el:
            body_el = soup.select_one(self.BODY_CSS_FALLBACK)
        if body_el:
            result["body"] = self._clean_body_text(body_el)

        # Date: dataLayer first_published_date -> meta tag
        if datalayer.get("first_published_date"):
            result["published_at"] = parse_korean_date(
                datalayer["first_published_date"]
            )
        if not result["published_at"]:
            date_str = self._extract_meta_content(soup, "article:published_time")
            if date_str:
                result["published_at"] = parse_korean_date(date_str)

        # Author: dataLayer author_name -> span.byline
        if datalayer.get("author_name"):
            result["author"] = extract_korean_author(datalayer["author_name"])
        if not result["author"]:
            author_el = soup.select_one(self.AUTHOR_CSS)
            if author_el:
                result["author"] = extract_korean_author(
                    author_el.get_text(strip=True)
                )

        # Category: dataLayer article_category -> URL sid1 param
        if datalayer.get("article_category"):
            result["category"] = datalayer["article_category"].lower()
        if not result["category"]:
            result["category"] = self._extract_category_from_kmib_url(url)

        return result

    def get_section_urls(self) -> list[str]:
        """Return Kookmin Ilbo section page URLs."""
        return list(self.SECTION_URLS)

    def _is_article_url(self, url: str) -> bool:
        """Kookmin Ilbo article URLs contain ?arcid= parameter."""
        if "arcid=" in url:
            return True
        return super()._is_article_url(url)

    @staticmethod
    def _extract_datalayer(html: str) -> dict[str, str]:
        """Extract Google Analytics dataLayer variables from HTML.

        Looks for inline script blocks containing ``dataLayer = [{...}]``
        and extracts key-value pairs.

        Args:
            html: Raw HTML content.

        Returns:
            Dict of extracted dataLayer fields. Empty dict if not found.
        """
        match = _DATALAYER_RE.search(html)
        if not match:
            return {}

        raw_content = match.group(1)
        result: dict[str, str] = {}

        # Extract simple string key-value pairs
        for kv_match in re.finditer(
            r"['\"]?(\w+)['\"]?\s*:\s*['\"]([^'\"]*)['\"]",
            raw_content,
        ):
            key = kv_match.group(1)
            value = kv_match.group(2)
            result[key] = value

        return result

    @staticmethod
    def _extract_category_from_kmib_url(url: str) -> str | None:
        """Extract category from kmib URL's sid1 parameter.

        Args:
            url: Article URL with potential sid1 parameter.

        Returns:
            Category string, or None.
        """
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        sid1 = params.get("sid1", [None])[0]
        if sid1:
            sid_map = {
                "pol": "politics",
                "eco": "economy",
                "soc": "society",
                "int": "international",
                "ens": "entertainment",
                "spo": "sports",
            }
            return sid_map.get(sid1.lower(), sid1.lower())

        return None
