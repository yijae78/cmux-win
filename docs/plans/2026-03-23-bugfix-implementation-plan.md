# 버그 수정 구현계획 v2: 디바이더 리사이즈 + CLI 실행

> **설계안 정본**: `2026-03-23-bugfix-divider-cli-plan.md`
> **성찰 반영**: v1 대비 3건 보완 (activator button 체크, passthrough 무한루프 차단, require 위치)

---

## 성찰 반영 사항

| # | v1 결함 | v2 수정 |
|---|--------|---------|
| S1 | FilteredMouseSensor activator가 `button === 0` 미체크 → 우클릭 드래그 가능 | activator handler에 `nativeEvent.button !== 0` 가드 추가 |
| S2 | `passthrough()`에서 `findRealClaude() \|\| 'claude'` → Claude 미설치 시 무한 루프 | null이면 에러 메시지 출력 후 `process.exit(127)` |
| S3 | `fs`, `os`를 함수 내부에서 매번 require | 파일 상단에서 1회만 require |

---

## Task B1: FilteredMouseSensor 커스텀 센서 구현

**File:** `src/renderer/components/panels/PanelLayout.tsx`

### 변경 1: import 정리

```typescript
// 기존 — MouseSensor를 직접 사용
import {
  DndContext,
  DragOverlay,
  MouseSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';

// 변경 — MouseSensor를 커스텀 센서의 부모로만 사용
import {
  DndContext,
  DragOverlay,
  MouseSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
// (import는 동일하지만 MouseSensor를 직접 useSensor에 전달하지 않음)
```

### 변경 2: FilteredMouseSensor 클래스 정의 (import 직후)

```typescript
/**
 * FilteredMouseSensor — data-no-dnd="true" 요소에서 시작된 이벤트를 무시.
 * PanelDivider가 @dnd-kit과 충돌하지 않도록 함.
 *
 * S1: button === 0 (좌클릭만) 체크 포함 — MouseSensor 기본 동작 유지.
 */
class FilteredMouseSensor extends MouseSensor {
  static activators = [
    {
      eventName: 'onMouseDown' as const,
      handler: ({ nativeEvent }: { nativeEvent: MouseEvent }) => {
        // S1: 좌클릭만 허용 (MouseSensor 기본 동작)
        if (nativeEvent.button !== 0) return false;

        // data-no-dnd="true" 요소에서 시작된 이벤트 무시 (PanelDivider 보호)
        let el = nativeEvent.target as HTMLElement | null;
        while (el) {
          if (el.dataset?.noDnd === 'true') return false;
          el = el.parentElement;
        }
        return true;
      },
    },
  ];
}
```

### 변경 3: sensor 생성 코드

```typescript
// 기존
const mouseSensor = useSensor(MouseSensor, {
  activationConstraint: { distance: 5 },
});

// 변경
const mouseSensor = useSensor(FilteredMouseSensor, {
  activationConstraint: { distance: 5 },
});
```

### 변경 4: 미사용 코드 삭제

`shouldHandleEvent` 콜백 정의 전체 삭제 (사용되지 않으므로):

```typescript
// 삭제 대상:
const shouldHandleEvent = useCallback((element: Element | null) => {
  while (element) {
    if ((element as HTMLElement).dataset?.noDnd === 'true') return false;
    element = element.parentElement;
  }
  return true;
}, []);
```

### 검증 항목

- [ ] 디바이더 마우스 호버 → col-resize/row-resize 커서
- [ ] 디바이더 좌클릭 드래그 → 패널 비율 변경
- [ ] 디바이더 우클릭 → 드래그 발동 안됨 (S1)
- [ ] ☰ 핸들 좌클릭 드래그 → 패널 이동 정상
- [ ] 3개 패널 분할 후 각 디바이더 독립 동작

---

## Task B2: findRealClaude + passthrough 무한루프 차단

**File:** `resources/bin/claude-wrapper-lib.js`

### 변경 1: 파일 상단 require 추가 (S3)

```javascript
// 기존
const path = require('path');

// 변경
const path = require('path');
const fs = require('fs');
const os = require('os');
```

### 변경 2: findRealClaude 함수 전체 교체

