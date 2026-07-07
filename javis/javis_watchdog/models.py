"""Dataclass models for the Javis Fleet Auto-Recovery Watchdog.

Defines the core types used across the watchdog system: worker state
tracking, recovery actions, event logging, and configuration.

Requires Python 3.10+ for ``X | None`` union syntax.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class WorkerStatus(Enum):
    """Observable health state of a fleet worker.

    Attributes:
        LIVE: Worker is responsive and actively processing.
        IDLE: Worker is responsive but has had no output for a while.
        STUCK: Worker appears hung (no output beyond stuck_timeout).
        DEAD: Worker process has exited or the pane is gone.
        UNKNOWN: Status could not be determined (e.g. first check).
    """

    LIVE = "live"
    IDLE = "idle"
    STUCK = "stuck"
    DEAD = "dead"
    UNKNOWN = "unknown"


class RecoveryTier(Enum):
    """Escalation level for automatic recovery actions.

    Attributes:
        RETRY: Soft nudge -- send Ctrl+C and re-issue the last command.
        RESTART: Hard recovery -- kill the process and relaunch the AI CLI.
        ESCALATE: All automatic options exhausted -- notify the master pane.
    """

    RETRY = "retry"
    RESTART = "restart"
    ESCALATE = "escalate"


class AIType(Enum):
    """AI runtime running inside a worker pane.

    Attributes:
        CLAUDE: Claude Code CLI (interactive).
        AGY: Antigravity CLI (Gemini).
        CODEX: OpenAI Codex CLI.
        UNKNOWN: Could not determine the AI type.
    """

    CLAUDE = "claude"
    AGY = "agy"
    CODEX = "codex"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class WorkerState:
    """Snapshot of a single fleet worker's health and metadata.

    Attributes:
        pane_id: tmux-style pane identifier (e.g. ``%1``).
        label: Human-readable panel label (e.g. ``Worker1(Claude)``).
        ai_type: Which AI runtime is running in this pane.
        status: Current health status.
        last_active: Timestamp of the last detected output change.
        last_check: Timestamp of the most recent watchdog poll.
        stuck_since: When the worker first appeared stuck, or ``None``.
        recovery_attempts: Cumulative recovery attempts since last healthy state.
        current_task: Free-text description of what the worker is doing.
    """

    pane_id: str
    label: str
    ai_type: AIType
    status: WorkerStatus
    last_active: datetime
    last_check: datetime
    stuck_since: datetime | None = None
    recovery_attempts: int = 0
    current_task: str = ""


@dataclass
class RecoveryAction:
    """Record of a single recovery attempt against a worker.

    Attributes:
        worker: The worker state at the time recovery was triggered.
        tier: Which escalation tier was chosen.
        reason: Human-readable explanation of why recovery was triggered.
        timestamp: When the recovery action was created.
        success: Outcome -- ``True`` if the worker recovered, ``False`` if
            it failed, or ``None`` if the action has not been executed yet.
    """

    worker: WorkerState
    tier: RecoveryTier
    reason: str
    timestamp: datetime
    success: bool | None = None


@dataclass
class WatchdogEvent:
    """Structured event emitted by the watchdog for logging and dashboard.

    Attributes:
        event_type: Category tag such as ``"detection"``, ``"recovery"``,
            or ``"escalation"``.
        worker_label: Label of the worker this event pertains to.
        detail: Free-text description of what happened.
        timestamp: When the event occurred.
    """

    event_type: str
    worker_label: str
    detail: str
    timestamp: datetime

    def to_dict(self) -> dict:
        """Serialize the event to a plain dict suitable for JSON output.

        Returns:
            A dictionary with all fields converted to JSON-safe types.
            The ``timestamp`` is formatted as an ISO-8601 string.
        """
        return {
            "event_type": self.event_type,
            "worker_label": self.worker_label,
            "detail": self.detail,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class WatchdogConfig:
    """Tunable parameters for the watchdog loop.

    Attributes:
        check_interval: Seconds between successive health polls.
        idle_timeout: Seconds of no output before a worker is marked IDLE.
        stuck_timeout: Seconds of no output before a worker is marked STUCK.
        max_retries: Maximum RETRY-tier attempts before escalating to RESTART.
        log_file: Path to the JSONL event log (relative to repo root).
    """

    check_interval: int = 10
    idle_timeout: int = 300
    stuck_timeout: int = 120
    max_retries: int = 3
    log_file: str = "javis/watchdog/events.jsonl"
    stop_file: str = "javis/watchdog/.stop"

    @classmethod
    def from_dict(cls, data: dict) -> WatchdogConfig:
        """Create a config from a dictionary, ignoring unknown keys."""
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in valid})
