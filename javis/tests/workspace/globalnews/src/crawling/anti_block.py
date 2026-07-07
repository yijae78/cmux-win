"""6-Tier Escalation Engine for the GlobalNews crawling system.

Implements the adaptive anti-blocking strategy that automatically escalates
through 6 tiers when block detection signals are received. Each tier applies
progressively more sophisticated countermeasures.

Tiers:
    T1 - Delay adjustment: Increase inter-request delay (5s -> 10s -> 15s) + UA rotation
    T2 - Session cycling: New cookies, Referer chain, header diversification
    T3 - Headless browser: Playwright/Patchright for JS rendering
    T4 - Fingerprint stealth: Patchright + randomized canvas/WebGL/fonts
    T5 - Proxy rotation: Switch to next proxy in the configured pool
    T6 - Never-Abandon Persistence: DynamicBypassEngine strategy dispatch + TotalWar fallback

Reference: Step 5 Architecture Blueprint, Anti-Block System.
Reference: Step 6 Crawling Strategies, per-site tier assignments.
"""

from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass, field
from enum import IntEnum, unique
from pathlib import Path
from typing import Any

from src.config.constants import (
    DATA_CONFIG_DIR,
    DEFAULT_RATE_LIMIT_SECONDS,
    MIN_RATE_LIMIT_SECONDS,
    MAX_RATE_LIMIT_SECONDS,
)
from src.crawling.block_detector import BlockDiagnosis, BlockDetector, BlockType, HttpResponse

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================

@unique
class EscalationTier(IntEnum):
    """6-tier escalation levels. Higher values = more aggressive countermeasures."""
    T1_DELAY = 1
    T2_SESSION = 2
    T3_BROWSER = 3
    T4_FINGERPRINT = 4
    T5_PROXY = 5
    T6_NEVER_ABANDON = 6


