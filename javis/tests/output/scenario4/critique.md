# Javis Fleet Auto-Recovery Watchdog -- Combined Critique

> **Design Under Review**: `design_v1.md` (Architecture Design v1)
> **Date**: 2026-06-17
> **Format**: AGY perspective (Design/Strategy) + Codex perspective (Technical/Security)

---

## AGY Critique (Design / UX / Strategy)

### AGY-1: idle_timeout > stuck_timeout Inversion (Severity: HIGH)

**Issue**: `idle_timeout` is 300s but `stuck_timeout` is 120s. The state machine says IDLE transitions to STUCK after `stuck_timeout`, but numerically a worker would be classified STUCK (120s) *before* it would be classified IDLE (300s). The `_classify` method checks `idle_seconds > stuck_timeout` before `idle_seconds > idle_timeout`, so a worker will jump from LIVE directly to STUCK, *skipping IDLE entirely*.

**Expected**: LIVE -> IDLE (some threshold) -> STUCK (higher threshold). The idle_timeout should be less than stuck_timeout, or the classification logic needs to evaluate IDLE first.

**Impact**: The IDLE state is effectively dead code. Workers never enter IDLE -- they go straight from LIVE to STUCK after 120s, triggering premature recovery actions on workers that are simply waiting for input.

---

### AGY-2: No Distinction Between "Legitimately Thinking" and "Stuck" (Severity: HIGH)

**Issue**: AI CLIs (especially Claude) can legitimately process for minutes without screen output changes. A complex coding task might show "Thinking..." for 3+ minutes. The current hash-based detection would classify this as STUCK and send Ctrl+C, *interrupting a valid operation*.

**Expected**: The detector should recognize active-processing patterns (spinner animation, "Thinking...", "Processing...") and treat them as LIVE even when the screen hash does not change (spinners might repeat the same frame across two scans). The dashboard's `detect_status()` already has an extensive list of such patterns -- the watchdog's pattern list is impoverished by comparison.

**Impact**: False-positive STUCK detection leading to Ctrl+C of active work. This is worse than doing nothing.

---

### AGY-3: Master Panel Escalation Is a Shell Echo (Severity: MEDIUM)

**Issue**: Tier 3 escalation sends `echo '[WATCHDOG ALERT]...'` to the Master pane. But the Master pane is running an interactive Claude CLI, not a shell. Sending `echo` to Claude will be interpreted as a user prompt, not a system alert. Claude will try to "answer" the echo command instead of alerting the human.

**Expected**: Escalation should either (a) write to a shared file that the dashboard reads and displays as an alert banner, or (b) use the cmux-win Socket API to display a notification, or (c) write to a log file that the human monitors.

**Impact**: Escalation messages are swallowed by the Claude CLI and never reach the human operator.

---

### AGY-4: No Backoff Between Scan Cycles for the Same Worker (Severity: MEDIUM)

**Issue**: The `recovery_cooldown` (60s) prevents rapid-fire actions, but the *detection* runs every 10s and will keep classifying the same worker as STUCK every cycle. After cooldown expires, it immediately fires another Tier 1 action. There is no exponential backoff.

**Expected**: After each failed recovery attempt, the cooldown should increase (e.g., 60s -> 120s -> 240s). This prevents the watchdog from hammering a worker that might be in a genuinely unrecoverable state but not yet escalated.

**Impact**: A worker stuck in an unusual state gets Ctrl+C every 60s, three times, then restarted, then escalated -- all within ~5 minutes. This is aggressive and may cause data loss if the worker is actually processing.

---

### AGY-5: CSO Panel Is Not Excluded by Default (Severity: MEDIUM)

**Issue**: The default exclusion list is `["Master", "Dashboard"]`. But the fleet has a CSO (Chief of Staff Officer) panel that runs Claude in a monitoring/coordination role. The CSO may be idle for extended periods between tasks. The watchdog would detect CSO as STUCK and start sending Ctrl+C.

**Expected**: CSO should be in the exclusion list, or the exclusion matching should be configurable per-role rather than just label-substring matching.

**Impact**: Watchdog interferes with the CSO's coordination work.

---

### AGY-6: No "Pause Worker" State for Intentional Inactivity (Severity: LOW)

**Issue**: Sometimes a worker is intentionally idle -- waiting for another worker to finish a prerequisite. The master might park a worker deliberately. The watchdog has no concept of "paused" or "parked" workers.

**Expected**: A mechanism to mark workers as "paused" (e.g., a file-based marker, or a list in config) so the watchdog skips them.

**Impact**: Watchdog needlessly recovers intentionally-parked workers.

---

### AGY-7: Over-Engineering Concern -- WorkerHistory Lives in Two Places (Severity: LOW)

**Issue**: Both `Detector` and `Strategy` maintain their own `_histories: dict[str, WorkerHistory]` dictionaries. The Detector tracks hash changes and consecutive_stuck; the Strategy tracks tier counts and cooldowns. This splits a single conceptual entity (worker tracking state) across two modules, risking data inconsistency.

