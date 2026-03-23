# Phase 3: 브라우저 + 마크다운 — 구현 계획 v3

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Electron webview 기반 브라우저 패널, 옴니바, 히스토리 DB, 브라우저 자동화 API P0, 마크다운 뷰어, Find-in-page를 구현한다.

**Architecture:** `<webview>` 태그로 프로세스 격리된 브라우저를 React DOM 내에 렌더링. 히스토리는 better-sqlite3(Main Process)에 저장, IPC로 조회. 자동화 API는 Socket RPC로 webview.executeJavaScript를 호출.

**Tech Stack:** Electron webview, better-sqlite3, React, JSON-RPC 2.0

**선행 조건:** Phase 1-2, Phase 4-5 완료 (273 tests, 31 files)
**설계안 정본:** `2026-03-21-phases-3-to-6-design.md` v3

---

## 5차 성찰 반영 사항

| # | 결함 | 수정 |
|---|------|------|
| P3-1 | normalizeUrl/inputToUrl 중복 | url-utils.ts 하나로 통합, Task 23에서 import |
| P3-2 | SurfaceUpdateMetaAction 이미 Task 29에서 추가 | 재추가 안 함, browser 필드만 스키마 확장 |
| P3-3 | webview JSX 타입 미선언 | BrowserSurface에 JSX.IntrinsicElements 선언 |
| P3-4 | onCrashed stale url | wv.getURL() 직접 호출로 변경 |
| P3-5 | Omnibar 코드 없음 | 전체 컴포넌트 코드 명시 |
| P3-6 | MarkdownViewer 미렌더링 | stub 인정, remark 의존성 제거 |
| P3-7 | dangerouslySetInnerHTML XSS | stub이므로 해당 없음 |
| P3-8 | dispatch prop drilling | callback props 패턴 유지 |

### 6차 성찰

| # | 결함 | 심각도 | 수정 |
|---|------|--------|------|
| P3-N1 | BrowserSurface useEffect 콜백 deps → 무한 재실행 | **높음** | deps를 [surfaceId]만, 콜백은 useRef |
| P3-N2 | Task 24가 url-utils.ts만으로 너무 작음 | **중간** | Task 23에 병합 |
| P3-N3 | SearchOverlay 테스트에 React DOM 환경 없음 | **중간** | 컴포넌트 테스트 생략, pure 함수만 |

---

## 의존성 그래프 (P3-1, P3-N2 수정)

```
Task 23 (url-utils + BrowserSurface + NavigationBar)  ← P3-N2: Task 24 병합
  ├─→ Task 25 (히스토리 DB)
  └─→ Task 26 (자동화 API P0)

Task 27 (마크다운 + Find) ← 독립

실행 순서: 23 → 25,26 (병렬), 27 (독립, 아무 때나)
```

---

## 추가 의존성 설치

```bash
npm install better-sqlite3
npm install -D @types/better-sqlite3
```

`electron-vite.config.ts`에 external 추가:
```typescript
main: { external: ['electron', 'node-pty', 'better-sqlite3'] }
```

NOTE: remark/rehype/shiki/chokidar는 Phase 3에서 설치하지 않음 (P3-6: stub).

---

## ~~Task 24~~ → Task 23 Step 1에 병합 (P3-N2)

---

## Task 23: url-utils + BrowserSurface + NavigationBar

**Files:**
- Create: `src/shared/url-utils.ts`
- Create: `src/renderer/components/browser/BrowserSurface.tsx`
- Create: `src/renderer/components/browser/NavigationBar.tsx`
- Modify: `src/shared/actions.ts` — SurfaceUpdateMetaAction에 browser 필드 추가
- Modify: `src/main/sot/store.ts` — surface.update_meta browser 처리
- Modify: `src/renderer/components/panels/PanelContainer.tsx` — browser 분기 + callbacks
- Modify: `src/renderer/components/panels/PanelLayout.tsx` — callback 전달
- Modify: `src/renderer/App.tsx` — callback 전달
- Test: `tests/unit/shared/url-utils.test.ts`

### Step 1: url-utils.ts (P3-1: 통합)

