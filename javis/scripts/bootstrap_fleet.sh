#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Javis Fleet Bootstrap — "너는 마스터다" 트리거
# Master → CSO → Worker1(Claude) → Worker2(AGY) → Worker3(Codex) → Dashboard 순서
# 총 6-pane 구성 (5터미널 + 1대시보드 브라우저)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set -uo pipefail  # -e 제거: Socket API 실패가 전체를 죽이지 않도록
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
JAVIS_DIR="$(dirname "$SCRIPT_DIR")"
MAPPING_FILE="$JAVIS_DIR/fleet_mapping.env"
LOG_DIR="$JAVIS_DIR/logs"
LOG_FILE="$LOG_DIR/fleet_bootstrap_$(date +%Y%m%d_%H%M%S).log"
DASHBOARD="$JAVIS_DIR/dashboard.py"

mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

# ── Socket API 설정 (함수보다 먼저 선언) ──
SOCKET_TOKEN_FILE="$HOME/AppData/Roaming/cmux-win/socket-token"
# 포트를 socket-token 파일 line 2에서 동적 읽기 (하드코딩 금지)
if [ -f "$SOCKET_TOKEN_FILE" ] && [ "$(wc -l < "$SOCKET_TOKEN_FILE")" -ge 2 ]; then
    SOCKET_PORT=$(sed -n '2p' "$SOCKET_TOKEN_FILE" | tr -d '[:space:]')
else
    SOCKET_PORT=19840
fi
export SOCKET_PORT  # Python 내장 스크립트에서 os.environ으로 접근
log "Socket port: $SOCKET_PORT"

