# Phase 6: 완성도 — 구현 계획 v3

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Windows 알림/트레이, 커맨드 팔레트, 설정 UI, 자동 업데이트, 다국어, 텔레메트리, 테마 변환, 접근성을 구현하여 프로덕션 수준의 완성도를 달성한다.

**Architecture:** 각 Task가 독립적. 모든 기능은 기존 SOT Store + IPC + React 컴포넌트 패턴을 따른다.

**Tech Stack:** Electron Notification/Tray, i18next, electron-updater, Sentry, PostHog, axe-core

**선행 조건:** Phase 1-5, Phase 3 완료
**설계안 정본:** `2026-03-21-phases-3-to-6-design.md` v3

---

## 5차 성찰 반영 사항

| # | 결함 | 수정 |
|---|------|------|
| P6-1 | parseGhosttyTheme 구현 없음 | 파싱 로직 전체 코드 명시 |
| P6-2 | Windows Toast에 AppUserModelID 필요 | app.setAppUserModelId() 추가 |
| P6-3 | Function 타입 unsafe | 구체적 타입으로 변경 |
| P6-4 | 테마 소스 파일 미존재 | 변환된 JSON을 직접 번들 |
| P6-5 | 200키 과다 | 초기 ~50 핵심 키만 |

### 6차 성찰

| # | 결함 | 심각도 | 수정 |
|---|------|--------|------|
| P6-N1 | Tray 아이콘 파일 미존재 | **중간** | resources/icon.png placeholder 생성 명시 |
| P6-N2 | react-i18next Suspense 미처리 | **중간** | useSuspense: false 설정 |
| P6-N3 | package npm script 누락 | **낮음** | Task 35에 "package" script 추가 |

---

## 의존성 그래프

```
모든 Task가 독립. 순서 자유.
권장 순서: 38(테마) → 32(알림) → 33(팔레트) → 34(설정) → 35(업데이트) → 36(i18n) → 37(텔레메트리) → 39(접근성)
```

테마를 먼저 구현하면 설정 UI에서 테마 선택 프리뷰를 바로 연동 가능.

---

## Task 32: Windows Toast 알림 + 시스템 트레이

**Files:**
- Create: `src/main/notifications/windows-toast.ts`
- Create: `src/main/notifications/tray-manager.ts`
- Modify: `src/main/index.ts` — AppUserModelID + 트레이 + 알림 초기화
- Test: `tests/unit/notifications/tray-manager.test.ts`

### 구현

```typescript
// main/index.ts app.whenReady() 초반에:
app.setAppUserModelId('com.cmux-win.app'); // P6-2: Toast 필수

// P6-N1: Tray 아이콘 — resources/icon.png 필요
// 없으면 nativeImage.createEmpty() 사용 (빈 아이콘)
// 실제 아이콘은 디자이너가 제공 후 교체

// windows-toast.ts
import { Notification } from 'electron';

export function showToast(title: string, body: string, onClick?: () => void): void {
  const notification = new Notification({ title, body, silent: false });
  if (onClick) notification.on('click', onClick);
  notification.show();
}

// tray-manager.ts
import { Tray, Menu, nativeImage } from 'electron';

export class TrayManager {
  private tray: Tray | null = null;

  init(iconPath: string, onShow: () => void, onQuit: () => void): void {
    this.tray = new Tray(nativeImage.createFromPath(iconPath));
    this.tray.setContextMenu(Menu.buildFromTemplate([
      { label: 'Show', click: onShow },
      { label: 'Quit', click: onQuit },
    ]));
  }

  updateBadge(unreadCount: number): void {
    this.tray?.setTitle(unreadCount > 0 ? String(unreadCount) : '');
  }

  destroy(): void {
    this.tray?.destroy();
    this.tray = null;
  }
}
```

### 순수 함수 테스트

```typescript
describe('TrayManager badge logic', () => {
  it('unreadCount > 0 → 숫자 표시');
  it('unreadCount === 0 → 빈 문자열');
});
```

---

## Task 33: 커맨드 팔레트 (Ctrl+Shift+P)

**Files:**
- Create: `src/shared/fuzzy-search.ts`
- Create: `src/shared/command-registry.ts`
- Create: `src/renderer/components/command-palette/CommandPalette.tsx`
- Modify: `src/shared/shortcuts.ts` — Ctrl+Shift+P
- Modify: `src/renderer/hooks/useShortcuts.ts` — toggleCommandPalette
- Modify: `src/renderer/App.tsx` — CommandPalette 렌더링
- Test: `tests/unit/shared/fuzzy-search.test.ts`

### fuzzy-search.ts

