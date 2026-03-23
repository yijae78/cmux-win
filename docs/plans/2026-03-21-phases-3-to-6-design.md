# cmux-win Phases 3-6 통합 설계안 (완전판 v3)

> **작성일**: 2026-03-21
> **선행 완료**: Phase 1 (기반, Tasks 1-9), Phase 2 (UI, Tasks 10pre-15)
> **설계안 정본**: `2026-03-19-cmux-win-design-v3.md`
> **현재 상태**: 소스 46파일, 테스트 19파일 182개 통과
> **원칙**: cmux(macOS)의 모든 기능/설계를 Windows에 동일하게 이식
> **이 문서가 Phase 3-6 유일한 설계 정본이다.**

---

## Critical Path

```
[완료] Phase 1 (기반) → [완료] Phase 2 (UI) → Phase 4 (에이전트) ← 즉시 착수
                                                ↓
                          Phase 3 (브라우저) ‖ Phase 5 (셸/원격) ‖ Phase 6 (완성도)
```

---

## 성찰 반영 사항

### 1-2차 성찰 (Phase 4 설계 과정)

| # | 성찰 | 반영 |
|---|------|------|
| R1 | 통신 방향이 거꾸로 — Main→Claude가 아니라 Claude→cmux-win | ClaudeHookClient 삭제, CLI 역방향 호출만 |
| R2 | CMD batch에서 JSON 생성 불가 | claude.cmd는 trampoline, 실제 로직은 Node.js |
| R3 | 기존 agent.* Action 재활용 가능 | 저수준 set_status 명령 불필요, 기존 RPC 사용 |
| R4 | 세션 스토어는 SOT 외부 (CLI 직접 접근) | 별도 JSON 파일 (%APPDATA%) |
| R5 | codex/gemini 래퍼는 cmux에도 없음 | claude 래퍼만 구현 |
| R6 | process.kill(pid, 0) Windows 동작 확인 | tasklist 불필요 |
| R7 | 환경변수 주입 경로 불명확 | preload 자체 구성으로 변경 (3차 성찰) |

### 3차 성찰 (전체 설계안 검토)

| # | 결함 | 심각도 | 수정 |
|---|------|--------|------|
| F1 | socketAlive() async인데 동기 흐름에서 호출 | **높음** | 전체 래퍼를 async IIFE로 감싸기 |
| F2 | session_id를 env에서 읽지만 실제는 stdin JSON | **높음** | stdin JSON에서 읽기로 통일 |
| F3 | env를 Renderer에서 구성 → prop drilling 5단계 | **중간** | preload 자체 구성, surfaceId/workspaceId만 전달 |
| F4 | surface.update_url Action 미정의 | **중간** | surface.update_meta Action 추가 |
| F5 | tmux -t 플래그 ID 변환 미설계 | **중간** | list → index-to-UUID 매핑 |
| F6 | better-sqlite3 빌드/config 누락 | **낮음** | 의존성/external 명시 |
| F7 | 코드 서명 미언급 | **낮음** | Phase 6 배포에 추가 |
| F8 | ssh.exe 미존재 폴백 없음 | **낮음** | ssh2 폴백 또는 안내 |
| F9 | Task별 에러 핸들링 불충분 | **낮음** | 각 Task에 에러 시나리오 추가 |
| F10 | 자체 오케스트레이션 (경로 B) 누락 | **높음** | Task 22 추가: agent.spawn + UI |

### 4차 성찰 (전면 정밀 검토)

| # | 결함 | 심각도 | 수정 |
|---|------|--------|------|
| F11 | Socket 포트 하드코딩 19840, 실제 바인딩 포트와 불일치 | **높음** | Main Process가 실제 포트를 process.env에 설정, preload가 상속 |
| F12 | binDir 경로 프로덕션 asar에서 깨짐 | **높음** | Main Process가 binDir을 process.env.CMUX_BIN_DIR에 설정 |
| F13 | claude-wrapper error→passthrough 이중 자식 프로세스 경쟁 | **높음** | error 핸들러에서 exit 리스너 제거 후 passthrough |
| F14 | findRealClaude() 연산자 우선순위 버그 | **높음** | 조건 단순화: `dir !== myDir`만 체크 |
| F15 | claude-hook에서 addr 변수 미정의 | **높음** | case 시작부에 addr 구성 추가 |
| F17 | PID sweep이 EPERM을 사망으로 오판 | **높음** | err.code === 'ESRCH'일 때만 정리 |
| F20 | agent.spawn send_text가 PTY 미존재 시 유실 | **높음** | surface 메타에 pendingCommand 저장, XTermWrapper mount 시 실행 |
| F18 | tmux split-window에 활성 panelId 미지정 | **중간** | system.identify RPC로 현재 focused panelId 획득 |
| F19 | TMUX_PANE 정적 '%0' — surface마다 고유해야 함 | **중간** | workspace 내 surface 인덱스 계산하여 동적 할당 |
| F23 | PowerShell 셸 통합 스크립트 로딩 메커니즘 없음 | **중간** | PTY spawn 시 `-NoExit -Command ". 'path'"` 인자 추가 |
| F24 | OSC 133 파싱에 xterm.js 커스텀 핸들러 등록 필요 | **중간** | terminal.parser.registerOscHandler(133/7) 명시 |
| F25 | surface.update_meta의 store applyAction 미구현 | **낮음** | applyAction case 추가 명시 |

---

# Phase 4 — AI 에이전트 오케스트레이션

## 4.0 아키텍처

```
사용자 터미널 (PTY spawn 시 env 주입)
  │ CMUX_SURFACE_ID, CMUX_WORKSPACE_ID, CMUX_SOCKET_PORT, PATH
  │
  ├─ "claude" 입력 → PATH에서 claude.cmd 먼저 발견
  │    ↓
  │  claude.cmd → node claude-wrapper.js (async IIFE)     ← F1 수정
  │    → CMUX_SURFACE_ID 확인 → await socketAlive() → Hook JSON 생성
  │    → 실제 claude.exe --session-id <UUID> --settings <JSON>
  │
  ├─ Claude Code Hook 발생 → cmux-win claude-hook <subcommand>
  │    → stdin JSON에서 session_id 읽기                    ← F2 수정
  │    → 세션 파일에서 workspace/surface 조회
  │    → Socket RPC → Store 업데이트 → IPC → Sidebar 반영
  │
  ├─ 자체 오케스트레이션 (경로 B)                           ← F10 수정
  │    → UI [+ Agent] 버튼 또는 커맨드 팔레트
  │    → agent.spawn RPC → 새 패널 + 에이전트 CLI 실행
  │
  └─ Main Process PID sweep (10초)
       → agents[] 순회 → process.kill(pid, 0) → 죽으면 자동 정리
```