# ── 패널 균등 분할 함수 (workspace.set_layout — 수평/수직 모두 균등화) ──
equalize_panels() {
    sleep 1
    PYTHONIOENCODING=utf-8 python3 << 'EQUALIZE_EOF'
import socket, json, pathlib, os, time, sys

token_path = pathlib.Path(os.path.expanduser("~")) / "AppData" / "Roaming" / "cmux-win" / "socket-token"
try:
    lines = token_path.read_text().strip().split('\n')
    token = lines[0].strip()
    port = int(lines[1].strip()) if len(lines) > 1 else int(os.environ.get('SOCKET_PORT', '19840'))
except:
    print("equalize: token read fail", file=sys.stderr)
    sys.exit(1)

def equalize_ratios(node):
    """기존 레이아웃 트리의 방향(horizontal/vertical)은 보존하고, 모든 ratio를 균등화"""
    if node.get('type') == 'leaf':
        return node
    children = node.get('children', [])
    if len(children) != 2:
        return node
    left_leaves = count_leaves(children[0])
    right_leaves = count_leaves(children[1])
    total = left_leaves + right_leaves
    node['ratio'] = left_leaves / total  # 리프 수에 비례한 균등 비율
    node['children'] = [equalize_ratios(c) for c in children]
    return node

def count_leaves(node):
    if node.get('type') == 'leaf':
        return 1
    return sum(count_leaves(c) for c in node.get('children', []))

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(10)
try:
    s.connect(('127.0.0.1', port))
    s.sendall((json.dumps({'jsonrpc':'2.0','id':0,'method':'auth.handshake','params':{'token':token}}) + '\n').encode())
    time.sleep(0.5); s.recv(4096)
    # 현재 레이아웃 읽기
    s.sendall((json.dumps({'jsonrpc':'2.0','id':2,'method':'workspace.list','params':{}}) + '\n').encode())
    time.sleep(0.5); ws = json.loads(s.recv(32768).decode('utf-8')).get('result',{}).get('workspaces',[])
    if ws:
        layout = ws[0].get('panelLayout', {})
        n = count_leaves(layout)
        if n <= 1:
            sys.exit(0)
        equalized = equalize_ratios(layout)
        s.sendall((json.dumps({'jsonrpc':'2.0','id':3,'method':'workspace.set_layout','params':{'workspaceId':ws[0]['id'],'panelLayout':equalized}}) + '\n').encode())
        time.sleep(0.5); s.recv(4096)
        print(f'equalized {n} panels (preserved directions)')
except Exception as e:
    print(f'equalize ERROR: {e}', file=sys.stderr)
finally:
    s.close()
EQUALIZE_EOF
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
    lines = token_path.read_text().strip().split('\n')
    token = lines[0].strip()
    port = int(lines[1].strip()) if len(lines) > 1 else int(os.environ.get('SOCKET_PORT', '19840'))
except:
    print("token 없음 — 건너뜀")
    exit(0)
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
try:
    s.connect(('127.0.0.1', port))
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
log "패널 순서: 마스터 → CSO → Worker1(Claude) → Worker2(AGY) → Worker3(Codex) → Dashboard"

# ── 0. 대시보드 실행 (가장 먼저) ──
log "[0] Javis Dashboard 실행..."
PID=$(netstat -ano 2>/dev/null | grep "0.0.0.0:8500" | awk '{print $5}' | head -1)
if [ -n "$PID" ] && [ "$PID" != "0" ]; then
    cmd.exe //c "taskkill /F /PID $PID" 2>/dev/null || true
    log "  기존 대시보드 종료 (PID: $PID)"
    sleep 1
fi
nohup streamlit run "$DASHBOARD" --server.headless true --server.port 8500 > "$LOG_DIR/dashboard.log" 2>&1 &
DASH_PID=$!
sleep 3
if kill -0 "$DASH_PID" 2>/dev/null; then
    log "  대시보드 시작 (PID: $DASH_PID) — http://localhost:8500"
else
    log "  [WARN] 대시보드 프로세스 시작 실패 — 로그 확인: $LOG_DIR/dashboard.log"
fi

# ── 워커 생성 + 검증 함수 (시나리오2+3 교훈 반영) ──
# 시나리오3 Fix: 인라인 명령(tmux split-window -h "cmd") 대신
#   2단계 방식(쉘 열기 → send-keys 명령 전송)으로 AGY/Codex 자동 시작 실패 해결
spawn_worker() {
    local STEP="$1"
    local TOTAL="$2"
    local NAME="$3"
    local CMD="$4"
    local MAX_RETRY=3
    local ATTEMPT=0

    while [ "$ATTEMPT" -lt "$MAX_RETRY" ]; do
        ATTEMPT=$((ATTEMPT + 1))
        log "[$STEP/$TOTAL] $NAME 생성 (시도 $ATTEMPT/$MAX_RETRY)..."
        BEFORE=$(tmux list-panes -F '#{pane_id}' | wc -l)

        # [시나리오3 Fix] 2단계 방식: 빈 쉘 열기 → send-keys로 명령 전송
        # 인라인 방식(split-window -h "agy")은 Git Bash에서 간헐 실패
        tmux split-window -h
        sleep 1
        AFTER=$(tmux list-panes -F '#{pane_id}' | wc -l)
        NEW_PANE=$(tmux list-panes -F '#{pane_id}' | tail -1)

        if [ "$AFTER" -gt "$BEFORE" ]; then
            # 쉘이 열렸으면 명령 전송
            tmux send-keys -t "$NEW_PANE" "$CMD" Enter
            sleep 2

            # CLI 로딩 대기 (최대 15초 — AGY는 초기화가 느림)
            CLI_OK=0
            for i in $(seq 1 15); do
                SCREEN=$(tmux capture-pane -t "$NEW_PANE" -p 2>/dev/null | tail -5)
                if echo "$SCREEN" | grep -qiE "(claude|agy|codex|gemini|what would|how can|type your|>|\\$|tips for)"; then
                    CLI_OK=1
                    break
                fi
                sleep 1
            done
            if [ "$CLI_OK" = "1" ]; then
                log "  $NAME pane: $NEW_PANE (CLI 확인됨)"
                echo "$NEW_PANE"
                return 0
            else
                log "  [WARN] $NAME CLI 로딩 미확인 — 패널은 생성됨: $NEW_PANE"
                echo "$NEW_PANE"
                return 0
            fi
        fi
        log "  [RETRY] $NAME 패널 생성 실패 — 재시도 $ATTEMPT/$MAX_RETRY"
        sleep 2
    done
    log "  [ERROR] $NAME 생성 $MAX_RETRY회 실패"
    echo ""
    return 1
}

# ── 파일 기반 장문 프롬프트 전달 (시나리오3 Fix: Codex/AGY send-keys 장문 실패 해결) ──
# 사용법: send_long_prompt <pane_id> <prompt_text>
# 200자 이하 → 직접 send-keys, 초과 → 파일 → cat으로 전달
PROMPT_DIR="$JAVIS_DIR/tmp/prompts"
mkdir -p "$PROMPT_DIR"

send_long_prompt() {
    local PANE="$1"
    local PROMPT="$2"
    local PROMPT_LEN=${#PROMPT}

    if [ "$PROMPT_LEN" -le 200 ]; then
        # 짧은 프롬프트: 직접 전송
        tmux send-keys -t "$PANE" "$PROMPT" Enter
    else
        # 장문 프롬프트: 파일 기반 전달
        local PROMPT_FILE="$PROMPT_DIR/prompt_$(date +%s)_$$.txt"
        printf '%s' "$PROMPT" > "$PROMPT_FILE"
        log "  장문 프롬프트 파일: $PROMPT_FILE ($PROMPT_LEN chars)"
        # CLI에 cat 파이프로 전달 (Codex/AGY 모두 표준입력 지원)
        tmux send-keys -t "$PANE" "cat \"$PROMPT_FILE\"" Enter
        sleep 1
        # 파일 정리는 세션 종료 시 (tmp/prompts/ 전체 삭제)
    fi
}

# ── 동적 워커 생성 함수 (시나리오3+ 확장 시 사용) ──
# 사용법: spawn_dynamic_worker <name> <ai_type> [prompt]
# ai_type: claude | agy | codex
spawn_dynamic_worker() {
    local NAME="$1"
    local AI_TYPE="$2"
    local PROMPT="${3:-}"
    local CMD=""
    local PANE_COUNT=$(tmux list-panes -F '#{pane_id}' | wc -l)
    local STEP=$((PANE_COUNT + 1))

    case "$AI_TYPE" in
        claude)
            # [시나리오3 Fix] Claude 워커는 반드시 --dangerously-skip-permissions
            CMD="claude --dangerously-skip-permissions"
            ;;
        agy)
            CMD="agy"
            ;;
        codex)
            CMD="codex -a full-auto --no-alt-screen"
            ;;
        *)
            log "[ERROR] 미지원 AI 타입: $AI_TYPE"
            return 1
            ;;
    esac

    local NEW_PANE=$(spawn_worker "$STEP" "$STEP" "$NAME" "$CMD")
    if [ -z "$NEW_PANE" ]; then
        log "[ERROR] 동적 워커 $NAME 생성 실패"
        return 1
    fi

    equalize_panels

    # 프롬프트가 있으면 전달
    if [ -n "$PROMPT" ]; then
        sleep 2
        send_long_prompt "$NEW_PANE" "$PROMPT"
    fi

    echo "$NEW_PANE"
    return 0
}