```typescript
export type SearchEngine = 'google' | 'duckduckgo' | 'bing' | 'kagi' | 'startpage';

const SEARCH_URLS: Record<SearchEngine, string> = {
  google: 'https://www.google.com/search?q=',
  duckduckgo: 'https://duckduckgo.com/?q=',
  bing: 'https://www.bing.com/search?q=',
  kagi: 'https://kagi.com/search?q=',
  startpage: 'https://www.startpage.com/search?q=',
};

export function isUrl(input: string): boolean {
  if (/^https?:\/\//i.test(input)) return true;
  if (/^localhost(:\d+)?/i.test(input)) return true;
  if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/.test(input)) return true;
  if (/^[a-z0-9]([a-z0-9-]*[a-z0-9])?\.[a-z]{2,}(\/|$)/i.test(input)) return true;
  return false;
}

export function inputToUrl(input: string, engine: SearchEngine = 'google'): string {
  const trimmed = input.trim();
  if (!trimmed) return 'about:blank';
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  if (isUrl(trimmed)) {
    if (/^localhost/i.test(trimmed) || /^\d/.test(trimmed)) return `http://${trimmed}`;
    return `https://${trimmed}`;
  }
  return SEARCH_URLS[engine] + encodeURIComponent(trimmed);
}
```

### Step 2: 테스트

```typescript
import { describe, it, expect } from 'vitest';
import { isUrl, inputToUrl } from '../../../src/shared/url-utils';

describe('isUrl', () => {
  it('detects http:// prefix', () => expect(isUrl('http://x.com')).toBe(true));
  it('detects https:// prefix', () => expect(isUrl('https://x.com')).toBe(true));
  it('detects localhost', () => expect(isUrl('localhost:3000')).toBe(true));
  it('detects IP addresses', () => expect(isUrl('192.168.1.1')).toBe(true));
  it('detects domain.tld', () => expect(isUrl('example.com')).toBe(true));
  it('rejects plain text', () => expect(isUrl('hello world')).toBe(false));
  it('rejects partial domains', () => expect(isUrl('notadomain')).toBe(false));
});

describe('inputToUrl', () => {
  it('passes http URLs through', () => expect(inputToUrl('http://x.com')).toBe('http://x.com'));
  it('passes https URLs through', () => expect(inputToUrl('https://x.com')).toBe('https://x.com'));
  it('adds http:// to localhost', () => expect(inputToUrl('localhost:3000')).toBe('http://localhost:3000'));
  it('adds http:// to IPs', () => expect(inputToUrl('192.168.1.1')).toBe('http://192.168.1.1'));
  it('adds https:// to domains', () => expect(inputToUrl('example.com')).toBe('https://example.com'));
  it('converts text to search query', () => expect(inputToUrl('hello')).toContain('google.com/search?q=hello'));
  it('uses specified search engine', () => expect(inputToUrl('test', 'duckduckgo')).toContain('duckduckgo.com'));
  it('returns about:blank for empty', () => expect(inputToUrl('')).toBe('about:blank'));
});
```

### Step 2: actions.ts — SurfaceUpdateMetaAction에 browser 필드 추가 (P3-2)

기존 스키마에 browser 필드만 추가 (재생성 아님):

```typescript
// 현재:
payload: z.object({
  surfaceId: z.string(),
  title: z.string().optional(),
  pendingCommand: z.string().nullable().optional(),
  terminal: z.object({ ... }).optional(),
})

// 변경 후:
payload: z.object({
  surfaceId: z.string(),
  title: z.string().optional(),
  pendingCommand: z.string().nullable().optional(),
  terminal: z.object({ ... }).optional(),
  browser: z.object({               // P3-2: 추가
    url: z.string().optional(),
    isLoading: z.boolean().optional(),
  }).optional(),
})
```

### Step 3: store.ts — surface.update_meta에 browser 처리 추가

기존 `case 'surface.update_meta'`에 추가:

```typescript
if (action.payload.browser) {
  if (!surface.browser) surface.browser = { url: '', profileId: 'default', isLoading: false };
  if (action.payload.browser.url !== undefined) surface.browser.url = action.payload.browser.url;
  if (action.payload.browser.isLoading !== undefined) surface.browser.isLoading = action.payload.browser.isLoading;
}
```

### Step 4: NavigationBar.tsx

```typescript
import { type FC } from 'react';

export interface NavigationBarProps {
  url: string;
  isLoading: boolean;
  canGoBack: boolean;
  canGoForward: boolean;
  onNavigate: (url: string) => void;
  onGoBack: () => void;
  onGoForward: () => void;
  onReload: () => void;
  onStop: () => void;
  onToggleDevTools: () => void;
}

