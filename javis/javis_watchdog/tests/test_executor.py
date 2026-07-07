"""Tests for the executor module with mocked subprocess."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch, MagicMock, call

import pytest

from javis.watchdog.executor import RecoveryExecutor
from javis.watchdog.models import (
    AIType, RecoveryAction, RecoveryTier, WatchdogConfig, WorkerState, WorkerStatus,
)


@pytest.fixture
def executor(config):
    return RecoveryExecutor(config)


def _make_worker(
    ai_type: AIType = AIType.CLAUDE,
    pane_id: str = "%2",
    label: str = "Worker1(Claude)",
    recovery_attempts: int = 0,
) -> WorkerState:
    """Helper to construct a WorkerState with defaults."""
    return WorkerState(
        pane_id=pane_id,
        label=label,
        ai_type=ai_type,
        status=WorkerStatus.STUCK,
        last_active=datetime.now(),
        last_check=datetime.now(),
        recovery_attempts=recovery_attempts,
    )


def _make_action(
    worker: WorkerState,
    tier: RecoveryTier,
) -> RecoveryAction:
    """Helper to construct a RecoveryAction."""
    return RecoveryAction(
        worker=worker,
        tier=tier,
        reason=f"Test {tier.value}",
        timestamp=datetime.now(),
    )


class TestRetry:
    """Tests for the RETRY recovery tier."""

    @patch("javis.watchdog.executor.subprocess.run")
    @patch("javis.watchdog.executor.time.sleep")
    def test_retry_sends_ctrl_c(self, mock_sleep, mock_run, executor):
        """RETRY should send Ctrl+C via tmux send-keys."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        worker = _make_worker()
        action = _make_action(worker, RecoveryTier.RETRY)

        result = executor.execute(action)

        assert result is True
        assert action.success is True
        # Verify tmux send-keys was called with C-c
        mock_run.assert_called_once()
        cmd_args = mock_run.call_args[0][0]
        assert "send-keys" in cmd_args
        assert "C-c C-c" in cmd_args


class TestRestart:
    """Tests for the RESTART recovery tier."""

    @patch("javis.watchdog.executor.subprocess.run")
    @patch("javis.watchdog.executor.time.sleep")
    def test_restart_sends_cli_command(self, mock_sleep, mock_run, executor):
        """RESTART should send Ctrl+C then launch the correct CLI command."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        worker = _make_worker(ai_type=AIType.AGY, label="Worker2(AGY)", pane_id="%3")
        action = _make_action(worker, RecoveryTier.RESTART)

        result = executor.execute(action)

        assert result is True
        assert action.success is True
        # Should have been called twice: once for Ctrl+C, once for CLI command
        assert mock_run.call_count == 2
        # Second call should contain the "agy" command
        second_call_args = mock_run.call_args_list[1][0][0]
        assert "send-keys" in second_call_args

    @patch("javis.watchdog.executor.subprocess.run")
    @patch("javis.watchdog.executor.time.sleep")
    def test_restart_fails_on_ctrl_c_error(self, mock_sleep, mock_run, executor):
        """RESTART should fail if the initial Ctrl+C fails."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        worker = _make_worker()
        action = _make_action(worker, RecoveryTier.RESTART)

        result = executor.execute(action)

        assert result is False
        assert action.success is False


class TestEscalate:
    """Tests for the ESCALATE recovery tier."""

    @patch("javis.watchdog.executor.subprocess.run")
    @patch("javis.watchdog.executor.time.sleep")
    def test_escalate_sends_alert(self, mock_sleep, mock_run, executor):
        """ESCALATE should send an alert message to pane %0 (master)."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        worker = _make_worker(recovery_attempts=5)
        action = _make_action(worker, RecoveryTier.ESCALATE)

        result = executor.execute(action)

        assert result is True
        assert action.success is True
        # Should target pane %0
        cmd_args = mock_run.call_args[0][0]
        assert "%0" in cmd_args
        assert "send-keys" in cmd_args


class TestGetCliCommand:
    """Tests for RecoveryExecutor._get_cli_command."""

    def test_get_cli_command_claude(self, executor):
        """AIType.CLAUDE should return the claude CLI command."""
        cmd = executor._get_cli_command(AIType.CLAUDE)
        assert "claude" in cmd
        assert "--dangerously-skip-permissions" in cmd

    def test_get_cli_command_agy(self, executor):
        """AIType.AGY should return 'agy'."""
        cmd = executor._get_cli_command(AIType.AGY)
        assert cmd == "agy"

    def test_get_cli_command_codex(self, executor):
        """AIType.CODEX should return the codex CLI command."""
        cmd = executor._get_cli_command(AIType.CODEX)
        assert "codex" in cmd

    def test_get_cli_command_unknown(self, executor):
        """AIType.UNKNOWN should return a fallback echo command."""
        cmd = executor._get_cli_command(AIType.UNKNOWN)
        assert "unknown" in cmd.lower()


# -----------------------------------------------------------------------
# RSI Round 3: executor edge cases
# -----------------------------------------------------------------------


class TestSendKeysEdgeCases:
    """Test _send_keys with timeout and FileNotFoundError."""

    @patch("javis.watchdog.executor.subprocess.run")
    def test_send_keys_timeout(self, mock_run, executor):
        """TimeoutExpired should make _send_keys return False."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="tmux", timeout=10)
        result = executor._send_keys("%1", "C-c")
        assert result is False

    @patch("javis.watchdog.executor.subprocess.run")
    def test_send_keys_file_not_found(self, mock_run, executor):
        """FileNotFoundError (no tmux binary) should return False."""
        mock_run.side_effect = FileNotFoundError("tmux not found")
        result = executor._send_keys("%1", "C-c")
        assert result is False

    @patch("javis.watchdog.executor.subprocess.run")
    def test_send_keys_nonzero_rc(self, mock_run, executor):
        """Non-zero return code should return False."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="pane not found")
        result = executor._send_keys("%99", "C-c")
        assert result is False

    @patch("javis.watchdog.executor.subprocess.run")
    def test_send_keys_success(self, mock_run, executor):
        """Successful send-keys should return True."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = executor._send_keys("%1", "echo hello Enter")
        assert result is True


class TestExecuteUnknownTier:
    """Test execute() with an invalid/unrecognized tier."""

    @patch("javis.watchdog.executor.subprocess.run")
    def test_retry_send_keys_failure(self, mock_run, executor):
        """RETRY should return False when send-keys fails."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        worker = _make_worker()
        action = _make_action(worker, RecoveryTier.RETRY)
        result = executor.execute(action)
        assert result is False
        assert action.success is False

    @patch("javis.watchdog.executor.subprocess.run")
    @patch("javis.watchdog.executor.time.sleep")
    def test_restart_cli_launch_failure(self, mock_sleep, mock_run, executor):
        """RESTART should fail if CLI launch send-keys fails (but Ctrl+C succeeds)."""
        # First call (Ctrl+C) succeeds, second call (CLI launch) fails
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=1, stdout="", stderr="error"),
        ]
        worker = _make_worker()
        action = _make_action(worker, RecoveryTier.RESTART)
        result = executor.execute(action)
        assert result is False

    @patch("javis.watchdog.executor.subprocess.run")
    def test_escalate_failure(self, mock_run, executor):
        """ESCALATE should return False when master pane notification fails."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        worker = _make_worker(recovery_attempts=10)
        action = _make_action(worker, RecoveryTier.ESCALATE)
        result = executor.execute(action)
        assert result is False
