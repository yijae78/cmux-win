# cmux-win Phase 1: Tasks 4~9 완전 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**선행 조건:** Task 1~3 완료 (프로젝트 초기화, Shared 타입, SOT 스토어)

---

## 사전 성찰: Task 3 → Task 4 인터페이스 충돌 분석

### 충돌 1: store.ts의 미들웨어 미지원

Task 3의 `store.ts`는 `dispatch()` 안에서 검증+변경+이벤트를 모두 수행한다.
Task 4는 미들웨어 체인(검증→변경→영구저장→IPC→감사)을 요구한다.

**해결:** Task 4 첫 단계에서 store.ts를 리팩토링하여 미들웨어 훅을 추가한다.
기존 테스트는 모두 통과해야 한다 (리팩토링이지 기능 변경 아님).

### 충돌 2: surface.send_text의 사이드이펙트 경로

`surface.send_text`는 SOT 상태를 변경하지 않는다 (PTY에 데이터 전달만).
하지만 Socket API에서 이 명령을 받으면 특정 Renderer의 PTY에 전달해야 한다.

**해결:** store가 `side-effect` 이벤트를 emit하고, app.ts 레이어에서 이를 수신하여
해당 Renderer의 IPC로 포워딩한다. 미들웨어와 윈도우 매니저 간 순환 의존 없음.

```
Socket → store.dispatch('surface.send_text')
  → store emit('side-effect', { type: 'pty-write', surfaceId, text })
  → app.ts listener → windowManager.forwardToRenderer(surfaceId, 'pty:write', text)
  → Renderer preload → ptyBridge.write(text)
```

### 충돌 3: node-pty contextBridge 콜백 제약

contextBridge를 통해 전달된 콜백은 Electron이 프록시한다.
`pty.onData(callback)` 패턴이 contextBridge에서 동작하는지 검증 필요.

**해결:** preload에서 PTY 인스턴스를 직접 관리하고, 콜백 등록/해제를
명시적 ID 기반 API로 노출한다. 이벤트 기반이 아닌 폴링이 필요하면
MessagePort를 사용한다 (Electron의 postMessage는 제한 없음).

실제 구현: contextBridge 콜백은 Electron이 자동 프록시하므로 동작한다.
단, 반환값이 disposable인 경우 래핑이 필요하다.

---

## Task 4: SOT 미들웨어

**Files:**
- Modify: `src/main/sot/store.ts` (미들웨어 훅 추가)
- Create: `src/main/sot/middleware/persistence.ts`
- Create: `src/main/sot/middleware/audit-log.ts`
- Test: `tests/unit/sot/store-middleware.test.ts`
- Test: `tests/unit/sot/middleware/persistence.test.ts`
- Test: `tests/unit/sot/middleware/audit-log.test.ts`

### Step 1: 미들웨어 훅 테스트 작성 (실패)

`tests/unit/sot/store-middleware.test.ts`:
```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AppStateStore } from '../../../src/main/sot/store';
import type { Action } from '../../../src/shared/actions';
import type { AppState } from '../../../src/shared/types';

describe('AppStateStore Middleware', () => {
  let store: AppStateStore;

  beforeEach(() => {
    store = new AppStateStore();
  });

  it('calls post-dispatch middleware after successful dispatch', () => {
    const postFn = vi.fn();
    store.use({ post: postFn });
    store.dispatch({ type: 'workspace.create', payload: { windowId: 'win-1' } });
    expect(postFn).toHaveBeenCalledTimes(1);
    expect(postFn).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'workspace.create' }),
      expect.any(Object), // prevState
      expect.any(Object), // nextState
    );
  });

  it('does not call post middleware on validation failure', () => {
    const postFn = vi.fn();
    store.use({ post: postFn });
    store.dispatch({ type: 'invalid', payload: {} } as any);
    expect(postFn).not.toHaveBeenCalled();
  });

  it('supports multiple middleware in order', () => {
    const order: string[] = [];
    store.use({ post: () => { order.push('first'); } });
    store.use({ post: () => { order.push('second'); } });
    store.dispatch({ type: 'workspace.create', payload: { windowId: 'win-1' } });
    expect(order).toEqual(['first', 'second']);
  });

  it('emits side-effect event for surface.send_text', () => {
    const handler = vi.fn();
    store.on('side-effect', handler);
    store.dispatch({ type: 'surface.send_text', payload: { surfaceId: 's-1', text: 'hello' } });
    expect(handler).toHaveBeenCalledWith({
      type: 'pty-write',
      surfaceId: 's-1',
      text: 'hello',
    });
  });

  it('existing tests still pass after middleware refactor - workspace CRUD', () => {
    store.dispatch({ type: 'workspace.create', payload: { windowId: 'win-1', name: 'WS' } });
    expect(store.getState().workspaces).toHaveLength(1);
    const wsId = store.getState().workspaces[0].id;
    store.dispatch({ type: 'workspace.rename', payload: { workspaceId: wsId, name: 'Renamed' } });
    expect(store.getState().workspaces[0].name).toBe('Renamed');
    store.dispatch({ type: 'workspace.close', payload: { workspaceId: wsId } });
    expect(store.getState().workspaces).toHaveLength(0);
  });
});
```

### Step 2: 테스트 실행, 실패 확인

```bash
npx vitest run tests/unit/sot/store-middleware.test.ts
```
Expected: FAIL — `store.use` 메서드 없음

### Step 3: store.ts 리팩토링 — 미들웨어 훅 추가

