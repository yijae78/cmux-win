# RSI Round 2 Worker 3 Review: javis/dashboard.py

Reviewed file: `javis/dashboard.py`

Context: re-evaluation after Phase 1 fixes for XSS escaping, narrowed exceptions plus logging, code deduplication, socket cleanup in `finally`, and fleet data caching. Original file was not modified.

## Scores

- Functionality: 8/10
- Code quality: 7/10
- Security: 7/10
- Performance: 6/10
- Error handling: 7/10
- Architecture: 6/10

## Phase 1 Fix Assessment

Phase 1 materially improved the file. `_esc()` now uses `html.escape(str(...))` at `dashboard.py:617-619`; socket cleanup in `gather_fleet_data()` is handled in `finally` at `dashboard.py:162-167`; broad catches were narrowed and logged across socket/API/JSONL/system paths; fleet matching was deduplicated into `_match_fleet_config()` at `dashboard.py:625-635`; and `_fleet_data_cache` reduces repeated socket reads at `dashboard.py:117-124`.

The remaining quality ceiling is mostly architectural rather than cosmetic: data collection, HTTP serving, rendering, and Streamlit startup still live in one module with global mutable state. The dashboard is likely usable locally, but still has security and performance edges that should be addressed before treating it as robust operational tooling.

## Remaining Improvements

### 1. High: Local data server is unauthenticated and explicitly CORS-open

Locations: `dashboard.py:1046-1054`, `dashboard.py:957-960`

`_DataHandler` serves the rendered fleet body on `127.0.0.1:8501` and sends `Access-Control-Allow-Origin: *`. Any web page opened in the same browser can fetch `http://localhost:8501/` and read the response. That response can expose terminal-derived status, token usage, system metrics, and operational state. Binding to localhost prevents remote network access, but CORS `*` removes browser-origin protection for local websites.

Recommendation: remove wildcard CORS unless it is required. If browser fetches from the Streamlit iframe require CORS, issue a random per-process token and require it in a header or query string, or restrict allowed origins to the Streamlit origin.

### 2. High: Data server lifecycle is session-scoped, but the port is process-global

Locations: `dashboard.py:1079-1082`, `dashboard.py:1066-1076`, `dashboard.py:622`

The server thread is guarded by `st.session_state`, so each new Streamlit browser session can try to start another server on fixed port `8501`. Only one process can own the port; later sessions will log a bind failure and then rely on whichever server is already running. This is fragile and makes failures dependent on session ordering.

Recommendation: move server startup behind a module-level singleton guarded by a `threading.Lock`, store the actual server object globally, and make startup idempotent across all Streamlit sessions. Also consider dynamic port allocation if `8501` is already in use.

### 3. Medium: Token usage still scans and parses large JSONL sets every cache interval

Locations: `dashboard.py:400-489`, especially `dashboard.py:433-468`

`get_token_usage()` caches for five seconds, but cache misses still call `projects_dir.rglob("*.jsonl")`, stat every matching file, and parse every line in files modified today. On long active sessions this can become the dominant cost, especially under synced home directories or many Claude project logs.

Recommendation: cache by file path, mtime, and size; parse only appended portions where possible; or maintain a lightweight incremental index. A 15-30 second cache would also be more consistent with dashboard-level monitoring than a five second full rescan.

### 4. Medium: `get_claude_contexts()` rereads recent JSONL files without caching

Locations: `dashboard.py:334-393`, especially `dashboard.py:360-371`

Context usage scans up to ten recent JSONL files and reads each line to find the last usage record. Unlike token usage and fleet data, this path has no cache. If it is later rendered or called during every refresh, it will add avoidable I/O.

Recommendation: cache by recent file mtimes or integrate this into the same JSONL usage index used by `get_token_usage()`.

### 5. Medium: Error handling still misses renderer and schema failures in the data endpoint

Locations: `dashboard.py:1046-1059`, `dashboard.py:638-946`, `dashboard.py:1022-1043`

`_DataHandler.do_GET()` catches only `OSError` and `ConnectionError`. Most likely render-time failures are `KeyError`, `TypeError`, or `ValueError` from unexpected shapes in `usage_data`, `metrics`, `rate_limits`, `pane_data`, or color/status fields. Those exceptions would escape the handler path and may close the request without a clean diagnostic.

Recommendation: validate the view model before rendering, or broaden only this top-level HTTP boundary to catch `Exception` after logging `exc_info=True`, returning a safe fallback HTML fragment. Keep inner catches narrow, but the service boundary should fail closed and visibly.

### 6. Medium: Type safety remains weak at the data boundaries

Locations: `dashboard.py:121`, `dashboard.py:174`, `dashboard.py:400`, `dashboard.py:638`, `dashboard.py:1022`

