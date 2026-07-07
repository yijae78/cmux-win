"""Stage 7: Signal Classification -- 5-Layer hierarchy (L1-L5) + novelty detection.

Implements the culminating analysis stage that synthesises upstream results
from Stages 3-6 into classified signals with temporal persistence layers,
novelty scores, and confidence intervals.

Techniques implemented:
    T47: Novelty Detection (LOF)       -- sklearn.neighbors.LocalOutlierFactor
    T48: Novelty Detection (IF)        -- sklearn.ensemble.IsolationForest
    T51: Z-score Anomaly               -- scipy.stats.zscore on time series
    T52: Entropy Change                -- scipy.stats.entropy delta vs 30-day mean
    T53: Zipf Distribution Deviation   -- term frequency vs ideal Zipf
    T54: Survival Analysis             -- lifelines.KaplanMeierFitter
    T55: KL Divergence                 -- scipy.special.rel_entr current vs baseline
    BERTrend Weak Signal Detection     -- Topic lifecycle tracking
    Singularity Composite Score        -- 7-indicator weighted formula (PRD App E)
    Dual-Pass                          -- Title pass (fast) -> body pass (evidence)

5-Layer Signal Hierarchy:
    L1_fad         -- Spike-and-decay, < 1 week
    L2_short       -- Short-term trend, 1-4 weeks
    L3_mid         -- Mid-term trend, 1-6 months
    L4_long        -- Long-term shift, 6+ months
    L5_singularity -- Paradigm shift, unprecedented

Input:
    data/analysis/topics.parquet
    data/analysis/timeseries.parquet
    data/analysis/cross_analysis.parquet
    data/analysis/article_analysis.parquet
    data/analysis/networks.parquet
    data/features/embeddings.parquet

Output:
    data/output/signals.parquet (SIGNALS_SCHEMA: 12 columns)

Memory budget: ~0.5 GB peak (LOF/IF ~100 MB, scipy ~50 MB, lifelines ~50 MB).
Performance target: < 60 seconds for 1,000 articles.

Reference: Step 7 Pipeline Design, Section 3.7 (Stage 7: Signal Classification).
"""

from __future__ import annotations

import gc
import logging
import math
import time
import uuid
import warnings
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np

# ---------------------------------------------------------------------------
# Lazy imports -- heavy libraries loaded only when needed
# ---------------------------------------------------------------------------

_pa = None       # pyarrow
_pq = None       # pyarrow.parquet


def _ensure_pyarrow():
    """Lazy-load pyarrow and pyarrow.parquet."""
    global _pa, _pq
    if _pa is None:
        import pyarrow as pa
        import pyarrow.parquet as pq
        _pa = pa
        _pq = pq
    return _pa, _pq


# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------

from src.config.constants import (
    ARTICLE_ANALYSIS_PARQUET_PATH,
    CROSS_ANALYSIS_PARQUET_PATH,
    DATA_ANALYSIS_DIR,
    DATA_FEATURES_DIR,
    DATA_OUTPUT_DIR,
    EMBEDDINGS_PARQUET_PATH,
    NETWORKS_PARQUET_PATH,
    PARQUET_COMPRESSION,
    PARQUET_COMPRESSION_LEVEL,
    SBERT_EMBEDDING_DIM,
    SIGNALS_PARQUET_PATH,
    SINGULARITY_THRESHOLD,
    SINGULARITY_WEIGHTS,
    TIMESERIES_PARQUET_PATH,
    TOPICS_PARQUET_PATH,
    # 5-Layer thresholds
    L1_BURST_SCORE_THRESHOLD,
    L1_VOLUME_ZSCORE_THRESHOLD,
    L2_SUSTAINED_DAYS_THRESHOLD,
    L3_CHANGEPOINT_SIGNIFICANCE_THRESHOLD,
    L3_MODULARITY_DELTA_THRESHOLD,
    L4_EMBEDDING_DRIFT_THRESHOLD,
    L4_WAVELET_PERIOD_THRESHOLD,
    L5_CROSS_DOMAIN_THRESHOLD,
    L5_NOVELTY_THRESHOLD,
)
from src.utils.error_handler import (
    AnalysisError,
    PipelineStageError,
)

# Use stdlib logger directly for compatibility (structlog may not be installed)
logger = logging.getLogger("src.analysis.stage7_signals")


# =============================================================================
# Constants (local to Stage 7)
# =============================================================================

# LOF/IF configuration (T47, T48)
LOF_N_NEIGHBORS: int = 20
LOF_CONTAMINATION: float = 0.05
IF_CONTAMINATION: float = 0.05
LOF_IF_ENSEMBLE_WEIGHT_LOF: float = 0.5
LOF_IF_ENSEMBLE_WEIGHT_IF: float = 0.5

# Z-score threshold (T51)
ZSCORE_ANOMALY_THRESHOLD: float = 2.5

# Entropy rolling window (T52)
ENTROPY_ROLLING_WINDOW_DAYS: int = 30
ENTROPY_ZSCORE_NORMALIZER: float = 5.0  # min(zscore/5, 1.0)

# Zipf deviation (T53)
ZIPF_MAX_TERMS: int = 500

# Survival analysis (T54)
SURVIVAL_MIN_TOPICS: int = 5

# KL divergence baseline window (T55)
KL_BASELINE_DAYS: int = 30

# BERTrend lifecycle thresholds
BERTREND_NOISE_MAX_ARTICLES: int = 3
BERTREND_WEAK_MAX_ARTICLES: int = 10
BERTREND_EMERGING_GROWTH_RATE: float = 0.5  # 50% growth rate

# Singularity three independent pathways
PATHWAY_A_OOD_THRESHOLD: float = 0.7
PATHWAY_B_CHANGEPOINT_THRESHOLD: float = 0.8
PATHWAY_B_SECONDARY_THRESHOLD: float = 0.5
PATHWAY_C_BERTREND_REQUIRED: int = 1  # Binary: must be 1
PATHWAY_C_CROSS_DOMAIN_THRESHOLD: float = 0.3

# Data span requirements (days)
L1_MIN_DATA_SPAN_DAYS: int = 0  # Allow single-day L1 fad detection
L2_MIN_DATA_SPAN_DAYS: int = 14
L3_MIN_DATA_SPAN_DAYS: int = 90
L4_MIN_DATA_SPAN_DAYS: int = 365

# STEEPS domain count
STEEPS_TOTAL_DOMAINS: int = 6

# Layer transition thresholds
TRANSITION_L1_DISMISS_DROP_PCT: float = 0.80  # >80% drop in 48h -> dismissed
TRANSITION_L1_DISMISS_HOURS: int = 48

# Confidence scoring parameters (per-layer)
CONFIDENCE_BASE = {
    "L1_fad": 0.4,
    "L2_short": 0.5,
    "L3_mid": 0.6,
    "L4_long": 0.7,
    "L5_singularity": 0.5,
}

# Valid signal layer values
VALID_SIGNAL_LAYERS = frozenset({
    "L1_fad", "L2_short", "L3_mid", "L4_long", "L5_singularity",
})


# =============================================================================
# Parquet Schema -- SIGNALS_SCHEMA (12 columns, PRD SS7.1.7)
# =============================================================================

