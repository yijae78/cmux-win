"""User-Agent rotation pool for the GlobalNews crawling system.

Implements a 4-tier UA system with 61+ static User-Agent strings covering
Chrome, Firefox, Safari, and Edge across Windows, macOS, Linux, and mobile
platforms. Weighted rotation matches real-world browser market share data.

Architecture Reference: Step 5 Blueprint Section 2.2 (Crawling Layer),
Step 6 Crawling Strategies — UA Pool (61+ static agents, 4-tier design).

Tier mapping:
    T1 — 1 bot UA (Googlebot) for LOW bot-blocking sites
    T2 — 10 desktop UAs (Chrome/Firefox latest) for MEDIUM blocking
    T3 — 50 diverse browser/OS combos for HIGH/EXTREME blocking
    T4 — Dynamic Patchright fingerprints (not in this pool; on-demand)

Usage:
    from src.crawling.ua_manager import UAManager
    manager = UAManager()
    ua = manager.get_ua("chosun")         # T2 site
    ua = manager.get_ua("nytimes")        # T3 site
    ua = manager.get_ua("nocutnews")      # T1 site
"""

from __future__ import annotations

import logging
import random
import threading
from dataclasses import dataclass, field
from typing import Any

from src.config.constants import UA_TIER_SIZES

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# UA Metadata Model
# ---------------------------------------------------------------------------

@dataclass
class UAEntry:
    """Parsed metadata for a single User-Agent string.

    Attributes:
        ua_string: The raw User-Agent header value.
        browser: Browser family name ("Chrome", "Firefox", "Safari", "Edge",
                 "Googlebot").
        browser_version: Major version integer (e.g., 131).
        os: Operating system name ("Windows", "macOS", "Linux", "iOS",
            "Android").
        os_version: OS version string (e.g., "10.0", "14.4.1").
        device_type: Device class ("desktop", "mobile", "bot").
        tier: UA tier assignment (1, 2, or 3).
        weight: Relative selection weight for weighted random sampling.
    """

    ua_string: str
    browser: str
    browser_version: int
    os: str
    os_version: str
    device_type: str
    tier: int
    weight: float = 1.0


# ---------------------------------------------------------------------------
# Static UA Pool Definition
# ---------------------------------------------------------------------------
#
# All UA strings are real fingerprints from browsers released within the last
# 12 months (Chrome 120-131 released Nov 2023 - Nov 2024; Firefox 120-133
# released Nov 2023 - Dec 2024; Safari 17.x on iOS/macOS 2023-2024;
# Edge 120-131 mirroring Chrome cadence).
#
# Distribution targets (T3 pool of 50):
#   Chrome  65%  →  Chrome Win 12 + Chrome Mac 8 + Chrome Linux 5 = 25 (~50%)
#   Firefox 20%  →  Firefox Win 6 + Firefox Mac 4 = 10 (20%)
#   Safari  10%  →  Safari Mac 6 + Safari iOS 5 = 11 (22%, 2 extras balance T2)
#   Edge     5%  →  Edge Win 4 = 4 (8%)
#
# T2 pool (10) is drawn from Chrome/Firefox latest only (modern desktop UAs).
# T1 pool (1) is Googlebot 2.1.
# ---------------------------------------------------------------------------

# T1: Bot UA (1 entry) — for LOW bot-blocking sites (9 sites)
_T1_UA: list[UAEntry] = [
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (compatible; Googlebot/2.1; "
            "+http://www.google.com/bot.html)"
        ),
        browser="Googlebot",
        browser_version=2,
        os="Linux",
        os_version="",
        device_type="bot",
        tier=1,
        weight=1.0,
    ),
]

# T2: 10 desktop UAs — Chrome/Firefox latest, for MEDIUM blocking (12 sites).
# These 10 are also included in T3 for completeness; the tier attribute
# marks them as T2-eligible.
_T2_UA: list[UAEntry] = [
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=131, os="Windows", os_version="10.0",
        device_type="desktop", tier=2, weight=2.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=130, os="Windows", os_version="10.0",
        device_type="desktop", tier=2, weight=2.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=129, os="Windows", os_version="10.0",
        device_type="desktop", tier=2, weight=1.5,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=131, os="macOS", os_version="10.15.7",
        device_type="desktop", tier=2, weight=2.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=130, os="macOS", os_version="10.15.7",
        device_type="desktop", tier=2, weight=1.5,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 11.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=131, os="Windows", os_version="11.0",
        device_type="desktop", tier=2, weight=2.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) "
            "Gecko/20100101 Firefox/133.0"
        ),
        browser="Firefox", browser_version=133, os="Windows", os_version="10.0",
        device_type="desktop", tier=2, weight=1.5,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) "
            "Gecko/20100101 Firefox/132.0"
        ),
        browser="Firefox", browser_version=132, os="Windows", os_version="10.0",
        device_type="desktop", tier=2, weight=1.5,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:133.0) "
            "Gecko/20100101 Firefox/133.0"
        ),
        browser="Firefox", browser_version=133, os="macOS", os_version="14.7",
        device_type="desktop", tier=2, weight=1.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 11.0; Win64; x64; rv:131.0) "
            "Gecko/20100101 Firefox/131.0"
        ),
        browser="Firefox", browser_version=131, os="Windows", os_version="11.0",
        device_type="desktop", tier=2, weight=1.0,
    ),
]

