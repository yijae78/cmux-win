# -*- coding: utf-8 -*-
"""Javis Fleet Dashboard — cmux-win 실시간 작업 현황

Benchmark: EnvironmentScan monitor.py + GlobalNews dashboard.py
Anti-flicker: components.html() 단일 iframe 렌더링
Layout: 900px centered, 블랙 + 시안 1색, SVG 레이더 도넛

    streamlit run dashboard.py --server.port 8500 --server.headless true
"""
from __future__ import annotations

import json
import math
import re
import socket as _socket
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# ━━━━━━━ Config ━━━━━━━
SOCKET_TOKEN_FILE = Path.home() / "AppData" / "Roaming" / "cmux-win" / "socket-token"
SOCKET_PORT = 19840
REFRESH_SEC = 5

# ━━━━━━━ Colors ━━━━━━━
BG = "#0a0a0a"
C1 = "#00d4ff"
C_RED = "#ff5252"
W = "#ffffff"
G1 = "rgba(255,255,255,0.55)"
G2 = "rgba(255,255,255,0.35)"
G3 = "rgba(255,255,255,0.20)"
TK = "rgba(255,255,255,0.06)"

C_MASTER = "#3b82f6"
C_CSO = "#8b5cf6"
C_AGY = "#00e676"
C_GEMINI = "#ffa726"
C_CODEX = "#00d4ff"

FLEET = [
    {"key": "Master", "icon": "👑", "color": C_MASTER, "ai": "Claude", "desc": "총지휘 · 신교수님 대화"},
    {"key": "CSO", "icon": "🛡️", "color": C_CSO, "ai": "Claude", "desc": "시스템 운영 · 모니터링"},
    {"key": "Worker1(AGY)", "icon": "⚙️", "color": C_AGY, "ai": "Claude", "desc": "작업 수행 워커"},
    {"key": "Worker2(Gemini)", "icon": "💎", "color": C_GEMINI, "ai": "Gemini", "desc": "리뷰 · 비평"},
    {"key": "Worker3(Codex)", "icon": "🔍", "color": C_CODEX, "ai": "Codex", "desc": "코드 검수"},
]

# ━━━━━━━ Page config ━━━━━━━
st.set_page_config(page_title="Javis Fleet", page_icon="🤖",
                   layout="centered", initial_sidebar_state="collapsed")

# Hide Streamlit chrome
st.markdown("""<style>
.stApp>header,#MainMenu,footer,[data-testid="stHeader"],
[data-testid="stToolbar"],[data-testid="stDecoration"],
.stDeployButton,[data-testid="stStatusWidget"]{display:none!important;}
section[data-testid="stSidebar"]{display:none!important;}
.block-container{padding-top:0!important;padding-bottom:0!important;}
[data-testid="stVerticalBlockBorderWrapper"]{gap:0!important;}
[data-testid="stVerticalBlock"]{gap:0!important;}
.stApp{background:#0a0a0a;}
</style>""", unsafe_allow_html=True)


# ━━━━━━━ Socket API ━━━━━━━
def _get_token() -> str:
    try:
        return SOCKET_TOKEN_FILE.read_text().strip().split("\n")[0].strip()
    except Exception:
        return ""


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


def gather_fleet_data():
    token = _get_token()
    if not token:
        return [], []
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        s.settimeout(8)
        s.connect(("127.0.0.1", SOCKET_PORT))
        s.sendall((json.dumps({"jsonrpc": "2.0", "id": 0, "method": "auth.handshake",
                                "params": {"token": token}}) + "\n").encode())
        _recv_line(s)
        s.sendall((json.dumps({"jsonrpc": "2.0", "id": 1, "method": "surface.list",
                                "params": {}}) + "\n").encode())
        resp = _recv_line(s)
        surfaces = resp.get("result", {}).get("surfaces", [])
        terminals = [sf for sf in surfaces if sf.get("surfaceType") == "terminal"][:5]
        contents = []
        for i, sf in enumerate(terminals):
            s.sendall((json.dumps({"jsonrpc": "2.0", "id": i + 10,
                                    "method": "surface.read",
                                    "params": {"surfaceId": sf["id"], "lines": 20}
                                    }) + "\n").encode())
            r = _recv_line(s)
            contents.append(r.get("result", {}).get("content", ""))
        s.close()
        return terminals, contents
    except Exception:
        return [], []


# ━━━━━━━ Data processing ━━━━━━━
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\r")


def _strip(text):
    return _ANSI_RE.sub("", text)


