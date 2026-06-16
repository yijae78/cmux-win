#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Javis Fleet Bootstrap — "너는 마스터다" 트리거
# Master → CSO → Worker1(AGY) → Worker2(AGY) → Worker3(Codex) 순서
# 총 5개 pane 구성 (마스터 기존 유지)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
JAVIS_DIR="$(dirname "$SCRIPT_DIR")"
MAPPING_FILE="$JAVIS_DIR/fleet_mapping.env"
LOG_DIR="$JAVIS_DIR/logs"
LOG_FILE="$LOG_DIR/fleet_bootstrap_$(date +%Y%m%d_%H%M%S).log"
DASHBOARD="$JAVIS_DIR/dashboard.py"

mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

# ── Socket API helper ──
SOCKET_TOKEN_FILE="$HOME/AppData/Roaming/cmux-win/socket-token"
SOCKET_PORT=19840

cmux_api() {
    local method="$1"
    local params="$2"
    local token
    token=$(cat "$SOCKET_TOKEN_FILE" 2>/dev/null || echo "")
    if [ -z "$token" ]; then
        log "  [WARN] socket-token 없음 — 라벨 설정 건너뜀"
        return 1
    fi
    # Auth handshake + method call
    python3 -c "
import socket, json, sys
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
try:
    s.connect(('127.0.0.1', $SOCKET_PORT))
    # Auth
    auth = json.dumps({'jsonrpc':'2.0','id':0,'method':'auth.handshake','params':{'token':'$token'}})
    s.sendall((auth + '\n').encode())
    s.recv(4096)
    # API call
    req = json.dumps({'jsonrpc':'2.0','id':1,'method':'$method','params':$params})
    s.sendall((req + '\n').encode())
    resp = s.recv(4096).decode()
    print(resp)
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
finally:
    s.close()
" 2>/dev/null
}

set_label() {
    local surface_id="$1"
    local label="$2"
    cmux_api "surface.rename" "{\"surfaceId\":\"$surface_id\",\"label\":\"$label\"}" >/dev/null 2>&1 || true
}

get_surface_ids() {
    # 모든 surface ID를 순서대로 반환
    local token
    token=$(cat "$SOCKET_TOKEN_FILE" 2>/dev/null || echo "")
    if [ -z "$token" ]; then return 1; fi
    python3 -c "
import socket, json
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
try:
    s.connect(('127.0.0.1', $SOCKET_PORT))
    auth = json.dumps({'jsonrpc':'2.0','id':0,'method':'auth.handshake','params':{'token':'$token'}})
    s.sendall((auth + '\n').encode())
    s.recv(4096)
    req = json.dumps({'jsonrpc':'2.0','id':1,'method':'surface.list','params':{}})
    s.sendall((req + '\n').encode())
    resp = json.loads(s.recv(8192).decode())
    for sf in resp.get('result',{}).get('surfaces',[]):
        print(sf['id'])
except:
    pass
finally:
    s.close()
" 2>/dev/null
}

# ── 멱등성 가드 ──
PANE_COUNT=$(tmux list-panes 2>/dev/null | wc -l)
if [ "$PANE_COUNT" -gt 2 ] && [ "${FORCE:-0}" != "1" ]; then
    log "[GUARD] 이미 워커 pane ${PANE_COUNT}개 존재. 재구축: FORCE=1 bash $0"
    exit 2
fi

# ── 유령 패널 정리 (Ghost Panel Cleanup) ──
log "[PRE] 유령 패널 정리..."
python3 << 'GHOST_CLEANUP'
import socket, json, pathlib, os, time
token_path = pathlib.Path(os.path.expanduser("~")) / "AppData" / "Roaming" / "cmux-win" / "socket-token"
try:
    token = token_path.read_text().strip().split('\n')[0].strip()
except:
    print("token 없음 — 건너뜀")
    exit(0)
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
try:
    s.connect(('127.0.0.1', 19840))
    s.sendall((json.dumps({'jsonrpc':'2.0','id':0,'method':'auth.handshake','params':{'token':token}}) + '\n').encode())
    time.sleep(0.3); s.recv(4096)
    # 패널 목록
    s.sendall((json.dumps({'jsonrpc':'2.0','id':1,'method':'panel.list','params':{}}) + '\n').encode())
    time.sleep(0.3); panels = json.loads(s.recv(16384).decode()).get('result',{}).get('panels',[])
    live_ids = {p['id'] for p in panels}
    # 워크스페이스 레이아웃
    s.sendall((json.dumps({'jsonrpc':'2.0','id':2,'method':'workspace.list','params':{}}) + '\n').encode())
    time.sleep(0.3); wss = json.loads(s.recv(16384).decode()).get('result',{}).get('workspaces',[])
    for ws in wss:
        layout = ws.get('panelLayout',{})
        def collect(node):
            if node.get('type')=='leaf': return [node.get('panelId','')]
            return collect(node['children'][0]) + collect(node['children'][1])
        leaf_ids = collect(layout)
        ghosts = [lid for lid in leaf_ids if lid not in live_ids]
        if ghosts:
            # Master 패널만 남기는 clean layout
            master_id = panels[0]['id'] if panels else leaf_ids[0]
            clean = {'type':'leaf','panelId':master_id}
            s.sendall((json.dumps({'jsonrpc':'2.0','id':3,'method':'workspace.set_layout','params':{'workspaceId':ws['id'],'panelLayout':clean}}) + '\n').encode())
            time.sleep(0.3); s.recv(4096)
            print(f"유령 {len(ghosts)}개 제거, layout 리셋")
        else:
            print("유령 없음")
    s.close()
