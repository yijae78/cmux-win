"""GlobalNews Pipeline — Interactive Dashboard (Multi-Period).

Launch:
    streamlit run dashboard.py

Reads Parquet/JSONL/SQLite outputs produced by the 8-stage analysis pipeline.
Supports daily, monthly, quarterly, and yearly aggregation via sidebar controls.

Tabs: Overview, Topics, Sentiment & Emotions, Time Series, Word Cloud,
      Article Explorer.
"""

from __future__ import annotations

import datetime
import json
import re
import sqlite3
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from wordcloud import WordCloud

# ---------------------------------------------------------------------------
# Base paths
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Sub-directory names that contain date-partitioned outputs
_DATE_PARTITIONED_DIRS = ("raw", "processed", "features", "analysis", "output")

# ---------------------------------------------------------------------------
# Live crawling helpers
# ---------------------------------------------------------------------------

import glob as _glob_mod


def _find_active_crawl_date() -> str | None:
    """Find a date directory with an active crawl (.crawl_state.json exists)."""
    raw_dir = DATA_DIR / "raw"
    if not raw_dir.exists():
        return None
    for p in sorted(raw_dir.iterdir(), reverse=True):
        if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name):
            if (p / ".crawl_state.json").exists():
                return p.name
    return None


def _load_crawl_state(date_str: str) -> dict:
    """Load .crawl_state.json for a given date."""
    path = DATA_DIR / "raw" / date_str / ".crawl_state.json"
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _count_tmp_articles(date_str: str) -> int:
    """Count lines in the temp JSONL file (articles collected so far)."""
    pattern = str(DATA_DIR / "raw" / date_str / "*.jsonl.tmp")
    for fpath in _glob_mod.glob(pattern):
        try:
            with open(fpath, encoding="utf-8", errors="ignore") as f:
                return sum(1 for line in f if line.strip())
        except Exception:
            return 0
    # Also check final file
    final = DATA_DIR / "raw" / date_str / "all_articles.jsonl"
    if final.exists():
        try:
            with open(final, encoding="utf-8", errors="ignore") as f:
                return sum(1 for line in f if line.strip())
        except Exception:
            return 0
    return 0


def _load_recent_errors(max_lines: int = 50) -> list[str]:
    """Load recent lines from errors.log."""
    err_log = DATA_DIR / "logs" / "errors.log"
    if not err_log.exists():
        return []
    try:
        with open(err_log, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        return lines[-max_lines:]
    except Exception:
        return []


def _load_sources_config() -> dict:
    """Load sources.yaml for group/name mapping."""
    path = DATA_DIR / "config" / "sources.yaml"
    if not path.exists():
        return {}
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        return cfg.get("sources", {})
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Live crawl monitor renderer
# ---------------------------------------------------------------------------


def _render_live_crawl_monitor(date_str: str) -> None:
    """Render real-time crawling progress from .crawl_state.json + tmp JSONL."""
    st.subheader(f"실시간 크롤링 모니터 — {date_str}")

    crawl_state = _load_crawl_state(date_str)
    sources_cfg = _load_sources_config()
    total_articles = _count_tmp_articles(date_str)

    total_configured = len(sources_cfg) if sources_cfg else 116
    completed_sites = sum(1 for s in crawl_state.values() if s.get("complete"))
    in_progress = len(crawl_state) - completed_sites

    # Hero metrics
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("수집 기사 수", f"{total_articles:,}")
    mc2.metric("완료 사이트", f"{completed_sites}/{total_configured}")
    mc3.metric("진행 중 사이트", f"{in_progress}")
    mc4.metric("남은 사이트", f"{total_configured - len(crawl_state)}")

    # Progress bar
    progress = completed_sites / total_configured if total_configured > 0 else 0
    st.progress(progress, text=f"전체: {progress:.0%}")

    # Per-site table
    st.subheader("사이트 상태")

    _group_lookup = {
        sid: s.get("group", "?") for sid, s in sources_cfg.items()
    } if sources_cfg else {}
    _name_lookup = {
        sid: s.get("name", sid) for sid, s in sources_cfg.items()
    } if sources_cfg else {}

    rows = []
    for site_id, state in sorted(crawl_state.items()):
        is_done = state.get("complete", False)
        url_count = len(state.get("processed_urls", []))
        group = _group_lookup.get(site_id, "?")
        name = _name_lookup.get(site_id, site_id)
        rows.append({
            "Group": group,
            "Site": name,
            "ID": site_id,
            "URLs": url_count,
            "Status": "완료" if is_done else "크롤링 중...",
        })

    if rows:
        site_df = pd.DataFrame(rows).sort_values(["Group", "Site"])
        st.dataframe(site_df, use_container_width=True, hide_index=True, height=400)

    # Group summary chart
    if rows:
        gdf = pd.DataFrame(rows)
        group_summary = gdf.groupby("Group").agg(
            Sites=("Site", "count"),
            URLs=("URLs", "sum"),
            Done=("Status", lambda x: (x == "완료").sum()),
        ).reset_index()
        group_summary["남은"] = group_summary["Sites"] - group_summary["Done"]
        group_summary.rename(columns={"Done": "완료"}, inplace=True)

        _gn = {
            "A": "한국 주요", "B": "한국 경제", "C": "한국 전문",
            "D": "한국 IT", "E": "영어권", "F": "아시아태평양",
            "G": "유럽/중동", "H": "중남미", "I": "다국어", "J": "북유럽/동유럽",
        }
        group_summary["Name"] = group_summary["Group"].map(_gn).fillna("?")

        fig_grp = px.bar(
            group_summary, x="Name", y=["완료", "남은"],
            title="그룹별 크롤링 진행률",
            barmode="stack",
            color_discrete_map={"완료": "#00e676", "남은": "#616161"},
            height=350,
        )
        st.plotly_chart(fig_grp, use_container_width=True)

    # Recent errors
    err_lines = _load_recent_errors(30)
    if err_lines:
        with st.expander(f"최근 오류 ({len(err_lines)}줄)", expanded=False):
            st.code("".join(err_lines[-20:]), language="log")

    # Auto-refresh
    st.caption("10초마다 자동 새로고침")
    time.sleep(0.1)  # Allow render
    st.rerun() if st.button("지금 새로고침") else None
    _auto_refresh_placeholder = st.empty()


# ---------------------------------------------------------------------------
# Date discovery
# ---------------------------------------------------------------------------


@st.cache_data(ttl=600)
def discover_dates() -> list[str]:
    """Scan data/raw/ for valid YYYY-MM-DD subdirectories and return sorted."""
    raw_dir = DATA_DIR / "raw"
    if not raw_dir.exists():
        return []
    dates: list[str] = []
    for p in sorted(raw_dir.iterdir()):
        if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name):
            dates.append(p.name)
    return dates


