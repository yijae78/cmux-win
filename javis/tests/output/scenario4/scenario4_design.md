# 시나리오 4: 자비스 자가진화 — 풀스택 구축 + 장애 복구 + RSI 3R

> **난이도**: ★★★★★ (극한)
> **설계일**: 2026-06-17
> **설계**: Master Claude

---

## 왜 이 시나리오가 극한인가

| 구분 | 시나리오 1~3 | **시나리오 4** |
|------|-------------|---------------|
| **산출물** | Markdown 보고서 | **실제 작동하는 Python 코드** |
| **워커 관계** | 독립 병렬 분석 | **의존성 체인 (A→B→C)** |
| **장애** | 우발적 지연만 | **의도적 장애 주입 (Chaos Engineering)** |
| **RSI** | 보고서 개선 | **코드 품질 실측 개선 (테스트 통과율)** |
| **검증** | 사람이 읽고 판단 | **pytest 자동 실행으로 Pass/Fail 결정** |
| **상태 동기화** | 파일 공유만 | **공유 코드베이스 동시 수정** |
| **컨텍스트** | 자연 소진 | **강제 소진 + compact 복구** |

---

## 구축 대상: Javis Fleet Auto-Recovery Watchdog

**무엇을 만드는가**: cmux-win 워커가 멈추거나 죽었을 때 자동으로 감지하고 복구하는 워치독 시스템.

**왜 이것인가**: 시나리오 1~3에서 반복 발생한 "워커 멈춤/지연" 문제를 자동 해결하는 시스템을 플릿 스스로 구축한다 — **자가진화(Self-Evolution)**.

### 목표 아키텍처

```
javis/watchdog/
├── __init__.py              # 패키지 초기화
├── detector.py              # 워커 상태 감지 (heartbeat + screen 분석)
├── strategy.py              # 복구 전략 엔진 (재시작/인수/에스컬레이션)
├── executor.py              # 복구 실행기 (tmux 명령 + Socket API)
├── orchestrator.py          # 메인 오케스트레이터 (감지→판단→실행 루프)
├── config.py                # 설정 (임계값, 타임아웃, 정책)
├── models.py                # 데이터 모델 (WorkerState, RecoveryAction 등)
├── cli.py                   # CLI 인터페이스 (javis-watchdog 명령)
└── tests/
    ├── __init__.py
    ├── test_detector.py     # 감지 모듈 단위 테스트
    ├── test_strategy.py     # 전략 엔진 단위 테스트
    ├── test_executor.py     # 실행기 단위 테스트 (mock)
    ├── test_orchestrator.py # 통합 테스트
    └── conftest.py          # 공통 fixture
```

### 핵심 기능 요구사항

| 기능 | 설명 | 난이도 |
|------|------|--------|
| **Heartbeat 감지** | 워커 화면을 주기적 읽어 idle/stuck/dead 판별 | 중 |
| **지능형 분류** | "생각 중"과 "멈춤"을 구분 (dashboard.py의 detect_status 확장) | 상 |
| **3단계 복구 전략** | ① Ctrl+C 재시도 → ② 워커 재시작 → ③ 마스터 에스컬레이션 | 상 |
| **핸드오프 자동화** | 죽은 워커의 미완 작업을 다른 워커에 인계 | 극상 |
| **Socket API 통합** | cmux-win Socket API로 패널 생성/닫기/라벨 설정 | 중 |
| **이벤트 로그** | 모든 감지/복구 이벤트를 JSON 로그로 기록 | 하 |
| **CLI** | `python -m javis.watchdog start/status/stop` 명령 | 중 |
| **테스트 커버리지** | pytest 80%+ 라인 커버리지 | 상 |

---

## 실행 계획: 5 Phase

### Phase 0: 준비 (마스터 단독, 5분)

1. 8-pane fleet 구성 (6-pane 기본 + Worker4 + Worker5)
2. 작업 디렉토리 생성: `javis/watchdog/`
3. 워커별 역할 브리핑 + WORKER_DIRECTIVE 주입
4. 의존성 체인 선언 및 대시보드 확인

### Phase 1: 아키텍처 논쟁 + 합의 (15분)

**목적**: 5명의 워커가 아키텍처를 토론하고 합의에 도달

