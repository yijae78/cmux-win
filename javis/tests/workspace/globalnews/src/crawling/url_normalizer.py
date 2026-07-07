"""URL normalization for deduplication.

Converts raw article URLs to a canonical form so that URLs pointing to
the same content (modulo tracking parameters, scheme variations, www
prefixes, etc.) hash identically.

Design decisions:
- Tracking parameter stripping is the highest-value transformation because
  news aggregators and social shares embed utm_*, fbclid, etc. on every URL.
- www normalization is explicit (www.example.com == example.com) because the
  crawling target list mixes both forms.
- https is preferred over http for the canonical form to match modern
  publisher conventions.
- Fragment (#) is always removed: server-side content is identical regardless
  of the anchor.
- Query parameters are sorted alphabetically so ?b=2&a=1 == ?a=1&b=2.

Reference: Step 5 Architecture Blueprint, Section 3 (Dedup Engine interface).
"""

import re
from urllib.parse import (
    parse_qs,
    urlencode,
    urlparse,
    urlunparse,
    unquote_plus,
    quote,
)

from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Tracking / campaign parameters to strip unconditionally
# ---------------------------------------------------------------------------

# Each set is prefixed with a comment identifying the ad / analytics platform.

# Google Analytics / Google Ads
_GOOGLE_PARAMS: frozenset[str] = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_source_platform", "utm_creative_format",
    "utm_marketing_tactic",
    "gclid", "gclsrc", "dclid",
})

# Meta (Facebook / Instagram)
_META_PARAMS: frozenset[str] = frozenset({
    "fbclid", "fb_action_ids", "fb_action_types", "fb_ref", "fb_source",
    "fb_comment_id",
})

# Twitter / X
_TWITTER_PARAMS: frozenset[str] = frozenset({
    "twclid", "s",  # 's' is Twitter's share-tracking param
})

# Microsoft / Bing
_MICROSOFT_PARAMS: frozenset[str] = frozenset({
    "msclkid",
})

# Generic referral / sharing params found across CMS platforms
_GENERIC_PARAMS: frozenset[str] = frozenset({
    "ref", "source", "referer", "referrer",
    "from", "via", "origin",
    "share", "shared_via",
    "naver_from",    # Naver-specific referral
    "daum_from",     # Daum-specific referral
    "kakaotalkshare",
    "nclick_suffix", "n_media", "n_query", "n_rank", "n_ad_group",
    "n_ad", "n_keyword", "n_campaign_type",   # Naver ad click tracking
    "_ga",           # GA cookie value sometimes serialized into URL
    "yclid",         # Yandex click ID
    "wickedid",      # WickedReports
    "mc_cid", "mc_eid",  # Mailchimp
    "igshid",        # Instagram
    "linkId",        # various CMS link IDs
    "trk", "trkInfo",  # LinkedIn tracking
    "si",            # Spotify / misc
    "cmpid", "cmp",  # generic campaign IDs
})

TRACKING_PARAMS: frozenset[str] = (
    _GOOGLE_PARAMS | _META_PARAMS | _TWITTER_PARAMS | _MICROSOFT_PARAMS | _GENERIC_PARAMS
)

# ---------------------------------------------------------------------------
# Default ports that should be stripped from the netloc
# ---------------------------------------------------------------------------

_DEFAULT_PORTS: dict[str, int] = {"http": 80, "https": 443}

# ---------------------------------------------------------------------------
# Characters that are safe to decode from percent-encoding (RFC 3986 §2.3)
# Decoding reserved characters would change URL semantics.
# ---------------------------------------------------------------------------

_UNRESERVED = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789"
    "-._~"
)

# ---------------------------------------------------------------------------
# Site-name suffix patterns stripped from the end of titles during
# canonical title extraction (used by title_matcher, exposed here for reuse).
# ---------------------------------------------------------------------------

_SITE_SUFFIX_RE = re.compile(
    r"\s*[\|\-–—»:]\s*.{2,50}$",  # "Title | Site Name" or "Title - Site Name"
    re.UNICODE,
)


def _decode_unreserved(url: str) -> str:
    """Decode percent-encoded unreserved characters only.

    RFC 3986 §2.3 defines unreserved characters as safe to decode.
    Decoding reserved characters (e.g., %2F for /) would alter routing.

    Args:
        url: Raw URL string.

    Returns:
        URL with unreserved percent-encoded chars decoded.
    """
    # Pattern: %XX where XX are hex digits
    def _replace(match: re.Match) -> str:
        char = chr(int(match.group(1), 16))
        return char if char in _UNRESERVED else match.group(0)

    return re.sub(r"%([0-9A-Fa-f]{2})", _replace, url)


