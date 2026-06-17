# EnvironmentScan 코드 리뷰 보고서

**대상 파일**
| 파일 | 줄 수 | 역할 |
|------|-------|------|
| `monitor.py` | 746 | Streamlit 기반 환경스캐닝 브리핑 대시보드 (읽기 전용) |
| `launch_monitor.py` | 38 | 대시보드 원클릭 실행 런처 |

**리뷰 일자**: 2026-06-17

---

## 1. 아키텍처

### 1.1 전체 구조

단일 파일(`monitor.py`)에 데이터 로딩, 상태 모델, HTML/SVG 렌더링, Streamlit 페이지 구성이 모두 응집되어 있다. 읽기 전용 대시보드라는 범위 내에서는 합리적이나, 746줄의 단일 파일은 유지보수 임계점에 근접한다.

### 1.2 긍정적 요소

- **`State` dataclass 도입**: 데이터 로딩(`_load`)과 렌더링(`main`)이 `State` 객체를 매개로 명확히 분리되어 있다. 테스트 시 `State`를 직접 생성해 렌더링 로직만 검증할 수 있다.
- **모드 3상태 모델**: `live` / `completed` / `idle` 구분이 명확하며, 각 모드에 따른 자동 갱신 주기(5초/30초/갱신 없음)가 합리적이다.
- **WF_ORDER 중심 일관성**: 워크플로우 순서와 라벨 매핑이 상수로 중앙 관리되어, 워크플로우 추가 시 2곳(WF_ORDER, WF_LABEL)만 수정하면 된다.
- **`launch_monitor.py` 관심사 분리**: 실행 로직(포트, headless, 브라우저 오픈)이 대시보드 로직과 분리되어 있다.

### 1.3 개선 필요 사항

| 항목 | 현재 | 권장 |
|------|------|------|
| **파일 분할** | 단일 746줄 | `state.py`(State + _load), `render.py`(SVG/HTML 헬퍼), `app.py`(main)으로 3분할 |
| **렌더링 레이어 혼재** | CSS 문자열, SVG 문자열, HTML 문자열이 Python 로직에 인라인 | Jinja2 템플릿 또는 별도 `.html` 파일로 분리 |
| **상수 하드코딩** | `wf_total: int = 5`, 포트 8504 등 | 환경변수 또는 `config.toml` 기반 설정 외부화 |
| **의존성 명세 부재** | `requirements.txt` 없음 | `streamlit>=1.28` 최소 명세 필요 |
| **타입 힌트 불완전** | `_j` 반환형 `dict | None` (정확), 그러나 `_load` 내부 `m` 변수는 `dict | None` 혼용 | `m`에 대해 Optional narrowing 또는 early return 패턴 적용 |

### 1.4 아키텍처 다이어그램

```
launch_monitor.py
  └─ subprocess → streamlit run monitor.py
                    ├─ _load() → State dataclass
                    │   ├─ master-status-*.json (LOGS)
                    │   └─ dashboard-data-*.json (ANALYSIS)
                    ├─ _donut() / _bars() / _dual_bars() → HTML/SVG
                    └─ main() → Streamlit 렌더링 + auto-refresh
```

---

## 2. 보안

### 2.1 긍정적 요소

- **읽기 전용 설계**: 파일 시스템에 쓰기 작업이 전혀 없다. 데이터 무결성 위험이 원천 차단된다.
- **외부 입력 없음**: 사용자 입력 폼이 없으므로 XSS 공격 벡터가 제한적이다.
- **인증 정보 부재**: API 키, 토큰, 크레덴셜이 코드에 없다.

### 2.2 취약점 및 위험 요소

