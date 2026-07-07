"""Main orchestrator for the Javis Fleet Auto-Recovery Watchdog.

Ties together the detector, strategy, and executor into a single
run-loop that periodically checks worker health, decides on recovery
actions, and executes them.

Requires Python 3.10+.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from .config import load_config
from .detector import WorkerDetector
from .executor import RecoveryExecutor
from .models import WatchdogConfig, WatchdogEvent, WorkerState
from .strategy import RecoveryStrategy


class Watchdog:
    """Central orchestrator that monitors fleet workers and auto-recovers.

    Coordinates a ``WorkerDetector`` (health checks), a ``RecoveryStrategy``
    (decides *what* to do), and a ``RecoveryExecutor`` (carries out recovery)
    inside a polling loop.

    Args:
        config: Optional configuration override.  When ``None``, the config
            is loaded from environment / YAML via ``load_config()``.

    Attributes:
        config: Active watchdog configuration.
        detector: Worker health-check component.
        strategy: Decision engine for recovery actions.
        executor: Component that carries out recovery actions.
    """

    def __init__(self, config: WatchdogConfig | None = None) -> None:
        """Initialize detector, strategy, executor, and event log.

        Args:
            config: Watchdog tuning parameters.  Defaults are loaded from
                the environment / YAML file when ``None``.
        """
        self.config: WatchdogConfig = config or load_config()
        self.detector = WorkerDetector(self.config)
        self.strategy = RecoveryStrategy(self.config)
        self.executor = RecoveryExecutor(self.config)
        self._running: bool = False
        self._events: list[WatchdogEvent] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the watchdog polling loop.

        Sets the running flag and enters ``_run_loop()``.  The loop blocks
        the calling thread until ``stop()`` is called or a ``KeyboardInterrupt``
        is received.
        """
        self._running = True
        print(f"[Watchdog] Started — interval={self.config.check_interval}s, "
              f"log={self.config.log_file}")
        self._run_loop()

    def stop(self) -> None:
        """Signal the polling loop to exit after the current cycle."""
        self._running = False
        print("[Watchdog] Stop requested.")

    def status(self) -> list[WorkerState]:
        """Return a one-shot snapshot of all worker states.

        Returns:
            List of ``WorkerState`` instances from a single detection pass.
        """
        return self.detector.detect_all()

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Execute check cycles until stopped or interrupted.

        Each cycle calls ``_check_cycle()``, prints a one-line summary to
        stdout, then sleeps for ``config.check_interval`` seconds.
        A ``KeyboardInterrupt`` triggers a clean stop.
        """
        try:
            while self._running:
                cycle_start = time.monotonic()
                events = self._check_cycle()
                elapsed = time.monotonic() - cycle_start

                summary = self._format_cycle_summary(events, elapsed)
                print(summary)

                time.sleep(self.config.check_interval)
        except KeyboardInterrupt:
            print("\n[Watchdog] Interrupted — shutting down.")
        finally:
            self._running = False
            print("[Watchdog] Stopped.")

    def _check_cycle(self) -> list[WatchdogEvent]:
        """Run one full detection → strategy → execution cycle.

        For each worker detected:
        1. Log a detection event.
        2. Ask the strategy whether action is needed.
        3. If so, execute the action and log the result.

        Returns:
            All ``WatchdogEvent`` instances produced in this cycle.
        """
        cycle_events: list[WatchdogEvent] = []
        now = datetime.now()
        workers = self.detector.detect_all()

        for worker in workers:
            det_event = WatchdogEvent(
                event_type="detection",
                worker_label=worker.label,
                detail=f"status={worker.status.value}",
                timestamp=now,
            )
            cycle_events.append(det_event)
            self._log_event(det_event)

            action = self.strategy.evaluate(worker)
            if action is None:
                continue

            cycle_events.append(self._execute_and_log(action, now))

        self._events.extend(cycle_events)
        return cycle_events

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _execute_and_log(self, action, now: datetime) -> WatchdogEvent:
        """Execute a recovery action and return the corresponding event.

        Args:
            action: A ``RecoveryAction`` chosen by the strategy.
            now: Timestamp for the event record.

        Returns:
            A ``WatchdogEvent`` describing the recovery attempt and outcome.
        """
        success = self.executor.execute(action)
        action.success = success

        outcome = "succeeded" if success else "failed"
        event = WatchdogEvent(
            event_type="recovery",
            worker_label=action.worker.label,
            detail=(
                f"tier={action.tier.value}, reason={action.reason}, "
                f"outcome={outcome}"
            ),
            timestamp=now,
        )
        self._log_event(event)
        return event

    def _log_event(self, event: WatchdogEvent) -> None:
        """Append an event as a JSON line to the configured log file.

        File I/O errors are caught and printed to stderr so they never
        crash the watchdog loop.

        Args:
            event: The watchdog event to persist.
        """
        try:
            log_path = Path(self.config.log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        except OSError as exc:
            print(f"[Watchdog] Log write error: {exc}")

    @staticmethod
    def _format_cycle_summary(
        events: list[WatchdogEvent],
        elapsed: float,
    ) -> str:
        """Build a one-line stdout summary for a completed cycle.

        Args:
            events: Events produced during the cycle.
            elapsed: Wall-clock seconds the cycle took.

        Returns:
            A human-readable summary string.
        """
        detections = sum(1 for e in events if e.event_type == "detection")
        recoveries = sum(1 for e in events if e.event_type == "recovery")
        ts = datetime.now().strftime("%H:%M:%S")
        return (
            f"[Watchdog {ts}] "
            f"workers={detections}, recoveries={recoveries}, "
            f"cycle={elapsed:.2f}s"
        )


Orchestrator = Watchdog

