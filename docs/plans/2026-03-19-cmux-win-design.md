# cmux-win 설계안 v2 (수정본)

> 최종 수정: 2026-03-19
> 상태: 논의 중 — 승인 전 구현 불가
> 절대 기준: 품질과 질적 수준 최우선. 속도/비용 무시.

---

## 1. 프로젝트 비전

cmux-win은 macOS용 cmux의 **모든 지능을 Windows에서 동일하게 실행**하는 AI 에이전트 오케스트레이션 플랫폼이다.

핵심 가치:
- Claude Code가 리더로서 Gemini/Codex를 팀원처럼 호출하는 멀티 에이전트 환경
- 터미널 + 브라우저 + 마크다운이 하나의 워크스페이스에 통합된 분할 패널 UI
- 소켓 API로 모든 것을 프로그래밍적으로 제어 가능
- cmux와 동일한 프로토콜/명령 체계 (호환성)

---

## 2. 아키텍처 원칙

### 2.1 역할 분리 (성찰 #1 반영)

```
앱(cmux-win) = 인프라 플랫폼
  - 패널 생성/관리, IPC, 상태 관리, UI 제공
  - 에이전트를 위한 환경을 만들어주는 것이 역할

Claude Code = Orchestrator (리더)
  - 터미널 패널 안에서 실행
  - tmux shim을 통해 패널을 생성하고 팀원을 스폰
  - 작업 분배, 결과 수집, 품질 판단은 Claude가 수행

Gemini/Codex = Worker (팀원)
  - Claude가 스폰한 터미널 패널에서 독립 실행
  - Hook 시스템으로 상태가 앱에 보고됨
```

### 2.2 SOT (Source of Truth) 원칙 (성찰 #2 반영)

```
단일 진실 소스 = Main Process의 AppStateStore

규칙:
1. 모든 상태 변경은 Action Dispatch를 통해서만 발생
2. Renderer는 읽기 전용 구독자 (직접 변경 불가)
3. CLI/Socket도 동일한 Action 경로로 진입
4. 모든 Action은 로깅됨 (디버그 추적 가능)
5. 상태 변경 → 미들웨어 체인 → 영구저장 + IPC 브로드캐스트
```

### 2.3 품질 원칙

```
1. TypeScript strict mode (noImplicitAny, strictNullChecks, 전부 ON)
2. 모든 공개 함수에 Zod 스키마 기반 런타임 검증
3. 테스트 없는 코드는 커밋 불가
4. 에러는 삼키지 않고 복구하거나 명시적으로 전파
5. 성능 예산: 키 입력 → 화면 반영 16ms 이내
```

---

## 3. 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                        cmux-win                              │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              Main Process (인프라 플랫폼)                │  │
│  │                                                        │  │
│  │  ┌─────────────────────────────────────────────────┐   │  │
│  │  │            AppStateStore (SOT)                   │   │  │
│  │  │                                                 │   │  │
│  │  │  AppState {                                     │   │  │
│  │  │    windows:        WindowState[]                │   │  │
│  │  │    workspaces:     WorkspaceState[]             │   │  │
│  │  │    panels:         PanelState[]                 │   │  │
│  │  │    surfaces:       SurfaceState[]               │   │  │
│  │  │    agents:         AgentSessionState[]          │   │  │
│  │  │    notifications:  NotificationState[]          │   │  │
│  │  │    settings:       SettingsState                │   │  │
│  │  │    shortcuts:      ShortcutState                │   │  │
│  │  │    session:        SessionSnapshot              │   │  │
│  │  │  }                                              │   │  │
│  │  │                                                 │   │  │
│  │  │  Action Dispatcher                              │   │  │
│  │  │    → Validation Middleware                      │   │  │
│  │  │    → State Mutation (Immer)                     │   │  │
│  │  │    → Persistence Middleware (디바운스 JSON 저장)  │   │  │
│  │  │    → IPC Broadcast Middleware (Renderer 동기화)  │   │  │
│  │  │    → Audit Log Middleware (디버그 추적)          │   │  │
│  │  └─────────────────────────────────────────────────┘   │  │
│  │                                                        │  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌───────────────┐  │  │
│  │  │ Terminal      │ │ Browser      │ │ Socket API    │  │  │
│  │  │ Manager      │ │ Manager      │ │ Server        │  │  │
│  │  │              │ │              │ │               │  │  │
│  │  │ node-pty     │ │ WebContents  │ │ TCP localhost │  │  │
│  │  │ (ConPTY)     │ │ View         │ │ JSON-RPC v2   │  │  │
│  │  │              │ │ (Electron30+)│ │               │  │  │
│  │  │ Shell        │ │ Profile      │ │ Auth Layer    │  │  │
│  │  │ Integration  │ │ Isolation    │ │ (password/    │  │  │
│  │  │ (PS/CMD/WSL) │ │ History(SQL) │ │  ACL modes)   │  │  │
│  │  └──────────────┘ └──────────────┘ └───────────────┘  │  │
│  │                                                        │  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌───────────────┐  │  │
│  │  │ Hook System  │ │ Session      │ │ Notification  │  │  │
│  │  │              │ │ Persistence  │ │ Manager       │  │  │
│  │  │ claude.cmd   │ │              │ │               │  │  │
│  │  │ claude.ps1   │ │ JSON snapshot│ │ Windows Toast │  │  │
│  │  │ codex wrapper│ │ Auto-save    │ │ In-app badge  │  │  │
│  │  │ tmux.cmd shim│ │ Restore      │ │ Tray icon     │  │  │
│  │  └──────────────┘ └──────────────┘ └───────────────┘  │  │
│  │                                                        │  │
│  │  ┌──────────────┐ ┌──────────────┐                    │  │
│  │  │ Error        │ │ Performance  │                    │  │
│  │  │ Recovery     │ │ Monitor      │                    │  │
│  │  │              │ │              │                    │  │
│  │  │ PTY restart  │ │ Key latency  │                    │  │
│  │  │ WebView      │ │ IPC overhead │                    │  │
│  │  │ respawn      │ │ Frame budget │                    │  │
│  │  │ Session heal │ │ 16ms gate    │                    │  │
│  │  └──────────────┘ └──────────────┘                    │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              Renderer Process (UI)                      │  │
│  │                                                        │  │
│  │  ┌──────────┐ ┌─────────────┐ ┌─────────────────────┐ │  │
│  │  │ Sidebar  │ │ Panel       │ │ Command Palette     │ │  │
│  │  │          │ │ Layout      │ │                     │ │  │
│  │  │ 워크스페이│ │ Manager     │ │ 퍼지 검색            │ │  │
│  │  │ 스 목록   │ │             │ │ 스위처              │ │  │
│  │  │ 상태 뱃지 │ │ 분할/리사이즈│ │ 명령 실행            │ │  │
│  │  │ 드래그    │ │ 줌/최대화   │ │                     │ │  │
│  │  │ 알림 뱃지 │ │ 탭 관리     │ │                     │ │  │
│  │  └──────────┘ └─────────────┘ └─────────────────────┘ │  │
│  │                                                        │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │                Panel Renderers                    │  │  │
│  │  │                                                  │  │  │
│  │  │  ┌─────────────┐ ┌──────────┐ ┌──────────────┐  │  │  │
│  │  │  │ xterm.js    │ │ Browser  │ │ Markdown     │  │  │  │
│  │  │  │ (WebGL)     │ │ Panel UI │ │ Panel        │  │  │  │
│  │  │  │             │ │          │ │              │  │  │  │
│  │  │  │ React 렌더  │ │ Omnibar  │ │ Live preview │  │  │  │
│  │  │  │ 사이클에서   │ │ History  │ │ File watch   │  │  │  │
│  │  │  │ 완전 분리   │ │ Find     │ │ Syntax HL    │  │  │  │
│  │  │  │             │ │ DevTools │ │              │  │  │  │
│  │  │  └─────────────┘ └──────────┘ └──────────────┘  │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                 CLI (cmux-win.exe)                      │  │
│  │  TCP localhost 클라이언트 → JSON-RPC v2 프로토콜         │  │
│  │  cmux 호환 명령 체계 (list-workspaces, send, notify...) │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ════════════════════════════════════════════════════════    │
│  AI 에이전트 계층 (앱 위에서 실행, 앱이 인프라 제공)           │
│                                                              │
│  Claude Code (리더) ← 터미널 패널 안에서 실행                 │
│    │  tmux.cmd shim을 통해 앱을 제어                         │
│    │  Hook 시스템으로 세션 상태가 SOT에 반영                   │
│    │                                                        │
│    ├─ "tmux split-window -h"                                │
│    │   → cmux-win이 가로채서 새 터미널 패널 생성               │
│    │   → Claude가 send-keys로 Codex 실행                    │
│    │                                                        │
│    ├─ Codex (팀원) ← 분할된 터미널 패널에서 독립 실행          │
│    │   Hook 시스템으로 상태 추적                               │
│    │                                                        │
│    └─ Gemini (팀원) ← 다른 패널에서 독립 실행                  │
│        Hook 시스템으로 상태 추적                               │
│  ════════════════════════════════════════════════════════    │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 기술 스택 상세

