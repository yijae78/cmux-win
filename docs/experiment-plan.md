# 씨윈 통합 실험 계획 v3

> 작성: 2026-04-27
> 목적: 씨윈의 모든 채널(CLI shim, 소켓 API, Bridge, Workflow, MCP)이 실전에서 100% 작동하는지 검증
> 상태: Phase 0.1부터 시작

---

## Ground Truth (실험 시작 시점)

| 항목 | 실태 |
|------|------|
| 씨윈 앱 | 꺼져 있음 (ECONNREFUSED) |
| 프로젝트 경로 | C:\dev\cmux-win (이전: OneDrive 바탕화면) |
| MCP auto-launch | 구경로 참조 중 → 수정 필요 |
| Bridge inbox | 잔재 2개 (client_start.json, server_start.json) |
| 에이전트 | 없음 (새로 스폰 필요) |
| 외부 프로젝트 | OneDrive 바탕화면에 3개 존재 (공백+한글 경로) |
| symlink | 없음 (생성 필요) |

---

## 위험 목록

| ID | 위험 | 대응 |
|----|------|------|
| R1 | OneDrive 경로 공백+한글 → shell escaping 실패 | symlink로 단축 경로 확보 |
| R2 | Gemini idle 패턴 버전 변동 | 1.4에서 실측 채취 |
| R3 | Codex --no-alt-screen 미적용 시 capture 불가 | 1.3 스폰 시 명시 적용 |
| R4 | Bridge "DONE" 오탐 | 프롬프트에 ===BRIDGE_DONE=== 마커 명시 |
| R5 | workflow.run 패널 누적 | 정리 단계 삽입 |
| R6 | send-keys 한글 깨짐 | 영문 프롬프트 우선 |
| R7 | Bridge target=Claude(자신) → 순환 충돌 | target을 Gemini paneIndex로 고정 |

---

## Phase 0: 환경 정비

### 0.1 MCP auto-launch 경로 수정
- **상태**: [x] 완료 (c6eda3c)
- **내용**: src/mcp/cmux-mcp-server.ts의 launchCmuxWin() projectDir을 C:\dev\cmux-win으로 변경
- **성공 조건**: 빌드 성공
- **시간**: 2분