# T3: Full 50-UA diverse pool for HIGH/EXTREME blocking (21 sites)
# Breakdown: Chrome Win (12), Chrome Mac (8), Chrome Linux (5),
#            Firefox Win (6), Firefox Mac (4), Safari Mac (6),
#            Safari iOS (5), Edge Win (4)  — total = 50
_T3_UA: list[UAEntry] = [
    # --- Chrome Windows (12) ---
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=131, os="Windows", os_version="10.0",
        device_type="desktop", tier=3, weight=2.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=130, os="Windows", os_version="10.0",
        device_type="desktop", tier=3, weight=2.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=129, os="Windows", os_version="10.0",
        device_type="desktop", tier=3, weight=1.5,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=128, os="Windows", os_version="10.0",
        device_type="desktop", tier=3, weight=1.5,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/127.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=127, os="Windows", os_version="10.0",
        device_type="desktop", tier=3, weight=1.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=126, os="Windows", os_version="10.0",
        device_type="desktop", tier=3, weight=1.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 11.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=131, os="Windows", os_version="11.0",
        device_type="desktop", tier=3, weight=2.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 11.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=130, os="Windows", os_version="11.0",
        device_type="desktop", tier=3, weight=1.5,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 11.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=129, os="Windows", os_version="11.0",
        device_type="desktop", tier=3, weight=1.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 11.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=128, os="Windows", os_version="11.0",
        device_type="desktop", tier=3, weight=1.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 10.0; WOW64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=131, os="Windows", os_version="10.0",
        device_type="desktop", tier=3, weight=1.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=120, os="Windows", os_version="10.0",
        device_type="desktop", tier=3, weight=0.5,
    ),

    # --- Chrome macOS (8) ---
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=131, os="macOS", os_version="10.15.7",
        device_type="desktop", tier=3, weight=2.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=130, os="macOS", os_version="10.15.7",
        device_type="desktop", tier=3, weight=1.5,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=129, os="macOS", os_version="10.15.7",
        device_type="desktop", tier=3, weight=1.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=131, os="macOS", os_version="14.7",
        device_type="desktop", tier=3, weight=1.5,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=130, os="macOS", os_version="14.7",
        device_type="desktop", tier=3, weight=1.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_0) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=131, os="macOS", os_version="15.0",
        device_type="desktop", tier=3, weight=1.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_9) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=131, os="macOS", os_version="13.6.9",
        device_type="desktop", tier=3, weight=1.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_9) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=128, os="macOS", os_version="13.6.9",
        device_type="desktop", tier=3, weight=0.5,
    ),

    # --- Chrome Linux (5) ---
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=131, os="Linux", os_version="x86_64",
        device_type="desktop", tier=3, weight=1.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=130, os="Linux", os_version="x86_64",
        device_type="desktop", tier=3, weight=1.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=131, os="Linux", os_version="x86_64",
        device_type="desktop", tier=3, weight=0.7,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (X11; Fedora; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=130, os="Linux", os_version="x86_64",
        device_type="desktop", tier=3, weight=0.5,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36"
        ),
        browser="Chrome", browser_version=129, os="Linux", os_version="x86_64",
        device_type="desktop", tier=3, weight=0.5,
    ),

    # --- Firefox Windows (6) ---
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) "
            "Gecko/20100101 Firefox/133.0"
        ),
        browser="Firefox", browser_version=133, os="Windows", os_version="10.0",
        device_type="desktop", tier=3, weight=1.5,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) "
            "Gecko/20100101 Firefox/132.0"
        ),
        browser="Firefox", browser_version=132, os="Windows", os_version="10.0",
        device_type="desktop", tier=3, weight=1.5,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) "
            "Gecko/20100101 Firefox/131.0"
        ),
        browser="Firefox", browser_version=131, os="Windows", os_version="10.0",
        device_type="desktop", tier=3, weight=1.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) "
            "Gecko/20100101 Firefox/130.0"
        ),
        browser="Firefox", browser_version=130, os="Windows", os_version="10.0",
        device_type="desktop", tier=3, weight=1.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 11.0; Win64; x64; rv:133.0) "
            "Gecko/20100101 Firefox/133.0"
        ),
        browser="Firefox", browser_version=133, os="Windows", os_version="11.0",
        device_type="desktop", tier=3, weight=1.5,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 11.0; Win64; x64; rv:131.0) "
            "Gecko/20100101 Firefox/131.0"
        ),
        browser="Firefox", browser_version=131, os="Windows", os_version="11.0",
        device_type="desktop", tier=3, weight=1.0,
    ),

    # --- Firefox macOS (4) ---
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:133.0) "
            "Gecko/20100101 Firefox/133.0"
        ),
        browser="Firefox", browser_version=133, os="macOS", os_version="14.7",
        device_type="desktop", tier=3, weight=1.5,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:132.0) "
            "Gecko/20100101 Firefox/132.0"
        ),
        browser="Firefox", browser_version=132, os="macOS", os_version="14.7",
        device_type="desktop", tier=3, weight=1.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13.6; rv:133.0) "
            "Gecko/20100101 Firefox/133.0"
        ),
        browser="Firefox", browser_version=133, os="macOS", os_version="13.6",
        device_type="desktop", tier=3, weight=1.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 15.0; rv:131.0) "
            "Gecko/20100101 Firefox/131.0"
        ),
        browser="Firefox", browser_version=131, os="macOS", os_version="15.0",
        device_type="desktop", tier=3, weight=0.7,
    ),

    # --- Safari macOS (6) ---
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_2) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/18.1.1 Safari/605.1.15"
        ),
        browser="Safari", browser_version=18, os="macOS", os_version="14.7.2",
        device_type="desktop", tier=3, weight=1.5,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.6 Safari/605.1.15"
        ),
        browser="Safari", browser_version=17, os="macOS", os_version="14.7",
        device_type="desktop", tier=3, weight=1.5,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_9) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.5 Safari/605.1.15"
        ),
        browser="Safari", browser_version=17, os="macOS", os_version="13.6.9",
        device_type="desktop", tier=3, weight=1.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_0) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/18.0 Safari/605.1.15"
        ),
        browser="Safari", browser_version=18, os="macOS", os_version="15.0",
        device_type="desktop", tier=3, weight=1.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.4.1 Safari/605.1.15"
        ),
        browser="Safari", browser_version=17, os="macOS", os_version="14.5",
        device_type="desktop", tier=3, weight=0.7,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/16.6.1 Safari/605.1.15"
        ),
        browser="Safari", browser_version=16, os="macOS", os_version="13.5",
        device_type="desktop", tier=3, weight=0.5,
    ),

    # --- Safari iOS (5) ---
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1_1 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/18.1.1 Mobile/15E148 Safari/604.1"
        ),
        browser="Safari", browser_version=18, os="iOS", os_version="18.1.1",
        device_type="mobile", tier=3, weight=1.5,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_7_2 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.7.2 Mobile/15E148 Safari/604.1"
        ),
        browser="Safari", browser_version=17, os="iOS", os_version="17.7.2",
        device_type="mobile", tier=3, weight=1.5,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (iPad; CPU OS 17_6_1 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.6 Mobile/15E148 Safari/604.1"
        ),
        browser="Safari", browser_version=17, os="iOS", os_version="17.6.1",
        device_type="mobile", tier=3, weight=1.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.4.1 Mobile/15E148 Safari/604.1"
        ),
        browser="Safari", browser_version=17, os="iOS", os_version="17.4.1",
        device_type="mobile", tier=3, weight=0.7,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_7_10 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/16.6 Mobile/15E148 Safari/604.1"
        ),
        browser="Safari", browser_version=16, os="iOS", os_version="16.7.10",
        device_type="mobile", tier=3, weight=0.5,
    ),

    # --- Edge Windows (4) ---
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
        ),
        browser="Edge", browser_version=131, os="Windows", os_version="10.0",
        device_type="desktop", tier=3, weight=1.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0"
        ),
        browser="Edge", browser_version=130, os="Windows", os_version="10.0",
        device_type="desktop", tier=3, weight=0.7,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 11.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
        ),
        browser="Edge", browser_version=131, os="Windows", os_version="11.0",
        device_type="desktop", tier=3, weight=1.0,
    ),
    UAEntry(
        ua_string=(
            "Mozilla/5.0 (Windows NT 11.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0"
        ),
        browser="Edge", browser_version=129, os="Windows", os_version="11.0",
        device_type="desktop", tier=3, weight=0.5,
    ),
]