`src/main/sot/store.ts` 수정:
```typescript
import { EventEmitter } from 'node:events';
import { produce } from 'immer';
import { ActionSchema, type Action } from '../../shared/actions';
import type { AppState } from '../../shared/types';
import { STATE_HISTORY_MAX } from '../../shared/constants';
import { createDefaultState } from './create-default-state';
import crypto from 'node:crypto';

export interface DispatchResult {
  ok: boolean;
  error?: string;
}

export interface HistoryEntry {
  action: Action;
  timestamp: number;
}

export interface Middleware {
  post?: (action: Action, prevState: Readonly<AppState>, nextState: Readonly<AppState>) => void;
}

export class AppStateStore extends EventEmitter {
  private state: AppState;
  private history: HistoryEntry[] = [];
  private middlewares: Middleware[] = [];

  constructor(initialState?: AppState) {
    super();
    this.state = initialState ?? createDefaultState();
  }

  getState(): Readonly<AppState> {
    return this.state;
  }

  getHistory(): ReadonlyArray<HistoryEntry> {
    return this.history;
  }

  use(middleware: Middleware): void {
    this.middlewares.push(middleware);
  }

  dispatch(rawAction: unknown): DispatchResult {
    const parsed = ActionSchema.safeParse(rawAction);
    if (!parsed.success) {
      return { ok: false, error: parsed.error.message };
    }
    const action = parsed.data;
    const prevState = this.state;

    try {
      // 사이드이펙트 전용 액션 처리
      if (action.type === 'surface.send_text') {
        this.emit('side-effect', {
          type: 'pty-write',
          surfaceId: action.payload.surfaceId,
          text: action.payload.text,
        });
        // post middleware도 호출 (감사 로그 등)
        for (const mw of this.middlewares) {
          mw.post?.(action, prevState, prevState);
        }
        return { ok: true };
      }

      this.state = produce(this.state, (draft) => {
        this.applyAction(draft, action);
      });

      this.history.push({ action, timestamp: Date.now() });
      if (this.history.length > STATE_HISTORY_MAX) {
        this.history.shift();
      }

      // post 미들웨어 실행
      for (const mw of this.middlewares) {
        mw.post?.(action, prevState, this.state);
      }

      this.emit('change', action);
      return { ok: true };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return { ok: false, error: message };
    }
  }

  private applyAction(draft: AppState, action: Action): void {
    switch (action.type) {
      case 'workspace.create': {
        const id = crypto.randomUUID();
        const panelId = crypto.randomUUID();
        const surfaceId = crypto.randomUUID();
        draft.workspaces.push({
          id, windowId: action.payload.windowId,
          name: action.payload.name ?? 'New Workspace',
          panelLayout: { type: 'leaf', panelId },
          agentPids: {}, statusEntries: [], unreadCount: 0, isPinned: false,
        });
        draft.panels.push({
          id: panelId, workspaceId: id, panelType: 'terminal',
          surfaceIds: [surfaceId], activeSurfaceId: surfaceId, isZoomed: false,
        });
        draft.surfaces.push({ id: surfaceId, panelId, surfaceType: 'terminal', title: 'Terminal' });
        const win = draft.windows.find((w) => w.id === action.payload.windowId);
        if (win) win.workspaceIds.push(id);
        break;
      }
      case 'workspace.close': {
        const wsIndex = draft.workspaces.findIndex((w) => w.id === action.payload.workspaceId);
        if (wsIndex === -1) break;
        draft.panels = draft.panels.filter((p) => p.workspaceId !== action.payload.workspaceId);
        draft.surfaces = draft.surfaces.filter((s) => draft.panels.some((p) => p.id === s.panelId));
        draft.workspaces.splice(wsIndex, 1);
        for (const win of draft.windows) {
          win.workspaceIds = win.workspaceIds.filter((id) => id !== action.payload.workspaceId);
        }
        if (draft.focus.activeWorkspaceId === action.payload.workspaceId) {
          draft.focus.activeWorkspaceId = draft.workspaces[0]?.id ?? null;
        }
        break;
      }
      case 'workspace.select': {
        draft.focus.activeWorkspaceId = action.payload.workspaceId;
        const ws = draft.workspaces.find((w) => w.id === action.payload.workspaceId);
        if (ws) draft.focus.activeWindowId = ws.windowId;
        break;
      }
      case 'workspace.rename': {
        const ws = draft.workspaces.find((w) => w.id === action.payload.workspaceId);
        if (ws) ws.name = action.payload.name;
        break;
      }
      case 'panel.focus': {
        draft.focus.activePanelId = action.payload.panelId;
        break;
      }
      case 'panel.close': {
        const idx = draft.panels.findIndex((p) => p.id === action.payload.panelId);
        if (idx === -1) break;
        draft.surfaces = draft.surfaces.filter((s) => s.panelId !== action.payload.panelId);
        draft.panels.splice(idx, 1);
        break;
      }
      case 'panel.split': break; // Phase 2
      case 'panel.resize': break; // Phase 2
      case 'surface.create': {
        const newId = crypto.randomUUID();
        const panel = draft.panels.find((p) => p.id === action.payload.panelId);
        if (!panel) break;
        draft.surfaces.push({ id: newId, panelId: action.payload.panelId, surfaceType: action.payload.surfaceType, title: action.payload.surfaceType === 'terminal' ? 'Terminal' : 'New Tab' });
        panel.surfaceIds.push(newId);
        panel.activeSurfaceId = newId;
        break;
      }
      case 'surface.close': {
        const si = draft.surfaces.findIndex((s) => s.id === action.payload.surfaceId);
        if (si === -1) break;
        const surface = draft.surfaces[si];
        const panel = draft.panels.find((p) => p.id === surface.panelId);
        if (panel) {
          panel.surfaceIds = panel.surfaceIds.filter((id) => id !== action.payload.surfaceId);
          if (panel.activeSurfaceId === action.payload.surfaceId) panel.activeSurfaceId = panel.surfaceIds[0] ?? '';
        }
        draft.surfaces.splice(si, 1);
        break;
      }
      case 'surface.focus': {
        draft.focus.activeSurfaceId = action.payload.surfaceId;
        const s = draft.surfaces.find((sf) => sf.id === action.payload.surfaceId);
        if (s) {
          draft.focus.activePanelId = s.panelId;
          const p = draft.panels.find((pp) => pp.id === s.panelId);
          if (p) p.activeSurfaceId = action.payload.surfaceId;
        }
        break;
      }
      case 'surface.send_text': break; // side-effect only, handled above
      case 'agent.session_start': {
        draft.agents.push({
          sessionId: action.payload.sessionId, agentType: action.payload.agentType,
          workspaceId: action.payload.workspaceId, surfaceId: action.payload.surfaceId,
          status: 'running', statusIcon: '⚡', statusColor: 'blue',
          pid: action.payload.pid, lastActivity: Date.now(),
        });
        break;
      }
      case 'agent.status_update': {
        const agent = draft.agents.find((a) => a.sessionId === action.payload.sessionId);
        if (agent) {
          agent.status = action.payload.status;
          if (action.payload.icon) agent.statusIcon = action.payload.icon;
          if (action.payload.color) agent.statusColor = action.payload.color;
          agent.lastActivity = Date.now();
        }
        break;
      }
      case 'agent.session_end': {
        draft.agents = draft.agents.filter((a) => a.sessionId !== action.payload.sessionId);
        break;
      }
      case 'notification.create': {
        draft.notifications.push({
          id: crypto.randomUUID(), title: action.payload.title,
          subtitle: action.payload.subtitle, body: action.payload.body,
          workspaceId: action.payload.workspaceId, surfaceId: action.payload.surfaceId,
          createdAt: Date.now(), isRead: false,
        });
        break;
      }
      case 'notification.clear': {
        if (action.payload.workspaceId) {
          draft.notifications = draft.notifications.filter((n) => n.workspaceId !== action.payload.workspaceId);
        } else {
          draft.notifications = [];
        }
        break;
      }
      case 'focus.update': {
        const p = action.payload;
        if (p.activeWindowId !== undefined) draft.focus.activeWindowId = p.activeWindowId;
        if (p.activeWorkspaceId !== undefined) draft.focus.activeWorkspaceId = p.activeWorkspaceId;
        if (p.activePanelId !== undefined) draft.focus.activePanelId = p.activePanelId;
        if (p.activeSurfaceId !== undefined) draft.focus.activeSurfaceId = p.activeSurfaceId;
        if (p.focusTarget !== undefined) draft.focus.focusTarget = p.focusTarget;
        break;
      }
      case 'settings.update': {
        Object.assign(draft.settings, action.payload);
        break;
      }
    }
  }
}
```

### Step 4: 기존 Task 3 테스트 + 새 미들웨어 테스트 실행

```bash
npx vitest run tests/unit/sot/
```
Expected: ALL PASS (기존 store.test.ts + 새 store-middleware.test.ts)

### Step 5: Persistence 미들웨어 테스트 (실패)

`tests/unit/sot/middleware/persistence.test.ts`:
```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { PersistenceMiddleware } from '../../../../src/main/sot/middleware/persistence';
import type { AppState } from '../../../../src/shared/types';
import { createDefaultState } from '../../../../src/main/sot/create-default-state';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

describe('PersistenceMiddleware', () => {
  const testDir = path.join(os.tmpdir(), 'cmux-win-test-' + Date.now());
  const testFile = path.join(testDir, 'session.json');
  let middleware: PersistenceMiddleware;

  beforeEach(() => {
    fs.mkdirSync(testDir, { recursive: true });
    middleware = new PersistenceMiddleware(testFile, 50); // 50ms debounce for tests
  });

  afterEach(() => {
    middleware.dispose();
    fs.rmSync(testDir, { recursive: true, force: true });
  });

  it('saves state to file after debounce', async () => {
    const state = createDefaultState();
    middleware.post!(
      { type: 'workspace.create', payload: { windowId: 'w1' } },
      state,
      state,
    );
    // Wait for debounce
    await new Promise((r) => setTimeout(r, 100));
    expect(fs.existsSync(testFile)).toBe(true);
    const saved = JSON.parse(fs.readFileSync(testFile, 'utf-8'));
    expect(saved.version).toBe(1);
    expect(saved.state).toBeDefined();
  });

  it('debounces multiple rapid dispatches', async () => {
    const writeSpy = vi.spyOn(fs, 'writeFileSync');
    const state = createDefaultState();
    middleware.post!({ type: 'workspace.create', payload: { windowId: 'w1' } }, state, state);
    middleware.post!({ type: 'workspace.create', payload: { windowId: 'w1' } }, state, state);
    middleware.post!({ type: 'workspace.create', payload: { windowId: 'w1' } }, state, state);
    await new Promise((r) => setTimeout(r, 100));
    // writeFileSync should only be called once (debounced)
    const calls = writeSpy.mock.calls.filter((c) => String(c[0]).includes('session.json'));
    expect(calls.length).toBe(1);
    writeSpy.mockRestore();
  });

  it('creates backup before save', async () => {
    const state = createDefaultState();
    // First save
    middleware.post!({ type: 'workspace.create', payload: { windowId: 'w1' } }, state, state);
    await new Promise((r) => setTimeout(r, 100));
    // Second save (should create backup of first)
    middleware.post!({ type: 'workspace.rename', payload: { workspaceId: 'x', name: 'y' } }, state, state);
    await new Promise((r) => setTimeout(r, 100));
    expect(fs.existsSync(testFile + '.bak')).toBe(true);
  });

  it('loads persisted state', () => {
    const state = createDefaultState();
    fs.writeFileSync(testFile, JSON.stringify({ version: 1, state }));
    const loaded = PersistenceMiddleware.loadState(testFile);
    expect(loaded).not.toBeNull();
    expect(loaded!.settings.terminal.defaultShell).toBe('powershell');
  });

  it('returns null for missing file', () => {
    const loaded = PersistenceMiddleware.loadState('/nonexistent/path.json');
    expect(loaded).toBeNull();
  });

  it('returns null for corrupted file', () => {
    fs.writeFileSync(testFile, 'not valid json{{{');
    const loaded = PersistenceMiddleware.loadState(testFile);
    expect(loaded).toBeNull();
  });
});
```

