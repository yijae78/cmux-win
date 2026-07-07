"""Recovery strategy engine for the Javis Fleet Watchdog.

Evaluates worker health snapshots and decides whether (and how) to
recover a worker, following a tiered escalation model:

    RETRY → RESTART → ESCALATE

Requires Python 3.10+.
"""

from __future__ import annotations

from datetime import datetime

from .models import (
    RecoveryAction,
    RecoveryTier,
    WatchdogConfig,
    WorkerState,
    WorkerStatus,
)


class RecoveryStrategy:
    """Decides what recovery action to take for a given worker state.

    Args:
        config: Watchdog tunable parameters (max_retries, etc.).
    """

    def __init__(self, config: WatchdogConfig) -> None:
        self._config = config

    def evaluate(self, worker: WorkerState) -> RecoveryAction | None:
        """Evaluate a worker and return a recovery action if needed.

        Args:
            worker: The current snapshot of the worker's health.

        Returns:
            A ``RecoveryAction`` describing what to do, or ``None`` if the
            worker is healthy and no intervention is required.
        """
        if not self._should_recover(worker):
            return None

        tier = self._select_tier(worker)
        reason = self._build_reason(worker, tier)

        return RecoveryAction(
            worker=worker,
            tier=tier,
            reason=reason,
            timestamp=datetime.now(),
        )

    def _should_recover(self, worker: WorkerState) -> bool:
        """Determine whether the worker needs recovery.

        Args:
            worker: The current snapshot of the worker's health.

        Returns:
            ``True`` if the worker's status is STUCK or DEAD.
        """
        return worker.status in (WorkerStatus.STUCK, WorkerStatus.DEAD)

    def _select_tier(self, worker: WorkerState) -> RecoveryTier:
        """Choose the appropriate escalation tier for recovery.

        Tier selection logic:
            - STUCK with attempts < max_retries → RETRY (soft nudge).
            - STUCK with attempts >= max_retries → RESTART (hard recovery).
            - DEAD → RESTART (process is gone, must relaunch).
            - If a RESTART has already been attempted (attempts > max_retries)
              → ESCALATE (notify master).

        Args:
            worker: The current snapshot of the worker's health.

        Returns:
            The selected ``RecoveryTier``.
        """
        max_retries = self._config.max_retries

        if worker.status == WorkerStatus.DEAD:
            if worker.recovery_attempts > max_retries:
                return RecoveryTier.ESCALATE
            return RecoveryTier.RESTART

        # WorkerStatus.STUCK
        if worker.recovery_attempts < max_retries:
            return RecoveryTier.RETRY
        if worker.recovery_attempts == max_retries:
            return RecoveryTier.RESTART
        return RecoveryTier.ESCALATE

    def _build_reason(self, worker: WorkerState, tier: RecoveryTier) -> str:
        """Compose a human-readable reason string for the recovery action.

        Args:
            worker: The worker being recovered.
            tier: The chosen escalation tier.

        Returns:
            A concise explanation of why recovery was triggered.
        """
        status = worker.status.value.upper()
        label = worker.label
        attempts = worker.recovery_attempts

        if tier == RecoveryTier.RETRY:
            return (
                f"{label} is {status} "
                f"(attempt {attempts + 1}/{self._config.max_retries}); "
                f"sending soft retry."
            )
        if tier == RecoveryTier.RESTART:
            return (
                f"{label} is {status} "
                f"after {attempts} retries; restarting process."
            )
        # ESCALATE
        return (
            f"{label} is {status} "
            f"after {attempts} recovery attempts; "
            f"escalating to master."
        )
