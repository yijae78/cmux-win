# Javis Fleet Auto-Recovery Watchdog -- Architecture Design v1

> **Purpose**: Automatically monitor cmux-win fleet workers, detect stuck/dead states, and recover them via a 3-tier escalation strategy.
> **Date**: 2026-06-17
> **Author**: Phase 1 Design Agent
> **Target**: Python 3.10+, stdlib only (no external deps except pytest for tests)
> **Platform**: Windows 11 + Git Bash tmux shim (cmux-win)

---

## 1. System Overview

### 1.1 Architecture Diagram

```
+=====================================================================+
|                        orchestrator.py                               |
|                   (Main Loop: configurable interval)                 |
|                                                                      |
|  +-------------+     +-------------+     +-------------+            |
|  |  detector   |---->|  strategy   |---->|  executor   |            |
|  |    .py      |     |    .py      |     |    .py      |            |
|  +------+------+     +------+------+     +------+------+            |
|         |                   |                   |                    |
|         v                   v                   v                    |
|   tmux capture       RecoveryPlan         tmux send-keys            |
|   -pane -t %N        3-tier logic         Socket API                |
|                                                                      |
|  +-------------+     +-------------+     +-------------+            |
|  |  models.py  |     |  config.py  |     |   cli.py    |            |
|  +-------------+     +-------------+     +-------------+            |
+=====================================================================+
```

### 1.2 Data Flow

```
[tmux capture-pane -t %N -p -S -50] --> Detector.scan_all()
        |
        v
  list[WorkerState]   (LIVE / IDLE / STUCK / DEAD / UNKNOWN)
        |
        v
  Strategy.decide(states) --> list[RecoveryAction]
        |
        v
  Executor.execute(action) --> WatchdogEvent
        |
        v
  Orchestrator: log event to JSONL, update strategy history, emit to dashboard
```

### 1.3 Worker Status State Machine

```
                  +----------+
        +-------->| UNKNOWN  |<--------+
        |         +----+-----+         |
        |              |               |
        |   first scan |               | capture fails
        |              v               |
        |         +----+-----+         |
        +---------|   LIVE   |---------+
        |         +----+-----+
        |              |
        |  no output   | output detected
        |  change      |
        |              v
        |         +----+-----+
        |         |   IDLE   |
        |         +----+-----+
        |              |
        |  idle_timeout| exceeded
        |              v
        |         +----+-----+
        +---------|  STUCK   |
        |         +----+-----+
        |              |
        |  process     | recovery succeeds
        |  exits       |
        |              v
        |         +----+-----+           +------------+
        +-------->|   DEAD   |---------->| ESCALATED  |
                  +----------+           | (terminal) |
                                         +------------+
```

**Transitions**:
- `UNKNOWN -> LIVE`: First scan detects output changes
- `LIVE -> IDLE`: No output change for `idle_timeout` seconds
- `IDLE -> STUCK`: No output change for `stuck_timeout` seconds after IDLE
- `STUCK -> LIVE`: Tier1 recovery succeeds (Ctrl+C unsticks worker)
- `STUCK -> DEAD`: Process exits during stuck state
- `DEAD -> LIVE`: Tier2 recovery succeeds (restart)
- `DEAD -> ESCALATED`: All retries exhausted, master notified
- `ANY -> UNKNOWN`: Screen capture fails (tmux error)

---

## 2. Module Specifications

### 2.1 `models.py` -- Data Models

Already implemented in the codebase. Key types:

```python
class WorkerStatus(Enum):
    LIVE = "live"       # Active output changes detected
    IDLE = "idle"       # No output change within idle_timeout
    STUCK = "stuck"     # No output change beyond stuck_timeout
    DEAD = "dead"       # Process exited or pane gone
    UNKNOWN = "unknown" # Cannot determine status

class RecoveryTier(Enum):
    TIER1_INTERRUPT = 1  # Ctrl+C to interrupt
    TIER2_RESTART = 2    # Kill + relaunch CLI
    TIER3_ESCALATE = 3   # Notify master pane

class ActionResult(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"

@dataclass
class WorkerState:
    panel_id: str                    # e.g. "%1"
    label: str                       # e.g. "Worker1(Claude)"
    status: WorkerStatus
    last_output_hash: str = ""       # MD5 of last screen capture
    last_change_at: datetime         # When output last changed
    idle_seconds: float = 0.0        # Seconds since last change
    process_alive: bool = True       # Whether CLI process is running
    retry_count: int = 0             # Current recovery attempt count
    screen_snippet: str = ""         # Last 5 lines for diagnostics

@dataclass
class WorkerHistory:
    panel_id: str
    label: str
    consecutive_stuck: int = 0
    consecutive_dead: int = 0
    total_recoveries: int = 0
    last_recovery_at: datetime | None = None
    tier1_count: int = 0
    tier2_count: int = 0
    previous_hashes: list[str] = field(default_factory=list)

@dataclass
class RecoveryAction:
    panel_id: str
    label: str
    tier: RecoveryTier
    reason: str
    current_state: WorkerState

@dataclass
class WatchdogEvent:
    timestamp: datetime
    panel_id: str
    label: str
    action_tier: RecoveryTier
    result: ActionResult
    detail: str = ""
    duration_ms: float = 0.0
```