| 워커 | 역할 | 산출물 |
|------|------|--------|
| Worker1(Claude) | 초안 아키텍처 설계 | `design_v1.md` |
| Worker2(AGY) | **반박**: 설계 결함 지적, 대안 제시 | `critique_gy.md` |
| Worker3(Codex) | **반박**: 기술적 실현 가능성 검증, 테스트 전략 | `critique_cx.md` |
| Worker4(Claude) | Worker2+3 피드백 반영한 수정안 | `design_v2.md` |
| Worker5(AGY) | **최종 판정**: v1 vs v2 비교 평가, 합의안 도출 | `design_final.md` |

**핵심 제약**:
- Worker1은 Worker2/3 피드백을 보기 전에 v1을 완성해야 함 (의존성)
- Worker4는 반드시 Worker2+3의 비판을 수용/반박해야 함 (논쟁 기록)
- Worker5가 60% 이상 동의하지 않으면 Phase 1 재시작

### Phase 2: 병렬 구현 (25분)

**목적**: 합의된 아키텍처에 따라 실제 코드 생성

| 워커 | 담당 모듈 | 의존성 | 산출물 |
|------|----------|--------|--------|
| Worker1(Claude) | `detector.py` + `models.py` | 없음 (최초 시작) | 감지 로직 + 데이터 모델 |
| Worker2(AGY) | `strategy.py` + `config.py` | ← Worker1의 models.py (인터페이스) | 복구 전략 엔진 |
| Worker3(Codex) | `tests/` 전체 | ← Worker1+2 인터페이스 | 테스트 코드 |
| Worker4(Claude) | `executor.py` + `orchestrator.py` | ← Worker1+2 완성 후 | 실행기 + 통합 |
| Worker5(AGY) | `cli.py` + `__init__.py` + README | ← Worker4 API 확정 후 | CLI + 문서 |

**의존성 체인 (핵심 난관)**:
```
Worker1 ─────┬─→ Worker2 ──┬─→ Worker4 ──→ Worker5
              │              │
              └─→ Worker3 ───┘
```

**동기화 프로토콜**:
1. Worker1이 `models.py` 완성 → 마스터가 Worker2+3에 "models.py 확정, 구현 시작" 전달
2. Worker2가 `strategy.py` 완성 → 마스터가 Worker4에 "strategy.py 확정" 전달
3. Worker3은 Worker1+2 인터페이스 기반으로 mock 테스트 선행 작성 → 실제 코드 완성 후 통합 테스트로 전환

**코드 규약 (전 워커 공통)**:
- Python 3.10+, type hints 필수
- docstring Google style
- import는 상대 경로 (`from .models import WorkerState`)
- 외부 의존성 금지 (표준 라이브러리 + cmux-win 기존 코드만)
- 모든 함수 max 50줄

### Phase 3: 장애 주입 — Chaos Engineering (10분)

**목적**: 워커 장애 시 플릿이 복구할 수 있는지 실증

Phase 2 진행 중 **마스터가 의도적으로** 다음 장애를 순차 주입:

| 시점 | 장애 | 대상 | 예상 반응 | 검증 |
|------|------|------|-----------|------|
| Phase2 10분차 | **워커 강제 종료** | Worker2(AGY) | Worker5가 strategy.py 인수 | Worker5 산출물에 strategy.py 포함 |
| Phase2 15분차 | **컨텍스트 강제 소진** | Worker1에 대용량 파일 읽기 지시 | Worker1 /compact 자동 실행 → 작업 재개 | compact 전후 산출물 연속성 |
| Phase2 20분차 | **대시보드 프로세스 종료** | Dashboard (port 8500) | 마스터가 대시보드 재시작 | 재시작 후 플릿 현황 정확 반영 |
| Phase3 시작 | **동시 2워커 종료** | Worker3(Codex) + Worker4(Claude) | 마스터가 sub-agent로 대체 | 테스트+통합 코드 sub-agent 산출 |

**장애 주입 명령**:
```bash
# Worker2 강제 종료
tmux send-keys -t %AGY_PANE C-c C-c
sleep 1
tmux send-keys -t %AGY_PANE "exit" Enter

# 대시보드 종료
pkill -f "streamlit run.*dashboard.py"

# 컨텍스트 강제 소진 (Worker1에 큰 파일 반복 읽기 지시)
tmux send-keys -t %W1_PANE "Read the entire file /c/dev/cmux-win/javis/dashboard.py 5 times and summarize each read" Enter
```

