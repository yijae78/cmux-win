# 코드 품질 분석 보고서

**대상 파일:**
- `monitor.py` (745줄) — 환경스캐닝 브리핑 Streamlit 대시보드
- `launch_monitor.py` (37줄) — 대시보드 원클릭 실행기

**분석일:** 2026-06-17

---

## 1. 코드 구조

### monitor.py

| 영역 | 줄 범위 | 설명 |
|------|---------|------|
| 모듈 docstring + imports | 1–20 | 표준 라이브러리 + Streamlit 의존성 |
| 경로/상수 정의 | 22–31 | `PROJECT`, `ENV`, `LOGS`, `ANALYSIS`, KST 타임존, 워크플로우 순서 |
| FSSF 매핑 | 33–46 | 미래신호 유형 영→한 번역 딕셔너리 + 변환 함수 |
| 색상/CSS 상수 | 48–131 | 디자인 토큰, CSS 스타일시트, 애니메이션 키프레임, 줌 스크립트 |
| 데이터 계층 | 133–391 | `State` dataclass, JSON 로더(`_j`), ETA 추정(`_estimate_total_seconds`), 타이밍 디스플레이 상태(`_timing_display_state`), 메인 데이터 로더(`_load`) |
| 렌더러 | 394–535 | SVG 도넛 차트(`_donut`), 신호 바 차트(`_signal_bars`), 단일/이중 바 차트(`_bars`, `_dual_bars`) |
| 메인 함수 | 538–745 | Streamlit 페이지 구성, 조건부 UI 렌더링, 자동 갱신 루프 |

**구조적 특징:**
- 단일 파일(monolith)로 데이터 로딩, 비즈니스 로직, 렌더링이 모두 포함
- `_load()` 함수가 약 175줄로 가장 큰 단일 함수 — 데이터 수집과 상태 결정 로직이 혼재
- `main()` 함수도 약 200줄로 UI 렌더링 전체를 담당

### launch_monitor.py

| 영역 | 줄 범위 | 설명 |
|------|---------|------|
| imports | 6–10 | subprocess, sys, time, webbrowser, pathlib |
| 상수 | 12–13 | MONITOR 경로, PORT 번호 |
| main() | 16–33 | Streamlit 프로세스 실행 → 브라우저 오픈 → 종료 대기 |

**구조적 특징:**
- 단일 책임: Streamlit 서버 실행 + 브라우저 오픈만 수행
- 깔끔하고 간결한 런처 패턴

---

## 2. 주요 기능

### monitor.py

1. **데이터 로딩 (`_load`)**: JSON 기반 마스터 상태 파일을 읽어 스캔 진행 상태, 워크플로우별 신호 수, FSSF 분류, Three Horizons, 교차 분석 데이터를 `State` dataclass에 통합
2. **실시간 ETA 추정 (`_estimate_total_seconds`, `_timing_display_state`)**: 현재 단계(수집/분석, 통합, 보고서)에 따른 예상 완료 시간 계산. 초과 시 20분 블록 단위 자동 연장
3. **SVG 도넛 차트 (`_donut`)**: 레이더 스캔 애니메이션, 방사형 파동, 세그먼트 라벨을 포함한 커스텀 SVG 도넛 차트 렌더링
4. **바 차트 시스템 (`_signal_bars`, `_bars`, `_dual_bars`)**: 단일/이중 비교 바 차트. WF별 색상 코딩 및 FSSF 한글 라벨 지원
5. **3모드 대시보드 (`main`)**: `live`(실시간 크롤링 중), `completed`(완료), `idle`(대기) 3가지 상태에 따른 차등 UI 표시 및 자동 갱신 주기 조절 (live: 5초, idle: 30초, completed: 갱신 안 함)
6. **줌 기능**: Ctrl+휠로 브라우저 내 줌 레벨 조정 가능

### launch_monitor.py

1. **Streamlit 서버 실행**: headless 모드 + 다크 테마로 서버 실행
2. **브라우저 자동 오픈**: 3초 대기 후 브라우저에서 대시보드 열기
3. **프로세스 관리**: Ctrl+C로 안전한 종료 지원

---

## 3. 코드 품질

### 가독성

| 항목 | 평가 | 상세 |
|------|------|------|
| 네이밍 | **보통** | 공개 함수/클래스명은 명확하나, 내부 변수명이 약어 과다 (`G1`, `G2`, `G3`, `TK`, `W`, `C1`, `C2`, `s`, `m`, `dd`, `h` 등). 특히 `h`가 HTML 문자열 축적 변수로 여러 함수에서 반복 사용되어 검색·추적이 어려움 |
| 타입 힌트 | **양호** | `from __future__ import annotations` 적용. 함수 시그니처에 타입 힌트 대부분 제공. `State` dataclass에도 필드 타입 명시 |
| Docstring | **부족** | 모듈 docstring과 `_fssf_ko`, `_estimate_total_seconds`, `_timing_display_state`에만 docstring 존재. `_load`, `_donut`, `_signal_bars`, `_bars`, `_dual_bars`, `main` 등 핵심 함수에는 미작성 |
| 코드 조직 | **보통** | 주석 구분선(`# ── Section ──`)으로 영역 구분은 잘 되어 있으나, 단일 파일 내 745줄이 응집도를 떨어뜨림 |
| 인라인 HTML | **낮음** | f-string으로 직접 HTML/CSS/SVG를 조합하는 패턴이 전체의 약 40%를 차지. 문자열 안에 중첩된 스타일 속성이 읽기 어렵고 유지보수가 까다로움 |

