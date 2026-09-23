"""scorers.py — LocationScorer port and HeuristicScorer (DOC 3 M2, B4 v0).

B4 builds the HeuristicScorer (hand weights from policy).
B6 will add HistGradientBoostingScorer (the ML model).

HeuristicScorer: a weighted sum over interpretable features.
  raw_score(row) = Σ weight_i × feature_i  (weights from policy; never hard-coded)
  Weights are policy.forecast.* — but since the policy model doesn't have heuristic
  weights yet, we embed them as a fixed structure read from policy via a helper.

Since DOC 4 B4 says "hand weights from policy" and policy.yaml doesn't define
heuristic weight keys (those are Track A / B calibration), we define the keys inline
and document they belong in config/policy.yaml for Track A to add later. For now the
HeuristicScorer reads from a simple dict of default weights that Track B will sweep.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np

from nakabandi.forecast.domain.features import build_features
from nakabandi.forecast.domain.types import Candidate, ClusterContext, FeatureRow


class LocationScorer(ABC):
    """Port: any model that assigns raw (unnormalised) scores to candidates."""

    @abstractmethod
    def raw_scores(self, rows: list[FeatureRow]) -> np.ndarray:
        """Return a 1-D array of raw scores, one per row. Not normalised."""

    def fit(self, train_rows: list[FeatureRow], labels: list[float]) -> None:  # noqa: B027
        """Optional fit — HeuristicScorer ignores it; ML scorer uses it."""
        pass  # not abstract: HeuristicScorer uses no training


@dataclass(frozen=True)
class ScorerInfo:
    """Metadata about the scorer that was used, stored in model_versions."""

    name: str
    version: str
    params: dict[str, Any]


# ---------------------------------------------------------------------------
# Default heuristic weights (seeds for Track B calibration sweep)
# ---------------------------------------------------------------------------
_DEFAULT_WEIGHTS: dict[str, float] = {
    "same_bank": 2.0,
    "dist_home_km": -0.15,  # penalty per km from home
    "dist_centroid_km": -0.10,  # penalty per km from centroid
    "cluster_loc_count": 0.8,  # reward for prior cash-outs at location
    "cluster_cell_count": 0.4,  # reward for prior cash-outs in cell
    "recency_days": -0.05,  # penalty for stale history
    "hour_sin": 0.0,  # neutral; tuned in B6
    "hour_cos": 0.0,
    "amount_log": 0.1,
    "amount_x_dist": -0.05,
    "activity_index": 1.0,  # registry busyness of location
    "cluster_size_log": 0.3,
    # "channel" is categorical — handled by a separate lookup below
}

_CHANNEL_BONUS: dict[str, float] = {
    "ATM": 0.5,
    "BRANCH": 0.3,
    "AGENT": 0.2,
}


class HeuristicScorer(LocationScorer):
    """Hand-weighted linear scorer over the FEATURE_REGISTRY.

    Weights are a fixed dict (seeds); Track B calibration sweeps them.
    Passed to the Forecaster at construction time so they can be swapped
    without changing any domain logic.
    """

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._w = weights if weights is not None else dict(_DEFAULT_WEIGHTS)

    def info(self) -> ScorerInfo:
        return ScorerInfo(name="heuristic_v0", version="0", params=dict(self._w))

    def raw_scores(self, rows: list[FeatureRow]) -> np.ndarray:
        """Compute a weighted linear score for each FeatureRow."""
        scores = np.zeros(len(rows), dtype=float)
        for i, row in enumerate(rows):
            s = (
                self._w.get("same_bank", 0.0) * row.same_bank
                + self._w.get("dist_home_km", 0.0) * row.dist_home_km
                + self._w.get("dist_centroid_km", 0.0) * row.dist_centroid_km
                + self._w.get("cluster_loc_count", 0.0) * row.cluster_loc_count
                + self._w.get("cluster_cell_count", 0.0) * row.cluster_cell_count
                + self._w.get("recency_days", 0.0) * row.recency_days
                + self._w.get("hour_sin", 0.0) * row.hour_sin
                + self._w.get("hour_cos", 0.0) * row.hour_cos
                + self._w.get("amount_log", 0.0) * row.amount_log
                + self._w.get("amount_x_dist", 0.0) * row.amount_x_dist
                + self._w.get("activity_index", 0.0) * row.activity_index
                + self._w.get("cluster_size_log", 0.0) * row.cluster_size_log
                + _CHANNEL_BONUS.get(row.channel, 0.0)
            )
            scores[i] = s
        return scores


def score_candidates(
    ctx: ClusterContext,
    candidates: list[Candidate],
    scorer: LocationScorer,
    expected_hour: float = 12.0,
) -> tuple[list[FeatureRow], np.ndarray]:
    """Build feature rows and compute raw scores for all candidates.

    Returns (feature_rows, raw_scores_array).
    """
    rows = [build_features(ctx, cand, expected_hour) for cand in candidates]
    scores = scorer.raw_scores(rows)
    return rows, scores