| 심각도 | 항목 | 상세 |
|--------|------|------|
| **중** | **HTML 인젝션 경로** | `_signal_bars()`의 `title` 변수가 JSON에서 읽은 값을 그대로 HTML에 삽입한다 (L475-476). 악의적 JSON 데이터에 `<script>` 태그가 포함되면 Streamlit의 `unsafe_allow_html=True` 컨텍스트에서 실행될 수 있다. |
| **중** | **Zoom 스크립트의 parent 접근** | `ZOOM` 변수(L126-131)가 `window.parent.document`에 접근하며, iframe 샌드박스 우회 시도가 가능한 패턴이다. Streamlit의 `components.html` 내에서 실행되므로 현재는 격리되나, 구조 변경 시 위험하다. |
| **낮** | **Path Traversal 간접 위험** | `data_date`가 `master_id`에서 파싱된다 (L231). `master_id`가 `quadruple-scan-../../etc/passwd` 형태이면 `ANALYSIS / f"dashboard-data-{data_date}.json"` 경로가 상위 디렉토리로 이탈할 수 있다. 현재는 JSON 파싱 실패로 무해하나, 방어 코드가 필요하다. |
| **낮** | **네트워크 노출** | Streamlit은 기본적으로 `0.0.0.0`에 바인딩된다. `launch_monitor.py`에서 `--server.address localhost`를 명시하지 않아, 같은 네트워크의 타 기기에서 접근 가능하다. |

### 2.3 권장 조치

```python
# 1. HTML 이스케이프 적용
from html import escape
title = escape(sig.get("title_ko") or sig.get("title", ""))

# 2. data_date 검증
import re
if not re.match(r"^\d{4}-\d{2}-\d{2}$", data_date):
    return s  # 잘못된 형식이면 조기 반환

# 3. 런처에 localhost 바인딩 추가
"--server.address", "localhost",
```

---

## 3. 성능

### 3.1 긍정적 요소

- **경량 파일 I/O**: JSON 파일 직접 읽기로 DB 오버헤드가 없다.
- **모드별 차등 갱신**: live=5초, idle=30초, completed=갱신 없음. 불필요한 리소스 소모를 방지한다.
- **`_j()` 헬퍼의 방어적 설계**: 파일 읽기 실패 시 `None` 반환으로 전체 흐름이 중단되지 않는다.

### 3.2 병목 및 개선 사항

| 항목 | 영향 | 현재 | 권장 |
|------|------|------|------|
| **`time.sleep()` 블로킹** | Streamlit 워커 스레드 점유 | `time.sleep(5)` 후 `st.rerun()` (L736-737) | `st.cache_data(ttl=5)` + `st_autorefresh` 컴포넌트 사용 |
| **매 리런마다 전체 재로딩** | 5초마다 모든 JSON 파싱 + State 재구축 | `_load()`가 캐싱 없이 매번 호출 | `@st.cache_data(ttl=3)` 적용으로 중복 파싱 방지 |
| **glob + sort 매 호출** | 파일 수 증가 시 O(n log n) | `LOGS.glob("master-status-????-??-??.json")` 후 정렬 (L233-238) | 최신 날짜부터 역순 검색하는 `_find_latest()` 전용 함수로 분리, 결과 캐싱 |
| **SVG 인라인 생성** | 매 렌더마다 문자열 조합 | `_donut()` 내 f-string 연쇄 | 정적 SVG 템플릿 + 동적 값 주입으로 분리 (성능보다 가독성 이점) |
| **classified-signals 파일 반복 읽기** | WF별 2회 파일 I/O (L379-386) | 루프 내 `_j()` 호출 | 파일 존재 여부 사전 확인 + 결과 캐싱 |
| **`components.html()` 비용** | iframe 생성 오버헤드 | Zoom + 도넛 차트에 2회 사용 | Zoom은 `st.markdown`의 `<script>`로 대체 가능 (iframe 1개 절약) |

### 3.3 메모리 프로파일

현재 규모(JSON 수십 KB, 시그널 수십 개)에서는 메모리 문제 없음. 그러나 시그널이 1,000개 이상으로 증가하면 `_load()` 내 리스트 조작(L345-369)이 O(n) 메모리를 소비한다. `top_signals`에 대해서는 힙 기반 top-K 추출(`heapq.nlargest`)이 효율적이다.

---

## 4. 에러 처리

### 4.1 긍정적 요소