### 유지보수성

| 항목 | 평가 | 상세 |
|------|------|------|
| 모듈 분리 | **낮음** | 데이터 로딩, 상태 판단, 차트 렌더링, CSS 정의, 메인 UI가 한 파일에 혼재. 변경 시 영향 범위 파악이 어려움 |
| 하드코딩 | **보통** | 색상값, 워크플로우 ID, 시간 추정치(70/75/85/95/110분), 애니메이션 지속시간 등이 상수로 정의되어 있으나, ETA 계산 내부의 매직넘버(20분 블록, 6시간 등)는 의미가 불명확 |
| 테스트 용이성 | **낮음** | `_load()`가 파일시스템에 직접 의존하고, 렌더러 함수들이 HTML 문자열을 반환해 단위 테스트 작성이 어려움. 의존성 주입 없음 |
| CSS 관리 | **낮음** | CSS가 Python f-string 안에 매립되어 있어 IDE 지원(자동완성, 문법 검사) 없음. `CSS`와 `CSS_ANIM`에 동일 키프레임이 중복 정의됨 |

---

## 4. 잠재적 버그

### 4.1 [심각도: 중] CSS 키프레임 중복 정의 (monitor.py:64–107 vs 109–124)

`CSS` 문자열(64–107줄)과 `CSS_ANIM` 문자열(109–124줄)에 `blink`, `neon-pulse`, `wave-rotate` 키프레임이 **중복 정의**됨. `CSS`는 `st.markdown()`으로, `CSS_ANIM`은 `components.html()` 안에 삽입됨. Streamlit의 `components.html()`은 iframe이므로 `CSS` 정의가 적용되지 않아 `CSS_ANIM`에 재선언이 필요한 것이나, `CSS` 안의 동일 정의는 불필요한 중복이며 유지보수 시 한쪽만 수정하는 실수가 발생할 수 있음.

### 4.2 [심각도: 중] `_load()`의 fallback 날짜 불일치 (monitor.py:217–241)

`today`(KST 기준 오늘)로 파일을 찾지 못하면 `master-status.json`(날짜 없는 파일)을 시도하고, 그래도 없으면 `glob`로 최신 파일을 탐색함. 이때 `data_date`가 세 가지 경로에서 서로 다른 소스로 결정됨:
- 경로1: `today` (KST 오늘)
- 경로2: `master_id`에서 추출
- 경로3: 파일명에서 추출

이 `data_date`로 `dashboard-data-{data_date}.json`을 조회하는데(340줄), 경로2/3에서 결정된 날짜의 대시보드 데이터 파일이 존재하지 않으면 FSSF, 시그널 등의 데이터가 누락됨. 에러 없이 빈 상태로 렌더링되어 디버깅이 어려움.

### 4.3 [심각도: 중] Three Horizons 데이터에 오늘 날짜 하드코딩 (monitor.py:380)

```python
p = ENV / wf_id / "structured" / f"classified-signals-{today}.json"
```

`today`는 `_load()` 내부의 로컬 변수인데, Three Horizons 데이터 로딩에서도 `today`를 사용함. 그러나 실제 데이터는 `data_date`(fallback으로 과거 날짜일 수 있음)에 해당하는 파일에 있을 수 있음. `data_date`와 `today`가 다를 때 Three Horizons 데이터가 누락됨.

### 4.4 [심각도: 낮] 제로 디비전 방지 미흡 (monitor.py:662)

```python
t = s.total or 1
```

`s.total`이 0일 때 `t=1`로 대체하지만, 이 경우 퍼센티지가 `0/1*100=0%`로 표시됨. 기능상 문제는 없으나, `s.total == 0`인데 도넛 차트에 `0`이 표시되고 세그먼트 퍼센트가 모두 `0%`인 상태가 혼란스러울 수 있음.

### 4.5 [심각도: 낮] `time.sleep()` 블로킹 (monitor.py:651, 736–739)

Streamlit에서 `time.sleep(5)` + `st.rerun()`은 서버 스레드를 점유함. 동시 접속자가 많아지면 서버 응답 지연 가능. Streamlit의 `st.fragment` 데코레이터나 JavaScript 기반 자동 갱신이 더 안정적.

