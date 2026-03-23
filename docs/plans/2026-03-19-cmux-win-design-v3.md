# cmux-win 설계안 v3 (최종 검토본)

> 최종 수정: 2026-03-19
> 상태: 최종 검토 대기 — 승인 전 구현 불가
> 절대 기준: 품질과 질적 수준 최우선. 속도/비용 무시.
> 이전 버전: v1(초안), v2(1차 성찰 반영), v3(2차 성찰 14개 GAP 반영)

---

## 1. 프로젝트 비전

cmux-win은 macOS용 cmux의 **모든 지능을 Windows에서 동일하게 실행**하는
AI 에이전트 오케스트레이션 플랫폼이다.

핵심 가치:
- Claude Code가 리더로서 Gemini/Codex를 팀원처럼 호출하는 멀티 에이전트 환경
- 터미널 + 브라우저 + 마크다운이 하나의 워크스페이스에 통합된 분할 패널 UI
- 소켓 API로 모든 것을 프로그래밍적으로 제어 가능
- cmux와 호환되는 프로토콜/명령 체계

---

## 2. 설계 원칙

### 2.1 역할 분리

```
앱(cmux-win) = 인프라 플랫폼 + 폴백 오케스트레이터
  - 패널 생성/관리, IPC, 상태 관리, UI 제공
  - Claude Teams 지원 시: 인프라만 제공
  - Claude Teams 미지원 시: 자체 오케스트레이션 UI 제공 (GAP-10 대응)

Claude Code = Primary Orchestrator (리더)
  - 터미널 패널 안에서 실행
  - tmux.cmd shim을 통해 패널을 생성하고 팀원을 스폰

Gemini/Codex = Worker (팀원)
  - Claude가 스폰하거나, 사용자가 UI로 직접 추가
  - Hook 시스템으로 상태가 앱에 보고됨
```

### 2.2 SOT (Source of Truth) 원칙

```
단일 진실 소스 = Main Process의 AppStateStore

규칙:
1. 모든 상태 변경은 Action Dispatch를 통해서만 발생
2. Renderer는 읽기 전용 구독자 (직접 변경 불가)
3. Renderer → Main 통신은 typesafe IPC invoke (GAP-7 대응)
4. CLI/Socket도 동일한 Action 경로로 진입
5. 모든 Action은 로깅됨 (디버그 추적 가능)
6. 상태 스키마는 버전 관리됨 (GAP-6 대응)
```

### 2.3 품질 원칙

```
1. TypeScript strict mode 전체 ON
2. Zod 스키마 기반 런타임 검증 (Action payload, 소켓 입력, IPC 메시지)
3. 테스트 없는 코드는 커밋 불가
4. 에러는 삼키지 않고 복구하거나 명시적으로 전파
5. 성능 예산: 키 입력 → 화면 반영 ≤10ms (Renderer 직접 PTY, GAP-3 대응)
6. Plan B 필수: 모든 외부 의존(Claude Teams, ConPTY)에 폴백 경로 존재
```

---

## 3. 전체 아키텍처

```
┌───────────────────────────────────────────────────────────────┐
│                          cmux-win                              │
│                                                               │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │                Main Process (인프라 플랫폼)                │ │
│  │                                                          │ │
│  │  ┌────────────────────────────────────────────────────┐  │ │
│  │  │              AppStateStore (SOT)                    │  │ │
│  │  │                                                    │  │ │
│  │  │  스키마 버전: { version: 1, state: AppState }       │  │ │
│  │  │  마이그레이션 체인: v1→v2→...→vN (GAP-6)           │  │ │
│  │  │                                                    │  │ │
│  │  │  미들웨어:                                          │  │ │
│  │  │  Validation → Mutation(Immer) → SideEffects        │  │ │
│  │  │  → Persistence(디바운스) → IPC Broadcast            │  │ │
│  │  │  → AuditLog(DEBUG)                                 │  │ │
│  │  └────────────────────────────────────────────────────┘  │ │
│  │                                                          │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │ │
│  │  │ Window       │  │ Socket API   │  │ Hook System  │   │ │
│  │  │ Manager      │  │ Server       │  │              │   │ │
│  │  │              │  │              │  │ claude.cmd   │   │ │
│  │  │ BrowserWindow│  │ TCP localhost│  │ claude.ps1   │   │ │
│  │  │ ↔ windowId   │  │ :19840      │  │ codex.cmd    │   │ │
│  │  │ 매핑 (GAP-8) │  │ JSON-RPC v2 │  │ tmux.cmd     │   │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │ │
│  │                                                          │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │ │
│  │  │ Session      │  │ Notification │  │ Error        │   │ │
│  │  │ Persistence  │  │ Manager      │  │ Recovery     │   │ │
│  │  │              │  │              │  │              │   │ │
│  │  │ 스키마 버전   │  │ Windows Toast│  │ PTY 재시작   │   │ │
│  │  │ 마이그레이션  │  │ 트레이 아이콘 │  │ WebView 복구 │   │ │
│  │  │ 자동 백업    │  │ 인앱 뱃지    │  │ 세션 복원    │   │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │ │
│  │                                                          │ │
│  │  ┌──────────────────────────────────────────────────┐    │ │
│  │  │ Agent Orchestration Fallback (GAP-1/10 대응)      │    │ │
│  │  │                                                  │    │ │
│  │  │ Claude Teams 감지 → 성공: tmux.cmd shim 모드     │    │ │
│  │  │                  → 실패: 자체 오케스트레이션 모드  │    │ │
│  │  │                                                  │    │ │
│  │  │ 자체 모드:                                        │    │ │
│  │  │   UI에서 "에이전트 추가" → 패널 생성 → CLI 실행   │    │ │
│  │  │   → Hook 주입 → 상태 추적 → 결과 수집            │    │ │
│  │  └──────────────────────────────────────────────────┘    │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │            Renderer Process (UI — per window)             │ │
│  │            windowId 기반 SOT 구독 (GAP-8)                 │ │
│  │                                                          │ │
│  │  ┌─────────────────────────────────────────────────────┐ │ │
│  │  │           Typesafe IPC Layer (GAP-7)                 │ │ │
│  │  │                                                     │ │ │
│  │  │  Renderer → Main: ipcRenderer.invoke('dispatch', a) │ │ │
│  │  │  Main → Renderer: ipcMain → webContents.send()      │ │ │
│  │  │  양방향 Zod 스키마 검증                               │ │ │
│  │  └─────────────────────────────────────────────────────┘ │ │
│  │                                                          │ │
│  │  ┌──────────┐ ┌─────────────┐ ┌──────────────────────┐  │ │
│  │  │ Sidebar  │ │ Panel       │ │ Command Palette      │  │ │
│  │  │          │ │ Layout      │ │                      │  │ │
│  │  │ 워크스페이│ │ Manager     │ │ 퍼지 검색             │  │ │
│  │  │ 스 목록   │ │             │ │ 스위처               │  │ │
│  │  │ 상태 뱃지 │ │ CSS Grid/   │ │ 에이전트 추가 (폴백) │  │ │
│  │  │ 에이전트  │ │ Flexbox     │ │                      │  │ │
│  │  │ 추가 버튼 │ │ 분할 트리   │ │                      │  │ │
│  │  └──────────┘ └─────────────┘ └──────────────────────┘  │ │
│  │                                                          │ │
│  │  ┌──────────────────────────────────────────────────┐    │ │
│  │  │    Panel Renderers (모두 React DOM 내부)           │    │ │
│  │  │                                                  │    │ │
│  │  │  ┌────────────┐ ┌────────────┐ ┌─────────────┐  │    │ │
│  │  │  │ Terminal   │ │ Browser    │ │ Markdown    │  │    │ │
│  │  │  │            │ │            │ │             │  │    │ │
│  │  │  │ xterm.js   │ │ <webview>  │ │ remark +    │  │    │ │
│  │  │  │ (WebGL/    │ │ 태그       │ │ rehype +    │  │    │ │
│  │  │  │  Canvas    │ │ (GAP-2)    │ │ shiki       │  │    │ │
│  │  │  │  동적전환)  │ │            │ │             │  │    │ │
│  │  │  │            │ │ 프로필격리  │ │ 라이브리로드 │  │    │ │
│  │  │  │ node-pty   │ │ partition  │ │ chokidar    │  │    │ │
│  │  │  │ Renderer   │ │ 기반       │ │             │  │    │ │
│  │  │  │ 직접실행   │ │            │ │             │  │    │ │
│  │  │  │ (GAP-3)    │ │ Omnibar    │ │             │  │    │ │
│  │  │  │            │ │ DevTools   │ │             │  │    │ │
│  │  │  │ WebSocket  │ │ Find       │ │             │  │    │ │
│  │  │  │ 브릿지     │ │ History    │ │             │  │    │ │
│  │  │  │ (폴백)     │ │            │ │             │  │    │ │
│  │  │  └────────────┘ └────────────┘ └─────────────┘  │    │ │
│  │  └──────────────────────────────────────────────────┘    │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │                CLI (cmux-win.exe)                         │ │
│  │  TCP 클라이언트 → JSON-RPC v2                             │ │
│  │  소켓 주소: tcp://127.0.0.1:19840 (GAP-5)                │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                               │
│  ═══════════════════════════════════════════════════════════  │
│  AI 에이전트 계층                                              │
│                                                               │
│  경로 A: Claude Teams 지원 시 (tmux.cmd shim)                 │
│    Claude Code → tmux.cmd → Socket API → 패널 생성/제어       │
│                                                               │
│  경로 B: 자체 오케스트레이션 (폴백, GAP-1/10)                  │
│    UI "에이전트 추가" → 패널 생성 → CLI 실행 → Hook 주입       │
│  ═══════════════════════════════════════════════════════════  │
└───────────────────────────────────────────────────────────────┘
```

