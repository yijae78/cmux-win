# Technical Review: env-scan monitor

Reviewed files:
- `javis/tests/workspace/env-scan/monitor.py`
- `javis/tests/workspace/env-scan/launch_monitor.py`

Scope: performance issues, type safety, and architectural concerns. Original files were not modified.

## Findings

### 1. High: Streamlit refresh loop blocks execution with `time.sleep`

Locations: `monitor.py:651-652`, `monitor.py:736-740`

`main()` sleeps before calling `st.rerun()` for empty, live, and idle states. In Streamlit, each script run is synchronous for a user session, so the sleep occupies the session worker for 5 to 30 seconds and delays interactions or cancellation. With multiple viewers, every active session can spend most of its time sleeping.

Recommendation: replace blocking sleeps with a Streamlit-native refresh mechanism such as `st_autorefresh`, a frontend timer component, or a timestamp-driven rerun approach that does not block the Python run.

### 2. High: Every refresh repeats filesystem scans and JSON parsing

Locations: `monitor.py:216-340`, `monitor.py:235`, `monitor.py:276`, `monitor.py:380-381`

`_load()` reads and parses several JSON files on every render. In live mode that happens every five seconds. When the primary status files are missing, it also globs historical `master-status-????-??-??.json` files and sorts them by `stat().st_mtime`, then stats the chosen master file again. This is fine for a tiny local folder, but it will get slower as logs accumulate or when files are on a synced or network-backed filesystem.

Recommendation: cache parsed JSON by `(path, mtime)` with `st.cache_data`, keep a lightweight latest-status lookup, and avoid scanning historical files unless the primary status files are missing.

### 3. High: JSON-derived values are interpolated into unsafe HTML

Locations: `monitor.py:469-493`, `monitor.py:496-507`, `monitor.py:511-537`, `monitor.py:560-735`

The dashboard uses `unsafe_allow_html=True` and directly inserts values from JSON into HTML strings. Signal titles, category labels, FSSF keys, dates, and other display values can contain markup-significant characters. That can break the UI and creates a display injection risk even if the source is local.

Recommendation: escape all data-derived values with `html.escape(str(value))` before interpolation. Keep only trusted constant CSS/HTML fragments unescaped, and validate numeric values before formatting.

### 4. Medium: `_load()` mutates parsed signal dictionaries in place

Location: `monitor.py:344-349`

The code adds UI-only workflow metadata directly to dictionaries loaded from `dashboard-data`. This is local today because the JSON is freshly parsed each time, but it couples raw data to presentation state. If caching is added later, the extra field becomes a hidden side effect on shared parsed data.

Recommendation: create a copy for view-only fields instead of mutating parsed JSON objects.

### 5. Medium: Type annotations are too broad for useful checking

Locations: `monitor.py:142-154`, `monitor.py:158`, `monitor.py:469`, `monitor.py:496`, `monitor.py:511`

Most structured data is typed as `dict`, `list[dict]`, or `dict[str, int]`, while `_j()` returns `dict | None`. The implementation then assumes nested JSON shapes and numeric values. A type checker cannot catch malformed `signal_count`, non-list `top_signals`, or non-numeric `psst_score`.

Recommendation: introduce `TypedDict` or small dataclasses for master status, workflow results, dashboard data, and signals. At minimum, use `dict[str, Any]` at JSON boundaries and add helper functions such as `get_int`, `get_str`, and `get_mapping` to normalize external data.

### 6. Medium: Broad exception handling hides data and file errors

Locations: `monitor.py:158-162`, `monitor.py:246-249`, `monitor.py:256-259`, `monitor.py:268-271`

`_j()` catches every exception and returns `None`, and timestamp parsing failures are silently ignored. This makes the UI resilient, but it also makes invalid JSON, permission errors, schema drift, and missing files look the same. Operational failures will be difficult to diagnose.

