"""Taiwan News (taiwannews.com.tw) adapter -- Bilingual English/Chinese news.

Site #35, Group F (Asia-Pacific).
Language: English (en). Encoding: UTF-8.
Primary method: Sitemap (3 sitemaps: main, en, zh).
Rate limit: 2s. Bot-blocking: LOW.
Next.js SSR with microdata (itemProp="articleBody").

Reference:
    Step 6 crawl-strategy-asia.md, Section 4.4.
"""

from __future__ import annotations

from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter


class TaiwanNewsAdapter(BaseSiteAdapter):
    """Adapter for Taiwan News (taiwannews.com.tw)."""

    SITE_ID = "taiwannews"
    SITE_NAME = "Taiwan News"
    SITE_URL = "https://www.taiwannews.com.tw"
    LANGUAGE = "en"
    REGION = "tw"
    GROUP = "F"

    # --- URL discovery ---
    SITEMAP_URL = "https://www.taiwannews.com.tw/sitemap_en.xml"

    # --- Selectors (verified via live probe) ---
    TITLE_CSS = "h1.text-head-semibold"
    TITLE_CSS_FALLBACK = "h1"
    BODY_CSS = "div[itemProp='articleBody']"
    BODY_CSS_FALLBACK = "div.article-content"
    DATE_CSS = "meta[property='article:published_time']"
    AUTHOR_CSS = "h3"  # Author name in h3 within author bio section
    ARTICLE_LINK_CSS = "a[href*='/news/']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, nav, aside, footer, "
        "div[id*='gpt-ad'], div[class*='related'], "
        "div.most-read, div[class*='ad']"
    )

    SECTION_URLS = [
        "https://www.taiwannews.com.tw/category/Politics",
        "https://www.taiwannews.com.tw/category/Business",
        "https://www.taiwannews.com.tw/category/Society",
        "https://www.taiwannews.com.tw/category/World",
        "https://www.taiwannews.com.tw/category/Sports",
        "https://www.taiwannews.com.tw/category/Culture",
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
        """Extract article from Taiwan News HTML."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")

        # Title (verified selector)
        title = ""
        title_el = soup.select_one(self.TITLE_CSS)
        if not title_el:
            title_el = soup.select_one(self.TITLE_CSS_FALLBACK)
        if title_el:
            title = title_el.get_text(strip=True)
        if not title:
            title = self._extract_meta_content(soup, "og:title")

        # Body using microdata selector (most stable for Next.js)
        body = ""
        body_el = soup.select_one(self.BODY_CSS)
        if not body_el:
            body_el = soup.select_one(self.BODY_CSS_FALLBACK)
        if body_el:
            body = self._clean_body_text(body_el)

        # Date from meta tag
        published_at = None
        meta_date = self._extract_meta_content(soup, "article:published_time")
        if meta_date:
            published_at = self.normalize_date(meta_date)

        # Author from h3 in author bio section
        author = None
        # Look for author in the flex container near article metadata
        author_section = soup.select_one("div.flex.gap-3 h3")
        if author_section:
            author = author_section.get_text(strip=True)
        if not author:
            author = self._extract_meta_content(soup, "author") or None

        # Category from URL or breadcrumb
        category = None
        breadcrumb = soup.select("nav a")
        if len(breadcrumb) > 1:
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

    def _is_article_url(self, url: str) -> bool:
        """Taiwan News articles have URL pattern /news/{numeric_id}."""
        from urllib.parse import urlparse
        import re
        parsed = urlparse(url)
        return bool(re.search(r"/news/\d+", parsed.path))