---

## 4. 기술 스택

### 4.1 핵심

| 계층 | 기술 | 버전 | 선택 이유 |
|------|------|------|----------|
| 런타임 | Electron | 33 (고정) | WebContentsView 안정, 보안 패치 |
| 언어 | TypeScript | 5.4+ | strict mode 전체 활성화 |
| UI | React | 18.3 | Concurrent 모드 비활성 (xterm.js DOM 직접 조작 호환) |
| 터미널 | xterm.js | 5.x | WebGL addon + Canvas 폴백 |
| PTY | node-pty | 1.x | Renderer preload에서 직접 실행 (GAP-3) |
| 브라우저 패널 | Electron `<webview>` 태그 | Electron 내장 | React DOM 내 통합 (GAP-2) |
| SOT | 커스텀 스토어 + Immer | — | Main Process 네이티브, React 의존성 없음 |
| 런타임 검증 | Zod | 3.x | Action, IPC, Socket 입력 전부 검증 |
| IPC 타입 안전 | electron-trpc 또는 커스텀 | — | 양방향 타입 검증 (GAP-7) |
| DB | better-sqlite3 | — | 브라우저 히스토리, 동기 SQLite |
| 외부 IPC | TCP localhost:19840 | — | WSL 호환, 디버깅 용이 |
| CLI | Node.js SEA | — | 단일 실행 파일 |
| 빌드 | electron-builder | — | Windows 인스톨러 |
| 자동 업데이트 | electron-updater | — | GitHub Releases 연동 |
| 다국어 | i18next | — | 한/영/일 |
| 파일 감시 | chokidar | — | 마크다운 라이브 리로드 |
| 파일 잠금 | proper-lockfile | — | Windows 호환 (GAP-1) |

### 4.2 React 18.3을 선택한 이유 (React 19가 아닌 이유)

```
React 19의 Concurrent 렌더링은 xterm.js와 충돌할 수 있음.
xterm.js는 DOM을 직접 조작하며, React의 가상 DOM 외부에서 작동함.
React 18.3의 Legacy 렌더링 모드가 더 안전하고 예측 가능.
필요 시 React 19로 마이그레이션 가능 (터미널 래퍼를 StrictMode 밖에 배치).
```

### 4.3 테스트

| 레벨 | 도구 | 대상 |
|------|------|------|
| Unit | Vitest | SOT, Action, 미들웨어, 유틸, 테마 파서 |
| Integration | Vitest + electron-mock-ipc | IPC, Socket, Hook, 세션 |
| E2E | Playwright (Electron) | UI 워크플로우, 에이전트 |
| Terminal I/O | 커스텀 PTY 하네스 | ConPTY I/O, winpty 폴백 |
| Browser | Playwright | 자동화 P0/P1 |
| Performance | 커스텀 벤치마크 | 키 지연, IPC, 프레임 |
| Accessibility | axe-core + Playwright | ARIA, 키보드 탐색 (GAP-13) |

### 4.4 개발 환경

| 도구 | 용도 |
|------|------|
| Vite | Renderer 빌드 + HMR |
| electron-vite | Main + Renderer 통합 빌드 |
| nodemon | Main Process 자동 재시작 |
| ESLint (flat config) | 코드 품질 |
| Prettier | 포맷 통일 |
| Husky + lint-staged | pre-commit 강제 |
| commitlint | 커밋 메시지 규칙 |

---

## 5. 터미널 데이터 경로 (GAP-3 해결)

### 5.1 Primary: Renderer 직접 PTY

```
키보드 → xterm.js (Renderer)
           │
           ▼
         node-pty (Renderer preload에서 실행)
           │
           ▼
         ConPTY (Windows 커널)
           │
           ▼ (응답)
         node-pty.onData
           │
           ▼
         xterm.js.write()
           │
           ▼
         화면 (WebGL/Canvas)

IPC 경유 없음 → 지연 ≤5ms 목표

구현:
  - preload.ts에서 node-pty를 import
  - contextBridge로 PTY API를 Renderer에 노출:
    ptyBridge.spawn(shell, args, options)
    ptyBridge.write(data)
    ptyBridge.resize(cols, rows)
    ptyBridge.onData(callback)
    ptyBridge.kill()
  - xterm.js는 ptyBridge를 직접 호출
  - SOT에는 PTY 메타데이터만 전달 (pid, cwd, shell — 저빈도)
```

### 5.2 Fallback: WebSocket 브릿지

```
ConPTY 직접 접근이 불가능한 환경 (보안 정책 등):
  Main Process에서 로컬 WebSocket 서버 실행 (ws://localhost:임의포트)
  xterm.js attach addon이 WebSocket에 직접 연결
  바이너리 전송 (JSON 직렬화 없음)
  지연: ≤10ms 목표
```

### 5.3 ConPTY 폴백 (GAP-14 대응)

```
ConPTY 사용 불가 시 (Windows 10 1809 미만):
  winpty로 자동 폴백
  node-pty가 내부적으로 처리 (useConpty: false 옵션)

최소 지원: Windows 10 version 1809 (2018년 10월 업데이트)
권장: Windows 11
```

---

## 6. 브라우저 패널 아키텍처 (GAP-2 해결)

### 6.1 `<webview>` 태그 방식

```
선택 이유:
  - React DOM 내부에서 렌더링 → CSS 레이아웃으로 분할 패널 동기화
  - 별도 프로세스로 격리 (보안)
  - partition 속성으로 프로필별 세션 격리
  - preload script로 커스텀 API 주입 가능
  - DevTools 접근 가능

WebContentsView를 선택하지 않은 이유:
  - React DOM 밖에서 setBounds() 수동 관리 필요
  - 드래그 리사이즈 시 16ms+ 동기화 지연
  - 분할 패널 레이아웃과 독립적으로 좌표 계산해야 함
  → 복잡도 증가 + 사용자 경험 저하

<webview> deprecation 리스크 대응:
  - Electron 33 기준 <webview>는 여전히 지원됨
  - 만약 향후 제거 시: iframe + 세션 파티션으로 마이그레이션
  - 브라우저 패널 인터페이스를 추상화해두어 교체 가능하게 설계
```

### 6.2 프로필 격리

```html
<!-- React 컴포넌트 내 -->
<webview
  src={url}
  partition={`persist:profile-${profileId}`}
  preload={preloadPath}
  webpreferences="contextIsolation=yes"
/>

각 partition은 독립된:
  - 쿠키/세션 스토리지
  - localStorage/IndexedDB
  - HTTP 캐시
  - 인증 상태
```

### 6.3 옴니바 + 히스토리

```
옴니바 (주소바):
  - React 컴포넌트 (webview 상단)
  - 인라인 자동완성 (히스토리 + 검색 제안)
  - 검색엔진: Google, DuckDuckGo, Bing, Kagi, Startpage

히스토리:
  - better-sqlite3 (Main Process)
  - IPC로 쿼리: invoke('browser:history:query', prefix)
  - 프로필별 분리 테이블
```

---

## 7. SOT 상세 설계

### 7.1 상태 구조 (스키마 버전 포함 — GAP-6)