## 4.1 Task 16: 환경변수 주입

### 변경 파일
- `src/preload/index.ts` — spawn 시 CMUX_* env 자체 구성 + PATH prepend
- `src/renderer/components/terminal/XTermWrapper.tsx` — workspaceId prop 추가 (최소)
- `src/renderer/components/panels/PanelContainer.tsx` — workspaceId prop 전달
- `src/renderer/App.tsx` — workspaceId 전달

### 설계 (F3+F11+F12 수정: Main Process가 환경변수 설정, preload가 상속)

**Main Process (index.ts)에서 사전 설정:**
```typescript
// app.whenReady() 내부, socket 서버 시작 후:
const actualPort = await socketServer.start(DEFAULT_SOCKET_PORT);
process.env.CMUX_SOCKET_PORT = String(actualPort);  // F11: 실제 바인딩 포트

// binDir 결정 (F12: dev/prod 분기)
const binDir = app.isPackaged
  ? path.join(process.resourcesPath, 'bin')
  : path.join(__dirname, '../../resources/bin');
process.env.CMUX_BIN_DIR = binDir;
```

**preload/index.ts spawn 내부:**
```typescript
spawn(surfaceId: string, options?: { ..., workspaceId?: string }) {
  const mergedEnv = { ...process.env, ...(options?.env || {}) };

  // preload가 자체적으로 CMUX_* 구성 (Renderer는 surfaceId/workspaceId만 전달)
  mergedEnv.CMUX_SURFACE_ID = surfaceId;
  if (options?.workspaceId) mergedEnv.CMUX_WORKSPACE_ID = options.workspaceId;
  // F11: CMUX_SOCKET_PORT는 Main이 process.env에 설정한 실제 포트를 상속
  // F12: CMUX_BIN_DIR도 Main이 설정한 올바른 경로를 상속

  // resources/bin을 PATH 앞에 추가 (claude.cmd, tmux.cmd 발견용)
  const binDir = mergedEnv.CMUX_BIN_DIR || path.join(__dirname, '../../resources/bin');
  mergedEnv.PATH = binDir + path.delimiter + (mergedEnv.PATH || '');

  const result = bridge.spawn({ ...options, env: mergedEnv });
  surfacePtyMap.set(surfaceId, result.id);
  // ...
}
```

### XTermWrapper 변경 (최소)

```typescript
// prop 추가: workspaceId만
interface XTermWrapperProps {
  surfaceId: string;
  workspaceId: string;  // 추가 (env 주입용)
  // ... 기존 props (fontSize, fontFamily, etc.)
}

// spawn 호출:
window.ptyBridge.spawn(surfaceId, { shell, cwd, cols, rows, workspaceId });
```

### 에러 처리
- binDir 존재하지 않을 때: PATH에 추가하지 않고 경고 로그
- workspaceId 누락 시: env에 포함하지 않고 진행 (hook이 fallback)

### 테스트
- spawn 시 CMUX_SURFACE_ID 포함 확인
- spawn 시 PATH에 binDir prepend 확인
- workspaceId 없어도 spawn 성공 확인

---

## 4.2 Task 17: claude.cmd + claude-wrapper.js

### 생성 파일
- `resources/bin/claude.cmd`
- `resources/bin/claude-wrapper.js`
- `tests/unit/cli/claude-wrapper.test.ts`

### claude.cmd (2줄 trampoline)

```cmd
@echo off
node "%~dp0claude-wrapper.js" %*
```

### claude-wrapper.js (F1 수정: async IIFE)

```javascript
#!/usr/bin/env node
'use strict';

const { spawn: spawnChild } = require('child_process');
const crypto = require('crypto');
const net = require('net');
const path = require('path');

const args = process.argv.slice(2);

// ---- async IIFE로 전체를 감쌈 (F1 수정) ----
(async () => {
  // 1. cmux 외부면 통과
  if (!process.env.CMUX_SURFACE_ID) return passthrough();

  // 2. Hook 비활성화면 통과
  if (process.env.CMUX_CLAUDE_HOOKS_DISABLED === '1') return passthrough();

  // 3. bypass 서브명령 (mcp, config, api-key, rc, remote-control)
  const BYPASS = ['mcp', 'config', 'api-key', 'rc', 'remote-control'];
  if (args.length > 0 && BYPASS.includes(args[0])) return passthrough();

  // 4. Socket ping (F1: await 가능)
  const port = parseInt(process.env.CMUX_SOCKET_PORT || '19840', 10);
  const alive = await socketAlive(port);
  if (!alive) return passthrough();

  // 5. UUID 생성
  const sessionId = crypto.randomUUID();

  // 6. CLI 경로
  const cliPath = process.env.CMUX_CLI_PATH
    || path.join(__dirname, '../../out/cli/cmux-win.js');

  // 7. Hook JSON 구성
  const makeCmd = (sub) => `node "${cliPath}" claude-hook ${sub}`;
  const hooks = {
    hooks: {
      SessionStart: [{ matcher: '', hooks: [
        { type: 'command', command: makeCmd('session-start'), timeout: 10 }] }],
      Stop: [{ matcher: '', hooks: [
        { type: 'command', command: makeCmd('stop'), timeout: 10 }] }],
      SessionEnd: [{ matcher: '', hooks: [
        { type: 'command', command: makeCmd('session-end'), timeout: 1 }] }],
      Notification: [{ matcher: '', hooks: [
        { type: 'command', command: makeCmd('notification'), timeout: 10 }] }],
      UserPromptSubmit: [{ matcher: '', hooks: [
        { type: 'command', command: makeCmd('prompt-submit'), timeout: 10 }] }],
      PreToolUse: [{ matcher: '', hooks: [
        { type: 'command', command: makeCmd('pre-tool-use'), timeout: 5, async: true }] }],
    },
  };

  // 8. 실제 claude.exe 찾기 (자기 자신 제외)
  const realClaude = findRealClaude();
  if (!realClaude) return passthrough(); // 못 찾으면 통과 (F9 에러 처리)

  // 9. 실행 (stdio inherit — 터미널 직접 연결)
  const env = { ...process.env, CMUX_CLAUDE_PID: String(process.pid) };
  delete env.CLAUDECODE; // 중첩 세션 방지

  const child = spawnChild(realClaude, [
    '--session-id', sessionId,
    '--settings', JSON.stringify(hooks),
    ...args,
  ], { stdio: 'inherit', env });

  // F13 수정: error 시 exit 리스너 제거 후 passthrough (이중 자식 방지)
  const onExit = (code) => process.exit(code ?? 0);
  child.on('exit', onExit);
  child.on('error', () => {
    child.removeListener('exit', onExit);
    passthrough();
  });

})().catch(() => passthrough());

// ---- 헬퍼 ----

function passthrough() {
  const real = findRealClaude() || 'claude';
  const child = spawnChild(real, args, { stdio: 'inherit' });
  child.on('exit', (code) => process.exit(code ?? 0));
  child.on('error', (err) => {
    process.stderr.write(`cmux-win: claude not found: ${err.message}\n`);
    process.exit(127);
  });
}

function socketAlive(port) {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    socket.setTimeout(750);
    socket.connect(port, '127.0.0.1', () => { socket.destroy(); resolve(true); });
    socket.on('error', () => { socket.destroy(); resolve(false); });
    socket.on('timeout', () => { socket.destroy(); resolve(false); });
  });
}

function findRealClaude() {
  try {
    const { execSync } = require('child_process');
    const result = execSync('where claude 2>nul', { encoding: 'utf8' }).trim().split(/\r?\n/);
    const myDir = __dirname.toLowerCase().replace(/\\/g, '/');
    for (const p of result) {
      const trimmed = p.trim();
      if (!trimmed) continue;
      const dir = path.dirname(trimmed).toLowerCase().replace(/\\/g, '/');
      // F14 수정: 자기 자신의 디렉토리만 건너뜀 (연산자 우선순위 버그 제거)
      if (dir !== myDir) return trimmed;
    }
  } catch { /* where failed */ }
  return null;
}
```

