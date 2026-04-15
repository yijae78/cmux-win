# cmux-win — Windows AI Terminal Multiplexer

> **중요: 당신은 지금 cmux-win 앱 안의 터미널에서 실행 중입니다.**
> cmux-win은 여러 AI CLI를 동시에 실행하고 협업시키는 Windows 터미널 멀티플렉서입니다.
> 옆에 다른 터미널 패널(Gemini, Codex 등)이 있을 수 있으며, tmux-shim을 통해 제어할 수 있습니다.
> 소켓 API(localhost:19840)로 패널 생성, 텍스트 전송, 화면 읽기가 가능합니다.
> 파일 승인은 앱의 Auto-Approver가 자동 처리합니다.

이 프로젝트는 **cmux-win**입니다. Windows용 AI 에이전트 터미널 멀티플렉서로, 여러 AI CLI(Claude, Gemini, Codex 등)를 동시에 실행하고 협업시킬 수 있는 Electron 기반 데스크톱 앱입니다.

## 앱 구조

```
┌──────────┬─────────────────────────────────────┐
│ Sidebar  │  Terminal / Browser Panels           │
│ (200px)  │  (분할 가능, 드래그 재배치)          │
│──────────│                                      │
│ Explorer │  [Claude CLI] [Gemini CLI] [Codex]  │
│ (파일)   │                                      │
│──────────│                                      │
│ 🧠Claude │                                      │
│ 💎Gemini │                                      │
│ 🤖ChatGPT│                                      │
│+Workspace│                                      │
└──────────┴─────────────────────────────────────┘
```

## 핵심 기능

### 1. 터미널 멀티플렉서
- 패널 분할 (좌우/상하), 드래그로 재배치
- 각 터미널에 다른 AI CLI 실행 가능
- 균등 분할 (⊞/⊟ 버튼, Ctrl+Shift+=, Ctrl+Alt+=)
- 터미널 닫으면 자동 레이아웃 정리

### 2. AI CLI 실행 방식 (중요!)
각 CLI는 입력 방식이 다릅니다:

| CLI | 실행 방식 | 이유 |
|-----|----------|------|
| **Claude** | `claude` (interactive) → `send_text`로 작업 지시 | TUI가 PTY write를 입력으로 받음 |
| **Gemini** | `gemini -i "프롬프트" -y` (interactive + 자동승인) | `-i`로 세션 유지, send_text로 후속 작업 전송 (Enter 분리 필요) |
| **Codex** | `codex --full-auto --no-alt-screen "프롬프트"` (interactive) | `--no-alt-screen`으로 scrollback 유지, 세션 지속 |

### 3. 자동 승인 (Auto-Approver)
앱에 내장된 PTY 레벨 자동 승인기가 있습니다:
- "Do you want to create" → 자동 Enter
- "Apply this change" → 자동 Enter (Gemini)
- "Press enter to confirm" → 자동 Enter (Codex)
- "requires approval" → 자동 Enter (Claude)
- 1초 쿨다운으로 중복 방지

### 4. 소켓 API (TCP localhost:19840)
앱의 모든 기능을 JSON-RPC 2.0으로 제어할 수 있습니다:

```
인증: auth.handshake + token (파일: %APPDATA%/Electron/socket-token)

패널 제어:
  panel.list          — 패널 목록
  panel.split         — 패널 분할 (direction, newPanelType, url)
  panel.close         — 패널 닫기
  panel.focus         — 패널 포커스

터미널 제어:
  surface.send_text   — 터미널에 텍스트 전송
  surface.read        — 터미널 화면 읽기 (lines 파라미터)
  surface.list        — 서피스 목록

워크스페이스:
  workspace.list      — 워크스페이스 목록
  workspace.create    — 새 워크스페이스
  workspace.set_layout — 레이아웃 변경 (균등 분할 등)

에이전트:
  agent.spawn         — 에이전트 생성 (패널 + CLI 자동 실행)
```

### 5. 파일 탐색기
- 사이드바 안에 내장 (Ctrl+E 토글)
- 포커스된 터미널의 CWD에 따라 자동 전환
- 폴더 더블클릭 → 터미널에 `cd` 전송
- 프로젝트 탭으로 여러 폴더 전환

