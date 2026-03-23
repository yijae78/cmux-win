# Phase 4: AI 에이전트 오케스트레이션 — 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Claude Code Hook 시스템, tmux shim, 자체 오케스트레이션을 구현하여 AI 에이전트가 cmux-win 터미널에서 완전히 동작하도록 한다.

**Architecture:** claude.cmd 래퍼가 Claude Code에 Hook을 주입하고, Hook이 CLI를 통해 Socket RPC로 Store를 업데이트한다. 역방향 통신 (Claude→cmux-win). tmux.cmd shim은 Claude Teams 호환. agent.spawn은 UI 기반 에이전트 추가.

**Tech Stack:** Node.js (래퍼/shim), JSON-RPC 2.0 (Socket), Vitest (테스트), Electron IPC

**선행 조건:** Phase 1-2 완료 (182 tests, 15 commits)
**설계안 정본:** `2026-03-21-phases-3-to-6-design.md` v3

---

## 의존성 그래프

```
Task 16 (환경변수)
  ├─→ Task 17 (claude.cmd + wrapper)
  │     └─→ Task 18 (CLI claude-hook + 세션 스토어)
  │           └─→ Task 19 (PID sweep)
  ├─→ Task 21 (tmux.cmd shim)
  │
Task 20 (Sidebar UI) ← 독립
Task 22 (agent.spawn) ← 독립

실행 순서: 16 → 17 → 18 → 19 → 20,21,22 (병렬 가능)
```

---

## Task 16: 환경변수 주입

**Files:**
- Modify: `src/main/index.ts`
- Modify: `src/preload/index.ts`
- Modify: `src/renderer/components/terminal/XTermWrapper.tsx`
- Modify: `src/renderer/components/panels/PanelContainer.tsx`
- Modify: `src/renderer/components/panels/PanelLayout.tsx`
- Modify: `src/renderer/App.tsx`
- Test: `tests/unit/preload/env-injection.test.ts`

### Step 1: main/index.ts — 실제 포트와 binDir를 process.env에 설정

`app.whenReady()` 내부, socket 서버 시작 직후에 추가:

```typescript
// F11: 실제 바인딩 포트를 process.env에 설정 (preload가 상속)
const actualPort = await socketServer.start(DEFAULT_SOCKET_PORT);
process.env.CMUX_SOCKET_PORT = String(actualPort);

// F12: binDir를 process.env에 설정 (dev/prod 분기)
process.env.CMUX_BIN_DIR = app.isPackaged
  ? path.join(process.resourcesPath, 'bin')
  : path.join(__dirname, '../../resources/bin');
```

기존 `const port = await socketServer.start(...)` 줄을 교체.

### Step 2: preload/index.ts — spawn에서 CMUX_* env 주입 + PATH prepend

현재 spawn 시그니처: `spawn(surfaceId, options?)`.
options에 `workspaceId`를 추가하고, env를 자동 구성:

```typescript
spawn(surfaceId: string, options?: {
  shell?: string; cwd?: string; cols?: number; rows?: number;
  env?: Record<string, string>;
  workspaceId?: string;  // 추가
}) {
  const mergedEnv: Record<string, string> = { ...process.env as Record<string, string>, ...(options?.env || {}) };

  // CMUX_* 환경변수 자동 구성
  mergedEnv.CMUX_SURFACE_ID = surfaceId;
  if (options?.workspaceId) mergedEnv.CMUX_WORKSPACE_ID = options.workspaceId;
  // CMUX_SOCKET_PORT, CMUX_BIN_DIR는 Main이 process.env에 설정 → 자동 상속

  // PATH prepend (claude.cmd, tmux.cmd 발견용)
  const binDir = mergedEnv.CMUX_BIN_DIR || path.join(__dirname, '../../resources/bin');
  mergedEnv.PATH = binDir + path.delimiter + (mergedEnv.PATH || '');

  const result = bridge.spawn({ ...options, env: mergedEnv });
  surfacePtyMap.set(surfaceId, result.id);
  ipcRenderer.send(IPC_CHANNELS.PTY_METADATA, { surfaceId, ptyId: result.id, pid: result.pid });
  return result;
}
```