def detect_status(content):
    if not content:
        return "offline"
    last = _strip("\n".join(content.strip().split("\n")[-8:])).lower()
    if any(k in last for k in ["error", "failed", "traceback", "exception", "crash"]):
        return "error"
    if any(k in last for k in ["working", "running", "processing", "generating", "searching",
                                "reading", "writing", "editing", "creating", "analyzing",
                                "building", "fetching", "compiling", "levitating"]):
        return "live"
    if any(k in last for k in ["waiting", "idle", "$ ", "❯", "> ", ">>> ",
                                "what would you like", "how can i help"]):
        return "idle"
    return "live"


def get_activity_summary(content):
    if not content:
        return "연결 안 됨"
    lines = [_strip(l).strip() for l in content.strip().split("\n") if _strip(l).strip()]
    if not lines:
        return "대기 중"
    for line in reversed(lines[-10:]):
        low = line.lower()
        if any(skip in low for skip in ["$", "❯", ">>>", "╭", "╰", "───", "```"]):
            continue
        if len(line) > 5:
            return line[:80] + ("…" if len(line) > 80 else "")
    return lines[-1][:80] if lines else "대기 중"


def get_claude_contexts():
    """각 Claude 세션의 마지막 메시지에서 context 사용량 읽기."""
    results = []
    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        return results
    try:
        # Find recently modified .jsonl files (active sessions)
        import glob
        jsonls = []
        for p in projects_dir.rglob("*.jsonl"):
            if "subagent" in str(p):
                continue
            try:
                mtime = p.stat().st_mtime
                size = p.stat().st_size
                if size > 1000:  # skip tiny files
                    jsonls.append((mtime, p))
            except Exception:
                pass
        jsonls.sort(key=lambda x: x[0], reverse=True)

        for _, jf in jsonls[:6]:  # top 6 most recent
            last_usage = None
            session_id = ""
            cwd = ""
            try:
                with open(jf, "r", encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        try:
                            data = json.loads(line)
                            u = data.get("message", {}).get("usage", {})
                            if u and u.get("input_tokens") is not None:
                                last_usage = u
                                session_id = data.get("sessionId", "")[:12]
                                cwd = data.get("cwd", "")
                        except Exception:
                            pass
            except Exception:
                continue
            if last_usage:
                inp = last_usage.get("input_tokens", 0)
                cache_r = last_usage.get("cache_read_input_tokens", 0)
                cache_c = last_usage.get("cache_creation_input_tokens", 0)
                ctx = inp + cache_r + cache_c
                limit = 200_000
                pct = min(100, round(ctx / limit * 100, 1))
                # Derive a short label from cwd
                label = cwd.split("\\")[-1].split("/")[-1] if cwd else jf.stem[:12]
                results.append({"label": label, "ctx": ctx, "limit": limit,
                                "pct": pct, "session": session_id})
    except Exception:
        pass
    return results


def get_system_metrics():
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.3)
        mem = psutil.virtual_memory()
        return {"cpu": cpu, "mem_pct": mem.percent,
                "mem_used": round(mem.used / (1024**3), 1),
                "mem_total": round(mem.total / (1024**3), 1)}
    except Exception:
        return {"cpu": 0, "mem_pct": 0, "mem_used": 0, "mem_total": 0}


