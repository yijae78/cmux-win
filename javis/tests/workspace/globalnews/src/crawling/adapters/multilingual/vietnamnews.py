"""Adapter for Vietnam News (https://vietnamnews.vn)."""

from __future__ import annotations

from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter


class VietnamNewsAdapter(BaseSiteAdapter):
    """Adapter for Vietnam News."""

    SITE_ID = "vietnamnews"
    SITE_NAME = "Vietnam News"
    SITE_URL = "https://vietnamnews.vn"
    LANGUAGE = "en"
    GROUP = "F"
    REGION = "VN"

    UA_TIER = 1
    RATE_LIMIT_SECONDS = 2.0
    MAX_REQUESTS_PER_HOUR = 200

    RSS_URL = "https://vietnamnews.vn/feed"
    SITEMAP_URL = "https://vietnamnews.vn/sitemap.xml"

    TITLE_CSS = "h1"
    BODY_CSS = "article, .article-body, .story-body, .entry-content, main"
    BODY_EXCLUDE_CSS = "nav, footer, .ad, .advertisement, .social-share, .related"
    DATE_CSS = "time, .date, .published, .article-date"
    AUTHOR_CSS = ".author, .byline, [rel=author]"

    SECTION_URLS = [
        "https://vietnamnews.vn",
    ]

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from HTML using CSS selectors."""
        return self._default_extract(html, url)

    def get_section_urls(self) -> list[str]:
        """Return section URLs for DOM-based article discovery."""
        return list(self.SECTION_URLS)

