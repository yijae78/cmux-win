"""Integration tests for the orchestrator with mocked detector."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from javis.watchdog.orchestrator import Watchdog
from javis.watchdog.models import (
    AIType, WatchdogConfig, WatchdogEvent, WorkerState, WorkerStatus,
)


def _make_worker(
    pane_id: str = "%2",
    label: str = "Worker1(Claude)",
    status: WorkerStatus = WorkerStatus.LIVE,
    ai_type: AIType = AIType.CLAUDE,
    recovery_attempts: int = 0,
) -> WorkerState:
    """Helper to construct a WorkerState with defaults."""
    return WorkerState(
        pane_id=pane_id,
        label=label,
        ai_type=ai_type,
        status=status,
        last_active=datetime.now(),
        last_check=datetime.now(),
        recovery_attempts=recovery_attempts,
    )


class TestCheckCycle:
    """Tests for Watchdog._check_cycle with mocked components."""

    def test_check_cycle_no_issues(self, config):
        """When all workers are LIVE, no recovery actions should fire."""
        wd = Watchdog(config)
        workers = [
            _make_worker("%2", "Worker1(Claude)", WorkerStatus.LIVE, AIType.CLAUDE),
            _make_worker("%3", "Worker2(AGY)", WorkerStatus.LIVE, AIType.AGY),
            _make_worker("%4", "Worker3(Codex)", WorkerStatus.LIVE, AIType.CODEX),
        ]

        with patch.object(wd.detector, "detect_all", return_value=workers):
            events = wd._check_cycle()

        # Only detection events, no recovery events
        detection_events = [e for e in events if e.event_type == "detection"]
        recovery_events = [e for e in events if e.event_type == "recovery"]
        assert len(detection_events) == 3
        assert len(recovery_events) == 0

    def test_check_cycle_stuck_worker(self, config):
        """When one worker is STUCK, exactly one recovery action should fire."""
        wd = Watchdog(config)
        workers = [
            _make_worker("%2", "Worker1(Claude)", WorkerStatus.LIVE, AIType.CLAUDE),
            _make_worker(
                "%3", "Worker2(AGY)", WorkerStatus.STUCK, AIType.AGY,
            ),
        ]
        # Patch stuck_since on the stuck worker
        workers[1].stuck_since = datetime.now()

        with patch.object(wd.detector, "detect_all", return_value=workers), \
             patch.object(wd.executor, "execute", return_value=True):
            events = wd._check_cycle()

        detection_events = [e for e in events if e.event_type == "detection"]
        recovery_events = [e for e in events if e.event_type == "recovery"]
        assert len(detection_events) == 2
        assert len(recovery_events) == 1
        assert "Worker2(AGY)" in recovery_events[0].worker_label


class TestLogEvent:
    """Tests for Watchdog._log_event JSONL writing."""

    def test_log_event_writes_jsonl(self, config):
        """Logging an event should append a valid JSON line to the log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = str(Path(tmpdir) / "test_events.jsonl")
            config.log_file = log_path
            wd = Watchdog(config)

            event = WatchdogEvent(
                event_type="detection",
                worker_label="Worker1(Claude)",
                detail="status=live",
                timestamp=datetime.now(),
            )
            wd._log_event(event)

            # Verify the file was created and contains valid JSON
            log_file = Path(log_path)
            assert log_file.exists()
            lines = log_file.read_text(encoding="utf-8").strip().splitlines()
            assert len(lines) == 1
            data = json.loads(lines[0])
            assert data["event_type"] == "detection"
            assert data["worker_label"] == "Worker1(Claude)"
            assert data["detail"] == "status=live"
            assert "timestamp" in data

    def test_log_event_appends_multiple(self, config):
        """Multiple events should produce multiple JSON lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = str(Path(tmpdir) / "test_events.jsonl")
            config.log_file = log_path
            wd = Watchdog(config)

            for i in range(3):
                event = WatchdogEvent(
                    event_type="detection",
                    worker_label=f"Worker{i}",
                    detail=f"event #{i}",
                    timestamp=datetime.now(),
                )
                wd._log_event(event)

            lines = Path(log_path).read_text(encoding="utf-8").strip().splitlines()
            assert len(lines) == 3


class TestStatus:
    """Tests for Watchdog.status."""

    def test_status_returns_workers(self, config):
        """status() should return the list from detector.detect_all()."""
        wd = Watchdog(config)
        expected = [
            _make_worker("%2", "Worker1(Claude)", WorkerStatus.LIVE, AIType.CLAUDE),
            _make_worker("%3", "Worker2(AGY)", WorkerStatus.IDLE, AIType.AGY),
        ]

        with patch.object(wd.detector, "detect_all", return_value=expected):
            result = wd.status()

        assert len(result) == 2
        assert result[0].label == "Worker1(Claude)"
        assert result[0].status == WorkerStatus.LIVE
        assert result[1].label == "Worker2(AGY)"
        assert result[1].status == WorkerStatus.IDLE

    def test_status_returns_empty_when_no_panes(self, config):
        """status() should return an empty list when no panes are found."""
        wd = Watchdog(config)

        with patch.object(wd.detector, "detect_all", return_value=[]):
            result = wd.status()

        assert result == []


# -----------------------------------------------------------------------
# RSI Round 2: deeper orchestrator coverage
# -----------------------------------------------------------------------


class TestFormatCycleSummary:
    """Tests for Watchdog._format_cycle_summary."""

    def test_format_empty_events(self):
        """Empty event list should still produce a valid summary."""
        summary = Watchdog._format_cycle_summary([], 0.12)
        assert "workers=0" in summary
        assert "recoveries=0" in summary
        assert "0.12s" in summary

    def test_format_with_detections_and_recoveries(self):
        """Should count detections and recoveries separately."""
        events = [
            WatchdogEvent("detection", "W1", "status=live", datetime.now()),
            WatchdogEvent("detection", "W2", "status=stuck", datetime.now()),
            WatchdogEvent("recovery", "W2", "tier=retry", datetime.now()),
        ]
        summary = Watchdog._format_cycle_summary(events, 1.5)
        assert "workers=2" in summary
        assert "recoveries=1" in summary

    def test_format_includes_timestamp(self):
        """Summary should include a time stamp."""
        summary = Watchdog._format_cycle_summary([], 0.0)
        assert "[Watchdog" in summary


class TestExecuteAndLog:
    """Tests for Watchdog._execute_and_log."""

    def test_execute_and_log_success(self, config):
        """Successful recovery should produce a 'succeeded' event."""
        from javis.watchdog.models import RecoveryAction, RecoveryTier
        wd = Watchdog(config)
        worker = _make_worker()
        action = RecoveryAction(
            worker=worker,
            tier=RecoveryTier.RETRY,
            reason="stuck for 5m",
            timestamp=datetime.now(),
        )
        with patch.object(wd.executor, "execute", return_value=True):
            event = wd._execute_and_log(action, datetime.now())
        assert "succeeded" in event.detail
        assert event.event_type == "recovery"

    def test_execute_and_log_failure(self, config):
        """Failed recovery should produce a 'failed' event."""
        from javis.watchdog.models import RecoveryAction, RecoveryTier
        wd = Watchdog(config)
        worker = _make_worker()
        action = RecoveryAction(
            worker=worker,
            tier=RecoveryTier.RESTART,
            reason="dead",
            timestamp=datetime.now(),
        )
        with patch.object(wd.executor, "execute", return_value=False):
            event = wd._execute_and_log(action, datetime.now())
        assert "failed" in event.detail
        assert action.success is False


class TestLogEventErrors:
    """Test _log_event error handling."""

    def test_log_event_handles_oserror(self, config, capsys):
        """OSError during file write should be caught and printed."""
        wd = Watchdog(config)
        wd.config.log_file = "/nonexistent/deeply/nested/path/log.jsonl"
        event = WatchdogEvent("test", "W1", "detail", datetime.now())
        # On Windows, deeply nested nonexistent path may raise OSError
        # The method should catch it gracefully
        wd._log_event(event)  # should not raise


class TestStartStop:
    """Tests for start/stop lifecycle."""

    def test_stop_sets_running_false(self, config):
        """stop() should set _running to False."""
        wd = Watchdog(config)
        wd._running = True
        wd.stop()
        assert wd._running is False

    def test_start_calls_run_loop(self, config):
        """start() should set _running and call _run_loop."""
        wd = Watchdog(config)
        with patch.object(wd, "_run_loop") as mock_loop:
            wd.start()
            assert wd._running is True
            mock_loop.assert_called_once()