```typescript
// shared/types.ts

interface PersistedState {
  version: number;          // 스키마 버전 (GAP-6)
  state: AppState;
}

interface AppState {
  windows: WindowState[];
  workspaces: WorkspaceState[];
  panels: PanelState[];
  surfaces: SurfaceState[];
  agents: AgentSessionState[];
  notifications: NotificationState[];
  settings: SettingsState;
  shortcuts: ShortcutState;
  focus: FocusState;
}

interface WindowState {
  id: string;
  workspaceIds: string[];
  geometry: { x: number; y: number; width: number; height: number };
  isActive: boolean;
}

interface WorkspaceState {
  id: string;
  windowId: string;
  name: string;
  color?: string;
  panelLayout: PanelLayoutTree;
  agentPids: Record<string, number>;
  statusEntries: StatusEntry[];
  unreadCount: number;
  isPinned: boolean;
  remoteSession?: RemoteSessionState;
}

type PanelLayoutTree =
  | { type: 'leaf'; panelId: string }
  | { type: 'split'; direction: 'horizontal' | 'vertical';
      ratio: number; children: [PanelLayoutTree, PanelLayoutTree] };

interface PanelState {
  id: string;
  workspaceId: string;
  panelType: 'terminal' | 'browser' | 'markdown';
  surfaceIds: string[];
  activeSurfaceId: string;
  isZoomed: boolean;
}

interface SurfaceState {
  id: string;
  panelId: string;
  surfaceType: 'terminal' | 'browser' | 'markdown';
  title: string;
  terminal?: { pid: number; cwd: string; shell: string };
  browser?: { url: string; profileId: string; isLoading: boolean };
  markdown?: { filePath: string };
}

interface AgentSessionState {
  sessionId: string;
  agentType: 'claude' | 'codex' | 'gemini' | 'opencode';
  workspaceId: string;
  surfaceId: string;
  status: 'running' | 'idle' | 'needs_input';
  statusIcon: string;       // ⚡ ⏸ 🔔
  statusColor: string;
  pid?: number;
  lastActivity: number;
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
    language: 'system' | 'en' | 'ko' | 'ja';
    iconMode: 'auto' | 'colorful' | 'monochrome';
  };
  terminal: {
    defaultShell: 'powershell' | 'cmd' | 'wsl' | 'git-bash';
    fontSize: number;
    fontFamily: string;
    themeName: string;       // Ghostty 호환 테마명
    cursorStyle: 'block' | 'underline' | 'bar';
  };
  browser: {
    searchEngine: 'google' | 'duckduckgo' | 'bing' | 'kagi' | 'startpage';
    searchSuggestions: boolean;
    httpAllowlist: string[];
    externalUrlPatterns: string[];
  };
  socket: {
    mode: 'off' | 'cmux-only' | 'automation' | 'password' | 'allow-all';
    port: number;
  };
  agents: {
    claudeHooksEnabled: boolean;
    codexHooksEnabled: boolean;
    geminiHooksEnabled: boolean;
    orchestrationMode: 'auto' | 'claude-teams' | 'self-managed';
  };
  telemetry: { enabled: boolean };
  updates: { autoCheck: boolean; channel: 'stable' | 'nightly' };
  accessibility: { screenReaderMode: boolean; reducedMotion: boolean };
}
```

### 7.2 스키마 마이그레이션 체인 (GAP-6)

```typescript
// main/sot/migrations.ts

type Migration = {
  fromVersion: number;
  toVersion: number;
  migrate: (oldState: unknown) => unknown;
};

const migrations: Migration[] = [
  // 향후 스키마 변경 시 여기에 추가
  // { fromVersion: 1, toVersion: 2, migrate: (s) => ({...s, newField: default}) },
];

function loadAndMigrate(persisted: PersistedState): AppState {
  let { version, state } = persisted;

  // 마이그레이션 전 백업 (원본 JSON 보존)
  backupSessionFile(persisted);

  for (const m of migrations) {
    if (version === m.fromVersion) {
      state = m.migrate(state);
      version = m.toVersion;
    }
  }

  if (version !== CURRENT_VERSION) {
    // 마이그레이션 실패 → 빈 상태 + 사용자 알림
    return createDefaultState();
  }

  return state as AppState;
}
```

### 7.3 Typesafe IPC (GAP-7)

```typescript
// shared/ipc-contract.ts

import { z } from 'zod';

// 모든 IPC 채널의 입출력 스키마 정의
const IpcContract = {
  // Renderer → Main (Action dispatch)
  'dispatch': {
    input: ActionSchema,          // Zod 스키마
    output: z.object({ ok: z.boolean(), error: z.string().optional() }),
  },

  // Main → Renderer (상태 브로드캐스트)
  'state:update': {
    payload: z.object({
      windowId: z.string(),       // GAP-8: 윈도우별 필터링
      slice: z.string(),          // 변경된 상태 슬라이스 이름
      data: z.unknown(),          // 슬라이스 데이터
    }),
  },

  // Renderer → Main (쿼리)
  'query:state': {
    input: z.object({ windowId: z.string(), slice: z.string() }),
    output: z.unknown(),
  },

  // PTY 메타데이터 (저빈도, SOT 업데이트용)
  'pty:metadata': {
    input: z.object({ surfaceId: z.string(), cwd: z.string(), title: z.string() }),
    output: z.void(),
  },

  // 브라우저 히스토리 쿼리
  'browser:history:query': {
    input: z.object({ profileId: z.string(), prefix: z.string(), limit: z.number() }),
    output: z.array(z.object({ url: z.string(), title: z.string(), visitedAt: z.number() })),
  },
};

// Main에서: typesafe handler 등록
// Renderer에서: typesafe invoke 호출
// 양쪽 모두 Zod 검증 통과해야 실행됨
```

### 7.4 멀티 윈도우 SOT 구독 (GAP-8)

```typescript
// main/sot/ipc-broadcast.ts

class IpcBroadcastMiddleware {
  // 각 BrowserWindow 생성 시 windowId와 webContents를 등록
  private windowRegistry: Map<string, Electron.WebContents> = new Map();

  register(windowId: string, webContents: Electron.WebContents) {
    this.windowRegistry.set(windowId, webContents);
    webContents.on('destroyed', () => this.windowRegistry.delete(windowId));
  }

  // 상태 변경 브로드캐스트
  broadcast(action: Action, changedSlices: string[]) {
    for (const [windowId, wc] of this.windowRegistry) {
      // 해당 윈도우와 관련된 슬라이스만 전송
      const relevantSlices = changedSlices.filter(
        slice => this.isRelevantToWindow(windowId, slice)
      );
      if (relevantSlices.length > 0) {
        wc.send('state:update', { windowId, slices: relevantSlices, data: /* ... */ });
      }
    }
  }

  private isRelevantToWindow(windowId: string, slice: string): boolean {
    // 글로벌 슬라이스 (settings, shortcuts): 모든 윈도우에 전송
    // 윈도우별 슬라이스 (workspaces, panels): 해당 윈도우만
    // 알림/에이전트: 모든 윈도우에 전송
    // ...
  }
}
```

---

## 8. AI 에이전트 오케스트레이션 (GAP-1/10 해결)

### 8.1 하이브리드 전략

```
앱 시작 시:
  1. Claude Code 설치 여부 확인 (which claude 또는 where claude)
  2. Claude Code 버전 확인 (claude --version)
  3. teammate mode 지원 여부 프로빙:
     - CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 환경변수 인식 테스트
     - tmux 명령 실행 가능 여부 테스트

  지원 확인됨 → 경로 A (tmux.cmd shim)
  지원 미확인 → 경로 B (자체 오케스트레이션)
  사용자 수동 선택 → settings.agents.orchestrationMode
```

### 8.2 경로 A: tmux.cmd Shim (Claude Teams 지원 시)

