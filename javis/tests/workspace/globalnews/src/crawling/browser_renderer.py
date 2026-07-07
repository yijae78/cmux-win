"""Subprocess-based browser renderer for JS-heavy and paywall sites.

Executes Patchright (or Playwright) in a separate subprocess to avoid
sync/async conflicts with the synchronous crawling pipeline. Returns
rendered HTML as a string.

Design decisions:
    - Subprocess isolation: The main pipeline is synchronous (httpx).
      Patchright is async. Running async code in a subprocess avoids
      event loop conflicts and provides process-level failure isolation.
    - Fresh browser context: Each render uses a new browser context with
      no cookies or session state. This gives metered-paywall sites a
      "first visit" experience that often shows full article content.
    - Timeout enforcement: subprocess.run with timeout_seconds provides
      a hard kill guarantee. No hung browser process can stall the pipeline.
    - Patchright preference: Patchright patches Playwright at the C++ level
      for undetectable automation. Falls back to Playwright if unavailable.

Reference: Phase 0 V1-V3 findings — Wayback Machine is ineffective for
    hard paywall sites (archived content is also paywalled). Browser
    rendering with fresh context is the primary strategy.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import textwrap

logger = logging.getLogger(__name__)

# Subprocess timeout (seconds). Generous to allow for slow page loads.
_DEFAULT_TIMEOUT_S = 45

# The inline script executed in a subprocess.
# It imports patchright (or playwright), launches a browser, fetches
# the page, waits for content to settle, and prints the HTML to stdout.
_RENDER_SCRIPT = textwrap.dedent("""\
    import asyncio
    import json
    import sys

    async def render(url, timeout_ms, wait_until, wait_after_ms):
        pw_mod = None
        engine_name = "unknown"
        try:
            from patchright.async_api import async_playwright
            engine_name = "patchright"
        except ImportError:
            try:
                from playwright.async_api import async_playwright
                engine_name = "playwright"
            except ImportError:
                print(json.dumps({"error": "no_browser_engine",
                                  "detail": "Neither patchright nor playwright installed"}),
                      file=sys.stderr)
                sys.exit(1)

        pw = await async_playwright().start()
        try:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/New_York",
            )
            context.set_default_timeout(timeout_ms)
            context.set_default_navigation_timeout(timeout_ms)
            page = await context.new_page()

            try:
                await page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            except Exception as nav_err:
                # Some sites throw on navigation but still load content
                print(json.dumps({"warning": f"navigation: {nav_err}"}),
                      file=sys.stderr)

            # Wait for JS to settle (hydration, lazy loading)
            if wait_after_ms > 0:
                await asyncio.sleep(wait_after_ms / 1000.0)

            html = await page.content()
            # Output HTML to stdout as JSON-encoded string (safe for any content)
            sys.stdout.write(json.dumps({"html": html, "engine": engine_name}))
        finally:
            await pw.stop()

    url = sys.argv[1]
    timeout_ms = int(sys.argv[2]) if len(sys.argv) > 2 else 30000
    wait_until = sys.argv[3] if len(sys.argv) > 3 else "domcontentloaded"
    wait_after_ms = int(sys.argv[4]) if len(sys.argv) > 4 else 2000

    asyncio.run(render(url, timeout_ms, wait_until, wait_after_ms))
