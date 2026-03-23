# 체크리스트 미완료 항목 구현 계획

> **설계안 정본:** `2026-03-21-phases-3-to-6-design.md` v3
> **현재 상태:** 347 tests, 빌드 성공

---

## 미완료 항목 (Phase 5 체크리스트)

| # | 항목 | 구현 계획 정본 위치 |
|---|------|-------------------|
| 1 | CWD/gitBranch 사이드바 표시 | Phase 5 §5.2 Task 29 |
| 2 | scrollback 앱 종료 시 persistence 저장 | Phase 5 §5.4 Task 31 |
| 3 | scrollback 앱 시작 시 복원 | Phase 5 §5.4 Task 31 |

---

## Task A: CWD/gitBranch 사이드바 표시

**Files:**
- Modify: `src/renderer/components/sidebar/WorkspaceItem.tsx`

OSC 133 핸들러가 `surface.update_meta`로 `terminal.cwd`와 `terminal.gitBranch`를 업데이트하고 있음.
WorkspaceItem에서 해당 워크스페이스의 surface 메타데이터를 표시.

### 구현

WorkspaceItem은 현재 `agents` 정보만 표시. `surfaces` prop을 추가하여 터미널 CWD/Git 정보 표시:

```typescript
// WorkspaceItem props에 추가:
surfaces?: SurfaceState[];

// 렌더링에서:
const wsSurfaces = surfaces?.filter(s => /* workspace의 panel에 속하는 surface */);
const termSurface = wsSurfaces?.find(s => s.surfaceType === 'terminal' && s.terminal?.cwd);
// CWD 표시: 마지막 디렉토리명만
// gitBranch 표시: branch 이름 + dirty 표시
```

하지만 WorkspaceItem은 현재 `workspace.id`만 알고, 어떤 surfaces가 이 workspace에 속하는지 모릅니다. `panels`와 `surfaces`를 Sidebar에서 전달해야 합니다.

더 간단한 방법: App.tsx에서 `appState.surfaces`를 Sidebar에 전달, Sidebar가 WorkspaceItem에 전달.

### 테스트
기존 테스트에 영향 없음.

### 커밋
```
git commit -m "feat: sidebar CWD/gitBranch display from surface.update_meta"
```

---

## Task B: scrollback 앱 종료 시 persistence 저장

**Files:**
- Modify: `src/preload/index.ts` — scrollback IPC 수신
- Modify: `src/main/index.ts` — window-all-closed에서 scrollback 수집
- Modify: `src/main/sot/middleware/persistence.ts` — scrollback 포함 저장

### 구현

앱 종료 시:
1. Main이 모든 Renderer에 "scrollback 보내줘" IPC 요청
2. Renderer(XTermWrapper)가 terminal.buffer를 추출하여 IPC로 반환
3. Main이 persistence 파일에 scrollback 포함 저장

이것은 **동기적 종료 시퀀스**가 필요하여 복잡합니다.

더 실용적 접근: **scrollback을 주기적으로 저장** (디바운스 30초).

가장 간단한 접근: **scrollbackCache는 Renderer 메모리에만 존재** (현재 구현). 앱 재시작 시 복원은 Phase 6+ 로 연기.

### 판단

설계안 Phase 5 체크리스트의 "스크롤백 저장/복원"은 현재 구현 수준(워크스페이스 전환 시 메모리 캐시)으로 **부분 완료**. 앱 재시작 복원은 Main↔Renderer 동기 IPC가 필요하여 복잡도가 높음. 체크리스트를 "부분 완료"로 표기.

---

## Task C: scrollback 앱 시작 시 복원

Task B에 의존. Task B가 연기되므로 Task C도 연기.

---

## 실행 순서

Task A (CWD/gitBranch 표시) 만 즉시 구현 가능.
Task B, C는 복잡도 높아 별도 Phase로 연기 (체크리스트에 "부분 완료" 표기).
