"""ZDNet Korea adapter -- Enterprise IT/tech news.

ZDNet Korea (zdnet.co.kr) is the Korean edition of ZDNet, covering
enterprise IT, cloud computing, AI, mobile, and security. Articles
use a /view/?no=YYYYMMDDNNNNNN URL pattern.

Key characteristics:
    - Article URLs: /view/?no=YYYYMMDDNNNNNN
    - Section navigation: /news/?lstcode=NNNN
    - RSS feed at /rss
    - MEDIUM bot blocking
    - Structured article format with clear title/body separation
    - ~80 articles/day across 8 sections

Reference:
    sources.yaml key: zdnet_kr
    Step 6: Group D, RSS-first strategy
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter

import logging

logger = logging.getLogger(__name__)

# Korean relative date patterns
_KR_RELATIVE_RE = re.compile(
    r"(\d+)\s*(시간|분|초|일)\s*전"
)
_KR_DATE_RE = re.compile(
    r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\s*(\d{1,2}):(\d{2})(?::(\d{2}))?"
)


class ZdnetKrAdapter(BaseSiteAdapter):
    """Adapter for ZDNet Korea (zdnet.co.kr)."""

    # --- Site identity ---
    SITE_ID = "zdnet_kr"
    SITE_NAME = "ZDNet Korea"
    SITE_URL = "https://www.zdnet.co.kr"
    LANGUAGE = "ko"
    REGION = "kr"
    GROUP = "D"

    # --- URL discovery ---
    RSS_URL = "https://www.zdnet.co.kr/rss"
    SITEMAP_URL = "/sitemap.xml"

    # --- Article extraction selectors ---
    # ZDNet Korea uses structured article layout
    TITLE_CSS = "h1.article_tit"
    TITLE_CSS_FALLBACK = "h2.article_tit, div.article_header h1"
    # Body: article content container
    BODY_CSS = "div.article_txt"
    BODY_CSS_FALLBACK = "div.article_body, div#article_body"
    # Date element
    DATE_CSS = "span.article_date, li.article_date"
    # Author byline
    AUTHOR_CSS = "span.article_writer, li.article_writer a"
    # Article links on listing pages: /view/?no=...
    ARTICLE_LINK_CSS = "a[href*='/view/?no=']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div.ad_wrap, div.article_ad, "
        "div.article_relation, div.relation_news, "
        "div.article_sns, div.share_area, "
        "div.article_tag, "
        "div.comment_wrap, "
        "div.copyright_area, "
        "nav, aside, footer"
    )

    # --- Section URLs ---
    # ZDNet Korea uses lstcode parameter for sections
    SECTION_URLS = [
        "https://www.zdnet.co.kr/news/?lstcode=0000",  # Latest
        "https://www.zdnet.co.kr/news/?lstcode=0010",  # Telecom
        "https://www.zdnet.co.kr/news/?lstcode=0020",  # Computing
        "https://www.zdnet.co.kr/news/?lstcode=0030",  # Internet
        "https://www.zdnet.co.kr/news/?lstcode=0040",  # Mobile
        "https://www.zdnet.co.kr/news/?lstcode=0050",  # Security
        "https://www.zdnet.co.kr/news/?lstcode=0060",  # SW/Dev
        "https://www.zdnet.co.kr/news/?lstcode=0070",  # Game
    ]

    PAGINATION_TYPE = "page_number"
    PAGINATION_PARAM = "page"
    MAX_PAGES = 5

    # --- Rate limiting (from sources.yaml) ---
    RATE_LIMIT_SECONDS = 5.0
    MAX_REQUESTS_PER_HOUR = 720
    JITTER_SECONDS = 0.0

    # --- Anti-block ---
    ANTI_BLOCK_TIER = 1
    UA_TIER = 2
    REQUIRES_PROXY = True
    PROXY_REGION = "kr"
    BOT_BLOCK_LEVEL = "MEDIUM"

    # --- Extraction ---
    PAYWALL_TYPE = "none"
    CHARSET = "utf-8"
    RENDERING_REQUIRED = False

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from ZDNet Korea HTML.

        ZDNet Korea uses a structured article layout similar to the
        international ZDNet but with Korean-specific CSS classes and
        date formats.

        Args:
            html: Raw HTML of the article page.
            url: Article URL.

        Returns:
            Dict with title, body, published_at, author, category.
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")

        # --- Title ---
        title = ""
        for selector in (self.TITLE_CSS, self.TITLE_CSS_FALLBACK):
            el = soup.select_one(selector)
            if el:
                title = el.get_text(strip=True)
                if title:
                    break
        if not title:
            title = self._extract_meta_content(soup, "og:title")

        # --- Body ---
        body = ""
        for selector in (self.BODY_CSS, self.BODY_CSS_FALLBACK):
            el = soup.select_one(selector)
            if el:
                body = self._clean_body_text(el)
                if body:
                    break

        # --- Date ---
        published_at = None
        date_el = soup.select_one(self.DATE_CSS)
        if date_el:
            date_text = date_el.get_text(strip=True)
            # ZDNet dates: "2026.02.25 14:30" or "입력 : 2026.02.25 14:30"
            date_text = re.sub(r"^(입력|수정)\s*:?\s*", "", date_text).strip()
            published_at = self._parse_korean_date(date_text)

        if not published_at:
            meta_date = self._extract_meta_content(soup, "article:published_time")
            if meta_date:
                published_at = self.normalize_date(meta_date)

        if not published_at:
            ld = self._extract_json_ld(soup)
            if ld.get("datePublished"):
                published_at = self.normalize_date(ld["datePublished"])

        # --- Author ---
        author = None
        author_el = soup.select_one(self.AUTHOR_CSS)
        if author_el:
            author_text = author_el.get_text(strip=True)
            # Remove email in parentheses first: "홍길동 기자 (email)" -> "홍길동 기자"
            author = re.sub(r"\s*\(.*?\)\s*$", "", author_text).strip()
            # Strip trailing " 기자" suffix (reporter title)
            author = re.sub(r"\s+기자\s*$", "", author).strip()
            if not author:
                author = author_text
        if not author:
            author = self._extract_meta_content(soup, "article:author") or None

        # --- Category ---
        category = None
        cat_el = soup.select_one(
            "span.article_cate, a.article_cate, "
            "div.article_header span.cate, li.article_cate"
        )
        if cat_el:
            category = cat_el.get_text(strip=True)
        if not category:
            category = self._extract_meta_content(soup, "article:section") or None
        # Try extracting from lstcode in URL
        if not category and "lstcode=" in url:
            _lstcode_map = {
                "0010": "Telecom",
                "0020": "Computing",
                "0030": "Internet",
                "0040": "Mobile",
                "0050": "Security",
                "0060": "Software",
                "0070": "Game",
            }
            m = re.search(r"lstcode=(\d+)", url)
            if m and m.group(1) in _lstcode_map:
                category = _lstcode_map[m.group(1)]

        return {
            "title": title,
            "body": body,
            "published_at": published_at,
            "author": author,
            "category": category,
        }

    def get_section_urls(self) -> list[str]:
        """Return ZDNet Korea section page URLs."""
        return list(self.SECTION_URLS)

    def _is_article_url(self, url: str) -> bool:
        """Check if URL matches ZDNet Korea article pattern.

        ZDNet Korea articles use: /view/?no=YYYYMMDDNNNNNN
        """
        if "/view/" in url and "no=" in url:
            return True
        return super()._is_article_url(url)

    def _parse_korean_date(self, text: str) -> datetime | None:
        """Parse Korean date formats used by ZDNet Korea.

        Handles:
            - "2026.02.25 14:30"
            - "2026-02-25 14:30:00"
            - Relative: "3시간 전"
        """
        text = text.strip()

        # Relative dates
        m = _KR_RELATIVE_RE.search(text)
        if m:
            value = int(m.group(1))
            unit = m.group(2)
            now = datetime.now(timezone.utc)
            if unit == "시간":
                return now - timedelta(hours=value)
            elif unit == "분":
                return now - timedelta(minutes=value)
            elif unit == "초":
                return now - timedelta(seconds=value)
            elif unit == "일":
                return now - timedelta(days=value)

        # Absolute dates
        m = _KR_DATE_RE.search(text)
        if m:
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            hour, minute = int(m.group(4)), int(m.group(5))
            second = int(m.group(6)) if m.group(6) else 0
            try:
                kst = timezone(timedelta(hours=9))
                dt = datetime(year, month, day, hour, minute, second, tzinfo=kst)
                return dt.astimezone(timezone.utc)
            except (ValueError, OverflowError):
                pass

        return self.normalize_date(text)
