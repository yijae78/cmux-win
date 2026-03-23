# cmux-win Phase 1: Foundation — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Electron 앱이 터미널을 띄우고, SOT로 상태를 관리하며, TCP Socket으로 외부 제어가 가능한 최소 동작 상태를 구축한다.

**Architecture:** Electron 33 Main Process에 EventEmitter + Immer 기반 SOT 스토어를 두고, Renderer에서 React 18.3 + xterm.js로 터미널을 렌더링한다. node-pty는 preload에서 직접 실행하여 IPC 없이 키 입력 지연을 최소화한다. TCP localhost:19840에서 JSON-RPC v2 Socket API를 노출한다.

**Tech Stack:** Electron 33, TypeScript 5.4+ (strict), React 18.3, xterm.js 5.x, node-pty 1.x, Immer, Zod, Vitest, electron-vite

**Design Doc:** `docs/plans/2026-03-19-cmux-win-design-v3.md`

---

## 의존성 그래프

```
Task 1 (프로젝트 초기화)
  │
  ├─→ Task 2 (shared 타입 + Zod 스키마)
  │     │
  │     ├─→ Task 3 (SOT 스토어)
  │     │     │
  │     │     ├─→ Task 4 (SOT 미들웨어)
  │     │     │     │
  │     │     │     └─→ Task 7 (Typesafe IPC)
  │     │     │           │
  │     │     │           └─→ Task 9 (통합: Electron 앱 조립)
  │     │     │
  │     │     └─→ Task 5 (터미널 엔진)
  │     │           │
  │     │           └─→ Task 9
  │     │
  │     └─→ Task 6 (Socket API 서버)
  │           │
  │           └─→ Task 8 (CLI 기본)
  │                 │
  │                 └─→ Task 9
  │
  └─→ Task 9 (통합 + E2E 검증)
```

병렬 가능: Task 3/5/6은 Task 2 완료 후 동시 진행 가능.

---

## Task 1: 프로젝트 초기화

**Files:**
- Create: `package.json`
- Create: `tsconfig.json`, `tsconfig.main.json`, `tsconfig.renderer.json`, `tsconfig.preload.json`
- Create: `electron-vite.config.ts`
- Create: `vitest.config.ts`
- Create: `.eslintrc.cjs`
- Create: `.prettierrc`
- Create: `.husky/pre-commit`
- Create: `commitlint.config.ts`
- Create: `src/main/app.ts`
- Create: `src/renderer/App.tsx`
- Create: `src/renderer/index.html`
- Create: `src/preload/main-preload.ts`

**Step 1: 프로젝트 디렉토리 생성 및 npm init**

```bash
cd C:/Users/yijae/Desktop/cmux-win
npm init -y
```

**Step 2: 핵심 의존성 설치**

```bash
npm install electron@33 react@18.3 react-dom@18.3 immer zod
npm install -D typescript@5.4 electron-vite vite @vitejs/plugin-react vitest eslint prettier husky lint-staged @commitlint/cli @commitlint/config-conventional @types/react @types/react-dom
```

**Step 3: TypeScript 설정 파일 생성**

`tsconfig.json`:
```json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "strictFunctionTypes": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "isolatedModules": true
  },
  "references": [
    { "path": "./tsconfig.main.json" },
    { "path": "./tsconfig.renderer.json" },
    { "path": "./tsconfig.preload.json" }
  ]
}
```

`tsconfig.main.json`:
```json
{
  "extends": "./tsconfig.json",
  "compilerOptions": {
    "module": "ESNext",
    "moduleResolution": "bundler",
    "target": "ESNext",
    "outDir": "dist/main",
    "rootDir": "src",
    "lib": ["ESNext"]
  },
  "include": ["src/main/**/*", "src/shared/**/*"]
}
```

`tsconfig.renderer.json`:
```json
{
  "extends": "./tsconfig.json",
  "compilerOptions": {
    "module": "ESNext",
    "moduleResolution": "bundler",
    "target": "ESNext",
    "outDir": "dist/renderer",
    "rootDir": "src",
    "lib": ["ESNext", "DOM", "DOM.Iterable"],
    "jsx": "react-jsx"
  },
  "include": ["src/renderer/**/*", "src/shared/**/*"]
}
```

`tsconfig.preload.json`:
```json
{
  "extends": "./tsconfig.json",
  "compilerOptions": {
    "module": "ESNext",
    "moduleResolution": "bundler",
    "target": "ESNext",
    "outDir": "dist/preload",
    "rootDir": "src",
    "lib": ["ESNext", "DOM"]
  },
  "include": ["src/preload/**/*", "src/shared/**/*"]
}
```

**Step 4: electron-vite 설정**

`electron-vite.config.ts`:
```typescript
import { defineConfig } from 'electron-vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  main: {
    build: {
      outDir: 'dist/main',
      rollupOptions: {
        external: ['electron', 'node-pty'],
      },
    },
  },
  preload: {
    build: {
      outDir: 'dist/preload',
      rollupOptions: {
        external: ['electron', 'node-pty'],
      },
    },
  },
  renderer: {
    plugins: [react()],
    build: {
      outDir: 'dist/renderer',
    },
  },
});
```

**Step 5: Vitest 설정**

`vitest.config.ts`:
```typescript
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    include: ['tests/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/**/*.ts'],
      exclude: ['src/renderer/**', 'src/preload/**'],
    },
  },
});
```

**Step 6: ESLint + Prettier + Husky 설정**

`.eslintrc.cjs`:
```javascript
module.exports = {
  root: true,
  parser: '@typescript-eslint/parser',
  plugins: ['@typescript-eslint'],
  extends: ['eslint:recommended', 'plugin:@typescript-eslint/strict-type-checked'],
  parserOptions: { project: ['./tsconfig.main.json', './tsconfig.renderer.json', './tsconfig.preload.json'] },
  rules: {
    '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    'no-console': ['warn', { allow: ['warn', 'error'] }],
  },
};
```

`.prettierrc`:
```json
{
  "singleQuote": true,
  "trailingComma": "all",
  "printWidth": 100,
  "tabWidth": 2
}
```

