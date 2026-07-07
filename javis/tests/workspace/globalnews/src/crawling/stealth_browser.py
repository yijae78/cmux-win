"""Stealth Browser Management for the GlobalNews crawling system.

Wraps Playwright/Patchright with anti-detection features for Tier 3-4
escalation. Provides browser fingerprint randomization, human-like
behavior simulation, and cookie/session management per instance.

Capabilities:
    - Tier 3: Standard Playwright headless browser for JS rendering.
    - Tier 4: Patchright with fingerprint randomization (canvas, WebGL, fonts,
      viewport, timezone, language matching target site region).
    - "Total War" mode: Patchright stealth for Extreme-difficulty sites.
    - Human behavior simulation: random scroll, mouse movement, wait jitter.
    - Graceful lifecycle: create -> use -> cleanup (context manager support).

Reference: Step 5 Architecture Blueprint, Crawling Layer.
Reference: Step 6 Crawling Strategies, Tier 3-4 assignments.
Reference: Step 2 Tech Validation, Patchright 1.58 GO verdict.
"""

from __future__ import annotations

import asyncio
import logging
import random
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from src.config.constants import (
    PLAYWRIGHT_TIMEOUT_MS,
    PLAYWRIGHT_NAVIGATION_TIMEOUT_MS,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

@dataclass(frozen=True)
class BrowserProfile:
    """Browser fingerprint profile for stealth mode.

    Each profile represents a realistic browser configuration to reduce
    fingerprint-based detection.

    Attributes:
        viewport_width: Browser viewport width in pixels.
        viewport_height: Browser viewport height in pixels.
        screen_width: Screen resolution width.
        screen_height: Screen resolution height.
        user_agent: The User-Agent string to use.
        locale: Browser locale (e.g., "en-US", "ko-KR").
        timezone_id: IANA timezone (e.g., "America/New_York", "Asia/Seoul").
        color_scheme: Preferred color scheme ("light" or "dark").
        device_scale_factor: Device pixel ratio (1.0, 1.5, 2.0, etc.).
        has_touch: Whether to emulate touch support.
        platform: Navigator.platform value.
    """
    viewport_width: int = 1920
    viewport_height: int = 1080
    screen_width: int = 1920
    screen_height: int = 1080
    user_agent: str = ""
    locale: str = "en-US"
    timezone_id: str = "America/New_York"
    color_scheme: str = "light"
    device_scale_factor: float = 1.0
    has_touch: bool = False
    platform: str = "Win32"


# Common desktop viewport sizes (from real browser usage statistics)
_VIEWPORT_SIZES: list[tuple[int, int]] = [
    (1920, 1080),
    (1366, 768),
    (1536, 864),
    (1440, 900),
    (1280, 720),
    (1600, 900),
    (2560, 1440),
    (1280, 800),
    (1680, 1050),
    (1360, 768),
]

# Platform/OS combos
_PLATFORMS: list[tuple[str, str]] = [
    ("Win32", "Windows"),
    ("MacIntel", "macOS"),
    ("Linux x86_64", "Linux"),
]

# Locale/timezone pairings by target region
_REGION_PROFILES: dict[str, dict[str, Any]] = {
    "kr": {"locale": "ko-KR", "timezone_id": "Asia/Seoul"},
    "us": {"locale": "en-US", "timezone_id": "America/New_York"},
    "uk": {"locale": "en-GB", "timezone_id": "Europe/London"},
    "cn": {"locale": "zh-CN", "timezone_id": "Asia/Shanghai"},
    "jp": {"locale": "ja-JP", "timezone_id": "Asia/Tokyo"},
    "de": {"locale": "de-DE", "timezone_id": "Europe/Berlin"},
    "fr": {"locale": "fr-FR", "timezone_id": "Europe/Paris"},
    "me": {"locale": "ar-SA", "timezone_id": "Asia/Riyadh"},
    "in": {"locale": "en-IN", "timezone_id": "Asia/Kolkata"},
    "tw": {"locale": "zh-TW", "timezone_id": "Asia/Taipei"},
    "il": {"locale": "he-IL", "timezone_id": "Asia/Jerusalem"},
    "ru": {"locale": "ru-RU", "timezone_id": "Europe/Moscow"},
    "mx": {"locale": "es-MX", "timezone_id": "America/Mexico_City"},
    "sg": {"locale": "en-SG", "timezone_id": "Asia/Singapore"},
}


def generate_random_profile(
    region: str = "us",
    user_agent: str = "",
) -> BrowserProfile:
    """Generate a randomized browser profile matching a target region.

    Creates a realistic-looking browser fingerprint by combining random
    viewport sizes, platform strings, and region-appropriate locale/timezone.

    Args:
        region: Target site region code (e.g., "kr", "us", "jp").
        user_agent: User-Agent string to use (empty = default Playwright UA).

    Returns:
        A randomized BrowserProfile.
    """
    viewport = random.choice(_VIEWPORT_SIZES)
    platform_str, _ = random.choice(_PLATFORMS)
    region_cfg = _REGION_PROFILES.get(region, _REGION_PROFILES["us"])

    # Slight variation in screen size vs viewport (realistic: screen >= viewport)
    screen_w = viewport[0] + random.choice([0, 0, 0, 80, 160])
    screen_h = viewport[1] + random.choice([0, 0, 0, 40, 80])

    return BrowserProfile(
        viewport_width=viewport[0],
        viewport_height=viewport[1],
        screen_width=screen_w,
        screen_height=screen_h,
        user_agent=user_agent,
        locale=region_cfg["locale"],
        timezone_id=region_cfg["timezone_id"],
        color_scheme=random.choice(["light", "light", "light", "dark"]),
        device_scale_factor=random.choice([1.0, 1.0, 1.25, 1.5, 2.0]),
        has_touch=False,
        platform=platform_str,
    )


# =============================================================================
# Stealth Browser
# =============================================================================

class StealthBrowser:
    """Stealth browser wrapper for Playwright/Patchright.

    Provides anti-detection browser automation for Tier 3-4 escalation.
    Supports both standard Playwright (Tier 3) and Patchright with
    fingerprint randomization (Tier 4).

    Lifecycle:
        browser = StealthBrowser(use_patchright=True)
        await browser.start()
        try:
            html = await browser.fetch_page("https://example.com")
        finally:
            await browser.close()

    Or use as async context manager:
        async with StealthBrowser.create(use_patchright=True) as browser:
            html = await browser.fetch_page("https://example.com")

    Thread-safety: NOT thread-safe. Use one instance per async task.

    Attributes:
        use_patchright: Whether to use Patchright (True) or Playwright (False).
        profile: The browser fingerprint profile.
        headless: Whether to run headless (True) or headed (False).
    """

    def __init__(
        self,
        use_patchright: bool = False,
        profile: BrowserProfile | None = None,
        headless: bool = True,
        region: str = "us",
        user_agent: str = "",
        timeout_ms: int = PLAYWRIGHT_TIMEOUT_MS,
        navigation_timeout_ms: int = PLAYWRIGHT_NAVIGATION_TIMEOUT_MS,
    ) -> None:
        """Initialize a stealth browser instance (does not start yet).

        Args:
            use_patchright: Use Patchright for CDP stealth bypass (Tier 4).
            profile: Browser fingerprint profile (auto-generated if None).
            headless: Run in headless mode.
            region: Target site region for locale/timezone matching.
            user_agent: User-Agent override (empty = browser default).
            timeout_ms: Default timeout for operations in milliseconds.
            navigation_timeout_ms: Navigation timeout in milliseconds.
        """
        self.use_patchright = use_patchright
        self.profile = profile or generate_random_profile(region=region, user_agent=user_agent)
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.navigation_timeout_ms = navigation_timeout_ms

        # Internal state -- set by start()
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None
        self._started = False

    @classmethod
    @asynccontextmanager
    async def create(
        cls,
        use_patchright: bool = False,
        profile: BrowserProfile | None = None,
        headless: bool = True,
        region: str = "us",
        user_agent: str = "",
        **kwargs: Any,
    ) -> AsyncIterator[StealthBrowser]:
        """Async context manager factory for StealthBrowser.

        Handles start() and close() automatically.

        Args:
            use_patchright: Use Patchright for stealth.
            profile: Browser profile override.
            headless: Headless mode.
            region: Target site region.
            user_agent: User-Agent override.
            **kwargs: Additional kwargs passed to __init__.

        Yields:
            A started StealthBrowser instance.
        """
        browser = cls(
            use_patchright=use_patchright,
            profile=profile,
            headless=headless,
            region=region,
            user_agent=user_agent,
            **kwargs,
        )
        await browser.start()
        try:
            yield browser
        finally:
            await browser.close()

    async def start(self) -> None:
        """Start the browser and create a context with stealth settings.

        Imports Playwright or Patchright dynamically to avoid hard dependencies
        when the module is not installed.

        Raises:
            ImportError: If the required browser package is not installed.
            RuntimeError: If the browser fails to launch.
        """
        if self._started:
            logger.warning("StealthBrowser.start() called but already started")
            return

        try:
            if self.use_patchright:
                from patchright.async_api import async_playwright
                logger.info("Starting Patchright stealth browser")
            else:
                from playwright.async_api import async_playwright
                logger.info("Starting Playwright browser")

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
            )

            # Build context options from profile
            context_options: dict[str, Any] = {
                "viewport": {
                    "width": self.profile.viewport_width,
                    "height": self.profile.viewport_height,
                },
                "screen": {
                    "width": self.profile.screen_width,
                    "height": self.profile.screen_height,
                },
                "locale": self.profile.locale,
                "timezone_id": self.profile.timezone_id,
                "color_scheme": self.profile.color_scheme,
                "device_scale_factor": self.profile.device_scale_factor,
                "has_touch": self.profile.has_touch,
            }

            if self.profile.user_agent:
                context_options["user_agent"] = self.profile.user_agent

            self._context = await self._browser.new_context(**context_options)
            self._context.set_default_timeout(self.timeout_ms)
            self._context.set_default_navigation_timeout(self.navigation_timeout_ms)

            self._page = await self._context.new_page()
            self._started = True

            logger.info(
                "StealthBrowser started",
                extra={
                    "patchright": self.use_patchright,
                    "viewport": f"{self.profile.viewport_width}x{self.profile.viewport_height}",
                    "locale": self.profile.locale,
                    "timezone": self.profile.timezone_id,
                },
            )
        except ImportError as e:
            pkg = "patchright" if self.use_patchright else "playwright"
            logger.error(f"Browser package not installed: {pkg}")
            raise ImportError(
                f"{pkg} is required for Tier {'4' if self.use_patchright else '3'} "
                f"escalation. Install with: pip install {pkg}"
            ) from e
        except Exception as e:
            logger.error("Failed to start stealth browser", exc_info=True)
            await self.close()
            raise RuntimeError(f"Browser launch failed: {e}") from e

    async def close(self) -> None:
        """Close the browser and clean up resources.

        Safe to call multiple times. Catches and logs cleanup errors.
        """
        if not self._started and self._playwright is None:
            return

        errors: list[str] = []

        if self._page is not None:
            try:
                await self._page.close()
            except Exception as e:
                errors.append(f"page.close: {e}")
            self._page = None

        if self._context is not None:
            try:
                await self._context.close()
            except Exception as e:
                errors.append(f"context.close: {e}")
            self._context = None

        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception as e:
                errors.append(f"browser.close: {e}")
            self._browser = None

        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception as e:
                errors.append(f"playwright.stop: {e}")
            self._playwright = None

        self._started = False

        if errors:
            logger.warning("StealthBrowser cleanup errors", extra={"errors": errors})
        else:
            logger.info("StealthBrowser closed cleanly")

    # -------------------------------------------------------------------------
    # Page Interaction
    # -------------------------------------------------------------------------

    async def fetch_page(
        self,
        url: str,
        wait_until: str = "domcontentloaded",
        simulate_human: bool = True,
    ) -> str:
        """Navigate to a URL and return the rendered HTML.

        Optionally simulates human-like behavior (scrolling, mouse movement)
        to reduce bot detection probability.

        Args:
            url: The URL to navigate to.
            wait_until: Playwright wait condition ("domcontentloaded", "load",
                "networkidle").
            simulate_human: Whether to simulate human behavior after page load.

        Returns:
            The rendered page HTML as a string.

        Raises:
            RuntimeError: If the browser is not started.
        """
        if not self._started or self._page is None:
            raise RuntimeError("StealthBrowser not started. Call start() first.")

        logger.debug("Fetching page", extra={"url": url, "wait_until": wait_until})

        response = await self._page.goto(url, wait_until=wait_until)

        if simulate_human:
            await self._simulate_human_behavior()

        # Wait a bit for dynamic content to load
        await asyncio.sleep(random.uniform(0.5, 1.5))

        html = await self._page.content()
        status = response.status if response else 0

        logger.debug(
            "Page fetched",
            extra={"url": url, "status": status, "html_length": len(html)},
        )
        return html

    async def fetch_page_with_status(
        self,
        url: str,
        wait_until: str = "domcontentloaded",
        simulate_human: bool = True,
    ) -> tuple[str, int, dict[str, str]]:
        """Navigate to a URL and return HTML, status code, and headers.

        Extended version of fetch_page() that also captures the HTTP status
        and response headers for block detection analysis.

        Args:
            url: The URL to navigate to.
            wait_until: Playwright wait condition.
            simulate_human: Whether to simulate human behavior.

        Returns:
            Tuple of (html, status_code, headers_dict).

        Raises:
            RuntimeError: If the browser is not started.
        """
        if not self._started or self._page is None:
            raise RuntimeError("StealthBrowser not started. Call start() first.")

        response = await self._page.goto(url, wait_until=wait_until)

        if simulate_human:
            await self._simulate_human_behavior()

        await asyncio.sleep(random.uniform(0.5, 1.5))

        html = await self._page.content()
        status = response.status if response else 0
        headers = dict(response.headers) if response else {}

        return html, status, headers

    async def evaluate_js(self, expression: str) -> Any:
        """Evaluate a JavaScript expression in the page context.

        Args:
            expression: JavaScript code to evaluate.

        Returns:
            The result of the evaluation.

        Raises:
            RuntimeError: If the browser is not started.
        """
        if not self._started or self._page is None:
            raise RuntimeError("StealthBrowser not started. Call start() first.")
        return await self._page.evaluate(expression)

    async def get_cookies(self) -> list[dict[str, Any]]:
        """Get all cookies from the current browser context.

        Returns:
            List of cookie dictionaries.
        """
        if not self._started or self._context is None:
            return []
        return await self._context.cookies()

    async def clear_cookies(self) -> None:
        """Clear all cookies from the current browser context."""
        if self._context is not None:
            await self._context.clear_cookies()
            logger.debug("Cleared browser cookies")

    async def set_cookies(self, cookies: list[dict[str, Any]]) -> None:
        """Set cookies in the current browser context.

        Args:
            cookies: List of cookie dictionaries with name, value, domain, path.
        """
        if self._context is not None:
            await self._context.add_cookies(cookies)

    # -------------------------------------------------------------------------
    # Human Behavior Simulation
    # -------------------------------------------------------------------------

    async def _simulate_human_behavior(self) -> None:
        """Simulate human-like interaction with the page.

        Performs a random subset of:
        - Mouse movement to random positions
        - Smooth scrolling down the page
        - Brief pauses between actions
        """
        if self._page is None:
            return

        try:
            # Random mouse movement (1-3 movements)
            for _ in range(random.randint(1, 3)):
                x = random.randint(100, self.profile.viewport_width - 100)
                y = random.randint(100, self.profile.viewport_height - 100)
                await self._page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.1, 0.3))

            # Smooth scroll down (simulate reading)
            scroll_distance = random.randint(200, 800)
            scroll_steps = random.randint(3, 6)
            step_size = scroll_distance // scroll_steps
            for _ in range(scroll_steps):
                await self._page.mouse.wheel(0, step_size)
                await asyncio.sleep(random.uniform(0.1, 0.4))

            # Occasionally scroll back up slightly
            if random.random() < 0.3:
                await self._page.mouse.wheel(0, -random.randint(50, 150))
                await asyncio.sleep(random.uniform(0.2, 0.5))

        except Exception:
            # Human simulation failures should never crash the page fetch
            logger.debug("Human behavior simulation error (non-fatal)", exc_info=True)

    # -------------------------------------------------------------------------
    # Session Management
    # -------------------------------------------------------------------------

    async def new_session(self, profile: BrowserProfile | None = None) -> None:
        """Create a fresh browser context (new cookies, new fingerprint).

        Used for session cycling at Tier 2+ when the current session is
        suspected to be fingerprinted.

        Args:
            profile: New browser profile (auto-generates one if None).
        """
        if not self._started or self._browser is None:
            raise RuntimeError("StealthBrowser not started. Call start() first.")

        # Update profile
        if profile is not None:
            self.profile = profile

        # Close old context
        if self._page is not None:
            try:
                await self._page.close()
            except Exception:
                pass
        if self._context is not None:
            try:
                await self._context.close()
            except Exception:
                pass

        # Create new context with updated profile
        context_options: dict[str, Any] = {
            "viewport": {
                "width": self.profile.viewport_width,
                "height": self.profile.viewport_height,
            },
            "screen": {
                "width": self.profile.screen_width,
                "height": self.profile.screen_height,
            },
            "locale": self.profile.locale,
            "timezone_id": self.profile.timezone_id,
            "color_scheme": self.profile.color_scheme,
            "device_scale_factor": self.profile.device_scale_factor,
            "has_touch": self.profile.has_touch,
        }

        if self.profile.user_agent:
            context_options["user_agent"] = self.profile.user_agent

        self._context = await self._browser.new_context(**context_options)
        self._context.set_default_timeout(self.timeout_ms)
        self._context.set_default_navigation_timeout(self.navigation_timeout_ms)
        self._page = await self._context.new_page()

        logger.info(
            "New browser session created",
            extra={
                "viewport": f"{self.profile.viewport_width}x{self.profile.viewport_height}",
                "locale": self.profile.locale,
            },
        )

    @property
    def is_started(self) -> bool:
        """Whether the browser is currently running."""
        return self._started

    def __repr__(self) -> str:
        mode = "Patchright" if self.use_patchright else "Playwright"
        state = "running" if self._started else "stopped"
        return (
            f"StealthBrowser(mode={mode}, state={state}, "
            f"viewport={self.profile.viewport_width}x{self.profile.viewport_height}, "
            f"locale={self.profile.locale})"
        )