def dates_for_period(
    all_dates: list[str], period: str, ref_date: str,
) -> list[str]:
    """Return the subset of *all_dates* that fall within the selected period.

    Parameters
    ----------
    all_dates : available date strings (YYYY-MM-DD), sorted ascending.
    period : "Daily" | "Monthly" | "Quarterly" | "Yearly"
    ref_date : reference date string chosen in the sidebar.
    """
    ref = datetime.date.fromisoformat(ref_date)

    if period in ("Daily", "일별"):
        return [ref_date] if ref_date in all_dates else []

    if period in ("Monthly", "월별"):
        return [d for d in all_dates
                if d[:7] == ref_date[:7]]  # same YYYY-MM

    if period in ("Quarterly", "분기별"):
        q_start_month = ((ref.month - 1) // 3) * 3 + 1
        q_start = datetime.date(ref.year, q_start_month, 1)
        q_end_month = q_start_month + 2
        if q_end_month == 12:
            q_end = datetime.date(ref.year, 12, 31)
        else:
            q_end = datetime.date(ref.year, q_end_month + 1, 1) - datetime.timedelta(days=1)
        return [d for d in all_dates if q_start <= datetime.date.fromisoformat(d) <= q_end]

    if period in ("Yearly", "연간"):
        return [d for d in all_dates if d[:4] == ref_date[:4]]

    return [ref_date] if ref_date in all_dates else []


# ---------------------------------------------------------------------------
# Multi-date loaders
# ---------------------------------------------------------------------------


@st.cache_data(ttl=3600)
def load_multi_parquet(
    sub_dir: str, filename: str, dates: tuple[str, ...],
) -> pd.DataFrame | None:
    """Load and concatenate a parquet file from multiple date directories."""
    frames: list[pd.DataFrame] = []
    for d in dates:
        p = DATA_DIR / sub_dir / d / filename
        if p.exists():
            df = pd.read_parquet(str(p))
            df["_data_date"] = d
            frames.append(df)
    if not frames:
        return None
    combined = pd.concat(frames, ignore_index=True)
    # Deduplicate across dates if article_id column exists
    if "article_id" in combined.columns:
        combined = combined.drop_duplicates(subset=["article_id"], keep="last")
    return combined


@st.cache_data(ttl=3600)
def load_multi_jsonl(dates: tuple[str, ...]) -> pd.DataFrame | None:
    """Load and concatenate raw JSONL files from multiple date directories."""
    frames: list[pd.DataFrame] = []
    for d in dates:
        p = DATA_DIR / "raw" / d / "all_articles.jsonl"
        if not p.exists():
            continue
        records = []
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        if records:
            df = pd.DataFrame(records)
            df["_data_date"] = d
            frames.append(df)
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def format_number(n: int | float) -> str:
    if isinstance(n, float):
        return f"{n:,.1f}"
    return f"{n:,}"


# Source -> Group mapping
SOURCE_GROUPS = {
    "yna": "A", "chosun": "A", "joongang": "A", "donga": "A", "hani": "A",
    "mt": "B", "hankyung": "B",
    "nocutnews": "C", "kmib": "C", "ohmynews": "C",
    "bloter": "D", "etnews": "D", "irobotnews": "D", "38north": "D",
    "sciencetimes": "D", "techneedle": "D",
    "nytimes": "E", "ft": "E", "cnn": "E", "huffpost": "E",
    "wsj": "E", "bloomberg": "E", "buzzfeed": "E", "nationalpost": "E",
    "marketwatch": "E",
    "scmp": "F", "people": "F", "thehindu": "F", "globaltimes": "F",
    "yomiuri": "F", "taiwannews": "F",
    "thesun": "G", "lemonde": "G", "themoscowtimes": "G",
    "israelhayom": "G", "bild": "G", "arabnews": "G",
}

GROUP_NAMES = {
    "A": "한국 주요",
    "B": "한국 경제/기술",
    "C": "한국 전문",
    "D": "한국 IT/기술",
    "E": "영어권 주요",
    "F": "아시아태평양",
    "G": "유럽/중동",
}

LANG_NAMES = {
    "ko": "한국어", "en": "영어", "fr": "프랑스어", "de": "독일어",
    "zh": "중국어", "ja": "일본어", "ar": "아랍어", "ru": "러시아어",
}

# ---------------------------------------------------------------------------
# Word Cloud helpers
# ---------------------------------------------------------------------------

_KO_STOPWORDS = {
    "것", "수", "등", "이", "그", "저", "때", "중", "년", "월", "일",
    "위", "곳", "바", "뉴스", "기자", "연합뉴스", "서울", "제공",
    "사진", "대한", "관련", "이후", "올해", "현재", "경우", "이상",
    "이번", "지난", "전체", "가장", "오늘", "지금", "우리", "모든",
    "뉴스1", "한편", "또한", "기사", "무단", "전재", "배포", "금지",
    "특파원", "통신", "보도", "데일리", "저작권", "재배포", "헤럴드",
}

_EN_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "shall", "may", "might", "can", "must", "need",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
    "into", "about", "between", "through", "after", "before", "during",
    "above", "below", "up", "down", "out", "off", "over", "under",
    "and", "but", "or", "nor", "not", "so", "yet", "both", "either",
    "neither", "each", "every", "all", "any", "few", "more", "most",
    "other", "some", "such", "no", "only", "same", "than", "too",
    "very", "just", "also", "now", "then", "here", "there", "when",
    "where", "why", "how", "what", "which", "who", "whom", "this",
    "that", "these", "those", "it", "its", "he", "she", "they", "them",
    "his", "her", "their", "our", "my", "your", "we", "you", "i", "me",
    "us", "him", "if", "while", "because", "since", "until", "unless",
    "although", "though", "even", "still", "already", "never", "always",
    "often", "much", "many", "well", "however", "said", "says", "new",
    "like", "one", "two", "first", "last", "get", "got", "make", "made",
    "going", "come", "take", "know", "think", "see", "look", "want",
    "give", "use", "find", "tell", "ask", "work", "call", "try", "keep",
    "let", "put", "say", "go", "people", "time", "year", "day", "way",
    "man", "world", "life", "part", "back", "long", "great", "right",
    "old", "big", "high", "different", "small", "large", "next", "early",
    "young", "important", "public", "bad", "according", "reuters", "ap",
    "per", "set", "don", "didn", "won", "isn", "aren", "wasn", "weren",
    "haven", "hasn", "hadn", "doesn", "couldn", "shouldn", "wouldn",
}


