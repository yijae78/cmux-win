"""Adapter for El Comercio Peru (https://elcomercio.pe)."""

from __future__ import annotations

from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter


class ElComercioAdapter(BaseSiteAdapter):
    """Adapter for El Comercio Peru."""

    SITE_ID = "elcomercio_pe"
    SITE_NAME = "El Comercio Peru"
    SITE_URL = "https://elcomercio.pe"
    LANGUAGE = "es"
    GROUP = "I"
    REGION = "PE"

    UA_TIER = 2
    RATE_LIMIT_SECONDS = 3.0
    MAX_REQUESTS_PER_HOUR = 120

    RSS_URL = "https://elcomercio.pe/feed"
    SITEMAP_URL = "https://elcomercio.pe/sitemap.xml"

    TITLE_CSS = "h1"
    BODY_CSS = "article, .article-body, .story-body, .entry-content, main"
    BODY_EXCLUDE_CSS = "nav, footer, .ad, .advertisement, .social-share, .related"
    DATE_CSS = "time, .date, .published, .article-date"
    AUTHOR_CSS = ".author, .byline, [rel=author]"

    SECTION_URLS = [
        "https://elcomercio.pe",
    ]

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from HTML using CSS selectors."""
        return self._default_extract(html, url)

    def get_section_urls(self) -> list[str]:
        """Return section URLs for DOM-based article discovery."""
        return list(self.SECTION_URLS)