**복구 판정 기준**:
- 장애 발생 후 **5분 이내** 대체 워커/sub-agent가 작업 인수
- 인수된 작업의 산출물이 원래 요구사항의 **80% 이상** 충족
- 핸드오프 문서(`handoff_W2.md` 등)가 생성되어 작업 연속성 보장

### Phase 4: 통합 + RSI 3라운드 (20분)

**목적**: 전 워커의 코드를 통합하고 3라운드에 걸쳐 품질을 측정 가능하게 개선

#### 통합 단계 (5분)
1. 마스터가 모든 `.py` 파일을 `javis/watchdog/`에 취합
2. `python -m pytest javis/watchdog/tests/ -v` 실행 → **기준선(Baseline) 점수** 기록
3. `python -m javis.watchdog --help` 실행 → CLI 작동 확인

#### RSI Round 1 — AGY 리뷰 (5분)
| 단계 | 동작 |
|------|------|
| 1 | Worker2(AGY) 또는 대체 AGY가 전체 코드 리뷰 |
| 2 | 발견사항을 `rsi_r1_review.md`에 기록 (점수 포함) |
| 3 | Worker1이 리뷰 반영하여 코드 수정 |
| 4 | pytest 재실행 → **Round 1 점수** 기록 |
| **목표** | Baseline 대비 **테스트 통과율 +10%** 또는 커버리지 +10% |

#### RSI Round 2 — Codex 리뷰 (5분)
| 단계 | 동작 |
|------|------|
| 1 | Worker3(Codex) 또는 대체 sub-agent가 보안/성능 검수 |
| 2 | 발견사항을 `rsi_r2_review.md`에 기록 |
| 3 | Worker4가 리뷰 반영하여 코드 수정 |
| 4 | pytest 재실행 → **Round 2 점수** 기록 |
| **목표** | Round 1 대비 **+10%** |

#### RSI Round 3 — 교차 리뷰 + 최종 (5분)
| 단계 | 동작 |
|------|------|
| 1 | 생존한 전 워커가 각자 담당 외 모듈 1개씩 교차 리뷰 |
| 2 | 발견사항을 `rsi_r3_cross_review.md`에 종합 |
| 3 | 마스터가 최종 수정 지시 |
| 4 | pytest 최종 실행 → **Final 점수** 기록 |
| **목표** | **pytest 전체 통과 + 커버리지 80%+** |

**RSI 점수 추적표** (마스터가 실시간 갱신):
```
| 라운드    | 테스트 수 | 통과 | 실패 | 통과율 | 커버리지 | 비고 |
|-----------|----------|------|------|--------|---------|------|
| Baseline  |    ?     |  ?   |  ?   |   ?%   |   ?%    |      |
| Round 1   |    ?     |  ?   |  ?   |   ?%   |   ?%    | +?%  |
| Round 2   |    ?     |  ?   |  ?   |   ?%   |   ?%    | +?%  |
| Final     |    ?     |  ?   |  ?   |   ?%   |   ?%    | +?%  |
```

### Phase 5: 실전 검증 — 자기 자신을 지키는 워치독 (10분)

**목적**: 구축한 워치독을 실제 플릿에서 실행하여 장애 감지·복구가 작동하는지 실증

| 단계 | 동작 | 검증 |
|------|------|------|
| 1 | `python -m javis.watchdog start` 실행 | 프로세스 시작 확인 |
| 2 | 워치독이 현재 6-pane 상태를 정확히 감지하는지 확인 | `status` 명령으로 워커 목록 출력 |
| 3 | Worker1을 의도적으로 5분 idle 시킴 | 워치독이 "idle 경고" 로그 생성 |
| 4 | Worker1에 Ctrl+C×2로 CLI 종료 | 워치독이 "dead" 감지 → 복구 시도 로그 |
| 5 | 워치독 로그 파일 확인 | JSON 이벤트 로그에 감지·복구 기록 존재 |
| 6 | `python -m javis.watchdog stop` 실행 | 깨끗한 종료 확인 |

**최종 판정**: 워치독이 4단계(dead 감지)까지 성공하면 Phase 5 **합격**.

---

## 타임라인 총괄