@st.cache_data(ttl=3600)
def extract_word_frequencies(
    texts: list[str], languages: list[str],
) -> dict[str, int]:
    """Extract word frequencies using kiwipiepy (Korean) + regex (English)."""
    ko_texts = [t for t, lang in zip(texts, languages) if lang == "ko" and t]
    en_texts = [t for t, lang in zip(texts, languages) if lang != "ko" and t]

    word_freq: dict[str, int] = {}

    if ko_texts:
        from kiwipiepy import Kiwi
        import kiwipiepy_model, os, shutil
        _src_dir = os.path.dirname(kiwipiepy_model.__file__)
        _ascii_dir = "C:/kiwi_model"
        if not os.path.exists(os.path.join(_ascii_dir, "extract.mdl")):
            os.makedirs(_ascii_dir, exist_ok=True)
            for _f in os.listdir(_src_dir):
                _s = os.path.join(_src_dir, _f)
                if os.path.isfile(_s):
                    shutil.copy2(_s, os.path.join(_ascii_dir, _f))
        kiwi = Kiwi(model_path=_ascii_dir)
        for text in ko_texts:
            tokens = kiwi.tokenize(text)
            for token in tokens:
                if token.tag in ("NNG", "NNP") and len(token.form) >= 2:
                    w = token.form
                    if w not in _KO_STOPWORDS:
                        word_freq[w] = word_freq.get(w, 0) + 1

    if en_texts:
        pattern = re.compile(r"[a-zA-Z]{3,}")
        for text in en_texts:
            for m in pattern.finditer(text.lower()):
                w = m.group()
                if w not in _EN_STOPWORDS:
                    word_freq[w] = word_freq.get(w, 0) + 1

    return word_freq


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="GlobalNews Dashboard",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Auto-refresh support (JS injection — no extra packages needed)
# ---------------------------------------------------------------------------