### 4.1 핵심 기술

| 계층 | 기술 | 버전 | 선택 이유 |
|------|------|------|----------|
| 런타임 | Electron | 30+ | WebContentsView, 멀티윈도우 성숙 |
| 언어 | TypeScript | 5.4+ | strict mode 전체 활성화 |
| UI | React | 19+ | 생태계, 커뮤니티, 컴포넌트 재사용 |
| 터미널 | xterm.js | 5.x | WebGL addon, ConPTY 검증됨 |
| PTY | node-pty | 1.x | ConPTY 바인딩, Electron 호환 |
| 브라우저 | WebContentsView | Electron 내장 | BrowserView 후속, 공식 API |
| SOT | 커스텀 스토어 + Immer | — | Main Process에서 React 의존성 제거 |
| 런타임 검증 | Zod | 3.x | Action payload, 소켓 입력 검증 |
| DB (브라우저 히스토리) | better-sqlite3 | — | 동기 SQLite, node-pty와 충돌 없음 |
| IPC (외부) | TCP localhost | — | WSL 호환, 디버깅 용이, cmux 프로토콜 호환 |
| CLI | Node.js SEA 또는 pkg | — | 단일 실행 파일 배포 |
| 빌드 | electron-builder | — | Windows 인스톨러, 자동 업데이트 |
| 자동 업데이트 | electron-updater | — | GitHub Releases 연동 |
| 다국어 | i18next | — | 한/영/일 + 확장 가능 |

### 4.2 테스트 기술

| 레벨 | 도구 | 대상 |
|------|------|------|
| Unit | Vitest | SOT, Action, 미들웨어, 유틸리티, 프로토콜 파서 |
| Integration | Vitest + electron-mock-ipc | IPC, Socket API, Hook 시스템, 세션 퍼시스턴스 |
| E2E | Playwright (Electron 모드) | 전체 UI 워크플로우, 에이전트 오케스트레이션 |
| Terminal I/O | 커스텀 PTY 하네스 | ConPTY 입출력, 이스케이프 시퀀스 |
| Browser API | Playwright | 브라우저 자동화 P0/P1 명령 |
| Performance | 커스텀 벤치마크 | 키 입력 지연, IPC 오버헤드, 프레임 예산 |

### 4.3 개발 도구

| 도구 | 용도 |
|------|------|
| ESLint (flat config) | 코드 품질 강제 |
| Prettier | 포맷 통일 |
| Husky + lint-staged | pre-commit 테스트/린트 강제 |
| commitlint | 커밋 메시지 규칙 |
| GitHub Actions | CI/CD 파이프라인 |

---

## 5. SOT (Source of Truth) 상세 설계

### 5.1 상태 구조