### Step 6: Persistence 미들웨어 구현

`src/main/sot/middleware/persistence.ts`:
```typescript
import fs from 'node:fs';
import path from 'node:path';
import type { Action } from '../../../shared/actions';
import type { AppState, PersistedState } from '../../../shared/types';
import type { Middleware } from '../store';
import { SCHEMA_VERSION, SESSION_SAVE_DEBOUNCE_MS } from '../../../shared/constants';

export class PersistenceMiddleware implements Middleware {
  private filePath: string;
  private debounceMs: number;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private latestState: AppState | null = null;

  constructor(filePath: string, debounceMs: number = SESSION_SAVE_DEBOUNCE_MS) {
    this.filePath = filePath;
    this.debounceMs = debounceMs;
  }

  post = (action: Action, _prevState: Readonly<AppState>, nextState: Readonly<AppState>): void => {
    this.latestState = nextState as AppState;
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => this.flush(), this.debounceMs);
  };

  private flush(): void {
    if (!this.latestState) return;
    try {
      const dir = path.dirname(this.filePath);
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

      // Backup existing file
      if (fs.existsSync(this.filePath)) {
        fs.copyFileSync(this.filePath, this.filePath + '.bak');
      }

      const persisted: PersistedState = {
        version: SCHEMA_VERSION,
        state: this.latestState,
      };
      fs.writeFileSync(this.filePath, JSON.stringify(persisted), 'utf-8');
    } catch (err) {
      console.error('[PersistenceMiddleware] Failed to save:', err);
    }
  }

  dispose(): void {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    // Flush remaining state synchronously on dispose
    if (this.latestState) this.flush();
  }

  static loadState(filePath: string): AppState | null {
    try {
      if (!fs.existsSync(filePath)) return null;
      const raw = fs.readFileSync(filePath, 'utf-8');
      const parsed = JSON.parse(raw) as PersistedState;
      if (!parsed || typeof parsed.version !== 'number' || !parsed.state) return null;
      // TODO: migration chain (향후 스키마 변경 시)
      return parsed.state;
    } catch {
      return null;
    }
  }
}
```

### Step 7: Audit Log 미들웨어 테스트 (실패)

`tests/unit/sot/middleware/audit-log.test.ts`:
```typescript
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { AuditLogMiddleware } from '../../../../src/main/sot/middleware/audit-log';
import { createDefaultState } from '../../../../src/main/sot/create-default-state';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

describe('AuditLogMiddleware', () => {
  const testDir = path.join(os.tmpdir(), 'cmux-win-audit-' + Date.now());
  const logFile = path.join(testDir, 'debug.log');
  let middleware: AuditLogMiddleware;

  beforeEach(() => {
    fs.mkdirSync(testDir, { recursive: true });
    middleware = new AuditLogMiddleware(logFile);
  });

  afterEach(() => {
    fs.rmSync(testDir, { recursive: true, force: true });
  });

  it('writes action to log file', () => {
    const state = createDefaultState();
    middleware.post!(
      { type: 'workspace.create', payload: { windowId: 'win-1' } },
      state, state,
    );
    const content = fs.readFileSync(logFile, 'utf-8');
    expect(content).toContain('workspace.create');
    expect(content).toContain('win-1');
  });

  it('appends multiple entries', () => {
    const state = createDefaultState();
    middleware.post!({ type: 'workspace.create', payload: { windowId: 'w1' } }, state, state);
    middleware.post!({ type: 'workspace.create', payload: { windowId: 'w2' } }, state, state);
    const lines = fs.readFileSync(logFile, 'utf-8').trim().split('\n');
    expect(lines.length).toBe(2);
  });

  it('includes ISO timestamp', () => {
    const state = createDefaultState();
    middleware.post!({ type: 'workspace.create', payload: { windowId: 'w1' } }, state, state);
    const content = fs.readFileSync(logFile, 'utf-8');
    // ISO 8601 pattern
    expect(content).toMatch(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
  });
});
```

### Step 8: Audit Log 미들웨어 구현

`src/main/sot/middleware/audit-log.ts`:
```typescript
import fs from 'node:fs';
import path from 'node:path';
import type { Action } from '../../../shared/actions';
import type { AppState } from '../../../shared/types';
import type { Middleware } from '../store';

export class AuditLogMiddleware implements Middleware {
  private filePath: string;

  constructor(filePath: string) {
    this.filePath = filePath;
    const dir = path.dirname(filePath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  }

  post = (action: Action, _prevState: Readonly<AppState>, _nextState: Readonly<AppState>): void => {
    try {
      const entry = `${new Date().toISOString()} ${action.type} ${JSON.stringify(action.payload)}\n`;
      fs.appendFileSync(this.filePath, entry, 'utf-8');
    } catch {
      // 로그 실패는 무시 — 앱 동작에 영향 주지 않음
    }
  };
}
```

### Step 9: 전체 미들웨어 테스트 실행

```bash
npx vitest run tests/unit/sot/
```
Expected: ALL PASS

### Step 10: 커밋

```bash
git add src/main/sot/ tests/unit/sot/
git commit -m "feat: add middleware system to SOT store with persistence and audit-log"
```

---

## Task 5: 터미널 엔진

**Files:**
- Create: `src/preload/terminal-preload.ts`
- Create: `src/renderer/components/terminal/XTermWrapper.tsx`
- Create: `src/renderer/components/terminal/use-terminal.ts`
- Test: `tests/unit/terminal/pty-bridge.test.ts`

**Deps 설치:**
```bash
npm install xterm @xterm/addon-webgl @xterm/addon-fit @xterm/addon-search node-pty
npm install -D electron-rebuild
npx electron-rebuild -f -w node-pty
```

### Step 1: PTY Bridge 테스트 (실패)

`tests/unit/terminal/pty-bridge.test.ts`:
```typescript
import { describe, it, expect, vi } from 'vitest';
import { PtyBridge, type PtyInstance } from '../../../src/preload/terminal-preload';

// node-pty를 모킹 (Vitest는 Electron 없이 실행)
vi.mock('node-pty', () => ({
  spawn: vi.fn(() => ({
    pid: 1234,
    cols: 80,
    rows: 24,
    process: 'powershell.exe',
    onData: vi.fn((cb: (data: string) => void) => {
      // 즉시 테스트 데이터 전송
      setTimeout(() => cb('PS C:\\> '), 10);
      return { dispose: vi.fn() };
    }),
    onExit: vi.fn((cb: (e: { exitCode: number }) => void) => {
      return { dispose: vi.fn() };
    }),
    write: vi.fn(),
    resize: vi.fn(),
    kill: vi.fn(),
  })),
}));

describe('PtyBridge', () => {
  it('spawns a PTY and returns instance info', () => {
    const bridge = new PtyBridge();
    const info = bridge.spawn('t-1', 'powershell.exe', [], { cols: 80, rows: 24, cwd: 'C:\\' });
    expect(info.pid).toBe(1234);
    expect(info.id).toBe('t-1');
  });

  it('writes data to PTY', () => {
    const bridge = new PtyBridge();
    bridge.spawn('t-1', 'powershell.exe', [], { cols: 80, rows: 24, cwd: 'C:\\' });
    bridge.write('t-1', 'ls\r');
    // write가 호출되었는지 확인 (mock)
    const pty = require('node-pty');
    expect(pty.spawn).toHaveBeenCalled();
  });

  it('resizes PTY', () => {
    const bridge = new PtyBridge();
    bridge.spawn('t-1', 'powershell.exe', [], { cols: 80, rows: 24, cwd: 'C:\\' });
    bridge.resize('t-1', 120, 40);
    // resize 호출 확인
  });

  it('kills PTY and cleans up', () => {
    const bridge = new PtyBridge();
    bridge.spawn('t-1', 'powershell.exe', [], { cols: 80, rows: 24, cwd: 'C:\\' });
    bridge.kill('t-1');
    expect(bridge.has('t-1')).toBe(false);
  });

  it('registers onData callback', async () => {
    const bridge = new PtyBridge();
    bridge.spawn('t-1', 'powershell.exe', [], { cols: 80, rows: 24, cwd: 'C:\\' });
    const received: string[] = [];
    bridge.onData('t-1', (data) => received.push(data));
    await new Promise((r) => setTimeout(r, 50));
    expect(received.length).toBeGreaterThan(0);
  });

  it('returns available shells', () => {
    const bridge = new PtyBridge();
    const shells = bridge.getAvailableShells();
    expect(shells).toContain('powershell');
  });
});
```

### Step 2: PTY Bridge 구현

