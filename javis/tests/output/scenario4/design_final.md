# Javis Fleet Auto-Recovery Watchdog -- Final Consensus Design

> **Purpose**: Automatically monitor cmux-win fleet workers, detect stuck/dead states, and recover them via a 3-tier escalation strategy.
> **Date**: 2026-06-17
> **Status**: FINAL -- approved after AGY + Codex critique resolution
> **Target**: Python 3.10+, stdlib only (no external deps except pytest)
> **Platform**: Windows 11 + Git Bash tmux shim (cmux-win)

---

## 0. Critique Resolution Summary

### Accepted (with changes applied)

| ID | Severity | Resolution |
|----|----------|------------|
| AGY-1 | HIGH | **ACCEPTED.** Swapped defaults: `idle_timeout=60.0`, `stuck_timeout=180.0`. Now the progression is LIVE -> IDLE (60s) -> STUCK (180s). Classification logic updated to check idle_timeout first, then stuck_timeout. |
| AGY-2 | HIGH | **ACCEPTED.** Added `_THINKING_PATTERNS` list derived from dashboard's `detect_status()`. If a thinking pattern is detected, the worker is classified LIVE regardless of hash changes. |
| CDX-1 | HIGH | **ACCEPTED.** Added `last_output_change_at: datetime` to `WorkerHistory`. Updated `_scan_one` to compute `idle_seconds = (now - history.last_output_change_at).total_seconds()` correctly. |
| AGY-3 | MEDIUM | **ACCEPTED.** Tier 3 escalation now writes to a shared alert file `javis/watchdog/alerts.jsonl` that the dashboard can read. Also writes to Python logger at CRITICAL level. No more echo to master pane. |
| AGY-5 | MEDIUM | **ACCEPTED.** Default exclusion list expanded to `["Master", "Dashboard", "CSO"]`. |
| CDX-2 | MEDIUM | **ACCEPTED.** Added `_strip_ansi(text)` function (reusing dashboard's regex pattern) applied before hashing. |
| CDX-4 | MEDIUM | **ACCEPTED.** Added `_prune_stale_histories()` called at the start of each `scan_all()`. Removes entries for panels not in the current panel list. |
| CDX-6 | MEDIUM | **ACCEPTED.** Added PID file mechanism: write PID to `javis/watchdog/watchdog.pid` on start, check on startup, remove on shutdown. Cross-platform (no fcntl needed). |
| CDX-7 | LOW | **ACCEPTED.** If content changed but stripped screen is effectively empty (<10 non-whitespace chars), classify as UNKNOWN instead of LIVE. |
| CDX-8 | LOW | **ACCEPTED.** Added file-based stop sentinel: main loop checks for `javis/watchdog/watchdog.stop` file each cycle. CLI "stop" command creates this file. |
| CDX-9 | LOW | **ACCEPTED.** Audit log uses date-stamped filenames: `audit_YYYYMMDD.jsonl`. Files older than 7 days are auto-deleted at startup. |
| CDX-10 | LOW | **ACCEPTED.** Test strategy section now specifies exact mock targets. |

### Partially Accepted

| ID | Severity | Resolution |
|----|----------|------------|
| AGY-4 | MEDIUM | **PARTIALLY ACCEPTED.** Added linear backoff: cooldown doubles after each failed attempt on the same worker (60 -> 120 -> 240, capped at 300s). Rejected exponential backoff as overkill for a system with max 5 workers. |
| CDX-5 | MEDIUM | **PARTIALLY ACCEPTED.** Reduced sleep times (Tier2 total from 7s to 4s). Full async rejected as over-engineering for 5 workers. Added documentation note about blocking behavior. Verification moved to next scan cycle instead of inline sleep+check. |
| AGY-7 | LOW | **PARTIALLY ACCEPTED.** Renamed Strategy's tracking dict to `_action_tracker` (holds cooldown + tier counts) and kept Detector's `_histories` for hash tracking. Now the names are distinct and purposes clear. Rejected single shared store as it would break module independence. |

### Rejected (with counter-arguments)

| ID | Severity | Reason |
|----|----------|--------|
| AGY-6 | LOW | **REJECTED.** The exclusion list already handles this. Adding a "paused" concept introduces state that must be synchronized across master, watchdog, and dashboard -- complexity not justified for v1. Workers that should be idle can be added to `excluded_panels` dynamically via config reload. |
| CDX-3 | MEDIUM | **REJECTED (as-is).** The restart commands dict is hardcoded and never loaded from external input. Added a code comment documenting that values must be trusted literals. The validation whitelist adds complexity with no current attack surface. Will revisit if config file loading is added. |

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
|   (ANSI-stripped)    3-tier + backoff     alerts.jsonl               |
|                                                                      |
|  +-------------+     +-------------+     +-------------+            |
|  |  models.py  |     |  config.py  |     |   cli.py    |            |
|  +-------------+     +-------------+     +-------------+            |
+=====================================================================+
```

### 1.2 Data Flow

```
[tmux capture-pane -t %N -p -S -50]
        |
        v
  _strip_ansi() --> MD5 hash --> Detector.scan_all()
        |
        v
  list[WorkerState]   (LIVE / IDLE / STUCK / DEAD / UNKNOWN)
        |
        v
  Strategy.decide(states) --> list[RecoveryAction]
        |                     (with linear backoff cooldown)
        v
  Executor.execute(action) --> WatchdogEvent
        |
        v
  Orchestrator:
    - append to audit_YYYYMMDD.jsonl
    - update strategy action tracker
    - for Tier3: append to alerts.jsonl (dashboard reads this)
```

### 1.3 Worker Status State Machine (REVISED)

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
        |  no change   | thinking pattern = stay LIVE
        |  60s         |
        |              v
        |         +----+-----+
        |         |   IDLE   |
        |         +----+-----+
        |              |
        |  no change   |
        |  180s total  |
        |              v
        |         +----+-----+
        +---------|  STUCK   |      Tier1 (Ctrl+C) x3
        |         +----+-----+ ---> if success --> LIVE
        |              |
        |  process     |  Tier1 exhausted
        |  exits       v
        |         +----+-----+
        +-------->|   DEAD   |      Tier2 (restart) x2
                  +----+-----+ ---> if success --> LIVE
                       |
                       |  Tier2 exhausted
                       v
                  +----+-----+
                  | ESCALATED|      Tier3: write to alerts.jsonl
                  | (terminal)|
                  +----------+
```

**Key Change from v1**: LIVE -> IDLE at 60s, IDLE -> STUCK at 180s (was inverted in v1). Thinking patterns keep worker in LIVE regardless of hash changes.

---

## 2. Module Specifications

### 2.1 `models.py` -- Data Models (DELTA from v1)

**Changes**:
- Added `last_output_change_at` to `WorkerHistory` (CDX-1 fix)
- Added `ActionResult.TIMEOUT` variant for clearer timeout reporting

```python
class WorkerStatus(Enum):
    LIVE = "live"
    IDLE = "idle"
    STUCK = "stuck"
    DEAD = "dead"
    UNKNOWN = "unknown"

class RecoveryTier(Enum):
    TIER1_INTERRUPT = 1
    TIER2_RESTART = 2
    TIER3_ESCALATE = 3

class ActionResult(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"       # NEW: subprocess timeout
    SKIPPED = "skipped"
    PENDING = "pending"

@dataclass
class WorkerState:
    panel_id: str
    label: str
    status: WorkerStatus
    last_output_hash: str = ""
    last_change_at: datetime = field(default_factory=datetime.now)
    idle_seconds: float = 0.0
    process_alive: bool = True
    retry_count: int = 0
    screen_snippet: str = ""

@dataclass
class WorkerHistory:
    panel_id: str
    label: str
    consecutive_stuck: int = 0
    consecutive_dead: int = 0
    total_recoveries: int = 0
    last_recovery_at: datetime | None = None
    last_output_change_at: datetime = field(default_factory=datetime.now)  # NEW (CDX-1)
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

### 2.2 `config.py` -- Configuration (DELTA from v1)

**Changes**:
- Swapped idle/stuck timeouts (AGY-1 fix)
- Added `CSO` to default exclusions (AGY-5 fix)
- Added `max_cooldown` for backoff cap (AGY-4 fix)
- Added `alert_file` path for Tier3 alerts (AGY-3 fix)
- Added `audit_retention_days` for log rotation (CDX-9 fix)

```python
@dataclass
class WatchdogConfig:
    # Timing
    scan_interval: float = 10.0
    idle_timeout: float = 60.0           # CHANGED: was 300 (AGY-1)
    stuck_timeout: float = 180.0         # CHANGED: was 120 (AGY-1)
    dead_check_interval: float = 30.0

    # Recovery limits
    max_tier1_retries: int = 3
    max_tier2_retries: int = 2
    recovery_cooldown: float = 60.0
    max_cooldown: float = 300.0          # NEW: backoff cap (AGY-4)

    # Detection
    hash_window_size: int = 10
    screen_capture_lines: int = 50

    # Exclusions
    excluded_panels: list[str] | None = None  # CHANGED default below

    # Paths
    alert_file: str = "javis/watchdog/alerts.jsonl"    # NEW (AGY-3)
    pid_file: str = "javis/watchdog/watchdog.pid"      # NEW (CDX-6)
    stop_file: str = "javis/watchdog/watchdog.stop"    # NEW (CDX-8)
    audit_retention_days: int = 7                       # NEW (CDX-9)

    def __post_init__(self) -> None:
        if self.excluded_panels is None:
            self.excluded_panels = ["Master", "Dashboard", "CSO"]  # CHANGED (AGY-5)

    @classmethod
    def from_dict(cls, data: dict) -> WatchdogConfig:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known})
