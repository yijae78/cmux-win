# Analysis Module 코드 리뷰

> **대상 파일**: `pipeline.py`, `stage1_preprocessing.py`, `stage3_article_analysis.py`
> **리뷰 관점**: 파이프라인 아키텍처, 데이터 흐름, 성능, 에러 처리

---

## 1. 파이프라인 아키텍처

### 1.1 강점

- **명확한 8단계 순차 실행 모델**: `STAGE_DEPENDENCIES` 딕셔너리로 단계 간 의존성을 선언적으로 정의하고, `INDEPENDENT_STAGES = {5, 6}`으로 독립 단계를 분리해 부분 실패 시에도 후속 단계 진행이 가능하다. 이는 장시간 파이프라인에서 실용적인 설계다.

- **체크포인트/재개 지원**: `_check_dependencies()`가 디스크 상의 파일 존재 여부를 확인하여 임의 단계부터 재개할 수 있다. 일일 배치 파이프라인에서 Stage 4 실패 후 `--stage 4`로 재시작할 수 있어 운용 효율이 높다.

- **Atomic 쓰기 의도 명시**: docstring에 "temp file + rename" 원자적 쓰기를 설계 원칙으로 명시. 실패 시 이전 출력이 손상되지 않는 안전한 구조를 의도하고 있다.

- **날짜 기반 파티셔닝**: `_data_dir / "processed" / self._date` 구조로 일별 결과가 독립 디렉토리에 축적되어, 월간/분기/연간 분석 시 기간별 데이터 접근이 용이하다.

### 1.2 개선 필요 사항

**[높음] `_remap_path()` 경로 매핑의 잠재적 불일치**
(`pipeline.py:1007-1030`)

`STAGE_DEPENDENCIES`는 전역 상수 경로(예: `ARTICLES_PARQUET_PATH`)를 사용하고, `_remap_path()`가 이를 커스텀 `data_dir` + 날짜 서브디렉토리로 변환한다. 그런데 `relative_to(DATA_DIR)` 호출이 실패하면(상수 경로가 `DATA_DIR` 하위가 아닌 경우) 원본 경로를 그대로 반환하므로, 커스텀 `data_dir`을 쓸 때 의존성 검증이 잘못될 수 있다.

```python
# pipeline.py:1028
except ValueError:
    return default_path  # 위험: 커스텀 data_dir 사용 시 항상 False 반환 가능
```

**권장**: 단위 테스트로 커스텀 `data_dir` 시나리오의 경로 매핑을 검증하거나, 상수 대신 상대 경로 기반 의존성 그래프로 전환.

**[중간] Atomic 쓰기가 실제로는 미구현**

docstring(line 17)에서 "temp file + rename"을 명시하지만, 실제 각 Stage runner에서 `pq.write_table()`은 최종 경로에 직접 쓰기를 수행한다. 쓰기 중 프로세스가 중단되면 손상된 Parquet 파일이 남아, 체크포인트 재개 시 `_check_dependencies()`를 통과하지만 읽기에서 실패할 수 있다.

**권장**: `write_table()`을 `.tmp` 확장자로 쓴 뒤 `os.replace()`로 원자적 이동하는 유틸리티 래퍼 도입.

**[낮음] `_get_stage_runner()` 매 호출마다 딕셔너리 생성**
(`pipeline.py:639-652`)

`runners` 딕셔너리를 매 호출 시 새로 생성한다. 성능 임팩트는 미미하지만, 클래스 속성이나 `__init__`에서 한 번 생성하는 것이 깔끔하다.

---

## 2. 데이터 흐름

### 2.1 강점

- **Stage 1 → Stage 3 데이터 계약 명확**: Stage 1은 `ARTICLES_SCHEMA` (12 컬럼 Parquet)를, Stage 3는 13 컬럼 `article_analysis.parquet`를 출력한다. 각 스키마가 코드 내에서 명시적으로 정의되어 있어 계약 위반 시 즉시 감지 가능하다.