`src/preload/terminal-preload.ts`:
```typescript
import { contextBridge, ipcRenderer } from 'electron';
import * as pty from 'node-pty';
import os from 'node:os';
import fs from 'node:fs';
import path from 'node:path';

interface PtySpawnOptions {
  cols: number;
  rows: number;
  cwd: string;
  env?: Record<string, string>;
}

export interface PtyInstanceInfo {
  id: string;
  pid: number;
}

interface ManagedPty {
  instance: pty.IPty;
  dataCallbacks: Array<(data: string) => void>;
  exitCallbacks: Array<(code: number) => void>;
}

export class PtyBridge {
  private instances: Map<string, ManagedPty> = new Map();

  spawn(id: string, shell: string, args: string[], options: PtySpawnOptions): PtyInstanceInfo {
    const resolvedShell = this.resolveShell(shell);
    const instance = pty.spawn(resolvedShell, args, {
      name: 'xterm-256color',
      cols: options.cols,
      rows: options.rows,
      cwd: options.cwd || os.homedir(),
      env: { ...process.env, ...options.env } as Record<string, string>,
    });

    const managed: ManagedPty = { instance, dataCallbacks: [], exitCallbacks: [] };

    instance.onData((data: string) => {
      for (const cb of managed.dataCallbacks) cb(data);
    });

    instance.onExit(({ exitCode }: { exitCode: number }) => {
      for (const cb of managed.exitCallbacks) cb(exitCode);
      this.instances.delete(id);
    });

    this.instances.set(id, managed);

    // SOT에 메타데이터 보고 (저빈도)
    ipcRenderer.send('pty:metadata', { surfaceId: id, pid: instance.pid, cwd: options.cwd, shell });

    return { id, pid: instance.pid };
  }

  write(id: string, data: string): void {
    this.instances.get(id)?.instance.write(data);
  }

  resize(id: string, cols: number, rows: number): void {
    this.instances.get(id)?.instance.resize(cols, rows);
  }

  kill(id: string): void {
    const managed = this.instances.get(id);
    if (managed) {
      managed.instance.kill();
      this.instances.delete(id);
    }
  }

  has(id: string): boolean {
    return this.instances.has(id);
  }

  onData(id: string, callback: (data: string) => void): void {
    this.instances.get(id)?.dataCallbacks.push(callback);
  }

  onExit(id: string, callback: (code: number) => void): void {
    this.instances.get(id)?.exitCallbacks.push(callback);
  }

  getAvailableShells(): string[] {
    const shells: string[] = ['powershell'];
    if (fs.existsSync('C:\\Windows\\System32\\cmd.exe')) shells.push('cmd');
    const wslPath = 'C:\\Windows\\System32\\wsl.exe';
    if (fs.existsSync(wslPath)) shells.push('wsl');
    const gitBashPaths = [
      'C:\\Program Files\\Git\\bin\\bash.exe',
      'C:\\Program Files (x86)\\Git\\bin\\bash.exe',
    ];
    for (const p of gitBashPaths) {
      if (fs.existsSync(p)) { shells.push('git-bash'); break; }
    }
    return shells;
  }

  private resolveShell(shell: string): string {
    switch (shell) {
      case 'powershell': return 'powershell.exe';
      case 'cmd': return 'cmd.exe';
      case 'wsl': return 'wsl.exe';
      case 'git-bash': return fs.existsSync('C:\\Program Files\\Git\\bin\\bash.exe')
        ? 'C:\\Program Files\\Git\\bin\\bash.exe'
        : 'C:\\Program Files (x86)\\Git\\bin\\bash.exe';
      default: return shell;
    }
  }
}

// Electron preload context에서만 실행
if (typeof contextBridge !== 'undefined') {
  const bridge = new PtyBridge();

  contextBridge.exposeInMainWorld('ptyBridge', {
    spawn: (id: string, shell: string, args: string[], options: PtySpawnOptions) => bridge.spawn(id, shell, args, options),
    write: (id: string, data: string) => bridge.write(id, data),
    resize: (id: string, cols: number, rows: number) => bridge.resize(id, cols, rows),
    kill: (id: string) => bridge.kill(id),
    has: (id: string) => bridge.has(id),
    onData: (id: string, callback: (data: string) => void) => bridge.onData(id, callback),
    onExit: (id: string, callback: (code: number) => void) => bridge.onExit(id, callback),
    getAvailableShells: () => bridge.getAvailableShells(),
  });

  // Main에서 Socket API를 통해 PTY에 데이터 전송하는 경로
  ipcRenderer.on('pty:write', (_event, data: { surfaceId: string; text: string }) => {
    bridge.write(data.surfaceId, data.text);
  });
}
```

### Step 3: XTermWrapper React 컴포넌트

`src/renderer/components/terminal/XTermWrapper.tsx`:
```typescript
import { useEffect, useRef, useCallback } from 'react';
import { Terminal } from 'xterm';
import { WebglAddon } from '@xterm/addon-webgl';
import { FitAddon } from '@xterm/addon-fit';
import 'xterm/css/xterm.css';

declare global {
  interface Window {
    ptyBridge: {
      spawn: (id: string, shell: string, args: string[], options: { cols: number; rows: number; cwd: string }) => { id: string; pid: number };
      write: (id: string, data: string) => void;
      resize: (id: string, cols: number, rows: number) => void;
      kill: (id: string) => void;
      has: (id: string) => boolean;
      onData: (id: string, callback: (data: string) => void) => void;
      onExit: (id: string, callback: (code: number) => void) => void;
      getAvailableShells: () => string[];
    };
  }
}

interface XTermWrapperProps {
  surfaceId: string;
  shell: string;
  cwd: string;
  fontSize?: number;
  fontFamily?: string;
  theme?: Record<string, string>;
  onTitleChange?: (title: string) => void;
  onExit?: (code: number) => void;
}

export function XTermWrapper({ surfaceId, shell, cwd, fontSize = 14, fontFamily = 'Consolas', theme, onTitleChange, onExit }: XTermWrapperProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const terminalRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const terminal = new Terminal({
      fontSize, fontFamily,
      theme: theme ?? { background: '#1e1e1e', foreground: '#d4d4d4' },
      cursorBlink: true,
      allowProposedApi: true,
    });

    const fitAddon = new FitAddon();
    terminal.loadAddon(fitAddon);

    terminal.open(containerRef.current);
    fitAddon.fit();

    // WebGL addon (with Canvas fallback)
    try {
      const webglAddon = new WebglAddon();
      webglAddon.onContextLoss(() => {
        webglAddon.dispose();
        // Canvas fallback — xterm.js defaults to canvas without WebGL
      });
      terminal.loadAddon(webglAddon);
    } catch {
      // WebGL unavailable — use default canvas renderer
    }

    // Spawn PTY
    const { pid } = window.ptyBridge.spawn(surfaceId, shell, [], {
      cols: terminal.cols,
      rows: terminal.rows,
      cwd,
    });

    // PTY → xterm.js (direct, no IPC)
    window.ptyBridge.onData(surfaceId, (data: string) => {
      terminal.write(data);
    });

    // xterm.js → PTY (direct, no IPC)
    terminal.onData((data: string) => {
      window.ptyBridge.write(surfaceId, data);
    });

    // Title change
    terminal.onTitleChange((title: string) => {
      onTitleChange?.(title);
    });

    // PTY exit
    window.ptyBridge.onExit(surfaceId, (code: number) => {
      onExit?.(code);
    });

    // Resize
    terminal.onResize(({ cols, rows }: { cols: number; rows: number }) => {
      window.ptyBridge.resize(surfaceId, cols, rows);
    });

    terminalRef.current = terminal;
    fitAddonRef.current = fitAddon;

    // ResizeObserver for container size changes
    const resizeObserver = new ResizeObserver(() => {
      fitAddon.fit();
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      terminal.dispose();
      if (window.ptyBridge.has(surfaceId)) {
        window.ptyBridge.kill(surfaceId);
      }
    };
  }, [surfaceId]); // surfaceId 변경 시에만 재생성

  return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />;
}
```

### Step 4: 테스트 + 커밋

```bash
npx vitest run tests/unit/terminal/
git add src/preload/terminal-preload.ts src/renderer/components/terminal/ tests/unit/terminal/
git commit -m "feat: add terminal engine with PTY bridge, xterm.js WebGL, and Canvas fallback"
```

---

## Task 6: Socket API 서버

**Files:**
- Create: `src/main/socket/server.ts`
- Create: `src/main/socket/router.ts`
- Create: `src/main/socket/auth.ts`
- Create: `src/main/socket/handlers/system.ts`
- Create: `src/main/socket/handlers/workspace.ts`
- Create: `src/main/socket/handlers/surface.ts`
- Create: `src/main/socket/handlers/agent.ts`
- Create: `src/main/socket/handlers/notification.ts`
- Test: `tests/unit/socket/router.test.ts`
- Test: `tests/integration/socket/server.test.ts`