**Expected**: Either share a single history store (passed by reference), or clearly separate the two concerns into distinct data structures with different names so the overlap is not confusing.

**Impact**: Maintenance burden. If someone changes the Detector's history logic, they might forget the Strategy's copy.

---

## Codex Critique (Technical / Security / Performance)

### CDX-1: Race Condition in Hash Comparison (Severity: HIGH)

**Issue**: The `idle_seconds` calculation in `_scan_one` is incorrect:

```python
if content_changed:
    history.consecutive_stuck = 0
    idle_seconds = 0.0
else:
    history.consecutive_stuck += 1
    elapsed = (now - (history.last_recovery_at or now)).total_seconds()
    idle_seconds = elapsed
```

When `content_changed` is False and `last_recovery_at` is None, `elapsed = (now - now).total_seconds() = 0.0`. So `idle_seconds` is always 0 on the first detection of no-change, which means the worker can *never* become STUCK on the first pass. The field `last_recovery_at` is semantically wrong here -- it should be `last_change_at`, but `last_change_at` is set on the WorkerState (output), not tracked persistently in WorkerHistory.

**Expected**: Track `last_output_change_at` in WorkerHistory. When content changes, update it. When content does not change, compute `idle_seconds = now - last_output_change_at`.

**Impact**: idle_seconds is always 0 on the first no-change scan. The worker must go through multiple scan cycles with the wrong elapsed time before the accumulated `consecutive_stuck * scan_interval` approximation happens to exceed stuck_timeout. Detection is delayed and unreliable.

---

### CDX-2: MD5 Hash for Change Detection Is Fragile (Severity: MEDIUM)

**Issue**: The screen capture includes ANSI escape codes, cursor position sequences, and trailing whitespace that can differ between captures even when the "visible" content is identical. Two captures of the same idle screen may produce different MD5 hashes due to cursor blink sequences or timestamp updates in the terminal.

**Expected**: Strip ANSI escape codes (the dashboard already has `_ANSI_RE` regex for this) and normalize whitespace before hashing. The `fleet_health_check.py` already strips ANSI -- the watchdog should reuse that approach.

**Impact**: False-positive "content changed" detections, making the watchdog think a stuck worker is live.

---

### CDX-3: Subprocess Calls Without `shell=False` Safety (Severity: MEDIUM)

**Issue**: All subprocess calls use `subprocess.run(["tmux", ...])` which is safe (list form, no shell). However, in `_execute_tier2`, the restart command is sent via `send-keys` as a string:

```python
self._tmux_send_keys(panel_id, restart_cmd, enter=True)
```

Where `restart_cmd` could be `'codex -a never --no-alt-screen "Resume previous task"'`. The `send-keys` call is: `["tmux", "send-keys", "-t", panel_id, restart_cmd, "Enter"]`. This is safe from injection since it is list-form. However, the *content* of `restart_cmd` is a command that gets typed into a shell running inside the pane. If the `_RESTART_COMMANDS` dict ever gets populated from external config or user input, this becomes a command injection vector.

**Expected**: Validate restart commands against a whitelist, or at minimum document that `_RESTART_COMMANDS` values must be trusted literals.

**Impact**: Low today (hardcoded dict), but a latent injection vector if config loading is added later.

---

### CDX-4: Resource Leak -- Unbounded WorkerHistory Growth (Severity: MEDIUM)

**Issue**: Both `Detector._histories` and `Strategy._histories` grow unboundedly. If workers are dynamically spawned and destroyed (which happens in cmux-win fleet), entries for defunct panels are never cleaned up.

**Expected**: Prune histories for panels that no longer exist. In `scan_all()`, after listing current panels, remove history entries for panels not in the current list. Or use a TTL-based eviction (e.g., remove entries not accessed in 30 minutes).

**Impact**: Memory leak proportional to the number of unique panel IDs seen over the watchdog's lifetime. In practice this is small (maybe dozens of entries), but it violates clean resource management.

---

### CDX-5: `time.sleep()` in Executor Blocks the Entire Watchdog (Severity: MEDIUM)

**Issue**: `_execute_tier2` has `sleep(1.0) + sleep(2.0) + sleep(1.0) + sleep(3.0) = 7 seconds` of blocking sleep. During this time, the entire watchdog is blocked -- no other workers can be scanned or recovered. If three workers need Tier 2 recovery simultaneously, the total block is 21 seconds.

**Expected**: Either (a) execute recovery actions asynchronously (threading or asyncio), or (b) move the verification step to the next scan cycle instead of sleeping in-line, or (c) at minimum document this limitation and keep sleep times short.

**Impact**: During multi-worker recovery, the watchdog is unresponsive. A new worker crash during recovery execution would not be detected until the sleep chain completes.

---