### 에러 처리 (F9)
- `findRealClaude()` 실패 → passthrough (claude가 PATH에 없으면 원래 에러 메시지)
- socket connect 실패 → passthrough (cmux-win 미실행 시 일반 claude 실행)
- child spawn 실패 → passthrough
- 전체 async IIFE catch → passthrough

### 테스트
- Hook JSON 구조 검증 (6개 이벤트, timeout, async 값)
- CMUX_SURFACE_ID 없으면 passthrough 확인
- CMUX_CLAUDE_HOOKS_DISABLED=1이면 passthrough 확인
- bypass 서브명령 passthrough 확인
- socket 미응답 시 passthrough 확인
- findRealClaude가 자기 자신 제외 확인

---

## 4.3 Task 18: CLI claude-hook 6개 subcommand + 세션 스토어

### 변경/생성 파일
- `src/cli/cmux-win.ts` — claude-hook 구현
- `src/cli/claude-hook-session-store.ts` — 세션 파일 관리
- `tests/unit/cli/claude-hook-session-store.test.ts`
- `tests/unit/cli/claude-hook-commands.test.ts`

### 세션 스토어

```typescript
// src/cli/claude-hook-session-store.ts

interface SessionRecord {
  sessionId: string;
  workspaceId: string;
  surfaceId: string;
  cwd?: string;
  pid?: number;
  lastSubtitle?: string;
  lastBody?: string;
  startedAt: number;
  updatedAt: number;
}

interface SessionStoreData {
  sessions: Record<string, SessionRecord>;
}

const SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7일

export class ClaudeHookSessionStore {
  private filePath: string;

  constructor(filePath?: string) {
    this.filePath = filePath ?? path.join(
      process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming'),
      'cmux-win', 'claude-hook-sessions.json'
    );
  }

  /** 파일 읽기 + 7일 만료 자동 정리 */
  load(): SessionStoreData;

  /** atomic write: .tmp 파일에 쓴 후 rename (F9: 손상 방지) */
  save(data: SessionStoreData): void;

  upsert(record: SessionRecord): void;
  lookup(sessionId: string): SessionRecord | null;

  /** 읽고 삭제 — stop/session-end에서 사용 */
  consume(sessionId: string): SessionRecord | null;

  /** sessionId 없을 때 surfaceId+workspaceId로 fallback 조회 */
  findByContext(surfaceId: string, workspaceId: string): SessionRecord | null;
}
```

### 6개 subcommand (F2 수정: stdin JSON에서 session_id 읽기)

```typescript
case 'claude-hook': {
  const subCmd = commandArgs[0];
  const sessionStore = new ClaudeHookSessionStore();

  // F15 수정: addr 정의
  const addr = `tcp://127.0.0.1:${process.env.CMUX_SOCKET_PORT || '19840'}`;

  // F2 수정: session_id는 stdin JSON에서 읽음 (환경변수 아님)
  const input = readStdinJson(); // { session_id, cwd, tool_name, tool_input, ... }
  const sessionId = input?.session_id;
  const surfaceId = process.env.CMUX_SURFACE_ID;
  const workspaceId = process.env.CMUX_WORKSPACE_ID;
  const claudePid = process.env.CMUX_CLAUDE_PID;

  switch (subCmd) {
    case 'session-start':
    case 'active': {
      const sid = sessionId || crypto.randomUUID();
      sessionStore.upsert({
        sessionId: sid, workspaceId, surfaceId,
        cwd: input?.cwd || process.cwd(),
        pid: claudePid ? parseInt(claudePid) : undefined,
        startedAt: Date.now(), updatedAt: Date.now(),
      });
      await rpcCall(addr, 'agent.session_start', {
        sessionId: sid, agentType: 'claude',
        workspaceId, surfaceId,
        pid: claudePid ? parseInt(claudePid) : undefined,
      });
      break;
    }

    case 'prompt-submit': {
      const record = resolveSession(sessionStore, sessionId, surfaceId, workspaceId);
      if (!record) break;
      await rpcCall(addr, 'notification.clear', { workspaceId: record.workspaceId });
      await rpcCall(addr, 'agent.status_update', {
        sessionId: record.sessionId,
        status: 'running', icon: '⚡', color: '#4C8DFF',
      });
      break;
    }

    case 'pre-tool-use': {
      const record = resolveSession(sessionStore, sessionId, surfaceId, workspaceId);
      if (!record) break;
      if (input?.tool_name === 'AskUserQuestion' && input?.tool_input?.question) {
        record.lastBody = input.tool_input.question;
        record.updatedAt = Date.now();
        sessionStore.upsert(record);
      }
      await rpcCall(addr, 'agent.status_update', {
        sessionId: record.sessionId, status: 'running',
      });
      break;
    }

    case 'notification':
    case 'notify': {
      const record = resolveSession(sessionStore, sessionId, surfaceId, workspaceId);
      if (!record) break;
      const body = record.lastBody || input?.body || '';
      record.lastBody = undefined;
      record.updatedAt = Date.now();
      sessionStore.upsert(record);
      await rpcCall(addr, 'agent.status_update', {
        sessionId: record.sessionId,
        status: 'needs_input', icon: '🔔', color: '#4C8DFF',
      });
      await rpcCall(addr, 'notification.create', {
        title: input?.title || 'Claude needs input',
        subtitle: input?.subtitle, body,
        workspaceId: record.workspaceId, surfaceId: record.surfaceId,
      });
      break;
    }

    case 'stop':
    case 'idle': {
      const record = consumeSession(sessionStore, sessionId, surfaceId, workspaceId);
      if (!record) break;
      await rpcCall(addr, 'agent.status_update', {
        sessionId: record.sessionId,
        status: 'idle', icon: '⏸', color: '#8E8E93',
      });
      await rpcCall(addr, 'notification.create', {
        title: 'Claude finished',
        body: input?.transcript_summary || `Completed in ${record.cwd || 'unknown'}`,
        workspaceId: record.workspaceId, surfaceId: record.surfaceId,
      });
      break;
    }

    case 'session-end': {
      const record = consumeSession(sessionStore, sessionId, surfaceId, workspaceId);
      if (!record) break;
      await rpcCall(addr, 'agent.session_end', { sessionId: record.sessionId });
      await rpcCall(addr, 'notification.clear', { workspaceId: record.workspaceId });
      break;
    }
  }
  break;
}

