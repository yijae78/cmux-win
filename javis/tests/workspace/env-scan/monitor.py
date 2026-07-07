"""환경스캐닝 브리핑 대시보드.

디자인: 브라우저디자인샘플1.jpg, 2.jpg 기반.
읽기 전용. 기존 코드 수정 없음.

    streamlit run monitor.py
    python launch_monitor.py
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

# ── Paths ──
PROJECT = Path(__file__).resolve().parent
ENV = PROJECT / "env-scanning"
LOGS = ENV / "integrated" / "logs"
ANALYSIS = ENV / "integrated" / "analysis"
KST = timezone(timedelta(hours=9))

WF_ORDER = ["wf1-general", "wf2-arxiv", "wf3-naver", "wf4-multiglobal-news"]
WF_LABEL = {"wf1-general": "일반", "wf2-arxiv": "arXiv",
            "wf3-naver": "네이버", "wf4-multiglobal-news": "글로벌뉴스"}

FSSF_KO = {
    "Driver": "동인 (Driver)",
    "Trend": "추세 (Trend)",
    "Megatrend": "메가트렌드",
    "Weak Signal": "약한 신호",
    "Wild Card": "와일드 카드",
    "Discontinuity": "불연속성",
    "Emerging Issue": "부상 이슈",
    "Precursor Event": "전조 사건",
}

def _fssf_ko(data: dict[str, int]) -> dict[str, int]:
    """FSSF 키를 한글로 변환."""
    return {FSSF_KO.get(k, k): v for k, v in data.items()}

# ── Colors — 디자인 샘플: 블랙 + 시안 1색 ──
BG = "#0a0a0a"
C1 = "#00d4ff"
C2 = "#ffa726"
C_WF1 = "#00d4ff"   # 일반 — 시안
C_WF2 = "#b388ff"   # arXiv — 보라
C_WF3 = "#00e676"   # 네이버 — 그린
C_WF4 = "#ffa726"   # 글로벌뉴스 — 앰버
C_NEUTRAL = "#90a4ae"  # 소스 무관 차트용 (FSSF 전체, Three Horizons)
W = "#ffffff"
G1 = "rgba(255,255,255,0.55)"
G2 = "rgba(255,255,255,0.35)"
G3 = "rgba(255,255,255,0.20)"
TK = "rgba(255,255,255,0.06)"

# ── CSS — 디자인 샘플: 장식 없음, 여백 넉넉, 숫자 중심 ──
CSS = f"""<style>
.stApp{{background:{BG};color:{W};}}
.stApp>header,#MainMenu,footer,[data-testid="stHeader"],
[data-testid="stToolbar"],[data-testid="stDecoration"],
.stDeployButton,[data-testid="stStatusWidget"]{{display:none!important;}}
.block-container{{padding-top:0.5rem!important;max-width:660px;}}
[data-testid="stVerticalBlockBorderWrapper"]{{gap:0!important;}}
[data-testid="stVerticalBlock"]{{gap:0!important;}}
section[data-testid="stSidebar"]{{display:none!important;}}

.title{{font-size:clamp(20px,4vw,26px);font-weight:800;color:{W};letter-spacing:-.5px;}}
.date{{font-size:12px;color:{G2};margin:1px 0 8px 0;}}

.sec{{font-size:14px;font-weight:700;color:{W};margin:24px 0 10px 0;}}
.sec-box{{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:14px 16px;margin-bottom:8px;}}
.sub{{font-size:12px;font-weight:600;color:{G1};margin:10px 0 6px 0;}}

.sig-row{{padding:6px 0;border-bottom:1px solid {TK};}}
.sig-title{{font-size:12px;color:{G1};}}
.sig-cat{{font-size:10px;color:{G2};margin-top:1px;}}
.sig-bar-wrap{{margin-top:4px;height:5px;background:{TK};border-radius:3px;overflow:hidden;}}
.sig-bar{{height:100%;border-radius:3px;background:{C1};transition:width .5s;}}
.sig-score{{font-size:18px;font-weight:800;color:{W};float:right;margin-top:-28px;}}

