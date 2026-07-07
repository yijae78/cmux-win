"""Bild (bild.de) adapter -- Germany's largest tabloid (Axel Springer).

Site #39, Group G (Europe/ME).
Language: German (de). Encoding: UTF-8.
Primary method: RSS (dzbildplus=false filter for free articles).
Rate limit: 10s + jitter. Bot-blocking: HIGH.
Proxy: German residential REQUIRED.
Paywall: Soft-metered (BILDplus ~30% of content).

German special characters: Umlauts (ae/oe/ue), Eszett (ss) -- all UTF-8 native.

Reference:
    Step 6 crawl-strategy-global.md, Section 39.
"""

from __future__ import annotations

from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter
from src.crawling.adapters.multilingual._ml_utils import parse_german_date


class BildAdapter(BaseSiteAdapter):
    """Adapter for Bild (bild.de)."""

    SITE_ID = "bild"
    SITE_NAME = "Bild"
    SITE_URL = "https://www.bild.de"
    LANGUAGE = "de"
    REGION = "de"
    GROUP = "G"

    # --- URL discovery ---
    # dzbildplus=false filters out BILDplus paywall articles
    RSS_URL = (
        "https://www.bild.de/rssfeeds/vw-alles/"
        "vw-alles-26970986,dzbildplus=false,sort=1,"
        "teaserbildmob498=true,view=rss2.bild.xml"
    )
    RSS_URLS = [
        "https://www.bild.de/rssfeeds/rss-16738684,dzbildplus=false,sort=1,view=rss2.bild.xml",
        "https://www.bild.de/rssfeeds/vw-politik/vw-politik-26971178,dzbildplus=false,sort=1,view=rss2.bild.xml",
        "https://www.bild.de/rssfeeds/vw-wirtschaft/vw-wirtschaft-26972740,dzbildplus=false,sort=1,view=rss2.bild.xml",
    ]
    SITEMAP_URL = "/sitemap.xml"

    # --- Selectors ---
    TITLE_CSS = "h1.article-headline, h1[class*='headline']"
    TITLE_CSS_FALLBACK = "h1"
    BODY_CSS = "div.article-body, div[class*='article__body']"
    BODY_CSS_FALLBACK = "div.body, div[data-module='article-body']"
    DATE_CSS = "time[datetime]"
    AUTHOR_CSS = "span.author-info__name, span[class*='author']"
    ARTICLE_LINK_CSS = "a[class*='teaser-link']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, nav, aside, footer, "
        "div[class*='related'], div[class*='teaser-list'], "
        "div[class*='ad-container'], div[class*='social'], "
        "div[class*='newsletter'], div[class*='bildplus']"
    )

    SECTION_URLS = [
        "https://www.bild.de/politik/",
        "https://www.bild.de/wirtschaft/",
        "https://www.bild.de/sport/",
        "https://www.bild.de/unterhaltung/",
        "https://www.bild.de/digital/",
        "https://www.bild.de/ratgeber/",
    ]

    # --- Rate limiting ---
    RATE_LIMIT_SECONDS = 10.0
    MAX_REQUESTS_PER_HOUR = 240
    JITTER_SECONDS = 3.0

    # --- Anti-block (HIGH, DE proxy required) ---
    ANTI_BLOCK_TIER = 2
    UA_TIER = 3
    REQUIRES_PROXY = True
    PROXY_REGION = "de"
    BOT_BLOCK_LEVEL = "HIGH"

    PAYWALL_TYPE = "soft-metered"
    CHARSET = "utf-8"

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article from Bild HTML.

        Handles German date formats and BILDplus detection.
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")

        # Check for BILDplus paywall marker
        is_bildplus = bool(
            soup.select_one("svg.bildplus-icon")
            or soup.select_one("span.bildplus-badge")
            or soup.select_one("[data-bildplus='true']")
        )

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
        if not is_bildplus:
            body_el = soup.select_one(self.BODY_CSS)
            if not body_el:
                body_el = soup.select_one(self.BODY_CSS_FALLBACK)
            if body_el:
                body = self._clean_body_text(body_el)

        # Date: meta tag (ISO 8601) > German locale format
        published_at = None
        meta_date = self._extract_meta_content(soup, "article:published_time")
        if meta_date:
            published_at = self.normalize_date(meta_date)
        if not published_at:
            # JSON-LD datePublished
            json_ld = self._extract_json_ld(soup)
            date_str = json_ld.get("datePublished", "")
            if date_str:
                published_at = self.normalize_date(date_str)
        if not published_at:
            time_el = soup.select_one(self.DATE_CSS)
            if time_el:
                dt_attr = time_el.get("datetime", "")
                if dt_attr:
                    published_at = self.normalize_date(dt_attr)
                else:
                    published_at = parse_german_date(time_el.get_text(strip=True))

        # Author
        author = None
        author_el = soup.select_one(self.AUTHOR_CSS)
        if author_el:
            author = author_el.get_text(strip=True)
        if not author:
            author = self._extract_meta_content(soup, "author") or None

        # Category from URL
        category = self._extract_category_from_url(url)

        return {
            "title": title,
            "body": body,
            "published_at": published_at,
            "author": author,
            "category": category,
            "is_paywall_truncated": is_bildplus,
        }

    def get_section_urls(self) -> list[str]:
        return list(self.SECTION_URLS)

    def normalize_date(self, date_str: str) -> Any:
        """Parse ISO 8601 first, then German date formats."""
        result = super().normalize_date(date_str)
        if result:
            return result
        return parse_german_date(date_str)

    def _is_article_url(self, url: str) -> bool:
        """Bild articles have .bild.html extension or numeric article IDs."""
        return ".bild.html" in url or "/artikel/" in url
