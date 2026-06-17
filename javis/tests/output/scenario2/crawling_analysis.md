# 크롤링 레이어 코드 리뷰

> **대상 파일**: `crawler.py`, `pipeline.py`, `contracts.py`
> **리뷰 일시**: 2026-06-17
> **리뷰 관점**: 아키텍처, 보안, 성능, 에러 처리

---

## 1. 아키텍처 분석

### 1.1 전체 구조 — 강점

| 항목 | 평가 |
|------|------|
| **계층 분리** | `contracts.py`(데이터 계약) → `crawler.py`(단일 사이트 오케스트레이터) → `pipeline.py`(전체 파이프라인) 3계층 분리가 명확. Crawling Layer → Analysis Layer 경계가 `RawArticle` 데이터클래스로 엄격히 정의됨 |
| **Conductor 패턴** | `CrawlingPipeline`이 14개 이상의 서브시스템(NetworkGuard, URLDiscovery, ArticleExtractor, DedupEngine, UAManager, CircuitBreaker, AntiBlock, DynamicBypass, RetryManager 등)을 조율하는 Conductor 역할을 수행. 책임 분리 우수 |
| **재개(Resume) 지원** | `CrawlState` JSON 기반 상태 영속화로 중단-재개 가능. Atomic write (temp → rename) 패턴 사용 |
| **Never-Abandon 철학** | 4-Level 재시도 → Never-Abandon 루프 → Multi-Pass 추가 패스 — "절대 포기하지 않는" 설계 |
| **Cooperative Deadline** | 스레드 killing 대신 URL 단위 경계에서 자발적 양보. `deadline_yielded` 플래그로 부분 결과 보존 |

### 1.2 아키텍처 — 문제점

#### (A-1) `crawler.py`와 `pipeline.py`의 역할 중복

`Crawler.crawl_site()`과 `CrawlingPipeline._crawl_site_with_retry()`가 거의 동일한 파이프라인(URL 발견 → 중복 제거 → 추출 → JSONL 기록 → 상태 갱신)을 독립적으로 구현한다. `crawler.py`의 `Crawler` 클래스는 `pipeline.py`에서 전혀 사용되지 않으며 사실상 Dead Code에 가깝다.

- **위험**: 버그 수정이 한쪽에만 적용되면 동작 불일치 발생
- **권장**: `Crawler`를 deprecated하거나, `pipeline.py`의 내부 구현으로 통합

#### (A-2) God Class 경향 — `CrawlingPipeline`

`CrawlingPipeline`은 약 2,377줄, 25개 이상의 메서드로 구성되어 있다. URL 발견, 추출, 중복 제거, 재시도, bypass, 상태 영속화, 리포트 생성을 모두 담당하는 God Class다.

- **위험**: 테스트 어려움, 변경 영향 범위 과대
- **권장**: `NeverAbandonRunner`, `BypassDiscoveryHandler`, `FailureReporter` 등을 별도 클래스로 추출

#### (A-3) `Any` 타입 남용

`crawler.py`에서 `browser_renderer: Any`, `adaptive_extractor: Any`, `_dedup_checker: Any`, `_ua_manager: Any`로 선언. Protocol 또는 ABC를 정의하지 않아 타입 안전성이 없다.

```python
# 현재
self._dedup_checker: Any = None

# 권장
class DedupProtocol(Protocol):
    def is_duplicate(self, url: str, content_hash: str) -> bool: ...
    def register(self, url: str, content_hash: str) -> None: ...
```

#### (A-4) 순환 의존 징후

`pipeline.py` 내부에서 조건부 `from src.crawling.block_detector import BlockType`와 `from src.crawling.dynamic_bypass import BlockType`를 함수 내부에서 반복 import한다. 이는 순환 의존을 회피하기 위한 지연 임포트로 보이며, 의존 구조 개선이 필요하다.

---

## 2. 보안 분석

### (S-1) 크롤링 상태 파일 경로 주입 — 낮은 위험

`CrawlState`의 `state_dir`이 외부 입력에서 올 수 있다면 path traversal 가능성이 있으나, 실제로는 `DATA_RAW_DIR / date` 구조로 내부에서 생성되므로 현실적 위험은 낮다.

### (S-2) JSONL 출력에 미정제 HTML 포함 가능

`_write_bypass_result()`에서 bypass로 얻은 HTML을 `ArticleExtractor`에 전달해 파싱 후 JSONL에 기록한다. 추출 실패 시 원시 HTML이 body 필드에 들어갈 수 있으며, 하류 시스템에서 XSS 벡터가 될 수 있다.

