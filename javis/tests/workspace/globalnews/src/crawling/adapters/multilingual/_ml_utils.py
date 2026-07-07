"""Multilingual utility functions for Asia-Pacific and Europe/ME adapters.

Provides encoding detection, CJK date parsing, RTL text normalization,
and script detection used by all 13 multilingual site adapters (Groups F+G).

Reference:
    Step 5 Architecture Blueprint, Section 4.2.
    Step 6 crawl-strategy-asia.md Section 8 (CJK Technical Notes).
    Step 6 crawl-strategy-global.md (Language & Encoding Matrix).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
from typing import Any

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Timezone constants
# ---------------------------------------------------------------------------
TZ_CST = timezone(timedelta(hours=8))    # China Standard Time (UTC+8)
TZ_JST = timezone(timedelta(hours=9))    # Japan Standard Time (UTC+9)
TZ_IST = timezone(timedelta(hours=5, minutes=30))  # India Standard Time (UTC+5:30)
TZ_MSK = timezone(timedelta(hours=3))    # Moscow Standard Time (UTC+3)
TZ_CET = timezone(timedelta(hours=1))    # Central European Time (UTC+1)
TZ_GMT = timezone.utc                     # GMT / UTC

# ---------------------------------------------------------------------------
# Chinese date parsing
# ---------------------------------------------------------------------------

# Pattern: 2026年02月26日12:25 or 2026年2月26日 12:25
_CHINESE_DATE_FULL = re.compile(
    r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*(\d{1,2})\s*[:：]\s*(\d{1,2})"
)

# Pattern: 2026年02月26日 (date only)
_CHINESE_DATE_ONLY = re.compile(
    r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
)

# Pattern: 02月26日 (month-day only, year inferred)
_CHINESE_MONTH_DAY = re.compile(
    r"(\d{1,2})\s*月\s*(\d{1,2})\s*日"
)

# Relative time patterns: "X小时前", "X分钟前", "X天前"
_CHINESE_RELATIVE = re.compile(r"(\d+)\s*(小时|分钟|天|秒)\s*前")


def parse_chinese_date(date_str: str) -> datetime | None:
    """Parse Chinese date formats to UTC datetime.

    Supports:
        - 2026年02月26日12:25
        - 2026年2月26日 12:25
        - 2026年02月26日
        - 3小时前, 5分钟前, 2天前

    Args:
        date_str: Chinese date string.

    Returns:
        datetime in UTC, or None if parsing fails.
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    # Full date with time
    m = _CHINESE_DATE_FULL.search(date_str)
    if m:
        try:
            dt = datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                int(m.group(4)), int(m.group(5)),
                tzinfo=TZ_CST,
            )
            return dt.astimezone(timezone.utc)
        except (ValueError, OverflowError):
            pass

    # Date only (use noon to prevent calendar date shift during UTC conversion)
    m = _CHINESE_DATE_ONLY.search(date_str)
    if m:
        try:
            dt = datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                12, 0,  # noon default prevents date shift on TZ conversion
                tzinfo=TZ_CST,
            )
            return dt.astimezone(timezone.utc)
        except (ValueError, OverflowError):
            pass

    # Relative time
    m = _CHINESE_RELATIVE.search(date_str)
    if m:
        amount = int(m.group(1))
        unit = m.group(2)
        now = datetime.now(timezone.utc)
        if unit == "小时":
            return now - timedelta(hours=amount)
        elif unit == "分钟":
            return now - timedelta(minutes=amount)
        elif unit == "天":
            return now - timedelta(days=amount)
        elif unit == "秒":
            return now - timedelta(seconds=amount)

    return None


# ---------------------------------------------------------------------------
# Japanese date parsing
# ---------------------------------------------------------------------------

# Pattern: 2026年2月26日 14時30分
_JAPANESE_DATE_FULL = re.compile(
    r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*"
    r"(?:\([^)]*\)\s*)?"  # Optional day-of-week in parens: (水)
    r"(\d{1,2})\s*時\s*(\d{1,2})\s*分"
)

# Pattern: 2026年2月26日 (date only, no time)
_JAPANESE_DATE_ONLY = re.compile(
    r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
)

# Relative: 3時間前, 5分前, 2日前
_JAPANESE_RELATIVE = re.compile(r"(\d+)\s*(時間|分|日|秒)\s*前")