def _inject_auto_refresh(interval_sec: int = 10) -> None:
    """Inject a JS timer that reloads the page every *interval_sec* seconds."""
    st.markdown(
        f"""<meta http-equiv="refresh" content="{interval_sec}">""",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Sidebar — Period selector
# ---------------------------------------------------------------------------

all_dates = discover_dates()
_crawl_active = _find_active_crawl_date() is not None

with st.sidebar:
    st.header("기간 선택")

    if _crawl_active:
        _auto = st.toggle("자동 새로고침 (10초)", value=False, key="auto_refresh")
        if _auto:
            _inject_auto_refresh(10)
        st.success("크롤링 진행 중...")

    if not all_dates:
        if not _crawl_active:
            st.info("첫 크롤링 대기 중...")

# ---------------------------------------------------------------------------
# Welcome screen — shown when no data is available yet
# ---------------------------------------------------------------------------

if not all_dates:
    st.title("GlobalNews 파이프라인 대시보드")

    st.markdown("---")

    # System status section
    _sources_yaml = DATA_DIR / "config" / "sources.yaml"
    _src_count = 0
    _group_counts: dict[str, int] = {}
    _lang_counts_cfg: dict[str, int] = {}
    _daily_est = 0
    _enabled_count = 0

    if _sources_yaml.exists():
        try:
            import yaml  # available in the venv

            with open(_sources_yaml, encoding="utf-8") as _f:
                _cfg = yaml.safe_load(_f)
            _sources = _cfg.get("sources", {})
            _src_count = len(_sources)
            for _s in _sources.values():
                _g = _s.get("group", "?")
                _group_counts[_g] = _group_counts.get(_g, 0) + 1
                _l = _s.get("language", "?")
                _lang_counts_cfg[_l] = _lang_counts_cfg.get(_l, 0) + 1
                _daily_est += _s.get("meta", {}).get("daily_article_estimate", 0)
                if _s.get("meta", {}).get("enabled", False):
                    _enabled_count += 1
        except Exception:
            pass

    # Hero metrics
    col_h1, col_h2, col_h3, col_h4 = st.columns(4)
    col_h1.metric("설정된 언론사", f"{_src_count}")
    col_h2.metric("활성 언론사", f"{_enabled_count}")
    col_h3.metric("언어 수", f"{len(_lang_counts_cfg)}")
    col_h4.metric("일일 예상 기사 수", f"{_daily_est:,}")

    st.markdown("---")

    # Coverage map
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("언론사 그룹")

        _group_names_full = {
            "A": ("한국 주요", 5),
            "B": ("한국 경제/비즈니스", 3),
            "C": ("한국 전문", 2),
            "D": ("한국 IT/기술", 8),
            "E": ("영어권 주요", 23),
            "F": ("아시아태평양", 22),
            "G": ("유럽 / 중동", 36),
            "H": ("중남미", 4),
            "I": ("다국어 CJK", 9),
            "J": ("북유럽 / 동유럽", 4),
        }

        _group_rows = []
        for _gk, (_gname, _default) in _group_names_full.items():
            _cnt = _group_counts.get(_gk, _default)
            _group_rows.append({
                "그룹": _gk,
                "명칭": _gname,
                "언론사 수": _cnt,
            })
        st.dataframe(
            pd.DataFrame(_group_rows),
            use_container_width=True,
            hide_index=True,
            height=400,
        )

    with col_right:
        st.subheader("언어")

        _lang_display = {
            "ko": "한국어", "en": "영어", "ja": "일본어",
            "zh": "중국어", "de": "독일어", "fr": "프랑스어",
            "es": "스페인어", "it": "이탈리아어", "pt": "포르투갈어",
            "ru": "러시아어", "pl": "폴란드어", "cs": "체코어",
            "no": "노르웨이어", "sv": "스웨덴어", "mn": "몽골어",
        }
        if _lang_counts_cfg:
            _ldf = pd.DataFrame([
                {"언어": _lang_display.get(k, k), "언론사 수": v}
                for k, v in sorted(_lang_counts_cfg.items(), key=lambda x: -x[1])
            ])
            st.dataframe(_ldf, use_container_width=True, hide_index=True, height=400)

    st.markdown("---")

    # ----- Live Crawling Monitor (shown during active crawl) -----
    _active_date = _find_active_crawl_date()
    if _active_date:
        st.markdown("---")
        _render_live_crawl_monitor(_active_date)
    else:
        # Pipeline info (static — no active crawl)
        st.subheader("8단계 분석 파이프라인")
        _stages = [
            ("1. 크롤링", "116개 언론사, 안티블록, 동적 우회"),
            ("2. 전처리", "Kiwi (한국어) + spaCy (다국어) NLP"),
            ("3. 특징 추출", "SBERT 임베딩, TF-IDF, NER, KeyBERT"),
            ("4. 토픽 모델링", "BERTopic + HDBSCAN 클러스터링"),
            ("5. 감성 & 감정", "기사별 감성, STEEPS 분류"),
            ("6. 시계열", "STL 분해, 급등 감지, Prophet 예측"),
            ("7. 교차 분석", "그랜저 인과관계, PCMCI, 네트워크 분석"),
            ("8. 신호 분류", "5계층 신호 감지, 새로움 점수"),
        ]
        for _label, _desc in _stages:
            st.markdown(f"**{_label}**  \n{_desc}")

        st.markdown("---")
        st.subheader("시작하기")
        st.code(
            "# Run the full pipeline\n"
            ".venv/bin/python main.py --mode full --date 2026-03-27\n\n"
            "# Or crawl only\n"
            ".venv/bin/python main.py --mode crawl --date 2026-03-27",
            language="bash",
        )

    st.info(
        "첫 크롤링이 완료되면 이 대시보드에서 수집된 기사, 토픽, 감성 분석 결과 등을 자동으로 표시합니다."
    )
    st.stop()


# ---------------------------------------------------------------------------
# Normal mode — data exists, show period selector and analysis
# ---------------------------------------------------------------------------

with st.sidebar:
    period = st.selectbox(
        "분석 기간",
        ["일별", "월별", "분기별", "연간"],
        index=0,
    )

    if period == "일별":
        selected_ref = st.selectbox("날짜", all_dates, index=len(all_dates) - 1)
    elif period == "월별":
        months = sorted(set(d[:7] for d in all_dates))
        selected_month = st.selectbox("월", months, index=len(months) - 1)
        selected_ref = selected_month + "-01"
    elif period == "분기별":
        quarters: list[str] = []
        seen: set[str] = set()
        for d in all_dates:
            dt = datetime.date.fromisoformat(d)
            q = (dt.month - 1) // 3 + 1
            label = f"{dt.year} Q{q}"
            if label not in seen:
                seen.add(label)
                quarters.append(label)
        selected_q = st.selectbox("분기", quarters, index=len(quarters) - 1)
        # Parse back to a ref date
        q_year, q_num = selected_q.split(" Q")
        q_month = (int(q_num) - 1) * 3 + 1
        selected_ref = f"{q_year}-{q_month:02d}-01"
    else:  # 연간
        years = sorted(set(d[:4] for d in all_dates))
        selected_year = st.selectbox("연도", years, index=len(years) - 1)
        selected_ref = f"{selected_year}-01-01"

    active_dates = dates_for_period(all_dates, period, selected_ref)

    if not active_dates:
        st.warning("선택한 기간의 데이터가 없습니다.")
        st.stop()

    st.info(f"**{len(active_dates)}**일 선택됨: {active_dates[0]} — {active_dates[-1]}"
            if len(active_dates) > 1
            else f"**1**일: {active_dates[0]}")

    st.markdown("---")

# Convert to tuple for caching
_dates_key = tuple(active_dates)

# ---------------------------------------------------------------------------
# Load data for the selected period
# ---------------------------------------------------------------------------

raw_df = load_multi_jsonl(_dates_key)
articles_df = load_multi_parquet("processed", "articles.parquet", _dates_key)
analysis_df = load_multi_parquet("analysis", "article_analysis.parquet", _dates_key)
topics_df = load_multi_parquet("analysis", "topics.parquet", _dates_key)
timeseries_df = load_multi_parquet("analysis", "timeseries.parquet", _dates_key)
cross_df = load_multi_parquet("analysis", "cross_analysis.parquet", _dates_key)
networks_df = load_multi_parquet("analysis", "networks.parquet", _dates_key)
mood_df = load_multi_parquet("analysis", "mood_trajectory.parquet", _dates_key)
output_df = load_multi_parquet("output", "analysis.parquet", _dates_key)

# Merge articles + analysis + topics for unified view
if articles_df is not None and analysis_df is not None and topics_df is not None:
    _topic_cols = ["article_id", "topic_id", "topic_label", "topic_probability"]
    _topic_cols = [c for c in _topic_cols if c in topics_df.columns]
    merged_df = (
        articles_df
        .merge(analysis_df, on="article_id", how="left", suffixes=("", "_analysis"))
        .merge(topics_df[_topic_cols], on="article_id", how="left", suffixes=("", "_topic"))
    )
else:
    merged_df = articles_df

# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------

_period_label = (
    f"{active_dates[0]}" if period == "일별"
    else f"{active_dates[0]} ~ {active_dates[-1]} ({len(active_dates)}일)"
)
st.title("🌐 GlobalNews 파이프라인 대시보드")
st.caption(f"기간: **{period}** | {_period_label}")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_overview, tab_crawl_live, tab_topics, tab_sentiment, tab_timeseries, tab_wordcloud, tab_explorer = st.tabs([
    "📊 개요",
    "🛰️ 실시간 크롤",
    "🏷️ 토픽",
    "😊 감성 & 감정",
    "📈 시계열",
    "☁️ 워드클라우드",
    "🔍 기사 탐색기",
])

# ========================= TAB: LIVE CRAWL =================================

with tab_crawl_live:
    _live_date = _find_active_crawl_date()
    if _live_date:
        _render_live_crawl_monitor(_live_date)
    else:
        st.info("실행 중인 크롤링이 없습니다. 파이프라인을 시작하면 실시간 현황이 여기 표시됩니다.")

# ========================= TAB 1: OVERVIEW =================================

with tab_overview:
    st.header("크롤링 & 파이프라인 개요")

    if raw_df is not None:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("수집된 총 기사 수", format_number(len(raw_df)))
        col2.metric("고유 언론사", format_number(raw_df["source_id"].nunique()))
        col3.metric("언어 수", format_number(raw_df["language"].nunique()))
        if articles_df is not None:
            col4.metric("중복제거 후 기사 수", format_number(len(articles_df)))
        else:
            col4.metric("처리 후 기사 수", "N/A")

        # Days covered
        if len(active_dates) > 1:
            col_d1, col_d2 = st.columns(2)
            col_d1.metric("기간 내 일수", len(active_dates))
            avg_per_day = len(raw_df) / len(active_dates)
            col_d2.metric("일평균 기사 수", format_number(avg_per_day))

    st.subheader("언론사별 기사 수")

    if raw_df is not None:
        source_counts = (
            raw_df.groupby("source_id")
            .size()
            .reset_index(name="articles")
            .sort_values("articles", ascending=False)
        )
        source_counts["group"] = source_counts["source_id"].map(SOURCE_GROUPS).fillna("?")
        source_counts["group_name"] = source_counts["group"].map(GROUP_NAMES).fillna("Unknown")

        fig_src = px.bar(
            source_counts,
            x="source_id",
            y="articles",
            color="group_name",
            title="언론사별 기사 수 (그룹별 색상)",
            labels={"source_id": "언론사", "articles": "기사 수", "group_name": "그룹"},
            text_auto=True,
            height=450,
        )
        fig_src.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_src, use_container_width=True)

        col_left, col_right = st.columns(2)

        with col_left:
            group_counts = (
                source_counts.groupby(["group", "group_name"])["articles"]
                .sum()
                .reset_index()
                .sort_values("group")
            )
            fig_grp = px.pie(
                group_counts,
                values="articles",
                names="group_name",
                title="그룹별 기사 수",
                hole=0.4,
            )
            st.plotly_chart(fig_grp, use_container_width=True)

        with col_right:
            lang_counts = raw_df["language"].value_counts().reset_index()
            lang_counts.columns = ["language", "count"]
            lang_counts["lang_name"] = lang_counts["language"].map(LANG_NAMES).fillna(lang_counts["language"])
            fig_lang = px.pie(
                lang_counts,
                values="count",
                names="lang_name",
                title="언어별 기사 수",
                hole=0.4,
            )
            st.plotly_chart(fig_lang, use_container_width=True)

        # Daily trend (useful for multi-day periods)
        if len(active_dates) > 1 and "_data_date" in raw_df.columns:
            st.subheader("일별 기사량")
            daily_vol = raw_df.groupby("_data_date").size().reset_index(name="articles")
            fig_daily = px.bar(
                daily_vol, x="_data_date", y="articles",
                title="일별 수집 기사 수",
                labels={"_data_date": "날짜", "articles": "기사 수"},
                text_auto=True,
            )
            st.plotly_chart(fig_daily, use_container_width=True)

    # Pipeline stage summary
    st.subheader("파이프라인 출력 파일")
    file_info = []
    _file_defs = [
        ("원시 JSONL", "raw", "all_articles.jsonl"),
        ("전처리 기사", "processed", "articles.parquet"),
        ("기사 분석", "analysis", "article_analysis.parquet"),
        ("토픽", "analysis", "topics.parquet"),
        ("시계열", "analysis", "timeseries.parquet"),
        ("교차 분석", "analysis", "cross_analysis.parquet"),
        ("네트워크", "analysis", "networks.parquet"),
        ("최종 분석", "output", "analysis.parquet"),
        ("신호", "output", "signals.parquet"),
    ]
    for label, sub, fname in _file_defs:
        total_size = 0.0
        found = 0
        for d in active_dates:
            p = DATA_DIR / sub / d / fname
            if p.exists():
                total_size += p.stat().st_size / (1024 * 1024)
                found += 1
        status = f"✅ ({found}/{len(active_dates)})" if found > 0 else "❌"
        file_info.append({
            "파일": label,
            "파일명": fname,
            "총 크기 (MB)": round(total_size, 2),
            "발견된 일수": found,
            "상태": status,
        })
    st.dataframe(pd.DataFrame(file_info), use_container_width=True, hide_index=True)