@dataclass
class SiteProfile:
    """Per-site escalation state and strategy persistence.

    Tracks the current escalation tier, successful strategies, and block history
    for a single domain. Serializable to JSON for persistence across restarts.

    Attributes:
        site_id: Unique identifier for the site (e.g., "chosun").
        current_tier: The current escalation tier (1-6).
        consecutive_failures: Number of consecutive block detections.
        consecutive_successes: Number of consecutive successes at current tier.
        total_blocks: Lifetime block count.
        total_successes: Lifetime success count.
        last_block_type: The most recent block type observed.
        last_escalation_time: Epoch timestamp of last tier change.
        successful_tier: The lowest tier that consistently works (for de-escalation target).
        delay_seconds: Current inter-request delay for this site.
        block_history: Recent block types for pattern analysis (capped at 50).
    """
    site_id: str
    current_tier: int = 1
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    total_blocks: int = 0
    total_successes: int = 0
    last_block_type: str = ""
    last_escalation_time: float = 0.0
    successful_tier: int = 1
    delay_seconds: float = DEFAULT_RATE_LIMIT_SECONDS
    block_history: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON persistence."""
        return {
            "site_id": self.site_id,
            "current_tier": self.current_tier,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "total_blocks": self.total_blocks,
            "total_successes": self.total_successes,
            "last_block_type": self.last_block_type,
            "last_escalation_time": self.last_escalation_time,
            "successful_tier": self.successful_tier,
            "delay_seconds": self.delay_seconds,
            "block_history": self.block_history[-50:],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SiteProfile:
        """Deserialize from dict."""
        return cls(
            site_id=data.get("site_id", "unknown"),
            current_tier=data.get("current_tier", 1),
            consecutive_failures=data.get("consecutive_failures", 0),
            consecutive_successes=data.get("consecutive_successes", 0),
            total_blocks=data.get("total_blocks", 0),
            total_successes=data.get("total_successes", 0),
            last_block_type=data.get("last_block_type", ""),
            last_escalation_time=data.get("last_escalation_time", 0.0),
            successful_tier=data.get("successful_tier", 1),
            delay_seconds=data.get("delay_seconds", DEFAULT_RATE_LIMIT_SECONDS),
            block_history=data.get("block_history", [])[-50:],
        )


@dataclass
class EscalationDecision:
    """Result of an escalation/de-escalation decision.

    Attributes:
        site_id: The site this decision applies to.
        previous_tier: Tier before the decision.
        new_tier: Tier after the decision.
        action: Human-readable description of the action taken.
        reason: Evidence/rationale for the decision.
        delay_seconds: The delay to apply before the next request.
    """
    site_id: str
    previous_tier: int
    new_tier: int
    action: str
    reason: str
    delay_seconds: float


# =============================================================================
# Tier Strategy Implementations
# =============================================================================

@dataclass
class TierStrategy:
    """Parameters for a single escalation tier.

    Attributes:
        tier: The tier level.
        name: Human-readable name.
        min_delay: Minimum delay in seconds.
        max_delay: Maximum delay in seconds.
        requires_browser: Whether this tier needs a headless browser.
        requires_proxy: Whether this tier needs proxy rotation.
        requires_fingerprint: Whether this tier needs fingerprint randomization.
        description: What this tier does.
    """
    tier: int
    name: str
    min_delay: float
    max_delay: float
    requires_browser: bool = False
    requires_proxy: bool = False
    requires_fingerprint: bool = False
    description: str = ""


# Tier strategy definitions from the architecture blueprint
TIER_STRATEGIES: dict[int, TierStrategy] = {
    1: TierStrategy(
        tier=1,
        name="Delay Adjustment + UA Rotation",
        min_delay=5.0,
        max_delay=15.0,
        description="Increase inter-request delay (5->10->15s) and rotate User-Agent.",
    ),
    2: TierStrategy(
        tier=2,
        name="Session Cycling + Header Diversification",
        min_delay=8.0,
        max_delay=20.0,
        description="Clear cookies, new session, Referer chain, diversified headers.",
    ),
    3: TierStrategy(
        tier=3,
        name="Headless Browser (Playwright/Patchright)",
        min_delay=10.0,
        max_delay=25.0,
        requires_browser=True,
        description="Full browser rendering for JS-heavy sites.",
    ),
    4: TierStrategy(
        tier=4,
        name="Fingerprint Stealth (Patchright + fingerprint-suite)",
        min_delay=10.0,
        max_delay=30.0,
        requires_browser=True,
        requires_fingerprint=True,
        description="Randomized canvas/WebGL/fonts to evade fingerprinting.",
    ),
    5: TierStrategy(
        tier=5,
        name="Proxy Rotation",
        min_delay=10.0,
        max_delay=30.0,
        requires_proxy=True,
        description="Switch to next proxy in pool for IP rotation.",
    ),
    6: TierStrategy(
        tier=6,
        name="Never-Abandon Persistence (크롤링 절대 원칙)",
        min_delay=30.0,
        max_delay=120.0,
        requires_browser=True,
        requires_proxy=True,
        requires_fingerprint=True,
        description=(
            "Maximum escalation with ALL countermeasures active. "
            "Cycles through alternative sources (RSS, Google Cache, AMP). "
            "NEVER surrenders -- keeps retrying with different approaches."
        ),
    ),
}


# =============================================================================
# Anti-Block Engine
# =============================================================================

# De-escalation threshold: how many consecutive successes before we drop a tier
_DEESCALATION_SUCCESS_THRESHOLD = 10

# Escalation threshold: how many consecutive failures before we escalate
_ESCALATION_FAILURE_THRESHOLD = 3

# Cooldown after escalation: minimum seconds before another tier change
_ESCALATION_COOLDOWN_SECONDS = 60.0

# Profile persistence path
_SITE_PROFILES_PATH = DATA_CONFIG_DIR / "site_profiles.json"


class AntiBlockEngine:
    """6-Tier Escalation Engine with self-modifying strategy.

    Manages per-site escalation state and makes tier-change decisions
    based on block detection signals. Persists successful strategies
    to disk for resume after restart.

    Usage:
        engine = AntiBlockEngine()
        # After each request:
        decision = engine.record_result(
            site_id="chosun",
            response=response,
            was_blocked=True,
            diagnosis=block_diagnosis,
        )
        # Apply the decision:
        strategy = engine.get_strategy(site_id="chosun")
        await asyncio.sleep(strategy.delay_seconds)

    Thread-safety: This class is NOT thread-safe. Use one instance per
    async event loop, or add external synchronization.

    Attributes:
        detector: BlockDetector instance for response analysis.
        profiles: Per-site profile dict.
        profiles_path: Path to the JSON persistence file.
    """

    def __init__(
        self,
        detector: BlockDetector | None = None,
        profiles_path: Path | None = None,
        auto_load: bool = True,
    ) -> None:
        """Initialize the AntiBlockEngine.

        Args:
            detector: BlockDetector to use for response analysis.
                Defaults to a new BlockDetector with default settings.
            profiles_path: Path to the site_profiles.json persistence file.
                Defaults to data/config/site_profiles.json.
            auto_load: Whether to automatically load persisted profiles on init.
        """
        self.detector = detector or BlockDetector()
        self.profiles: dict[str, SiteProfile] = {}
        self.profiles_path = profiles_path or _SITE_PROFILES_PATH

        if auto_load:
            self._load_profiles()

    # -------------------------------------------------------------------------
    # Profile Management
    # -------------------------------------------------------------------------

    def get_profile(self, site_id: str) -> SiteProfile:
        """Get or create a SiteProfile for the given site.

        Args:
            site_id: Unique site identifier.

        Returns:
            The existing or newly created SiteProfile.
        """
        if site_id not in self.profiles:
            self.profiles[site_id] = SiteProfile(site_id=site_id)
        return self.profiles[site_id]

    def get_strategy(self, site_id: str) -> TierStrategy:
        """Get the current tier strategy for a site.

        Args:
            site_id: Unique site identifier.

        Returns:
            The TierStrategy for the site's current tier.
        """
        profile = self.get_profile(site_id)
        return TIER_STRATEGIES[profile.current_tier]

    def get_delay(self, site_id: str) -> float:
        """Calculate the delay to apply before the next request to this site.

        Adds jitter to the base delay to avoid request pattern detection.

        Args:
            site_id: Unique site identifier.

        Returns:
            Delay in seconds (with jitter).
        """
        profile = self.get_profile(site_id)
        strategy = TIER_STRATEGIES[profile.current_tier]
        base_delay = profile.delay_seconds
        # Add 10-25% jitter
        jitter = base_delay * random.uniform(0.1, 0.25)
        return min(base_delay + jitter, MAX_RATE_LIMIT_SECONDS)

    # -------------------------------------------------------------------------
    # Core Decision Logic
    # -------------------------------------------------------------------------

    def record_result(
        self,
        site_id: str,
        response: HttpResponse | None = None,
        was_blocked: bool = False,
        diagnosis: BlockDiagnosis | None = None,
    ) -> EscalationDecision:
        """Record a request result and decide whether to escalate/de-escalate.

        This is the primary entry point for the escalation state machine.
        Call this after every HTTP request to a site.

        Args:
            site_id: Unique site identifier.
            response: The HTTP response (optional; used for auto-detection).
            was_blocked: Whether the caller already determined this was a block.
            diagnosis: Pre-computed BlockDiagnosis (optional; skips detection).

        Returns:
            An EscalationDecision describing what changed and what to do next.
        """
        profile = self.get_profile(site_id)
        previous_tier = profile.current_tier

        # Auto-detect blocks if no explicit diagnosis provided
        if diagnosis is None and response is not None and not was_blocked:
            diagnosis = self.detector.primary_diagnosis(response)
            if diagnosis is not None:
                was_blocked = True

        if was_blocked:
            return self._handle_block(profile, diagnosis)
        else:
            return self._handle_success(profile)

    def _handle_block(
        self,
        profile: SiteProfile,
        diagnosis: BlockDiagnosis | None,
    ) -> EscalationDecision:
        """Handle a blocked request: update counters and possibly escalate.

        Args:
            profile: The site profile to update.
            diagnosis: The block diagnosis (may be None if block was inferred).

        Returns:
            EscalationDecision with the action taken.
        """
        previous_tier = profile.current_tier
        profile.consecutive_failures += 1
        profile.consecutive_successes = 0
        profile.total_blocks += 1

        if diagnosis:
            profile.last_block_type = diagnosis.block_type.value
            profile.block_history.append(diagnosis.block_type.value)
            if len(profile.block_history) > 50:
                profile.block_history = profile.block_history[-50:]

        # Decide whether to escalate
        should_escalate = (
            profile.consecutive_failures >= _ESCALATION_FAILURE_THRESHOLD
            and profile.current_tier < EscalationTier.T6_NEVER_ABANDON
        )

        # Fast-track escalation: if the diagnosis recommends a higher tier, jump there
        if diagnosis and diagnosis.recommended_tier > profile.current_tier:
            should_escalate = True

        # Cooldown check: avoid rapid tier thrashing
        now = time.time()
        if should_escalate and (now - profile.last_escalation_time) < _ESCALATION_COOLDOWN_SECONDS:
            # Still in cooldown, do not escalate yet
            should_escalate = False

        if should_escalate:
            # Escalate to the higher of current+1 or the recommended tier
            new_tier = profile.current_tier + 1
            if diagnosis and diagnosis.recommended_tier > new_tier:
                new_tier = min(diagnosis.recommended_tier, EscalationTier.T6_NEVER_ABANDON)
            new_tier = min(new_tier, EscalationTier.T6_NEVER_ABANDON)

            profile.current_tier = new_tier
            profile.consecutive_failures = 0
            profile.last_escalation_time = now

            # Update delay based on new tier
            strategy = TIER_STRATEGIES[new_tier]
            profile.delay_seconds = strategy.min_delay

            action = f"ESCALATED to Tier {new_tier} ({strategy.name})"
            reason = (
                f"Block detected (type={profile.last_block_type}, "
                f"consecutive_failures={_ESCALATION_FAILURE_THRESHOLD})"
            )
            if diagnosis:
                reason += f"; evidence: {'; '.join(diagnosis.evidence[:3])}"

            logger.warning(
                "Anti-block escalation",
                extra={
                    "site_id": profile.site_id,
                    "previous_tier": previous_tier,
                    "new_tier": new_tier,
                    "block_type": profile.last_block_type,
                    "consecutive_failures": profile.consecutive_failures,
                },
            )
        else:
            # No escalation yet; increase delay within current tier
            strategy = TIER_STRATEGIES[profile.current_tier]
            delay_increment = (strategy.max_delay - strategy.min_delay) / _ESCALATION_FAILURE_THRESHOLD
            profile.delay_seconds = min(
                profile.delay_seconds + delay_increment,
                strategy.max_delay,
            )

            action = f"STAY at Tier {profile.current_tier}, increased delay to {profile.delay_seconds:.1f}s"
            reason = (
                f"Block #{profile.consecutive_failures} "
                f"(threshold={_ESCALATION_FAILURE_THRESHOLD} for escalation)"
            )

        self._save_profiles()

        return EscalationDecision(
            site_id=profile.site_id,
            previous_tier=previous_tier,
            new_tier=profile.current_tier,
            action=action,
            reason=reason,
            delay_seconds=profile.delay_seconds,
        )

    def _handle_success(self, profile: SiteProfile) -> EscalationDecision:
        """Handle a successful request: update counters and possibly de-escalate.

        Args:
            profile: The site profile to update.

        Returns:
            EscalationDecision with the action taken.
        """
        previous_tier = profile.current_tier
        profile.consecutive_successes += 1
        profile.consecutive_failures = 0
        profile.total_successes += 1

        # Track the successful tier
        if profile.current_tier < profile.successful_tier or profile.successful_tier == 1:
            profile.successful_tier = profile.current_tier

        # De-escalation: after enough successes at current tier, try to step down
        should_deescalate = (
            profile.consecutive_successes >= _DEESCALATION_SUCCESS_THRESHOLD
            and profile.current_tier > 1
        )

        # Cooldown check
        now = time.time()
        if should_deescalate and (now - profile.last_escalation_time) < _ESCALATION_COOLDOWN_SECONDS:
            should_deescalate = False

        if should_deescalate:
            new_tier = max(profile.current_tier - 1, 1)
            profile.current_tier = new_tier
            profile.consecutive_successes = 0
            profile.last_escalation_time = now

            strategy = TIER_STRATEGIES[new_tier]
            profile.delay_seconds = strategy.min_delay

            action = f"DE-ESCALATED to Tier {new_tier} ({strategy.name})"
            reason = (
                f"Consecutive successes={_DEESCALATION_SUCCESS_THRESHOLD} "
                f"at Tier {previous_tier}"
            )

            logger.info(
                "Anti-block de-escalation",
                extra={
                    "site_id": profile.site_id,
                    "previous_tier": previous_tier,
                    "new_tier": new_tier,
                    "consecutive_successes": _DEESCALATION_SUCCESS_THRESHOLD,
                },
            )
        else:
            action = f"STAY at Tier {profile.current_tier} (success #{profile.consecutive_successes})"
            reason = f"Awaiting {_DEESCALATION_SUCCESS_THRESHOLD} successes for de-escalation"

        self._save_profiles()

        return EscalationDecision(
            site_id=profile.site_id,
            previous_tier=previous_tier,
            new_tier=profile.current_tier,
            action=action,
            reason=reason,
            delay_seconds=profile.delay_seconds,
        )

    # -------------------------------------------------------------------------
    # Convenience Methods
    # -------------------------------------------------------------------------

    def is_at_max_escalation(self, site_id: str) -> bool:
        """Check if a site has reached Tier 6 (Never-Abandon persistence loop).

        Args:
            site_id: Unique site identifier.

        Returns:
            True if the site is at Tier 6.
        """
        profile = self.get_profile(site_id)
        return profile.current_tier >= EscalationTier.T6_NEVER_ABANDON

    def reset_site(self, site_id: str) -> None:
        """Reset a site back to Tier 1 (e.g., after manual intervention).

        Args:
            site_id: Unique site identifier.
        """
        profile = self.get_profile(site_id)
        profile.current_tier = 1
        profile.consecutive_failures = 0
        profile.consecutive_successes = 0
        profile.delay_seconds = DEFAULT_RATE_LIMIT_SECONDS
        profile.last_escalation_time = 0.0
        self._save_profiles()
        logger.info("Site reset to Tier 1", extra={"site_id": site_id})

    def get_all_max_escalation_sites(self) -> list[str]:
        """Get all sites currently at Tier 6 (Never-Abandon persistence loop).

        Returns:
            List of site IDs at Tier 6.
        """
        return [
            sid for sid, profile in self.profiles.items()
            if profile.current_tier >= EscalationTier.T6_NEVER_ABANDON
        ]

    def get_statistics(self) -> dict[str, Any]:
        """Get aggregate statistics across all tracked sites.

        Returns:
            Dict with tier distribution, total blocks/successes, paused sites.
        """
        tier_distribution: dict[int, int] = {t: 0 for t in range(1, 7)}
        total_blocks = 0
        total_successes = 0
        for profile in self.profiles.values():
            tier_distribution[profile.current_tier] = tier_distribution.get(profile.current_tier, 0) + 1
            total_blocks += profile.total_blocks
            total_successes += profile.total_successes

        return {
            "total_sites": len(self.profiles),
            "tier_distribution": tier_distribution,
            "total_blocks": total_blocks,
            "total_successes": total_successes,
            "block_rate": total_blocks / max(total_blocks + total_successes, 1),
            "paused_sites": self.get_all_max_escalation_sites(),
        }

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def _save_profiles(self) -> None:
        """Persist all site profiles to disk as JSON.

        Gracefully handles write failures (logs error, does not raise).
        """
        try:
            self.profiles_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                sid: profile.to_dict()
                for sid, profile in self.profiles.items()
            }
            # Atomic write via temp file
            tmp_path = self.profiles_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            tmp_path.replace(self.profiles_path)
        except Exception:
            logger.warning("Failed to persist site profiles", exc_info=True)

    def _load_profiles(self) -> None:
        """Load site profiles from disk.

        Gracefully handles missing/corrupt files (starts fresh).
        """
        if not self.profiles_path.exists():
            return
        try:
            with open(self.profiles_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for sid, profile_dict in data.items():
                self.profiles[sid] = SiteProfile.from_dict(profile_dict)
            logger.info(
                "Loaded site profiles",
                extra={"count": len(self.profiles), "path": str(self.profiles_path)},
            )
        except Exception:
            logger.warning("Failed to load site profiles, starting fresh", exc_info=True)
            self.profiles = {}

    def __repr__(self) -> str:
        return (
            f"AntiBlockEngine(sites={len(self.profiles)}, "
            f"paused={len(self.get_all_max_escalation_sites())})"
        )