def parse_japanese_date(date_str: str) -> datetime | None:
    """Parse Japanese date formats to UTC datetime.

    Supports:
        - 2026年2月26日 14時30分
        - 2026年2月26日(水) 14時30分
        - 2026年2月26日
        - 3時間前, 5分前, 2日前

    Args:
        date_str: Japanese date string.

    Returns:
        datetime in UTC, or None if parsing fails.
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    # Full date with time
    m = _JAPANESE_DATE_FULL.search(date_str)
    if m:
        try:
            dt = datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                int(m.group(4)), int(m.group(5)),
                tzinfo=TZ_JST,
            )
            return dt.astimezone(timezone.utc)
        except (ValueError, OverflowError):
            pass

    # Date only (use noon to prevent calendar date shift during UTC conversion)
    m = _JAPANESE_DATE_ONLY.search(date_str)
    if m:
        try:
            dt = datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                12, 0,  # noon default prevents date shift on TZ conversion
                tzinfo=TZ_JST,
            )
            return dt.astimezone(timezone.utc)
        except (ValueError, OverflowError):
            pass

    # Relative time
    m = _JAPANESE_RELATIVE.search(date_str)
    if m:
        amount = int(m.group(1))
        unit = m.group(2)
        now = datetime.now(timezone.utc)
        if unit == "時間":
            return now - timedelta(hours=amount)
        elif unit == "分":
            return now - timedelta(minutes=amount)
        elif unit == "日":
            return now - timedelta(days=amount)
        elif unit == "秒":
            return now - timedelta(seconds=amount)

    return None


def strip_ruby_annotations(html: str) -> str:
    """Remove ruby/furigana annotations from HTML, keeping base text.

    Japanese HTML may contain <ruby> tags with <rt> reading annotations.
    For text extraction, we want the base kanji text only.

    Args:
        html: HTML string potentially containing ruby annotations.

    Returns:
        HTML with <rt>, <rp>, and <ruby> tags removed.
    """
    text = re.sub(r"<rt[^>]*>.*?</rt>", "", html, flags=re.DOTALL)
    text = re.sub(r"<rp[^>]*>.*?</rp>", "", text, flags=re.DOTALL)
    text = re.sub(r"</?ruby[^>]*>", "", text)
    return text


# ---------------------------------------------------------------------------
# German date parsing
# ---------------------------------------------------------------------------

_GERMAN_MONTHS: dict[str, int] = {
    "januar": 1, "februar": 2, "m\u00e4rz": 3, "maerz": 3, "marz": 3,
    "april": 4, "mai": 5, "juni": 6, "juli": 7, "august": 8,
    "september": 9, "oktober": 10, "november": 11, "dezember": 12,
    # Abbreviated
    "jan": 1, "feb": 2, "mrz": 3, "apr": 4, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dez": 12,
}

# Pattern: "15. Februar 2026" or "15. Februar 2026, 14:30 Uhr"
_GERMAN_DATE_LONG = re.compile(
    r"(\d{1,2})\.\s*(\w+)\s+(\d{4})"
    r"(?:\s*,?\s*(\d{1,2}):(\d{2})\s*(?:Uhr)?)?"
)

# Pattern: "15.02.2026" or "15.02.2026, 14:30"
_GERMAN_DATE_SHORT = re.compile(
    r"(\d{1,2})\.(\d{1,2})\.(\d{4})"
    r"(?:\s*,?\s*(\d{1,2}):(\d{2}))?"
)


def parse_german_date(date_str: str) -> datetime | None:
    """Parse German date formats to UTC datetime.

    Supports:
        - 15. Februar 2026
        - 15. Februar 2026, 14:30 Uhr
        - 15.02.2026
        - 15.02.2026, 14:30

    Args:
        date_str: German date string.

    Returns:
        datetime in UTC, or None if parsing fails.
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    # Long format with German month name
    m = _GERMAN_DATE_LONG.search(date_str)
    if m:
        month_name = m.group(2).lower()
        month = _GERMAN_MONTHS.get(month_name)
        if month:
            try:
                has_time = m.group(4) is not None
                hour = int(m.group(4)) if has_time else 12  # noon default
                minute = int(m.group(5)) if has_time else 0
                dt = datetime(
                    int(m.group(3)), month, int(m.group(1)),
                    hour, minute,
                    tzinfo=TZ_CET,
                )
                return dt.astimezone(timezone.utc)
            except (ValueError, OverflowError):
                pass

    # Short numeric format
    m = _GERMAN_DATE_SHORT.search(date_str)
    if m:
        try:
            has_time = m.group(4) is not None
            hour = int(m.group(4)) if has_time else 12  # noon default
            minute = int(m.group(5)) if has_time else 0
            dt = datetime(
                int(m.group(3)), int(m.group(2)), int(m.group(1)),
                hour, minute,
                tzinfo=TZ_CET,
            )
            return dt.astimezone(timezone.utc)
        except (ValueError, OverflowError):
            pass

    return None


