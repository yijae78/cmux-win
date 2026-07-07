"""Arab News (arabnews.com) adapter -- Saudi/ME English-language news.

Site #42, Group G (Europe/ME).
Language: English (en). Encoding: UTF-8.
Primary method: Sitemap (RSS returns 403).
Rate limit: 10s MANDATORY crawl-delay (robots.txt).
Proxy: ME residential RECOMMENDED.
CMS: Drupal.

RTL note: English edition only -- no RTL handling required for primary scope.
Strip bidi marks from mixed English/Arabic content in author names or tags.

Reference:
    Step 6 crawl-strategy-global.md, Section 42.
"""

from __future__ import annotations

from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter
from src.crawling.adapters.multilingual._ml_utils import strip_rtl_marks


class ArabNewsAdapter(BaseSiteAdapter):
    """Adapter for Arab News (arabnews.com)."""

    SITE_ID = "arabnews"
    SITE_NAME = "Arab News"
    SITE_URL = "https://www.arabnews.com"
    LANGUAGE = "en"
    REGION = "me"
    GROUP = "G"

    # --- URL discovery ---
    # RSS returns 403 (confirmed Step 1), so sitemap is primary
    SITEMAP_URL = "/sitemap.xml"

    # --- Selectors (Drupal CMS structure) ---
    TITLE_CSS = "h1.page-title, h1.article-title"
    TITLE_CSS_FALLBACK = "h1"
    BODY_CSS = "div.field--name-body, div.article-body"
    BODY_CSS_FALLBACK = "div.node__content, article.node"
    DATE_CSS = "time[datetime]"
    AUTHOR_CSS = "span.field--name-field-author, a[class*='author']"
    ARTICLE_LINK_CSS = "h2 a, h3 a, a.article-title"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, nav, aside, footer, "
        "div.field--name-field-related, div[class*='social-share'], "
        "div[class*='ad-'], div.sidebar, "
        "div[class*='newsletter'], div.comment-section"
    )

    SECTION_URLS = [
        "https://www.arabnews.com/saudi-arabia",
        "https://www.arabnews.com/middle-east",
        "https://www.arabnews.com/world",
        "https://www.arabnews.com/business",
        "https://www.arabnews.com/sport",
        "https://www.arabnews.com/lifestyle",
    ]

    # --- Rate limiting (10s MANDATORY) ---
    RATE_LIMIT_SECONDS = 10.0
    MAX_REQUESTS_PER_HOUR = 360
    JITTER_SECONDS = 0.0

    # --- Anti-block ---
    ANTI_BLOCK_TIER = 1
    UA_TIER = 2
    REQUIRES_PROXY = False
    PROXY_REGION = "me"
    BOT_BLOCK_LEVEL = "MEDIUM"

    CHARSET = "utf-8"

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article from Arab News (Drupal) HTML.

        Strips RTL marks from extracted text fields.
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")

        # Title
        title = ""
        title_el = soup.select_one(self.TITLE_CSS)
        if not title_el:
            title_el = soup.select_one(self.TITLE_CSS_FALLBACK)
        if title_el:
            title = strip_rtl_marks(title_el.get_text(strip=True))
        if not title:
            title = strip_rtl_marks(self._extract_meta_content(soup, "og:title"))

        # Body
        body = ""
        body_el = soup.select_one(self.BODY_CSS)
        if not body_el:
            body_el = soup.select_one(self.BODY_CSS_FALLBACK)
        if body_el:
            body = strip_rtl_marks(self._clean_body_text(body_el))

        # Date
        published_at = None
        meta_date = self._extract_meta_content(soup, "article:published_time")
        if meta_date:
            published_at = self.normalize_date(meta_date)
        if not published_at:
            json_ld = self._extract_json_ld(soup)
            date_str = json_ld.get("datePublished", "")
            if date_str:
                published_at = self.normalize_date(date_str)
        if not published_at:
            time_el = soup.select_one(self.DATE_CSS)
            if time_el and time_el.get("datetime"):
                published_at = self.normalize_date(time_el["datetime"])

        # Author (strip bidi marks from mixed content)
        author = None
        author_el = soup.select_one(self.AUTHOR_CSS)
        if author_el:
            author = strip_rtl_marks(author_el.get_text(strip=True))
        if not author:
            author_meta = self._extract_meta_content(soup, "author")
            if author_meta:
                author = strip_rtl_marks(author_meta)

        # Category from Drupal field or URL
        category = None
        cat_el = soup.select_one("div.field--name-field-section a")
        if cat_el:
            category = cat_el.get_text(strip=True)
        if not category:
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
