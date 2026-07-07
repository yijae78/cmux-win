"""Per-Site Circuit Breaker Coordinator for the GlobalNews crawling system.

Wraps the base CircuitBreaker from error_handler.py with per-domain isolation,
integration with the BlockDetector and AntiBlockEngine, and centralized
state management across all 116 news sites.

State Machine per domain:
    CLOSED     -- Normal operation, counting consecutive failures.
    OPEN       -- After 5 consecutive block detections, wait 30 min (1800s).
    HALF_OPEN  -- After timeout, allow a single probe request.

    CLOSED -> OPEN:      after failure_threshold (5) consecutive block failures
    OPEN -> HALF_OPEN:   after recovery_timeout (1800s) seconds
    HALF_OPEN -> CLOSED: after half_open_max_calls (3) consecutive successes
    HALF_OPEN -> OPEN:   on any failure during probe

Thread-safety: The underlying CircuitBreaker uses threading.Lock for state
transitions. The CircuitBreakerCoordinator is also thread-safe for concurrent
access to different domains.

Reference: Step 5 Architecture Blueprint, Section 4a (Error Handling Contract).
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from src.config.constants import (
    CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS,
    CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS,
)
from src.utils.error_handler import CircuitBreaker, CircuitState

logger = logging.getLogger(__name__)


# =============================================================================
# Extended Circuit Breaker (block-aware)
# =============================================================================

class BlockAwareCircuitBreaker(CircuitBreaker):
    """Extended CircuitBreaker that tracks block-specific failure metadata.

    Inherits the core state machine from error_handler.CircuitBreaker and adds:
    - Block type tracking (which block types triggered transitions).
    - Transition history for diagnostics.
    - Integration hooks for the AntiBlockEngine.

    Args:
        name: Identifier (typically the site_id / domain).
        failure_threshold: Block failures before opening circuit.
        recovery_timeout: Seconds to wait in OPEN before probing.
        half_open_max_calls: Successes needed in HALF_OPEN to close.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        recovery_timeout: float = CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS,
        half_open_max_calls: int = CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS,
    ) -> None:
        super().__init__(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            half_open_max_calls=half_open_max_calls,
        )
        self._last_block_type: str = ""
        self._transition_history: list[dict[str, Any]] = []
        self._transition_lock = threading.Lock()

    @property
    def last_block_type(self) -> str:
        """The most recent block type that caused a failure recording."""
        return self._last_block_type

    @property
    def transition_history(self) -> list[dict[str, Any]]:
        """List of state transition records for diagnostics."""
        with self._transition_lock:
            return list(self._transition_history)

    def record_block_failure(self, block_type: str = "unknown") -> None:
        """Record a failure caused by a block detection.

        This extends record_failure() with block-type tracking and
        transition history recording.

        Args:
            block_type: The BlockType.value string (e.g., "ip_block", "captcha").
        """
        previous_state = self.state
        self._last_block_type = block_type
        self.record_failure()
        new_state = self.state

        if previous_state != new_state:
            self._record_transition(previous_state, new_state, block_type)

    def record_success(self) -> None:
        """Record a successful request. Extends base with transition tracking."""
        previous_state = self.state
        super().record_success()
        new_state = self.state

        if previous_state != new_state:
            self._record_transition(previous_state, new_state, "success")

    def _record_transition(
        self,
        from_state: CircuitState,
        to_state: CircuitState,
        trigger: str,
    ) -> None:
        """Record a state transition for diagnostics.

        Args:
            from_state: The state before transition.
            to_state: The state after transition.
            trigger: What triggered the transition (block_type or "success").
        """
        import time
        record = {
            "timestamp": time.time(),
            "from_state": from_state.value,
            "to_state": to_state.value,
            "trigger": trigger,
            "circuit_name": self.name,
        }
        with self._transition_lock:
            self._transition_history.append(record)
            # Cap history at 100 entries
            if len(self._transition_history) > 100:
                self._transition_history = self._transition_history[-100:]

        logger.info(
            "Circuit breaker transition",
            extra={
                "circuit_name": self.name,
                "from_state": from_state.value,
                "to_state": to_state.value,
                "trigger": trigger,
            },
        )

    def get_status(self) -> dict[str, Any]:
        """Get a summary of this circuit breaker's status.

        Returns:
            Dict with state, failure count, last block type, etc.
        """
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_block_type": self._last_block_type,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "transitions": len(self._transition_history),
        }


# =============================================================================
# Circuit Breaker Coordinator (manages per-site breakers)
# =============================================================================

