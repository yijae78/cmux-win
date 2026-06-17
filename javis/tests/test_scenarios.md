# cmux-win 통합 테스트 시나리오

> 작성일: 2026-06-17
> 목적: cmux-win의 6/7/8-pane 구성에서 패널 생성·균등분할·워커 협업·대시보드가 정상 작동하는지 검증
> 원칙: 바탕화면 원본 프로젝트 절대 수정 금지 — 필요한 파일은 `javis/tests/workspace/`에 복사하여 사용

---

## 시나리오 1: 기본 6-pane Fleet 부트스트랩 + 코드 리뷰

**패널 수**: 6개 (Master + CSO + Worker1~3 + Dashboard)
**활용 프로젝트**: `EnvironmentScan-system-main-v4` (환경 스캔 시스템, Python 782줄)
**소요 시간**: 약 5~10분

### 목적
기본 Javis Fleet 부트스트랩이 처음부터 끝까지 정상 작동하는지 전수 검증

### 사전 준비
```bash
# 1. 프로젝트 파일 복사 (원본 절대 건드리지 않음)
mkdir -p /c/dev/cmux-win/javis/tests/workspace/env-scan
cp <바탕화면>/EnvironmentScan-system-main-v4/*.py /c/dev/cmux-win/javis/tests/workspace/env-scan/
cp <바탕화면>/EnvironmentScan-system-main-v4/README.md /c/dev/cmux-win/javis/tests/workspace/env-scan/
```

### 실행 단계

| 단계 | 동작 | 검증 포인트 |
|------|------|-------------|
| 1 | Master에게 "너는 마스터다" 입력 | 부트스트랩 스크립트 실행 |
| 2 | 5개 패널 자동 생성 확인 | `tmux list-panes` → 6개 (%0~%5) |
| 3 | 라벨 확인 | Master, CSO, Worker1(Claude), Worker2(AGY), Worker3(Codex), Dashboard |
| 4 | 균등분할 확인 | 6개 패널이 균등하게 분할됨 |
| 5 | 대시보드 가동 확인 | `http://localhost:8500` 브라우저 패널에서 렌더링 |
| 6 | Worker1에 작업 지시 | "javis/tests/workspace/env-scan/monitor.py를 분석하고 코드 품질 보고서 작성" |
| 7 | Worker2(AGY)에 리뷰 지시 | "Worker1의 분석 결과를 리뷰하고 놓친 점 지적" |
| 8 | Worker3(Codex)에 검수 지시 | "monitor.py의 보안 취약점과 성능 이슈 검토" |
| 9 | 대시보드 상태 확인 | 플릿 현황에서 각 워커가 "작업중" → "작업완료"로 전환 |
| 10 | 결과 취합 | Master가 3개 워커의 산출물을 종합하여 최종 보고서 작성 |

### 체크리스트

- [ ] 부트스트랩 6-pane 생성 성공
- [ ] 모든 라벨 정확히 설정됨
- [ ] 패널 균등분할 적용됨
- [ ] 대시보드 Streamlit 가동 + 브라우저 패널 렌더링
- [ ] 대시보드 플릿 현황 5가지 상태 정확 반영 (대기→작업중→작업완료)
- [ ] Worker1(Claude) 작업 수신 및 실행
- [ ] Worker2(AGY) 리뷰 수신 및 실행
- [ ] Worker3(Codex) 검수 수신 및 실행
- [ ] 컨텍스트 경고(CTX) 감지 시 /compact 자동 전송
- [ ] 최종 산출물 `javis/tests/output/scenario1/` 저장

### 산출물
- `javis/tests/output/scenario1/code_review_report.md` — 코드 리뷰 종합 보고서

---

## 시나리오 2: 7-pane 동적 확장 + 병렬 분석

**패널 수**: 7개 (6-pane 기본 + Worker4 추가)
**활용 프로젝트**: `GlobalNews-Crawling-AgenticWorkflow` (글로벌뉴스 크롤링 시스템, 다중 모듈)
**소요 시간**: 약 10~15분

### 목적
기본 Fleet에서 워커를 동적으로 추가했을 때 패널 생성·균등분할 재조정·워커 협업이 정상 작동하는지 검증

