"""Tests for the detector module with mocked subprocess calls."""
from __future__ import annotations

import subprocess
from unittest.mock import patch, MagicMock

import pytest

from javis.watchdog.detector import WorkerDetector, _strip_ansi
from javis.watchdog.models import AIType, WatchdogConfig, WorkerStatus


@pytest.fixture
def detector(config):
    return WorkerDetector(config)


class TestClassifyStatus:
    """Tests for WorkerDetector._classify_status."""

    def test_classify_status_live(self, detector):
        """Content containing 'thinking' should be classified as LIVE."""
        content = "Some output\n> thinking about the problem..."
        status = detector._classify_status(content, prev=None)
        assert status == WorkerStatus.LIVE

    def test_classify_status_idle(self, detector):
        """Content ending with a shell prompt '$ ' should be classified as IDLE."""
        content = "Previous output\n$ "
        status = detector._classify_status(content, prev=None)
        assert status == WorkerStatus.IDLE

    def test_classify_status_dead(self, detector):
        """Empty content should be classified as DEAD."""
        content = ""
        status = detector._classify_status(content, prev=None)
        assert status == WorkerStatus.DEAD

    def test_classify_status_dead_whitespace(self, detector):
        """Whitespace-only content should be classified as DEAD."""
        content = "   \n\n  "
        status = detector._classify_status(content, prev=None)
        assert status == WorkerStatus.DEAD


class TestDetectAIType:
    """Tests for WorkerDetector._detect_ai_type."""

    def test_detect_ai_type_from_label(self, detector):
        """Label 'Worker1(Claude)' should detect AIType.CLAUDE."""
        ai_type = detector._detect_ai_type("some content", "Worker1(Claude)")
        assert ai_type == AIType.CLAUDE

    def test_detect_ai_type_agy(self, detector):
        """Label 'Worker2(AGY)' should detect AIType.AGY."""
        ai_type = detector._detect_ai_type("some content", "Worker2(AGY)")
        assert ai_type == AIType.AGY

    def test_detect_ai_type_codex_from_label(self, detector):
        """Label 'Worker3(Codex)' should detect AIType.CODEX."""
        ai_type = detector._detect_ai_type("some content", "Worker3(Codex)")
        assert ai_type == AIType.CODEX

    def test_detect_ai_type_from_content_fallback(self, detector):
        """When label has no AI hint, content keywords should be used."""
        ai_type = detector._detect_ai_type("anthropic claude code", "SomePane")
        assert ai_type == AIType.CLAUDE

    def test_detect_ai_type_unknown(self, detector):
        """No AI hints in label or content should return UNKNOWN."""
        ai_type = detector._detect_ai_type("hello world", "GenericPane")
        assert ai_type == AIType.UNKNOWN


class TestReadPane:
    """Tests for WorkerDetector._read_pane with mocked subprocess."""

    @patch("javis.watchdog.detector.subprocess.run")
    def test_read_pane_failure(self, mock_run, detector):
        """When subprocess raises an exception, _read_pane returns None."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="tmux", timeout=5)
        result = detector._read_pane("%99")
        assert result is None

    @patch("javis.watchdog.detector.subprocess.run")
    def test_read_pane_nonzero_returncode(self, mock_run, detector):
        """Non-zero return code should yield None."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        result = detector._read_pane("%99")
        assert result is None

    @patch("javis.watchdog.detector.subprocess.run")
    def test_read_pane_success(self, mock_run, detector):
        """Successful capture should return cleaned content."""
        mock_run.return_value = MagicMock(returncode=0, stdout="hello world\n")
        result = detector._read_pane("%1")
        assert result is not None
        assert "hello world" in result


class TestStripAnsi:
    """Tests for the _strip_ansi utility function."""

    def test_strip_ansi(self):
        """ANSI escape codes should be removed from the output."""
        raw = "\x1b[32mGreen text\x1b[0m and \x1b[1;34mBold Blue\x1b[0m"
        cleaned = _strip_ansi(raw)
        assert "\x1b" not in cleaned
        assert "Green text" in cleaned
        assert "Bold Blue" in cleaned

    def test_strip_ansi_carriage_return(self):
        """Carriage returns should also be stripped."""
        raw = "line one\rline two\r\n"
        cleaned = _strip_ansi(raw)
        assert "\r" not in cleaned

    def test_strip_ansi_plain_text(self):
        """Plain text without escapes should pass through unchanged."""
        raw = "No special characters here"
        cleaned = _strip_ansi(raw)
        assert cleaned == raw