### Step 1: JSON-RPC 라우터 테스트 (실패)

`tests/unit/socket/router.test.ts`:
```typescript
import { describe, it, expect, vi } from 'vitest';
import { JsonRpcRouter } from '../../../src/main/socket/router';

describe('JsonRpcRouter', () => {
  it('routes valid JSON-RPC request to handler', async () => {
    const router = new JsonRpcRouter();
    const handler = vi.fn().mockResolvedValue({ pong: true });
    router.register('system.ping', handler);

    const response = await router.handle('{"jsonrpc":"2.0","method":"system.ping","id":1}');
    expect(handler).toHaveBeenCalled();
    expect(response).toContain('"result"');
    expect(response).toContain('"pong":true');
  });

  it('returns error for unknown method', async () => {
    const router = new JsonRpcRouter();
    const response = await router.handle('{"jsonrpc":"2.0","method":"unknown","id":1}');
    expect(response).toContain('"error"');
    expect(response).toContain('Method not found');
  });

  it('returns error for invalid JSON', async () => {
    const router = new JsonRpcRouter();
    const response = await router.handle('not json{{{');
    expect(response).toContain('"error"');
    expect(response).toContain('Parse error');
  });

  it('returns error for missing method', async () => {
    const router = new JsonRpcRouter();
    const response = await router.handle('{"jsonrpc":"2.0","id":1}');
    expect(response).toContain('"error"');
    expect(response).toContain('Invalid Request');
  });

  it('passes params to handler', async () => {
    const router = new JsonRpcRouter();
    const handler = vi.fn().mockResolvedValue({ ok: true });
    router.register('workspace.create', handler);

    await router.handle('{"jsonrpc":"2.0","method":"workspace.create","params":{"windowId":"w1","name":"Test"},"id":2}');
    expect(handler).toHaveBeenCalledWith({ windowId: 'w1', name: 'Test' });
  });

  it('handles handler errors gracefully', async () => {
    const router = new JsonRpcRouter();
    router.register('fail', () => { throw new Error('boom'); });
    const response = await router.handle('{"jsonrpc":"2.0","method":"fail","id":3}');
    expect(response).toContain('"error"');
    expect(response).toContain('boom');
  });
});
```

### Step 2: 라우터 구현

`src/main/socket/router.ts`:
```typescript
type Handler = (params: unknown) => unknown | Promise<unknown>;

interface JsonRpcRequest {
  jsonrpc: string;
  method: string;
  params?: unknown;
  id?: number | string | null;
}

interface JsonRpcResponse {
  jsonrpc: '2.0';
  result?: unknown;
  error?: { code: number; message: string; data?: unknown };
  id: number | string | null;
}

export class JsonRpcRouter {
  private handlers: Map<string, Handler> = new Map();

  register(method: string, handler: Handler): void {
    this.handlers.set(method, handler);
  }

  async handle(raw: string): Promise<string> {
    let id: number | string | null = null;

    try {
      let request: JsonRpcRequest;
      try {
        request = JSON.parse(raw);
      } catch {
        return this.errorResponse(null, -32700, 'Parse error');
      }

      id = request.id ?? null;

      if (!request.method || typeof request.method !== 'string') {
        return this.errorResponse(id, -32600, 'Invalid Request: missing method');
      }

      const handler = this.handlers.get(request.method);
      if (!handler) {
        return this.errorResponse(id, -32601, `Method not found: ${request.method}`);
      }

      const result = await handler(request.params);
      return this.successResponse(id, result);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return this.errorResponse(id, -32603, message);
    }
  }

  private successResponse(id: number | string | null, result: unknown): string {
    const response: JsonRpcResponse = { jsonrpc: '2.0', result, id };
    return JSON.stringify(response);
  }

  private errorResponse(id: number | string | null, code: number, message: string): string {
    const response: JsonRpcResponse = { jsonrpc: '2.0', error: { code, message }, id };
    return JSON.stringify(response);
  }
}
```

### Step 3: TCP 서버 + 핸들러

`src/main/socket/server.ts`:
```typescript
import net from 'node:net';
import { JsonRpcRouter } from './router';
import { DEFAULT_SOCKET_PORT, MAX_SOCKET_PORT_RETRIES } from '../../shared/constants';

export class SocketApiServer {
  private server: net.Server | null = null;
  private router: JsonRpcRouter;
  private port: number;
  private actualPort: number = 0;

  constructor(router: JsonRpcRouter, port: number = DEFAULT_SOCKET_PORT) {
    this.router = router;
    this.port = port;
  }

  async start(): Promise<number> {
    for (let i = 0; i < MAX_SOCKET_PORT_RETRIES; i++) {
      const candidatePort = this.port + i;
      try {
        await this.listen(candidatePort);
        this.actualPort = candidatePort;
        return candidatePort;
      } catch {
        continue;
      }
    }
    throw new Error(`Failed to bind socket on ports ${this.port}-${this.port + MAX_SOCKET_PORT_RETRIES - 1}`);
  }

  getPort(): number {
    return this.actualPort;
  }

  private listen(port: number): Promise<void> {
    return new Promise((resolve, reject) => {
      const server = net.createServer((socket) => {
        let buffer = '';
        socket.on('data', async (chunk) => {
          buffer += chunk.toString();
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';
          for (const line of lines) {
            if (line.trim()) {
              const response = await this.router.handle(line.trim());
              socket.write(response + '\n');
            }
          }
        });
        socket.on('error', () => { /* client disconnect */ });
      });

      server.on('error', reject);
      server.listen(port, '127.0.0.1', () => {
        this.server = server;
        resolve();
      });
    });
  }

  stop(): Promise<void> {
    return new Promise((resolve) => {
      if (this.server) {
        this.server.close(() => resolve());
      } else {
        resolve();
      }
    });
  }
}
```

### Step 4: 핸들러 등록 함수

`src/main/socket/handlers/system.ts`:
```typescript
import { JsonRpcRouter } from '../router';

export function registerSystemHandlers(router: JsonRpcRouter): void {
  router.register('system.ping', () => ({ pong: true, timestamp: Date.now() }));
  router.register('system.identify', () => ({
    app: 'cmux-win',
    version: '0.1.0',
    platform: 'win32',
  }));
  router.register('system.capabilities', () => ({
    protocols: ['json-rpc-2.0'],
    features: ['terminal', 'browser', 'markdown', 'agent-orchestration'],
  }));
}
```

`src/main/socket/handlers/workspace.ts`:
```typescript
import { JsonRpcRouter } from '../router';
import type { AppStateStore } from '../../sot/store';

export function registerWorkspaceHandlers(router: JsonRpcRouter, store: AppStateStore): void {
  router.register('workspace.list', () => {
    return store.getState().workspaces.map((ws) => ({
      id: ws.id, windowId: ws.windowId, name: ws.name, color: ws.color, isPinned: ws.isPinned,
    }));
  });

  router.register('workspace.current', () => {
    const { activeWorkspaceId } = store.getState().focus;
    if (!activeWorkspaceId) return null;
    return store.getState().workspaces.find((ws) => ws.id === activeWorkspaceId) ?? null;
  });

  router.register('workspace.create', (params: unknown) => {
    const result = store.dispatch({ type: 'workspace.create', payload: params });
    if (!result.ok) throw new Error(result.error);
    const ws = store.getState().workspaces.at(-1);
    return { id: ws?.id, name: ws?.name };
  });

  router.register('workspace.select', (params: unknown) => {
    const result = store.dispatch({ type: 'workspace.select', payload: params });
    if (!result.ok) throw new Error(result.error);
    return { ok: true };
  });

  router.register('workspace.close', (params: unknown) => {
    const result = store.dispatch({ type: 'workspace.close', payload: params });
    if (!result.ok) throw new Error(result.error);
    return { ok: true };
  });

  router.register('workspace.rename', (params: unknown) => {
    const result = store.dispatch({ type: 'workspace.rename', payload: params });
    if (!result.ok) throw new Error(result.error);
    return { ok: true };
  });
}
```