- **권장**: `RawArticle` 생성 시 body 필드에 대한 HTML 태그 제거 또는 sanitization 검증 추가

### (S-3) `os.replace()` 경쟁 조건

`JSONLWriter.close()`에서 기존 파일 존재 시 append 경로, 미존재 시 `os.replace()` 경로를 탄다. 파일 존재 여부 확인(L138)과 실제 작업(L140/L148) 사이에 TOCTOU(Time-of-Check-to-Time-of-Use) 경쟁 조건이 있다. 동일 경로에 대해 여러 프로세스가 동시에 실행될 경우 데이터 유실 가능.

- **권장**: `fcntl.flock()` 또는 Windows `msvcrt.locking()` 등 파일 잠금 추가

### (S-4) bypass_state.json 무결성 보호 없음

`_save_bypass_state()`가 atomic write 없이 직접 `open("w")`로 기록한다. 크래시 시 파일 손상 가능. `CrawlState.save()`에서는 temp → replace 패턴을 사용하나, bypass state에서는 누락.

```python
# 현재 (pipeline.py L1817-1818)
with open(BYPASS_STATE_PATH, "w", encoding="utf-8") as f:
    json.dump(self._bypass_state, f, ...)

# 권장: CrawlState.save()와 동일한 atomic write 패턴
```

---

## 3. 성능 분석

### (P-1) RawArticle frozen dataclass 재생성 비용

`pipeline.py` L2133-2148에서 `crawl_method` 오버라이드를 위해 14개 필드를 일일이 복사하여 새 `RawArticle`을 생성한다. `frozen=True` 때문인데, 매 기사마다 객체 재생성은 비효율적이다.

- **권장**: `dataclasses.replace()` 사용으로 간결화 + 성능 개선

```python
# 현재: 14줄 수동 복사
article = RawArticle(url=article.url, title=article.title, ...)

# 권장: 1줄
from dataclasses import replace
article = replace(article, crawl_method=effective_method)
```

### (P-2) CrawlState의 processed_urls set → sorted list 변환

`CrawlState.save()`에서 매 저장마다 `sorted(set)` 변환을 수행한다 (L229). 대규모 사이트에서 수천 개의 URL이 누적되면 O(n log n) 정렬 비용이 누적된다.

- **현재 수준**: 단일 사이트 URL 수가 수천 수준이면 무시 가능
- **스케일링 시**: 정렬 생략 (list 변환만) 또는 save 빈도 최적화 고려

### (P-3) 중복된 RSS fallback 로직

`_crawl_urls()`의 `NetworkError` 핸들러(L2217-2236)와 `BlockDetectedError` 핸들러(L2249-2271)에 거의 동일한 RSS fallback 코드가 복붙되어 있다. 약 20줄 × 2 = 40줄의 중복.

- **권장**: 공통 헬퍼 메서드 추출

### (P-4) ThreadPoolExecutor 동시성 설정

`DEFAULT_CONCURRENCY = 5`가 하드코딩되어 있다. 사이트 수, 네트워크 대역폭, rate limit에 따라 최적값이 달라지므로 설정 파일 또는 환경변수로 외부화가 바람직하다.

### (P-5) result.articles 메모리 누적

`_merge_result()`(L2335)에서 `target.articles.extend(source.articles)`로 기사 객체를 메모리에 누적한다. L2193-2197 주석에서 H-16 fix로 메모리 최적화를 언급하면서도, `_merge_result`에서는 여전히 articles 리스트를 확장한다. 116개 사이트 대규모 실행 시 메모리 이슈 재발 가능.

---

## 4. 에러 처리 분석

### 4.1 에러 처리 — 강점

| 항목 | 평가 |
|------|------|
| **계층적 예외 체계** | `CrawlError` → `NetworkError`, `ParseError`, `BlockDetectedError`, `RateLimitError`로 명확한 예외 계층 |
| **사이트 격리** | `crawl_site()`/`_crawl_site_with_retry()`가 사이트별 독립 처리. 한 사이트 실패가 다른 사이트에 영향 없음 |
| **Circuit Breaker** | 연속 실패 시 해당 사이트 자동 차단, Never-Abandon 정책 시 force half-open 전환 |
| **4-Level 재시도** | L1(NetworkGuard 내부) → L2(Standard/TotalWar) → L3(라운드) → L4(파이프라인 재시작) 체계적 재시도 |
| **Graceful degradation** | 페이지 차단 시 RSS 제목 fallback, discovery 실패 시 bypass engine fallback |

### 4.2 에러 처리 — 문제점

#### (E-1) 조용한 예외 삼킴 (Silent Exception Swallowing)

