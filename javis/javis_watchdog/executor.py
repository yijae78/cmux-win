"""Recovery action executor for the Javis Fleet Auto-Recovery Watchdog.

Translates ``RecoveryAction`` decisions into concrete tmux commands that
retry, restart, or escalate stuck/dead fleet workers.

Requires Python 3.10+ for ``X | None`` union syntax.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time

from .detector import _TMUX_CMD
from .models import (
    AIType,
    RecoveryAction,
    RecoveryTier,
    WatchdogConfig,
    WorkerState,
)

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stderr))
logger.setLevel(logging.INFO)

# Subprocess timeout for every tmux call (seconds).
_SUBPROCESS_TIMEOUT = 10


class RecoveryExecutor:
    """Executes recovery actions against fleet workers via tmux commands.

    Args:
        config: Watchdog configuration with tuning knobs.
    """

    def __init__(self, config: WatchdogConfig) -> None:
        self._config = config
        self._dispatch = {
            RecoveryTier.RETRY: self._retry,
            RecoveryTier.RESTART: self._restart,
            RecoveryTier.ESCALATE: self._escalate,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, action: RecoveryAction) -> bool:
        """Dispatch *action* to the appropriate recovery handler.

        Selects ``_retry``, ``_restart``, or ``_escalate`` based on
        ``action.tier``, executes it, and writes back the outcome.

        Args:
            action: The recovery action to execute.

        Returns:
            ``True`` if recovery succeeded, ``False`` otherwise.
        """
        handler = self._dispatch.get(action.tier)
        if handler is None:
            logger.error("Unknown recovery tier: %s", action.tier)
            action.success = False
            return False

        worker = action.worker
        logger.info(
            "[%s] Executing %s for %s (pane %s)",
            action.tier.value,
            action.tier.name,
            worker.label,
            worker.pane_id,
        )

        success = handler(worker)
        action.success = success
        return success

    # ------------------------------------------------------------------
    # Recovery handlers
    # ------------------------------------------------------------------

    def _retry(self, worker: WorkerState) -> bool:
        """Send Ctrl+C twice and wait for the worker to recover.

        Args:
            worker: The worker to nudge.

        Returns:
            ``True`` if the send-keys command succeeded.
        """
        logger.info(
            "[retry] Sending Ctrl+C x2 to %s (pane %s)",
            worker.label,
            worker.pane_id,
        )
        ok = self._send_keys(worker.pane_id, "C-c C-c")
        if not ok:
            logger.warning("[retry] send-keys failed for %s", worker.label)
            return False

        time.sleep(2)
        logger.info("[retry] Recovery nudge sent to %s", worker.label)
        return True

    def _restart(self, worker: WorkerState) -> bool:
        """Kill the current process and relaunch the AI CLI.

        Sends Ctrl+C twice, waits for the process to die, then issues the
        appropriate CLI command based on the worker's AI type.

        Args:
            worker: The worker to restart.

        Returns:
            ``True`` if all tmux commands succeeded.
        """
        pane = worker.pane_id
        label = worker.label

        logger.info("[restart] Killing process in %s (pane %s)", label, pane)
        if not self._send_keys(pane, "C-c C-c"):
            logger.warning("[restart] Ctrl+C failed for %s", label)
            return False

        time.sleep(2)

        cli_cmd = self._get_cli_command(worker.ai_type)
        logger.info(
            "[restart] Launching '%s' in %s (pane %s)", cli_cmd, label, pane,
        )
        if not self._send_keys(pane, f'"{cli_cmd}" Enter'):
            logger.warning("[restart] CLI launch failed for %s", label)
            return False

        time.sleep(5)
        logger.info("[restart] Worker %s restarted successfully", label)
        return True

    def _escalate(self, worker: WorkerState) -> bool:
        """Notify the master pane that a worker is unrecoverable.

        Sends an alert message to pane ``%0`` (the master pane) so the
        human operator can intervene.

        Args:
            worker: The worker that could not be recovered.

        Returns:
            ``True`` if the alert was delivered to the master pane.
        """
        msg = (
            f"WATCHDOG ALERT: {worker.label} unrecoverable "
            f"after {worker.recovery_attempts} attempts"
        )
        logger.warning("[escalate] %s", msg)

        ok = self._send_keys("%0", f'"{msg}" Enter')
        if not ok:
            logger.error("[escalate] Failed to notify master pane")
        return ok

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _send_keys(self, pane_id: str, keys: str) -> bool:
        """Execute ``tmux send-keys`` targeting *pane_id*.

        Args:
            pane_id: tmux pane identifier (e.g. ``%1``).
            keys: Key sequence string passed to ``tmux send-keys``.

        Returns:
            ``True`` if the subprocess exited with code 0.
        """
        cmd = [*_TMUX_CMD, "send-keys", "-t", pane_id, keys]
        logger.debug("Running: %s", " ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=_SUBPROCESS_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            logger.error(
                "tmux send-keys timed out for pane %s", pane_id,
            )
            return False
        except FileNotFoundError:
            logger.error("tmux binary not found on PATH")
            return False

        if result.returncode != 0:
            logger.error(
                "tmux send-keys failed (rc=%d): %s",
                result.returncode,
                (result.stderr or "").strip(),
            )
            return False

        return True

    def _get_cli_command(self, ai_type: AIType) -> str:
        """Return the shell command to launch the given AI runtime.

        Args:
            ai_type: Which AI backend to start.

        Returns:
            The CLI invocation string.
        """
        commands = {
            AIType.CLAUDE: "claude --dangerously-skip-permissions",
            AIType.AGY: "agy",
            AIType.CODEX: "codex -a full-auto --no-alt-screen",
        }
        return commands.get(ai_type, "echo 'unknown AI type'")
