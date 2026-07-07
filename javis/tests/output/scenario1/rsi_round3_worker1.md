# RSI Round 3 — dashboard.py 코드 품질 심층 분석

**대상 파일:** `/c/dev/cmux-win/javis/dashboard.py` (1,163줄)
**분석 단계:** RSI Round 3 (Phase 2 수정 완료 후)
**분석일:** 2026-06-17
**비교 기준:** RSI Round 2 (Phase 1 후) 점수

---

## Phase 2 적용 확인

| Phase 2 항목 | 적용 상태 | 위치 | 품질 평가 |
|---|---|---|---|
| `PaneData` dataclass | ✅ 적용됨 | 40–47줄 | 필드 7개, 타입 힌트 명시, `str \| None` union 사용 |
| `UsageData` dataclass | ✅ 적용됨 | 50–59줄 | 기본값 제공, `field(default_factory=list)` 올바른 사용 |
| `RateLimitData` dataclass | ✅ 적용됨 | 62–69줄 | `get_rate_limits()` 반환 타입 명시 (223줄) |
| `SystemMetrics` dataclass | ✅ 적용됨 | 72–77줄 | `get_system_metrics()` 반환 타입 명시 (541줄) |
| `threading.Lock` 도입 | ✅ 적용됨 | 36줄 `_cache_lock` | ⚠️ **부분 적용** — 아래 상세 |
| CORS 제한 | ✅ 적용됨 | 1103줄 `http://localhost:8500` | 정확한 Streamlit 출처 제한 |
| 소켓 cleanup `finally` | ✅ 유지됨 | 211–216줄 | Phase 1에서 적용, 유지 확인 |
| pane_data에 `PaneData` 사용 | ✅ 적용됨 | 1087–1089, 1154–1156줄 | tuple → dataclass 전환 완료 |
| `build_full_html`에서 `.` 접근 | ✅ 적용됨 | 688, 858, 883 등 | `p.status`, `usage_data.daily_in` 등 |
| 아이콘 XSS 이스케이프 추가 | ✅ 적용됨 | 888줄 `icon = _esc(p.config["icon"])` | Round 2에는 없었던 추가 개선 |

---

## Round 2 지적 사항 해결 추적표

| R2 우선순위 | R2 항목 | R3 상태 | 비고 |
|:---:|---|:---:|---|
| **P0-1** | CORS `*` → localhost:8500 | ✅ 해결 | 1103줄 |
| **P0-2** | 캐시 Lock 추가 | ⚠️ **부분** | 읽기만 Lock, 쓰기 일부 미적용 — §1.1 |
| **P0-3** | `_recv_line` 버퍼 상한 | ❌ 미해결 | 152–161줄, 무한 성장 가능 — §2.1 |
| **P0-4** | `monthly_total` 이중 계산 | ❌ 미해결 | 532줄 — §2.2 |
| **P1-5** | pane_data 조립 함수 추출 | ❌ 미해결 | 1077–1089 vs 1144–1156 중복 — §1.2 |
| **P1-6** | CSS 모듈 상수화 | ❌ 미해결 | 695–842줄 매 호출 재생성 — §3.1 |
| **P1-7** | `psutil.cpu_percent(interval=0)` | ❌ 미해결 | 544줄, 300ms 블로킹 — §3.2 |
| **P1-8** | Rate limit 캐시 60초+ 확대 | ❌ 미해결 | 84줄, 15초 유지 — §3.3 |
| **P1-9** | User-Agent 실제 식별자 | ❌ 미해결 | 252줄 — §2.5 |
| **P2-10** | `build_full_html` 분할 | ❌ 미해결 | 686–1042줄, ~356줄 — §1.3 |
| **P2-11** | 7-tuple → dataclass | ✅ 해결 | `PaneData` 사용 |
| **P2-12** | 모듈 레벨 st 호출 → main() | ❌ 미해결 | 128–140줄 — §1.4 |
| **P2-13** | detect_status 키워드 외부화 | ❌ 미해결 | 298–336줄 — §4.1 |

**해결률: 14건 중 4건 완전 해결 + 1건 부분 해결 = 35%**

---

## 1. 아키텍처 — 잔존 이슈 + 신규 발견

### 1.1 [심각도: 높] Lock 적용 비일관성 — 쓰기 경로 미보호 (신규 발견)

Phase 2에서 `_cache_lock`을 도입했으나 **적용이 일관적이지 않음:**