// 헬퍼: 세션 조회 (sessionId 우선, fallback으로 context)
function resolveSession(store, sessionId, surfaceId, workspaceId) {
  if (sessionId) return store.lookup(sessionId);
  return store.findByContext(surfaceId, workspaceId);
}

// 헬퍼: 세션 consume (조회 + 삭제)
function consumeSession(store, sessionId, surfaceId, workspaceId) {
  if (sessionId) return store.consume(sessionId);
  const found = store.findByContext(surfaceId, workspaceId);
  if (found) return store.consume(found.sessionId);
  return null;
}
```

### 에러 처리 (F9)
- 세션 파일 손상: load() 실패 시 빈 객체 반환, 기존 파일을 .bak으로 이동
- RPC 호출 실패: catch 후 stderr에 경고, 프로세스는 정상 종료 (exit 0)
- stdin JSON 파싱 실패: null 반환, 환경변수 fallback

### 테스트 (세션 스토어)
- upsert/lookup/consume CRUD
- 7일 만료 자동 정리
- findByContext fallback
- atomic write (중간 중단 시 원본 보존)
- 손상 파일 복구 (빈 객체 반환)

### 테스트 (claude-hook commands)
- session-start → agent.session_start RPC 호출 확인
- prompt-submit → status 'running' 설정 확인
- stop → status 'idle' + notification 생성 확인
- notification → status 'needs_input' + notification 생성 확인
- pre-tool-use → AskUserQuestion lastBody 저장 확인
- session-end → agent.session_end + 세션 삭제 확인
- stdin JSON 파싱 실패 시 정상 종료 확인

---

## 4.4 Task 19: PID sweep 타이머

### 변경 파일
- `src/main/index.ts`

### 구현

```typescript
// main/index.ts의 app.whenReady() 내부:

// 앱 시작 시 agents 초기화 (ephemeral 런타임 상태)
if (initialState) {
  initialState = { ...initialState, agents: [] };
}

// PID sweep: 10초마다 죽은 에이전트 프로세스 자동 정리
setInterval(() => {
  const agents = store.getState().agents;
  for (const agent of agents) {
    if (!agent.pid) continue;
    try {
      process.kill(agent.pid, 0); // signal 0 = 존재만 확인
    } catch (err: unknown) {
      // F17 수정: ESRCH(프로세스 없음)일 때만 정리
      // EPERM은 프로세스 존재하지만 권한 부족 → 유지
      const code = (err as NodeJS.ErrnoException).code;
      if (code === 'ESRCH') {
        store.dispatch({
          type: 'agent.session_end',
          payload: { sessionId: agent.sessionId },
        });
      }
    }
  }
}, 10_000);
```

### 테스트
- PID 존재 시 유지 확인
- PID 없을 시 agent.session_end dispatch 확인

---

## 4.5 Task 20: Sidebar 에이전트 상태 UI 강화

### 변경 파일
- `src/renderer/components/sidebar/WorkspaceItem.tsx`

### 강화

```
현재:  │ WS 1    ⚡    │  ← statusIcon만
강화:  │▎WS 1          │
       │  ⚡ Running    │  ← 아이콘 + 텍스트 + 색상
       │  claude        │  ← 에이전트 타입
```

```tsx
{wsAgents.map((agent) => (
  <div key={agent.sessionId} style={{ fontSize: '11px', padding: '0 12px 2px' }}>
    <span style={{ color: agent.statusColor || '#888' }}>
      {agent.statusIcon} {agent.status === 'running' ? 'Running'
        : agent.status === 'idle' ? 'Idle'
        : agent.status === 'needs_input' ? 'Needs input' : agent.status}
    </span>
    <span style={{ color: '#666', fontSize: '10px', marginLeft: '4px' }}>
      {agent.agentType}
    </span>
  </div>
))}
```

---

## 4.6 Task 21: tmux.cmd shim

### 생성 파일
- `resources/bin/tmux.cmd` — trampoline
- `resources/bin/tmux-shim.js` — 매핑 로직
- `tests/unit/cli/tmux-shim.test.ts`

### tmux.cmd

```cmd
@echo off
node "%~dp0tmux-shim.js" %*
```

### 명령 매핑 (17개)

| tmux 명령 | Socket RPC | 인자 변환 |
|----------|-----------|---------|
| `new-session -s <name>` | `workspace.create {name}` | -s → name |
| `new-window -n <name>` | `workspace.create {name}` | -n → name |
| `split-window -h` | `panel.split {direction:'horizontal'}` | -h/-v |
| `split-window -v` | `panel.split {direction:'vertical'}` | |
| `select-window -t <id>` | `workspace.select` | F5: index→UUID |
| `select-pane -t <id>` | `panel.focus` | F5: index→UUID |
| `send-keys <text> [Enter]` | `surface.send_text` | Enter→\n |
| `capture-pane -p` | (stub: 빈 문자열) | Phase 5 완성 |
| `list-windows` | `workspace.list` | tmux 형식 출력 |
| `list-panes` | `panel.list` | tmux 형식 출력 |
| `kill-window -t <id>` | `workspace.close` | |
| `kill-pane -t <id>` | `panel.close` | |
| `resize-pane -D/-U/-L/-R <n>` | `panel.resize` | 방향→ratio |
| `display-message -p <fmt>` | (로컬 치환) | #{window_id} 등 |
| `last-pane` | `panel.focus` (이전) | focus history |
| `swap-pane` | (stub) | Phase 5 |
| `break-pane` | (stub) | Phase 5 |

### F5 수정: -t 플래그 ID 변환

```javascript
// tmux target 형식: session:window.pane 또는 %N (pane index)
// 변환 로직:
async function resolveTarget(target, addr) {
  // %N 형식 (pane index)
  if (target.startsWith('%')) {
    const index = parseInt(target.slice(1));
    const panels = await rpcCall(addr, 'panel.list', {});
    return panels.result?.[index]?.id || null;
  }
  // 숫자 (window index)
  if (/^\d+$/.test(target)) {
    const workspaces = await rpcCall(addr, 'workspace.list', {});
    return workspaces.result?.[parseInt(target)]?.id || null;
  }
  // UUID 그대로
  return target;
}
```

### F18 수정: split-window 시 활성 panelId 획득

```javascript
// split-window에 -t 없으면 현재 포커스 패널 사용:
async function getActivePanelId(addr) {
  // system.identify로 현재 caller 컨텍스트 획득
  // 또는 환경변수 CMUX_SURFACE_ID로부터 역추적
  const surfaceId = process.env.CMUX_SURFACE_ID;
  if (surfaceId) {
    const surfaces = await rpcCall(addr, 'surface.list', {});
    const surface = surfaces.result?.find(s => s.id === surfaceId);
    if (surface) return surface.panelId;
  }
  // fallback: 첫 번째 패널
  const panels = await rpcCall(addr, 'panel.list', {});
  return panels.result?.[0]?.id || null;
}
```

### TMUX 환경변수 (F19 수정: TMUX_PANE 동적 할당)

```typescript
// PTY spawn 시 추가 (Task 16 preload에서):
TMUX: `cmux-win://127.0.0.1:${socketPort},${process.pid},0`
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: '1'

