# cmux-win 전수조사 보고서

**일시:** 2026-04-23
**조사 범위:** src/main, src/renderer, src/shared, src/mcp, resources/, 빌드/설정
**조사 방법:** 4개 병렬 에이전트 전수 탐색

---

## CRITICAL — 보안/안정성 (즉시 조치)

### C1. Electron 33.4.11 — 18개 High CVE
- **위치:** package.json:24
- **문제:** 최신 41.3.0 대비 8버전 뒤처짐. ASAR Integrity Bypass, AppleScript injection 등
- **조치:** Electron 업그레이드 (breaking change 검토 필요)

### C2. Vite 6.4.1 — Path Traversal CVE
- **위치:** package.json:58
- **문제:** 2개 High severity CVE (Arbitrary File Read)
- **조치:** Vite 8.x 업그레이드

### C3. 소켓 서버 버퍼 크기 무제한 (OOM)
- **위치:** src/main/socket/server.ts:83-90
- **문제:** newline-delimited JSON 파싱 시 버퍼 제한 없음. 거대 JSON으로 메모리 폭주 가능
- **조치:** 최대 버퍼 크기 제한 (예: 10MB)

### C4. 소켓 인증 JSON parse 에러 시 silent pass
- **위치:** src/main/socket/server.ts:131-146
- **문제:** 파싱 실패한 요청이 권한 검사 우회 가능
- **조치:** JSON parse 실패 시 즉시 연결 종료

---

## HIGH — 메모리 릭/Race Condition (단기 조치)

### H1. MCP taskStore 메모리 릭
- **위치:** src/mcp/cmux-mcp-server.ts:224
- **문제:** 완료된 task가 Map에서 삭제되지 않음. 장시간 운영 시 무제한 증가
- **조치:** TTL 기반 자동 정리 (예: 완료 후 5분 삭제)

### H2. XTermWrapper PTY 리스너 누수
- **위치:** src/renderer/components/terminal/XTermWrapper.tsx:155, 284-285
- **문제:** workspace 전환 시 이전 disposers 미호출. F2-FIX 주석 존재
- **조치:** disposer 배열을 mount/unmount 시 확실히 정리

### H3. PanelLayout pointermove 리스너 영구 할당
- **위치:** src/renderer/components/panels/PanelLayout.tsx:303-304
- **문제:** cleanup 없이 window에 리스너 등록. 앱 수명 동안 누적
- **조치:** useEffect cleanup에서 removeEventListener

### H4. BrowserSurface contextmenu 리스너 누적
- **위치:** src/renderer/components/browser/BrowserSurface.tsx:196-202
- **문제:** 웹뷰 생성/파괴 반복 시 리스너 중복 등록
- **조치:** useEffect cleanup 추가

### H5. 소켓 재연결 race condition
- **위치:** src/mcp/cmux-mcp-server.ts:63-67, 147-165
- **문제:** ensureConnection() 동시 호출 시 중복 연결 시도
- **조치:** connection promise를 캐시하여 중복 방지

### H6. agent.ts sendLocks race condition
- **위치:** src/main/socket/handlers/agent.ts:109-113
- **문제:** 동시 요청 시 lock 경합. 자동 정리 타임아웃 없음
- **조치:** lock TTL 추가, mutex 패턴 적용

### H7. App.tsx setTimeout 누수
- **위치:** src/renderer/App.tsx:339, 606, 673
- **문제:** 폴더 열기 후 setTimeout cleanup 없음. 언마운트 시 타이머 잔존
- **조치:** useRef + useEffect cleanup

---

## MEDIUM — 기능 결함/불완전 (중기 조치)

### M1. isAgentIdle false positive
- **위치:** src/mcp/cmux-mcp-server.ts:204-211
- **문제:** Claude '> ' 패턴이 너무 일반적. 에러 메시지와 혼동 가능
- **조치:** 패턴 정교화 (줄 시작 위치, 앞뒤 컨텍스트 확인)

### M2. 자동 승인 패턴 경직
- **위치:** src/main/terminal/pty-manager.ts:116-131
- **문제:** hardcoded 패턴. Gemini/Codex 버전 업데이트 시 호환 불가
- **조치:** 설정 파일로 외부화, 정규식 지원

### M3. tmux-shim 옵션 파싱 불완전
- **위치:** resources/bin/tmux-shim.js:167-233
- **문제:** split-window의 -l, -f, -c 옵션 무시. capture-pane 에러 시 빈 문자열 반환
- **조치:** 주요 옵션 추가 파싱, 에러 시 stderr 출력

### M4. PowerShell 한글 경로 URI 깨짐
- **위치:** resources/shell-integration/powershell.ps1:5
- **문제:** 공백만 %20 치환. 한글/특수문자 미인코딩
- **조치:** [uri]::EscapeUriString() 사용

### M5. WorkspaceSetLayoutAction z.any()
- **위치:** src/shared/actions.ts:195-201
- **문제:** panelLayout 타입 검증 없음. 잘못된 구조도 통과
- **조치:** PanelLayoutTree 스키마 정의