### 2.2 `config.py` -- Configuration

```python
@dataclass
class WatchdogConfig:
    scan_interval: float = 10.0          # Seconds between scans
    idle_timeout: float = 300.0          # Seconds before IDLE status
    stuck_timeout: float = 120.0         # Seconds before STUCK status
    dead_check_interval: float = 30.0    # Seconds between liveness checks
    max_tier1_retries: int = 3           # Max Ctrl+C before escalating
    max_tier2_retries: int = 2           # Max restarts before escalating
    recovery_cooldown: float = 60.0      # Min seconds between actions/worker
    hash_window_size: int = 10           # Rolling hash buffer size
    screen_capture_lines: int = 50       # Lines to capture per scan
    excluded_panels: list[str] | None = None  # Panels to skip

    def __post_init__(self) -> None:
        if self.excluded_panels is None:
            self.excluded_panels = ["Master", "Dashboard"]

    @classmethod
    def from_dict(cls, data: dict) -> WatchdogConfig:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known})
```

### 2.3 `detector.py` -- Worker Status Detection

**Responsibility**: Capture screen content from each worker pane via tmux and classify health status.

**Key Interface**:
```python
class Detector:
    def __init__(self, config: WatchdogConfig) -> None: ...
    def scan_all(self) -> list[WorkerState]: ...
    def _list_panels(self) -> list[tuple[str, str]]: ...
    def _scan_one(self, panel_id: str, label: str) -> WorkerState: ...
    def _capture_screen(self, panel_id: str) -> str: ...
    def _classify(self, screen: str, content_changed: bool, idle_seconds: float) -> WorkerStatus: ...
    def _get_history(self, panel_id: str, label: str) -> WorkerHistory: ...
    def _update_hash_history(self, history: WorkerHistory, screen_hash: str) -> bool: ...
    @staticmethod
    def _matches_any(text: str, patterns: list[str]) -> bool: ...
```

**Detection Patterns**:
- LIVE patterns: spinner chars, "writing", "Reading", "Searching", progress bars, "Edit(", "Bash("
- IDLE patterns: shell prompts ("$ ", "> "), "waiting for input", "What would you like"
- DEAD patterns: "Traceback", "Error: process exited", "Segmentation fault", "Killed"

**Classification Priority**: DEAD > STUCK > LIVE > IDLE > UNKNOWN

**Hash-based Change Detection**:
- Each scan computes MD5 of captured screen content
- Rolling window of last N hashes stored in WorkerHistory
- Content changed = current hash differs from previous hash
- If content unchanged for `stuck_timeout` seconds -> STUCK

### 2.4 `strategy.py` -- Recovery Decision Engine

**Responsibility**: Given a list of WorkerStates, decide which recovery actions to take.

**Key Interface**:
```python
class Strategy:
    def __init__(self, config: WatchdogConfig) -> None: ...
    def decide(self, states: list[WorkerState]) -> list[RecoveryAction]: ...
    def record_action(self, panel_id: str) -> None: ...
```

**Recovery Decision Tree**:

```
Worker status?
  |
  +-- LIVE or IDLE --> No action (reset retry counts)
  |
  +-- UNKNOWN --> No action (wait for more data)
  |
  +-- STUCK:
  |     |
  |     +-- Cooldown elapsed?
  |     |     |
  |     |     +-- No --> Skip (too soon)
  |     |     |
  |     |     +-- Yes:
  |     |           |
  |     |           +-- tier1_count < max_tier1_retries?
  |     |           |     +-- Yes --> TIER1_INTERRUPT (Ctrl+C)
  |     |           |     +-- No:
  |     |           |           +-- tier2_count < max_tier2_retries?
  |     |           |                 +-- Yes --> TIER2_RESTART
  |     |           |                 +-- No  --> TIER3_ESCALATE
  |
  +-- DEAD:
        |
        +-- Cooldown elapsed?
              |
              +-- No --> Skip
              |
              +-- Yes:
                    +-- tier2_count < max_tier2_retries?
                          +-- Yes --> TIER2_RESTART (skip Tier1 -- no process to interrupt)
                          +-- No  --> TIER3_ESCALATE
```