// F19: TMUX_PANE은 workspace 내 surface 인덱스로 동적 설정
// preload spawn에서 계산:
//   panels = 현재 workspace의 panels (순서대로)
//   index = panels.flatMap(p => p.surfaceIds).indexOf(surfaceId)
//   TMUX_PANE = `%${index}`
// Main Process가 IPC로 인덱스를 제공하거나,
// 단순 방법: surface UUID 해시의 하위 4자리를 인덱스로 사용
// 실용적 방법: workspace 내 surface 생성 순서 카운터 (store에서 관리)
```

### send-keys 키 변환

```javascript
function convertTmuxKeys(args) {
  return args.map(arg => {
    if (arg === 'Enter') return '\n';
    if (arg === 'Space') return ' ';
    if (arg === 'Tab') return '\t';
    if (/^C-(.)$/.test(arg)) return String.fromCharCode(arg.charCodeAt(2) - 96);
    return arg;
  }).join('');
}
```

### 에러 처리 (F9)
- 알 수 없는 tmux 명령 → stderr: "Unknown tmux command: X", exit 1
- target 해석 실패 → stderr: "Target not found: X", exit 1
- socket 미연결 → stderr: "cmux-win not running", exit 1

### 테스트
- 12개 핵심 명령 매핑 (각각 RPC 호출 검증)
- send-keys 키 변환 (Enter, C-c 등)
- -t 인덱스→UUID 변환
- 잘못된 명령 에러 메시지

---

## 4.7 Task 22: 자체 오케스트레이션 — agent.spawn (F10 수정)

### 생성/변경 파일
- `src/shared/actions.ts` — AgentSpawnAction 추가
- `src/main/sot/store.ts` — agent.spawn applyAction
- `src/main/socket/handlers/agent.ts` — agent.spawn RPC
- `src/renderer/components/sidebar/Sidebar.tsx` — [+ Agent] 버튼
- `tests/unit/sot/agent-spawn.test.ts`

### agent.spawn Action

```typescript
// actions.ts
export const AgentSpawnAction = z.object({
  type: z.literal('agent.spawn'),
  payload: z.object({
    agentType: z.enum(['claude', 'codex', 'gemini', 'opencode']),
    workspaceId: z.string(),
    task: z.string().optional(), // 초기 명령 (에이전트에 전달할 텍스트)
  }),
});
```

### store applyAction

```typescript
case 'agent.spawn': {
  const { agentType, workspaceId, task } = action.payload;
  const ws = draft.workspaces.find(w => w.id === workspaceId);
  if (!ws) break;

  // 새 패널 + 서피스 생성 (panel.split과 유사)
  const newPanelId = crypto.randomUUID();
  const newSurfaceId = crypto.randomUUID();

  draft.panels.push({
    id: newPanelId, workspaceId,
    panelType: 'terminal', surfaceIds: [newSurfaceId],
    activeSurfaceId: newSurfaceId, isZoomed: false,
  });
  draft.surfaces.push({
    id: newSurfaceId, panelId: newPanelId,
    surfaceType: 'terminal', title: `${agentType} agent`,
  });

  // 레이아웃에 추가 (현재 레이아웃 오른쪽에 split)
  ws.panelLayout = {
    type: 'split', direction: 'horizontal', ratio: 0.5,
    children: [ws.panelLayout, { type: 'leaf', panelId: newPanelId }],
  };

  // 에이전트 세션 등록 (Hook이 나중에 상세 업데이트)
  draft.agents.push({
    sessionId: crypto.randomUUID(),
    agentType, workspaceId, surfaceId: newSurfaceId,
    status: 'running', statusIcon: '⚡', statusColor: '#4C8DFF',
    lastActivity: Date.now(),
  });

  break;
}
```

### Side effect: 에이전트 CLI 실행 (F20 수정: PTY spawn 대기)

```typescript
// store applyAction에서 surface에 pendingCommand 저장 (F20):
draft.surfaces.push({
  id: newSurfaceId, panelId: newPanelId,
  surfaceType: 'terminal', title: `${agentType} agent`,
  pendingCommand: task ? `${agentType} "${task}"\n` : `${agentType}\n`,  // F20
});

// XTermWrapper가 mount 시 pendingCommand 확인 후 실행:
// initPty() 완료 후:
if (pendingCommand) {
  window.ptyBridge.write(surfaceId, pendingCommand);
  // pendingCommand 소비: dispatch(surface.update_meta, { surfaceId, pendingCommand: null })
}