const NavigationBar: FC<NavigationBarProps> = ({
  url, isLoading, canGoBack, canGoForward,
  onNavigate, onGoBack, onGoForward, onReload, onStop, onToggleDevTools,
}) => (
  <div style={{
    display: 'flex', alignItems: 'center', gap: '4px',
    height: '32px', padding: '0 8px',
    background: '#252526', borderBottom: '1px solid #3c3c3c', flexShrink: 0,
  }}>
    <button onClick={onGoBack} disabled={!canGoBack} style={navBtnStyle}>←</button>
    <button onClick={onGoForward} disabled={!canGoForward} style={navBtnStyle}>→</button>
    <button onClick={isLoading ? onStop : onReload} style={navBtnStyle}>
      {isLoading ? '✕' : '⟳'}
    </button>
    <input
      defaultValue={url}
      onKeyDown={(e) => {
        if (e.key === 'Enter') onNavigate((e.target as HTMLInputElement).value);
      }}
      style={{
        flex: 1, padding: '2px 8px', fontSize: '12px',
        background: '#3c3c3c', color: '#ccc', border: '1px solid #555',
        borderRadius: '3px', outline: 'none',
      }}
    />
    <button onClick={onToggleDevTools} style={navBtnStyle}>☰</button>
  </div>
);

const navBtnStyle: React.CSSProperties = {
  background: 'transparent', border: 'none', color: '#ccc',
  cursor: 'pointer', fontSize: '14px', padding: '2px 6px', borderRadius: '3px',
};

export default NavigationBar;
```

### Step 5: BrowserSurface.tsx (P3-1, P3-3, P3-4, P3-N1 수정)

```typescript
import { useRef, useEffect, useState, type FC } from 'react';
import NavigationBar from './NavigationBar';
import { inputToUrl } from '../../../shared/url-utils'; // P3-1: 통합 유틸 사용

// P3-3: webview JSX 타입 선언
declare global {
  namespace JSX {
    interface IntrinsicElements {
      webview: React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement> & {
        src?: string;
        partition?: string;
        webpreferences?: string;
      };
    }
  }
}

export interface BrowserSurfaceProps {
  surfaceId: string;
  initialUrl: string;
  profileId: string;
  onUrlChange?: (url: string) => void;
  onTitleChange?: (title: string) => void;
}