### Step 3: XTermWrapper — workspaceId prop 추가

```typescript
export interface XTermWrapperProps {
  surfaceId: string;
  workspaceId: string;  // 추가
  // ... 기존 props
}

// initPty 내부 spawn 호출:
await window.ptyBridge.spawn(surfaceId, { shell, cwd, cols, rows, workspaceId });
```

### Step 4: PanelContainer, PanelLayout, App.tsx — workspaceId 전달

PanelContainer에 `workspaceId: string` prop 추가 → XTermWrapper에 전달.
PanelLayout에 `workspaceId: string` prop 추가 → PanelContainer에 전달.
App.tsx에서 `workspaceId={activeWsId || ''}` 전달.

### Step 5: env 구성 로직을 pure 함수로 추출

```typescript
// src/shared/env-utils.ts (새 파일)
export function buildPtyEnv(
  surfaceId: string,
  workspaceId: string | undefined,
  baseEnv: Record<string, string>,
): Record<string, string> {
  const env = { ...baseEnv };
  env.CMUX_SURFACE_ID = surfaceId;
  if (workspaceId) env.CMUX_WORKSPACE_ID = workspaceId;
  const binDir = env.CMUX_BIN_DIR || '';
  if (binDir) {
    const sep = process.platform === 'win32' ? ';' : ':';
    env.PATH = binDir + sep + (env.PATH || '');
  }
  return env;
}
```

preload에서 이 함수를 호출하여 env 구성.

### Step 6: 테스트

```typescript
// tests/unit/shared/env-utils.test.ts
import { describe, it, expect } from 'vitest';
import { buildPtyEnv } from '../../../src/shared/env-utils';

describe('buildPtyEnv', () => {
  it('sets CMUX_SURFACE_ID', () => {
    const env = buildPtyEnv('surf-1', undefined, {});
    expect(env.CMUX_SURFACE_ID).toBe('surf-1');
  });
  it('sets CMUX_WORKSPACE_ID when provided', () => {
    const env = buildPtyEnv('surf-1', 'ws-1', {});
    expect(env.CMUX_WORKSPACE_ID).toBe('ws-1');
  });
  it('omits CMUX_WORKSPACE_ID when undefined', () => {
    const env = buildPtyEnv('surf-1', undefined, {});
    expect(env.CMUX_WORKSPACE_ID).toBeUndefined();
  });
  it('inherits CMUX_SOCKET_PORT from baseEnv', () => {
    const env = buildPtyEnv('surf-1', undefined, { CMUX_SOCKET_PORT: '19841' });
    expect(env.CMUX_SOCKET_PORT).toBe('19841');
  });
  it('prepends CMUX_BIN_DIR to PATH', () => {
    const env = buildPtyEnv('surf-1', undefined, { CMUX_BIN_DIR: '/app/bin', PATH: '/usr/bin' });
    expect(env.PATH).toMatch(/^\/app\/bin/);
  });
  it('works without CMUX_BIN_DIR', () => {
    const env = buildPtyEnv('surf-1', undefined, { PATH: '/usr/bin' });
    expect(env.PATH).toBe('/usr/bin');
  });
});
```

### Step 7: 전체 테스트 실행 + 커밋

```
npx vitest run
git add -A && git commit -m "feat(task-16): env injection — CMUX_* vars + PATH prepend in PTY spawn"
```

---

## Task 17: claude.cmd + claude-wrapper.js

**Files:**
- Create: `resources/bin/claude.cmd`
- Create: `resources/bin/claude-wrapper.js`
- Test: `tests/unit/cli/claude-wrapper.test.ts`

### Step 1: resources/bin 디렉토리 생성 + claude.cmd

```cmd
@echo off
node "%~dp0claude-wrapper.js" %*
```

### Step 2: claude-wrapper.js 작성

설계안 v3 §4.2의 전체 코드 구현. 핵심 포인트:
- async IIFE (F1)
- socketAlive() async → await (F1)
- findRealClaude() `dir !== myDir`만 체크 (F14)
- error 시 exit 리스너 제거 후 passthrough (F13)
- BYPASS 서브명령 목록: mcp, config, api-key, rc, remote-control