except Exception as e:
    print(f"cleanup 건너뜀: {e}")
GHOST_CLEANUP

log "=== Javis Fleet Bootstrap 시작 (총 6-pane 구성: 5터미널 + 1대시보드) ==="
log "패널 순서: Master → CSO → Worker1(AGY) → Worker2(AGY) → Worker3(Codex) → Dashboard(browser)"

# ── 0. 대시보드 실행 (가장 먼저) ──
log "[0] Javis Dashboard 실행..."
PID=$(netstat -ano 2>/dev/null | grep "0.0.0.0:8500" | awk '{print $5}' | head -1)
if [ -n "$PID" ] && [ "$PID" != "0" ]; then
    cmd.exe //c "taskkill /F /PID $PID" 2>/dev/null || true
    log "  기존 대시보드 종료 (PID: $PID)"
    sleep 1
fi
powershell.exe -Command "Start-Process -WindowStyle Hidden streamlit -ArgumentList 'run','$DASHBOARD','--server.port','8500','--server.headless','true'" &
sleep 2
# 엣지 브라우저 열지 않음 — cmux-win 브라우저 패널로만 표시
log "  대시보드: http://localhost:8500 (cmux-win 패널 전용)"

# ── 1. CSO pane (2번 — 마스터 바로 옆) ──
log "[1/4] CSO pane 생성 (Claude Code)..."
tmux split-window -h "claude --dangerously-skip-permissions"
sleep 1
CSO_PANE=$(tmux list-panes -F '#{pane_id}' | tail -1)
log "  CSO pane: $CSO_PANE"

# ── 2. Worker1(AGY) pane (3번) ──
log "[2/4] Worker1(AGY) pane 생성 (Claude Code)..."
tmux split-window -h "claude --dangerously-skip-permissions"
sleep 1
AGY_PANE=$(tmux list-panes -F '#{pane_id}' | tail -1)
log "  Worker1(AGY) pane: $AGY_PANE"

# ── 3. Worker2(AGY) pane (4번) ──
log "[3/4] Worker2(AGY) pane 생성..."
tmux split-window -h "agy"
sleep 1
AGY2_PANE=$(tmux list-panes -F '#{pane_id}' | tail -1)
log "  Worker2(AGY) pane: $AGY2_PANE"

# ── 4. Worker3(Codex) pane (5번) ──
log "[4/4] Worker3(Codex) pane 생성..."
tmux split-window -h "codex --full-auto --no-alt-screen"
sleep 1
CODEX_PANE=$(tmux list-panes -F '#{pane_id}' | tail -1)
log "  Worker3(Codex) pane: $CODEX_PANE"

# ── 라벨 설정 (Socket API) ──
log "=== 패널 라벨 설정 ==="
sleep 2  # 패널 생성 안정화 대기

