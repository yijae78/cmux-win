# cmux-win

**Windows AI Terminal Multiplexer** — 여러 AI CLI(Claude, Gemini, Codex 등)를 동시에 실행하고 협업시키는 Electron 기반 데스크톱 앱

![Electron](https://img.shields.io/badge/Electron-33-47848F?logo=electron&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![xterm.js](https://img.shields.io/badge/xterm.js-5.x-000000)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows&logoColor=white)

```
┌──────────┬──────────────────────────────────────────┐
│ Sidebar  │  🧠 Claude  │  💎 Gemini  │  🤖 Codex   │
│──────────│─────────────│────────────│──────────────│
│ Explorer │  > _        │  $ gemini  │  >_ codex    │
│ (파일)   │  Claude CLI │  Gemini CLI│  Codex CLI   │
│──────────│  interactive│  -p "task" │  --full-auto │
│ Claude.ai│             │            │              │
│ Gemini   │             │            │              │
│ ChatGPT  │             │            │              │
│+Workspace│             │            │              │
└──────────┴──────────────────────────────────────────┘
```

## 주요 기능

### 터미널 멀티플렉서
- **패널 분할** — 좌우/상하 분할, 드래그로 재배치
- **균등 분할** — ⊞/⊟ 버튼 또는 `Ctrl+Shift+=` / `Ctrl+Alt+=`
- **AI CLI 자동 감지** — 터미널에서 Claude/Gemini/Codex 실행 시 탭에 아이콘+이름 자동 표시
- **자동 레이아웃 정리** — 터미널 닫으면 남은 패널 자동 재배치

### AI CLI 통합

| CLI | 실행 방식 | 비고 |
|-----|----------|------|
| **Claude** | `claude` (interactive) → `send_text`로 작업 지시 | TUI가 PTY write를 입력으로 받음 |
| **Gemini** | `gemini -p "프롬프트" -y` | ink TUI 특성상 인자 방식만 지원 |
| **Codex** | `codex --full-auto "프롬프트"` | ink TUI 특성상 인자 방식만 지원 |

### 자동 승인 (Auto-Approver)
PTY 출력에서 승인 패턴을 감지하여 자동 Enter 전송:
- `Do you want to create` / `requires approval` → Enter
- `Apply this change` → Enter (Gemini)
- `Press enter to confirm` → Enter (Codex)
- 1초 쿨다운으로 중복 방지

### 소켓 API (JSON-RPC 2.0)
`TCP localhost:19840`으로 앱의 모든 기능을 프로그래밍 방식으로 제어:

```
인증:     auth.handshake + token (%APPDATA%/Electron/socket-token)

패널:     panel.list / panel.split / panel.close / panel.focus
터미널:   surface.send_text / surface.read / surface.list
워크스페이스: workspace.list / workspace.create / workspace.set_layout
에이전트:  agent.spawn (패널 + CLI 자동 실행)
```

### tmux-shim (Claude Agent Teams 호환)
```bash
tmux split-window -h              # 패널 분할
tmux send-keys -t %1 "text" Enter # 텍스트 전송
tmux capture-pane -t %1 -p        # 화면 읽기
tmux list-panes                   # 패널 목록
```
> 환경변수: `CMUX_SOCKET_TOKEN`, `CMUX_SURFACE_ID` 필요

### 사이드바
- **파일 탐색기** — `Ctrl+E` 토글, 포커스 터미널 CWD 자동 추적
- **브라우저 패널** — Claude.ai / Gemini / ChatGPT 웹 접속
- **워크스페이스** — 여러 작업 환경 전환

### 텔레그램 봇 연동
- 알림 전달 (outbound) + 원격 제어 (inbound)
- `/status`, `/approve`, `/reject`, `/send`, `/agents`, `/help`
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
    index.ts         — 앱 진입점, IPC, 소켓 서버
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
      terminal/      — XTermWrapper (xterm.js + CLI 자동 감지)
      browser/       — BrowserSurface, NavigationBar
      explorer/      — FileExplorer (파일 트리)
  shared/            — 타입, 액션, 상수, 유틸리티
resources/
  icon.png           — 앱 아이콘 (256x256)
  icon.ico           — Windows 아이콘 (멀티사이즈)
  bin/               — claude.cmd, claude-wrapper.js, tmux-shim.js
  shell-integration/ — PowerShell/Bash 셸 통합
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
| 보안 | Electron safeStorage, 소켓 토큰 인증 |

## 개발 로드맵

### 완료
- 터미널 멀티플렉서 (패널 분할, 드래그 재배치, 균등 분할)
- AI CLI 통합 (Claude/Gemini/Codex 동시 실행, 탭 자동 감지)
- tmux-shim (Claude Agent Teams 호환, 14개 명령 구현)
- 소켓 API (JSON-RPC 2.0, 토큰 인증)
- 자동 승인 (Auto-Approver, 1초 쿨다운)
- 텔레그램 봇 (원격 알림 + 제어)
- 파일 탐색기, 브라우저 패널, 앱 아이콘

### 진행 예정 (구현계획 v6)

| 단계 | 내용 | 상태 |
|------|------|------|
| 0 | **tmux-shim 자동 감지** — 토큰/포트 파일 자동 읽기, Dispatch 원격 제어 기반 | 예정 |
| 1 | **Gemini/Codex interactive 모드** — `-i`/`--no-alt-screen` 플래그 전환, 에이전트 세션 유지 | 예정 |
| 2 | **agent.send_task RPC** — interactive 에이전트에 후속 작업 전송, 동시성 방어 | 예정 |
| 3 | **isTTY 검증 + auto-approver 패턴 보강** | 예정 |
| 4 | **Claude CLI 자동 실행** — 앱 시작 시 Dispatch 대상 확보 | 예정 |
| 5 | **텔레그램 원격 제어 강화** — `/send agent "task"`, `/task` 명령 | 예정 |

### 원격 접속 경로

```
1. Claude Desktop Dispatch → Claude CLI → tmux-shim → 씨윈 패널 제어
2. Telegram Bot → /send, /agents, /approve → 소켓 API
3. Socket API (TCP 19840) → JSON-RPC 2.0 직접 제어
```

### cmux(macOS) 대비 호환성

| 기능 | 달성율 |
|------|--------|
| 멀티 AI 동시 실행 | 100% |
| 패널 제어 (split, resize, close) | 100% |
| 에이전트 → 다른 패널 읽기/쓰기 | 100% |
| Dispatch 원격 제어 | 100% (0단계 후) |
| Agent Teams 자동 협업 | 검증 중 |

## 주의사항

- `electron-vite build`는 main 단계 후 멈추는 이슈 → esbuild 직접 사용
- Gemini CLI: `-i` 플래그로 interactive 유지, `send_text`로 후속 작업 전송 (Enter 분리 필요)
- Codex CLI: `--full-auto --no-alt-screen`으로 interactive 유지
- claude.ai 웹은 데스크톱 반응형 CSS 없음 → 모바일 UA 적용
- 소켓 토큰은 앱 시작마다 재생성 (`%APPDATA%/Electron/socket-token` 또는 `%APPDATA%/cmux-win/socket-token`)
- 싱글 인스턴스 잠금 — 동시에 1개만 실행 가능

## 라이선스

MIT