```
Windows 네이티브 shim 생성:

파일: %APPDATA%/cmux-win/shims/tmux.cmd
내용:
  @echo off
  "%CMUX_WIN_CLI%" __tmux-compat %*

파일: %APPDATA%/cmux-win/shims/tmux (WSL/Git Bash용)
내용:
  #!/bin/sh
  exec "$CMUX_WIN_CLI" __tmux-compat "$@"

환경변수 설정:
  PATH=%APPDATA%/cmux-win/shims;%PATH%        ← Windows PATH 구분자 ";"
  TMUX=%TEMP%\cmux-win-teams\<ws>,<win>,<pane> ← Windows 경로
  TMUX_PANE=%<pane_handle>
  CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
  CMUX_WIN_CLI=<cmux-win.exe 경로>
  CMUX_SOCKET_ADDR=tcp://127.0.0.1:19840       ← GAP-5 스킴 명시
  CMUX_SURFACE_ID=<UUID>
  CMUX_WORKSPACE_ID=<UUID>

tmux.cmd 명령 매핑:
  ┌──────────────────────────┬─────────────────────────────────┐
  │ tmux 명령                 │ Socket Action                   │
  ├──────────────────────────┼─────────────────────────────────┤
  │ new-session -n <name>    │ workspace.create { name }       │
  │ new-window -n <name>     │ workspace.create { name }       │
  │ split-window [-h|-v]     │ panel.split { direction }       │
  │ send-keys -t <id> <text> │ surface.send_text { id, text }  │
  │ select-pane -t <id>      │ panel.focus { id }              │
  │ select-window -t <id>    │ workspace.select { id }         │
  │ kill-pane -t <id>        │ panel.close { id }              │
  │ kill-window -t <id>      │ workspace.close { id }          │
  │ list-panes               │ pane.list                       │
  │ list-windows             │ workspace.list                  │
  │ resize-pane -L/-R/-U/-D  │ panel.resize { id, delta }      │
  │ capture-pane             │ surface.read                    │
  │ display-message -p       │ (stdout 출력)                    │
  │ last-pane                │ focus.last_panel                │
  │ swap-pane                │ panel.swap                      │
  │ break-pane               │ panel.break_to_workspace        │
  │ join-pane                │ panel.join                      │
  └──────────────────────────┴─────────────────────────────────┘
```

### 8.3 경로 B: 자체 오케스트레이션 (폴백)

```
Claude Teams가 Windows에서 작동하지 않을 경우의 완전한 대안.

UI에서의 에이전트 관리:
  1. 사이드바 하단: [+ 에이전트 추가] 버튼
  2. 클릭 → 드롭다운: Claude / Codex / Gemini / 커스텀
  3. 선택 → 새 분할 패널 생성 + 에이전트 CLI 실행
  4. Hook 시스템이 세션 추적

커맨드 팔레트에서:
  Cmd+Shift+P → "Add Agent" → 에이전트 선택 → 패널 생성

CLI에서:
  cmux-win spawn-agent --type codex --task "write tests for auth module"
  cmux-win spawn-agent --type gemini --task "research best practices"
  → 새 패널 생성 + 에이전트 실행 + Hook 주입

Socket API:
  agent.spawn { type: 'codex', task: '...', targetWorkspaceId: '...' }
  → SOT: surface.create + agent.session_start
  → UI: 새 패널 나타남 + 사이드바 상태 업데이트

에이전트 간 통신:
  리더(Claude)가 직접 관리하지 않으므로:
  - 사용자가 수동으로 에이전트에게 지시
  - 또는 CLI 스크립트로 자동화:
    cmux-win send --surface <codex-id> "run tests"
    cmux-win send --surface <gemini-id> "summarize findings"
```

### 8.4 Hook 시스템 (두 경로 공통)

```
래퍼 스크립트:

claude.cmd:
  @echo off
  setlocal
  if not defined CMUX_SURFACE_ID goto :passthrough
  :: 소켓 health check
  "%CMUX_WIN_CLI%" ping >nul 2>&1
  if errorlevel 1 goto :passthrough
  :: Hook 주입 + Claude 실행
  set CMUX_CLAUDE_PID=%RANDOM%%RANDOM%
  "%REAL_CLAUDE%" --session-id %SESSION_ID% --settings "{\"hooks\":{...}}" %*
  goto :eof
  :passthrough
  "%REAL_CLAUDE%" %*

claude.ps1:
  if (-not $env:CMUX_SURFACE_ID) { & $RealClaude @args; return }
  # 소켓 health check
  try { & $CmuxWinCli ping | Out-Null } catch { & $RealClaude @args; return }
  # Hook 주입 + Claude 실행
  $env:CMUX_CLAUDE_PID = [System.Diagnostics.Process]::GetCurrentProcess().Id
  & $RealClaude --session-id $SessionId --settings $HooksJson @args

Hook JSON (cmux 동일):
  {
    "hooks": {
      "SessionStart":     { "command": "cmux-win claude-hook session-start",  "timeout": 10 },
      "Stop":             { "command": "cmux-win claude-hook stop",           "timeout": 10 },
      "SessionEnd":       { "command": "cmux-win claude-hook session-end",    "timeout": 1 },
      "Notification":     { "command": "cmux-win claude-hook notification",   "timeout": 10 },
      "UserPromptSubmit": { "command": "cmux-win claude-hook prompt-submit",  "timeout": 10 },
      "PreToolUse":       { "command": "cmux-win claude-hook pre-tool-use",   "timeout": 5, "async": true }
    }
  }

Hook → SOT Action:
  session-start  → agent.session_start
  prompt-submit  → agent.status_update { status: 'running', icon: '⚡' }
  pre-tool-use   → agent.status_update { status: 'running' } (async)
  notification   → agent.status_update { status: 'needs_input', icon: '🔔' }
                 + notification.create
  stop           → agent.status_update { status: 'idle', icon: '⏸' }
  session-end    → agent.session_end + agent.clear_pid

세션 스토어:
  위치: %APPDATA%/cmux-win/claude-hook-sessions.json
  잠금: proper-lockfile (Windows 호환)
  TTL: 7일 자동 정리
  PID 검증: 5초마다 tasklist /FI "PID eq <pid>" 로 생존 확인
```

---

## 9. Socket API

### 9.1 전송 계층 (GAP-5 해결)

```
기본: TCP localhost:19840

주소 체계:
  CMUX_SOCKET_ADDR=tcp://127.0.0.1:19840

  CLI가 주소를 파싱하는 규칙:
    tcp://host:port  → TCP 소켓 연결
    pipe://name      → Windows Named Pipe (옵션)
    /path/to/sock    → Unix 소켓 (WSL 내부용)

  기본값: tcp://127.0.0.1:19840
  포트 충돌 시: 자동 증가 (19841, 19842, ...)

프로토콜: 개행 구분 JSON-RPC 2.0
인증: cmux 동일 5단계 (off/cmux-only/automation/password/allow-all)
```

### 9.2 명령 체계 (cmux V2 호환)

```
시스템:
  system.ping, system.identify, system.capabilities

윈도우:
  window.list, window.current, window.create, window.focus, window.close

워크스페이스:
  workspace.list, workspace.current, workspace.create, workspace.select,
  workspace.close, workspace.rename, workspace.reorder, workspace.move_to_window

패널:
  pane.list, pane.focus, pane.create, pane.close,
  pane.resize, pane.swap, pane.break, pane.join

서피스:
  surface.list, surface.focus, surface.create, surface.close,
  surface.send_text, surface.send_key, surface.read, surface.move,
  surface.split, surface.health, surface.trigger_flash, surface.reorder

브라우저:
  browser.navigate, browser.back, browser.forward, browser.reload,
  browser.url.get, browser.snapshot, browser.eval, browser.wait,
  browser.click, browser.dblclick, browser.type, browser.fill,
  browser.press, browser.keydown, browser.keyup, browser.hover,
  browser.focus, browser.check, browser.uncheck, browser.select,
  browser.scroll, browser.scroll_into_view, browser.screenshot,
  browser.find.role, browser.find.text, browser.find.label,
  browser.find.placeholder, browser.find.testid,
  browser.find.first, browser.find.last, browser.find.nth,
  browser.dialog.accept, browser.dialog.dismiss,
  browser.console.list, browser.console.clear,
  browser.errors.list, browser.errors.clear,
  browser.highlight, browser.state.save, browser.state.load,
  browser.cookies.get, browser.cookies.set, browser.cookies.clear,
  browser.tab.new, browser.tab.list, browser.tab.switch, browser.tab.close

알림:
  notification.create, notification.list, notification.clear

상태:
  status.set, status.clear, status.list
  progress.set, progress.clear

에이전트 (cmux 호환 + 확장):
  agent.session_start, agent.status_update, agent.session_end,
  agent.set_pid, agent.clear_pid,
  agent.spawn (신규 — 자체 오케스트레이션용)

설정:
  settings.get, settings.update

디버그 (DEBUG 빌드만):
  debug.layout, debug.performance, debug.state_history
```

---

## 10. 성능 전략 (GAP-3/4 해결)

### 10.1 성능 예산

| 지표 | 목표 | 방법 |
|------|------|------|
| 키 입력 → 화면 | ≤10ms | Renderer 직접 PTY (IPC 없음) |
| IPC 라운드트립 | ≤5ms | SOT 메타데이터 전용 |
| 패널 분할 생성 | ≤100ms | Action → DOM 업데이트 |
| 앱 시작 | ≤3s | 지연 로딩, 세션 복원은 비동기 |
| 메모리 (베이스) | ≤300MB | 터미널 1개, 빈 상태 |