```typescript
// shared/types.ts — Main과 Renderer가 공유하는 타입 정의

interface AppState {
  // 윈도우 계층
  windows: WindowState[];

  // 워크스페이스 계층
  workspaces: WorkspaceState[];

  // 패널 계층 (터미널/브라우저/마크다운)
  panels: PanelState[];

  // 서피스 계층 (패널 내 개별 탭)
  surfaces: SurfaceState[];

  // AI 에이전트 세션
  agents: AgentSessionState[];

  // 알림
  notifications: NotificationState[];

  // 설정
  settings: SettingsState;

  // 키보드 단축키
  shortcuts: ShortcutState;

  // 포커스 상태
  focus: FocusState;
}

interface WindowState {
  id: string;              // UUID
  workspaceIds: string[];  // 순서 있는 워크스페이스 목록
  geometry: WindowGeometry;
  isActive: boolean;
}

interface WorkspaceState {
  id: string;
  windowId: string;
  name: string;
  color?: string;
  panelLayout: PanelLayoutTree; // 분할 트리 구조
  agentPids: Record<string, number>; // "claude_code" → PID
  statusEntries: StatusEntry[];
  unreadCount: number;
  isPinned: boolean;
  remoteSession?: RemoteSessionState;
}

// 분할 패널 트리 (재귀 구조)
type PanelLayoutTree =
  | { type: 'leaf'; panelId: string }
  | { type: 'split'; direction: 'horizontal' | 'vertical';
      ratio: number; children: [PanelLayoutTree, PanelLayoutTree] };

interface PanelState {
  id: string;
  workspaceId: string;
  panelType: 'terminal' | 'browser' | 'markdown';
  surfaceIds: string[];   // 탭 목록
  activeSurfaceId: string;
  isZoomed: boolean;
}

interface SurfaceState {
  id: string;
  panelId: string;
  surfaceType: 'terminal' | 'browser' | 'markdown';
  title: string;
  // 터미널 전용
  terminal?: { pid: number; cwd: string; shell: string };
  // 브라우저 전용
  browser?: { url: string; profileId: string; isLoading: boolean };
  // 마크다운 전용
  markdown?: { filePath: string };
}

interface AgentSessionState {
  sessionId: string;
  agentType: 'claude' | 'codex' | 'gemini' | 'opencode';
  workspaceId: string;
  surfaceId: string;
  status: 'running' | 'idle' | 'needs_input';
  pid?: number;
  lastActivity: number;   // timestamp
}

interface FocusState {
  activeWindowId: string | null;
  activeWorkspaceId: string | null;
  activePanelId: string | null;
  activeSurfaceId: string | null;
  focusTarget: 'terminal' | 'browser_webview' | 'browser_omnibar'
             | 'browser_find' | 'terminal_find' | null;
}

interface SettingsState {
  appearance: {
    theme: 'system' | 'light' | 'dark';
    language: string;
  };
  terminal: {
    defaultShell: string;    // powershell, cmd, wsl, git-bash
    fontSize: number;
    fontFamily: string;
    ghosttyTheme: string;
  };
  browser: {
    searchEngine: 'google' | 'duckduckgo' | 'bing' | 'kagi' | 'startpage';
    searchSuggestions: boolean;
    httpAllowlist: string[];
  };
  socket: {
    mode: 'off' | 'cmux-only' | 'automation' | 'password' | 'allow-all';
    port: number;            // TCP localhost 포트
  };
  agents: {
    claudeHooksEnabled: boolean;
    codexHooksEnabled: boolean;
    geminiHooksEnabled: boolean;
  };
  telemetry: {
    enabled: boolean;
  };
  updates: {
    autoCheck: boolean;
    channel: 'stable' | 'nightly';
  };
}
```

### 5.2 Action 시스템

```typescript
// main/sot/actions.ts

// 모든 Action은 Zod 스키마로 검증됨
type Action =
  // 워크스페이스
  | { type: 'workspace.create'; payload: { windowId: string; name?: string; cwd?: string } }
  | { type: 'workspace.close'; payload: { workspaceId: string } }
  | { type: 'workspace.select'; payload: { workspaceId: string } }
  | { type: 'workspace.rename'; payload: { workspaceId: string; name: string } }
  | { type: 'workspace.reorder'; payload: { workspaceId: string; index: number } }
  | { type: 'workspace.move_to_window'; payload: { workspaceId: string; windowId: string } }

  // 패널
  | { type: 'panel.split'; payload: { panelId: string; direction: 'h' | 'v';
      newPanelType: PanelType } }
  | { type: 'panel.close'; payload: { panelId: string } }
  | { type: 'panel.resize'; payload: { panelId: string; ratio: number } }
  | { type: 'panel.zoom'; payload: { panelId: string } }
  | { type: 'panel.focus'; payload: { panelId: string } }

  // 서피스
  | { type: 'surface.create'; payload: { panelId: string; surfaceType: SurfaceType } }
  | { type: 'surface.close'; payload: { surfaceId: string } }
  | { type: 'surface.focus'; payload: { surfaceId: string } }
  | { type: 'surface.move'; payload: { surfaceId: string; targetPanelId: string } }
  | { type: 'surface.reorder'; payload: { surfaceId: string; index: number } }
  | { type: 'surface.send_text'; payload: { surfaceId: string; text: string } }
  | { type: 'surface.send_key'; payload: { surfaceId: string; key: string } }

  // 에이전트
  | { type: 'agent.session_start'; payload: AgentSessionPayload }
  | { type: 'agent.status_update'; payload: { sessionId: string; status: AgentStatus } }
  | { type: 'agent.session_end'; payload: { sessionId: string } }
  | { type: 'agent.set_pid'; payload: { workspaceId: string; agentType: string; pid: number } }
  | { type: 'agent.clear_pid'; payload: { workspaceId: string; agentType: string } }

  // 알림
  | { type: 'notification.create'; payload: NotificationPayload }
  | { type: 'notification.clear'; payload: { workspaceId?: string } }

  // 브라우저
  | { type: 'browser.navigate'; payload: { surfaceId: string; url: string } }
  | { type: 'browser.back'; payload: { surfaceId: string } }
  | { type: 'browser.forward'; payload: { surfaceId: string } }

  // 설정
  | { type: 'settings.update'; payload: Partial<SettingsState> }
  | { type: 'shortcuts.update'; payload: { action: string; shortcut: string } }

  // 포커스
  | { type: 'focus.update'; payload: Partial<FocusState> };
```

### 5.3 미들웨어 체인

```
Action 수신
  │
  ▼
┌──────────────────────┐
│ 1. Validation        │ Zod 스키마로 payload 검증
│    실패 시 에러 반환   │ 잘못된 ID, 범위 초과 등 차단
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 2. State Mutation    │ Immer produce()로 불변 상태 갱신
│    이전 상태 보존     │ 디버그용 상태 히스토리 유지 (최근 100개)
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 3. Side Effects      │ Action 타입별 부수효과 실행
│                      │ - workspace.create → node-pty 프로세스 생성
│                      │ - surface.close → PTY kill
│                      │ - browser.navigate → WebContentsView loadURL
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 4. Persistence       │ 디바운스(500ms) JSON 스냅샷 저장
│                      │ %APPDATA%/cmux-win/session.json
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 5. IPC Broadcast     │ 변경된 상태 슬라이스를 모든 Renderer에 전송
│    디바운스(16ms)     │ requestAnimationFrame 단위
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 6. Audit Log         │ Action + timestamp + 이전/이후 diff
│    (DEBUG 빌드만)     │ 파일 로그: %TEMP%/cmux-win-debug.log
└──────────────────────┘
```

