"""Watchdog configuration with sensible defaults.

Provides a default ``WatchdogConfig`` instance and a ``load_config``
helper that optionally overrides defaults from environment variables
or a YAML file.

Environment variable mapping (all optional):

* ``WATCHDOG_CHECK_INTERVAL`` → ``check_interval``
* ``WATCHDOG_IDLE_TIMEOUT``   → ``idle_timeout``
* ``WATCHDOG_STUCK_TIMEOUT``  → ``stuck_timeout``
* ``WATCHDOG_MAX_RETRIES``    → ``max_retries``
* ``WATCHDOG_LOG_FILE``       → ``log_file``
* ``WATCHDOG_CONFIG_FILE``    → path to a YAML override file

Requires Python 3.10+.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .models import WatchdogConfig

DEFAULT_CONFIG = WatchdogConfig()

# Maps env-var names → (WatchdogConfig field name, type converter).
_ENV_MAP: dict[str, tuple[str, type]] = {
    "WATCHDOG_CHECK_INTERVAL": ("check_interval", int),
    "WATCHDOG_IDLE_TIMEOUT": ("idle_timeout", int),
    "WATCHDOG_STUCK_TIMEOUT": ("stuck_timeout", int),
    "WATCHDOG_MAX_RETRIES": ("max_retries", int),
    "WATCHDOG_LOG_FILE": ("log_file", str),
}


def _overrides_from_env() -> dict[str, Any]:
    """Collect config overrides from environment variables.

    Returns:
        A dict of field-name → converted-value for every env var that
        is set and passes type conversion.
    """
    overrides: dict[str, Any] = {}
    for env_key, (field_name, converter) in _ENV_MAP.items():
        raw = os.environ.get(env_key)
        if raw is not None:
            try:
                overrides[field_name] = converter(raw)
            except (ValueError, TypeError):
                # Silently skip malformed values; defaults remain.
                pass
    return overrides


def _overrides_from_yaml(path: str | Path) -> dict[str, Any]:
    """Load config overrides from a YAML file.

    Args:
        path: Filesystem path to the YAML config file.

    Returns:
        A dict of field-name → value.  Returns an empty dict if the
        file does not exist or ``pyyaml`` is not installed.
    """
    filepath = Path(path)
    if not filepath.is_file():
        return {}

    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return {}

    with open(filepath, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if not isinstance(data, dict):
        return {}

    # Only accept keys that match WatchdogConfig fields.
    valid_fields = {f.name for f in WatchdogConfig.__dataclass_fields__.values()}
    return {k: v for k, v in data.items() if k in valid_fields}


def load_config() -> WatchdogConfig:
    """Load watchdog configuration with optional overrides.

    Resolution order (later wins):
        1. Built-in defaults (``DEFAULT_CONFIG``).
        2. YAML file pointed to by ``WATCHDOG_CONFIG_FILE`` env var.
        3. Individual ``WATCHDOG_*`` environment variables.

    Returns:
        A fully-resolved ``WatchdogConfig`` instance.
    """
    overrides: dict[str, Any] = {}

    # Layer 1: YAML file (if specified).
    yaml_path = os.environ.get("WATCHDOG_CONFIG_FILE")
    if yaml_path:
        overrides.update(_overrides_from_yaml(yaml_path))

    # Layer 2: Environment variables (highest priority).
    overrides.update(_overrides_from_env())

    if not overrides:
        return DEFAULT_CONFIG

    # Build a new config by merging defaults with overrides.
    defaults = {
        "check_interval": DEFAULT_CONFIG.check_interval,
        "idle_timeout": DEFAULT_CONFIG.idle_timeout,
        "stuck_timeout": DEFAULT_CONFIG.stuck_timeout,
        "max_retries": DEFAULT_CONFIG.max_retries,
        "log_file": DEFAULT_CONFIG.log_file,
    }
    defaults.update(overrides)
    return WatchdogConfig(**defaults)