// 이 방식으로 PTY가 확실히 존재한 후에 명령이 전송됨
// SideEffectsMiddleware에서 즉시 send_text를 하지 않음 (경쟁 상태 제거)
```

**SurfaceState 확장** (pendingCommand 필드):
```typescript
interface SurfaceState {
  // ... 기존 필드
  pendingCommand?: string;  // F20: agent.spawn 시 PTY 준비 후 실행할 명령
}
```

### UI: Sidebar [+ Agent] 버튼

```tsx
// Sidebar.tsx 하단:
<div style={{ padding: '8px 12px', borderTop: '1px solid #3c3c3c' }}>
  <select
    onChange={(e) => {
      if (e.target.value) {
        void dispatch({
          type: 'agent.spawn',
          payload: { agentType: e.target.value, workspaceId: activeWorkspaceId },
        });
        e.target.value = '';
      }
    }}
    style={{ width: '100%', background: '#2d2d2d', color: '#ccc', border: '1px solid #555' }}
  >
    <option value="">+ Add Agent</option>
    <option value="claude">Claude</option>
    <option value="codex">Codex</option>
    <option value="gemini">Gemini</option>
    <option value="opencode">OpenCode</option>
  </select>
</div>
```

### 테스트
- agent.spawn → 패널/서피스 생성 확인
- agent.spawn → agents[] 등록 확인
- agent.spawn → panelLayout에 split 추가 확인
- 존재하지 않는 workspaceId → 무시 확인

---

# Phase 3 — 브라우저 + 마크다운

## 3.0 추가 의존성 (F6 수정)

```bash
npm install better-sqlite3
npm install -D @types/better-sqlite3
```

`electron-vite.config.ts`에 external 추가:
```typescript
main: { external: ['electron', 'node-pty', 'better-sqlite3'] }
```

## 3.1 Task 23: BrowserSurface 컴포넌트

### 생성 파일
- `src/renderer/components/browser/BrowserSurface.tsx`
- `src/renderer/components/browser/NavigationBar.tsx`
- `src/preload/browser-preload.ts`

### surface.update_meta Action (F4 수정) + applyAction (F25 수정)

```typescript
// actions.ts에 추가:
export const SurfaceUpdateMetaAction = z.object({
  type: z.literal('surface.update_meta'),
  payload: z.object({
    surfaceId: z.string(),
    title: z.string().optional(),
    pendingCommand: z.string().nullable().optional(),  // F20: agent.spawn 소비
    browser: z.object({
      url: z.string().optional(),
      isLoading: z.boolean().optional(),
    }).optional(),
    terminal: z.object({
      cwd: z.string().optional(),
      gitBranch: z.string().optional(),
      gitDirty: z.boolean().optional(),
      exitCode: z.number().optional(),
    }).optional(),
  }),
});
```

```typescript
// F25: store.ts applyAction에 추가:
case 'surface.update_meta': {
  const surface = draft.surfaces.find(s => s.id === action.payload.surfaceId);
  if (!surface) break;
  if (action.payload.title !== undefined) surface.title = action.payload.title;
  if (action.payload.pendingCommand !== undefined) {
    (surface as any).pendingCommand = action.payload.pendingCommand; // F20
  }
  if (action.payload.browser) {
    surface.browser = { ...surface.browser, ...action.payload.browser } as any;
  }
  if (action.payload.terminal) {
    surface.terminal = { ...surface.terminal, ...action.payload.terminal } as any;
  }
  break;
}
```

### BrowserSurface.tsx

```typescript
interface BrowserSurfaceProps {
  surfaceId: string;
  url: string;
  profileId: string;
  dispatch: (action: unknown) => Promise<{ ok: boolean }>;
}

// <webview> 이벤트 → dispatch(surface.update_meta):
// did-navigate → url 업데이트
// page-title-updated → title 업데이트
// did-start-loading / did-stop-loading → isLoading 업데이트
// crashed → URL 재로드 (F9: 연속 3회 크래시 시 에러 표시)
```

### NavigationBar.tsx

```
┌──────────────────────────────────────────────────┐
│ ← → ⟳  │ https://example.com                │ ☰ │
└──────────────────────────────────────────────────┘
```

### 에러 처리 (F9)
- webview crashed → 자동 URL 재로드 (최대 3회)
- 연속 3회 크래시 → "페이지를 로드할 수 없습니다" 메시지 표시
- 네트워크 오류 → did-fail-load 이벤트에서 에러 페이지 표시

### 테스트
- webview 마운트/언마운트
- URL 네비게이션 이벤트
- 크래시 복구 (3회 제한)

---

## 3.2 Task 24: Omnibar

### 생성 파일
- `src/renderer/components/browser/Omnibar.tsx`

### 기능

```
입력 → URL 인지? → Yes → 네비게이션
                → No → 검색엔진 쿼리

URL 감지: http://, https://, localhost, localhost:port, x.x.x.x, domain.tld
검색엔진: settings.browser.searchEngine에서 선택

자동완성:
  1. 히스토리 (IPC: browser:history:query)
  2. 검색 제안 (fetch, settings.browser.searchSuggestions)
```

### 테스트
- URL 감지 정확도
- 검색 쿼리 변환

---

## 3.3 Task 25: 히스토리 DB

### 생성/수정 파일
- `src/main/browser/history-db.ts`
- `src/main/index.ts` — IPC 핸들러 등록
- `tests/unit/browser/history-db.test.ts`

### 스키마

```sql
CREATE TABLE history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_id TEXT NOT NULL,
  url TEXT NOT NULL,
  title TEXT,
  visit_time INTEGER NOT NULL,
  favicon_url TEXT
);
CREATE INDEX idx_history_url ON history(url);
CREATE INDEX idx_history_profile ON history(profile_id);
CREATE INDEX idx_history_visit ON history(visit_time DESC);
```

### IPC 핸들러

```typescript
ipcMain.handle('browser:history:query', (_, { prefix, profileId, limit }) => { ... });
ipcMain.handle('browser:history:add', (_, { url, title, profileId }) => { ... });
ipcMain.handle('browser:history:clear', (_, { profileId }) => { ... });
```

### 테스트
- CRUD, 프로필 격리, prefix 검색, 방문 횟수 정렬

---

## 3.4 Task 26: 브라우저 자동화 API (P0)

### 생성 파일
- `src/main/socket/handlers/browser.ts`
- `tests/unit/socket/browser-automation.test.ts`

### P0 RPC 메서드 (8개)

| 메서드 | 기능 |
|-------|------|
| `browser.snapshot` | DOM 접근성 트리 스냅샷 |
| `browser.eval` | JS 실행 |
| `browser.wait` | 요소/조건 대기 |
| `browser.click` | 요소 클릭 |
| `browser.type` | 텍스트 입력 |
| `browser.fill` | 폼 필드 채우기 |
| `browser.press` | 키 입력 |
| `browser.screenshot` | 스크린샷 (base64 PNG) |

### Ref 시스템

```
스냅샷 시 @e1, @e2, ... ref 할당
ref → {selector, coordinates, tagName, text} 매핑 (세션 로컬)
이후 click(@e1), fill(@e3, "text") 등으로 참조
```

---

## 3.5 Task 27: 마크다운 뷰어 + Find-in-page

### 생성 파일
- `src/renderer/components/markdown/MarkdownViewer.tsx`
- `src/renderer/components/search/SearchOverlay.tsx`

### 마크다운: chokidar + remark + rehype + shiki
### Find: 터미널(@xterm/addon-search), 브라우저(webview.findInPage)
### 공통 UI: Ctrl+F → SearchOverlay

---

# Phase 5 — 셸 통합 + 원격

## 5.1 Task 28: 셸 프롬프트 통합

### 생성 파일
- `resources/shell-integration/powershell.ps1`
- `resources/shell-integration/bash.sh`
- `src/main/terminal/shell-integration.ts`

### PowerShell: OSC 133 프롬프트 마커 + CWD + Git 정보

**F23 수정: 로딩 메커니즘**
```typescript
// PTY spawn 시 PowerShell이면 통합 스크립트를 자동 로드:
// shell-integration.ts에서:
if (shell === 'powershell') {
  const integrationPath = path.join(binDir, '../shell-integration/powershell.ps1');
  // -NoExit -Command ". 'path'" 으로 dot-source
  shellArgs = ['-NoExit', '-Command', `. '${integrationPath}'`];
}