### Step 3: 테스트

```typescript
// tests/unit/cli/claude-wrapper.test.ts
import { describe, it, expect } from 'vitest';

// claude-wrapper.js는 Node.js 스크립트이므로 로직을 추출하여 테스트
// hookJson 생성, bypass 판단, findRealClaude 로직 등

describe('claude-wrapper', () => {
  describe('Hook JSON', () => {
    it('generates 6 hook events with correct structure');
    it('SessionEnd has timeout 1');
    it('PreToolUse has async true and timeout 5');
    it('all commands reference correct CLI path');
  });

  describe('bypass logic', () => {
    it('bypasses mcp subcommand');
    it('bypasses config subcommand');
    it('does not bypass empty args');
    it('does not bypass unknown subcommands');
  });

  describe('findRealClaude', () => {
    it('skips entries in own directory');
    it('returns first entry from different directory');
    it('returns null when where fails');
  });
});
```

테스트를 위해 claude-wrapper.js의 핵심 로직(hookJson 생성, bypass 판단, findRealClaude)을 `resources/bin/claude-wrapper-lib.js`로 분리하고 `module.exports`로 내보낸다. 메인 스크립트는 이 lib를 require하여 사용. 테스트에서 `require('../../resources/bin/claude-wrapper-lib.js')`로 import.

### Step 4: 커밋

```
git add resources/bin/ tests/unit/cli/claude-wrapper.test.ts
git commit -m "feat(task-17): claude.cmd wrapper — async IIFE, hook injection, passthrough"
```

---

## Task 18: CLI claude-hook 6개 subcommand + 세션 스토어

**Files:**
- Create: `src/cli/claude-hook-session-store.ts`
- Modify: `src/cli/cmux-win.ts`
- Test: `tests/unit/cli/claude-hook-session-store.test.ts`
- Test: `tests/unit/cli/claude-hook-commands.test.ts`

### Step 1: 세션 스토어 구현

```typescript
// src/cli/claude-hook-session-store.ts
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

export interface SessionRecord {
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

export interface SessionStoreData {
  sessions: Record<string, SessionRecord>;
}

const SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1000;

export class ClaudeHookSessionStore {
  private filePath: string;

  constructor(filePath?: string) {
    this.filePath = filePath ?? path.join(
      process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming'),
      'cmux-win', 'claude-hook-sessions.json',
    );
  }

  load(): SessionStoreData {
    try {
      const raw = fs.readFileSync(this.filePath, 'utf8');
      const data: SessionStoreData = JSON.parse(raw);
      // 7일 만료 정리
      const now = Date.now();
      for (const [key, record] of Object.entries(data.sessions)) {
        if (now - record.updatedAt > SESSION_TTL_MS) {
          delete data.sessions[key];
        }
      }
      return data;
    } catch {
      return { sessions: {} };
    }
  }

  save(data: SessionStoreData): void {
    const dir = path.dirname(this.filePath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    const tmp = this.filePath + '.tmp';
    fs.writeFileSync(tmp, JSON.stringify(data, null, 2));
    fs.renameSync(tmp, this.filePath);
  }

  upsert(record: SessionRecord): void {
    const data = this.load();
    data.sessions[record.sessionId] = record;
    this.save(data);
  }

  lookup(sessionId: string): SessionRecord | null {
    if (!sessionId) return null;
    const data = this.load();
    return data.sessions[sessionId] ?? null;
  }

  consume(sessionId: string): SessionRecord | null {
    if (!sessionId) return null;
    const data = this.load();
    const record = data.sessions[sessionId];
    if (!record) return null;
    delete data.sessions[sessionId];
    this.save(data);
    return record;
  }

  findByContext(surfaceId: string, workspaceId: string): SessionRecord | null {
    const data = this.load();
    return Object.values(data.sessions).find(
      (r) => r.surfaceId === surfaceId && r.workspaceId === workspaceId,
    ) ?? null;
  }
}
```