### CDX-6: No Lock File / Singleton Guard for the Watchdog Process (Severity: MEDIUM)

**Issue**: Nothing prevents two watchdog instances from running simultaneously. If a user runs `python -m javis.watchdog start` twice, both instances will scan, detect, and attempt recovery on the same workers simultaneously. This could send Ctrl+C to a worker that was just successfully recovered by the other instance.

**Expected**: Use a PID file or filesystem lock (`fcntl.flock` on Unix, `msvcrt.locking` on Windows, or a cross-platform `lockfile` approach using a .lock file with the PID inside).

**Impact**: Duplicate recovery actions, potential for conflicting commands sent to the same pane.

---

### CDX-7: `_classify` Returns LIVE for Empty Content Change (Severity: LOW)

**Issue**: In the classify method:
```python
if content_changed:
    if self._matches_any(screen, self._LIVE_PATTERNS):
        return WorkerStatus.LIVE
    return WorkerStatus.LIVE  # Content changed = alive
```

Both branches return LIVE. The pattern check is redundant. More importantly, a screen that changed from "empty" to "slightly different empty" (e.g., a blank line added) would be classified as LIVE.

**Expected**: If content changed but screen is effectively empty or only contains whitespace/ANSI codes, classify as UNKNOWN rather than LIVE.

**Impact**: Misleading status. A nearly-dead worker that produces occasional blank output would be marked LIVE.

---

### CDX-8: Signal Handling on Windows (Severity: LOW)

**Issue**: The orchestrator registers handlers for SIGINT and SIGTERM. On Windows, SIGTERM is not naturally generated (there is no `kill -15` equivalent in standard Windows tooling). The `signal.signal(signal.SIGTERM, ...)` call works but is only triggered if the process receives the signal programmatically. The `cli.py` "stop" command just prints a message telling the user to send SIGTERM, which is unhelpful on Windows.

**Expected**: On Windows, implement stop via a file-based sentinel (e.g., write a `watchdog.stop` file that the main loop checks) or use a named mutex.

**Impact**: No clean way to stop the watchdog on Windows other than Ctrl+C in the terminal or killing the process.

---

### CDX-9: Audit Log Rotation Not Addressed (Severity: LOW)

**Issue**: The JSONL audit log is append-only with no rotation. Over weeks of operation, this file will grow indefinitely.

**Expected**: Implement basic rotation (e.g., daily files like `audit_20260617.jsonl`, or max-size rotation), or at minimum document that external log rotation should be configured.

**Impact**: Disk space consumption over long-running deployments. Not critical for a development tool, but poor practice.

---

### CDX-10: Test Isolation -- Detector Tests Need subprocess Mock Discipline (Severity: LOW)

**Issue**: The design says "mock subprocess.run to simulate tmux output" but does not specify *how*. If tests use `monkeypatch` on the module-level `subprocess` import, other tests in the same process might be affected. If tests use `unittest.mock.patch` with the wrong target string, they will silently not patch.

**Expected**: Specify the exact mock targets:
- `javis.watchdog.detector.subprocess.run` (not `subprocess.run`)
- Use `pytest.fixture` with `autouse=False` so each test opts in explicitly.

**Impact**: Flaky tests that pass in isolation but fail in CI when test order changes.

---

## Summary of All Issues

| ID | Severity | Category | Issue |
|----|----------|----------|-------|
| AGY-1 | HIGH | Logic | idle_timeout > stuck_timeout inversion -- IDLE state unreachable |
| AGY-2 | HIGH | Strategy | No "legitimately thinking" detection -- false-positive STUCK |
| CDX-1 | HIGH | Logic | idle_seconds always 0 on first no-change scan |
| AGY-3 | MEDIUM | UX | Tier3 escalation echo goes to Claude CLI, not human |
| AGY-4 | MEDIUM | Strategy | No exponential backoff between recovery attempts |
| AGY-5 | MEDIUM | Config | CSO panel not in default exclusion list |
| CDX-2 | MEDIUM | Detection | ANSI codes in screen capture corrupt hash comparison |
| CDX-3 | MEDIUM | Security | Restart commands not validated -- latent injection vector |
| CDX-4 | MEDIUM | Resources | WorkerHistory dicts grow unboundedly |
| CDX-5 | MEDIUM | Performance | sleep() in executor blocks entire watchdog |
| CDX-6 | MEDIUM | Safety | No singleton guard -- multiple instances can conflict |
| AGY-6 | LOW | UX | No "paused worker" concept for intentional inactivity |
| AGY-7 | LOW | Maintenance | WorkerHistory split across Detector and Strategy |
| CDX-7 | LOW | Logic | classify() returns LIVE for trivial content changes |
| CDX-8 | LOW | Platform | SIGTERM stop mechanism does not work on Windows |
| CDX-9 | LOW | Ops | No audit log rotation |
| CDX-10 | LOW | Testing | Test mock targets not specified |
