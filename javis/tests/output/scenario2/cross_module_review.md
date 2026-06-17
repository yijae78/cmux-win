# 크로스 모듈 인터페이스 리뷰 보고서 (정밀 갱신)

신교수님, 요청하신 크롤링(Crawling) 레이어와 분석(Analysis) 레이어 간의 크로스 모듈 인터페이스(데이터 규약, 포맷 매칭, 저장소 레이어 통합, 에러 전파) 정밀 분석 보고서입니다.

본 리뷰는 지시하신 다음의 6개 핵심 소스 코드를 바탕으로 구조적 연동성과 잠재적 한계점을 분석하여 작성되었습니다:
* [contracts.py](file:///C:/dev/cmux-win/javis/tests/workspace/globalnews/src/crawling/contracts.py)
* [pipeline.py (Crawling)](file:///C:/dev/cmux-win/javis/tests/workspace/globalnews/src/crawling/pipeline.py)
* [pipeline.py (Analysis)](file:///C:/dev/cmux-win/javis/tests/workspace/globalnews/src/analysis/pipeline.py)
* [stage1_preprocessing.py](file:///C:/dev/cmux-win/javis/tests/workspace/globalnews/src/analysis/stage1_preprocessing.py)
* [parquet_writer.py](file:///C:/dev/cmux-win/javis/tests/workspace/globalnews/src/storage/parquet_writer.py)
* [sqlite_builder.py](file:///C:/dev/cmux-win/javis/tests/workspace/globalnews/src/storage/sqlite_builder.py)

---

## 1. 데이터 규약 (Data Contracts)

* **RawArticle 규약과 Parquet 스키마 규격의 불일치**:
  - 크롤링 결과의 직렬화 모델인 [RawArticle](file:///C:/dev/cmux-win/javis/tests/workspace/globalnews/src/crawling/contracts.py#L21)과 저장소 레이어의 Stage 1 출력인 [ARTICLES_PA_SCHEMA](file:///C:/dev/cmux-win/javis/tests/workspace/globalnews/src/storage/parquet_writer.py#L60) 사이에는 다음과 같은 구조적 차이가 존재합니다.
  - **네이밍 및 필드 매핑(ADR-049)**: `RawArticle.source_id`는 Parquet의 `source` 필드로 축소 결합되며, 크롤러에 존재하는 `source_name`은 Parquet 저장 시 누락됩니다.
  - **생성 시점 차이**: 기본 키인 `article_id`와 데이터 분석용 메트릭인 `word_count`는 크롤링 완료 시점에는 존재하지 않으며, Stage 1 전처리 단계([stage1_preprocessing.py](file:///C:/dev/cmux-win/javis/tests/workspace/globalnews/src/analysis/stage1_preprocessing.py#L1))에서 동적으로 계측 및 생성되어 바인딩됩니다.
  - **유실 메타데이터**: 크롤링 회피 성능 및 품질 추적을 위한 핵심 데이터(`crawl_tier`, `crawl_method`, `is_paywall_truncated`)가 Parquet 변환 시 최종 스키마에서 배제되어, 다운스트림 분석 엔진에서 활용할 기회가 조기에 상실됩니다.

---

## 2. 포맷 매칭 (Format Matching)

* **직렬화/역직렬화의 완결성**:
  - 수집된 기사는 JSONL(한 행당 하나의 JSON 객체) 구조로 출력 디렉토리(`data/raw/YYYY-MM-DD/`)에 직렬화되어 보관됩니다.
  - 분석 레이어의 Stage 1 전처리 모듈([run_stage1](file:///C:/dev/cmux-win/javis/tests/workspace/globalnews/src/analysis/stage1_preprocessing.py#L658))이 이 JSONL 파일들을 라인 단위로 읽어 텍스트 정규화([normalize_text](file:///C:/dev/cmux-win/javis/tests/workspace/globalnews/src/analysis/stage1_preprocessing.py#L272)) 및 다국어 형태소 분석을 마친 후, 최종 바이너리 포맷인 Parquet로 이관합니다.
  - 날짜 형식은 JSONL 상의 ISO 8601 표준 문자열에서 Parquet 상의 고정밀 `timestamp("us", tz="UTC")` 데이터 형식으로 타입 캐스팅 매칭이 안정적으로 수행됩니다.

---

## 3. 저장소 레이어 통합 (Storage Layer Integration)

* **Parquet 스키마 강제 및 밸리데이션**:
  - [ParquetWriter](file:///C:/dev/cmux-win/javis/tests/workspace/globalnews/src/storage/parquet_writer.py#L359)는 파일 쓰기 전 [validate_schema](file:///C:/dev/cmux-win/javis/tests/workspace/globalnews/src/storage/parquet_writer.py#L201)를 호출하여 타입 불일치와 [_RANGE_CONSTRAINTS](file:///C:/dev/cmux-win/javis/tests/workspace/globalnews/src/storage/parquet_writer.py#L149)를 바탕으로 데이터 범위를 엄밀하게 사전 검증합니다.
  - 무손실 정밀도 하향(`float64 -> float32`, `int64 -> int32`) 캐스팅 교정(`_coerce_to_schema`) 기능이 유기적으로 통합되어 다운스트림 분석 패키지 로딩 병목을 방지합니다.
* **SQLite 관계형 데이터베이스로의 동적 이관**:
  - [SQLiteBuilder](file:///C:/dev/cmux-win/javis/tests/workspace/globalnews/src/storage/sqlite_builder.py#L123)는 Stage 8의 파켓 데이터들을 SQLite 인덱스 데이터베이스(`data/output/index.sqlite`)로 전송합니다.
  - 효율적인 쓰기 속도 보장과 메모리 제어를 위해 `executemany`를 통한 배치 처리(1000개 단위) 및 벌크 데이터 삽입 완료 후 인덱스 생성 기법을 철저히 고수하고 있습니다.
  - 데이터 검색의 핵심으로 다국어 인덱싱 능력이 우수한 `unicode61` 토크나이저(FTS5)가 성공적으로 융합되어 있습니다.

---

## 4. 모듈 경계를 넘는 에러 전파 (Error Propagation)

* **예외 처리 경계 분리와 상태 데이터 전파 단절**:
  - **독립적 오류 제어**: 크롤링 레이어([pipeline.py](file:///C:/dev/cmux-win/javis/tests/workspace/globalnews/src/crawling/pipeline.py#L153))와 분석 레이어([AnalysisPipeline](file:///C:/dev/cmux-win/javis/tests/workspace/globalnews/src/analysis/pipeline.py#L306)) 모두, 특정 사이트 수집 혹은 특정 스테이지 처리 중 발생하는 예외를 내부의 Result 인스턴스에 안전하게 격리 보관함으로써 파이프라인 전체가 붕괴(Crash)하는 결함을 효과적으로 통제하고 있습니다.
  - **컨텍스트 유실에 따른 장벽**: 하지만 수집 단계 도중 발생하는 블록 감지(`BlockDetectedError`), 타임아웃 양보(`deadline_yielded`), 재시도 기록 등은 오직 크롤러의 메모리나 `.crawl_state.json` 상에 폐쇄적으로 유지됩니다.
  - 분석 모듈은 오직 JSONL 기사 텍스트 본체만을 읽어들이기 때문에, 분석 대상 텍스트가 심하게 유실(예: 페이월 단절)되었거나 크롤링 도중 예외가 발생했는지에 관한 메타적 장애 컨텍스트를 구조화된 형태로 안전하게 인계받지 못하고 있습니다.

---

## 💡 주요 개선 사항 제언 (Action Items)

1. **Parquet 공통 스키마에 수집 지표 추가**: `ARTICLES_PA_SCHEMA`에 기사 수집 루트 플래그(`crawl_method`), 크롤러 시도 단계(`crawl_tier`), 본문 훼손 판단값(`is_paywall_truncated`)을 함께 기록하여 최종 데이터 분석의 정확도 및 정밀도를 보장해야 합니다.
2. **모듈 간 헬스 모니터링 동기화**: 크롤러의 `.crawl_state.json`과 데이터베이스 빌더 간의 결합을 설계하여, 최종 SQLite `crawl_status` 테이블에 각 수집 소스의 에러 로그 및 실시간 장애 상태 정보가 즉각적으로 투영될 수 있도록 흐름을 통합해야 합니다.
