# RSI Round 2 — dashboard.py 코드 품질 심층 분석

**대상 파일:** `/c/dev/cmux-win/javis/dashboard.py` (1,110줄)
**분석 단계:** RSI Round 2 (Phase 1 수정 완료 후)
**분석일:** 2026-06-17

---

## Phase 1 적용 확인

| Phase 1 항목 | 적용 상태 | 위치 |
|---|---|---|
| XSS 방지 (`html.escape`) | ✅ 적용됨 | `_esc()` 함수 (617줄), `_esc(s_reset)` (885줄) 등 |
| 예외 범위 축소 + 로깅 | ✅ 적용됨 | 구체적 예외 타입 지정 전역 적용 |
| `_match_fleet_config()` 중복 제거 | ✅ 적용됨 | 625줄, 1032/1096줄에서 호출 |
| 소켓 cleanup (`finally`) | ✅ 적용됨 | `gather_fleet_data()` 162줄 |
| fleet 데이터 캐싱 | ✅ 적용됨 | `_fleet_data_cache` (117줄), 2초 TTL |

---

## 1. 아키텍처 이슈

### 1.1 [심각도: 높] pane_data 조립 로직 중복 — DRY 위반

1028–1038줄 (`_gather_and_render_body`)과 1093–1103줄 (모듈 하단 메인 블록)에 **동일한 pane_data 조립 로직**이 복사-붙여넣기되어 있음.

```python
# 1028–1038줄 (HTTP 서버용)
label_map = {cfg["key"]: cfg for cfg in FLEET}
pane_data = []
for i, sf in enumerate(terminals):
    label = sf.get("label") or sf.get("title", "Terminal")
    cfg = _match_fleet_config(label, label_map)
    content = contents[i] if i < len(contents) else ""
    status = detect_status(content)
    activity = get_activity_summary(content)
    preview = get_terminal_preview(content, 3)
    ctx_warn = detect_context_warning(content)
    pane_data.append((sf, cfg, content, status, activity, preview, ctx_warn))

# 1093–1103줄 (Streamlit 초기 렌더링용)
# ← 위와 완전 동일한 코드
```

Phase 1에서 `_match_fleet_config`을 추출했지만, 이를 사용하는 **상위 조립 루프 자체가 여전히 중복**. `_build_pane_data(terminals, contents)` 함수로 추출 필요.

### 1.2 [심각도: 높] `build_full_html` 거대 함수 — 350줄, 단일 책임 위반

638–993줄까지 약 **355줄**의 단일 함수. 다음 역할이 혼재:
- 데이터 변환 (경과시간 계산, 색상 결정, 퍼센트 계산)
- CSS 문자열 생성 (647–794줄, **약 150줄**)
- HTML 마크업 생성 (796–948줄)
- JavaScript 생성 (953–989줄)

CSS는 함수 호출마다 동일한 문자열을 재생성. **전역 상수로 한 번만 생성** 가능.

**개선 구조 제안:**
```
_CSS: str = "..."  (모듈 상수, 1회 생성)
_JS_TEMPLATE: str = "..."  (모듈 상수)
_build_header_html(mode, now) → str
_build_kpi_html(radar, uptime, ...) → str
_build_fleet_html(pane_data) → str
_build_usage_html(usage_data, rate_limits) → str
_build_system_html(metrics) → str
build_full_html(...)  → 위 함수 조합만
```

### 1.3 [심각도: 중] 이중 시작시간 — `_fleet_start` vs `st.session_state.fleet_start`

```python
_fleet_start = datetime.now()           # 1019줄 — 모듈 로드 시점
st.session_state.fleet_start = datetime.now()  # 1085줄 — 세션 시작 시점
```

HTTP 서버(`_gather_and_render_body`)는 `_fleet_start`를 사용(1043줄), Streamlit 초기 렌더링은 `st.session_state.fleet_start`를 사용(1108줄). 두 값은 **동일하지 않을 수 있고**, Streamlit rerun 시 `_fleet_start`만 갱신되는 등 불일치 발생 가능.

### 1.4 [심각도: 중] 모듈 레벨 Streamlit 호출 — 임포트 불가

```python
# 80–93줄
st.set_page_config(...)
st.markdown(...)
```

모듈 최상위에서 `st.set_page_config()`과 `st.markdown()`을 호출. 이 파일을 테스트나 유틸리티에서 `import dashboard`하면 **즉시 Streamlit 에러** 발생. 모든 Streamlit 호출은 `if __name__ == "__main__"` 또는 `main()` 함수 내부에 있어야 함.

### 1.5 [심각도: 낮] 7-tuple pane_data — 구조체 부재