```bash
npx husky init
echo "npx lint-staged" > .husky/pre-commit
```

`commitlint.config.ts`:
```typescript
export default { extends: ['@commitlint/config-conventional'] };
```

`package.json`에 추가:
```json
{
  "lint-staged": {
    "*.ts": ["eslint --fix", "prettier --write"],
    "*.tsx": ["eslint --fix", "prettier --write"]
  },
  "scripts": {
    "dev": "electron-vite dev",
    "build": "electron-vite build",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage",
    "lint": "eslint src/",
    "format": "prettier --write src/"
  }
}
```

**Step 7: 최소 Electron 진입점 생성**

`src/main/app.ts`:
```typescript
import { app, BrowserWindow } from 'electron';
import path from 'node:path';

function createWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, '../preload/main-preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (process.env.NODE_ENV === 'development') {
    win.loadURL('http://localhost:5173');
  } else {
    win.loadFile(path.join(__dirname, '../renderer/index.html'));
  }

  return win;
}

app.whenReady().then(() => {
  createWindow();
});

app.on('window-all-closed', () => {
  app.quit();
});
```

`src/preload/main-preload.ts`:
```typescript
import { contextBridge } from 'electron';

contextBridge.exposeInMainWorld('cmuxWin', {
  platform: process.platform,
});
```

`src/renderer/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>cmux-win</title>
</head>
<body>
  <div id="root"></div>
  <script type="module" src="./main.tsx"></script>
</body>
</html>
```

`src/renderer/main.tsx`:
```typescript
import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';

const root = createRoot(document.getElementById('root')!);
root.render(<App />);
```

`src/renderer/App.tsx`:
```typescript
export default function App() {
  return <div style={{ color: '#fff', background: '#1e1e1e', height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
    <h1>cmux-win</h1>
  </div>;
}
```

**Step 8: 빌드 + 실행 검증**

```bash
npm run dev
```
Expected: Electron 창에 "cmux-win" 텍스트가 표시됨

**Step 9: 첫 커밋**

```bash
git init
echo "node_modules/\ndist/\ncoverage/\n.env" > .gitignore
git add -A
git commit -m "feat: initialize cmux-win Electron project with TypeScript strict, React 18.3, Vitest, ESLint, Prettier, Husky"
```

---

## Task 2: Shared 타입 + Zod 스키마

**Files:**
- Create: `src/shared/types.ts`
- Create: `src/shared/schemas.ts`
- Create: `src/shared/actions.ts`
- Create: `src/shared/constants.ts`
- Test: `tests/unit/shared/schemas.test.ts`
- Test: `tests/unit/shared/actions.test.ts`

**Step 1: 타입 테스트 작성 (실패)**

`tests/unit/shared/schemas.test.ts`:
```typescript
import { describe, it, expect } from 'vitest';
import { WindowStateSchema, WorkspaceStateSchema, PanelStateSchema, SurfaceStateSchema, AppStateSchema, SettingsStateSchema } from '../../../src/shared/schemas';

describe('Zod Schemas', () => {
  it('validates a valid WindowState', () => {
    const valid = { id: 'win-1', workspaceIds: ['ws-1'], geometry: { x: 0, y: 0, width: 1200, height: 800 }, isActive: true };
    expect(WindowStateSchema.safeParse(valid).success).toBe(true);
  });

  it('rejects WindowState with missing id', () => {
    const invalid = { workspaceIds: [], geometry: { x: 0, y: 0, width: 100, height: 100 }, isActive: false };
    expect(WindowStateSchema.safeParse(invalid).success).toBe(false);
  });

  it('validates a valid WorkspaceState', () => {
    const valid = {
      id: 'ws-1', windowId: 'win-1', name: 'My Workspace', panelLayout: { type: 'leaf' as const, panelId: 'p-1' },
      agentPids: {}, statusEntries: [], unreadCount: 0, isPinned: false,
    };
    expect(WorkspaceStateSchema.safeParse(valid).success).toBe(true);
  });

  it('validates a valid PanelState', () => {
    const valid = { id: 'p-1', workspaceId: 'ws-1', panelType: 'terminal' as const, surfaceIds: ['s-1'], activeSurfaceId: 's-1', isZoomed: false };
    expect(PanelStateSchema.safeParse(valid).success).toBe(true);
  });

  it('rejects PanelState with invalid panelType', () => {
    const invalid = { id: 'p-1', workspaceId: 'ws-1', panelType: 'invalid', surfaceIds: [], activeSurfaceId: '', isZoomed: false };
    expect(PanelStateSchema.safeParse(invalid).success).toBe(false);
  });

  it('validates a valid SurfaceState with terminal data', () => {
    const valid = { id: 's-1', panelId: 'p-1', surfaceType: 'terminal' as const, title: 'PowerShell', terminal: { pid: 1234, cwd: 'C:\\Users', shell: 'powershell' } };
    expect(SurfaceStateSchema.safeParse(valid).success).toBe(true);
  });

  it('validates SettingsState defaults', () => {
    const valid = {
      appearance: { theme: 'system' as const, language: 'system' as const, iconMode: 'auto' as const },
      terminal: { defaultShell: 'powershell' as const, fontSize: 14, fontFamily: 'Consolas', themeName: 'Dracula', cursorStyle: 'block' as const },
      browser: { searchEngine: 'google' as const, searchSuggestions: true, httpAllowlist: [], externalUrlPatterns: [] },
      socket: { mode: 'automation' as const, port: 19840 },
      agents: { claudeHooksEnabled: true, codexHooksEnabled: true, geminiHooksEnabled: true, orchestrationMode: 'auto' as const },
      telemetry: { enabled: true },
      updates: { autoCheck: true, channel: 'stable' as const },
      accessibility: { screenReaderMode: false, reducedMotion: false },
    };
    expect(SettingsStateSchema.safeParse(valid).success).toBe(true);
  });
});
```

**Step 2: 테스트 실행, 실패 확인**

```bash
npx vitest run tests/unit/shared/schemas.test.ts
```
Expected: FAIL — 모듈 없음