```typescript
export interface FuzzyResult<T> {
  item: T;
  score: number;
}

export function fuzzySearch<T>(
  items: T[],
  query: string,
  getText: (item: T) => string,
): FuzzyResult<T>[] {
  if (!query) return items.map(item => ({ item, score: 0 }));
  const lower = query.toLowerCase();
  return items
    .map(item => ({ item, score: fuzzyScore(getText(item).toLowerCase(), lower) }))
    .filter(r => r.score > 0)
    .sort((a, b) => b.score - a.score);
}

function fuzzyScore(text: string, query: string): number {
  let score = 0;
  let qi = 0;
  let consecutive = 0;
  for (let ti = 0; ti < text.length && qi < query.length; ti++) {
    if (text[ti] === query[qi]) {
      score += 1 + consecutive;
      if (ti === qi) score += 2;
      consecutive++;
      qi++;
    } else {
      consecutive = 0;
    }
  }
  return qi === query.length ? score : 0;
}
```

### command-registry.ts (P6-3: 구체적 타입)

```typescript
import type { ShortcutDef } from './shortcuts';

export interface Command {
  id: string;
  label: string;
  category: string;
  shortcut?: string;
}

export function buildCommandList(shortcuts: ShortcutDef[]): Command[] {
  return shortcuts.map(s => ({
    id: s.id,
    label: s.label,
    category: s.category,
    shortcut: s.defaultKey,
  }));
}
```

### 테스트

```typescript
describe('fuzzySearch', () => {
  it('matches substring', () => {
    const items = [{ name: 'Split Right' }, { name: 'New Workspace' }];
    const results = fuzzySearch(items, 'spl', i => i.name);
    expect(results[0].item.name).toBe('Split Right');
  });

  it('scores consecutive matches higher', () => {
    const items = [{ name: 'abc' }, { name: 'axbxc' }];
    const results = fuzzySearch(items, 'abc', i => i.name);
    expect(results[0].item.name).toBe('abc');
  });

  it('returns all items for empty query', () => {
    const items = [{ name: 'a' }, { name: 'b' }];
    expect(fuzzySearch(items, '', i => i.name)).toHaveLength(2);
  });

  it('returns empty for no match', () => {
    const items = [{ name: 'hello' }];
    expect(fuzzySearch(items, 'xyz', i => i.name)).toHaveLength(0);
  });
});
```

---

## Task 34: 설정 UI 패널

**Files:**
- Create: `src/renderer/components/settings/SettingsPanel.tsx`
- Modify: `src/shared/shortcuts.ts` — Ctrl+, 추가
- Modify: `src/renderer/App.tsx` — settingsVisible state + 토글

7 섹션. 각 변경 → `dispatch({ type: 'settings.update', payload })`.
Escape 또는 X 버튼으로 닫기 (P6-4).

---

## Task 35: 자동 업데이트

**Files:**
- Create: `src/main/updates/update-manager.ts`
- Create: `electron-builder.yml`

**의존성:** `npm install electron-updater`

**P6-N3:** package.json에 패키징 스크립트 추가:
```json
"package": "electron-vite build && electron-builder"
```

```yaml
# electron-builder.yml
appId: com.cmux-win.app
productName: cmux-win
win:
  target: nsis
  sign: false  # 개발용. CI: CSC_LINK + CSC_KEY_PASSWORD
publish:
  provider: github
  owner: manaflow-ai
  repo: cmux-win
```

---

## Task 36: 다국어 (P6-5: ~50 핵심 키)

**Files:**
- Create: `src/renderer/i18n.ts`
- Create: `resources/locales/en.json` (~50 키)
- Create: `resources/locales/ko.json` (~50 키)
- Create: `resources/locales/ja.json` (~50 키)

**의존성:** `npm install i18next react-i18next`

초기 번역 범위: 사이드바 (Workspaces, New, Close), 설정 섹션명, 커맨드 팔레트 레이블, 에러 메시지.
나머지 ~150키는 incremental 추가.

**P6-N2:** i18n 초기화에 Suspense 비활성화:
```typescript
i18next.use(initReactI18next).init({
  react: { useSuspense: false }, // Suspense 경계 없이 동작
  // ...
});
```

---

## Task 37: 텔레메트리

**Files:**
- Create: `src/main/telemetry/telemetry-manager.ts`

**의존성:** `npm install @sentry/electron posthog-node`

옵트아웃: `settings.telemetry.enabled = false`.
Sentry DSN + PostHog API key는 환경변수 또는 빌드 시 주입.

---

## Task 38: 테마 (P6-1, P6-4 수정)

**Files:**
- Create: `src/main/terminal/theme-parser.ts`
- Create: `resources/themes/themes.json` (P6-4: 변환된 JSON 직접 번들)
- Test: `tests/unit/terminal/theme-parser.test.ts`

