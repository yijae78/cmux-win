# cmux-win Socket API 전체 분석 (Round 1)

> **Worker1(Claude) | 2026-06-17**
> **소스 경로**: `/c/dev/cmux-win/src/main/socket/`
> **원본 수정**: 없음 (읽기 전용 분석)

---

## 1. 아키텍처 개요

### 프로토콜
- **JSON-RPC 2.0** over **TCP** (newline-delimited)
- 서버: `server.ts` — `net.createServer`, 127.0.0.1 바인딩
- 라우터: `router.ts` — `JsonRpcRouter` 클래스, `Map<string, RpcHandler>` 기반

### 인증 체계 (`auth.ts`)
5단계 인증 모드:

| 모드 | 설명 | 허용 메서드 |
|------|------|------------|
| `off` | API 비활성화, 모든 연결 거부 | 없음 |
| `cmux-only` | 공유 토큰 검증 | system.*, workspace.*, surface.*, panel.*, window.*, notification.*, agent.*, workflow.* |
| `automation` | 토큰 검증 + browser.* 허용 | 전체 |
| `password` | 비밀번호 인증 | 전체 |
| `allow-all` | 인증 없음 | 전체 |

### 특수 메서드
- `auth.handshake` — 라우터에 등록되지 않음. `server.ts`에서 인라인 처리 (인증 후 `{ok: true}` 응답)

### 보안 기능
- TCP keepalive 30초 (`server.ts:80`)
- 버퍼 10MB 제한 — OOM 방지 (`server.ts:90`)
- 토큰은 `process.env.CMUX_SOCKET_TOKEN`으로 자식 프로세스에 주입 (`server.ts:23`)

---

## 2. 전체 API 메서드 목록 (10개 도메인, 53개 메서드)

### 2.1 auth (1개) — `server.ts` 인라인

| # | 메서드 | params | 반환값 | 비고 |
|---|--------|--------|--------|------|
| 1 | `auth.handshake` | `{ token: string }` | `{ ok: true }` | 라우터 미등록, server.ts L111에서 직접 처리 |

### 2.2 system (4개) — `handlers/system.ts`

| # | 메서드 | params | 반환값 | 비고 |
|---|--------|--------|--------|------|
| 2 | `system.ping` | 없음 | `{ pong: true, timestamp }` | 헬스체크 |
| 3 | `system.identify` | `{ surfaceId?: string }` | `{ name, version, platform, caller? }` | L3: surfaceId 전달 시 caller 컨텍스트 포함 |
| 4 | `system.tree` | 없음 | `{ workspaces: [...], focus }` | L3: 전체 토폴로지 스냅샷 |
| 5 | `system.capabilities` | 없음 | `{ methods: string[] }` | 등록된 전체 메서드 목록 반환 |

### 2.3 panel (6개) — `handlers/panel.ts`

| # | 메서드 | params | 반환값 | 비고 |
|---|--------|--------|--------|------|
| 6 | `panel.list` | 없음 | `{ panels: Panel[] }` | |
| 7 | `panel.focus` | `{ panelId: string }` | `{ ok: true }` | |
| 8 | `panel.split` | `{ panelId, direction, newPanelType?, url?, filePath? }` | `{ ok, paneIndex, panelId, surfaceId }` | GAP-3: 새 패널 정보 반환. L4: url/filePath 지원 |
| 9 | `panel.resize` | `{ panelId, ratio: number }` | `{ ok: true }` | |
| 10 | `panel.zoom` | `{ panelId: string }` | `{ ok: true }` | |
| 11 | `panel.close` | `{ panelId: string }` | `{ ok: true }` | BUG-18: 연관 surface 정리 |

### 2.4 surface (8개) — `handlers/surface.ts`