The file still passes loosely shaped dictionaries and tuples between collection and rendering functions. `pane_data` is a tuple with seven positional fields, `rate_limits` and `usage_data` are untyped dictionaries, and `_match_fleet_config()` returns a generic `dict`. This makes accidental key drift hard to catch.

Recommendation: introduce `TypedDict` or dataclasses for `FleetConfig`, `Surface`, `PaneData`, `UsageData`, `RateLimitData`, and `SystemMetrics`. This would also make `build_full_html()` easier to test.

### 7. Medium: Network/API behavior is embedded in render-time data collection

Locations: `dashboard.py:174-240`, `dashboard.py:1040-1043`, `dashboard.py:1105-1108`

`get_rate_limits()` performs an Anthropic API request on cache miss as part of dashboard rendering/fetching. It is cached for 15 seconds, but failures or latency still affect refresh responses. It also sends a real `/v1/messages` request solely to inspect rate-limit headers.

Recommendation: move external API polling into a background worker with a longer interval and stale-last-good values. If headers can be obtained from a cheaper endpoint or existing telemetry, use that instead.

### 8. Low: Logging is present but not operationally structured

Locations: `dashboard.py:29-31`, `dashboard.py:160`, `dashboard.py:239`, `dashboard.py:473`, `dashboard.py:1076`

Logging is a clear improvement over silent failure. However, logs mostly contain message strings without stack traces or context identifiers. For intermittent handler/render failures, this may not be enough to diagnose the failing file, endpoint, or data shape.

Recommendation: use `exc_info=True` for unexpected boundary failures, include path/count metadata for JSONL scans, and avoid repeated warning spam by rate-limiting recurrent errors.

### 9. Low: Rendering remains hard to test because HTML, CSS, data, and transport are coupled

Locations: `dashboard.py:638-993`, `dashboard.py:1022-1043`, `dashboard.py:1079-1109`

`build_full_html()` contains CSS, SVG composition, markup, JavaScript refresh logic, numeric formatting assumptions, and display logic. `_gather_and_render_body()` directly calls live collectors. This is practical for a single-file dashboard, but it limits focused tests and makes regressions harder to isolate.

Recommendation: split into collector, view-model, and renderer layers. Unit-test the view-model builder with fixture data, and keep Streamlit/HTTP code as a thin shell.

### 10. Low: Status heuristics are broad and may misclassify terminal state

Locations: `dashboard.py:251-289`

`detect_status()` relies on substring lists over the last terminal lines. The lists include many generic terms, so harmless output can be marked live or error, while active processes with different wording can be missed. This is acceptable for a visual monitor, but the status should be treated as heuristic.

Recommendation: prefer explicit agent state from cmux if available. If terminal parsing remains necessary, keep keyword groups configurable and add tests for known terminal transcripts.

## Axis Rationale

Functionality 8/10: the dashboard has a coherent live rendering path, fallback empty view, socket fleet collection, token/rate/system metrics, and client-side refresh. Main functional risk is server lifecycle around fixed port `8501`.

Code quality 7/10: Phase 1 improved duplication and exception hygiene. Remaining issues are large single-file structure, untyped dictionaries/tuples, and render logic that is difficult to test in isolation.

Security 7/10: `html.escape` is a strong improvement and removes the main XSS issue for currently rendered external text. The major remaining concern is the unauthenticated CORS-open localhost endpoint.

Performance 6/10: fleet socket caching helps, and client-side refresh avoids Streamlit rerun flicker. JSONL scans and API polling still happen on refresh paths and will scale poorly as logs grow.

Error handling 7/10: catches are narrower and logged, and socket cleanup is reliable. The HTTP boundary still catches too little for render/schema failures, and several parse loops intentionally drop bad records silently.

Architecture 6/10: the design works as a local dashboard, but global mutable caches, per-session server startup, fixed ports, collection and rendering in one module, and tuple-based view data limit maintainability.

## Priority Next Steps

1. Protect or remove wildcard CORS on the localhost data server.
2. Make the data server process-singleton and port-aware rather than session-scoped.
3. Add typed view models for usage, metrics, rate limits, fleet config, and pane data.
4. Cache JSONL parsing incrementally by path/mtime/size.
5. Add a top-level safe fallback in `_DataHandler` for renderer/schema exceptions with `exc_info=True`.

## Overall

Post Phase 1, `dashboard.py` is noticeably safer and more maintainable than the earlier pattern. I would rate it as good enough for local personal monitoring, but not yet production-grade. The next round should focus less on escaping and local cleanup, and more on service boundaries, typed data contracts, and avoiding repeated expensive scans.