---

## 6. AI 에이전트 오케스트레이션 상세 설계

### 6.1 사용자 워크플로우 (성찰 #4 반영)

```
Step 1: 사용자가 cmux-win 실행
        → 터미널 패널 열림 (기본 셸: PowerShell)

Step 2: 터미널에서 "cmux-win claude-teams" 입력
        → Claude Code 실행 (--teammate-mode auto)
        → PATH에 tmux.cmd shim 주입
        → CMUX_SOCKET_PATH, CMUX_SURFACE_ID 환경변수 설정
        → Hook 시스템 활성화

Step 3: 사용자가 Claude에게 작업 지시
        "이 프로젝트를 분석하고, Codex에게 테스트 작성을 시키고,
         Gemini에게 문서를 업데이트하게 해줘"

Step 4: Claude가 tmux 명령으로 팀원 스폰
        $ tmux split-window -h
          → cmux-win이 tmux.cmd shim으로 가로챔
          → Socket API: surface.split { direction: 'horizontal' }
          → SOT: 새 터미널 패널 생성
          → UI: 오른쪽에 새 패널 나타남

        $ tmux send-keys -t 1 "codex --task 'write tests'" Enter
          → cmux-win이 가로챔
          → Socket API: surface.send_text { surfaceId, text }
          → Codex가 새 패널에서 실행 시작

        $ tmux split-window -v
          → 아래에 또 다른 패널 생성
        $ tmux send-keys -t 2 "gemini --task 'update docs'" Enter
          → Gemini가 실행 시작

Step 5: 사이드바 상태 실시간 반영
        ┌─────────────────┐
        │ 📁 my-project    │
        │   ⚡ Claude      │ Running
        │   ⚡ Codex       │ Running
        │   ⚡ Gemini      │ Running
        └─────────────────┘

Step 6: Codex 완료
        → Hook: session stop
        → SOT: agent.status_update { status: 'idle' }
        → 사이드바: ⏸ Codex — Idle

Step 7: Claude가 Codex 결과 확인, 사용자에게 보고
        "Codex가 15개 테스트를 작성했습니다. 모두 통과합니다."

Step 8: 사용자가 결과 확인
        → 각 패널을 클릭해서 에이전트 출력 확인
        → 브라우저 패널에서 테스트 커버리지 리포트 확인 가능
```

### 6.2 tmux Shim 설계 (Windows)

```
위치: %APPDATA%/cmux-win/shims/tmux.cmd
PATH 주입: claude-teams 명령 실행 시 PATH 앞에 shim 디렉토리 추가

tmux.cmd 내부:
  1. 인자 파싱 (tmux 명령 문법)
  2. cmux-win CLI로 변환
  3. TCP localhost로 Socket API 호출
  4. 결과 반환

지원하는 tmux 명령 → cmux-win 매핑:
┌──────────────────────────┬─────────────────────────────────────┐
│ tmux 명령                 │ cmux-win Socket Action              │
├──────────────────────────┼─────────────────────────────────────┤
│ new-session -n <name>    │ workspace.create { name }            │
│ new-window -n <name>     │ workspace.create { name }            │
│ split-window [-h|-v]     │ panel.split { direction }            │
│ send-keys -t <id> <text> │ surface.send_text { surfaceId, text }│
│ select-pane -t <id>      │ panel.focus { panelId }              │
│ select-window -t <id>    │ workspace.select { workspaceId }     │
│ kill-pane -t <id>        │ panel.close { panelId }              │
│ kill-window -t <id>      │ workspace.close { workspaceId }      │
│ list-panes               │ panel.list                           │
│ list-windows             │ workspace.list                       │
│ resize-pane -L/-R/-U/-D  │ panel.resize { panelId, delta }      │
│ capture-pane             │ surface.read_screen                   │
│ display-message -p       │ (stdout 출력)                         │
│ last-pane                │ focus.last_panel                      │
│ swap-pane                │ panel.swap                            │
│ break-pane               │ panel.break_to_workspace              │
│ join-pane                │ panel.join                            │
└──────────────────────────┴─────────────────────────────────────┘

TMUX 환경변수 설정:
  TMUX=/tmp/cmux-win-claude-teams/<workspace>,<window>,<pane>
  TMUX_PANE=%<pane_handle>
```

### 6.3 Hook 시스템

```
claude.cmd / claude.ps1 래퍼:
  1. CMUX_SURFACE_ID 존재 확인
  2. Socket health check (TCP ping)
  3. Claude Code 실행 + Hook JSON 주입:
     {
       "hooks": {
         "SessionStart":      { "command": "cmux-win claude-hook session-start" },
         "Stop":              { "command": "cmux-win claude-hook stop" },
         "SessionEnd":        { "command": "cmux-win claude-hook session-end" },
         "Notification":      { "command": "cmux-win claude-hook notification" },
         "UserPromptSubmit":  { "command": "cmux-win claude-hook prompt-submit" },
         "PreToolUse":        { "command": "cmux-win claude-hook pre-tool-use", "async": true }
       }
     }

Hook → SOT Action 매핑:
  session-start  → agent.session_start
  prompt-submit  → agent.status_update { status: 'running' }
  pre-tool-use   → agent.status_update { status: 'running' } (async)
  notification   → agent.status_update { status: 'needs_input' } + notification.create
  stop           → agent.status_update { status: 'idle' }
  session-end    → agent.session_end + agent.clear_pid

세션 스토어:
  위치: %APPDATA%/cmux-win/claude-hook-sessions.json
  잠금: proper-lockfile (Windows 호환 파일 잠금)
  TTL: 7일 (stale 세션 자동 정리)
```

---

## 7. Socket API 설계

### 7.1 전송 계층