**Cooldown Mechanism**: Minimum `recovery_cooldown` seconds between consecutive actions on the same worker. Prevents rapid-fire recovery attempts.

**History Reset**: When a worker returns to LIVE or IDLE, all retry counters reset to zero.

### 2.5 `executor.py` -- Recovery Executor

**Responsibility**: Execute recovery actions using tmux commands and cmux-win Socket API.

**Key Interface**:
```python
class Executor:
    def execute(self, action: RecoveryAction) -> WatchdogEvent: ...
```

**Tier 1 Execution (Interrupt)**:
```
1. tmux send-keys -t %N C-c
2. sleep 0.5s
3. tmux send-keys -t %N C-c (double Ctrl+C for safety)
4. sleep 2s
5. Verify: capture screen, check for output
```

**Tier 2 Execution (Restart)**:
```
1. tmux send-keys -t %N C-c (x2, graceful shutdown)
2. sleep 2s
3. tmux send-keys -t %N "exit" Enter
4. sleep 1s
5. Detect worker type from label:
   - "Claude" in label --> "claude --dangerously-skip-permissions"
   - "AGY" in label    --> "agy"
   - "Codex" in label  --> "codex -a never --no-alt-screen"
6. tmux send-keys -t %N "<restart_cmd>" Enter
7. sleep 3s
8. Verify: capture screen, check for CLI startup
```

**Tier 3 Execution (Escalate)**:
```
1. Send echo message to Master pane (%0):
   tmux send-keys -t %0 "echo '[WATCHDOG ALERT] Worker2(AGY) (%2) unrecoverable: ...'" Enter
2. IMPORTANT: Never send slash commands (shell interprets as paths in Git Bash)
```

**Worker Type Detection**:
```python
_RESTART_COMMANDS = {
    "Claude": "claude --dangerously-skip-permissions",
    "AGY": "agy",
    "Codex": 'codex -a never --no-alt-screen',
}
```

### 2.6 `orchestrator.py` -- Main Loop

**Responsibility**: Coordinate detector, strategy, and executor in a continuous loop. Manage audit logging and signal handling.

**Key Interface**:
```python
class Orchestrator:
    def __init__(self, config: WatchdogConfig | None = None,
                 audit_log_path: Path | None = None) -> None: ...
    def start(self) -> None: ...     # Blocking main loop
    def stop(self) -> None: ...      # Set flag to exit loop
    def get_status(self) -> dict[str, Any]: ...  # Status snapshot
```

**Main Loop Cycle**:
```
while running:
    1. states = detector.scan_all()
    2. actions = strategy.decide(states)
    3. for action in actions:
        a. event = executor.execute(action)
        b. strategy.record_action(action.panel_id)
        c. write_audit(event)
        d. log event
    4. sleep(scan_interval)
```

**Signal Handling**: SIGINT and SIGTERM trigger graceful shutdown via `stop()`.

**Audit Log**: JSONL format, each line:
```json
{
  "timestamp": "2026-06-17T14:30:00",
  "panel_id": "%2",
  "label": "Worker2(AGY)",
  "tier": 1,
  "result": "success",
  "detail": "Ctrl+C sent, screen shows output",
  "duration_ms": 2540.3
}
```

### 2.7 `cli.py` -- CLI Interface

**Usage**:
```bash
python -m javis.watchdog start [--config config.json] [--audit-log path.jsonl]
python -m javis.watchdog status
python -m javis.watchdog stop   # prints hint to send SIGTERM
```

**Key Interface**:
```python
def main(argv: list[str] | None = None) -> int: ...
```

---

## 3. Interface Contracts

### 3.1 Module Dependency Graph

```
models.py  <--  config.py
    ^              ^
    |              |
    +----+---------+------+
         |         |      |
     detector.py  strategy.py  executor.py
         ^         ^      ^
         |         |      |
         +---------+------+
                |
         orchestrator.py
                ^
                |
             cli.py
```

**Rule**: All imports flow upward. No circular dependencies. No module imports from a module below it in the graph.

### 3.2 Function Signature Summary

| Module | Method | Input | Output |
|--------|--------|-------|--------|
| `Detector` | `scan_all()` | -- | `list[WorkerState]` |
| `Detector` | `_scan_one(panel_id, label)` | `str, str` | `WorkerState` |
| `Detector` | `_capture_screen(panel_id)` | `str` | `str` |
| `Detector` | `_classify(screen, changed, idle_s)` | `str, bool, float` | `WorkerStatus` |
| `Strategy` | `decide(states)` | `list[WorkerState]` | `list[RecoveryAction]` |
| `Strategy` | `record_action(panel_id)` | `str` | `None` |
| `Executor` | `execute(action)` | `RecoveryAction` | `WatchdogEvent` |
| `Orchestrator` | `start()` | -- | `None` (blocks) |
| `Orchestrator` | `stop()` | -- | `None` |
| `Orchestrator` | `get_status()` | -- | `dict[str, Any]` |
| `cli` | `main(argv)` | `list[str] | None` | `int` |