```python
# crawler.py L480-481
except Exception:
    pass  # UA manager 오류 무시

# crawler.py L502-503
except Exception:
    pass  # dedup register 오류 무시
```

이 패턴이 여러 곳에서 반복된다. 최소한 `logger.debug()`로 기록해야 디버깅이 가능하다.

#### (E-2) assert 문의 프로덕션 사용

`pipeline.py` 전반에 `assert self._retry_manager is not None` 등의 assert 문이 산재한다 (L1108, 1113, 1358, 1518, 2020-2026 등). Python에서 `-O` 최적화 플래그로 실행 시 assert가 제거되므로, 프로덕션 환경에서 None 참조 예외가 발생할 수 있다.

- **권장**: 초기화 검증이 필요하면 명시적 `if ... is None: raise RuntimeError(...)` 사용

#### (E-3) CrawlState.mark_site_complete()의 타입 불일치

```python
# L302: 새 엔트리 생성 시 list 사용
self._state[source_id] = {"processed_urls": []}

# L274: 다른 곳에서는 set 사용
self._state[source_id] = {"processed_urls": set(), "last_updated": ""}
```

`mark_site_complete()`에서 `processed_urls`를 빈 리스트로 초기화하지만, 다른 메서드에서는 set을 기대한다. `is_url_processed()`에서 `in` 연산자가 리스트에 대해 O(n)이 된다.

#### (E-4) Never-Abandon 루프의 무한 실행 가능성

`_run_never_abandon_loop()`에서 `while self._retry_manager.advance_never_abandon_cycle()`로 루프를 돌며, `DISCOVERY_BYPASS_MAX_ATTEMPTS`와 `time.sleep(min(delay, 120.0))`로 제어한다. 하지만 `advance_never_abandon_cycle()`의 종료 조건이 외부 모듈에 의존하므로, 해당 모듈의 버그로 무한루프에 빠질 수 있다.

- **권장**: 루프에 절대 상한(예: `max_cycles = 50`) 가드 추가

#### (E-5) `from_jsonl_dict()` 검증 부재

`RawArticle.from_jsonl_dict()`가 `data["url"]`과 `data["title"]`에서 KeyError를 발생시킬 수 있다. 외부 JSONL 파일을 읽을 때 누락 필드에 대한 방어 코드가 없다. docstring에는 "title이 비어있거나 url이 유효하지 않으면 거부해야 한다"고 명시하지만 실제 검증 로직은 부재.

#### (E-6) compute_content_hash()의 정규화 한계

```python
normalized = " ".join(body.lower().split())
```

이 정규화는 영문 기준으로 설계되었다. 한국어(`ko`)와 같이 공백 규칙이 다른 언어에서는 동일 기사의 미세한 공백 차이로 다른 해시가 생성될 수 있다. 또한 HTML 엔티티(`&amp;`, `&lt;` 등)가 잔류할 경우 동일 콘텐츠에 대해 서로 다른 해시가 생성된다.

---

## 5. 종합 평가

| 영역 | 점수 | 요약 |
|------|------|------|
| **아키텍처** | 7/10 | 계층 분리와 Conductor 패턴 우수. 단, `crawler.py`↔`pipeline.py` 중복과 God Class 문제 |
| **보안** | 7/10 | 입력 경로 내부 생성으로 주입 위험 낮음. bypass HTML sanitization, atomic write 일관성 부족 |
| **성능** | 7/10 | Cooperative deadline + ThreadPoolExecutor 설계 적절. frozen dataclass 재생성, 메모리 누적 이슈 존재 |
| **에러 처리** | 8/10 | 4-Level 재시도 + Circuit Breaker + Never-Abandon 구조 우수. 조용한 예외 삼킴, assert 남용 주의 |

### 우선 수정 권장 사항 (Critical → High)

1. **[Critical]** `_merge_result()`의 `articles.extend()` — H-16 메모리 최적화와 모순. 대규모 실행 시 OOM 위험
2. **[Critical]** `CrawlState.mark_site_complete()`의 `processed_urls` 타입 불일치 (list vs set)
3. **[High]** `_save_bypass_state()`에 atomic write 패턴 적용 (데이터 무결성)
4. **[High]** `assert` → 명시적 예외로 전환 (프로덕션 안전성)
5. **[High]** `crawler.py` `Crawler` 클래스 — deprecated 선언 또는 `pipeline.py`로 통합
6. **[Medium]** `dataclasses.replace()` 적용으로 frozen dataclass 복사 간결화
7. **[Medium]** RSS fallback 중복 코드 헬퍼 메서드 추출
8. **[Low]** Silent `except: pass` → `logger.debug()` 추가
