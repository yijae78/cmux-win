"""BuzzFeed adapter -- entertainment-only (BuzzFeed News shut down April 2023).

BuzzFeed News ceased operations in April 2023. BuzzFeed itself continues
as an entertainment/lifestyle platform publishing quizzes, listicles, and
pop culture content. This adapter handles the entertainment content only.
Uses Playwright as primary method due to heavy JavaScript rendering.

Reference:
    sources.yaml key: buzzfeed
    Primary method: playwright (JS rendering required)
    Paywall: none
    Bot block level: HIGH
    Difficulty: Hard
    Note: BuzzFeed News shut down April 2023
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter

logger = logging.getLogger(__name__)

# BuzzFeed News shutdown date for filtering legacy content
BUZZFEED_NEWS_SHUTDOWN = "2023-04-20"


class BuzzFeedAdapter(BaseSiteAdapter):
    """Adapter for BuzzFeed (buzzfeed.com).

    IMPORTANT: BuzzFeed News was shut down in April 2023. This adapter
    handles BuzzFeed entertainment/lifestyle content only. Articles from
    the former BuzzFeed News section are treated as archived content.

    BuzzFeed uses heavy JavaScript rendering; Playwright is the primary
    extraction method. Sitemap is available for URL discovery.
    """

    # --- Site identity ---
    SITE_ID = "buzzfeed"
    SITE_NAME = "BuzzFeed"
    SITE_URL = "https://www.buzzfeed.com"
    LANGUAGE = "en"
    REGION = "us"
    GROUP = "E"

    # --- URL discovery ---
    RSS_URL = ""  # Blocked by robots.txt /*.xml$
    SITEMAP_URL = "/sitemaps/buzzfeed/sitemap.xml"

    # --- Article extraction selectors ---
    # BuzzFeed uses React-based rendering with data-testid attributes
    TITLE_CSS = "h1[class*='title'], h1[data-testid='content-title']"
    TITLE_CSS_FALLBACK = "h1"
    BODY_CSS = "div[data-testid='story-card'], div.js-subbuzz"
    BODY_CSS_FALLBACK = "div[class*='content-module'], article"
    DATE_CSS = "time[datetime]"
    AUTHOR_CSS = "span[class*='byline'], a[data-testid='byline-link']"
    ARTICLE_LINK_CSS = "a[href*='/article/'], a[class*='card__link']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div[class*='ad-unit'], div[class*='newsletter'], "
        "div[class*='related'], div[class*='trending'], "
        "aside, nav, footer"
    )

    # --- Section/listing pages ---
    SECTION_URLS = [
        "https://www.buzzfeed.com/trending",
        "https://www.buzzfeed.com/entertainment",
        "https://www.buzzfeed.com/celebrity",
        "https://www.buzzfeed.com/tvandmovies",
        "https://www.buzzfeed.com/food",
        "https://www.buzzfeed.com/shopping",
    ]
    PAGINATION_TYPE = "none"
    MAX_PAGES = 3

    # --- Rate limiting ---
    RATE_LIMIT_SECONDS = 10.0
    MAX_REQUESTS_PER_HOUR = 240
    JITTER_SECONDS = 3.0

    # --- Anti-block ---
    ANTI_BLOCK_TIER = 3
    UA_TIER = 3
    REQUIRES_PROXY = False
    BOT_BLOCK_LEVEL = "HIGH"

    # --- Extraction config ---
    PAYWALL_TYPE = "none"
    CHARSET = "utf-8"
    RENDERING_REQUIRED = True

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from BuzzFeed HTML.

        BuzzFeed articles are JavaScript-heavy. This extractor handles
        both server-rendered and client-rendered content. Articles from
        the former BuzzFeed News section are flagged in the category.

        Args:
            html: Raw HTML (possibly from Playwright rendering).
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

        # 2. Title from CSS
        if not result["title"]:
            title_el = (
                soup.select_one(self.TITLE_CSS)
                or soup.select_one(self.TITLE_CSS_FALLBACK)
            )
            if title_el:
                result["title"] = title_el.get_text(strip=True)

        if not result["title"]:
            result["title"] = self._extract_meta_content(soup, "og:title")

        # 3. Body extraction -- BuzzFeed uses subbuzz cards
        body_parts: list[str] = []
        # Try primary body container
        body_el = soup.select_one(self.BODY_CSS)
        if body_el:
            body_parts.append(self._clean_body_text(body_el))
        else:
            # Fallback: collect all subbuzz/story-card elements
            for card in soup.select("div.js-subbuzz, div[data-testid='story-card']"):
                text = self._clean_body_text(card)
                if text:
                    body_parts.append(text)

        if not body_parts:
            # Ultimate fallback: article tag
            article_el = soup.select_one(self.BODY_CSS_FALLBACK)
            if article_el:
                body_parts.append(self._clean_body_text(article_el))

        result["body"] = "\n\n".join(body_parts)

        # 4. Date fallback
        if not result["published_at"]:
            time_el = soup.select_one(self.DATE_CSS)
            if time_el:
                dt_str = time_el.get("datetime", "")
                result["published_at"] = self.normalize_date(dt_str)

        # 5. Author fallback
        if not result["author"]:
            author_el = soup.select_one(self.AUTHOR_CSS)
            if author_el:
                result["author"] = author_el.get_text(strip=True)

        # 6. Category -- detect if this was a BuzzFeed News article
        result["category"] = self._classify_content(url)

        return result

    def get_section_urls(self) -> list[str]:
        """Return BuzzFeed section URLs for DOM-based discovery."""
        return list(self.SECTION_URLS)

    def _classify_content(self, url: str) -> str:
        """Classify BuzzFeed content type.

        Distinguishes between entertainment content and archived
        BuzzFeed News content (shut down April 2023).

        Args:
            url: Article URL.

        Returns:
            Content category string.
        """
        from urllib.parse import urlparse
        path = urlparse(url).path.lower()

        # BuzzFeed News was at /news/ or specific verticals
        if "/news/" in path:
            return "news (archived)"

        category_map = {
            "/entertainment/": "entertainment",
            "/celebrity/": "celebrity",
            "/tvandmovies/": "tv and movies",
            "/food/": "food",
            "/shopping/": "shopping",
            "/trending/": "trending",
            "/quizzes/": "quizzes",
        }
        for prefix, cat in category_map.items():
            if prefix in path:
                return cat

        return "entertainment"

    def _is_article_url(self, url: str) -> bool:
        """BuzzFeed article URLs contain specific path patterns."""
        from urllib.parse import urlparse
        path = urlparse(url).path
        # BuzzFeed articles: /username/slug or /article/slug
        if "/article/" in path:
            return True
        segments = [s for s in path.strip("/").split("/") if s]
        # Author/slug pattern: at least 2 segments, not a section page
        if len(segments) >= 2 and segments[0] not in (
            "tag", "search", "about", "contact", "sitemaps",
        ):
            return True
        return False


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