```python
pane_data.append((sf, cfg, content, status, activity, preview, ctx_warn))
# 사용 시:
for idx, (sf, cfg, content, status, activity, preview, ctx_warn) in enumerate(pane_data):
```

7개 요소의 tuple은 인덱스 순서를 기억해야 하고, 필드 추가 시 모든 사용처를 수정해야 함. `@dataclass` 또는 `NamedTuple`로 전환 권장.

---

## 2. 스레드 안전성 이슈

### 2.1 [심각도: 높] 캐시 딕셔너리 경합 조건 (Race Condition)

```python
_fleet_data_cache = {"ts": 0, "data": ([], [])}     # 117줄
_rate_limit_cache = {"ts": 0, "data": None}          # 171줄
_token_usage_cache = {"ts": 0, "data": None}         # 396줄
```

이 3개 캐시 딕셔너리는 **두 스레드에서 동시 접근**:
- **Streamlit 메인 스레드** (1088–1109줄): 초기 렌더링 시 `gather_fleet_data()`, `get_token_usage()`, `get_rate_limits()` 호출
- **HTTP 서버 데몬 스레드** (1082줄): `_DataHandler.do_GET()` → `_gather_and_render_body()` → 동일 함수들 호출

Python GIL이 dict 연산의 원자성을 어느 정도 보장하지만, **복합 연산**(ts 읽기 → 비교 → 데이터 갱신)은 GIL로 보호되지 않음. 특히:

```python
def gather_fleet_data():
    now = time.time()
    if _fleet_data_cache["data"][0] and now - _fleet_data_cache["ts"] < _FLEET_CACHE_SEC:
        return _fleet_data_cache["data"]  # ← 스레드 A가 여기서 읽는 동안
    # ... 데이터 수집 ...
    _fleet_data_cache["ts"] = now         # ← 스레드 B가 여기서 쓸 수 있음
    _fleet_data_cache["data"] = result
```

**해결:** `threading.Lock()` per cache, 또는 `@functools.lru_cache` + TTL wrapper, 또는 `threading.local()` 분리.

### 2.2 [심각도: 중] HTTP 서버 graceful shutdown 부재

```python
threading.Thread(target=_start_data_server, daemon=True).start()  # 1082줄
```

데몬 스레드로 HTTP 서버를 실행하지만, `serve_forever()`를 멈출 방법이 없음. Streamlit이 rerun할 때마다 새로운 서버 시작을 시도할 수 있고(`"data_srv" not in st.session_state` 가드가 있지만, session_state가 리셋되면 중복 바인딩 시도 → `OSError: Address already in use`). `_ReusableHTTPServer`의 `allow_reuse_address`가 이를 완화하지만 근본 해결이 아님.

---

## 3. 성능 이슈

### 3.1 [심각도: 높] `get_token_usage()` — 재귀적 glob + 전체 JSONL 파싱

```python
for jf in projects_dir.rglob("*.jsonl"):  # 434줄
    ...
    with open(jf, "r", ...) as fh:
        for line in fh:                    # 전체 파일 라인 순회
```

`~/.claude/projects/` 하위의 **모든 JSONL 파일**을 재귀 탐색하고, 각 파일의 **모든 줄**을 JSON 파싱. JSONL 파일이 수십 MB에 달할 수 있으며, 5초마다 실행됨.

**최적화 방안:**
1. `mtime` 필터로 오늘 수정된 파일만 열기 (이미 적용됨 — 하지만 큰 파일은 여전히 전체 읽기)
2. 파일 끝에서부터 역순 읽기 (`seek` + 역방향 스캔)으로 최근 N개 메시지만 파싱
3. 누적 카운터를 캐시에 저장하고, 새로 추가된 줄만 파싱 (오프셋 기반 증분 파싱)

### 3.2 [심각도: 높] `get_rate_limits()` — 실제 API 호출로 토큰 소비

```python
body = json.dumps({
    "model": "claude-haiku-4-5-20251001",
    "max_tokens": 1,
    "messages": [{"role": "user", "content": "h"}],
})
conn.request("POST", "/v1/messages", body, {...})  # 201줄
```

Rate limit 헤더를 읽기 위해 **실제 Anthropic API에 메시지를 전송**. `max_tokens: 1`이지만:
- 입력 토큰 소비 (프롬프트 + 시스템 오버헤드)
- 출력 토큰 1개 소비
- 15초(`RATE_LIMIT_CACHE_SEC`)마다 반복 = **시간당 ~240회 API 호출**
- rate limit 확인 자체가 rate limit을 소진하는 아이러니

