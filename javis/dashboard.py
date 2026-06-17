# -*- coding: utf-8 -*-
"""Javis Fleet Dashboard v2 — 신교수님 통합 디자인 시스템 적용

글래스모피즘 + 브랜드 축A(블루-시안) + KPI 카드 + Usage 트래킹
Anti-flicker: components.html() 단일 iframe 렌더링

    streamlit run dashboard.py --server.port 8500 --server.headless true
"""
from __future__ import annotations

import html as _html
import http.client
import json
import logging
import math
import re
import socket as _socket
import ssl
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

# ━━━━━━━ Logging ━━━━━━━
logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
_log = logging.getLogger("javis-dashboard")

# ━━━━━━━ Thread-safe lock ━━━━━━━
_cache_lock = threading.Lock()

# ━━━━━━━ Typed Data Contracts ━━━━━━━
@dataclass
class PaneData:
    surface: dict[str, Any]
    config: dict[str, str]
    content: str
    status: str           # live | done | idle | error | offline
    activity: str
    preview: list[str]
    ctx_warn: str | None  # critical | warning | None


@dataclass
class UsageData:
    hourly_in: int = 0
    hourly_out: int = 0
    daily_in: int = 0
    daily_out: int = 0
    monthly_total: int = 0
    sessions: int = 0
    messages: int = 0
    sparkline: list[int] = field(default_factory=list)


@dataclass
class RateLimitData:
    session_pct: float = 0
    session_reset: str = ""
    session_status: str = "unknown"
    weekly_pct: float = 0
    weekly_reset: str = ""
    weekly_status: str = "unknown"


@dataclass
class SystemMetrics:
    cpu: float = 0
    mem_pct: float = 0
    mem_used: float = 0
    mem_total: float = 0


# ━━━━━━━ Config ━━━━━━━
SOCKET_TOKEN_FILE = Path.home() / "AppData" / "Roaming" / "cmux-win" / "socket-token"
REFRESH_SEC = 5
RATE_LIMIT_CACHE_SEC = 15  # Rate limit API 호출 캐시 (15초마다 갱신)

# ━━━━━━━ Design Tokens (신교수님 디자인 시스템) ━━━━━━━
BG_VOID = "#0a0a0a"
BG_PRIMARY = "#0c111b"
BG_RAISED = "#111827"
SURFACE_1 = "rgba(255,255,255,0.04)"
SURFACE_2 = "rgba(255,255,255,0.06)"
SURFACE_3 = "rgba(255,255,255,0.09)"
BORDER = "rgba(255,255,255,0.08)"
BORDER_HEAVY = "rgba(255,255,255,0.12)"

TEXT_PRIMARY = "#f1f5f9"
TEXT_SECONDARY = "#94a3b8"
TEXT_MUTED = "#64748b"

# Semantic
GREEN = "#22c55e"
BLUE = "#3b82f6"
AMBER = "#f59e0b"
RED = "#ef4444"
CYAN = "#00d4ff"

# Brand Accent A (tech/monitoring)
ACCENT = "#00A8FF"
ACCENT_LIGHT = "#00d4ff"
ACCENT_DIM = "#38bdf8"

# Agent colors
C_MASTER = "#3b82f6"
C_CSO = "#8b5cf6"
C_AGY = "#00e676"
C_AGY2 = "#ffa726"
C_CODEX = "#00d4ff"

FLEET = [
    {"key": "마스터(claude)", "icon": "M", "color": C_MASTER, "ai": "Claude", "desc": "총지휘"},
    {"key": "CSO(claude)", "icon": "C", "color": C_CSO, "ai": "Claude", "desc": "시스템 운영"},
    {"key": "Worker1(claude)", "icon": "A", "color": C_AGY, "ai": "Claude", "desc": "작업 수행"},
    {"key": "Worker2(AGY)", "icon": "G", "color": C_AGY2, "ai": "AGY", "desc": "리뷰"},
    {"key": "Worker3(Codex)", "icon": "X", "color": C_CODEX, "ai": "Codex", "desc": "검수"},
    {"key": "Worker4(Claude)", "icon": "4", "color": "#ec4899", "ai": "Claude", "desc": "병렬 작업"},
    {"key": "Worker5(AGY)", "icon": "5", "color": "#a78bfa", "ai": "AGY", "desc": "교차 리뷰"},
]