- **중간 데이터의 분리**: `ArticleIntermediateData` (토큰, 문장, POS 태그)는 Parquet에 저장하지 않고 메모리에서만 Stage 2로 전달된다. 이는 불필요한 I/O를 방지하면서도 Stage 2가 필요한 NLP 중간 결과를 제공하는 효율적 설계다.

- **Stage 3의 입력 다중성**: `articles.parquet` + `embeddings.parquet` (coverage 추정) + `ner.parquet` (entity density) 세 가지 입력을 조합한다. embeddings/NER가 없어도 graceful하게 기본값으로 동작하여, 선행 단계 부분 실패에 강건하다.

### 2.2 개선 필요 사항

**[높음] `run_stage3()`와 `AnalysisPipeline._run_stage3()` 간 인터페이스 불일치**
(`pipeline.py:722-762` vs `stage3_article_analysis.py:1570-1617`)

파이프라인 오케스트레이터의 `_run_stage3()`은 `run_stage3()`을 호출하고 반환값에서 `result["stats"]["total_articles"]`를 추출한다. 그런데 `run_stage3()`의 반환 딕셔너리에서 `stats` 키는 `analyzer.get_distribution_stats()` 결과이며, 이 안의 `total_articles`는 **출력** 파일에서 다시 읽은 값이다. 즉 입력 기사 수가 아닌 출력 기사 수를 보고하게 된다. 정상 동작 시 동일할 수 있지만, 스키핑된 기사가 있으면 차이가 난다.

**[중간] Stage 3의 `_estimate_coverage()`가 O(N) 코사인 유사도 계산**
(`stage3_article_analysis.py:865-899`)

매 기사마다 전체 임베딩 행렬에 대해 `np.dot(embeddings, target)`을 수행한다. 1,000개 기사 기준 1,000 x 1,000 = 100만 연산. 현재 규모에서는 수용 가능하지만, 기사 수 증가 시 O(N^2) 병목이 된다.

**권장**: FAISS index나 사전 계산된 유사도 행렬 활용, 또는 배치 단위 유사도 계산 후 캐싱.

**[중간] `_process_article_batch()`에서 내부 임시 키 유출**
(`stage3_article_analysis.py:984-988`)

`_emotions_dict`, `_source`, `_published_at` 같은 언더스코어 접두사 키가 결과 딕셔너리에 포함된다. `_write_analysis_output()`은 이들을 무시하지만, `_compute_mood_and_trajectory()`에서 소비된다. 이 임시 데이터가 `all_results` 리스트에 모두 남아 메모리를 차지하며, 다른 소비자가 실수로 접근할 여지가 있다.

**권장**: 분석 결과와 집계용 임시 데이터를 별도 구조체(dataclass 또는 NamedTuple)로 분리.

---

## 3. 성능

### 3.1 강점

- **16GB 메모리 예산 관리**: `MemoryMonitor`가 RSS를 추적하고 경고/중단 임계치를 적용한다. 단계 간 `gc.collect()` + `torch.cuda.empty_cache()` + MPS 캐시 정리로 메모리 해제를 적극 수행한다.

- **지연 로딩(Lazy Loading) 패턴 일관 적용**: Stage 1의 Kiwi/spaCy, Stage 3의 트랜스포머 모델 모두 필요 시점에 로딩하여 초기 메모리 부담을 분산시킨다.

- **배치 크기 최적화**: Stage 3의 `TRANSFORMER_BATCH_SIZE = 4`는 16GB M2 Pro 환경에 맞춤 설정. 100건마다 `gc.collect()` 호출로 메모리 누적을 방지한다.

### 3.2 개선 필요 사항

**[높음] Stage 1의 `process()` 단일 스레드 순차 처리**
(`stage1_preprocessing.py:1113-1230`)

기사를 하나씩 `process_article()`로 처리한다. 언어 감지(`langdetect`)와 Kiwi/spaCy 토크나이징이 CPU-bound인데, 멀티코어 활용이 없다. 1,000개 기사에서 수분 소요가 예상된다.

**권장**: `concurrent.futures.ProcessPoolExecutor` 또는 Kiwi/spaCy의 `pipe()` 배치 API 활용. 단, Kiwi 인스턴스의 프로세스 간 공유는 불가하므로 워커별 인스턴스 필요.