### 사전 준비
```bash
# 프로젝트 구조 복사
mkdir -p /c/dev/cmux-win/javis/tests/workspace/globalnews
cp -r <바탕화면>/GlobalNews-Crawling-AgenticWorkflow/src/ /c/dev/cmux-win/javis/tests/workspace/globalnews/src/
cp <바탕화면>/GlobalNews-Crawling-AgenticWorkflow/README.md /c/dev/cmux-win/javis/tests/workspace/globalnews/ 2>/dev/null
cp <바탕화면>/GlobalNews-Crawling-AgenticWorkflow/CLAUDE.md /c/dev/cmux-win/javis/tests/workspace/globalnews/ 2>/dev/null
```

### 실행 단계

| 단계 | 동작 | 검증 포인트 |
|------|------|-------------|
| 1 | 시나리오 1의 6-pane Fleet 가동 상태에서 시작 | 6-pane 정상 확인 |
| 2 | Worker4(Claude) 패널 추가 | `tmux split-window -h "claude"` |
| 3 | 7-pane 균등분할 실행 | `workspace.set_layout` API로 7개 패널 균등화 |
| 4 | Worker4 라벨 설정 | `surface.rename` → "Worker4(Claude)" |
| 5 | `tmux list-panes` 확인 | 7개 패널 (%0~%6) |
| 6 | 대시보드 확인 | 플릿 현황에 Worker4 표시됨 |
| 7 | **병렬 작업 지시** | |
| 7a | Worker1 → 크롤링 모듈 분석 | `src/crawling/` 디렉토리 분석 |
| 7b | Worker4 → 분석 모듈 분석 | `src/analysis/` 디렉토리 분석 |
| 8 | Worker2(AGY) → 크롤링 vs 분석 교차 리뷰 | 두 모듈 간 인터페이스 정합성 검토 |
| 9 | Worker3(Codex) → 전체 아키텍처 검수 | 모듈 간 의존성, 에러 핸들링 검토 |
| 10 | 대시보드 모니터링 | 4개 워커 동시 "작업중" 표시 확인 |
| 11 | Master 종합 | 4개 산출물 취합하여 아키텍처 분석 보고서 작성 |

### 체크리스트

- [ ] 7번째 패널 동적 생성 성공
- [ ] 7-pane 균등분할 정확히 재조정됨
- [ ] Worker4 라벨 "Worker4(Claude)" 설정됨
- [ ] 대시보드에 Worker4 자동 반영
- [ ] Worker1과 Worker4 병렬 작업 동시 수행
- [ ] 4개 워커 동시 "작업중" 대시보드 표시
- [ ] 워커 간 결과물 참조 가능 (capture-pane 또는 파일 공유)
- [ ] 균등분할 후 모든 패널이 사용 가능한 크기 유지
- [ ] 최종 산출물 `javis/tests/output/scenario2/` 저장

### 산출물
- `javis/tests/output/scenario2/architecture_report.md` — 아키텍처 분석 보고서
- `javis/tests/output/scenario2/crawling_analysis.md` — 크롤링 모듈 분석
- `javis/tests/output/scenario2/analysis_module_review.md` — 분석 모듈 리뷰

---

## 시나리오 3: 8-pane 최대 구성 + 교차 프로젝트 RSI

**패널 수**: 8개 (6-pane 기본 + Worker4 + Worker5 추가)
**활용 프로젝트**: `Office-Monitor` (사무실 모니터링 시스템, Python) + `EnvironmentScan-system-main-v4` (환경 스캔)
**소요 시간**: 약 15~20분

### 목적
8-pane 최대 구성에서 다중 프로젝트를 교차 분석하고, RSI(재귀적 자기개선) 사이클을 돌려 씨윈의 극한 성능을 검증

### 사전 준비
```bash
# Office-Monitor 복사
mkdir -p /c/dev/cmux-win/javis/tests/workspace/office-monitor
cp <바탕화면>/Office-Monitor/*.py /c/dev/cmux-win/javis/tests/workspace/office-monitor/
cp <바탕화면>/Office-Monitor/README.md /c/dev/cmux-win/javis/tests/workspace/office-monitor/ 2>/dev/null

# EnvironmentScan 복사 (시나리오 1에서 이미 복사됨)
# javis/tests/workspace/env-scan/ 존재 확인
```