```
기본: TCP localhost:19840 (포트 번호 설정 가능)
프로토콜: 개행 구분 JSON-RPC 2.0

장점 (성찰 #9 반영):
  - WSL에서 바로 접근 가능 (127.0.0.1)
  - curl/telnet으로 디버깅 가능
  - cmux의 소켓 프로토콜과 거의 동일
  - 크로스플랫폼 호환

옵션: Named Pipe (\\.\pipe\cmux-win) — 설정으로 활성화 가능
```

### 7.2 인증

```
5단계 보안 모드 (cmux 동일):
  off:        소켓 비활성화
  cmux-only:  앱 내부 호출만 허용 (PID 검증)
  automation: 앱 + 래퍼 스크립트 허용
  password:   비밀번호 인증 필수
  allow-all:  모든 접근 허용

비밀번호 저장:
  %APPDATA%/cmux-win/socket-password (파일 기반)
  Windows Credential Manager (폴백)
```

### 7.3 명령 체계

cmux V2 JSON-RPC와 완전 호환:

```
시스템:      system.ping, system.identify, system.capabilities
윈도우:      window.list, window.current, window.create, window.focus, window.close
워크스페이스: workspace.list, workspace.current, workspace.create, workspace.select,
             workspace.close, workspace.rename, workspace.reorder, workspace.move_to_window
패널:        pane.list, pane.focus, pane.create, pane.close, pane.resize, pane.swap
서피스:      surface.list, surface.focus, surface.create, surface.close,
             surface.send_text, surface.send_key, surface.read, surface.move,
             surface.split, surface.health, surface.trigger_flash
브라우저:    browser.navigate, browser.back, browser.forward, browser.reload,
             browser.url.get, browser.snapshot, browser.eval, browser.wait,
             browser.click, browser.type, browser.fill, browser.screenshot,
             browser.press, browser.scroll, browser.find.*, browser.dialog.*
알림:        notification.create, notification.list, notification.clear
상태:        status.set, status.clear, status.list
에이전트:    agent.session_start, agent.status_update, agent.session_end
설정:        settings.get, settings.update
```

---

## 8. 성능 전략 (성찰 #7 반영)

### 8.1 성능 예산

| 지표 | 목표 | 측정 방법 |
|------|------|----------|
| 키 입력 → 화면 반영 | ≤16ms | 커스텀 벤치마크 (키 이벤트 → xterm.js 렌더 완료) |
| IPC 라운드트립 | ≤5ms | Action dispatch → Renderer 수신 |
| 패널 분할 생성 | ≤100ms | Action → UI 반영 |
| 앱 시작 | ≤3s | 프로세스 시작 → 첫 터미널 준비 완료 |
| 메모리 (베이스라인) | ≤300MB | 터미널 1개, 빈 상태 |

### 8.2 최적화 전략

```
1. xterm.js WebGL Addon 필수
   - Canvas 렌더러 대비 ~10배 빠른 렌더링
   - GPU 가속 글리프 캐시

2. 터미널은 React 렌더 사이클에서 완전 분리
   - xterm.js 인스턴스는 DOM에 직접 마운트
   - React는 컨테이너 div만 관리
   - PTY 데이터 → xterm.js 직접 전달 (React 경유 안 함)

3. IPC 최소화
   - 고빈도 이벤트(키 입력, PTY 출력)는 Renderer에서 직접 처리
   - SOT 브로드캐스트는 16ms 디바운스 (requestAnimationFrame 동기화)
   - 사이드바/패널 목록은 변경 시에만 전송 (diff 기반)

4. UI 가상화
   - 사이드바: 50개+ 워크스페이스 → react-virtuoso
   - 알림 목록: 가상 스크롤
   - 커맨드 팔레트 결과: 가상 스크롤

5. 무거운 작업 오프로드
   - 포트 스캔: Worker Thread
   - 세션 스냅샷: 디바운스 + 비동기 파일 I/O
   - 브라우저 히스토리 검색: better-sqlite3 (메인 스레드 차단 최소화)
```

---

## 9. 에러 복구 전략 (성찰 #8 반영)

```
┌────────────────┬──────────────────────────────────────────┐
│ 장애 유형       │ 복구 전략                                 │
├────────────────┼──────────────────────────────────────────┤
│ PTY 크래시      │ 자동 재생성 + 스크롤백 복원 시도            │
│                │ SOT에서 surface.terminal.cwd 읽어 동일     │
│                │ 디렉토리에서 셸 재시작                      │
├────────────────┼──────────────────────────────────────────┤
│ WebContentsView│ 자동 재생성 + 마지막 URL 로드              │
│ 프로세스 종료   │ SOT에서 surface.browser.url 읽어 복원      │
├────────────────┼──────────────────────────────────────────┤
│ 에이전트 세션   │ stale PID 감지 (5초마다 프로세스 존재 확인) │
│ 끊김           │ 존재하지 않으면 agent.session_end 발행     │
│                │ 사이드바에서 상태 정리                     │
├────────────────┼──────────────────────────────────────────┤
│ Socket 연결    │ CLI: 3회 재시도 (1초 간격)                │
│ 실패           │ 앱 재시작 시 포트 충돌 감지 + 대체 포트     │
├────────────────┼──────────────────────────────────────────┤
│ 세션 복원 실패  │ 부분 복원 (유효한 워크스페이스만 복원)      │
│                │ 손상된 JSON → 백업에서 복원 시도            │
│                │ 최후: 빈 상태로 시작                       │
├────────────────┼──────────────────────────────────────────┤
│ 앱 비정상 종료  │ 다음 시작 시 마지막 스냅샷에서 자동 복원    │
│                │ 디바운스 스냅샷으로 최대 500ms 손실         │
└────────────────┴──────────────────────────────────────────┘
```

---

## 10. TDD 자동화 전략 (성찰 #6 반영)

### 10.1 강제 메커니즘

```
1. 테스트 우선 스캐폴딩
   $ npm run create-module terminal-manager
   → src/main/terminal/terminal-manager.ts        (빈 모듈)
   → tests/unit/terminal/terminal-manager.test.ts  (실패하는 테스트 스켈레톤)
   → 테스트 파일이 먼저 생성되어야 모듈 파일 생성 가능

2. Pre-commit Hook (Husky)
   → lint-staged: 변경된 파일의 관련 테스트 실행
   → 테스트 실패 시 커밋 차단
   → 새 .ts 파일에 대응하는 .test.ts 없으면 경고

3. CI 게이트 (GitHub Actions)
   → PR 머지 조건:
     - 전체 테스트 통과
     - 커버리지 하락 시 차단 (기존 대비)
     - Phase별 커버리지 게이트 충족

4. 커버리지 게이트 (Phase별)
   Phase 1 (기반 인프라):  ≥90%
   Phase 2 (핵심 UI):     ≥80%
   Phase 3 (브라우저):    ≥80%
   Phase 4 (에이전트):    ≥90%
   Phase 5 (셸/원격):     ≥85%
   Phase 6 (완성도):      ≥80%
```

