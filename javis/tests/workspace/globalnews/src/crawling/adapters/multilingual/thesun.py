"""The Sun (thesun.co.uk) adapter -- UK tabloid.

Site #38, Group G (Europe/ME).
Language: English (en). Encoding: UTF-8.
Primary method: RSS.
Rate limit: 10s + jitter. Bot-blocking: HIGH.
Proxy: UK residential RECOMMENDED.

Reference:
    Step 6 crawl-strategy-global.md, Section 38.
"""

from __future__ import annotations

from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter


class TheSunAdapter(BaseSiteAdapter):
    """Adapter for The Sun (thesun.co.uk)."""

    SITE_ID = "thesun"
    SITE_NAME = "The Sun"
    SITE_URL = "https://www.thesun.co.uk"
    LANGUAGE = "en"
    REGION = "uk"
    GROUP = "G"

    # --- URL discovery ---
    RSS_URL = "https://www.thesun.co.uk/feed/"
    RSS_URLS = [
        "https://www.thesun.co.uk/feed/",
        "https://www.thesun.co.uk/news/feed/",
        "https://www.thesun.co.uk/money/feed/",
        "https://www.thesun.co.uk/tech/feed/",
        "https://www.thesun.co.uk/health/feed/",
        "https://www.thesun.co.uk/sport/feed/",
    ]
    SITEMAP_URL = "/sitemap.xml"

    # --- Selectors (verified structure) ---
    TITLE_CSS = "h1.article__headline"
    TITLE_CSS_FALLBACK = "h1"
    BODY_CSS = "div.article__content"
    BODY_CSS_FALLBACK = "div[class*='article-body'], div.article__body"
    DATE_CSS = "time[datetime]"
    AUTHOR_CSS = "span.article__author-name a"
    ARTICLE_LINK_CSS = "a.teaser-anchor__text"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, nav, aside, footer, "
        "div.related-stories, div.article__info-bar, "
        "div[class*='newsletter'], div[class*='advert'], "
        "div[class*='social-share'], div.breaking-news-banner"
    )

    SECTION_URLS = [
        "https://www.thesun.co.uk/news/",
        "https://www.thesun.co.uk/money/",
        "https://www.thesun.co.uk/tech/",
        "https://www.thesun.co.uk/health/",
        "https://www.thesun.co.uk/sport/",
        "https://www.thesun.co.uk/tvandshowbiz/",
    ]

    # --- Rate limiting ---
    RATE_LIMIT_SECONDS = 10.0
    MAX_REQUESTS_PER_HOUR = 240
    JITTER_SECONDS = 3.0

    # --- Anti-block (HIGH, UK proxy recommended) ---
    ANTI_BLOCK_TIER = 2
    UA_TIER = 3
    REQUIRES_PROXY = False
    PROXY_REGION = "uk"
    BOT_BLOCK_LEVEL = "HIGH"

    CHARSET = "utf-8"

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article from The Sun HTML."""
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

        # Date: prefer meta tag, then time element
        published_at = None
        meta_date = self._extract_meta_content(soup, "article:published_time")
        if meta_date:
            published_at = self.normalize_date(meta_date)
        if not published_at:
            time_el = soup.select_one(self.DATE_CSS)
            if time_el and time_el.get("datetime"):
                published_at = self.normalize_date(time_el["datetime"])

        # Author
        author = None
        author_el = soup.select_one(self.AUTHOR_CSS)
        if not author_el:
            author_el = soup.select_one("span.article__author-name")
        if author_el:
            author = author_el.get_text(strip=True)
        if not author:
            author = self._extract_meta_content(soup, "author") or None

        # Category from breadcrumb or URL
        category = None
        breadcrumb = soup.select("a.breadcrumb__link")
        if breadcrumb:
            category = breadcrumb[-1].get_text(strip=True)
        if not category:
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
