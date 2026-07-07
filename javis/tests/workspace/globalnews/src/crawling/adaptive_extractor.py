"""Adaptive content extractor — CSS selector-based extraction at runtime.

When the standard extraction chain (Fundus/Trafilatura/CSS) fails to extract
article body from browser-rendered HTML, this module tries multiple CSS
selector strategies and heuristic paragraph extraction.

Design decisions:
    - Deterministic only: No exec(), no LLM-generated code execution.
      All extraction uses CSS selectors via BeautifulSoup.
    - Caching: Successful selectors are cached per source_id so the same
      strategy is reused for subsequent articles from the same site.
    - 4-stage fallback: cached → known → generic → heuristic paragraphs.

Security:
    - No code execution (exec/eval removed — P1-3).
    - BeautifulSoup CSS selectors only. No network, file, or system calls.

Reference: User requirement — "막히면 알아서 '실시간'으로 파이썬 코드를 짜서 우회"
"""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

# Maximum body length from adaptive extraction (prevent memory bombs)
_MAX_BODY_LENGTH = 500_000

# Common article body CSS selectors by site pattern
_KNOWN_SELECTORS: dict[str, list[str]] = {
    "ft": ["div.article__content-body", "div.body-content", "article .body"],
    "nytimes": ["section[name='articleBody']", "div.StoryBodyCompanionColumn", "article p"],
    "wsj": ["div.article-content", "div.wsj-snippet-body", "section.article-body"],
    "bloomberg": ["div.body-content", "div.article-body__content", "article .body-copy"],
    "lemonde": ["div.article__content", "section.article__body", "article .article__paragraph"],
}

# Generic selectors tried when site-specific ones fail
_GENERIC_SELECTORS: list[str] = [
    "article",
    "[role='main'] p",
    "div.article-body",
    "div.post-content",
    "div.entry-content",
    "div.story-body",
    "main p",
]


class AdaptiveExtractor:
    """Tries multiple CSS selector strategies to extract article body.

    Maintains a per-source_id cache of successful selectors to avoid
    redundant analysis on subsequent articles.

    Usage::

        extractor = AdaptiveExtractor()
        body = extractor.extract_body(html, source_id="ft")
        if body:
            # Use extracted body
            ...
    """

    def __init__(
        self,
        known_selectors: dict[str, list[str]] | None = None,
    ) -> None:
        """Initialize the adaptive extractor.

        Args:
            known_selectors: Optional per-site CSS selectors override.
                If None, uses the module-level _KNOWN_SELECTORS defaults.
                Can be populated from sources.yaml when the config schema
                includes extraction.selectors per site.
        """
        self._known_selectors = known_selectors or _KNOWN_SELECTORS
        # Cache: source_id -> list of CSS selectors that worked
        self._selector_cache: dict[str, list[str]] = {}
        self._lock = threading.Lock()

    def extract_body(self, html: str, source_id: str) -> str | None:
        """Attempt to extract article body using adaptive selectors.

        Strategy:
        1. Try cached selectors for this source_id
        2. Try known selectors for this source_id
        3. Try generic article selectors
        4. Try heuristic paragraph extraction

        Args:
            html: Rendered HTML content.
            source_id: Site identifier for selector lookup/caching.

        Returns:
            Extracted body text, or None if all strategies fail.
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.warning("adaptive_extractor_no_bs4")
            return None

        soup = BeautifulSoup(html, "html.parser")

        # 1. Try cached selectors (lock for cache read)
        with self._lock:
            cached = self._selector_cache.get(source_id)
        if cached is not None:
            body = self._try_selectors(soup, cached)
            if body:
                return body

        # 2. Try known selectors for this source
        known = self._known_selectors.get(source_id, [])
        if known:
            body = self._try_selectors(soup, known)
            if body:
                with self._lock:
                    self._selector_cache[source_id] = known
                logger.info(
                    "adaptive_known_selector_hit source_id=%s len=%d",
                    source_id, len(body),
                )
                return body

        # 3. Try generic selectors
        body = self._try_selectors(soup, _GENERIC_SELECTORS)
        if body:
            with self._lock:
                self._selector_cache[source_id] = _GENERIC_SELECTORS
            logger.info(
                "adaptive_generic_selector_hit source_id=%s len=%d",
                source_id, len(body),
            )
            return body

        # 4. Heuristic: collect all <p> tags with substantial text
        body = self._heuristic_paragraph_extraction(soup)
        if body:
            logger.info(
                "adaptive_heuristic_hit source_id=%s len=%d",
                source_id, len(body),
            )
            return body

        logger.info("adaptive_extractor_failed source_id=%s", source_id)
        return None

    def _try_selectors(
        self, soup: Any, selectors: list[str]
    ) -> str | None:
        """Try a list of CSS selectors and return the first good result."""
        for selector in selectors:
            try:
                elements = soup.select(selector)
                if not elements:
                    continue

                # Extract text from all matching elements
                paragraphs = []
                for el in elements:
                    text = el.get_text(strip=True)
                    if text and len(text) > 20:
                        paragraphs.append(text)

                if paragraphs:
                    body = "\n\n".join(paragraphs)
                    if len(body) >= 100:
                        return body[:_MAX_BODY_LENGTH]
            except Exception:
                continue

        return None

    def _heuristic_paragraph_extraction(self, soup: Any) -> str | None:
        """Extract body by collecting substantial <p> tags.

        Heuristic: paragraphs with > 40 chars that aren't navigation/footer.
        """
        paragraphs = []
        for p in soup.find_all("p"):
            text = p.get_text(strip=True)
            if len(text) > 40:
                # Skip if parent is likely nav/footer/header
                parent = p.parent
                if parent and parent.name in ("nav", "footer", "header", "aside"):
                    continue
                parent_class = " ".join(parent.get("class", [])) if parent else ""
                if any(skip in parent_class.lower()
                       for skip in ("nav", "footer", "header", "sidebar", "menu", "cookie")):
                    continue
                paragraphs.append(text)

        if len(paragraphs) >= 3:
            body = "\n\n".join(paragraphs)
            if len(body) >= 200:
                return body[:_MAX_BODY_LENGTH]

        return None
