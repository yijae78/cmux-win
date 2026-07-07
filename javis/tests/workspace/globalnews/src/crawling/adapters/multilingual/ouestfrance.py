"""Adapter for Ouest-France (https://www.ouest-france.fr)."""

from __future__ import annotations

from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter


class OuestFranceAdapter(BaseSiteAdapter):
    """Adapter for Ouest-France."""

    SITE_ID = "ouestfrance"
    SITE_NAME = "Ouest-France"
    SITE_URL = "https://www.ouest-france.fr"
    LANGUAGE = "fr"
    GROUP = "G"
    REGION = "FR"

    UA_TIER = 3
    RATE_LIMIT_SECONDS = 5.0
    MAX_REQUESTS_PER_HOUR = 60

    RSS_URL = "https://www.ouest-france.fr/feed"
    SITEMAP_URL = "https://www.ouest-france.fr/sitemap.xml"

    TITLE_CSS = "h1"
    BODY_CSS = "article, .article-body, .story-body, .entry-content, main"
    BODY_EXCLUDE_CSS = "nav, footer, .ad, .advertisement, .social-share, .related"
    DATE_CSS = "time, .date, .published, .article-date"
    AUTHOR_CSS = ".author, .byline, [rel=author]"

    SECTION_URLS = [
        "https://www.ouest-france.fr",
    ]

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from HTML using CSS selectors."""
        return self._default_extract(html, url)

    def get_section_urls(self) -> list[str]:
        """Return section URLs for DOM-based article discovery."""
        return list(self.SECTION_URLS)