# ━━━━━━━ SVG Radar ━━━━━━━
def _radar_svg(active, total, size=120):
    pct = active / max(total, 1)
    cx, cy = size // 2, size // 2
    r = size * 0.36
    sw = size * 0.07
    circ = 2 * math.pi * r
    dash = f"{pct * circ:.1f} {circ:.1f}"
    color = C1 if active > 0 else "#90a4ae"
    ro = int(size * 0.45)

    sweep = ""
    ripples = ""
    if active > 0:
        sweep = f'''<defs><linearGradient id="sw" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stop-color="{C1}" stop-opacity="0.5"/>
          <stop offset="100%" stop-color="{C1}" stop-opacity="0"/>
        </linearGradient></defs>
        <line x1="{cx}" y1="{cy}" x2="{cx}" y2="{cy-ro}"
              stroke="url(#sw)" stroke-width="2" style="transform-origin:{cx}px {cy}px;animation:radar-spin 4s linear infinite;"/>'''
        for i in range(3):
            ripples += f'<circle cx="{cx}" cy="{cy}" r="0" fill="none" stroke="{C1}" stroke-opacity="0.25" style="animation:rp-out 4s ease-out infinite {i*1.5}s;"/>'

    cross = f'''<line x1="{cx}" y1="{cy-ro+5}" x2="{cx}" y2="{cy+ro-5}" stroke="rgba(255,255,255,0.04)" stroke-width="1"/>
    <line x1="{cx-ro+5}" y1="{cy}" x2="{cx+ro-5}" y2="{cy}" stroke="rgba(255,255,255,0.04)" stroke-width="1"/>'''

    ring = f'<circle cx="{cx}" cy="{cy}" r="{ro}" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="1" stroke-dasharray="4 4" style="animation:wave-rot 3s linear infinite;"/>'

    return f'''<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" style="filter:drop-shadow(0 0 12px {color}30);">
      {cross}{ring}{ripples}{sweep}
      <circle cx="{cx}" cy="{cy}" r="{r:.0f}" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="{sw:.0f}"/>
      <circle cx="{cx}" cy="{cy}" r="{r:.0f}" fill="none" stroke="{color}" stroke-width="{sw:.0f}"
              stroke-dasharray="{dash}" stroke-linecap="round" transform="rotate(-90 {cx} {cy})"
              style="filter:drop-shadow(0 0 6px {color});animation:neon-p 2.5s ease-in-out infinite;"/>
      <text x="{cx}" y="{cy-4}" text-anchor="middle" dominant-baseline="central"
            fill="{W}" font-size="{size*0.22:.0f}" font-weight="800" font-family="system-ui,sans-serif">{active}/{total}</text>
      <text x="{cx}" y="{cy+size*0.12:.0f}" text-anchor="middle"
            fill="{G2}" font-size="{size*0.07:.0f}" font-family="system-ui,sans-serif">ACTIVE</text>
    </svg>'''