**Step 3: shared/types.ts 구현**

설계안 v3 섹션 7.1의 타입 정의를 그대로 구현. (설계 문서 참조 — 여기서는 생략하지 않고 전체 작성)

`src/shared/types.ts`:
```typescript
export interface PersistedState {
  version: number;
  state: AppState;
}

export interface AppState {
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

export interface WindowState {
  id: string;
  workspaceIds: string[];
  geometry: { x: number; y: number; width: number; height: number };
  isActive: boolean;
}

export interface WorkspaceState {
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

export type PanelLayoutTree =
  | { type: 'leaf'; panelId: string }
  | { type: 'split'; direction: 'horizontal' | 'vertical'; ratio: number; children: [PanelLayoutTree, PanelLayoutTree] };

export interface PanelState {
  id: string;
  workspaceId: string;
  panelType: 'terminal' | 'browser' | 'markdown';
  surfaceIds: string[];
  activeSurfaceId: string;
  isZoomed: boolean;
}

export interface SurfaceState {
  id: string;
  panelId: string;
  surfaceType: 'terminal' | 'browser' | 'markdown';
  title: string;
  terminal?: { pid: number; cwd: string; shell: string };
  browser?: { url: string; profileId: string; isLoading: boolean };
  markdown?: { filePath: string };
}

export interface AgentSessionState {
  sessionId: string;
  agentType: 'claude' | 'codex' | 'gemini' | 'opencode';
  workspaceId: string;
  surfaceId: string;
  status: 'running' | 'idle' | 'needs_input';
  statusIcon: string;
  statusColor: string;
  pid?: number;
  lastActivity: number;
}

export interface NotificationState {
  id: string;
  workspaceId?: string;
  surfaceId?: string;
  title: string;
  subtitle?: string;
  body?: string;
  createdAt: number;
  isRead: boolean;
}

export interface StatusEntry {
  key: string;
  label: string;
  icon?: string;
  color?: string;
}

export interface FocusState {
  activeWindowId: string | null;
  activeWorkspaceId: string | null;
  activePanelId: string | null;
  activeSurfaceId: string | null;
  focusTarget: 'terminal' | 'browser_webview' | 'browser_omnibar' | 'browser_find' | 'terminal_find' | null;
}

export interface SettingsState {
  appearance: { theme: 'system' | 'light' | 'dark'; language: 'system' | 'en' | 'ko' | 'ja'; iconMode: 'auto' | 'colorful' | 'monochrome' };
  terminal: { defaultShell: 'powershell' | 'cmd' | 'wsl' | 'git-bash'; fontSize: number; fontFamily: string; themeName: string; cursorStyle: 'block' | 'underline' | 'bar' };
  browser: { searchEngine: 'google' | 'duckduckgo' | 'bing' | 'kagi' | 'startpage'; searchSuggestions: boolean; httpAllowlist: string[]; externalUrlPatterns: string[] };
  socket: { mode: 'off' | 'cmux-only' | 'automation' | 'password' | 'allow-all'; port: number };
  agents: { claudeHooksEnabled: boolean; codexHooksEnabled: boolean; geminiHooksEnabled: boolean; orchestrationMode: 'auto' | 'claude-teams' | 'self-managed' };
  telemetry: { enabled: boolean };
  updates: { autoCheck: boolean; channel: 'stable' | 'nightly' };
  accessibility: { screenReaderMode: boolean; reducedMotion: boolean };
}

export interface ShortcutState {
  shortcuts: Record<string, string>;
}

export interface RemoteSessionState {
  host: string;
  port: number;
  status: 'connecting' | 'connected' | 'disconnected' | 'error';
}
```

**Step 4: shared/schemas.ts — Zod 스키마 구현**

