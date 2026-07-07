"""Global Times (globaltimes.cn) adapter -- Chinese English-language outlet.

Site #33, Group F (Asia-Pacific).
Language: English (en). Encoding: UTF-8.
Primary method: Sitemap (news namespace with rich metadata).
Rate limit: 2s. Bot-blocking: LOW.

Reference:
    Step 6 crawl-strategy-asia.md, Section 4.2.
"""

from __future__ import annotations

from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter


class GlobalTimesAdapter(BaseSiteAdapter):
    """Adapter for Global Times (globaltimes.cn)."""

    SITE_ID = "globaltimes"
    SITE_NAME = "Global Times"
    SITE_URL = "https://www.globaltimes.cn"
    LANGUAGE = "en"
    REGION = "cn"
    GROUP = "F"

    # --- URL discovery ---
    SITEMAP_URL = "https://www.globaltimes.cn/sitemap.xml"

    # --- Selectors ---
    # Globaltimes uses a jQuery-based template; title in h3 header area
    TITLE_CSS = "h3"
    TITLE_CSS_FALLBACK = "h1"
    BODY_CSS = "div.article_right"
    BODY_CSS_FALLBACK = "div.article_content"
    DATE_CSS = ""  # Date from sitemap news:publication_date or byline
    AUTHOR_CSS = ""  # Byline pattern: "By Global Times"
    ARTICLE_LINK_CSS = "a[href*='/page/']"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, nav, aside, footer, "
        "div.related_articles, div[class*='share'], "
        "div[class*='ad'], div.article_bottom"
    )

    SECTION_URLS = [
        "https://www.globaltimes.cn/china/index.html",
        "https://www.globaltimes.cn/opinion/",
        "https://www.globaltimes.cn/source/index.html",
        "https://www.globaltimes.cn/life/index.html",
    ]

    # --- Rate limiting ---
    RATE_LIMIT_SECONDS = 2.0
    MAX_REQUESTS_PER_HOUR = 1800
    JITTER_SECONDS = 0.0

    # --- Anti-block (LOW) ---
    ANTI_BLOCK_TIER = 1
    UA_TIER = 1
    REQUIRES_PROXY = False
    BOT_BLOCK_LEVEL = "LOW"

    CHARSET = "utf-8"

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article from Global Times HTML."""
        from bs4 import BeautifulSoup
        import re

        soup = BeautifulSoup(html, "lxml")

        # Title
        title = ""
        title_el = soup.select_one(self.TITLE_CSS)
        if not title_el:
            title_el = soup.select_one(self.TITLE_CSS_FALLBACK)
        if title_el:
            title = title_el.get_text(strip=True)
        if not title:
            title = self._extract_meta_content(soup, "og:title")

        # Body -- use trafilatura-style extraction from article area
        body = ""
        body_el = soup.select_one(self.BODY_CSS)
        if not body_el:
            body_el = soup.select_one(self.BODY_CSS_FALLBACK)
        if body_el:
            body = self._clean_body_text(body_el)

        # Date: try byline pattern "Published: Feb 26, 2026 11:59 AM"
        published_at = None
        byline_match = re.search(r"Published:\s*(.+?)(?:\n|$)", html)
        if byline_match:
            published_at = self.normalize_date(byline_match.group(1).strip())
        if not published_at:
            meta_date = self._extract_meta_content(soup, "article:published_time")
            if meta_date:
                published_at = self.normalize_date(meta_date)

        # Author: pattern "By Global Times" or "By {Name}"
        author = None
        author_match = re.search(r"By\s+(.+?)\s+Published:", html)
        if author_match:
            author = author_match.group(1).strip()
        if not author:
            author = self._extract_meta_content(soup, "author") or None

        # Category from breadcrumb
        category = None
        breadcrumb = soup.select("div.breadcrumb a")
        if len(breadcrumb) > 1:
            category = breadcrumb[-1].get_text(strip=True)
        if not category:
            category = self._extract_category_from_url(url)

        return {
            "title": title,
            "body": body,
            "published_at": published_at,
            "author": author,
            "category": category,
            "is_paywall_truncated": False,
        }

    def get_section_urls(self) -> list[str]:
        return list(self.SECTION_URLS)

    def _extract_category_from_url(self, url: str, segment_index: int = 1) -> str | None:
        """Extract category from globaltimes.cn URL path."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        parts = [p for p in parsed.path.split("/") if p]
        # URL: /page/YYYYMM/{id}.shtml -- no category in URL
        # Section pages: /china/index.html -> "china"
        if parts and parts[0] not in ("page",):
            return parts[0]
        return None