# ━━━━━━━ Full HTML builder ━━━━━━━
def _esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_full_html(pane_data, metrics, start_time):
    now = datetime.now()
    n_live = sum(1 for _, _, _, s, _ in pane_data if s == "live")
    n_total = len(pane_data)
    elapsed = now - start_time
    h, rem = divmod(int(elapsed.total_seconds()), 3600)
    m, sec = divmod(rem, 60)
    mode_color = "#00e676" if n_live > 0 else "#90a4ae"
    dot_cls = "dot-live" if n_live > 0 else "dot-idle"

    css = f"""
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css');
    *{{margin:0;padding:0;box-sizing:border-box;}}
    html,body{{height:100%;overflow-y:auto;overflow-x:hidden;}}
    body{{background:{BG};color:{W};font-family:'Pretendard Variable','Inter',system-ui,sans-serif;
         padding:8px 10px;width:100%;}}
    .hud{{display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap;}}
    .hud-title{{font-size:16px;font-weight:800;letter-spacing:-.3px;}}
    .hud-time{{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:600;color:{G1};margin-left:auto;}}
    .hud-badge{{font-size:9px;font-weight:700;padding:1px 7px;border-radius:9999px;}}
    .hud-sub{{font-size:10px;color:{G2};margin-bottom:6px;}}
    /* --- Radar + Stats side by side --- */
    .top-row{{display:flex;align-items:center;gap:10px;margin-bottom:6px;}}
    .top-stats{{flex:1;display:flex;flex-direction:column;gap:3px;}}
    .ts-row{{display:flex;align-items:center;gap:6px;}}
    .ts-lbl{{font-size:9px;color:{G3};width:36px;flex-shrink:0;}}
    .ts-val{{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;}}
    /* --- Fleet list --- */
    .fleet-row{{display:flex;align-items:center;gap:6px;padding:5px 8px;
                border-radius:6px;margin-bottom:2px;transition:background 0.2s;}}
    .fleet-row:hover{{background:rgba(255,255,255,0.04);}}
    .fr-icon{{font-size:13px;flex-shrink:0;width:18px;text-align:center;}}
    .fr-name{{font-size:11px;font-weight:700;flex-shrink:0;min-width:0;}}
    .fr-ai{{font-size:8px;font-weight:600;padding:0 5px;border-radius:9999px;
            background:rgba(255,255,255,0.07);color:{G1};flex-shrink:0;}}
    .fr-act{{font-size:9px;color:{G2};flex:1;min-width:0;overflow:hidden;
             text-overflow:ellipsis;white-space:nowrap;}}
    .dot{{width:6px;height:6px;border-radius:50%;display:inline-block;flex-shrink:0;}}
    .dot-live{{background:#00e676;animation:blink 1.4s ease-in-out infinite;}}
    .dot-idle{{background:#90a4ae;}}
    .dot-err{{background:{C_RED};animation:blink 0.8s ease-in-out infinite;}}
    .dot-off{{background:#424242;}}
    .fr-badge{{font-size:8px;font-weight:600;padding:0 6px;border-radius:9999px;flex-shrink:0;}}
    .st-live{{background:rgba(0,230,118,0.12);color:#00e676;}}
    .st-idle{{background:rgba(144,164,174,0.12);color:#90a4ae;}}
    .st-err{{background:rgba(255,82,82,0.12);color:{C_RED};}}
    .st-off{{background:rgba(66,66,66,0.12);color:#616161;}}
    /* --- Bars (system, context) --- */
    .sec-title{{font-size:10px;font-weight:700;color:{G2};margin:8px 0 4px 0;
                text-transform:uppercase;letter-spacing:0.8px;}}
    .bar-row{{display:flex;align-items:center;gap:5px;margin:2px 0;}}
    .bar-lbl{{font-size:9px;color:{G1};flex-shrink:0;min-width:28px;}}
    .bar-tk{{flex:1;height:6px;background:{TK};border-radius:3px;overflow:hidden;}}
    .bar-fl{{height:100%;border-radius:3px;transition:width 0.5s;}}
    .bar-v{{font-family:'JetBrains Mono',monospace;font-size:9px;color:{G2};
            text-align:right;flex-shrink:0;min-width:50px;}}
    .foot{{font-size:8px;color:{G3};margin-top:8px;padding-top:4px;border-top:1px solid {TK};}}
    @keyframes blink{{0%,100%{{opacity:1;}}50%{{opacity:0.3;}}}}
    @keyframes radar-spin{{0%{{transform:rotate(0deg);}}100%{{transform:rotate(360deg);}}}}
    @keyframes rp-out{{
      0%{{r:0;opacity:0.4;stroke-width:1.5;}}
      100%{{r:80;opacity:0;stroke-width:0.3;}}
    }}
    @keyframes wave-rot{{0%{{stroke-dashoffset:0;}}100%{{stroke-dashoffset:-60;}}}}
    @keyframes neon-p{{
      0%,100%{{filter:drop-shadow(0 0 4px {C1}40);}}
      50%{{filter:drop-shadow(0 0 12px {C1}aa);}}
    }}
    ::-webkit-scrollbar{{width:4px;}}
    ::-webkit-scrollbar-track{{background:transparent;}}
    ::-webkit-scrollbar-thumb{{background:rgba(255,255,255,0.10);border-radius:2px;}}
    """

    body = []

    # Header: compact single line
    mode_rgb = "0,230,118" if n_live > 0 else "144,164,174"
    mode_label = "LIVE" if n_live > 0 else "IDLE"
    body.append(f'''
    <div class="hud">
      <span class="dot {dot_cls}"></span>
      <span class="hud-title">Javis Fleet</span>
      <span class="hud-badge" style="color:{mode_color};background:rgba({mode_rgb},0.12);">{mode_label}</span>
      <span class="hud-time">{now.strftime('%H:%M:%S')}</span>
    </div>''')

    # Top row: radar + stats side by side
    radar = _radar_svg(n_live, n_total)
    body.append(f'''
    <div class="top-row">
      <div>{radar}</div>
      <div class="top-stats">
        <div class="ts-row"><span class="ts-lbl">가동</span>
          <span class="ts-val" style="color:{G1}">{h:02d}:{m:02d}:{sec:02d}</span></div>
        <div class="ts-row"><span class="ts-lbl">시작</span>
          <span class="ts-val" style="color:{C1}">{start_time.strftime('%H:%M')}</span></div>
        <div class="ts-row"><span class="ts-lbl">활성</span>
          <span class="ts-val" style="color:{mode_color}">{n_live}/{n_total}</span></div>
      </div>
    </div>''')

    # Fleet list: compact rows
    body.append('<div class="sec-title">Fleet</div>')
    for _, cfg, content, status, activity in pane_data:
        color = cfg["color"]
        dot_c = {"live": "dot-live", "idle": "dot-idle", "error": "dot-err"}.get(status, "dot-off")
        st_c = {"live": "st-live", "idle": "st-idle", "error": "st-err"}.get(status, "st-off")
        st_l = {"live": "LIVE", "idle": "IDLE", "error": "ERR", "offline": "OFF"}.get(status, "?")
        short_name = cfg["key"].split("(")[0].strip()

        body.append(f'''
        <div class="fleet-row">
          <span class="fr-icon">{cfg["icon"]}</span>
          <span class="fr-name" style="color:{color}">{short_name}</span>
          <span class="fr-ai">{cfg["ai"]}</span>
          <span class="fr-act">{_esc(activity)}</span>
          <span class="dot {dot_c}"></span>
          <span class="fr-badge {st_c}">{st_l}</span>
        </div>''')

    # Context / Token usage (compact)
    ctx_data = get_claude_contexts()
    if ctx_data:
        body.append('<div class="sec-title">Context</div>')
        for cd in ctx_data[:4]:
            cp = cd["pct"]
            cc = "#00e676" if cp < 50 else C_GEMINI if cp < 80 else C_RED
            ctx_k = f'{cd["ctx"]//1000}k'
            body.append(f'''
            <div class="bar-row">
              <div class="bar-lbl">{_esc(cd["label"][:8])}</div>
              <div class="bar-tk"><div class="bar-fl" style="width:{cp:.0f}%;background:{cc};"></div></div>
              <div class="bar-v">{ctx_k} ({cp:.0f}%)</div>
            </div>''')

    # System (compact)
    cpu_c = "#00e676" if metrics["cpu"] < 60 else C_GEMINI if metrics["cpu"] < 80 else C_RED
    mem_c = "#00e676" if metrics["mem_pct"] < 70 else C_GEMINI if metrics["mem_pct"] < 90 else C_RED
    body.append(f'''
    <div class="sec-title">System</div>
    <div class="bar-row">
      <div class="bar-lbl">CPU</div>
      <div class="bar-tk"><div class="bar-fl" style="width:{metrics["cpu"]:.0f}%;background:{cpu_c};"></div></div>
      <div class="bar-v">{metrics["cpu"]:.0f}%</div>
    </div>
    <div class="bar-row">
      <div class="bar-lbl">MEM</div>
      <div class="bar-tk"><div class="bar-fl" style="width:{metrics["mem_pct"]:.0f}%;background:{mem_c};"></div></div>
      <div class="bar-v">{metrics["mem_used"]:.1f}/{metrics["mem_total"]:.0f}G</div>
    </div>''')

    # Footer
    body.append(f'<div class="foot">Javis Fleet · {REFRESH_SEC}s · {now.strftime("%H:%M:%S")}</div>')

    return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>{css}</style></head>