# ━━━━━━━ Page config ━━━━━━━
st.set_page_config(page_title="Javis Fleet", page_icon="J",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown("""<style>
.stApp>header,#MainMenu,footer,[data-testid="stHeader"],
[data-testid="stToolbar"],[data-testid="stDecoration"],
.stDeployButton,[data-testid="stStatusWidget"]{display:none!important;}
section[data-testid="stSidebar"]{display:none!important;}
.block-container{padding-top:0!important;padding-bottom:0!important;max-width:100%!important;}
[data-testid="stVerticalBlockBorderWrapper"]{gap:0!important;}
[data-testid="stVerticalBlock"]{gap:0!important;}
.stApp{background:#0a0a0a;}
</style>""", unsafe_allow_html=True)


# ━━━━━━━ Socket API ━━━━━━━
def _read_socket_config() -> tuple[str, int]:
    """socket-token 파일에서 토큰(line1)과 포트(line2)를 동적으로 읽는다."""
    try:
        lines = SOCKET_TOKEN_FILE.read_text().strip().split("\n")
        token = lines[0].strip() if lines else ""
        port = int(lines[1].strip()) if len(lines) > 1 else 19840
        return token, port
    except (FileNotFoundError, OSError, IndexError, ValueError) as e:
        _log.debug("Socket config read failed: %s", e)
        return "", 19840


def _get_token() -> str:
    return _read_socket_config()[0]


def _get_port() -> int:
    return _read_socket_config()[1]


def _recv_line(s):
    buf = b""
    while True:
        chunk = s.recv(65536)
        if not chunk:
            return {}
        buf += chunk
        idx = buf.find(b"\n")
        if idx >= 0:
            return json.loads(buf[:idx].decode("utf-8"))


_fleet_data_cache: dict[str, Any] = {"ts": 0, "data": ([], [])}
_FLEET_CACHE_SEC = 2  # 2초 캐시 — JS fetch 5초보다 짧게


def gather_fleet_data():
    now = time.time()
    with _cache_lock:
        if _fleet_data_cache["data"][0] and now - _fleet_data_cache["ts"] < _FLEET_CACHE_SEC:
            return _fleet_data_cache["data"]

    token = _get_token()
    if not token:
        return [], []
    s = None
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        s.settimeout(8)
        s.connect(("127.0.0.1", _get_port()))
        s.sendall((json.dumps({"jsonrpc": "2.0", "id": 0, "method": "auth.handshake",
                                "params": {"token": token}}) + "\n").encode())
        _recv_line(s)
        s.sendall((json.dumps({"jsonrpc": "2.0", "id": 1, "method": "surface.list",
                                "params": {}}) + "\n").encode())
        resp = _recv_line(s)
        surfaces = resp.get("result", {}).get("surfaces", [])
        terminals = [sf for sf in surfaces if sf.get("surfaceType") == "terminal"]
        contents = []
        for i, sf in enumerate(terminals):
            sid = sf.get("id", "")
            if not sid:
                contents.append("")
                continue
            s.sendall((json.dumps({"jsonrpc": "2.0", "id": i + 10,
                                    "method": "surface.read",
                                    "params": {"surfaceId": sid, "lines": 20}
                                    }) + "\n").encode())
            r = _recv_line(s)
            contents.append(r.get("result", {}).get("content", ""))
        result = (terminals, contents)
        with _cache_lock:
            _fleet_data_cache["ts"] = now
            _fleet_data_cache["data"] = result
        return result
    except (OSError, ConnectionError, _socket.error, _socket.timeout,
            json.JSONDecodeError, ValueError) as e:
        _log.warning("Fleet data gather failed: %s", e)
        return _fleet_data_cache.get("data", ([], []))
    finally:
        if s:
            try:
                s.close()
            except OSError:
                pass


# ━━━━━━━ Rate Limit API (실제 한도 조회) ━━━━━━━
_rate_limit_cache: dict[str, Any] = {"ts": 0, "data": None}


def get_rate_limits() -> RateLimitData:
    """Anthropic API 최소 호출로 실제 rate limit 헤더 추출 (캐시 15초)."""
    now = time.time()
    with _cache_lock:
        if _rate_limit_cache["data"] and now - _rate_limit_cache["ts"] < RATE_LIMIT_CACHE_SEC:
            return _rate_limit_cache["data"]

    default = RateLimitData()
    try:
        cred_path = Path.home() / ".claude" / ".credentials.json"
        if not cred_path.exists():
            return default
        cred = json.loads(cred_path.read_text())
        token = cred.get("claudeAiOauth", {}).get("accessToken", "")
        if not token:
            return default

        body = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "h"}],
        })
        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection("api.anthropic.com", context=ctx, timeout=8)
        try:
            conn.request("POST", "/v1/messages", body, {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
                "User-Agent": "claude-code/2.1.94",
            })
            resp = conn.getresponse()
            resp.read()  # drain body

            headers = {k.lower(): v for k, v in resp.getheaders()}

            # 5h session
            s5_util = float(headers.get("anthropic-ratelimit-unified-5h-utilization", 0))
            s5_reset_ts = int(headers.get("anthropic-ratelimit-unified-5h-reset", 0))
            s5_status = headers.get("anthropic-ratelimit-unified-5h-status", "unknown")
            s5_reset = datetime.fromtimestamp(s5_reset_ts).strftime("%H:%M") if s5_reset_ts else ""

            # 7d weekly
            w7_util = float(headers.get("anthropic-ratelimit-unified-7d-utilization", 0))
            w7_reset_ts = int(headers.get("anthropic-ratelimit-unified-7d-reset", 0))
            w7_status = headers.get("anthropic-ratelimit-unified-7d-status", "unknown")
            w7_reset = datetime.fromtimestamp(w7_reset_ts).strftime("%m/%d %H:%M") if w7_reset_ts else ""
        finally:
            conn.close()

        result = RateLimitData(
            session_pct=round(s5_util * 100, 1),
            session_reset=s5_reset,
            session_status=s5_status,
            weekly_pct=round(w7_util * 100, 1),
            weekly_reset=w7_reset,
            weekly_status=w7_status,
        )
        _rate_limit_cache["ts"] = now
        _rate_limit_cache["data"] = result
        return result
    except (OSError, ssl.SSLError, http.client.HTTPException,
            json.JSONDecodeError, ValueError, KeyError) as e:
        _log.warning("Rate limit API failed: %s", e)
        return _rate_limit_cache.get("data") or default


# ━━━━━━━ Data processing ━━━━━━━
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\r")


def _strip(text):
    return _ANSI_RE.sub("", text)


def detect_status(content):
    if not content:
        return "offline"
    last = _strip("\n".join(content.strip().split("\n")[-8:])).lower()
    # 에러 감지 (최우선)
    error_kws = ["traceback", "exception", "crash", "fatal error", "panic",
                 "error:", "errno", "segfault", "killed"]
    noise_kws = ["mcp server failed", "mcp server", "settings issue", "/doctor", "/mcp",
                 "error handling", "error_handler", "errorcount"]
    has_error = any(k in last for k in error_kws)
    is_noise = any(k in last for k in noise_kws)
    if has_error and not is_noise:
        return "error"
    # 작업 중 감지 (idle보다 먼저 — thinking + bypass permissions 동시 존재 시 live 우선)
    if any(k in last for k in ["working", "running", "processing", "generating", "searching",
                                "reading file", "writing file", "editing", "creating", "analyzing",
                                "building", "fetching", "compiling", "levitating",
                                "thinking", "tool call", "spinning", "moonwalking",
                                "deciphering", "contemplating", "pondering",
                                "pontificating", "cogitating", "ruminating",
                                "meditating", "deliberating", "musing",
                                "waddling", "combobulating", "crunching", "brewing",
                                "brewed for", "loading", "computing", "reasoning",
                                "considering", "investigating", "gathering",
                                "esc to interrupt", "esc to cancel",
                                # AGY (Gemini) 상태 패턴
                                "calling tool", "executing", "reading", "writing",
                                "applying patch", "searching codebase",
                                # Codex 상태 패턴
                                "codex is thinking", "applying changes", "reviewing",
                                # 한국어 상태
                                "분석 중", "작업 중", "모니터링", "읽는 중", "작성 중",
                                "검토 중", "리뷰 중", "수정 중", "생성 중", "실행 중",
                                # compact 진행 중
                                "compacting", "auto-compact",
                                "zigzagging", "shenaniganing", "cooked"]):
        return "live"
    # 작업완료 감지 (idle보다 먼저)
    if any(k in last for k in ["분석 완료", "작업 완료", "완료했습니다", "보고합니다",
                                "각성 완료", "awakened", "worked for",
                                "작업이 완료", "결과를 보고", "산출물",
                                "saved to", "저장했습니다", "저장 완료",
                                "report generated", "보고서 작성 완료"]):
        return "done"
    # 대기 감지
    if any(k in last for k in ["waiting", "idle", "$ ", "> ", ">>> ", "ps c:\\",
                                "what would you like", "how can i help",
                                "대기합니다", "지시를 대기", "명령을 대기",
                                "try \"",
                                "type your message", "run /review",
                                # AGY/Codex 대기 패턴
                                "enter a prompt", "what can i do", "ready"]):
        return "idle"
    return "idle"