# -----------------------------------------------------------------------
# RSI Round 2: deeper detector coverage
# -----------------------------------------------------------------------


class TestDetectOne:
    """Tests for WorkerDetector.detect_one (full flow)."""

    @patch("javis.watchdog.detector.subprocess.run")
    def test_detect_one_live_worker(self, mock_run, detector):
        """detect_one should return LIVE when pane shows active keywords."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="processing your request\n"
        )
        state = detector.detect_one("%2", label="Worker1(Claude)")
        assert state.status == WorkerStatus.LIVE
        assert state.pane_id == "%2"
        assert state.label == "Worker1(Claude)"
        assert state.ai_type == AIType.CLAUDE

    @patch("javis.watchdog.detector.subprocess.run")
    def test_detect_one_dead_pane(self, mock_run, detector):
        """detect_one should return DEAD when read_pane returns None."""
        mock_run.side_effect = FileNotFoundError("tmux not found")
        state = detector.detect_one("%99", label="DeadPane")
        assert state.status == WorkerStatus.DEAD

    @patch("javis.watchdog.detector.subprocess.run")
    def test_detect_one_idle_worker(self, mock_run, detector):
        """detect_one should return IDLE for shell prompt content."""
        mock_run.return_value = MagicMock(returncode=0, stdout="$ ")
        state = detector.detect_one("%3", label="Worker2(AGY)")
        assert state.status == WorkerStatus.IDLE

    @patch("javis.watchdog.detector.subprocess.run")
    def test_detect_one_preserves_recovery_attempts(self, mock_run, detector):
        """Successive detect_one calls should preserve recovery_attempts from prev state."""
        mock_run.return_value = MagicMock(returncode=0, stdout="$ ")
        # First call establishes state
        state1 = detector.detect_one("%2", label="W1")
        assert state1.recovery_attempts == 0
        # Manually set recovery_attempts on the stored prev state
        detector._prev_states["%2"].recovery_attempts = 3
        # Second call should carry forward
        state2 = detector.detect_one("%2", label="W1")
        assert state2.recovery_attempts == 3


class TestDetectAll:
    """Tests for WorkerDetector.detect_all with mocked _list_panes."""

    @patch("javis.watchdog.detector.subprocess.run")
    def test_detect_all_returns_all_panes(self, mock_run, detector):
        """detect_all should return one WorkerState per discovered pane."""
        # First call = list-panes, subsequent calls = capture-pane
        list_result = MagicMock(
            returncode=0, stdout="%1\tMaster\n%2\tWorker1(Claude)\n"
        )
        capture_result = MagicMock(returncode=0, stdout="thinking...\n")
        mock_run.side_effect = [list_result, capture_result, capture_result]

        states = detector.detect_all()
        assert len(states) == 2
        assert states[0].pane_id == "%1"
        assert states[1].pane_id == "%2"

    @patch("javis.watchdog.detector.subprocess.run")
    def test_detect_all_empty_on_failure(self, mock_run, detector):
        """detect_all should return empty list when tmux list-panes fails."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="err")
        states = detector.detect_all()
        assert states == []


class TestUpdateHash:
    """Tests for WorkerDetector._update_hash content tracking."""

    def test_new_content_creates_entry(self, detector):
        """First content for a pane should create a hash entry."""
        detector._update_hash("%5", "hello world")
        assert "%5" in detector._hash_history
        h, ts = detector._hash_history["%5"]
        assert isinstance(h, str)
        assert isinstance(ts, float)

    def test_same_content_keeps_timestamp(self, detector):
        """Identical content should not update the timestamp."""
        detector._update_hash("%5", "same content")
        _, ts1 = detector._hash_history["%5"]
        import time; time.sleep(0.01)
        detector._update_hash("%5", "same content")
        _, ts2 = detector._hash_history["%5"]
        assert ts1 == ts2

    def test_different_content_updates_timestamp(self, detector):
        """Changed content should update both hash and timestamp."""
        detector._update_hash("%5", "content A")
        h1, ts1 = detector._hash_history["%5"]
        import time; time.sleep(0.01)
        detector._update_hash("%5", "content B")
        h2, ts2 = detector._hash_history["%5"]
        assert h1 != h2
        assert ts2 >= ts1