`src/shared/schemas.ts`:
```typescript
import { z } from 'zod';

export const GeometrySchema = z.object({
  x: z.number(), y: z.number(), width: z.number().positive(), height: z.number().positive(),
});

export const WindowStateSchema = z.object({
  id: z.string().min(1),
  workspaceIds: z.array(z.string()),
  geometry: GeometrySchema,
  isActive: z.boolean(),
});

const PanelLayoutLeafSchema = z.object({ type: z.literal('leaf'), panelId: z.string() });
const PanelLayoutSplitSchema: z.ZodType<any> = z.lazy(() =>
  z.object({
    type: z.literal('split'),
    direction: z.enum(['horizontal', 'vertical']),
    ratio: z.number().min(0).max(1),
    children: z.tuple([PanelLayoutTreeSchema, PanelLayoutTreeSchema]),
  }),
);
export const PanelLayoutTreeSchema = z.union([PanelLayoutLeafSchema, PanelLayoutSplitSchema]);

export const StatusEntrySchema = z.object({
  key: z.string(), label: z.string(), icon: z.string().optional(), color: z.string().optional(),
});

export const WorkspaceStateSchema = z.object({
  id: z.string().min(1),
  windowId: z.string().min(1),
  name: z.string(),
  color: z.string().optional(),
  panelLayout: PanelLayoutTreeSchema,
  agentPids: z.record(z.string(), z.number()),
  statusEntries: z.array(StatusEntrySchema),
  unreadCount: z.number().int().min(0),
  isPinned: z.boolean(),
  remoteSession: z.object({
    host: z.string(), port: z.number(), status: z.enum(['connecting', 'connected', 'disconnected', 'error']),
  }).optional(),
});

export const PanelTypeEnum = z.enum(['terminal', 'browser', 'markdown']);

export const PanelStateSchema = z.object({
  id: z.string().min(1),
  workspaceId: z.string().min(1),
  panelType: PanelTypeEnum,
  surfaceIds: z.array(z.string()),
  activeSurfaceId: z.string(),
  isZoomed: z.boolean(),
});

export const SurfaceStateSchema = z.object({
  id: z.string().min(1),
  panelId: z.string().min(1),
  surfaceType: PanelTypeEnum,
  title: z.string(),
  terminal: z.object({ pid: z.number(), cwd: z.string(), shell: z.string() }).optional(),
  browser: z.object({ url: z.string(), profileId: z.string(), isLoading: z.boolean() }).optional(),
  markdown: z.object({ filePath: z.string() }).optional(),
});

export const AgentTypeEnum = z.enum(['claude', 'codex', 'gemini', 'opencode']);
export const AgentStatusEnum = z.enum(['running', 'idle', 'needs_input']);

export const AgentSessionStateSchema = z.object({
  sessionId: z.string().min(1),
  agentType: AgentTypeEnum,
  workspaceId: z.string(),
  surfaceId: z.string(),
  status: AgentStatusEnum,
  statusIcon: z.string(),
  statusColor: z.string(),
  pid: z.number().optional(),
  lastActivity: z.number(),
});

export const NotificationStateSchema = z.object({
  id: z.string().min(1),
  workspaceId: z.string().optional(),
  surfaceId: z.string().optional(),
  title: z.string(),
  subtitle: z.string().optional(),
  body: z.string().optional(),
  createdAt: z.number(),
  isRead: z.boolean(),
});

export const SettingsStateSchema = z.object({
  appearance: z.object({
    theme: z.enum(['system', 'light', 'dark']),
    language: z.enum(['system', 'en', 'ko', 'ja']),
    iconMode: z.enum(['auto', 'colorful', 'monochrome']),
  }),
  terminal: z.object({
    defaultShell: z.enum(['powershell', 'cmd', 'wsl', 'git-bash']),
    fontSize: z.number().int().min(6).max(72),
    fontFamily: z.string(),
    themeName: z.string(),
    cursorStyle: z.enum(['block', 'underline', 'bar']),
  }),
  browser: z.object({
    searchEngine: z.enum(['google', 'duckduckgo', 'bing', 'kagi', 'startpage']),
    searchSuggestions: z.boolean(),
    httpAllowlist: z.array(z.string()),
    externalUrlPatterns: z.array(z.string()),
  }),
  socket: z.object({
    mode: z.enum(['off', 'cmux-only', 'automation', 'password', 'allow-all']),
    port: z.number().int().min(1024).max(65535),
  }),
  agents: z.object({
    claudeHooksEnabled: z.boolean(),
    codexHooksEnabled: z.boolean(),
    geminiHooksEnabled: z.boolean(),
    orchestrationMode: z.enum(['auto', 'claude-teams', 'self-managed']),
  }),
  telemetry: z.object({ enabled: z.boolean() }),
  updates: z.object({ autoCheck: z.boolean(), channel: z.enum(['stable', 'nightly']) }),
  accessibility: z.object({ screenReaderMode: z.boolean(), reducedMotion: z.boolean() }),
});

export const FocusStateSchema = z.object({
  activeWindowId: z.string().nullable(),
  activeWorkspaceId: z.string().nullable(),
  activePanelId: z.string().nullable(),
  activeSurfaceId: z.string().nullable(),
  focusTarget: z.enum(['terminal', 'browser_webview', 'browser_omnibar', 'browser_find', 'terminal_find']).nullable(),
});

export const AppStateSchema = z.object({
  windows: z.array(WindowStateSchema),
  workspaces: z.array(WorkspaceStateSchema),
  panels: z.array(PanelStateSchema),
  surfaces: z.array(SurfaceStateSchema),
  agents: z.array(AgentSessionStateSchema),
  notifications: z.array(NotificationStateSchema),
  settings: SettingsStateSchema,
  shortcuts: z.object({ shortcuts: z.record(z.string(), z.string()) }),
  focus: FocusStateSchema,
});

export const PersistedStateSchema = z.object({
  version: z.number().int().positive(),
  state: AppStateSchema,
});
```

**Step 5: shared/actions.ts — Action 타입 + 스키마**

`src/shared/actions.ts`:
```typescript
import { z } from 'zod';
import { PanelTypeEnum } from './schemas';

// --- Action Schemas ---
export const WorkspaceCreateAction = z.object({ type: z.literal('workspace.create'), payload: z.object({ windowId: z.string(), name: z.string().optional(), cwd: z.string().optional() }) });
export const WorkspaceCloseAction = z.object({ type: z.literal('workspace.close'), payload: z.object({ workspaceId: z.string() }) });
export const WorkspaceSelectAction = z.object({ type: z.literal('workspace.select'), payload: z.object({ workspaceId: z.string() }) });
export const WorkspaceRenameAction = z.object({ type: z.literal('workspace.rename'), payload: z.object({ workspaceId: z.string(), name: z.string() }) });

export const PanelSplitAction = z.object({ type: z.literal('panel.split'), payload: z.object({ panelId: z.string(), direction: z.enum(['horizontal', 'vertical']), newPanelType: PanelTypeEnum }) });
export const PanelCloseAction = z.object({ type: z.literal('panel.close'), payload: z.object({ panelId: z.string() }) });
export const PanelFocusAction = z.object({ type: z.literal('panel.focus'), payload: z.object({ panelId: z.string() }) });
export const PanelResizeAction = z.object({ type: z.literal('panel.resize'), payload: z.object({ panelId: z.string(), ratio: z.number().min(0).max(1) }) });

export const SurfaceCreateAction = z.object({ type: z.literal('surface.create'), payload: z.object({ panelId: z.string(), surfaceType: PanelTypeEnum }) });
export const SurfaceCloseAction = z.object({ type: z.literal('surface.close'), payload: z.object({ surfaceId: z.string() }) });
export const SurfaceFocusAction = z.object({ type: z.literal('surface.focus'), payload: z.object({ surfaceId: z.string() }) });
export const SurfaceSendTextAction = z.object({ type: z.literal('surface.send_text'), payload: z.object({ surfaceId: z.string(), text: z.string() }) });

export const AgentSessionStartAction = z.object({ type: z.literal('agent.session_start'), payload: z.object({ sessionId: z.string(), agentType: z.enum(['claude', 'codex', 'gemini', 'opencode']), workspaceId: z.string(), surfaceId: z.string(), pid: z.number().optional() }) });
export const AgentStatusUpdateAction = z.object({ type: z.literal('agent.status_update'), payload: z.object({ sessionId: z.string(), status: z.enum(['running', 'idle', 'needs_input']), icon: z.string().optional(), color: z.string().optional() }) });
export const AgentSessionEndAction = z.object({ type: z.literal('agent.session_end'), payload: z.object({ sessionId: z.string() }) });

export const NotificationCreateAction = z.object({ type: z.literal('notification.create'), payload: z.object({ title: z.string(), subtitle: z.string().optional(), body: z.string().optional(), workspaceId: z.string().optional(), surfaceId: z.string().optional() }) });
export const NotificationClearAction = z.object({ type: z.literal('notification.clear'), payload: z.object({ workspaceId: z.string().optional() }) });

export const FocusUpdateAction = z.object({ type: z.literal('focus.update'), payload: z.object({ activeWindowId: z.string().nullable().optional(), activeWorkspaceId: z.string().nullable().optional(), activePanelId: z.string().nullable().optional(), activeSurfaceId: z.string().nullable().optional(), focusTarget: z.enum(['terminal', 'browser_webview', 'browser_omnibar', 'browser_find', 'terminal_find']).nullable().optional() }) });

export const SettingsUpdateAction = z.object({ type: z.literal('settings.update'), payload: z.record(z.string(), z.unknown()) });

export const ActionSchema = z.discriminatedUnion('type', [
  WorkspaceCreateAction, WorkspaceCloseAction, WorkspaceSelectAction, WorkspaceRenameAction,
  PanelSplitAction, PanelCloseAction, PanelFocusAction, PanelResizeAction,
  SurfaceCreateAction, SurfaceCloseAction, SurfaceFocusAction, SurfaceSendTextAction,
  AgentSessionStartAction, AgentStatusUpdateAction, AgentSessionEndAction,
  NotificationCreateAction, NotificationClearAction,
  FocusUpdateAction, SettingsUpdateAction,
]);

export type Action = z.infer<typeof ActionSchema>;
```