// Bash (WSL/Git Bash)의 경우:
if (shell === 'bash' || shell === 'wsl' || shell === 'git-bash') {
  // CMUX_SHELL_INTEGRATION_DIR 환경변수 설정
  // bash.sh가 PROMPT_COMMAND에 자동 injection
  env.CMUX_SHELL_INTEGRATION = '1';
  env.CMUX_SHELL_INTEGRATION_DIR = path.join(binDir, '../shell-integration');
  // .bashrc에서 확인: if [ -n "$CMUX_SHELL_INTEGRATION" ]; then source ...; fi
  // 또는 --rcfile 인자로 직접 지정
}
```

### Bash (WSL/Git Bash): cmux integration 이식

---

## 5.2 Task 29: OSC 133 프롬프트 감지

### 변경 파일
- `src/renderer/components/terminal/XTermWrapper.tsx`
- `src/shared/types.ts` — SurfaceState.terminal 확장

### 파싱 (F24 수정: xterm.js 커스텀 핸들러 등록)

```typescript
// XTermWrapper initPty() 완료 후:

// F24: xterm.js는 알 수 없는 OSC를 무시하므로 커스텀 핸들러 등록 필수
terminal.parser.registerOscHandler(133, (data) => {
  // data: "A" (프롬프트 시작), "B" (명령 시작),
  //       "D;0" (실행 완료, exitCode=0),
  //       "P;k=git_branch;v=main*" (메타데이터)
  if (data === 'A') { /* 프롬프트 시작 감지 */ }
  if (data.startsWith('P;')) {
    const params = Object.fromEntries(data.slice(2).split(';').map(kv => kv.split('=')));
    // params.k, params.v → dispatch(surface.update_meta)
  }
  if (data.startsWith('D;')) {
    const exitCode = parseInt(data.slice(2));
    // dispatch(surface.update_meta, { terminal: { exitCode } })
  }
  return true; // handled
});

terminal.parser.registerOscHandler(7, (data) => {
  // data: "file://localhost/c/Users/..." → CWD
  const cwd = decodeURIComponent(new URL(data).pathname);
  // dispatch(surface.update_meta, { terminal: { cwd } })
  return true;
});
```

### SurfaceState.terminal 확장

```typescript
terminal?: {
  pid: number;
  cwd: string;
  shell: string;
  gitBranch?: string;
  gitDirty?: boolean;
  exitCode?: number;
};
```

---

## 5.3 Task 30: SSH 기본 (F8 수정)

### 생성 파일
- `src/main/remote/ssh-session.ts`
- `src/cli/ssh-command.ts`

### 구현

```typescript
// cmux-win ssh user@host
// 1. ssh.exe 존재 확인 (where ssh)
// 2. 있으면: node-pty + ssh.exe (네이티브)
// 3. 없으면: ssh2 npm 패키지 (순수 JS, F8 폴백)
//    → npm install ssh2 (Phase 5 의존성 추가)
// 4. 새 workspace 생성 → 원격 터미널 표시
// 5. 재접속: exponential backoff, 최대 5회

// remoteSession 상태:
// { host, port, status: 'connecting'|'connected'|'disconnected'|'error' }
```

### 에러 처리 (F9)
- ssh.exe 미존재 + ssh2 설치 실패 → "SSH client not available" 에러
- 인증 실패 → 사용자에게 비밀번호/키 재입력 요청
- 연결 끊김 → 자동 재시도 (backoff)

---

## 5.4 Task 31: 세션 스크롤백 저장/복원

### 변경 파일
- `src/main/sot/middleware/persistence.ts`
- `src/preload/index.ts`

### 구현
- 앱 종료 시: xterm buffer → ANSI 덤프 (최대 10000줄, 1MB/surface)
- 앱 시작 시: terminal.write(ansiString) 복원
- ANSI-safe (escape 시퀀스 보존)

---

# Phase 6 — 완성도

## 6.1 Task 32: Windows Toast 알림 + 트레이

- Electron Notification API → Windows Action Center
- 클릭 시 workspace 포커스 이동
- Tray 아이콘 + 미읽음 카운트

## 6.2 Task 33: 커맨드 팔레트 (Ctrl+Shift+P)

- 퍼지 검색 (연속/비연속 매칭, 스코어링)
- 단축키 힌트
- 명령 소스: shortcuts, workspaces, agent spawn, settings

## 6.3 Task 34: 설정 UI 패널

- 7 섹션: 외형, 터미널, 브라우저, 에이전트, 단축키, 업데이트, 접근성

## 6.4 Task 35: 자동 업데이트 (F7 수정: 코드 서명 포함)

### 생성 파일
- `src/main/updates/update-manager.ts`
- `electron-builder.yml`

### 코드 서명 (F7)

```yaml
# electron-builder.yml
win:
  target: nsis
  sign: true
  certificateSubjectName: "cmux-win"
  # CI에서: CSC_LINK, CSC_KEY_PASSWORD 환경변수로 인증서 제공
  # 없으면: 서명 건너뜀 (개발 빌드)