Recommendation: catch narrower exceptions such as `FileNotFoundError`, `json.JSONDecodeError`, `OSError`, and `ValueError`. Preserve graceful UI behavior, but log or surface a compact diagnostic when data exists but cannot be parsed.

### 7. Medium: Date handling can mix historical and current-day data

Locations: `monitor.py:217-241`, `monitor.py:340`, `monitor.py:379-381`

`data_date` may be resolved from a historical `master-status-YYYY-MM-DD.json`, and `dashboard-data-{data_date}.json` follows that date. Three Horizons classification files, however, are loaded with `classified-signals-{today}.json`. When viewing a historical scan, the dashboard can combine historical dashboard data with current-day classified data or show no horizon data.

Recommendation: use `data_date` consistently for all files representing the selected scan date.

### 8. Medium: Launch script assumes readiness after a fixed sleep and discards startup errors

Locations: `launch_monitor.py:17-27`, `launch_monitor.py:23-26`

`launch_monitor.py` suppresses stdout and stderr, sleeps for three seconds, then opens the browser. If Streamlit fails to import, the port is occupied, dependencies are missing, or startup takes longer than three seconds, the browser still opens and the user gets no useful error.

Recommendation: poll `http://localhost:8504` until ready with a timeout, check `proc.poll()` during startup, and capture stderr to a log file or show it on failure.

### 9. Medium: Fixed port can collide with existing Streamlit processes

Location: `launch_monitor.py:13`

The launcher hard-codes port `8504`. A collision can cause startup failure or unexpected behavior, and the current stderr suppression hides the reason.

Recommendation: probe for a free port or detect an existing service on `8504` before launching. If the fixed port is intentional, fail fast with a clear message.

### 10. Low: Process termination is not robust on KeyboardInterrupt

Location: `launch_monitor.py:31-33`

On `KeyboardInterrupt`, the script calls `proc.terminate()` but does not wait, kill on timeout, or handle child processes. Depending on platform behavior, a Streamlit child process may remain alive.

Recommendation: after `terminate()`, call `wait(timeout=...)`, then `kill()` if needed. If Streamlit spawns child processes in this environment, consider process-group termination.

### 11. Low: Rendering, data access, and state derivation are tightly coupled

Locations: `monitor.py:59-138`, `monitor.py:395-735`

The file mixes filesystem access, JSON normalization, state derivation, CSS, SVG generation, and Streamlit rendering. This is workable for a single dashboard, but it makes unit testing difficult and increases the chance that a data change breaks markup.

Recommendation: split into three layers: data access/parsing, view-model derivation, and rendering. Keep pure functions for chart/view-model generation so they can be tested without Streamlit.

### 12. Low: Some loaded state appears unused

Locations: `monitor.py:148`, `monitor.py:154`, `monitor.py:321-322`, `monitor.py:388`

`wf_validation` and `cross_wf` are loaded into `State` but not rendered in the current UI. This may be planned, but unused state increases cognitive load and can hide stale assumptions.

Recommendation: render these fields, remove them from the view model, or leave a clear comment that they are reserved for planned sections.

## Type Safety Notes

The riskiest type boundary is JSON ingestion. Normalize unknown JSON into explicit shapes before rendering. For fields like counts and scores, explicit coercion is preferable to relying on arithmetic against arbitrary JSON values.

## Performance Notes

The current data volume may be small enough that the dashboard feels fine locally. The main risk is growth over time: frequent reruns plus file globbing, stat calls, and repeated JSON parsing will become visible as logs accumulate or if files are stored in OneDrive/network-backed directories. Caching by file modification time would address most of this without changing user-facing behavior.

## Architectural Summary

The implementation is compact and easy to run, but it is built as a single Streamlit script with global constants and direct filesystem reads during render. A small separation between data loading, state derivation, and HTML rendering would improve testability, enable caching cleanly, and reduce injection/type risks. The launcher should be treated as operational code: readiness detection and visible failure output matter more than a fixed sleep and suppressed logs.