**Step 6: shared/constants.ts**

`src/shared/constants.ts`:
```typescript
export const SCHEMA_VERSION = 1;
export const DEFAULT_SOCKET_PORT = 19840;
export const MAX_SOCKET_PORT_RETRIES = 10;
export const SESSION_SAVE_DEBOUNCE_MS = 500;
export const IPC_BROADCAST_DEBOUNCE_MS = 16;
export const AGENT_PID_CHECK_INTERVAL_MS = 5000;
export const AGENT_SESSION_TTL_DAYS = 7;
export const STATE_HISTORY_MAX = 100;

export const DEFAULT_SETTINGS: import('./types').SettingsState = {
  appearance: { theme: 'system', language: 'system', iconMode: 'auto' },
  terminal: { defaultShell: 'powershell', fontSize: 14, fontFamily: 'Consolas', themeName: 'Dracula', cursorStyle: 'block' },
  browser: { searchEngine: 'google', searchSuggestions: true, httpAllowlist: ['localhost', '127.0.0.1', '::1'], externalUrlPatterns: [] },
  socket: { mode: 'automation', port: DEFAULT_SOCKET_PORT },
  agents: { claudeHooksEnabled: true, codexHooksEnabled: true, geminiHooksEnabled: true, orchestrationMode: 'auto' },
  telemetry: { enabled: true },
  updates: { autoCheck: true, channel: 'stable' },
  accessibility: { screenReaderMode: false, reducedMotion: false },
};
```

**Step 7: Action 테스트 작성**

`tests/unit/shared/actions.test.ts`:
```typescript
import { describe, it, expect } from 'vitest';
import { ActionSchema } from '../../../src/shared/actions';

describe('Action Schema Validation', () => {
  it('validates workspace.create', () => {
    const action = { type: 'workspace.create', payload: { windowId: 'win-1', name: 'Test' } };
    expect(ActionSchema.safeParse(action).success).toBe(true);
  });

  it('validates panel.split', () => {
    const action = { type: 'panel.split', payload: { panelId: 'p-1', direction: 'horizontal', newPanelType: 'terminal' } };
    expect(ActionSchema.safeParse(action).success).toBe(true);
  });

  it('rejects unknown action type', () => {
    const action = { type: 'unknown.action', payload: {} };
    expect(ActionSchema.safeParse(action).success).toBe(false);
  });

  it('rejects panel.split with invalid direction', () => {
    const action = { type: 'panel.split', payload: { panelId: 'p-1', direction: 'diagonal', newPanelType: 'terminal' } };
    expect(ActionSchema.safeParse(action).success).toBe(false);
  });

  it('validates agent.session_start', () => {
    const action = { type: 'agent.session_start', payload: { sessionId: 's1', agentType: 'claude', workspaceId: 'ws-1', surfaceId: 'sf-1', pid: 1234 } };
    expect(ActionSchema.safeParse(action).success).toBe(true);
  });

  it('validates notification.create', () => {
    const action = { type: 'notification.create', payload: { title: 'Hello' } };
    expect(ActionSchema.safeParse(action).success).toBe(true);
  });
});
```

**Step 8: 테스트 실행, 통과 확인**

```bash
npx vitest run tests/unit/shared/
```
Expected: ALL PASS

**Step 9: 커밋**

```bash
git add src/shared/ tests/unit/shared/
git commit -m "feat: add shared types, Zod schemas, and action definitions with full validation tests"
```

---

## Task 3: SOT 스토어 (AppStateStore)

**Files:**
- Create: `src/main/sot/store.ts`
- Create: `src/main/sot/create-default-state.ts`
- Test: `tests/unit/sot/store.test.ts`

**Step 1: 스토어 테스트 작성 (실패)**

