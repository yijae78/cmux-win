"""Al Jazeera English (aljazeera.com) adapter -- Qatar-based English news.

Site #43, Group G (Europe/ME).
Language: English (en). Encoding: UTF-8.
Primary method: RSS (verified active, 25 items).
Rate limit: 5s. Bot-blocking: HIGH (blocks 8+ AI bots explicitly).
SSR content with Apollo GraphQL state available.

CRITICAL: Must NOT use AI-identifying User-Agents.
Blocked UAs: anthropic-ai, ChatGPT-User, ClaudeBot, GPTBot, etc.

Reference:
    Step 6 crawl-strategy-global.md, Section 43.
"""

from __future__ import annotations

from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter


class AlJazeeraAdapter(BaseSiteAdapter):
    """Adapter for Al Jazeera English (aljazeera.com)."""

    SITE_ID = "aljazeera"
    SITE_NAME = "Al Jazeera English"
    SITE_URL = "https://www.aljazeera.com"
    LANGUAGE = "en"
    REGION = "me"
    GROUP = "G"

    # --- URL discovery ---
    RSS_URL = "https://www.aljazeera.com/xml/rss/all.xml"
    SITEMAP_URL = "/sitemap.xml"

    # --- Selectors (verified via live fetch) ---
    TITLE_CSS = "h1"
    TITLE_CSS_FALLBACK = "meta[property='og:title']"
    BODY_CSS = "div.wysiwyg"  # Al Jazeera's article content class
    BODY_CSS_FALLBACK = "#main-content-area"
    DATE_CSS = ""  # Use Schema.org datePublished
    AUTHOR_CSS = "div.article-author__name, span[class*='author']"
    ARTICLE_LINK_CSS = (
        "a[href^='/news/'], a[href^='/features/'], "
        "a[href^='/opinions/'], a[href^='/economy/']"
    )

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, nav, aside, footer, "
        "div[class*='related-content'], div[class*='recommended'], "
        "div[class*='social-share'], div[class*='newsletter'], "
        "div[class*='ad-'], div[class*='video-player'], "
        "figure.article-featured-image"
    )

    SECTION_URLS = [
        "https://www.aljazeera.com/news/",
        "https://www.aljazeera.com/features/",
        "https://www.aljazeera.com/opinions/",
        "https://www.aljazeera.com/economy/",
        "https://www.aljazeera.com/sport/",
        "https://www.aljazeera.com/culture/",
    ]

    # --- Rate limiting ---
    RATE_LIMIT_SECONDS = 5.0
    MAX_REQUESTS_PER_HOUR = 720
    JITTER_SECONDS = 0.0

    # --- Anti-block (HIGH -- blocks AI bots) ---
    ANTI_BLOCK_TIER = 1
    UA_TIER = 2
    REQUIRES_PROXY = False
    BOT_BLOCK_LEVEL = "HIGH"

    CHARSET = "utf-8"

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article from Al Jazeera English HTML.

        Uses Schema.org JSON-LD for metadata, wysiwyg div for body.
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
        if not title:
            title = json_ld.get("headline", "")

        # Body
        body = ""
        body_el = soup.select_one(self.BODY_CSS)
        if not body_el:
            body_el = soup.select_one(self.BODY_CSS_FALLBACK)
        if body_el:
            body = self._clean_body_text(body_el)

        # Date: Schema.org datePublished (UTC)
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
        elif isinstance(author_data, list):
            names = [a.get("name", "") for a in author_data if isinstance(a, dict)]
            author = ", ".join(n for n in names if n) or None
        if not author:
            author_el = soup.select_one(self.AUTHOR_CSS)
            if author_el:
                author = author_el.get_text(strip=True)
        if not author:
            author = "Al Jazeera"  # Default when attributed to staff

        # Category from breadcrumb or URL
        category = None
        cat_el = soup.select_one("a.article-section-link")
        if cat_el:
            category = cat_el.get_text(strip=True)
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
