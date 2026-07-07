"""Adapter for La Vanguardia (https://www.lavanguardia.com)."""

from __future__ import annotations

from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter


class LaVanguardiaAdapter(BaseSiteAdapter):
    """Adapter for La Vanguardia."""

    SITE_ID = "lavanguardia"
    SITE_NAME = "La Vanguardia"
    SITE_URL = "https://www.lavanguardia.com"
    LANGUAGE = "es"
    GROUP = "G"
    REGION = "ES"

    UA_TIER = 2
    RATE_LIMIT_SECONDS = 3.0
    MAX_REQUESTS_PER_HOUR = 120

    RSS_URL = "https://www.lavanguardia.com/feed"
    SITEMAP_URL = "https://www.lavanguardia.com/sitemap.xml"

    TITLE_CSS = "h1"
    BODY_CSS = "article, .article-body, .story-body, .entry-content, main"
    BODY_EXCLUDE_CSS = "nav, footer, .ad, .advertisement, .social-share, .related"
    DATE_CSS = "time, .date, .published, .article-date"
    AUTHOR_CSS = ".author, .byline, [rel=author]"

    SECTION_URLS = [
        "https://www.lavanguardia.com",
    ]

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from HTML using CSS selectors."""
        return self._default_extract(html, url)

    def get_section_urls(self) -> list[str]:
        """Return section URLs for DOM-based article discovery."""
        return list(self.SECTION_URLS)