def get_activity_summary(content):
    if not content:
        return "연결 안 됨"
    lines = [_strip(l).strip() for l in content.strip().split("\n") if _strip(l).strip()]
    if not lines:
        return "대기 중"
    for line in reversed(lines[-10:]):
        low = line.lower()
        if any(skip in low for skip in ["$", ">>>", "```"]):
            continue
        if len(line) > 5:
            return line[:90] + ("..." if len(line) > 90 else "")
    return lines[-1][:90] if lines else "대기 중"


def get_terminal_preview(content, n=3):
    """터미널 마지막 n줄 미리보기."""
    if not content:
        return []
    lines = [_strip(l).strip() for l in content.strip().split("\n") if _strip(l).strip()]
    return lines[-n:] if lines else []


def detect_context_warning(content):
    """워커 화면에서 컨텍스트 부족 경고 감지. 반환: 'critical'|'warning'|None"""
    if not content:
        return None
    text = _strip(content).lower()
    # critical: 자동 compact 발동 또는 context 거의 소진
    if any(k in text for k in ["auto-compacting", "compacting conversation",
                                 "context window is full", "out of context",
                                 "context limit reached", "0% context",
                                 "1% context", "2% context", "3% context",
                                 "4% context", "5% context",
                                 "context is almost full"]):
        return "critical"
    # warning: compact 메시지 감지 또는 context low 표시
    if any(k in text for k in ["compacted", "context low", "context is getting",
                                 "running low on context",
                                 "10% context", "15% context", "20% context",
                                 "consider using /compact", "/compact",
                                 "conversation is getting long"]):
        return "warning"
    return None


def get_claude_contexts():
    """cmux-win 세션을 하나로 통합하여 현재 활성 세션 기준으로 표시."""
    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        return []
    try:
        # cmux-win 세션만 (홈 디렉토리 프로젝트 = C--Users----)
        cmux_project = projects_dir / "C--Users----"
        search_dirs = [cmux_project] if cmux_project.exists() else [projects_dir]
        jsonls = []
        for search_dir in search_dirs:
            for p in search_dir.glob("*.jsonl"):
                if "subagent" in str(p):
                    continue
                try:
                    mtime = p.stat().st_mtime
                    size = p.stat().st_size
                    if size > 1000:
                        jsonls.append((mtime, p))
                except OSError:
                    pass
        jsonls.sort(key=lambda x: x[0], reverse=True)

        # 가장 최근 활성 세션 1개만 (컨텍스트 사용량 가장 높은 것)
        best = None
        session_count = 0
        for _, jf in jsonls[:10]:
            last_usage = None
            try:
                with open(jf, "r", encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        try:
                            data = json.loads(line)
                            u = data.get("message", {}).get("usage", {})
                            if u and u.get("input_tokens") is not None:
                                last_usage = u
                        except (json.JSONDecodeError, TypeError):
                            pass
            except OSError as e:
                _log.debug("JSONL read failed %s: %s", jf, e)
                continue
            if last_usage:
                session_count += 1
                inp = last_usage.get("input_tokens", 0)
                cache_r = last_usage.get("cache_read_input_tokens", 0)
                cache_c = last_usage.get("cache_creation_input_tokens", 0)
                ctx = inp + cache_r + cache_c
                if best is None or ctx > best["ctx"]:
                    best = {"ctx": ctx}

        if best:
            limit = 200_000
            ctx = best["ctx"]
            pct = min(100, round(ctx / limit * 100, 1))
            return [{"label": "cmux-win", "project": "cmux-win",
                      "ctx": ctx, "limit": limit, "pct": pct,
                      "sessions": session_count}]
    except (OSError, json.JSONDecodeError, ValueError) as e:
        _log.warning("Context data read failed: %s", e)
    return []


_token_usage_cache: dict[str, Any] = {"ts": 0, "data": None}
_TOKEN_USAGE_CACHE_SEC = 10  # 10초마다 갱신 (C: 증분 캐시로 빈도 낮춤)
_jsonl_file_cache: dict[str, tuple[float, dict]] = {}  # path → (mtime, parsed_result)


def get_token_usage() -> UsageData:
    """JSONL 파싱으로 시간별/일별/월별 토큰 사용량 집계."""
    now_ts = time.time()
    with _cache_lock:
        if _token_usage_cache["data"] and now_ts - _token_usage_cache["ts"] < _TOKEN_USAGE_CACHE_SEC:
            return _token_usage_cache["data"]
    projects_dir = Path.home() / ".claude" / "projects"
    now = datetime.now()
    hour_ago = now - timedelta(hours=1)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    hourly_in = 0
    hourly_out = 0
    daily_in = 0
    daily_out = 0
    monthly_in = 0
    monthly_out = 0
    session_count = 0
    message_count = 0
    hourly_buckets = defaultdict(int)

    try:
        # stats-cache.json for monthly data
        stats_file = Path.home() / ".claude" / "stats-cache.json"
        if stats_file.exists():
            stats = json.loads(stats_file.read_text())
            dmt = stats.get("dailyModelTokens", [])
            month_str = now.strftime("%Y-%m")
            for d in dmt:
                if d["date"].startswith(month_str):
                    for model, tokens in d.get("tokensByModel", {}).items():
                        monthly_in += tokens

        # JSONL for today's detailed data (C: 증분 파싱 — mtime 변경 시만 재파싱)
        for jf in projects_dir.rglob("*.jsonl"):
            jf_str = str(jf)
            if "subagent" in jf_str:
                continue
            try:
                stat = jf.stat()
                mtime = stat.st_mtime
                if datetime.fromtimestamp(mtime) < today_start:
                    continue

                # 증분 캐시: mtime 동일하면 이전 파싱 결과 재사용
                cached = _jsonl_file_cache.get(jf_str)
                if cached and cached[0] == mtime:
                    file_data = cached[1]
                else:
                    file_data = {"msgs": []}
                    with open(jf, "r", encoding="utf-8", errors="replace") as fh:
                        for line in fh:
                            try:
                                d = json.loads(line)
                                ts_str = d.get("timestamp", "")
                                usage = d.get("message", {}).get("usage", {})
                                if not usage or not ts_str:
                                    continue
                                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
                                inp = usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
                                out = usage.get("output_tokens", 0)
                                file_data["msgs"].append((ts, inp, out))
                            except (json.JSONDecodeError, TypeError, ValueError):
                                pass
                    _jsonl_file_cache[jf_str] = (mtime, file_data)

                session_count += 1
                for ts, inp, out in file_data["msgs"]:
                    message_count += 1
                    if ts >= today_start:
                        daily_in += inp
                        daily_out += out
                    if ts >= hour_ago:
                        hourly_in += inp
                        hourly_out += out
                    bucket = ts.strftime("%H")
                    hourly_buckets[bucket] += inp + out
            except OSError:
                pass
    except (OSError, json.JSONDecodeError, ValueError) as e:
        _log.warning("Token usage calculation failed: %s", e)

    # Build sparkline data (last 12 hours)
    sparkline = []
    for i in range(12):
        h = (now - timedelta(hours=11 - i)).strftime("%H")
        sparkline.append(hourly_buckets.get(h, 0))

    result = UsageData(
        hourly_in=hourly_in, hourly_out=hourly_out,
        daily_in=daily_in, daily_out=daily_out,
        monthly_total=monthly_in + daily_in,
        sessions=session_count, messages=message_count,
        sparkline=sparkline,
    )
    _token_usage_cache["ts"] = now_ts
    _token_usage_cache["data"] = result
    return result


def get_system_metrics() -> SystemMetrics:
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.3)
        mem = psutil.virtual_memory()
        return SystemMetrics(cpu=cpu, mem_pct=mem.percent,
                             mem_used=round(mem.used / (1024**3), 1),
                             mem_total=round(mem.total / (1024**3), 1))
    except (ImportError, OSError, AttributeError) as e:
        _log.debug("System metrics unavailable: %s", e)
        return SystemMetrics()