```

- 코드 서명 인증서 없이 배포 시 → SmartScreen 경고 표시
- CI/CD에서 인증서 환경변수 주입
- 개발 빌드는 서명 건너뜀

### electron-updater
- stable / nightly 채널
- GitHub Releases 배포

## 6.5 Task 36: 다국어 (i18next, ko/en/ja)

- ~200 번역 키
- 설정에서 언어 전환

## 6.6 Task 37: 텔레메트리 (Sentry + PostHog)

- 옵트아웃: settings.telemetry.enabled = false
- 에러 추적 + 사용 통계

## 6.7 Task 38: 테마 (90+ Ghostty 변환)

- Ghostty 형식 → xterm.js ITheme 변환
- ANSI 0-15 → black/red/.../brightWhite 매핑
- 빌드 스크립트: themes/*.theme → themes.json
- 설정 UI에서 실시간 프리뷰

## 6.8 Task 39: 접근성

- tabindex 순서, aria-label, aria-live
- xterm.js screenReaderMode
- 고대비 테마, reducedMotion
- axe-core CI 자동 스캔

---

# 전체 Task 목록 (24 tasks)

## Phase 4 — 에이전트 (Critical Path): 7 tasks

| Task | 내용 | 의존 |
|------|------|------|
| 16 | 환경변수 주입 (preload 자체 구성, PATH prepend) | - |
| 17 | claude.cmd + claude-wrapper.js (async IIFE) | 16 |
| 18 | CLI claude-hook 6 subcommand + 세션 스토어 (stdin JSON) | 17 |
| 19 | PID sweep 타이머 (10초, Main Process) | 18 |
| 20 | Sidebar 에이전트 상태 UI 강화 | - |
| 21 | tmux.cmd shim (17개 명령, -t ID 변환) | 16 |
| 22 | 자체 오케스트레이션 — agent.spawn + UI [+ Agent] | - |

## Phase 3 — 브라우저 + 마크다운: 5 tasks

| Task | 내용 | 의존 |
|------|------|------|
| 23 | BrowserSurface + NavigationBar + surface.update_meta Action | - |
| 24 | Omnibar (URL + 검색 + 자동완성) | 23 |
| 25 | 히스토리 DB (better-sqlite3, F6 config 포함) | 23 |
| 26 | 브라우저 자동화 API P0 (8 메서드 + ref 시스템) | 23 |
| 27 | 마크다운 뷰어 + Find-in-page | - |

## Phase 5 — 셸 통합 + 원격: 4 tasks

| Task | 내용 | 의존 |
|------|------|------|
| 28 | 셸 프롬프트 통합 (PS/CMD/WSL/Bash) | - |
| 29 | OSC 133 프롬프트 감지 + surface.update_meta | 28 |
| 30 | SSH 기본 (ssh.exe + ssh2 폴백, F8) | - |
| 31 | 세션 스크롤백 저장/복원 | - |

## Phase 6 — 완성도: 8 tasks

| Task | 내용 | 의존 |
|------|------|------|
| 32 | Windows Toast 알림 + 시스템 트레이 | - |
| 33 | 커맨드 팔레트 (Ctrl+Shift+P, 퍼지 검색) | - |
| 34 | 설정 UI 패널 (7 섹션) | - |
| 35 | 자동 업데이트 (electron-updater + 코드 서명 F7) | - |
| 36 | 다국어 (i18next, ko/en/ja, ~200키) | - |
| 37 | 텔레메트리 (Sentry + PostHog, 옵트아웃) | - |
| 38 | 테마 (90+ Ghostty 변환 + 빌드 스크립트) | - |
| 39 | 접근성 (axe-core + ARIA + 키보드 + screenReader) | - |

---

# 설계 결정 기록 (Locked)

| # | 결정 | 이유 |
|---|------|------|
| D1 | 통신 방향: Claude → cmux-win (역방향) | cmux와 동일 |
| D2 | 래퍼: claude.cmd → Node.js async wrapper | CMD batch JSON 불가 + async 필수 |
| D3 | 세션 스토어: 별도 JSON 파일 | CLI 별도 프로세스 직접 접근 |
| D4 | PID 확인: process.kill(pid, 0) | Windows Node.js 동작 확인 |
| D5 | 기존 agent.* Action 재활용 | 저수준 명령 불필요 |
| D6 | Socket: TCP localhost | Windows Unix socket 없음 |
| D7 | tmux shim: Node.js + index→UUID 변환 | 크로스플랫폼 |
| D8 | claude 래퍼만 (codex/gemini 없음) | cmux 동일 |
| D9 | PreToolUse: async=true, 5초 | Claude 응답성 |
| D10 | SessionEnd: 1초 timeout | 빠른 정리 |
| D11 | 브라우저: webview 태그 | React DOM 내부, 프로세스 격리 |
| D12 | 히스토리: better-sqlite3 | cmux 동일, 성능 |
| D13 | 테마: Ghostty → xterm.js 변환 | 90+ 테마 재사용 |
| D14 | 다국어: i18next | React 통합 성숙 |
| D15 | 업데이트: electron-updater + 코드 서명 | SmartScreen 대응 |
| D16 | session_id 소스: stdin JSON | Claude Code hook 프로토콜 |
| D17 | env 구성: preload 자체 (Renderer 최소 전달) | prop drilling 방지 |
| D18 | SSH 폴백: ssh2 npm 패키지 | ssh.exe 미존재 대응 |
| D19 | 자체 오케스트레이션: agent.spawn Action | Claude Teams 미지원 시 폴백 |
| D20 | Socket 포트: Main이 process.env에 실제 포트 설정 | 포트 충돌 시 자동 증가 대응 |
| D21 | binDir: Main이 process.env.CMUX_BIN_DIR 설정 | dev/prod(asar) 경로 분기 |
| D22 | PID sweep: ESRCH만 사망 판정, EPERM은 유지 | 권한 부족 프로세스 오판 방지 |
| D23 | agent.spawn: pendingCommand로 PTY 대기 | send_text 경쟁 상태 방지 |
| D24 | OSC 133: terminal.parser.registerOscHandler | xterm.js는 미등록 OSC 무시 |
| D25 | PowerShell 통합: -NoExit -Command dot-source | 프로필 수정 없이 로드 |

---

# 커버리지 목표

| Phase | 목표 |
|-------|------|
| Phase 4 (에이전트) | ≥90% |
| Phase 3 (브라우저) | ≥80% |
| Phase 5 (셸/원격) | ≥85% |
| Phase 6 (완성도) | ≥80% |