```

### 2.3 `detector.py` -- Worker Status Detection (DELTA from v1)

**Changes**:
- Added `_strip_ansi()` preprocessing (CDX-2 fix)
- Added `_THINKING_PATTERNS` for AI processing detection (AGY-2 fix)
- Fixed `idle_seconds` calculation using `last_output_change_at` (CDX-1 fix)
- Added `_prune_stale_histories()` (CDX-4 fix)
- Content-changed-but-empty classified as UNKNOWN (CDX-7 fix)
- Classification order: DEAD > THINKING(=LIVE) > STUCK > LIVE > IDLE > UNKNOWN (AGY-1)

```python
"""Worker health detection via tmux screen capture."""
from __future__ import annotations

import hashlib
import re
import subprocess
import time
from datetime import datetime

from .config import WatchdogConfig
from .models import WorkerHistory, WorkerState, WorkerStatus

# Reuse dashboard's ANSI stripping regex (CDX-2)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\r")


def _strip_ansi(text: str) -> str:
    """Strip ANSI escape codes and carriage returns."""
    return _ANSI_RE.sub("", text)


class Detector:
    """Scans fleet workers and classifies their health status.

    Uses tmux capture-pane to read worker screens. Screen content
    is ANSI-stripped before hashing to avoid false change detections.
    Recognizes AI "thinking" patterns to avoid false STUCK classification.

    Args:
        config: Watchdog configuration.
    """

    # Patterns indicating active work
    _LIVE_PATTERNS: list[str] = [
        "writing", "reading file", "searching", "running",
        "edit(", "write(", "bash(",
        "building", "fetching", "compiling",
    ]

    # Patterns indicating AI is actively thinking (AGY-2)
    # Derived from dashboard.py detect_status() -- kept in sync
    _THINKING_PATTERNS: list[str] = [
        "thinking", "processing", "generating", "analyzing",
        "spinning", "pondering", "cogitating", "ruminating",
        "contemplating", "deliberating", "musing",
        "moonwalking", "combobulating", "crunching", "brewing",
        "loading", "computing", "reasoning", "considering",
        "investigating", "gathering", "levitating",
        "esc to interrupt", "esc to cancel",
        # AGY (Gemini) patterns
        "calling tool", "executing", "applying patch",
        "searching codebase",
        # Codex patterns
        "codex is thinking", "applying changes", "reviewing",
        # Spinner characters (single frame may repeat)
        "\u280b", "\u2819", "\u2839", "\u2838",
        "\u283c", "\u2834", "\u2826", "\u2827",
        "\u2807", "\u280f",
    ]

    # Patterns indicating prompt/idle state
    _IDLE_PATTERNS: list[str] = [
        "$ ", "> ", ">>> ",
        "waiting for input",
        "what would you like",
        "how can i help",
        "type your message",
        "enter a prompt",
    ]

    # Patterns indicating error/crash
    _DEAD_PATTERNS: list[str] = [
        "traceback (most recent call last)",
        "error: process exited",
        "segmentation fault",
        "killed",
        "oomkilled",
    ]

    def __init__(self, config: WatchdogConfig) -> None:
        self._config = config
        self._histories: dict[str, WorkerHistory] = {}

    def scan_all(self) -> list[WorkerState]:
        """Scan all fleet panels and return their states.

        Discovers panels via tmux list-panes, excludes configured
        panels, captures screen content, classifies each worker.
        Prunes history for panels that no longer exist.

        Returns:
            List of WorkerState for each monitored worker.
        """
        panels = self._list_panels()
        current_ids = {pid for pid, _ in panels}
        self._prune_stale_histories(current_ids)  # CDX-4

        states: list[WorkerState] = []
        for panel_id, label in panels:
            if self._is_excluded(label):
                continue
            state = self._scan_one(panel_id, label)
            states.append(state)
        return states

    def _list_panels(self) -> list[tuple[str, str]]:
        """List active panels via tmux list-panes.

        Returns:
            List of (panel_id, label) tuples.
        """
        try:
            result = subprocess.run(
                ["tmux", "list-panes", "-F",
                 "#{pane_id}:#{pane_title}"],
                capture_output=True, text=True, timeout=5,
            )
            panels = []
            for line in result.stdout.strip().splitlines():
                if ":" in line:
                    pid, label = line.split(":", 1)
                    panels.append((pid.strip(), label.strip()))
            return panels
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []

    def _is_excluded(self, label: str) -> bool:
        """Check if panel label matches any exclusion entry."""
        excluded = self._config.excluded_panels or []
        label_lower = label.lower()
        return any(ex.lower() in label_lower for ex in excluded)

    def _scan_one(
        self, panel_id: str, label: str,
    ) -> WorkerState:
        """Capture and classify a single worker panel.

        Args:
            panel_id: tmux panel identifier.
            label: Human-readable panel label.

        Returns:
            WorkerState with current classification.
        """
        raw_screen = self._capture_screen(panel_id)
        screen = _strip_ansi(raw_screen)  # CDX-2: strip before hash
        screen_hash = hashlib.md5(screen.encode()).hexdigest()
        now = datetime.now()

        history = self._get_history(panel_id, label)
        content_changed = self._update_hash_history(
            history, screen_hash,
        )

        # CDX-1 fix: track last_output_change_at in history
        if content_changed:
            history.last_output_change_at = now
            history.consecutive_stuck = 0

        idle_seconds = (
            now - history.last_output_change_at
        ).total_seconds()

        status = self._classify(
            screen, content_changed, idle_seconds,
        )

        lines = screen.strip().splitlines()
        snippet = "\n".join(lines[-5:]) if lines else ""

        return WorkerState(
            panel_id=panel_id,
            label=label,
            status=status,
            last_output_hash=screen_hash,
            last_change_at=history.last_output_change_at,
            idle_seconds=idle_seconds,
            process_alive=(status != WorkerStatus.DEAD),
            retry_count=history.tier1_count,
            screen_snippet=snippet,
        )

    def _capture_screen(self, panel_id: str) -> str:
        """Capture panel screen content via tmux.

        Returns:
            Raw screen content. Empty string on failure.
        """
        try:
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", panel_id, "-p",
                 "-S", f"-{self._config.screen_capture_lines}"],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""

    def _classify(
        self,
        screen: str,
        content_changed: bool,
        idle_seconds: float,
    ) -> WorkerStatus:
        """Classify worker status from screen content and timing.

        Priority: DEAD > THINKING(LIVE) > STUCK > LIVE > IDLE > UNKNOWN

        Args:
            screen: ANSI-stripped screen content.
            content_changed: Whether content changed since last scan.
            idle_seconds: Seconds since last content change.

        Returns:
            WorkerStatus classification.
        """
        stripped = screen.strip()

        # 1. No content at all = DEAD
        if not stripped:
            return WorkerStatus.DEAD

        # 2. Crash/exit patterns = DEAD
        if self._matches_any(stripped, self._DEAD_PATTERNS):
            return WorkerStatus.DEAD

        # 3. AI thinking patterns = LIVE (AGY-2)
        #    Even if hash unchanged (same spinner frame)
        if self._matches_any(stripped, self._THINKING_PATTERNS):
            return WorkerStatus.LIVE

        # 4. Content changed
        if content_changed:
            # CDX-7: trivial change (nearly empty) = UNKNOWN
            non_ws = len(stripped.replace(" ", "").replace("\n", ""))
            if non_ws < 10:
                return WorkerStatus.UNKNOWN
            return WorkerStatus.LIVE

        # 5. No content change -- check timeouts (AGY-1 fix)
        if idle_seconds > self._config.stuck_timeout:
            return WorkerStatus.STUCK

        if idle_seconds > self._config.idle_timeout:
            return WorkerStatus.IDLE

        # 6. Within thresholds -- check for idle patterns
        if self._matches_any(stripped, self._IDLE_PATTERNS):
            return WorkerStatus.IDLE

        return WorkerStatus.UNKNOWN

    def _get_history(
        self, panel_id: str, label: str,
    ) -> WorkerHistory:
        """Get or create worker history."""
        if panel_id not in self._histories:
            self._histories[panel_id] = WorkerHistory(
                panel_id=panel_id, label=label,
            )
        return self._histories[panel_id]

    def _update_hash_history(
        self, history: WorkerHistory, screen_hash: str,
    ) -> bool:
        """Update hash rolling window.

        Returns:
            True if content changed (hash differs from previous).
        """
        changed = (
            not history.previous_hashes
            or history.previous_hashes[-1] != screen_hash
        )
        history.previous_hashes.append(screen_hash)
        if len(history.previous_hashes) > self._config.hash_window_size:
            history.previous_hashes.pop(0)
        return changed

    def _prune_stale_histories(
        self, current_ids: set[str],
    ) -> None:
        """Remove history entries for panels that no longer exist.

        CDX-4 fix: prevents unbounded memory growth.

        Args:
            current_ids: Set of currently active panel IDs.
        """
        stale = [
            pid for pid in self._histories
            if pid not in current_ids
        ]
        for pid in stale:
            del self._histories[pid]

    @staticmethod
    def _matches_any(text: str, patterns: list[str]) -> bool:
        """Check if text contains any of the given patterns.

        Case-insensitive matching.
        """
        text_lower = text.lower()
        return any(p.lower() in text_lower for p in patterns)
