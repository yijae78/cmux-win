"""Worker health detector for the Javis Fleet Auto-Recovery Watchdog.

Reads tmux pane content via subprocess and classifies each worker's
health status using keyword-based heuristics consistent with
``dashboard.py``'s ``detect_status`` logic.

Requires Python 3.10+ for ``X | None`` union syntax.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

from .models import AIType, WatchdogConfig, WorkerState, WorkerStatus


def _resolve_tmux_cmd() -> list[str]:
    """Resolve the tmux binary, falling back to the cmux-win Node.js shim.

    On Windows with cmux-win, the bash shim ``~/bin/tmux`` is a Node.js
    script that Python's subprocess cannot execute directly.  This
    function detects that situation and returns the appropriate
    ``['node', '/path/to/tmux-shim.js']`` prefix.

    Returns:
        A list of command tokens to prepend to every tmux invocation.
    """
    # Try the shim first (cmux-win on Windows)
    shim_path = Path.home() / "bin" / "tmux-shim.js"
    if shim_path.is_file():
        return ["node", str(shim_path)]
    # Fallback: assume tmux is on PATH (Linux/Mac or tmux installed)
    return ["tmux"]


_TMUX_CMD: list[str] = _resolve_tmux_cmd()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\r")
"""Regex to strip ANSI escape codes and carriage returns from terminal output."""

_LIVE_KEYWORDS: tuple[str, ...] = (
    "thinking", "working", "running", "processing", "generating",
    "searching", "reading file", "writing file", "editing", "creating",
    "analyzing", "building", "fetching", "compiling", "levitating",
    "tool call", "spinning", "moonwalking", "deciphering", "contemplating",
    "pondering", "pontificating", "cogitating", "ruminating", "meditating",
    "deliberating", "musing", "waddling", "combobulating", "crunching",
    "brewing", "brewed for", "loading", "computing", "reasoning",
    "considering", "investigating", "gathering",
    "esc to interrupt", "esc to cancel",
    # AGY (Gemini) patterns
    "herding", "calling tool", "executing", "applying patch",
    "searching codebase",
    # Codex patterns
    "codex is thinking", "applying changes", "reviewing",
    # Korean patterns
    "분석 중", "작업 중", "모니터링", "읽는 중", "작성 중",
    "검토 중", "리뷰 중", "수정 중", "생성 중", "실행 중",
    # Compact in progress
    "compacting", "auto-compact",
    "zigzagging", "shenaniganing", "cooked",
)

_IDLE_KEYWORDS: tuple[str, ...] = (
    "$ ", "> ", ">>> ", "ps c:\\",
    "what would you like", "how can i help",
    "대기합니다", "지시를 대기", "명령을 대기",
    'try "', "type your message", "run /review",
    # AGY / Codex idle patterns
    "enter a prompt", "what can i do", "ready",
)

_LABEL_AI_MAP: dict[str, AIType] = {
    "claude": AIType.CLAUDE,
    "agy": AIType.AGY,
    "codex": AIType.CODEX,
}

_CONTENT_AI_HINTS: tuple[tuple[str, AIType], ...] = (
    ("claude", AIType.CLAUDE),
    ("anthropic", AIType.CLAUDE),
    ("agy", AIType.AGY),
    ("antigravity", AIType.AGY),
    ("gemini", AIType.AGY),
    ("codex", AIType.CODEX),
    ("openai codex", AIType.CODEX),
)


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes and carriage returns from *text*.

    Args:
        text: Raw terminal output potentially containing escape sequences.

    Returns:
        Cleaned plain-text string.
    """
    return _ANSI_RE.sub("", text)


# ---------------------------------------------------------------------------
# WorkerDetector
# ---------------------------------------------------------------------------