# ========================= TAB 2: TOPICS ====================================

with tab_topics:
    st.header("토픽 분석")

    if topics_df is not None:
        try:
            topic_counts = (
                topics_df[topics_df["topic_id"] != -1]
                .groupby(["topic_id", "topic_label"])
                .size()
                .reset_index(name="articles")
                .sort_values("articles", ascending=False)
            )

            col_info1, col_info2, col_info3 = st.columns(3)
            n_topics = topics_df[topics_df["topic_id"] != -1]["topic_id"].nunique()
            n_outliers = (topics_df["topic_id"] == -1).sum()
            outlier_pct = n_outliers / len(topics_df) * 100 if len(topics_df) > 0 else 0
            col_info1.metric("발견된 토픽 수", n_topics)
            col_info2.metric("아웃라이어 기사", f"{n_outliers} ({outlier_pct:.1f}%)")
            col_info3.metric("전체 기사 수", format_number(len(topics_df)))

            topic_counts["short_label"] = topic_counts["topic_label"].str[:40]

            fig_topics = px.bar(
                topic_counts.head(20),
                x="articles",
                y="short_label",
                orientation="h",
                title="기사 수 기준 상위 20 토픽",
                labels={"short_label": "토픽", "articles": "기사 수"},
                text_auto=True,
                height=600,
            )
            fig_topics.update_layout(yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig_topics, use_container_width=True)

            st.subheader("토픽 배정 신뢰도")
            fig_prob = px.histogram(
                topics_df[topics_df["topic_id"] != -1],
                x="topic_probability",
                nbins=50,
                title="토픽 배정 확률 분포",
                labels={"topic_probability": "확률"},
            )
            st.plotly_chart(fig_prob, use_container_width=True)

            if merged_df is not None and "steeps_category" in merged_df.columns:
                st.subheader("STEEPS 분류")
                steeps = merged_df["steeps_category"].value_counts().reset_index()
                steeps.columns = ["카테고리", "수"]
                fig_steeps = px.bar(
                    steeps,
                    x="카테고리",
                    y="수",
                    title="STEEPS 카테고리별 기사 수",
                    color="카테고리",
                    text_auto=True,
                )
                st.plotly_chart(fig_steeps, use_container_width=True)

            # Topic evolution across days (multi-day periods)
            if len(active_dates) > 1 and "_data_date" in topics_df.columns:
                st.subheader("일별 토픽 추세")
                top5_topics = topic_counts.head(5)["topic_id"].tolist()
                topic_daily = (
                    topics_df[topics_df["topic_id"].isin(top5_topics)]
                    .groupby(["_data_date", "topic_label"])
                    .size()
                    .reset_index(name="articles")
                )
                if len(topic_daily) > 0:
                    fig_topic_trend = px.line(
                        topic_daily, x="_data_date", y="articles", color="topic_label",
                        title="상위 5 토픽 — 일별 추세",
                        labels={"_data_date": "날짜", "articles": "기사 수", "topic_label": "토픽"},
                    )
                    st.plotly_chart(fig_topic_trend, use_container_width=True)
        except Exception as e:
            st.error(f"토픽 분석 렌더링 실패: {e}")
    else:
        st.info("토픽 분석 데이터가 아직 없습니다.")
        st.markdown(
            "**How to generate:**  Run the full analysis pipeline to produce topic modeling results.\n\n"
            "```bash\n"
            ".venv/Scripts/python main.py --mode full --date YYYY-MM-DD\n"
            "```\n\n"
            "This runs BERTopic + HDBSCAN clustering (Stage 4 of the 8-stage pipeline)."
        )


# ========================= TAB 3: SENTIMENT & EMOTIONS =====================

