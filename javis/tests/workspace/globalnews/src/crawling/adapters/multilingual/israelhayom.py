"""Israel Hayom (israelhayom.com) adapter -- Israeli English-language daily.

Site #44, Group G (Europe/ME).
Language: English (en). Encoding: UTF-8.
Primary method: RSS (WordPress with content:encoded -- FULL body in RSS).
Rate limit: 2s. Bot-blocking: LOW (no robots.txt).
CMS: WordPress / JNews theme.

Key advantage: Full article body available in RSS content:encoded field.
This means zero article page fetches are needed for body extraction.

RTL note: English edition only -- no RTL handling required for primary scope.
Strip bidi marks from mixed English/Hebrew content.

Reference:
    Step 6 crawl-strategy-global.md, Section 44.
"""

from __future__ import annotations

from typing import Any

from src.crawling.adapters.base_adapter import BaseSiteAdapter
from src.crawling.adapters.multilingual._ml_utils import strip_rtl_marks


class IsraelHayomAdapter(BaseSiteAdapter):
    """Adapter for Israel Hayom (israelhayom.com)."""

    SITE_ID = "israelhayom"
    SITE_NAME = "Israel Hayom"
    SITE_URL = "https://www.israelhayom.com"
    LANGUAGE = "en"
    REGION = "il"
    GROUP = "G"

    # --- URL discovery ---
    RSS_URL = "https://www.israelhayom.com/feed"
    SITEMAP_URL = "/sitemap.xml"

    # --- Selectors (WordPress/JNews, verified via live fetch) ---
    TITLE_CSS = "h1.jeg_post_title"
    TITLE_CSS_FALLBACK = "h1"
    BODY_CSS = "div.content-inner, div.entry-content"
    BODY_CSS_FALLBACK = "div.jeg_inner_content"
    DATE_CSS = ""  # Use Schema.org datePublished
    AUTHOR_CSS = "a.jeg_meta_author"
    ARTICLE_LINK_CSS = "h3.jeg_post_title a"

    BODY_EXCLUDE_CSS = (
        "script, style, iframe, nav, aside, footer, "
        "div.jeg_post_tags, div.jeg_share_bottom, "
        "div.jeg_authorbox, div.jeg_post_related, "
        "div.jeg_ad, div[class*='newsletter'], "
        "div.comment-respond, div.jnews_inline_related_post"
    )

    SECTION_URLS = [
        "https://www.israelhayom.com/category/news/",
        "https://www.israelhayom.com/category/politics/",
        "https://www.israelhayom.com/category/business/",
        "https://www.israelhayom.com/category/israel-inside/",
        "https://www.israelhayom.com/category/columns/",
    ]

    # --- Rate limiting ---
    RATE_LIMIT_SECONDS = 2.0
    MAX_REQUESTS_PER_HOUR = 1800
    JITTER_SECONDS = 0.0

    # --- Anti-block (LOW, no robots.txt) ---
    ANTI_BLOCK_TIER = 1
    UA_TIER = 1
    REQUIRES_PROXY = False
    BOT_BLOCK_LEVEL = "LOW"

    CHARSET = "utf-8"

    def extract_article(self, html: str, url: str) -> dict[str, Any]:
        """Extract article from Israel Hayom HTML.

        Note: For RSS-based extraction, the article body is available
        in content:encoded -- this method is for HTML page fallback.
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")

        # JSON-LD for metadata
        json_ld = self._extract_json_ld(soup)

        # Title
        title = ""
        title_el = soup.select_one(self.TITLE_CSS)
        if not title_el:
            title_el = soup.select_one(self.TITLE_CSS_FALLBACK)
        if title_el:
            title = strip_rtl_marks(title_el.get_text(strip=True))
        if not title:
            title = strip_rtl_marks(self._extract_meta_content(soup, "og:title"))

        # Body
        body = ""
        body_el = soup.select_one(self.BODY_CSS)
        if not body_el:
            body_el = soup.select_one(self.BODY_CSS_FALLBACK)
        if body_el:
            body = strip_rtl_marks(self._clean_body_text(body_el))

        # Date: Schema.org > meta
        published_at = None
        date_str = json_ld.get("datePublished", "")
        if date_str:
            published_at = self.normalize_date(date_str)
        if not published_at:
            meta_date = self._extract_meta_content(soup, "article:published_time")
            if meta_date:
                published_at = self.normalize_date(meta_date)

        # Author
        author = None
        author_el = soup.select_one(self.AUTHOR_CSS)
        if author_el:
            author = strip_rtl_marks(author_el.get_text(strip=True))
        if not author:
            author_data = json_ld.get("author")
            if isinstance(author_data, dict):
                author = author_data.get("name")
            elif isinstance(author_data, str):
                author = author_data
        if not author:
            author = self._extract_meta_content(soup, "author") or None

        # Category from JNews badge or URL
        category = None
        cat_el = soup.select_one("span.jeg_post_category a")
        if cat_el:
            category = cat_el.get_text(strip=True)
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

    def extract_from_rss_content(self, content_encoded: str, rss_item: dict[str, str]) -> dict[str, Any]:
        """Extract article fields from RSS content:encoded field.

        Israel Hayom provides FULL article body in RSS content:encoded,
        avoiding the need for individual page fetches.

        Args:
            content_encoded: HTML content from <content:encoded> CDATA.
            rss_item: Dict with RSS fields (title, link, dc:creator, pubDate, category).

        Returns:
            Article dict with all fields populated from RSS.
        """
        from bs4 import BeautifulSoup

        # Parse the content:encoded HTML
        soup = BeautifulSoup(content_encoded, "lxml")
        body = strip_rtl_marks(soup.get_text(separator="\n", strip=True))

        # Date from RSS pubDate (RFC 822)
        published_at = None
        pub_date = rss_item.get("pubDate", "")
        if pub_date:
            published_at = self.normalize_date(pub_date)

        # Categories from RSS (multiple <category> tags)
        categories = rss_item.get("category", "")
        category = categories.split(",")[0].strip() if categories else None

        return {
            "title": strip_rtl_marks(rss_item.get("title", "")),
            "body": body,
            "published_at": published_at,
            "author": strip_rtl_marks(rss_item.get("dc:creator", "")),
            "category": category,
            "is_paywall_truncated": False,
        }
