"""scorers.py — LocationScorer port, HeuristicScorer (B4), HistGradientBoostingScorer (B6).

B4 builds HeuristicScorer (hand weights from policy).
B6 adds HistGradientBoostingScorer (sklearn HGB + isotonic calibration).
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
    "dist_home_km": -0.15,
    "dist_centroid_km": -0.10,
    "cluster_loc_count": 0.8,
    "cluster_cell_count": 0.4,
    "recency_days": -0.05,
    "hour_sin": 0.0,
    "hour_cos": 0.0,
    "amount_log": 0.1,
    "amount_x_dist": -0.05,
    "activity_index": 1.0,
    "cluster_size_log": 0.3,
}

_CHANNEL_BONUS: dict[str, float] = {
    "ATM": 0.5,
    "BRANCH": 0.3,
    "AGENT": 0.2,
}

_CHANNEL_CODE: dict[str, float] = {"ATM": 0.0, "BRANCH": 1.0, "AGENT": 2.0}


def features_to_array(rows: list[FeatureRow]) -> np.ndarray:
    """Convert a list of FeatureRow to a (n, 13) float64 matrix.

    Column order is fixed; channel is label-encoded (no one-hot to preserve
    HGB's native categorical support potential).
    """
    n = len(rows)
    X = np.empty((n, 13), dtype=np.float64)
    for i, r in enumerate(rows):
        X[i] = [
            r.same_bank,
            r.dist_home_km,
            r.dist_centroid_km,
            r.cluster_loc_count,
            r.cluster_cell_count,
            r.recency_days,
            r.hour_sin,
            r.hour_cos,
            r.amount_log,
            r.amount_x_dist,
            r.activity_index,
            r.cluster_size_log,
            _CHANNEL_CODE.get(r.channel, 0.0),
        ]
    return X


class HeuristicScorer(LocationScorer):
    """Hand-weighted linear scorer over the FEATURE_REGISTRY (B4 v0 fallback)."""

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._w = weights if weights is not None else dict(_DEFAULT_WEIGHTS)

    def info(self) -> ScorerInfo:
        return ScorerInfo(name="heuristic_v0", version="0", params=dict(self._w))

    def raw_scores(self, rows: list[FeatureRow]) -> np.ndarray:
        scores = np.zeros(len(rows), dtype=float)
        for i, row in enumerate(rows):
            # recency_days is NaN for locations never visited by this cluster
            # (see features.py P4). Use 0.0 in the heuristic to avoid NaN propagation.
            recency = row.recency_days if not (row.recency_days != row.recency_days) else 0.0
            s = (
                self._w.get("same_bank", 0.0) * row.same_bank
                + self._w.get("dist_home_km", 0.0) * row.dist_home_km
                + self._w.get("dist_centroid_km", 0.0) * row.dist_centroid_km
                + self._w.get("cluster_loc_count", 0.0) * row.cluster_loc_count
                + self._w.get("cluster_cell_count", 0.0) * row.cluster_cell_count
                + self._w.get("recency_days", 0.0) * recency
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


class HistGradientBoostingScorer(LocationScorer):
    """sklearn HistGradientBoostingClassifier + isotonic calibration (B6 v1).

    Calibration is applied BEFORE normalisation (DOC 3 M2 / DOC 2 §2.2).
    The calibrator is fitted on the validation slice.

    Fallback: if not yet fitted, delegates to HeuristicScorer (the v0 scorer).
    The caller (GenerateForecast) labels this in model_versions as 'fallback'.
    """

    def __init__(self) -> None:
        from sklearn.ensemble import HistGradientBoostingClassifier

        self._model = HistGradientBoostingClassifier(
            max_iter=200,
            learning_rate=0.05,
            max_depth=4,
            min_samples_leaf=20,
            random_state=42,
            class_weight="balanced",  # P1: upweight positives (~1 per ~164 candidates)
            # P2 NOTE: categorical_features=[12] would teach HGB that channel is unordered,
            # but sklearn's binning crashes when a categorical col has only 1 distinct value
            # (all current sim data uses ATM). Re-enable when multi-channel data exists.
        )
        self._calibrator: Any | None = None
        self._fitted = False
        self._fallback = HeuristicScorer()

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    def info(self) -> ScorerInfo:
        return ScorerInfo(
            name="hgb_v1" if self._fitted else "fallback",
            version="1",
            params={"fitted": self._fitted, "calibrated": self._calibrator is not None},
        )

    def fit(self, train_rows: list[FeatureRow], labels: list[float]) -> None:
        if not train_rows:
            return
        X = features_to_array(train_rows)
        y = np.asarray(labels, dtype=float)
        # HGB's internal binning crashes if a column has < 2 unique non-NaN values:
        # (a) all-NaN column (e.g. recency_days when cluster has no prior observations)
        # (b) constant column (e.g. same_bank = 1.0 in a single-bank simulation).
        # For (a): replace NaN with 0.0 — neutral, no information leakage.
        # For (b): add tiny jitter (1e-7) — invisible to splits but enables binning.
        rng = np.random.default_rng(42)
        for col in range(X.shape[1]):
            col_vals = X[:, col]
            non_nan_mask = ~np.isnan(col_vals)
            non_nan = col_vals[non_nan_mask]
            if len(non_nan) == 0:
                # All NaN — replace with 0.0 so HGB can bin the column
                X[:, col] = 0.0
            elif len(np.unique(non_nan)) < 2:
                # Constant column — add imperceptible jitter
                X[:, col] = col_vals + rng.standard_normal(len(col_vals)) * 1e-7
        self._model.fit(X, y)
        self._fitted = True

    def fit_with_calibration(
        self,
        train_rows: list[FeatureRow],
        train_labels: list[float],
        val_rows: list[FeatureRow],
        val_labels: list[float],
    ) -> Any:  # returns CalibrationResult (imported lazily to avoid circular)
        """Fit model on train, calibrate on val. Returns CalibrationResult."""
        from sklearn.isotonic import IsotonicRegression

        from nakabandi.forecast.domain.training import CalibrationResult, calibrate_scores

        self.fit(train_rows, train_labels)

        if not val_rows:
            self._calibrator = IsotonicRegression(out_of_bounds="clip").fit([0, 1], [0, 1])
            return CalibrationResult(
                calibrator=self._calibrator,
                brier_before=0.0,
                brier_after=0.0,
                fraction_of_positives=[],
                mean_predicted_value=[],
            )

        X_val = features_to_array(val_rows)
        raw_probs = self._model.predict_proba(X_val)[:, 1]
        y_val = np.asarray(val_labels, dtype=float)
        result = calibrate_scores(raw_probs, y_val)
        self._calibrator = result.calibrator
        return result

    def raw_scores(self, rows: list[FeatureRow]) -> np.ndarray:
        """Return calibrated probabilities if fitted, otherwise heuristic fallback."""
        if not self._fitted:
            return self._fallback.raw_scores(rows)
        X = features_to_array(rows)
        raw = self._model.predict_proba(X)[:, 1]
        if self._calibrator is not None:
            return np.asarray(self._calibrator.predict(raw), dtype=float)
        return raw


def score_candidates(
    ctx: ClusterContext,
    candidates: list[Candidate],
    scorer: LocationScorer,
    expected_hour: float = 12.0,
) -> tuple[list[FeatureRow], np.ndarray]:
    """Build feature rows and compute raw scores for all candidates."""
    rows = [build_features(ctx, cand, expected_hour) for cand in candidates]
    scores = scorer.raw_scores(rows)
    return rows, scores