class CircuitBreakerCoordinator:
    """Centralized coordinator for per-site circuit breakers.

    Manages a registry of BlockAwareCircuitBreaker instances, one per domain.
    Provides a unified API for the crawling orchestrator to check circuit
    status and record results.

    Usage:
        coordinator = CircuitBreakerCoordinator()

        # Before making a request:
        if not coordinator.is_allowed("chosun"):
            # Circuit is open, skip this site
            continue

        # After receiving a response:
        if was_blocked:
            coordinator.record_failure("chosun", block_type="ip_block")
        else:
            coordinator.record_success("chosun")

    Thread-safety: Uses a lock for the breakers registry. Individual circuit
    breakers are also thread-safe.

    Attributes:
        failure_threshold: Default failure threshold for new circuit breakers.
        recovery_timeout: Default recovery timeout for new circuit breakers.
        half_open_max_calls: Default half-open success count for new breakers.
    """

    def __init__(
        self,
        failure_threshold: int = CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        recovery_timeout: float = CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS,
        half_open_max_calls: int = CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS,
    ) -> None:
        """Initialize the coordinator.

        Args:
            failure_threshold: Block failures before opening a circuit.
            recovery_timeout: Seconds to wait before probing in HALF_OPEN.
            half_open_max_calls: Successes needed to close from HALF_OPEN.
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self._breakers: dict[str, BlockAwareCircuitBreaker] = {}
        self._lock = threading.Lock()

    def _get_or_create(self, site_id: str) -> BlockAwareCircuitBreaker:
        """Get or create a circuit breaker for a site.

        Thread-safe: uses double-check locking pattern.

        Args:
            site_id: Unique site identifier.

        Returns:
            The BlockAwareCircuitBreaker for this site.
        """
        # Fast path without lock
        breaker = self._breakers.get(site_id)
        if breaker is not None:
            return breaker

        # Slow path with lock
        with self._lock:
            breaker = self._breakers.get(site_id)
            if breaker is not None:
                return breaker

            breaker = BlockAwareCircuitBreaker(
                name=site_id,
                failure_threshold=self.failure_threshold,
                recovery_timeout=self.recovery_timeout,
                half_open_max_calls=self.half_open_max_calls,
            )
            self._breakers[site_id] = breaker
            return breaker

    def is_allowed(self, site_id: str) -> bool:
        """Check if a request to this site should proceed.

        Returns False if the circuit is OPEN (site is being given a cooldown).

        Args:
            site_id: Unique site identifier.

        Returns:
            True if the request should proceed (CLOSED or HALF_OPEN).
            False if the circuit is OPEN.
        """
        breaker = self._get_or_create(site_id)
        return breaker.is_call_allowed()

    def get_state(self, site_id: str) -> CircuitState:
        """Get the current circuit state for a site.

        Args:
            site_id: Unique site identifier.

        Returns:
            CircuitState (CLOSED, OPEN, or HALF_OPEN).
        """
        breaker = self._get_or_create(site_id)
        return breaker.state

    def record_success(self, site_id: str) -> None:
        """Record a successful request for a site.

        May transition HALF_OPEN -> CLOSED after enough successes.

        Args:
            site_id: Unique site identifier.
        """
        breaker = self._get_or_create(site_id)
        breaker.record_success()

    def record_failure(self, site_id: str, block_type: str = "unknown") -> None:
        """Record a blocked/failed request for a site.

        May transition CLOSED -> OPEN or HALF_OPEN -> OPEN.

        Args:
            site_id: Unique site identifier.
            block_type: The BlockType.value string for diagnostics.
        """
        breaker = self._get_or_create(site_id)
        breaker.record_block_failure(block_type)

    def force_half_open(self, site_id: str) -> None:
        """Force a circuit breaker from OPEN to HALF_OPEN for immediate probe.

        Implements the Crawling Absolute Principle (크롤링 절대 원칙):
        NEVER abandon a crawl target. When circuit is OPEN, bypass the
        recovery_timeout and immediately allow a probe with escalated
        anti-block strategy.

        Args:
            site_id: Unique site identifier.
        """
        breaker = self._get_or_create(site_id)
        breaker.force_half_open()

    def reset(self, site_id: str) -> None:
        """Force-reset a circuit breaker to CLOSED state.

        Use this after manual intervention or configuration changes.

        Args:
            site_id: Unique site identifier.
        """
        breaker = self._get_or_create(site_id)
        breaker.reset()
        logger.info("Circuit breaker force-reset", extra={"site_id": site_id})

    def reset_all(self) -> None:
        """Force-reset all circuit breakers to CLOSED state."""
        with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()
        logger.info("All circuit breakers reset", extra={"count": len(self._breakers)})

    def get_open_circuits(self) -> list[str]:
        """Get all site IDs with OPEN circuits (currently blocked).

        Returns:
            List of site IDs where the circuit is OPEN.
        """
        with self._lock:
            return [
                sid for sid, breaker in self._breakers.items()
                if breaker.state == CircuitState.OPEN
            ]

    def get_all_statuses(self) -> dict[str, dict[str, Any]]:
        """Get status summaries for all tracked circuit breakers.

        Returns:
            Dict mapping site_id -> status dict.
        """
        with self._lock:
            return {
                sid: breaker.get_status()
                for sid, breaker in self._breakers.items()
            }

    def get_statistics(self) -> dict[str, Any]:
        """Get aggregate statistics across all circuit breakers.

        Returns:
            Dict with state distribution and total counts.
        """
        state_counts = {s.value: 0 for s in CircuitState}
        with self._lock:
            for breaker in self._breakers.values():
                state_counts[breaker.state.value] += 1

        return {
            "total_circuits": len(self._breakers),
            "state_distribution": state_counts,
            "open_circuits": self.get_open_circuits(),
        }

    def __repr__(self) -> str:
        stats = self.get_statistics()
        return (
            f"CircuitBreakerCoordinator("
            f"total={stats['total_circuits']}, "
            f"open={len(stats['open_circuits'])})"
        )