---

## 4. Error Handling Strategy

### 4.1 Fault Isolation

Each module handles its own errors and never propagates exceptions upward unless fatal:

| Component | Error Source | Handling |
|-----------|-------------|----------|
| `Detector._capture_screen` | subprocess timeout, tmux not found | Return empty string, classify as UNKNOWN |
| `Detector._list_panels` | tmux command fails | Return empty list (no workers scanned) |
| `Strategy.decide` | Internal logic error | Catch-all in orchestrator, log, continue |
| `Executor._tmux_send_keys` | subprocess timeout | Return FAILED ActionResult |
| `Executor._execute_tier2` | Unknown worker type | Return FAILED with detail message |
| `Orchestrator._run_cycle` | Any exception | Log error, continue to next cycle |
| `Orchestrator._write_audit` | File I/O error | Log warning, continue (non-fatal) |

### 4.2 Graceful Degradation

- If tmux is unavailable: Detector returns empty list, orchestrator idles harmlessly
- If a single worker scan fails: Other workers still scanned
- If audit log is unwritable: Events still logged to Python logger
- If master panel unreachable for Tier3: Event logged as FAILED, no crash

### 4.3 Never Crash Principles

1. All subprocess calls have timeouts (5s default)
2. All file I/O wrapped in try/except
3. Main loop catches all exceptions per cycle
4. Signal handlers set flag rather than raising

---

## 5. Test Strategy

### 5.1 `tests/conftest.py` -- Common Fixtures

```python
@pytest.fixture
def config() -> WatchdogConfig:
    """Fast config for tests."""
    return WatchdogConfig(
        scan_interval=1.0, idle_timeout=5.0, stuck_timeout=3.0,
        max_tier1_retries=2, max_tier2_retries=1, recovery_cooldown=1.0,
    )

@pytest.fixture
def live_worker() -> WorkerState: ...
@pytest.fixture
def stuck_worker() -> WorkerState: ...
@pytest.fixture
def dead_worker() -> WorkerState: ...
```

### 5.2 Test Matrix

| File | Tests | Approach |
|------|-------|----------|
| `test_detector.py` | Pattern matching accuracy, status classification, hash change detection, history updates, excluded panel filtering | Mock `subprocess.run` to simulate tmux output |
| `test_strategy.py` | 3-tier escalation order, cooldown enforcement, DEAD->Tier2 skip, LIVE/IDLE history reset, edge: rapid state flapping | Pure logic tests against WorkerState inputs |
| `test_executor.py` | tmux command construction, worker type detection, Tier 1/2/3 execution sequences, error paths | Mock `subprocess.run`, verify call args |
| `test_orchestrator.py` | Full detect->decide->execute pipeline, audit log writes, graceful shutdown, cycle counting | Mock all three sub-modules |

---

## 6. Design Principles

1. **Single Responsibility**: Each module owns one concern (detect / decide / execute).
2. **Unidirectional Dependencies**: models <- config <- detector/strategy/executor <- orchestrator <- cli.
3. **No Circular Imports**: Enforced by the dependency graph.
4. **Stdlib Only**: No external packages (except pytest for tests).
5. **Testability**: All external I/O (subprocess, file) mockable at module boundaries.
6. **50-Line Limit**: Every function body fits within 50 lines.
7. **Audit Trail**: Every recovery action recorded in append-only JSONL.
8. **Graceful Degradation**: Never crash the watchdog itself; degrade to idle if subsystems fail.
9. **Windows Compatibility**: Uses tmux shim provided by cmux-win; no Unix-specific syscalls.

---

## 7. File Structure

```
javis/watchdog/
+-- __init__.py          # Package: from .orchestrator import Orchestrator
+-- __main__.py          # Entry: from .cli import main; main()
+-- config.py            # WatchdogConfig dataclass
+-- models.py            # WorkerState, RecoveryAction, WatchdogEvent, enums
+-- detector.py          # Detector: tmux capture -> status classification
+-- strategy.py          # Strategy: 3-tier escalation decision
+-- executor.py          # Executor: tmux send-keys / restart / escalate
+-- orchestrator.py      # Orchestrator: main loop + audit log
+-- cli.py               # CLI: start / status / stop
+-- tests/
    +-- __init__.py
    +-- conftest.py      # Shared fixtures
    +-- test_detector.py
    +-- test_strategy.py
    +-- test_executor.py
    +-- test_orchestrator.py
```
