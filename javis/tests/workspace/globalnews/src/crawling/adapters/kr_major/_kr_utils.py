"""Korean-specific utility functions for news site adapters.

Handles:
  - Korean date format parsing ("2024.03.15 14:30", "2024년 3월 15일",
    "3시간 전", "어제", "입력 2024.03.15 10:30 | 수정 ..." etc.).
  - Korean author/byline extraction ("홍길동 기자", "기자 = 홍길동").
  - EUC-KR / CP949 encoding detection and conversion.
  - URL normalization for Korean news sites.
  - Category extraction from URL path segments.

Reference:
    Step 6 Crawling Strategies, Korean sections (Groups A-D).
    Step 1 Site Reconnaissance, Korean site analysis.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# KST timezone (UTC+9)
KST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# Korean date parsing
# ---------------------------------------------------------------------------

# Compiled regex patterns for Korean date formats
_KR_FULL_DATE_RE = re.compile(
    r"(\d{4})\s*[년./-]\s*(\d{1,2})\s*[월./-]\s*(\d{1,2})\s*[일.]?"
    r"(?:\s*(\d{1,2})\s*[:시]\s*(\d{1,2})\s*분?\s*(?:(\d{1,2})\s*초?)?)?"
)

# "2024.03.15 14:30" or "2024-03-15 14:30:00"
_DOT_DATE_RE = re.compile(
    r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})"
    r"(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?"
)

# Relative time: "N시간 전", "N분 전", "N일 전"
_RELATIVE_TIME_RE = re.compile(
    r"(\d+)\s*(초|분|시간|일|주|개월|달)\s*전"
)

# "오전 10:30" or "오후 2:30" (AM/PM Korean)
_KR_AMPM_RE = re.compile(
    r"(오전|오후)\s*(\d{1,2}):(\d{2})(?::(\d{2}))?"
)

# "입력 2024.03.15 10:30" prefix stripping
_INPUT_PREFIX_RE = re.compile(
    r"^(?:입력|등록|발행|작성|게시|수정|최종수정)\s*"
)

# Day-of-week suffix: "2024.03.15(금)" — strip the parenthetical
_DOW_SUFFIX_RE = re.compile(r"\([월화수목금토일]\)")

# "어제", "오늘", "그저께"
_RELATIVE_DAY_MAP = {
    "오늘": 0,
    "어제": 1,
    "그저께": 2,
    "그끄저께": 3,
}


def parse_korean_date(date_str: str) -> datetime | None:
    """Parse a Korean date string to a UTC datetime.

    Handles all major Korean news date formats:
      - ISO 8601: "2024-03-15T10:30:00+09:00"
      - Dotted: "2024.03.15 14:30", "2024.03.15"
      - Korean: "2024년 3월 15일 14시 30분"
      - Relative: "3시간 전", "어제", "2일 전"
      - AM/PM Korean: "오후 2:30"
      - With prefix: "입력 2024.03.15 10:30 | 수정 2024.03.15 11:45"
      - With day-of-week: "2024.03.15(금)"

    Args:
        date_str: Raw date string from the page.

    Returns:
        datetime in UTC, or None if parsing fails entirely.
    """
    if not date_str or not date_str.strip():
        return None

    original = date_str.strip()

    # Strip common prefixes (입력, 수정, etc.)
    cleaned = _INPUT_PREFIX_RE.sub("", original).strip()

    # If there's a " | " separator (입력/수정 pair), take the first part
    if " | " in cleaned:
        cleaned = cleaned.split(" | ")[0].strip()
        # Strip prefix again in case format is "입력 2024.03.15 | 수정 ..."
        cleaned = _INPUT_PREFIX_RE.sub("", cleaned).strip()

    # Strip day-of-week parenthetical: "2024.03.15(금)" -> "2024.03.15"
    cleaned = _DOW_SUFFIX_RE.sub("", cleaned).strip()

    # 1. Try ISO 8601 first
    try:
        dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=KST)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        pass

    # 2. Try relative day words ("오늘", "어제", etc.)
    for word, days_ago in _RELATIVE_DAY_MAP.items():
        if word in cleaned:
            now = datetime.now(KST)
            target = now - timedelta(days=days_ago)
            # Try to extract time component if present
            ampm_match = _KR_AMPM_RE.search(cleaned)
            if ampm_match:
                hour, minute = _parse_ampm(ampm_match)
                target = target.replace(hour=hour, minute=minute, second=0)
            else:
                # Check for simple HH:MM
                time_match = re.search(r"(\d{1,2}):(\d{2})", cleaned)
                if time_match:
                    target = target.replace(
                        hour=int(time_match.group(1)),
                        minute=int(time_match.group(2)),
                        second=0,
                    )
                else:
                    target = target.replace(hour=0, minute=0, second=0)
            return target.astimezone(timezone.utc)

    # 3. Try relative time expressions ("N시간 전", "N분 전")
    rel_match = _RELATIVE_TIME_RE.search(cleaned)
    if rel_match:
        return _parse_relative_time(rel_match)

    # 4. Try AM/PM Korean combined with date FIRST — must detect 오전/오후
    # before other date-only matchers capture the date part without time.
    # e.g., "2024.03.15 오후 2:30"
    ampm_match = _KR_AMPM_RE.search(cleaned)
    if ampm_match:
        # Try to find a date part before it
        date_part = cleaned[:ampm_match.start()].strip()
        date_part = _DOW_SUFFIX_RE.sub("", date_part).strip()
        dot_m = _DOT_DATE_RE.search(date_part)
        if dot_m:
            hour, minute = _parse_ampm(ampm_match)
            try:
                dt = datetime(
                    year=int(dot_m.group(1)),
                    month=int(dot_m.group(2)),
                    day=int(dot_m.group(3)),
                    hour=hour,
                    minute=minute,
                    tzinfo=KST,
                )
                return dt.astimezone(timezone.utc)
            except (ValueError, TypeError):
                pass

    # 5. Try Korean full date ("2024년 3월 15일 14시 30분")
    kr_match = _KR_FULL_DATE_RE.search(cleaned)
    if kr_match:
        return _build_datetime_from_groups(kr_match)

    # 6. Try dot/dash date ("2024.03.15 14:30")
    dot_match = _DOT_DATE_RE.search(cleaned)
    if dot_match:
        return _build_datetime_from_groups(dot_match)

    # 7. Try RFC 2822 (for RSS feeds)
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(original)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError, IndexError):
        pass

    logger.debug("korean_date_parse_failed date_str=%r", original)
    return None


def _parse_ampm(match: re.Match) -> tuple[int, int]:
    """Parse Korean AM/PM time match into 24-hour (hour, minute).

    Args:
        match: Regex match with groups (ampm, hour, minute, [second]).

    Returns:
        Tuple of (hour_24, minute).
    """
    ampm = match.group(1)
    hour = int(match.group(2))
    minute = int(match.group(3))

    if ampm == "오후" and hour != 12:
        hour += 12
    elif ampm == "오전" and hour == 12:
        hour = 0

    return hour, minute


def _parse_relative_time(match: re.Match) -> datetime:
    """Convert a relative time expression to an absolute UTC datetime.

    Args:
        match: Regex match with groups (number, unit).

    Returns:
        datetime in UTC.
    """
    amount = int(match.group(1))
    unit = match.group(2)

    now = datetime.now(timezone.utc)

    delta_map = {
        "초": timedelta(seconds=amount),
        "분": timedelta(minutes=amount),
        "시간": timedelta(hours=amount),
        "일": timedelta(days=amount),
        "주": timedelta(weeks=amount),
        "개월": timedelta(days=amount * 30),
        "달": timedelta(days=amount * 30),
    }

    delta = delta_map.get(unit, timedelta())
    return now - delta


def _build_datetime_from_groups(match: re.Match) -> datetime | None:
    """Build a datetime from regex groups (year, month, day, [hour, min, sec]).

    Assumes KST timezone if no timezone info is present.

    Args:
        match: Regex match with groups for date/time components.

    Returns:
        datetime in UTC, or None if construction fails.
    """
    try:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        hour = int(match.group(4)) if match.group(4) else 0
        minute = int(match.group(5)) if match.group(5) else 0
        second = int(match.group(6)) if match.lastindex and match.lastindex >= 6 and match.group(6) else 0

        dt = datetime(
            year=year, month=month, day=day,
            hour=hour, minute=minute, second=second,
            tzinfo=KST,
        )
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


# ---------------------------------------------------------------------------
# Korean author extraction
# ---------------------------------------------------------------------------

# Common Korean byline patterns
_BYLINE_PATTERNS = [
    # "홍길동 기자" — name followed by reporter suffix
    re.compile(r"([가-힣]{2,4})\s*(기자|특파원|선임기자|수습기자|객원기자|편집위원|논설위원|칼럼니스트)"),
    # "기자 = 홍길동" or "기자=홍길동"
    re.compile(r"(?:기자|특파원)\s*[=:]\s*([가-힣]{2,4})"),
    # "CBS노컷뉴스 홍길동 기자" — prefix + name + suffix
    re.compile(r"(?:[가-힣A-Za-z]+)\s+([가-힣]{2,4})\s*기자"),
    # "[홍길동]" — bracketed name
    re.compile(r"\[([가-힣]{2,4})\]"),
    # Email-based: "gildong@chosun.com" — extract name part
    re.compile(r"([가-힣]{2,4})\s*[\w.+-]+@[\w-]+\.[\w.]+"),
]

# Suffixes to strip from author names
_AUTHOR_SUFFIXES = [
    "기자", "특파원", "선임기자", "수습기자", "객원기자",
    "편집위원", "논설위원", "칼럼니스트", "리포터", "통신원",
]

# Prefixes to strip from author bylines
_AUTHOR_PREFIXES = [
    "기자", "글", "사진", "영상",
    "CBS노컷뉴스", "머니투데이", "뉴스1",
]


def extract_korean_author(text: str) -> str | None:
    """Extract an author name from a Korean byline string.

    Handles patterns like:
      - "홍길동 기자"
      - "기자 = 홍길동"
      - "CBS노컷뉴스 홍길동 기자"
      - "[홍길동]"
      - "홍길동 기자 gildong@chosun.com"

    Args:
        text: Raw byline/author text from the page.

    Returns:
        Cleaned author name, or None if no Korean name found.
    """
    if not text or not text.strip():
        return None

    text = text.strip()

    # Try each pattern
    for pattern in _BYLINE_PATTERNS:
        match = pattern.search(text)
        if match:
            name = match.group(1).strip()
            if _is_valid_korean_name(name):
                return name

    # Fallback: try to extract any 2-4 char Korean-only string
    # that is not a common word
    korean_names = re.findall(r"([가-힣]{2,4})", text)
    for candidate in korean_names:
        if _is_valid_korean_name(candidate):
            return candidate

    # If nothing Korean found, return cleaned text (could be English name)
    cleaned = text.strip()
    for suffix in _AUTHOR_SUFFIXES:
        cleaned = cleaned.replace(suffix, "").strip()
    for prefix in _AUTHOR_PREFIXES:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()

    return cleaned if cleaned else None


def _is_valid_korean_name(name: str) -> bool:
    """Check if a string looks like a valid Korean personal name.

    Filters out common non-name Korean words (newspaper names, section
    names, action words).

    Args:
        name: Candidate Korean name string (2-4 characters).

    Returns:
        True if the string is likely a personal name.
    """
    if len(name) < 2 or len(name) > 4:
        return False

    # Common non-name words to exclude
    non_names = {
        "기자", "특파원", "사진", "영상", "글쓴이", "작성자",
        "편집국", "취재팀", "사회부", "정치부", "경제부", "국제부",
        "문화부", "스포츠", "연예부", "기획팀", "데이터", "디지털",
        "뉴스팀", "뉴스룸", "편집부", "논설실",
        "입력", "수정", "등록", "게시",
        "조선일보", "중앙일보", "동아일보", "한겨레",
    }
    return name not in non_names


# ---------------------------------------------------------------------------
# Encoding handling
# ---------------------------------------------------------------------------

def detect_and_decode_korean(raw_bytes: bytes, declared_charset: str = "utf-8") -> str:
    """Detect encoding and decode Korean text.

    Tries the declared charset first, then falls back through common
    Korean encodings. This handles legacy sites that declare UTF-8 but
    actually serve EUC-KR, or vice versa.

    Fallback chain: declared -> UTF-8 -> EUC-KR -> CP949 -> latin-1.

    Args:
        raw_bytes: Raw response bytes.
        declared_charset: Charset declared in HTTP headers or HTML meta.

    Returns:
        Decoded string.
    """
    # Try declared charset first
    if declared_charset:
        try:
            return raw_bytes.decode(declared_charset)
        except (UnicodeDecodeError, LookupError):
            pass

    # Try UTF-8
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        pass

    # Try EUC-KR (superset: CP949)
    try:
        return raw_bytes.decode("euc-kr")
    except UnicodeDecodeError:
        pass

    try:
        return raw_bytes.decode("cp949")
    except UnicodeDecodeError:
        pass

    # Last resort: latin-1 (never fails, but may produce garbled Korean)
    return raw_bytes.decode("latin-1")


# ---------------------------------------------------------------------------
# URL and category utilities
# ---------------------------------------------------------------------------

def extract_category_from_url(url: str, site_id: str = "") -> str | None:
    """Extract article category from a Korean news site URL.

    Most Korean sites encode the category in the URL path:
      - chosun.com/politics/ -> "politics"
      - hani.co.kr/arti/economy/ -> "economy"
      - mk.co.kr/news/stock/ -> "stock"
      - yna.co.kr/economy/index -> "economy"

    Args:
        url: Article URL.
        site_id: Site identifier for site-specific parsing.

    Returns:
        Category string, or None if extraction fails.
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    path = parsed.path.strip("/")
    segments = [s for s in path.split("/") if s]

    if not segments:
        return None

    # Site-specific category extraction
    if site_id == "hani":
        # hani.co.kr/arti/{category}/{subcategory}/...
        if len(segments) >= 2 and segments[0] == "arti":
            return segments[1]

    elif site_id == "mk":
        # mk.co.kr/news/{category}/...
        if len(segments) >= 2 and segments[0] == "news":
            return segments[1]

    elif site_id == "yna":
        # yna.co.kr/{category}/index or yna.co.kr/{category}/all
        if segments[0] in (
            "politics", "economy", "society", "international",
            "sports", "culture", "science", "nk",
        ):
            return segments[0]

    elif site_id == "fnnews":
        # fnnews.com/news/{article_id} -- category from section code
        return None  # fnnews uses numeric section codes; defer to metadata

    elif site_id in ("chosun", "donga", "joongang"):
        # Direct path segments: /politics/, /economy/, etc.
        category_words = {
            "politics", "economy", "national", "society",
            "international", "sports", "culture", "culture-life",
            "opinion", "entertainment", "tech", "science",
            "world", "money", "life", "lifestyle",
        }
        for seg in segments:
            if seg.lower() in category_words:
                return seg.lower()

    # Generic: return the first meaningful path segment
    skip_prefixes = {"article", "news", "view", "read", "arti", "content"}
    for seg in segments:
        seg_lower = seg.lower()
        if seg_lower not in skip_prefixes and not seg_lower.isdigit():
            # Check if it looks like a category (short, alphabetic)
            if len(seg_lower) <= 20 and re.match(r"^[a-z_-]+$", seg_lower):
                return seg_lower

    return None
