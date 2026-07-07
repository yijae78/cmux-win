"""iRobot News adapter -- Korean robotics industry news.

iRobot News (irobotnews.com) is a niche Korean news site focused on
robotics, automation, AI, and related industries. It uses a WordPress-based
platform with a standard post structure.

Key characteristics:
    - WordPress-based (RSS at /feed)
    - Niche robotics focus with low daily volume (~10/day)
    - HIGH bot blocking -- needs Tier 2+ escalation
    - Standard WordPress article URL patterns
    - Korean language with English technical terms mixed in

Reference:
    sources.yaml key: irobotnews
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
    r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\s*(?:(\d{1,2}):(\d{2})(?::(\d{2}))?)?"
)


class IrobotnewsAdapter(BaseSiteAdapter):
    """Adapter for iRobot News (irobotnews.com)."""

    # --- Site identity ---
    SITE_ID = "irobotnews"
    SITE_NAME = "iRobot News"
    SITE_URL = "https://www.irobotnews.com"
    LANGUAGE = "ko"
    REGION = "kr"
    GROUP = "D"

    # --- URL discovery ---
    RSS_URL = "https://www.irobotnews.com/feed"
    SITEMAP_URL = "/sitemap.xml"

    # --- Article extraction selectors ---
    # WordPress theme with standard classes
    TITLE_CSS = "h1.entry-title"
    TITLE_CSS_FALLBACK = "h1.post-title, h2.entry-title"
    # Body: WordPress content container
    BODY_CSS = "div.entry-content"
    BODY_CSS_FALLBACK = "div.post-content, article .content"
    # Date: time element or date span
    DATE_CSS = "time.entry-date, span.entry-date, span.posted-on time"
    # Author: WordPress author links
    AUTHOR_CSS = "span.author a, a.author-name, span.byline a"
    # Listing: article links
    ARTICLE_LINK_CSS = (
        "h2.entry-title a, h3.entry-title a, "
        "article a[href*='irobotnews.com']"
    )

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div.sharedaddy, div.jp-relatedposts, "
        "div.post-navigation, "
        "div.related-posts, div.yarpp-related, "
        "div.social-share, div.share-buttons, "
        "div.entry-footer, div.post-tags, "
        "div.comments-area, "
        "nav, aside, footer"
    )

    # --- Section URLs ---
    # iRobot News categories
    SECTION_URLS = [
        "https://www.irobotnews.com/",
        "https://www.irobotnews.com/category/robot/",
        "https://www.irobotnews.com/category/ai/",
        "https://www.irobotnews.com/category/drone/",
        "https://www.irobotnews.com/category/industry/",
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
        """Extract article fields from iRobot News HTML.

        iRobot News uses a standard WordPress theme with entry-title,
        entry-content, and metadata classes. Content often mixes Korean
        text with English robotics/AI technical terms.

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
            dt_attr = date_el.get("datetime", "")
            if dt_attr:
                published_at = self.normalize_date(dt_attr)
            if not published_at:
                date_text = date_el.get_text(strip=True)
                published_at = self._parse_korean_date(date_text)

        # Fallback: JSON-LD
        if not published_at:
            ld = self._extract_json_ld(soup)
            if ld.get("datePublished"):
                published_at = self.normalize_date(ld["datePublished"])

        # Fallback: meta tag
        if not published_at:
            meta_date = self._extract_meta_content(soup, "article:published_time")
            if meta_date:
                published_at = self.normalize_date(meta_date)

        # --- Author ---
        author = None
        author_el = soup.select_one(self.AUTHOR_CSS)
        if author_el:
            author_text = author_el.get_text(strip=True)
            # Clean author format: strip trailing " 기자" (reporter title)
            author = re.sub(r"\s+기자\s*$", "", author_text).strip()
            if not author:
                author = author_text

        # Fallback: JSON-LD author
        if not author:
            ld = self._extract_json_ld(soup)
            author_data = ld.get("author")
            if isinstance(author_data, dict):
                author = author_data.get("name")
            elif isinstance(author_data, str):
                author = author_data

        # --- Category ---
        category = None
        cat_el = soup.select_one(
            "span.cat-links a, a[rel='category tag'], "
            "span.category a"
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
        """Return iRobot News section page URLs."""
        return list(self.SECTION_URLS)

    def _is_article_url(self, url: str) -> bool:
        """Check if URL matches iRobot News article pattern.

        iRobot News articles use WordPress patterns:
        - /YYYY/MM/DD/slug/
        - /news/slug/
        - /?p=NNNNN
        """
        if re.search(r"/\d{4}/\d{2}/\d{2}/[a-z0-9-]+/?$", url):
            return True
        if re.search(r"/news/[a-z0-9-]+/?$", url):
            return True
        if "?p=" in url:
            return True
        return super()._is_article_url(url)

    def _parse_korean_date(self, text: str) -> datetime | None:
        """Parse Korean date formats used by iRobot News.

        Handles relative and absolute Korean dates, plus
        WordPress standard dates.
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