### 10.2 xterm.js 렌더러 동적 전환 (GAP-4)

```
전략:
  - 포커스된 패널: WebGL 렌더러 (최고 성능)
  - 인접 패널 (화면에 보이는): WebGL (최대 3개)
  - 비활성/숨겨진 패널: Canvas 렌더러로 폴백
  - GPU 컨텍스트 손실 시: 자동으로 Canvas 전환 + 포커스 시 WebGL 재시도

  WebGL 인스턴스 수 제한: 최대 4개 동시
  webglcontextlost 이벤트 핸들링 필수
  dispose() 후 명시적 GPU 리소스 해제 시도
```

### 10.3 UI 최적화

```
1. xterm.js는 React 외부 DOM 직접 마운트
   - useRef로 컨테이너 div만 관리
   - useEffect에서 xterm.Terminal 인스턴스 생성
   - React 리렌더와 무관하게 동작

2. 사이드바 가상화
   - react-virtuoso로 50개+ 워크스페이스 처리
   - 화면에 보이는 항목만 DOM에 존재

3. SOT 브로드캐스트 최적화
   - 16ms 디바운스 (requestAnimationFrame 동기화)
   - 변경된 슬라이스만 전송 (diff 기반)
   - Renderer는 React.memo + 얕은 비교로 불필요한 리렌더 방지

4. 비동기 작업 오프로드
   - 포트 스캔: Worker Thread (netstat 파싱)
   - 세션 스냅샷: 디바운스 500ms + 비동기 파일 I/O
   - 테마 파싱: 빌드 타임 캐시 (90+ 테마 → JSON)
```

---

## 11. 에러 복구 전략 (GAP-8 강화)

```
┌────────────────┬──────────────────────────────────────────────────┐
│ 장애 유형       │ 복구 전략                                         │
├────────────────┼──────────────────────────────────────────────────┤
│ PTY 크래시      │ 1. SOT에서 cwd/shell 읽기                        │
│                │ 2. 동일 설정으로 PTY 재생성                        │
│                │ 3. 스크롤백은 복원 불가 (사용자 알림)               │
│                │ 4. 연속 3회 크래시 → winpty 폴백 시도              │
├────────────────┼──────────────────────────────────────────────────┤
│ WebView 크래시  │ 1. <webview>의 crashed 이벤트 감지               │
│                │ 2. SOT에서 url/profileId 읽기                     │
│                │ 3. webview 재생성 + URL 로드                      │
│                │ 4. 사용자에게 "페이지가 다시 로드되었습니다" 알림    │
├────────────────┼──────────────────────────────────────────────────┤
│ 에이전트 세션   │ 1. 5초마다 PID 생존 확인 (tasklist)              │
│ 끊김           │ 2. PID 없음 → agent.session_end 발행             │
│                │ 3. 사이드바 상태 정리                              │
│                │ 4. 알림: "<에이전트>가 종료되었습니다"              │
├────────────────┼──────────────────────────────────────────────────┤
│ Socket 포트    │ 1. 기본 포트(19840) bind 실패 감지                │
│ 충돌           │ 2. 자동 증가 (19841, 19842, ... 최대 10회)       │
│                │ 3. 실제 포트를 환경변수/파일로 기록                 │
│                │ 4. CLI가 포트 자동 탐지                           │
├────────────────┼──────────────────────────────────────────────────┤
│ 세션 복원 실패  │ 1. 원본 JSON 자동 백업 (session.json.bak)        │
│                │ 2. 마이그레이션 시도                               │
│                │ 3. 실패 → 부분 복원 (파싱 가능한 워크스페이스만)    │
│                │ 4. 전체 실패 → 빈 상태 + 사용자 알림              │
├────────────────┼──────────────────────────────────────────────────┤
│ 앱 비정상 종료  │ 1. 디바운스 스냅샷으로 최대 500ms 손실            │
│                │ 2. 다음 시작 시 마지막 스냅샷에서 자동 복원         │
│                │ 3. 복원 성공 → "이전 세션이 복원되었습니다"         │
├────────────────┼──────────────────────────────────────────────────┤
│ ConPTY 미지원  │ 1. Windows 버전 확인 (1809 미만?)                 │
│                │ 2. winpty 자동 폴백 (node-pty useConpty: false)   │
│                │ 3. 설정에서 수동 전환 가능                         │
│                │ 4. 안티바이러스 차단 감지 → 사용자 안내             │
├────────────────┼──────────────────────────────────────────────────┤
│ GPU 컨텍스트   │ 1. webglcontextlost 이벤트 핸들링                 │
│ 손실           │ 2. Canvas 렌더러로 즉시 폴백                      │
│                │ 3. 포커스 시 WebGL 복구 시도                       │
│                │ 4. 연속 실패 → Canvas 영구 전환                    │
└────────────────┴──────────────────────────────────────────────────┘
```

---

## 12. Ghostty 테마 변환 (GAP-9)

```typescript
// main/terminal/theme-parser.ts

// Ghostty 테마 형식
// palette = 0=#1d1f21
// palette = 1=#cc6666
// background = #1d1f21
// foreground = #c5c8c6

// xterm.js 테마 형식
// { background: '#1d1f21', foreground: '#c5c8c6', black: '#1d1f21', red: '#cc6666', ... }

interface GhosttyTheme {
  palette: Record<number, string>;  // 0-15
  background: string;
  foreground: string;
  cursor_color?: string;
  selection_background?: string;
  selection_foreground?: string;
}

const ANSI_TO_XTERM: Record<number, string> = {
  0: 'black', 1: 'red', 2: 'green', 3: 'yellow',
  4: 'blue', 5: 'magenta', 6: 'cyan', 7: 'white',
  8: 'brightBlack', 9: 'brightRed', 10: 'brightGreen', 11: 'brightYellow',
  12: 'brightBlue', 13: 'brightMagenta', 14: 'brightCyan', 15: 'brightWhite',
};

function ghosttyToXterm(ghostty: GhosttyTheme): ITheme {
  const theme: Record<string, string> = {
    background: ghostty.background,
    foreground: ghostty.foreground,
  };
  if (ghostty.cursor_color) theme.cursor = ghostty.cursor_color;
  if (ghostty.selection_background) theme.selectionBackground = ghostty.selection_background;
  if (ghostty.selection_foreground) theme.selectionForeground = ghostty.selection_foreground;

  for (const [index, color] of Object.entries(ghostty.palette)) {
    const xtermKey = ANSI_TO_XTERM[Number(index)];
    if (xtermKey) theme[xtermKey] = color;
  }
  return theme as ITheme;
}

// 라이트/다크 쌍 지원: "light:Solarized Light,dark:Solarized Dark"
function resolveThemePair(themeSpec: string, isDark: boolean): string {
  if (!themeSpec.includes(',')) return themeSpec;
  const parts = themeSpec.split(',').map(s => s.trim());
  for (const part of parts) {
    if (isDark && part.startsWith('dark:')) return part.slice(5);
    if (!isDark && part.startsWith('light:')) return part.slice(6);
  }
  return parts[0].replace(/^(light|dark):/, '');
}

// 빌드 타임: 90+ .theme 파일 → themes.json 캐시
// 런타임: themes.json 로드 → 테마 선택 → ghosttyToXterm 변환
```

---

## 13. macOS 기능 대응표 (GAP-12)

