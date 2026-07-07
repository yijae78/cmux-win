"""Electronic Times (ET News) adapter -- Korean electronics/IT industry news.

ETNews (etnews.com) is a major Korean IT/electronics news site covering
semiconductors, telecommunications, software, and IT policy. It has a
large article volume (~100/day) with structured sections.

Key characteristics:
    - Article URLs use numeric IDs: /YYYYMMDDNNNNNN
    - RSS feed available at /rss
    - Sections use lstcode parameter: /news/section.html?id1=XX
    - UTF-8 encoding (modern, despite being a legacy publisher)
    - MEDIUM bot blocking
    - Many sections: broadcasting, computing, mobile, etc.

Reference:
    sources.yaml key: etnews
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
# ETNews article ID pattern: 14-digit numeric
_ETNEWS_ARTICLE_RE = re.compile(r"/(\d{14,})$")


class EtnewsAdapter(BaseSiteAdapter):
    """Adapter for Electronic Times / ETNews (etnews.com)."""

    # --- Site identity ---
    SITE_ID = "etnews"
    SITE_NAME = "Electronic Times"
    SITE_URL = "https://www.etnews.com"
    LANGUAGE = "ko"
    REGION = "kr"
    GROUP = "D"

    # --- URL discovery ---
    RSS_URL = "https://www.etnews.com/rss"
    SITEMAP_URL = "/sitemap.xml"

    # --- Article extraction selectors ---
    # ETNews article pages use article_header and article_body patterns
    TITLE_CSS = "h1.article_tit"
    TITLE_CSS_FALLBACK = "h2.article_tit, div.article_header h1"
    # Body: div.article_txt (main content container)
    BODY_CSS = "div.article_txt"
    BODY_CSS_FALLBACK = "div.article_body, div#articleBody"
    # Date: ETNews has date info in article header section
    DATE_CSS = "span.article_date, time.article_date"
    # Author: byline section
    AUTHOR_CSS = "span.article_writer, div.article_byline span"
    # Listing: article links with numeric IDs
    ARTICLE_LINK_CSS = "a[href*='/2026'], a[href*='/2025'], a[href*='/view/?no=']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div.ad_wrap, div.article_ad, "
        "div.related_news, div.article_relation, "
        "div.article_sns, div.sns_share, "
        "div.article_tag, div.tag_area, "
        "div.comment_area, "
        "nav, aside, footer"
    )

    # --- Section URLs ---
    # ETNews uses lstcode-based sections: 0000=latest, 0010=telecom, etc.
    SECTION_URLS = [
        "https://www.etnews.com/news/section.html?id1=01",   # Telecom/Broadcasting
        "https://www.etnews.com/news/section.html?id1=02",   # Semiconductor/Display
        "https://www.etnews.com/news/section.html?id1=03",   # IT/Internet
        "https://www.etnews.com/news/section.html?id1=04",   # Software
        "https://www.etnews.com/news/section.html?id1=05",   # Game
        "https://www.etnews.com/news/section.html?id1=06",   # Security
        "https://www.etnews.com/news/section.html?id1=07",   # Mobile
        "https://www.etnews.com/news/section.html?id1=08",   # Economy
        "https://www.etnews.com/news/section.html?id1=09",   # Policy
        "https://www.etnews.com/news/section.html?id1=10",   # International
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
        """Extract article fields from ETNews HTML.

        ETNews uses structured article pages with article_tit for title,
        article_txt for body, and metadata in the article header area.
        The site produces high-volume tech/electronics industry content.

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
            # ETNews dates: "2026.02.25 14:30:00" or "입력 2026.02.25 14:30"
            date_text = date_text.replace("입력", "").replace("수정", "").strip()
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
            # Clean ETNews author format: "홍길동 기자" -> "홍길동"
            author = re.sub(r"\s+기자\s*$", "", author_text).strip()
            if not author:
                author = author_text
        if not author:
            author = self._extract_meta_content(soup, "article:author") or None

        # --- Category ---
        category = None
        cat_el = soup.select_one(
            "span.article_cate, a.article_cate, "
            "div.article_header span.cate"
        )
        if cat_el:
            category = cat_el.get_text(strip=True)
        if not category:
            category = self._extract_meta_content(soup, "article:section") or None

        return {
            "title": title,
            "body": body,
            "published_at": published_at,
            "author": author,
            "category": category,
        }

    def get_section_urls(self) -> list[str]:
        """Return ETNews section page URLs."""
        return list(self.SECTION_URLS)

    def _is_article_url(self, url: str) -> bool:
        """Check if URL matches ETNews article pattern.

        ETNews articles use: /YYYYMMDDNNNNNN (14+ digit numeric ID)
        or /view/?no=YYYYMMDDNNNNNN
        """
        if _ETNEWS_ARTICLE_RE.search(url):
            return True
        if "view/?no=" in url:
            return True
        return super()._is_article_url(url)

    def _parse_korean_date(self, text: str) -> datetime | None:
        """Parse Korean date formats used by ETNews.

        Handles:
            - "2026.02.25 14:30:00"
            - "2026-02-25 14:30"
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