`tests/unit/sot/store.test.ts`:
```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { AppStateStore } from '../../../src/main/sot/store';

describe('AppStateStore', () => {
  let store: AppStateStore;

  beforeEach(() => {
    store = new AppStateStore();
  });

  it('initializes with default state', () => {
    const state = store.getState();
    expect(state.windows).toEqual([]);
    expect(state.workspaces).toEqual([]);
    expect(state.settings.terminal.defaultShell).toBe('powershell');
  });

  it('dispatches workspace.create and adds workspace', () => {
    store.dispatch({ type: 'workspace.create', payload: { windowId: 'win-1', name: 'Test WS' } });
    const state = store.getState();
    expect(state.workspaces).toHaveLength(1);
    expect(state.workspaces[0].name).toBe('Test WS');
    expect(state.workspaces[0].windowId).toBe('win-1');
  });

  it('dispatches workspace.close and removes workspace', () => {
    store.dispatch({ type: 'workspace.create', payload: { windowId: 'win-1', name: 'WS' } });
    const wsId = store.getState().workspaces[0].id;
    store.dispatch({ type: 'workspace.close', payload: { workspaceId: wsId } });
    expect(store.getState().workspaces).toHaveLength(0);
  });

  it('dispatches workspace.rename', () => {
    store.dispatch({ type: 'workspace.create', payload: { windowId: 'win-1', name: 'Old' } });
    const wsId = store.getState().workspaces[0].id;
    store.dispatch({ type: 'workspace.rename', payload: { workspaceId: wsId, name: 'New' } });
    expect(store.getState().workspaces[0].name).toBe('New');
  });

  it('dispatches workspace.select and updates focus', () => {
    store.dispatch({ type: 'workspace.create', payload: { windowId: 'win-1', name: 'WS' } });
    const wsId = store.getState().workspaces[0].id;
    store.dispatch({ type: 'workspace.select', payload: { workspaceId: wsId } });
    expect(store.getState().focus.activeWorkspaceId).toBe(wsId);
  });

  it('rejects invalid action payload', () => {
    const result = store.dispatch({ type: 'workspace.create', payload: {} } as any);
    expect(result.ok).toBe(false);
    expect(result.error).toBeDefined();
  });

  it('emits change event on dispatch', () => {
    let emitted = false;
    store.on('change', () => { emitted = true; });
    store.dispatch({ type: 'workspace.create', payload: { windowId: 'win-1' } });
    expect(emitted).toBe(true);
  });

  it('maintains state history for debugging', () => {
    store.dispatch({ type: 'workspace.create', payload: { windowId: 'win-1', name: 'A' } });
    store.dispatch({ type: 'workspace.create', payload: { windowId: 'win-1', name: 'B' } });
    expect(store.getHistory()).toHaveLength(2);
  });

  it('dispatches agent.session_start', () => {
    store.dispatch({ type: 'agent.session_start', payload: { sessionId: 'as-1', agentType: 'claude', workspaceId: 'ws-1', surfaceId: 'sf-1' } });
    expect(store.getState().agents).toHaveLength(1);
    expect(store.getState().agents[0].status).toBe('running');
  });

  it('dispatches agent.status_update', () => {
    store.dispatch({ type: 'agent.session_start', payload: { sessionId: 'as-1', agentType: 'claude', workspaceId: 'ws-1', surfaceId: 'sf-1' } });
    store.dispatch({ type: 'agent.status_update', payload: { sessionId: 'as-1', status: 'idle' } });
    expect(store.getState().agents[0].status).toBe('idle');
  });

  it('dispatches agent.session_end', () => {
    store.dispatch({ type: 'agent.session_start', payload: { sessionId: 'as-1', agentType: 'claude', workspaceId: 'ws-1', surfaceId: 'sf-1' } });
    store.dispatch({ type: 'agent.session_end', payload: { sessionId: 'as-1' } });
    expect(store.getState().agents).toHaveLength(0);
  });

  it('dispatches notification.create', () => {
    store.dispatch({ type: 'notification.create', payload: { title: 'Hello' } });
    expect(store.getState().notifications).toHaveLength(1);
    expect(store.getState().notifications[0].title).toBe('Hello');
  });

  it('dispatches notification.clear', () => {
    store.dispatch({ type: 'notification.create', payload: { title: 'A' } });
    store.dispatch({ type: 'notification.create', payload: { title: 'B' } });
    store.dispatch({ type: 'notification.clear', payload: {} });
    expect(store.getState().notifications).toHaveLength(0);
  });
});
```

**Step 2: 테스트 실행, 실패 확인**

```bash
npx vitest run tests/unit/sot/store.test.ts
```
Expected: FAIL

**Step 3: create-default-state.ts 구현**

`src/main/sot/create-default-state.ts`:
```typescript
import type { AppState } from '../../shared/types';
import { DEFAULT_SETTINGS } from '../../shared/constants';

export function createDefaultState(): AppState {
  return {
    windows: [],
    workspaces: [],
    panels: [],
    surfaces: [],
    agents: [],
    notifications: [],
    settings: structuredClone(DEFAULT_SETTINGS),
    shortcuts: { shortcuts: {} },
    focus: {
      activeWindowId: null,
      activeWorkspaceId: null,
      activePanelId: null,
      activeSurfaceId: null,
      focusTarget: null,
    },
  };
}
```

**Step 4: store.ts 구현**