```
┌────────────────────────┬────────────────────────┬─────────────┐
│ cmux (macOS)            │ cmux-win (Windows)      │ 구현 방식    │
├────────────────────────┼────────────────────────┼─────────────┤
│ Ghostty 터미널 엔진     │ xterm.js + node-pty    │ 대체 구현    │
│ Metal GPU 렌더링        │ WebGL (xterm.js addon) │ 대체 구현    │
│ AppKit/SwiftUI UI      │ React + CSS            │ 대체 구현    │
│ Bonsplit 분할 패널      │ CSS Grid + 커스텀 트리  │ 대체 구현    │
│ WKWebView 브라우저      │ <webview> 태그         │ 대체 구현    │
│ Unix Domain Socket     │ TCP localhost           │ 대체 구현    │
│ Sparkle 자동 업데이트    │ electron-updater       │ 대체 구현    │
│ macOS 알림 센터         │ Windows Toast          │ 대체 구현    │
│ Dock 뱃지              │ 시스템 트레이 아이콘     │ 대체 구현    │
│ Keychain              │ Credential Manager      │ 대체 구현    │
│ NSPasteboard          │ Electron clipboard      │ 대체 구현    │
│ lsof/ps 포트 스캔      │ netstat -ano + Worker   │ 대체 구현    │
│ flock() 파일 잠금      │ proper-lockfile         │ 대체 구현    │
│ zsh/bash 셸 통합       │ PS/CMD/WSL/Git Bash    │ 대체 구현    │
│ Carbon 키보드 레이아웃  │ Windows IME API        │ 대체 구현    │
│ CJK IME               │ xterm.js IME 지원       │ 네이티브     │
├────────────────────────┼────────────────────────┼─────────────┤
│ AppleScript 자동화     │ 미지원 (Phase 7+)       │ 향후 검토    │
│ macOS Services         │ 미지원 (Phase 7+)       │ 향후 검토    │
│ cmuxd-remote SSH 데몬  │ 동일 (Go, 크로스플랫폼) │ 재사용       │
│ 90+ Ghostty 테마       │ 변환 후 재사용          │ 파서 구현    │
│ 다국어 (영/일/한)      │ i18next                │ 대체 구현    │
└────────────────────────┴────────────────────────┴─────────────┘

명시적으로 미지원:
  - AppleScript → Windows에 동등한 스크립팅 없음 (COM Automation은 범위 다름)
  - macOS Services → Shell Extension은 Electron에서 구현 비용 과도
  - 이 두 기능은 Phase 7 이후 별도 검토
```

---

## 14. 접근성 (GAP-13)

```
Phase 6에 포함:

1. 키보드 전용 탐색
   - 모든 UI 요소에 tabindex 순서
   - 사이드바: 화살표 키 탐색
   - 패널: Cmd+Alt+방향키 포커스 이동
   - 커맨드 팔레트: 모든 기능 키보드 접근 가능

2. 스크린 리더
   - xterm.js 접근성 모드 활성화 (settings.accessibility.screenReaderMode)
   - 모든 버튼/입력 필드에 aria-label
   - 상태 변경 시 aria-live 알림
   - 에이전트 상태 변경 → 스크린 리더 안내

3. 시각 접근성
   - 고대비 테마 번들
   - reducedMotion 설정 시 애니메이션 비활성화
   - 포커스 표시자 항상 가시

4. 테스트
   - axe-core 자동 스캔 (CI)
   - Playwright 키보드 전용 E2E
```

---

## 15. TDD 자동화 전략

### 15.1 강제 메커니즘

```
1. 테스트 우선 스캐폴딩
   $ npm run create-module -- --name terminal-manager --path main/terminal
   → src/main/terminal/terminal-manager.ts         (빈 export)
   → tests/unit/terminal/terminal-manager.test.ts   (describe 블록 + 실패 테스트)

2. Pre-commit Hook (Husky + lint-staged)
   → 변경된 .ts 파일의 대응 .test.ts 실행
   → 테스트 실패 시 커밋 차단
   → 새 모듈에 테스트 파일 없으면 경고

3. CI 게이트 (GitHub Actions)
   PR 머지 조건:
   - 전체 테스트 통과
   - 커버리지가 기존 대비 하락하면 차단
   - Phase별 최소 커버리지 충족

4. 커버리지 게이트
   Phase 1 (기반):    ≥90%  (SOT, IPC, 소켓은 버그 허용 불가)
   Phase 2 (UI):     ≥80%  (레이아웃 로직)
   Phase 3 (브라우저): ≥80%
   Phase 4 (에이전트): ≥90%  (오케스트레이션은 버그 허용 불가)
   Phase 5 (셸/원격): ≥85%
   Phase 6 (완성도):  ≥80%
```

### 15.2 테스트 카테고리

```
Unit (Vitest):
  - SOT: 모든 Action → 상태 변경 검증 (정상 + 에러)
  - 미들웨어: 검증, 영구저장, 브로드캐스트 각각
  - 테마 파서: Ghostty → xterm.js 변환
  - 퍼지 검색: 알고리즘 정확도
  - 스키마 마이그레이션: 각 버전 전이

Integration (Vitest + mocks):
  - IPC: Renderer dispatch → Main 처리 → 결과 반환
  - Socket: TCP 연결 → JSON-RPC → Action → 응답
  - Hook: claude-hook 명령 → SOT 업데이트
  - 세션: 스냅샷 저장 → 복원 → 상태 일치 검증

E2E (Playwright Electron):
  - 에이전트 오케스트레이션: 팀원 스폰 → 상태 추적 → 정리
  - 터미널 분할: 4분할 → 포커스 전환 → 리사이즈
  - 브라우저 패널: URL 로드 → find → DevTools
  - 세션 퍼시스턴스: 레이아웃 저장 → 재시작 → 복원
  - 키보드 단축키: 모든 기본 단축키 검증

Performance (커스텀 벤치마크):
  - 키 입력 지연: ≤10ms (Renderer PTY 경로)
  - 패널 생성: ≤100ms
  - 50개 워크스페이스 렌더링: ≤16ms/프레임
```

---

## 16. 구현 Phase

### Critical Path (최단 경로: 에이전트 오케스트레이션까지)

```
Phase 1 (기반) → Phase 2 (UI) → Phase 4 (에이전트)
  ↓ 이후 병렬 가능
Phase 3 (브라우저) ‖ Phase 5 (셸/원격) ‖ Phase 6 (완성도)
```

### Phase 1 — 기반 인프라

```
1.1 프로젝트 초기화
    - Electron 33 + TypeScript strict + React 18.3 + Vite
    - ESLint + Prettier + Husky + commitlint
    - Vitest + Playwright 설정
    - GitHub Actions CI
    - TDD 스캐폴딩 스크립트 (npm run create-module)
    테스트: 빌드, 린트, 빈 테스트 실행

1.2 SOT 스토어
    - AppStateStore (EventEmitter + Immer)
    - Action Dispatcher + 미들웨어 6단계 체인
    - Zod 스키마 검증
    - 스키마 버전 + 마이그레이션 (GAP-6)
    - 상태 히스토리 (디버그, 최근 100개)
    테스트: 모든 Action CRUD, 미들웨어 순서, 검증 실패, 마이그레이션

1.3 Typesafe IPC (GAP-7)
    - IPC 계약 정의 (shared/ipc-contract.ts)
    - Main: 핸들러 등록
    - Renderer: invoke 래퍼
    - 양방향 Zod 검증
    - 멀티윈도우 브로드캐스트 (GAP-8)
    테스트: IPC 라운드트립, 타입 검증, 윈도우 필터링

1.4 터미널 엔진
    - node-pty preload 통합 (GAP-3)
    - ConPTY + winpty 폴백 (GAP-14)
    - xterm.js WebGL/Canvas 동적 전환 (GAP-4)
    - 셸 선택 (PowerShell/CMD/WSL/Git Bash)
    - React 외부 DOM 마운트
    테스트: PTY 생성/종료, 입출력, 리사이즈, 셸 전환, 렌더러 전환

1.5 Socket API 서버
    - TCP localhost 서버 (GAP-5)
    - JSON-RPC 2.0 파서 + 라우터
    - 인증 레이어 (5단계)
    - 포트 충돌 자동 해결
    테스트: 연결, 명령 실행, 인증, 포트 충돌

1.6 CLI 기본
    - cmux-win.exe (Node.js SEA)
    - tcp:// 주소 파싱 (GAP-5)
    - ping, version, list-workspaces, send, notify
    테스트: CLI → Socket → SOT → 결과 전체 경로
```

### Phase 2 — 핵심 UI

```
2.1 윈도우 관리
    - BrowserWindow ↔ windowId 매핑 (GAP-8)
    - 멀티 윈도우 생성/소멸
    - 윈도우 간 워크스페이스 이동
    - 윈도우 지오메트리 영구저장
    테스트: 멀티윈도우 CRUD, 크로스윈도우 이동

2.2 사이드바
    - 워크스페이스 목록 (react-virtuoso)
    - 드래그 재정렬
    - 컬러 커스텀
    - 에이전트 상태 뱃지 (⚡⏸🔔)
    - 알림 뱃지 + 미읽음 카운트
    - [+ 에이전트 추가] 버튼 (GAP-10 폴백)
    테스트: CRUD, 재정렬, 뱃지, 가상화 성능

2.3 분할 패널 레이아웃
    - PanelLayoutTree 기반 CSS Grid 렌더링
    - 상하좌우 분할
    - 드래그 리사이즈 (디바이더)
    - 줌/최대화 토글
    - 패널 간 포커스 이동 (방향키)
    테스트: 분할/병합/리사이즈, 포커스 방향, 줌

2.4 탭 관리
    - 패널 내 멀티탭 (PanelTabBar)
    - 탭 드래그 (패널 내 + 크로스 패널)
    - 탭 컨텍스트 메뉴
    테스트: 탭 CRUD, 드래그 이동, 포커스

2.5 키보드 단축키
    - 30개 액션 + 커스텀 가능
    - 단축키 힌트 오버레이
    - 국제 키보드 감지
    테스트: 모든 기본 단축키, 커스텀, 충돌 감지
```