### Step 2: 세션 스토어 테스트

```typescript
// tests/unit/cli/claude-hook-session-store.test.ts
describe('ClaudeHookSessionStore', () => {
  it('upsert and lookup');
  it('consume reads and deletes');
  it('findByContext fallback');
  it('7-day auto expiry');
  it('returns empty on missing file');
  it('recovers from corrupted file');
  it('atomic write (tmp → rename)');
});
```

### Step 3: cmux-win.ts claude-hook 구현

기존 stub(`case 'claude-hook': console.log(...); return;`)을 설계안 §4.3의 전체 구현으로 교체.

핵심: `readStdinJson()` 헬퍼 추가, `resolveSession()`/`consumeSession()` 헬퍼, `addr` 구성(F15).

```typescript
function readStdinJson(): Record<string, unknown> | null {
  try {
    // TTY stdin이면 무한 대기 방지 — 즉시 null 반환
    if (process.stdin.isTTY) return null;
    const input = fs.readFileSync(0, 'utf8'); // stdin = fd 0
    return input.trim() ? JSON.parse(input) : null;
  } catch { return null; }
}
```

### Step 4: claude-hook 명령 테스트

```typescript
// tests/unit/cli/claude-hook-commands.test.ts
describe('claude-hook commands', () => {
  it('session-start upserts session and calls agent.session_start RPC');
  it('prompt-submit sets running status and clears notifications');
  it('pre-tool-use saves AskUserQuestion lastBody');
  it('notification sets needs_input and creates notification');
  it('stop consumes session and sets idle status');
  it('session-end consumes session and calls agent.session_end');
  it('handles missing session gracefully');
  it('handles stdin parse failure gracefully');
});
```

RPC 호출은 mock으로 검증 (실제 socket 불필요).

### Step 5: 커밋

```
git add src/cli/ tests/unit/cli/
git commit -m "feat(task-18): CLI claude-hook 6 subcommands + session store"
```

---

## Task 19: PID sweep 타이머

**Files:**
- Modify: `src/main/index.ts`
- Test: `tests/unit/sot/pid-sweep.test.ts`

### Step 1: main/index.ts 수정

초기 상태 로드 부분에 agents 초기화 추가:

```typescript
if (initialState) {
  initialState = { ...initialState, agents: [] };
}
```

`app.whenReady()` 내부, socket 서버 시작 후에 PID sweep 타이머 추가:

```typescript
setInterval(() => {
  const agents = store.getState().agents;
  for (const agent of agents) {
    if (!agent.pid) continue;
    try {
      process.kill(agent.pid, 0);
    } catch (err: unknown) {
      const code = (err as NodeJS.ErrnoException).code;
      if (code === 'ESRCH') {
        store.dispatch({ type: 'agent.session_end', payload: { sessionId: agent.sessionId } });
      }
      // EPERM: 프로세스 존재 (권한 부족) → 유지 (F17)
    }
  }
}, 10_000);
```

### Step 2: PID sweep 로직 테스트

PID sweep 로직을 pure 함수로 추출하여 테스트:

```typescript
// tests/unit/sot/pid-sweep.test.ts
describe('PID sweep', () => {
  it('dispatches session_end for ESRCH (dead process)');
  it('keeps agent for EPERM (alive but no permission)');
  it('keeps agent when pid is undefined');
  it('keeps agent when process.kill succeeds (alive)');
});
```

### Step 3: 커밋

```
git add src/main/index.ts tests/unit/sot/pid-sweep.test.ts
git commit -m "feat(task-19): PID sweep timer — 10s interval, ESRCH-only cleanup"
```

---

## Task 20: Sidebar 에이전트 상태 UI 강화

**Files:**
- Modify: `src/renderer/components/sidebar/WorkspaceItem.tsx`

### Step 1: WorkspaceItem에 에이전트 상태 표시 강화

기존 `statusIcon`만 표시하던 부분을 교체:

