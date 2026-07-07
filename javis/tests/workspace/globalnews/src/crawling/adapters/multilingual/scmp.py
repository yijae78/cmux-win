"""South China Morning Post (scmp.com) adapter -- Hong Kong English-language daily.

Site #34, Group F (Asia-Pacific).
Language: English (en). Encoding: UTF-8.
Primary method: RSS (80+ category feeds).
Rate limit: 10s MANDATORY crawl-delay (robots.txt).
Paywall: Soft-metered (Alibaba-owned, generous free quota).

Key strategy: JSON-LD structured data as primary metadata source.
CSS-in-JS classes are unstable (Emotion-generated hashes); prefer tag/semantic selectors.

Reference:
    Step 6 crawl-strategy-asia.md, Section 4.3.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse, urlencode, parse_qs

from src.crawling.adapters.base_adapter import BaseSiteAdapter


class SCMPAdapter(BaseSiteAdapter):
    """Adapter for South China Morning Post (scmp.com)."""

    SITE_ID = "scmp"
    SITE_NAME = "South China Morning Post"
    SITE_URL = "https://www.scmp.com"
    LANGUAGE = "en"
    REGION = "cn"
    GROUP = "F"

    # --- URL discovery ---
    RSS_URL = "https://www.scmp.com/rss/91/feed"
    RSS_URLS = [
        "https://www.scmp.com/rss/91/feed",   # News general
        "https://www.scmp.com/rss/2/feed",    # Hong Kong
        "https://www.scmp.com/rss/4/feed",    # China
        "https://www.scmp.com/rss/3/feed",    # Asia
        "https://www.scmp.com/rss/5/feed",    # World
        "https://www.scmp.com/rss/92/feed",   # Business
        "https://www.scmp.com/rss/36/feed",   # Tech
    ]

    # --- Selectors (prefer tag-based, NOT CSS-in-JS hash classes) ---
    TITLE_CSS = "h1"
    TITLE_CSS_FALLBACK = "meta[property='og:title']"
    BODY_CSS = "[itemProp='articleBody']"
    BODY_CSS_FALLBACK = "article"
    DATE_CSS = "time[datetime]"
    AUTHOR_CSS = ""  # Use JSON-LD
    ARTICLE_LINK_CSS = "a[href*='/article/']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, nav, aside, footer, "
        "div[class*='ad'], div[data-qa*='ad'], "
        "div[class*='related'], div[class*='carousel'], "
        "div[class*='paywall'], div[class*='speech']"
    )

    SECTION_URLS = [
        "https://www.scmp.com/news",
        "https://www.scmp.com/news/hong-kong",
        "https://www.scmp.com/news/china",
        "https://www.scmp.com/news/asia",
        "https://www.scmp.com/news/world",
        "https://www.scmp.com/business",
        "https://www.scmp.com/tech",
    ]

    # --- Rate limiting (10s MANDATORY) ---
    RATE_LIMIT_SECONDS = 10.0
    MAX_REQUESTS_PER_HOUR = 360
    JITTER_SECONDS = 0.0

    # --- Anti-block ---
    ANTI_BLOCK_TIER = 1
    UA_TIER = 2
    REQUIRES_PROXY = False
    BOT_BLOCK_LEVEL = "MEDIUM"

    PAYWALL_TYPE = "soft-metered"
    CHARSET = "utf-8"

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article from SCMP HTML.

        Primary strategy: JSON-LD for metadata, semantic selectors for body.
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")

        # JSON-LD is the most reliable source for SCMP
        json_ld = self._extract_json_ld(soup)

        # Title: JSON-LD > h1 > og:title
        title = json_ld.get("headline", "")
        if not title:
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

        # Date: JSON-LD datePublished > meta > time element
        published_at = None
        date_str = json_ld.get("datePublished", "")
        if date_str:
            published_at = self.normalize_date(date_str)
        if not published_at:
            meta_date = self._extract_meta_content(soup, "article:published_time")
            if meta_date:
                published_at = self.normalize_date(meta_date)
        if not published_at:
            time_el = soup.select_one(self.DATE_CSS)
            if time_el and time_el.get("datetime"):
                published_at = self.normalize_date(time_el["datetime"])

        # Author: JSON-LD > meta
        author = None
        author_data = json_ld.get("author")
        if isinstance(author_data, dict):
            author = author_data.get("name")
        elif isinstance(author_data, list):
            names = [a.get("name", "") for a in author_data if isinstance(a, dict)]
            author = ", ".join(n for n in names if n) or None
        elif isinstance(author_data, str):
            author = author_data
        if not author:
            author = self._extract_meta_content(soup, "author") or None

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

    def get_article_links_from_page(self, html: str) -> list[str]:
        """Extract article links, stripping UTM parameters."""
        links = super().get_article_links_from_page(html)
        return [self._strip_utm(u) for u in links]

    @staticmethod
    def _strip_utm(url: str) -> str:
        """Remove utm_source=rss_feed and similar tracking params."""
        parsed = urlparse(url)
        if not parsed.query:
            return url
        params = parse_qs(parsed.query)
        clean_params = {k: v for k, v in params.items() if not k.startswith("utm_")}
        if clean_params:
            return parsed._replace(query=urlencode(clean_params, doseq=True)).geturl()
        return parsed._replace(query="").geturl()

    def _extract_category_from_url(self, url: str, segment_index: int = 1) -> str | None:
        """Extract category from SCMP URL: /news/china/science/article/..."""
        parsed = urlparse(url)
        parts = [p for p in parsed.path.split("/") if p]
        # Skip 'article' and numeric id
        category_parts = []
        for p in parts:
            if p in ("article",) or p.isdigit():
                break
            category_parts.append(p)
        if category_parts:
            return "/".join(category_parts)
        return None