# ━━━━━━━ SVG Uptime Circle ━━━━━━━
def _uptime_svg(h, m, sec, size=130):
    """가동시간을 원형 SVG로 표시. 레이더와 동일 크기. 60분 기준 원호 진행."""
    cx, cy = size // 2, size // 2
    r = size * 0.34
    sw = size * 0.055
    circ = 2 * math.pi * r
    pct = m / 60
    dash = f"{pct * circ:.1f} {circ:.1f}"
    color = ACCENT_LIGHT
    ro = int(size * 0.43)
    ri = int(size * 0.25)

    return f'''<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
      <circle cx="{cx}" cy="{cy}" r="{ro}" fill="none" stroke="rgba(255,255,255,0.03)" stroke-width="1" stroke-dasharray="3 5"/>
      <circle cx="{cx}" cy="{cy}" r="{ri}" fill="none" stroke="rgba(255,255,255,0.03)" stroke-width="0.5" stroke-dasharray="2 4"/>
      <circle cx="{cx}" cy="{cy}" r="{r:.0f}" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="{sw:.0f}"/>
      <circle cx="{cx}" cy="{cy}" r="{r:.0f}" fill="none" stroke="{color}" stroke-width="{sw:.0f}"
              stroke-dasharray="{dash}" stroke-linecap="round" transform="rotate(-90 {cx} {cy})"
              style="transition:stroke-dasharray 1s ease;"/>
      <text id="uptime-val" x="{cx}" y="{cy-2}" text-anchor="middle" dominant-baseline="central"
            fill="#fff" font-size="16" font-weight="700"
            font-family="'JetBrains Mono',monospace"
            style="letter-spacing:-0.3px;">{h:02d}:{m:02d}:{sec:02d}</text>
      <text x="{cx}" y="{cy+size*0.18:.0f}" text-anchor="middle"
            fill="{ACCENT_LIGHT}" font-size="{size*0.085:.0f}" font-weight="600"
            font-family="'Pretendard Variable','Inter',sans-serif"
            style="letter-spacing:0.5px;">가동시간</text>
    </svg>'''


# ━━━━━━━ SVG Radar ━━━━━━━
def _radar_svg(active, total, size=130):
    pct = active / max(total, 1)
    cx, cy = size // 2, size // 2
    r = size * 0.34
    sw = size * 0.055
    circ = 2 * math.pi * r
    dash = f"{pct * circ:.1f} {circ:.1f}"
    color = GREEN if active > 0 else TEXT_MUTED
    ro = int(size * 0.43)
    ri = int(size * 0.25)  # inner decoration ring

    sweep = ""
    ripples = ""
    if active > 0:
        sweep = f'''<defs>
          <linearGradient id="sw" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stop-color="{GREEN}" stop-opacity="0.6"/>
            <stop offset="100%" stop-color="{GREEN}" stop-opacity="0"/>
          </linearGradient>
          <radialGradient id="rg" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stop-color="{GREEN}" stop-opacity="0.08"/>
            <stop offset="100%" stop-color="{GREEN}" stop-opacity="0"/>
          </radialGradient>
        </defs>
        <circle cx="{cx}" cy="{cy}" r="{ro}" fill="url(#rg)"/>
        <line x1="{cx}" y1="{cy}" x2="{cx}" y2="{cy-ro}"
              stroke="url(#sw)" stroke-width="1.5" style="transform-origin:{cx}px {cy}px;animation:radar-spin 4s linear infinite;"/>'''
        for i in range(3):
            ripples += f'<circle cx="{cx}" cy="{cy}" r="0" fill="none" stroke="{GREEN}" stroke-opacity="0.15" style="animation:rp-out 4s ease-out infinite {i*1.3}s;"/>'

    # 작업 중 표현: 레이더 스윕 + 리플만 사용. 원호는 애니메이션 없음 (두께 변화 방지)

    return f'''<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
      <circle cx="{cx}" cy="{cy}" r="{ro}" fill="none" stroke="rgba(255,255,255,0.03)" stroke-width="1" stroke-dasharray="3 5" style="animation:wave-rot 4s linear infinite;"/>
      <circle cx="{cx}" cy="{cy}" r="{ri}" fill="none" stroke="rgba(255,255,255,0.03)" stroke-width="0.5" stroke-dasharray="2 4"/>
      {ripples}{sweep}
      <circle cx="{cx}" cy="{cy}" r="{r:.0f}" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="{sw:.0f}"/>
      <circle cx="{cx}" cy="{cy}" r="{r:.0f}" fill="none" stroke="{color}" stroke-width="{sw:.0f}"
              stroke-dasharray="{dash}" stroke-linecap="round" transform="rotate(-90 {cx} {cy})"/>
      <text x="{cx}" y="{cy-4}" text-anchor="middle" dominant-baseline="central"
            fill="#fff" font-size="{size*0.17:.0f}" font-weight="700"
            font-family="'Pretendard Variable','Inter',sans-serif"
            style="letter-spacing:-0.5px;">{round(pct*100)}%</text>
      <text x="{cx}" y="{cy+size*0.18:.0f}" text-anchor="middle"
            fill="{GREEN}" font-size="{size*0.085:.0f}" font-weight="600"
            font-family="'Pretendard Variable','Inter',sans-serif"
            style="letter-spacing:0.5px;">{active}/{total} 활성</text>
    </svg>'''