# ---------------------------------------------------------------------------
# Site-to-Tier mapping from Step 6 crawling strategy table
# ---------------------------------------------------------------------------

# Sites not listed here default to T3.
_SITE_TIER_MAP: dict[str, int] = {
    # T1 (LOW bot-blocking, 9 sites)
    "nocutnews": 1,
    "ohmynews": 1,
    "38north": 1,
    "voakorea": 1,
    "afmedios": 1,
    "globaltimes": 1,
    "taiwannews": 1,
    "themoscowtimes": 1,
    "israelhayom": 1,

    # T2 (MEDIUM bot-blocking, 14 sites)
    "chosun": 2,
    "donga": 2,
    "hani": 2,
    "yna": 2,
    "mk": 2,
    "hankyung": 2,
    "fnnews": 2,
    "mt": 2,
    "kmib": 2,
    "etnews": 2,
    "zdnet": 2,
    "people": 2,
    "arabnews": 2,
    "aljazeera": 2,
    "huffpost": 2,
    "latimes": 2,
    "edition_cnn": 2,
    "scmp": 2,

    # T3 (HIGH/EXTREME bot-blocking, 21+ sites)
    "joongang": 3,
    "bloter": 3,
    "sciencetimes": 3,
    "irobotnews": 3,
    "techneedle": 3,
    "marketwatch": 3,
    "nytimes": 3,
    "ft": 3,
    "wsj": 3,
    "buzzfeed": 3,
    "nationalpost": 3,
    "bloomberg": 3,
    "yomiuri": 3,
    "thehindu": 3,
    "thesun": 3,
    "bild": 3,
    "lemonde": 3,
}


