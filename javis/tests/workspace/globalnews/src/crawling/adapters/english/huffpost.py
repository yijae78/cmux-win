"""HuffPost adapter -- open-access general news and opinion.

HuffPost (formerly Huffington Post) publishes news, opinion, and lifestyle
content with no paywall. Uses sitemap as primary discovery method since
RSS feeds are not reliably available. Heavy use of JavaScript for rendering
but articles are accessible via standard HTML.

Reference:
    sources.yaml key: huffpost
    Primary method: sitemap (Google News sitemap available)
    Paywall: none
    Bot block level: HIGH
    Difficulty: Medium
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter

logger = logging.getLogger(__name__)


class HuffPostAdapter(BaseSiteAdapter):
    """Adapter for HuffPost (huffpost.com).

    HuffPost uses a React-based frontend but serves articles with
    server-side rendering. JSON-LD is available for most articles.
    The main content is in a well-structured ``entry__text`` container.
    """

    # --- Site identity ---
    SITE_ID = "huffpost"
    SITE_NAME = "HuffPost"
    SITE_URL = "https://www.huffpost.com"
    LANGUAGE = "en"
    REGION = "us"
    GROUP = "E"

    # --- URL discovery ---
    RSS_URL = ""  # No confirmed RSS endpoint
    SITEMAP_URL = "/sitemap.xml"

    # --- Article extraction selectors ---
    TITLE_CSS = "h1.headline__title"
    TITLE_CSS_FALLBACK = "h1[data-testid='headline']"
    BODY_CSS = "div.entry__text"
    BODY_CSS_FALLBACK = "section.entry__content"
    DATE_CSS = "time[datetime]"
    AUTHOR_CSS = "span.author-card__details__name"
    ARTICLE_LINK_CSS = "a.card__link, a[class*='card__headline']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div.cli-embed, div.related-article, "
        "div.below-entry, div[class*='advertisement'], "
        "div.entry__adblocker, div.newsletter-tout, "
        "aside, nav, footer"
    )

    # --- Section/listing pages ---
    SECTION_URLS = [
        "https://www.huffpost.com/news",
        "https://www.huffpost.com/news/politics",
        "https://www.huffpost.com/news/world-news",
        "https://www.huffpost.com/news/us-news",
        "https://www.huffpost.com/news/business",
        "https://www.huffpost.com/entertainment",
        "https://www.huffpost.com/life",
    ]
    PAGINATION_TYPE = "none"
    MAX_PAGES = 3

    # --- Rate limiting ---
    RATE_LIMIT_SECONDS = 5.0
    MAX_REQUESTS_PER_HOUR = 720
    JITTER_SECONDS = 0.0

    # --- Anti-block ---
    ANTI_BLOCK_TIER = 1
    UA_TIER = 2
    REQUIRES_PROXY = False
    BOT_BLOCK_LEVEL = "HIGH"

    # --- Extraction config ---
    PAYWALL_TYPE = "none"
    CHARSET = "utf-8"

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from HuffPost HTML.

        HuffPost articles have JSON-LD metadata and a clean body container.
        The ``entry__text`` div contains the article paragraphs.

        Args:
            html: Raw HTML of the article page.
            url: Canonical article URL.

        Returns:
            Dict with title, body, published_at, author, category,
            is_paywall_truncated.
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        result: dict[str, Any] = {
            "title": "",
            "body": "",
            "published_at": None,
            "author": None,
            "category": None,
            "is_paywall_truncated": False,
        }

        # 1. JSON-LD extraction
        json_ld = self._extract_json_ld(soup)
        if json_ld:
            result["title"] = json_ld.get("headline", "")
            result["author"] = _extract_author_from_json_ld(json_ld)
            date_str = json_ld.get("datePublished", "")
            if date_str:
                result["published_at"] = self.normalize_date(date_str)
            section = json_ld.get("articleSection")
            if isinstance(section, str):
                result["category"] = section
            elif isinstance(section, list) and section:
                result["category"] = section[0]

        # 2. Title from CSS
        if not result["title"]:
            title_el = (
                soup.select_one(self.TITLE_CSS)
                or soup.select_one(self.TITLE_CSS_FALLBACK)
            )
            if title_el:
                result["title"] = title_el.get_text(strip=True)

        # 3. og:title fallback
        if not result["title"]:
            result["title"] = self._extract_meta_content(soup, "og:title")

        # 4. Body extraction
        body_el = (
            soup.select_one(self.BODY_CSS)
            or soup.select_one(self.BODY_CSS_FALLBACK)
        )
        if body_el:
            result["body"] = self._clean_body_text(body_el)

        # 5. Date fallback
        if not result["published_at"]:
            time_el = soup.select_one(self.DATE_CSS)
            if time_el:
                dt_str = time_el.get("datetime", "")
                result["published_at"] = self.normalize_date(dt_str)

        # 6. Author fallback
        if not result["author"]:
            author_el = soup.select_one(self.AUTHOR_CSS)
            if author_el:
                result["author"] = author_el.get_text(strip=True)

        # 7. Category from URL path
        if not result["category"]:
            result["category"] = self._extract_category_from_url(url)

        return result

    def get_section_urls(self) -> list[str]:
        """Return HuffPost section URLs for DOM-based discovery."""
        return list(self.SECTION_URLS)

    @staticmethod
    def _extract_category_from_url(url: str) -> str | None:
        """Extract category from HuffPost URL path.

        HuffPost URLs follow the pattern: /entry/slug_id
        The entry type is often in the path.
        """
        from urllib.parse import urlparse
        path = urlparse(url).path.strip("/")
        segments = path.split("/")
        # /news/politics/entry/... -> "politics"
        if len(segments) >= 2 and segments[0] == "news":
            return segments[1]
        if len(segments) >= 1 and segments[0] in (
            "news", "entertainment", "life", "voices", "impact"
        ):
            return segments[0]
        return None


def _extract_author_from_json_ld(json_ld: dict[str, Any]) -> str | None:
    """Extract author name from JSON-LD data."""
    author = json_ld.get("author")
    if isinstance(author, str):
        return author
    if isinstance(author, dict):
        return author.get("name")
    if isinstance(author, list):
        names = []
        for a in author:
            if isinstance(a, dict):
                names.append(a.get("name", ""))
            elif isinstance(a, str):
                names.append(a)
        return ", ".join(n for n in names if n) or None
    return None