| # | 메서드 | params | 반환값 | 비고 |
|---|--------|--------|--------|------|
| 12 | `surface.list` | 없음 | `{ surfaces: Surface[] }` | |
| 13 | `surface.create` | `{ panelId, surfaceType? }` | `{ surface }` | surfaceType: terminal/browser/markdown |
| 14 | `surface.close` | `{ surfaceId: string }` | `{ ok: true }` | |
| 15 | `surface.focus` | `{ surfaceId: string }` | `{ ok: true }` | |
| 16 | `surface.send_text` | `{ surfaceId, text: string }` | `{ ok: true }` | #4: PTY 없으면 에러 반환 |
| 17 | `surface.rename` | `{ surfaceId, label: string }` | `{ ok: true }` | 커스텀 라벨 설정 |
| 18 | `surface.read` | `{ surfaceId, lines?: number }` | `{ content: string }` | R6/BUG-D: live PTY 버퍼 우선, ANSI 스트립 |
| 19 | `surface.health` | `{ surfaceId: string }` | `{ surfaceId, surfaceType, title, hasPty, bufferSize, terminal, agent }` | L3: PTY 상태 + 에이전트 정보 |

### 2.5 workspace (7개) — `handlers/workspace.ts`

| # | 메서드 | params | 반환값 | 비고 |
|---|--------|--------|--------|------|
| 20 | `workspace.list` | 없음 | `{ workspaces: Workspace[] }` | |
| 21 | `workspace.current` | 없음 | `{ workspace }` | 활성 워크스페이스 반환 |
| 22 | `workspace.create` | `{ windowId, name?, cwd? }` | `{ workspace }` | |
| 23 | `workspace.select` | `{ workspaceId: string }` | `{ ok: true }` | |
| 24 | `workspace.close` | `{ workspaceId: string }` | `{ ok: true }` | |
| 25 | `workspace.set_layout` | `{ workspaceId, panelLayout }` | `{ ok: true }` | panelLayout: 트리 구조 |
| 26 | `workspace.rename` | `{ workspaceId, name: string }` | `{ ok: true }` | |

### 2.6 window (5개) — `handlers/window.ts`

| # | 메서드 | params | 반환값 | 비고 |
|---|--------|--------|--------|------|
| 27 | `window.list` | 없음 | `{ windows: Window[] }` | |
| 28 | `window.current` | 없음 | `{ window }` | |
| 29 | `window.create` | `{ geometry?: {x,y,width,height} }` | `{ window }` | |
| 30 | `window.move` | `{ x, y, width?, height? }` | `{ ok, bounds }` | Electron BrowserWindow 직접 조작 |
| 31 | `window.close` | `{ windowId: string }` | `{ ok: true }` | |

### 2.7 agent (8개) — `handlers/agent.ts`

| # | 메서드 | params | 반환값 | 비고 |
|---|--------|--------|--------|------|
| 32 | `agent.spawn` | `{ agentType, workspaceId, task? }` | `{ ok, paneIndex, panelId, surfaceId }` | GAP-3: 새 패널 정보 반환 |
| 33 | `agent.session_start` | `{ sessionId, agentType, workspaceId, surfaceId, pid? }` | `{ ok: true }` | agentType: claude/codex/gemini/opencode |
| 34 | `agent.status_update` | `{ sessionId, status, icon?, color? }` | `{ ok: true }` | status: running/idle/needs_input/done/error |
| 35 | `agent.session_end` | `{ sessionId: string }` | `{ ok: true }` | |
| 36 | `agent.send_task` | `{ surfaceId, task: string }` | `{ ok, surfaceId }` | B3: send lock (30s TTL). 텍스트+500ms딜레이+Enter |
| 37 | `agent.rerun` | `{ surfaceId, task, agentType? }` | `{ ok, surfaceId, mode }` | B4: interactive 우선, relaunch 폴백. mode: interactive/relaunch |
| 38 | `agent.wait` | `{ surfaceId, timeout? }` | `{ exitCode, elapsed, timeout }` | L10: PTY exit 대기. 기본 5분 |
| 39 | `agent.output` | `{ surfaceId, lines? }` | `{ content: string }` | L10: 에이전트 출력 읽기. 기본 50줄 |