SURFACE_IDS=($(get_surface_ids))
SURFACE_COUNT=${#SURFACE_IDS[@]}
log "  Surface 수: $SURFACE_COUNT"

if [ "$SURFACE_COUNT" -ge 5 ]; then
    set_label "${SURFACE_IDS[0]}" "마스터(claude)"
    set_label "${SURFACE_IDS[1]}" "CSO(claude)"
    set_label "${SURFACE_IDS[2]}" "Worker1(AGY)"
    set_label "${SURFACE_IDS[3]}" "Worker2(AGY)"
    set_label "${SURFACE_IDS[4]}" "Worker3(Codex)"
    log "  라벨 설정 완료: 마스터(claude), CSO(claude), Worker1(AGY), Worker2(AGY), Worker3(Codex)"
elif [ "$SURFACE_COUNT" -gt 0 ]; then
    LABELS=("마스터(claude)" "CSO(claude)" "Worker1(AGY)" "Worker2(AGY)" "Worker3(Codex)")
    for i in "${!SURFACE_IDS[@]}"; do
        if [ "$i" -lt "${#LABELS[@]}" ]; then
            set_label "${SURFACE_IDS[$i]}" "${LABELS[$i]}"
        fi
    done
    log "  라벨 설정 완료 (${SURFACE_COUNT}개)"
else
    log "  [WARN] Surface 조회 실패 — 라벨 수동 설정 필요"
fi

# ── 6번째 패널: 대시보드 (브라우저) ──
log "[5/5] Dashboard 브라우저 패널 생성..."
sleep 2

# 대시보드가 준비될 때까지 대기 (최대 15초)
DASH_READY=0
for i in $(seq 1 15); do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8500 2>/dev/null | grep -q "200"; then
        DASH_READY=1
        break
    fi
    sleep 1
done

if [ "$DASH_READY" = "1" ]; then
    # Socket API로 브라우저 패널 생성 (panel.split RPC 직접 호출) + 라벨 설정
    python3 << 'PYEOF'
import socket, json, pathlib, os, time
token_path = pathlib.Path(os.path.expanduser("~")) / "AppData" / "Roaming" / "cmux-win" / "socket-token"
token = token_path.read_text().strip().split('\n')[0].strip()

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(10)
s.connect(('127.0.0.1', 19840))
s.sendall((json.dumps({'jsonrpc':'2.0','id':0,'method':'auth.handshake','params':{'token':token}}) + '\n').encode())
time.sleep(0.3)
s.recv(4096)

# panel.list로 마지막 패널 ID 가져오기
s.sendall((json.dumps({'jsonrpc':'2.0','id':1,'method':'panel.list','params':{}}) + '\n').encode())
time.sleep(0.3)
data = s.recv(16384).decode('utf-8')
panels = json.loads(data).get('result',{}).get('panels',[])

if panels:
    last_panel_id = panels[-1]['id']
    # panel.split RPC로 브라우저 패널 생성 (dispatch가 아닌 직접 호출)
    split_req = json.dumps({
        'jsonrpc':'2.0','id':2,'method':'panel.split',
        'params':{
            'panelId': last_panel_id,
            'direction': 'horizontal',
            'newPanelType': 'browser',
            'url': 'http://localhost:8500'
        }
    }) + '\n'
    s.sendall(split_req.encode())
    time.sleep(1)
    r = s.recv(4096).decode('utf-8')
    result = json.loads(r).get('result',{})
    new_surface_id = result.get('surfaceId','')
    print(f"Dashboard panel: paneIndex={result.get('paneIndex')}, surfaceId={new_surface_id[:12]}")

    # Dashboard 라벨 설정
    if new_surface_id:
        time.sleep(0.5)
        rename_req = json.dumps({
            'jsonrpc':'2.0','id':3,'method':'surface.rename',
            'params':{'surfaceId': new_surface_id, 'label': 'Dashboard'}
        }) + '\n'
        s.sendall(rename_req.encode())
        time.sleep(0.3)
        s.recv(4096)
        print(f"Dashboard label set: {new_surface_id[:12]}")

s.close()
PYEOF
    log "  Dashboard 브라우저 패널 생성 완료"
else
    log "  [WARN] Dashboard 미응답 — 외부 브라우저로 대체"
    start "" "http://localhost:8500"
fi

# ── 매핑 저장 ──
cat > "$MAPPING_FILE" << EOF
# Javis Fleet Mapping — $(date '+%Y-%m-%d %H:%M:%S')
# 순서: Master → CSO → Worker1(AGY) → Worker2(AGY) → Worker3(Codex) → Dashboard
# 대시보드: http://localhost:8500
CSO=$CSO_PANE
AGY=$AGY_PANE
AGY2=$AGY2_PANE
CODEX=$CODEX_PANE
DASHBOARD=browser:8500
EOF

# ── 패널 균등 크기 조정 ──
log "=== 패널 균등 크기 조정 ==="
sleep 1
python3 << 'PYEOF'
import socket, json, pathlib, os, time
token_path = pathlib.Path(os.path.expanduser("~")) / "AppData" / "Roaming" / "cmux-win" / "socket-token"
token = token_path.read_text().strip().split('\n')[0].strip()
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(10)
s.connect(('127.0.0.1', 19840))
s.sendall((json.dumps({'jsonrpc':'2.0','id':0,'method':'auth.handshake','params':{'token':token}}) + '\n').encode())
time.sleep(0.3)
s.recv(4096)
s.sendall((json.dumps({'jsonrpc':'2.0','id':1,'method':'panel.list','params':{}}) + '\n').encode())
time.sleep(0.3)
data = s.recv(16384).decode('utf-8')
resp = json.loads(data)
panels = resp.get('result',{}).get('panels',[])
ratio = round(1.0 / max(len(panels), 1), 4)
for i, p in enumerate(panels):
    req = json.dumps({'jsonrpc':'2.0','id':i+10,'method':'panel.resize','params':{'panelId':p['id'],'ratio':ratio}})
    s.sendall((req + '\n').encode())
    time.sleep(0.2)
    s.recv(4096)
s.close()
print(f"Equalized {len(panels)} panels at ratio {ratio}")
PYEOF
log "  패널 균등화 완료"

log "=== Fleet Bootstrap 완료 (총 6-pane: 5터미널 + 1대시보드 브라우저) ==="
log "매핑 저장: $MAPPING_FILE"
cat "$MAPPING_FILE"