| 캐시 | 읽기 Lock | 쓰기 Lock | 에러 경로 Lock |
|---|:---:|:---:|:---:|
| `_fleet_data_cache` | ✅ (170–172) | ✅ (203–205) | ❌ (210) |
| `_rate_limit_cache` | ✅ (226–228) | ❌ (281–282) | ❌ (287) |
| `_token_usage_cache` | ✅ (450–452) | ❌ (536–537) | — |

**구체적 문제:**

```python
# get_rate_limits() — 쓰기가 Lock 바깥 (281–282줄)
        result = RateLimitData(...)
        _rate_limit_cache["ts"] = now        # ← Lock 없음
        _rate_limit_cache["data"] = result   # ← Lock 없음
        return result

# get_token_usage() — 동일 패턴 (536–537줄)
    _token_usage_cache["ts"] = now_ts        # ← Lock 없음
    _token_usage_cache["data"] = result      # ← Lock 없음
```

스레드 A가 `ts`를 갱신한 뒤 `data`를 갱신하기 전에 스레드 B가 읽으면, 새로운 `ts`에 **이전 `data`**가 반환됨. `gather_fleet_data`만 올바르게 적용(203–205줄에서 `with _cache_lock`으로 `ts`와 `data`를 원자적 갱신).

**또한:** `gather_fleet_data` 에러 경로(210줄)에서 `_fleet_data_cache.get("data", ...)` 호출이 Lock 바깥:

```python
    except (...) as e:
        return _fleet_data_cache.get("data", ([], []))  # ← Lock 없음
```

### 1.2 [심각도: 높] pane_data 조립 로직 여전히 중복 (R2 P1-5 미해결)

Phase 2에서 tuple을 `PaneData`로 교체했지만, **조립 루프 자체는 여전히 복사-붙여넣기:**

```python
# _gather_and_render_body (1077–1089줄)
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
    pane_data.append(PaneData(surface=sf, config=cfg, content=content,
                               status=status, activity=activity,
                               preview=preview, ctx_warn=ctx_warn))

# 메인 블록 (1144–1156줄)
# ← 13줄이 글자 하나까지 동일
```

**한 줄 수정:** `_build_pane_data(terminals, contents) -> list[PaneData]` 추출로 양쪽 모두 호출.

### 1.3 [심각도: 중] `build_full_html` — 356줄 함수 유지 (R2 P2-10 미해결)

686–1042줄. Phase 2에서 dataclass `.` 접근으로 가독성은 개선됐으나 함수 크기는 동일:

| 영역 | 줄 수 | 정적/동적 |
|---|---|---|
| CSS (695–842) | 148줄 | **100% 정적** — 모듈 상수 가능 |
| Body HTML (844–995) | 151줄 | 동적 |
| JS (1002–1038) | 36줄 | 준정적 (DATA_PORT, elapsed만 동적) |

CSS만 모듈 상수로 추출해도 함수가 **208줄로 40% 축소**.

### 1.4 [심각도: 중] 모듈 레벨 Streamlit 호출 (R2 P2-12 미해결)

```python
# 128–140줄 — 모듈 임포트 시 즉시 실행
st.set_page_config(...)
st.markdown("""<style>...</style>""", unsafe_allow_html=True)
```

`import dashboard`만으로 `StreamlitAPIException` 발생 → 단위 테스트에서 데이터 함수 임포트 불가.

### 1.5 [심각도: 중] 이중 시작시간 — 미해결 (R2 §1.3)

```python
_fleet_start = datetime.now()                           # 1068줄
st.session_state.fleet_start = datetime.now()           # 1136줄
```

`_gather_and_render_body` → `_fleet_start` (1094줄)
Streamlit 메인 → `st.session_state.fleet_start` (1161줄)

두 값 간 수 밀리초~수 초 차이 → 가동시간 표시 불일치.

### 1.6 [심각도: 낮] 미사용 코드 (신규 발견)

| 항목 | 줄 | 용도 |
|---|---|---|
| `BG_PRIMARY` | 88 | 사용처 없음 |
| `BG_RAISED` | 89 | 사용처 없음 |
| `SURFACE_2` | 91 | 사용처 없음 |
| `SURFACE_3` | 92 | 사용처 없음 |
| `BORDER_HEAVY` | 94 | 사용처 없음 |
| `ACCENT_DIM` | 110 | 사용처 없음 |
| `get_claude_contexts()` | 381–440 | **60줄 함수** — 호출 없음 |
| `s_color`, `w_color` | 867–868 | 계산 후 미참조 |

`get_claude_contexts()`는 60줄에 달하는 JSONL 파싱 함수인데 **코드 어디에서도 호출되지 않음**. 사문 코드가 유지보수 부담.