class WorkerDetector:
    """Detects worker health status by reading tmux pane content.

    Maintains per-pane content hashes across calls to identify stuck
    workers whose output has not changed within ``stuck_timeout`` seconds.

    Args:
        config: Tunable watchdog parameters (timeouts, retries, etc.).
    """

    def __init__(self, config: WatchdogConfig) -> None:
        self._config = config
        # pane_id -> (content_hash, timestamp_of_last_change)
        self._hash_history: dict[str, tuple[str, float]] = {}
        # pane_id -> previous WorkerState (for delta comparison)
        self._prev_states: dict[str, WorkerState] = {}

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def detect_all(self) -> list[WorkerState]:
        """Poll every tmux pane and return a list of worker states.

        Runs ``tmux list-panes`` to discover pane IDs, then inspects
        each one individually.

        Returns:
            A list of :class:`WorkerState` objects, one per pane.
        """
        pane_ids = self._list_panes()
        states: list[WorkerState] = []
        for pane_id, label in pane_ids:
            state = self.detect_one(pane_id, label=label)
            states.append(state)
        return states

    def detect_one(self, pane_id: str, *, label: str = "") -> WorkerState:
        """Inspect a single tmux pane and return its worker state.

        Args:
            pane_id: tmux pane identifier (e.g. ``%1``).
            label: Optional human-readable label for the pane.

        Returns:
            A :class:`WorkerState` snapshot.
        """
        now = datetime.now()
        content = self._read_pane(pane_id)
        prev = self._prev_states.get(pane_id)

        if content is None:
            status = WorkerStatus.DEAD
        else:
            self._update_hash(pane_id, content)
            status = self._classify_status(content, prev)

        ai_type = self._detect_ai_type(content or "", label)
        state = WorkerState(
            pane_id=pane_id,
            label=label or pane_id,
            ai_type=ai_type,
            status=status,
            last_active=self._last_active_time(pane_id, now),
            last_check=now,
            stuck_since=self._stuck_since(pane_id, status, prev),
            recovery_attempts=prev.recovery_attempts if prev else 0,
            current_task="",
        )
        self._prev_states[pane_id] = state
        return state

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _read_pane(self, pane_id: str) -> str | None:
        """Capture the visible content of a tmux pane.

        Args:
            pane_id: tmux pane identifier (e.g. ``%1``).

        Returns:
            Cleaned pane text, or ``None`` if the pane could not be read
            (process error, pane missing, etc.).
        """
        try:
            result = subprocess.run(
                [*_TMUX_CMD, "capture-pane", "-t", pane_id, "-p"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )
            if result.returncode != 0:
                return None
            stdout = result.stdout or ""
            text = _strip_ansi(stdout)
            return text if text.strip() else None
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return None

    def _classify_status(
        self, content: str, prev: WorkerState | None
    ) -> WorkerStatus:
        """Classify worker health from pane content and history.

        Priority order mirrors ``dashboard.py``:
        1. Empty/missing content -> DEAD
        2. LIVE keywords detected -> LIVE
        3. IDLE keywords detected -> IDLE
        4. Content hash unchanged for ``stuck_timeout`` -> STUCK
        5. Fallback -> IDLE

        Args:
            content: Cleaned pane text (non-None).
            prev: Previous worker state for the same pane, or ``None``.

        Returns:
            The determined :class:`WorkerStatus`.
        """
        if not content or not content.strip():
            return WorkerStatus.DEAD

        last_lines = "\n".join(content.strip().splitlines()[-8:]).lower()

        if any(kw in last_lines for kw in _LIVE_KEYWORDS):
            return WorkerStatus.LIVE

        if any(kw in last_lines for kw in _IDLE_KEYWORDS):
            return WorkerStatus.IDLE

        # Stuck detection: content hash unchanged beyond threshold
        if prev and prev.pane_id in self._hash_history:
            _, last_change_ts = self._hash_history[prev.pane_id]
            elapsed = time.time() - last_change_ts
            if elapsed >= self._config.stuck_timeout:
                return WorkerStatus.STUCK

        return WorkerStatus.IDLE

    def _detect_ai_type(self, content: str, label: str) -> AIType:
        """Determine which AI runtime is running in the pane.

        Checks the pane label first (e.g. ``Worker1(Claude)``), then
        falls back to content keyword matching.

        Args:
            content: Cleaned pane text.
            label: Human-readable pane label.

        Returns:
            The detected :class:`AIType`, or ``AIType.UNKNOWN``.
        """
        # Parse label: "Worker2(AGY)" -> extract "agy"
        label_lower = label.lower()
        paren_match = re.search(r"\(([^)]+)\)", label_lower)
        if paren_match:
            inner = paren_match.group(1).strip()
            for key, ai in _LABEL_AI_MAP.items():
                if key in inner:
                    return ai

        # Fallback: scan content for AI-specific keywords
        content_lower = content.lower()
        for hint, ai in _CONTENT_AI_HINTS:
            if hint in content_lower:
                return ai

        return AIType.UNKNOWN

    # ------------------------------------------------------------------ #
    # Hash tracking
    # ------------------------------------------------------------------ #

    def _update_hash(self, pane_id: str, content: str) -> None:
        """Update the content hash for *pane_id*, tracking change times.

        Args:
            pane_id: tmux pane identifier.
            content: Current cleaned pane text.
        """
        new_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
        prev_entry = self._hash_history.get(pane_id)
        now = time.time()

        if prev_entry is None or prev_entry[0] != new_hash:
            self._hash_history[pane_id] = (new_hash, now)
        # else: hash unchanged -- keep existing timestamp

    def _last_active_time(self, pane_id: str, fallback: datetime) -> datetime:
        """Return the timestamp when the pane content last changed.

        Args:
            pane_id: tmux pane identifier.
            fallback: Returned when no history exists for *pane_id*.

        Returns:
            A :class:`datetime` of the last content change.
        """
        entry = self._hash_history.get(pane_id)
        if entry is not None:
            return datetime.fromtimestamp(entry[1])
        return fallback

    def _stuck_since(
        self,
        pane_id: str,
        status: WorkerStatus,
        prev: WorkerState | None,
    ) -> datetime | None:
        """Determine the ``stuck_since`` timestamp for a pane.

        Args:
            pane_id: tmux pane identifier.
            status: The newly classified status.
            prev: Previous worker state, or ``None``.

        Returns:
            The datetime when the worker first became stuck, or ``None``
            if it is not stuck.
        """
        if status != WorkerStatus.STUCK:
            return None
        if prev and prev.stuck_since:
            return prev.stuck_since
        entry = self._hash_history.get(pane_id)
        if entry:
            return datetime.fromtimestamp(entry[1])
        return datetime.now()

    # ------------------------------------------------------------------ #
    # tmux helpers
    # ------------------------------------------------------------------ #

    def _list_panes(self) -> list[tuple[str, str]]:
        """Enumerate tmux panes via ``tmux list-panes``.

        Supports both standard tmux (``%id<TAB>title``) and cmux-win
        shim format (``%id: type (uuid) [surface: uuid]``).

        Returns:
            A list of ``(pane_id, label)`` tuples.  The label is
            derived from the pane title.  Returns an empty list on
            failure.
        """
        try:
            result = subprocess.run(
                [
                    *_TMUX_CMD, "list-panes", "-a",
                    "-F", "#{pane_id}\t#{pane_title}",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )
            if result.returncode != 0:
                return []
            panes: list[tuple[str, str]] = []
            for line in result.stdout.strip().splitlines():
                if "\t" in line:
                    # Standard tmux format: %id\ttitle
                    parts = line.split("\t", 1)
                    pane_id = parts[0].strip()
                    label = parts[1].strip() if len(parts) > 1 else pane_id
                else:
                    # cmux-win shim format: %id: type (uuid) [...]
                    match = re.match(r"(%\d+)", line)
                    pane_id = match.group(1) if match else ""
                    label = pane_id
                if pane_id:
                    panes.append((pane_id, label))
            return panes
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return []