### 6. 브라우저 패널
- 사이드바에서 🧠Claude.ai / 💎Gemini / 🤖ChatGPT 클릭 → 브라우저 패널 열기
- claude.ai는 모바일 UA로 반응형 적용

### 7. 텔레그램 봇 연동
- 알림 전달 (outbound) + 원격 제어 (inbound)
- /status, /agents, /approve, /reject 명령
- /send gemini "작업" — 특정 에이전트에 텍스트 전송
- /task "작업" — Claude 리더에게 작업 지시
- Bot token은 Electron safeStorage로 암호화 저장

### 8. Claude CLI 자동 실행
- 앱 시작 시 첫 번째 터미널에 Claude CLI 자동 실행
- Claude Desktop Dispatch 대상이 항상 존재
- 원격(핸드폰)에서 Dispatch → Claude CLI → tmux-shim → 다른 에이전트 제어

## 프로젝트 구조

```
src/
  main/           — Electron main process
    index.ts      — 앱 진입점, IPC, 소켓 서버
    sot/store.ts  — 상태 관리 (immer)
    terminal/     — PTY 관리, 자동 승인
    socket/       — JSON-RPC 서버, 핸들러
    notifications/ — Windows toast, Telegram bot
  preload/        — IPC 브릿지 (ptyBridge, cmuxFile 등)
  renderer/       — React UI
    App.tsx       — 메인 레이아웃
    components/
      panels/     — PanelContainer, PanelLayout, PanelDivider, EdgeDropZone
      sidebar/    — Sidebar, SidebarFooter, WorkspaceItem
      terminal/   — XTermWrapper (xterm.js)
      browser/    — BrowserSurface, NavigationBar
      explorer/   — FileExplorer (파일 트리)
  shared/         — 타입, 액션, 상수, 유틸리티
resources/
  bin/            — claude.cmd, claude-wrapper.js, tmux-shim.js
  shell-integration/ — PowerShell/Bash 셸 통합
```

## 터미널 간 협업 방법

### 소켓 API로 제어하는 예시:
```javascript
// 토큰 읽기
const token = fs.readFileSync(APPDATA + '/Electron/socket-token', 'utf8').split('\n')[0];

// 연결 + 인증
client.connect(19840, '127.0.0.1');
client.write(JSON.stringify({ jsonrpc: '2.0', id: 0, method: 'auth.handshake', token }) + '\n');

// 터미널에 명령 전송
client.write(JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'surface.send_text',
  params: { surfaceId: '...', text: 'claude\r' } }) + '\n');

// 터미널 화면 읽기
client.write(JSON.stringify({ jsonrpc: '2.0', id: 2, method: 'surface.read',
  params: { surfaceId: '...', lines: 10 } }) + '\n');
```

### tmux-shim 명령 (Claude Agent Teams 호환):
```bash
tmux split-window -h          # 패널 분할
tmux send-keys -t %1 "text" Enter  # 텍스트 전송
tmux capture-pane -t %1 -p   # 화면 읽기
tmux list-panes               # 패널 목록
tmux has-session              # 세션 확인
```

## 빌드 & 실행

```bash
# 빌드 (esbuild 사용)
npx esbuild src/main/index.ts --bundle --outfile=out/main/index.js --platform=node --format=cjs --external:electron --external:node-pty --external:better-sqlite3 --external:grammy --external:@grammyjs/auto-retry
npx esbuild src/preload/index.ts --bundle --outfile=out/preload/index.js --platform=node --format=cjs --external:electron
npx esbuild src/renderer/main.tsx --bundle --outfile=out/renderer/assets/index.js --format=esm --loader:.tsx=tsx --loader:.ts=ts --loader:.css=css --jsx=automatic --external:electron

# 실행
npx electron out/main/index.js

# 테스트
npx vitest run
```

## 주의사항
- `electron-vite build`는 현재 main 단계 후 멈추는 이슈 있음 → esbuild 직접 사용
- Gemini CLI에 `send_text`로 텍스트 전달 안 됨 → `-p "prompt" -y` 인자 방식 사용
- Codex CLI도 동일 → `--full-auto "prompt"` 사용
- claude.ai 웹은 데스크톱 반응형 CSS 없음 → 모바일 UA 적용
- 소켓 토큰은 앱 시작마다 새로 생성됨 (경로: %APPDATA%/Electron/socket-token)