**대안:** Anthropic API에 rate limit 전용 엔드포인트가 없다면, 캐시 주기를 60초 이상으로 늘리거나, Claude Code CLI의 내부 상태 파일을 직접 읽는 방법 검토.

### 3.3 [심각도: 중] `psutil.cpu_percent(interval=0.3)` — 300ms 블로킹

```python
cpu = psutil.cpu_percent(interval=0.3)  # 496줄
```

`interval=0.3`은 CPU 사용률 측정을 위해 **300ms 동안 스레드를 블로킹**. HTTP 서버 스레드에서 호출되면 응답 지연 직결.

**해결:** `interval=0`으로 변경 (마지막 호출 이후 누적값 반환) 또는 별도 스레드에서 주기적 측정 후 캐시 값만 읽기.

### 3.4 [심각도: 중] CSS 문자열 매 요청마다 재생성

`build_full_html()` 내부의 `css` 변수 (647–794줄)는 **동적 값이 전혀 없는 순수 정적 문자열**임에도, 함수 호출마다 f-string으로 재생성됨.

```python
css = f"""
    @import url(...);
    ...  # 150줄의 CSS
    """
```

색상 상수(`BG_VOID`, `RED`, `GREEN` 등)는 모듈 상수이므로, CSS는 **모듈 로드 시 1회만 생성**하면 됨.

### 3.5 [심각도: 낮] `_recv_line` — 무제한 버퍼 성장

```python
def _recv_line(s):
    buf = b""
    while True:
        chunk = s.recv(65536)
        if not chunk:
            return {}
        buf += chunk  # ← 무한 성장 가능
```

`\n`이 도착하지 않으면 `buf`가 메모리 소진까지 성장. 소켓 타임아웃(8초)이 걸려 있지만, 데이터가 계속 들어오면 타임아웃 미발동.

**해결:** `MAX_BUF = 1_048_576` (1MB) 등 상한선 추가.

---

## 4. 보안 이슈

### 4.1 [심각도: 높] CORS `Access-Control-Allow-Origin: *` — 데이터 서버 무방비

```python
self.send_header("Access-Control-Allow-Origin", "*")  # 1052줄
```

`localhost:8501`의 HTTP 서버가 **모든 출처의 요청을 허용**. 악성 웹사이트가 사용자 브라우저에서 `fetch('http://localhost:8501/')`로 플릿 상태 데이터(터미널 내용, 토큰 사용량, API 사용 패턴)를 탈취 가능.

**해결:** `Access-Control-Allow-Origin: http://localhost:8500` (Streamlit 대시보드 출처만 허용).

### 4.2 [심각도: 높] Anthropic 자격증명 직접 접근

```python
cred_path = Path.home() / ".claude" / ".credentials.json"  # 185줄
cred = json.loads(cred_path.read_text())
token = cred.get("claudeAiOauth", {}).get("accessToken", "")
```

OAuth 토큰을 직접 파일에서 읽어 API 호출에 사용. 이 토큰은:
- Claude Code CLI의 전체 권한을 가진 OAuth 토큰
- 예외 발생 시 `_log.warning("Rate limit API failed: %s", e)` 로 에러 메시지에 토큰 일부가 포함될 수 있음
- 프로세스 메모리에 평문으로 상주

**완화:** 토큰 변수를 `del token` 또는 `token = None`으로 사용 후 즉시 해제. 로그 메시지에 예외의 전체 traceback이 포함되지 않도록 확인.

### 4.3 [심각도: 중] User-Agent 스푸핑

```python
"User-Agent": "claude-code/2.1.94",  # 206줄
```

Claude Code CLI로 위장. Anthropic 이용약관 위반 가능성. API 호출이 CLI 내부 호출과 구분 불가해지므로, 이상 행동 감지나 디버깅이 어려워짐.

**해결:** `"User-Agent": "javis-dashboard/2.0"` 등 실제 클라이언트 식별자 사용.

### 4.4 [심각도: 중] 데이터 서버 인증 없음

```python
class _DataHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = _gather_and_render_body()
        # 인증 확인 없이 즉시 응답
```

`localhost:8501`에 바인딩되어 외부 접근은 차단되지만, **같은 시스템의 다른 사용자/프로세스**가 플릿 데이터(터미널 내용 포함)에 접근 가능. 터미널 내용에는 API 키, 파일 경로, 비즈니스 로직 등 민감 정보가 포함될 수 있음.

**완화:** 간단한 Bearer 토큰 인증 (Streamlit → JS → fetch 시 토큰 포함).

### 4.5 [심각도: 낮] `send_error`에 내부 에러 메시지 노출

