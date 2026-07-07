"""Tests for the CLI module (cli.py + __main__.py)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from javis.watchdog.cli import main
from javis.watchdog.config import WatchdogConfig


class TestCLIHelp:
    """Test --help and no-command behavior."""

    def test_no_command_raises_system_exit(self):
        with pytest.raises(SystemExit) as exc_info:
            main([])
        # argparse with required subparser exits with code 2
        assert exc_info.value.code == 2

    def test_help_flag(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0


class TestCLIStatus:
    """Test the 'status' subcommand."""

    @patch("javis.watchdog.cli.Orchestrator")
    def test_status_command(self, mock_orch_cls, capsys):
        mock_orch = MagicMock()
        mock_orch.get_status.return_value = {
            "running": False,
            "cycle_count": 0,
            "workers": []
        }
        mock_orch_cls.return_value = mock_orch

        rc = main(["status"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "running" in out
        mock_orch.get_status.assert_called_once()


class TestCLIStart:
    """Test the 'start' subcommand."""

    @patch("javis.watchdog.cli.Orchestrator")
    @patch("javis.watchdog.cli._load_config")
    def test_start_command(self, mock_load_config, mock_orch_cls):
        mock_orch = MagicMock()
        mock_orch_cls.return_value = mock_orch
        mock_config = WatchdogConfig()
        mock_load_config.return_value = mock_config

        rc = main(["start", "--config", "config.json", "--audit-dir", "audit_dir"])
        assert rc == 0
        mock_load_config.assert_called_once_with(Path("config.json"))
        mock_orch_cls.assert_called_once_with(config=mock_config, audit_dir=Path("audit_dir"))
        mock_orch.start.assert_called_once()


class TestCLIStop:
    """Test the 'stop' subcommand."""

    @patch("javis.watchdog.cli._load_config")
    @patch("javis.watchdog.cli.Path.write_text")
    @patch("javis.watchdog.cli.Path.mkdir")
    def test_stop_command(self, mock_mkdir, mock_write_text, mock_load_config, capsys):
        mock_config = MagicMock()
        mock_config.stop_file = "stop_file.stop"
        mock_load_config.return_value = mock_config


        rc = main(["stop"])
        assert rc == 0
        mock_mkdir.assert_called_once()
        mock_write_text.assert_called_once_with("stop")
        out = capsys.readouterr().out
        assert "Stop file created" in out


class TestMainModule:
    """Test __main__.py module entry point."""

    def test_main_module_calls_main(self):
        """__main__.py should invoke cli.main() and raise SystemExit."""
        with patch("javis.watchdog.cli.main", return_value=0):
            with pytest.raises(SystemExit) as exc_info:
                import importlib
                import javis.watchdog.__main__ as mod
                importlib.reload(mod)
            assert exc_info.value.code == 0
