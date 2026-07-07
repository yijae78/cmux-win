"""38 North adapter -- English-language North Korea analysis.

38 North (38north.org) is a program of the Stimson Center that provides
informed analysis of North Korea. It is an English-language site despite
being classified in the Korea region group.

Key characteristics:
    - WordPress-based site with clean semantic HTML
    - English-language content (LANGUAGE = "en")
    - RSS feed at /feed (WordPress default)
    - Low daily article volume (~5/day)
    - Categories: Domestic Affairs, Economy, Foreign Affairs, Military, etc.
    - LOW bot blocking, no proxy required

Reference:
    sources.yaml key: 38north
    Step 6: Group D, RSS-first strategy
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter

import logging

logger = logging.getLogger(__name__)


class North38Adapter(BaseSiteAdapter):
    """Adapter for 38 North (38north.org)."""

    # --- Site identity ---
    SITE_ID = "38north"
    SITE_NAME = "38 North"
    SITE_URL = "https://www.38north.org"
    LANGUAGE = "en"  # English-language site despite Korea region
    REGION = "kr"
    GROUP = "D"

    # --- URL discovery ---
    RSS_URL = "https://www.38north.org/feed"
    SITEMAP_URL = "/sitemap_index.xml"

    # --- Article extraction selectors ---
    # WordPress article structure with semantic HTML5
    TITLE_CSS = "h1.entry-title"
    TITLE_CSS_FALLBACK = "h1.post-title"
    # Body: div.entry-content (standard WordPress)
    BODY_CSS = "div.entry-content"
    BODY_CSS_FALLBACK = "article .post-content"
    # Date: time.entry-date or published date in metadata
    DATE_CSS = "time.entry-date, time.published"
    # Author: span.author a, or byline
    AUTHOR_CSS = "span.author a, .byline a, a[rel='author']"
    # Listing: article links in WordPress post format
    ARTICLE_LINK_CSS = "article a[href], h2.entry-title a, h3 a[href*='38north.org']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div.sharedaddy, div.jp-relatedposts, "
        "div.post-navigation, div.author-bio, "
        "div.related-posts, div.newsletter-signup, "
        "div.social-share, div.entry-footer, "
        "nav, aside, footer"
    )

    # --- Section URLs ---
    # 38 North organizes content by topic categories
    SECTION_URLS = [
        "https://www.38north.org/",
        "https://www.38north.org/category/domestic-affairs/",
        "https://www.38north.org/category/economy/",
        "https://www.38north.org/category/foreign-affairs/",
        "https://www.38north.org/category/military/",
        "https://www.38north.org/category/nuclear/",
        "https://www.38north.org/category/satellite-imagery/",
        "https://www.38north.org/category/media-analysis/",
    ]

    PAGINATION_TYPE = "page_number"
    PAGINATION_PARAM = "page"
    MAX_PAGES = 5

    # --- Rate limiting (from sources.yaml) ---
    RATE_LIMIT_SECONDS = 2.0
    MAX_REQUESTS_PER_HOUR = 1800
    JITTER_SECONDS = 0.0

    # --- Anti-block ---
    ANTI_BLOCK_TIER = 1
    UA_TIER = 1
    REQUIRES_PROXY = False
    PROXY_REGION = ""
    BOT_BLOCK_LEVEL = "LOW"

    # --- Extraction ---
    PAYWALL_TYPE = "none"
    CHARSET = "utf-8"
    RENDERING_REQUIRED = False

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from 38 North HTML.

        38 North uses standard WordPress markup with clean semantic HTML.
        Articles typically have clear entry-title, entry-content, and
        author metadata.

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
        # Try time element with datetime attribute first
        date_el = soup.select_one(self.DATE_CSS)
        if date_el:
            dt_attr = date_el.get("datetime", "")
            if dt_attr:
                published_at = self.normalize_date(dt_attr)
            if not published_at:
                published_at = self.normalize_date(date_el.get_text(strip=True))

        # Fallback to JSON-LD
        if not published_at:
            ld = self._extract_json_ld(soup)
            if ld.get("datePublished"):
                published_at = self.normalize_date(ld["datePublished"])

        # Fallback to meta tag
        if not published_at:
            meta_date = self._extract_meta_content(soup, "article:published_time")
            if meta_date:
                published_at = self.normalize_date(meta_date)

        # --- Author ---
        author = None
        author_el = soup.select_one(self.AUTHOR_CSS)
        if author_el:
            author = author_el.get_text(strip=True)

        # Fallback to JSON-LD author
        if not author:
            ld = self._extract_json_ld(soup)
            author_data = ld.get("author")
            if isinstance(author_data, dict):
                author = author_data.get("name")
            elif isinstance(author_data, str):
                author = author_data
            elif isinstance(author_data, list) and author_data:
                names = []
                for a in author_data:
                    if isinstance(a, dict):
                        names.append(a.get("name", ""))
                    elif isinstance(a, str):
                        names.append(a)
                author = ", ".join(n for n in names if n)

        # Fallback to dc:creator meta tag
        if not author:
            author = self._extract_meta_content(soup, "dc.creator") or None

        # --- Category ---
        category = None
        # 38 North uses category tags in post metadata
        cat_el = soup.select_one("span.cat-links a, a[rel='category tag']")
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
        """Return 38 North section page URLs."""
        return list(self.SECTION_URLS)

    def _is_article_url(self, url: str) -> bool:
        """Check if URL matches 38 North article pattern.

        38 North articles use: /YYYY/MM/slug/ pattern (WordPress default).
        """
        import re as _re

        if _re.search(r"/\d{4}/\d{2}/[a-z0-9-]+/?$", url):
            return True
        return super()._is_article_url(url)