# ── 1. CSO pane ──
CSO_PANE=$(spawn_worker 1 4 "CSO(Claude)" "claude --dangerously-skip-permissions")
equalize_panels

# ── 2. Worker1(Claude) pane ──
W1_PANE=$(spawn_worker 2 4 "Worker1(Claude)" "claude --dangerously-skip-permissions")
equalize_panels

# ── 3. Worker2(AGY) pane ──
AGY_PANE=$(spawn_worker 3 4 "Worker2(AGY)" "agy")
equalize_panels

# ── 4. Worker3(Codex) pane ──
CODEX_PANE=$(spawn_worker 4 4 "Worker3(Codex)" "codex -a never --no-alt-screen")
equalize_panels

# ── 라벨 설정 (panel.list → surface.rename 직접 호출) ──
log "=== 패널 라벨 설정 ==="
sleep 3  # 패널 생성 안정화 대기

python3 << 'LABEL_EOF'
import socket, json, pathlib, os, time, sys

token_path = pathlib.Path(os.path.expanduser("~")) / "AppData" / "Roaming" / "cmux-win" / "socket-token"
try:
    lines = token_path.read_text().strip().split('\n')
    token = lines[0].strip()
    port = int(lines[1].strip()) if len(lines) > 1 else int(os.environ.get('SOCKET_PORT', '19840'))