### 0.2 Bridge inbox 정리
- **상태**: [x] 완료
- **내용**: ~/cmux-bridge/inbox/*.json 삭제
- **성공 조건**: inbox 빈 폴더
- **시간**: 1분

### 0.3 Symlink 생성
- **상태**: [x] 완료 (PowerShell junction)
- **내용**: 3개 외부 프로젝트에 공백 없는 경로 확보
  - C:\projects\sermon → My-Sermon-Editor
  - C:\projects\globalnews → GlobalNews-Crawling-AgenticWorkflow
  - C:\projects\envscan → EnvironmentScan-system-main-v4
- **성공 조건**: ls /c/projects/sermon 등 3개 모두 성공
- **시간**: 3분
- **주의**: junction 사용 (관리자 권한 불필요)

### 0.4 씨윈 빌드
- **상태**: [x] 완료 (esbuild MCP 번들 포함)
- **내용**: npm run build (0.1 경로 수정 반영)
- **성공 조건**: exit 0 + out/main/index.js 갱신
- **시간**: 1분

### 0.5 씨윈 실행
- **상태**: [x] 완료
- **내용**: 신교수님이 앱 수동 실행 (또는 npx electron out/main/index.js)
- **성공 조건**: 소켓 19840 수신 시작
- **시간**: 10분 (앱 초기화 대기 포함)

### 0.6 [GATE] 연결 확인
- **상태**: [x] 통과
- **내용**: tmux has-session → exit 0
- **성공 조건**: shim이 소켓 연결 성공
- **실패 시**: 앱 재시작 or 소켓 서버 로그 확인
- **시간**: 1분

---

## Phase 1: 기초 연결

### 1.1 shim 왕복
- **상태**: [x] 완료 (3패널 확인)
- **내용**: tmux list-panes → 패널 목록 반환
- **성공 조건**: JSON 출력에 paneIndex 존재
- **시간**: 2분

### 1.2 Gemini 스폰
- **��태**: [x] 완료 (%1, "OK" 응답)
- **내용**: tmux split-window -h "gemini -i \"hello\" -y"
- **성공 조건**: 새 패널 생성 + Gemini 응답 출력
- **시간**: 5분

### 1.3 Codex 스폰
- **상태**: [x] 완료 (%2, "OK" 응답, capture 가능)
- **내용**: tmux split-window -h "codex --full-auto --no-alt-screen \"hello\""
- **성공 조건**: 새 패널 생성 + 응답 출력 + capture 가능
- **시간**: 5분

### 1.4 [GATE] idle 패턴 실측
- **상태**: [x] 통과 (Gemini: "Type your message", Codex: PS 프롬프트 복귀)
- **내용**: 두 에이전트 idle 후 capture-pane → 실제 idle 문자열 채취
- **성공 조건**: Gemini idle 문자열 확인, Codex capture 가능
- **실패 시**: constants.ts idle 패턴 업데이트 → 재빌드 → 0.4로 복귀
- **시간**: 5분

---

## Phase 2: 소켓 API

### 2.1 소켓 직접 연결
- **상태**: [x] 완료 (auth + panel.list 3패널)
- **내용**: Node 스크립트로 auth.handshake + panel.list 호출
- **성공 조건**: 3개 패널 JSON 응답
- **시간**: 5분

### 2.2 surface.read 3패널
- **상태**: [x] 완료 (3개 모두 non-empty)
- **내용**: 소켓으로 3개 surface 읽기
- **성공 조건**: 3개 모두 non-empty 텍스트 반환
- **시간**: 5분

### 2.3 [GATE] 안정성 테스트
- **상태**: [x] 통과 (10/10 성공, avg <1ms)
- **내용**: panel.list 10회 연속 호출
- **성공 조건**: 10/10 성공, 응답 < 100ms
- **실패 시**: 소켓 서버 점검
- **시간**: 3분

---

## Phase 3: 다중 AI 협업

### 3.1 Claude→Gemini 왕복
- **상태**: [x] 완료 (10*5=50 정답)
- **내용**: send-keys로 질문 → 30초 대기 → capture → 응답 유효성
- **성공 조건**: 응답에 의미 있는 내용 포함
- **시간**: 10분

### 3.2 Claude→Codex 왕복
- **상태**: [x] 완료 (3+3=6 정답)
- **내용**: 동일 패턴으로 Codex에 간단 작업 지시
- **성공 조건**: 응답 유효
- **시간**: 10분

### 3.3 [GATE] 동시 전송+회수
- **상태**: [x] 통과 (Gemini 50, Codex 56 — 동시 정답)
- **내용**: %1, %2에 동시에 다른 작업 → 각각 결과 회수
- **성공 조건**: 두 결과 모두 올바른 작업에 대한 응답
- **실패 시**: send lock 타이밍 조정
- **시간**: 10분

---

## Phase 4: Bridge + 외부 프로젝트

### 4.0 [사전] 경로 + symlink 검증
- **상태**: [x] 통과 (3/3 접근 가능)
- **내용**: symlink 3개 ls + cd 성공
- **성공 조건**: 3/3 접근 가능
- **시간**: 2분

### 4.1 Bridge direct → Gemini
- **상태**: [△] 부분성공 — task 전달됨, Gemini 응답함, 그러나 liveBuffer 폴링 버그로 output 미수집 (Ink TUI 호환 이슈)
- **내용**: task.json (target: Gemini paneIndex, mode: direct, 간단 질문)
- **성공 조건**: outbox에 result.json (status: completed)
- **실패 시**: paneIndex 확인, timeout 조정
- **시간**: 10분
- **프롬프트 규칙**: 응답 끝에 "===BRIDGE_DONE===" 출력 지시 포함

### 4.2 Bridge leader → Gemini
- **상태**: [△] 건너뜀 — 4.1과 동일한 liveBuffer 버그 (수정 후 재시도 필요)
- **내용**: task.json (mode: leader, "Sermon 폴더 구조 파악") + 마커 지시
- **성공 조건**: result.json에 유의미한 분석 결과
- **시간**: 15분

### 4.3 Sermon 프로젝트 분석
- **상태**: [x] 완료 (Gemini가 6개 설교 폴더 정확히 보고)
- **내용**: Gemini에게 symlink 경로(C:\projects\sermon)로 분석 지시
- **성공 조건**: capture에 실제 설교 제목/파일 목록
- **시간**: 15분

### 4.4 [GATE] 교차 검증
- **상태**: [x] 통과 (Gemini 보고 6개 = 실제 6개, 100% 일치)
- **내용**: Gemini 보고 vs ls sermons/ 실제 결과 비교
- **성공 조건**: 일치율 80% 이상
- **실패 시**: 프롬프트 구체화
- **시간**: 5분

---

## Phase 5: 풀 오케스트레이션

### 5.1 GlobalNews 3AI 팬아웃
- **상태**: [ ] 미완
- **내용**: Gemini(설정분석) + Codex(코드점검) + Claude(통합)
- **성공 조건**: 3개 결과 모두 유효 + 통합 리포트
- **시간**: 30분

### 5.1.5 [정리] 패널 복원
- **상태**: [ ] 미완
- **내용**: 새로 생긴 패널 close → 원래 3패널 복원
- **시간**: 2분

### 5.2 EnvScan Bridge 체인
- **상태**: [ ] 미완
- **내용**: Bridge → Gemini → env-scanning 분석 → outbox 결과
- **성공 조건**: 자동 체인 완주 (사람 개입 0)
- **시간**: 20분

### 5.2.5 [정리] 패널 복원 + heartbeat 확인
- **상태**: [ ] 미완
- **내용**: 패널 정리 + heartbeat.ts < 30초 전
- **시간**: 2분

### 5.3 Workflow 3프로젝트 순차
- **상태**: [ ] 미완
- **내용**: workflow.run — Sermon→GlobalNews→EnvScan (symlink 경로, timeout 10분/step)
- **성공 조건**: stepsCompleted=3, 각 output 유효
- **시간**: 35분

### 5.4 [최종] 전체 성공률 보고
- **상태**: [ ] 미완
- **내용**: 전 단계 결과 집계 + 시스템 상태 확인
- **성공 조건**: 전체 PASS + heartbeat 정상 + 패널 정리 완료
- **시간**: 5분

---

## GATE 규칙

```
GATE 실패 → 해당 Phase에서 정지
         → 원인 분석
         → 수정 조치
         → GATE 재시도 (최대 3회)
         → 3회 실패 → 신교수님 판단 요청
         → 통과 시에만 다음 Phase 진입
```

---

## 의존성 그래프

```
0.1 → 0.4 → 0.5 → 0.6(GATE)
0.2 ──────────────→ 4.1
0.3 ──────────────→ 4.0

0.6 → 1.1 → 1.2 → 1.4(GATE)
            1.3 ──→ 1.4(GATE)

1.4 → 2.1 → 2.2 → 2.3(GATE)

2.3 → 3.1 → 3.3(GATE)
      3.2 → 3.3(GATE)

3.3 + 4.0 → 4.1 → 4.2 → 4.3 → 4.4(GATE)

4.4 → 5.1 → 5.1.5 → 5.2 → 5.2.5 → 5.3 → 5.4
```

---

## 소요 시간

| Phase | 작업 | 검증 | 소계 |
|-------|------|------|------|
| 0 | 17분 | 1분 | 18분 |
| 1 | 12분 | 5분 | 17분 |
| 2 | 10분 | 3분 | 13분 |
| 3 | 20분 | 10분 | 30분 |
| 4 | 40분 | 7분 | 47분 |
| 5 | 87분 | 9분 | 96분 |
| **합계** | | | **~3시간 40분** |

---

## 불확실성

| ID | 내용 | 해소 시점 | 최악의 경우 |
|----|------|----------|------------|
| U1 | junction 권한 | 0.3 | 관리자 실행 or 신교수님 수동 생성 |
| U2 | Gemini idle 패턴 변경 | 1.4 | constants.ts 업데이트 + 재빌드 |
| U3 | Codex 설치 여부 | 1.3 | npm i -g @openai/codex |
| U4 | workflow cwd OneDrive 처리 | 5.3 | symlink 경로로 대체 |
| U5 | 씨윈 수동 실행 | 0.5 | 신교수님 액션 필요 |