**[높음] `langdetect` 반복 호출 시 `DetectorFactory.seed = 42` 설정 위치**
(`stage1_preprocessing.py:416-417`)

`detect_language()` 함수가 호출될 때마다 `DetectorFactory.seed = 42`를 설정한다. `langdetect`의 `DetectorFactory`는 모듈 수준 싱글톤이므로 매 호출 시 재설정은 불필요하며, 스레드 안전성 문제도 있다. 또한 `detect()` + `detect_langs()` 두 번 호출하여 동일 텍스트를 이중 분석한다.

**권장**: 모듈 로딩 시 한 번만 seed 설정. `detect_langs()`만 호출하여 상위 결과의 `lang`과 `prob`를 한 번에 추출.

**[중간] Stage 3 `_classify_emotions()`와 `_classify_steeps()`의 이중 추론**
(`stage3_article_analysis.py:602-683`)

같은 기사의 같은 텍스트로 zero-shot 파이프라인을 emotion (8 라벨) + STEEPS (6 라벨) 두 번 호출한다. BART-MNLI는 동일 모델이므로, 14개 라벨을 한 번에 `multi_label=True`로 분류한 뒤 결과를 분리하면 추론 횟수를 절반으로 줄일 수 있다.

**권장**: 감정 8 + STEEPS 6 = 14 라벨 통합 추론 후 결과 분리.

**[중간] `_build_table()` 컬럼별 수동 리스트 구성**
(`stage1_preprocessing.py:1232-1274`)

12개 컬럼을 수동으로 `columns["article_id"].append(row["article_id"])` 식으로 구성한다. `pa.Table.from_pylist(rows, schema=ARTICLES_SCHEMA)` 한 줄로 대체 가능하며, 필드 추가/삭제 시 유지보수 부담도 줄어든다.

**[낮음] `_get_rss_mb()` vs `MemoryMonitor.get_rss_gb()`**

Stage 1에 `_get_rss_mb()` (MB 단위), 파이프라인에 `MemoryMonitor.get_rss_gb()` (GB 단위)가 별도 존재한다. 같은 기능의 중복 구현이며, `os.uname()` (pipeline) vs `platform.system()` (stage1)으로 OS 판별 방식도 다르다. Windows에서 `os.uname()`은 `AttributeError`를 발생시킨다 (pipeline.py:224).

**권장**: `MemoryMonitor.get_rss_gb()` 하나로 통일하고 Stage 1에서도 import하여 사용.

---

## 4. 에러 처리

### 4.1 강점

- **다층 예외 계층**: `AnalysisError` > `PipelineStageError`, `MemoryLimitError`, `ModelLoadError`로 구조화된 예외 체계. `_run_stage()`에서 각 타입별로 분기 처리하고, 최종 `Exception` catch-all도 있어 누락 없다.

- **Graceful Degradation**: Stage 3가 트랜스포머 모델 로드 실패 시 VADER(영어)/한국어 감정 사전(한국어)/균등 분포(감정)/소스 기반 휴리스틱(STEEPS)으로 폴백한다. `_en_sentiment_available` 플래그로 실패 상태를 추적하여 매번 재시도하지 않는다.

- **Stage 1의 기사 단위 격리**: 개별 기사 처리 실패가 전체 배치를 중단시키지 않고, `skipped` 카운터를 증가시키고 계속 진행한다. 에러 메시지도 처음 10개만 stats에 보존하여 로그 폭발을 방지한다.

- **Stage 3 출력 검증 (`validate_output()`)**: 9가지 검증 항목(스키마, 범위, 분포 이상 등)으로 출력 품질을 체계적으로 검사한다. 특히 neutral 비율 95% 초과 시 모델 장애를 의심하는 진단은 실전적이다.

### 4.2 개선 필요 사항

**[높음] `_run_stage()` 예외 체인의 중복 패턴**
(`pipeline.py:504-625`)