```python
self.send_error(500, _esc(str(e)))  # 1058줄
```

`_esc`로 XSS는 방지했지만, 내부 에러 메시지(파일 경로, 소켓 에러 상세)가 HTTP 응답으로 노출됨.

**해결:** `self.send_error(500, "Internal Server Error")` — 상세 정보는 로그에만 기록.

---

## 5. 테스트 용이성 이슈

### 5.1 [심각도: 높] 파일시스템/네트워크 직접 의존 — DI 부재

모든 데이터 함수가 파일시스템과 네트워크에 직접 접근:

| 함수 | 외부 의존 |
|---|---|
| `_get_token()` | `SOCKET_TOKEN_FILE.read_text()` |
| `gather_fleet_data()` | `_socket.socket()` → TCP 연결 |
| `get_rate_limits()` | `http.client.HTTPSConnection()` → HTTPS |
| `get_claude_contexts()` | `Path.home() / ".claude" / "projects"` glob |
| `get_token_usage()` | `projects_dir.rglob("*.jsonl")` + 파일 읽기 |
| `get_system_metrics()` | `psutil.cpu_percent()` |

테스트하려면 실제 cmux-win 실행, Anthropic API 접근, 파일 생성이 필요. **의존성 주입** 또는 **프로토콜/인터페이스 기반 추상화**로 모킹 가능하게 해야 함.

### 5.2 [심각도: 중] `detect_status()` — 하드코딩된 키워드, 순서 의존

```python
def detect_status(content):
    if has_error and not is_noise: return "error"
    if any(k in last for k in ["working", "running", ...]): return "live"
    if any(k in last for k in ["분석 완료", ...]): return "done"
    if any(k in last for k in ["waiting", "idle", ...]): return "idle"
    return "idle"
```

- **키워드 중복:** "$ " 는 idle에 매칭되지만, 작업 출력 중 "$" 포함 줄이 있으면 오탐
- **순서 의존:** `live` 키워드에 "loading"이 있어, 페이지 로딩 관련 메시지도 live로 분류
- **테스트 불가:** 키워드 리스트가 함수 내부에 하드코딩 → 설정 파일이나 상수로 추출 필요

### 5.3 [심각도: 중] HTML 출력 검증 불가

렌더러 함수들(`_donut_svg`, `_radar_svg`, `_sparkline_svg`, `build_full_html`)이 HTML 문자열을 반환하지만:
- 반환값의 구조 검증이 불가 (DOM 파싱 필요)
- 특정 데이터가 올바르게 렌더링되었는지 확인하려면 문자열 패턴 매칭 필요
- **개선:** 데이터 변환 함수와 HTML 렌더링 함수를 분리하면, 데이터 계층만 단위 테스트 가능

---

## 6. 기타 이슈

### 6.1 [심각도: 중] `monthly_total` 이중 계산 가능성

```python
# 423-431줄: stats-cache.json에서 월간 합계
for d in dmt:
    if d["date"].startswith(month_str):
        monthly_in += tokens

# 484줄: 결과 조합
"monthly_total": monthly_in + daily_in,
```

`stats-cache.json`의 `dailyModelTokens`에 오늘 날짜 데이터가 이미 포함되어 있으면, `monthly_in`에 오늘 분이 포함된 상태에서 `daily_in`을 다시 더하게 되어 **오늘 토큰이 이중 계산**됨.

### 6.2 [심각도: 중] 컨텍스트 한도 하드코딩

```python
limit = 200_000  # 385줄
```

모델별 컨텍스트 한도가 다를 수 있음 (예: Opus 200K, Sonnet 200K, Haiku 200K — 현재는 동일하나 향후 변경 가능). 상수로 추출하고 모델별 매핑을 고려해야 함.

### 6.3 [심각도: 낮] `_strip` 정규식 — `\r`만 제거, `\r\n` 미고려

```python
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\r")  # 244줄
```

Windows 환경에서 `\r\n` 줄바꿈의 `\r`만 제거하면 빈 줄이 남음. 실질적 문제는 아니나, `\r\n?` 패턴이 더 정확.

### 6.4 [심각도: 낮] `components.html(height=2000)` — 하드코딩된 높이

```python
components.html(html, height=2000, scrolling=True)  # 1109줄
```

콘텐츠 양에 관계없이 2000px 고정. 플릿 크기가 작으면 과도한 빈 공간, 크면 잘림.

---

## 7. 종합 평가

### 6축 점수표

