"""People's Daily (people.com.cn) adapter -- Chinese state media.

Site #32, Group F (Asia-Pacific).
Language: Chinese (zh). Encoding: UTF-8 / GB2312 legacy.
Primary method: Sitemap (78 category sitemaps).
Rate limit: 120s MANDATORY crawl-delay (robots.txt).

Reference:
    Step 6 crawl-strategy-asia.md, Section 4.1.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter
from src.crawling.adapters.multilingual._ml_utils import (
    parse_chinese_date,
    extract_chinese_author,
    detect_encoding,
    decode_with_fallback,
)


class PeopleAdapter(BaseSiteAdapter):
    """Adapter for People's Daily (people.com.cn)."""

    SITE_ID = "people"
    SITE_NAME = "People's Daily"
    SITE_URL = "http://www.people.com.cn"
    LANGUAGE = "zh"
    REGION = "cn"
    GROUP = "F"

    # --- URL discovery ---
    SITEMAP_URL = "http://www.people.cn/sitemap_index.xml"

    # --- Selectors ---
    TITLE_CSS = ".rm_txt h1"
    TITLE_CSS_FALLBACK = "h1"
    BODY_CSS = "div.rm_txt_con"
    BODY_CSS_FALLBACK = "div.box_con"
    DATE_CSS = "div.box01 .fl"
    AUTHOR_CSS = ""  # Extracted via regex from body text
    ARTICLE_LINK_CSS = ".list1 li a"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, nav, aside, footer, "
        "div.rm_nav, div.edit, div.page_num, "
        "div[class*='share'], div[class*='ad'], "
        "div.related, div.otherContent_01"
    )

    SECTION_URLS = [
        "http://world.people.com.cn/",
        "http://finance.people.com.cn/",
        "http://politics.people.com.cn/",
        "http://society.people.com.cn/",
        "http://sports.people.com.cn/",
        "http://culture.people.com.cn/",
        "http://health.people.com.cn/",
        "http://military.people.com.cn/",
        "http://edu.people.com.cn/",
        "http://scitech.people.com.cn/",
    ]

    # --- Rate limiting (120s MANDATORY) ---
    RATE_LIMIT_SECONDS = 120.0
    MAX_REQUESTS_PER_HOUR = 30
    JITTER_SECONDS = 0.0

    # --- Anti-block ---
    ANTI_BLOCK_TIER = 1
    UA_TIER = 2
    REQUIRES_PROXY = False
    BOT_BLOCK_LEVEL = "MEDIUM"

    # --- Encoding ---
    CHARSET = "utf-8"

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article from People's Daily HTML."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")

        # Title
        title = ""
        title_el = soup.select_one(self.TITLE_CSS)
        if not title_el:
            title_el = soup.select_one(self.TITLE_CSS_FALLBACK)
        if title_el:
            title = title_el.get_text(strip=True)

        if not title:
            title = self._extract_meta_content(soup, "og:title")

        # Body
        body = ""
        body_el = soup.select_one(self.BODY_CSS)
        if not body_el:
            body_el = soup.select_one(self.BODY_CSS_FALLBACK)
        if body_el:
            body = self._clean_body_text(body_el)

        # Date: pattern "2026年02月26日12:25" in article metadata area
        published_at = None
        date_el = soup.select_one(self.DATE_CSS)
        if date_el:
            date_text = date_el.get_text(strip=True)
            published_at = parse_chinese_date(date_text)

        # Try meta tag fallback
        if not published_at:
            meta_date = self._extract_meta_content(soup, "article:published_time")
            if meta_date:
                published_at = self.normalize_date(meta_date)

        # Author: extract from body text using Chinese patterns
        author = None
        if body:
            author = extract_chinese_author(body)
        if not author:
            # Check for source attribution
            source_match = re.search(r"来源[：:]\s*([\u4e00-\u9fff\w]+)", html)
            if source_match:
                author = source_match.group(1)

        # Category from URL
        category = self._extract_category_from_url(url)
        if not category:
            # Try breadcrumb
            breadcrumb = soup.select_one(".col_nav a:last-child")
            if breadcrumb:
                category = breadcrumb.get_text(strip=True)

        return {
            "title": title,
            "body": body,
            "published_at": published_at,
            "author": author,
            "category": category,
            "is_paywall_truncated": False,
        }

    def get_section_urls(self) -> list[str]:
        """Return People's Daily section URLs."""
        return list(self.SECTION_URLS)

    def handle_encoding(self, raw_bytes: bytes) -> str:
        """Handle GB2312/GBK/UTF-8 encoding detection for People's Daily.

        Legacy pages on subdomains may serve GB2312; modern pages use UTF-8.
        Decode with gb18030 superset for any GB-family encoding detected.
        """
        return decode_with_fallback(
            raw_bytes,
            primary_encoding="utf-8",
            fallback_encodings=["gb18030", "gbk", "gb2312"],
        )

    def _extract_category_from_url(self, url: str, segment_index: int = 1) -> str | None:
        """Extract category from people.com.cn subdomain-based URL.

        People.com.cn uses subdomain architecture:
            http://world.people.com.cn/...  -> "world"
            http://finance.people.com.cn/... -> "finance"

        Note: .com.cn is a double TLD, so hostname splits as:
            ["world", "people", "com", "cn"]
        """
        from urllib.parse import urlparse
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        parts = hostname.split(".")
        # Check for *.people.com.cn pattern (double TLD)
        if len(parts) >= 4 and "people" in parts:
            subdomain = parts[0]
            if subdomain not in ("www", "people"):
                return subdomain
        # Check for *.people.cn pattern
        if len(parts) >= 3 and parts[-3] == "people":
            subdomain = parts[0]
            if subdomain not in ("www", "people"):
                return subdomain
        return None