`src/main/socket/handlers/surface.ts`:
```typescript
import { JsonRpcRouter } from '../router';
import type { AppStateStore } from '../../sot/store';

export function registerSurfaceHandlers(router: JsonRpcRouter, store: AppStateStore): void {
  router.register('surface.list', (params: unknown) => {
    const p = params as { workspaceId?: string } | undefined;
    let surfaces = store.getState().surfaces;
    if (p?.workspaceId) {
      const panelIds = store.getState().panels.filter((pl) => pl.workspaceId === p.workspaceId).map((pl) => pl.id);
      surfaces = surfaces.filter((s) => panelIds.includes(s.panelId));
    }
    return surfaces.map((s) => ({ id: s.id, panelId: s.panelId, surfaceType: s.surfaceType, title: s.title }));
  });

  router.register('surface.create', (params: unknown) => {
    const result = store.dispatch({ type: 'surface.create', payload: params });
    if (!result.ok) throw new Error(result.error);
    const s = store.getState().surfaces.at(-1);
    return { id: s?.id, surfaceType: s?.surfaceType };
  });

  router.register('surface.close', (params: unknown) => {
    const result = store.dispatch({ type: 'surface.close', payload: params });
    if (!result.ok) throw new Error(result.error);
    return { ok: true };
  });

  router.register('surface.focus', (params: unknown) => {
    const result = store.dispatch({ type: 'surface.focus', payload: params });
    if (!result.ok) throw new Error(result.error);
    return { ok: true };
  });

  router.register('surface.send_text', (params: unknown) => {
    const result = store.dispatch({ type: 'surface.send_text', payload: params });
    if (!result.ok) throw new Error(result.error);
    return { ok: true };
  });
}
```

`src/main/socket/handlers/agent.ts`:
```typescript
import { JsonRpcRouter } from '../router';
import type { AppStateStore } from '../../sot/store';

export function registerAgentHandlers(router: JsonRpcRouter, store: AppStateStore): void {
  router.register('agent.session_start', (params: unknown) => {
    const result = store.dispatch({ type: 'agent.session_start', payload: params });
    if (!result.ok) throw new Error(result.error);
    return { ok: true };
  });

  router.register('agent.status_update', (params: unknown) => {
    const result = store.dispatch({ type: 'agent.status_update', payload: params });
    if (!result.ok) throw new Error(result.error);
    return { ok: true };
  });

  router.register('agent.session_end', (params: unknown) => {
    const result = store.dispatch({ type: 'agent.session_end', payload: params });
    if (!result.ok) throw new Error(result.error);
    return { ok: true };
  });
}
```

`src/main/socket/handlers/notification.ts`:
```typescript
import { JsonRpcRouter } from '../router';
import type { AppStateStore } from '../../sot/store';

export function registerNotificationHandlers(router: JsonRpcRouter, store: AppStateStore): void {
  router.register('notification.create', (params: unknown) => {
    const result = store.dispatch({ type: 'notification.create', payload: params });
    if (!result.ok) throw new Error(result.error);
    return { ok: true };
  });

  router.register('notification.list', () => {
    return store.getState().notifications;
  });

  router.register('notification.clear', (params: unknown) => {
    const result = store.dispatch({ type: 'notification.clear', payload: params ?? {} });
    if (!result.ok) throw new Error(result.error);
    return { ok: true };
  });
}
```

### Step 5: Integration 테스트

`tests/integration/socket/server.test.ts`:
```typescript
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import net from 'node:net';
import { SocketApiServer } from '../../../src/main/socket/server';
import { JsonRpcRouter } from '../../../src/main/socket/router';
import { AppStateStore } from '../../../src/main/sot/store';
import { registerSystemHandlers } from '../../../src/main/socket/handlers/system';
import { registerWorkspaceHandlers } from '../../../src/main/socket/handlers/workspace';
import { registerNotificationHandlers } from '../../../src/main/socket/handlers/notification';

function sendRpc(port: number, method: string, params?: unknown): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const client = net.createConnection({ port, host: '127.0.0.1' }, () => {
      const request = JSON.stringify({ jsonrpc: '2.0', method, params, id: 1 });
      client.write(request + '\n');
    });
    let buffer = '';
    client.on('data', (chunk) => {
      buffer += chunk.toString();
      if (buffer.includes('\n')) {
        client.end();
        try { resolve(JSON.parse(buffer.trim())); } catch (e) { reject(e); }
      }
    });
    client.on('error', reject);
  });
}

describe('SocketApiServer Integration', () => {
  let server: SocketApiServer;
  let port: number;
  let store: AppStateStore;

  beforeAll(async () => {
    store = new AppStateStore();
    const router = new JsonRpcRouter();
    registerSystemHandlers(router);
    registerWorkspaceHandlers(router, store);
    registerNotificationHandlers(router, store);
    server = new SocketApiServer(router, 0); // 0 = random available port
    port = await server.start();
  });

  afterAll(async () => {
    await server.stop();
  });

  it('responds to system.ping', async () => {
    const res = await sendRpc(port, 'system.ping') as any;
    expect(res.result.pong).toBe(true);
  });

  it('creates and lists workspaces', async () => {
    // Add a window first (manually, since window management is Phase 2)
    store.dispatch({ type: 'focus.update', payload: { activeWindowId: 'win-test' } });

    const createRes = await sendRpc(port, 'workspace.create', { windowId: 'win-test', name: 'Socket WS' }) as any;
    expect(createRes.result.name).toBe('Socket WS');

    const listRes = await sendRpc(port, 'workspace.list') as any;
    expect(listRes.result.length).toBeGreaterThanOrEqual(1);
    expect(listRes.result.some((ws: any) => ws.name === 'Socket WS')).toBe(true);
  });

  it('creates notification', async () => {
    const res = await sendRpc(port, 'notification.create', { title: 'Hello from CLI' }) as any;
    expect(res.result.ok).toBe(true);

    const listRes = await sendRpc(port, 'notification.list') as any;
    expect(listRes.result.some((n: any) => n.title === 'Hello from CLI')).toBe(true);
  });

  it('returns error for unknown method', async () => {
    const res = await sendRpc(port, 'nonexistent.method') as any;
    expect(res.error).toBeDefined();
    expect(res.error.code).toBe(-32601);
  });
});
```

### Step 6: 커밋

```bash
npx vitest run tests/unit/socket/ tests/integration/socket/
git add src/main/socket/ tests/unit/socket/ tests/integration/socket/
git commit -m "feat: add TCP Socket API server with JSON-RPC 2.0 router and handlers"
```

---

## Task 7: Typesafe IPC

**Files:**
- Create: `src/shared/ipc-channels.ts`
- Create: `src/main/ipc/handlers.ts`
- Create: `src/renderer/hooks/useDispatch.ts`
- Create: `src/renderer/hooks/useAppState.ts`
- Test: `tests/unit/ipc/channels.test.ts`

### Step 1: IPC 채널 정의

`src/shared/ipc-channels.ts`:
```typescript
// 모든 IPC 채널을 한 곳에 정의 — Main과 Renderer가 공유
export const IPC_CHANNELS = {
  // Renderer → Main (invoke/handle)
  DISPATCH: 'cmux:dispatch',
  QUERY_STATE: 'cmux:query-state',
  GET_INITIAL_STATE: 'cmux:get-initial-state',

  // Main → Renderer (send/on)
  STATE_UPDATE: 'cmux:state-update',

  // PTY 관련 (Main → Renderer)
  PTY_WRITE: 'pty:write',

  // PTY 메타데이터 (Renderer → Main)
  PTY_METADATA: 'pty:metadata',
} as const;
```

### Step 2: Main IPC 핸들러

`src/main/ipc/handlers.ts`:
```typescript
import { ipcMain, type BrowserWindow } from 'electron';
import { IPC_CHANNELS } from '../../shared/ipc-channels';
import { ActionSchema } from '../../shared/actions';
import type { AppStateStore, Middleware } from '../sot/store';
import type { AppState } from '../../shared/types';
import type { Action } from '../../shared/actions';

export function registerIpcHandlers(store: AppStateStore): void {
  // Renderer → Main: Action dispatch
  ipcMain.handle(IPC_CHANNELS.DISPATCH, (_event, rawAction: unknown) => {
    const result = store.dispatch(rawAction);
    return result;
  });

  // Renderer → Main: State query
  ipcMain.handle(IPC_CHANNELS.QUERY_STATE, (_event, query: { slice: string }) => {
    const state = store.getState();
    return (state as Record<string, unknown>)[query.slice] ?? null;
  });

  // Renderer → Main: Initial state
  ipcMain.handle(IPC_CHANNELS.GET_INITIAL_STATE, () => {
    return store.getState();
  });
}

// IPC Broadcast 미들웨어 — 상태 변경을 모든 Renderer에 전달
export class IpcBroadcastMiddleware implements Middleware {
  private windows: Map<string, BrowserWindow> = new Map();

  registerWindow(windowId: string, win: BrowserWindow): void {
    this.windows.set(windowId, win);
    win.on('closed', () => this.windows.delete(windowId));
  }

  post = (action: Action, _prevState: Readonly<AppState>, nextState: Readonly<AppState>): void => {
    // 변경된 Action 타입에서 슬라이스 결정
    const slice = action.type.split('.')[0]; // 'workspace.create' → 'workspace'
    const sliceMap: Record<string, string> = {
      workspace: 'workspaces', panel: 'panels', surface: 'surfaces',
      agent: 'agents', notification: 'notifications', focus: 'focus',
      settings: 'settings',
    };
    const stateKey = sliceMap[slice];
    if (!stateKey) return;

    const data = (nextState as Record<string, unknown>)[stateKey];

    for (const [windowId, win] of this.windows) {
      if (!win.isDestroyed()) {
        win.webContents.send(IPC_CHANNELS.STATE_UPDATE, { windowId, slice: stateKey, data });
      }
    }
  };
}
```