### 2.8 notification (3개) + telegram (4개) — `handlers/notification.ts`

| # | 메서드 | params | 반환값 | 비고 |
|---|--------|--------|--------|------|
| 40 | `notification.create` | `{ title, subtitle?, body?, workspaceId?, surfaceId? }` | `{ notification }` | |
| 41 | `notification.list` | 없음 | `{ notifications }` | |
| 42 | `notification.clear` | `{ workspaceId? }` | `{ ok: true }` | 특정 워크스페이스만 또는 전체 |
| 43 | `telegram.set_token` | `{ token: string }` | `{ ok: true }` | C4: safeStorage 암호화 저장 |
| 44 | `telegram.get_token_status` | 없음 | `{ hasToken: boolean }` | |
| 45 | `telegram.delete_token` | 없음 | `{ ok: true }` | |
| 46 | `telegram.test` | 없음 | `{ ok, message }` | 토큰+chatId 존재 확인 |

### 2.9 browser (11개) — `handlers/browser.ts`

| # | 메서드 | params | 반환값 | 비고 |
|---|--------|--------|--------|------|
| 47 | `browser.eval` | `{ surfaceId, code: string }` | `{ ok, result }` | webview에서 JS 실행 |
| 48 | `browser.snapshot` | `{ surfaceId: string }` | `{ ok, snapshot }` | DOM HTML 스냅샷 |
| 49 | `browser.screenshot` | `{ surfaceId, format? }` | `{ ok, format, data, note }` | 현재 HTML만 (이미지 캡처 미구현) |
| 50 | `browser.click` | `{ surfaceId, ref: string }` | `{ ok: true }` | data-cmux-ref 셀렉터 |
| 51 | `browser.type` | `{ surfaceId, text: string }` | `{ ok: true }` | activeElement에 텍스트 입력 |
| 52 | `browser.fill` | `{ surfaceId, ref, value? }` | `{ ok: true }` | ref 요소에 값 설정 |
| 53 | `browser.press` | `{ surfaceId, key: string }` | `{ ok: true }` | 키보드 이벤트 발생 |
| 54 | `browser.wait` | `{ surfaceId, selector?, timeout? }` | `{ ok: true }` | MutationObserver 기반 대기 |
| 55 | `browser.navigate` | `{ surfaceId, url: string }` | `{ ok: true }` | L7: URL 이동 |
| 56 | `browser.url.get` | `{ surfaceId: string }` | `{ url }` | 현재 URL 반환 |
| 57 | `browser.title.get` | `{ surfaceId: string }` | `{ title }` | 페이지 타이틀 반환 |

### 2.10 settings (2개) — `handlers/settings.ts`

| # | 메서드 | params | 반환값 | 비고 |
|---|--------|--------|--------|------|
| 58 | `settings.get` | 없음 | `{ settings }` | 전체 설정 반환 |
| 59 | `settings.update` | `{ [key]: value, ... }` | `{ settings }` | BUG-18: 부분 머지 |

### 2.11 workflow (1개) — `handlers/workflow.ts`

| # | 메서드 | params | 반환값 | 비고 |
|---|--------|--------|--------|------|
| 60 | `workflow.run` | `{ name?, workspaceId?, steps: [{agent, task, cwd?}], timeout? }` | `{ name, stepsCompleted, stepsTotal, results }` | 다단계 에이전트 워크플로우 실행. 에이전트 spawn → idle 대기 반복 |

---

## 3. 마스터 사용 중 vs 미사용 메서드 분류

### 마스터가 사용 중인 메서드 (9개)