<body>{"".join(body)}</body></html>'''


def build_empty_html():
    return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>body{{background:{BG};color:{W};font-family:system-ui,sans-serif;
  display:flex;flex-direction:column;align-items:center;justify-content:center;height:90vh;}}</style>
</head><body>
  <div style="font-size:48px;margin-bottom:16px;">🤖</div>
  <div style="font-size:20px;font-weight:700;margin-bottom:8px;">Javis Fleet 대기 중</div>
  <div style="color:{G2};font-size:13px;text-align:center;">
    마스터 Claude에게 <strong style="color:{C_MASTER};">"너는 마스터다"</strong>를 입력하면<br>
    5-pane fleet이 자동으로 부트스트랩됩니다.
  </div>
</body></html>'''


# ━━━━━━━ Main ━━━━━━━
if "fleet_start" not in st.session_state:
    st.session_state.fleet_start = datetime.now()


@st.fragment(run_every=timedelta(seconds=REFRESH_SEC))
def live_content():
    terminals, contents = gather_fleet_data()

    if not terminals:
        components.html(build_empty_html(), height=400, scrolling=False)
        return

    label_map = {cfg["key"]: cfg for cfg in FLEET}
    pane_data = []
    for i, sf in enumerate(terminals):
        label = sf.get("label") or sf.get("title", "Terminal")
        cfg = label_map.get(label)
        if not cfg:
            for k, v in label_map.items():
                if k.lower() in label.lower():
                    cfg = v
                    break
        if not cfg:
            cfg = {"key": label, "icon": "📦", "color": "#888", "ai": "?", "desc": ""}
        content = contents[i] if i < len(contents) else ""
        status = detect_status(content)
        activity = get_activity_summary(content)
        pane_data.append((sf, cfg, content, status, activity))

    metrics = get_system_metrics()
    html = build_full_html(pane_data, metrics, st.session_state.fleet_start)
    # 컴팩트 HUD: header 50 + radar+stats 130 + fleet 30*N + context 60 + system 50 + footer 30
    est_h = 50 + 130 + len(pane_data) * 30 + 60 + 50 + 30
    components.html(html, height=est_h, scrolling=True)


live_content()
