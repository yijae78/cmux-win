# 시나리오 2 — GlobalNews-Crawling-AgenticWorkflow 아키텍처 분석 종합 보고서

**대상**: GlobalNews-Crawling-AgenticWorkflow (글로벌뉴스 크롤링+분석 시스템)
**분석 모듈**: `src/crawling/` (20+ 파일), `src/analysis/` (8단계 파이프라인), `src/storage/`, `src/utils/`
**분석일**: 2026-06-17
**참여 워커**: Worker1(Claude) — 크롤링 모듈, Worker2(AGY) — 교차 인터페이스, Worker3(Codex) — 전체 아키텍처, Worker4(Claude) — 분석 모듈

---

## Executive Summary

4개 워커의 독립적 분석을 종합한 결과, GlobalNews 시스템은 **운영급(production-grade) 크롤링 인프라**와 **연구급(research-grade) 분석 파이프라인**을 결합한 높은 완성도의 시스템입니다. 다만 두 모듈 간 **인터페이스 계약**과 **상태 관리 일관성**에서 개선이 필요합니다.

| 평가 항목 | 점수 | 요약 |
|-----------|------|------|
| 크롤링 아키텍처 | 7.5/10 | Conductor 패턴 + 4-Level 재시도 + Never-Abandon 우수. God Class/중복 코드 문제 |
| 분석 파이프라인 | 7.5/10 | 8단계 순차 + 체크포인트 + 메모리 관리 우수. CPU 병렬화 미흡 |
| 모듈 간 인터페이스 | 6/10 | JSONL→Parquet 변환 안정적이나, 메타데이터 유실 + 에러 컨텍스트 단절 |
| 보안 | 7/10 | 내부 경로 생성으로 주입 위험 낮음. TOCTOU, atomic write 불일치 |
| 에러 처리 | 8/10 | 계층적 예외 + Circuit Breaker + Graceful Degradation 우수 |
| 전체 아키텍처 | 7/10 | Staged Monolith 설계 적절. 복구 상태 SOT 분산, self-recovery 미통합 |
| **종합** | **7.2/10** | 운영급 크롤링 + 연구급 분석 결합 우수. 인터페이스·상태 관리 정비 필요 |

---

## 1. 4개 워커 공통 지적 사항 (Critical — 3개 이상 워커 일치)

### 1.1 `crawler.py`와 `pipeline.py`의 역할 중복
- **Worker1**: Crawler 클래스가 CrawlingPipeline과 거의 동일한 파이프라인을 독립 구현 — Dead Code
- **Worker3**: pipeline.py가 주 경로, crawler.py는 Writer/State만 재사용. Crawler 클래스는 중복 오케스트레이터
- **Worker2**: 크롤링 레이어 내부 오케스트레이터 중복 확인

> **권장**: `Crawler` 클래스를 deprecated하고 `CrawlingPipeline`으로 통합

### 1.2 `assert` 문의 프로덕션 사용
- **Worker1**: pipeline.py 전반에 assert 남용 (L1108, 1113, 1358 등)
- **Worker3**: 런타임 필수 조건이 assert에 의존 — `python -O`에서 방어 소실
- **Worker4**: 분석 파이프라인에서도 동일 패턴

> **권장**: `assert` → `if ... is None: raise RuntimeError(...)` 명시적 예외로 전환

### 1.3 Atomic Write 불일치
- **Worker1**: `_save_bypass_state()`에 atomic write 미적용 (CrawlState는 적용)
- **Worker2**: Parquet 쓰기도 최종 경로에 직접 기록
- **Worker4**: docstring에 temp+rename 명시했으나 실제 미구현

> **권장**: 모든 상태/데이터 파일에 temp → `os.replace()` 패턴 통일

---

## 2. 2개 워커 이상 지적 사항 (High)

### 2.1 크롤링-분석 메타데이터 유실
- **Worker2(AGY)**: `crawl_method`, `crawl_tier`, `is_paywall_truncated`가 Parquet 변환 시 누락
- **Worker3(Codex)**: 분석 모듈이 JSONL 텍스트만 읽어 장애 컨텍스트 인계 불가

> **권장**: `ARTICLES_PA_SCHEMA`에 크롤링 메타 필드 추가

### 2.2 God Class — `CrawlingPipeline` (2,377줄)
- **Worker1**: URL 발견, 추출, 중복 제거, 재시도, bypass, 상태 영속화를 모두 담당
- **Worker3**: private field 직접 접근 (`self._guard._circuit_breakers`)

> **권장**: `NeverAbandonRunner`, `BypassHandler`, `FailureReporter` 등 분리

### 2.3 메모리 유틸리티 중복
- **Worker4**: Stage 1의 `_get_rss_mb()` vs 파이프라인의 `MemoryMonitor.get_rss_gb()` 중복
- **Worker4**: `os.uname()` 사용 — Windows에서 `AttributeError`

> **권장**: `MemoryMonitor` 하나로 통일, Windows 호환 확보

---

## 3. 개별 워커 고유 발견 사항

### Worker1(Claude) — 크롤링 모듈 고유
- `RawArticle` frozen dataclass 재생성 비용 → `dataclasses.replace()` 권장
- `CrawlState.mark_site_complete()`의 `processed_urls` 타입 불일치 (list vs set)
- `_merge_result()`의 articles.extend() — H-16 메모리 최적화와 모순
- RSS fallback 코드 약 40줄 중복
- `compute_content_hash()` 한국어 정규화 한계

