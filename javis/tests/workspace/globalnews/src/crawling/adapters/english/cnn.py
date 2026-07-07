"""CNN International adapter -- open-access news with JS-heavy pages.

CNN International (edition.cnn.com) is a major global news source with no
paywall. The international edition is used to avoid US-centric content
filtering. Uses sitemap as primary discovery method. Some pages require
JavaScript rendering, but most articles are accessible via server-rendered HTML.

Reference:
    sources.yaml key: cnn
    Primary method: sitemap (Google News sitemap available)
    Paywall: none
    Bot block level: HIGH
    Difficulty: Medium
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter

logger = logging.getLogger(__name__)


class CNNAdapter(BaseSiteAdapter):
    """Adapter for CNN International (edition.cnn.com).

    CNN uses a custom CMS with JSON-LD structured data. Article bodies
    are in well-defined containers with paragraph elements. The site
    restructured its URLs and templates in 2023; this adapter handles
    both legacy and current article formats.
    """

    # --- Site identity ---
    SITE_ID = "cnn"
    SITE_NAME = "CNN"
    SITE_URL = "https://edition.cnn.com"
    LANGUAGE = "en"
    REGION = "us"
    GROUP = "E"

    # --- URL discovery ---
    RSS_URL = "http://rss.cnn.com/rss/edition.rss"
    SITEMAP_URL = "/sitemaps/sitemap-index.xml"

    # --- Article extraction selectors ---
    # CNN's 2023+ article format
    TITLE_CSS = "h1.headline__text"
    TITLE_CSS_FALLBACK = "h1[data-editable='headlineText'], h1[class*='pg-headline']"
    BODY_CSS = "div.article__content"
    BODY_CSS_FALLBACK = "section[class*='body-text'], div[class*='zn-body__paragraph']"
    DATE_CSS = "div.timestamp"
    AUTHOR_CSS = "span.byline__name"
    ARTICLE_LINK_CSS = "a[href*='/2'], a[data-link-type='article']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, "
        "div[class*='ad-slot'], div[class*='ad_'], "
        "div[class*='related'], div[class*='outbrain'], "
        "div[class*='video-player'], div.el__gallery-embed, "
        "div[class*='newsletter'], div[class*='social'], "
        "aside, nav, footer"
    )

    # --- Section/listing pages ---
    SECTION_URLS = [
        "https://edition.cnn.com/world",
        "https://edition.cnn.com/us",
        "https://edition.cnn.com/politics",
        "https://edition.cnn.com/business",
        "https://edition.cnn.com/tech",
        "https://edition.cnn.com/entertainment",
        "https://edition.cnn.com/sport",
        "https://edition.cnn.com/health",
        "https://edition.cnn.com/travel",
        "https://edition.cnn.com/style",
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
        """Extract article fields from CNN HTML.

        CNN articles have JSON-LD metadata and a structured body container.
        Handles both the 2023+ and legacy article formats.

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

        # 2. Title fallback
        if not result["title"]:
            title_el = (
                soup.select_one(self.TITLE_CSS)
                or soup.select_one(self.TITLE_CSS_FALLBACK)
            )
            if title_el:
                result["title"] = title_el.get_text(strip=True)

        if not result["title"]:
            result["title"] = self._extract_meta_content(soup, "og:title")

        # 3. Body extraction -- handle CNN's paragraph structure
        body_el = soup.select_one(self.BODY_CSS)
        if body_el:
            result["body"] = self._clean_body_text(body_el)
        else:
            # Fallback: collect individual paragraph elements
            result["body"] = self._extract_cnn_paragraphs(soup)

        # 4. Date fallback
        if not result["published_at"]:
            # CNN uses a timestamp div with a specific format
            ts_el = soup.select_one(self.DATE_CSS)
            if ts_el:
                ts_text = ts_el.get_text(strip=True)
                result["published_at"] = self._parse_cnn_timestamp(ts_text)

        if not result["published_at"]:
            pub_time = self._extract_meta_content(soup, "article:published_time")
            if pub_time:
                result["published_at"] = self.normalize_date(pub_time)

        # 5. Author fallback
        if not result["author"]:
            author_el = soup.select_one(self.AUTHOR_CSS)
            if author_el:
                text = author_el.get_text(strip=True)
                result["author"] = re.sub(r"^By\s+", "", text, flags=re.IGNORECASE)

        # 6. Category from URL path
        if not result["category"]:
            result["category"] = self._extract_section_from_url(url)

        return result

    def get_section_urls(self) -> list[str]:
        """Return CNN section URLs for DOM-based discovery."""
        return list(self.SECTION_URLS)

    def _extract_cnn_paragraphs(self, soup: Any) -> str:
        """Extract body text from CNN's paragraph-based structure.

        CNN sometimes uses individual paragraph containers instead of a
        single body div.

        Args:
            soup: BeautifulSoup object.

        Returns:
            Joined paragraph text.
        """
        paragraphs: list[str] = []

        # Try various CNN paragraph selectors
        selectors = [
            "p.paragraph--lite",
            "div.zn-body__paragraph",
            "p[class*='Paragraph']",
        ]
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                for el in elements:
                    text = el.get_text(strip=True)
                    if text and len(text) > 10:
                        paragraphs.append(text)
                break

        return "\n\n".join(paragraphs)

    def _parse_cnn_timestamp(self, text: str) -> datetime | None:
        """Parse CNN's custom timestamp format.

        CNN uses formats like:
        - "Updated 2:30 PM EST, Mon February 25, 2026"
        - "Published 10:00 AM ET, Tue February 25, 2026"

        Args:
            text: Raw timestamp text from the page.

        Returns:
            datetime in UTC, or None if parsing fails.
        """
        # Strip "Updated" / "Published" prefix
        text = re.sub(r"^(Updated|Published)\s+", "", text.strip(), flags=re.IGNORECASE)
        # Strip timezone abbreviation (handle conversion separately)
        text = re.sub(r"\s+(EST|EDT|CST|CDT|MST|MDT|PST|PDT|ET)\s*,?", ",", text)
        # Strip day name
        text = re.sub(r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*\s*", "", text, flags=re.IGNORECASE)
        text = text.strip().strip(",").strip()

        # Try standard parsing
        return self.normalize_date(text)

    def _is_article_url(self, url: str) -> bool:
        """CNN article URLs contain year/month/day pattern or specific paths."""
        if re.search(r"/\d{4}/\d{2}/\d{2}/", url):
            return True
        # Some CNN URLs use /article/ path
        if "/article/" in url:
            return True
        return super()._is_article_url(url)

    @staticmethod
    def _extract_section_from_url(url: str) -> str | None:
        """Extract section from CNN URL path.

        CNN URLs: /YYYY/MM/DD/section/slug/index.html or /section/...
        """
        from urllib.parse import urlparse
        path = urlparse(url).path.strip("/")
        segments = path.split("/")

        # /YYYY/MM/DD/section/slug pattern
        if len(segments) >= 4 and segments[0].isdigit():
            section = segments[3]
            if section != "index.html":
                return section

        # /section/... pattern
        if segments and segments[0] in (
            "world", "us", "politics", "business", "tech",
            "entertainment", "sport", "health", "travel", "style",
            "africa", "americas", "asia", "australia", "china",
            "europe", "india", "middle-east", "uk",
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
