"""OhmyNews adapter -- Korean citizen journalism portal.

OhmyNews (ohmynews.com) is a citizen journalism platform with varied article
formats. Articles use ASP.NET URL patterns with CNTN_CD (content ID) and
PAGE_CD (section code) parameters.

Key characteristics:
    - ASP.NET URL structure: /NWS_Web/View/at_pg.aspx?CNTN_CD=...
    - Citizen journalists + professional reporters
    - RSS feed available at /rss/rss.xml
    - UTF-8 encoding
    - LOW bot blocking

Reference:
    sources.yaml key: ohmynews
    Step 6: Group C, RSS-first strategy
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
# Korean absolute date: YYYY.MM.DD HH:MM or YYYY-MM-DD HH:MM:SS
_KR_DATE_RE = re.compile(
    r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\s*(\d{1,2}):(\d{2})(?::(\d{2}))?"
)


class OhmynewsAdapter(BaseSiteAdapter):
    """Adapter for OhmyNews (ohmynews.com)."""

    # --- Site identity ---
    SITE_ID = "ohmynews"
    SITE_NAME = "OhmyNews"
    SITE_URL = "https://www.ohmynews.com"
    LANGUAGE = "ko"
    REGION = "kr"
    GROUP = "C"

    # --- URL discovery ---
    RSS_URL = "https://www.ohmynews.com/rss/rss.xml"
    SITEMAP_URL = "/sitemap.xml"

    # --- Article extraction selectors ---
    # OhmyNews article pages use these structures:
    # Title: h2.tit_head or og:title
    TITLE_CSS = "h2.tit_head"
    TITLE_CSS_FALLBACK = "h3.at_head"
    # Body: div.at_contents (article text container)
    BODY_CSS = "div.at_contents"
    BODY_CSS_FALLBACK = "div.article_view"
    # Date: span.info_data or time element
    DATE_CSS = "span.info_data"
    # Author: span.info_name or a.info_name
    AUTHOR_CSS = "span.info_name, a.info_name"
    # Listing pages: article links
    ARTICLE_LINK_CSS = "a[href*='at_pg.aspx'], a[href*='CNTN_CD=']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div.ad-container, div.advertisement, "
        "div.related-articles, div.related, "
        "div.social-share, div.sns_area, "
        "div.comments, div.comment-section, "
        "div.article_copywriter, "
        "nav, aside, footer"
    )

    # --- Section URLs ---
    SECTION_URLS = [
        "https://www.ohmynews.com/NWS_Web/ArticlePage/Total_Article.aspx",
        "https://www.ohmynews.com/NWS_Web/View/ss_pg.aspx?PAGE_CD=C0400",  # Politics
        "https://www.ohmynews.com/NWS_Web/View/ss_pg.aspx?PAGE_CD=C0300",  # Economy
        "https://www.ohmynews.com/NWS_Web/View/ss_pg.aspx?PAGE_CD=C0200",  # Society
        "https://www.ohmynews.com/NWS_Web/View/ss_pg.aspx?PAGE_CD=C0700",  # Education
        "https://www.ohmynews.com/NWS_Web/View/ss_pg.aspx?PAGE_CD=C0500",  # International
    ]

    PAGINATION_TYPE = "page_number"
    PAGINATION_PARAM = "PAGE_INDEX"
    MAX_PAGES = 5

    # --- Rate limiting (from sources.yaml) ---
    RATE_LIMIT_SECONDS = 2.0
    MAX_REQUESTS_PER_HOUR = 1800
    JITTER_SECONDS = 0.0

    # --- Anti-block ---
    ANTI_BLOCK_TIER = 1
    UA_TIER = 1
    REQUIRES_PROXY = True
    PROXY_REGION = "kr"
    BOT_BLOCK_LEVEL = "LOW"

    # --- Extraction ---
    PAYWALL_TYPE = "none"
    CHARSET = "utf-8"
    RENDERING_REQUIRED = False

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from OhmyNews HTML.

        OhmyNews uses ASP.NET-generated pages with consistent CSS classes
        for article content, titles, author info, and publication dates.

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
            published_at = self._parse_korean_date(date_text)
        if not published_at:
            # Try meta tag
            meta_date = self._extract_meta_content(soup, "article:published_time")
            if meta_date:
                published_at = self.normalize_date(meta_date)

        # --- Author ---
        author = None
        author_el = soup.select_one(self.AUTHOR_CSS)
        if author_el:
            author = author_el.get_text(strip=True)
            # Clean common prefixes
            for prefix in ("기자 ", "시민기자 ", "기고 "):
                if author.endswith(prefix.strip()):
                    break
            author = author.strip()

        # --- Category ---
        category = None
        cat_el = soup.select_one("span.at_cate, a.category")
        if cat_el:
            category = cat_el.get_text(strip=True)
        if not category:
            category = self._extract_meta_content(soup, "article:section")

        return {
            "title": title,
            "body": body,
            "published_at": published_at,
            "author": author,
            "category": category,
        }

    def get_section_urls(self) -> list[str]:
        """Return OhmyNews section page URLs for DOM discovery."""
        return list(self.SECTION_URLS)

    def _is_article_url(self, url: str) -> bool:
        """Check if URL matches OhmyNews article pattern.

        OhmyNews articles use: /NWS_Web/View/at_pg.aspx?CNTN_CD=...
        """
        if "at_pg.aspx" in url and "CNTN_CD=" in url:
            return True
        return super()._is_article_url(url)

    def _parse_korean_date(self, text: str) -> datetime | None:
        """Parse Korean-format date strings.

        Handles:
            - Relative: "3시간 전", "30분 전"
            - Absolute: "2026.02.25 14:30"
            - Standard: "2026-02-25 14:30:00"

        Args:
            text: Date string in Korean format.

        Returns:
            Datetime in UTC or None.
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

        # Absolute Korean dates
        m = _KR_DATE_RE.search(text)
        if m:
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            hour, minute = int(m.group(4)), int(m.group(5))
            second = int(m.group(6)) if m.group(6) else 0
            try:
                # Korean times are KST (UTC+9)
                kst = timezone(timedelta(hours=9))
                dt = datetime(year, month, day, hour, minute, second, tzinfo=kst)
                return dt.astimezone(timezone.utc)
            except (ValueError, OverflowError):
                pass

        # Fall back to base parser
        return self.normalize_date(text)
