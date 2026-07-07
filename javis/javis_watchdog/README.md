# Javis Fleet Auto-Recovery Watchdog

The **Javis Fleet Auto-Recovery Watchdog** is a lightweight, robust, and zero-dependency monitoring tool designed to oversee active workers in the `cmux-win` workspace. It automatically detects stalled (stuck) or crashed (dead) AI CLI agents (e.g., Claude, Gemini, Codex) and performs a 3-tier escalation recovery process.

---

## 1. System Architecture & Flow

The watchdog follows a strict **unidirectional dependency pipeline** to ensure reliability and testability:

```
+=====================================================================+
|                        Orchestrator Loop                             |
|                   (Main Loop: configurable interval)                 |
|                                                                      |
|  +-------------+     +-------------+     +-------------+            |
|  |  Detector   |---->|  Strategy   |---->|  Executor   |            |
|  |    (Scan)   |     |  (Decide)   |     |  (Recover)  |            |
|  +------+------+     +------+------+     +------+------+            |
|         |                   |                   |                    |
|         v                   v                   v                    |
|   tmux capture       RecoveryPlan         tmux send-keys            |
|   (ANSI-stripped)    3-tier + backoff     alerts.jsonl               |
|                                                                      |
|  +-------------+     +-------------+     +-------------+            |
|  |   Models    |     |   Config    |     |     CLI     |            |
|  +-------------+     +-------------+     +-------------+            |
+=====================================================================+
```

### 1.1 Data Flow Sequence

1. **Orchestrator** wakes up at configured `scan_interval` (default: 10s).
2. **Detector** fetches active tmux panels, captures screen contents via `tmux capture-pane`, strips ANSI escape sequences, computes MD5 hashes, and identifies active AI thinking patterns (e.g., spinning indicators).
3. **Strategy** evaluates historical changes and timing against config thresholds. If a worker goes over the timeout limits without screen changes, it determines the required recovery action tier.
4. **Executor** processes the chosen recovery action:
   - **Tier 1 (Ctrl+C)**: Sends double interrupt signals to the stuck tmux panel.
   - **Tier 2 (Restart)**: Kills the defunct shell and restarts the specific worker CLI.
   - **Tier 3 (Escalate)**: Writes a critical alert entry to a shared JSONL file (`alerts.jsonl`) for dashboard display.
5. **Orchestrator** appends the watchdog event to a date-stamped audit log (`audit_YYYYMMDD.jsonl`), updates strategy action tracking (linear backoff), and purges stale state tracking.

---

## 2. Worker Status State Machine

Workers are classified into one of the following statuses during each cycle:

```
                  +----------+
        +-------->| UNKNOWN  |<--------+
        |         +----+-----+         |
        |              |               |
        |   first scan |               | capture fails / empty screen
        |              v               |
        |         +----+-----+         |
        +---------|   LIVE   |---------+
        |         +----+-----+
        |              |
        |  no change   | active thinking pattern = remain LIVE
        |  >= 60s      |
        |              v
        |         +----+-----+
        |         |   IDLE   |
        |         +----+-----+
        |              |
        |  no change   |
        |  >= 180s     |
        |              v
        |         +----+-----+
        |         |  STUCK   | ----> Tier 1 (Ctrl+C x2) (up to 3x)
        |         +----+-----+       if success -> LIVE
        |              |
        |  shell exits | Tier 1 exhausted
        |              v
        |         +----+-----+
        +-------->|   DEAD   | ----> Tier 2 (Restart shell) (up to 2x)
                  +----+-----+       if success -> LIVE
                       |
                       | Tier 2 exhausted
                       v
                  +----+-----+
                  | ESCALATED| ----> Tier 3: write to alerts.jsonl
                  | (critical|
                  +----------+
```

---

## 3. Configuration Properties

The watchdog is configured via `WatchdogConfig` (in `config.py`), which loads defaults that can be overridden by a JSON configuration file.

| Field Name | Type | Default | Description |
|------------|------|---------|-------------|
| `scan_interval` | `float` | `10.0` | Polling frequency in seconds. |
| `idle_timeout` | `float` | `60.0` | Timeout threshold to transition LIVE -> IDLE. |
| `stuck_timeout` | `float` | `180.0` | Timeout threshold to transition IDLE -> STUCK. |
| `dead_check_interval`| `float` | `30.0` | Unused in basic loops (general interval helper). |
| `max_tier1_retries` | `int` | `3` | Maximum Ctrl+C interrupts before escalating to restart. |
| `max_tier2_retries` | `int` | `2` | Maximum restarts before escalating to human attention. |
| `recovery_cooldown` | `float` | `60.0` | Base cooldown in seconds between recovery attempts. |
| `max_cooldown` | `float` | `300.0` | Maximum capped backoff cooldown. |
| `hash_window_size` | `int` | `10` | Size of the rolling hash history window. |
| `screen_capture_lines`| `int` | `50` | Number of screen buffer lines captured. |
| `excluded_panels` | `list[str]`| `["Master", "Dashboard", "CSO"]` | Panel labels excluded from monitoring. |
| `alert_file` | `str` | `"javis/watchdog/alerts.jsonl"` | File path where Tier 3 alerts are written. |
| `pid_file` | `str` | `"javis/watchdog/watchdog.pid"` | File path representing the daemon PID lock. |
| `stop_file` | `str` | `"javis/watchdog/watchdog.stop"` | File path used as a stop sentinel for the daemon. |
| `audit_retention_days`| `int` | `7` | Retention limit for date-stamped audit logs. |

---

## 4. Installation & CLI Usage

Run the watchdog from the project root using standard Python command execution.

### Start the Watchdog

Starts the watchdog in the current foreground shell. It will run continuously until stopped.

```bash
python -m javis.watchdog start [--config path/to/config.json] [--audit-dir path/to/audit]
```

### Stop the Watchdog

Gracefully stops a running watchdog daemon by creating a file-based sentinel (`watchdog.stop`). The orchestrator polls for this file and shuts down.

```bash
python -m javis.watchdog stop
```

### Check Fleet Status

Shows a JSON snapshot of the monitored workers and their health metrics.

```bash
python -m javis.watchdog status
```

---

## 5. Directory Structure

The module structure under `javis/watchdog/` consists of:

```
javis/watchdog/
├── __init__.py          # Exposes Orchestrator class
├── __main__.py          # Calls cli.main()
├── cli.py               # Handles start/status/stop CLI options
├── config.py            # Holds WatchdogConfig properties
├── models.py            # Dataclasses (WorkerState, WorkerHistory, etc.)
├── detector.py          # Captures screen and classifies status
├── strategy.py          # Escalation decider with backoff cooldown
├── executor.py          # Executes tmux interventions & alerts
├── orchestrator.py      # Daemon run loop, PID guard, log retention
└── tests/               # Unit test suites (conftest, test_config, etc.)
```

---

## 6. Development & Verification

### Running Tests

To verify the watchdog components and CLI logic, run the test suite with pytest from the project root:

```bash
pytest javis/watchdog/tests
```

All functions adhere to a maximum **50-line size limit** and utilize standard libraries only, ensuring full compatibility with Windows environments and the `cmux-win` Git Bash terminal environment.
