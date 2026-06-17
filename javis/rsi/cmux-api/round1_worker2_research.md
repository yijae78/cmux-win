# RSI cmux-api — Round 1 Worker2(AGY) 심층 리서치 보고서

* **Researcher**: Worker2(AGY) (디자인/UX/전략/컨텐츠 리뷰어)
* **Date**: 2026-06-17
* **RSI Stage**: cmux-api 설계 및 운용을 위한 사전 연구
* **Status**: COMPLETE

---

## 1. AI 터미널 멀티플렉서/오케스트레이터 최신 트렌드와 베스트 프랙티스

### 1-1. 최신 트렌드: AI CLI 플릿(Fleet) 협업 시스템
2026년 현재 AI CLI 시장은 단일 에이전트의 단독 코딩(Claude Code 등)을 넘어, 터미널 멀티플렉서(`tmux`, `cmux-win` 등) 환경에서 여러 개의 특화된 AI CLI들을 동시에 가동하고 상호 통신을 유도하는 **'에이전트 플릿(Fleet) / 스웜(Swarm)'**으로 전환되고 있습니다.

### 1-2. 다중 AI CLI(Claude Code, Gemini, Codex)의 병렬/동시 운용 방법론

1. **역할 정의 및 라우팅 (Role-based Workload Routing)**
   * **Claude Code**: 다중 파일 리팩토링, 소스코드 독해, 직접적인 코드 수정 및 빌드/테스트 등 **실행형 프론트엔드/백엔드 코딩**에 최적화(Worker1 역할).
   - **Gemini CLI (with Conductor)**: **기획 설계, 마일스톤 정립, UX/UI 감수 및 전략 연구**에 최적화. Markdown 스펙 기반의 탑다운(Top-down) 설계 검증에 강점(CSO & Worker2 역할).
   - **Codex CLI**: **코드 및 보안 검수(Audit), 유효성 검사(Validation), 이미지 생성(OpenAI DALL-E 3 연동) 및 기술 사양 정합성 검토**에 최적화(Worker3 역할).

2. **tmux 네이티브 IPC 및 협업 제어**
   * **tmux send-keys & capture-pane**: 에이전트 간 직접적인 API 연동이 어려운 독립 CLI 환경에서, 마스터 에이전트(%0)가 tmux API를 통해 하위 에이전트 패널에 인라인 명령(`gemini -i "명령" -y`)을 주입하고, 그 결과를 캡처하여 의사결정에 반영합니다.
   - **교착 상태(Deadlock) 방지**: 에이전트 간의 1:1 대화(Ping-pong loop)가 무한 루프를 돌며 토큰을 낭비하는 것을 막기 위해, 모든 명령의 조율은 마스터(%0)를 거치도록 통신 통로를 단일 방향으로 격리(Star topology)하는 것이 베스트 프랙티스입니다.

---

## 2. 멀티 에이전트 오케스트레이션에서 마스터-워커 패턴의 모니터링 자동화 방법

마스터-워커 패턴에서 가장 중요한 것은 하위 워커들의 상태(State)와 비정상 종료(Hang, Error)를 휴먼 개입 없이 자동 감시하는 것입니다.

### 2-1. 터미널 스크래핑 및 상태 감지 자동화
* **상태 정의**: `Idle`, `Thinking`, `Executing`, `Waiting for Input`, `Error`, `Complete`
* **패턴 매칭 기술**:
  - `tmux capture-pane -t %<pane_id> -p`를 사용하여 각 터미널 pane의 출력 스트림을 실시간(또는 주기적 폴링)으로 가져옵니다.
  - 캡처된 텍스트 스트림의 끝부분을 대상으로 정규표현식(Regex) 감지:
    - `"Thinking..."`, `"Analyzing..."` 감지 시 → `Thinking` 상태 기록
    - `"[y/N]"`, `"Enter input:"` 등 프롬프트 대기 패턴 감지 시 → `Waiting for Input` 상태 기록
    - `"The command completed successfully"`, `"✓"` 등 빌드 성공 패턴 감지 시 → `Complete` 기록
    - `"ParserError"`, `"exit code: 1"` 등 에러 패턴 감지 시 → `Error` 기록 및 마스터에 인터럽트(Interrupt) 알림

### 2-2. 경량 모니터링 데몬 벤치마킹
* **`agentoast` / `aque` / `tmuxpulse`**:
  - 이 도구들은 백그라운드에서 tmux 소켓 출력을 지속적으로 수신하여 상태 플래그 파일(예: `fleet_status.json`)을 갱신하거나 소켓 서버를 통해 실시간 이벤트를 전송합니다.
  - **Liveness Watchdog**: 워커 에이전트가 CPU 루프에 빠지거나 특정 연산 중 먹통(Hang)이 되는 것을 감지하기 위해, 상태가 `Thinking`으로 전환된 지 5분을 초과할 경우 데몬이 강제로 해당 패널에 인터럽트(Ctrl+C) 신호를 보내거나 마스터에게 리셋 신호를 송신하는 자동화 메커니즘이 필수적입니다.