| 메서드 | 도메인 | 용도 |
|--------|--------|------|
| `auth.handshake` | auth | 소켓 연결 인증 |
| `panel.list` | panel | 패널 목록 조회 |
| `panel.split` | panel | 새 패널 생성 (tmux split-window 대체) |
| `panel.close` | panel | 패널 닫기 |
| `surface.list` | surface | 서피스 목록 조회 |
| `surface.read` | surface | 터미널 화면 읽기 (tmux capture-pane 대체) |
| `surface.rename` | surface | 패널 라벨 설정 |
| `workspace.list` | workspace | 워크스페이스 목록 |
| `workspace.set_layout` | workspace | 패널 레이아웃/균등분할 |

### 마스터가 미사용 중인 메서드 (51개)

#### 즉시 활용 가능 (마스터 워크플로우 개선 잠재력 높음)

| 메서드 | 잠재 활용 | 우선순위 |
|--------|----------|---------|
| `system.ping` | fleet 헬스체크 자동화 | **높음** |
| `system.tree` | 전체 토폴로지 1회 호출로 파악 (list 3회 → tree 1회) | **높음** |
| `system.identify` | 워커 자기 위치 파악 | **높음** |
| `system.capabilities` | 사용 가능 메서드 동적 확인 | 중간 |
| `surface.health` | PTY 상태 + 에이전트 상태 통합 조회 | **높음** |
| `surface.send_text` | send-keys 대체 (직접 텍스트 전송) | **높음** |
| `agent.spawn` | tmux split-window + CLI 실행을 1회 호출로 통합 | **높음** |
| `agent.send_task` | 에이전트에 후속 작업 전송 (send-keys 대체, lock 내장) | **높음** |
| `agent.wait` | 에이전트 완료 대기 (폴링 불필요) | **높음** |
| `agent.output` | 에이전트 출력 읽기 (surface.read + ANSI 스트립) | **높음** |
| `agent.status_update` | 에이전트 상태 수동 갱신 | 중간 |
| `agent.rerun` | 에이전트 재실행 (interactive 우선) | 중간 |
| `workspace.current` | 활성 워크스페이스 직접 조회 | 중간 |
| `workspace.rename` | 워크스페이스 이름 변경 | 낮음 |
| `workflow.run` | 다단계 워크플로우 JSON 실행 | **높음** |
| `notification.create` | 작업 완료 알림 | 중간 |

#### 특수 용도 (조건부 필요)

| 메서드 | 설명 |
|--------|------|
| `panel.focus` | 패널 포커스 전환 |
| `panel.resize` | 패널 크기 조정 (set_layout 보다 세밀) |
| `panel.zoom` | 패널 줌 (최대화) |
| `surface.create` | 패널 내 서피스 추가 생성 |
| `surface.close` | 서피스 닫기 |
| `surface.focus` | 서피스 포커스 전환 |
| `workspace.create` | 새 워크스페이스 생성 |
| `workspace.select` | 워크스페이스 전환 |
| `workspace.close` | 워크스페이스 닫기 |
| `window.list` / `window.current` / `window.create` / `window.move` / `window.close` | 윈도우 관리 (다중 윈도우) |
| `agent.session_start` / `agent.session_end` | 에이전트 세션 수동 관리 |
| `notification.list` / `notification.clear` | 알림 조회/삭제 |
| `telegram.*` (4개) | 텔레그램 봇 토큰 관리 |
| `settings.get` / `settings.update` | 설정 조회/변경 |
| `browser.*` (11개) | 브라우저 패널 자동화 (eval, click, type, navigate 등) |

---

## 4. 라우팅 구조 분석

### 등록 흐름
```
server.ts (TCP 서버)
  └→ auth.ts (인증 5단계)
  └→ router.ts (JsonRpcRouter)
       ├→ handlers/system.ts      → registerSystemHandlers()
       ├→ handlers/panel.ts       → registerPanelHandlers()
       ├→ handlers/surface.ts     → registerSurfaceHandlers()
       ├→ handlers/workspace.ts   → registerWorkspaceHandlers()
       ├→ handlers/window.ts      → registerWindowHandlers()
       ├→ handlers/agent.ts       → registerAgentHandlers()
       ├→ handlers/notification.ts→ registerNotificationHandlers()
       ├→ handlers/browser.ts     → registerBrowserHandlers()
       ├→ handlers/settings.ts    → registerSettingsHandlers()
       └→ handlers/workflow.ts    → registerWorkflowHandlers()
```