### 실행 단계

| 단계 | 동작 | 검증 포인트 |
|------|------|-------------|
| 1 | 시나리오 2의 7-pane 상태에서 시작 | 7-pane 정상 확인 |
| 2 | Worker5(AGY) 패널 추가 | `tmux split-window -h "agy"` |
| 3 | 8-pane 균등분할 실행 | `workspace.set_layout` API로 8개 패널 균등화 |
| 4 | Worker5 라벨 설정 | `surface.rename` → "Worker5(AGY)" |
| 5 | `tmux list-panes` 확인 | 8개 패널 (%0~%7) |
| 6 | 대시보드 확인 | 플릿 현황에 Worker4 + Worker5 표시 |
| 7 | **교차 프로젝트 배치** | |
| 7a | Worker1 → Office-Monitor 코드 분석 | `detection_engine.py`, `monitor_engine.py` 분석 |
| 7b | Worker4 → EnvironmentScan 코드 분석 | `monitor.py`, `launch_monitor.py` 분석 |
| 8 | **교차 리뷰 (RSI Round 1)** | |
| 8a | Worker2(AGY) → 두 프로젝트의 모니터링 패턴 비교 분석 | 공통 패턴 추출, 우수 사례 식별 |
| 8b | Worker5(AGY) → 두 프로젝트의 아키텍처 비교 | 구조적 차이, 개선 포인트 |
| 9 | Worker3(Codex) → 교차 리뷰 결과 기술 검증 | 코드 수준 정합성 확인 |
| 10 | **RSI 종합 (Master)** | |
| 10a | 5개 워커 산출물 취합 | |
| 10b | 두 프로젝트에서 추출한 모니터링 모범 패턴 문서화 | |
| 10c | 개선 제안 보고서 작성 | |
| 11 | 대시보드 전체 확인 | 8개 에이전트 상태, 토큰 사용량, Rate Limit |
| 12 | 컨텍스트 관리 테스트 | 워커 중 1개 이상 CTX 경고 발생 시 /compact 자동 실행 검증 |
| 13 | Worker4, Worker5 패널 닫기 | `panel.close` → 6-pane 복귀 |
| 14 | 6-pane 복귀 후 균등분할 확인 | 패널 닫힌 후 남은 6개 재균등화 |

### 체크리스트

- [ ] 8번째 패널 동적 생성 성공
- [ ] 8-pane 균등분할 정확히 적용됨 (8개 모두 사용 가능한 크기)
- [ ] Worker4 + Worker5 라벨 정확히 설정됨
- [ ] 대시보드에 8개 에이전트 전부 표시
- [ ] 5개 워커 동시 작업 수행 (최대 부하)
- [ ] 교차 프로젝트 분석 결과 참조 가능
- [ ] RSI 산출물 생성 및 저장
- [ ] 워커 패널 닫기 후 6-pane 복귀 + 재균등분할 성공
- [ ] 대시보드에서 닫힌 워커 "죽음" 또는 제거 반영
- [ ] 최종 산출물 `javis/tests/output/scenario3/` 저장

### 산출물
- `javis/tests/output/scenario3/cross_project_report.md` — 교차 프로젝트 분석 보고서
- `javis/tests/output/scenario3/monitoring_patterns.md` — 모니터링 모범 패턴 문서
- `javis/tests/output/scenario3/rsi_improvements.md` — RSI 개선 제안

---

## 시나리오 4: 자비스 자가진화 — 풀스택 구축 + 장애 복구 + RSI 3R ★★★★★

**패널 수**: 8개 (6-pane 기본 + Worker4 + Worker5)
**구축 대상**: `javis/watchdog/` — Fleet Auto-Recovery Watchdog (9개 .py 파일)
**소요 시간**: 약 80분 (1시간 20분)