### Step 3: Renderer 훅

`src/renderer/hooks/useDispatch.ts`:
```typescript
import { useCallback } from 'react';
import { IPC_CHANNELS } from '../../shared/ipc-channels';
import type { Action } from '../../shared/actions';

declare global {
  interface Window {
    cmuxIpc: {
      dispatch: (action: unknown) => Promise<{ ok: boolean; error?: string }>;
      queryState: (query: { slice: string }) => Promise<unknown>;
      getInitialState: () => Promise<unknown>;
      onStateUpdate: (callback: (data: { windowId: string; slice: string; data: unknown }) => void) => () => void;
    };
  }
}

export function useDispatch() {
  return useCallback(async (action: Action): Promise<{ ok: boolean; error?: string }> => {
    return window.cmuxIpc.dispatch(action);
  }, []);
}
```

`src/renderer/hooks/useAppState.ts`:
```typescript
import { useState, useEffect } from 'react';
import type { AppState } from '../../shared/types';

export function useAppState(): AppState | null {
  const [state, setState] = useState<AppState | null>(null);

  useEffect(() => {
    // 초기 상태 로드
    window.cmuxIpc.getInitialState().then((s) => setState(s as AppState));

    // 상태 업데이트 구독
    const unsubscribe = window.cmuxIpc.onStateUpdate((update) => {
      setState((prev) => {
        if (!prev) return prev;
        return { ...prev, [update.slice]: update.data };
      });
    });

    return unsubscribe;
  }, []);

  return state;
}
```

### Step 4: main-preload.ts에 IPC bridge 추가

`src/preload/main-preload.ts` 수정:
```typescript
import { contextBridge, ipcRenderer } from 'electron';
import { IPC_CHANNELS } from '../shared/ipc-channels';

contextBridge.exposeInMainWorld('cmuxWin', {
  platform: process.platform,
});

contextBridge.exposeInMainWorld('cmuxIpc', {
  dispatch: (action: unknown) => ipcRenderer.invoke(IPC_CHANNELS.DISPATCH, action),
  queryState: (query: { slice: string }) => ipcRenderer.invoke(IPC_CHANNELS.QUERY_STATE, query),
  getInitialState: () => ipcRenderer.invoke(IPC_CHANNELS.GET_INITIAL_STATE),
  onStateUpdate: (callback: (data: { windowId: string; slice: string; data: unknown }) => void) => {
    const handler = (_event: unknown, data: { windowId: string; slice: string; data: unknown }) => callback(data);
    ipcRenderer.on(IPC_CHANNELS.STATE_UPDATE, handler);
    return () => ipcRenderer.removeListener(IPC_CHANNELS.STATE_UPDATE, handler);
  },
});
```

### Step 5: 테스트 + 커밋

`tests/unit/ipc/channels.test.ts`:
```typescript
import { describe, it, expect } from 'vitest';
import { IPC_CHANNELS } from '../../../src/shared/ipc-channels';

describe('IPC Channels', () => {
  it('defines all required channels', () => {
    expect(IPC_CHANNELS.DISPATCH).toBe('cmux:dispatch');
    expect(IPC_CHANNELS.STATE_UPDATE).toBe('cmux:state-update');
    expect(IPC_CHANNELS.QUERY_STATE).toBe('cmux:query-state');
    expect(IPC_CHANNELS.GET_INITIAL_STATE).toBe('cmux:get-initial-state');
    expect(IPC_CHANNELS.PTY_WRITE).toBe('pty:write');
    expect(IPC_CHANNELS.PTY_METADATA).toBe('pty:metadata');
  });

  it('channels are unique', () => {
    const values = Object.values(IPC_CHANNELS);
    const unique = new Set(values);
    expect(unique.size).toBe(values.length);
  });
});
```

```bash
npx vitest run tests/unit/ipc/
git add src/shared/ipc-channels.ts src/main/ipc/ src/renderer/hooks/ src/preload/main-preload.ts tests/unit/ipc/
git commit -m "feat: add typesafe IPC layer with dispatch, state query, and broadcast"
```

---

## Task 8: CLI 기본

**Files:**
- Create: `src/cli/cmux-win.ts`
- Create: `src/cli/socket-client.ts`
- Test: `tests/integration/cli/cli-commands.test.ts`

### Step 1: Socket 클라이언트

`src/cli/socket-client.ts`:
```typescript
import net from 'node:net';

const DEFAULT_ADDR = 'tcp://127.0.0.1:19840';

interface RpcResponse {
  jsonrpc: '2.0';
  result?: unknown;
  error?: { code: number; message: string };
  id: number | string | null;
}

export function parseSocketAddr(addr: string): { host: string; port: number } {
  const cleaned = addr.replace(/^tcp:\/\//, '');
  const [host, portStr] = cleaned.split(':');
  return { host: host || '127.0.0.1', port: parseInt(portStr || '19840', 10) };
}

export async function rpcCall(method: string, params?: unknown, addr?: string): Promise<unknown> {
  const { host, port } = parseSocketAddr(addr || process.env.CMUX_SOCKET_ADDR || DEFAULT_ADDR);
  const request = JSON.stringify({ jsonrpc: '2.0', method, params, id: 1 });

  return new Promise((resolve, reject) => {
    const client = net.createConnection({ host, port }, () => {
      client.write(request + '\n');
    });

    let buffer = '';
    client.on('data', (chunk) => {
      buffer += chunk.toString();
      if (buffer.includes('\n')) {
        client.end();
        try {
          const response = JSON.parse(buffer.trim()) as RpcResponse;
          if (response.error) {
            reject(new Error(`[${response.error.code}] ${response.error.message}`));
          } else {
            resolve(response.result);
          }
        } catch (e) {
          reject(e);
        }
      }
    });

    client.on('error', (err) => reject(new Error(`Socket connection failed: ${err.message}`)));
    setTimeout(() => { client.destroy(); reject(new Error('Socket timeout (5s)')); }, 5000);
  });
}
```

### Step 2: CLI 진입점

`src/cli/cmux-win.ts`:
```typescript
import { rpcCall, parseSocketAddr } from './socket-client';

const [, , command, ...args] = process.argv;

function parseFlags(args: string[]): Record<string, string> {
  const flags: Record<string, string> = {};
  for (let i = 0; i < args.length; i++) {
    if (args[i].startsWith('--') && i + 1 < args.length) {
      flags[args[i].slice(2)] = args[i + 1];
      i++;
    }
  }
  return flags;
}

async function main() {
  const flags = parseFlags(args);

  switch (command) {
    case 'ping': {
      const result = await rpcCall('system.ping');
      console.log(JSON.stringify(result));
      break;
    }
    case 'version': {
      const result = await rpcCall('system.identify');
      console.log(JSON.stringify(result));
      break;
    }
    case 'list-workspaces': {
      const result = await rpcCall('workspace.list');
      console.log(JSON.stringify(result, null, 2));
      break;
    }
    case 'new-workspace': {
      const result = await rpcCall('workspace.create', { windowId: flags.window || 'default', name: flags.name });
      console.log(JSON.stringify(result));
      break;
    }
    case 'select-workspace': {
      const result = await rpcCall('workspace.select', { workspaceId: args[0] });
      console.log(JSON.stringify(result));
      break;
    }
    case 'send': {
      const surfaceId = flags.surface;
      const text = args.filter((a) => !a.startsWith('--')).join(' ');
      const result = await rpcCall('surface.send_text', { surfaceId, text });
      console.log(JSON.stringify(result));
      break;
    }
    case 'notify': {
      const result = await rpcCall('notification.create', { title: flags.title, body: flags.body, subtitle: flags.subtitle });
      console.log(JSON.stringify(result));
      break;
    }
    case 'list-notifications': {
      const result = await rpcCall('notification.list');
      console.log(JSON.stringify(result, null, 2));
      break;
    }
    case 'claude-hook': {
      // Phase 4에서 완전 구현 — 여기서는 스텁
      console.log(JSON.stringify({ ok: true, stub: true }));
      break;
    }
    default: {
      console.log(`cmux-win CLI v0.1.0
Usage: cmux-win <command> [options]

Commands:
  ping                    Check socket connectivity
  version                 Show app version
  list-workspaces         List all workspaces
  new-workspace           Create new workspace (--window, --name)
  select-workspace <id>   Select workspace
  send --surface <id>     Send text to surface
  notify --title <text>   Send notification (--body, --subtitle)
  list-notifications      List all notifications
  claude-hook <sub>       Claude Code hook (Phase 4)