### 라우터 설계 특징
- **단일 Map 기반**: `Map<string, RpcHandler>` — 평면 네임스페이스, 도메인 접두사로 논리 분리
- **동기/비동기 통합**: 핸들러는 `unknown | Promise<unknown>` 반환, 라우터가 자동 await
- **에러 코드**: JSON-RPC 2.0 표준 (-32700, -32600, -32601, -32603)
- **메서드 열거**: `getMethods()` → `system.capabilities`에서 활용

### 인증 흐름 (server.ts)
```
TCP 연결
  → 첫 메시지로 인증
    → auth.handshake이면 {ok:true} 응답 후 대기
    → 일반 RPC이면 isMethodAllowed() 체크 → router.handle()
  → 인증 실패 → 에러 응답 + socket.destroy()
```

---

## 5. 핵심 발견사항

### 5.1 마스터 부트스트랩 최적화 기회

현재 부트스트랩 (tmux 명령 기반):
```
tmux split-window -h "claude"     → 패널 생성 + CLI 실행 (2단계)
tmux send-keys -t %1 "..." Enter  → 텍스트 전송 (tmux shim 경유)
tmux capture-pane -t %1 -p        → 화면 읽기 (tmux shim 경유)
```

Socket API 직접 호출 시:
```
agent.spawn {agentType, workspaceId, task}  → 패널 생성 + CLI 실행 (1단계)
agent.send_task {surfaceId, task}           → 텍스트 전송 (lock 내장, 딜레이 자동)
agent.output {surfaceId, lines}             → 출력 읽기 (ANSI 자동 스트립)
agent.wait {surfaceId, timeout}             → 완료 대기 (폴링 불필요)
```

### 5.2 system.tree — 모니터링 효율화
현재: `panel.list` + `surface.list` + `workspace.list` = 3회 호출
대안: `system.tree` = **1회 호출**로 전체 토폴로지 (패널+서피스+에이전트+포커스) 획득

### 5.3 workflow.run — 워크플로우 자동화
다단계 에이전트 워크플로우를 JSON 1개로 선언적 실행 가능.
마스터가 직접 spawn → send → wait 루프 대신 `workflow.run` 1회 호출.

### 5.4 surface.health — PTY + 에이전트 통합 상태
PTY 존재 여부, 버퍼 크기, 에이전트 상태를 1회 호출로 확인.
현재 모니터링에서 "대기 중을 진행중으로 오판" 문제 해결 가능.

### 5.5 browser.* — 대시보드 자동화 잠재력
브라우저 패널(대시보드)에 대한 DOM 조작, 네비게이션, 스크린샷 가능.
`automation` 모드 이상에서만 허용.

---

## 6. 통계 요약

| 항목 | 수치 |
|------|------|
| 총 도메인 | 11개 (auth 포함) |
| 총 메서드 | 60개 |
| 핸들러 파일 | 10개 (.ts) |
| 마스터 사용 중 | 9개 (15%) |
| 마스터 미사용 | 51개 (85%) |
| 즉시 활용 가능 (높은 우선순위) | 12개 |
| 특수 용도 / 조건부 | 39개 |

---

## 7. Round 2 제안

1. **부트스트랩 스크립트 Socket API 전환**: tmux shim → `agent.spawn` + `agent.send_task` 직접 호출
2. **모니터링 효율화**: `system.tree` + `surface.health` 기반 실시간 상태 파악
3. **워크플로우 자동화**: `workflow.run` 활용한 선언적 에이전트 오케스트레이션
4. **대시보드 연동**: `browser.*` API를 활용한 대시보드 자동 조작/데이터 주입