```tsx
{wsAgents.map((agent) => (
  <div key={agent.sessionId} style={{
    fontSize: '11px', padding: '2px 12px',
    display: 'flex', alignItems: 'center', gap: '4px',
  }}>
    <span style={{ color: agent.statusColor || '#888' }}>
      {agent.statusIcon}{' '}
      {agent.status === 'running' ? 'Running'
        : agent.status === 'idle' ? 'Idle'
        : agent.status === 'needs_input' ? 'Needs input'
        : agent.status}
    </span>
    <span style={{ color: '#555', fontSize: '10px' }}>
      {agent.agentType}
    </span>
  </div>
))}
```

### Step 2: 커밋

```
git add src/renderer/components/sidebar/WorkspaceItem.tsx
git commit -m "feat(task-20): sidebar agent status — icon + text + color + type"
```

---

## Task 21: tmux.cmd shim

**Files:**
- Create: `resources/bin/tmux.cmd`
- Create: `resources/bin/tmux-shim.js`
- Test: `tests/unit/cli/tmux-shim.test.ts`

### Step 1: tmux.cmd

```cmd
@echo off
node "%~dp0tmux-shim.js" %*
```

### Step 2: tmux-shim.js

12개 핵심 명령 매핑 구현. 설계안 §4.6 기반.

핵심 함수:
- `resolveTarget(target, addr)` — %N/숫자/UUID 변환 (F5)
- `getActivePanelId(addr)` — split-window 시 활성 패널 조회 (F18)
- `convertTmuxKeys(args)` — Enter/Space/Tab/C-x 변환

매핑: new-session, new-window, split-window, select-window, select-pane, send-keys, capture-pane(stub), list-windows, list-panes, kill-window, kill-pane, resize-pane, display-message, last-pane, swap-pane(stub), break-pane(stub).

### Step 3: 테스트

```typescript
// tests/unit/cli/tmux-shim.test.ts
describe('tmux-shim', () => {
  describe('convertTmuxKeys', () => {
    it('converts Enter to \\n');
    it('converts Space to " "');
    it('converts C-c to \\x03');
    it('passes through normal text');
  });

  describe('command mapping', () => {
    it('new-session -s name → workspace.create');
    it('split-window -h → panel.split horizontal');
    it('split-window -v → panel.split vertical');
    it('send-keys text Enter → surface.send_text with \\n');
    it('select-window -t 2 → workspace.select (index resolve)');
    it('kill-pane -t %1 → panel.close (pane resolve)');
    it('list-windows → workspace.list');
    it('unknown command → error exit 1');
  });
});
```

### Step 4: 커밋

```
git add resources/bin/tmux.cmd resources/bin/tmux-shim.js tests/unit/cli/tmux-shim.test.ts
git commit -m "feat(task-21): tmux.cmd shim — 17 commands, target resolution, key conversion"
```

---

## Task 22: 자체 오케스트레이션 — agent.spawn

**Files:**
- Modify: `src/shared/actions.ts` — AgentSpawnAction 추가
- Modify: `src/shared/types.ts` — SurfaceState.pendingCommand 추가
- Modify: `src/main/sot/store.ts` — agent.spawn applyAction
- Modify: `src/main/socket/handlers/agent.ts` — agent.spawn RPC
- Modify: `src/renderer/components/sidebar/Sidebar.tsx` — [+ Agent] UI
- Modify: `src/renderer/components/terminal/XTermWrapper.tsx` — pendingCommand 실행
- Test: `tests/unit/sot/agent-spawn.test.ts`

### Step 1: actions.ts — AgentSpawnAction

```typescript
export const AgentSpawnAction = z.object({
  type: z.literal('agent.spawn'),
  payload: z.object({
    agentType: z.enum(['claude', 'codex', 'gemini', 'opencode']),
    workspaceId: z.string(),
    task: z.string().optional(),
  }),
});
```

ActionSchema union에 추가.

### Step 2: types.ts — pendingCommand

```typescript
export interface SurfaceState {
  // ... 기존
  pendingCommand?: string; // F20: agent.spawn 시 PTY ready 후 실행
}
```

### Step 3: store.ts — agent.spawn applyAction

설계안 §4.7 코드. 새 패널+서피스 생성, panelLayout에 split 추가, agents[]에 등록, pendingCommand 설정.

