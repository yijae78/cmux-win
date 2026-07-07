"""Adapter for La Nacion Argentina (https://www.lanacion.com.ar)."""

from __future__ import annotations

from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter


class LaNacionAdapter(BaseSiteAdapter):
    """Adapter for La Nacion Argentina."""

    SITE_ID = "lanacion_ar"
    SITE_NAME = "La Nacion Argentina"
    SITE_URL = "https://www.lanacion.com.ar"
    LANGUAGE = "es"
    GROUP = "I"
    REGION = "AR"

    UA_TIER = 2
    RATE_LIMIT_SECONDS = 3.0
    MAX_REQUESTS_PER_HOUR = 120

    RSS_URL = "https://www.lanacion.com.ar/feed"
    SITEMAP_URL = "https://www.lanacion.com.ar/sitemap.xml"

    TITLE_CSS = "h1"
    BODY_CSS = "article, .article-body, .story-body, .entry-content, main"
    BODY_EXCLUDE_CSS = "nav, footer, .ad, .advertisement, .social-share, .related"
    DATE_CSS = "time, .date, .published, .article-date"
    AUTHOR_CSS = ".author, .byline, [rel=author]"

    SECTION_URLS = [
        "https://www.lanacion.com.ar",
    ]

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from HTML using CSS selectors."""
        return self._default_extract(html, url)

    def get_section_urls(self) -> list[str]:
        """Return section URLs for DOM-based article discovery."""
        return list(self.SECTION_URLS)