except:
    print("ERROR: socket-token 읽기 실패", file=sys.stderr)
    sys.exit(1)

labels = ["Master", "CSO", "Worker1(Claude)", "Worker2(AGY)", "Worker3(Codex)"]

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(10)
try:
    s.connect(('127.0.0.1', port))
    s.sendall((json.dumps({'jsonrpc':'2.0','id':0,'method':'auth.handshake','params':{'token':token}}) + '\n').encode())
    time.sleep(0.5); s.recv(4096)

    s.sendall((json.dumps({'jsonrpc':'2.0','id':1,'method':'panel.list','params':{}}) + '\n').encode())
    time.sleep(0.5); data = s.recv(16384).decode('utf-8')
    panels = json.loads(data).get('result',{}).get('panels',[])

    ok_count = 0
    for i, p in enumerate(panels):
        if i < len(labels):
            # BUG FIX: surfaceId는 panelId가 아니라 activeSurfaceId를 사용해야 함
            surface_id = p.get('activeSurfaceId', p['id'])
            req = json.dumps({'jsonrpc':'2.0','id':i+10,'method':'surface.rename','params':{'surfaceId':surface_id,'label':labels[i]}})
            s.sendall((req + '\n').encode())
            time.sleep(0.3); r = s.recv(4096).decode('utf-8')
            if 'true' in r:
                ok_count += 1
                print(f"  [{i}] '{labels[i]}' OK (surface={surface_id[:12]})")
            else:
                print(f"  [{i}] '{labels[i]}' FAIL: {r[:60]}", file=sys.stderr)
    print(f"label {ok_count}/{len(labels)} done")
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
finally:
    s.close()
LABEL_EOF
log "  라벨 설정 단계 완료"

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
lines = token_path.read_text().strip().split('\n')
token = lines[0].strip()
port = int(lines[1].strip()) if len(lines) > 1 else int(os.environ.get('SOCKET_PORT', '19840'))

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(10)
s.connect(('127.0.0.1', port))
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
equalize_panels

# ── 매핑 저장 ──
cat > "$MAPPING_FILE" << EOF
# Javis Fleet Mapping — $(date '+%Y-%m-%d %H:%M:%S')
# 순서: 마스터 → CSO → Worker1(Claude) → Worker2(AGY) → Worker3(Codex) → Dashboard
# 대시보드: http://localhost:8500
CSO=$CSO_PANE
WORKER1=$W1_PANE
WORKER2_AGY=$AGY_PANE
WORKER3_CODEX=$CODEX_PANE
DASHBOARD=browser:8500
SOCKET_PORT=$SOCKET_PORT
EOF

# ── 최종 균등 분할 (안정화 후 재시도) ──
log "=== 최종 균등 분할 ==="
sleep 3
equalize_panels

log "=== Fleet Bootstrap 완료 (총 6-pane: 5터미널 + 1대시보드 브라우저) ==="
log "매핑 저장: $MAPPING_FILE"
cat "$MAPPING_FILE"