`src/main/sot/store.ts`:
```typescript
import { EventEmitter } from 'node:events';
import { produce } from 'immer';
import { ActionSchema, type Action } from '../../shared/actions';
import type { AppState } from '../../shared/types';
import { STATE_HISTORY_MAX } from '../../shared/constants';
import { createDefaultState } from './create-default-state';
import crypto from 'node:crypto';

interface DispatchResult {
  ok: boolean;
  error?: string;
}

interface HistoryEntry {
  action: Action;
  timestamp: number;
}

export class AppStateStore extends EventEmitter {
  private state: AppState;
  private history: HistoryEntry[] = [];

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

  dispatch(rawAction: unknown): DispatchResult {
    const parsed = ActionSchema.safeParse(rawAction);
    if (!parsed.success) {
      return { ok: false, error: parsed.error.message };
    }
    const action = parsed.data;

    try {
      this.state = produce(this.state, (draft) => {
        this.applyAction(draft, action);
      });

      this.history.push({ action, timestamp: Date.now() });
      if (this.history.length > STATE_HISTORY_MAX) {
        this.history.shift();
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
          id,
          windowId: action.payload.windowId,
          name: action.payload.name ?? 'New Workspace',
          panelLayout: { type: 'leaf', panelId },
          agentPids: {},
          statusEntries: [],
          unreadCount: 0,
          isPinned: false,
        });
        draft.panels.push({
          id: panelId,
          workspaceId: id,
          panelType: 'terminal',
          surfaceIds: [surfaceId],
          activeSurfaceId: surfaceId,
          isZoomed: false,
        });
        draft.surfaces.push({
          id: surfaceId,
          panelId,
          surfaceType: 'terminal',
          title: 'Terminal',
        });
        const win = draft.windows.find((w) => w.id === action.payload.windowId);
        if (win) {
          win.workspaceIds.push(id);
        }
        break;
      }
      case 'workspace.close': {
        const wsIndex = draft.workspaces.findIndex((w) => w.id === action.payload.workspaceId);
        if (wsIndex === -1) break;
        const ws = draft.workspaces[wsIndex];
        draft.panels = draft.panels.filter((p) => p.workspaceId !== ws.id);
        draft.surfaces = draft.surfaces.filter((s) => {
          const panel = draft.panels.find((p) => p.id === s.panelId);
          return panel !== undefined || !draft.workspaces.some(() => true);
        });
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
        if (ws) {
          draft.focus.activeWindowId = ws.windowId;
        }
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
        const panelIndex = draft.panels.findIndex((p) => p.id === action.payload.panelId);
        if (panelIndex === -1) break;
        draft.surfaces = draft.surfaces.filter((s) => s.panelId !== action.payload.panelId);
        draft.panels.splice(panelIndex, 1);
        break;
      }
      case 'panel.split': {
        // Phase 2에서 구현 — 여기서는 noop
        break;
      }
      case 'panel.resize': {
        // Phase 2에서 구현 — 여기서는 noop
        break;
      }
      case 'surface.create': {
        const newId = crypto.randomUUID();
        const panel = draft.panels.find((p) => p.id === action.payload.panelId);
        if (!panel) break;
        draft.surfaces.push({
          id: newId,
          panelId: action.payload.panelId,
          surfaceType: action.payload.surfaceType,
          title: action.payload.surfaceType === 'terminal' ? 'Terminal' : 'New Tab',
        });
        panel.surfaceIds.push(newId);
        panel.activeSurfaceId = newId;
        break;
      }
      case 'surface.close': {
        const surfaceIndex = draft.surfaces.findIndex((s) => s.id === action.payload.surfaceId);
        if (surfaceIndex === -1) break;
        const surface = draft.surfaces[surfaceIndex];
        const panel = draft.panels.find((p) => p.id === surface.panelId);
        if (panel) {
          panel.surfaceIds = panel.surfaceIds.filter((id) => id !== action.payload.surfaceId);
          if (panel.activeSurfaceId === action.payload.surfaceId) {
            panel.activeSurfaceId = panel.surfaceIds[0] ?? '';
          }
        }
        draft.surfaces.splice(surfaceIndex, 1);
        break;
      }
      case 'surface.focus': {
        draft.focus.activeSurfaceId = action.payload.surfaceId;
        const surface = draft.surfaces.find((s) => s.id === action.payload.surfaceId);
        if (surface) {
          draft.focus.activePanelId = surface.panelId;
          const panel = draft.panels.find((p) => p.id === surface.panelId);
          if (panel) {
            panel.activeSurfaceId = action.payload.surfaceId;
          }
        }
        break;
      }
      case 'surface.send_text': {
        // 사이드이펙트 전용 — 상태 변경 없음 (미들웨어에서 PTY에 전달)
        break;
      }
      case 'agent.session_start': {
        draft.agents.push({
          sessionId: action.payload.sessionId,
          agentType: action.payload.agentType,
          workspaceId: action.payload.workspaceId,
          surfaceId: action.payload.surfaceId,
          status: 'running',
          statusIcon: '⚡',
          statusColor: 'blue',
          pid: action.payload.pid,
          lastActivity: Date.now(),
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
          id: crypto.randomUUID(),
          title: action.payload.title,
          subtitle: action.payload.subtitle,
          body: action.payload.body,
          workspaceId: action.payload.workspaceId,
          surfaceId: action.payload.surfaceId,
          createdAt: Date.now(),
          isRead: false,
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
        if (action.payload.activeWindowId !== undefined) draft.focus.activeWindowId = action.payload.activeWindowId;
        if (action.payload.activeWorkspaceId !== undefined) draft.focus.activeWorkspaceId = action.payload.activeWorkspaceId;
        if (action.payload.activePanelId !== undefined) draft.focus.activePanelId = action.payload.activePanelId;
        if (action.payload.activeSurfaceId !== undefined) draft.focus.activeSurfaceId = action.payload.activeSurfaceId;
        if (action.payload.focusTarget !== undefined) draft.focus.focusTarget = action.payload.focusTarget;
        break;
      }
      case 'settings.update': {
        // 단순 shallow merge — 향후 깊은 merge로 개선
        Object.assign(draft.settings, action.payload);
        break;
      }
    }
  }
}
```

**Step 5: 테스트 실행, 통과 확인**

```bash
npx vitest run tests/unit/sot/store.test.ts
```
Expected: ALL PASS

**Step 6: 커밋**

```bash
git add src/main/sot/ tests/unit/sot/
git commit -m "feat: implement AppStateStore with Immer, Zod validation, event emission, and state history"
```

---

## Task 4~9: 요약 (Phase 1 후반)

> 분량 제한으로 Task 4~9는 핵심 구조만 기술합니다.
> 실제 구현 시 Task 3과 동일한 RED→GREEN→REFACTOR→COMMIT 사이클을 따릅니다.

### Task 4: SOT 미들웨어

**Files:** `src/main/sot/middleware/` (validation.ts, persistence.ts, ipc-broadcast.ts, audit-log.ts)
**Tests:** `tests/unit/sot/middleware/` (각각)

- **Validation**: Action 도착 → Zod 검증 → 통과/거부
- **Persistence**: 상태 변경 → 500ms 디바운스 → `%APPDATA%/cmux-win/session.json` 저장
- **IPC Broadcast**: 변경 슬라이스 → windowId 필터링 → webContents.send()
- **Audit Log**: DEBUG 빌드 → `%TEMP%/cmux-win-debug.log` 기록

