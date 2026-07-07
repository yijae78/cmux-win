"""MarketWatch adapter -- financial news with soft-metered paywall.

MarketWatch (Dow Jones / News Corp) publishes financial news, stock market data,
and personal finance content. Uses RSS as primary discovery method with multiple
topic-specific feeds. Soft-metered paywall allows several free articles before
requiring MarketWatch+ subscription.

Reference:
    sources.yaml key: marketwatch
    Primary method: RSS (3 section feeds)
    Paywall: soft-metered (MarketWatch+ for premium content)
    Bot block level: HIGH
    Difficulty: Hard
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter

logger = logging.getLogger(__name__)


class MarketWatchAdapter(BaseSiteAdapter):
    """Adapter for MarketWatch (marketwatch.com).

    MarketWatch uses well-structured HTML with JSON-LD for article metadata.
    Article body is in a dedicated container with clear paragraph structure.
    Premium/MarketWatch+ content is marked with specific CSS classes.
    """

    # --- Site identity ---
    SITE_ID = "marketwatch"
    SITE_NAME = "MarketWatch"
    SITE_URL = "https://www.marketwatch.com"
    LANGUAGE = "en"
    REGION = "us"
    GROUP = "E"

    # --- URL discovery ---
    RSS_URL = "https://www.marketwatch.com/rss"
    RSS_URLS = [
        "https://feeds.marketwatch.com/marketwatch/topstories",
        "https://feeds.marketwatch.com/marketwatch/marketpulse",
        "https://feeds.marketwatch.com/marketwatch/bulletins",
    ]
    SITEMAP_URL = "/sitemap.xml"

    # --- Article extraction selectors ---
    # MarketWatch uses article__headline for titles and article__body for content
    TITLE_CSS = "h1.article__headline"
    TITLE_CSS_FALLBACK = "h1[class*='headline']"
    BODY_CSS = "div.article__body"
    BODY_CSS_FALLBACK = "div[class*='article__body']"
    DATE_CSS = "time.timestamp--pub"
    AUTHOR_CSS = "span.article__byline"
    ARTICLE_LINK_CSS = "a[class*='link']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div.article__inset, div.element--ad, "
        "div[class*='advertisement'], div[class*='related'], "
        "div.article__social, div.article__video, "
        "aside, nav, footer"
    )

    # --- Section/listing pages ---
    SECTION_URLS = [
        "https://www.marketwatch.com/latest-news",
        "https://www.marketwatch.com/markets",
        "https://www.marketwatch.com/investing",
        "https://www.marketwatch.com/economy-politics",
        "https://www.marketwatch.com/personal-finance",
    ]
    PAGINATION_TYPE = "page_number"
    PAGINATION_PARAM = "page"
    MAX_PAGES = 5

    # --- Rate limiting ---
    RATE_LIMIT_SECONDS = 10.0
    MAX_REQUESTS_PER_HOUR = 240
    JITTER_SECONDS = 3.0

    # --- Anti-block ---
    ANTI_BLOCK_TIER = 2
    UA_TIER = 3
    REQUIRES_PROXY = False
    BOT_BLOCK_LEVEL = "HIGH"

    # --- Extraction config ---
    PAYWALL_TYPE = "soft-metered"
    CHARSET = "utf-8"

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from MarketWatch HTML.

        Extraction chain:
            1. JSON-LD structured data for metadata (title, date, author).
            2. CSS selectors for body text.
            3. Paywall detection via MarketWatch+ premium indicators.

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

        # 1. JSON-LD extraction (primary for metadata)
        json_ld = self._extract_json_ld(soup)
        if json_ld:
            result["title"] = json_ld.get("headline", "")
            result["author"] = self._extract_json_ld_author(json_ld)
            date_str = json_ld.get("datePublished", "")
            if date_str:
                result["published_at"] = self.normalize_date(date_str)
            section = json_ld.get("articleSection")
            if isinstance(section, list):
                result["category"] = section[0] if section else None
            elif isinstance(section, str):
                result["category"] = section

        # 2. CSS-based title fallback
        if not result["title"]:
            title_el = soup.select_one(self.TITLE_CSS) or soup.select_one(self.TITLE_CSS_FALLBACK)
            if title_el:
                result["title"] = title_el.get_text(strip=True)

        # 3. og:title ultimate fallback
        if not result["title"]:
            result["title"] = self._extract_meta_content(soup, "og:title")

        # 4. Body extraction
        body_el = soup.select_one(self.BODY_CSS) or soup.select_one(self.BODY_CSS_FALLBACK)
        if body_el:
            result["body"] = self._clean_body_text(body_el)

        # 5. Date fallback from CSS
        if not result["published_at"]:
            date_el = soup.select_one(self.DATE_CSS)
            if date_el:
                dt_str = date_el.get("datetime", "") or date_el.get_text(strip=True)
                result["published_at"] = self.normalize_date(dt_str)

        # 6. Author fallback
        if not result["author"]:
            author_el = soup.select_one(self.AUTHOR_CSS)
            if author_el:
                result["author"] = author_el.get_text(strip=True).replace("By ", "")

        # 7. Paywall detection: MarketWatch+ premium content marker
        is_paywalled = self._detect_marketwatch_paywall(soup, html)
        if is_paywalled and len(result["body"]) < 200:
            result["is_paywall_truncated"] = True

        # 8. Category fallback from breadcrumb
        if not result["category"]:
            breadcrumb = soup.select_one("nav.breadcrumbs a, li.breadcrumb a")
            if breadcrumb:
                result["category"] = breadcrumb.get_text(strip=True)

        return result

    def get_section_urls(self) -> list[str]:
        """Return MarketWatch section URLs for DOM-based discovery."""
        return list(self.SECTION_URLS)

    def _detect_marketwatch_paywall(self, soup: Any, html: str) -> bool:
        """Detect MarketWatch+ paywall indicators.

        Args:
            soup: BeautifulSoup object.
            html: Raw HTML string.

        Returns:
            True if premium content paywall detected.
        """
        # Check for MarketWatch+ subscription gate
        if soup.select_one("div[class*='paywall']"):
            return True
        if soup.select_one("div[class*='premium']"):
            return True
        if "marketwatch-plus" in html.lower() or "mw-plus" in html.lower():
            return True
        return False

    @staticmethod
    def _extract_json_ld_author(json_ld: dict[str, Any]) -> str | None:
        """Extract author from JSON-LD data."""
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