def _sparkline_svg(data, w=160, h=36, color=ACCENT_LIGHT):
    if not data or max(data) == 0:
        return f'<svg width="{w}" height="{h}"><text x="{w//2}" y="{h//2}" text-anchor="middle" fill="rgba(255,255,255,0.2)" font-size="10">데이터 없음</text></svg>'
    mx = max(data)
    n = len(data)
    step = w / max(n - 1, 1)
    points = " ".join(f"{i*step:.1f},{h - (v/mx)*(h-4) - 2:.1f}" for i, v in enumerate(data))
    base = f"0,{h} {points} {w},{h}"
    return f'''<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="filter:drop-shadow(0 0 4px {color}30);">
      <defs><linearGradient id="spk" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="{color}" stop-opacity="0.4"/>
        <stop offset="100%" stop-color="{color}" stop-opacity="0.03"/>
      </linearGradient></defs>
      <polygon points="{base}" fill="url(#spk)"/>
      <polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"
                style="filter:drop-shadow(0 0 3px {color});"/>
    </svg>'''


def _fmt_tokens(n):
    """토큰 수를 읽기 쉬운 형태로 (만 단위)."""
    if n >= 10_000:
        return f"{n/10_000:.1f}만"
    if n >= 1_000:
        return f"{n/1_000:.1f}천"
    return str(n)


# ━━━━━━━ HTML builder ━━━━━━━
def _esc(t):
    """HTML 특수문자 이스케이프 — 외부 데이터 삽입 시 XSS 방지."""
    return _html.escape(str(t))


DATA_PORT = 8501

# D: 데이터 서버 인증 토큰 (프로세스 시작 시 1회 생성, JS fetch에서 사용)
import secrets as _secrets
_DATA_AUTH_TOKEN = _secrets.token_urlsafe(16)


_DYNAMIC_COLORS = ["#ec4899", "#a78bfa", "#06b6d4", "#f97316", "#84cc16", "#e879f9", "#fb923c", "#2dd4bf"]
_dynamic_color_idx = 0


def _match_fleet_config(label: str, label_map: dict) -> dict:
    """surface 라벨을 FLEET 설정에 매칭. 미등록 워커는 자동 색상/아이콘 할당."""
    cfg = label_map.get(label)
    if cfg:
        return cfg
    label_base = label.split("(")[0].strip().lower()
    for k, v in label_map.items():
        k_base = k.split("(")[0].strip().lower()
        if k_base == label_base or k.lower() in label.lower() or label.lower() in k.lower():
            return v
    # 미등록 워커 자동 등록 — 동적 색상·아이콘 할당
    global _dynamic_color_idx
    color = _DYNAMIC_COLORS[_dynamic_color_idx % len(_DYNAMIC_COLORS)]
    _dynamic_color_idx += 1
    # 라벨에서 AI 이름 추출: "Worker6(Claude)" → "Claude"
    ai = label.split("(")[1].rstrip(")") if "(" in label else "?"
    icon = label[0].upper() if label else "?"
    # 숫자가 있으면 숫자를 아이콘으로
    nums = re.findall(r"\d+", label)
    if nums:
        icon = nums[0]
    auto_cfg = {"key": label, "icon": icon, "color": color, "ai": ai, "desc": "auto"}
    # label_map에 캐싱하여 같은 라벨 재할당 방지
    label_map[label] = auto_cfg
    return auto_cfg