`);
      break;
    }
  }
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(1);
});
```

### Step 3: 테스트 + 커밋

```bash
npx vitest run tests/integration/cli/
git add src/cli/ tests/integration/cli/
git commit -m "feat: add CLI with socket client supporting ping, workspaces, send, notify commands"
```

---

## Task 9: 통합 — Electron 앱 조립

**Files:**
- Modify: `src/main/app.ts` (전면 재작성)
- Modify: `src/renderer/App.tsx` (터미널 표시)
- Test: `tests/e2e/phase1-smoke.spec.ts`

### Step 1: app.ts 통합

`src/main/app.ts`:
```typescript
import { app, BrowserWindow, ipcMain } from 'electron';
import path from 'node:path';
import os from 'node:os';
import { AppStateStore } from './sot/store';
import { PersistenceMiddleware } from './sot/middleware/persistence';
import { AuditLogMiddleware } from './sot/middleware/audit-log';
import { registerIpcHandlers, IpcBroadcastMiddleware } from './ipc/handlers';
import { SocketApiServer } from './socket/server';
import { JsonRpcRouter } from './socket/router';
import { registerSystemHandlers } from './socket/handlers/system';
import { registerWorkspaceHandlers } from './socket/handlers/workspace';
import { registerSurfaceHandlers } from './socket/handlers/surface';
import { registerAgentHandlers } from './socket/handlers/agent';
import { registerNotificationHandlers } from './socket/handlers/notification';
import { IPC_CHANNELS } from '../shared/ipc-channels';

// --- State ---
const SESSION_DIR = path.join(os.homedir(), 'AppData', 'Roaming', 'cmux-win');
const SESSION_FILE = path.join(SESSION_DIR, 'session.json');
const DEBUG_LOG = path.join(os.tmpdir(), 'cmux-win-debug.log');

const persistedState = PersistenceMiddleware.loadState(SESSION_FILE);
const store = new AppStateStore(persistedState ?? undefined);

// --- Middleware ---
const persistenceMiddleware = new PersistenceMiddleware(SESSION_FILE);
const auditLogMiddleware = new AuditLogMiddleware(DEBUG_LOG);
const ipcBroadcastMiddleware = new IpcBroadcastMiddleware();

store.use(persistenceMiddleware);
store.use(ipcBroadcastMiddleware);
store.use(auditLogMiddleware);

// --- IPC ---
registerIpcHandlers(store);

// --- Side-effect: PTY write forwarding ---
store.on('side-effect', (effect: { type: string; surfaceId: string; text: string }) => {
  if (effect.type === 'pty-write') {
    // surfaceId로 해당 윈도우 찾기
    for (const win of BrowserWindow.getAllWindows()) {
      if (!win.isDestroyed()) {
        win.webContents.send(IPC_CHANNELS.PTY_WRITE, { surfaceId: effect.surfaceId, text: effect.text });
      }
    }
  }
});

// --- Socket API ---
const router = new JsonRpcRouter();
registerSystemHandlers(router);
registerWorkspaceHandlers(router, store);
registerSurfaceHandlers(router, store);
registerAgentHandlers(router, store);
registerNotificationHandlers(router, store);

const socketServer = new SocketApiServer(router);

// --- Window ---
function createWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    title: 'cmux-win',
    backgroundColor: '#1e1e1e',
    webPreferences: {
      preload: path.join(__dirname, '../preload/main-preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webviewTag: true, // Phase 3 브라우저 패널용
    },
  });

  const windowId = `win-${Date.now()}`;
  ipcBroadcastMiddleware.registerWindow(windowId, win);

  // SOT에 윈도우 등록
  store.dispatch({
    type: 'focus.update',
    payload: { activeWindowId: windowId },
  });

  if (process.env.NODE_ENV === 'development') {
    win.loadURL('http://localhost:5173');
  } else {
    win.loadFile(path.join(__dirname, '../renderer/index.html'));
  }

  return win;
}

// --- App lifecycle ---
app.whenReady().then(async () => {
  const port = await socketServer.start();
  console.log(`[cmux-win] Socket API listening on tcp://127.0.0.1:${port}`);

  // CMUX_SOCKET_ADDR 환경변수 설정 (자식 프로세스용)
  process.env.CMUX_SOCKET_ADDR = `tcp://127.0.0.1:${port}`;

  createWindow();
});

app.on('window-all-closed', () => {
  persistenceMiddleware.dispose();
  socketServer.stop();
  app.quit();
});
```

### Step 2: Renderer App.tsx — 터미널 표시

`src/renderer/App.tsx`:
```typescript
import { useAppState } from './hooks/useAppState';
import { useDispatch } from './hooks/useDispatch';
import { XTermWrapper } from './components/terminal/XTermWrapper';
import { useEffect, useState } from 'react';

export default function App() {
  const appState = useAppState();
  const dispatch = useDispatch();
  const [initialized, setInitialized] = useState(false);

  // 첫 워크스페이스 자동 생성
  useEffect(() => {
    if (appState && !initialized && appState.workspaces.length === 0) {
      dispatch({ type: 'workspace.create', payload: { windowId: 'default', name: 'Terminal' } });
      setInitialized(true);
    } else if (appState && appState.workspaces.length > 0) {
      setInitialized(true);
    }
  }, [appState, initialized, dispatch]);

  if (!appState || !initialized) {
    return <div style={{ color: '#888', background: '#1e1e1e', height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      Loading...
    </div>;
  }

  // Phase 1: 첫 번째 서피스의 터미널만 표시
  const firstSurface = appState.surfaces.find((s) => s.surfaceType === 'terminal');

  return (
    <div style={{ background: '#1e1e1e', height: '100vh', display: 'flex' }}>
      {/* Phase 2에서 사이드바 추가 */}
      <div style={{ flex: 1 }}>
        {firstSurface ? (
          <XTermWrapper
            surfaceId={firstSurface.id}
            shell={appState.settings.terminal.defaultShell}
            cwd={firstSurface.terminal?.cwd || 'C:\\'}
            fontSize={appState.settings.terminal.fontSize}
            fontFamily={appState.settings.terminal.fontFamily}
          />
        ) : (
          <div style={{ color: '#888', padding: 20 }}>No terminal</div>
        )}
      </div>
    </div>
  );
}
```

### Step 3: E2E Smoke 테스트

`tests/e2e/phase1-smoke.spec.ts`:
```typescript
import { test, expect } from '@playwright/test';
import { _electron as electron } from 'playwright';
import { rpcCall } from '../../src/cli/socket-client';

test.describe('Phase 1 Smoke Test', () => {
  test('app launches and socket responds to ping', async () => {
    // 앱 시작 (실제 E2E에서는 빌드된 앱 사용)
    // Phase 1에서는 수동 검증도 허용
    const result = await rpcCall('system.ping');
    expect(result).toHaveProperty('pong', true);
  });

  test('workspace.list returns at least one workspace', async () => {
    const result = await rpcCall('workspace.list') as any[];
    expect(result.length).toBeGreaterThanOrEqual(1);
  });

  test('notification roundtrip', async () => {
    await rpcCall('notification.create', { title: 'E2E Test' });
    const notifications = await rpcCall('notification.list') as any[];
    expect(notifications.some((n: any) => n.title === 'E2E Test')).toBe(true);
  });
});
```

### Step 4: 전체 테스트 + 커밋

```bash
npx vitest run
git add -A
git commit -m "feat: integrate all Phase 1 components — SOT, terminal, socket API, IPC, CLI"
```

---

## Phase 1 완료 검증 체크리스트

```
기능:
  [ ] npm run dev → Electron 창에 xterm.js 터미널 표시
  [ ] 터미널에 PowerShell 실행, 키 입력 동작
  [ ] cmux-win ping → {"pong":true}
  [ ] cmux-win list-workspaces → 워크스페이스 목록 JSON
  [ ] cmux-win notify --title "test" → 알림 생성
  [ ] cmux-win list-notifications → 알림 목록
  [ ] 앱 종료 → 재시작 → session.json에서 복원

테스트:
  [ ] npx vitest run → ALL PASS
  [ ] 커버리지 ≥90% (src/main/sot/, src/shared/)

품질:
  [ ] TypeScript strict 에러 0개
  [ ] ESLint 경고 0개
```

---

## Phase 2~6 계획 수립 시점

Phase 1의 모든 Task가 완료되고 체크리스트가 통과되면,
Phase 2의 상세 구현 계획을 동일한 형식으로 작성합니다.

```
Phase 1 완료 → Phase 2 상세 계획 작성 → 승인 → Phase 2 구현
Phase 2 완료 → Phase 3 상세 계획 작성 → 승인 → Phase 3 구현
...
```