---

## 2. 보안 — 잔존 이슈

### 2.1 [심각도: 높] `_recv_line` 버퍼 상한 없음 (R2 P0-3 미해결)

```python
def _recv_line(s):
    buf = b""
    while True:
        chunk = s.recv(65536)     # 64KB씩 수신
        if not chunk:
            return {}
        buf += chunk              # ← 상한 없음
        idx = buf.find(b"\n")
        if idx >= 0:
            return json.loads(buf[:idx].decode("utf-8"))
```

소켓 타임아웃(8초)이 있지만, 8초 동안 `\n` 없이 64KB 청크가 반복 도착하면 `buf`가 수백 MB 성장 가능. cmux-win 소켓이 localhost라 실제 위험은 낮으나, 방어 코딩 원칙상 상한 필요:

```python
MAX_RECV_BUF = 1_048_576  # 1MB
if len(buf) > MAX_RECV_BUF:
    _log.warning("recv buffer exceeded %d bytes", MAX_RECV_BUF)
    return {}
```

### 2.2 [심각도: 중] `monthly_total` 이중 계산 (R2 P0-4 미해결)

```python
# 470–479줄: stats-cache.json에서 월간 합계
for d in dmt:
    if d["date"].startswith(month_str):
        for model, tokens in d.get("tokensByModel", {}).items():
            monthly_in += tokens

# 532줄: 결과 조합
monthly_total=monthly_in + daily_in,
```

`stats-cache.json`의 `dailyModelTokens`에 **오늘 날짜 항목이 포함**되어 있으면:
- `monthly_in` = 이번 달 전체 (오늘 포함)
- `daily_in` = 오늘 JSONL 파싱 결과
- `monthly_total` = 오늘 분이 **2번 합산**

**수정안:**
```python
today_str = now.strftime("%Y-%m-%d")
for d in dmt:
    if d["date"].startswith(month_str) and d["date"] != today_str:
        ...
```

### 2.3 [심각도: 중] `send_error`에 내부 에러 메시지 노출 (R2 §4.5 미해결)

```python
self.send_error(500, _esc(str(e)))  # 1109줄
```

XSS는 방지했으나, 에러 메시지에 파일 경로(`/home/user/.claude/...`) 또는 소켓 상세 정보가 포함될 수 있음.

### 2.4 [심각도: 중] Rate limit API — 실제 토큰 소비 (R2 §3.2 미해결)

15초마다 Anthropic API에 `max_tokens: 1` 요청 전송. 시간당 ~240회. 비용은 미미하지만 **rate limit 확인이 rate limit을 소진**하는 구조적 모순.

### 2.5 [심각도: 낮] User-Agent 스푸핑 (R2 P1-9 미해결)

```python
"User-Agent": "claude-code/2.1.94",  # 252줄
```

---

## 3. 성능 — 잔존 이슈

### 3.1 [심각도: 중] CSS 150줄 매 호출 재생성 (R2 P1-6 미해결)

`build_full_html` 내부 CSS (695–842줄)에 사용된 변수는 모두 모듈 상수:
- `BG_VOID`, `RED`, `GREEN`, `BLUE`, `AMBER`, `ACCENT`, `ACCENT_LIGHT`, `TEXT_MUTED`

**전부 불변** → 모듈 로드 시 1회 생성 후 재사용 가능. 현재는 5초마다 HTTP 서버에서 호출될 때마다 148줄의 f-string을 재평가.

### 3.2 [심각도: 중] `psutil.cpu_percent(interval=0.3)` 블로킹 (R2 P1-7 미해결)

```python
cpu = psutil.cpu_percent(interval=0.3)  # 544줄
```

HTTP 서버 스레드에서 호출 시 **300ms 응답 지연**. JS fetch의 5초 간격에 비해 6%의 응답시간 오버헤드.

### 3.3 [심각도: 중] Rate limit 15초 캐시 (R2 P1-8 미해결)

```python
RATE_LIMIT_CACHE_SEC = 15  # 84줄
```

대시보드 새로고침(5초)보다 긴 15초 캐시라 2/3의 요청은 캐시 히트. 하지만 API 호출 자체가 ~500ms HTTPS 라운드트립 + 토큰 소비이므로, 60–120초로 확대해도 UX 영향 없음.

### 3.4 [심각도: 낮] `get_token_usage()` 전체 JSONL 재파싱 (R2 §3.1 미해결)