with tab_sentiment:
    st.header("감성 & 감정 분석")

    if analysis_df is not None:
      try:
        col_s1, col_s2 = st.columns(2)

        with col_s1:
            sent_counts = analysis_df["sentiment_label"].value_counts().reset_index()
            sent_counts.columns = ["label", "count"]
            color_map = {"positive": "#2ecc71", "negative": "#e74c3c", "neutral": "#95a5a6"}
            fig_sent = px.pie(
                sent_counts,
                values="count",
                names="label",
                title="감성 분포",
                color="label",
                color_discrete_map=color_map,
                hole=0.4,
            )
            st.plotly_chart(fig_sent, use_container_width=True)

        with col_s2:
            fig_score = px.histogram(
                analysis_df,
                x="sentiment_score",
                nbins=50,
                title="감성 점수 분포",
                labels={"sentiment_score": "점수 (-1 ~ 1)"},
                color_discrete_sequence=["#3498db"],
            )
            st.plotly_chart(fig_score, use_container_width=True)

        # Sentiment trend across days
        if len(active_dates) > 1 and "_data_date" in analysis_df.columns:
            st.subheader("일별 감성 추세")
            sent_daily = (
                analysis_df.groupby(["_data_date", "sentiment_label"])
                .size()
                .reset_index(name="count")
            )
            fig_sent_trend = px.bar(
                sent_daily, x="_data_date", y="count", color="sentiment_label",
                title="일별 감성 분포",
                labels={"_data_date": "날짜", "count": "기사 수", "sentiment_label": "감성"},
                color_discrete_map=color_map,
                barmode="stack",
            )
            st.plotly_chart(fig_sent_trend, use_container_width=True)

        # Emotion radar
        st.subheader("감정 프로파일 (전체 기사 평균)")
        emotion_cols = [c for c in analysis_df.columns if c.startswith("emotion_")]
        if emotion_cols:
            avg_emotions = analysis_df[emotion_cols].mean()
            emotion_labels = [c.replace("emotion_", "").title() for c in emotion_cols]

            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(
                r=avg_emotions.values.tolist() + [avg_emotions.values[0]],
                theta=emotion_labels + [emotion_labels[0]],
                fill="toself",
                name="평균",
                line_color="#3498db",
            ))
            fig_radar.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
                title="감정 레이더 — 전체 평균",
                height=500,
            )
            st.plotly_chart(fig_radar, use_container_width=True)

            if merged_df is not None and "source" in merged_df.columns:
                st.subheader("언론사별 감정 히트맵")
                _emo_cols_merged = [c for c in merged_df.columns if c.startswith("emotion_")]
                if _emo_cols_merged:
                    emo_by_source = (
                        merged_df.groupby("source")[_emo_cols_merged]
                        .mean()
                        .sort_index()
                    )
                    emo_labels = [c.replace("emotion_", "").title() for c in _emo_cols_merged]
                    emo_by_source.columns = emo_labels

                    fig_heat = px.imshow(
                        emo_by_source.values,
                        x=emo_by_source.columns.tolist(),
                        y=emo_by_source.index.tolist(),
                        color_continuous_scale="RdYlBu_r",
                        title="뉴스 언론사별 평균 감정 점수",
                        labels=dict(color="점수"),
                        aspect="auto",
                        height=max(400, len(emo_by_source) * 25),
                    )
                    st.plotly_chart(fig_heat, use_container_width=True)

        # Mood trajectory
        if mood_df is not None and len(mood_df) > 0:
            st.subheader("감정 궤적")
            fig_mood = px.line(
                mood_df,
                x="date",
                y="mood_index",
                color="source",
                title="시간별 감정 지수",
                labels={"mood_index": "감정 지수", "date": "날짜"},
            )
            st.plotly_chart(fig_mood, use_container_width=True)
      except Exception as e:
        st.error(f"감성 분석 렌더링 실패: {e}")
    else:
        st.info("감성 & 감정 분석 데이터가 아직 없습니다.")
        st.markdown(
            "**생성 방법:**  전체 분석 파이프라인을 실행하여 감성 분석 결과를 생성하세요.\n\n"
            "```bash\n"
            ".venv/Scripts/python main.py --mode full --date YYYY-MM-DD\n"
            "```\n\n"
            "기사별 감성 점수 및 감정 감지를 실행합니다 (8단계 파이프라인의 5단계)."
        )


# ========================= TAB 4: TIME SERIES ===============================

with tab_timeseries:
    st.header("시계열 분석")

    if timeseries_df is not None:
      try:
        col_f1, col_f2 = st.columns(2)

        metric_types = sorted(timeseries_df["metric_type"].unique())
        with col_f1:
            selected_metric = st.selectbox("지표 유형", metric_types, index=0)

        topic_ids = sorted(timeseries_df["topic_id"].unique())
        with col_f2:
            selected_topics = st.multiselect(
                "토픽 ID (비우면 전체 집계 -1)",
                topic_ids,
                default=[-1] if -1 in topic_ids else topic_ids[:1],
            )

        if not selected_topics:
            selected_topics = [-1] if -1 in topic_ids else topic_ids[:1]

        mask = (
            (timeseries_df["metric_type"] == selected_metric) &
            (timeseries_df["topic_id"].isin(selected_topics))
        )
        ts_filtered = timeseries_df[mask].copy()

        if len(ts_filtered) > 0:
            ts_filtered["date"] = pd.to_datetime(ts_filtered["date"])
            ts_filtered = ts_filtered.sort_values("date")

            fig_ts = go.Figure()
            for tid in selected_topics:
                tid_data = ts_filtered[ts_filtered["topic_id"] == tid]
                fig_ts.add_trace(go.Scatter(
                    x=tid_data["date"],
                    y=tid_data["value"],
                    mode="lines",
                    name=f"토픽 {tid} — 값",
                    opacity=0.6,
                ))
                if "trend" in tid_data.columns and tid_data["trend"].notna().any():
                    fig_ts.add_trace(go.Scatter(
                        x=tid_data["date"],
                        y=tid_data["trend"],
                        mode="lines",
                        name=f"토픽 {tid} — 추세",
                        line=dict(dash="dash", width=2),
                    ))

                if "burst_score" in tid_data.columns:
                    burst_data = tid_data[tid_data["burst_score"].notna() & (tid_data["burst_score"] > 0)]
                    if len(burst_data) > 0:
                        fig_ts.add_trace(go.Scatter(
                            x=burst_data["date"],
                            y=burst_data["value"],
                            mode="markers",
                            name=f"토픽 {tid} — 급등",
                            marker=dict(size=10, symbol="star", color="red"),
                        ))

            fig_ts.update_layout(
                title=f"시계열: {selected_metric}",
                xaxis_title="날짜",
                yaxis_title="값",
                height=500,
            )
            st.plotly_chart(fig_ts, use_container_width=True)

            if "ma_short" in ts_filtered.columns and ts_filtered["ma_short"].notna().any():
                st.subheader("이동평균 교차")
                fig_ma = go.Figure()
                for tid in selected_topics:
                    tid_data = ts_filtered[ts_filtered["topic_id"] == tid]
                    fig_ma.add_trace(go.Scatter(
                        x=tid_data["date"], y=tid_data["ma_short"],
                        name=f"토픽 {tid} — 단기 이평 (3일)",
                        line=dict(width=1),
                    ))
                    fig_ma.add_trace(go.Scatter(
                        x=tid_data["date"], y=tid_data["ma_long"],
                        name=f"토픽 {tid} — 장기 이평 (14일)",
                        line=dict(width=1, dash="dash"),
                    ))
                fig_ma.update_layout(height=400, title="단기 vs 장기 이동평균")
                st.plotly_chart(fig_ma, use_container_width=True)

            if "prophet_forecast" in ts_filtered.columns and ts_filtered["prophet_forecast"].notna().any():
                st.subheader("Prophet 예측")
                for tid in selected_topics:
                    tid_data = ts_filtered[ts_filtered["topic_id"] == tid]
                    forecast_data = tid_data[tid_data["prophet_forecast"].notna()]
                    if len(forecast_data) > 0:
                        fig_prophet = go.Figure()
                        fig_prophet.add_trace(go.Scatter(
                            x=tid_data["date"], y=tid_data["value"],
                            name="실제", line=dict(color="#3498db"),
                        ))
                        fig_prophet.add_trace(go.Scatter(
                            x=forecast_data["date"], y=forecast_data["prophet_forecast"],
                            name="예측", line=dict(color="#e74c3c", dash="dash"),
                        ))
                        if "prophet_lower" in forecast_data.columns and forecast_data["prophet_lower"].notna().any():
                            fig_prophet.add_trace(go.Scatter(
                                x=forecast_data["date"], y=forecast_data["prophet_upper"],
                                mode="lines", line=dict(width=0), showlegend=False,
                            ))
                            fig_prophet.add_trace(go.Scatter(
                                x=forecast_data["date"], y=forecast_data["prophet_lower"],
                                mode="lines", line=dict(width=0), showlegend=False,
                                fill="tonexty", fillcolor="rgba(231,76,60,0.15)",
                            ))
                        fig_prophet.update_layout(
                            title=f"Prophet 예측 — 토픽 {tid}",
                            height=400,
                        )
                        st.plotly_chart(fig_prophet, use_container_width=True)
        else:
            st.info("선택한 필터에 해당하는 데이터가 없습니다.")

        st.subheader("시계열 통계")
        ts_stats = {
            "전체 시리즈": timeseries_df["series_id"].nunique() if "series_id" in timeseries_df.columns else "N/A",
            "날짜 범위": f"{timeseries_df['date'].min()} → {timeseries_df['date'].max()}" if "date" in timeseries_df.columns else "N/A",
            "데이터 포인트": format_number(len(timeseries_df)),
            "급등 이벤트": int((timeseries_df["burst_score"].notna() & (timeseries_df["burst_score"] > 0)).sum()) if "burst_score" in timeseries_df.columns else 0,
            "변화점": int(timeseries_df["is_changepoint"].sum()) if "is_changepoint" in timeseries_df.columns else 0,
        }
        for k, v in ts_stats.items():
            st.text(f"  {k}: {v}")
      except Exception as e:
        st.error(f"시계열 분석 렌더링 실패: {e}")
    else:
        st.info("시계열 데이터가 아직 없습니다.")
        st.markdown(
            "**생성 방법:**  전체 분석 파이프라인을 실행하여 시계열 분해 결과를 생성하세요.\n\n"
            "```bash\n"
            ".venv/Scripts/python main.py --mode full --date YYYY-MM-DD\n"
            "```\n\n"
            "STL 분해, 급등 감지, Prophet 예측을 실행합니다 (8단계 파이프라인의 6단계)."
        )