### 목적
**보고서가 아닌 실제 작동하는 코드**를 5명의 워커가 의존성 체인으로 구축하고, 중간에 장애를 주입하여 복구 능력을 검증하며, RSI 3라운드로 코드 품질을 측정 가능하게 개선

### 이전 시나리오와의 차별점
- 산출물 = 실제 Python 코드 (보고서 X)
- 워커 간 의존성 체인 (A→B→C)
- 의도적 장애 주입 4회 (Chaos Engineering)
- pytest 자동 실행으로 Pass/Fail 판정
- 구축한 코드가 실제 플릿에서 작동하는지 실전 검증

### 5 Phase 요약

| Phase | 내용 | 시간 | 핵심 난관 |
|-------|------|------|-----------|
| 0 | 8-pane 준비 | 5분 | - |
| 1 | 아키텍처 논쟁 + 합의 | 15분 | 5워커 토론→합의 도출 |
| 2 | 병렬 구현 | 25분 | 의존성 체인 동기화 |
| 3 | 장애 주입 (Phase 2 중) | - | 워커 종료/컨텍스트 소진/대시보드 종료 |
| 4 | 통합 + RSI 3라운드 | 20분 | pytest 통과율 단조 증가 |
| 5 | 실전 검증 | 10분 | 워치독이 실제 장애 감지 |

### 성공 기준 (전부 충족)
- [ ] `javis/watchdog/` 9개 .py 파일 생성
- [ ] `python -m pytest` 전체 통과
- [ ] `python -m javis.watchdog --help` 정상 출력
- [ ] RSI 3라운드 점수 단조 증가 (Baseline < R1 < R2 < Final)
- [ ] 장애 주입 4건 중 3건 이상 5분 내 복구
- [ ] 핸드오프 문서 2건 이상 생성
- [ ] Phase 5 실전 검증에서 "dead" 감지 성공

### 상세 설계
- `javis/tests/output/scenario4/scenario4_design.md` 참조

### 산출물
- `javis/watchdog/` — 워치독 패키지 (9개 .py 파일)
- `javis/tests/output/scenario4/scenario4_design.md` — 설계 문서
- `javis/tests/output/scenario4/design_final.md` — 합의된 아키텍처
- `javis/tests/output/scenario4/rsi_r1_review.md` — RSI Round 1
- `javis/tests/output/scenario4/rsi_r2_review.md` — RSI Round 2
- `javis/tests/output/scenario4/rsi_r3_cross_review.md` — RSI Round 3
- `javis/tests/output/scenario4/final_report.md` — 최종 보고서

---

## 공통 검증 항목

모든 시나리오에서 반드시 확인할 사항:

### 패널 관리
- [ ] `tmux split-window -h`로 패널 생성 (-v 절대 금지)
- [ ] `workspace.set_layout`으로 균등분할 (panel.resize 단독 사용 금지)
- [ ] `surface.rename`으로 라벨 설정 (activeSurfaceId 사용, panelId 금지)
- [ ] 패널 닫힌 후 남은 패널 재균등분할

### 대시보드
- [ ] Streamlit 가동 (port 8500)
- [ ] 데이터 서버 가동 (port 8501)
- [ ] JS fetch 5초 간격 anti-flicker 업데이트
- [ ] 5가지 상태 정확 반영: 대기 / 작업중 / 작업완료 / 오류 / 죽음
- [ ] CTX/CTX! 컨텍스트 경고 표시
- [ ] 토큰 사용량 실시간 반영 (UTC→로컬 시간대 정확)

### 워커 관리
- [ ] 워커 컨텍스트 20% 이하 시 /compact (exit 금지)
- [ ] 마스터 autoCompact 활성화 확인
- [ ] 워커 idle 5분+ 감지 시 재지시
- [ ] 원본 프로젝트 파일 절대 수정 금지

### 결과물 저장 경로
```
/c/dev/cmux-win/javis/tests/
├── test_scenarios.md          ← 이 문서
├── workspace/                 ← 복사된 프로젝트 파일
│   ├── env-scan/
│   ├── globalnews/
│   └── office-monitor/
└── output/                    ← 테스트 산출물
    ├── scenario1/
    ├── scenario2/
    ├── scenario3/
    └── scenario4/
```