.bar-row{{display:flex;align-items:center;gap:6px;margin:2px 0;}}
.bar-lbl{{width:110px;font-size:11px;color:{G1};text-align:right;flex-shrink:0;}}
.bar-tk{{flex:1;height:10px;background:{TK};border-radius:3px;overflow:hidden;}}
.bar-fl{{height:100%;border-radius:3px;transition:width .5s;}}
.bar-v{{width:34px;font-size:11px;color:{G2};text-align:right;flex-shrink:0;}}

.dual-tk{{flex:1;height:14px;background:{TK};border-radius:3px;overflow:hidden;position:relative;}}
.dual-a{{position:absolute;top:0;left:0;height:50%;border-radius:3px 3px 0 0;}}
.dual-b{{position:absolute;bottom:0;left:0;height:50%;border-radius:0 0 3px 3px;}}
.leg{{display:flex;gap:12px;justify-content:center;margin-top:4px;}}
.leg-i{{display:flex;align-items:center;gap:4px;font-size:10px;color:{G2};}}
.leg-d{{width:8px;height:8px;border-radius:2px;}}

.foot{{font-size:10px;color:{G3};margin-top:12px;padding-top:6px;border-top:1px solid {TK};}}
@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
@keyframes neon-pulse{{0%,100%{{filter:drop-shadow(0 0 8px #ff525250)}}50%{{filter:drop-shadow(0 0 24px #ff5252bb)}}}}
.neon-glow{{animation:neon-pulse 2.5s ease-in-out infinite;}}
@keyframes wave-rotate{{0%{{stroke-dashoffset:0}}100%{{stroke-dashoffset:-60}}}}
.wave-ring{{animation:wave-rotate 3s linear infinite;}}
</style>"""

CSS_ANIM = """
@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
@keyframes neon-pulse{0%,100%{filter:drop-shadow(0 0 8px #ff525250)}50%{filter:drop-shadow(0 0 24px #ff5252bb)}}
.neon-glow{animation:neon-pulse 2.5s ease-in-out infinite;}
@keyframes wave-rotate{0%{stroke-dashoffset:0}100%{stroke-dashoffset:-60}}
.wave-ring{animation:wave-rotate 3s linear infinite;}
@keyframes radar-sweep{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}
.radar-sweep{animation:radar-sweep 4s linear infinite;transform-origin:center;}
@keyframes ripple-out{
    0%{r:0;opacity:0.6;stroke-width:2;}
    100%{r:110;opacity:0;stroke-width:0.5;}
}
.ripple1{animation:ripple-out 4s ease-out infinite;}
.ripple2{animation:ripple-out 4s ease-out infinite 1.3s;}
.ripple3{animation:ripple-out 4s ease-out infinite 2.6s;}
"""

ZOOM = """<script>
(function(){const d=window.parent.document,r=d.documentElement;let s=1;
d.addEventListener('wheel',function(e){if(e.ctrlKey){e.preventDefault();
s+=e.deltaY<0?.05:-.05;s=Math.min(2,Math.max(.5,s));
r.style.zoom=s;}},{passive:false});})();
</script>"""

# ── Data ──
@dataclass
class State:
    date: str = ""
    mode: str = "idle"  # live | completed | idle
    status_raw: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    phase_started_at: datetime | None = None
    current_wf: str = ""  # 현재 처리 중인 WF 라벨
    current_phase: str = ""
    wf_done: int = 0
    wf_total: int = 5  # 4 WF + 통합
    total: int = 0
    wf_counts: dict[str, int] = field(default_factory=dict)
    wf_validation: dict[str, str] = field(default_factory=dict)
    top_signals: list[dict] = field(default_factory=list)
    fssf_total: dict[str, int] = field(default_factory=dict)
    fssf_wf3: dict[str, int] = field(default_factory=dict)
    fssf_wf4: dict[str, int] = field(default_factory=dict)
    horizons: dict[str, int] = field(default_factory=dict)
    cross_wf: list[dict] = field(default_factory=list)
    has_data: bool = False


def _j(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _estimate_total_seconds(s: State) -> tuple[int, str]:
    """Return estimated total runtime seconds and a phase label."""
    phase = s.current_phase or "수집/분석"

    # Base estimates by major stage. These are deterministic dashboard heuristics,
    # not prediction models, and are intentionally conservative.
    if phase == "통합":
        base = 95 * 60
    elif phase == "보고서":
        base = 85 * 60
    elif phase == "분석":
        base = 75 * 60
    else:
        base = 70 * 60

    # If all workflow collection/phase2 work is done and only integration remains,
    # keep the ETA visible with an integration-weighted budget.
    if s.wf_done >= 4 and phase == "통합":
        return max(base, 110 * 60), phase

    # Progress-based interpolation for earlier stages.
    if s.wf_total > 0:
        progress_ratio = max(0.0, min(1.0, s.wf_done / s.wf_total))
        base = int(base + progress_ratio * 20 * 60)

    return base, phase


def _timing_display_state(s: State) -> tuple[bool, int, int, str]:
    """Return whether ETA should be shown, plus elapsed/remain seconds and phase."""
    if not s.started_at or not s.has_data:
        return False, 0, 0, ""

    est_total, phase = _estimate_total_seconds(s)
    anchor = s.phase_started_at or s.started_at
    elapsed_sec = max(0, int((datetime.now(timezone.utc) - anchor).total_seconds()))

    # Show ETA not only for live crawling, but also for integration_pending/reporting.
    show_eta = s.mode == "live" or (s.status_raw in {"integration_pending", "reporting_pending", "phase3_pending"})
    if show_eta and s.status_raw in {"integration_pending", "reporting_pending", "phase3_pending"}:
        # Keep ETA decreasing during active pending work.
        # When a stage exceeds its heuristic budget, extend it in 20-minute blocks
        # so the countdown continues to tick down instead of sticking at a flat value.
        if elapsed_sec >= est_total:
            overrun = elapsed_sec - est_total
            extension_blocks = (overrun // (20 * 60)) + 1
            est_total += extension_blocks * 20 * 60
    remain_sec = max(0, est_total - elapsed_sec)
    return show_eta, elapsed_sec, remain_sec, phase


def _load() -> State:
    s = State()
    today = datetime.now(KST).strftime("%Y-%m-%d")
    data_date = today
    master_path: Path | None = None

    m = _j(LOGS / f"master-status-{today}.json")
    if m:
        master_path = LOGS / f"master-status-{today}.json"
    if not m:
        m = _j(LOGS / "master-status.json")
        if m:
            master_path = LOGS / "master-status.json"
            master_id = m.get("master_id", "")
            if master_id.startswith("quadruple-scan-"):
                data_date = master_id.replace("quadruple-scan-", "")
    if not m:
        ff = sorted(
            LOGS.glob("master-status-????-??-??.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if ff:
            m = _j(ff[0])
            master_path = ff[0]
            data_date = ff[0].stem.replace("master-status-", "")
    if not m:
        return s

    s.date = data_date
    s.has_data = True

    # Mode detection
    s.started_at = None
    sa = m.get("started_at", "")
    if sa:
        try:
            s.started_at = datetime.fromisoformat(sa.replace("Z", "+00:00"))
        except Exception:
            pass
    ca = m.get("completed_at", "")
    if ca:
        try:
            s.completed_at = datetime.fromisoformat(ca.replace("Z", "+00:00"))
        except Exception:
            pass

    ms = m.get("status", "pending")
    s.status_raw = ms
    wf_statuses = [
        (m.get("workflow_results", {}).get(wf_id, {}) or {}).get("status", "pending")
        for wf_id in WF_ORDER
    ]
    integration_status = (m.get("integration_result", {}) or {}).get("status", "pending")
    incomplete_statuses = {"pending", "running", "failed", "live", "paused"}
    has_incomplete_work = any(status in incomplete_statuses for status in wf_statuses)
    has_incomplete_work = has_incomplete_work or integration_status in incomplete_statuses

    recently_updated = False
    if master_path and master_path.exists():
        age = time.time() - master_path.stat().st_mtime
        recently_updated = age < 6 * 3600

    if ms == "completed":
        s.mode = "completed"
    elif has_incomplete_work and recently_updated:
        s.mode = "live"
    else:
        s.mode = "idle"

    # WF counts + progress
    done_count = 0
    current_found = False
    wf_completed_times: list[datetime] = []
    for wf_id in WF_ORDER:
        wr = m.get("workflow_results", {}).get(wf_id, {})
        s.wf_counts[wf_id] = wr.get("signal_count", 0)
        s.wf_validation[wf_id] = wr.get("validation", "")
        if wr.get("status") == "completed":
            done_count += 1
            c_at = wr.get("completed_at", "")
            if c_at:
                try:
                    wf_completed_times.append(datetime.fromisoformat(c_at.replace("Z", "+00:00")))
                except Exception:
                    pass
        elif not current_found:
            s.current_wf = WF_LABEL.get(wf_id, wf_id)
            current_found = True

    ir = m.get("integration_result", {})
    if ir.get("status") == "completed":
        done_count += 1
    elif not current_found:
        s.current_wf = "통합"
    s.wf_done = done_count

    if ir.get("status") in {"pending", "running", "failed", "live", "paused"} and done_count >= 4:
        s.current_phase = "통합"
        if not s.current_wf:
            s.current_wf = "통합"
        if wf_completed_times:
            s.phase_started_at = max(wf_completed_times)
    elif any((m.get("workflow_results", {}).get(wf_id, {}) or {}).get("status") in {"pending", "running"} for wf_id in WF_ORDER):
        s.current_phase = "수집/분석"
        s.phase_started_at = s.started_at
    elif ms in {"integration_pending", "reporting_pending", "phase3_pending"}:
        s.current_phase = "통합"
        if wf_completed_times:
            s.phase_started_at = max(wf_completed_times)
    else:
        s.current_phase = "보고서"
        s.phase_started_at = s.started_at

    # Integration may still be pending while per-workflow counts are already populated.
    # In that case, prefer the sum of workflow counts over a placeholder 0.
    ir_total = ir.get("total_signals")
    wf_total_count = sum(s.wf_counts.values())
    if isinstance(ir_total, int) and ir_total > 0:
        s.total = ir_total
    else:
        s.total = wf_total_count

    # dashboard-data
    dd = _j(ANALYSIS / f"dashboard-data-{data_date}.json")
    if not dd:
        return s

    # Top signals — 각 WF에서 1개씩 먼저 뽑고 나머지 채움
    per_wf: dict[str, list[dict]] = {}
    for wf_id, sigs in dd.get("top_signals", {}).items():
        for sig in sigs:
            sig["_wf"] = WF_LABEL.get(wf_id, wf_id)
        per_wf[wf_id] = sigs

    picked: list[dict] = []
    seen_ids: set = set()
    # 1라운드: 각 WF에서 1위 1개씩
    for wf_id in WF_ORDER:
        sigs = per_wf.get(wf_id, [])
        if sigs:
            picked.append(sigs[0])
            seen_ids.add(sigs[0].get("id", id(sigs[0])))
    # 2라운드: 나머지에서 pSST 순으로 채움
    rest = []
    for sigs in per_wf.values():
        for sig in sigs:
            sid = sig.get("id", id(sig))
            if sid not in seen_ids:
                rest.append(sig)
                seen_ids.add(sid)
    rest.sort(key=lambda x: -(x.get("psst_score", 0) or 0))
    picked.extend(rest)
    s.top_signals = picked[:5]

    # FSSF
    fssf = dd.get("fssf", {})
    s.fssf_total = fssf.get("total", {})
    pw = fssf.get("per_workflow", {})
    s.fssf_wf3 = pw.get("wf3-naver", {})
    s.fssf_wf4 = pw.get("wf4-multiglobal-news", {})

    # 시간 지평 (Three Horizons) — from classified signals
    for wf_id in ["wf3-naver", "wf4-multiglobal-news"]:
        p = ENV / wf_id / "structured" / f"classified-signals-{today}.json"
        d2 = _j(p)
        if d2:
            for item in d2.get("signals", d2.get("items", [])):
                th = item.get("three_horizons", "")
                if th:
                    s.horizons[th] = s.horizons.get(th, 0) + 1

    # Cross-WF
    s.cross_wf = dd.get("cross_wf", {}).get("reinforcements", [])

    return s


# ── Renderers ──
def _donut(center: str, label: str, pct: float, size: int = 180,
           stroke: int = 12, color: str = C1,
           segs: list[tuple[str, str]] | None = None,
           wave: bool = False) -> str:
    r = (size - stroke) / 2
    cx = cy = size / 2
    circ = 2 * math.pi * r
    p = max(0, min(100, pct))
    arc = circ * p / 100
    gap = circ - arc
    fv = int(size * 0.27)
    fl = int(size * 0.08)

    seg_html = ""
    if segs:
        positions = [
            f"top:12px;left:0;text-align:left;",
            f"top:12px;right:0;text-align:right;",
            f"bottom:0;left:50%;transform:translateX(-50%);text-align:center;",
        ]
        for i, (txt, _) in enumerate(segs):
            if i < len(positions):
                seg_html += f'<span style="position:absolute;{positions[i]}font-size:13px;font-weight:600;color:{W};opacity:0.75;">{txt}</span>'

    # D안: 레이더 스캔 + 방사형 파동
    wave_html = ""
    if wave:
        # 방사형 파동 (소나 펄스 3겹)
        wave_html = f"""
        <circle cx="{cx}" cy="{cy}" r="0" fill="none" stroke="{color}" class="ripple1"/>
        <circle cx="{cx}" cy="{cy}" r="0" fill="none" stroke="{color}" class="ripple2"/>
        <circle cx="{cx}" cy="{cy}" r="0" fill="none" stroke="{color}" class="ripple3"/>"""

        # 레이더 스윕 (부채꼴 빛이 회전)
        wave_html += f"""
        <g class="radar-sweep">
            <defs>
                <linearGradient id="sweepGrad" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stop-color="{color}" stop-opacity="0.5"/>
                    <stop offset="100%" stop-color="{color}" stop-opacity="0"/>
                </linearGradient>
            </defs>
            <path d="M{cx},{cy} L{cx},{cy-r-4} A{r+4},{r+4} 0 0,1 {cx + (r+4)*0.5},{cy - (r+4)*0.866}"
                  fill="url(#sweepGrad)" opacity="0.4"/>
        </g>"""

        # 외곽 점선 링 (천천히 역회전)
        wave_html += f"""
        <circle cx="{cx}" cy="{cy}" r="{r + stroke}" fill="none"
            stroke="{color}" stroke-width="1" opacity="0.2"
            stroke-dasharray="6 10" class="wave-ring"/>"""

    margin = 30 if wave else 8
    vb = size + margin * 2

    return f"""<div style="position:relative;width:{size+90}px;margin:0 auto;padding:4px 0;">
    {seg_html}
    <svg width="{vb}" height="{vb}" style="display:block;margin:0 auto;filter:drop-shadow(0 0 12px {color}30);"
         viewBox="{-margin} {-margin} {vb} {vb}">
        {wave_html}
        <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{TK}" stroke-width="{stroke}"/>
        <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="{stroke}"
            stroke-dasharray="{arc:.1f} {gap:.1f}" stroke-linecap="round"
            transform="rotate(-90 {cx} {cy})"
            style="filter:drop-shadow(0 0 6px {color});"/>
        <text x="{cx}" y="{cy-4}" text-anchor="middle" dominant-baseline="middle"
            fill="{W}" font-size="{fv}px" font-weight="800" font-family="system-ui,sans-serif">{center}</text>
        <text x="{cx}" y="{cy+fv*.55}" text-anchor="middle"
            fill="{G1}" font-size="{fl}px" font-family="system-ui,sans-serif">{label}</text>
    </svg></div>"""


WF_COLOR = {"일반": C_WF1, "arXiv": C_WF2, "네이버": C_WF3, "글로벌뉴스": C_WF4}

def _signal_bars(signals: list[dict]) -> str:
    if not signals:
        return ""
    mx = max((s.get("psst_score", 0) or 1) for s in signals)
    h = ""
    for sig in signals:
        title = sig.get("title_ko") or sig.get("title", "")
        if len(title) > 60:
            title = title[:58] + "…"
        fssf = sig.get("fssf_type", "")
        fssf_ko = FSSF_KO.get(fssf, fssf) if fssf else ""
        wf = sig.get("_wf", "")
        bar_color = WF_COLOR.get(wf, C1)
        cat_parts = [x for x in [fssf_ko, wf] if x]
        cat = " · ".join(cat_parts) if cat_parts else ""
        score = sig.get("psst_score", 0) or 0
        w = score / mx * 100 if mx else 0
        h += f"""<div class="sig-row">
            <div class="sig-title">{title}</div>
            <div class="sig-cat"><span style="display:inline-block;width:8px;height:8px;
                border-radius:50%;background:{bar_color};margin-right:5px;"></span>{cat}</div>
            <div class="sig-bar-wrap"><div class="sig-bar" style="width:{w:.1f}%;background:{bar_color};"></div></div>
            <div class="sig-score">{score:.1f}</div>
        </div>"""
    return h


def _bars(data: dict[str, int], color: str = C1) -> str:
    if not data:
        return ""
    mx = max(data.values(), default=1)
    h = ""
    for k, v in sorted(data.items(), key=lambda x: -x[1]):
        w = v / mx * 100
        h += f"""<div class="bar-row">
            <span class="bar-lbl">{k}</span>
            <div class="bar-tk"><div class="bar-fl" style="width:{w:.1f}%;background:{color};"></div></div>
            <span class="bar-v">{v}</span>
        </div>"""
    return h


def _dual_bars(da: dict[str, int], db: dict[str, int],
               la: str = "네이버", lb: str = "글로벌뉴스",
               ca: str = C_WF3, cb: str = C_WF4) -> str:
    if not da and not db:
        return ""
    keys = sorted(set(list(da.keys()) + list(db.keys())),
                  key=lambda k: -(da.get(k, 0) + db.get(k, 0)))
    mx = max(max(da.values(), default=1), max(db.values(), default=1), 1)
    h = ""
    for k in keys:
        va, vb = da.get(k, 0), db.get(k, 0)
        wa, wb = va / mx * 100, vb / mx * 100
        h += f"""<div class="bar-row">
            <span class="bar-lbl">{k}</span>
            <div class="dual-tk">
                <div class="dual-a" style="width:{wa:.1f}%;background:{ca};"></div>
                <div class="dual-b" style="width:{wb:.1f}%;background:{cb};"></div>
            </div>
            <span class="bar-v">{va} / {vb}</span>
        </div>"""
    h += f"""<div class="leg">
        <div class="leg-i"><div class="leg-d" style="background:{ca};"></div>{la}</div>
        <div class="leg-i"><div class="leg-d" style="background:{cb};"></div>{lb}</div>
    </div>"""
    return h


# ── Main ──
def main() -> None:
    st.set_page_config(page_title="환경스캐닝 브리핑", page_icon="🔬",
                       layout="centered", initial_sidebar_state="collapsed")
    st.markdown(CSS, unsafe_allow_html=True)
    components.html(ZOOM, height=0)

    s = _load()

    # Header
    if s.date:
        dp = s.date.split("-")
        dd = f"{dp[0]}년 {dp[1]}월 {dp[2]}일" if len(dp) == 3 else s.date
    else:
        dd = datetime.now(KST).strftime("%Y년 %m월 %d일")
    st.markdown(f'<div class="title">환경스캐닝 브리핑</div><div class="date">{dd}</div>',
                unsafe_allow_html=True)

    # ── 시간 정보 + 실시간 상태 ──
    now_kst = datetime.now(KST)
    now_str = now_kst.strftime("%H:%M:%S")
    start_str = s.started_at.astimezone(KST).strftime("%H:%M:%S") if s.started_at else "—"

    TS = f"font-family:'JetBrains Mono','Fira Code',monospace;font-size:13px;"
    LBL = f"font-size:11px;color:{G3};"

    show_eta, elapsed_sec, remain_sec, phase = _timing_display_state(s)
    if show_eta:
        em, es = divmod(elapsed_sec, 60)
        eh, em = divmod(em, 60)
        rm, rs = divmod(remain_sec, 60)
        rh, rm = divmod(rm, 60)
        cur = s.current_wf if s.current_wf else "처리 중"

        st.markdown(f'''<div style="display:flex;justify-content:space-between;padding:4px 0 6px 0;
            border-bottom:1px solid {TK};margin-bottom:6px;">
            <div style="text-align:center;flex:1;">
                <div style="{LBL}">현재 시간</div>
                <div style="{TS}color:{W};">{now_str}</div>
            </div>
            <div style="text-align:center;flex:1;">
                <div style="{LBL}">시작 시간</div>
                <div style="{TS}color:{C1};">{start_str}</div>
            </div>
            <div style="text-align:center;flex:1;">
                <div style="{LBL}">남은 시간</div>
                <div style="{TS}color:{C2};">~{rh:02d}:{rm:02d}:{rs:02d}</div>
            </div>
            <div style="text-align:center;flex:1;">
                <div style="{LBL}">경과 시간</div>
                <div style="{TS}color:{G1};">{eh:02d}:{em:02d}:{es:02d}</div>
            </div>
        </div>
        <div style="font-size:13px;color:{G2};margin-bottom:6px;">
            <span style="display:inline-block;width:6px;height:6px;border-radius:50%;
            background:{C1};margin-right:6px;animation:blink 1.4s ease-in-out infinite;"></span>
            {cur} 처리 중 · {phase} 단계 · {s.wf_done}/{s.wf_total} 완료
        </div>''', unsafe_allow_html=True)

    elif s.mode == "completed":
        dur = ""
        if s.started_at and s.completed_at:
            d = s.completed_at - s.started_at
            dm, ds = divmod(int(d.total_seconds()), 60)
            dh, dm = divmod(dm, 60)
            dur = f"{dh:02d}:{dm:02d}:{ds:02d}"
        end_str = s.completed_at.astimezone(KST).strftime("%H:%M:%S") if s.completed_at else "—"

        st.markdown(f'''<div style="display:flex;justify-content:space-between;padding:4px 0 6px 0;
            border-bottom:1px solid {TK};margin-bottom:6px;">
            <div style="text-align:center;flex:1;">
                <div style="{LBL}">현재 시간</div>
                <div style="{TS}color:{W};">{now_str}</div>
            </div>
            <div style="text-align:center;flex:1;">
                <div style="{LBL}">시작 시간</div>
                <div style="{TS}color:{C1};">{start_str}</div>
            </div>
            <div style="text-align:center;flex:1;">
                <div style="{LBL}">남은 시간</div>
                <div style="{TS}color:#00e676;">00:00:00</div>
            </div>
            <div style="text-align:center;flex:1;">
                <div style="{LBL}">소요 시간</div>
                <div style="{TS}color:{G1};">{dur}</div>
            </div>
        </div>
        <div style="font-size:13px;color:{G2};margin-bottom:6px;">
            <span style="display:inline-block;width:6px;height:6px;border-radius:50%;
            background:#00e676;margin-right:6px;"></span>
            스캔 완료 · {s.wf_done}/{s.wf_total} · 완료 {end_str}
        </div>''', unsafe_allow_html=True)

    elif s.has_data:
        st.markdown(f'''<div style="display:flex;justify-content:space-between;padding:4px 0 6px 0;
            border-bottom:1px solid {TK};margin-bottom:6px;">
            <div style="text-align:center;flex:1;">
                <div style="{LBL}">현재 시간</div>
                <div style="{TS}color:{W};">{now_str}</div>
            </div>
            <div style="text-align:center;flex:1;">
                <div style="{LBL}">마지막 스캔</div>
                <div style="{TS}color:{G2};">{s.date}</div>
            </div>
            <div style="text-align:center;flex:1;">
                <div style="{LBL}">상태</div>
                <div style="{TS}color:{G3};">대기 중</div>
            </div>
        </div>''', unsafe_allow_html=True)

    if not s.has_data:
        st.markdown(f'<div style="color:{G2};font-size:14px;margin-top:40px;text-align:center;">'
                    f'스캔 데이터가 없습니다</div>', unsafe_allow_html=True)
        time.sleep(30)
        st.rerun()
        return

    # ── 탐지 신호 현황 (샘플: 참가기업 만족도) ──
    st.markdown('<div class="sec">탐지 신호 현황</div>', unsafe_allow_html=True)

    wf1 = s.wf_counts.get("wf1-general", 0)
    wf2 = s.wf_counts.get("wf2-arxiv", 0)
    wf3 = s.wf_counts.get("wf3-naver", 0)
    wf4 = s.wf_counts.get("wf4-multiglobal-news", 0)
    t = s.total or 1

    C_RED = "#ff5252"
    donut_html = _donut(str(s.total), "탐지 신호", 100, size=170, color=C_RED, wave=True)
    donut_html = donut_html.replace("<svg ", '<svg class="neon-glow" ', 1)
    seg_line = (f'<div style="display:flex;justify-content:center;gap:16px;margin-top:6px;'
                f'font-size:13px;font-weight:700;font-family:system-ui,sans-serif;">'
                f'<span style="color:{C_WF1};">일반 {wf1/t*100:.0f}%</span>'
                f'<span style="color:{C_WF2};">arXiv {wf2/t*100:.0f}%</span>'
                f'<span style="color:{C_WF3};">네이버 {wf3/t*100:.0f}%</span>'
                f'<span style="color:{C_WF4};">글로벌 {wf4/t*100:.0f}%</span>'
                f'</div>')
    components.html(f'<div style="background:{BG};text-align:center;padding-bottom:4px;">'
                    f'<style>{CSS_ANIM}</style>{donut_html}{seg_line}</div>', height=250)

    # ── 주요 탐지 신호 ──
    if s.top_signals:
        st.markdown('<div class="sec">주요 탐지 신호</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sec-box">{_signal_bars(s.top_signals)}</div>',
                    unsafe_allow_html=True)

    # ── 소스별 수집 현황 ──
    st.markdown('<div class="sec">소스별 수집 현황</div>', unsafe_allow_html=True)
    src_data = [
        ("arXiv", wf2, C_WF2),
        ("일반", wf1, C_WF1),
        ("네이버", wf3, C_WF3),
        ("글로벌뉴스", wf4, C_WF4),
    ]
    src_max = max(wf1, wf2, wf3, wf4, 1)
    src_html = ""
    for name, cnt, clr in sorted(src_data, key=lambda x: -x[1]):
        w = cnt / src_max * 100
        src_html += f'''<div class="bar-row">
            <span class="bar-lbl" style="color:{clr};font-weight:600;">{name}</span>
            <div class="bar-tk"><div class="bar-fl" style="width:{w:.1f}%;background:{clr};"></div></div>
            <span class="bar-v" style="color:{clr};font-weight:700;">{cnt}</span>
        </div>'''
    st.markdown(f'<div class="sec-box">{src_html}</div>', unsafe_allow_html=True)

    # ── 미래신호 유형 분포 (FSSF) ──
    if s.fssf_total:
        st.markdown('<div class="sec">미래신호 유형 분포 (FSSF)</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sec-box">{_bars(_fssf_ko(s.fssf_total), C_NEUTRAL)}</div>',
                    unsafe_allow_html=True)

    # ── 미래신호 뉴스 비교 (FSSF) ──
    if s.fssf_wf3 or s.fssf_wf4:
        st.markdown('<div class="sec">미래신호 뉴스 비교 (FSSF)</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sec-box">{_dual_bars(_fssf_ko(s.fssf_wf3), _fssf_ko(s.fssf_wf4))}</div>',
                    unsafe_allow_html=True)

    # ── 시간 지평 (Three Horizons) ──
    if s.horizons:
        st.markdown('<div class="sec">시간 지평 (Three Horizons)</div>', unsafe_allow_html=True)
        labeled = {}
        for k, v in s.horizons.items():
            if k == "H1":
                labeled["H1 (0-2년)"] = v
            elif k == "H2":
                labeled["H2 (2-7년)"] = v
            elif k == "H3":
                labeled["H3 (7년+)"] = v
            else:
                labeled[k] = v
        st.markdown(f'<div class="sec-box">{_bars(labeled, C_NEUTRAL)}</div>',
                    unsafe_allow_html=True)

    # ── Footer ──
    st.markdown(f'<div class="foot">환경스캐닝 시스템 · {s.date} · '
                f'총 {s.total}개 신호 탐지</div>', unsafe_allow_html=True)

    # Auto-refresh — 모드별 차등
    if s.mode == "live":
        time.sleep(5)
        st.rerun()
    elif s.mode == "idle":
        time.sleep(30)
        st.rerun()
    # completed: 자동 갱신 안 함


if __name__ == "__main__":
    main()