### 10.2 테스트 설계 원칙

```
1. 행동 기반 테스트 (구현 세부사항 테스트 금지)
   ✗ "store 내부 배열 길이가 3인지 확인"
   ✓ "workspace.create 3회 후 workspace.list가 3개 반환하는지 확인"

2. 각 SOT Action에 대한 테스트 필수
   - 정상 경로: 올바른 payload → 상태 변경 검증
   - 에러 경로: 잘못된 payload → 에러 반환 검증
   - 부수효과: Action 후 Side Effect 발생 검증

3. E2E 시나리오 (핵심 워크플로우)
   - "claude-teams로 에이전트 3개 스폰, 상태 추적, 결과 수집"
   - "터미널 4분할 + 각각 다른 셸 + 포커스 전환"
   - "브라우저 패널에서 localhost 앱 열기 + find-in-page"
   - "세션 저장 → 앱 종료 → 재시작 → 레이아웃 복원"

4. 성능 회귀 테스트
   - 키 입력 지연 ≤16ms (벤치마크 실패 시 CI 경고)
   - IPC 라운드트립 ≤5ms
```

---

## 11. 구현 Phase

### Phase 1 — 기반 인프라 (Foundation)

```
목표: Electron 앱이 터미널을 띄우고, Socket으로 제어할 수 있는 최소 동작 상태

1.1 프로젝트 초기화
    - Electron + TypeScript + React 보일러플레이트
    - ESLint + Prettier + Husky 설정
    - Vitest + Playwright 설정
    - CI 파이프라인 (GitHub Actions)
    - TDD 스캐폴딩 스크립트

1.2 SOT 스토어
    - AppStateStore 구현 (EventEmitter + Immer)
    - Action Dispatcher + 미들웨어 체인
    - Zod 스키마 검증
    - 상태 히스토리 (디버그)
    테스트: 모든 Action CRUD, 미들웨어 순서, 검증 실패

1.3 터미널 엔진
    - node-pty + ConPTY 래퍼
    - xterm.js WebGL 마운트
    - React 렌더 사이클에서 분리
    - 셸 선택 (PowerShell/CMD/WSL/Git Bash)
    테스트: PTY 생성/종료, 입출력, 리사이즈, 셸 전환

1.4 IPC 레이어
    - Main ↔ Renderer: Electron IPC + 타입 안전 채널
    - 외부: TCP localhost Socket API 서버
    - JSON-RPC 2.0 파서 + 라우터
    - 인증 레이어
    테스트: IPC 라운드트립, Socket 명령 실행, 인증 모드별 접근 제어

1.5 CLI 기본
    - cmux-win.exe (Node.js SEA)
    - ping, version, list-workspaces, send
    테스트: CLI → Socket → SOT → 결과 반환 전체 경로
```

### Phase 2 — 핵심 UI (Core UI)

```
목표: 사이드바 + 분할 패널 + 탭 + 키보드 단축키가 동작하는 완전한 UI

2.1 윈도우 관리
    - 멀티 윈도우 생성/소멸
    - 윈도우 간 워크스페이스 이동
    - 윈도우 지오메트리 영구저장
    테스트: 멀티 윈도우 CRUD, 크로스 윈도우 이동

2.2 사이드바
    - 워크스페이스 목록 (가상화)
    - 드래그 앤 드롭 재정렬
    - 컬러 커스텀
    - 에이전트 상태 뱃지
    - 알림 뱃지 + 미읽음 카운트
    테스트: CRUD, 재정렬, 뱃지 표시, 선택 상태

2.3 분할 패널 레이아웃
    - 상하좌우 분할 (트리 구조)
    - 드래그 리사이즈
    - 줌/최대화 토글
    - 패널 간 포커스 이동 (화살표)
    테스트: 분할/병합/리사이즈, 포커스 방향 이동, 줌 토글

2.4 탭 관리
    - 패널 내 멀티탭
    - 탭 드래그 (패널 내 + 크로스 패널)
    - 탭 컨텍스트 메뉴
    테스트: 탭 CRUD, 드래그 이동, 포커스 전환

2.5 키보드 단축키
    - 30개 액션 정의 + 커스텀 가능
    - 단축키 힌트 오버레이
    - 국제 키보드 레이아웃 감지
    테스트: 모든 기본 단축키, 커스텀 바인딩, 충돌 감지
```

### Phase 3 — 브라우저 + 마크다운 (Content Panels)

```
목표: 터미널 옆에 브라우저와 마크다운 뷰어가 나란히 동작

3.1 브라우저 패널
    - WebContentsView 래퍼
    - 옴니바 (주소바 + 인라인 자동완성 + 검색 제안)
    - 프로필 격리 (Session partition)
    - 히스토리 (better-sqlite3)
    - 네비게이션 (back/forward/reload)
    - HTTP 보안 경고 + 화이트리스트
    - DevTools 토글
    테스트: 네비게이션, 프로필 격리, 히스토리 CRUD, 보안 경고

3.2 브라우저 자동화 API
    - P0: snapshot, eval, wait, click, type, fill, press, screenshot
    - P1: find.role/text/label, dialog, download, console
    - Socket API로 노출
    테스트: P0 전체 (각 명령별), P1 주요 명령

3.3 Find-in-page
    - 터미널: xterm.js 검색 addon
    - 브라우저: JS DOM TreeWalker (cmux 방식 이식)
    - 드래그 가능한 검색 오버레이
    테스트: 검색/이전/다음/닫기, 매치 카운트, 특수문자

3.4 마크다운 뷰어
    - 파일 열기 + chokidar 파일 감시
    - 마크다운 렌더링 (remark + rehype)
    - 코드 블록 구문 강조 (shiki)
    테스트: 렌더링, 라이브 리로드, 파일 삭제/재생성
```

### Phase 4 — AI 에이전트 오케스트레이션 (핵심 기능)