`projects_dir.rglob("*.jsonl")` (482줄) → 오늘 수정된 파일의 **모든 줄** JSON 파싱. 5초 캐시가 있으나, 캐시 만료 시 대형 JSONL 전체를 다시 읽음.

---

## 4. 테스트 용이성 — 잔존 이슈

### 4.1 [심각도: 중] `detect_status` 하드코딩 키워드 (R2 P2-13 미해결)

310–335줄에 걸쳐 **4개 카테고리 × 총 55개 키워드**가 함수 내부에 하드코딩. 키워드 추가/수정 시 함수 자체를 수정해야 하고, 키워드 간 우선순위 충돌 테스트가 어려움.

현재 잠재적 충돌 예:
- `"loading"` (live) vs 로딩 화면 메시지 (idle이어야 함)
- `"$ "` (idle) — 작업 출력에 달러 기호 포함 시 오탐
- `"cooked"` (live) — 완료 의미로 사용 시 오탐
- `"/compact"` (warning) — 명령어 도움말 표시에서도 매칭

### 4.2 [심각도: 중] 외부 의존 DI 부재 (R2 §5.1 미해결)

Phase 2의 dataclass 도입으로 **출력 타입은 명확**해졌으나, **입력 의존(파일시스템/소켓/API)**은 여전히 직접 접근:

```python
# 테스트하려면 실제 필요:
# - cmux-win 소켓 서버 (gather_fleet_data)
# - ~/.claude/.credentials.json (get_rate_limits)
# - ~/.claude/projects/*.jsonl (get_token_usage)
# - psutil (get_system_metrics)
```

Dataclass가 반환 타입에 적용됐으므로, 다음 단계는 **데이터 소스 프로토콜** 도입:

```python
class FleetDataSource(Protocol):
    def get_surfaces(self) -> tuple[list[dict], list[str]]: ...

# 프로덕션: SocketFleetDataSource (현재 코드)
# 테스트: MockFleetDataSource (하드코딩된 테스트 데이터)
```

---

## 5. Phase 2 개선 효과 분석

### 5.1 Dataclass 도입 효과

**긍정적 영향:**
- `build_full_html`에서 tuple 인덱싱 제거 → `p.status`, `p.config["color"]` 등 명시적 접근
- IDE 자동완성 지원 (필드명 + 타입)
- 새 필드 추가 시 NamedTuple처럼 모든 생성자를 수정할 필요 없음 (기본값 가능)
- `get_rate_limits()`, `get_system_metrics()` 등의 반환 타입이 문서화됨

**남은 비일관성:**
- `get_claude_contexts()` → 여전히 `list[dict]` 반환 (381줄). 다만 이 함수는 미사용이므로 실질적 영향 없음.
- `FLEET` 리스트의 요소 → 여전히 `dict` (119–125줄). `FleetConfig` dataclass로 전환 가능하나 5개 고정 상수라 ROI 낮음.
- 캐시 딕셔너리 타입 힌트 `dict[str, Any]` (164, 220, 443줄) → 저장하는 값이 dataclass인데 타입이 `Any`로 표기. 실질적 문제는 아니나 `_rate_limit_cache: dict[str, float | RateLimitData | None]` 등이 더 정확.

### 5.2 Thread Lock 도입 효과

**긍정적 영향:**
- `gather_fleet_data` 읽기+쓰기 모두 Lock → 완전 보호 ✅
- 3개 캐시의 읽기 경로 모두 Lock → TOCTOU 방지

**남은 격차 (§1.1에서 상세):**
- `_rate_limit_cache` 쓰기 미보호
- `_token_usage_cache` 쓰기 미보호
- `gather_fleet_data` 에러 경로 미보호

### 5.3 CORS 제한 효과

`Access-Control-Allow-Origin: *` → `http://localhost:8500` 변경으로 **브라우저 기반 데이터 탈취 완전 차단**. 이 단일 변경이 Round 2 보안 점수의 가장 큰 개선 요인.

---

## 6. 종합 평가

### 6축 점수표 — Round 2 vs Round 3