const BrowserSurface: FC<BrowserSurfaceProps> = ({
  surfaceId, initialUrl, profileId, onUrlChange, onTitleChange,
}) => {
  const webviewRef = useRef<any>(null);
  const [url, setUrl] = useState(initialUrl);

  // P3-N1: 콜백을 ref로 관리 (useEffect deps에서 제거)
  const onUrlChangeRef = useRef(onUrlChange);
  onUrlChangeRef.current = onUrlChange;
  const onTitleChangeRef = useRef(onTitleChange);
  onTitleChangeRef.current = onTitleChange;
  const [isLoading, setIsLoading] = useState(false);
  const [canGoBack, setCanGoBack] = useState(false);
  const [canGoForward, setCanGoForward] = useState(false);
  const [crashCount, setCrashCount] = useState(0);

  useEffect(() => {
    const wv = webviewRef.current;
    if (!wv) return;

    const onDidNavigate = () => {
      const currentUrl = wv.getURL();
      setUrl(currentUrl);
      setCanGoBack(wv.canGoBack());
      setCanGoForward(wv.canGoForward());
      onUrlChangeRef.current?.(currentUrl);  // P3-N1: ref 사용
    };
    const onTitleUpdated = (_e: any) => {
      onTitleChangeRef.current?.(wv.getTitle());  // P3-N1: ref 사용
    };
    const onStartLoading = () => setIsLoading(true);
    const onStopLoading = () => setIsLoading(false);
    const onCrashed = () => {
      setCrashCount(prev => {
        if (prev < 3) {
          // P3-4: wv.getURL() 사용 (stale closure 방지)
          const currentUrl = wv.getURL() || initialUrl;
          setTimeout(() => wv.loadURL(currentUrl), 500);
          return prev + 1;
        }
        return prev;
      });
    };

    wv.addEventListener('did-navigate', onDidNavigate);
    wv.addEventListener('did-navigate-in-page', onDidNavigate);
    wv.addEventListener('page-title-updated', onTitleUpdated);
    wv.addEventListener('did-start-loading', onStartLoading);
    wv.addEventListener('did-stop-loading', onStopLoading);
    wv.addEventListener('crashed', onCrashed);

    return () => {
      wv.removeEventListener('did-navigate', onDidNavigate);
      wv.removeEventListener('did-navigate-in-page', onDidNavigate);
      wv.removeEventListener('page-title-updated', onTitleUpdated);
      wv.removeEventListener('did-start-loading', onStartLoading);
      wv.removeEventListener('did-stop-loading', onStopLoading);
      wv.removeEventListener('crashed', onCrashed);
    };
  }, [surfaceId]); // P3-N1: surfaceId만 의존 (XTermWrapper 패턴과 동일)

  if (crashCount >= 3) {
    return (
      <div style={{ color: '#888', display: 'flex', alignItems: 'center',
        justifyContent: 'center', height: '100%', flexDirection: 'column', gap: '8px' }}>
        <span>Page crashed repeatedly.</span>
        <button onClick={() => { setCrashCount(0); webviewRef.current?.loadURL(url); }}
          style={{ padding: '4px 12px', cursor: 'pointer' }}>Retry</button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', width: '100%', height: '100%' }}>
      <NavigationBar
        url={url} isLoading={isLoading}
        canGoBack={canGoBack} canGoForward={canGoForward}
        onNavigate={(u) => webviewRef.current?.loadURL(inputToUrl(u))}
        onGoBack={() => webviewRef.current?.goBack()}
        onGoForward={() => webviewRef.current?.goForward()}
        onReload={() => webviewRef.current?.reload()}
        onStop={() => webviewRef.current?.stop()}
        onToggleDevTools={() => {
          if (webviewRef.current?.isDevToolsOpened()) webviewRef.current.closeDevTools();
          else webviewRef.current?.openDevTools();
        }}
      />
      <webview
        ref={webviewRef}
        src={initialUrl}
        partition={`persist:profile-${profileId}`}
        style={{ flex: 1 }}
        webpreferences="contextIsolation=yes"
        data-surface-id={surfaceId}
      />
    </div>
  );
};

export default BrowserSurface;
```

### Step 6: PanelContainer 수정 (P3-8: callback props 패턴)

PanelContainerProps에 callback 추가:
```typescript
onBrowserUrlChange?: (surfaceId: string, url: string) => void;
onBrowserTitleChange?: (surfaceId: string, title: string) => void;
```

browser 분기:
```typescript
{activeSurface?.surfaceType === 'browser' && (
  <BrowserSurface
    surfaceId={activeSurface.id}
    initialUrl={activeSurface.browser?.url || 'about:blank'}
    profileId={activeSurface.browser?.profileId || 'default'}
    onUrlChange={(u) => onBrowserUrlChange?.(activeSurface.id, u)}
    onTitleChange={(t) => onBrowserTitleChange?.(activeSurface.id, t)}
  />
)}
```

PanelLayout, App에서 같은 callback을 전달.
App.tsx에서 dispatch:
```typescript
onBrowserUrlChange={(sid, u) => void dispatch({
  type: 'surface.update_meta', payload: { surfaceId: sid, browser: { url: u } }
})}
onBrowserTitleChange={(sid, t) => void dispatch({
  type: 'surface.update_meta', payload: { surfaceId: sid, title: t }
})}
```

### Step 7: 커밋

```
git add src/shared/url-utils.ts src/shared/actions.ts src/main/sot/store.ts \
  src/renderer/components/browser/ src/renderer/components/panels/ src/renderer/App.tsx \
  tests/unit/shared/url-utils.test.ts
git commit -m "feat(task-23): BrowserSurface + url-utils — webview, navigation, crash recovery"
```

---

## Task 25: 히스토리 DB

**Files:**
- Create: `src/main/browser/history-db.ts`
- Modify: `src/main/index.ts` — IPC 핸들러 (기존 electron import에 ipcMain 추가, P3-8)
- Modify: `electron-vite.config.ts` — better-sqlite3 external
- Test: `tests/unit/browser/history-db.test.ts`

### history-db.ts

HistoryDb 클래스: constructor (SQLite `:memory:` 또는 파일), add, query, clear, close.
WAL 모드, 인덱스 3개.

### 테스트

better-sqlite3는 `:memory:` DB로 테스트 (시스템 Node.js에서 동작):

```typescript
describe('HistoryDb', () => {
  let db: HistoryDb;
  beforeEach(() => { db = new HistoryDb(':memory:'); });
  afterEach(() => { db.close(); });

  it('add and query');
  it('query filters by profileId');
  it('query filters by prefix');
  it('query orders by visits DESC');
  it('clear removes all for profile');
  it('clear without profile removes everything');
});
```

### 커밋

---

## Task 26: 브라우저 자동화 API P0 (stub)

**Files:**
- Create: `src/main/socket/handlers/browser.ts`
- Modify: `src/main/index.ts` — registerBrowserHandlers
- Test: `tests/unit/socket/browser-automation.test.ts`

8개 RPC (browser.eval/snapshot/click/type/fill/press/wait/screenshot).
**모두 stub** — params 검증만, 실제 webview 연동은 후속 작업 (P3-9).

NOTE: 실제 webview 연동에는 Main↔Renderer IPC 브릿지가 필요 (surfaceId → webview 인스턴스 참조). 이것은 Phase 3의 scope 외부이며 후속 작업으로 문서화.

### 커밋

---

## Task 27: 마크다운 뷰어 (stub) + SearchOverlay + Find

**Files:**
- Create: `src/renderer/components/markdown/MarkdownViewer.tsx` (stub, P3-6)
- Create: `src/renderer/components/search/SearchOverlay.tsx`
- Modify: `src/renderer/components/panels/PanelContainer.tsx` — markdown 분기
- Modify: `src/shared/shortcuts.ts` — Ctrl+F 추가

### MarkdownViewer (stub — P3-6)

```typescript
// remark/rehype 미사용. 파일 경로만 표시.
// 실제 렌더링은 Phase 6에서 구현.
const MarkdownViewer: FC<{ filePath: string }> = ({ filePath }) => (
  <div style={{ padding: '16px', color: '#ccc', overflow: 'auto', height: '100%' }}>
    <p>Markdown viewer (stub)</p>
    <p>File: {filePath}</p>
  </div>
);
```

### SearchOverlay

```typescript
const SearchOverlay: FC<SearchOverlayProps> = ({
  onSearch, onNext, onPrev, onClose, matchCount, currentMatch,
}) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState('');
  useEffect(() => { inputRef.current?.focus(); }, []);

  return (
    <div style={{
      position: 'absolute', top: 0, right: 0,
      background: '#252526', border: '1px solid #3c3c3c',
      padding: '4px 8px', display: 'flex', alignItems: 'center',
      gap: '4px', borderRadius: '0 0 0 4px', zIndex: 100,
    }}>
      <input ref={inputRef} value={query}
        onChange={(e) => { setQuery(e.target.value); onSearch(e.target.value); }}
        onKeyDown={(e) => {
          if (e.key === 'Enter') e.shiftKey ? onPrev() : onNext();
          if (e.key === 'Escape') onClose();
        }}
        style={{ width: '200px', padding: '2px 6px', fontSize: '12px',
          background: '#3c3c3c', color: '#ccc', border: '1px solid #555',
          borderRadius: '3px', outline: 'none' }}
        placeholder="Find..."
      />
      {matchCount !== undefined && (
        <span style={{ fontSize: '11px', color: '#888' }}>{currentMatch ?? 0}/{matchCount}</span>
      )}
      <button onClick={onPrev} style={btnStyle}>↑</button>
      <button onClick={onNext} style={btnStyle}>↓</button>
      <button onClick={onClose} style={btnStyle}>✕</button>
    </div>
  );
};
```

### 테스트 (P3-N3)

SearchOverlay는 pure UI. React DOM 테스트 환경 없으므로 컴포넌트 테스트 생략.
E2E 또는 수동 검증으로 대체.

### 커밋

```
git add src/renderer/components/markdown/ src/renderer/components/search/ \
  src/renderer/components/panels/PanelContainer.tsx src/shared/shortcuts.ts
git commit -m "feat(task-27): MarkdownViewer stub + SearchOverlay + Ctrl+F"
```

---

## Phase 3 완료 체크리스트

```
[ ] url-utils: isUrl, inputToUrl 테스트 통과
[ ] SurfaceUpdateMetaAction에 browser 필드 확장됨
[ ] BrowserSurface: webview 렌더링, partition 격리, JSX 타입 선언
[ ] NavigationBar: 뒤로/앞으로/새로고침/DevTools
[ ] 크래시 복구: 최대 3회, wv.getURL() 사용 (stale 방지)
[ ] PanelContainer: callback props로 dispatch (prop drilling 없음)
[ ] 히스토리 DB: :memory: 테스트 통과
[ ] 자동화 API: 8개 stub 등록, params 검증 테스트
[ ] MarkdownViewer: stub (remark 미사용)
[ ] SearchOverlay: Ctrl+F UI
[ ] 전체 테스트 ALL PASS
```