---

## 3. 실시간 대시보드 모니터링: Streamlit vs 대안

멀티 에이전트 오케스트레이터를 가시화하는 실시간 대시보드 도구들의 특징과 비교 분석입니다.

### 3-1. Streamlit과 대안들 비교

| 프레임워크 | 장점 | 단점 | AI CLI 적합성 |
|-----------|------|------|-------------|
| **Streamlit** | 개발이 극도로 빠름, 단순 파이썬 코딩, 기본 UI 컴포넌트 내장 | 단방향 Rerun 모델로 실시간 스트리밍 대용량 데이터 시 처리 지연, 웹소켓 세밀한 제어 어려움 | **LOW** (단순 로그 뷰어로선 쓸만하나 실시간 멀티에이전트용으론 부적합) |
| **Dash (Plotly)** | React 기반 콜백 구조, 대용량 상태 관리 우수, 엔터프라이즈급 | 개발 리소스 큼, 즉각적인 TUI 통합성 부족 | **MEDIUM** (상태가 복잡한 기업형 시스템용) |
| **Textual (TUI)** | **터미널 내부 상주**, 리소스 극도로 가벼움, Asyncio 비동기 완벽 지원, 개발자의 컨텍스트 스위칭 최소화 | 시각적 화려함(차트, 그래디언트 등) 표현 한계 | **HIGH** (개발자가 터미널 환경을 벗어나지 않고 일할 수 있는 최적의 도구) |
| **React/Vite (HTML/JS)** | **극강의 Aesthetics 구현 가능** (Vibrant gradients, Radar 애니메이션 등), 커스텀 렌더링 자유 | Node.js 스택 및 파일/소켓 IPC 레이어 추가 빌드 필요 | **HIGH** (디자인 퀄리티가 최우선인 프리미엄 대시보드용, Javis 현재 모델) |

### 3-2. 전략적 제언
* 개발자의 **업무 집중(Context Retention)**이 최우선이고 터미널 안에서 끝내는 것이 목적이라면 **Textual (TUI)**이 2026년 기준 실용성 면에서 세계적인 베스트 프랙티스입니다.
* 사용성 및 **시각적 완성도(Visual Wow Factor)**가 필수적인 프로젝트의 경우, Javis와 같이 React/Vite 기반 프론트엔드에 Electron 또는 로컬 웹소켓 브릿지(IPC)를 탑재하여 화려한 다이내믹 그래디언트 및 상태 레이더를 연출하는 디자인 중심 대시보드가 적합합니다.

---

## 4. AI CLI 컨텍스트 관리 베스트 프랙티스 (Compact, Clear, Session 복원)

AI CLI 환경에서 제한된 컨텍스트 윈도우(Token limits)를 방어하고 기억 상실을 막기 위한 최선의 전략입니다.

### 4-1. 컨텍스트 압축 전략 (Context Budgeting)
1. **SOT (Source of Truth) 격리**:
   - 세세한 로그나 히스토리를 에이전트 컨텍스트에 모두 밀어 넣지 말고, 핵심 사양과 룰만 정리한 `CLAUDE.md`, `DESIGN.md`를 루트에 고정해 두고 상시 참조하게 합니다.
2. **로그 다이어트 (Log Sanitization)**:
   - 빌드 로그, 린트 에러 메시지 중 중복되거나 무의미한 부분(Warning 등)은 셸 래퍼가 필터링하여 에이전트에는 에러 본체와 스택 트레이스만 압축해서 주입합니다.
3. **주기적 `/clear` 및 세션 리로드**:
   - 토큰 소비가 100k~150k를 초과하면 속도 저하와 프롬프트 혼동이 발생합니다. 에이전트에게 `/clear` 명령을 내려 이전 대화를 소거하게 하되, 디스크에 누적 저장된 핵심 요약 파일들을 주입하여 기억을 "Hot-reload"합니다.

### 4-2. 세션 복원 및 핸드오프 (Session Recovery & Handoff)
1. **`SESSION_STATE.md` 수시 디스크 보관**:
   - 마스터와 워커들은 태스크 완료 또는 주요 마일스톤 도달 시마다 현재의 태스크 맵, 변수값, 다음 실행 예정 태스크를 `SESSION_STATE.md`(또는 JSON) 파일에 동기적으로 업데이트합니다.
   - 예기치 않은 세션 단절이나 `/clear` 기동 시, 에이전트는 이 파일을 1순위로 조회하여 1초 만에 이전 상태로 복구(Hot restoration)합니다.
2. **핸드오프 문서 (`*_handoff.md`) 작성**:
   - 에이전트 간의 태스크 전환이나, 세션이 전환될 때 인수인계 전용 파일(`roundX_handoff.md`)을 생성합니다. 
   - 여기에는 **[1] 현재까지 완료된 구체적 실적, [2] 해결된 Gap, [3] 잔여 Task와 미결정 사항, [4] 다음 워커가 즉시 실행해야 할 명령어**만을 콤팩트하게 마크다운으로 기술하여 정보 전달 손실률을 0%로 통제합니다.
