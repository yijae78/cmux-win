"""GlobalNews Pipeline — Real-Time Monitoring Dashboard.

Launch:
    streamlit run monitor.py

Approach A (safe): Reads existing log files (crawl.log, analysis.log)
without modifying pipeline code. Parses structlog JSON events to
reconstruct live pipeline state.

Design: Dark theme inspired by Google Stitch — glassmorphism cards,
neon accent colors, rounded corners, minimalist layout.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_DIR = Path(__file__).parent
DATA_DIR = PROJECT_DIR / "data"
LOGS_DIR = DATA_DIR / "logs"
CRAWL_LOG = LOGS_DIR / "crawl.log"
ANALYSIS_LOG = LOGS_DIR / "analysis.log"
ERROR_LOG = LOGS_DIR / "errors.log"
RUN_METADATA = DATA_DIR / "output" / "run_metadata.json"
SOURCES_YAML = DATA_DIR / "config" / "sources.yaml"

# ---------------------------------------------------------------------------
# Design tokens — Google Stitch dark theme
# ---------------------------------------------------------------------------

BG_PRIMARY = "#191a1f"
BG_CARD = "rgba(255,255,255,0.04)"
BG_CARD_HOVER = "rgba(255,255,255,0.07)"
BORDER_CARD = "rgba(255,255,255,0.08)"
TEXT_PRIMARY = "#ffffff"
TEXT_SECONDARY = "rgba(255,255,255,0.55)"
TEXT_MUTED = "rgba(255,255,255,0.35)"

NEON_GREEN = "#00e676"
NEON_RED = "#ff5252"
NEON_BLUE = "#448aff"
NEON_AMBER = "#ffd740"
NEON_PURPLE = "#b388ff"
NEON_CYAN = "#18ffff"

# ---------------------------------------------------------------------------
# Group colors (A–J)
# ---------------------------------------------------------------------------

GROUP_COLORS = {
    "A": "#ff6b6b",
    "B": "#ffa06b",
    "C": "#ffd93d",
    "D": "#6bcb77",
    "E": "#4d96ff",
    "F": "#9b59b6",
    "G": "#1abc9c",
    "H": "#e74c3c",
    "I": "#f39c12",
    "J": "#3498db",
}

# ---------------------------------------------------------------------------
# CUSTOM_CSS — built from design tokens
# ---------------------------------------------------------------------------

CUSTOM_CSS = "".join([
    f"""
<style>
    /* Global dark theme */
    .stApp {{
        background-color: {BG_PRIMARY};
        color: {TEXT_PRIMARY};
    }}

    /* Hide Streamlit branding + remove top padding */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{visibility: hidden;}}
    .stApp > header {{display: none;}}
    .block-container {{padding-top: 0 !important; padding-bottom: 0 !important; margin-top: -1rem !important;}}
    .element-container {{margin-bottom: 0.3rem !important;}}
    div[data-testid="stVerticalBlock"] > div {{gap: 0.3rem !important;}}
    [data-testid="stHeader"] {{display: none !important;}}
    [data-testid="stToolbar"] {{display: none !important;}}
    [data-testid="stDecoration"] {{display: none !important;}}
    .stDeployButton {{display: none !important;}}

    /* KPI card styling — compact */
    .kpi-card {{
        background: {BG_CARD};
        border: 1px solid {BORDER_CARD};
        border-radius: 12px;
        padding: 10px 14px;
        text-align: center;
        backdrop-filter: blur(10px);
        transition: background 0.2s ease;
    }}
    .kpi-card:hover {{
        background: {BG_CARD_HOVER};
    }}
    .kpi-value {{
        font-size: clamp(22px, 3vw, 36px);
        font-weight: 700;
        line-height: 1.2;
        letter-spacing: -0.3px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .kpi-label {{
        font-size: clamp(10px, 1.2vw, 14px);
        color: {TEXT_SECONDARY};
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-top: 4px;
        white-space: nowrap;
    }}
    .kpi-delta {{
        font-size: clamp(10px, 1.1vw, 13px);
        margin-top: 3px;
        white-space: nowrap;
    }}

    /* Section card — compact */
    .section-card {{
        background: {BG_CARD};
        border: 1px solid {BORDER_CARD};
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 10px;
        backdrop-filter: blur(10px);
    }}
    .section-title {{
        font-size: 12px;
        font-weight: 600;
        color: {TEXT_SECONDARY};
        text-transform: uppercase;
        letter-spacing: 1.2px;
        margin-bottom: 10px;
    }}

    /* Progress bar */
    .progress-container {{
        background: rgba(255,255,255,0.06);
        border-radius: 10px;
        height: 20px;
        overflow: hidden;
        margin: 8px 0;
    }}
    .progress-fill {{
        height: 100%;
        border-radius: 10px;
        transition: width 0.5s ease;
        background: linear-gradient(90deg, {NEON_BLUE}, {NEON_GREEN});
    }}

    /* Pipeline stages */
    .stage-node {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 40px;
        height: 40px;
        border-radius: 50%;
        font-size: 14px;
        font-weight: 700;
        margin: 0 4px;
        transition: all 0.3s ease;
    }}
    .stage-done {{
        background: {NEON_GREEN};
        color: #000;
        box-shadow: 0 0 12px {NEON_GREEN}40;
    }}
    .stage-active {{
        background: {NEON_BLUE};
        color: #fff;
        box-shadow: 0 0 16px {NEON_BLUE}60;
        animation: pulse 1.5s infinite;
    }}
    .stage-pending {{
        background: transparent;
        border: 2px solid {TEXT_MUTED};
        color: {TEXT_MUTED};
    }}
    .stage-failed {{
        background: {NEON_RED};
        color: #fff;
        box-shadow: 0 0 12px {NEON_RED}40;
    }}

    @keyframes pulse {{
        0%, 100% {{ box-shadow: 0 0 16px {NEON_BLUE}60; }}
        50% {{ box-shadow: 0 0 24px {NEON_BLUE}90; }}
    }}

    /* Live indicator */
    .live-dot {{
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: {NEON_RED};
        margin-right: 8px;
        animation: blink 1s infinite;
    }}
    @keyframes blink {{
        0%, 100% {{ opacity: 1; }}
        50% {{ opacity: 0.3; }}
    }}

    /* Status badges */
    .badge {{
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
    }}
    .badge-success {{ background: {NEON_GREEN}20; color: {NEON_GREEN}; }}
    .badge-running {{ background: {NEON_BLUE}20; color: {NEON_BLUE}; }}
    .badge-pending {{ background: {TEXT_MUTED}20; color: {TEXT_MUTED}; }}
    .badge-error {{ background: {NEON_RED}20; color: {NEON_RED}; }}

    /* Log stream */
    .log-stream {{
        background: rgba(0,0,0,0.3);
        border: 1px solid {BORDER_CARD};
        border-radius: 12px;
        padding: 16px;
        font-family: 'JetBrains Mono', 'Fira Code', monospace;
        font-size: 12px;
        max-height: 250px;
        overflow-y: auto;
        line-height: 1.8;
    }}
    .log-error {{ color: {NEON_RED}; }}
    .log-warn {{ color: {NEON_AMBER}; }}
    .log-info {{ color: {TEXT_SECONDARY}; }}
    .log-success {{ color: {NEON_GREEN}; }}

    /* Site table */
    .site-row {{
        display: flex;
        align-items: center;
        padding: 8px 12px;
        border-bottom: 1px solid rgba(255,255,255,0.04);
        font-size: 13px;
    }}
    .site-row:hover {{
        background: rgba(255,255,255,0.03);
    }}

    /* Header bar — compact */
    .header-bar {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 8px 0;
        border-bottom: 1px solid {BORDER_CARD};
        margin-bottom: 12px;
    }}
    .header-title {{
        font-size: 16px;
        font-weight: 700;
        letter-spacing: -0.3px;
    }}
    .header-timer {{
        font-size: 20px;
        font-weight: 300;
        color: {TEXT_SECONDARY};
        font-family: 'JetBrains Mono', monospace;
    }}

    /* Streamlit element overrides */
    .stMetric > div {{
        background: transparent !important;
    }}
    div[data-testid="stMetricValue"] {{
        font-size: 32px !important;
    }}
