"""7-Type Block Diagnosis Engine for the GlobalNews crawling system.

Analyzes HTTP responses to detect and classify 7 distinct block types
with confidence scoring. Each detector is a pluggable class that examines
status codes, headers, and body content to produce a BlockDiagnosis.

Block Types:
    1. IP Block       - 403/429 status, "access denied" patterns
    2. UA Filter      - 406 status, redirect to bot verification pages
    3. Rate Limit     - 429 status, Retry-After header, degraded responses
    4. CAPTCHA        - reCAPTCHA, hCaptcha, Cloudflare Turnstile markers
    5. JS Challenge   - Cloudflare JS challenge, empty body with JS redirect
    6. Fingerprint    - TLS fingerprint rejection, 403 with specific headers
    7. Geo-Block      - Redirect to regional site, "not available" messages

Reference: Step 5 Architecture Blueprint, Crawling Layer (Anti-Block System).
Reference: Step 6 Crawling Strategies, per-site bot-block levels.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Sequence

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================

@unique
class BlockType(Enum):
    """Enumeration of the 7 recognized block types."""
    IP_BLOCK = "ip_block"
    UA_FILTER = "ua_filter"
    RATE_LIMIT = "rate_limit"
    CAPTCHA = "captcha"
    JS_CHALLENGE = "js_challenge"
    FINGERPRINT = "fingerprint"
    GEO_BLOCK = "geo_block"


@dataclass(frozen=True)
class BlockDiagnosis:
    """Result of a block detection analysis.

    Attributes:
        block_type: The classified block type.
        confidence: Detection confidence from 0.0 (uncertain) to 1.0 (certain).
        evidence: Human-readable list of evidence that led to this diagnosis.
        recommended_tier: The minimum escalation tier (1-6) to bypass this block.
    """
    block_type: BlockType
    confidence: float
    evidence: list[str] = field(default_factory=list)
    recommended_tier: int = 1

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be 0.0-1.0, got {self.confidence}")
        if not 1 <= self.recommended_tier <= 6:
            raise ValueError(f"Recommended tier must be 1-6, got {self.recommended_tier}")


@dataclass
class HttpResponse:
    """Lightweight HTTP response representation for block detection.

    This is a framework-agnostic container so the detector does not depend
    on httpx, requests, or Playwright response types directly.

    Attributes:
        status_code: HTTP status code (e.g. 200, 403, 429).
        headers: Response headers as a case-insensitive-ish dict.
        body: Response body as a decoded string (may be empty or truncated).
        url: The final URL after redirects.
        original_url: The originally requested URL (before redirects).
        elapsed_seconds: Time taken for the response (for rate limit heuristics).
    """
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""
    url: str = ""
    original_url: str = ""
    elapsed_seconds: float = 0.0

    def header(self, name: str, default: str = "") -> str:
        """Case-insensitive header lookup."""
        name_lower = name.lower()
        for k, v in self.headers.items():
            if k.lower() == name_lower:
                return v
        return default


# =============================================================================
# Individual Detectors
# =============================================================================

class _BaseDetector:
    """Abstract base for a single block-type detector."""

    block_type: BlockType
    default_tier: int = 1

    def detect(self, response: HttpResponse) -> BlockDiagnosis | None:
        """Analyze response and return a BlockDiagnosis or None if no block."""
        raise NotImplementedError


class IPBlockDetector(_BaseDetector):
    """Detect IP-based blocks: 403 Forbidden, connection resets, access denied pages."""

    block_type = BlockType.IP_BLOCK
    default_tier = 5  # Proxy rotation needed

    # Patterns that indicate IP-level blocking (case-insensitive)
    _BODY_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"access\s+denied", re.IGNORECASE),
        re.compile(r"ip\s+(has\s+been\s+)?blocked", re.IGNORECASE),
        re.compile(r"your\s+ip\s+(address\s+)?is\s+(not\s+allowed|blocked|banned)", re.IGNORECASE),
        re.compile(r"request\s+blocked", re.IGNORECASE),
        re.compile(r"forbidden", re.IGNORECASE),
        re.compile(r"you\s+have\s+been\s+blocked", re.IGNORECASE),
        re.compile(r"error\s+1006", re.IGNORECASE),  # Cloudflare banned IP
        re.compile(r"error\s+1015", re.IGNORECASE),  # Cloudflare rate limited
    ]

    def detect(self, response: HttpResponse) -> BlockDiagnosis | None:
        evidence: list[str] = []
        confidence = 0.0

        # Strong signal: 403 Forbidden
        if response.status_code == 403:
            evidence.append(f"HTTP 403 Forbidden")
            confidence += 0.5

        # Strong signal: empty body on 403 (typical IP ban)
        if response.status_code == 403 and len(response.body.strip()) < 200:
            evidence.append("403 with minimal body (likely IP ban)")
            confidence += 0.2

        # Body pattern matching
        for pattern in self._BODY_PATTERNS:
            match = pattern.search(response.body[:5000])  # Only scan first 5KB
            if match:
                evidence.append(f"Body contains: '{match.group()}'")
                confidence += 0.3
                break  # One body match is sufficient

        # Header signals: some WAFs set specific headers on blocks
        if response.header("x-amzn-waf-action") == "block":
            evidence.append("x-amzn-waf-action: block")
            confidence += 0.4

        if response.header("cf-mitigated") == "challenge":
            evidence.append("cf-mitigated: challenge (Cloudflare)")
            confidence += 0.3

        if confidence > 0.0:
            return BlockDiagnosis(
                block_type=self.block_type,
                confidence=min(confidence, 1.0),
                evidence=evidence,
                recommended_tier=self.default_tier,
            )
        return None


class UAFilterDetector(_BaseDetector):
    """Detect User-Agent filtering: 406 Not Acceptable, bot redirect pages."""

    block_type = BlockType.UA_FILTER
    default_tier = 2  # Header rotation needed

    _BODY_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"bot\s+detected", re.IGNORECASE),
        re.compile(r"automated\s+access", re.IGNORECASE),
        re.compile(r"please\s+use\s+a\s+(modern\s+)?browser", re.IGNORECASE),
        re.compile(r"browser\s+not\s+supported", re.IGNORECASE),
        re.compile(r"enable\s+javascript", re.IGNORECASE),
        re.compile(r"suspicious\s+activity", re.IGNORECASE),
    ]

    def detect(self, response: HttpResponse) -> BlockDiagnosis | None:
        evidence: list[str] = []
        confidence = 0.0

        # 406 Not Acceptable -- strong UA filter signal
        if response.status_code == 406:
            evidence.append("HTTP 406 Not Acceptable")
            confidence += 0.7

        # Redirect to a "verify you are human" or bot-check page
        if response.url != response.original_url:
            lower_url = response.url.lower()
            for marker in ("bot", "verify", "challenge", "captcha", "human"):
                if marker in lower_url:
                    evidence.append(f"Redirected to bot-check URL: {response.url}")
                    confidence += 0.5
                    break

        # Body pattern matching
        for pattern in self._BODY_PATTERNS:
            match = pattern.search(response.body[:5000])
            if match:
                evidence.append(f"Body contains: '{match.group()}'")
                confidence += 0.3
                break

        if confidence > 0.0:
            return BlockDiagnosis(
                block_type=self.block_type,
                confidence=min(confidence, 1.0),
                evidence=evidence,
                recommended_tier=self.default_tier,
            )
        return None


class RateLimitDetector(_BaseDetector):
    """Detect rate limiting: 429 Too Many Requests, Retry-After header."""

    block_type = BlockType.RATE_LIMIT
    default_tier = 1  # Delay adjustment first

    def detect(self, response: HttpResponse) -> BlockDiagnosis | None:
        evidence: list[str] = []
        confidence = 0.0

        # Strong signal: HTTP 429
        if response.status_code == 429:
            evidence.append("HTTP 429 Too Many Requests")
            confidence += 0.8

        # Retry-After header present (even without 429)
        retry_after = response.header("retry-after")
        if retry_after:
            evidence.append(f"Retry-After header: {retry_after}")
            confidence += 0.3

        # X-RateLimit headers
        remaining = response.header("x-ratelimit-remaining")
        if remaining:
            try:
                if int(remaining) == 0:
                    evidence.append(f"x-ratelimit-remaining: 0")
                    confidence += 0.5
            except ValueError:
                pass

        # Some CDNs return 503 with rate-limit semantics
        if response.status_code == 503:
            body_lower = response.body[:3000].lower()
            if "rate" in body_lower and ("limit" in body_lower or "exceeded" in body_lower):
                evidence.append("HTTP 503 with rate-limit language in body")
                confidence += 0.5

        # Body patterns for soft rate limits
        if response.status_code == 200:
            body_lower = response.body[:3000].lower()
            if "too many requests" in body_lower or "rate limit" in body_lower:
                evidence.append("200 OK but body contains rate-limit language (soft limit)")
                confidence += 0.4

        if confidence > 0.0:
            return BlockDiagnosis(
                block_type=self.block_type,
                confidence=min(confidence, 1.0),
                evidence=evidence,
                recommended_tier=self.default_tier,
            )
        return None


class CAPTCHADetector(_BaseDetector):
    """Detect CAPTCHA challenges: reCAPTCHA, hCaptcha, Cloudflare Turnstile."""

    block_type = BlockType.CAPTCHA
    default_tier = 4  # Stealth browser with fingerprint randomization

    _SCRIPT_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"google\.com/recaptcha", re.IGNORECASE),
        re.compile(r"gstatic\.com/recaptcha", re.IGNORECASE),
        re.compile(r"hcaptcha\.com", re.IGNORECASE),
        re.compile(r"challenges\.cloudflare\.com", re.IGNORECASE),
        re.compile(r"turnstile", re.IGNORECASE),
    ]

    _DOM_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r'class=["\'].*g-recaptcha', re.IGNORECASE),
        re.compile(r'class=["\'].*h-captcha', re.IGNORECASE),
        re.compile(r'id=["\']captcha', re.IGNORECASE),
        re.compile(r'data-sitekey\s*=', re.IGNORECASE),
        re.compile(r'cf-turnstile', re.IGNORECASE),
        re.compile(r'id=["\']cf-challenge', re.IGNORECASE),
    ]

    def detect(self, response: HttpResponse) -> BlockDiagnosis | None:
        evidence: list[str] = []
        confidence = 0.0

        body = response.body[:10000]  # Scan first 10KB for CAPTCHA markers

        # Script source patterns
        for pattern in self._SCRIPT_PATTERNS:
            match = pattern.search(body)
            if match:
                evidence.append(f"CAPTCHA script source: '{match.group()}'")
                confidence += 0.6
                break

        # DOM element patterns
        for pattern in self._DOM_PATTERNS:
            match = pattern.search(body)
            if match:
                evidence.append(f"CAPTCHA DOM element: '{match.group()}'")
                confidence += 0.4
                break

        # Cloudflare-specific challenge page detection
        if response.status_code == 403:
            cf_ray = response.header("cf-ray")
            if cf_ray and "challenge" in response.body[:5000].lower():
                evidence.append(f"Cloudflare challenge page (cf-ray: {cf_ray})")
                confidence += 0.5

        # Title-based detection
        title_match = re.search(r"<title>(.*?)</title>", body, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = title_match.group(1).lower()
            for keyword in ("captcha", "verify", "challenge", "security check", "robot"):
                if keyword in title:
                    evidence.append(f"Page title contains '{keyword}': '{title_match.group(1)}'")
                    confidence += 0.3
                    break

        if confidence > 0.0:
            return BlockDiagnosis(
                block_type=self.block_type,
                confidence=min(confidence, 1.0),
                evidence=evidence,
                recommended_tier=self.default_tier,
            )
        return None


class JSChallengeDetector(_BaseDetector):
    """Detect JavaScript challenges: Cloudflare JS Challenge, Akamai Bot Manager, DataDome."""

    block_type = BlockType.JS_CHALLENGE
    default_tier = 3  # Headless browser rendering

    _JS_CHALLENGE_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"_cf_chl_opt", re.IGNORECASE),
        re.compile(r"__cf_chl_rt_tk", re.IGNORECASE),
        re.compile(r"jschl[_-]?answer", re.IGNORECASE),
        re.compile(r"cf[_-]?chl[_-]?managed", re.IGNORECASE),
        re.compile(r"akamai.*bot.*manager", re.IGNORECASE),
        re.compile(r"datadome", re.IGNORECASE),
        re.compile(r"perimeterx", re.IGNORECASE),
        re.compile(r"imperva", re.IGNORECASE),
        re.compile(r"incapsula", re.IGNORECASE),
    ]

    def detect(self, response: HttpResponse) -> BlockDiagnosis | None:
        evidence: list[str] = []
        confidence = 0.0

        body = response.body[:10000]

        # Cloudflare 503 challenge
        if response.status_code == 503:
            server = response.header("server", "").lower()
            if "cloudflare" in server:
                evidence.append("HTTP 503 from Cloudflare server (JS challenge)")
                confidence += 0.7

        # Very small HTML body with JS redirect (meta refresh or window.location)
        if response.status_code in (200, 503):
            body_stripped = body.strip()
            if len(body_stripped) < 2000 and body_stripped:
                has_meta_refresh = bool(re.search(
                    r'<meta[^>]*http-equiv=["\']refresh', body_stripped, re.IGNORECASE
                ))
                has_js_redirect = bool(re.search(
                    r'(window\.location|document\.location|location\.href)\s*=', body_stripped, re.IGNORECASE
                ))
                if has_meta_refresh or has_js_redirect:
                    evidence.append(f"Small body ({len(body_stripped)} chars) with JS/meta redirect")
                    confidence += 0.5

        # JS challenge variable/function patterns
        for pattern in self._JS_CHALLENGE_PATTERNS:
            match = pattern.search(body)
            if match:
                evidence.append(f"JS challenge marker: '{match.group()}'")
                confidence += 0.5
                break

        # Specific headers
        if response.header("cf-chl-bypass"):
            evidence.append("cf-chl-bypass header present")
            confidence += 0.4

        # Empty body on 200 (JS rendered page returned nothing).
        # Only flag truly empty responses: < 50 chars AND no real HTML content tags.
        # This avoids false positives on small but legitimate pages.
        if response.status_code == 200 and len(body.strip()) < 50:
            has_content_tag = bool(re.search(
                r"<(p|div|article|section|main|h[1-6]|span|body)[>\s]",
                body, re.IGNORECASE,
            ))
            if not has_content_tag:
                evidence.append("HTTP 200 with near-empty body (possible JS-only page)")
                confidence += 0.3

        if confidence > 0.0:
            return BlockDiagnosis(
                block_type=self.block_type,
                confidence=min(confidence, 1.0),
                evidence=evidence,
                recommended_tier=self.default_tier,
            )
        return None


class FingerprintDetector(_BaseDetector):
    """Detect TLS/browser fingerprint rejection."""

    block_type = BlockType.FINGERPRINT
    default_tier = 4  # Patchright + fingerprint-suite

    def detect(self, response: HttpResponse) -> BlockDiagnosis | None:
        evidence: list[str] = []
        confidence = 0.0

        # 403 with specific fingerprint-related headers
        if response.status_code == 403:
            # Akamai Bot Manager fingerprint rejection
            akamai_ref = response.header("x-akamai-session-info")
            if akamai_ref:
                evidence.append(f"Akamai fingerprint rejection (x-akamai-session-info present)")
                confidence += 0.6

            # Generic fingerprint indicators in body
            body_lower = response.body[:5000].lower()
            fp_keywords = ["fingerprint", "browser verification", "tls", "ja3", "ja4"]
            for kw in fp_keywords:
                if kw in body_lower:
                    evidence.append(f"Body references '{kw}' in block context")
                    confidence += 0.3
                    break

        # DataDome fingerprint challenge
        if "datadome" in response.header("set-cookie", "").lower():
            evidence.append("DataDome cookie set (fingerprint tracking)")
            confidence += 0.3

        # Kasada anti-bot
        if response.header("x-kpsdk-ct"):
            evidence.append("Kasada anti-bot header (x-kpsdk-ct)")
            confidence += 0.5

        # Shape Security
        if response.header("x-px"):
            evidence.append("PerimeterX header (x-px)")
            confidence += 0.5

        # Connection reset / TLS error indication
        # (In practice this is caught as an exception before response parsing,
        #  but some proxies surface it as a 403 with specific body)
        if response.status_code == 403:
            body_lower = response.body[:3000].lower()
            if "ssl" in body_lower or "tls" in body_lower:
                if "handshake" in body_lower or "error" in body_lower:
                    evidence.append("TLS/SSL error language in 403 body")
                    confidence += 0.4

        if confidence > 0.0:
            return BlockDiagnosis(
                block_type=self.block_type,
                confidence=min(confidence, 1.0),
                evidence=evidence,
                recommended_tier=self.default_tier,
            )
        return None


class GeoBlockDetector(_BaseDetector):
    """Detect geographic restrictions: redirects to regional sites, availability messages."""

    block_type = BlockType.GEO_BLOCK
    default_tier = 5  # Proxy rotation to appropriate region

    _GEO_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"not\s+available\s+in\s+your\s+(region|country|area)", re.IGNORECASE),
        re.compile(r"content\s+is\s+not\s+available", re.IGNORECASE),
        re.compile(r"geographic\s+restriction", re.IGNORECASE),
        re.compile(r"geo[_-]?block", re.IGNORECASE),
        re.compile(r"this\s+service\s+is\s+not\s+available\s+in\s+your\s+location", re.IGNORECASE),
        re.compile(r"access\s+from\s+your\s+(country|region)\s+is\s+not\s+permitted", re.IGNORECASE),
    ]

    def detect(self, response: HttpResponse) -> BlockDiagnosis | None:
        evidence: list[str] = []
        confidence = 0.0

        body = response.body[:5000]

        # Redirect to a regional variant of the site
        if response.url != response.original_url:
            # Check if domain changed (e.g., nytimes.com -> cn.nytimes.com)
            from urllib.parse import urlparse
            orig_domain = urlparse(response.original_url).netloc.lower()
            final_domain = urlparse(response.url).netloc.lower()
            if orig_domain and final_domain and orig_domain != final_domain:
                # Check for country/region prefixes
                for prefix in ("kr.", "cn.", "jp.", "de.", "fr.", "uk.", "us.", "eu.", "asia.", "intl."):
                    if final_domain.startswith(prefix) and not orig_domain.startswith(prefix):
                        evidence.append(f"Redirected to regional domain: {response.url}")
                        confidence += 0.6
                        break

        # Body geo-restriction patterns
        for pattern in self._GEO_PATTERNS:
            match = pattern.search(body)
            if match:
                evidence.append(f"Body contains: '{match.group()}'")
                confidence += 0.5
                break

        # HTTP 451 Unavailable For Legal Reasons (sometimes used for geo-blocks)
        if response.status_code == 451:
            evidence.append("HTTP 451 Unavailable For Legal Reasons")
            confidence += 0.7

        # GDPR/cookie consent redirect (not a true geo-block, lower confidence)
        if response.status_code in (301, 302, 307):
            location = response.header("location", "").lower()
            if "consent" in location or "gdpr" in location or "cookie" in location:
                evidence.append(f"Redirect to consent/GDPR page: {response.header('location')}")
                confidence += 0.3

        if confidence > 0.0:
            return BlockDiagnosis(
                block_type=self.block_type,
                confidence=min(confidence, 1.0),
                evidence=evidence,
                recommended_tier=self.default_tier,
            )
        return None


# =============================================================================
# Block Detector Engine (Orchestrates all 7 detectors)
# =============================================================================

# Ordered by specificity: more specific detectors run first so that a CAPTCHA
# page is not misclassified as a generic IP block.
_DEFAULT_DETECTORS: list[_BaseDetector] = [
    CAPTCHADetector(),
    JSChallengeDetector(),
    FingerprintDetector(),
    RateLimitDetector(),
    GeoBlockDetector(),
    UAFilterDetector(),
    IPBlockDetector(),
]


class BlockDetector:
    """7-Type Block Diagnosis Engine.

    Runs all 7 block type detectors against an HTTP response and returns
    diagnoses sorted by confidence (highest first).

    Usage:
        detector = BlockDetector()
        diagnoses = detector.diagnose(response)
        if diagnoses:
            primary = diagnoses[0]  # Highest confidence diagnosis
            print(f"Blocked: {primary.block_type.value} "
                  f"(confidence={primary.confidence:.0%})")

    Thread-safety: Detectors are stateless and read-only; safe to share
    across threads.

    Attributes:
        detectors: The list of pluggable detector instances.
        confidence_threshold: Minimum confidence to include in results.
    """

    def __init__(
        self,
        detectors: Sequence[_BaseDetector] | None = None,
        confidence_threshold: float = 0.3,
    ) -> None:
        """Initialize the BlockDetector.

        Args:
            detectors: Custom detector list (defaults to all 7 built-in detectors).
            confidence_threshold: Minimum confidence to include a diagnosis.
                Diagnoses below this threshold are discarded to reduce false positives.
        """
        self.detectors: list[_BaseDetector] = list(detectors or _DEFAULT_DETECTORS)
        self.confidence_threshold = confidence_threshold

    def diagnose(self, response: HttpResponse) -> list[BlockDiagnosis]:
        """Analyze an HTTP response for all 7 block types.

        Args:
            response: The HTTP response to analyze.

        Returns:
            List of BlockDiagnosis objects sorted by confidence (highest first).
            Empty list if no blocks detected above the confidence threshold.
        """
        diagnoses: list[BlockDiagnosis] = []

        for detector in self.detectors:
            try:
                diagnosis = detector.detect(response)
                if diagnosis is not None and diagnosis.confidence >= self.confidence_threshold:
                    diagnoses.append(diagnosis)
            except Exception:
                # Never crash the detector pipeline -- log and continue
                logger.warning(
                    "Detector failed",
                    exc_info=True,
                    extra={"detector": type(detector).__name__, "url": response.url},
                )

        # Sort by confidence descending; on tie, prefer higher-tier recommendation
        # (more specific diagnosis)
        diagnoses.sort(key=lambda d: (d.confidence, d.recommended_tier), reverse=True)
        return diagnoses

    def is_blocked(self, response: HttpResponse) -> bool:
        """Quick check: is this response a block?

        Returns True if any detector finds a block above the confidence threshold.
        Use this for fast decision-making when you do not need the full diagnosis.

        Args:
            response: The HTTP response to check.

        Returns:
            True if at least one block diagnosis was found.
        """
        return len(self.diagnose(response)) > 0

    def primary_diagnosis(self, response: HttpResponse) -> BlockDiagnosis | None:
        """Return the single highest-confidence diagnosis, or None.

        Args:
            response: The HTTP response to analyze.

        Returns:
            The BlockDiagnosis with the highest confidence, or None.
        """
        diagnoses = self.diagnose(response)
        return diagnoses[0] if diagnoses else None

    def __repr__(self) -> str:
        detector_names = [type(d).__name__ for d in self.detectors]
        return f"BlockDetector(detectors={detector_names}, threshold={self.confidence_threshold})"
