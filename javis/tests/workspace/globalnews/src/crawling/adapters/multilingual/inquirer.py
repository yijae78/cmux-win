"""Adapter for Philippine Daily Inquirer (https://www.inquirer.net)."""

from __future__ import annotations

from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter


class InquirerAdapter(BaseSiteAdapter):
    """Adapter for Philippine Daily Inquirer."""

    SITE_ID = "inquirer"
    SITE_NAME = "Philippine Daily Inquirer"
    SITE_URL = "https://www.inquirer.net"
    LANGUAGE = "en"
    GROUP = "F"
    REGION = "PH"

    UA_TIER = 2
    RATE_LIMIT_SECONDS = 3.0
    MAX_REQUESTS_PER_HOUR = 120

    RSS_URL = "https://www.inquirer.net/feed"
    SITEMAP_URL = "https://www.inquirer.net/sitemap.xml"

    TITLE_CSS = "h1"
    BODY_CSS = "article, .article-body, .story-body, .entry-content, main"
    BODY_EXCLUDE_CSS = "nav, footer, .ad, .advertisement, .social-share, .related"
    DATE_CSS = "time, .date, .published, .article-date"
    AUTHOR_CSS = ".author, .byline, [rel=author]"

    SECTION_URLS = [
        "https://www.inquirer.net",
    ]

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from HTML using CSS selectors."""
        return self._default_extract(html, url)

    def get_section_urls(self) -> list[str]:
        """Return section URLs for DOM-based article discovery."""
        return list(self.SECTION_URLS)