### theme-parser.ts (P6-1: 전체 구현)

```typescript
export interface GhosttyTheme {
  palette: Record<number, string>;
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

/** Ghostty 테마 파일 파싱: "key = value" 행 기반 */
export function parseGhosttyTheme(content: string): GhosttyTheme {
  const theme: GhosttyTheme = { palette: {}, background: '#000000', foreground: '#ffffff' };
  for (const rawLine of content.split('\n')) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    const eqIdx = line.indexOf('=');
    if (eqIdx === -1) continue;
    const key = line.slice(0, eqIdx).trim();
    const value = line.slice(eqIdx + 1).trim();
    if (key === 'palette') {
      // "palette = 0=#1d1f21"
      const innerEq = value.indexOf('=');
      if (innerEq !== -1) {
        const idx = parseInt(value.slice(0, innerEq));
        const color = value.slice(innerEq + 1);
        if (!isNaN(idx)) theme.palette[idx] = color;
      }
    } else if (key === 'background') theme.background = value;
    else if (key === 'foreground') theme.foreground = value;
    else if (key === 'cursor-color') theme.cursor_color = value;
    else if (key === 'selection-background') theme.selection_background = value;
    else if (key === 'selection-foreground') theme.selection_foreground = value;
  }
  return theme;
}

/** Ghostty → xterm.js ITheme 변환 */
export function ghosttyToXterm(ghostty: GhosttyTheme): Record<string, string> {
  const result: Record<string, string> = {
    background: ghostty.background,
    foreground: ghostty.foreground,
  };
  if (ghostty.cursor_color) result.cursor = ghostty.cursor_color;
  if (ghostty.selection_background) result.selectionBackground = ghostty.selection_background;
  if (ghostty.selection_foreground) result.selectionForeground = ghostty.selection_foreground;
  for (const [index, color] of Object.entries(ghostty.palette)) {
    const xtermKey = ANSI_TO_XTERM[Number(index)];
    if (xtermKey) result[xtermKey] = color;
  }
  return result;
}
```

### 테스트

```typescript
describe('parseGhosttyTheme', () => {
  it('parses background and foreground');
  it('parses palette entries');
  it('parses cursor-color');
  it('skips comments and empty lines');
});

describe('ghosttyToXterm', () => {
  it('maps palette 0 to black');
  it('maps palette 1 to red');
  it('maps palette 8 to brightBlack');
  it('includes cursor and selection colors');
  it('handles empty palette');
});
```

### P6-4: 테마 JSON 번들

cmux-win은 ghostty 서브모듈이 없으므로, 몇 개의 인기 테마를 직접 `resources/themes/themes.json`에 포함:

```json
{
  "Dracula": { "background": "#282a36", "foreground": "#f8f8f2", ... },
  "Solarized Dark": { ... },
  "One Dark": { ... },
  "Gruvbox Dark": { ... },
  "Nord": { ... }
}
```

초기 5개 테마. 나머지는 incremental 추가 또는 빌드 스크립트로 upstream에서 변환.

---

## Task 39: 접근성

**Files:**
- Modify: `src/renderer/components/sidebar/Sidebar.tsx` — role, aria-label
- Modify: `src/renderer/components/sidebar/WorkspaceItem.tsx` — role
- Modify: `src/renderer/components/panels/PanelContainer.tsx` — role, aria-label
- Modify: `src/renderer/components/terminal/XTermWrapper.tsx` — screenReaderMode

```typescript
// Sidebar: role="navigation" aria-label="Workspaces"
// WorkspaceItem: role="option" aria-selected={isActive}
// PanelContainer: role="region" aria-label={`Panel: ${panel.panelType}`}
// XTermWrapper: if settings.accessibility.screenReaderMode →
//   terminal.options.screenReaderMode = true
```

접근성 자동 스캔(axe-core)은 E2E 환경이 필요하므로 CI 설정과 함께 별도 추가.

---

## Phase 6 완료 체크리스트

```
[ ] AppUserModelID 설정 (Toast 필수)
[ ] Windows Toast 알림 + Tray 뱃지
[ ] 커맨드 팔레트: Ctrl+Shift+P, fuzzySearch, 화살표 탐색
[ ] 설정 UI: 7 섹션, Escape/X 닫기
[ ] 자동 업데이트: electron-updater + electron-builder.yml
[ ] 다국어: ~50 핵심 키 (ko/en/ja)
[ ] 텔레메트리: Sentry + PostHog (옵트아웃)
[ ] 테마: parseGhosttyTheme + ghosttyToXterm + 5개 번들 테마
[ ] 접근성: ARIA roles, screenReaderMode
[ ] 전체 테스트 ALL PASS
```