### M6. findAgentSurface system.tree 파싱
- **위치:** src/mcp/cmux-mcp-server.ts:574-582
- **문제:** agent.agentType undefined 시 toLowerCase() 에러
- **조치:** optional chaining 강화

### M7. index.ts 파일 복사 에러 무시
- **위치:** src/main/index.ts:481-523
- **문제:** mkdirSync/copyFileSync 실패 시 조용히 지남
- **조치:** try-catch + 로그

### M8. ANSI 필터링 불완전
- **위치:** src/main/terminal/pty-manager.ts:38-56
- **문제:** 일부 ANSI 시퀀스(8진법 등) 미처리
- **조치:** stripAnsi 패턴 확장

### M9. MarkdownViewer 2초 폴링
- **위치:** src/renderer/components/markdown/MarkdownViewer.tsx:77-79
- **문제:** 대용량 파일 시 IPC 호출 부하
- **조치:** fs.watch 기반 변경 감지

### M10. Telegram bot 중복 폴링
- **위치:** src/main/notifications/telegram-bot.ts:58-130
- **문제:** configure() 재호출 시 이전 bot.stop() 보장 없음
- **조치:** 기존 인스턴스 확실히 종료 후 재시작

---

## LOW — 코드 품질/최적화 (장기 개선)

### L1. Prop drilling 심화
- App.tsx → PanelContainer (8 콜백) → Sidebar (14+ props)
- **조치:** Context API 또는 zustand 도입

### L2. 9개 독립 useState
- **위치:** src/renderer/App.tsx:112-121
- **조치:** useReducer 또는 상태 그룹화

### L3. XTermWrapper 이중 resize 타이머
- **위치:** src/renderer/components/terminal/XTermWrapper.tsx:565-582
- **조치:** 단일 ResizeObserver + debounce

### L4. PanelDivider overlay DOM 고아화
- **위치:** src/renderer/components/panels/PanelDivider.tsx:42-45
- **조치:** finally 블록에서 확실히 remove

### L5. FileExplorer debounce 타이밍
- **위치:** src/renderer/components/explorer/FileExplorer.tsx:66-78
- **조치:** abort controller 패턴

### L6. .gitignore 누락 패턴
- .cache/, .eslintcache, .DS_Store, Thumbs.db, tmp-captures/
- **조치:** 추가

### L7. CLAUDE.md와 빌드 스크립트 불일치
- CLAUDE.md에 esbuild 수동 명령, package.json에 electron-vite
- **조치:** 문서 동기화

### L8. 테스트 커버리지 임계값 없음
- **위치:** vitest.config.ts
- **조치:** 최소 커버리지 설정 (예: 60%)

### L9. Electron Builder 코드 서명 없음
- **위치:** electron-builder.yml
- **조치:** 배포 시 서명 설정 추가

### L10. git dirty check 중복 호출
- **위치:** resources/shell-integration/powershell.ps1:7-11
- **조치:** git status 1회 호출로 통합

---

## TODO/FIXME/BUG 태그 발견 목록

| 태그 | 위치 | 내용 |
|------|------|------|
| BUG-7 | XTermWrapper.tsx:5 | @xterm 패키지 관련 |
| BUG-13 | XTermWrapper.tsx:6 | 폰트 변경 효과 |
| BUG-17 | useDispatch.ts:4 | IPC_CHANNELS import 금지 |
| P2-BUG-5 | XTermWrapper.tsx:320 | PTY 재부착 로직 |
| F2-FIX | XTermWrapper.tsx:598 | PTY 리스너 정리 |
| BUG-9 | ipc-broadcast.ts | sliceMap 매핑 |
| BUG-11 | ipc-broadcast.ts | electron 모듈 import |
| TODO | useShortcuts.ts:156-162 | find overlay, rename, multi-window |

---

## 우선순위 로드맵

### Phase 1 — 즉시 (보안)
- [ ] C1: Electron 업그레이드 (33→41)
- [ ] C2: Vite 업그레이드 (6→8)
- [ ] C3: 소켓 버퍼 크기 제한
- [ ] C4: JSON parse 에러 시 연결 종료

### Phase 2 — 1주 이내 (안정성)
- [ ] H1: taskStore TTL 정리
- [ ] H2: XTermWrapper disposer 정리
- [ ] H3: PanelLayout 리스너 cleanup
- [ ] H5: 소켓 재연결 dedup
- [ ] H7: setTimeout cleanup

### Phase 3 — 2주 이내 (기능)
- [ ] M1: idle 패턴 정교화
- [ ] M2: 자동 승인 패턴 외부화
- [ ] M3: tmux-shim 옵션 확장
- [ ] M4: PowerShell URI 인코딩

### Phase 4 — 1달 이내 (품질)
- [ ] L1-L2: 상태 관리 리팩토링
- [ ] L6: .gitignore 보강
- [ ] L7: 문서 동기화
- [ ] L8: 테스트 커버리지

---

## 통계

| 등급 | 건수 |
|------|------|
| CRITICAL | 4 |
| HIGH | 7 |
| MEDIUM | 10 |
| LOW | 10 |
| TODO/BUG 태그 | 8 |
| **합계** | **39건** |