### Worker2(AGY) — 인터페이스 고유
- `RawArticle.source_id` → Parquet `source` 축소 결합, `source_name` 누락
- SQLite `unicode61` FTS5 토크나이저 융합 우수
- 크롤러 `.crawl_state.json`과 분석 레이어 간 헬스 모니터링 동기화 부재

### Worker3(Codex) — 아키텍처 고유
- 복구 상태 SOT 분산 (CrawlState, RetryManager, CircuitBreaker, bypass_state.json, failure report)
- `self_recovery.py`가 main.py 실행 경로에 미통합
- Circuit Breaker 계층 중복 (error_handler.py + NetworkGuard 내부 + CircuitBreakerCoordinator)
- 실패 URL과 성공 URL이 같은 processed set — resume semantics 약화

### Worker4(Claude) — 분석 모듈 고유
- Stage 1 단일 스레드 순차 처리 — 멀티코어 미활용
- `langdetect` 매 호출 시 seed 재설정 + `detect()` + `detect_langs()` 이중 호출
- Stage 3 zero-shot 파이프라인: emotion(8) + STEEPS(6) 이중 추론 → 통합 추론으로 50% 절감 가능
- `_estimate_coverage()` O(N^2) 코사인 유사도 병목
- Kiwi 모델 하드코딩 경로 `C:/kiwi_model`

---

## 4. 모듈별 종합 점수

| 모듈 | 아키텍처 | 보안 | 성능 | 에러 처리 | 종합 |
|------|----------|------|------|-----------|------|
| crawling | 7/10 | 7/10 | 7/10 | 8/10 | **7.3** |
| analysis | 8/10 | 6/10 | 6/10 | 7/10 | **6.8** |
| storage | 8/10 | 7/10 | 8/10 | 7/10 | **7.5** |
| interface | 6/10 | — | — | 5/10 | **5.5** |

---

## 5. 개선 우선순위

### Phase 1 — 즉시 (데이터 무결성·안전성)
1. `CrawlState.mark_site_complete()` 타입 불일치 수정 (list→set)
2. Atomic write 패턴 전체 통일 (bypass_state, Parquet 출력)
3. `assert` → 명시적 예외 전환
4. Windows 호환: `os.uname()` → `platform.system()` 통일

### Phase 2 — 단기 (성능·효율)
5. Stage 1 병렬화 (ProcessPoolExecutor 또는 Kiwi `pipe()`)
6. Stage 3 zero-shot 통합 추론 (14 라벨 한 번에)
7. `langdetect` 최적화 (seed 1회, detect_langs() 단독)
8. `dataclasses.replace()` 적용

### Phase 3 — 중기 (아키텍처)
9. `Crawler` 클래스 deprecated → `CrawlingPipeline` 통합
10. `CrawlingPipeline` God Class 분리 (2,377줄 → 4~5개 모듈)
11. Parquet 스키마에 크롤링 메타데이터 추가
12. 복구 상태 SOT 통합 (단일 상태 저장소)
13. `self_recovery.py` main.py 실행 경로 통합

---

## 6. 워커별 원본 보고서

| 워커 | 파일 | 크기 | 담당 |
|------|------|------|------|
| Worker1(Claude) | `crawling_analysis.md` | 11,662 bytes | 크롤링 모듈 코드 리뷰 |
| Worker2(AGY) | `cross_module_review.md` | 6,878 bytes | 모듈 간 인터페이스 리뷰 |
| Worker3(Codex) | `architecture_review.md` | 20,103 bytes | 전체 아키텍처 리뷰 |
| Worker4(Claude) | `analysis_module_review.md` | 13,602 bytes | 분석 모듈 코드 리뷰 |

---

## 7. 시나리오 2 테스트 검증 결과

| 검증 항목 | 결과 |
|-----------|------|
| 7번째 패널(Worker4) 동적 생성 | 성공 — %6 pane 생성 |
| 7-pane 균등분할 재조정 | 성공 — workspace.set_layout API |
| Worker4 라벨 "Worker4(Claude)" | 성공 — surface.rename API |
| 대시보드에 Worker4 자동 반영 | 성공 (터미널 제한 5→8 수정 후) |
| Worker1과 Worker4 병렬 작업 | 성공 — 동시 크롤링/분석 모듈 분석 |
| 4개 워커 동시 "작업중" | 확인 — 모든 워커 동시 가동 |
| 워커 간 결과물 파일 공유 | 성공 — output/scenario2/ 공용 디렉토리 |
| Claude 워커 컨텍스트 관리 | 이슈 발견 — CLAUDE.md 43k 부하로 컨텍스트 조기 소진 |
| 최종 산출물 저장 | 성공 — 5개 파일 scenario2/ 저장 |

### 발견된 cmux-win 이슈
1. **대시보드 터미널 제한 `:5`**: Worker4 추가 시 표시 안 됨 → `:8`로 수정
2. **Claude 워커 컨텍스트 소진**: 43k CLAUDE.md + 대용량 소스 파일 = 빠른 컨텍스트 풀 → 집중 프롬프트 필요

---

*본 보고서는 Javis Fleet 시나리오 2 테스트의 일환으로 생성되었습니다.*
*마스터가 4개 워커의 독립 분석을 종합하여 작성.*