```
[00:00] Phase 0 — 준비 (8-pane 구성)                    5분
[00:05] Phase 1 — 아키텍처 논쟁 + 합의                  15분
[00:20] Phase 2 — 병렬 구현 (+ Phase 3 장애 주입)       25분
        ├─ [00:30] 장애1: Worker2 강제 종료
        ├─ [00:35] 장애2: Worker1 컨텍스트 강제 소진
        ├─ [00:40] 장애3: 대시보드 종료
        └─ [00:45] 장애4: Worker3+4 동시 종료
[00:45] Phase 4 — 통합 + RSI 3라운드                    20분
        ├─ [00:45] 통합 + Baseline 측정
        ├─ [00:50] RSI Round 1 (AGY 리뷰)
        ├─ [00:55] RSI Round 2 (Codex 리뷰)
        └─ [01:00] RSI Round 3 (교차 리뷰 + Final)
[01:05] Phase 5 — 실전 검증                              10분
[01:15] 종료 — 최종 보고서 + 커밋                         5분

총 소요: ~80분 (1시간 20분)
```

---

## 성공 기준 (전부 충족해야 시나리오 통과)

### Must-Have (필수)
- [ ] `javis/watchdog/` 9개 .py 파일 생성 (테스트 5개 포함)
- [ ] `python -m pytest` 전체 통과 (0 failures)
- [ ] `python -m javis.watchdog --help` 정상 출력
- [ ] RSI 3라운드 점수가 **단조 증가** (Baseline < R1 < R2 < Final)
- [ ] 장애 주입 4건 중 3건 이상 **5분 이내 복구**
- [ ] 핸드오프 문서 2건 이상 생성
- [ ] Phase 5 실전 검증에서 "dead" 감지 성공

### Nice-to-Have (가점)
- [ ] 테스트 커버리지 80%+
- [ ] 워치독이 실제로 워커를 자동 재시작 성공
- [ ] RSI 최종 점수 90%+
- [ ] 전체 진행 중 마스터 개입 10회 이하 (자율 운영)
- [ ] 8-pane에서 6-pane으로 무중단 축소 성공

---

## 이전 시나리오 대비 난이도 비교

| 평가 축 | S1 | S2 | S3 | **S4** |
|---------|:--:|:--:|:--:|:------:|
| 산출물 복잡도 | ★☆☆☆☆ | ★★☆☆☆ | ★★★☆☆ | **★★★★★** |
| 워커 조율 난이도 | ★★☆☆☆ | ★★★☆☆ | ★★★☆☆ | **★★★★★** |
| 장애 대응 | ☆☆☆☆☆ | ★☆☆☆☆ | ★★☆☆☆ | **★★★★★** |
| RSI 깊이 | ★☆☆☆☆ | ★★☆☆☆ | ★★★☆☆ | **★★★★★** |
| 검증 엄격성 | ★☆☆☆☆ | ★★☆☆☆ | ★★★☆☆ | **★★★★★** |
| **종합 난이도** | **초급** | **중급** | **상급** | **극한** |

---

## 위험 요소 및 완화 계획

| 위험 | 확률 | 영향 | 완화 |
|------|------|------|------|
| 워커 컨텍스트 전부 소진 | 높음 | 치명 | Phase 2에서 집중 프롬프트 원칙 강제 + sub-agent 적극 활용 |
| 의존성 체인 교착 | 중간 | 높음 | 마스터가 5분 타임아웃으로 강제 진행 판단 |
| 코드 인터페이스 불일치 | 높음 | 높음 | models.py를 Worker1이 먼저 확정, 전 워커에 공유 후 구현 시작 |
| pytest 환경 미설치 | 낮음 | 중간 | `pip install pytest pytest-cov` 사전 실행 |
| 80분 초과 | 중간 | 중간 | Phase별 타임박스 엄격 적용, 초과 시 다음 Phase 강제 진입 |
| Codex CLI 프롬프트 실패 (재발) | 높음 | 중간 | 파일 기반 프롬프트 전달 (시나리오3 Fix) 적용 |

---

*이 시나리오는 cmux-win의 모든 역량 — 패널 관리, 워커 조율, 장애 복구, RSI, 대시보드 모니터링 — 을 동시에 극한까지 시험합니다.*
*시나리오 1~3이 "이 시스템이 작동하는가?"를 검증했다면, 시나리오 4는 "이 시스템이 실전에서 살아남는가?"를 검증합니다.*