### 4.6 [심각도: 낮] launch_monitor.py — 프로세스 실패 감지 없음 (launch_monitor.py:17–25)

`stdout`/`stderr`가 모두 `DEVNULL`로 전달되어, Streamlit이 실패해도 에러 메시지가 표시되지 않음. `time.sleep(3)` 후 무조건 브라우저를 열기 때문에, 포트 충돌이나 의존성 오류 시 빈 페이지가 열림.

### 4.7 [심각도: 낮] launch_monitor.py — 포트 충돌 미처리 (launch_monitor.py:13)

`PORT = 8504`가 고정값. 이미 해당 포트가 사용 중이면 Streamlit이 다른 포트로 실행되지만, 브라우저는 여전히 8504를 열어 불일치 발생.

---

## 5. 개선 제안

### 5.1 [우선순위: 높] `_load()` 함수 분할

175줄의 `_load()` 함수를 역할별로 분리:
- `_resolve_master_file()` → 마스터 상태 JSON 파일 경로 결정
- `_parse_mode()` → live/completed/idle 모드 판정
- `_parse_wf_progress()` → 워크플로우별 진행 상태 파싱
- `_parse_dashboard_data()` → 대시보드 분석 데이터 파싱

각 함수가 20–40줄 이내가 되면 단위 테스트도 가능해짐.

### 5.2 [우선순위: 높] Three Horizons 날짜 변수를 `data_date`로 통일

```python
# 현재 (버그)
p = ENV / wf_id / "structured" / f"classified-signals-{today}.json"

# 수정안
p = ENV / wf_id / "structured" / f"classified-signals-{s.date}.json"
```

### 5.3 [우선순위: 중] CSS 중복 제거

`CSS` 안의 키프레임(`blink`, `neon-pulse`, `wave-rotate`)을 제거하고, `CSS_ANIM`에만 보관. `CSS`에는 Streamlit 메인 도큐먼트에서 필요한 스타일만 유지. 또는 별도 `_css_keyframes()` 함수로 통합 관리.

### 5.4 [우선순위: 중] 변수명 개선

| 현재 | 개선안 | 이유 |
|------|--------|------|
| `G1`, `G2`, `G3` | `TEXT_SECONDARY`, `TEXT_MUTED`, `TEXT_DIM` | 색상 역할 명시 |
| `TK` | `TRACK_BG` 또는 `BG_SUBTLE` | 바 차트 트랙 배경색임을 명시 |
| `W` | `TEXT_WHITE` 또는 `FG` | 전경색임을 명시 |
| `h` (렌더러 내) | `html_parts` 또는 `markup` | HTML 축적 변수임을 명시 |
| `m` (_load 내) | `master_data` | 마스터 상태 JSON임을 명시 |
| `dd` (_load 내) | `dashboard_data` | 대시보드 데이터임을 명시 |

### 5.5 [우선순위: 중] launch_monitor.py — 에러 핸들링 추가

```python
proc = subprocess.Popen(...)
time.sleep(3)
if proc.poll() is not None:
    print(f"Streamlit 실행 실패 (exit code: {proc.returncode})")
    sys.exit(1)
```

### 5.6 [우선순위: 낮] ETA 매직넘버를 명명된 상수로 추출

```python
# 현재
base = 95 * 60  # 의미 불명확

# 개선안
INTEGRATION_PHASE_ESTIMATE_MIN = 95
base = INTEGRATION_PHASE_ESTIMATE_MIN * 60
```

### 5.7 [우선순위: 낮] HTML 렌더링을 Jinja2 템플릿으로 분리 (장기)

인라인 f-string HTML이 코드의 40% 이상을 차지함. Jinja2 템플릿으로 분리하면:
- IDE의 HTML/CSS 지원 활용 가능
- 렌더링 로직과 프레젠테이션 분리
- 디자이너/프론트엔드 개발자의 협업 용이

---

## 종합 평가

| 항목 | 점수 (10점) | 비고 |
|------|:-----------:|------|
| 기능 완성도 | **8** | 3모드 대시보드, 실시간 ETA, 다양한 차트 등 기능이 충실함 |
| 코드 가독성 | **5** | 약어 변수명 + 인라인 HTML로 가독성 저하 |
| 유지보수성 | **4** | 단일 파일 745줄, 함수 분할 부족, 테스트 불가 구조 |
| 에러 처리 | **5** | JSON 파싱 try/except 있으나 사용자 피드백 부재 |
| 버그 위험도 | **6** | 날짜 불일치 외 치명적 런타임 에러 가능성은 낮음 |
| 디자인 품질 | **8** | CSS 애니메이션, SVG 차트, 색상 체계가 세련됨 |
| **종합** | **6.0** | 프로토타입/내부 도구로는 충분하나, 장기 유지보수를 위해 리팩토링 필요 |

---

*보고서 생성: Claude Code Worker1 · 2026-06-17*