```

### 2.4 `strategy.py` -- Recovery Decision Engine (DELTA from v1)

**Changes**:
- Renamed `_histories` to `_action_tracker` for clarity (AGY-7 partial fix)
- Added linear backoff: cooldown doubles per failed attempt, capped (AGY-4 partial fix)
- `_action_tracker` stores `consecutive_failures` for backoff calculation

```python
"""3-tier recovery strategy decision engine with linear backoff."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime

from .config import WatchdogConfig
from .models import (
    RecoveryAction,
    RecoveryTier,
    WorkerState,
    WorkerStatus,
)


@dataclass
class ActionTracker:
    """Per-worker recovery tracking (distinct from Detector history).

    Tracks tier counts, cooldowns, and backoff state.
    """
    panel_id: str
    label: str
    tier1_count: int = 0
    tier2_count: int = 0
    consecutive_failures: int = 0
    last_action_at: float = 0.0    # time.time() of last action


class Strategy:
    """Decides recovery actions based on worker states.

    3-tier escalation with linear backoff:
        Tier 1: Send Ctrl+C to interrupt stuck process
        Tier 2: Kill and restart the worker process
        Tier 3: Escalate -- write alert for human attention

    Cooldown increases linearly per consecutive failure:
        base_cooldown * (1 + consecutive_failures), capped at max_cooldown.

    Args:
        config: Watchdog configuration.
    """

    def __init__(self, config: WatchdogConfig) -> None:
        self._config = config
        self._trackers: dict[str, ActionTracker] = {}

    def decide(
        self, states: list[WorkerState],
    ) -> list[RecoveryAction]:
        """Analyze worker states and produce recovery actions.

        Only produces actions for STUCK or DEAD workers.
        Respects cooldown with linear backoff.

        Args:
            states: Current worker states from Detector.

        Returns:
            List of recovery actions. May be empty.
        """
        actions: list[RecoveryAction] = []
        for state in states:
            action = self._decide_one(state)
            if action is not None:
                actions.append(action)
        return actions

    def _decide_one(
        self, state: WorkerState,
    ) -> RecoveryAction | None:
        """Decide recovery action for a single worker."""
        # Healthy workers: reset tracker
        if state.status in (WorkerStatus.LIVE, WorkerStatus.IDLE):
            self._reset_tracker(state.panel_id)
            return None

        if state.status == WorkerStatus.UNKNOWN:
            return None

        tracker = self._get_tracker(state)

        if not self._cooldown_elapsed(tracker):
            return None

        if state.status == WorkerStatus.DEAD:
            return self._decide_dead(state, tracker)

        if state.status == WorkerStatus.STUCK:
            return self._decide_stuck(state, tracker)

        return None

    def _decide_stuck(
        self,
        state: WorkerState,
        tracker: ActionTracker,
    ) -> RecoveryAction:
        """Decide tier for stuck worker.

        Tier1 (max_tier1_retries) -> Tier2 (max_tier2_retries) -> Tier3.
        """
        if tracker.tier1_count < self._config.max_tier1_retries:
            tracker.tier1_count += 1
            return RecoveryAction(
                panel_id=state.panel_id,
                label=state.label,
                tier=RecoveryTier.TIER1_INTERRUPT,
                reason=(
                    f"Stuck {state.idle_seconds:.0f}s, "
                    f"Ctrl+C {tracker.tier1_count}/"
                    f"{self._config.max_tier1_retries}"
                ),
                current_state=state,
            )

        if tracker.tier2_count < self._config.max_tier2_retries:
            tracker.tier2_count += 1
            return RecoveryAction(
                panel_id=state.panel_id,
                label=state.label,
                tier=RecoveryTier.TIER2_RESTART,
                reason=(
                    f"Tier1 exhausted ({tracker.tier1_count}x), "
                    f"restart {tracker.tier2_count}/"
                    f"{self._config.max_tier2_retries}"
                ),
                current_state=state,
            )

        return RecoveryAction(
            panel_id=state.panel_id,
            label=state.label,
            tier=RecoveryTier.TIER3_ESCALATE,
            reason=(
                f"All retries exhausted "
                f"(T1={tracker.tier1_count}, "
                f"T2={tracker.tier2_count}). Escalating."
            ),
            current_state=state,
        )

    def _decide_dead(
        self,
        state: WorkerState,
        tracker: ActionTracker,
    ) -> RecoveryAction:
        """Decide tier for dead worker.

        Skip Tier1 (no process to Ctrl+C), go to Tier2.
        """
        if tracker.tier2_count < self._config.max_tier2_retries:
            tracker.tier2_count += 1
            return RecoveryAction(
                panel_id=state.panel_id,
                label=state.label,
                tier=RecoveryTier.TIER2_RESTART,
                reason=(
                    f"Worker dead, restart "
                    f"{tracker.tier2_count}/"
                    f"{self._config.max_tier2_retries}"
                ),
                current_state=state,
            )

        return RecoveryAction(
            panel_id=state.panel_id,
            label=state.label,
            tier=RecoveryTier.TIER3_ESCALATE,
            reason=(
                f"Worker dead, restarts exhausted "
                f"(T2={tracker.tier2_count}). Escalating."
            ),
            current_state=state,
        )

    def _cooldown_elapsed(self, tracker: ActionTracker) -> bool:
        """Check if cooldown (with linear backoff) has elapsed.

        Effective cooldown = base * (1 + failures), capped at max.
        """
        base = self._config.recovery_cooldown
        multiplier = 1 + tracker.consecutive_failures
        effective = min(base * multiplier, self._config.max_cooldown)
        return time.time() - tracker.last_action_at >= effective

    def record_action(
        self, panel_id: str, success: bool,
    ) -> None:
        """Record that an action was executed.

        Args:
            panel_id: Target panel.
            success: Whether the action succeeded.
        """
        if panel_id in self._trackers:
            t = self._trackers[panel_id]
            t.last_action_at = time.time()
            if success:
                t.consecutive_failures = 0
            else:
                t.consecutive_failures += 1

    def _get_tracker(self, state: WorkerState) -> ActionTracker:
        """Get or create action tracker for a worker."""
        if state.panel_id not in self._trackers:
            self._trackers[state.panel_id] = ActionTracker(
                panel_id=state.panel_id, label=state.label,
            )
        return self._trackers[state.panel_id]

    def _reset_tracker(self, panel_id: str) -> None:
        """Reset tracker when worker returns to healthy state."""
        if panel_id in self._trackers:
            t = self._trackers[panel_id]
            t.tier1_count = 0
            t.tier2_count = 0
            t.consecutive_failures = 0

    def prune_trackers(self, active_ids: set[str]) -> None:
        """Remove trackers for panels that no longer exist.

        CDX-4 fix. Called by orchestrator.
        """
        stale = [pid for pid in self._trackers
                 if pid not in active_ids]
        for pid in stale:
            del self._trackers[pid]
```

### 2.5 `executor.py` -- Recovery Executor (DELTA from v1)

**Changes**:
- Tier 3 writes to `alerts.jsonl` instead of echo to master (AGY-3 fix)
- Reduced sleep times in Tier 2 (CDX-5 partial fix)
- Verification moved out of executor -- next scan cycle verifies (CDX-5)
- Added `ActionResult.TIMEOUT` for subprocess timeouts
- Restart commands documented as trusted-literals-only (CDX-3 note)

```python
"""Execute recovery actions via tmux commands."""
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

from .config import WatchdogConfig
from .models import (
    ActionResult,
    RecoveryAction,
    RecoveryTier,
    WatchdogEvent,
)


class Executor:
    """Executes recovery actions against fleet workers.

    Tier 1: Send Ctrl+C via tmux send-keys.
    Tier 2: Kill worker process and restart via tmux.
    Tier 3: Write alert to alerts.jsonl for dashboard/human.

    SECURITY NOTE: _RESTART_COMMANDS values are trusted literals.
    Never populate from external/user input without validation.
    """

    # Worker type -> restart command (TRUSTED LITERALS ONLY)
    _RESTART_COMMANDS: dict[str, str] = {
        "Claude": "claude --dangerously-skip-permissions",
        "AGY": "agy",
        "Codex": "codex -a never --no-alt-screen",
    }

    def __init__(self, config: WatchdogConfig) -> None:
        self._config = config

    def execute(self, action: RecoveryAction) -> WatchdogEvent:
        """Execute a single recovery action.

        Args:
            action: The recovery action to execute.

        Returns:
            WatchdogEvent with the outcome.
        """
        start = time.monotonic()

        handlers = {
            RecoveryTier.TIER1_INTERRUPT: self._execute_tier1,
            RecoveryTier.TIER2_RESTART: self._execute_tier2,
            RecoveryTier.TIER3_ESCALATE: self._execute_tier3,
        }
        handler = handlers.get(action.tier)
        if handler:
            result, detail = handler(action)
        else:
            result = ActionResult.SKIPPED
            detail = f"Unknown tier: {action.tier}"

        elapsed_ms = (time.monotonic() - start) * 1000

        return WatchdogEvent(
            timestamp=datetime.now(),
            panel_id=action.panel_id,
            label=action.label,
            action_tier=action.tier,
            result=result,
            detail=detail,
            duration_ms=elapsed_ms,
        )

    def _execute_tier1(
        self, action: RecoveryAction,
    ) -> tuple[ActionResult, str]:
        """Tier 1: Send Ctrl+C to interrupt stuck process.

        Double Ctrl+C with short delay. No inline verification
        (next scan cycle will check if worker recovered).
        """
        try:
            self._tmux_send_keys(action.panel_id, "C-c")
            time.sleep(0.5)
            self._tmux_send_keys(action.panel_id, "C-c")
            return (
                ActionResult.PENDING,
                "Ctrl+C x2 sent, verifying next cycle",
            )
        except subprocess.TimeoutExpired:
            return ActionResult.TIMEOUT, "tmux send-keys timed out"

    def _execute_tier2(
        self, action: RecoveryAction,
    ) -> tuple[ActionResult, str]:
        """Tier 2: Kill and restart worker process.

        Steps: Ctrl+C x2 -> wait -> exit -> restart command.
        Total blocking time: ~4s (reduced from 7s in v1).
        Verification deferred to next scan cycle.
        """
        panel_id = action.panel_id
        worker_type = self._detect_worker_type(action.label)
        restart_cmd = self._RESTART_COMMANDS.get(worker_type)

        if restart_cmd is None:
            return (
                ActionResult.FAILED,
                f"Unknown worker type '{worker_type}' "
                f"for '{action.label}'",
            )

        try:
            # Graceful shutdown
            self._tmux_send_keys(panel_id, "C-c")
            time.sleep(0.5)
            self._tmux_send_keys(panel_id, "C-c")
            time.sleep(1.0)

            # Force exit
            self._tmux_send_keys(panel_id, "exit", enter=True)
            time.sleep(1.0)

            # Restart
            self._tmux_send_keys(panel_id, restart_cmd, enter=True)
            time.sleep(1.5)

            return (
                ActionResult.PENDING,
                f"Restarted with '{restart_cmd}', "
                f"verifying next cycle",
            )
        except subprocess.TimeoutExpired:
            return (
                ActionResult.TIMEOUT,
                "Restart sequence timed out",
            )

    def _execute_tier3(
        self, action: RecoveryAction,
    ) -> tuple[ActionResult, str]:
        """Tier 3: Escalate by writing to alerts.jsonl.

        AGY-3 fix: No longer sends echo to master pane.
        Writes structured alert for dashboard to display.
        """
        alert = {
            "timestamp": datetime.now().isoformat(),
            "level": "critical",
            "panel_id": action.panel_id,
            "label": action.label,
            "reason": action.reason,
            "message": (
                f"[WATCHDOG] {action.label} ({action.panel_id}) "
                f"unrecoverable: {action.reason}"
            ),
        }
        try:
            alert_path = Path(self._config.alert_file)
            alert_path.parent.mkdir(parents=True, exist_ok=True)
            with open(alert_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(alert, ensure_ascii=False) + "\n")
            return (
                ActionResult.SUCCESS,
                f"Alert written: {action.reason[:80]}",
            )
        except OSError as e:
            return (
                ActionResult.FAILED,
                f"Alert write failed: {e}",
            )

    @staticmethod
    def _detect_worker_type(label: str) -> str:
        """Extract worker type from panel label.

        Args:
            label: e.g. "Worker1(Claude)" or "Worker2(AGY)".

        Returns:
            "Claude", "AGY", "Codex", or "Unknown".
        """
        label_lower = label.lower()
        if "claude" in label_lower:
            return "Claude"
        if "agy" in label_lower or "gemini" in label_lower:
            return "AGY"
        if "codex" in label_lower:
            return "Codex"
        return "Unknown"

    @staticmethod
    def _tmux_send_keys(
        panel_id: str, keys: str, enter: bool = False,
    ) -> None:
        """Send keys to a tmux panel.

        Args:
            panel_id: Target panel (e.g., "%1").
            keys: Keys to send.
            enter: If True, append Enter key.
        """
        cmd = ["tmux", "send-keys", "-t", panel_id, keys]
        if enter:
            cmd.append("Enter")
        subprocess.run(cmd, timeout=5, check=True)
```

### 2.6 `orchestrator.py` -- Main Loop (DELTA from v1)

**Changes**:
- PID file for singleton guard (CDX-6 fix)
- Stop-file sentinel check each cycle (CDX-8 fix)
- Date-stamped audit logs with retention cleanup (CDX-9 fix)
- Strategy.record_action now takes success bool for backoff (AGY-4)
- Strategy.prune_trackers called each cycle (CDX-4)

```python
"""Main watchdog orchestrator: detect -> decide -> execute loop."""
from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .config import WatchdogConfig
from .detector import Detector
from .executor import Executor
from .models import ActionResult, WatchdogEvent
from .strategy import Strategy

logger = logging.getLogger(__name__)


class Orchestrator:
    """Main watchdog loop with singleton guard and file-based stop.

    Runs detect -> decide -> execute at configurable intervals.
    Events logged to date-stamped JSONL files with auto-retention.

    Args:
        config: Watchdog configuration.
        audit_dir: Directory for JSONL audit logs. None to disable.
    """

    def __init__(
        self,
        config: WatchdogConfig | None = None,
        audit_dir: Path | None = None,
    ) -> None:
        self._config = config or WatchdogConfig()
        self._detector = Detector(self._config)
        self._strategy = Strategy(self._config)
        self._executor = Executor(self._config)
        self._running = False
        self._audit_dir = audit_dir
        self._cycle_count = 0

    def start(self) -> None:
        """Start the watchdog main loop.

        Acquires PID file, cleans old audit logs, then blocks
        until stop() is called, SIGINT/SIGTERM, or stop-file detected.
        """
        if not self._acquire_pid():
            logger.error("Another watchdog is running. Exiting.")
            return

        self._cleanup_old_audits()
        self._remove_stop_file()

        self._running = True
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        logger.info(
            "Watchdog started (interval=%.0fs, "
            "idle=%.0fs, stuck=%.0fs)",
            self._config.scan_interval,
            self._config.idle_timeout,
            self._config.stuck_timeout,
        )

        try:
            while self._running:
                if self._stop_file_exists():
                    logger.info("Stop file detected, shutting down")
                    break
                try:
                    self._run_cycle()
                except Exception as e:
                    logger.error("Cycle error: %s", e)
                time.sleep(self._config.scan_interval)
        finally:
            self._release_pid()

        logger.info(
            "Watchdog stopped after %d cycles",
            self._cycle_count,
        )

    def stop(self) -> None:
        """Stop the watchdog loop."""
        self._running = False

    def _run_cycle(self) -> None:
        """Execute one scan-decide-execute cycle."""
        self._cycle_count += 1

        # Phase 1: Detect
        states = self._detector.scan_all()
        if not states:
            return

        # Prune stale strategy trackers (CDX-4)
        active_ids = {s.panel_id for s in states}
        self._strategy.prune_trackers(active_ids)

        # Phase 2: Decide
        actions = self._strategy.decide(states)
        if not actions:
            return

        # Phase 3: Execute
        for action in actions:
            logger.warning(
                "Recovery: %s (%s) Tier%s: %s",
                action.label, action.panel_id,
                action.tier.value, action.reason,
            )
            event = self._executor.execute(action)

            success = event.result in (
                ActionResult.SUCCESS,
                ActionResult.PENDING,
            )
            self._strategy.record_action(
                action.panel_id, success=success,
            )

            self._log_event(event)
            self._write_audit(event)

    def _log_event(self, event: WatchdogEvent) -> None:
        """Log event to Python logger."""
        if event.result == ActionResult.SUCCESS:
            logger.info(
                "SUCCESS: %s -- %s (%.0fms)",
                event.label, event.detail, event.duration_ms,
            )
        else:
            logger.warning(
                "%s: %s -- %s (%.0fms)",
                event.result.value.upper(), event.label,
                event.detail, event.duration_ms,
            )

    def _write_audit(self, event: WatchdogEvent) -> None:
        """Append event to date-stamped JSONL audit log."""
        if self._audit_dir is None:
            return
        entry = {
            "timestamp": event.timestamp.isoformat(),
            "panel_id": event.panel_id,
            "label": event.label,
            "tier": event.action_tier.value,
            "result": event.result.value,
            "detail": event.detail,
            "duration_ms": round(event.duration_ms, 1),
        }
        try:
            self._audit_dir.mkdir(parents=True, exist_ok=True)
            date_str = datetime.now().strftime("%Y%m%d")
            path = self._audit_dir / f"audit_{date_str}.jsonl"
            with open(path, "a", encoding="utf-8") as f:
                f.write(
                    json.dumps(entry, ensure_ascii=False) + "\n"
                )
        except OSError as e:
            logger.warning("Audit write failed: %s", e)

    def _cleanup_old_audits(self) -> None:
        """Delete audit files older than retention period."""
        if self._audit_dir is None or not self._audit_dir.exists():
            return
        cutoff = datetime.now() - timedelta(
            days=self._config.audit_retention_days,
        )
        for f in self._audit_dir.glob("audit_*.jsonl"):
            try:
                date_part = f.stem.replace("audit_", "")
                file_date = datetime.strptime(date_part, "%Y%m%d")
                if file_date < cutoff:
                    f.unlink()
                    logger.info("Deleted old audit: %s", f.name)
            except (ValueError, OSError):
                pass

    # -- Singleton PID file (CDX-6) --

    def _acquire_pid(self) -> bool:
        """Write PID file. Returns False if already running."""
        pid_path = Path(self._config.pid_file)
        if pid_path.exists():
            try:
                old_pid = int(pid_path.read_text().strip())
                # Check if process is still alive
                os.kill(old_pid, 0)
                return False  # Process alive
            except (ValueError, OSError):
                pass  # Stale PID file
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text(str(os.getpid()))
        return True

    def _release_pid(self) -> None:
        """Remove PID file on shutdown."""
        try:
            Path(self._config.pid_file).unlink(missing_ok=True)
        except OSError:
            pass

    # -- File-based stop sentinel (CDX-8) --

    def _stop_file_exists(self) -> bool:
        """Check if stop sentinel file exists."""
        return Path(self._config.stop_file).exists()

    def _remove_stop_file(self) -> None:
        """Remove stop file on startup."""
        try:
            Path(self._config.stop_file).unlink(missing_ok=True)
        except OSError:
            pass

    # -- Status & signals --

    def get_status(self) -> dict[str, Any]:
        """Get current watchdog status snapshot."""
        states = self._detector.scan_all()
        return {
            "running": self._running,
            "cycle_count": self._cycle_count,
            "workers": [
                {
                    "panel_id": s.panel_id,
                    "label": s.label,
                    "status": s.status.value,
                    "idle_seconds": round(s.idle_seconds, 1),
                }
                for s in states
            ],
        }

    def _handle_signal(self, signum: int, frame: Any) -> None:
        """Handle SIGINT/SIGTERM for graceful shutdown."""
        logger.info("Signal %d received, stopping", signum)
        self.stop()
```

### 2.7 `cli.py` -- CLI Interface (DELTA from v1)

**Changes**:
- `stop` command creates the stop-file sentinel (CDX-8 fix)
- Audit dir instead of single file path
- Config loads alert_file and pid_file paths

```python
"""Watchdog CLI: python -m javis.watchdog start|status|stop"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import WatchdogConfig
from .orchestrator import Orchestrator


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Command-line arguments. None uses sys.argv.

    Returns:
        Exit code (0 = success).
    """
    parser = argparse.ArgumentParser(
        prog="javis.watchdog",
        description="Javis Fleet Auto-Recovery Watchdog",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # start
    start_p = sub.add_parser("start", help="Start watchdog")
    start_p.add_argument(
        "--config", type=Path, default=None,
        help="Path to JSON config file",
    )
    start_p.add_argument(
        "--audit-dir", type=Path,
        default=Path("javis/watchdog/audit"),
        help="Directory for JSONL audit logs",
    )

    # status
    sub.add_parser("status", help="Show fleet status")

    # stop
    sub.add_parser("stop", help="Stop running watchdog")

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.command == "start":
        config = _load_config(args.config)
        orch = Orchestrator(
            config=config, audit_dir=args.audit_dir,
        )
        orch.start()
        return 0

    if args.command == "status":
        orch = Orchestrator(config=WatchdogConfig())
        status = orch.get_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return 0

    if args.command == "stop":
        config = _load_config(None)
        stop_path = Path(config.stop_file)
        stop_path.parent.mkdir(parents=True, exist_ok=True)
        stop_path.write_text("stop")
        print(f"Stop file created: {stop_path}")
        return 0

    return 1


def _load_config(path: Path | None) -> WatchdogConfig:
    """Load config from JSON file or return defaults."""
    if path is None or not path.exists():
        return WatchdogConfig()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return WatchdogConfig.from_dict(data)


if __name__ == "__main__":
    sys.exit(main())
```

---

## 3. Interface Contracts

### 3.1 Module Dependency Graph (unchanged)

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

### 3.2 Function Signature Summary (FINAL)

| Module | Method | Input | Output |
|--------|--------|-------|--------|
| `Detector` | `scan_all()` | -- | `list[WorkerState]` |
| `Detector` | `_scan_one(panel_id, label)` | `str, str` | `WorkerState` |
| `Detector` | `_capture_screen(panel_id)` | `str` | `str` |
| `Detector` | `_classify(screen, changed, idle_s)` | `str, bool, float` | `WorkerStatus` |
| `Detector` | `_prune_stale_histories(ids)` | `set[str]` | `None` |
| `Strategy` | `decide(states)` | `list[WorkerState]` | `list[RecoveryAction]` |
| `Strategy` | `record_action(panel_id, success)` | `str, bool` | `None` |
| `Strategy` | `prune_trackers(active_ids)` | `set[str]` | `None` |
| `Executor` | `__init__(config)` | `WatchdogConfig` | -- |
| `Executor` | `execute(action)` | `RecoveryAction` | `WatchdogEvent` |
| `Orchestrator` | `__init__(config, audit_dir)` | `Config, Path|None` | -- |
| `Orchestrator` | `start()` | -- | `None` (blocks) |
| `Orchestrator` | `stop()` | -- | `None` |
| `Orchestrator` | `get_status()` | -- | `dict[str, Any]` |
| `cli` | `main(argv)` | `list[str] | None` | `int` |

---

## 4. Error Handling Strategy (FINAL)

### 4.1 Fault Isolation (unchanged + additions)

| Component | Error Source | Handling |
|-----------|-------------|----------|
| `Detector._capture_screen` | subprocess timeout | Return `""`, classify UNKNOWN |
| `Detector._list_panels` | tmux command fails | Return `[]`, no workers scanned |
| `Strategy.decide` | Internal error | Caught in orchestrator, logged, continue |
| `Executor._execute_tier1` | subprocess timeout | Return `TIMEOUT` ActionResult |
| `Executor._execute_tier2` | Unknown worker type | Return `FAILED` with detail |
| `Executor._execute_tier3` | File I/O error | Return `FAILED` (was: tmux timeout) |
| `Orchestrator._run_cycle` | Any exception | Log error, continue to next cycle |
| `Orchestrator._write_audit` | File I/O error | Log warning, non-fatal |
| `Orchestrator._acquire_pid` | Stale PID file | Remove and acquire |

### 4.2 Never-Crash Principles (unchanged)

1. All subprocess calls have 5s timeouts
2. All file I/O wrapped in try/except
3. Main loop catches all exceptions per cycle
4. Signal handlers and stop-file sentinel set flag, never raise

---

## 5. Test Strategy (FINAL)

### 5.1 `tests/conftest.py` -- Common Fixtures

```python
"""Shared test fixtures for watchdog tests."""
import pytest
from datetime import datetime
from javis.watchdog.config import WatchdogConfig
from javis.watchdog.models import WorkerState, WorkerStatus


@pytest.fixture
def config() -> WatchdogConfig:
    """Fast test config with short timeouts."""
    return WatchdogConfig(
        scan_interval=1.0,
        idle_timeout=3.0,       # Quick transitions for tests
        stuck_timeout=6.0,
        max_tier1_retries=2,
        max_tier2_retries=1,
        recovery_cooldown=1.0,
        max_cooldown=5.0,
    )


@pytest.fixture
def live_worker() -> WorkerState:
    return WorkerState(
        panel_id="%1", label="Worker1(Claude)",
        status=WorkerStatus.LIVE, idle_seconds=0,
    )


@pytest.fixture
def stuck_worker() -> WorkerState:
    return WorkerState(
        panel_id="%2", label="Worker2(AGY)",
        status=WorkerStatus.STUCK, idle_seconds=200,
    )


@pytest.fixture
def dead_worker() -> WorkerState:
    return WorkerState(
        panel_id="%3", label="Worker3(Codex)",
        status=WorkerStatus.DEAD, process_alive=False,
    )
```

### 5.2 Test Matrix with Mock Targets

| File | Tests | Mock Target |
|------|-------|-------------|
| `test_detector.py` | Pattern matching, classification logic, hash change detection, ANSI stripping, thinking-pattern recognition, history pruning, excluded panel filtering | `javis.watchdog.detector.subprocess.run` |
| `test_strategy.py` | 3-tier escalation, cooldown with backoff, DEAD->Tier2 skip, LIVE/IDLE tracker reset, tracker pruning | Pure logic (no mocks needed) |
| `test_executor.py` | tmux command construction, worker type detection, Tier 1/2/3 execution, alert file write, timeout handling | `javis.watchdog.executor.subprocess.run` |
| `test_orchestrator.py` | Full pipeline, audit log rotation, PID file singleton, stop-file sentinel, signal handling, cycle counting | Mock Detector/Strategy/Executor classes |

### 5.3 Key Test Cases per Module

**test_detector.py**:
- `test_classify_empty_screen_is_dead` -- empty string -> DEAD
- `test_classify_traceback_is_dead` -- "Traceback" in screen -> DEAD
- `test_classify_thinking_is_live` -- "Thinking..." -> LIVE even with no hash change
- `test_classify_idle_timeout` -- no change for idle_timeout -> IDLE
- `test_classify_stuck_timeout` -- no change for stuck_timeout -> STUCK
- `test_classify_content_changed_is_live` -- hash changed -> LIVE
- `test_classify_trivial_change_is_unknown` -- near-empty change -> UNKNOWN
- `test_ansi_stripped_before_hash` -- ANSI codes do not affect hash
- `test_excluded_panel_skipped` -- "Master" label skipped
- `test_prune_removes_stale_history` -- defunct panel history removed

**test_strategy.py**:
- `test_live_worker_no_action` -- LIVE -> no recovery
- `test_stuck_first_attempt_tier1` -- first STUCK -> TIER1
- `test_stuck_exhausted_tier1_to_tier2` -- 3x TIER1 -> TIER2
- `test_stuck_exhausted_all_to_tier3` -- all retries -> TIER3
- `test_dead_skips_tier1` -- DEAD -> straight to TIER2
- `test_cooldown_blocks_rapid_action` -- action within cooldown -> skip
- `test_backoff_increases_cooldown` -- failed actions increase cooldown
- `test_backoff_capped` -- cooldown does not exceed max_cooldown
- `test_recovery_resets_tracker` -- LIVE after STUCK resets counters
- `test_prune_removes_stale_tracker` -- defunct panel tracker removed

**test_executor.py**:
- `test_tier1_sends_ctrl_c_twice` -- verify send-keys "C-c" x2
- `test_tier2_sends_exit_then_restart` -- verify shutdown + restart sequence
- `test_tier2_unknown_type_fails` -- unknown worker -> FAILED
- `test_tier3_writes_alert_file` -- alert JSON appended to file
- `test_tier3_file_error_returns_failed` -- unwritable path -> FAILED
- `test_detect_worker_type_claude` -- "Worker1(Claude)" -> "Claude"
- `test_detect_worker_type_agy` -- "Worker2(AGY)" -> "AGY"
- `test_timeout_returns_timeout_result` -- subprocess timeout -> TIMEOUT

**test_orchestrator.py**:
- `test_full_cycle_stuck_to_recovery` -- stuck detected -> action executed
- `test_no_action_when_all_live` -- all LIVE -> no executor calls
- `test_audit_log_created` -- event written to audit_YYYYMMDD.jsonl
- `test_old_audit_cleaned` -- files beyond retention deleted
- `test_pid_prevents_duplicate` -- second start returns immediately
- `test_stop_file_terminates_loop` -- stop-file -> loop exits
- `test_cycle_error_does_not_crash` -- exception in cycle -> continues

---

## 6. Design Principles (FINAL)

1. **Single Responsibility**: Detect / Decide / Execute / Orchestrate -- each module owns one job.
2. **Unidirectional Dependencies**: models <- config <- detector/strategy/executor <- orchestrator <- cli.
3. **No Circular Imports**: Enforced by the dependency graph.
4. **Stdlib Only**: No external packages (except pytest for tests).
5. **Testability**: All external I/O mockable at module boundaries. Exact mock targets specified.
6. **50-Line Limit**: Every function body within 50 lines.
7. **Audit Trail**: Date-stamped JSONL with auto-retention.
8. **Graceful Degradation**: Never crash; degrade to idle if subsystems fail.
9. **Windows Native**: PID file + stop-file sentinel instead of Unix signals. tmux via cmux-win shim.
10. **Linear Backoff**: Recovery cooldown scales with failures, capped at max_cooldown.
11. **False-Positive Prevention**: Thinking patterns recognized as LIVE. ANSI stripped before hashing.
12. **Alert Separation**: Tier3 writes to file (not to Claude CLI). Dashboard reads alerts.jsonl.

---

## 7. File Structure (FINAL)

```
javis/watchdog/
+-- __init__.py          # Package: from .orchestrator import Orchestrator
+-- __main__.py          # Entry: from .cli import main; main()
+-- config.py            # WatchdogConfig dataclass (revised defaults)
+-- models.py            # WorkerState, WorkerHistory (with last_output_change_at),
|                        # RecoveryAction, WatchdogEvent, enums (with TIMEOUT)
+-- detector.py          # Detector: ANSI-strip + hash + thinking patterns + classify
+-- strategy.py          # Strategy: 3-tier + ActionTracker + linear backoff
+-- executor.py          # Executor: tmux send-keys / restart / alerts.jsonl
+-- orchestrator.py      # Orchestrator: main loop + PID + stop-file + audit rotation
+-- cli.py               # CLI: start / status / stop (file-based)
+-- audit/               # Date-stamped audit logs (auto-created)
|   +-- audit_20260617.jsonl
+-- alerts.jsonl         # Tier3 escalation alerts (dashboard reads)
+-- watchdog.pid         # Singleton PID file (auto-created/removed)
+-- tests/
    +-- __init__.py
    +-- conftest.py      # Shared fixtures (fast timeouts)
    +-- test_detector.py # 10 test cases, mock: detector.subprocess.run
    +-- test_strategy.py # 10 test cases, pure logic (no mocks)
    +-- test_executor.py # 8 test cases, mock: executor.subprocess.run
    +-- test_orchestrator.py  # 7 test cases, mock all sub-modules
```

---

## 8. Implementation Assignment Guide

This design is intended for 5 workers to implement in parallel:

| Worker | Module(s) | Dependencies | Estimated Lines |
|--------|-----------|-------------|-----------------|
| Worker A | `models.py` + `config.py` | None | ~120 |
| Worker B | `detector.py` + `test_detector.py` | models, config | ~250 |
| Worker C | `strategy.py` + `test_strategy.py` | models, config | ~220 |
| Worker D | `executor.py` + `test_executor.py` | models, config | ~200 |
| Worker E | `orchestrator.py` + `cli.py` + `__main__.py` + `__init__.py` + `conftest.py` + `test_orchestrator.py` | all above | ~300 |

**Dependency chain**: Workers A-D can start simultaneously. Worker E must wait for A to complete models/config, but can develop against interfaces immediately using the function signatures above.
