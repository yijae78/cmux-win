"""The Hindu (thehindu.com) adapter -- India's leading English daily.

Site #37, Group F (Asia-Pacific).
Language: English (en). Encoding: UTF-8.
Primary method: RSS.
Rate limit: 10s + jitter. Bot-blocking: HIGH (Cloudflare).
Paywall: Soft-metered (10 free articles/month per IP).

NOTE: Selectors are pattern-based (site blocked by Cloudflare during probe).
Runtime verification via Cloudflare-bypassing access required.

Reference:
    Step 6 crawl-strategy-asia.md, Section 4.6.
"""

from __future__ import annotations

from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter


class TheHinduAdapter(BaseSiteAdapter):
    """Adapter for The Hindu (thehindu.com)."""

    SITE_ID = "thehindu"
    SITE_NAME = "The Hindu"
    SITE_URL = "https://www.thehindu.com"
    LANGUAGE = "en"
    REGION = "in"
    GROUP = "F"

    # --- URL discovery ---
    RSS_URL = "https://www.thehindu.com/feeder/default.rss"
    RSS_URLS = [
        "https://www.thehindu.com/feeder/default.rss",
        "https://www.thehindu.com/news/national/feeder/default.rss",
        "https://www.thehindu.com/news/international/feeder/default.rss",
        "https://www.thehindu.com/business/feeder/default.rss",
        "https://www.thehindu.com/opinion/feeder/default.rss",
        "https://www.thehindu.com/sport/feeder/default.rss",
        "https://www.thehindu.com/sci-tech/feeder/default.rss",
    ]
    SITEMAP_URL = "/sitemap.xml"

    # --- Selectors (pattern-based -- require Cloudflare bypass verification) ---
    TITLE_CSS = "h1.title"
    TITLE_CSS_FALLBACK = "h1"
    BODY_CSS = "div[itemprop='articleBody']"
    BODY_CSS_FALLBACK = "div.articlebodycontent"
    DATE_CSS = "time[datetime]"
    AUTHOR_CSS = "[itemprop='author']"
    ARTICLE_LINK_CSS = "a[href*='/article']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, nav, aside, footer, "
        "div.also-read, div.related-stories, "
        "div[class*='ad'], div[class*='share'], "
        "div[class*='subscribe'], div[class*='newsletter']"
    )

    SECTION_URLS = [
        "https://www.thehindu.com/news/national/",
        "https://www.thehindu.com/news/international/",
        "https://www.thehindu.com/business/",
        "https://www.thehindu.com/opinion/",
        "https://www.thehindu.com/sport/",
        "https://www.thehindu.com/sci-tech/",
        "https://www.thehindu.com/entertainment/",
    ]

    # --- Rate limiting ---
    RATE_LIMIT_SECONDS = 10.0
    MAX_REQUESTS_PER_HOUR = 240
    JITTER_SECONDS = 3.0

    # --- Anti-block (HIGH, Cloudflare) ---
    ANTI_BLOCK_TIER = 1
    UA_TIER = 3
    REQUIRES_PROXY = False
    BOT_BLOCK_LEVEL = "HIGH"

    PAYWALL_TYPE = "soft-metered"
    CHARSET = "utf-8"

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article from The Hindu HTML."""
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

        # Date
        published_at = None
        time_el = soup.select_one(self.DATE_CSS)
        if time_el and time_el.get("datetime"):
            published_at = self.normalize_date(time_el["datetime"])
        if not published_at:
            meta_date = self._extract_meta_content(soup, "article:published_time")
            if meta_date:
                published_at = self.normalize_date(meta_date)

        # Author
        author = None
        author_el = soup.select_one(self.AUTHOR_CSS)
        if author_el:
            author = author_el.get_text(strip=True)
        if not author:
            author = self._extract_meta_content(soup, "author") or None

        # Category from URL path: /{section}/{subsection}/article{id}.ece
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

    def _extract_category_from_url(self, url: str, segment_index: int = 1) -> str | None:
        """Extract category from The Hindu URL: /news/national/article12345.ece"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        parts = [p for p in parsed.path.split("/") if p]
        # Skip 'news' and find actual category
        if len(parts) >= 2:
            if parts[0] == "news" and len(parts) >= 3:
                return parts[1]  # e.g., "national", "international"
            return parts[0]  # e.g., "business", "sport"
        return None

    def _is_article_url(self, url: str) -> bool:
        """The Hindu articles have .ece extension."""
        return ".ece" in url or "/article" in url