""")


class BrowserRenderer:
    """Renders a URL using a headless browser in a subprocess.

    Each call to ``render()`` launches a fresh browser process with no
    cookies or session state. This provides:
    - Process isolation (no async conflict with sync pipeline)
    - Clean state (metered paywalls see a "first visit")
    - Hard timeout (subprocess.run kills hung processes)

    Usage::

        renderer = BrowserRenderer()
        html = renderer.render("https://ft.com/content/some-article")
        if html is not None:
            # Use html for extraction
            ...

    Attributes:
        python_path: Path to the Python interpreter with patchright/playwright.
        timeout_s: Hard subprocess timeout in seconds.
        navigation_timeout_ms: Playwright navigation timeout in milliseconds.
        wait_until: Playwright wait_until strategy.
        wait_after_ms: Extra wait after page load for JS hydration.
    """

    # After this many consecutive failures for a source_id, skip rendering
    _MAX_CONSECUTIVE_FAILURES = 3

    def __init__(
        self,
        python_path: str | None = None,
        timeout_s: int = _DEFAULT_TIMEOUT_S,
        navigation_timeout_ms: int = 30_000,
        wait_until: str = "domcontentloaded",
        wait_after_ms: int = 2000,
    ) -> None:
        # Use the same Python that the pipeline runs on (venv-aware)
        self._python = python_path or sys.executable
        self._timeout_s = timeout_s
        self._nav_timeout_ms = navigation_timeout_ms
        self._wait_until = wait_until
        self._wait_after_ms = wait_after_ms
        # P1-4: Per-site consecutive failure counter for early bail-out
        self._failure_counts: dict[str, int] = {}

    def render(self, url: str, source_id: str | None = None) -> str | None:
        """Render a URL and return the HTML content.

        Args:
            url: The URL to render in a headless browser.
            source_id: Optional site identifier for per-site failure tracking.
                If a site fails _MAX_CONSECUTIVE_FAILURES times in a row,
                subsequent render calls are skipped (early bail-out).

        Returns:
            Rendered HTML string, or None if rendering failed.
        """
        # P1-4: Early bail-out for sites with repeated failures
        if source_id and self._failure_counts.get(source_id, 0) >= self._MAX_CONSECUTIVE_FAILURES:
            logger.info(
                "browser_render_skipped source_id=%s consecutive_failures=%d",
                source_id, self._failure_counts[source_id],
            )
            return None

        try:
            result = subprocess.run(
                [
                    self._python, "-c", _RENDER_SCRIPT,
                    url,
                    str(self._nav_timeout_ms),
                    self._wait_until,
                    str(self._wait_after_ms),
                ],
                capture_output=True,
                text=True,
                timeout=self._timeout_s,
            )

            if result.returncode != 0:
                stderr_msg = result.stderr.strip()[:500] if result.stderr else "no stderr"
                logger.warning(
                    "browser_render_failed url=%s returncode=%d stderr=%s",
                    url, result.returncode, stderr_msg,
                )
                self._record_failure(source_id)
                return None

            if not result.stdout.strip():
                logger.warning("browser_render_empty url=%s", url)
                self._record_failure(source_id)
                return None

            output = json.loads(result.stdout)
            html = output.get("html", "")
            engine = output.get("engine", "unknown")

            if not html or len(html) < 100:
                logger.warning(
                    "browser_render_too_short url=%s length=%d",
                    url, len(html),
                )
                self._record_failure(source_id)
                return None

            logger.info(
                "browser_render_success url=%s engine=%s length=%d",
                url, engine, len(html),
            )
            self._record_success(source_id)
            return html

        except subprocess.TimeoutExpired:
            logger.warning(
                "browser_render_timeout url=%s timeout_s=%d",
                url, self._timeout_s,
            )
            self._record_failure(source_id)
            return None
        except json.JSONDecodeError:
            logger.warning("browser_render_invalid_json url=%s", url)
            self._record_failure(source_id)
            return None
        except Exception as e:
            logger.warning("browser_render_error url=%s error=%s", url, str(e))
            self._record_failure(source_id)
            return None

    def _record_failure(self, source_id: str | None) -> None:
        """Increment consecutive failure counter for a source."""
        if source_id:
            self._failure_counts[source_id] = self._failure_counts.get(source_id, 0) + 1

    def _record_success(self, source_id: str | None) -> None:
        """Reset consecutive failure counter on success."""
        if source_id:
            self._failure_counts[source_id] = 0

    def is_available(self) -> bool:
        """Check if a browser engine (patchright or playwright) is installed.

        Returns:
            True if at least one browser engine is available.
        """
        try:
            result = subprocess.run(
                [self._python, "-c",
                 "try:\n import patchright; print('patchright')\n"
                 "except ImportError:\n"
                 " try:\n  import playwright; print('playwright')\n"
                 " except ImportError:\n  print('none')"],
                capture_output=True, text=True, timeout=10,
            )
            engine = result.stdout.strip()
            return engine in ("patchright", "playwright")
        except Exception:
            return False
