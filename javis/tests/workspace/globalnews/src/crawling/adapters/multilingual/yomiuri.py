"""Yomiuri Shimbun (yomiuri.co.jp) adapter -- Japan's largest newspaper.

Site #36, Group F (Asia-Pacific).
Language: Japanese (ja). Encoding: UTF-8 / Shift_JIS legacy.
Primary method: RSS.
Rate limit: 10s + jitter. Bot-blocking: HIGH.
Proxy: Japanese residential IP REQUIRED.

NOTE: All selectors are pattern-based (site blocked from non-Japanese IPs).
Runtime verification from Japanese proxy required before production.

Reference:
    Step 6 crawl-strategy-asia.md, Section 4.5.
"""

from __future__ import annotations

import re
from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter
from src.crawling.adapters.multilingual._ml_utils import (
    parse_japanese_date,
    extract_japanese_author,
    strip_ruby_annotations,
    decode_with_fallback,
)


class YomiuriAdapter(BaseSiteAdapter):
    """Adapter for Yomiuri Shimbun (yomiuri.co.jp)."""

    SITE_ID = "yomiuri"
    SITE_NAME = "Yomiuri Shimbun"
    SITE_URL = "https://www.yomiuri.co.jp"
    LANGUAGE = "ja"
    REGION = "jp"
    GROUP = "F"

    # --- URL discovery ---
    RSS_URL = "https://www.yomiuri.co.jp/feed/"
    RSS_URLS = [
        "https://www.yomiuri.co.jp/feed/",
        "https://www.yomiuri.co.jp/feed/national/",
        "https://www.yomiuri.co.jp/feed/world/",
        "https://www.yomiuri.co.jp/feed/economy/",
        "https://www.yomiuri.co.jp/feed/sports/",
        "https://www.yomiuri.co.jp/feed/culture/",
        "https://www.yomiuri.co.jp/feed/science/",
    ]
    SITEMAP_URL = "/sitemap.xml"

    # --- Selectors (pattern-based -- require JP proxy verification) ---
    TITLE_CSS = "h1"
    TITLE_CSS_FALLBACK = "meta[property='og:title']"
    BODY_CSS = "article"
    BODY_CSS_FALLBACK = "div.article-body, div#article-body"
    DATE_CSS = "time[datetime]"
    AUTHOR_CSS = ""  # Extracted via regex from body text
    ARTICLE_LINK_CSS = "a[href*='/20']"  # Year-based URL pattern

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, nav, aside, footer, "
        "div.article-related, div[class*='ad'], "
        "div[class*='share'], div[class*='recommend'], "
        "div.premium-banner"
    )

    SECTION_URLS = [
        "https://www.yomiuri.co.jp/national/",
        "https://www.yomiuri.co.jp/world/",
        "https://www.yomiuri.co.jp/economy/",
        "https://www.yomiuri.co.jp/sports/",
        "https://www.yomiuri.co.jp/culture/",
        "https://www.yomiuri.co.jp/science/",
        "https://www.yomiuri.co.jp/editorial/",
    ]

    # --- Rate limiting ---
    RATE_LIMIT_SECONDS = 10.0
    MAX_REQUESTS_PER_HOUR = 240
    JITTER_SECONDS = 3.0

    # --- Anti-block (HIGH, JP proxy required) ---
    ANTI_BLOCK_TIER = 2
    UA_TIER = 3
    REQUIRES_PROXY = True
    PROXY_REGION = "jp"
    BOT_BLOCK_LEVEL = "HIGH"

    PAYWALL_TYPE = "soft-metered"
    CHARSET = "utf-8"

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article from Yomiuri HTML.

        Handles ruby annotations and Japanese date formats.
        """
        # Strip ruby annotations before parsing
        html = strip_ruby_annotations(html)

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        # Title
        title = ""
        title_el = soup.select_one(self.TITLE_CSS)
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

        # Date: prefer datetime attribute from <time> element, then Japanese format
        published_at = None
        time_el = soup.select_one(self.DATE_CSS)
        if time_el and time_el.get("datetime"):
            published_at = self.normalize_date(time_el["datetime"])
        if not published_at:
            meta_date = self._extract_meta_content(soup, "article:published_time")
            if meta_date:
                published_at = self.normalize_date(meta_date)
        if not published_at:
            # Try Japanese date pattern in visible text
            date_text = soup.get_text()[:500]
            published_at = parse_japanese_date(date_text)

        # Author from body text
        author = None
        if body:
            author = extract_japanese_author(body)
        if not author:
            # Check for wire attribution: （読売新聞）
            wire_match = re.search(r"[（(](読売新聞|共同通信|ロイター|AP)[）)]", html)
            if wire_match:
                author = wire_match.group(1)

        # Category from URL path
        category = self._extract_category_from_url(url)

        return {
            "title": title,
            "body": body,
            "published_at": published_at,
            "author": author,
            "category": category,
            "is_paywall_truncated": False,
        }

    def get_section_urls(self) -> list[str]:
        return list(self.SECTION_URLS)

    def handle_encoding(self, raw_bytes: bytes) -> str:
        """Handle UTF-8/Shift_JIS/EUC-JP detection for Yomiuri.

        Modern pages use UTF-8; legacy archive pages may use Shift_JIS.
        """
        return decode_with_fallback(
            raw_bytes,
            primary_encoding="utf-8",
            fallback_encodings=["cp932", "euc-jp"],
        )

    def normalize_date(self, date_str: str) -> Any:
        """Parse ISO 8601 first, then Japanese date formats."""
        # Try standard ISO 8601 / RFC 2822
        result = super().normalize_date(date_str)
        if result:
            return result
        # Try Japanese format
        return parse_japanese_date(date_str)

    def _extract_category_from_url(self, url: str, segment_index: int = 1) -> str | None:
        """Extract category from Yomiuri URL: /national/20260226-OYT1T50123/"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        parts = [p for p in parsed.path.split("/") if p]
        if parts:
            first = parts[0]
            # Check it is not a date-like segment
            if not re.match(r"\d{8}", first):
                return first
        return None
