"""Science Times adapter -- Korean science & technology news.

Science Times (sciencetimes.co.kr) is a Korean government-supported
science journalism platform. It uses a custom CMS with specific URL
patterns for articles.

Key characteristics:
    - Custom URL structure: /nscvrg/view/menu/ID?searchCategory=X&nscvrgSn=Y
    - No RSS feed (sitemap-first strategy)
    - HIGH bot blocking -- needs Tier 2+ escalation
    - Government/institutional backing
    - Multiple science categories (basic science, IT, biotech, etc.)
    - Date format: YYYY-MM-DD consistently

Reference:
    sources.yaml key: sciencetimes
    Step 6: Group D, Sitemap-first strategy
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
    r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\s*(?:(\d{1,2}):(\d{2})(?::(\d{2}))?)?"
)


class SciencetimesAdapter(BaseSiteAdapter):
    """Adapter for Science Times (sciencetimes.co.kr)."""

    # --- Site identity ---
    SITE_ID = "sciencetimes"
    SITE_NAME = "Science Times"
    SITE_URL = "https://www.sciencetimes.co.kr"
    LANGUAGE = "ko"
    REGION = "kr"
    GROUP = "D"

    # --- URL discovery ---
    RSS_URL = ""  # No RSS feed available
    SITEMAP_URL = "/sitemap.xml"

    # --- Article extraction selectors ---
    # Science Times uses a custom CMS with specific class patterns
    TITLE_CSS = "h3.articleView_tit, h2.articleView_tit"
    TITLE_CSS_FALLBACK = "div.article_head h1, h1.article-title"
    # Body container
    BODY_CSS = "div.articleView_txt, div.article_txt"
    BODY_CSS_FALLBACK = "div.article_body, div#article-body"
    # Date: typically in article header metadata
    DATE_CSS = "span.articleView_date, span.article_date"
    # Author: reporter byline
    AUTHOR_CSS = "span.articleView_writer, span.article_writer"
    # Listing page article links
    ARTICLE_LINK_CSS = (
        "a[href*='nscvrg/view'], a[href*='nscvrgSn='], "
        "div.list_item a"
    )

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div.ad-area, div.ad_wrap, "
        "div.article_relation, div.related_article, "
        "div.article_sns, div.sns_area, "
        "div.comment_area, "
        "div.article_copyright, "
        "nav, aside, footer"
    )

    # --- Section URLs ---
    # Science Times organizes by menu categories with searchCategory parameter
    SECTION_URLS = [
        "https://www.sciencetimes.co.kr/nscvrg/list/menu/247?searchCategory=271",  # Basic Science
        "https://www.sciencetimes.co.kr/nscvrg/list/menu/248?searchCategory=272",  # IT/Convergence
        "https://www.sciencetimes.co.kr/nscvrg/list/menu/249?searchCategory=273",  # Biotech
        "https://www.sciencetimes.co.kr/nscvrg/list/menu/250?searchCategory=274",  # Energy/Environment
        "https://www.sciencetimes.co.kr/nscvrg/list/menu/251?searchCategory=275",  # Aerospace
        "https://www.sciencetimes.co.kr/nscvrg/list/menu/252?searchCategory=276",  # Health/Medicine
        "https://www.sciencetimes.co.kr/nscvrg/list/menu/254?searchCategory=278",  # Policy
        "https://www.sciencetimes.co.kr/nscvrg/list/menu/255?searchCategory=279",  # Culture
    ]

    PAGINATION_TYPE = "page_number"
    PAGINATION_PARAM = "page"
    MAX_PAGES = 5

    # --- Rate limiting (from sources.yaml) ---
    RATE_LIMIT_SECONDS = 10.0
    MAX_REQUESTS_PER_HOUR = 240
    JITTER_SECONDS = 3.0

    # --- Anti-block ---
    ANTI_BLOCK_TIER = 2
    UA_TIER = 3
    REQUIRES_PROXY = True
    PROXY_REGION = "kr"
    BOT_BLOCK_LEVEL = "HIGH"

    # --- Extraction ---
    PAYWALL_TYPE = "none"
    CHARSET = "utf-8"
    RENDERING_REQUIRED = False

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from Science Times HTML.

        Science Times uses a custom CMS with articleView_ prefixed classes.
        Content is science-focused with reporter bylines and consistent
        date formatting (YYYY-MM-DD).

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
            meta_date = self._extract_meta_content(soup, "article:published_time")
            if meta_date:
                published_at = self.normalize_date(meta_date)

        # --- Author ---
        author = None
        author_el = soup.select_one(self.AUTHOR_CSS)
        if author_el:
            author_text = author_el.get_text(strip=True)
            # Clean Science Times author format: "홍길동 기자" -> "홍길동"
            author = re.sub(r"\s+기자\s*$", "", author_text).strip()
            if not author:
                author = author_text
        if not author:
            author = self._extract_meta_content(soup, "article:author") or None

        # --- Category ---
        category = None
        cat_el = soup.select_one(
            "span.articleView_cate, a.articleView_cate, "
            "span.category_label"
        )
        if cat_el:
            category = cat_el.get_text(strip=True)
        if not category:
            category = self._extract_meta_content(soup, "article:section") or None
        # Also try extracting from URL parameter
        if not category:
            m = re.search(r"searchCategory=(\d+)", url)
            if m:
                category = f"category-{m.group(1)}"

        return {
            "title": title,
            "body": body,
            "published_at": published_at,
            "author": author,
            "category": category,
        }

    def get_section_urls(self) -> list[str]:
        """Return Science Times section page URLs."""
        return list(self.SECTION_URLS)

    def _is_article_url(self, url: str) -> bool:
        """Check if URL matches Science Times article pattern.

        Articles use: /nscvrg/view/menu/ID?searchCategory=X&nscvrgSn=Y
        """
        if "nscvrg/view" in url and "nscvrgSn=" in url:
            return True
        return super()._is_article_url(url)

    def _parse_korean_date(self, text: str) -> datetime | None:
        """Parse Science Times date formats.

        Handles:
            - "2026-02-25" (most common)
            - "2026.02.25 14:30"
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
            hour = int(m.group(4)) if m.group(4) else 0
            minute = int(m.group(5)) if m.group(5) else 0
            second = int(m.group(6)) if m.group(6) else 0
            try:
                kst = timezone(timedelta(hours=9))
                dt = datetime(year, month, day, hour, minute, second, tzinfo=kst)
                return dt.astimezone(timezone.utc)
            except (ValueError, OverflowError):
                pass

        return self.normalize_date(text)