```javascript
/**
 * 실제 claude 바이너리 찾기.
 *
 * 자기 자신 제외 방식: 경로 문자열 비교 대신 claude-wrapper.js 파일 존재 여부로
 * 래퍼 디렉토리를 식별. OneDrive 한글 경로의 Unicode NFC/NFD 불일치를 회피.
 *
 * @param {string} myDir - 현재 wrapper가 있는 디렉토리 (사용하지 않지만 API 호환 유지)
 * @param {function} execSyncFn - child_process.execSync (테스트용 DI)
 * @returns {string|null}
 */
function findRealClaude(myDir, execSyncFn) {
  const candidates = [];

  // 1. where claude (PATH 검색)
  try {
    const result = execSyncFn('where claude 2>nul', { encoding: 'utf8' })
      .trim().split(/\r?\n/);
    candidates.push(...result.map(s => s.trim()).filter(Boolean));
  } catch { /* where failed */ }

  // 2. 직접 경로 탐색 (where 실패 또는 PATH 미등록 대비)
  const homedir = os.homedir();
  const appData = process.env.APPDATA || path.join(homedir, 'AppData', 'Roaming');
  const localAppData = process.env.LOCALAPPDATA || path.join(homedir, 'AppData', 'Local');

  const directPaths = [
    path.join(homedir, '.local', 'bin', 'claude.exe'),
    path.join(appData, 'npm', 'claude.cmd'),
    path.join(homedir, 'scoop', 'shims', 'claude.cmd'),
    path.join(localAppData, 'Programs', 'claude', 'claude.exe'),
  ];
  for (const p of directPaths) {
    if (fs.existsSync(p) && !candidates.includes(p)) candidates.push(p);
  }

  // 3. 자기 자신 제외 — claude-wrapper.js 마커 파일로 래퍼 디렉토리 식별
  for (const p of candidates) {
    if (!p) continue;
    const dir = path.dirname(p);
    const wrapperMarker = path.join(dir, 'claude-wrapper.js');
    if (fs.existsSync(wrapperMarker)) continue; // 래퍼 디렉토리 → 건너뜀
    return p;
  }
  return null;
}
```

### 변경 3: passthrough 무한루프 차단 (S2)

**File:** `resources/bin/claude-wrapper.js`

```javascript
// 기존
function passthrough() {
  const real = findRealClaude(
    __dirname,
    require('child_process').execSync,
  ) || 'claude';
  const child = spawnChild(real, args, { stdio: 'inherit' });
  child.on('exit', (code) => process.exit(code ?? 0));
  child.on('error', (err) => {
    process.stderr.write(`cmux-win: claude not found: ${err.message}\n`);
    process.exit(127);
  });
}

// 변경
function passthrough() {
  const real = findRealClaude(
    __dirname,
    require('child_process').execSync,
  );
  // S2: Claude 미설치 시 무한 루프 방지
  if (!real) {
    process.stderr.write(
      'cmux-win: Claude Code not found.\n' +
      'Install: npm install -g @anthropic-ai/claude-code\n' +
      'Or download from: https://claude.ai/download\n'
    );
    process.exit(127);
    return;
  }
  const child = spawnChild(real, args, { stdio: 'inherit' });
  child.on('exit', (code) => process.exit(code ?? 0));
  child.on('error', (err) => {
    process.stderr.write(`cmux-win: failed to start claude: ${err.message}\n`);
    process.exit(127);
  });
}
```

### 검증 항목

- [ ] cmux-win 터미널에서 `claude` → Claude Code 시작
- [ ] `claude --version` → 버전 출력 (무한 루프 아님)
- [ ] `claude mcp` → passthrough bypass 정상
- [ ] Claude 미설치 환경 → 에러 메시지 출력 + exit 127 (S2)
- [ ] CMUX_SURFACE_ID 없는 일반 터미널 → passthrough 정상
- [ ] `where claude` 실패 시 → 직접 경로 탐색으로 fallback

---

## 실행 순서

```
B1 (FilteredMouseSensor)  ─┐
                            ├→ 동시 구현 가능
B2 (findRealClaude)       ─┘

→ esbuild 빌드 (main + preload)
→ 세션 초기화
→ 앱 실행
→ 수동 테스트:
   1. Split Right → 디바이더 드래그 → 크기 변경 확인
   2. 터미널에서 claude 입력 → 실행 확인
```

## 완료 체크리스트

```
[ ] B1: FilteredMouseSensor 클래스 정의 (button===0 + data-no-dnd 체크)
[ ] B1: useSensor(FilteredMouseSensor) 적용
[ ] B1: 미사용 shouldHandleEvent 콜백 삭제
[ ] B2: 파일 상단 fs/os require 추가
[ ] B2: findRealClaude() marker file 방식으로 전체 교체
[ ] B2: passthrough() 무한루프 차단 (null → 에러 + exit)
[ ] B2: 직접 경로에 중복 제거 (candidates.includes 체크)
[ ] 빌드 성공 (esbuild main + preload)
[ ] 디바이더 리사이즈 동작 확인
[ ] claude CLI 실행 확인
```