def _normalize_netloc(scheme: str, netloc: str) -> str:
    """Lowercase host, strip default port, strip 'www.' prefix.

    Args:
        scheme: URL scheme (already lowercased).
        netloc: Network location component from urlparse.

    Returns:
        Normalized netloc string.
    """
    # Split userinfo from host (userinfo is very rare in news URLs but handle it)
    if "@" in netloc:
        _userinfo, netloc = netloc.rsplit("@", 1)

    # Separate host and port
    if ":" in netloc:
        host, port_str = netloc.rsplit(":", 1)
        try:
            port = int(port_str)
            # Drop port if it is the default for this scheme
            if _DEFAULT_PORTS.get(scheme) == port:
                netloc = host
            else:
                netloc = f"{host}:{port}"
        except ValueError:
            pass  # Not a numeric port; keep as-is
    else:
        host = netloc

    # Lowercase
    netloc = netloc.lower()

    # Strip 'www.' prefix for canonical equivalence
    if netloc.startswith("www."):
        netloc = netloc[4:]

    return netloc


def _normalize_path(path: str) -> str:
    """Resolve '..' and '.' segments, remove trailing slash.

    Args:
        path: URL path component.

    Returns:
        Normalized path string.
    """
    if not path:
        return "/"

    # Split into segments and resolve . / ..
    parts = path.split("/")
    resolved: list[str] = []
    for part in parts:
        if part == "..":
            if resolved:
                resolved.pop()
        elif part == ".":
            pass
        else:
            resolved.append(part)

    path = "/".join(resolved)

    # Ensure leading slash
    if not path.startswith("/"):
        path = "/" + path

    # Remove trailing slash (except for root)
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    return path


def _strip_tracking_params(query_string: str) -> str:
    """Remove tracking parameters and sort remaining params alphabetically.

    Args:
        query_string: Raw query string (without leading '?').

    Returns:
        Cleaned, sorted query string. Empty string if no params remain.
    """
    if not query_string:
        return ""

    parsed = parse_qs(query_string, keep_blank_values=False)

    # Remove tracking params (case-insensitive key comparison)
    cleaned = {
        k: v
        for k, v in parsed.items()
        if k.lower() not in TRACKING_PARAMS
    }

    if not cleaned:
        return ""

    # Flatten to list of (key, value) pairs with sorted keys
    pairs: list[tuple[str, str]] = []
    for k in sorted(cleaned.keys()):
        for v in sorted(cleaned[k]):  # also sort multi-values for stability
            pairs.append((k, v))

    return urlencode(pairs)


class URLNormalizer:
    """Normalizes article URLs to canonical form for exact-match deduplication.

    Usage:
        normalizer = URLNormalizer()
        canonical = normalizer.normalize("https://www.example.com/article?utm_source=twitter#comments")
        # -> "https://example.com/article"

    The normalizer is stateless and thread-safe (no mutable state).
    """

    def normalize(self, url: str) -> str:
        """Return the canonical form of a URL.

        Transformations applied (in order):
            1. Strip leading/trailing whitespace.
            2. Decode percent-encoded unreserved characters.
            3. Normalize scheme: lowercase, prefer https over http.
            4. Normalize netloc: lowercase, strip default port, strip 'www.'.
            5. Normalize path: resolve '../' and './', remove trailing slash.
            6. Strip tracking query parameters; sort remaining params.
            7. Remove fragment.

        Args:
            url: Raw URL string (may include tracking params, fragment, etc.).

        Returns:
            Normalized URL string.

        Raises:
            ValueError: If the input is not a parseable URL (no scheme or host).
        """
        url = url.strip()

        # Decode unreserved percent-encoded characters first so parsing works correctly
        url = _decode_unreserved(url)

        parsed = urlparse(url)

        # Validate: must have scheme and host
        if not parsed.scheme or not parsed.netloc:
            # Attempt http:// prefix as a fallback for protocol-relative URLs
            if url.startswith("//"):
                url = "https:" + url
                parsed = urlparse(url)
            else:
                raise ValueError(f"URL has no scheme or host: {url!r}")

        # 1. Normalize scheme
        orig_scheme = parsed.scheme.lower()
        # Prefer https (nearly all modern news sites support it)
        scheme = "https" if orig_scheme == "http" else orig_scheme

        # 2. Normalize netloc — pass the ORIGINAL scheme for correct default-port
        # stripping (port 80 is default for http; stripping happens before promotion)
        netloc = _normalize_netloc(orig_scheme, parsed.netloc)

        # 3. Normalize path
        path = _normalize_path(parsed.path)

        # 4. Strip tracking params and sort
        query = _strip_tracking_params(parsed.query)

        # 5. Drop fragment entirely
        fragment = ""

        canonical = urlunparse((scheme, netloc, path, "", query, fragment))
        return canonical

    def are_equivalent(self, url_a: str, url_b: str) -> bool:
        """Return True if two URLs normalize to the same canonical form.

        Args:
            url_a: First URL.
            url_b: Second URL.

        Returns:
            True if both URLs are duplicates by URL normalization.
        """
        try:
            return self.normalize(url_a) == self.normalize(url_b)
        except ValueError:
            return False

    def url_key(self, url: str) -> str:
        """Return the normalized URL suitable for use as a dict/set key.

        Identical to normalize() but returns an empty string on error
        instead of raising, making it safe to use in bulk operations.

        Args:
            url: Raw URL string.

        Returns:
            Normalized URL, or empty string if normalization fails.
        """
        try:
            return self.normalize(url)
        except ValueError as exc:
            logger.warning(f"url_normalization_failed url={url!r} error={exc}")
            return ""
