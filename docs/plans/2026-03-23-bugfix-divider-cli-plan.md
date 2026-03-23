# 버그 수정 설계계획: 디바이더 리사이즈 + CLI 실행

> **작성일**: 2026-03-23
> **진단 결과 기반**: 심층 코드 추적 분석

---

## 버그 1: 패널 디바이더 리사이즈 안됨

### 근본 원인

`PanelLayout.tsx` line 326에서 `DndContext`에 `shouldHandleEvent` 콜백이 **정의만 되고 전달되지 않음**.

```typescript
// line 244-250: 정의됨
const shouldHandleEvent = useCallback((element: Element | null) => {
  while (element) {
    if ((element as HTMLElement).dataset?.noDnd === 'true') return false;
    element = element.parentElement;
  }
  return true;
}, []);

// line 326-332: DndContext에 전달 안됨!
<DndContext
  sensors={sensors}
  onDragStart={handleDragStart}
  onDragOver={handleDragOver}
  onDragEnd={handleDragEnd}
  onDragCancel={handleDragCancel}
>  // ← shouldHandleEvent 없음!
```

**결과**: `@dnd-kit`의 MouseSensor가 디바이더 위의 mousedown도 감지하여 드래그로 인식 시도. 디바이더의 `e.stopImmediatePropagation()`이 있지만, @dnd-kit은 capture phase에서 이벤트를 먼저 가져갈 수 있음.

### 수정 방안

**방안 A (추천): @dnd-kit의 MouseSensor에서 직접 필터링**

`@dnd-kit`의 `MouseSensor`는 `shouldHandleEvent` prop을 DndContext에서 받지 않음 (이것은 @dnd-kit API에 없는 prop). 대신 **커스텀 센서**를 만들어야 함:

```typescript
class FilteredMouseSensor extends MouseSensor {
  static activators = [
    {
      eventName: 'onMouseDown' as const,
      handler: ({ nativeEvent }: { nativeEvent: MouseEvent }) => {
        // data-no-dnd가 있는 요소에서 시작된 이벤트는 무시
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

이 커스텀 센서를 `useSensor(FilteredMouseSensor, { activationConstraint: { distance: 5 } })`로 사용.

**방안 B (대안): DndContext를 PanelDivider를 감싸지 않게 구조 변경**

CSS Grid에서 divider가 DndContext 내부에 있기 때문에 센서가 감지함. divider를 DndContext 밖으로 빼는 것은 구조적으로 불가능 (Grid의 중간 요소이므로).

**결론: 방안 A 채택**

### 수정 파일

| 파일 | 변경 |
|------|------|
| `src/renderer/components/panels/PanelLayout.tsx` | `MouseSensor` → `FilteredMouseSensor` 커스텀 센서 |

### 테스트 항목

- [ ] 2개 패널 분할 후 디바이더 좌우 드래그 → ratio 변경
- [ ] 3개 패널 분할 후 각 디바이더 독립 동작
- [ ] 디바이더 드래그 중 DnD(패널 이동)가 발동하지 않음
- [ ] ☰ 핸들 드래그 시 패널 이동은 정상 동작

---

## 버그 2: Claude CLI 실행 안됨

### 근본 원인

`findRealClaude()` 함수에서 **OneDrive 한글 경로의 Unicode normalization 불일치**.

```javascript
// claude-wrapper-lib.js line 78-83
const myDirNorm = myDir.toLowerCase().replace(/\\/g, '/');
for (const p of candidates) {
  const dir = path.dirname(p).toLowerCase().replace(/\\/g, '/');
  if (dir !== myDirNorm) return p;  // ← 한글 NFC/NFD 차이로 항상 불일치!
}
```

**문제 흐름**:
1. PTY 환경에서 PATH 앞에 `resources/bin` 추가 (`CMUX_BIN_DIR`)
2. 사용자가 `claude` 입력 → `resources/bin/claude.cmd` 먼저 발견
3. `claude.cmd` → `node claude-wrapper.js` 실행
4. `findRealClaude()` → `where claude` 실행
5. `where` 결과: `resources/bin/claude.cmd` (1순위) + `~/.local/bin/claude.exe` (2순위)
6. 자기 자신(`resources/bin`) 제외 시도
7. **`__dirname`과 `where` 출력의 한글 인코딩(NFC vs NFD) 불일치로 제외 실패**
8. 래퍼가 자기 자신을 반환 → 무한 루프 또는 실패

### 수정 방안

**방안 A (추천): 경로 비교 대신 파일명 기반 제외**

한글 경로 비교를 완전히 회피:

```javascript
function findRealClaude(myDir, execSyncFn) {
  const candidates = [];

  // 1. where claude
  try {
    const result = execSyncFn('where claude 2>nul', { encoding: 'utf8' })
      .trim().split(/\r?\n/).map(s => s.trim()).filter(Boolean);
    candidates.push(...result);
  } catch {}

  // 2. 직접 경로 탐색 (where 실패 대비)
  const directPaths = [
    path.join(os.homedir(), '.local', 'bin', 'claude.exe'),
    path.join(appData, 'npm', 'claude.cmd'),
    // ... 기타
  ];
  for (const p of directPaths) {
    if (fs.existsSync(p)) candidates.push(p);
  }

  // 3. 자기 자신 제외 — 경로 비교 대신 파일이 claude-wrapper.js인지 확인
  for (const p of candidates) {
    const trimmed = p.trim();
    if (!trimmed) continue;

    // claude-wrapper.js가 같은 디렉토리에 있으면 래퍼임
    const dir = path.dirname(trimmed);
    const wrapperPath = path.join(dir, 'claude-wrapper.js');
    if (fs.existsSync(wrapperPath)) continue;  // 래퍼 디렉토리 → 건너뜀

    return trimmed;
  }
  return null;
}
```

**핵심**: 한글 경로 문자열 비교를 하지 않고, 해당 디렉토리에 `claude-wrapper.js`가 존재하는지로 자기 자신을 식별.

**방안 B (대안): Unicode normalize 후 비교**

```javascript
const normalize = (s) => s.normalize('NFC').toLowerCase().replace(/\\/g, '/');
```

이 방법은 대부분 동작하지만 Edge case(OneDrive 가상 경로, 심볼릭 링크 등)에서 실패할 수 있음.

**결론: 방안 A 채택** (더 견고함)

### 수정 파일

| 파일 | 변경 |
|------|------|
| `resources/bin/claude-wrapper-lib.js` | `findRealClaude()` 자기 자신 제외 로직 변경 |

### 테스트 항목

- [ ] cmux-win 터미널에서 `claude` 입력 → Claude Code 실행
- [ ] `claude --version` → 버전 출력 (무한 루프 아님)
- [ ] `claude mcp` → passthrough (bypass 명령)
- [ ] CMUX_SURFACE_ID 없는 일반 터미널에서 `claude` → passthrough

---

## 실행 순서

1. Bug 1 (디바이더) → FilteredMouseSensor 구현
2. Bug 2 (CLI) → findRealClaude 자기 자신 제외 로직 변경
3. 빌드 + 테스트
