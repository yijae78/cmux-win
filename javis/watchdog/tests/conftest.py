"""Shared fixtures for watchdog tests."""
from __future__ import annotations
import pytest
from datetime import datetime
from javis.watchdog.models import (
    WorkerState, WorkerStatus, AIType, RecoveryAction,
    RecoveryTier, WatchdogConfig, WatchdogEvent,
)

@pytest.fixture
def config():
    return WatchdogConfig(check_interval=1, idle_timeout=10, stuck_timeout=5, max_retries=2)

@pytest.fixture
def live_worker():
    return WorkerState(
        pane_id="%2", label="Worker1(Claude)", ai_type=AIType.CLAUDE,
        status=WorkerStatus.LIVE, last_active=datetime.now(), last_check=datetime.now(),
    )

@pytest.fixture
def stuck_worker():
    return WorkerState(
        pane_id="%3", label="Worker2(AGY)", ai_type=AIType.AGY,
        status=WorkerStatus.STUCK, last_active=datetime.now(), last_check=datetime.now(),
        stuck_since=datetime.now(), recovery_attempts=0,
    )

@pytest.fixture
def dead_worker():
    return WorkerState(
        pane_id="%4", label="Worker3(Codex)", ai_type=AIType.CODEX,
        status=WorkerStatus.DEAD, last_active=datetime.now(), last_check=datetime.now(),
        recovery_attempts=3,
    )