6개 except 블록이 거의 동일한 `StageResult` 생성 로직을 반복한다. `MemoryLimitError`, `PipelineStageError`, `ModelLoadError`, `FileNotFoundError`, `AnalysisError`, `Exception` 각각에서 elapsed 계산 + StageResult 생성이 복사-붙여넣기 수준이다.

```python
# 6번 반복되는 패턴:
except SomeError as e:
    elapsed = time.monotonic() - stage_start
    return StageResult(
        stage_number=stage_num,
        stage_name=stage_name,
        success=False,
        elapsed_seconds=round(elapsed, 2),
        error_message=str(e),
        error_type="SomeError",
    )
```

**권장**: `(MemoryLimitError, PipelineStageError, ModelLoadError, FileNotFoundError, AnalysisError)`를 단일 except 절로 묶고, `Exception` catch-all만 분리하여 `exc_info=True` 로깅을 적용. 또는 error result를 생성하는 헬퍼 메서드 추출.

**[중간] Stage 1 `_load_kiwi()`의 하드코딩된 경로**
(`stage1_preprocessing.py:475-476`)

```python
_ascii_dir = "C:/kiwi_model"
```

Kiwi 모델을 한글 경로 문제 해결을 위해 `C:/kiwi_model`로 복사한다. 이 경로는 환경에 종속적이며, 다른 사용자/배포 환경에서 권한 문제가 발생할 수 있다. 또한 복사 여부를 `extract.mdl` 파일 존재로만 판단하여, 모델 버전 업데이트 시 구 버전이 캐싱될 수 있다.

**권장**: `tempfile.mkdtemp()` 또는 환경변수/설정 파일로 경로를 외부화. 버전 해시 기반 캐시 무효화 추가.

**[중간] Stage 3의 `_unload_models()` 불완전한 정리**
(`stage3_article_analysis.py:464-481`)

`del self._en_sentiment_pipeline` 후 `gc.collect()`를 호출하지만, HuggingFace 파이프라인이 내부적으로 보유한 토크나이저/모델 참조가 다른 곳에 캐싱되어 있을 수 있다(예: `transformers` 모듈의 모델 캐시). 완전한 메모리 해제를 보장하려면 추가 조치가 필요하다.

**[낮음] `detect_language()` spaCy 미활용**
(`stage1_preprocessing.py:377-455`)

언어 감지에 `langdetect` 라이브러리만 사용한다. spaCy가 이미 로드되어 있고 자체 언어 감지 기능(`spacy-langdetect`)도 있지만 활용하지 않는다. `langdetect`의 정확도 한계(짧은 텍스트, 혼합 언어)를 보완할 수 있다.

---

## 5. 종합 평가

| 영역 | 평가 | 비고 |
|------|------|------|
| **아키텍처** | 우수 | 8단계 순차 파이프라인 + 체크포인트 + 독립 단계 분리 |
| **데이터 흐름** | 양호 | 스키마 명확, 선택적 입력 graceful 처리. 인터페이스 불일치 주의 |
| **성능** | 보통 | 메모리 관리 우수하나, CPU 병렬화와 추론 최적화 여지 존재 |
| **에러 처리** | 양호 | 다층 예외 + 폴백 패턴 우수. 코드 중복 정리 필요 |

### 우선 수정 권장 사항 (Top 5)

1. **Atomic 쓰기 구현**: temp + rename 패턴을 실제 적용하여 데이터 무결성 보장
2. **Stage 1 병렬화**: Kiwi/spaCy `pipe()` 또는 멀티프로세싱으로 처리량 개선
3. **Zero-shot 통합 추론**: 감정 + STEEPS 라벨을 한 번에 분류하여 추론 시간 50% 절감
4. **`_run_stage()` 예외 핸들링 리팩토링**: 6개 중복 except 블록 통합
5. **메모리 유틸리티 통일**: `_get_rss_mb()`와 `MemoryMonitor` 중복 제거, Windows 호환성 확보

---

*리뷰 일시: 2026-06-17*
*대상 코드: globalnews/src/analysis/ (pipeline.py, stage1_preprocessing.py, stage3_article_analysis.py)*