# ━━━━━━━ CSS Module Constant (B: 매 호출 f-string 재생성 방지) ━━━━━━━
_CSS = f"""
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');
*{{margin:0;padding:0;box-sizing:border-box;}}
html,body{{height:100%;overflow-y:auto;overflow-x:hidden;}}
body{{background:{BG_VOID};color:#e2e8f0;
     font-family:'Pretendard Variable','Inter',-apple-system,'Noto Sans KR',sans-serif;
     padding:12px 14px;width:100%;word-break:keep-all;-webkit-font-smoothing:antialiased;
     font-size:14px;}}
.live-pulse{{width:10px;height:10px;border-radius:50%;background:{RED};flex-shrink:0;
             animation:red-pulse 0.8s ease-in-out infinite;
             box-shadow:0 0 8px {RED},0 0 16px rgba(239,68,68,0.5);}}
@keyframes red-pulse{{
  0%,100%{{opacity:1;box-shadow:0 0 8px {RED},0 0 20px rgba(239,68,68,0.6);transform:scale(1);}}
  50%{{opacity:0.3;box-shadow:0 0 2px {RED};transform:scale(0.8);}}
}}
.glass{{background:rgba(255,255,255,0.05);backdrop-filter:blur(16px) saturate(1.3);
        border:1px solid rgba(255,255,255,0.10);border-radius:12px;padding:14px;
        transition:all 0.25s cubic-bezier(0.22,1,0.36,1);}}
.glass:hover{{background:rgba(255,255,255,0.08);}}
.glass--accent{{border-top:3px solid {ACCENT_LIGHT};}}
.hdr{{display:flex;align-items:center;gap:10px;margin-bottom:12px;}}
.hdr-title{{font-size:clamp(18px,4vw,26px);font-weight:800;letter-spacing:-.5px;color:#fff;}}
.hdr-badge{{font-size:11px;font-weight:700;padding:3px 10px;border-radius:9999px;}}
.hdr-time{{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:600;color:#cbd5e1;margin-left:auto;}}
.kpi-section{{text-align:center;margin-bottom:12px;}}
.kpi-radar{{display:flex;justify-content:center;margin-bottom:10px;}}
.kpi-row{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;}}
.kpi{{text-align:center;padding:10px 8px;}}
.kpi-val{{font-family:'JetBrains Mono',monospace;font-size:clamp(18px,3vw,28px);font-weight:700;line-height:1.1;}}
.kpi-lbl{{font-size:13px;font-weight:700;color:#ffffff;margin-top:5px;letter-spacing:0.03em;}}
.sec{{font-size:15px;font-weight:800;color:#ffffff;margin:16px 0 8px 0;letter-spacing:0.3px;}}
.fleet-list{{display:flex;flex-direction:column;gap:5px;}}
.fleet-card{{display:flex;align-items:center;gap:6px;padding:8px 10px;}}
.fleet-status{{margin-left:auto;display:flex;align-items:center;gap:4px;}}
.ag-icon{{width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;
          font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;color:#fff;flex-shrink:0;
          border:2px solid var(--ac);background:rgba(0,0,0,0.3);}}
.ag-body{{flex:1;min-width:0;}}
.ag-top{{display:flex;align-items:center;gap:6px;}}
.ag-name{{font-size:13px;font-weight:700;color:var(--ac);}}
.ag-ai{{font-size:9px;font-weight:600;padding:2px 6px;border-radius:9999px;background:rgba(255,255,255,0.08);color:#cbd5e1;}}
.ag-status{{margin-left:auto;display:flex;align-items:center;gap:4px;}}
.ag-dot{{width:7px;height:7px;border-radius:50%;}}
.ag-dot--live{{background:{GREEN};animation:blink 1.4s ease-in-out infinite;box-shadow:0 0 6px {GREEN};}}
.ag-dot--done{{background:{BLUE};box-shadow:0 0 6px {BLUE};}}
.ag-dot--idle{{background:#94a3b8;}}
.ag-dot--err{{background:{RED};animation:blink 0.8s ease-in-out infinite;box-shadow:0 0 6px {RED};}}
.ag-dot--off{{background:#475569;}}
.ag-stlbl{{font-size:9px;font-weight:700;padding:2px 6px;border-radius:9999px;}}
.ag-stlbl--live{{background:rgba(34,197,94,0.15);color:#4ade80;}}
.ag-stlbl--done{{background:rgba(59,130,246,0.15);color:#60a5fa;}}
.ag-stlbl--idle{{background:rgba(148,163,184,0.15);color:#94a3b8;}}
.ag-stlbl--err{{background:rgba(239,68,68,0.15);color:#f87171;}}
.ag-stlbl--off{{background:rgba(71,85,105,0.15);color:#64748b;}}
.ag-act{{font-size:11px;color:#e2e8f0;opacity:0.75;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-top:3px;}}
.ctx-warn{{font-size:8px;font-weight:800;padding:1px 5px;border-radius:9999px;margin-left:auto;margin-right:4px;animation:blink 1s ease-in-out infinite;}}
.ctx-warn--critical{{background:rgba(239,68,68,0.25);color:#f87171;border:1px solid rgba(239,68,68,0.4);}}
.ctx-warn--warning{{background:rgba(245,158,11,0.2);color:#fbbf24;border:1px solid rgba(245,158,11,0.3);}}
.bar-row{{display:flex;align-items:center;gap:8px;margin:4px 0;}}
.bar-lbl{{font-size:12px;color:#cbd5e1;flex-shrink:0;min-width:40px;font-weight:600;}}
.bar-tk{{flex:1;height:8px;background:rgba(255,255,255,0.08);border-radius:4px;overflow:hidden;position:relative;}}
.bar-fl{{height:100%;border-radius:4px;transition:width 0.5s ease;}}
.bar-v{{font-family:'JetBrains Mono',monospace;font-size:11px;color:#e2e8f0;font-weight:600;text-align:right;flex-shrink:0;min-width:65px;}}
.usage-band{{display:flex;gap:0;border-radius:10px;overflow:hidden;margin-bottom:8px;}}
.usage-item{{flex:1;text-align:center;padding:10px 6px;position:relative;}}
.usage-item+.usage-item{{border-left:1px solid rgba(255,255,255,0.06);}}
.usage-item .usage-lbl-top{{font-size:11px;font-weight:700;color:rgba(255,255,255,0.55);margin-bottom:6px;letter-spacing:0.04em;}}
.usage-val{{font-family:'JetBrains Mono',monospace;font-size:18px;font-weight:700;}}
.usage-sub{{font-size:10px;color:#cbd5e1;margin-top:3px;}}
.sparkline-row{{display:flex;align-items:center;gap:8px;margin-top:8px;}}
.sparkline-lbl{{font-size:10px;color:#94a3b8;flex-shrink:0;}}
.foot{{font-size:11px;color:rgba(255,255,255,0.4);margin-top:12px;padding-top:8px;
       border-top:1px solid rgba(255,255,255,0.08);text-align:center;}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(12px);}}to{{opacity:1;transform:translateY(0);}}}}
@keyframes blink{{0%,100%{{opacity:1;}}50%{{opacity:0.3;}}}}
@keyframes pulse-glow{{0%,100%{{box-shadow:0 0 8px rgba(0,168,255,0.15);}}50%{{box-shadow:0 0 20px rgba(0,168,255,0.35);}}}}
@keyframes barFlow{{0%{{background-position:0% 50%;}}100%{{background-position:200% 50%;}}}}
@keyframes radar-spin{{0%{{transform:rotate(0deg);}}100%{{transform:rotate(360deg);}}}}
@keyframes rp-out{{0%{{r:0;opacity:0.4;stroke-width:1.5;}}100%{{r:60;opacity:0;stroke-width:0.3;}}}}
@keyframes wave-rot{{0%{{stroke-dashoffset:0;}}100%{{stroke-dashoffset:-60;}}}}
@keyframes neon-p{{0%,100%{{filter:drop-shadow(0 0 4px rgba(0,212,255,0.25));}}50%{{filter:drop-shadow(0 0 12px rgba(0,212,255,0.65));}}}}
@keyframes shimmer{{0%{{background-position:-200% 0;}}100%{{background-position:200% 0;}}}}
@keyframes pulse-glow-bar{{0%,100%{{opacity:1;filter:brightness(1);}}50%{{opacity:0.7;filter:brightness(1.4);}}}}
::-webkit-scrollbar{{width:6px;}}
::-webkit-scrollbar-track{{background:transparent;}}
::-webkit-scrollbar-thumb{{background:rgba(255,255,255,0.12);border-radius:4px;}}
::-webkit-scrollbar-thumb:hover{{background:rgba(255,255,255,0.22);}}
@media(prefers-reduced-motion:reduce){{*,*::before,*::after{{animation-duration:0.01ms!important;transition-duration:0.01ms!important;}}}}
@media(max-width:350px){{body{{padding:8px 10px;font-size:12px;}}.hdr-title{{font-size:16px;}}.kpi-val{{font-size:16px!important;}}.kpi-lbl{{font-size:9px;}}.agent{{padding:6px 8px;gap:8px;}}.ag-icon{{width:22px;height:22px;font-size:9px;}}.ag-name{{font-size:11px;}}.usage-val{{font-size:14px;}}.sec{{font-size:11px;}}.bar-lbl,.bar-v{{font-size:10px;}}}}
@media(max-width:220px){{.kpi-row{{grid-template-columns:1fr;}}.usage-grid{{grid-template-columns:1fr;}}.ag-act{{display:none;}}}}
"""


# ━━━━━━━ HTML Sub-builders (A: build_full_html 분할) ━━━━━━━
_STATUS_DOT = {"live": "live", "done": "done", "idle": "idle", "error": "err"}
_STATUS_LABEL = {"live": "작업중", "done": "작업완료", "idle": "대기", "error": "오류", "offline": "죽음"}


def _build_header(now: datetime, is_live: bool) -> str:
    mode_label = "LIVE" if is_live else "IDLE"
    return f'''
    <div class="hdr">
      <span class="live-pulse"></span>
      <span class="hdr-title">JARVIS Control Center</span>
      <span class="hdr-badge" style="color:{RED};background:rgba(239,68,68,0.15);">{mode_label}</span>
      <span class="hdr-time">{now.strftime('%Y.%m.%d')} <span style="color:rgba(255,255,255,0.6);margin:0 6px;">|</span> <span id="live-clock">{now.strftime('%H:%M:%S')}</span></span>
    </div>'''


def _build_kpi(n_live: int, n_total: int, h: int, m: int, sec: int) -> str:
    radar = _radar_svg(n_live, n_total, size=130)
    uptime_circle = _uptime_svg(h, m, sec, size=130)
    return f'''
    <div class="kpi-section">
      <div style="display:flex;justify-content:center;gap:16px;">
        <div style="display:inline-block;">{radar}</div>
        <div style="display:inline-block;">{uptime_circle}</div>
      </div>
    </div>'''


