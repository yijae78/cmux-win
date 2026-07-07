"""The Moscow Times (themoscowtimes.com) adapter -- English-language Russian news.

Site #41, Group G (Europe/ME).
Language: English (en). Encoding: UTF-8.
Primary method: RSS (4 category feeds).
Rate limit: 2s. Bot-blocking: LOW.
Paywall: None (freemium/donation model).

Easiest site in Group G. Schema.org structured data available.

Reference:
    Step 6 crawl-strategy-global.md, Section 41.
"""

from __future__ import annotations

import re
from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter


class MoscowTimesAdapter(BaseSiteAdapter):
    """Adapter for The Moscow Times (themoscowtimes.com)."""

    SITE_ID = "themoscowtimes"
    SITE_NAME = "The Moscow Times"
    SITE_URL = "https://www.themoscowtimes.com"
    LANGUAGE = "en"
    REGION = "ru"
    GROUP = "G"

    # --- URL discovery ---
    RSS_URL = "https://www.themoscowtimes.com/rss/news"
    RSS_URLS = [
        "https://www.themoscowtimes.com/rss/news",
        "https://www.themoscowtimes.com/rss/opinion",
        "https://www.themoscowtimes.com/rss/city",
        "https://www.themoscowtimes.com/rss/meanwhile",
    ]
    SITEMAP_URL = "https://static.themoscowtimes.com/sitemap/sitemap.xml"

    # --- Selectors (verified via live fetch) ---
    TITLE_CSS = "h1"
    TITLE_CSS_FALLBACK = "meta[property='og:title']"
    BODY_CSS = "div.article__content, div.article-body"
    BODY_CSS_FALLBACK = "article"
    DATE_CSS = ""  # Use Schema.org datePublished
    AUTHOR_CSS = "span.article__author, a[class*='author']"
    ARTICLE_LINK_CSS = "a[href*='/20']"  # URL pattern: /2026/02/25/article-slug

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, nav, aside, footer, "
        "div.sharing-buttons, div[class*='related'], "
        "div[class*='read-more'], div[class*='social'], "
        "div[class*='newsletter'], div[class*='podcast'], "
        "div.tags"
    )

    SECTION_URLS = [
        "https://www.themoscowtimes.com/news",
        "https://www.themoscowtimes.com/opinion",
        "https://www.themoscowtimes.com/business",
        "https://www.themoscowtimes.com/ukraine",
        "https://www.themoscowtimes.com/regions",
    ]

    # --- Rate limiting ---
    RATE_LIMIT_SECONDS = 2.0
    MAX_REQUESTS_PER_HOUR = 1800
    JITTER_SECONDS = 0.0

    # --- Anti-block (LOW) ---
    ANTI_BLOCK_TIER = 1
    UA_TIER = 1
    REQUIRES_PROXY = False
    BOT_BLOCK_LEVEL = "LOW"

    CHARSET = "utf-8"

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article from Moscow Times HTML.

        Uses Schema.org structured data for metadata when available.
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")

        # JSON-LD for metadata
        json_ld = self._extract_json_ld(soup)

        # Title
        title = ""
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

        # Date: Schema.org > meta
        published_at = None
        date_str = json_ld.get("datePublished", "")
        if date_str:
            published_at = self.normalize_date(date_str)
        if not published_at:
            meta_date = self._extract_meta_content(soup, "article:published_time")
            if meta_date:
                published_at = self.normalize_date(meta_date)

        # Author: Schema.org > CSS
        author = None
        author_data = json_ld.get("author")
        if isinstance(author_data, dict):
            author = author_data.get("name")
        elif isinstance(author_data, str):
            author = author_data
        if not author:
            author_el = soup.select_one(self.AUTHOR_CSS)
            if author_el:
                author = author_el.get_text(strip=True)
        if not author:
            author = "The Moscow Times"  # Default attribution

        # Category from breadcrumb Schema.org or tags
        category = None
        breadcrumb = soup.select("a.breadcrumb__link")
        if len(breadcrumb) > 1:
            category = breadcrumb[-1].get_text(strip=True)
        if not category:
            tags = soup.select("a.tag")
            if tags:
                category = tags[0].get_text(strip=True)

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