# ========================= TAB 5: WORD CLOUD ================================

with tab_wordcloud:
    st.header("워드클라우드 분석")

    if raw_df is not None:
      try:
        wc_col1, wc_col2, wc_col3 = st.columns(3)

        with wc_col1:
            wc_lang_options = ["전체", "한국어 (ko)", "영어 (en)"]
            wc_lang = st.selectbox("언어 필터", wc_lang_options, key="wc_lang")

        with wc_col2:
            wc_group_options = ["전체"] + [
                f"{k} — {v}" for k, v in sorted(GROUP_NAMES.items())
            ]
            wc_group = st.selectbox("그룹 필터", wc_group_options, key="wc_group")

        with wc_col3:
            wc_max_words = st.slider("최대 단어 수", 50, 300, 150, step=25, key="wc_max")

        wc_filtered = raw_df.copy()

        if wc_lang == "한국어 (ko)":
            wc_filtered = wc_filtered[wc_filtered["language"] == "ko"]
        elif wc_lang == "영어 (en)":
            wc_filtered = wc_filtered[wc_filtered["language"] == "en"]

        if wc_group != "전체":
            group_letter = wc_group.split(" — ")[0]
            group_sources = {
                sid for sid, g in SOURCE_GROUPS.items() if g == group_letter
            }
            wc_filtered = wc_filtered[wc_filtered["source_id"].isin(group_sources)]

        st.caption(f"{len(wc_filtered):,}개 기사 분석 중")

        if len(wc_filtered) == 0:
            st.warning("선택한 필터에 해당하는 기사가 없습니다.")
        else:
            texts = wc_filtered["body"].fillna("").tolist()
            langs = wc_filtered["language"].fillna("en").tolist()

            with st.spinner("단어 추출 중 (한국어 NLP + 영어 토크나이저)..."):
                word_freq = extract_word_frequencies(texts, langs)

            if not word_freq:
                st.warning("추출된 단어가 없습니다. 다른 필터를 선택해보세요.")
            else:
                st.success(f"{len(word_freq):,}개 고유 단어 추출 완료")

                st.subheader("워드클라우드")

                has_korean = any(
                    "\uac00" <= ch <= "\ud7a3"
                    for w in list(word_freq.keys())[:100]
                    for ch in w
                )
                font_path = None
                if has_korean:
                    for fp in [
                        # Windows
                        "C:/Windows/Fonts/malgun.ttf",
                        "C:/Windows/Fonts/NanumGothic.ttf",
                        "C:/Windows/Fonts/gulim.ttc",
                        # macOS
                        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
                        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
                        "/Library/Fonts/NanumGothic.ttf",
                        # Linux
                        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
                    ]:
                        if Path(fp).exists():
                            font_path = fp
                            break

                wc = WordCloud(
                    width=1200,
                    height=600,
                    max_words=wc_max_words,
                    background_color="white",
                    colormap="viridis",
                    font_path=font_path,
                    prefer_horizontal=0.7,
                    min_font_size=10,
                    max_font_size=120,
                    relative_scaling=0.5,
                )
                wc.generate_from_frequencies(word_freq)

                fig_wc, ax_wc = plt.subplots(figsize=(14, 7))
                ax_wc.imshow(wc, interpolation="bilinear")
                ax_wc.axis("off")
                st.pyplot(fig_wc)
                plt.close(fig_wc)

                st.subheader("빈도 기준 상위 30 단어")
                top_words = sorted(
                    word_freq.items(), key=lambda x: x[1], reverse=True
                )[:30]
                top_df = pd.DataFrame(top_words, columns=["단어", "빈도"])

                fig_top = px.bar(
                    top_df,
                    x="빈도",
                    y="단어",
                    orientation="h",
                    title="상위 30 빈출 단어",
                    labels={"단어": "단어", "빈도": "빈도"},
                    text_auto=True,
                    height=700,
                    color="count",
                    color_continuous_scale="viridis",
                )
                fig_top.update_layout(
                    yaxis=dict(autorange="reversed"),
                    showlegend=False,
                )
                st.plotly_chart(fig_top, use_container_width=True)

                col_ws1, col_ws2, col_ws3 = st.columns(3)
                col_ws1.metric("고유 단어 수", f"{len(word_freq):,}")
                col_ws2.metric("전체 단어 수", f"{sum(word_freq.values()):,}")
                col_ws3.metric(
                    "최빈 단어",
                    f"{top_words[0][0]} ({top_words[0][1]:,})" if top_words else "N/A",
                )
      except Exception as e:
        st.error(f"워드클라우드 렌더링 실패: {e}")
    else:
        st.info("원시 기사 데이터가 없습니다. 먼저 크롤링을 실행하세요.")