### Task 5: 터미널 엔진

**Files:** `src/preload/terminal-preload.ts`, `src/renderer/components/terminal/XTermWrapper.tsx`
**Deps:** `npm install xterm @xterm/addon-webgl @xterm/addon-fit node-pty`
**Tests:** `tests/unit/terminal/pty-bridge.test.ts`, `tests/integration/terminal/terminal-io.test.ts`

- **preload**: node-pty를 contextBridge로 Renderer에 노출
- **XTermWrapper**: React 외부에서 xterm.js DOM 직접 마운트
- **WebGL/Canvas 전환**: webglcontextlost → Canvas 폴백
- **셸 감지**: PowerShell > CMD > Git Bash > WSL 순서

### Task 6: Socket API 서버

**Files:** `src/main/socket/server.ts`, `src/main/socket/router.ts`, `src/main/socket/auth.ts`, `src/main/socket/handlers/`
**Tests:** `tests/unit/socket/router.test.ts`, `tests/integration/socket/server.test.ts`

- **TCP 서버**: localhost:19840, 포트 충돌 자동 증가
- **JSON-RPC 2.0**: 개행 구분, request/response
- **Auth**: 5단계 보안 모드
- **핸들러**: system.ping, workspace.*, surface.*, notification.*, agent.*
- 각 핸들러가 `store.dispatch(action)` 호출 → SOT 경유

### Task 7: Typesafe IPC

**Files:** `src/shared/ipc-contract.ts`, `src/main/ipc/handlers.ts`, `src/renderer/hooks/useDispatch.ts`
**Tests:** `tests/unit/ipc/contract.test.ts`

- **IPC 계약**: dispatch, state:update, query:state 채널
- **Main 핸들러**: ipcMain.handle('dispatch', ...)
- **Renderer 훅**: useDispatch() → ipcRenderer.invoke('dispatch', action)
- **양방향 Zod 검증**

### Task 8: CLI 기본

**Files:** `src/cli/cmux-win.ts`, `src/cli/socket-client.ts`, `src/cli/commands/`
**Tests:** `tests/integration/cli/cli-commands.test.ts`

- **진입점**: `cmux-win <command> [args]`
- **소켓 클라이언트**: `tcp://127.0.0.1:19840` 파싱 + 연결
- **명령**: ping, version, list-workspaces, send, notify, claude-hook
- 각 명령 → JSON-RPC 요청 → 응답 출력

### Task 9: 통합 — Electron 앱 조립

**Files:** `src/main/app.ts` (수정), `src/renderer/App.tsx` (수정)
**Tests:** `tests/e2e/phase1-smoke.spec.ts`

- Main Process: SOT + 미들웨어 + Socket + IPC 초기화
- Renderer: 사이드바(빈) + 터미널 패널 1개 렌더링
- E2E: 앱 시작 → 터미널 표시 → CLI로 workspace.list → 응답 확인
- **Phase 1 완료 검증 체크포인트**:
  - [ ] Electron 창에 xterm.js 터미널이 작동하는가
  - [ ] 터미널에 PowerShell이 실행되고 키 입력이 되는가
  - [ ] `cmux-win ping` CLI가 "pong" 응답을 받는가
  - [ ] `cmux-win list-workspaces`가 워크스페이스 목록을 반환하는가
  - [ ] 앱 종료 → 재시작 시 세션이 복원되는가

---

## Phase 2~6 로드맵 (상위 수준)

| Phase | 목표 | 주요 Task | 선행 조건 |
|-------|------|----------|----------|
| **2: 핵심 UI** | 사이드바, 분할 패널, 탭, 단축키 | 윈도우 관리, 사이드바, PanelLayout CSS Grid, 탭 드래그, 키보드 30개 액션 | Phase 1 |
| **3: 브라우저+마크다운** | webview 패널, 옴니바, Find, 마크다운 뷰어 | BrowserPanel(webview), 히스토리(SQLite), P0 자동화 API, Find-in-page, MarkdownPanel(chokidar+remark) | Phase 1 |
| **4: 에이전트 오케스트레이션** | Claude Teams, Hook, tmux shim, 폴백 UI | claude.cmd 래퍼, tmux.cmd shim, Hook→SOT, 자체 오케스트레이션 UI, claude-teams 명령 | Phase 1+2 |
| **5: 셸+원격** | 셸 통합, SSH, 세션 퍼시스턴스 | PowerShell/CMD/WSL 통합, cmuxd-remote 번들, 포트 스캔, 스냅샷 저장/복원/마이그레이션 | Phase 1 |
| **6: 완성도** | 알림, 팔레트, 설정, 업데이트, 다국어, 접근성 | Toast, 퍼지 검색, SettingsPage, electron-updater, i18next, axe-core, 90+ 테마 | Phase 2+3+4 |

각 Phase 시작 전 해당 Phase의 상세 구현 계획을 별도로 작성합니다.

---

## 검증 체크포인트 (Phase 1 완료 기준)

```
[Phase 1 완료 게이트]

기능 검증:
  [ ] Electron 앱이 시작되고 터미널 패널이 표시됨
  [ ] PowerShell/CMD에서 키 입력 → 화면 출력이 ≤10ms 이내
  [ ] 터미널에서 명령 실행 가능 (dir, ls, git status 등)
  [ ] cmux-win ping → "pong" 응답
  [ ] cmux-win list-workspaces → JSON 워크스페이스 목록
  [ ] cmux-win notify --title "test" → 알림 생성 확인
  [ ] 앱 종료 → 재시작 → 이전 세션 복원

테스트 검증:
  [ ] Unit 테스트 전체 통과
  [ ] 커버리지 ≥90% (src/main/sot/, src/shared/)
  [ ] Integration 테스트 통과 (Socket API, IPC)
  [ ] E2E smoke 테스트 통과

품질 검증:
  [ ] TypeScript strict 에러 0개
  [ ] ESLint 경고 0개
  [ ] pre-commit hook 작동
```
