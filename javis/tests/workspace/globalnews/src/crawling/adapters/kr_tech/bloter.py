"""Bloter adapter -- Korean IT/tech news with Playwright requirement.

Bloter (bloter.net) is a Korean tech news site focused on IT industry,
startups, and tech culture. It uses a modern web stack that requires
JavaScript rendering (Playwright).

Key characteristics:
    - Modern SPA-like rendering (rendering_required = True)
    - WordPress RSS feed at /feed as fallback
    - HIGH bot blocking level -- needs Tier 3+ escalation
    - Relatively low volume (~20 articles/day)
    - Clean HTML when rendered

Reference:
    sources.yaml key: bloter
    Step 6: Group D, Playwright-first strategy
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


class BloterAdapter(BaseSiteAdapter):
    """Adapter for Bloter (bloter.net)."""

    # --- Site identity ---
    SITE_ID = "bloter"
    SITE_NAME = "Bloter"
    SITE_URL = "https://www.bloter.net"
    LANGUAGE = "ko"
    REGION = "kr"
    GROUP = "D"

    # --- URL discovery ---
    RSS_URL = "https://www.bloter.net/feed"
    SITEMAP_URL = "/sitemap.xml"

    # --- Article extraction selectors ---
    # Bloter uses a custom theme with these CSS patterns
    TITLE_CSS = "h1.article-head__title"
    TITLE_CSS_FALLBACK = "h1.entry-title, h1.post-title"
    # Body container
    BODY_CSS = "div.article-body__content"
    BODY_CSS_FALLBACK = "div.entry-content, article .post-content"
    # Date
    DATE_CSS = "time.article-head__date, span.article-head__date"
    # Author
    AUTHOR_CSS = "span.article-head__author a, a.article-head__author"
    # Article links on listing pages
    ARTICLE_LINK_CSS = "a.article-item__link, h2.article-item__title a, a[href*='/news/']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div.ad-container, div.advertisement, "
        "div.article-body__related, div.related-articles, "
        "div.article-body__social, div.social-share, "
        "div.article-body__tag, "
        "div.comments, "
        "nav, aside, footer"
    )

    # --- Section URLs ---
    SECTION_URLS = [
        "https://www.bloter.net/news",
        "https://www.bloter.net/news/tech",
        "https://www.bloter.net/news/business",
        "https://www.bloter.net/news/policy",
        "https://www.bloter.net/news/science",
        "https://www.bloter.net/news/media",
    ]

    PAGINATION_TYPE = "page_number"
    PAGINATION_PARAM = "page"
    MAX_PAGES = 5

    # --- Rate limiting (from sources.yaml) ---
    RATE_LIMIT_SECONDS = 10.0
    MAX_REQUESTS_PER_HOUR = 240
    JITTER_SECONDS = 3.0

    # --- Anti-block ---
    ANTI_BLOCK_TIER = 3
    UA_TIER = 3
    REQUIRES_PROXY = True
    PROXY_REGION = "kr"
    BOT_BLOCK_LEVEL = "HIGH"

    # --- Extraction ---
    PAYWALL_TYPE = "none"
    CHARSET = "utf-8"
    RENDERING_REQUIRED = True

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from Bloter HTML.

        Bloter's article pages use a custom theme with article-head__ and
        article-body__ prefixed CSS classes. Rendering may be required for
        full content, but the adapter works on the rendered HTML.

        Args:
            html: Raw (or rendered) HTML of the article page.
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
            dt_attr = date_el.get("datetime", "")
            if dt_attr:
                published_at = self.normalize_date(dt_attr)
            if not published_at:
                date_text = date_el.get_text(strip=True)
                published_at = self._parse_korean_date(date_text)

        # Fallback: meta tags
        if not published_at:
            meta_date = self._extract_meta_content(soup, "article:published_time")
            if meta_date:
                published_at = self.normalize_date(meta_date)

        # Fallback: JSON-LD
        if not published_at:
            ld = self._extract_json_ld(soup)
            if ld.get("datePublished"):
                published_at = self.normalize_date(ld["datePublished"])

        # --- Author ---
        author = None
        author_el = soup.select_one(self.AUTHOR_CSS)
        if author_el:
            author = author_el.get_text(strip=True)
        if not author:
            # Bloter sometimes puts author in meta
            author = self._extract_meta_content(soup, "article:author") or None

        # --- Category ---
        category = None
        cat_el = soup.select_one(
            "span.article-head__category, a.article-head__category, "
            "span.cat-links a"
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
        """Return Bloter section page URLs."""
        return list(self.SECTION_URLS)

    def _is_article_url(self, url: str) -> bool:
        """Check if URL matches Bloter article pattern.

        Bloter articles use: /news/SLUG or /newsDetail/SLUG patterns.
        """
        if re.search(r"/news/[a-zA-Z0-9-]+$", url):
            return True
        if "/newsDetail/" in url:
            return True
        return super()._is_article_url(url)

    def _parse_korean_date(self, text: str) -> datetime | None:
        """Parse Korean date formats.

        Handles relative dates ("3시간 전") and absolute Korean dates.
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
                kst = timezone(timedelta(hours=9))
                dt = datetime(year, month, day, hour, minute, second, tzinfo=kst)
                return dt.astimezone(timezone.utc)
            except (ValueError, OverflowError):
                pass

        return self.normalize_date(text)