- **`_j()` 방어적 래퍼**: 모든 JSON 파일 읽기가 try-except로 보호된다 (L158-162).
- **Graceful degradation**: 데이터 없을 때 "스캔 데이터가 없습니다" 안내 후 30초 대기 → 재시도 (L648-653).
- **datetime 파싱 보호**: `fromisoformat()` 호출이 모두 try-except로 감싸져 있다 (L252-255, L258-261, L298-301).
- **ZeroDivision 방어**: `t = s.total or 1` (L663), `mx = max(..., 1)` (L518) 패턴으로 0 나눗셈을 방지한다.

### 4.2 취약점 및 개선 사항

| 심각도 | 항목 | 위치 | 상세 |
|--------|------|------|------|
| **중** | **무음 실패 (Silent failure)** | `_j()` L160-162 | 모든 예외를 삼킨다. JSON 파싱 오류, 인코딩 오류, 권한 오류가 구분 없이 `None` 반환된다. 최소한 `logging.debug()`로 기록 필요. |
| **중** | **`_load()` 내 `None` 체크 누락** | L266-268 | `m.get("workflow_results", {}).get(wf_id, {})` 체인에서 중간값이 `None`이면 `AttributeError` 발생. `or {}` 패턴이 L266에는 있으나 L319에는 없다 (불일치). |
| **중** | **`launch_monitor.py` stdout/stderr 소실** | L23-24 | `subprocess.DEVNULL`로 Streamlit의 에러 출력이 모두 폐기된다. 시작 실패 시 원인 파악 불가. |
| **낮** | **`time.sleep()` 후 `st.rerun()` 실패 가능** | L651-652, L736-740 | Streamlit이 스크립트 중단을 시도할 때 `sleep` 중이면 `StopException`이 발생할 수 있다. |
| **낮** | **날짜 파싱 가정** | L549 | `s.date.split("-")`이 정확히 3개 요소를 반환한다고 가정. 잘못된 형식이면 인덱스 에러 위험 (실제로 `len(dp) == 3` 가드가 있으나, 빈 문자열 요소 시 의미 없는 출력). |
| **낮** | **프로세스 좀비 위험** | `launch_monitor.py` L27 | `time.sleep(3)` 동안 프로세스가 즉시 종료되면 `webbrowser.open`이 실행되지만 서버는 없는 상태. `proc.poll()` 확인 필요. |

### 4.3 권장 에러 처리 패턴

```python
# _j() 개선안
import logging
logger = logging.getLogger(__name__)

def _j(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None  # 정상 경로: 파일 미존재
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning("JSON 파싱 실패: %s — %s", p, e)
        return None
    except OSError as e:
        logger.error("파일 접근 오류: %s — %s", p, e)
        return None

# launch_monitor.py 개선안
proc = subprocess.Popen(..., stderr=subprocess.PIPE)
time.sleep(3)
if proc.poll() is not None:
    err = proc.stderr.read().decode() if proc.stderr else ""
    print(f"Streamlit 시작 실패: {err}", file=sys.stderr)
    sys.exit(1)
```

---

## 종합 점수표

| 평가 항목 | 점수 (10점 만점) | 근거 |
|-----------|:---:|------|
| **아키텍처** | **7** | State dataclass 기반 분리 우수. 단일 파일 746줄은 분할 필요. 렌더링 레이어 혼재. |
| **보안** | **6** | 읽기 전용이라 공격 면적 작으나, HTML 인젝션·Path Traversal 방어 코드 부재. 네트워크 바인딩 미지정. |
| **성능** | **7** | 현재 데이터 규모에서 충분. `time.sleep` 블로킹과 캐싱 부재는 동시접속 증가 시 병목. 모드별 차등 갱신은 합리적. |
| **에러 처리** | **6** | 방어적 코딩 패턴 다수 존재(try-except, or 1). 그러나 무음 실패, 프로세스 좀비 위험, 로깅 부재가 운영 진단을 어렵게 함. |
| **종합** | **6.5** | 읽기 전용 대시보드로서 기능적으로 완성도 높음. 프로덕션 운영을 위해서는 보안 경화, 로깅 체계, 캐싱 레이어 추가가 필요. |

---

*리뷰어: Claude Opus 4.6 | 리뷰 일자: 2026-06-17*