### Phase 3 — 브라우저 + 마크다운

```
3.1 브라우저 패널
    - <webview> 래퍼 (GAP-2)
    - 프로필 격리 (partition)
    - 옴니바 (주소바 + 자동완성 + 검색 제안)
    - 히스토리 (better-sqlite3)
    - 네비게이션, DevTools, 보안 경고
    테스트: 네비게이션, 프로필, 히스토리, 보안

3.2 브라우저 자동화 API
    - P0: snapshot, eval, wait, click, type, fill, press, screenshot
    - P1: find.*, dialog, download, console
    테스트: P0 전체, P1 주요

3.3 Find-in-page
    - 터미널: xterm.js search addon
    - 브라우저: JS DOM TreeWalker (cmux 이식)
    - 드래그 가능 검색 오버레이
    테스트: 검색/이전/다음, 매치 카운트, 특수문자

3.4 마크다운 뷰어
    - chokidar 파일 감시
    - remark + rehype + shiki
    테스트: 렌더링, 리로드, 파일 삭제/재생성
```

### Phase 4 — AI 에이전트 오케스트레이션

```
4.1 Hook 시스템
    - claude.cmd + claude.ps1 + codex.cmd + open.cmd (GAP-1)
    - Hook JSON 주입 (6가지 라이프사이클)
    - 세션 스토어 (proper-lockfile)
    - PID 추적 + stale 감지 (tasklist)
    테스트: 라이프사이클 전체, 세션 CRUD, stale 정리

4.2 tmux Shim (경로 A)
    - tmux.cmd + tmux (WSL용) 생성 (GAP-1)
    - 17개 tmux 명령 → Socket 변환
    - TMUX/TMUX_PANE 환경변수 (Windows 경로)
    테스트: 모든 명령 매핑, 에러, 환경변수

4.3 자체 오케스트레이션 (경로 B, GAP-10)
    - agent.spawn Socket 명령
    - UI: 에이전트 추가 드롭다운
    - 커맨드 팔레트: "Add Agent"
    - 자동 패널 생성 + CLI 실행 + Hook 주입
    테스트: 에이전트 스폰 E2E, UI 통합

4.4 Claude Teams 통합
    - cmux-win claude-teams 명령
    - 경로 A/B 자동 감지
    - 리더 패널 포커스 유지
    테스트: 멀티 에이전트 E2E

4.5 상태 통합
    - 사이드바 에이전트 뱃지
    - 알림 연동
    - 에이전트 세션 복구
    테스트: 상태 전환, 알림, 복구
```

### Phase 5 — 셸 통합 + 원격

```
5.1 셸 통합
    - PowerShell: PWD, git 브랜치, dirty, PR
    - CMD: PWD (기본)
    - WSL: Linux bash 통합 재사용
    - Git Bash: bash 통합 재사용
    - 포트 스캔: netstat -ano (Worker Thread)
    테스트: 셸별 PWD, git, 포트

5.2 SSH 원격
    - cmuxd-remote 번들 (Go, 크로스플랫폼 재사용)
    - SSH 부트스트랩, RPC, 프록시
    - PTY 세션, 재접속
    테스트: 부트스트랩, RPC, 리사이즈, 재접속

5.3 세션 퍼시스턴스
    - JSON 스냅샷 (디바운스 500ms)
    - 스키마 마이그레이션 (GAP-6)
    - 복원: 레이아웃 + 스크롤백(ANSI-safe)
    - 손상 복구: 백업 → 부분 → 빈 상태
    테스트: 저장/복원, 마이그레이션, 손상 복구
```

### Phase 6 — 완성도

```
6.1 알림: 앱 내 + Windows Toast + 트레이 + 사운드
6.2 커맨드 팔레트: 퍼지 검색 + 스위처 + 에이전트 추가
6.3 설정 UI: 외형, 터미널, 브라우저, 에이전트, 단축키
6.4 자동 업데이트: electron-updater + stable/nightly
6.5 다국어: i18next (ko/en/ja)
6.6 텔레메트리: Sentry + PostHog (옵트아웃)
6.7 테마: 90+ Ghostty 테마 변환 + 프리뷰 (GAP-9)
6.8 접근성: axe-core, 키보드 탐색, aria (GAP-13)

각 항목별 테스트 필수.
```

---

## 17. 프로젝트 구조