### Step 4: agent.ts — agent.spawn RPC

```typescript
router.register('agent.spawn', (params) => {
  const p = params as { agentType: string; workspaceId: string; task?: string };
  if (!p?.agentType) throw new Error('agentType is required');
  if (!p?.workspaceId) throw new Error('workspaceId is required');
  const result = store.dispatch({ type: 'agent.spawn', payload: p });
  if (!result.ok) throw new Error(result.error ?? 'Failed to spawn agent');
  return { ok: true };
});
```

### Step 5: XTermWrapper — pendingCommand 실행 (F20)

initPty 완료 후, surface의 pendingCommand가 있으면 실행:

```typescript
// appState에서 surface의 pendingCommand 확인 (prop으로 전달)
// PTY spawn 성공 후:
if (pendingCommand) {
  window.ptyBridge.write(surfaceId, pendingCommand);
  // pendingCommand 소비
}
```

pendingCommand 전달 체인:
- `App.tsx`: appState.surfaces에서 activeSurface.pendingCommand 읽기
- `PanelLayout` → `PanelContainer` → `XTermWrapper`에 `pendingCommand` prop 전달
- `PanelContainer.tsx`: `const pendingCmd = (activeSurface as any)?.pendingCommand;`
- `XTermWrapper`: initPty 완료 후 pendingCommand 있으면 write + dispatch(surface.update_meta, {surfaceId, pendingCommand: null})

### Step 6: Sidebar.tsx — [+ Agent] 드롭다운

설계안 §4.7 UI 코드. Sidebar 하단에 select 드롭다운.

### Step 7: 테스트

```typescript
// tests/unit/sot/agent-spawn.test.ts
describe('agent.spawn', () => {
  it('creates new panel and surface');
  it('adds split to panelLayout');
  it('registers agent in agents[]');
  it('sets pendingCommand on surface');
  it('ignores nonexistent workspaceId');
});
```

### Step 8: 커밋

```
git add src/shared/ src/main/ src/renderer/ tests/unit/sot/agent-spawn.test.ts
git commit -m "feat(task-22): agent.spawn — self-orchestration with pendingCommand"
```

---

## Phase 4 완료 체크리스트

```
기능:
  [ ] PTY spawn 시 CMUX_* 환경변수 주입됨
  [ ] PATH에 resources/bin 추가됨
  [ ] claude 명령 시 wrapper가 Hook JSON 주입
  [ ] Hook 이벤트 → CLI → Socket RPC → Store 업데이트
  [ ] 세션 스토어에 session-workspace 매핑 저장
  [ ] Sidebar에 에이전트 상태 표시 (⚡Running/⏸Idle/🔔Needs input)
  [ ] PID sweep이 죽은 에이전트 자동 정리
  [ ] tmux 명령이 Socket RPC로 변환됨
  [ ] [+ Agent] UI로 에이전트 스폰 가능
  [ ] pendingCommand로 PTY ready 후 에이전트 명령 실행

테스트:
  [ ] env injection 테스트 통과
  [ ] claude-wrapper 테스트 통과
  [ ] session store CRUD 테스트 통과
  [ ] claude-hook 6 subcommand 테스트 통과
  [ ] PID sweep 테스트 통과
  [ ] tmux-shim 명령 매핑 테스트 통과
  [ ] agent.spawn 테스트 통과
  [ ] 전체 테스트 ALL PASS

BUG 검증:
  [ ] F11: 포트 충돌 시에도 올바른 포트 사용
  [ ] F13: claude spawn 실패 시 이중 자식 없음
  [ ] F14: findRealClaude가 자기 자신 제외
  [ ] F17: EPERM 프로세스가 정리되지 않음
  [ ] F20: agent.spawn 후 PTY에 명령 도달
```


> **Phase 3-6 구현 계획은 Phase 4 완료 후 각각 별도 문서로 작성한다.**
> - `2026-03-21-phase3-implementation-plan.md`
> - `2026-03-21-phase5-implementation-plan.md`
> - `2026-03-21-phase6-implementation-plan.md`
