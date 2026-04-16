# cmux-win

**Windows AI Terminal Multiplexer** — 여러 AI CLI(Claude, Gemini, Codex 등)를 동시에 실행하고 협업시키는 Electron 기반 데스크톱 앱

![Electron](https://img.shields.io/badge/Electron-33-47848F?logo=electron&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![xterm.js](https://img.shields.io/badge/xterm.js-5.x-000000)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows&logoColor=white)

```
┌──────────┬──────────────────────────────────────────────────┐
│ Sidebar  │  🧠 Claude (Opus) │ 💎 Gemini │ 🤖 Codex         │
│──────────│───────────────────│───────────│──────────────────│
│ Explorer │  > _              │  > gemini │  >_ codex        │
│ (파일)   │  Claude CLI       │  Gemini   │  Codex CLI       │
│──────────│  interactive      │  -i mode  │  --full-auto     │
│ Claude.ai│                   │           │                  │
│ Gemini   │                   │           │                  │
│ ChatGPT  │                   │           │                  │
│+Workspace│                   │           │                  │
└──────────┴──────────────────────────────────────────────────┘
```

## 주요 기능

### 터미널 멀티플렉서
- **패널 분할** — 좌우/상하 분할, 드래그로 재배치
- **균등 분할** — ⊞/⊟ 버튼 또는 `Ctrl+Shift+=` / `Ctrl+Alt+=`
- **자동 레이아웃 정리** — 터미널 닫으면 남은 패널 자동 재배치
- **사이드바 토글** — ◀ 버튼으로 닫기, 왼쪽 세로 바(▶) 호버 시 파란색으로 다시 열기

### AI CLI 자동 감지 + 모델명 표시
xterm.js 터미널 버퍼에서 CLI 출력을 분석하여 탭 제목에 자동 표시:

| CLI | 탭 제목 | 모델명 자동 감지 |
|-----|---------|------------------|
| **Claude** | 🧠 Claude (Opus) / (Sonnet) / (Haiku) | 배너 `Opus 4.6` 등에서 추출 |
| **Gemini** | 💎 Gemini | — |
| **Codex** | 🤖 Codex | — |
| **ChatGPT** | 💬 ChatGPT | — |

CLI 전환 시 5초 쿨다운 후 재감지 (Claude → Gemini 변경 시 탭 자동 변경).

### AI CLI 실행 방식

| CLI | 실행 명령 | 비고 |
|-----|----------|------|
| **Claude** | `claude` (interactive) → `send_text`로 작업 지시 | TUI가 PTY write를 입력으로 받음 |
| **Gemini** | `gemini -i "프롬프트" -y` (interactive + 자동승인) | 작업 후 세션 유지 |
| **Codex** | `codex --full-auto --no-alt-screen "프롬프트"` | scrollback 유지 |

### 협업 규칙 (필수 준수)
1. 새 터미널은 반드시 `tmux split-window -h` (-v 절대 금지)
2. Claude 중복 실행 금지 — 리더 1개면 충분
3. /슬래시 명령(예: `/model`)을 `send-keys`로 전송 금지 (셸이 경로로 해석함)
4. 인라인 명령 사용: `tmux split-window -h "gemini -i \"작업\" -y"`

### 자동 승인 (Auto-Approver)
PTY 출력에서 승인 패턴을 감지하여 자동 Enter 전송:
- `Do you want to create` / `requires approval` → Enter
- `Apply this change` → Enter (Gemini)
- `Press enter to confirm` → Enter (Codex)
- 1초 쿨다운으로 중복 방지

### Claude CLI 자동 실행
앱 시작 시 첫 번째 워크스페이스에 Claude CLI가 자동 실행됩니다.
- Claude Desktop Dispatch 대상이 항상 존재
- 원격(핸드폰) → Dispatch → Claude CLI → tmux-shim → 다른 에이전트 제어 가능

### Cowork Bridge (파일시스템 우편함)
외부 프로세스가 파일을 통해 씨윈 패널에 작업 주입 + 결과 회수:

```
%USERPROFILE%/cmux-bridge/
├── inbox/         ← 외부에서 *.task.json 드롭
├── outbox/        ← {id}.result.json 결과 기록
├── processed/     ← 완료된 task 이동
└── heartbeat.json ← 30초마다 alive 신호 + 패널/에이전트 상태
```

**Task 스키마**:
```json
{
  "id": "uuid",
  "target_panel": 0,
  "prompt": "작업 지시문",
  "mode": "leader" | "direct",
  "timeout_sec": 600,
  "created_at": "ISO8601"
}
```

- `mode: "leader"` → Claude를 리더로 활용하는 prefix 자동 추가
- 종결 조건: `===BRIDGE_DONE===` / `작업완료` / `DONE` 마커 + 3초 idle, 또는 timeout
- OneDrive 동기화 가능 (hostname lock으로 원격 중복 방지)

**사용 예**:
```bash
echo '{"id":"t1","target_panel":0,"prompt":"hello","mode":"direct","timeout_sec":30,"created_at":"2026-04-16T00:00:00Z"}' \
  > ~/cmux-bridge/inbox/t1.task.json
# → ~/cmux-bridge/outbox/t1.result.json 에 결과 생성
```

### 소켓 API (JSON-RPC 2.0)
`TCP localhost:19840`으로 앱의 모든 기능을 프로그래밍 방식으로 제어:

```
인증:     auth.handshake + token (%APPDATA%/Electron/socket-token)

패널:     panel.list / panel.split / panel.close / panel.focus
터미널:   surface.send_text / surface.read / surface.list
워크스페이스: workspace.list / workspace.create / workspace.set_layout
에이전트:  agent.spawn (패널 + CLI 자동 실행)
텔레그램:  telegram.set_token / telegram.test
```

### tmux-shim (Claude Agent Teams 호환)
```bash
tmux split-window -h              # 패널 분할 (기본값 horizontal, -v 사용 금지)
tmux split-window -h "gemini -i \"task\" -y"  # 인라인 명령
tmux send-keys -t %1 "text" Enter # 텍스트 전송 (슬래시 명령 금지)
tmux capture-pane -t %1 -p        # 화면 읽기
tmux list-panes                   # 패널 목록
```
> 환경변수 자동 감지: `CMUX_SOCKET_TOKEN`, `CMUX_SURFACE_ID` 또는 토큰 파일 fallback

### 사이드바
- **파일 탐색기** — `Ctrl+E` 또는 ⌂ 아이콘 토글, 포커스 터미널 CWD 자동 추적
- **브라우저 패널** — Claude.ai / Gemini / ChatGPT 웹 접속
- **워크스페이스** — 여러 작업 환경 전환

### 텔레그램 봇 연동
- 알림 전달 (outbound) + 원격 제어 (inbound)
- `/status`, `/agents`, `/approve`, `/reject`, `/help`
- `/send <text>` — 활성 에이전트에 텍스트 전송
- `/send claude|gemini|codex <text>` — 특정 에이전트에 전송
- `/task <text>` — Claude 리더에게 작업 지시
- Bot token은 Electron safeStorage로 암호화 저장

## 빌드 & 실행

```bash
# 빌드 (esbuild)
npx esbuild src/main/index.ts --bundle --outfile=out/main/index.js \
  --platform=node --format=cjs \
  --external:electron --external:node-pty --external:better-sqlite3 \
  --external:grammy --external:@grammyjs/auto-retry

npx esbuild src/preload/index.ts --bundle --outfile=out/preload/index.js \
  --platform=node --format=cjs --external:electron

npx esbuild src/renderer/main.tsx --bundle --outfile=out/renderer/assets/index.js \
  --format=esm --loader:.tsx=tsx --loader:.ts=ts --loader:.css=css \
  --jsx=automatic --external:electron

# 실행
npx electron out/main/index.js

# 테스트
npx vitest run
```

## 바탕화면 바로가기

```powershell
$project = "C:\path\to\cmux-win"
$electron = "$project\node_modules\electron\dist\electron.exe"
$s = (New-Object -COM WScript.Shell).CreateShortcut("$env:USERPROFILE\Desktop\cmux-win.lnk")
$s.TargetPath = $electron
$s.Arguments = "out/main/index.js"
$s.WorkingDirectory = $project
$s.IconLocation = "$electron,0"
$s.Save()
```

## 프로젝트 구조

```
src/
  main/              — Electron main process
    index.ts         — 앱 진입점, IPC, 소켓 서버, Bridge Watcher
    bridge-watcher.ts — Cowork Bridge (파일시스템 우편함)
    sot/store.ts     — 상태 관리 (immer)
    terminal/        — PTY 관리, 자동 승인
    socket/          — JSON-RPC 서버, 핸들러
    notifications/   — Windows toast, Telegram bot
  preload/           — IPC 브릿지 (ptyBridge, cmuxFile 등)
  renderer/          — React UI
    App.tsx          — 메인 레이아웃
    components/
      panels/        — PanelContainer, PanelLayout, PanelDivider
      sidebar/       — Sidebar, SidebarFooter, WorkspaceItem
      terminal/      — XTermWrapper (xterm.js + CLI/모델 자동 감지)
      browser/       — BrowserSurface, NavigationBar
      explorer/      — FileExplorer (파일 트리, CWD 자동 추적)
  shared/            — 타입, 액션, 상수, 유틸리티
resources/
  icon.png           — 앱 아이콘 (256x256)
  icon.ico           — Windows 아이콘 (멀티사이즈)
  bin/               — claude.cmd, claude-wrapper.js, tmux-shim.js
  shell-integration/ — PowerShell/Bash 셸 통합 (OSC 7 CWD 전송)
scripts/
  generate_icon.py   — 앱 아이콘 생성 스크립트 (Pillow)
```

## 기술 스택

| 영역 | 기술 |
|------|------|
| 프레임워크 | Electron 33 |
| 프론트엔드 | React 19, TypeScript |
| 터미널 | xterm.js 5, node-pty |
| 상태 관리 | immer |
| 번들러 | esbuild |
| 테스트 | Vitest |
| 알림 | grammY (Telegram), Windows Toast |
| 보안 | Electron safeStorage, 소켓 토큰 인증, hostname lock |

## 개발 로드맵

### 완료 (구현계획 v6 + v7)
- 터미널 멀티플렉서 (패널 분할, 드래그 재배치, 균등 분할)
- AI CLI 통합 (Claude/Gemini/Codex 동시 실행, 탭 자동 감지)
- **모델명 자동 감지** — Claude (Opus/Sonnet/Haiku) 표시
- **CLI 전환 재감지** — 5초 쿨다운 후 재확인
- tmux-shim (Claude Agent Teams 호환, 14개 명령 구현)
- **split-window 기본값 horizontal** — `-v` 사용 금지 정책
- 소켓 API (JSON-RPC 2.0, 토큰 인증)
- 자동 승인 (Auto-Approver, 1초 쿨다운)
- 텔레그램 봇 (원격 알림 + 제어, `/task` `/send` 명령)
- 파일 탐색기, 브라우저 패널, 앱 아이콘
- **Claude CLI 자동 실행** — 앱 시작 시 Dispatch 대상 확보
- **Cowork Bridge Watcher** — 파일시스템 우편함, hostname lock
- **사이드바 토글** — absolute wrapper로 레이아웃 보존, ▶ 호버 바

### 원격 접속 경로

```
1. Claude Desktop Dispatch → Claude CLI → tmux-shim → 씨윈 패널 제어
2. Telegram Bot → /send, /agents, /approve, /task → 소켓 API
3. Socket API (TCP 19840) → JSON-RPC 2.0 직접 제어
4. Cowork Bridge → 파일시스템 우편함 (inbox/outbox) ← 비동기 + OneDrive 호환
```

### cmux(macOS) 대비 호환성

| 기능 | 달성율 |
|------|--------|
| 멀티 AI 동시 실행 | 100% |
| 패널 제어 (split, resize, close) | 100% |
| 에이전트 → 다른 패널 읽기/쓰기 | 100% |
| Dispatch 원격 제어 | 100% |
| 모델명 자동 감지/전환 | 95% (재감지 검증 중) |
| Agent Teams 자동 협업 | 검증 중 |
| 비동기 우편함 (Bridge) | 100% (cmux-win 전용) |

## 주의사항

- `electron-vite build`는 main 단계 후 멈추는 이슈 → esbuild 직접 사용
- Gemini CLI: `-i "prompt" -y` 형식, interactive 유지
- Codex CLI: `--full-auto --no-alt-screen` 으로 scrollback 유지
- claude.ai 웹은 데스크톱 반응형 CSS 없음 → 모바일 UA 적용
- 소켓 토큰은 앱 시작마다 재생성 (`%APPDATA%/Electron/socket-token` 또는 `%APPDATA%/cmux-win/socket-token`)
- 싱글 인스턴스 잠금 — 동시에 1개만 실행 가능
- /슬래시 명령(예: `/model sonnet`)은 해당 CLI TUI 입력창에서만 동작 — `tmux send-keys`로 전달 불가 (셸이 경로로 해석)

## 라이선스

MIT