```
목표: Claude가 리더로서 Codex/Gemini를 스폰하고 제어하는 완전한 워크플로우

4.1 Hook 시스템
    - claude.cmd + claude.ps1 래퍼
    - Hook JSON 주입 (6가지 라이프사이클)
    - 세션 스토어 (JSON + proper-lockfile)
    - PID 추적 + stale 감지
    테스트: 훅 라이프사이클 전체, 세션 CRUD, stale 정리

4.2 tmux Shim
    - tmux.cmd 생성 + PATH 주입
    - 17개 tmux 명령 → Socket Action 변환
    - TMUX/TMUX_PANE 환경변수 설정
    테스트: 모든 tmux 명령 매핑, 에러 처리, 환경변수

4.3 Claude Teams
    - cmux-win claude-teams 명령
    - --teammate-mode auto 지원
    - 리더 패널 포커스 유지
    - 팀원 패널 자동 생성
    테스트: 팀원 스폰 E2E, 상태 추적, 세션 종료 정리

4.4 Codex/Gemini/OpenCode 래퍼
    - 에이전트별 래퍼 스크립트
    - notify 명령 연동
    - 상태 통합 (SOT agents 배열)
    테스트: 에이전트별 훅, 알림, 상태 전환

4.5 open 래퍼
    - URL을 내장 브라우저로 라우팅
    - 패턴 매칭 (화이트리스트/블랙리스트)
    - 폴백: 시스템 기본 브라우저
    테스트: URL 라우팅, 패턴 매칭, 폴백
```

### Phase 5 — 셸 통합 + 원격 (Shell & Remote)

```
목표: 셸 환경 인식 + SSH 원격 워크스페이스

5.1 셸 통합
    - PowerShell 통합: PWD 추적, git 브랜치, dirty 상태
    - CMD 통합: 기본 PWD 추적
    - WSL 통합: Linux 셸 통합 재사용
    - Git Bash 통합: bash 통합 재사용
    - 포트 스캔: netstat 기반 (Worker Thread)
    테스트: 셸별 PWD 감지, git 상태, 포트 감지

5.2 SSH 원격
    - cmuxd-remote(Go) 바이너리 번들
    - SSH 부트스트랩 (원격 데몬 업로드 + 실행)
    - RPC 프록시 (SOCKS5/HTTP CONNECT)
    - PTY 세션 관리 (smallest-screen-wins)
    - 재접속 로직
    테스트: 부트스트랩, RPC, PTY 리사이즈, 재접속

5.3 세션 퍼시스턴스
    - JSON 스냅샷 (디바운스 500ms)
    - 복원: 윈도우/워크스페이스/패널/탭 레이아웃
    - 스크롤백 저장/복원 (ANSI-safe 절단)
    - 손상 복구: 백업 → 부분 복원 → 빈 상태
    테스트: 저장/복원 사이클, 손상 복구, 부분 복원
```

### Phase 6 — 완성도 (Polish)

```
목표: 프로덕션 품질 완성

6.1 알림 시스템
    - 앱 내 알림 패널
    - Windows Toast Notification
    - 시스템 트레이 아이콘 + 미읽음 뱃지
    - 커스텀 사운드
    테스트: 알림 CRUD, Toast 발행, 뱃지 카운트

6.2 커맨드 팔레트
    - 퍼지 검색 (1-edit tolerance)
    - 스위처 모드 (워크스페이스/서피스)
    - 명령 사용 빈도 정렬
    테스트: 검색 알고리즘, 스위처 필터링, 빈도 정렬

6.3 설정 UI
    - 외형 (테마, 폰트, 아이콘)
    - 터미널 (셸, 폰트 크기)
    - 브라우저 (검색엔진, 보안)
    - 에이전트 (훅 활성화)
    - 단축키 커스텀
    테스트: 설정 CRUD, 영구저장, UI 반영

6.4 자동 업데이트
    - electron-updater + GitHub Releases
    - Stable/Nightly 채널
    - 진행률 UI
    테스트: 업데이트 확인, 다운로드, 설치 시뮬레이션

6.5 다국어
    - i18next (한국어, 영어, 일본어)
    - 모든 UI 문자열 키 기반
    테스트: 번역 키 누락 감지, 언어 전환

6.6 텔레메트리 + 에러 리포팅
    - Sentry (에러 리포팅)
    - PostHog (사용 분석, 옵트아웃)
    - 디버그 로그 (%TEMP%/cmux-win-debug.log)
    테스트: 이벤트 전송, 옵트아웃 동작

6.7 테마
    - Ghostty 호환 테마 파일 로드
    - 90+ 번들 테마
    - 테마 프리뷰 + 적용
    테스트: 테마 파싱, 적용, 라이트/다크 전환
```

---

## 12. 프로젝트 구조

