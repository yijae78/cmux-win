# 스크롤백 앱 재시작 복원 — 구현 계획 v2

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 앱 종료 시 터미널 스크롤백을 파일에 저장하고, 앱 시작 시 복원하여 사용자가 이전 터미널 내용을 유지할 수 있도록 한다.

**Architecture:** Renderer가 주기적으로 (30초) 터미널 buffer를 Main에 IPC로 전송 (push). Main이 scrollback.json에 저장. Renderer가 mount 시 Main에 요청하여 복원 (pull). 워크스페이스 전환은 기존 메모리 scrollbackCache 우선.

**Tech Stack:** Electron IPC (send/invoke), xterm.js buffer API, fs atomic write

---

## 성찰 반영

| # | 결함 | 해결 |
|---|------|------|
| P-1 | did-finish-load 시 XTermWrapper 미mount → IPC 유실 | **pull 모델**: Renderer mount 시 Main에 요청 |
| P-2 | 다수 surface 동시 IPC 부하 | surface별 stagger (surfaceId hash % 10초 offset) |
| P-3 | 앱 종료 시 마지막 30초 유실 | `before-quit`에서 scrollbackStore 즉시 동기 저장 |
| P-4 | scrollbackCache + file 중복 복원 | scrollbackCache 우선, 없으면 file fallback |
| P-5 | 닫힌 surface scrollback 미정리 | surface.close side-effect에서 삭제 |

---

## Task S1: IPC + preload

**Files:**
- Modify: `src/preload/index.ts`

### 구현

```typescript
// cmuxScrollback namespace — push(save) + pull(load)
contextBridge.exposeInMainWorld('cmuxScrollback', {
  // Renderer → Main: 주기적 scrollback 전송 (fire-and-forget)
  saveScrollback(surfaceId: string, content: string) {
    ipcRenderer.send(IPC_CHANNELS.SCROLLBACK_SAVE, surfaceId, content);
  },
  // Renderer → Main: mount 시 scrollback 요청 (request-response)
  loadScrollback(surfaceId: string): Promise<string | null> {
    return ipcRenderer.invoke(IPC_CHANNELS.SCROLLBACK_LOAD, surfaceId);
  },
});
```

IPC_CHANNELS에 SCROLLBACK_SAVE, SCROLLBACK_LOAD는 이미 정의됨.

**핵심**: `loadScrollback`은 `invoke` (request-response). `saveScrollback`은 `send` (fire-and-forget).

### 테스트
기존 테스트 영향 없음.

### 커밋
```
git commit -m "feat(scrollback-s1): preload cmuxScrollback — save(send) + load(invoke)"
```

---

## Task S2: Renderer 주기적 전송

**Files:**
- Modify: `src/renderer/components/terminal/XTermWrapper.tsx`

### 구현

main useEffect 내부, initPty 호출 후:

```typescript
// Window 타입 선언 (상단)
declare global {
  interface Window {
    cmuxScrollback?: {
      saveScrollback(surfaceId: string, content: string): void;
      loadScrollback(surfaceId: string): Promise<string | null>;
    };
  }
}

// P-2: surface별 stagger offset (0~10초)
const staggerMs = (surfaceId.charCodeAt(0) % 10) * 1000;

const scrollbackTimer = setTimeout(() => {
  const interval = setInterval(() => {
    const t = terminalRef.current;
    if (!t || !window.cmuxScrollback) return;
    const buffer = t.buffer.active;
    const lines: string[] = [];
    const start = Math.max(0, buffer.length - 10000); // MAX_SCROLLBACK_LINES
    for (let i = start; i < buffer.length; i++) {
      const line = buffer.getLine(i);
      if (line) lines.push(line.translateToString(true));
    }
    const content = lines.join('\n');
    if (content.length > 0 && content.length <= 1_000_000) { // MAX_SCROLLBACK_BYTES
      window.cmuxScrollback.saveScrollback(surfaceId, content);
    }
  }, 30_000);

  // cleanup에서 interval 정리
  // (이 참조를 cleanup에서 접근 가능하도록 저장)
  scrollbackIntervalRef.current = interval;
}, staggerMs);

// cleanup에 추가:
clearTimeout(scrollbackTimer);
if (scrollbackIntervalRef.current) clearInterval(scrollbackIntervalRef.current);
```

`scrollbackIntervalRef`를 useRef로 선언:
```typescript
const scrollbackIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
```

### 테스트
기존 테스트 영향 없음.

### 커밋
```
git commit -m "feat(scrollback-s2): periodic scrollback save — 30s staggered per surface"
```

---

## Task S3: Main 저장/로드/정리

**Files:**
- Modify: `src/main/index.ts`

### 구현