</style>
""",
])

# ---------------------------------------------------------------------------
# Ctrl+scroll zoom
# ---------------------------------------------------------------------------

ZOOM_JS = """
<script>
(function() {
    const doc = window.parent.document;
    const root = doc.documentElement;
    let scale = 1;
    doc.addEventListener('wheel', function(e) {
        if (e.ctrlKey) {
            e.preventDefault();
            scale += e.deltaY < 0 ? 0.05 : -0.05;
            scale = Math.min(2.0, Math.max(0.5, scale));
            root.style.zoom = scale;
        }
    }, {passive: false});
})();
</script>
"""

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SiteStatus:
    """Crawl status for a single site."""

    site_id: str = ""
    group: str = ""
    status: str = "pending"
    articles: int = 0
    discovered: int = 0
    failed: int = 0
    elapsed: float = 0.0
    error_msg: str = ""
    tier_used: int = 0
    timestamp: str = ""


@dataclass
class StageStatus:
    """Analysis stage status."""

    stage_num: int = 0
    name: str = ""
    status: str = "pending"
    elapsed: float = 0.0
    articles: int = 0
    total_items: int = 0
    rate_per_s: float = 0.0
    memory_gb: float = 0.0
    error_msg: str = ""


@dataclass
class PipelineState:
    """Full pipeline state reconstructed from logs."""

    is_running: bool = False
    mode: str = "unknown"
    start_time: datetime | None = None
    phase: str = "idle"
    sites: dict[str, SiteStatus] = field(default_factory=dict)
    stages: dict[int, StageStatus] = field(default_factory=dict)
    total_sites: int = 0
    total_articles: int = 0
    active_site_ids: list[str] = field(default_factory=list)  # 실제 크롤링 대상
    errors: list[str] = field(default_factory=list)
    recent_logs: list[dict] = field(default_factory=list)
    memory_history: list[tuple[str, float]] = field(default_factory=list)
    articles_history: list[tuple[str, int]] = field(default_factory=list)
    session_success: int = 0
    session_error: int = 0


# ---------------------------------------------------------------------------
# Stage names (1–8)
# ---------------------------------------------------------------------------

STAGE_NAMES = {
    1: "Preprocessing",
    2: "Feature Extraction",
    3: "Article Analysis",
    4: "Aggregation",
    5: "Time Series",
    6: "Cross Analysis",
    7: "Signal Classification",
    8: "Data Output",
}

# Fallback estimates for remaining analysis stages when live progress
# exists only for the current stage. Values are in seconds.
STAGE_ETA_FALLBACK_SECONDS = {
    4: 20 * 60,  # Aggregation
    5: 10 * 60,  # Time Series
    6: 25 * 60,  # Cross Analysis
    7: 5 * 60,   # Signal Classification
    8: 5 * 60,   # Data Output
}

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _load_site_groups() -> dict[str, str]:
    """Load site-to-group mapping from sources.yaml."""
    groups = {}
    if SOURCES_YAML.exists():
        try:
            import yaml

            with open(SOURCES_YAML, encoding="utf-8") as f:
                config = yaml.safe_load(f)
            for site_id, site_cfg in config.get("sources", {}).items():
                groups[site_id] = site_cfg.get("group", "?")
        except Exception:
            pass
    return groups


def _find_latest_crawl_state_file() -> Path | None:
    """Return the most recently modified crawl state file under data/raw."""
    raw_dir = DATA_DIR / "raw"
    if not raw_dir.exists():
        return None

    candidates: list[Path] = []
    for child in raw_dir.iterdir():
        if not child.is_dir():
            continue
        state_file = child / ".crawl_state.json"
        if state_file.exists():
            candidates.append(state_file)

    if not candidates:
        return None

    return max(candidates, key=lambda p: p.stat().st_mtime)


def _format_crawl_target_date() -> str:
    """Format the active crawl target date from data/raw/<date> directory name."""
    state_file = _find_latest_crawl_state_file()
    if state_file is None:
        from datetime import timedelta as _td
        _KST = timezone(_td(hours=9))
        _now_kst = datetime.now(_KST)
        _weekday_ko = ["월", "화", "수", "목", "금", "토", "일"][_now_kst.weekday()]
        return _now_kst.strftime(f"%Y년 %m월 %d일 ({_weekday_ko})")

    try:
        target_date = datetime.strptime(state_file.parent.name, "%Y-%m-%d")
        _weekday_ko = ["월", "화", "수", "목", "금", "토", "일"][target_date.weekday()]
        return target_date.strftime(f"%Y년 %m월 %d일 ({_weekday_ko})")
    except ValueError:
        return state_file.parent.name


def _overlay_crawl_state_file(state: "PipelineState", site_groups: dict[str, str]) -> None:
    """Overlay authoritative crawl status from .crawl_state.json onto parsed state."""
    state_file = _find_latest_crawl_state_file()
    if state_file is None:
        return

    try:
        crawl_state = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return

    configured_total = len(site_groups)
    if configured_total > 0:
        state.total_sites = configured_total

    tracked_site_ids = list(crawl_state.keys())
    tracked_site_set = set(tracked_site_ids)
    has_analysis_activity = any(stage.status != "pending" for stage in state.stages.values())
    if tracked_site_ids:
        state.active_site_ids = tracked_site_ids

    # While crawling, never count stale log-only successes outside the state file.
    if state.phase == "crawling":
        for site_id, site_status in state.sites.items():
            if site_id not in tracked_site_set and site_status.status == "success":
                site_status.status = "pending"

    any_incomplete = False
    for site_id, site_data in crawl_state.items():
        if site_id not in state.sites:
            state.sites[site_id] = SiteStatus(
                site_id=site_id,
                group=site_groups.get(site_id, "?"),
            )

        site_status = state.sites[site_id]
        site_status.group = site_groups.get(site_id, site_status.group or "?")
        site_status.timestamp = site_data.get("last_updated", site_status.timestamp)

        processed_urls = site_data.get("processed_urls", [])
        if isinstance(processed_urls, list):
            site_status.discovered = max(site_status.discovered, len(processed_urls))

        if site_data.get("complete"):
            site_status.status = "success"
        else:
            any_incomplete = True
            site_status.status = "running" if state.is_running or state.phase == "crawling" else "pending"

    if any_incomplete and not has_analysis_activity and state.phase != "analyzing":
        state.phase = "crawling"
        state.is_running = True
    elif tracked_site_ids and not any_incomplete and not has_analysis_activity and state.phase not in ("analyzing", "complete"):
        state.phase = "complete"
        state.is_running = False


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

_PYLOG_RE = re.compile(
    r"(\d{2}:\d{2}:\d{2})\s+\[(\w+)\s*\]\s+[\w.]+:\s+(.*)"
)

# structlog format: 2026-03-30T00:45:10.824778Z [info] message
_STRUCTLOG_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2}T[\d:.]+Z?)\s+\[(\w+)\s*\]\s+(.*)"
)

# JSON file handler format: {"timestamp":"...","level":"...","logger":"...","message":"..."}
_JSON_FILE_RE = re.compile(r'^\s*\{')


def _parse_log_line(line: str) -> dict[str, Any] | None:
    """Parse a structlog JSON, Python logging, or structlog console log line."""
    line = line.strip()
    if not line:
        return None

    # Strip ANSI color codes
    line = _ANSI_RE.sub("", line)

    # Try JSON first
    if _JSON_FILE_RE.match(line):
        try:
            return json.loads(line)
        except (json.JSONDecodeError, Exception):
            pass

    # Try Python logging format: HH:MM:SS [LEVEL] logger: message
    m = _PYLOG_RE.match(line)
    if m:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%dT")
        return {
            "timestamp": today + m.group(1) + "Z",
            "level": m.group(2).lower(),
            "message": m.group(3),
            "event": m.group(3),
        }

    # Try structlog console format: 2026-03-30T00:45:10Z [info] message
    m = _STRUCTLOG_RE.match(line)
    if m:
        return {
            "timestamp": m.group(1),
            "level": m.group(2).lower(),
            "message": m.group(3),
            "event": m.group(3),
        }

    return None


def _parse_kv_message(msg: str) -> dict[str, str]:
    """Extract key=value pairs from a log message string."""
    pairs = {}
    for match in re.finditer(r"(\w+)=([^\s]+)", msg):
        pairs[match.group(1)] = match.group(2)
    return pairs


def parse_pipeline_state() -> PipelineState:
    """Reconstruct pipeline state by parsing log files."""
    state = PipelineState()
    site_groups = _load_site_groups()

    # Register known sites
    for site_id, group in site_groups.items():
        state.sites[site_id] = SiteStatus(site_id=site_id, group=group)
    state.total_sites = len(site_groups)

    # Register stages
    for num, name in STAGE_NAMES.items():
        state.stages[num] = StageStatus(stage_num=num, name=name)

    all_logs: list = []

    # Parse crawl log
    if CRAWL_LOG.exists():
        try:
            with open(CRAWL_LOG, encoding="utf-8", errors="replace") as f:
                for line in f:
                    entry = _parse_log_line(line)
                    if not entry:
                        continue
                    all_logs.append(entry)
                    _process_crawl_event(state, entry, site_groups)
        except Exception:
            pass

    # Parse analysis log
    if ANALYSIS_LOG.exists():
        try:
            with open(ANALYSIS_LOG, encoding="utf-8", errors="replace") as f:
                for line in f:
                    entry = _parse_log_line(line)
                    if not entry:
                        continue
                    all_logs.append(entry)
                    _process_analysis_event(state, entry)
        except Exception:
            pass

    # Parse error log
    if ERROR_LOG.exists():
        try:
            with open(ERROR_LOG, encoding="utf-8", errors="replace") as f:
                for line in f:
                    entry = _parse_log_line(line)
                    if not entry:
                        continue
                    all_logs.append(entry)
        except Exception:
            pass

    # Sort and keep last 50
    all_logs.sort(key=lambda x: x.get("timestamp", ""))
    state.recent_logs = all_logs[-50:]

    # Determine phase
    _determine_phase(state)

    # Overwrite crawl site completion with the authoritative state file.
    _overlay_crawl_state_file(state, site_groups)

    # Calculate total articles
    state.total_articles = sum(
        s.articles for s in state.sites.values()
        if s.status == "success"
    )

    # Fallback: crawl.log가 덮어써진 경우 raw JSONL에서 기사 수 보완
    if state.total_articles == 0:
        _fill_articles_from_raw(state)

    return state


def _fill_articles_from_raw(state: "PipelineState") -> None:
    """crawl.log에 기사 수가 없을 때 raw JSONL에서 읽어 보완한다."""
    import json as _json
    import yaml as _yaml

    # 날짜 파악 (analysis.log에서 date= 추출)
    date_str = None
    if ANALYSIS_LOG.exists():
        try:
            with open(ANALYSIS_LOG, encoding="utf-8", errors="replace") as f:
                for line in f:
                    m = re.search(r"date[=:](\d{4}-\d{2}-\d{2})", line)
                    if m:
                        date_str = m.group(1)
                        break
        except Exception:
            pass

    if not date_str:
        from datetime import date
        date_str = date.today().isoformat()

    raw_file = DATA_DIR / "raw" / date_str / "all_articles.jsonl"
    if not raw_file.exists():
        return

    # sources.yaml에서 group 매핑
    group_map: dict[str, str] = {}
    try:
        with open(SOURCES_YAML, encoding="utf-8") as f:
            sources = _yaml.safe_load(f).get("sources", {})
        for key, s in sources.items():
            group_map[key] = s.get("group", "?")
    except Exception:
        pass

    site_counts: dict[str, int] = defaultdict(int)
    try:
        with open(raw_file, encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    d = _json.loads(line)
                    src = d.get("source_id") or d.get("site_id") or ""
                    if src:
                        site_counts[src] += 1
                except Exception:
                    pass
    except Exception:
        return

    for site_id, count in site_counts.items():
        if site_id in state.sites:
            state.sites[site_id].articles = count
            if state.sites[site_id].status == "pending":
                state.sites[site_id].status = "success"
            if not state.sites[site_id].group and site_id in group_map:
                state.sites[site_id].group = group_map[site_id]

    # active_site_ids가 비어있으면 raw에서 파악한 사이트 목록으로 채움
    if not state.active_site_ids and site_counts:
        state.active_site_ids = list(site_counts.keys())
        state.total_sites = len(state.active_site_ids)

    state.total_articles = sum(
        s.articles for s in state.sites.values() if s.articles > 0
    )


# ---------------------------------------------------------------------------
# Event processors
# ---------------------------------------------------------------------------


def _process_crawl_event(state: PipelineState, entry: dict, site_groups: dict[str, str]) -> None:
    """Process a single crawl log event."""
    msg = entry.get("message", "") or entry.get("event", "")
    ts = entry.get("timestamp", "")

    # Pipeline start
    if "Crawl started" in msg or "crawl_started" in msg or "Full pipeline started" in msg:
        state.is_running = True
        state.session_success = 0
        state.session_error = 0
        try:
            state.start_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            state.start_time = datetime.now(timezone.utc)

    # Actual target sites (overrides total_sites with real crawl count)
    if "target_sites" in msg:
        kv = _parse_kv_message(msg)
        count = kv.get("count", "")
        if count.isdigit():
            state.total_sites = int(count)
        # Parse sites list: sites=['chosun', 'bbc', ...]
        m = re.search(r"sites=\[([^\]]+)\]", msg)
        if m:
            raw = m.group(1)
            ids = [s.strip().strip("'\"") for s in raw.split(",") if s.strip()]
            state.active_site_ids = ids

    # Site already complete (이전 크롤링 데이터 존재 — 재수집 건너뜀)
    if "site_already_complete" in msg:
        kv = _parse_kv_message(msg)
        site_id = kv.get("site_id", kv.get("site", ""))
        if site_id and site_id in state.sites:
            state.sites[site_id].status = "success"
            state.sites[site_id].timestamp = ts

    # Site start
    if "crawl_site_start" in msg:
        kv = _parse_kv_message(msg)
        site_id = kv.get("site", "")
        if site_id and site_id in state.sites:
            state.sites[site_id].status = "running"
            state.sites[site_id].timestamp = ts

    # Site complete
    if "crawl_site_complete" in msg:
        kv = _parse_kv_message(msg)
        site_id = kv.get("site", "")
        if site_id and site_id in state.sites:
            articles = int(kv.get("articles", 0))
            yielded = kv.get("yielded", "False") == "True"
            # yielded=True: 데드라인 초과로 재시작 예정 → 아직 진행 중
            final_status = "running" if yielded else ("success" if articles >= 0 else "error")
            state.sites[site_id].status = final_status
            if not yielded:
                if final_status == "success":
                    state.session_success += 1
                elif final_status == "error":
                    state.session_error += 1
            
            state.sites[site_id].articles = articles
            state.sites[site_id].discovered = int(kv.get("discovered", 0))
            state.sites[site_id].failed = int(kv.get("failed", 0))
            state.sites[site_id].elapsed = float(kv.get("elapsed", "0").rstrip("s"))
            state.sites[site_id].timestamp = ts
            # Track cumulative articles
            total_so_far = sum(
                s.articles for s in state.sites.values()
                if s.status == "success"
            )
            state.articles_history.append((ts, total_so_far))

    # Discovery/extraction failure
    if "discovery_failed" in msg or "extraction_failed" in msg:
        kv = _parse_kv_message(msg)
        site_id = kv.get("site_id", kv.get("site", ""))
        if site_id and site_id in state.sites:
            if state.sites[site_id].status != "success":
                state.sites[site_id].status = "error"
                state.sites[site_id].error_msg = msg[:120]
                state.session_error += 1

    # Crawl complete
    if "crawl_complete" in msg or "Crawl complete" in msg or "pipeline_complete" in msg:
        state.phase = "complete"
        state.is_running = False


def _process_analysis_event(state: PipelineState, entry: dict) -> None:
    """Process a single analysis log event."""
    msg = entry.get("message", "") or entry.get("event", "")
    ts = entry.get("timestamp", "")

    if "analysis_pipeline_start" in msg:
        state.phase = "analyzing"
        state.is_running = True
        try:
            state.start_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            state.start_time = datetime.now(timezone.utc)
        for stage in state.stages.values():
            stage.status = "pending"
            stage.elapsed = 0.0
            stage.articles = 0
            stage.total_items = 0
            stage.rate_per_s = 0.0
            stage.memory_gb = 0.0
            stage.error_msg = ""

    if "stage_start" in msg:
        kv = _parse_kv_message(msg)
        stage = int(kv.get("stage", 0))
        if stage in state.stages:
            state.stages[stage].status = "running"

    if "stage_complete" in msg:
        kv = _parse_kv_message(msg)
        stage = int(kv.get("stage", 0))
        if stage in state.stages:
            elapsed = float(kv.get("elapsed", "0").rstrip("s"))
            articles = int(kv.get("articles", 0))
            state.stages[stage].status = "complete"
            state.stages[stage].elapsed = elapsed
            state.stages[stage].articles = articles
            state.stages[stage].total_items = articles
            state.stages[stage].rate_per_s = articles / elapsed if elapsed > 0 else 0.0
            mem_str = kv.get("memory", "0").replace("_GB", "")
            state.stages[stage].memory_gb = float(mem_str)
            state.memory_history.append((ts, float(mem_str)))

    if "stage3_progress" in msg:
        kv = _parse_kv_message(msg)
        stage = 3
        if stage in state.stages:
            processed = int(entry.get("processed", kv.get("processed", 0)))
            total = int(entry.get("total", kv.get("total", 0)))
            elapsed_val = entry.get("elapsed_s", kv.get("elapsed_s", "0"))
            elapsed = float(str(elapsed_val).rstrip("s"))
            rate = processed / elapsed if elapsed > 0 else 0.0
            current = state.stages[stage]
            current.status = "running"
            current.articles = processed
            current.total_items = total
            current.elapsed = elapsed
            current.rate_per_s = rate

    if "stage_failed" in msg:
        kv = _parse_kv_message(msg)
        stage = int(kv.get("stage", 0))
        if stage in state.stages:
            state.stages[stage].status = "failed"
            state.stages[stage].error_msg = kv.get("error", "")

    if "stage_skipped" in msg:
        kv = _parse_kv_message(msg)
        stage = int(kv.get("stage", 0))
        if stage in state.stages:
            state.stages[stage].status = "skipped"

    if "analysis_pipeline_complete" in msg or "Analysis complete:" in msg:
        state.phase = "complete"
        state.is_running = False


def _determine_phase(state: PipelineState) -> None:
    """Determine the overall pipeline phase."""
    # If already marked complete by log events, don't override
    if state.phase == "complete":
        state.is_running = False
        return

    has_running_site = any(s.status == "running" for s in state.sites.values())
    has_completed_site = any(s.status == "success" for s in state.sites.values())
    has_running_stage = any(s.status == "running" for s in state.stages.values())
    has_completed_stage = any(s.status == "complete" for s in state.stages.values())
    has_analysis_activity = any(s.status != "pending" for s in state.stages.values())
    all_stages_done = all(
        s.status in ("complete", "failed", "skipped")
        for s in state.stages.values()
    )

    if has_running_stage:
        state.phase = "analyzing"
        state.is_running = True
    elif has_running_site:
        state.phase = "crawling"
        state.is_running = True
    elif all_stages_done and has_completed_stage:
        state.phase = "complete"
        state.is_running = False
    elif all_stages_done and has_analysis_activity:
        state.phase = "complete"
        state.is_running = False
    elif has_completed_site and not has_running_site and not has_completed_stage:
        # All sites done, no analysis started — crawl complete
        state.phase = "complete"
        state.is_running = False
    elif has_analysis_activity:
        state.phase = "analyzing"
        state.is_running = False
    elif has_completed_site and not has_completed_stage:
        state.phase = "crawling"
    elif not has_completed_site and not has_completed_stage:
        state.phase = "idle"
        state.is_running = False


# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------


def generate_sample_state() -> PipelineState:
    """Generate realistic sample data for dashboard preview."""
    import random

    random.seed(42)

    state = PipelineState()
    site_groups = _load_site_groups()
    state.total_sites = len(site_groups) if site_groups else 116

    if not site_groups:
        demo_sites = {
            "chosun": "A", "donga": "A", "yna": "A", "hani": "A",
            "joongang": "B", "kbs": "B", "mbc": "B", "sbs": "B",
            "mk": "C", "hankyung": "C", "mt": "C",
            "etnews": "D", "bloter": "D", "zdnet_kr": "D",
            "bbc": "E", "reuters": "E", "nytimes": "E",
            **{
                "theguardian": "E",
                "cnn": "E", "fortune": "E", "wired": "E", "axios": "E",
                "asahi": "F", "scmp": "F", "taipeitimes": "F",
                "aljazeera": "G", "france24": "G", "spiegel": "G", "elpais": "G",
                "africanews": "H", "dailymaverick": "H",
                "folha": "I", "clarin": "I",
                "tass": "J",
            },
            "ria": "J",
        }
        site_groups = demo_sites

    now = datetime.now(timezone.utc)
    state.start_time = datetime(
        now.year, now.month, now.day, now.hour - 1, now.minute, 0,
        tzinfo=timezone.utc,
    )
    state.is_running = False
    state.phase = "complete"

    # Generate site statuses
    site_list = list(site_groups.items())
    n_done = int(len(site_list) * 0.92)
    n_running = 0
    n_error = int(len(site_list) * 0.08)

    for i, (site_id, group) in enumerate(site_list):
        ss = SiteStatus(site_id=site_id, group=group)
        if i < n_done:
            ss.status = "success"
            ss.articles = random.randint(15, 350)
            ss.discovered = ss.articles + random.randint(5, 50)
            ss.elapsed = random.uniform(8.0, 180.0)
        elif i < n_done + n_running:
            ss.status = "running"
        elif i < n_done + n_running + n_error:
            ss.status = "error"
            ss.error_msg = random.choice(
                ["403 Forbidden", "Connection timeout", "Cloudflare block",
                 "Empty RSS feed", "SSL certificate error"]
            )
        else:
            ss.status = "pending"
        state.sites[site_id] = ss

    state.total_articles = sum(
        s.articles for s in state.sites.values()
        if s.status == "success"
    )

    # Stages: all complete for demo
    for num, name in STAGE_NAMES.items():
        ss = StageStatus(stage_num=num, name=name)
        if True:  # all complete
            ss.status = "complete"
            ss.elapsed = random.uniform(30.0, 300.0)
            ss.articles = state.total_articles
            ss.memory_gb = random.uniform(0.8, 2.5)
        if False:  # disabled
            pass
        elif False:
            ss.status = "pending"
        state.stages[num] = ss

    # Build articles history
    cumulative = 0
    for i in range(n_done):
        cumulative += cumulative + site_list[i][0].__hash__() % 200 + 20
        ts = f"2026-03-27T{9 + i // 10:02d}:{i * 3 % 60:02d}:00Z"
        state.articles_history.append((ts, min(cumulative, state.total_articles)))

    # Clamp articles_history values
    state.articles_history = [
        (ts, min(v, state.total_articles))
        for ts, v in state.articles_history
    ]

    # Build memory history
    for i in range(20):
        ts = f"2026-03-27T{10 + i // 6:02d}:{i * 10 % 60:02d}:00Z"
        mem = 0.5 + i / 20 * 2.0 + random.uniform(-0.2, 0.2)
        state.memory_history.append((ts, max(0.3, mem)))

    # Sample logs
    state.recent_logs = [
        {"timestamp": "2026-03-27T10:42:15Z", "level": "info",
         "message": "crawl_site_complete site=reuters articles=187 discovered=210 failed=3 elapsed=45.2s"},
        {"timestamp": "2026-03-27T10:42:12Z", "level": "error",
         "message": "discovery_failed site_id=bbc error=403_Forbidden"},
        {"timestamp": "2026-03-27T10:42:10Z", "level": "info",
         "message": "crawl_site_complete site=chosun articles=203 discovered=215 failed=0 elapsed=32.1s"},
        {"timestamp": "2026-03-27T10:42:08Z", "level": "info",
         "message": "stage_complete stage=3 name=Article_Analysis elapsed=124.5s articles=2847 memory=1.82_GB"},
        {"timestamp": "2026-03-27T10:41:55Z", "level": "warning",
         "message": "memory_warning rss=2.31_GB threshold=2.0_GB context=stage_3"},
        {"timestamp": "2026-03-27T10:41:50Z", "level": "info",
         "message": "crawl_site_start site=scmp (45/116) restart=0 deadline_remaining=300s"},
        {"timestamp": "2026-03-27T10:41:42Z", "level": "info",
         "message": "crawl_site_complete site=nytimes articles=156 discovered=180 failed=2 elapsed=67.3s"},
        {"timestamp": "2026-03-27T10:41:30Z", "level": "info",
         "message": "stage_start stage=4 name=Aggregation"},
    ]

    return state


# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------


def render_kpi_card(value: str, label: str, color: str = TEXT_PRIMARY, delta: str = "") -> str:
    """Render a glassmorphism KPI card."""
    delta_html = f'<div class="kpi-delta" style="color:{color}">{delta}</div>' if delta else ""
    return (
        f'\n    <div class="kpi-card">\n        <div class="kpi-value" style="color:{color}">{value}'
        f'</div>\n        <div class="kpi-label">{label}'
        f'</div>\n        {delta_html}'
        f'\n    </div>\n    '
    )


def render_progress_bar(current: int, total: int) -> str:
    """Render a gradient progress bar."""
    pct = current / total * 100 if total > 0 else 0
    return (
        f'\n    <div class="progress-container">\n        <div class="progress-fill" style="width:'
        f'{pct:.1f}%"></div>\n    </div>\n    <div style="text-align:center; color:'
        f'{TEXT_SECONDARY}; font-size:13px; margin-top:4px">\n        '
        f'{current} / {total} 사이트 &nbsp;&middot;&nbsp; {pct:.0f}'
        f'%\n    </div>\n    '
    )


def render_stage_pipeline(stages: dict[int, StageStatus]) -> str:
    """Render the 8-stage pipeline indicator with inline styles only."""
    STAGE_LABELS_KO = {
        1: "전처리", 2: "특징추출", 3: "기사분석", 4: "집계",
        5: "시계열", 6: "교차분석", 7: "신호분류", 8: "출력",
    }

    node_base = (
        "display:inline-flex;align-items:center;justify-content:center;"
        "width:42px;height:42px;border-radius:50%;font-size:16px;"
        "font-weight:700;flex-shrink:0;"
    )

    styles = {
        "complete": f"{node_base}background:{NEON_GREEN};color:#000;box-shadow:0 0 10px {NEON_GREEN}40;",
        "running": f"{node_base}background:{NEON_BLUE};color:#fff;box-shadow:0 0 14px {NEON_BLUE}60;",
        "failed": f"{node_base}background:{NEON_RED};color:#fff;",
    }

    style_pending = f"{node_base}background:transparent;border:2px solid {TEXT_MUTED};color:{TEXT_MUTED};"

    items = []
    for num in range(1, 9):
        s = stages.get(num, StageStatus(stage_num=num, name=STAGE_NAMES[num]))
        st_style = styles.get(s.status, style_pending)
        label = STAGE_LABELS_KO.get(num, f"S{num}")

        elapsed_s = (
            f'<div style="color:{TEXT_MUTED};font-size:9px;">{s.elapsed:.0f}s</div>'
            if s.elapsed > 0
            else ""
        )
        progress_text = ""
        if s.total_items > 0:
            pct = s.articles / s.total_items * 100 if s.total_items else 0.0
            progress_text = (
                f'<div style="color:{TEXT_SECONDARY};font-size:9px;">'
                f'{s.articles:,}/{s.total_items:,} ({pct:.0f}%)</div>'
            )

        connector = ""
        if num > 1:
            prev_done = stages.get(num - 1, StageStatus()).status == "complete"
            c_color = NEON_GREEN if prev_done else TEXT_MUTED
            connector = (
                f'<div style="width:16px;height:2px;background:{c_color}'
                f';flex-shrink:0;margin:0 2px;align-self:center;"></div>'
            )

        items.append(
            f'{connector}'
            f'<div style="display:flex;flex-direction:column;align-items:center;flex-shrink:0;"><span style="'
            f'{st_style}">{num}'
            f'</span><div style="font-size:clamp(11px,1.2vw,14px);color:'
            f'{TEXT_SECONDARY};margin-top:4px;white-space:nowrap;font-weight:500;">{label}</div>'
            f'{elapsed_s}'
            f'{progress_text}'
            f'</div>'
        )

    return (
        f'<div style="display:flex;flex-wrap:wrap;justify-content:center;'
        f'align-items:flex-start;gap:2px 0;padding:6px 0;">'
        f'{"".join(items)}'
        f'</div>'
    )


def render_status_badge(status: str) -> str:
    """Render a colored status badge."""
    badge_map = {
        "success": ("badge-success", "성공"),
        "running": ("badge-running", "진행 중"),
        "pending": ("badge-pending", "대기"),
        "error": ("badge-error", "오류"),
        "complete": ("badge-success", "완료"),
        "failed": ("badge-error", "실패"),
        "skipped": ("badge-pending", "건너뜀"),
    }
    cls, text = badge_map.get(status, ("badge-pending", status.upper()))
    return f'<span class="badge {cls}">{text}</span>'


def render_log_stream(logs: list[dict]) -> str:
    """Render the real-time log stream."""
    lines = []
    for entry in reversed(logs[-15:]):
        ts = entry.get("timestamp", "")
        if ts:
            ts = ts.split("T")[-1][:8]
        msg = entry.get("message", "") or entry.get("event", "")
        level = entry.get("level", "info").lower()

        css_class = "log-info"
        if level == "error":
            css_class = "log-error"
        elif level == "warning":
            css_class = "log-warn"
        elif "complete" in msg and "articles=" in msg:
            css_class = "log-success"

        lines.append(
            f'<div class="{css_class}"><span style="color:'
            f'{TEXT_MUTED}">[{ts}]</span> {msg[:150]}'
            f'</div>'
        )

    return f'<div class="log-stream">{"".join(lines)}</div>'


def _format_eta(eta_secs: float) -> str:
    """Format seconds as HH:MM, capping very large values."""
    eta_int = max(0, int(eta_secs))
    if eta_int > 3600 * 24:
        return ">24h"
    return f"{eta_int // 3600:02d}:{eta_int % 3600 // 60:02d}"


def _estimate_remaining_analysis_seconds(state: PipelineState) -> float | None:
    """Estimate time remaining until all analysis stages are finished."""
    total_remaining = 0.0
    saw_active_stage = False

    for stage_num in range(1, 9):
        stage = state.stages.get(stage_num)
        if stage is None or stage.status in ("complete", "skipped"):
            continue

        if stage.status == "running":
            saw_active_stage = True
            if stage.total_items > 0 and stage.rate_per_s > 0:
                remaining_items = max(0, stage.total_items - stage.articles)
                total_remaining += remaining_items / stage.rate_per_s
            else:
                total_remaining += STAGE_ETA_FALLBACK_SECONDS.get(stage_num, 0)
            continue

        if stage.status == "pending":
            saw_active_stage = True
            total_remaining += STAGE_ETA_FALLBACK_SECONDS.get(stage_num, 0)

    if not saw_active_stage:
        return None
    return total_remaining


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------


def build_articles_chart(history: list[tuple[str, int]]) -> go.Figure:
    """Build cumulative articles collected chart."""
    if not history:
        return go.Figure()

    times = [
        h[0].split("T")[-1][:8] if "T" in h[0] else h[0]
        for h in history
    ]
    values = [h[1] for h in history]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=times, y=values,
        mode="lines+markers",
        line=dict(color=NEON_GREEN, width=2),
        marker=dict(size=4, color=NEON_GREEN),
        fill="tozeroy",
        fillcolor=f"{NEON_GREEN}10",
        name="기사 수",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT_SECONDARY, size=11),
        margin=dict(l=40, r=10, t=10, b=30),
        height=200,
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)", showgrid=True),
        yaxis=dict(gridcolor="rgba(255,255,255,0.05)", showgrid=True),
        showlegend=False,
    )
    return fig


def build_memory_chart(history: list[tuple[str, float]]) -> go.Figure:
    """Build memory usage area chart."""
    if not history:
        return go.Figure()

    times = [
        h[0].split("T")[-1][:8] if "T" in h[0] else h[0]
        for h in history
    ]
    values = [h[1] for h in history]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=times, y=values,
        mode="lines",
        line=dict(color=NEON_AMBER, width=2),
        fill="tozeroy",
        fillcolor=f"{NEON_AMBER}15",
        name="RSS (GB)",
    ))
    fig.add_hline(
        y=10.0,
        line_dash="dash",
        line_color=NEON_RED,
        annotation_text="중단 기준: 10 GB",
        annotation_font_color=NEON_RED,
        annotation_font_size=10,
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT_SECONDARY, size=11),
        margin=dict(l=40, r=10, t=10, b=30),
        height=200,
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)", showgrid=True),
        yaxis=dict(gridcolor="rgba(255,255,255,0.05)", showgrid=True, title="GB"),
        showlegend=False,
    )
    return fig


GROUP_REGION_NAMES = {
    "A": "한국 주요",
    "B": "한국 방송",
    "C": "한국 경제",
    "D": "한국 IT",
    "E": "영미권",
    "F": "아시아태평양",
    "G": "유럽·중동",
    "H": "아프리카",
    "I": "중남미",
    "J": "러시아",
}


def build_group_chart(sites: dict[str, SiteStatus], active_site_ids: list[str] | None = None) -> go.Figure:
    """Build articles per group horizontal bar chart (active sites only)."""
    group_articles: dict[str, int] = defaultdict(int)
    group_done: dict[str, int] = defaultdict(int)
    group_total: dict[str, int] = defaultdict(int)

    target = (
        {sid: sites[sid] for sid in active_site_ids if sid in sites}
        if active_site_ids else sites
    )

    for s in target.values():
        group_articles[s.group] += s.articles
        group_total[s.group] += 1
        if s.status in ("success",):
            group_done[s.group] += 1

    # 기사 수 기준 내림차순 정렬
    groups = sorted(group_articles.keys(), key=lambda g: group_articles[g], reverse=True)
    values = [group_articles[g] for g in groups]
    colors = [GROUP_COLORS.get(g, NEON_BLUE) for g in groups]
    labels = [
        f"{g} · {GROUP_REGION_NAMES.get(g, '')} ({group_done[g]}/{group_total[g]}개)"
        for g in groups
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=values, y=labels,
        orientation="h",
        marker_color=colors,
        text=[f"{v}건" for v in values],
        textposition="auto",
        textfont=dict(size=11),
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT_SECONDARY, size=12),
        margin=dict(l=160, r=20, t=10, b=10),
        height=max(200, len(groups) * 45),
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)", showgrid=True, title="기사 수"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
        showlegend=False,
    )
    return fig


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(
        page_title="GlobalNews Pipeline Monitor",
        page_icon="🌐",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    import streamlit.components.v1 as components
    components.html(ZOOM_JS, height=0)

    # Sidebar
    with st.sidebar:
        st.markdown("### 설정")
        refresh_rate = st.slider("갱신 주기 (초)", 1, 10, 3)
        demo_mode = st.toggle("데모 모드", value=False, help="샘플 데이터로 미리보기")
        if st.button("새로고침"):
            st.rerun()

    # URL param override: ?demo=1 forces demo mode
    _url_demo = st.query_params.get("demo", None)
    if _url_demo == "1":
        demo_mode = True

    _render_dashboard(refresh_rate=refresh_rate, demo_mode=demo_mode)


@st.fragment(run_every=3)
def _render_dashboard(refresh_rate: int = 3, demo_mode: bool = False) -> None:
    """Fragment: 전체 페이지 reload 없이 부분 갱신 — 깜빡임 없음."""
    # Load state
    if demo_mode:
        state = generate_sample_state()
    else:
        state = parse_pipeline_state()

    # Elapsed time
    elapsed_str = "00:00:00"
    if state.start_time:
        delta = datetime.now(timezone.utc) - state.start_time
        total_secs = int(delta.total_seconds())
        h, m, s = total_secs // 3600, total_secs % 3600 // 60, total_secs % 60
        elapsed_str = f"{h:02d}:{m:02d}:{s:02d}"

    # Phase label
    phase_label = {
        "idle": "대기 중",
        "crawling": "크롤링 중",
        "analyzing": "분석 중",
        "complete": "완료",
    }.get(state.phase, state.phase.upper())

    live_dot = '<span class="live-dot"></span>' if state.is_running else ""

    # Completion timestamp (KST = UTC+9)
    complete_time_str = ""
    if state.phase == "complete":
        from datetime import timedelta
        KST = timezone(timedelta(hours=9))
        complete_time_str = datetime.now(KST).strftime("%H:%M:%S")

    # Counts
    n_success = sum(1 for s in state.sites.values() if s.status == "success")
    n_running = sum(1 for s in state.sites.values() if s.status == "running")
    n_error = sum(1 for s in state.sites.values() if s.status == "error")
    success_rate = n_success / state.total_sites * 100 if state.total_sites > 0 else 0

    # ETA
    eta_label = "잔여 시간"
    if state.phase == "complete":
        eta_str = "0:00"
    elif state.phase == "analyzing":
        eta_label = "분석 ETA"
        analysis_eta_secs = _estimate_remaining_analysis_seconds(state)
        if analysis_eta_secs is not None:
            eta_str = _format_eta(analysis_eta_secs)
        else:
            eta_str = "--:--"
    elif (state.session_success + state.session_error) > 0 and state.start_time and state.is_running:
        elapsed_total = (datetime.now(timezone.utc) - state.start_time).total_seconds()
        # Rate based on actual work done in THIS session
        session_done = state.session_success + state.session_error
        rate = session_done / elapsed_total if elapsed_total > 0 else 0
        
        # Remaining items (overall)
        n_done_total = n_success + n_error
        remaining = state.total_sites - n_done_total
        
        if rate > 0 and remaining > 0:
            eta_str = _format_eta(remaining / rate)
        elif remaining <= 0:
            eta_str = "0:00"
        else:
            eta_str = "--:--"
    else:
        eta_str = "--:--"

    # Memory
    current_memory = 0.0
    if state.memory_history:
        current_memory = state.memory_history[-1][1]

    rate_color = NEON_GREEN if success_rate >= 80 else NEON_AMBER if success_rate >= 50 else NEON_RED
    mem_color = NEON_GREEN if current_memory < 4 else NEON_AMBER if current_memory < 8 else NEON_RED
    badge_cls = "running" if state.is_running else "success" if state.phase == "complete" else "pending"

    # Running sites
    running_sites = [s.site_id for s in state.sites.values() if s.status == "running"]
    sites_str = ", ".join(running_sites[:6])
    if len(running_sites) > 6:
        sites_str += f" +{len(running_sites) - 6}"
    running_stage = next(
        (
            stage
            for stage in sorted(state.stages.values(), key=lambda s: s.stage_num)
            if stage.status == "running"
        ),
        None,
    )

    # Progress
    prog_title = "크롤링 진행률"
    prog_numerator = n_success
    prog_denominator = state.total_sites
    prog_pct = n_success / state.total_sites * 100 if state.total_sites > 0 else 0
    progress_detail_html = ""

    if state.phase == "analyzing" and running_stage and running_stage.total_items > 0:
        prog_title = "분석 진행률"
        prog_numerator = running_stage.articles
        prog_denominator = running_stage.total_items
        prog_pct = running_stage.articles / running_stage.total_items * 100
        rate_text = ""
        if running_stage.rate_per_s > 0:
            rate_text = (
                f' · {running_stage.rate_per_s:.3f} article/s'
                if running_stage.rate_per_s >= 1
                else f' · {1 / running_stage.rate_per_s:.1f} sec/article'
            )
        progress_detail_html = (
            f'<div style="color:{TEXT_SECONDARY};font-size:11px;margin-top:4px">'
            f'현재: <span style="color:{NEON_BLUE}">Stage {running_stage.stage_num} {running_stage.name}'
            f'</span>{rate_text} · ETA includes stages 4-8</div>'
        )
    elif running_sites:
        progress_detail_html = (
            f'<div style="color:{TEXT_SECONDARY};font-size:11px;margin-top:4px">현재: <span style="color:'
            f'{NEON_BLUE}">{sites_str}</span></div>'
        )

    # Stage pipeline HTML
    stage_nodes_html = render_stage_pipeline(state.stages)

    # Deltas
    running_delta = f"{n_running}개 진행 중" if n_running > 0 else ""
    error_delta = f"{n_error}개 오류" if n_error > 0 else ""

    # Card wrappers
    CARD_OPEN = (
        f'<div style="background:{BG_CARD};border:1px solid {BORDER_CARD}'
        f';border-radius:12px;padding:14px 16px;margin-bottom:10px;">'
    )
    CARD_CLOSE = "</div>"

    def section_title(text: str, color: str) -> str:
        return (
            f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">'
            f'<div style="width:4px;height:20px;border-radius:2px;background:{color}'
            f';flex-shrink:0;"></div><span style="font-size:clamp(14px,1.4vw,17px);font-weight:700;color:'
            f'{TEXT_PRIMARY};letter-spacing:0.5px;">{text}</span></div>'
        )

    # ---- Detect dashboard.py port ----
    def _find_dashboard_port() -> int | None:
        """Find the port where dashboard.py is running."""
        import subprocess
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | "
                 "ForEach-Object { $p = Get-CimInstance Win32_Process -Filter \"ProcessId=$($_.OwningProcess)\" -ErrorAction SilentlyContinue; "
                 "if ($p.CommandLine -match 'dashboard\\.py.*--server\\.port\\s+(\\d+)') { $Matches[1] } }"],
                capture_output=True, text=True, timeout=5,
            )
            ports = [int(p.strip()) for p in result.stdout.strip().split("\n") if p.strip().isdigit()]
            return ports[0] if ports else None
        except Exception:
            return None

    # ---- HEADER BAR ----
    analysis_button = ""
    if state.phase == "complete":
        phase_badge = (
            f'<span style="display:inline-flex;align-items:center;gap:6px;'
            f'background:{NEON_GREEN}25;border:2px solid {NEON_GREEN};'
            f'border-radius:10px;padding:6px 16px;font-size:16px;color:{NEON_GREEN};'
            f'font-weight:700;white-space:nowrap;box-shadow:0 0 20px {NEON_GREEN}40;'
            f'animation:pulse 1.5s infinite;">&#10003; 완료</span>'
        )
        complete_info = (
            f'<span style="font-size:12px;color:{TEXT_SECONDARY};margin-left:8px;">'
            f'완료 시각: {complete_time_str}</span>'
        ) if complete_time_str else ""

        # "결과 분석 보기" button
        dash_port = _find_dashboard_port()
        dash_url = f"http://localhost:{dash_port}" if dash_port else None
        if dash_url:
            analysis_button = (
                f'<a href="{dash_url}" target="_blank" style="text-decoration:none;margin-left:8px;">'
                f'<span style="display:inline-flex;align-items:center;gap:6px;'
                f'background:{NEON_CYAN}20;border:2px solid {NEON_CYAN};'
                f'border-radius:10px;padding:6px 16px;font-size:15px;color:{NEON_CYAN};'
                f'font-weight:700;white-space:nowrap;box-shadow:0 0 16px {NEON_CYAN}35;'
                f'cursor:pointer;transition:all 0.3s ease;"'
                f' onmouseover="this.style.boxShadow=\'0 0 28px {NEON_CYAN}60\';this.style.background=\'{NEON_CYAN}30\'"'
                f' onmouseout="this.style.boxShadow=\'0 0 16px {NEON_CYAN}35\';this.style.background=\'{NEON_CYAN}20\'"'
                f'>&#128202; 결과 분석 보기 &rarr;</span></a>'
            )
    elif state.phase == "crawling":
        phase_badge = (
            f'<span style="display:inline-flex;align-items:center;gap:5px;'
            f'background:{NEON_BLUE}18;border:1px solid {NEON_BLUE}40;'
            f'border-radius:8px;padding:4px 10px;font-size:clamp(13px,1.3vw,16px);color:{NEON_BLUE};'
            f'font-weight:600;white-space:nowrap;">&#9654; 크롤링 중</span>'
        )
        complete_info = ""
    else:
        phase_badge = (
            f'<span style="display:inline-flex;align-items:center;gap:5px;'
            f'background:{TEXT_MUTED}18;border:1px solid {TEXT_MUTED}40;'
            f'border-radius:8px;padding:4px 10px;font-size:clamp(13px,1.3vw,16px);color:{TEXT_MUTED};'
            f'font-weight:600;white-space:nowrap;">{phase_label}</span>'
        )
        complete_info = ""

    # Crawl target date display
    _date_display = _format_crawl_target_date()

    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;padding:6px 0;margin-bottom:8px;">'
        f'<span style="font-size:15px;font-weight:700;">'
        f'{live_dot}GlobalNews Pipeline Monitor</span>'
        f'{phase_badge}{complete_info}{analysis_button}'
        f'<span style="font-size:18px;font-weight:300;color:{TEXT_SECONDARY}'
        f';font-family:monospace;margin-left:auto;">{elapsed_str}</span></div>'
        f'<div style="text-align:center;margin-bottom:10px;">'
        f'<span style="font-size:clamp(16px,1.8vw,22px);font-weight:600;color:{NEON_CYAN}'
        f';letter-spacing:1px;">{_date_display}</span></div>',
        unsafe_allow_html=True,
    )

    # ---- PROGRESS SECTION ----
    badge_style = {
        "running": f"background:{NEON_BLUE}20;color:{NEON_BLUE}",
        "success": f"background:{NEON_GREEN}20;color:{NEON_GREEN}",
        "pending": f"background:{TEXT_MUTED}20;color:{TEXT_MUTED}",
    }.get(badge_cls, f"background:{TEXT_MUTED}20;color:{TEXT_MUTED}")

    running_chips = ""
    if state.phase == "analyzing" and running_stage and running_stage.total_items > 0:
        chips = (
            f'<span style="display:inline-flex;align-items:center;gap:5px;background:'
            f'{NEON_BLUE}18;border:1px solid {NEON_BLUE}40;border-radius:8px;padding:4px 10px;'
            f'font-size:clamp(13px,1.3vw,16px);color:{NEON_BLUE};font-weight:600;white-space:nowrap;">'
            f'&#9654; Stage {running_stage.stage_num}: {running_stage.articles:,}/{running_stage.total_items:,}'
            f'</span>'
        )
        running_chips = f'<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;">{chips}</div>'
    elif running_sites:
        chips = "".join(
            f'<span style="display:inline-flex;align-items:center;gap:5px;background:'
            f'{NEON_BLUE}18;border:1px solid {NEON_BLUE}'
            f'40;border-radius:8px;padding:4px 10px;font-size:clamp(13px,1.3vw,16px);color:'
            f'{NEON_BLUE};font-weight:600;white-space:nowrap;">&#9654; {site_id}</span>'
            for site_id in running_sites[:6]
        )
        if len(running_sites) > 6:
            chips += (
                f'<span style="font-size:clamp(12px,1.2vw,15px);color:{TEXT_SECONDARY}'
                f';">+{len(running_sites) - 6}</span>'
            )
        running_chips = f'<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;">{chips}</div>'

    st.markdown(
        f'{CARD_OPEN}'
        f'{section_title(prog_title, NEON_BLUE)}'
        f'<div style="display:flex;align-items:center;gap:8px;">'
        f'<span style="display:inline-block;padding:3px 10px;border-radius:10px;'
        f'font-size:clamp(10px,1vw,12px);font-weight:600;{badge_style}'
        f';white-space:nowrap;">{phase_label}</span>'
        f'<div style="flex-grow:1;background:rgba(255,255,255,0.06);border-radius:8px;height:16px;overflow:hidden;">'
        f'<div style="height:100%;border-radius:8px;width:{prog_pct:.1f}'
        f'%;background:linear-gradient(90deg,{NEON_BLUE},{NEON_GREEN}'
        f');"></div></div><span style="color:{TEXT_SECONDARY}'
        f';font-size:clamp(11px,1.1vw,14px);white-space:nowrap;">'
        f'{prog_numerator}/{prog_denominator} · {prog_pct:.0f}%</span></div>'
        f'{progress_detail_html}'
        f'{running_chips}'
        f'{CARD_CLOSE}',
        unsafe_allow_html=True,
    )

    # ---- KPI SECTION ----
    running_d = (
        f'<div class="kpi-delta" style="color:{NEON_BLUE}">{n_running}개 진행 중</div>'
        if n_running > 0 else ""
    )
    error_d = (
        f'<div class="kpi-delta" style="color:{NEON_RED}">{n_error}개 오류</div>'
        if n_error > 0 else ""
    )

    st.markdown(
        f'{CARD_OPEN}'
        f'{section_title("핵심 지표", NEON_GREEN)}'
        f'<div style="display:flex;gap:8px;">'
        f'<div class="kpi-card" style="flex:1;min-width:0;">'
        f'<div class="kpi-value" style="color:{NEON_GREEN}">{state.total_articles:,}'
        f'</div><div class="kpi-label">수집된 기사</div></div>'
        f'<div class="kpi-card" style="flex:1;min-width:0;">'
        f'<div class="kpi-value" style="color:{NEON_BLUE}">{n_success}/{state.total_sites}'
        f'</div><div class="kpi-label">사이트 완료</div>'
        f'{running_d}'
        f'</div><div class="kpi-card" style="flex:1;min-width:0;">'
        f'<div class="kpi-value" style="color:{rate_color}">{success_rate:.0f}'
        f'%</div><div class="kpi-label">성공률</div>'
        f'{error_d}'
        f'</div><div class="kpi-card" style="flex:1;min-width:0;">'
        f'<div class="kpi-value" style="color:{mem_color}">{current_memory:.1f}'
        f' GB</div><div class="kpi-label">메모리</div></div>'
        f'<div class="kpi-card" style="flex:1;min-width:0;">'
        f'<div class="kpi-value" style="color:{NEON_CYAN}">{eta_str}'
        f'</div><div class="kpi-label">{eta_label}</div></div></div>'
        f'{CARD_CLOSE}',
        unsafe_allow_html=True,
    )

    # ---- PIPELINE STAGES ----
    st.markdown(
        f'{CARD_OPEN}'
        f'{section_title("분석 파이프라인", NEON_PURPLE)}'
        f'{stage_nodes_html}'
        f'{CARD_CLOSE}',
        unsafe_allow_html=True,
    )

    # ---- GROUP CHART ----
    st.markdown(
        f'{CARD_OPEN}{section_title("그룹별 기사 수", NEON_AMBER)}',
        unsafe_allow_html=True,
    )
    st.plotly_chart(
        build_group_chart(state.sites, state.active_site_ids or None),
        use_container_width=True,
        config={"displayModeBar": False},
    )
    st.markdown(CARD_CLOSE, unsafe_allow_html=True)

    # ---- COMPLETED SITES & ERRORS ----
    completed = sorted(
        [s for s in state.sites.values() if s.status == "success" and s.elapsed > 0],
        key=lambda x: x.timestamp or "",
        reverse=True,
    )[:5]

    errors_by_type = defaultdict(int)
    for s in state.sites.values():
        if s.status != "error":
            continue
        if not s.error_msg:
            continue
        msg = s.error_msg.lower()
        if "403" in msg or "forbidden" in msg:
            errors_by_type["403 차단"] += 1
        elif "timeout" in msg:
            errors_by_type["타임아웃"] += 1
        elif "cloudflare" in msg:
            errors_by_type["Cloudflare"] += 1
        elif "ssl" in msg or "certificate" in msg:
            errors_by_type["SSL 오류"] += 1
        elif "empty" in msg or "rss" in msg:
            errors_by_type["빈 피드"] += 1
        else:
            errors_by_type["기타"] += 1

    col_recent, col_errors = st.columns([1.2, 1])

    with col_recent:
        recent_rows = ""
        if completed:
            for s in completed:
                recent_rows += (
                    f'<div style="display:flex;align-items:center;gap:10px;padding:6px 0;'
                    f'border-bottom:1px solid rgba(255,255,255,0.04);'
                    f'font-size:clamp(13px,1.2vw,15px);">'
                    f'<span style="color:{NEON_GREEN};font-size:16px;">&#10003;</span>'
                    f'<span style="color:{TEXT_PRIMARY};font-weight:600;min-width:100px;">'
                    f'{s.site_id}</span>'
                    f'<span style="color:{NEON_GREEN};font-weight:700;">{s.articles}'
                    f'건</span><span style="color:{TEXT_MUTED}'
                    f';font-size:clamp(11px,1vw,13px);">({s.elapsed:.0f}초)</span></div>'
                )
        else:
            recent_rows = (
                f'<div style="color:{TEXT_MUTED};font-size:13px;padding:10px 0;">아직 완료된 사이트 없음</div>'
            )

        st.markdown(
            f'{CARD_OPEN}{section_title("최근 완료", NEON_GREEN)}{recent_rows}{CARD_CLOSE}',
            unsafe_allow_html=True,
        )

    with col_errors:
        error_rows = ""
        if errors_by_type:
            for err_type, count in sorted(errors_by_type.items(), key=lambda x: -x[1]):
                bar_w = min(count / max(errors_by_type.values()) * 100, 100)
                error_rows += (
                    f'<div style="margin-bottom:8px;"><div style="display:flex;justify-content:space-between;'
                    f'font-size:clamp(12px,1.1vw,14px);margin-bottom:3px;"><span style="color:'
                    f'{TEXT_PRIMARY};font-weight:500;">{err_type}</span><span style="color:'
                    f'{NEON_RED};font-weight:700;">{count}'
                    f'건</span></div><div style="background:rgba(255,255,255,0.06);border-radius:4px;'
                    f'height:6px;overflow:hidden;"><div style="width:{bar_w:.0f}'
                    f'%;height:100%;background:{NEON_RED}'
                    f';border-radius:4px;"></div></div></div>'
                )
        else:
            error_rows = (
                f'<div style="color:{NEON_GREEN}'
                f';font-size:clamp(13px,1.2vw,15px);padding:10px 0;font-weight:500;">'
                f'에러 없음 &#10003;</div>'
            )

        st.markdown(
            f'{CARD_OPEN}{section_title("에러 요약", NEON_RED)}{error_rows}{CARD_CLOSE}',
            unsafe_allow_html=True,
        )

    # ---- SITE TABLE ----
    st.markdown(
        f'{CARD_OPEN}{section_title("사이트별 상태", NEON_CYAN)}',
        unsafe_allow_html=True,
    )

    site_data = []
    # 실제 크롤링 대상만 표시 (active_site_ids가 있으면 필터, 없으면 비-pending만)
    if state.active_site_ids:
        visible_sites = [state.sites[sid] for sid in state.active_site_ids if sid in state.sites]
    else:
        visible_sites = [s for s in state.sites.values() if s.status != "pending"]
    for s in sorted(
        visible_sites,
        key=lambda x: ({"running": 0, "error": 1, "success": 2, "pending": 3}.get(x.status, 4), x.site_id),
    ):
        site_data.append({
            "상태": s.status,
            "사이트": s.site_id,
            "그룹": s.group,
            "기사 수": s.articles if s.articles > 0 else 0,
            "소요시간": f"{s.elapsed:.0f}초" if s.elapsed > 0 else "-",
            "오류": s.error_msg[:40] if s.error_msg else "-",
        })

    if site_data:
        df = pd.DataFrame(site_data)
        st.dataframe(
            df,
            width="stretch",
            height=400,
            column_config={
                "상태": st.column_config.TextColumn("상태", width="small"),
                "사이트": st.column_config.TextColumn("사이트", width="small"),
                "그룹": st.column_config.TextColumn("그룹", width="small"),
                "기사 수": st.column_config.NumberColumn("기사 수", width="small"),
                "소요시간": st.column_config.TextColumn("소요시간", width="small"),
                "오류": st.column_config.TextColumn("오류", width="medium"),
            },
        )

    st.markdown(CARD_CLOSE, unsafe_allow_html=True)

    # auto-refresh: @st.fragment(run_every=3) 가 처리함


if __name__ == "__main__":
    main()
