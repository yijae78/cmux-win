"""Tests for the config module.

RSI Round 1: covers env-var overrides, YAML loading, load_config integration.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from javis.watchdog.config import (
    DEFAULT_CONFIG,
    _overrides_from_env,
    _overrides_from_yaml,
    load_config,
)
from javis.watchdog.models import WatchdogConfig


class TestDefaultConfig:
    """Verify default configuration values."""

    def test_default_config_is_watchdog_config(self):
        assert isinstance(DEFAULT_CONFIG, WatchdogConfig)

    def test_default_values(self):
        assert DEFAULT_CONFIG.check_interval == 10
        assert DEFAULT_CONFIG.idle_timeout == 300
        assert DEFAULT_CONFIG.stuck_timeout == 120
        assert DEFAULT_CONFIG.max_retries == 3


class TestOverridesFromEnv:
    """Test _overrides_from_env with various env-var combinations."""

    def test_no_env_vars_returns_empty(self):
        with patch.dict(os.environ, {}, clear=True):
            result = _overrides_from_env()
            assert result == {}

    def test_single_env_var_override(self):
        with patch.dict(os.environ, {"WATCHDOG_CHECK_INTERVAL": "5"}, clear=True):
            result = _overrides_from_env()
            assert result == {"check_interval": 5}

    def test_multiple_env_vars(self):
        env = {
            "WATCHDOG_CHECK_INTERVAL": "15",
            "WATCHDOG_MAX_RETRIES": "5",
            "WATCHDOG_LOG_FILE": "/tmp/test.jsonl",
        }
        with patch.dict(os.environ, env, clear=True):
            result = _overrides_from_env()
            assert result["check_interval"] == 15
            assert result["max_retries"] == 5
            assert result["log_file"] == "/tmp/test.jsonl"

    def test_malformed_int_skipped(self):
        with patch.dict(os.environ, {"WATCHDOG_CHECK_INTERVAL": "not_a_number"}, clear=True):
            result = _overrides_from_env()
            assert "check_interval" not in result

    def test_string_type_accepted(self):
        with patch.dict(os.environ, {"WATCHDOG_LOG_FILE": "custom.log"}, clear=True):
            result = _overrides_from_env()
            assert result == {"log_file": "custom.log"}


class TestOverridesFromYaml:
    """Test _overrides_from_yaml with real temp files."""

    def test_nonexistent_file_returns_empty(self):
        result = _overrides_from_yaml("/nonexistent/path.yaml")
        assert result == {}

    def test_valid_yaml_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write("check_interval: 30\nmax_retries: 7\n")
            f.flush()
            path = f.name

        try:
            import yaml  # noqa: F401
            result = _overrides_from_yaml(path)
            assert result.get("check_interval") == 30
            assert result.get("max_retries") == 7
        except ImportError:
            # pyyaml not installed — function should return empty
            result = _overrides_from_yaml(path)
            assert result == {}
        finally:
            os.unlink(path)

    def test_yaml_with_invalid_keys_filtered(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write("check_interval: 20\nbogus_key: 999\n")
            f.flush()
            path = f.name

        try:
            import yaml  # noqa: F401
            result = _overrides_from_yaml(path)
            assert "bogus_key" not in result
            assert result.get("check_interval") == 20
        except ImportError:
            result = _overrides_from_yaml(path)
            assert result == {}
        finally:
            os.unlink(path)

    def test_yaml_non_dict_returns_empty(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write("- item1\n- item2\n")
            f.flush()
            path = f.name

        try:
            import yaml  # noqa: F401
            result = _overrides_from_yaml(path)
            assert result == {}
        except ImportError:
            pass
        finally:
            os.unlink(path)


class TestLoadConfig:
    """Integration tests for load_config."""

    def test_load_config_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            # Remove WATCHDOG_CONFIG_FILE if set
            os.environ.pop("WATCHDOG_CONFIG_FILE", None)
            config = load_config()
            assert config.check_interval == DEFAULT_CONFIG.check_interval

    def test_load_config_with_env_override(self):
        env = {"WATCHDOG_STUCK_TIMEOUT": "60"}
        with patch.dict(os.environ, env, clear=True):
            config = load_config()
            assert config.stuck_timeout == 60

    def test_env_overrides_yaml(self):
        """Env vars should take priority over YAML file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write("check_interval: 99\n")
            f.flush()
            yaml_path = f.name

        try:
            import yaml  # noqa: F401
            env = {
                "WATCHDOG_CONFIG_FILE": yaml_path,
                "WATCHDOG_CHECK_INTERVAL": "7",
            }
            with patch.dict(os.environ, env, clear=True):
                config = load_config()
                # env var (7) should win over yaml (99)
                assert config.check_interval == 7
        except ImportError:
            pass
        finally:
            os.unlink(yaml_path)