# ---------------------------------------------------------------------------
# UAManager
# ---------------------------------------------------------------------------

class UAManager:
    """4-tier User-Agent rotation pool for the GlobalNews crawling system.

    Manages selection of real browser User-Agent strings based on site tier
    assignment. Tracks per-domain UA usage to avoid immediate repetition.

    Tier semantics (Step 6):
        T1 — 1 Googlebot UA for LOW blocking sites
        T2 — 10 modern desktop UAs for MEDIUM blocking sites
        T3 — 50 diverse UAs for HIGH/EXTREME blocking sites
        T4 — Dynamic Patchright fingerprints (not in this pool)

    Browser distribution (T3 pool):
        Chrome   ~65%  (Chrome Win + Chrome Mac + Chrome Linux)
        Firefox  ~20%  (Firefox Win + Firefox Mac)
        Safari   ~10%  (Safari Mac + Safari iOS)
        Edge      ~5%  (Edge Win)

    Args:
        sources_config: Optional pre-loaded sources.yaml config dict. If
            provided, ua_tier values from anti_block.ua_tier override the
            built-in _SITE_TIER_MAP. Useful when sources.yaml is available.
        recent_ua_window: Number of recent UAs per domain to exclude from
            the next selection, preventing immediate repetition. Default 5.
        seed: Optional random seed for reproducibility in tests.
    """

    def __init__(
        self,
        sources_config: dict[str, Any] | None = None,
        recent_ua_window: int = 5,
        seed: int | None = None,
    ) -> None:
        self._rng = random.Random(seed)
        self._recent_ua_window = recent_ua_window
        self._lock = threading.Lock()

        # Build tier override map from sources.yaml if provided
        self._tier_override: dict[str, int] = {}
        if sources_config:
            for site_id, site_cfg in sources_config.get("sources", {}).items():
                ua_tier = site_cfg.get("anti_block", {}).get("ua_tier")
                if ua_tier in (1, 2, 3, 4):
                    self._tier_override[site_id] = ua_tier

        # Index UA entries by tier for O(1) pool lookup
        self._pools: dict[int, list[UAEntry]] = {
            1: list(_T1_UA),
            2: list(_T2_UA),
            3: list(_T3_UA),
        }

        # Pre-compute cumulative weights for each pool
        self._weights: dict[int, list[float]] = {
            tier: [e.weight for e in entries]
            for tier, entries in self._pools.items()
        }

        # Per-domain recent-UA tracking (circular buffer as list)
        self._domain_history: dict[str, list[str]] = {}

        logger.info(
            "ua_manager_initialized",
            t1_pool_size=len(self._pools[1]),
            t2_pool_size=len(self._pools[2]),
            t3_pool_size=len(self._pools[3]),
            total_static_uas=len(_T1_UA) + len(_T2_UA) + len(_T3_UA),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_ua(self, site_id: str) -> str:
        """Select a User-Agent string for the given site.

        Thread-safe: protected by internal lock for concurrent crawling.

        Selection process:
        1. Determine tier from sources.yaml override > _SITE_TIER_MAP > default T3.
        2. For T1: always return the single Googlebot UA.
        3. For T2/T3: weighted-random selection excluding recently-used UAs for
           this domain (anti-repetition window of `recent_ua_window`).

        Args:
            site_id: The source_id matching sources.yaml (e.g., "chosun",
                     "nytimes").

        Returns:
            A User-Agent string appropriate for the site's tier.
        """
        with self._lock:
            return self._get_ua_unlocked(site_id)

    def _get_ua_unlocked(self, site_id: str) -> str:
        """Internal UA selection (caller must hold self._lock)."""
        tier = self._resolve_tier(site_id)

        if tier == 1:
            return _T1_UA[0].ua_string

        if tier == 4:
            # T4 is dynamic Patchright — caller must handle; fall back to T3
            logger.debug("ua_tier4_fallback", site_id=site_id)
            tier = 3

        pool = self._pools[tier]
        weights = self._weights[tier]
        history = self._domain_history.get(site_id, [])

        # Build candidate list excluding recently-used UAs for this domain
        candidates = [
            (entry, w)
            for entry, w in zip(pool, weights)
            if entry.ua_string not in history
        ]

        if not candidates:
            # History window covers entire pool (unlikely) — reset history
            logger.debug("ua_history_reset", site_id=site_id)
            self._domain_history[site_id] = []
            candidates = list(zip(pool, weights))

        entries, candidate_weights = zip(*candidates)
        chosen: UAEntry = self._rng.choices(list(entries), weights=list(candidate_weights), k=1)[0]

        # Update domain history
        domain_hist = self._domain_history.setdefault(site_id, [])
        domain_hist.append(chosen.ua_string)
        if len(domain_hist) > self._recent_ua_window:
            domain_hist.pop(0)

        logger.debug(
            "ua_selected",
            site_id=site_id,
            tier=tier,
            browser=chosen.browser,
            browser_version=chosen.browser_version,
            os=chosen.os,
            device_type=chosen.device_type,
        )
        return chosen.ua_string

    def get_ua_entry(self, site_id: str) -> UAEntry:
        """Select a UA and return the full UAEntry metadata object.

        Useful when header builder needs browser/OS/version information for
        consistent header generation (e.g., Sec-Fetch headers, Accept headers).

        Args:
            site_id: The source_id matching sources.yaml.

        Returns:
            UAEntry with full metadata including the ua_string.
        """
        ua_string = self.get_ua(site_id)
        tier = self._resolve_tier(site_id)
        if tier == 4:
            tier = 3
        if tier == 1:
            return _T1_UA[0]
        pool = self._pools[tier]
        # Find the matching entry (linear scan on small pool)
        for entry in pool:
            if entry.ua_string == ua_string:
                return entry
        # Should not happen; construct a minimal fallback
        return UAEntry(
            ua_string=ua_string,
            browser="Chrome",
            browser_version=131,
            os="Windows",
            os_version="10.0",
            device_type="desktop",
            tier=tier,
            weight=1.0,
        )

    def get_tier(self, site_id: str) -> int:
        """Return the resolved UA tier for a site.

        Args:
            site_id: The source_id matching sources.yaml.

        Returns:
            Tier integer: 1, 2, 3, or 4.
        """
        return self._resolve_tier(site_id)

    def pool_stats(self) -> dict[str, Any]:
        """Return UA pool size statistics for monitoring.

        Returns:
            Dictionary with pool sizes per tier and total count.
        """
        return {
            "t1_size": len(self._pools[1]),
            "t2_size": len(self._pools[2]),
            "t3_size": len(self._pools[3]),
            "total_static": sum(len(p) for p in self._pools.values()),
            "t4_dynamic": True,  # Patchright generates on-demand
        }

    def reset_domain_history(self, site_id: str) -> None:
        """Clear UA rotation history for a domain.

        Call this after a session reset or proxy change to allow previously
        excluded UAs to be selected again.

        Args:
            site_id: The source_id to reset.
        """
        self._domain_history.pop(site_id, None)
        logger.debug("ua_domain_history_reset", site_id=site_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_tier(self, site_id: str) -> int:
        """Determine UA tier for a site (priority: sources.yaml > built-in map > T3).

        Args:
            site_id: The source_id string.

        Returns:
            Tier integer: 1, 2, 3, or 4.
        """
        if site_id in self._tier_override:
            return self._tier_override[site_id]
        return _SITE_TIER_MAP.get(site_id, 3)