# ========================= TAB 6: ARTICLE EXPLORER =========================

with tab_explorer:
    st.header("기사 탐색기")

    # Use the best available data: merged > articles > raw
    _explorer_df = merged_df if merged_df is not None else (articles_df if articles_df is not None else raw_df)

    if _explorer_df is not None:
      try:
        # Determine source column name (raw uses source_id, processed uses source)
        _src_col = "source" if "source" in _explorer_df.columns else ("source_id" if "source_id" in _explorer_df.columns else None)

        col_e1, col_e2, col_e3 = st.columns(3)

        with col_e1:
            if _src_col:
                sources = ["전체"] + sorted(_explorer_df[_src_col].dropna().unique().tolist())
                selected_source = st.selectbox("언론사", sources)
            else:
                selected_source = "전체"

        with col_e2:
            if "language" in _explorer_df.columns:
                languages = ["전체"] + sorted(_explorer_df["language"].dropna().unique().tolist())
                selected_lang = st.selectbox("언어", languages)
            else:
                selected_lang = "전체"

        with col_e3:
            search_query = st.text_input("제목 검색", "")

        filtered = _explorer_df.copy()
        if selected_source != "전체" and _src_col:
            filtered = filtered[filtered[_src_col] == selected_source]
        if selected_lang != "전체" and "language" in filtered.columns:
            filtered = filtered[filtered["language"] == selected_lang]
        if search_query and "title" in filtered.columns:
            filtered = filtered[
                filtered["title"].str.contains(search_query, case=False, na=False)
            ]

        st.caption(f"{len(_explorer_df)}개 중 {len(filtered)}개 표시")

        if merged_df is None and articles_df is None:
            st.caption("원시 크롤링 데이터입니다. 분석 파이프라인 실행 시 감성·토픽 등 풍부한 결과를 볼 수 있습니다.")

        _sort_options = [c for c in ["published_at", "importance_score", "sentiment_score", "topic_probability"] if c in filtered.columns]
        if _sort_options:
            sort_col = st.selectbox("정렬 기준", _sort_options, index=0)
            sort_asc = st.checkbox("오름차순", value=False)
            filtered = filtered.sort_values(sort_col, ascending=sort_asc, na_position="last")

        display_cols = [
            "title", "source", "source_id", "source_name", "language", "published_at",
            "sentiment_label", "sentiment_score",
            "topic_id", "topic_label",
            "steeps_category", "importance_score",
        ]
        display_cols = [c for c in display_cols if c in filtered.columns]

        st.dataframe(
            filtered[display_cols].head(100),
            use_container_width=True,
            hide_index=True,
            height=500,
        )

        st.subheader("기사 상세")
        if len(filtered) > 0 and "title" in filtered.columns:
            article_titles = filtered["title"].head(50).tolist()
            selected_title = st.selectbox("기사 선택", article_titles)
            row = filtered[filtered["title"] == selected_title].iloc[0]

            col_d1, col_d2 = st.columns([2, 1])
            with col_d1:
                st.markdown(f"**{row.get('title', 'N/A')}**")
                _src_val = row.get("source", row.get("source_id", "N/A"))
                st.caption(f"언론사: {_src_val} | "
                           f"언어: {row.get('language', 'N/A')} | "
                           f"발행: {row.get('published_at', 'N/A')}")
                body = row.get("body", "")
                if isinstance(body, str) and body:
                    st.text_area("본문", body[:3000], height=300, disabled=True)

            with col_d2:
                st.markdown("**분석 결과**")
                for field in ["sentiment_label", "sentiment_score", "steeps_category",
                              "importance_score", "topic_id", "topic_label", "topic_probability"]:
                    if field in row.index and pd.notna(row[field]):
                        label = field.replace("_", " ").title()
                        st.text(f"{label}: {row[field]}")

                emotion_cols = [c for c in row.index if c.startswith("emotion_")]
                if emotion_cols:
                    st.markdown("**감정**")
                    emo_data = {c.replace("emotion_", "").title(): row[c]
                                for c in emotion_cols if pd.notna(row[c])}
                    if emo_data:
                        fig_emo = px.bar(
                            x=list(emo_data.keys()),
                            y=list(emo_data.values()),
                            labels={"x": "", "y": "점수"},
                            height=250,
                        )
                        fig_emo.update_layout(margin=dict(t=10, b=10))
                        st.plotly_chart(fig_emo, use_container_width=True)
      except Exception as e:
        st.error(f"기사 탐색기 렌더링 실패: {e}")
    else:
        st.info("기사 데이터가 없습니다. 먼저 크롤링을 실행하세요.")
        st.markdown(
            "```bash\n"
            ".venv/Scripts/python main.py --mode crawl --date YYYY-MM-DD\n"
            "```"
        )


# ---------------------------------------------------------------------------
# Sidebar — Cross Analysis summary + meta
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("교차 분석")

    try:
        if cross_df is not None and len(cross_df) > 0:
            analysis_types = cross_df["analysis_type"].value_counts()
            st.markdown("**분석 기법 결과**")
            for atype, cnt in analysis_types.items():
                st.text(f"  {atype}: {cnt:,}")

            st.markdown("---")
            st.markdown("**상위 개체 쌍 (강도순)**")
            if "strength" in cross_df.columns:
                top_cross = (
                    cross_df[cross_df["strength"].notna()]
                    .nlargest(10, "strength")[["source_entity", "target_entity", "relationship", "strength"]]
                )
                if len(top_cross) > 0:
                    st.dataframe(top_cross, use_container_width=True, hide_index=True)
        else:
            st.info("교차 분석 데이터 없음.")

        if networks_df is not None and len(networks_df) > 0:
            st.markdown("---")
            st.markdown("**네트워크 통계**")
            st.text(f"  엣지: {len(networks_df):,}")
            if "entity_a" in networks_df.columns and "entity_b" in networks_df.columns:
                st.text(f"  고유 개체 수: {pd.concat([networks_df['entity_a'], networks_df['entity_b']]).nunique():,}")
            if "community_id" in networks_df.columns:
                st.text(f"  커뮤니티: {networks_df['community_id'].nunique()}")
    except Exception as e:
        st.error(f"교차 분석 오류: {e}")

    st.markdown("---")
    st.caption("GlobalNews 크롤링 & 분석 파이프라인")
    st.caption(f"Available dates: {len(all_dates)} | Current: {period} view")