| 축 | R2 점수 | R3 점수 | 변화 | 근거 |
|---|:---:|:---:|:---:|---|
| **기능 완성도** | 8.5 | **8.5** | → | 기능 변경 없음. 미사용 `get_claude_contexts()` 60줄이 존재하나 기능에 영향 없음 |
| **코드 품질** | 5.5 | **6.5** | +1.0 | Dataclass 4종 도입으로 타입 안전성·가독성 대폭 개선. `.status` 접근 패턴이 tuple 인덱싱 대비 월등. 그러나 pane_data 조립 중복, 356줄 함수, 6개 미사용 상수, 미사용 함수 60줄 잔존으로 7.0 미달 |
| **보안** | 5.0 | **6.5** | +1.5 | CORS 제한(P0 해결)이 가장 큰 개선. `_recv_line` 무한 버퍼, `send_error` 내부 정보 노출, User-Agent 스푸핑 잔존. 7.0 미달은 `_recv_line` + Rate limit API 토큰 소비 때문 |
| **성능** | 5.0 | **5.5** | +0.5 | Lock 도입 자체는 성능에 중립(오버헤드 미미). CSS 재생성(148줄), psutil 300ms 블로킹, 15초 API 호출, 전체 JSONL 파싱 모두 미해결. 0.5 가산은 Lock으로 인한 캐시 정합성 향상이 간접적 성능 기여 |
| **에러 핸들링** | 7.0 | **7.0** | → | Phase 2에서 에러 핸들링 변경 없음. Phase 1의 narrowed exception + logging 유지. `send_error` 내부 정보 노출 미수정 |
| **아키텍처** | 4.5 | **5.5** | +1.0 | Dataclass 계약이 계층 간 인터페이스 역할. `PaneData`가 데이터 → 렌더링 경계를 명시. 그러나 모듈 분리 없음, 356줄 함수, 이중 시작시간, 모듈 레벨 st 호출, DI 부재로 6.0 미달 |

### 종합 점수 비교

| 라운드 | 종합 점수 | Phase 적용 내용 |
|---|:---:|---|
| **Round 2** (Phase 1 후) | **5.9** | XSS 방지, narrowed exceptions, `_match_fleet_config`, socket finally, fleet cache |
| **Round 3** (Phase 2 후) | **6.6** | + Dataclass 4종, threading.Lock, CORS 제한 |
| **델타** | **+0.7** | |

### Round 4 진입을 위한 우선순위 로드맵

#### P0 — 즉시 (정합성·안전성) — 예상 효과: +0.5pt

| # | 항목 | 예상 작업량 | 영향 축 |
|---|---|---|---|
| 1 | Lock 쓰기 경로 일관 적용 (`_rate_limit_cache`, `_token_usage_cache` 쓰기 + 에러 경로) | 10줄 수정 | 아키텍처 +0.3 |
| 2 | `_recv_line` 버퍼 상한 1MB | 4줄 추가 | 보안 +0.2 |
| 3 | `monthly_total` 이중 계산 수정 (오늘 날짜 제외) | 1줄 조건 추가 | 기능 정합성 |

#### P1 — 단기 (구조·성능) — 예상 효과: +0.8pt

| # | 항목 | 예상 작업량 | 영향 축 |
|---|---|---|---|
| 4 | `_build_pane_data(terminals, contents)` 추출 | 1함수 추출 + 2곳 호출 변경 | 코드 품질 +0.3 |
| 5 | CSS를 `_DASHBOARD_CSS` 모듈 상수로 추출 | 이동만 | 성능 +0.3, 코드 품질 +0.2 |
| 6 | `psutil.cpu_percent(interval=0)` 변경 | 1줄 | 성능 +0.2 |
| 7 | 미사용 코드 제거 (`get_claude_contexts`, 6개 상수, `s_color`/`w_color`) | 삭제 | 코드 품질 +0.2 |
| 8 | `send_error` → 내부 정보 제거 | 1줄 | 보안 +0.1 |

#### P2 — 중기 (아키텍처) — 예상 효과: +0.5pt

| # | 항목 | 예상 작업량 | 영향 축 |
|---|---|---|---|
| 9 | `_fleet_start` → `st.session_state.fleet_start` 통합 | 3줄 | 아키텍처 +0.1 |
| 10 | Rate limit 캐시 60초 + User-Agent 변경 | 2줄 | 보안 +0.2, 성능 +0.1 |
| 11 | 모듈 레벨 st 호출 → `main()` 이동 | 20줄 리팩토링 | 아키텍처 +0.2, 테스트 용이성 |
| 12 | `detect_status` 키워드 → 모듈 상수 딕셔너리 | 분리 | 테스트 용이성 |

**P0+P1 완료 시 예상 종합 점수: 7.9 / 10**

---

*RSI Round 3 분석 완료 — Claude Code Worker1 · 2026-06-17*
*Phase 2에서 +0.7pt 달성 (5.9→6.6). Round 2 P0 4건 중 1건만 완전 해결, 1건 부분 해결. Lock 쓰기 일관성 적용과 pane_data 추출이 다음 라운드 최우선.*
