"""Tests for the strategy module."""
from __future__ import annotations

import pytest
from datetime import datetime

from javis.watchdog.strategy import RecoveryStrategy
from javis.watchdog.models import (
    AIType, RecoveryTier, WatchdogConfig, WorkerState, WorkerStatus,
)


@pytest.fixture
def strategy(config):
    return RecoveryStrategy(config)


def _make_worker(
    status: WorkerStatus,
    recovery_attempts: int = 0,
    **kwargs,
) -> WorkerState:
    """Helper to construct a WorkerState with defaults."""
    defaults = dict(
        pane_id="%2",
        label="TestWorker",
        ai_type=AIType.CLAUDE,
        status=status,
        last_active=datetime.now(),
        last_check=datetime.now(),
        recovery_attempts=recovery_attempts,
    )
    defaults.update(kwargs)
    return WorkerState(**defaults)


class TestRecoveryDecisions:
    """Tests for RecoveryStrategy.evaluate."""

    def test_no_recovery_for_live(self, strategy):
        """LIVE worker should not trigger any recovery action."""
        worker = _make_worker(WorkerStatus.LIVE)
        action = strategy.evaluate(worker)
        assert action is None

    def test_no_recovery_for_idle(self, strategy):
        """IDLE worker should not trigger any recovery action."""
        worker = _make_worker(WorkerStatus.IDLE)
        action = strategy.evaluate(worker)
        assert action is None

    def test_retry_for_stuck(self, strategy):
        """STUCK worker with 0 attempts should get RETRY tier."""
        worker = _make_worker(
            WorkerStatus.STUCK,
            recovery_attempts=0,
            stuck_since=datetime.now(),
        )
        action = strategy.evaluate(worker)
        assert action is not None
        assert action.tier == RecoveryTier.RETRY

    def test_restart_after_max_retries(self, strategy, config):
        """STUCK worker at max_retries should escalate to RESTART."""
        worker = _make_worker(
            WorkerStatus.STUCK,
            recovery_attempts=config.max_retries,
            stuck_since=datetime.now(),
        )
        action = strategy.evaluate(worker)
        assert action is not None
        assert action.tier == RecoveryTier.RESTART

    def test_restart_for_dead(self, strategy):
        """DEAD worker with low attempts should get RESTART tier."""
        worker = _make_worker(WorkerStatus.DEAD, recovery_attempts=0)
        action = strategy.evaluate(worker)
        assert action is not None
        assert action.tier == RecoveryTier.RESTART

    def test_escalate_after_restart(self, strategy, config):
        """DEAD worker with attempts > max_retries should ESCALATE."""
        worker = _make_worker(
            WorkerStatus.DEAD,
            recovery_attempts=config.max_retries + 1,
        )
        action = strategy.evaluate(worker)
        assert action is not None
        assert action.tier == RecoveryTier.ESCALATE

    def test_no_recovery_for_unknown(self, strategy):
        """UNKNOWN status should not trigger recovery."""
        worker = _make_worker(WorkerStatus.UNKNOWN)
        action = strategy.evaluate(worker)
        assert action is None

    def test_reason_contains_label(self, strategy):
        """Recovery reason string should mention the worker label."""
        worker = _make_worker(
            WorkerStatus.STUCK,
            recovery_attempts=0,
            label="Worker2(AGY)",
            stuck_since=datetime.now(),
        )
        action = strategy.evaluate(worker)
        assert action is not None
        assert "Worker2(AGY)" in action.reason
