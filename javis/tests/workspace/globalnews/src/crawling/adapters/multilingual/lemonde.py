"""Le Monde (lemonde.fr/en/) adapter -- French newspaper, English edition.

Site #40, Group G (Europe/ME).
Language: English (en) for the /en/ edition. French for main site.
Encoding: UTF-8.
Primary method: RSS (metadata extraction only).
Rate limit: 10s + jitter. Bot-blocking: HIGH.
Paywall: HARD (Le Monde Abonne subscription required for body).
Strategy: Title + lead paragraph only (PRD dual-pass analysis).

Reference:
    Step 6 crawl-strategy-global.md, Section 40.
"""

from __future__ import annotations

from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter
from src.crawling.adapters.multilingual._ml_utils import parse_french_date


class LeMondeAdapter(BaseSiteAdapter):
    """Adapter for Le Monde English edition (lemonde.fr/en/)."""

    SITE_ID = "lemonde"
    SITE_NAME = "Le Monde"
    SITE_URL = "https://www.lemonde.fr"
    LANGUAGE = "en"  # English edition at /en/
    REGION = "fr"
    GROUP = "G"

    # --- URL discovery ---
    # English edition RSS
    RSS_URL = "https://www.lemonde.fr/en/rss/une.xml"
    RSS_URLS = [
        "https://www.lemonde.fr/en/rss/une.xml",
        "https://www.lemonde.fr/rss/une.xml",
        "https://www.lemonde.fr/rss/en_continu.xml",
        "https://www.lemonde.fr/international/rss_full.xml",
        "https://www.lemonde.fr/politique/rss_full.xml",
        "https://www.lemonde.fr/economie/rss_full.xml",
    ]
    SITEMAP_URL = "/sitemap.xml"

    # --- Selectors (title-only mode due to hard paywall) ---
    TITLE_CSS = "h1.article__title"
    TITLE_CSS_FALLBACK = "h1"
    BODY_CSS = "p.article__desc"  # Lead paragraph only (visible before paywall)
    BODY_CSS_FALLBACK = ""
    DATE_CSS = ""
    AUTHOR_CSS = "span.article__author-name, a.article__author-link"
    ARTICLE_LINK_CSS = "a[href*='/article/']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, nav, aside, footer, "
        "div[class*='paywall'], div[class*='ad'], "
        "div[class*='share'], div[class*='subscribe']"
    )

    SECTION_URLS = [
        "https://www.lemonde.fr/en/international/",
        "https://www.lemonde.fr/en/economy/",
        "https://www.lemonde.fr/en/science/",
        "https://www.lemonde.fr/en/environment/",
        "https://www.lemonde.fr/en/culture/",
    ]

    # --- Rate limiting ---
    RATE_LIMIT_SECONDS = 10.0
    MAX_REQUESTS_PER_HOUR = 240
    JITTER_SECONDS = 3.0

    # --- Anti-block (HIGH) ---
    ANTI_BLOCK_TIER = 3
    UA_TIER = 3
    REQUIRES_PROXY = False
    BOT_BLOCK_LEVEL = "HIGH"

    PAYWALL_TYPE = "hard"
    CHARSET = "utf-8"

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract title and lead paragraph from Le Monde HTML.

        Body is limited to the lead paragraph due to hard paywall.
        Full article text requires Le Monde subscription.
        """
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

        # Body: lead paragraph only (paywall blocks full content)
        body = ""
        lead = soup.select_one(self.BODY_CSS)
        if lead:
            body = lead.get_text(strip=True)
        if not body:
            body = self._extract_meta_content(soup, "og:description")

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

        # Author
        author = None
        author_el = soup.select_one(self.AUTHOR_CSS)
        if author_el:
            author = author_el.get_text(strip=True)
        if not author:
            author = self._extract_meta_content(soup, "author") or None

        # Category from URL path or kicker
        category = None
        kicker = soup.select_one("span.article__kicker")
        if kicker:
            category = kicker.get_text(strip=True)
        if not category:
            category = self._extract_category_from_url(url)

        return {
            "title": title,
            "body": body,
            "published_at": published_at,
            "author": author,
            "category": category,
            "is_paywall_truncated": True,
        }

    def get_section_urls(self) -> list[str]:
        return list(self.SECTION_URLS)

    def normalize_date(self, date_str: str) -> Any:
        """Parse ISO 8601 first, then French date formats."""
        result = super().normalize_date(date_str)
        if result:
            return result
        return parse_french_date(date_str)