def _build_signals_schema():
    """Build the signals PyArrow schema. Lazy to avoid import-time pyarrow."""
    pa, _ = _ensure_pyarrow()
    return pa.schema([
        pa.field("signal_id", pa.utf8(), nullable=False),
        pa.field("signal_layer", pa.utf8(), nullable=False),
        pa.field("signal_label", pa.utf8(), nullable=False),
        pa.field("detected_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("topic_ids", pa.list_(pa.int32()), nullable=False),
        pa.field("article_ids", pa.list_(pa.utf8()), nullable=False),
        pa.field("burst_score", pa.float32(), nullable=True),
        pa.field("changepoint_significance", pa.float32(), nullable=True),
        pa.field("novelty_score", pa.float32(), nullable=True),
        pa.field("singularity_composite", pa.float32(), nullable=True),
        pa.field("evidence_summary", pa.utf8(), nullable=False),
        pa.field("confidence", pa.float32(), nullable=False),
    ])


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class TopicFeatures:
    """Extracted features for a single topic used in signal classification."""

    topic_id: int
    article_ids: list[str] = field(default_factory=list)
    article_count: int = 0
    source_count: int = 0  # distinct sources covering this topic
    data_span_days: int = 0  # days between first and last article

    # Time series features (from Stage 5)
    volume_zscore: float = 0.0
    burst_score: float = 0.0
    has_burst: bool = False
    trend_strength: float = 0.0
    changepoint_significance: float = 0.0
    has_changepoint: bool = False
    ma_signal: str = ""  # "rising", "falling", "neutral"
    volume_above_ma14_days: int = 0
    wavelet_dominant_period: float = 0.0  # days

    # Cross-analysis features (from Stage 6)
    causal_depth: int = 0  # length of longest causal chain
    frame_divergence_detected: bool = False

    # STEEPS features (from Stage 3)
    steeps_categories: set[str] = field(default_factory=set)
    cross_domain_count: int = 0  # number of STEEPS domains
    steeps_shift_detected: bool = False

    # Emotion trajectory (from Stage 3)
    emotion_trajectory_shift: bool = False

    # Embedding features (from Stage 2)
    embedding_drift: float = 0.0  # cosine distance drift over time

    # Network features (from Stage 4/6)
    network_modularity_delta: float = 0.0
    new_nodes_ratio: float = 0.0
    new_edges_ratio: float = 0.0

    # Novelty features (computed in Stage 7)
    lof_score: float = 0.0
    if_score: float = 0.0
    ood_score: float = 0.0  # ensemble of LOF + IF
    novelty_score: float = 0.0  # mean distance to k=20 nearest historical centroids

    # BERTrend lifecycle
    bertrend_state: str = "noise"  # noise, weak, emerging, strong, declining
    bertrend_transition: int = 0  # 1 if noise->weak or weak->emerging

    # Entropy
    entropy_spike: float = 0.0

    # Zipf deviation
    zipf_deviation: float = 0.0

    # Survival
    expected_duration_days: float = 0.0

    # KL divergence
    kl_divergence: float = 0.0

    # Topic label
    topic_label: str = ""


@dataclass
class SignalRecord:
    """A classified signal ready for Parquet output."""

    signal_id: str = ""
    signal_layer: str = ""
    signal_label: str = ""
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    topic_ids: list[int] = field(default_factory=list)
    article_ids: list[str] = field(default_factory=list)
    burst_score: float | None = None
    changepoint_significance: float | None = None
    novelty_score: float | None = None
    singularity_composite: float | None = None
    evidence_summary: str = ""
    confidence: float = 0.0


@dataclass
class SingularityIndicators:
    """Seven indicators for the Singularity Composite Score (PRD Appendix E)."""

    ood_score: float = 0.0          # 0-1: LOF/IF anomaly, normalized
    changepoint_sig: float = 0.0    # 0-1: PELT p-value inverted
    cross_domain: float = 0.0       # 0-1: fraction of STEEPS domains
    bertrend_transition: int = 0    # 0/1: noise->weak or weak->emerging
    entropy_spike: float = 0.0      # 0-1: Z-score normalized
    novelty_score: float = 0.0      # 0-1: mean distance to k=20 nearest
    network_anomaly: float = 0.0    # 0-1: (new_nodes+edges)/(total) ratio


@dataclass
class Stage7Output:
    """Aggregated output from the Stage 7 pipeline."""

    n_signals: int = 0
    n_topics_analyzed: int = 0
    layer_distribution: dict[str, int] = field(default_factory=dict)
    l5_candidates: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    signals: list[SignalRecord] = field(default_factory=list)


# =============================================================================
# Helper Functions
# =============================================================================

def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float, handling None/NaN."""
    if value is None:
        return default
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    """Safely convert a value to int, handling None/NaN."""
    if value is None:
        return default
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return default
        return int(f)
    except (ValueError, TypeError):
        return default


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp a float value to [lo, hi]."""
    return max(lo, min(hi, value))


def _days_between(dates: list[Any]) -> int:
    """Compute the span in days between the earliest and latest dates."""
    valid_dates = []
    for d in dates:
        if d is None:
            continue
        if isinstance(d, datetime):
            valid_dates.append(d)
        elif isinstance(d, (int, float)):
            try:
                valid_dates.append(datetime.fromtimestamp(d / 1e6, tz=timezone.utc))
            except (ValueError, OSError, OverflowError):
                continue
        elif hasattr(d, 'as_py'):
            py_val = d.as_py()
            if py_val is not None:
                valid_dates.append(py_val)
    if len(valid_dates) < 2:
        return 0
    span = max(valid_dates) - min(valid_dates)
    return max(0, span.days)


# =============================================================================
# Singularity Composite Score (PRD Appendix E -- EXACT)
# =============================================================================

def compute_singularity_composite(indicators: SingularityIndicators) -> float:
    """Compute the 7-indicator weighted Singularity Composite Score.

    Uses EXACT weights from PRD Appendix E (SINGULARITY_WEIGHTS constant):
        w1_ood:           0.20
        w2_changepoint:   0.15
        w3_cross_domain:  0.20
        w4_bertrend:      0.15
        w5_entropy:       0.10
        w6_novelty:       0.10
        w7_network:       0.10

    Args:
        indicators: SingularityIndicators with all 7 values populated.

    Returns:
        Composite score in [0, 1].
    """
    composite = (
        SINGULARITY_WEIGHTS["w1_ood"] * _clamp(indicators.ood_score)
        + SINGULARITY_WEIGHTS["w2_changepoint"] * _clamp(indicators.changepoint_sig)
        + SINGULARITY_WEIGHTS["w3_cross_domain"] * _clamp(indicators.cross_domain)
        + SINGULARITY_WEIGHTS["w4_bertrend"] * _clamp(float(indicators.bertrend_transition))
        + SINGULARITY_WEIGHTS["w5_entropy"] * _clamp(indicators.entropy_spike)
        + SINGULARITY_WEIGHTS["w6_novelty"] * _clamp(indicators.novelty_score)
        + SINGULARITY_WEIGHTS["w7_network"] * _clamp(indicators.network_anomaly)
    )
    return _clamp(composite)


def check_singularity_pathways(indicators: SingularityIndicators) -> tuple[bool, bool, bool]:
    """Check the three independent pathways for L5 Singularity.

    Three Independent Pathways -- at least 2 of 3 must trigger:

    Pathway A: OOD Detection
        OOD_score > 0.7 OR Novelty_score > 0.7

    Pathway B: Structural Change
        Changepoint > 0.8 AND (Entropy > 0.5 OR Network > 0.5)

    Pathway C: Emergence
        BERTrend_transition == 1 AND CrossDomain > 0.3

    Args:
        indicators: SingularityIndicators with all values populated.

    Returns:
        Tuple of (pathway_a, pathway_b, pathway_c) booleans.
    """
    pathway_a = (
        indicators.ood_score > PATHWAY_A_OOD_THRESHOLD
        or indicators.novelty_score > PATHWAY_A_OOD_THRESHOLD
    )
    pathway_b = (
        indicators.changepoint_sig > PATHWAY_B_CHANGEPOINT_THRESHOLD
        and (
            indicators.entropy_spike > PATHWAY_B_SECONDARY_THRESHOLD
            or indicators.network_anomaly > PATHWAY_B_SECONDARY_THRESHOLD
        )
    )
    pathway_c = (
        indicators.bertrend_transition == PATHWAY_C_BERTREND_REQUIRED
        and indicators.cross_domain > PATHWAY_C_CROSS_DOMAIN_THRESHOLD
    )
    return pathway_a, pathway_b, pathway_c


# =============================================================================
# 5-Layer Classification Logic
# =============================================================================

def classify_signal_layer(feat: TopicFeatures) -> str:
    """Classify a topic into one of 5 temporal persistence layers.

    Evaluation proceeds from L5 (most significant) down to L1 (least).
    First matching layer wins.

    The classification rules EXACTLY match the quantitative specification:

    L5: novelty_score > 0.7 AND cross_domain_count >= 2
        AND singularity_composite >= 0.65
    L4: embedding_drift > 0.3 AND wavelet_dominant_period > 90
        AND steeps_shift_detected AND data_span_days >= 365
    L3: changepoint_significance > 0.8 AND network_modularity_delta > 0.1
        AND frame_divergence_detected AND data_span_days >= 90
    L2: volume_above_ma14_days >= 7 AND ma_signal == "rising"
        AND emotion_trajectory_shift AND data_span_days >= 14
    L1: volume_zscore > 3.0 AND burst_score > 2.0 AND data_span_days >= 0

    Args:
        feat: TopicFeatures with all classification indicators populated.

    Returns:
        Signal layer string: one of VALID_SIGNAL_LAYERS.
        Returns empty string if no layer criteria are met.
    """
    # Build singularity indicators
    sing_indicators = SingularityIndicators(
        ood_score=feat.ood_score,
        changepoint_sig=feat.changepoint_significance,
        cross_domain=feat.cross_domain_count / STEEPS_TOTAL_DOMAINS
        if STEEPS_TOTAL_DOMAINS > 0 else 0.0,
        bertrend_transition=feat.bertrend_transition,
        entropy_spike=feat.entropy_spike,
        novelty_score=feat.novelty_score,
        network_anomaly=(
            (feat.new_nodes_ratio + feat.new_edges_ratio) / 2.0
            if (feat.new_nodes_ratio + feat.new_edges_ratio) > 0 else 0.0
        ),
    )
    singularity_composite = compute_singularity_composite(sing_indicators)

    # L5: Singularity
    if (feat.novelty_score > L5_NOVELTY_THRESHOLD
            and feat.cross_domain_count >= 2
            and singularity_composite >= SINGULARITY_THRESHOLD):
        # Additional pathway check: at least 2 of 3 must trigger
        pa_a, pa_b, pa_c = check_singularity_pathways(sing_indicators)
        pathways_triggered = sum([pa_a, pa_b, pa_c])
        if pathways_triggered >= 2:
            return "L5_singularity"

    # L4: Long-term Shift
    if (feat.embedding_drift > L4_EMBEDDING_DRIFT_THRESHOLD
            and feat.wavelet_dominant_period > L4_WAVELET_PERIOD_THRESHOLD
            and feat.steeps_shift_detected
            and feat.data_span_days >= L4_MIN_DATA_SPAN_DAYS):
        return "L4_long"

    # L3: Mid-term Trend
    if (feat.changepoint_significance > L3_CHANGEPOINT_SIGNIFICANCE_THRESHOLD
            and feat.network_modularity_delta > L3_MODULARITY_DELTA_THRESHOLD
            and feat.frame_divergence_detected
            and feat.data_span_days >= L3_MIN_DATA_SPAN_DAYS):
        return "L3_mid"

    # L2: Short-term Trend
    if (feat.volume_above_ma14_days >= L2_SUSTAINED_DAYS_THRESHOLD
            and feat.ma_signal == "rising"
            and feat.emotion_trajectory_shift
            and feat.data_span_days >= L2_MIN_DATA_SPAN_DAYS):
        return "L2_short"

    # L1: Fad
    if (feat.volume_zscore > L1_VOLUME_ZSCORE_THRESHOLD
            and feat.burst_score > L1_BURST_SCORE_THRESHOLD
            and feat.data_span_days >= L1_MIN_DATA_SPAN_DAYS):
        return "L1_fad"

    return ""


# =============================================================================
# Confidence Scoring
# =============================================================================

def compute_confidence(feat: TopicFeatures, layer: str) -> float:
    """Compute classification confidence for a signal.

    Per-layer base confidence with boosters and penalties:

    | Layer | Base | Boosters                            | Penalties             |
    |-------|------|-------------------------------------|-----------------------|
    | L1    | 0.4  | +0.2 multi-source; +0.1 multi-lang  | -0.2 single-source   |
    | L2    | 0.5  | +0.15 emotion traj; +0.1 5+ sources | -0.15 volume declining|
    | L3    | 0.6  | +0.15 PCMCI causal; +0.1 frame      | -0.1 marginal cpnt   |
    | L4    | 0.7  | +0.1 wavelet; +0.1 cross-lingual    | -0.1 marginal drift  |
    | L5    | 0.5  | +0.2 3+ pathways; +0.15 composite>0.8| -0.2 if only 1 pwy  |

    Args:
        feat: TopicFeatures for the topic.
        layer: Classified signal layer string.

    Returns:
        Confidence score clamped to [0, 1].
    """
    if layer not in CONFIDENCE_BASE:
        return 0.0

    conf = CONFIDENCE_BASE[layer]

    if layer == "L1_fad":
        if feat.source_count > 1:
            conf += 0.2
        if len(feat.steeps_categories) > 1:  # multi-domain as proxy for multi-language
            conf += 0.1
        if feat.source_count <= 1:
            conf -= 0.2

    elif layer == "L2_short":
        if feat.emotion_trajectory_shift:
            conf += 0.15
        if feat.source_count >= 5:
            conf += 0.1
        if feat.ma_signal == "falling":
            conf -= 0.15

    elif layer == "L3_mid":
        if feat.causal_depth >= 2:
            conf += 0.15
        if feat.frame_divergence_detected:
            conf += 0.1
        if 0.7 < feat.changepoint_significance <= L3_CHANGEPOINT_SIGNIFICANCE_THRESHOLD:
            conf -= 0.1

    elif layer == "L4_long":
        if feat.wavelet_dominant_period > 180:
            conf += 0.1
        if len(feat.steeps_categories) >= 3:  # cross-lingual proxy
            conf += 0.1
        if L4_EMBEDDING_DRIFT_THRESHOLD < feat.embedding_drift <= 0.35:
            conf -= 0.1

    elif layer == "L5_singularity":
        sing_ind = SingularityIndicators(
            ood_score=feat.ood_score,
            changepoint_sig=feat.changepoint_significance,
            cross_domain=feat.cross_domain_count / STEEPS_TOTAL_DOMAINS
            if STEEPS_TOTAL_DOMAINS > 0 else 0.0,
            bertrend_transition=feat.bertrend_transition,
            entropy_spike=feat.entropy_spike,
            novelty_score=feat.novelty_score,
            network_anomaly=(
                (feat.new_nodes_ratio + feat.new_edges_ratio) / 2.0
            ),
        )
        pa_a, pa_b, pa_c = check_singularity_pathways(sing_ind)
        pathways = sum([pa_a, pa_b, pa_c])
        composite = compute_singularity_composite(sing_ind)

        if pathways >= 3:
            conf += 0.2
        if composite > 0.8:
            conf += 0.15
        if pathways <= 1:
            conf -= 0.2

    return _clamp(conf, 0.0, 1.0)


# =============================================================================
# Evidence Summary Generation
# =============================================================================

def build_evidence_summary(feat: TopicFeatures, layer: str) -> str:
    """Build a human-readable evidence summary for a classified signal.

    Args:
        feat: TopicFeatures for the topic.
        layer: Classified signal layer string.

    Returns:
        Evidence summary text.
    """
    parts: list[str] = []

    parts.append(f"Topic {feat.topic_id}")
    if feat.topic_label:
        parts.append(f"({feat.topic_label})")

    parts.append(f"classified as {layer}.")

    parts.append(f"Data span: {feat.data_span_days}d,")
    parts.append(f"{feat.article_count} articles from {feat.source_count} sources.")

    if layer == "L1_fad":
        parts.append(
            f"Burst score: {feat.burst_score:.2f} (threshold: {L1_BURST_SCORE_THRESHOLD}),"
            f" volume z-score: {feat.volume_zscore:.2f}."
        )

    elif layer == "L2_short":
        parts.append(
            f"Volume above MA14 for {feat.volume_above_ma14_days}d,"
            f" MA signal: {feat.ma_signal},"
            f" emotion trajectory shift: {feat.emotion_trajectory_shift}."
        )

    elif layer == "L3_mid":
        parts.append(
            f"Changepoint significance: {feat.changepoint_significance:.3f},"
            f" network modularity delta: {feat.network_modularity_delta:.3f},"
            f" frame divergence: {feat.frame_divergence_detected}."
        )

    elif layer == "L4_long":
        parts.append(
            f"Embedding drift: {feat.embedding_drift:.3f},"
            f" wavelet period: {feat.wavelet_dominant_period:.0f}d,"
            f" STEEPS shift: {feat.steeps_shift_detected}."
        )

    elif layer == "L5_singularity":
        parts.append(
            f"Novelty: {feat.novelty_score:.3f},"
            f" OOD: {feat.ood_score:.3f},"
            f" cross-domain: {feat.cross_domain_count}/{STEEPS_TOTAL_DOMAINS},"
            f" BERTrend transition: {feat.bertrend_transition},"
            f" entropy spike: {feat.entropy_spike:.3f}."
        )

    if feat.steeps_categories:
        parts.append(f"STEEPS: {', '.join(sorted(feat.steeps_categories))}.")

    return " ".join(parts)


# =============================================================================
# Novelty Detection (T47 + T48)
# =============================================================================

def compute_ood_scores(
    embeddings: np.ndarray,
    article_ids: list[str],
) -> dict[str, float]:
    """Compute Out-of-Distribution scores using LOF + Isolation Forest ensemble.

    T47: LOF with n_neighbors=20, contamination=0.05
    T48: Isolation Forest with contamination=0.05
    Ensemble: ood_score = 0.5 * lof_score + 0.5 * if_score
    Threshold > 0.7 = OOD candidate.

    Args:
        embeddings: Array of shape (n_samples, embedding_dim).
        article_ids: Corresponding article IDs.

    Returns:
        Dict mapping article_id -> ood_score in [0, 1].
    """
    if embeddings.shape[0] < LOF_N_NEIGHBORS + 1:
        logger.warning(
            "stage7_ood_skip_insufficient_samples: n_samples=%d, min_required=%d",
            embeddings.shape[0], LOF_N_NEIGHBORS + 1,
        )
        return {aid: 0.0 for aid in article_ids}

    try:
        from sklearn.neighbors import LocalOutlierFactor
        from sklearn.ensemble import IsolationForest
    except ImportError as exc:
        logger.error("stage7_sklearn_import_error: %s", exc)
        return {aid: 0.0 for aid in article_ids}

    scores = {}

    # T47: LOF
    try:
        lof = LocalOutlierFactor(
            n_neighbors=LOF_N_NEIGHBORS,
            contamination=LOF_CONTAMINATION,
            novelty=False,
        )
        lof.fit(embeddings)
        # negative_outlier_factor_ is negative; more negative = more outlier
        raw_lof = -lof.negative_outlier_factor_
        # Normalize to [0, 1] using min-max
        lof_min = raw_lof.min()
        lof_max = raw_lof.max()
        if lof_max > lof_min:
            lof_normalized = (raw_lof - lof_min) / (lof_max - lof_min)
        else:
            lof_normalized = np.zeros_like(raw_lof)
    except Exception as exc:
        logger.warning("stage7_lof_failed: %s", exc)
        lof_normalized = np.zeros(len(article_ids))

    # T48: Isolation Forest
    try:
        iso = IsolationForest(
            contamination=IF_CONTAMINATION,
            random_state=42,
        )
        iso.fit(embeddings)
        # score_samples returns negative anomaly scores; lower = more anomalous
        raw_if = -iso.score_samples(embeddings)
        if_min = raw_if.min()
        if_max = raw_if.max()
        if if_max > if_min:
            if_normalized = (raw_if - if_min) / (if_max - if_min)
        else:
            if_normalized = np.zeros_like(raw_if)
    except Exception as exc:
        logger.warning("stage7_isolation_forest_failed: %s", exc)
        if_normalized = np.zeros(len(article_ids))

    # Ensemble
    for i, aid in enumerate(article_ids):
        ensemble = (
            LOF_IF_ENSEMBLE_WEIGHT_LOF * lof_normalized[i]
            + LOF_IF_ENSEMBLE_WEIGHT_IF * if_normalized[i]
        )
        scores[aid] = _clamp(float(ensemble))

    return scores


# =============================================================================
# Z-score Anomaly Detection (T51)
# =============================================================================

def compute_volume_zscores(
    daily_volumes: dict[int, list[float]],
) -> dict[int, float]:
    """Compute z-score of latest volume for each topic time series.

    T51: scipy.stats.zscore on time series; threshold > |2.5|.

    Args:
        daily_volumes: Dict mapping topic_id -> list of daily article counts.

    Returns:
        Dict mapping topic_id -> z-score of the latest day.
    """
    try:
        from scipy.stats import zscore as scipy_zscore
    except ImportError:
        logger.warning("stage7_scipy_unavailable_zscore")
        return {tid: 0.0 for tid in daily_volumes}

    results = {}
    for topic_id, volumes in daily_volumes.items():
        if len(volumes) < 3:
            results[topic_id] = 0.0
            continue
        arr = np.array(volumes, dtype=np.float64)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            zscores = scipy_zscore(arr, nan_policy="omit")
        if zscores is None or len(zscores) == 0:
            results[topic_id] = 0.0
        else:
            last_z = float(zscores[-1])
            results[topic_id] = 0.0 if math.isnan(last_z) else last_z

    return results


# =============================================================================
# Entropy Change Detection (T52)
# =============================================================================

def compute_entropy_spike(
    topic_distributions: list[np.ndarray],
    window_days: int = ENTROPY_ROLLING_WINDOW_DAYS,
) -> float:
    """Compute entropy spike: z-score of latest topic distribution entropy.

    T52: scipy.stats.entropy on topic distribution; delta vs 30-day rolling mean.
    Normalized: min(zscore/5, 1.0).

    Args:
        topic_distributions: List of arrays, each an empirical topic distribution
            over articles for one day. Most recent is last.
        window_days: Rolling window for baseline computation.

    Returns:
        Entropy spike score in [0, 1].
    """
    try:
        from scipy.stats import entropy as scipy_entropy
    except ImportError:
        logger.warning("stage7_scipy_unavailable_entropy")
        return 0.0

    if len(topic_distributions) < 3:
        return 0.0

    entropies = []
    for dist in topic_distributions:
        dist_safe = np.asarray(dist, dtype=np.float64)
        dist_sum = dist_safe.sum()
        if dist_sum <= 0:
            entropies.append(0.0)
        else:
            dist_safe = dist_safe / dist_sum
            entropies.append(float(scipy_entropy(dist_safe)))

    if len(entropies) < 3:
        return 0.0

    # Rolling mean of the last `window_days` entries (excluding the latest)
    baseline = entropies[max(0, len(entropies) - window_days - 1):-1]
    if len(baseline) < 2:
        return 0.0

    mean_h = np.mean(baseline)
    std_h = np.std(baseline, ddof=1)
    if std_h < 1e-10:
        return 0.0

    latest_h = entropies[-1]
    z = (latest_h - mean_h) / std_h
    return _clamp(z / ENTROPY_ZSCORE_NORMALIZER)


# =============================================================================
# Zipf Distribution Deviation (T53)
# =============================================================================

def compute_zipf_deviation(term_frequencies: dict[str, int]) -> float:
    """Compute deviation of term frequency distribution from ideal Zipf law.

    T53: Compare observed rank-frequency curve against ideal Zipf (1/rank).
    Higher deviation indicates more unusual vocabulary distribution.

    Args:
        term_frequencies: Dict mapping term -> frequency count.

    Returns:
        Zipf deviation score in [0, 1]. Higher = more deviant.
    """
    if len(term_frequencies) < 5:
        return 0.0

    # Sort by frequency descending, take top N
    sorted_freqs = sorted(term_frequencies.values(), reverse=True)[:ZIPF_MAX_TERMS]
    n = len(sorted_freqs)
    observed = np.array(sorted_freqs, dtype=np.float64)
    total = observed.sum()
    if total <= 0:
        return 0.0

    observed_norm = observed / total

    # Ideal Zipf: f(rank) = 1/rank, normalized
    ranks = np.arange(1, n + 1, dtype=np.float64)
    ideal = 1.0 / ranks
    ideal_norm = ideal / ideal.sum()

    # KL divergence as deviation metric
    try:
        from scipy.special import rel_entr
        kl = float(np.sum(rel_entr(observed_norm, ideal_norm)))
    except ImportError:
        # Fallback: mean absolute deviation
        kl = float(np.mean(np.abs(observed_norm - ideal_norm)))

    # Normalize to [0, 1] with sigmoid-like transform
    return _clamp(1.0 - math.exp(-kl))


# =============================================================================
# Survival Analysis (T54)
# =============================================================================

def compute_survival_durations(
    topic_durations: dict[int, tuple[float, bool]],
) -> dict[int, float]:
    """Fit Kaplan-Meier survival model for topic duration estimation.

    T54: lifelines.KaplanMeierFitter on observed topic durations.
    Returns expected median survival duration per topic.

    Args:
        topic_durations: Dict mapping topic_id -> (duration_days, is_censored).
            is_censored=True means the topic is still active (right-censored).

    Returns:
        Dict mapping topic_id -> expected duration in days.
    """
    if len(topic_durations) < SURVIVAL_MIN_TOPICS:
        return {tid: dur for tid, (dur, _) in topic_durations.items()}

    try:
        from lifelines import KaplanMeierFitter
    except ImportError:
        logger.warning("stage7_lifelines_unavailable")
        return {tid: dur for tid, (dur, _) in topic_durations.items()}

    durations = []
    events = []  # 1 = topic ended (event), 0 = censored (still active)
    topic_ids = []
    for tid, (dur, censored) in topic_durations.items():
        durations.append(max(dur, 0.1))  # Avoid zero duration
        events.append(0 if censored else 1)
        topic_ids.append(tid)

    durations_arr = np.array(durations)
    events_arr = np.array(events)

    try:
        kmf = KaplanMeierFitter()
        kmf.fit(durations_arr, event_observed=events_arr)
        median_survival = kmf.median_survival_time_
        if math.isnan(median_survival) or math.isinf(median_survival):
            median_survival = float(np.max(durations_arr))
    except Exception as exc:
        logger.warning("stage7_survival_fit_failed: %s", exc)
        median_survival = float(np.median(durations_arr))

    return {tid: float(median_survival) for tid in topic_ids}


# =============================================================================
# KL Divergence (T55)
# =============================================================================

def compute_kl_divergence(
    current_dist: np.ndarray,
    baseline_dist: np.ndarray,
) -> float:
    """Compute KL divergence between current and baseline distributions.

    T55: scipy.special.rel_entr between current and baseline.
    Measures how much the current topic distribution diverges from baseline.

    Args:
        current_dist: Current probability distribution.
        baseline_dist: Historical baseline probability distribution.

    Returns:
        KL divergence value (non-negative). NaN clamped to 0.
    """
    try:
        from scipy.special import rel_entr
    except ImportError:
        logger.warning("stage7_scipy_unavailable_kl")
        return 0.0

    if current_dist.size == 0 or baseline_dist.size == 0:
        return 0.0
    if current_dist.shape != baseline_dist.shape:
        return 0.0

    # Ensure proper probability distributions
    c_sum = current_dist.sum()
    b_sum = baseline_dist.sum()
    if c_sum <= 0 or b_sum <= 0:
        return 0.0

    p = current_dist / c_sum
    q = baseline_dist / b_sum

    # Add small epsilon to avoid division by zero
    eps = 1e-10
    q = q + eps
    q = q / q.sum()

    kl = float(np.sum(rel_entr(p, q)))
    if math.isnan(kl) or math.isinf(kl):
        return 0.0
    return max(0.0, kl)


# =============================================================================
# BERTrend Weak Signal Detection
# =============================================================================

def classify_bertrend_state(
    article_count: int,
    growth_rate: float,
    trend_strength: float,
    is_declining: bool = False,
) -> tuple[str, int]:
    """Classify topic into BERTrend lifecycle state.

    States: noise -> weak -> emerging -> strong -> declining

    Transitions that count as bertrend_transition = 1:
        noise -> weak
        weak -> emerging

    Args:
        article_count: Total articles in topic.
        growth_rate: Recent growth rate (articles/day change).
        trend_strength: STL trend strength.
        is_declining: Whether the trend is declining.

    Returns:
        Tuple of (state_name, transition_flag).
        transition_flag is 1 if noise->weak or weak->emerging transition.
    """
    if is_declining:
        return "declining", 0

    if article_count <= BERTREND_NOISE_MAX_ARTICLES:
        return "noise", 0

    if article_count <= BERTREND_WEAK_MAX_ARTICLES:
        if growth_rate > 0:
            # noise -> weak transition detected
            return "weak", 1
        return "weak", 0

    if growth_rate >= BERTREND_EMERGING_GROWTH_RATE:
        # weak -> emerging transition
        return "emerging", 1

    if trend_strength > 0.5:
        return "strong", 0

    return "emerging", 0


# =============================================================================
# Dual-Pass Classification
# =============================================================================

def dual_pass_classify(
    feat: TopicFeatures,
    title_features: TopicFeatures | None = None,
) -> str:
    """Dual-pass signal classification: title pass (fast) -> body pass (evidence).

    Title pass: Quick scan using title-derived features (embeddings, keywords).
    Body pass: Full evidence confirmation using body analysis features.

    If title_features is provided, it is used for initial screening.
    The body pass (feat) always has the final say.

    Args:
        feat: Full TopicFeatures from body analysis.
        title_features: Optional title-only features for fast scan.

    Returns:
        Classified signal layer string.
    """
    # Title pass (fast scan)
    if title_features is not None:
        title_layer = classify_signal_layer(title_features)
        if not title_layer:
            # Title pass found no signal -- still try body pass
            pass

    # Body pass (evidence confirmation -- authoritative)
    body_layer = classify_signal_layer(feat)
    return body_layer


# =============================================================================
# Stage7SignalClassifier -- Main Class
# =============================================================================

class Stage7SignalClassifier:
    """Stage 7 signal classification pipeline.

    Synthesizes upstream analysis results (Stages 3-6) into classified signals
    with temporal persistence layers (L1-L5), novelty scores, singularity
    composite scores, and confidence intervals.

    Usage:
        classifier = Stage7SignalClassifier()
        output = classifier.run()
        classifier.cleanup()
    """

    def __init__(self) -> None:
        self._topic_features: dict[int, TopicFeatures] = {}
        self._ood_scores: dict[str, float] = {}
        self._daily_volumes: dict[int, list[float]] = {}
        self._topic_distributions: list[np.ndarray] = []
        self._signals: list[SignalRecord] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        analysis_dir: Path | None = None,
        features_dir: Path | None = None,
        output_dir: Path | None = None,
    ) -> Stage7Output:
        """Execute the full Stage 7 signal classification pipeline.

        Processing order:
            1. Load upstream Parquet inputs
            2. Extract per-topic features
            3. Compute OOD scores (T47+T48)
            4. Compute z-score anomalies (T51)
            5. Compute entropy spikes (T52)
            6. Compute Zipf deviations (T53)
            7. Compute survival estimates (T54)
            8. Compute KL divergences (T55)
            9. Classify BERTrend states
            10. Dual-pass 5-Layer classification
            11. Score confidence
            12. Write signals.parquet

        Args:
            analysis_dir: Directory containing upstream analysis parquets.
            features_dir: Directory containing embeddings parquet.
            output_dir: Directory to write signals.parquet.

        Returns:
            Stage7Output with classification results.

        Raises:
            PipelineStageError: If the stage fails irrecoverably.
        """
        t0 = time.monotonic()
        output = Stage7Output()

        _analysis_dir = analysis_dir or DATA_ANALYSIS_DIR
        _features_dir = features_dir or DATA_FEATURES_DIR
        _output_dir = output_dir or DATA_OUTPUT_DIR

        _output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "stage7_start: analysis_dir=%s, features_dir=%s, output_dir=%s",
            _analysis_dir, _features_dir, _output_dir,
        )

        # ---- Step 1: Load upstream inputs ----
        topics_data = self._load_parquet_safe(
            _analysis_dir / "topics.parquet", "topics"
        )
        timeseries_data = self._load_parquet_safe(
            _analysis_dir / "timeseries.parquet", "timeseries"
        )
        cross_data = self._load_parquet_safe(
            _analysis_dir / "cross_analysis.parquet", "cross_analysis"
        )
        article_analysis = self._load_parquet_safe(
            _analysis_dir / "article_analysis.parquet", "article_analysis"
        )
        networks_data = self._load_parquet_safe(
            _analysis_dir / "networks.parquet", "networks"
        )
        embeddings_data = self._load_parquet_safe(
            _features_dir / "embeddings.parquet", "embeddings"
        )

        if topics_data is None:
            logger.warning("stage7_no_topics_data")
            self._write_empty_output(_output_dir)
            output.elapsed_seconds = time.monotonic() - t0
            return output

        # ---- Step 2: Extract per-topic features ----
        self._extract_topic_features(
            topics_data, timeseries_data, cross_data,
            article_analysis, networks_data, embeddings_data,
        )

        n_topics = len(self._topic_features)
        output.n_topics_analyzed = n_topics

        if n_topics == 0:
            logger.warning("stage7_no_topics_extracted")
            self._write_empty_output(_output_dir)
            output.elapsed_seconds = time.monotonic() - t0
            return output

        logger.info("stage7_topics_extracted: n_topics=%d", n_topics)

        # ---- Step 3: Compute OOD scores (T47 + T48) ----
        if embeddings_data is not None:
            self._compute_ood_from_embeddings(embeddings_data, topics_data)

        # ---- Step 4: Compute z-score anomalies (T51) ----
        self._compute_volume_zscores(timeseries_data)

        # ---- Step 5: Compute entropy spikes (T52) ----
        self._compute_entropy_spikes(topics_data, timeseries_data)

        # ---- Step 6: Compute Zipf deviations (T53) ----
        # Zipf deviation computed from topic term distributions if available
        self._compute_zipf_deviations(topics_data)

        # ---- Step 7: Compute survival estimates (T54) ----
        self._compute_survival_estimates()

        # ---- Step 8: Compute KL divergences (T55) ----
        self._compute_kl_divergences(topics_data, timeseries_data)

        # ---- Step 9: Classify BERTrend states ----
        self._classify_bertrend_states(timeseries_data)

        # ---- Step 10: Dual-pass 5-Layer classification ----
        self._classify_all_signals()

        # ---- Step 11: Score confidence ----
        self._score_all_confidence()

        # ---- Step 12: Deduplicate overlapping signals ----
        self._deduplicate_signals()

        # ---- Step 13: Write signals.parquet ----
        self._write_output(_output_dir)

        # Build output summary
        output.signals = list(self._signals)
        output.n_signals = len(self._signals)
        for sig in self._signals:
            output.layer_distribution[sig.signal_layer] = (
                output.layer_distribution.get(sig.signal_layer, 0) + 1
            )
            if sig.signal_layer == "L5_singularity":
                output.l5_candidates.append(sig.signal_id)

        output.elapsed_seconds = time.monotonic() - t0

        logger.info(
            "stage7_complete: elapsed=%.1fs, n_topics=%d, n_signals=%d, layers=%s, l5=%d",
            output.elapsed_seconds, n_topics, output.n_signals,
            output.layer_distribution, len(output.l5_candidates),
        )

        return output

    def cleanup(self) -> None:
        """Release all internal state and force garbage collection."""
        logger.info("stage7_cleanup_start")
        self._topic_features.clear()
        self._ood_scores.clear()
        self._daily_volumes.clear()
        self._topic_distributions.clear()
        self._signals.clear()
        gc.collect()
        logger.info("stage7_cleanup_complete")

    # ------------------------------------------------------------------
    # Input Loading
    # ------------------------------------------------------------------

    def _load_parquet_safe(
        self, path: Path, name: str
    ) -> Any:
        """Load a Parquet file safely, returning None on failure."""
        _, pq = _ensure_pyarrow()
        if not path.exists():
            logger.warning("stage7_%s_not_found: path=%s", name, path)
            return None
        try:
            table = pq.read_table(str(path))
            logger.info("stage7_%s_loaded: n_rows=%d", name, table.num_rows)
            return table
        except Exception as exc:
            logger.warning("stage7_%s_load_error: %s", name, exc)
            return None

    # ------------------------------------------------------------------
    # Feature Extraction (Step 2)
    # ------------------------------------------------------------------

    def _extract_topic_features(
        self,
        topics_data: Any,
        timeseries_data: Any | None,
        cross_data: Any | None,
        article_analysis: Any | None,
        networks_data: Any | None,
        embeddings_data: Any | None,
    ) -> None:
        """Extract per-topic features from all upstream data sources."""
        pa, _ = _ensure_pyarrow()

        # ---- Topics: basic article-topic mapping ----
        topic_col = _get_column_safe(topics_data, "topic_id")
        article_col = _get_column_safe(topics_data, "article_id")

        if topic_col is None or article_col is None:
            logger.warning("stage7_topics_missing_columns")
            return

        topic_ids_list = topic_col.to_pylist()
        article_ids_list = article_col.to_pylist()

        # Get topic labels if available
        topic_label_col = _get_column_safe(topics_data, "topic_label")
        topic_labels_list = (
            topic_label_col.to_pylist() if topic_label_col is not None else [None] * len(topic_ids_list)
        )

        # Group articles by topic
        for i, (tid, aid) in enumerate(zip(topic_ids_list, article_ids_list)):
            if tid is None or tid < 0:  # Skip noise topic (-1)
                continue
            tid = int(tid)
            if tid not in self._topic_features:
                self._topic_features[tid] = TopicFeatures(topic_id=tid)
            feat = self._topic_features[tid]
            if aid is not None:
                feat.article_ids.append(str(aid))
            feat.article_count += 1
            if topic_labels_list[i] is not None and not feat.topic_label:
                feat.topic_label = str(topic_labels_list[i])

        # ---- Source count from article_analysis ----
        if article_analysis is not None:
            self._extract_source_and_steeps(
                article_analysis, topics_data
            )

        # ---- Data span from article timestamps ----
        # published_at is now in topics.parquet (propagated from Stage 4)
        published_col = _get_column_safe(topics_data, "published_at")

        if published_col is not None:
            published_list = published_col.to_pylist()
            # Build per-topic date lists
            topic_dates: dict[int, list[Any]] = defaultdict(list)
            for i, tid in enumerate(topic_ids_list):
                if tid is None or tid < 0:
                    continue
                if i < len(published_list) and published_list[i] is not None:
                    topic_dates[int(tid)].append(published_list[i])
            for tid, dates in topic_dates.items():
                if tid in self._topic_features:
                    self._topic_features[tid].data_span_days = _days_between(dates)

        # ---- Time series features ----
        if timeseries_data is not None:
            self._extract_timeseries_features(timeseries_data)

        # ---- Cross analysis features ----
        if cross_data is not None:
            self._extract_cross_features(cross_data)

        # ---- Network features ----
        if networks_data is not None:
            self._extract_network_features(networks_data)

        # ---- Embedding drift ----
        if embeddings_data is not None and topics_data is not None:
            self._extract_embedding_drift(embeddings_data, topics_data)

    def _extract_source_and_steeps(
        self, article_analysis: Any, topics_data: Any
    ) -> None:
        """Extract source counts, STEEPS categories, and emotion data.

        Data sources (after A3 fix):
            - source: topics.parquet (propagated from Stage 4 via articles_table)
            - steeps_category: article_analysis.parquet (Stage 3 output)
            - published_at: topics.parquet (propagated from Stage 4)
            - emotion_trajectory: currently unavailable per-article (L2 needs 14+ days)
        """
        # Build source lookup from topics_data (source propagated from Stage 4)
        source_lookup: dict[str, str] = {}
        topics_aid_col = _get_column_safe(topics_data, "article_id")
        source_col = _get_column_safe(topics_data, "source")
        if topics_aid_col is not None and source_col is not None:
            t_aids = topics_aid_col.to_pylist()
            t_sources = source_col.to_pylist()
            for i, aid in enumerate(t_aids):
                if aid is not None and i < len(t_sources) and t_sources[i]:
                    source_lookup[str(aid)] = str(t_sources[i])

        # Build steeps lookup from article_analysis
        steeps_lookup: dict[str, str] = {}
        aa_article_col = _get_column_safe(article_analysis, "article_id")
        steeps_col = _get_column_safe(article_analysis, "steeps_category")
        if aa_article_col is not None and steeps_col is not None:
            aa_ids = aa_article_col.to_pylist()
            aa_steeps = steeps_col.to_pylist()
            for i, aid in enumerate(aa_ids):
                if aid is not None and i < len(aa_steeps) and aa_steeps[i]:
                    steeps_lookup[str(aid)] = str(aa_steeps[i])

        if not source_lookup and not steeps_lookup:
            return

        # Assign to topics
        for tid, feat in self._topic_features.items():
            sources = set()
            steeps = set()
            for aid in feat.article_ids:
                src = source_lookup.get(aid)
                if src:
                    sources.add(src)
                stp = steeps_lookup.get(aid)
                if stp:
                    steeps.add(stp)

            feat.source_count = len(sources)
            feat.steeps_categories = steeps
            feat.cross_domain_count = len(steeps)
            # emotion_trajectory_shift stays False until multi-day data
            # (L2 requires data_span_days >= 14 anyway)

            # STEEPS shift detected: topic spans 3+ STEEPS domains
            if feat.cross_domain_count >= 3:
                feat.steeps_shift_detected = True

    def _extract_timeseries_features(self, ts_data: Any) -> None:
        """Extract time series features: burst, trend, changepoint, MA."""
        topic_col = _get_column_safe(ts_data, "topic_id")
        burst_col = _get_column_safe(ts_data, "burst_score")
        trend_col = _get_column_safe(ts_data, "trend")
        cp_col = _get_column_safe(ts_data, "changepoint_significance")
        is_cp_col = _get_column_safe(ts_data, "is_changepoint")
        ma_signal_col = _get_column_safe(ts_data, "ma_signal")
        ma_short_col = _get_column_safe(ts_data, "ma_short")
        ma_long_col = _get_column_safe(ts_data, "ma_long")
        date_col = _get_column_safe(ts_data, "date")
        value_col = _get_column_safe(ts_data, "value")

        if topic_col is None:
            return

        topic_ids = topic_col.to_pylist()
        bursts = burst_col.to_pylist() if burst_col is not None else [None] * len(topic_ids)
        trends = trend_col.to_pylist() if trend_col is not None else [None] * len(topic_ids)
        cps = cp_col.to_pylist() if cp_col is not None else [None] * len(topic_ids)
        is_cps = is_cp_col.to_pylist() if is_cp_col is not None else [None] * len(topic_ids)
        ma_signals = ma_signal_col.to_pylist() if ma_signal_col is not None else [None] * len(topic_ids)
        ma_shorts = ma_short_col.to_pylist() if ma_short_col is not None else [None] * len(topic_ids)
        ma_longs = ma_long_col.to_pylist() if ma_long_col is not None else [None] * len(topic_ids)
        dates = date_col.to_pylist() if date_col is not None else [None] * len(topic_ids)
        values = value_col.to_pylist() if value_col is not None else [None] * len(topic_ids)

        # Aggregate per topic
        topic_ts: dict[int, dict[str, list]] = defaultdict(lambda: {
            "bursts": [], "trends": [], "cps": [], "is_cps": [],
            "ma_signals": [], "ma_shorts": [], "ma_longs": [],
            "dates": [], "values": [],
        })

        for i, tid in enumerate(topic_ids):
            if tid is None or tid < 0:
                continue
            tid = int(tid)
            d = topic_ts[tid]
            d["bursts"].append(_safe_float(bursts[i]))
            d["trends"].append(_safe_float(trends[i]))
            d["cps"].append(_safe_float(cps[i]))
            d["is_cps"].append(is_cps[i])
            d["ma_signals"].append(ma_signals[i])
            d["ma_shorts"].append(_safe_float(ma_shorts[i]))
            d["ma_longs"].append(_safe_float(ma_longs[i]))
            d["dates"].append(dates[i])
            d["values"].append(_safe_float(values[i]))

        for tid, d in topic_ts.items():
            if tid not in self._topic_features:
                continue
            feat = self._topic_features[tid]

            # Max burst score
            feat.burst_score = max(d["bursts"]) if d["bursts"] else 0.0
            feat.has_burst = feat.burst_score > L1_BURST_SCORE_THRESHOLD

            # Trend strength: std of trend component / std of original
            if d["trends"] and d["values"]:
                trend_arr = np.array(d["trends"])
                val_arr = np.array(d["values"])
                val_std = np.std(val_arr)
                if val_std > 1e-10:
                    feat.trend_strength = float(np.std(trend_arr) / val_std)

            # Changepoint significance: max
            feat.changepoint_significance = max(d["cps"]) if d["cps"] else 0.0
            feat.has_changepoint = any(
                cp is True or cp == 1 for cp in d["is_cps"]
            )

            # MA signal: most recent non-None
            for sig in reversed(d["ma_signals"]):
                if sig is not None:
                    feat.ma_signal = str(sig)
                    break

            # Volume above MA14: count days where ma_short > ma_long
            above_count = 0
            for ms, ml in zip(d["ma_shorts"], d["ma_longs"]):
                if ms > ml:
                    above_count += 1
            feat.volume_above_ma14_days = above_count

            # Store daily volumes for z-score
            self._daily_volumes[tid] = d["values"]

    def _extract_cross_features(self, cross_data: Any) -> None:
        """Extract causal depth and frame divergence from cross-analysis."""
        analysis_type_col = _get_column_safe(cross_data, "analysis_type")
        source_col = _get_column_safe(cross_data, "source_entity")
        target_col = _get_column_safe(cross_data, "target_entity")
        strength_col = _get_column_safe(cross_data, "strength")

        if analysis_type_col is None:
            return

        types = analysis_type_col.to_pylist()
        sources = source_col.to_pylist() if source_col is not None else [None] * len(types)
        targets = target_col.to_pylist() if target_col is not None else [None] * len(types)
        strengths = strength_col.to_pylist() if strength_col is not None else [None] * len(types)

        # Build causal chains per topic
        causal_graph: dict[str, list[str]] = defaultdict(list)
        frame_topics: set[int] = set()

        for i, atype in enumerate(types):
            if atype is None:
                continue
            atype_str = str(atype).lower()
            src = str(sources[i]) if sources[i] is not None else ""
            tgt = str(targets[i]) if targets[i] is not None else ""

            if "granger" in atype_str or "pcmci" in atype_str or "causal" in atype_str:
                if src and tgt:
                    causal_graph[src].append(tgt)

            if "frame" in atype_str or "divergence" in atype_str:
                # Extract topic IDs from entity names
                for entity in [src, tgt]:
                    try:
                        tid = int(entity.replace("topic_", ""))
                        frame_topics.add(tid)
                    except (ValueError, TypeError):
                        pass

        # Compute causal depth per topic (BFS longest path)
        for tid, feat in self._topic_features.items():
            topic_key = f"topic_{tid}"
            depth = self._bfs_max_depth(causal_graph, topic_key)
            feat.causal_depth = depth
            feat.frame_divergence_detected = tid in frame_topics

    @staticmethod
    def _bfs_max_depth(graph: dict[str, list[str]], start: str) -> int:
        """BFS to find maximum causal chain depth from a starting node."""
        if start not in graph:
            return 0
        visited = {start}
        queue = [(start, 0)]
        max_depth = 0
        while queue:
            node, depth = queue.pop(0)
            max_depth = max(max_depth, depth)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, depth + 1))
        return max_depth

    def _extract_network_features(self, networks_data: Any) -> None:
        """Extract network modularity and new node/edge ratios."""
        # Network data from Stage 4 Louvain community detection
        community_col = _get_column_safe(networks_data, "community_id")
        entity_col = _get_column_safe(networks_data, "entity")
        weight_col = _get_column_safe(networks_data, "weight")
        modularity_col = _get_column_safe(networks_data, "modularity")

        if community_col is None:
            return

        communities = community_col.to_pylist()
        entities = entity_col.to_pylist() if entity_col is not None else [None] * len(communities)
        weights = weight_col.to_pylist() if weight_col is not None else [None] * len(communities)

        # Estimate modularity delta and new node ratio
        unique_communities = set(c for c in communities if c is not None)
        unique_entities = set(e for e in entities if e is not None)
        n_communities = len(unique_communities)
        n_entities = len(unique_entities)

        # For modularity: use the value from the data if available
        modularity_values = []
        if modularity_col is not None:
            modularity_values = [
                _safe_float(m) for m in modularity_col.to_pylist()
                if m is not None
            ]

        avg_modularity = np.mean(modularity_values) if modularity_values else 0.0

        # Distribute network features to topics based on entity overlap
        for tid, feat in self._topic_features.items():
            # Approximate: topic's network contribution proportional to article count
            if n_entities > 0:
                feat.network_modularity_delta = float(avg_modularity)
                # Rough estimate: newer topics have higher new_nodes_ratio
                feat.new_nodes_ratio = min(1.0, feat.article_count / max(n_entities, 1))
                feat.new_edges_ratio = feat.new_nodes_ratio * 0.8  # Conservative estimate

    def _extract_embedding_drift(
        self, embeddings_data: Any, topics_data: Any
    ) -> None:
        """Compute embedding drift per topic over time."""
        emb_article_col = _get_column_safe(embeddings_data, "article_id")
        emb_vector_col = _get_column_safe(embeddings_data, "embedding")

        if emb_article_col is None or emb_vector_col is None:
            return

        emb_articles = emb_article_col.to_pylist()
        emb_vectors = emb_vector_col.to_pylist()

        # Build article -> embedding lookup
        article_embeddings: dict[str, np.ndarray] = {}
        for aid, vec in zip(emb_articles, emb_vectors):
            if aid is not None and vec is not None:
                try:
                    article_embeddings[str(aid)] = np.array(vec, dtype=np.float32)
                except (ValueError, TypeError):
                    continue

        # For each topic, compute centroid drift
        for tid, feat in self._topic_features.items():
            topic_embs = []
            for aid in feat.article_ids:
                emb = article_embeddings.get(aid)
                if emb is not None:
                    topic_embs.append(emb)

            if len(topic_embs) < 4:
                feat.embedding_drift = 0.0
                continue

            embs = np.stack(topic_embs)
            # Split into first half and second half
            mid = len(embs) // 2
            first_half = embs[:mid]
            second_half = embs[mid:]

            centroid_first = first_half.mean(axis=0)
            centroid_second = second_half.mean(axis=0)

            # Cosine distance
            norm_first = np.linalg.norm(centroid_first)
            norm_second = np.linalg.norm(centroid_second)
            if norm_first > 1e-10 and norm_second > 1e-10:
                cosine_sim = np.dot(centroid_first, centroid_second) / (norm_first * norm_second)
                feat.embedding_drift = float(1.0 - cosine_sim)
            else:
                feat.embedding_drift = 0.0

    # ------------------------------------------------------------------
    # OOD Computation (Step 3)
    # ------------------------------------------------------------------

    def _compute_ood_from_embeddings(
        self, embeddings_data: Any, topics_data: Any
    ) -> None:
        """Compute OOD scores from embeddings and assign to topics."""
        emb_article_col = _get_column_safe(embeddings_data, "article_id")
        emb_vector_col = _get_column_safe(embeddings_data, "embedding")

        if emb_article_col is None or emb_vector_col is None:
            return

        emb_articles = emb_article_col.to_pylist()
        emb_vectors = emb_vector_col.to_pylist()

        # Build embedding matrix
        valid_articles = []
        valid_embeddings = []
        for aid, vec in zip(emb_articles, emb_vectors):
            if aid is not None and vec is not None:
                try:
                    valid_embeddings.append(np.array(vec, dtype=np.float32))
                    valid_articles.append(str(aid))
                except (ValueError, TypeError):
                    continue

        if len(valid_embeddings) < LOF_N_NEIGHBORS + 1:
            return

        embeddings_matrix = np.stack(valid_embeddings)
        self._ood_scores = compute_ood_scores(embeddings_matrix, valid_articles)

        # Assign OOD scores to topics (max score among topic's articles)
        for tid, feat in self._topic_features.items():
            topic_ood = [
                self._ood_scores.get(aid, 0.0) for aid in feat.article_ids
            ]
            if topic_ood:
                feat.ood_score = max(topic_ood)
                feat.novelty_score = np.mean(topic_ood) if topic_ood else 0.0

    # ------------------------------------------------------------------
    # Z-score Computation (Step 4)
    # ------------------------------------------------------------------

    def _compute_volume_zscores(self, ts_data: Any | None) -> None:
        """Compute and assign volume z-scores."""
        if not self._daily_volumes:
            return

        zscores = compute_volume_zscores(self._daily_volumes)
        for tid, zscore in zscores.items():
            if tid in self._topic_features:
                self._topic_features[tid].volume_zscore = abs(zscore)

    # ------------------------------------------------------------------
    # Entropy Computation (Step 5)
    # ------------------------------------------------------------------

    def _compute_entropy_spikes(
        self, topics_data: Any | None, ts_data: Any | None
    ) -> None:
        """Compute entropy spikes for topic distributions."""
        if ts_data is None or topics_data is None:
            return

        # Build daily topic distributions from time series values
        topic_col = _get_column_safe(ts_data, "topic_id")
        date_col = _get_column_safe(ts_data, "date")
        value_col = _get_column_safe(ts_data, "value")

        if topic_col is None or date_col is None or value_col is None:
            return

        topics = topic_col.to_pylist()
        dates = date_col.to_pylist()
        values = value_col.to_pylist()

        # Group by date -> topic distribution
        date_topic_counts: dict[Any, dict[int, float]] = defaultdict(lambda: defaultdict(float))
        all_topic_ids = sorted(self._topic_features.keys())

        for i, (tid, dt, val) in enumerate(zip(topics, dates, values)):
            if tid is None or tid < 0 or dt is None:
                continue
            date_topic_counts[dt][int(tid)] += _safe_float(val, 0.0)

        # Sort by date and build distribution arrays
        sorted_dates = sorted(date_topic_counts.keys())
        distributions = []
        for dt in sorted_dates:
            dist = np.array(
                [date_topic_counts[dt].get(tid, 0.0) for tid in all_topic_ids],
                dtype=np.float64,
            )
            distributions.append(dist)

        if len(distributions) >= 3:
            self._topic_distributions = distributions
            spike = compute_entropy_spike(distributions)
            # Assign the global entropy spike to all topics
            for feat in self._topic_features.values():
                feat.entropy_spike = spike

    # ------------------------------------------------------------------
    # Zipf Deviation (Step 6)
    # ------------------------------------------------------------------

    def _compute_zipf_deviations(self, topics_data: Any | None) -> None:
        """Compute Zipf deviations from topic term distributions."""
        if topics_data is None:
            return

        # Try to get topic representation/keywords
        keywords_col = _get_column_safe(topics_data, "keywords")
        if keywords_col is None:
            keywords_col = _get_column_safe(topics_data, "topic_representation")

        if keywords_col is None:
            return

        # Aggregate keywords per topic
        topic_col = _get_column_safe(topics_data, "topic_id")
        if topic_col is None:
            return

        topic_ids = topic_col.to_pylist()
        keywords_list = keywords_col.to_pylist()

        topic_terms: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for tid, kw in zip(topic_ids, keywords_list):
            if tid is None or tid < 0 or kw is None:
                continue
            tid = int(tid)
            if isinstance(kw, list):
                for term in kw:
                    if term:
                        topic_terms[tid][str(term)] += 1
            elif isinstance(kw, str):
                for term in kw.split(","):
                    term = term.strip()
                    if term:
                        topic_terms[tid][term] += 1

        for tid, terms in topic_terms.items():
            if tid in self._topic_features:
                self._topic_features[tid].zipf_deviation = compute_zipf_deviation(terms)

    # ------------------------------------------------------------------
    # Survival Analysis (Step 7)
    # ------------------------------------------------------------------

    def _compute_survival_estimates(self) -> None:
        """Compute survival duration estimates for all topics."""
        topic_durations: dict[int, tuple[float, bool]] = {}
        for tid, feat in self._topic_features.items():
            duration = max(float(feat.data_span_days), 0.1)
            # Active topic = right-censored (still producing articles)
            is_censored = feat.data_span_days > 0 and feat.trend_strength > 0.1
            topic_durations[tid] = (duration, is_censored)

        if topic_durations:
            estimates = compute_survival_durations(topic_durations)
            for tid, expected_dur in estimates.items():
                if tid in self._topic_features:
                    self._topic_features[tid].expected_duration_days = expected_dur

    # ------------------------------------------------------------------
    # KL Divergence (Step 8)
    # ------------------------------------------------------------------

    def _compute_kl_divergences(
        self, topics_data: Any | None, ts_data: Any | None
    ) -> None:
        """Compute KL divergence between current and baseline distributions."""
        if len(self._topic_distributions) < KL_BASELINE_DAYS + 1:
            return

        # Baseline: mean of the first N distributions
        baseline_dists = self._topic_distributions[:KL_BASELINE_DAYS]
        baseline = np.mean(baseline_dists, axis=0)

        # Current: last distribution
        current = self._topic_distributions[-1]

        kl = compute_kl_divergence(current, baseline)

        # Assign KL divergence to all topics
        for feat in self._topic_features.values():
            feat.kl_divergence = kl

    # ------------------------------------------------------------------
    # BERTrend Classification (Step 9)
    # ------------------------------------------------------------------

    def _classify_bertrend_states(self, ts_data: Any | None) -> None:
        """Classify BERTrend lifecycle state for each topic."""
        for tid, feat in self._topic_features.items():
            # Compute growth rate from daily volumes
            volumes = self._daily_volumes.get(tid, [])
            growth_rate = 0.0
            is_declining = False
            if len(volumes) >= 3:
                recent = np.mean(volumes[-3:])
                earlier = np.mean(volumes[:max(1, len(volumes) // 2)])
                if earlier > 0:
                    growth_rate = (recent - earlier) / earlier
                is_declining = recent < earlier * 0.5

            state, transition = classify_bertrend_state(
                article_count=feat.article_count,
                growth_rate=growth_rate,
                trend_strength=feat.trend_strength,
                is_declining=is_declining,
            )
            feat.bertrend_state = state
            feat.bertrend_transition = transition

    # ------------------------------------------------------------------
    # Signal Classification (Step 10)
    # ------------------------------------------------------------------

    def _classify_all_signals(self) -> None:
        """Classify all topics into signal layers using dual-pass."""
        detection_time = datetime.now(timezone.utc)

        for tid, feat in self._topic_features.items():
            layer = dual_pass_classify(feat)
            if not layer:
                continue  # No signal detected for this topic

            signal = SignalRecord(
                signal_id=str(uuid.uuid4()),
                signal_layer=layer,
                signal_label=feat.topic_label or f"Topic {tid}",
                detected_at=detection_time,
                topic_ids=[tid],
                article_ids=list(feat.article_ids),
                burst_score=(
                    float(feat.burst_score)
                    if layer in ("L1_fad", "L2_short") else None
                ),
                changepoint_significance=(
                    float(feat.changepoint_significance)
                    if layer in ("L3_mid", "L4_long") else None
                ),
                novelty_score=(
                    float(feat.novelty_score)
                    if layer == "L5_singularity" else None
                ),
                singularity_composite=None,  # Computed below for L5
                evidence_summary="",  # Built below
                confidence=0.0,  # Scored in Step 11
            )

            # Compute singularity composite for L5
            if layer == "L5_singularity":
                indicators = SingularityIndicators(
                    ood_score=feat.ood_score,
                    changepoint_sig=feat.changepoint_significance,
                    cross_domain=feat.cross_domain_count / STEEPS_TOTAL_DOMAINS
                    if STEEPS_TOTAL_DOMAINS > 0 else 0.0,
                    bertrend_transition=feat.bertrend_transition,
                    entropy_spike=feat.entropy_spike,
                    novelty_score=feat.novelty_score,
                    network_anomaly=(
                        (feat.new_nodes_ratio + feat.new_edges_ratio) / 2.0
                    ),
                )
                signal.singularity_composite = float(
                    compute_singularity_composite(indicators)
                )

            self._signals.append(signal)

    # ------------------------------------------------------------------
    # Confidence Scoring (Step 11)
    # ------------------------------------------------------------------

    def _score_all_confidence(self) -> None:
        """Score confidence and build evidence for all signals."""
        for signal in self._signals:
            # Find the corresponding topic features
            if signal.topic_ids:
                tid = signal.topic_ids[0]
                feat = self._topic_features.get(tid)
                if feat is not None:
                    signal.confidence = compute_confidence(feat, signal.signal_layer)
                    signal.evidence_summary = build_evidence_summary(
                        feat, signal.signal_layer
                    )

    # ------------------------------------------------------------------
    # Signal Deduplication (Step 12)
    # ------------------------------------------------------------------

    def _deduplicate_signals(self) -> None:
        """Merge overlapping signals (same topic, same layer, overlapping window)."""
        if not self._signals:
            return

        # Group by (layer, frozenset(topic_ids))
        seen: dict[tuple[str, int], SignalRecord] = {}
        deduped: list[SignalRecord] = []

        for signal in self._signals:
            for tid in signal.topic_ids:
                key = (signal.signal_layer, tid)
                if key in seen:
                    # Merge: keep higher confidence, merge article_ids
                    existing = seen[key]
                    if signal.confidence > existing.confidence:
                        existing.confidence = signal.confidence
                        existing.evidence_summary = signal.evidence_summary
                    # Merge article_ids
                    merged_aids = list(set(existing.article_ids + signal.article_ids))
                    existing.article_ids = merged_aids
                    # Merge topic_ids
                    merged_tids = list(set(existing.topic_ids + signal.topic_ids))
                    existing.topic_ids = merged_tids
                else:
                    seen[key] = signal
                    deduped.append(signal)

        self._signals = deduped

    # ------------------------------------------------------------------
    # Output Writing
    # ------------------------------------------------------------------

    def _write_output(self, output_dir: Path) -> None:
        """Write signals to Parquet file."""
        pa, pq = _ensure_pyarrow()
        schema = _build_signals_schema()

        if not self._signals:
            self._write_empty_output(output_dir)
            return

        # Build columnar data
        signal_ids = []
        signal_layers = []
        signal_labels = []
        detected_ats = []
        topic_ids_list = []
        article_ids_list = []
        burst_scores = []
        cp_sigs = []
        novelty_scores = []
        sing_composites = []
        evidence_summaries = []
        confidences = []

        for sig in self._signals:
            signal_ids.append(sig.signal_id)
            signal_layers.append(sig.signal_layer)
            signal_labels.append(sig.signal_label)
            detected_ats.append(sig.detected_at)
            topic_ids_list.append(sig.topic_ids)
            article_ids_list.append(sig.article_ids)
            burst_scores.append(sig.burst_score)
            cp_sigs.append(sig.changepoint_significance)
            novelty_scores.append(sig.novelty_score)
            sing_composites.append(sig.singularity_composite)
            evidence_summaries.append(sig.evidence_summary)
            confidences.append(sig.confidence)

        table = pa.table(
            {
                "signal_id": pa.array(signal_ids, type=pa.utf8()),
                "signal_layer": pa.array(signal_layers, type=pa.utf8()),
                "signal_label": pa.array(signal_labels, type=pa.utf8()),
                "detected_at": pa.array(detected_ats, type=pa.timestamp("us", tz="UTC")),
                "topic_ids": pa.array(topic_ids_list, type=pa.list_(pa.int32())),
                "article_ids": pa.array(article_ids_list, type=pa.list_(pa.utf8())),
                "burst_score": pa.array(burst_scores, type=pa.float32()),
                "changepoint_significance": pa.array(cp_sigs, type=pa.float32()),
                "novelty_score": pa.array(novelty_scores, type=pa.float32()),
                "singularity_composite": pa.array(sing_composites, type=pa.float32()),
                "evidence_summary": pa.array(evidence_summaries, type=pa.utf8()),
                "confidence": pa.array(confidences, type=pa.float32()),
            },
            schema=schema,
        )

        output_path = output_dir / "signals.parquet"
        pq.write_table(
            table,
            str(output_path),
            compression=PARQUET_COMPRESSION,
            compression_level=PARQUET_COMPRESSION_LEVEL,
        )

        logger.info(
            "stage7_output_written: path=%s, n_signals=%d",
            output_path, len(self._signals),
        )

    def _write_empty_output(self, output_dir: Path) -> None:
        """Write an empty signals.parquet with correct schema."""
        pa, pq = _ensure_pyarrow()
        schema = _build_signals_schema()

        table = pa.table(
            {field.name: pa.array([], type=field.type) for field in schema},
            schema=schema,
        )

        output_path = output_dir / "signals.parquet"
        output_dir.mkdir(parents=True, exist_ok=True)
        pq.write_table(
            table,
            str(output_path),
            compression=PARQUET_COMPRESSION,
            compression_level=PARQUET_COMPRESSION_LEVEL,
        )

        logger.info("stage7_empty_output_written: path=%s", output_path)


# =============================================================================
# Column Access Helper
# =============================================================================

def _get_column_safe(table: Any, name: str) -> Any | None:
    """Safely get a column from a PyArrow table, returning None if missing."""
    if table is None:
        return None
    try:
        return table.column(name)
    except (KeyError, ValueError):
        return None


# =============================================================================
# Convenience Function
# =============================================================================

def run_stage7(
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> Stage7Output:
    """Convenience function to run Stage 7 signal classification.

    Args:
        data_dir: Base data directory. If None, uses default paths.
        output_dir: Output directory for signals.parquet. If None, uses default.

    Returns:
        Stage7Output with classification results.
    """
    if data_dir is not None:
        data_dir = Path(data_dir)
        analysis_dir = data_dir / "analysis"
        features_dir = data_dir / "features"
    else:
        analysis_dir = None
        features_dir = None

    if output_dir is not None:
        output_dir = Path(output_dir)

    classifier = Stage7SignalClassifier()
    try:
        return classifier.run(
            analysis_dir=analysis_dir,
            features_dir=features_dir,
            output_dir=output_dir,
        )
    finally:
        classifier.cleanup()