def _build_fleet(pane_data: list[PaneData]) -> str:
    parts = ['<div class="sec">플릿 현황</div>', '<div class="fleet-list">']
    for p in pane_data:
        color = p.config["color"]
        dot_cls = _STATUS_DOT.get(p.status, "off")
        st_label = _STATUS_LABEL.get(p.status, "?")
        short_name = _esc(p.config["key"].split("(")[0].strip())
        icon = _esc(p.config["icon"])
        ctx_html = ""
        if p.ctx_warn == "critical":
            ctx_html = '<span class="ctx-warn ctx-warn--critical">CTX!</span>'
        elif p.ctx_warn == "warning":
            ctx_html = '<span class="ctx-warn ctx-warn--warning">CTX</span>'
        parts.append(f'''
        <div class="fleet-card glass" style="border-left:3px solid {color};">
          <div class="ag-icon" style="border-color:{color};">{icon}</div>
          <span class="ag-name" style="color:{color};">{short_name}</span>
          {ctx_html}
          <span class="fleet-status">
            <span class="ag-dot ag-dot--{dot_cls}"></span>
            <span class="ag-stlbl ag-stlbl--{dot_cls}">{st_label}</span>
          </span>
        </div>''')
    parts.append('</div>')
    return "".join(parts)


def _bar_gradient(pct: float, normal_colors: str, warn_colors: str, crit_colors: str) -> str:
    if pct >= 80:
        return crit_colors
    if pct >= 60:
        return warn_colors
    return normal_colors


def _build_token_usage(now: datetime, usage_data: UsageData, rate_limits: RateLimitData) -> str:
    s_pct = rate_limits.session_pct
    s_reset = rate_limits.session_reset
    w_pct = rate_limits.weekly_pct
    w_reset = rate_limits.weekly_reset
    hourly_total = usage_data.hourly_in + usage_data.hourly_out
    daily_total = usage_data.daily_in + usage_data.daily_out

    s_bar = _bar_gradient(s_pct,
        f"linear-gradient(90deg, {ACCENT}, {ACCENT_LIGHT})",
        f"linear-gradient(90deg, {AMBER}, #fbbf24)",
        f"linear-gradient(90deg, {RED}, #f87171)")
    w_bar = _bar_gradient(w_pct,
        f"linear-gradient(90deg, {BLUE}, {CYAN})",
        f"linear-gradient(90deg, {AMBER}, #fbbf24)",
        f"linear-gradient(90deg, {RED}, #f87171)")

    sparkline = _sparkline_svg(usage_data.sparkline)
    hours_labels = " ".join(
        f'<span style="flex:1;text-align:center;">{(now - timedelta(hours=11-i)).strftime("%H")}</span>'
        for i in range(0, 12, 3))

    return f'''<div class="sec">토큰 사용량</div>
    <div class="glass" style="padding:0;">
    <div style="padding:16px 14px 10px;">
      <div class="bar-row" style="margin:6px 0;">
        <div class="bar-lbl">세션</div>
        <div class="bar-tk" style="height:12px;"><div class="bar-fl" style="width:{min(s_pct,100):.0f}%;background:{s_bar};"></div></div>
        <div class="bar-v" style="font-size:13px;">{s_pct:.0f}%</div>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:10px;color:#64748b;margin:2px 0 12px 48px;">
        <span>5시간 윈도우</span><span>리셋 {_esc(s_reset)}</span>
      </div>
      <div class="bar-row" style="margin:6px 0;">
        <div class="bar-lbl">주간</div>
        <div class="bar-tk" style="height:12px;"><div class="bar-fl" style="width:{min(w_pct,100):.0f}%;background:{w_bar};"></div></div>
        <div class="bar-v" style="font-size:13px;">{w_pct:.0f}%</div>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:10px;color:#64748b;margin:2px 0 6px 48px;">
        <span>전체 모델</span><span>리셋 {_esc(w_reset)}</span>
      </div>
    </div>
    <div class="usage-band">
      <div class="usage-item">
        <div class="usage-lbl-top">최근 1시간</div>
        <div class="usage-val" style="color:{ACCENT_LIGHT};">{_fmt_tokens(hourly_total)}</div>
        <div class="usage-sub">입력 {_fmt_tokens(usage_data.hourly_in)} · 출력 {_fmt_tokens(usage_data.hourly_out)}</div>
      </div>
      <div class="usage-item">
        <div class="usage-lbl-top">오늘 소비</div>
        <div class="usage-val" style="color:{GREEN};">{_fmt_tokens(daily_total)}</div>
        <div class="usage-sub">입력 {_fmt_tokens(usage_data.daily_in)} · 출력 {_fmt_tokens(usage_data.daily_out)}</div>
      </div>
      <div class="usage-item">
        <div class="usage-lbl-top">세션 수</div>
        <div class="usage-val" style="color:{AMBER};">{usage_data.sessions}</div>
        <div class="usage-sub">메시지 {usage_data.messages}건</div>
      </div>
    </div>
    <div class="sparkline-row">
      <span class="sparkline-lbl">12h</span>
      {sparkline}
    </div>
    <div style="display:flex;margin-left:28px;font-size:11px;color:rgba(255,255,255,0.6);font-family:'JetBrains Mono',monospace;font-weight:600;">{hours_labels}</div>
    </div>'''


def _build_system(metrics: SystemMetrics) -> str:
    cpu_c = GREEN if metrics.cpu < 60 else AMBER if metrics.cpu < 80 else RED
    mem_c = GREEN if metrics.mem_pct < 70 else AMBER if metrics.mem_pct < 90 else RED
    return f'''<div class="sec">시스템</div>
    <div class="glass" style="padding:10px;">
    <div class="bar-row">
      <div class="bar-lbl">CPU</div>
      <div class="bar-tk"><div class="bar-fl" style="width:{metrics.cpu:.0f}%;background:{cpu_c};"></div></div>
      <div class="bar-v">{metrics.cpu:.0f}%</div>
    </div>
    <div class="bar-row">
      <div class="bar-lbl">MEM</div>
      <div class="bar-tk"><div class="bar-fl" style="width:{metrics.mem_pct:.0f}%;background:{mem_c};"></div></div>
      <div class="bar-v">{metrics.mem_used:.1f}/{metrics.mem_total:.0f}G</div>
    </div>
    </div>'''