# ---------------------------------------------------------------------------
# French date parsing
# ---------------------------------------------------------------------------

_FRENCH_MONTHS: dict[str, int] = {
    "janvier": 1, "f\u00e9vrier": 2, "fevrier": 2,
    "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "ao\u00fbt": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "d\u00e9cembre": 12, "decembre": 12,
    # Abbreviated
    "janv": 1, "f\u00e9vr": 2, "fevr": 2, "avr": 4, "juil": 7,
    "sept": 9, "oct": 10, "nov": 11, "d\u00e9c": 12, "dec": 12,
}

# Pattern: "15 janvier 2026" or "15 janvier 2026 a 14h30"
_FRENCH_DATE_LONG = re.compile(
    r"(\d{1,2})\s+(\w+)\s+(\d{4})"
    r"(?:\s+\u00e0\s+(\d{1,2})\s*[hH]\s*(\d{2}))?"
)


def parse_french_date(date_str: str) -> datetime | None:
    """Parse French date formats to UTC datetime.

    Supports:
        - 15 janvier 2026
        - 15 janvier 2026 a 14h30

    Args:
        date_str: French date string.

    Returns:
        datetime in UTC, or None if parsing fails.
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    m = _FRENCH_DATE_LONG.search(date_str)
    if m:
        month_name = m.group(2).lower()
        month = _FRENCH_MONTHS.get(month_name)
        if month:
            try:
                has_time = m.group(4) is not None
                hour = int(m.group(4)) if has_time else 12  # noon default
                minute = int(m.group(5)) if has_time else 0
                dt = datetime(
                    int(m.group(3)), month, int(m.group(1)),
                    hour, minute,
                    tzinfo=TZ_CET,
                )
                return dt.astimezone(timezone.utc)
            except (ValueError, OverflowError):
                pass

    return None


# ---------------------------------------------------------------------------
# Encoding detection
# ---------------------------------------------------------------------------

def detect_encoding(raw_bytes: bytes, http_charset: str = "") -> str:
    """Auto-detect encoding from HTTP headers, meta charset, BOM, and heuristics.

    Priority: HTTP header > meta charset > BOM > chardet heuristic > UTF-8 default.

    Used by people.com.cn (GB2312/GBK), yomiuri.co.jp (Shift_JIS), and
    other sites that may serve non-UTF-8 content.

    Args:
        raw_bytes: Raw response bytes.
        http_charset: Charset from HTTP Content-Type header (may be empty).

    Returns:
        Encoding name suitable for bytes.decode().
    """
    # 1. HTTP header charset
    if http_charset:
        normalized = _normalize_encoding_name(http_charset)
        if normalized:
            return normalized

    # 2. HTML meta charset in first 4KB
    head_bytes = raw_bytes[:4096]
    meta_charset = _extract_meta_charset(head_bytes)
    if meta_charset:
        normalized = _normalize_encoding_name(meta_charset)
        if normalized:
            return normalized

    # 3. BOM detection
    if raw_bytes[:3] == b"\xef\xbb\xbf":
        return "utf-8"
    if raw_bytes[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "utf-16"

    # 4. chardet heuristic
    try:
        import chardet
        result = chardet.detect(raw_bytes[:10000])
        if result and result.get("confidence", 0) > 0.8:
            detected = result.get("encoding", "")
            if detected:
                normalized = _normalize_encoding_name(detected)
                if normalized:
                    return normalized
    except ImportError:
        logger.debug("chardet_not_available_falling_back_to_utf8")

    # 5. Default to UTF-8
    return "utf-8"


def _extract_meta_charset(head_bytes: bytes) -> str:
    """Extract charset from HTML meta tags in the first bytes of a page.

    Looks for:
        <meta charset="...">
        <meta http-equiv="Content-Type" content="text/html; charset=...">

    Args:
        head_bytes: First ~4KB of the HTML page as bytes.

    Returns:
        Charset string, or empty string if not found.
    """
    try:
        head_text = head_bytes.decode("ascii", errors="ignore")
    except Exception:
        return ""

    # <meta charset="...">
    m = re.search(r'<meta[^>]+charset=["\']?([^"\'\s;>]+)', head_text, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # <meta http-equiv="Content-Type" content="text/html; charset=...">
    m = re.search(
        r'<meta[^>]+http-equiv=["\']?Content-Type["\']?[^>]+content=["\'][^"\']*charset=([^"\'\s;>]+)',
        head_text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()

    return ""


def _normalize_encoding_name(encoding: str) -> str:
    """Normalize encoding name to a Python codec name.

    Maps GB2312/GBK to gb18030 (superset), Shift_JIS to cp932 (Windows superset).

    Args:
        encoding: Raw encoding name string.

    Returns:
        Normalized encoding name, or empty string if unrecognized.
    """
    if not encoding:
        return ""

    enc = encoding.strip().lower().replace("-", "").replace("_", "")

    mapping: dict[str, str] = {
        "utf8": "utf-8",
        "utf16": "utf-16",
        "gb2312": "gb18030",
        "gbk": "gb18030",
        "gb18030": "gb18030",
        "big5": "big5",
        "shiftjis": "cp932",
        "sjis": "cp932",
        "cp932": "cp932",
        "eucjp": "euc-jp",
        "euckr": "euc-kr",
        "cp949": "euc-kr",
        "windows1256": "windows-1256",
        "iso88591": "iso-8859-1",
        "latin1": "iso-8859-1",
        "ascii": "ascii",
    }

    return mapping.get(enc, encoding.strip().lower())


def decode_with_fallback(
    raw_bytes: bytes,
    primary_encoding: str = "utf-8",
    fallback_encodings: list[str] | None = None,
    http_charset: str = "",
) -> str:
    """Decode bytes with a cascading encoding fallback chain.

    Tries: detected encoding > primary > each fallback > utf-8 with replace.

    Args:
        raw_bytes: Raw response bytes.
        primary_encoding: Expected encoding for this site.
        fallback_encodings: Additional encodings to try in order.
        http_charset: Charset from HTTP Content-Type header.

    Returns:
        Decoded string.
    """
    # Try auto-detected encoding first
    detected = detect_encoding(raw_bytes, http_charset)
    if detected and detected != primary_encoding:
        try:
            return raw_bytes.decode(detected, errors="strict")
        except (UnicodeDecodeError, LookupError):
            pass

    # Try primary encoding
    try:
        text = raw_bytes.decode(primary_encoding, errors="strict")
        # Verify no excessive replacement characters
        if text.count("\ufffd") / max(len(text), 1) < 0.005:
            return text
    except (UnicodeDecodeError, LookupError):
        pass

    # Try fallbacks
    if fallback_encodings:
        for enc in fallback_encodings:
            try:
                text = raw_bytes.decode(enc, errors="strict")
                if text.count("\ufffd") / max(len(text), 1) < 0.005:
                    return text
            except (UnicodeDecodeError, LookupError):
                continue

    # Last resort: utf-8 with replacement
    return raw_bytes.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# RTL text handling
# ---------------------------------------------------------------------------

# Bidirectional control characters
_BIDI_CHARS = "\u200f\u200e\u061c\u200b\ufeff\u202a\u202b\u202c\u202d\u202e"
_BIDI_TRANS = str.maketrans("", "", _BIDI_CHARS)


def strip_rtl_marks(text: str) -> str:
    """Strip RTL/LTR directional marks and bidi control characters.

    Used for Arabic and Hebrew content where directional marks may
    appear in extracted text but are not needed for analysis.

    Args:
        text: Text potentially containing bidi marks.

    Returns:
        Text with directional marks removed.
    """
    return text.translate(_BIDI_TRANS)


# ---------------------------------------------------------------------------
# Chinese author extraction
# ---------------------------------------------------------------------------

# Common post-name words in Chinese bylines that signal end of author name.
# Used as lookahead to determine where the name ends and the verb begins.
# E.g., "记者王明报道" -> "王明" because "报道" is a post-name verb.
_CN_POST_NAME_WORDS = (
    "报道|发自|摄影|摄|编辑|综合|采写|撰文|述评|从|在|说|表示|称|据|指出|"
    "特约|通讯员|供稿|整理|实习|电|讯|消息"
)

# Pattern: 记者 + 2-4 Chinese characters, stopping before known post-name words.
# Strategy: match 2-4 CJK chars but only up to the point before a post-name word.
_CHINESE_REPORTER = re.compile(
    r"记者\s*([\u4e00-\u9fff]{2,4}?)(?=" + _CN_POST_NAME_WORDS + r"|[^\u4e00-\u9fff]|$)"
)
# Pattern: 编辑：+ 2-3 Chinese characters (editors have short names)
_CHINESE_EDITOR = re.compile(
    r"编辑[：:]\s*([\u4e00-\u9fff]{2,3})(?=[^\u4e00-\u9fff]|$)"
)
# Pattern: 来源：source name
_CHINESE_SOURCE = re.compile(r"来源[：:]\s*([\u4e00-\u9fff\w]+)")


def extract_chinese_author(text: str) -> str | None:
    """Extract Chinese author name from article text.

    Chinese bylines follow patterns like:
        - 记者王明 (reporter Wang Ming)
        - 编辑：李红 (editor: Li Hong)
        - 来源：人民网 (source: People's Net)

    Args:
        text: Article body text or byline text.

    Returns:
        Author name, or None if not found.
    """
    # Try reporter pattern first
    m = _CHINESE_REPORTER.search(text)
    if m:
        return m.group(1)

    # Try editor pattern
    m = _CHINESE_EDITOR.search(text)
    if m:
        return m.group(1)

    return None


# ---------------------------------------------------------------------------
# Japanese author extraction
# ---------------------------------------------------------------------------

# Pattern: 記者 + 2-6 chars (kanji/hiragana/katakana)
_JAPANESE_REPORTER = re.compile(
    r"記者\s*([\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]{2,6})"
)
# Pattern: name + 記者
_JAPANESE_REPORTER_SUFFIX = re.compile(
    r"([\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]{2,6})\s*記者"
)


def extract_japanese_author(text: str) -> str | None:
    """Extract Japanese author name from article text.

    Japanese bylines follow patterns like:
        - 記者 山田太郎 (reporter Yamada Taro)
        - 山田太郎 記者 (Yamada Taro reporter)
        - （読売新聞） (wire attribution)

    Args:
        text: Article body text or byline text.

    Returns:
        Author name, or None if not found.
    """
    m = _JAPANESE_REPORTER.search(text)
    if m:
        return m.group(1)

    m = _JAPANESE_REPORTER_SUFFIX.search(text)
    if m:
        return m.group(1)

    return None


# ---------------------------------------------------------------------------
# Script detection
# ---------------------------------------------------------------------------

def detect_primary_script(text: str) -> str:
    """Detect the primary script of a text sample.

    Counts characters in different Unicode ranges and returns
    the dominant script type.

    Args:
        text: Text sample (at least 50 characters recommended).

    Returns:
        One of: "cjk", "arabic", "hebrew", "cyrillic", "latin", "unknown".
    """
    if not text or len(text) < 5:
        return "unknown"

    cjk = 0
    arabic = 0
    hebrew = 0
    cyrillic = 0
    latin = 0

    for ch in text:
        cp = ord(ch)
        if 0x4E00 <= cp <= 0x9FFF or 0x3040 <= cp <= 0x30FF:
            cjk += 1
        elif 0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F:
            arabic += 1
        elif 0x0590 <= cp <= 0x05FF:
            hebrew += 1
        elif 0x0400 <= cp <= 0x04FF:
            cyrillic += 1
        elif 0x0041 <= cp <= 0x007A or 0x00C0 <= cp <= 0x024F:
            latin += 1

    counts = {
        "cjk": cjk,
        "arabic": arabic,
        "hebrew": hebrew,
        "cyrillic": cyrillic,
        "latin": latin,
    }

    max_script = max(counts, key=counts.get)  # type: ignore[arg-type]
    if counts[max_script] == 0:
        return "unknown"
    return max_script