```
cmux-win/
├── docs/
│   └── plans/
│       └── 2026-03-19-cmux-win-design-v3.md
├── src/
│   ├── main/                           # Electron Main Process
│   │   ├── app.ts                      # 진입점
│   │   ├── sot/
│   │   │   ├── store.ts                # AppStateStore (EventEmitter + Immer)
│   │   │   ├── actions.ts              # Action 타입
│   │   │   ├── reducers/               # Action별 상태 갱신
│   │   │   ├── middleware/             # 6단계 미들웨어
│   │   │   │   ├── validation.ts
│   │   │   │   ├── side-effects.ts
│   │   │   │   ├── persistence.ts
│   │   │   │   ├── ipc-broadcast.ts
│   │   │   │   └── audit-log.ts
│   │   │   └── migrations/            # 스키마 마이그레이션 (GAP-6)
│   │   ├── terminal/
│   │   │   ├── pty-manager.ts          # PTY 라이프사이클 (메타데이터)
│   │   │   ├── shell-integration/
│   │   │   │   ├── powershell.ts
│   │   │   │   ├── cmd.ts
│   │   │   │   ├── wsl.ts
│   │   │   │   └── git-bash.ts
│   │   │   ├── port-scanner.ts         # Worker Thread + netstat
│   │   │   └── theme-parser.ts         # Ghostty → xterm.js (GAP-9)
│   │   ├── browser/
│   │   │   ├── browser-manager.ts
│   │   │   ├── profile-manager.ts
│   │   │   ├── history-store.ts        # better-sqlite3
│   │   │   ├── automation/             # P0/P1 API
│   │   │   └── find-javascript.ts
│   │   ├── agents/
│   │   │   ├── orchestration.ts        # 하이브리드 감지 (GAP-1)
│   │   │   ├── hook-system.ts
│   │   │   ├── session-store.ts
│   │   │   ├── tmux-shim.ts            # Windows shim 생성 (GAP-1)
│   │   │   ├── self-orchestrator.ts    # 폴백 모드 (GAP-10)
│   │   │   └── wrappers/
│   │   │       ├── claude-wrapper.ts   # claude.cmd/ps1 생성
│   │   │       ├── codex-wrapper.ts
│   │   │       └── gemini-wrapper.ts
│   │   ├── socket/
│   │   │   ├── server.ts               # TCP localhost (GAP-5)
│   │   │   ├── router.ts               # JSON-RPC 라우터
│   │   │   ├── auth.ts                 # 5단계 인증
│   │   │   └── handlers/              # 명령 핸들러
│   │   ├── session/
│   │   │   ├── persistence.ts
│   │   │   ├── migrations.ts           # (GAP-6)
│   │   │   └── recovery.ts
│   │   ├── window/
│   │   │   └── window-manager.ts       # windowId 매핑 (GAP-8)
│   │   ├── notifications/
│   │   │   ├── notification-manager.ts
│   │   │   └── windows-toast.ts
│   │   ├── updates/
│   │   │   └── update-manager.ts
│   │   ├── performance/
│   │   │   └── monitor.ts
│   │   └── error-recovery/
│   │       └── recovery-manager.ts
│   │
│   ├── preload/                        # Electron preload scripts
│   │   ├── terminal-preload.ts         # node-pty bridge (GAP-3)
│   │   ├── browser-preload.ts          # webview preload
│   │   └── main-preload.ts             # 일반 IPC bridge
│   │
│   ├── renderer/                       # React UI
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── sidebar/
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   ├── WorkspaceItem.tsx
│   │   │   │   ├── AgentBadge.tsx
│   │   │   │   ├── AgentAddDropdown.tsx  # (GAP-10)
│   │   │   │   └── NotificationBadge.tsx
│   │   │   ├── panels/
│   │   │   │   ├── PanelLayout.tsx       # CSS Grid 분할 트리
│   │   │   │   ├── PanelContainer.tsx
│   │   │   │   ├── PanelDivider.tsx      # 드래그 리사이즈
│   │   │   │   ├── PanelTabBar.tsx
│   │   │   │   └── PanelZoomOverlay.tsx
│   │   │   ├── terminal/
│   │   │   │   ├── XTermWrapper.tsx      # React 외부 DOM (GAP-3)
│   │   │   │   └── TerminalFind.tsx
│   │   │   ├── browser/
│   │   │   │   ├── BrowserPanel.tsx      # <webview> (GAP-2)
│   │   │   │   ├── Omnibar.tsx
│   │   │   │   ├── BrowserFind.tsx
│   │   │   │   └── BrowserSettings.tsx
│   │   │   ├── markdown/
│   │   │   │   └── MarkdownPanel.tsx
│   │   │   ├── command-palette/
│   │   │   │   ├── CommandPalette.tsx
│   │   │   │   └── FuzzySearch.ts
│   │   │   ├── notifications/
│   │   │   │   └── NotificationPanel.tsx
│   │   │   ├── settings/
│   │   │   │   └── SettingsPage.tsx
│   │   │   └── shortcuts/
│   │   │       └── ShortcutHintOverlay.tsx
│   │   ├── hooks/
│   │   │   ├── useAppState.ts            # SOT 구독 (읽기 전용)
│   │   │   ├── useDispatch.ts            # typesafe dispatch (GAP-7)
│   │   │   ├── useShortcuts.ts
│   │   │   └── usePanelFocus.ts
│   │   └── styles/
│   │       └── themes/
│   │
│   ├── cli/
│   │   ├── cmux-win.ts                  # 진입점
│   │   ├── commands/                    # 서브커맨드
│   │   ├── socket-client.ts             # TCP 클라이언트 (GAP-5)
│   │   └── tmux-compat.ts              # __tmux-compat 핸들러
│   │
│   └── shared/
│       ├── types.ts                     # 전체 타입 (위 섹션 7.1)
│       ├── actions.ts                   # Action 타입
│       ├── schemas.ts                   # Zod 스키마
│       ├── ipc-contract.ts              # IPC 계약 (GAP-7)
│       ├── protocol.ts                  # JSON-RPC 프로토콜
│       └── constants.ts                 # 상수
│
├── resources/
│   ├── shims/                           # 래퍼 스크립트 템플릿
│   │   ├── claude.cmd
│   │   ├── claude.ps1
│   │   ├── codex.cmd
│   │   ├── tmux.cmd                     # (GAP-1)
│   │   ├── tmux                         # WSL/Git Bash용 (GAP-1)
│   │   └── open.cmd
│   ├── shell-integration/
│   │   ├── powershell/
│   │   ├── cmd/
│   │   └── wsl/
│   ├── themes/                          # 90+ Ghostty 호환 테마 (GAP-9)
│   └── locales/
│       ├── en.json
│       ├── ko.json
│       └── ja.json
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   ├── performance/
│   └── accessibility/                   # (GAP-13)
│
├── scripts/
│   ├── create-module.ts                 # TDD 스캐폴딩
│   └── build-themes.ts                  # Ghostty → JSON 캐시 (GAP-9)
│
├── package.json
├── tsconfig.json
├── tsconfig.main.json
├── tsconfig.renderer.json
├── tsconfig.preload.json
├── vite.config.ts                       # Renderer 빌드
├── electron-vite.config.ts              # 통합 빌드
├── vitest.config.ts
├── playwright.config.ts
├── electron-builder.yml
├── .eslintrc.cjs
├── .prettierrc
├── .husky/
│   ├── pre-commit
│   └── commit-msg
├── commitlint.config.ts
└── CLAUDE.md                            # 개발 지침
```

---

## 18. 리스크 매트릭스 및 대응

```
┌───┬──────────────────────────────┬────────┬──────────────────────────────┐
│ # │ 리스크                        │ 확률   │ 대응                          │
├───┼──────────────────────────────┼────────┼──────────────────────────────┤
│ 1 │ Claude Code가 Windows에서    │ 중간   │ 자체 오케스트레이션 폴백       │
│   │ teammate mode 미지원          │        │ (경로 B) 구현 필수             │
├───┼──────────────────────────────┼────────┼──────────────────────────────┤
│ 2 │ Electron <webview> 태그      │ 낮음   │ iframe + partition 마이그레이션 │
│   │ 향후 제거                     │        │ 브라우저 인터페이스 추상화      │
├───┼──────────────────────────────┼────────┼──────────────────────────────┤
│ 3 │ xterm.js WebGL GPU 메모리    │ 높음   │ Canvas 폴백 + 동적 전환       │
│   │ 누수 심각                     │        │ WebGL 최대 4인스턴스 제한      │
├───┼──────────────────────────────┼────────┼──────────────────────────────┤
│ 4 │ ConPTY 안티바이러스 차단      │ 중간   │ winpty 폴백 + 사용자 안내      │
├───┼──────────────────────────────┼────────┼──────────────────────────────┤
│ 5 │ 키 입력 지연 10ms 초과       │ 낮음   │ Renderer 직접 PTY로 IPC 제거  │
│   │                              │        │ WebSocket 브릿지 2차 폴백      │
├───┼──────────────────────────────┼────────┼──────────────────────────────┤
│ 6 │ 세션 스키마 마이그레이션 버그 │ 중간   │ 자동 백업 + 부분 복원 + 빈 상태│
├───┼──────────────────────────────┼────────┼──────────────────────────────┤
│ 7 │ Electron 버전 업그레이드 시   │ 중간   │ Electron 33 고정, 보안 패치만  │
│   │ API 호환성 깨짐              │        │ 메이저 업그레이드는 별도 작업   │
└───┴──────────────────────────────┴────────┴──────────────────────────────┘
```

---

## 19. 개발 워크플로우 (GAP-11)

```
개발 시작:
  git clone <repo>
  npm install
  npm run dev          → electron-vite dev (Main + Renderer 동시)
                         Renderer: Vite HMR (즉시 반영)
                         Main: 변경 감지 → 자동 재시작

디버그:
  VS Code: Electron 디버깅 launch.json 제공
  Main Process: --inspect 플래그
  Renderer: Chrome DevTools (Ctrl+Shift+I)
  로그: %TEMP%/cmux-win-debug.log

테스트:
  npm test             → Vitest (unit + integration)
  npm run test:e2e     → Playwright (E2E)
  npm run test:perf    → 성능 벤치마크
  npm run test:a11y    → 접근성 스캔
  npm run test:cover   → 커버리지 리포트

빌드:
  npm run build        → electron-builder (Windows 인스톨러)
  npm run build:cli    → Node.js SEA (cmux-win.exe)

모듈 생성 (TDD):
  npm run create-module -- --name <name> --path <path>
  → 테스트 파일 먼저 생성 → 모듈 스켈레톤 생성
```

---

## 20. 검증 완료 체크리스트

2차 성찰에서 발견한 14개 GAP의 반영 상태:

```
[✓] GAP-1:  Claude Teams Windows 미작동    → 하이브리드 전략 (경로 A + B)
[✓] GAP-2:  WebContentsView DOM 밖        → <webview> 태그 (React DOM 내)
[✓] GAP-3:  IPC 키 지연 초과              → Renderer 직접 PTY (preload)
[✓] GAP-4:  WebGL GPU 메모리 누수          → 동적 렌더러 전환 (최대 4)
[✓] GAP-5:  SOCKET_PATH 호환성            → tcp:// 스킴 + CMUX_SOCKET_ADDR
[✓] GAP-6:  세션 스키마 버전 없음          → 버전 + 마이그레이션 체인
[✓] GAP-7:  Renderer→Main 통신 미정의      → typesafe IPC (Zod 양방향)
[✓] GAP-8:  멀티윈도우 매핑 미정의          → windowId 기반 구독 필터링
[✓] GAP-9:  테마 변환 없음                → Ghostty→xterm.js 파서
[✓] GAP-10: Plan B 없음                   → 자체 오케스트레이션 UI
[✓] GAP-11: 개발 워크플로우 없음           → electron-vite + HMR
[✓] GAP-12: macOS 기능 대응 미정의         → 기능별 대응표
[✓] GAP-13: 접근성 미언급                  → Phase 6 + axe-core
[✓] GAP-14: ConPTY 특수 문제              → winpty 폴백 + 최소 버전
```
