"""Korea Economic Daily (hankyung.com) site adapter.

Group B — Korean Economy. PAYWALL SITE.
Primary method: RSS. Fallback: Sitemap > DOM.
Bot block level: MEDIUM. Proxy: KR required.

Decision Rationale [trace:step-6:hankyung-strategy]:
    RSS at http://rss.hankyung.com/economy.xml confirmed with multiple
    category feeds on the rss subdomain. Soft paywall (Hankyung Premium)
    gates some premium articles. Cookie clearing between sessions manages
    the meter. Category-specific RSS feeds enable targeted crawling.

Selectors verified via Step 6 analysis.
"""

from __future__ import annotations

import logging
from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter
from src.crawling.adapters.kr_major._kr_utils import (
    extract_category_from_url,
    extract_korean_author,
    parse_korean_date,
)

logger = logging.getLogger(__name__)

# Minimum body length to consider non-paywalled
_PAYWALL_BODY_THRESHOLD = 200


class HankyungAdapter(BaseSiteAdapter):
    """Adapter for Korea Economic Daily (hankyung.com).

    PAYWALL HANDLING:
        Hankyung Premium gates some articles behind a soft metered paywall.
        Strategy: clear cookies between crawl runs to refresh the meter.
        If body length < 200 chars, flag as ``is_paywall_truncated=True``.
    """

    # --- Site identity ---
    SITE_ID = "hankyung"
    SITE_NAME = "Korea Economic Daily"
    SITE_URL = "https://www.hankyung.com"
    LANGUAGE = "ko"
    REGION = "kr"
    GROUP = "B"

    # --- URL discovery ---
    RSS_URL = "http://rss.hankyung.com/economy.xml"
    RSS_URLS = [
        "http://rss.hankyung.com/economy.xml",
        "http://rss.hankyung.com/stock.xml",
        "http://rss.hankyung.com/realestate.xml",
        "http://rss.hankyung.com/international.xml",
        "http://rss.hankyung.com/politics.xml",
        "http://rss.hankyung.com/society.xml",
    ]
    SITEMAP_URL = "https://www.hankyung.com/sitemap.xml"

    # --- Article extraction selectors ---
    # [trace:step-6:hankyung-selectors]
    TITLE_CSS = 'meta[property="og:title"]'
    TITLE_CSS_FALLBACK = "h1.article-title"
    BODY_CSS = "div.article-body"
    BODY_CSS_FALLBACK = "div#articletxt"
    DATE_CSS = 'meta[property="article:published_time"]'
    AUTHOR_CSS = "span.byline"
    ARTICLE_LINK_CSS = "a[href*='/article/']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div.ad-container, div.article-ad, "
        "div.related-articles, "
        "div.social-share, div.sns-share, "
        "div.comment-area, "
        "div.paywall-prompt, div.premium-gate"
    )

    # --- Section URLs ---
    SECTION_URLS = [
        "https://www.hankyung.com/economy",
        "https://www.hankyung.com/finance",
        "https://www.hankyung.com/realestate",
        "https://www.hankyung.com/international",
        "https://www.hankyung.com/politics",
        "https://www.hankyung.com/society",
    ]

    PAGINATION_TYPE = "page_number"
    PAGINATION_PARAM = "page"
    MAX_PAGES = 5

    # --- Rate limiting ---
    RATE_LIMIT_SECONDS = 5.0
    MAX_REQUESTS_PER_HOUR = 720
    JITTER_SECONDS = 0.0

    # --- Anti-block ---
    ANTI_BLOCK_TIER = 1
    UA_TIER = 2
    REQUIRES_PROXY = True
    PROXY_REGION = "kr"
    BOT_BLOCK_LEVEL = "MEDIUM"

    # --- Extraction config ---
    PAYWALL_TYPE = "soft-metered"
    CHARSET = "utf-8"
    RENDERING_REQUIRED = False

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article fields from Hankyung HTML.

        Includes paywall detection: if body is shorter than the threshold,
        the article is flagged as paywall-truncated. The calling code should
        set ``is_paywall_truncated=True`` on the RawArticle.

        Notes:
            - Dynamic loading on some section pages.
            - Financial data articles heavy during market hours.
            - Multiple category RSS feeds for section-specific coverage.
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

        # Title
        result["title"] = self._extract_meta_content(soup, "og:title")
        if not result["title"]:
            el = soup.select_one("h1.article-title")
            if el:
                result["title"] = el.get_text(strip=True)

        # Body
        body_el = soup.select_one(self.BODY_CSS)
        if not body_el:
            body_el = soup.select_one(self.BODY_CSS_FALLBACK)
        if body_el:
            result["body"] = self._clean_body_text(body_el)

        # Paywall detection
        if result["body"] and len(result["body"].strip()) < _PAYWALL_BODY_THRESHOLD:
            result["is_paywall_truncated"] = True
            logger.info(
                "hankyung_paywall_detected url=%s body_len=%d",
                url,
                len(result["body"]),
            )

        # Also detect paywall prompt elements
        paywall_el = soup.select_one("div.paywall-prompt, div.premium-gate, div.article-lock")
        if paywall_el:
            result["is_paywall_truncated"] = True

        # Date
        date_str = self._extract_meta_content(soup, "article:published_time")
        if not date_str:
            date_el = soup.select_one("span.datetime")
            if date_el:
                date_str = date_el.get_text(strip=True)
        result["published_at"] = parse_korean_date(date_str) if date_str else None

        # Author
        author_el = soup.select_one(self.AUTHOR_CSS)
        if author_el:
            result["author"] = extract_korean_author(author_el.get_text(strip=True))
        if not result["author"]:
            meta_author = self._extract_meta_content(soup, "author")
            if meta_author:
                result["author"] = extract_korean_author(meta_author)

        # Category: from RSS feed name or URL
        result["category"] = extract_category_from_url(url, self.SITE_ID)

        return result

    def get_section_urls(self) -> list[str]:
        """Return Hankyung section page URLs."""
        return list(self.SECTION_URLS)

    def _is_article_url(self, url: str) -> bool:
        """Hankyung articles use /article/ path."""
        if "/article/" in url:
            return True
        return super()._is_article_url(url)
