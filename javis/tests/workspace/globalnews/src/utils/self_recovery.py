"""Self-recovery infrastructure for unattended pipeline operation.

Provides production self-recovery patterns for the GlobalNews Crawling &
Analysis System, enabling >= 7 days of continuous unattended operation
(PRD 12.2) with >= 90% auto-recovery rate.

Modules:
    LockFileManager   -- PID-based lock files with stale detection
    HealthChecker     -- Pre-run system health validation
    CheckpointManager -- Pipeline progress tracking and crash resume
    CleanupManager    -- Stale temp cleanup and log rotation
    RecoveryOrchestrator -- Top-level recovery coordination

All classes are importable for use from both shell scripts (via Python CLI)
and directly from main.py or pipeline modules.

CLI usage:
    python -m src.utils.self_recovery --health-check
    python -m src.utils.self_recovery --acquire-lock daily
    python -m src.utils.self_recovery --release-lock daily
    python -m src.utils.self_recovery --check-lock daily
    python -m src.utils.self_recovery --cleanup
    python -m src.utils.self_recovery --checkpoint-status
    python -m src.utils.self_recovery --status

Reference:
    Step 5 Architecture Blueprint, Section 8 (Operational Requirements).
    PRD Section 12.2 (Reliability: auto-recovery >= 90%).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Derive PROJECT_ROOT relative to this file: src/utils/self_recovery.py -> project root
_THIS_FILE = Path(__file__).resolve()
_DEFAULT_PROJECT_ROOT = _THIS_FILE.parent.parent.parent

# Lock file settings
LOCK_DIR = Path("/tmp")
LOCK_STALE_THRESHOLD_SECONDS = 4 * 3600  # 4 hours: match pipeline timeout

# Health check thresholds
MIN_DISK_SPACE_GB = 2.0
MIN_DISK_SPACE_BYTES = int(MIN_DISK_SPACE_GB * 1024 * 1024 * 1024)
REQUIRED_PYTHON_VERSION = (3, 11)

# Checkpoint file name
CHECKPOINT_FILENAME = ".pipeline_checkpoint.json"

# Cleanup settings
STALE_TEMP_AGE_HOURS = 24
LOG_MAX_AGE_DAYS = 30


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class HealthReport:
    """Results of a pre-run health check.

    Attributes:
        healthy: True if all critical checks passed.
        checks: Dict of check_name -> (passed, detail).
        timestamp: ISO timestamp of the check.
        disk_free_gb: Available disk space in GB.
        python_version: Running Python version string.
    """

    healthy: bool = True
    checks: dict[str, tuple[bool, str]] = field(default_factory=dict)
    timestamp: str = ""
    disk_free_gb: float = 0.0
    python_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "healthy": self.healthy,
            "checks": {k: {"passed": v[0], "detail": v[1]} for k, v in self.checks.items()},
            "timestamp": self.timestamp,
            "disk_free_gb": round(self.disk_free_gb, 2),
            "python_version": self.python_version,
        }


@dataclass
class PipelineCheckpoint:
    """Pipeline progress state for crash recovery.

    Attributes:
        pipeline_type: "crawl", "analyze", or "full".
        date: Target date (YYYY-MM-DD).
        started_at: ISO timestamp when the pipeline started.
        last_updated: ISO timestamp of the most recent update.
        current_phase: "crawl" or "analyze".
        crawl_completed: Whether crawling phase is done.
        analysis_stage: Last successfully completed analysis stage (0-8).
        sites_completed: List of site IDs that have been crawled.
        sites_failed: List of site IDs that failed.
        status: "running", "completed", "failed", "interrupted".
        error_message: Description of failure, if any.
        pid: PID of the process running the pipeline.
    """

    pipeline_type: str = "full"
    date: str = ""
    started_at: str = ""
    last_updated: str = ""
    current_phase: str = ""
    crawl_completed: bool = False
    analysis_stage: int = 0
    sites_completed: list[str] = field(default_factory=list)
    sites_failed: list[str] = field(default_factory=list)
    status: str = "running"
    error_message: str = ""
    pid: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PipelineCheckpoint:
        """Create from a dict (loaded from JSON)."""
        # Filter to only known fields
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


# =============================================================================
# Lock File Manager
# =============================================================================

class LockFileManager:
    """PID-based lock file manager with stale detection.

    Prevents concurrent execution of pipeline scripts. Detects stale locks
    left by crashed processes (PID no longer running or lock older than
    threshold).

    Args:
        lock_name: Identifier for this lock (e.g., "daily", "weekly").
        lock_dir: Directory for lock files. Defaults to /tmp.
        stale_threshold_seconds: Age threshold for stale lock detection.
        project_root: Project root directory for lock naming.
    """

    def __init__(
        self,
        lock_name: str = "daily",
        lock_dir: Path | None = None,
        stale_threshold_seconds: int = LOCK_STALE_THRESHOLD_SECONDS,
        project_root: Path | None = None,
    ) -> None:
        self._lock_name = lock_name
        self._lock_dir = lock_dir or LOCK_DIR
        self._stale_threshold = stale_threshold_seconds
        self._project_root = project_root or _DEFAULT_PROJECT_ROOT
        self._lock_path = self._lock_dir / f"globalnews_{lock_name}.lock"

    @property
    def lock_path(self) -> Path:
        """Path to the lock file."""
        return self._lock_path

    def acquire(self) -> bool:
        """Acquire the lock, cleaning stale locks if necessary.

        Returns:
            True if lock acquired, False if another process holds it.
        """
        # Check for existing lock
        if self._lock_path.exists():
            if self._is_stale():
                logger.warning(
                    "stale_lock_detected path=%s -- cleaning up",
                    self._lock_path,
                )
                self._cleanup_stale()
            else:
                holder_pid = self._read_lock_pid()
                logger.warning(
                    "lock_held path=%s pid=%s",
                    self._lock_path, holder_pid,
                )
                return False

        # Write lock file with our PID
        try:
            self._lock_path.parent.mkdir(parents=True, exist_ok=True)
            self._lock_path.write_text(
                json.dumps({
                    "pid": os.getpid(),
                    "acquired_at": datetime.now(timezone.utc).isoformat(),
                    "lock_name": self._lock_name,
                    "project_root": str(self._project_root),
                }),
                encoding="utf-8",
            )
            logger.info(
                "lock_acquired path=%s pid=%s",
                self._lock_path, os.getpid(),
            )
            return True
        except OSError as e:
            logger.error("lock_acquire_failed path=%s error=%s", self._lock_path, e)
            return False

    def release(self) -> bool:
        """Release the lock (only if we hold it).

        Returns:
            True if released, False if not held by us.
        """
        if not self._lock_path.exists():
            return True

        holder_pid = self._read_lock_pid()
        if holder_pid != os.getpid():
            logger.warning(
                "lock_release_skip not_our_lock path=%s holder=%s our_pid=%s",
                self._lock_path, holder_pid, os.getpid(),
            )
            return False

        try:
            self._lock_path.unlink()
            logger.info("lock_released path=%s", self._lock_path)
            return True
        except OSError as e:
            logger.error("lock_release_failed path=%s error=%s", self._lock_path, e)
            return False

    def is_locked(self) -> bool:
        """Check if the lock is currently held by a running process.

        Returns:
            True if locked by an active process, False otherwise.
        """
        if not self._lock_path.exists():
            return False
        if self._is_stale():
            return False
        return True

    def force_release(self) -> bool:
        """Force-release the lock regardless of holder.

        Use with caution: only for recovery scenarios.

        Returns:
            True if released, False on error.
        """
        if not self._lock_path.exists():
            return True
        try:
            self._lock_path.unlink()
            logger.info("lock_force_released path=%s", self._lock_path)
            return True
        except OSError as e:
            logger.error("lock_force_release_failed path=%s error=%s", self._lock_path, e)
            return False

    def _is_stale(self) -> bool:
        """Check if the lock file is stale.

        A lock is stale if:
        1. The PID in the lock file is no longer running, OR
        2. The lock file is older than the stale threshold.

        Returns:
            True if the lock is stale.
        """
        if not self._lock_path.exists():
            return False

        # Check PID
        holder_pid = self._read_lock_pid()
        if holder_pid <= 0:
            # Cannot read PID from lock file -- treat as stale
            logger.info(
                "stale_lock unreadable_pid lock_path=%s",
                self._lock_path,
            )
            return True
        if not self._is_process_running(holder_pid):
            logger.info(
                "stale_lock pid=%s not_running lock_path=%s",
                holder_pid, self._lock_path,
            )
            return True

        # Check age
        try:
            lock_age = time.time() - self._lock_path.stat().st_mtime
            if lock_age > self._stale_threshold:
                logger.info(
                    "stale_lock age=%ss threshold=%ss lock_path=%s",
                    int(lock_age), self._stale_threshold, self._lock_path,
                )
                return True
        except OSError:
            return True

        return False

    def _read_lock_pid(self) -> int:
        """Read the PID from the lock file.

        Returns:
            PID from lock file, or -1 on error.
        """
        try:
            data = json.loads(self._lock_path.read_text(encoding="utf-8"))
            return int(data.get("pid", -1))
        except (json.JSONDecodeError, OSError, ValueError):
            return -1

    def _cleanup_stale(self) -> None:
        """Remove a stale lock file."""
        try:
            self._lock_path.unlink(missing_ok=True)
            logger.info("stale_lock_cleaned path=%s", self._lock_path)
        except OSError as e:
            logger.error("stale_lock_cleanup_failed path=%s error=%s", self._lock_path, e)

    @staticmethod
    def _is_process_running(pid: int) -> bool:
        """Check if a process with the given PID is running.

        Args:
            pid: Process ID to check.

        Returns:
            True if the process is running.
        """
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # Process exists but we cannot signal it
            return True


# =============================================================================
# Health Checker
# =============================================================================

class HealthChecker:
    """Pre-run system health validation.

    Validates that the system has sufficient resources and dependencies
    to run the pipeline. Checks: disk space, Python version, critical
    Python packages, data directories, and config files.

    Args:
        project_root: Project root directory.
        min_disk_gb: Minimum free disk space in GB.
    """

    def __init__(
        self,
        project_root: Path | None = None,
        min_disk_gb: float = MIN_DISK_SPACE_GB,
    ) -> None:
        self._project_root = project_root or _DEFAULT_PROJECT_ROOT
        self._min_disk_bytes = int(min_disk_gb * 1024 * 1024 * 1024)
        self._min_disk_gb = min_disk_gb

    def run_all_checks(self) -> HealthReport:
        """Execute all health checks.

        Returns:
            HealthReport with aggregated results.
        """
        report = HealthReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        )

        # 1. Disk space
        passed, detail = self._check_disk_space()
        report.checks["disk_space"] = (passed, detail)
        if passed:
            # Parse free GB from detail
            try:
                report.disk_free_gb = float(detail.split("=")[1].split(" ")[0])
            except (IndexError, ValueError):
                report.disk_free_gb = 0.0

        # 2. Python version
        passed, detail = self._check_python_version()
        report.checks["python_version"] = (passed, detail)

        # 3. Critical dependencies
        passed, detail = self._check_critical_deps()
        report.checks["critical_deps"] = (passed, detail)

        # 4. Data directories
        passed, detail = self._check_data_dirs()
        report.checks["data_dirs"] = (passed, detail)

        # 5. Config files
        passed, detail = self._check_config_files()
        report.checks["config_files"] = (passed, detail)

        # 6. Log directory writable
        passed, detail = self._check_log_dir()
        report.checks["log_dir"] = (passed, detail)

        # Aggregate: healthy only if all checks pass
        report.healthy = all(v[0] for v in report.checks.values())

        return report

    def _check_disk_space(self) -> tuple[bool, str]:
        """Check available disk space.

        Returns:
            (passed, detail) tuple.
        """
        try:
            stat = shutil.disk_usage(str(self._project_root))
            free_gb = stat.free / (1024 ** 3)
            if stat.free < self._min_disk_bytes:
                return False, f"free={free_gb:.2f} GB < min={self._min_disk_gb} GB"
            return True, f"free={free_gb:.2f} GB (min={self._min_disk_gb} GB)"
        except OSError as e:
            return False, f"disk check failed: {e}"

    def _check_python_version(self) -> tuple[bool, str]:
        """Check Python version meets minimum requirement.

        Returns:
            (passed, detail) tuple.
        """
        version = sys.version_info
        version_str = f"{version.major}.{version.minor}.{version.micro}"
        if (version.major, version.minor) >= REQUIRED_PYTHON_VERSION:
            return True, f"Python {version_str} >= {REQUIRED_PYTHON_VERSION[0]}.{REQUIRED_PYTHON_VERSION[1]}"
        return False, f"Python {version_str} < {REQUIRED_PYTHON_VERSION[0]}.{REQUIRED_PYTHON_VERSION[1]}"

    def _check_critical_deps(self) -> tuple[bool, str]:
        """Check that critical Python packages are importable.

        Returns:
            (passed, detail) tuple.
        """
        critical = ["yaml", "requests"]
        missing = []
        for pkg in critical:
            try:
                __import__(pkg)
            except ImportError:
                missing.append(pkg)

        if missing:
            return False, f"missing: {', '.join(missing)}"
        return True, f"all {len(critical)} critical deps OK"

    def _check_data_dirs(self) -> tuple[bool, str]:
        """Check that required data directories exist or can be created.

        Returns:
            (passed, detail) tuple.
        """
        required = ["data/raw", "data/processed", "data/logs"]
        missing = []
        for rel in required:
            path = self._project_root / rel
            if not path.exists():
                try:
                    path.mkdir(parents=True, exist_ok=True)
                except OSError:
                    missing.append(rel)

        if missing:
            return False, f"cannot create: {', '.join(missing)}"
        return True, "all data dirs OK"

    def _check_config_files(self) -> tuple[bool, str]:
        """Check that critical config files exist.

        Returns:
            (passed, detail) tuple.
        """
        config_dir = self._project_root / "data" / "config"
        sources = config_dir / "sources.yaml"
        if not sources.exists():
            return False, f"missing: {sources}"
        return True, "sources.yaml present"

    def _check_log_dir(self) -> tuple[bool, str]:
        """Check that the log directory exists and is writable.

        Returns:
            (passed, detail) tuple.
        """
        log_dir = self._project_root / "data" / "logs"
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            test_file = log_dir / ".write_test"
            test_file.write_text("test", encoding="utf-8")
            test_file.unlink()
            return True, f"writable: {log_dir}"
        except OSError as e:
            return False, f"log dir not writable: {e}"


# =============================================================================
# Checkpoint Manager
# =============================================================================

class CheckpointManager:
    """Track pipeline progress for crash recovery.

    Persists pipeline state to a JSON file so that on crash, the pipeline
    can resume from the last successful stage rather than starting over.

    Args:
        project_root: Project root directory.
    """

    def __init__(self, project_root: Path | None = None) -> None:
        self._project_root = project_root or _DEFAULT_PROJECT_ROOT
        self._checkpoint_path = self._project_root / "data" / CHECKPOINT_FILENAME

    @property
    def checkpoint_path(self) -> Path:
        """Path to the checkpoint file."""
        return self._checkpoint_path

    def save(self, checkpoint: PipelineCheckpoint) -> None:
        """Save pipeline checkpoint to disk.

        Uses atomic write (write to temp + rename) to prevent corruption.

        Args:
            checkpoint: Current pipeline state.
        """
        checkpoint.last_updated = datetime.now(timezone.utc).isoformat()
        checkpoint.pid = os.getpid()

        tmp_path = self._checkpoint_path.with_suffix(".tmp")
        try:
            self._checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_text(
                json.dumps(checkpoint.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp_path.rename(self._checkpoint_path)
            logger.debug(
                "checkpoint_saved path=%s phase=%s stage=%s",
                self._checkpoint_path, checkpoint.current_phase,
                checkpoint.analysis_stage,
            )
        except OSError as e:
            logger.error("checkpoint_save_failed path=%s error=%s", self._checkpoint_path, e)
            # Clean up temp file
            tmp_path.unlink(missing_ok=True)

    def load(self) -> PipelineCheckpoint | None:
        """Load pipeline checkpoint from disk.

        Returns:
            PipelineCheckpoint if file exists and is valid, None otherwise.
        """
        if not self._checkpoint_path.exists():
            return None

        try:
            data = json.loads(self._checkpoint_path.read_text(encoding="utf-8"))
            checkpoint = PipelineCheckpoint.from_dict(data)
            logger.info(
                "checkpoint_loaded path=%s phase=%s stage=%s status=%s",
                self._checkpoint_path, checkpoint.current_phase,
                checkpoint.analysis_stage, checkpoint.status,
            )
            return checkpoint
        except (json.JSONDecodeError, OSError) as e:
            logger.error("checkpoint_load_failed path=%s error=%s", self._checkpoint_path, e)
            return None

    def clear(self) -> None:
        """Remove the checkpoint file (pipeline completed or abandoned)."""
        try:
            self._checkpoint_path.unlink(missing_ok=True)
            logger.info("checkpoint_cleared path=%s", self._checkpoint_path)
        except OSError as e:
            logger.error("checkpoint_clear_failed path=%s error=%s", self._checkpoint_path, e)

    def get_resume_args(self) -> dict[str, Any] | None:
        """Determine resume arguments from checkpoint.

        Examines the checkpoint to determine what arguments should be
        passed to main.py for a resume run.

        Returns:
            Dict with mode, date, stage (for analysis resume), or None
            if no resume is possible.
        """
        checkpoint = self.load()
        if checkpoint is None:
            return None

        if checkpoint.status != "running" and checkpoint.status != "interrupted":
            return None

        # Check if the process that created this checkpoint is still running
        if checkpoint.pid > 0 and LockFileManager._is_process_running(checkpoint.pid):
            logger.info(
                "checkpoint_process_still_running pid=%s",
                checkpoint.pid,
            )
            return None

        result: dict[str, Any] = {
            "date": checkpoint.date,
            "checkpoint": checkpoint,
        }

        if checkpoint.current_phase == "crawl" and not checkpoint.crawl_completed:
            # Resume crawl -- retry failed sites
            result["mode"] = "full"
            result["resume_from"] = "crawl"
            if checkpoint.sites_failed:
                result["retry_sites"] = checkpoint.sites_failed
        elif checkpoint.current_phase == "analyze" or checkpoint.crawl_completed:
            # Resume from analysis stage
            result["mode"] = "analyze"
            result["resume_from"] = "analyze"
            result["start_stage"] = checkpoint.analysis_stage + 1
        else:
            # Full restart
            result["mode"] = "full"
            result["resume_from"] = "start"

        return result

    def update_crawl_progress(
        self,
        site_id: str,
        success: bool,
    ) -> None:
        """Update checkpoint with crawl progress for a site.

        Args:
            site_id: Site that was just processed.
            success: Whether crawling this site succeeded.
        """
        checkpoint = self.load()
        if checkpoint is None:
            return

        if success:
            if site_id not in checkpoint.sites_completed:
                checkpoint.sites_completed.append(site_id)
            # Remove from failed list if it was retried successfully
            if site_id in checkpoint.sites_failed:
                checkpoint.sites_failed.remove(site_id)
        else:
            if site_id not in checkpoint.sites_failed:
                checkpoint.sites_failed.append(site_id)

        self.save(checkpoint)

    def update_analysis_stage(self, stage: int, success: bool) -> None:
        """Update checkpoint with analysis stage progress.

        Args:
            stage: Stage number that was just completed.
            success: Whether the stage succeeded.
        """
        checkpoint = self.load()
        if checkpoint is None:
            return

        checkpoint.current_phase = "analyze"
        if success:
            checkpoint.analysis_stage = stage
        else:
            checkpoint.status = "failed"
            checkpoint.error_message = f"Analysis stage {stage} failed"

        self.save(checkpoint)

    def mark_completed(self) -> None:
        """Mark the pipeline as successfully completed."""
        checkpoint = self.load()
        if checkpoint is None:
            return

        checkpoint.status = "completed"
        self.save(checkpoint)

    def mark_failed(self, error_message: str) -> None:
        """Mark the pipeline as failed.

        Args:
            error_message: Description of the failure.
        """
        checkpoint = self.load()
        if checkpoint is not None:
            checkpoint.status = "failed"
            checkpoint.error_message = error_message
            self.save(checkpoint)


# =============================================================================
# Cleanup Manager
# =============================================================================

class CleanupManager:
    """Clean up stale temp files, rotate logs, and remove incomplete runs.

    Args:
        project_root: Project root directory.
    """

    def __init__(self, project_root: Path | None = None) -> None:
        self._project_root = project_root or _DEFAULT_PROJECT_ROOT
        self._data_dir = self._project_root / "data"

    def cleanup_stale_temps(self, max_age_hours: int = STALE_TEMP_AGE_HOURS) -> int:
        """Remove temporary files older than max_age_hours.

        Looks for .tmp, .partial, .lock files in data directories.

        Args:
            max_age_hours: Maximum age of temp files in hours.

        Returns:
            Number of files removed.
        """
        removed = 0
        cutoff = time.time() - (max_age_hours * 3600)
        temp_patterns = ["*.tmp", "*.partial", "*.temp"]

        for pattern in temp_patterns:
            for tmp_file in self._data_dir.rglob(pattern):
                try:
                    if tmp_file.stat().st_mtime < cutoff:
                        tmp_file.unlink()
                        removed += 1
                        logger.info("temp_removed path=%s", tmp_file)
                except OSError as e:
                    logger.warning("temp_remove_failed path=%s error=%s", tmp_file, e)

        if removed > 0:
            logger.info("stale_temps_cleaned count=%s", removed)
        return removed

    def rotate_old_logs(self, max_age_days: int = LOG_MAX_AGE_DAYS) -> int:
        """Remove log files older than max_age_days.

        Only removes rotated log files (those with numeric suffixes like
        .log.1, .log.2), not the active log files.

        Args:
            max_age_days: Maximum age of log files in days.

        Returns:
            Number of files removed.
        """
        removed = 0
        cutoff = time.time() - (max_age_days * 86400)
        log_dir = self._data_dir / "logs"

        if not log_dir.exists():
            return 0

        for log_file in log_dir.iterdir():
            if not log_file.is_file():
                continue
            # Only remove rotated logs (*.log.N) not active logs
            name = log_file.name
            if not (name.endswith(tuple(f".{i}" for i in range(1, 100)))
                    or name.endswith(".gz")):
                continue
            try:
                if log_file.stat().st_mtime < cutoff:
                    log_file.unlink()
                    removed += 1
                    logger.info("old_log_removed path=%s", log_file)
            except OSError as e:
                logger.warning("log_remove_failed path=%s error=%s", log_file, e)

        if removed > 0:
            logger.info("old_logs_cleaned count=%s", removed)
        return removed

    def cleanup_incomplete_runs(self) -> int:
        """Remove data from incomplete pipeline runs.

        Checks for date-stamped directories in data/raw/ that have no
        corresponding checkpoint completion marker.

        Returns:
            Number of directories cleaned.
        """
        cleaned = 0
        raw_dir = self._data_dir / "raw"

        if not raw_dir.exists():
            return 0

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        for date_dir in sorted(raw_dir.iterdir()):
            if not date_dir.is_dir():
                continue
            # Never clean today's data
            if date_dir.name == today:
                continue
            # Check for completion marker
            articles_file = date_dir / "all_articles.jsonl"
            report_file = date_dir / "crawl_report.json"
            if not articles_file.exists() and not report_file.exists():
                # Incomplete run -- check if it is old enough to clean
                try:
                    age_hours = (time.time() - date_dir.stat().st_mtime) / 3600
                    if age_hours > STALE_TEMP_AGE_HOURS:
                        shutil.rmtree(date_dir)
                        cleaned += 1
                        logger.info(
                            "incomplete_run_cleaned path=%s age_hours=%s",
                            date_dir, int(age_hours),
                        )
                except OSError as e:
                    logger.warning(
                        "incomplete_run_cleanup_failed path=%s error=%s",
                        date_dir, e,
                    )

        if cleaned > 0:
            logger.info("incomplete_runs_cleaned count=%s", cleaned)
        return cleaned

    def run_all(self) -> dict[str, int]:
        """Execute all cleanup operations.

        Returns:
            Dict with counts of cleaned items per category.
        """
        return {
            "stale_temps": self.cleanup_stale_temps(),
            "old_logs": self.rotate_old_logs(),
            "incomplete_runs": self.cleanup_incomplete_runs(),
        }

    def get_disk_usage_report(self) -> dict[str, Any]:
        """Get disk usage report for data directories.

        Returns:
            Dict with per-directory size information.
        """
        report: dict[str, Any] = {}
        try:
            stat = shutil.disk_usage(str(self._data_dir))
            report["disk_total_gb"] = round(stat.total / (1024 ** 3), 2)
            report["disk_used_gb"] = round(stat.used / (1024 ** 3), 2)
            report["disk_free_gb"] = round(stat.free / (1024 ** 3), 2)
            report["disk_usage_pct"] = round(stat.used / stat.total * 100, 1)
        except OSError:
            report["disk_total_gb"] = 0
            report["disk_free_gb"] = 0

        # Per-directory sizes
        dirs_report: dict[str, float] = {}
        for subdir in ["raw", "processed", "features", "analysis", "output", "logs", "archive"]:
            path = self._data_dir / subdir
            if path.exists():
                total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
                dirs_report[subdir] = round(total / (1024 ** 2), 2)  # MB
            else:
                dirs_report[subdir] = 0.0

        report["directories_mb"] = dirs_report
        return report


# =============================================================================
# Recovery Orchestrator
# =============================================================================

class RecoveryOrchestrator:
    """Top-level coordination of all self-recovery subsystems.

    Provides a single entry point for health checks, lock management,
    checkpoint handling, and cleanup. Used by shell scripts via CLI.

    Args:
        project_root: Project root directory.
    """

    def __init__(self, project_root: Path | None = None) -> None:
        self._project_root = project_root or _DEFAULT_PROJECT_ROOT
        self._health_checker = HealthChecker(self._project_root)
        self._checkpoint_mgr = CheckpointManager(self._project_root)
        self._cleanup_mgr = CleanupManager(self._project_root)

    def pre_run_check(self) -> HealthReport:
        """Run all pre-run health checks.

        Returns:
            HealthReport indicating whether the system is ready.
        """
        return self._health_checker.run_all_checks()

    def get_lock_manager(self, name: str = "daily") -> LockFileManager:
        """Get a lock manager for the specified pipeline.

        Args:
            name: Lock name ("daily", "weekly", "archive").

        Returns:
            Configured LockFileManager.
        """
        return LockFileManager(
            lock_name=name,
            project_root=self._project_root,
        )

    def attempt_recovery(self) -> dict[str, Any]:
        """Attempt to recover from a previous failed/interrupted run.

        Checks for stale locks, incomplete checkpoints, and determines
        the best recovery strategy.

        Returns:
            Dict with recovery_needed, strategy, and details.
        """
        result: dict[str, Any] = {
            "recovery_needed": False,
            "strategy": "none",
            "details": {},
        }

        # Check for stale locks
        for lock_name in ["daily", "weekly"]:
            lock = self.get_lock_manager(lock_name)
            if lock._lock_path.exists() and lock._is_stale():
                result["recovery_needed"] = True
                result["details"]["stale_lock"] = lock_name
                lock.force_release()
                logger.info("recovery_cleaned_stale_lock name=%s", lock_name)

        # Check for resume-able checkpoint
        resume_args = self._checkpoint_mgr.get_resume_args()
        if resume_args is not None:
            result["recovery_needed"] = True
            result["strategy"] = "resume"
            result["details"]["resume_args"] = resume_args
            logger.info(
                "recovery_resume_available mode=%s date=%s",
                resume_args.get("mode"), resume_args.get("date"),
            )

        return result

    def get_status(self) -> dict[str, Any]:
        """Get comprehensive system status.

        Returns:
            JSON-serializable dict with health, locks, checkpoint, and disk info.
        """
        status: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "project_root": str(self._project_root),
        }

        # Health
        health = self._health_checker.run_all_checks()
        status["health"] = health.to_dict()

        # Locks
        locks: dict[str, Any] = {}
        for name in ["daily", "weekly", "archive"]:
            lock = self.get_lock_manager(name)
            locks[name] = {
                "locked": lock.is_locked(),
                "path": str(lock.lock_path),
            }
        status["locks"] = locks

        # Checkpoint
        checkpoint = self._checkpoint_mgr.load()
        status["checkpoint"] = checkpoint.to_dict() if checkpoint else None

        # Disk
        status["disk"] = self._cleanup_mgr.get_disk_usage_report()

        return status

    def run_cleanup(self) -> dict[str, int]:
        """Run all cleanup operations.

        Returns:
            Cleanup counts per category.
        """
        return self._cleanup_mgr.run_all()


# =============================================================================
# Timeout Handler
# =============================================================================

class TimeoutHandler:
    """Context manager for pipeline execution timeout.

    Uses SIGALRM on Unix systems. On non-Unix systems (Windows),
    falls back to a no-op.

    Args:
        timeout_seconds: Maximum execution time in seconds.
        message: Error message on timeout.
    """

    def __init__(
        self,
        timeout_seconds: int = 4 * 3600,
        message: str = "Pipeline execution timed out",
    ) -> None:
        self._timeout = timeout_seconds
        self._message = message
        self._has_sigalrm = hasattr(signal, "SIGALRM")

    def __enter__(self) -> TimeoutHandler:
        if self._has_sigalrm:
            self._old_handler = signal.signal(signal.SIGALRM, self._handle_timeout)
            signal.alarm(self._timeout)
        return self

    def __exit__(self, *args: Any) -> None:
        if self._has_sigalrm:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, self._old_handler)

    def _handle_timeout(self, signum: int, frame: Any) -> None:
        """Handle SIGALRM by raising TimeoutError."""
        raise TimeoutError(self._message)


# =============================================================================
# CLI Interface
# =============================================================================

def _cli_main() -> int:
    """CLI entry point for self-recovery operations.

    Returns:
        Exit code (0 = success, 1 = failure).
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="self_recovery",
        description="GlobalNews Self-Recovery Infrastructure",
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=_DEFAULT_PROJECT_ROOT,
        help="Project root directory",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--health-check", action="store_true", help="Run health checks")
    group.add_argument("--acquire-lock", metavar="NAME", help="Acquire named lock")
    group.add_argument("--release-lock", metavar="NAME", help="Release named lock")
    group.add_argument("--check-lock", metavar="NAME", help="Check if lock is held")
    group.add_argument("--force-release-lock", metavar="NAME", help="Force-release lock")
    group.add_argument("--cleanup", action="store_true", help="Run cleanup operations")
    group.add_argument("--checkpoint-status", action="store_true", help="Show checkpoint status")
    group.add_argument("--checkpoint-clear", action="store_true", help="Clear checkpoint")
    group.add_argument("--attempt-recovery", action="store_true", help="Attempt recovery")
    group.add_argument("--status", action="store_true", help="Show full system status")
    group.add_argument("--disk-report", action="store_true", help="Show disk usage report")

    args = parser.parse_args()
    project_root = args.project_dir.resolve()
    orch = RecoveryOrchestrator(project_root)

    try:
        if args.health_check:
            report = orch.pre_run_check()
            print(json.dumps(report.to_dict(), indent=2))
            return 0 if report.healthy else 1

        elif args.acquire_lock:
            lock = orch.get_lock_manager(args.acquire_lock)
            acquired = lock.acquire()
            print(json.dumps({"acquired": acquired, "path": str(lock.lock_path)}))
            return 0 if acquired else 1

        elif args.release_lock:
            lock = orch.get_lock_manager(args.release_lock)
            released = lock.release()
            print(json.dumps({"released": released, "path": str(lock.lock_path)}))
            return 0 if released else 1

        elif args.check_lock:
            lock = orch.get_lock_manager(args.check_lock)
            locked = lock.is_locked()
            print(json.dumps({"locked": locked, "path": str(lock.lock_path)}))
            return 0

        elif args.force_release_lock:
            lock = orch.get_lock_manager(args.force_release_lock)
            released = lock.force_release()
            print(json.dumps({"released": released, "path": str(lock.lock_path)}))
            return 0 if released else 1

        elif args.cleanup:
            counts = orch.run_cleanup()
            print(json.dumps(counts, indent=2))
            return 0

        elif args.checkpoint_status:
            mgr = CheckpointManager(project_root)
            cp = mgr.load()
            if cp:
                print(json.dumps(cp.to_dict(), indent=2))
            else:
                print(json.dumps({"checkpoint": None}))
            return 0

        elif args.checkpoint_clear:
            mgr = CheckpointManager(project_root)
            mgr.clear()
            print(json.dumps({"cleared": True}))
            return 0

        elif args.attempt_recovery:
            result = orch.attempt_recovery()
            print(json.dumps(result, indent=2, default=str))
            return 0

        elif args.status:
            status = orch.get_status()
            print(json.dumps(status, indent=2, default=str))
            return 0

        elif args.disk_report:
            mgr = CleanupManager(project_root)
            report = mgr.get_disk_usage_report()
            print(json.dumps(report, indent=2))
            return 0

    except Exception as e:
        print(json.dumps({"error": str(e), "type": type(e).__name__}), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(_cli_main())