def _build_js(elapsed_sec: int) -> str:
    return f"""
    <script>
    async function refreshDashboard() {{
        try {{
            const resp = await fetch('http://localhost:{DATA_PORT}/?token={_DATA_AUTH_TOKEN}');
            if (resp.ok) {{
                const root = document.getElementById('dash-root');
                root.innerHTML = await resp.text();
            }}
        }} catch(e) {{}}
    }}
    setInterval(refreshDashboard, {REFRESH_SEC * 1000});
    var _uptimeStart = Date.now() - {elapsed_sec * 1000};
    setInterval(function() {{
        var now = new Date();
        var el = document.getElementById('live-clock');
        if (el) {{
            var hh = String(now.getHours()).padStart(2,'0');
            var mm = String(now.getMinutes()).padStart(2,'0');
            var ss = String(now.getSeconds()).padStart(2,'0');
            el.textContent = hh + ':' + mm + ':' + ss;
        }}
        var uel = document.getElementById('uptime-val');
        if (uel) {{
            var elapsed = Math.floor((Date.now() - _uptimeStart) / 1000);
            var uh = Math.floor(elapsed / 3600);
            var um = Math.floor((elapsed % 3600) / 60);
            var us = elapsed % 60;
            uel.textContent = String(uh).padStart(2,'0') + ':' + String(um).padStart(2,'0') + ':' + String(us).padStart(2,'0');
        }}
    }}, 1000);
    </script>
    """


def build_full_html(pane_data, metrics, start_time, usage_data, rate_limits, body_only=False):
    now = datetime.now()
    n_live = sum(1 for p in pane_data if p.status == "live")
    n_total = len(pane_data)
    elapsed = now - start_time
    h, rem = divmod(int(elapsed.total_seconds()), 3600)
    m, sec = divmod(rem, 60)
    is_live = n_live > 0

    body_html = "".join([
        _build_header(now, is_live),
        _build_kpi(n_live, n_total, h, m, sec),
        _build_fleet(pane_data),
        _build_token_usage(now, usage_data, rate_limits),
        _build_system(metrics),
        f'<div class="foot">자비스 플릿 v2 &middot; {REFRESH_SEC}초 새로고침 &middot; {now.strftime("%Y-%m-%d %H:%M:%S")}</div>',
    ])

    if body_only:
        return body_html

    return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>{_CSS}</style>{_build_js(int(elapsed.total_seconds()))}</head>
<body><div id="dash-root">{body_html}</div></body></html>'''


def build_empty_html():
    return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css');
body{{background:{BG_VOID};color:{TEXT_PRIMARY};font-family:'Pretendard Variable',system-ui,sans-serif;
  display:flex;flex-direction:column;align-items:center;justify-content:center;height:90vh;}}
.glass{{background:{SURFACE_1};backdrop-filter:blur(16px);border:1px solid {BORDER};
        border-radius:20px;padding:40px;text-align:center;animation:fadeUp 0.6s cubic-bezier(0.22,1,0.36,1);}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(20px);}}to{{opacity:1;transform:translateY(0);}}}}
</style></head><body>
  <div class="glass">
    <div style="font-size:40px;margin-bottom:16px;font-weight:900;color:{ACCENT_LIGHT};">J</div>
    <div style="font-size:18px;font-weight:700;margin-bottom:8px;">자비스 플릿 대기 중</div>
    <div style="color:{TEXT_SECONDARY};font-size:13px;line-height:1.6;">
      마스터 Claude에게 <strong style="color:{C_MASTER};">"너는 마스터다"</strong>를 입력하면<br>
      5-pane fleet이 자동으로 부트스트랩됩니다.
    </div>
  </div>
</body></html>'''


# ━━━━━━━ Data Server (깜박임 방지용 — JS fetch 대상) ━━━━━━━
_fleet_start = datetime.now()


def _gather_and_render_body():
    """Fleet 데이터 수집 → body HTML 생성 (JS fetch 응답용)."""
    terminals, contents = gather_fleet_data()
    if not terminals:
        return '<div style="text-align:center;padding:40px;color:#64748b;">플릿 대기 중...</div>'

    label_map = {cfg["key"]: cfg for cfg in FLEET}
    pane_data = []
    for i, sf in enumerate(terminals):
        label = sf.get("label") or sf.get("title", "Terminal")
        cfg = _match_fleet_config(label, label_map)
        content = contents[i] if i < len(contents) else ""
        status = detect_status(content)
        activity = get_activity_summary(content)
        preview = get_terminal_preview(content, 3)
        ctx_warn = detect_context_warning(content)
        pane_data.append(PaneData(surface=sf, config=cfg, content=content,
                                   status=status, activity=activity,
                                   preview=preview, ctx_warn=ctx_warn))

    metrics = get_system_metrics()
    usage_data = get_token_usage()
    rl = get_rate_limits()
    return build_full_html(pane_data, metrics, _fleet_start, usage_data, rl, body_only=True)


class _DataHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # D: 토큰 검증 — ?token=xxx 파라미터 필수
        from urllib.parse import urlparse, parse_qs
        query = parse_qs(urlparse(self.path).query)
        token = query.get("token", [""])[0]
        if token != _DATA_AUTH_TOKEN:
            self.send_error(403, "Forbidden")
            return
        try:
            body = _gather_and_render_body()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "http://localhost:8500")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
        except (OSError, ConnectionError) as e:
            _log.warning("Data handler error: %s", e)
            try:
                self.send_error(500, _esc(str(e)))
            except OSError:
                pass

    def log_message(self, *_a):
        pass  # suppress logs


class _ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True
    allow_reuse_port = True


def _start_data_server():
    try:
        srv = _ReusableHTTPServer(("127.0.0.1", DATA_PORT), _DataHandler)
        srv.serve_forever()
    except OSError as e:
        _log.error("Data server failed to start on port %d: %s", DATA_PORT, e)


# ━━━━━━━ Main ━━━━━━━
if "data_srv" not in st.session_state:
    st.session_state.data_srv = True
    threading.Thread(target=_start_data_server, daemon=True).start()

if "fleet_start" not in st.session_state:
    st.session_state.fleet_start = datetime.now()

# 초기 렌더링 1회만 — 이후 JS가 자체 새로고침 (깜박임 없음)
terminals, contents = gather_fleet_data()

if not terminals:
    components.html(build_empty_html(), height=400, scrolling=False)
else:
    label_map = {cfg["key"]: cfg for cfg in FLEET}
    pane_data = []
    for i, sf in enumerate(terminals):
        label = sf.get("label") or sf.get("title", "Terminal")
        cfg = _match_fleet_config(label, label_map)
        content = contents[i] if i < len(contents) else ""
        status = detect_status(content)
        activity = get_activity_summary(content)
        preview = get_terminal_preview(content, 3)
        ctx_warn = detect_context_warning(content)
        pane_data.append(PaneData(surface=sf, config=cfg, content=content,
                                   status=status, activity=activity,
                                   preview=preview, ctx_warn=ctx_warn))

    metrics = get_system_metrics()
    usage_data = get_token_usage()
    rl = get_rate_limits()
    html = build_full_html(pane_data, metrics, st.session_state.fleet_start, usage_data, rl)
    components.html(html, height=2000, scrolling=True)