```typescript
import { ipcMain } from 'electron'; // 이미 import됨

// --- Scrollback persistence ---
const scrollbackPath = path.join(app.getPath('appData'), 'cmux-win', 'scrollback.json');
const scrollbackStore = new Map<string, string>();
let scrollbackSaveTimer: ReturnType<typeof setTimeout> | null = null;

// 앱 시작 시 로드
try {
  const raw = fs.readFileSync(scrollbackPath, 'utf8');
  const data = JSON.parse(raw) as Record<string, string>;
  for (const [k, v] of Object.entries(data)) scrollbackStore.set(k, v);
} catch { /* 파일 없거나 손상 → 무시 */ }

// Renderer → Main: scrollback 수신 (push)
ipcMain.on(IPC_CHANNELS.SCROLLBACK_SAVE, (_event, surfaceId: string, content: string) => {
  scrollbackStore.set(surfaceId, content);
  // 디바운스 5초 후 파일 저장
  if (scrollbackSaveTimer) clearTimeout(scrollbackSaveTimer);
  scrollbackSaveTimer = setTimeout(() => {
    try {
      const dir = path.dirname(scrollbackPath);
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
      const tmp = scrollbackPath + '.tmp';
      fs.writeFileSync(tmp, JSON.stringify(Object.fromEntries(scrollbackStore)));
      fs.renameSync(tmp, scrollbackPath);
    } catch (err) {
      console.error('[cmux-win] scrollback save error:', err);
    }
  }, 5000);
});

// Renderer → Main: scrollback 요청 (pull, P-1)
ipcMain.handle(IPC_CHANNELS.SCROLLBACK_LOAD, (_event, surfaceId: string) => {
  return scrollbackStore.get(surfaceId) ?? null;
});

// P-5: surface.close 시 scrollback 정리
store.on('change', (action: { type: string; payload?: { surfaceId?: string } }) => {
  if (action.type === 'surface.close' && action.payload?.surfaceId) {
    scrollbackStore.delete(action.payload.surfaceId);
  }
});
```

### P-3: before-quit에서 즉시 저장

```typescript
app.on('before-quit', () => {
  // 마지막 scrollback을 동기적으로 저장
  try {
    const dir = path.dirname(scrollbackPath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(scrollbackPath, JSON.stringify(Object.fromEntries(scrollbackStore)));
  } catch { /* 무시 */ }
});
```

### 테스트

```typescript
// tests/unit/main/scrollback-persistence.test.ts
import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

describe('scrollback file persistence', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sb-test-'));
  const filePath = path.join(tmpDir, 'scrollback.json');

  afterAll(() => fs.rmSync(tmpDir, { recursive: true, force: true }));

  it('saves and loads scrollback data', () => {
    const data = { 'surf-1': 'line1\nline2', 'surf-2': 'hello' };
    fs.writeFileSync(filePath, JSON.stringify(data));
    const loaded = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    expect(loaded['surf-1']).toBe('line1\nline2');
  });

  it('handles missing file', () => {
    const missing = path.join(tmpDir, 'nonexistent.json');
    let result: Record<string, string> = {};
    try { result = JSON.parse(fs.readFileSync(missing, 'utf8')); } catch { /* empty */ }
    expect(Object.keys(result)).toHaveLength(0);
  });

  it('handles corrupted file', () => {
    const corrupt = path.join(tmpDir, 'corrupt.json');
    fs.writeFileSync(corrupt, 'not json{{{');
    let result: Record<string, string> = {};
    try { result = JSON.parse(fs.readFileSync(corrupt, 'utf8')); } catch { /* empty */ }
    expect(Object.keys(result)).toHaveLength(0);
  });
});
```

### 커밋
```
git commit -m "feat(scrollback-s3): main scrollback.json — save/load/cleanup + before-quit"
```

---

## Task S4: Renderer mount 시 pull 복원

**Files:**
- Modify: `src/renderer/components/terminal/XTermWrapper.tsx`

### 구현

initPty 내부, PTY 설정 전에:

```typescript
// P-4: scrollbackCache(워크스페이스 전환) 우선, 없으면 file에서 pull
const cached = scrollbackCache.get(surfaceId);
if (cached) {
  terminal.write(cached);
  scrollbackCache.delete(surfaceId);
} else if (window.cmuxScrollback) {
  // P-1: mount 시 Main에 pull 요청
  const fileContent = await window.cmuxScrollback.loadScrollback(surfaceId);
  if (fileContent) {
    terminal.write(fileContent);
  }
}
```

기존 PTY reattach 분기의 scrollbackCache 로직을 이것으로 통합.

### 주의
- `loadScrollback`은 async → initPty는 이미 async이므로 await 가능
- 복원 후 PTY spawn이 이어지므로 새 출력은 복원 내용 뒤에 표시
- scrollbackCache가 있으면 file을 읽지 않음 (P-4: 메모리 우선)

### 커밋
```
git commit -m "feat(scrollback-s4): pull restore on mount — cache first, file fallback"
```

---

## 완료 체크리스트

```
[ ] preload cmuxScrollback.saveScrollback (send)
[ ] preload cmuxScrollback.loadScrollback (invoke → handle)
[ ] XTermWrapper 30초 주기 전송 (staggered)
[ ] Main ipcMain.on SCROLLBACK_SAVE → scrollbackStore
[ ] Main ipcMain.handle SCROLLBACK_LOAD → scrollbackStore.get
[ ] Main scrollback.json 파일 저장 (디바운스 5초, atomic write)
[ ] Main scrollback.json 파일 로드 (앱 시작 시)
[ ] Main before-quit 동기 저장 (P-3)
[ ] Main surface.close 시 scrollbackStore 삭제 (P-5)
[ ] XTermWrapper mount: scrollbackCache 우선 → file fallback (P-1, P-4)
[ ] 전체 테스트 ALL PASS
```