| 축 | 점수 (10) | Phase 1 이전 추정 | 근거 |
|---|:---:|:---:|---|
| **기능 완성도** | **8.5** | 8.0 | 실시간 플릿 모니터링, ETA, 토큰 트래킹, 시스템 메트릭, 컨텍스트 경고 등 풍부한 기능. 깜박임 방지 아키텍처(JS fetch + body 교체)가 잘 작동 |
| **코드 품질** | **5.5** | 4.5 | Phase 1에서 `_match_fleet_config` 추출, `_esc` 도입 등 개선. 그러나 350줄 `build_full_html`, 중복 pane_data 조립, 7-tuple 구조, 모듈 레벨 Streamlit 호출 등 **구조적 문제 잔존** |
| **보안** | **5.0** | 3.5 | XSS 방지 적용 완료. 그러나 CORS `*`, 인증 없는 데이터 서버, 자격증명 직접 접근, User-Agent 스푸핑 등 **네트워크 레벨 보안 미흡** |
| **성능** | **5.0** | 4.5 | fleet 캐시 추가로 소켓 호출 감소. 그러나 전체 JSONL 파싱, 15초마다 실제 API 호출, 300ms 블로킹 CPU 측정, 정적 CSS 매 요청 재생성 등 **I/O 바운드 병목 잔존** |
| **에러 핸들링** | **7.0** | 5.0 | 구체적 예외 타입 + 로깅 잘 적용됨. 소켓 finally cleanup 적용. 다만 `_recv_line` 무한 버퍼, `send_error`에 내부 정보 노출, HTTP 서버 shutdown 부재 등 **엣지 케이스 미처리** |
| **아키텍처** | **4.5** | 4.0 | 1,110줄 단일 파일 모놀리스. 데이터/렌더링/서버 미분리. 스레드 안전성 미보장. DI 부재로 테스트 불가. pane_data 중복 잔존. **가장 큰 개선 여지** |

### 종합 점수: **5.9 / 10** (Phase 1 이전 추정: 4.9)

### 우선순위별 개선 로드맵

#### P0 — 즉시 수정 (안전성·정합성)

| # | 항목 | 이유 |
|---|---|---|
| 1 | CORS를 `localhost:8500`으로 제한 | 외부 사이트의 fleet 데이터 탈취 차단 |
| 2 | 캐시 딕셔너리에 `threading.Lock` 추가 | 경합 조건으로 인한 데이터 손상 방지 |
| 3 | `_recv_line` 버퍼 상한 추가 | OOM 방지 |
| 4 | `monthly_total` 이중 계산 수정 | 잘못된 토큰 통계 표시 수정 |

#### P1 — 단기 개선 (코드 품질·성능)

| # | 항목 | 이유 |
|---|---|---|
| 5 | pane_data 조립 로직을 함수로 추출 | DRY 원칙 복원 |
| 6 | CSS를 모듈 상수로 추출 | 매 요청 150줄 f-string 재생성 방지 |
| 7 | `psutil.cpu_percent(interval=0)` 변경 | 300ms 블로킹 제거 |
| 8 | `get_rate_limits` 캐시 주기 60초+ 확대 | API 호출 빈도 75% 감소 |
| 9 | `User-Agent`를 실제 식별자로 변경 | 이용약관 준수 |

#### P2 — 중기 리팩토링 (아키텍처·테스트)

| # | 항목 | 이유 |
|---|---|---|
| 10 | `build_full_html` 함수 분할 | 350줄 → 5-6개 50줄 이내 함수 |
| 11 | 7-tuple을 `@dataclass PaneData`로 전환 | 타입 안전성 + 가독성 |
| 12 | 모듈 레벨 Streamlit 호출을 `main()`으로 이동 | 임포트 가능성 확보 |
| 13 | `detect_status` 키워드를 설정으로 추출 | 테스트 + 확장 용이성 |
| 14 | JSONL 증분 파싱 (오프셋 캐시) | 대용량 파일 성능 개선 |

#### P3 — 장기 개선 (아키텍처 재설계)

| # | 항목 | 이유 |
|---|---|---|
| 15 | 데이터 계층 / 렌더링 계층 / 서버 계층 3-모듈 분리 | 테스트 가능한 아키텍처 |
| 16 | 데이터 소스 프로토콜/인터페이스 정의 + DI | 모킹 기반 단위 테스트 가능 |
| 17 | 데이터 서버에 Bearer 토큰 인증 추가 | 로컬 프로세스 간 접근 제어 |

---

*RSI Round 2 분석 완료 — Claude Code Worker1 · 2026-06-17*
*Phase 1 대비 +1.0pt 개선 확인. P0 4건 즉시 수정으로 +0.8pt 추가 개선 예상.*