```
cmux-win/
├── docs/
│   └── plans/
│       └── 2026-03-19-cmux-win-design.md     ← 이 문서
├── src/
│   ├── main/                                  # Electron Main Process
│   │   ├── app.ts                             # 앱 진입점
│   │   ├── sot/                               # Source of Truth
│   │   │   ├── store.ts                       # AppStateStore
│   │   │   ├── actions.ts                     # Action 타입 정의
│   │   │   ├── reducers/                      # Action별 상태 갱신
│   │   │   │   ├── workspace.ts
│   │   │   │   ├── panel.ts
│   │   │   │   ├── surface.ts
│   │   │   │   ├── agent.ts
│   │   │   │   └── ...
│   │   │   └── middleware/                    # 미들웨어 체인
│   │   │       ├── validation.ts
│   │   │       ├── persistence.ts
│   │   │       ├── ipc-broadcast.ts
│   │   │       └── audit-log.ts
│   │   ├── terminal/                          # 터미널 엔진
│   │   │   ├── pty-manager.ts
│   │   │   ├── shell-integration/
│   │   │   │   ├── powershell.ts
│   │   │   │   ├── cmd.ts
│   │   │   │   ├── wsl.ts
│   │   │   │   └── git-bash.ts
│   │   │   └── port-scanner.ts
│   │   ├── browser/                           # 브라우저 엔진
│   │   │   ├── browser-manager.ts
│   │   │   ├── profile-manager.ts
│   │   │   ├── history-store.ts               # better-sqlite3
│   │   │   ├── automation/                    # P0/P1 API
│   │   │   └── find-javascript.ts
│   │   ├── agents/                            # AI 에이전트
│   │   │   ├── hook-system.ts
│   │   │   ├── session-store.ts
│   │   │   ├── tmux-shim.ts
│   │   │   └── wrappers/
│   │   │       ├── claude.ts
│   │   │       ├── codex.ts
│   │   │       └── gemini.ts
│   │   ├── socket/                            # Socket API
│   │   │   ├── server.ts                      # TCP localhost
│   │   │   ├── router.ts                      # JSON-RPC 라우터
│   │   │   ├── auth.ts
│   │   │   └── handlers/                      # 명령 핸들러
│   │   │       ├── window.ts
│   │   │       ├── workspace.ts
│   │   │       ├── panel.ts
│   │   │       ├── surface.ts
│   │   │       ├── browser.ts
│   │   │       ├── agent.ts
│   │   │       └── notification.ts
│   │   ├── session/                           # 세션 퍼시스턴스
│   │   │   ├── persistence.ts
│   │   │   └── recovery.ts
│   │   ├── notifications/                     # 알림
│   │   │   ├── notification-manager.ts
│   │   │   └── toast.ts                       # Windows Toast
│   │   ├── updates/                           # 자동 업데이트
│   │   │   └── update-manager.ts
│   │   ├── performance/                       # 성능 모니터
│   │   │   └── monitor.ts
│   │   └── error-recovery/                    # 에러 복구
│   │       └── recovery-manager.ts
│   │
│   ├── renderer/                              # React UI
│   │   ├── App.tsx                            # 루트 컴포넌트
│   │   ├── components/
│   │   │   ├── sidebar/
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   ├── WorkspaceItem.tsx
│   │   │   │   ├── AgentBadge.tsx
│   │   │   │   └── NotificationBadge.tsx
│   │   │   ├── panels/
│   │   │   │   ├── PanelLayout.tsx            # 분할 트리 렌더러
│   │   │   │   ├── PanelContainer.tsx
│   │   │   │   ├── TerminalPanel.tsx
│   │   │   │   ├── BrowserPanel.tsx
│   │   │   │   ├── MarkdownPanel.tsx
│   │   │   │   └── PanelTabBar.tsx
│   │   │   ├── terminal/
│   │   │   │   ├── XTermWrapper.tsx           # xterm.js 래퍼 (React 분리)
│   │   │   │   └── TerminalFind.tsx
│   │   │   ├── browser/
│   │   │   │   ├── Omnibar.tsx
│   │   │   │   ├── BrowserFind.tsx
│   │   │   │   └── BrowserSettings.tsx
│   │   │   ├── command-palette/
│   │   │   │   ├── CommandPalette.tsx
│   │   │   │   └── FuzzySearch.ts
│   │   │   ├── notifications/
│   │   │   │   └── NotificationPanel.tsx
│   │   │   ├── settings/
│   │   │   │   └── SettingsPage.tsx
│   │   │   └── shortcuts/
│   │   │       └── ShortcutHintOverlay.tsx
│   │   ├── hooks/                             # React 커스텀 훅
│   │   │   ├── useAppState.ts                 # SOT 구독 (읽기 전용)
│   │   │   ├── useShortcuts.ts
│   │   │   └── usePanelFocus.ts
│   │   └── ipc/
│   │       └── renderer-ipc.ts                # 타입 안전 IPC 클라이언트
│   │
│   ├── cli/                                   # CLI 도구
│   │   ├── cmux-win.ts                        # 진입점
│   │   ├── commands/                          # 서브커맨드
│   │   └── socket-client.ts                   # TCP 클라이언트
│   │
│   └── shared/                                # Main + Renderer 공유
│       ├── types.ts                           # 전체 타입 정의
│       ├── actions.ts                         # Action 타입
│       ├── protocol.ts                        # JSON-RPC 프로토콜
│       ├── schemas.ts                         # Zod 스키마
│       └── constants.ts                       # 상수
│
├── resources/
│   ├── shims/                                 # 래퍼 스크립트
│   │   ├── claude.cmd
│   │   ├── claude.ps1
│   │   ├── codex.cmd
│   │   ├── tmux.cmd
│   │   └── open.cmd
│   ├── shell-integration/
│   │   ├── powershell/
│   │   ├── cmd/
│   │   └── wsl/
│   ├── themes/                                # 90+ Ghostty 호환 테마
│   └── locales/                               # i18next 번역 파일
│       ├── en.json
│       ├── ko.json
│       └── ja.json
│
├── tests/
│   ├── unit/                                  # Vitest 유닛 테스트
│   │   ├── sot/
│   │   ├── terminal/
│   │   ├── browser/
│   │   ├── agents/
│   │   ├── socket/
│   │   └── ...
│   ├── integration/                           # Vitest 통합 테스트
│   │   ├── ipc/
│   │   ├── socket-api/
│   │   ├── hook-system/
│   │   └── ...
│   └── e2e/                                   # Playwright E2E 테스트
│       ├── agent-orchestration.spec.ts
│       ├── terminal-splits.spec.ts
│       ├── browser-panels.spec.ts
│       ├── session-persistence.spec.ts
│       └── ...
│
├── package.json
├── tsconfig.json
├── tsconfig.main.json
├── tsconfig.renderer.json
├── vitest.config.ts
├── playwright.config.ts
├── electron-builder.yml
├── .eslintrc.cjs
├── .prettierrc
├── .husky/
│   └── pre-commit
└── CLAUDE.md                                  # 개발 지침
```

---

## 13. cmux 프로토콜 호환성

```
cmux-win은 cmux와 동일한 Socket 명령 체계를 사용한다.
이를 통해:
  - cmux용으로 작성된 CLI 스크립트가 cmux-win에서도 동작
  - Claude Code의 tmux shim이 동일하게 동작
  - 에이전트 래퍼의 Hook 프로토콜이 동일

환경변수 호환:
  CMUX_SOCKET_PATH  → TCP 주소 (127.0.0.1:19840)
  CMUX_SURFACE_ID   → 동일 (UUID)
  CMUX_WORKSPACE_ID → 동일 (UUID)
  CMUX_TAB_ID       → 동일 (UUID)
  CMUX_PANE_ID      → 동일 (UUID)
```

---

이 수정 설계안에 대해 피드백 부탁드립니다. 섹션별로 질문이나 변경 요청이 있으시면 말씀해 주세요.