class TestLastActiveTime:
    """Tests for WorkerDetector._last_active_time."""

    def test_returns_fallback_when_no_history(self, detector):
        """Should return fallback datetime when pane has no hash history."""
        from datetime import datetime
        fallback = datetime(2026, 1, 1)
        result = detector._last_active_time("%99", fallback)
        assert result == fallback

    def test_returns_timestamp_from_history(self, detector):
        """Should return datetime from hash history when available."""
        from datetime import datetime
        import time as _time
        now = _time.time()
        detector._hash_history["%5"] = ("abc123", now)
        result = detector._last_active_time("%5", datetime(2026, 1, 1))
        assert result == datetime.fromtimestamp(now)


class TestStuckSince:
    """Tests for WorkerDetector._stuck_since."""

    def test_not_stuck_returns_none(self, detector):
        """Non-STUCK status should return None."""
        result = detector._stuck_since("%2", WorkerStatus.LIVE, prev=None)
        assert result is None

    def test_stuck_with_prev_stuck_since(self, detector):
        """STUCK status with existing stuck_since should preserve it."""
        from datetime import datetime
        prev = MagicMock()
        prev.stuck_since = datetime(2026, 6, 1, 12, 0)
        result = detector._stuck_since("%2", WorkerStatus.STUCK, prev=prev)
        assert result == datetime(2026, 6, 1, 12, 0)

    def test_stuck_without_prev_uses_hash_history(self, detector):
        """STUCK without prev.stuck_since should use hash history timestamp."""
        from datetime import datetime
        import time as _time
        now = _time.time()
        detector._hash_history["%2"] = ("abc", now)
        prev = MagicMock()
        prev.stuck_since = None
        result = detector._stuck_since("%2", WorkerStatus.STUCK, prev=prev)
        assert result == datetime.fromtimestamp(now)

    def test_stuck_without_any_history(self, detector):
        """STUCK without prev or hash history should return ~now."""
        from datetime import datetime
        prev = MagicMock()
        prev.stuck_since = None
        result = detector._stuck_since("%99", WorkerStatus.STUCK, prev=prev)
        assert isinstance(result, datetime)


class TestListPanes:
    """Tests for WorkerDetector._list_panes."""

    @patch("javis.watchdog.detector.subprocess.run")
    def test_list_panes_success(self, mock_run, detector):
        """Should parse tmux list-panes output into (pane_id, label) tuples."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="%0\tMaster\n%1\tCSO\n%2\tWorker1(Claude)\n"
        )
        panes = detector._list_panes()
        assert len(panes) == 3
        assert panes[0] == ("%0", "Master")
        assert panes[2] == ("%2", "Worker1(Claude)")

    @patch("javis.watchdog.detector.subprocess.run")
    def test_list_panes_failure(self, mock_run, detector):
        """Should return empty list when tmux command fails."""
        mock_run.side_effect = FileNotFoundError
        panes = detector._list_panes()
        assert panes == []

    @patch("javis.watchdog.detector.subprocess.run")
    def test_list_panes_nonzero_rc(self, mock_run, detector):
        """Should return empty list on non-zero return code."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="err")
        panes = detector._list_panes()
        assert panes == []


class TestClassifyStatusStuck:
    """Test stuck detection path in _classify_status."""

    def test_stuck_when_hash_unchanged_beyond_timeout(self, detector):
        """Content unchanged beyond stuck_timeout should be classified STUCK."""
        import time as _time
        from javis.watchdog.models import WorkerState
        from datetime import datetime

        # Set up prev state and hash history with old timestamp
        prev = WorkerState(
            pane_id="%2", label="W1", ai_type=AIType.CLAUDE,
            status=WorkerStatus.IDLE, last_active=datetime.now(),
            last_check=datetime.now(),
        )
        old_ts = _time.time() - (detector._config.stuck_timeout + 10)
        detector._hash_history["%2"] = ("stale_hash", old_ts)

        # Content has no live/idle keywords, hash unchanged beyond timeout
        content = "some random output that is not a keyword"
        status = detector._classify_status(content, prev)
        assert status == WorkerStatus.STUCK
