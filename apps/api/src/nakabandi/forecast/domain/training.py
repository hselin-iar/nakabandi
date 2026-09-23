"""training.py — PointInTimeStats, TrainingSetBuilder, calibration helpers (DOC 3 M2 B6).

PointInTimeStats:
  Replays observations in observed_at order alongside complaints in reported_at order.
  For each complaint, yields the stats that were knowable at its reported time (strictly
  observed_at <= reported_at). This prevents leakage.

TrainingSetBuilder:
  Consumes a sequence of (complaint, cluster_context, candidate_list, label) tuples
  sorted by reported_at and produces a time-based train/validation split.
  No random splitting — always time-ordered (oldest = train, newest = val).

TrainingRow:
  (feature_row: FeatureRow, label: float)  where label = 1 if this was the actual
  cash-out location, 0 otherwise.

CalibrationResult:
  Wraps a fitted IsotonicRegression + the brier score and reliability stats.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss

from nakabandi.forecast.domain.features import build_features
from nakabandi.forecast.domain.types import Candidate, ClusterContext, FeatureRow

# ---------------------------------------------------------------------------
# Training data types (pure domain — no I/O)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrainingRow:
    """One (candidate, label) pair extracted from history."""

    feature_row: FeatureRow
    label: float  # 1.0 = actual cash-out location; 0.0 = non-event candidate


@dataclass
class TrainingSet:
    """Train and validation splits produced by TrainingSetBuilder."""

    train_rows: list[TrainingRow]
    val_rows: list[TrainingRow]
    data_hash: str  # SHA-256 of the sorted external_refs used to build this set


@dataclass
class CalibrationResult:
    """Output of calibrate_scores()."""

    calibrator: IsotonicRegression
    brier_before: float
    brier_after: float
    # Reliability curve (for plotting / evidence)
    fraction_of_positives: list[float]
    mean_predicted_value: list[float]


# ---------------------------------------------------------------------------
# PointInTimeStats
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ObservationSnapshot:
    """Stats that were knowable at a specific reported_at timestamp."""

    cashout_location_counts: dict[str, int]
    cashout_cell_counts: dict[str, int]
    cashout_location_recency: dict[str, float]
    cashout_channel_counts: dict[str, int]
    prior_cashout_count: int
    unique_accounts: int
    total_cashout_paise: int
    centroid_lat: float | None
    centroid_lon: float | None
    radius_km: float


class PointInTimeStats:
    """Builds cluster observation snapshots that are strictly as-of reported_at.

    Usage (called by TrainingSetBuilder, not directly):
        pit = PointInTimeStats()
        for ext_ref, reported_at, obs_list in sorted_history:
            snapshot = pit.snapshot_at(cluster_id, reported_at, all_obs)

    In production we replay the observation table sorted by observed_at and
    track a running dict per cluster. The key invariant: snapshot_at(t) only
    includes observations with observed_at <= t.
    """

    def __init__(self) -> None:
        # cluster_id -> list of (observed_at_ts, location_id, cell_id, amount_paise, channel)
        self._obs: dict[str, list[tuple[float, str, str, int, str]]] = {}

    def add_observation(
        self,
        cluster_id: str,
        observed_at_ts: float,  # unix epoch seconds
        location_id: str,
        cell_id: str,
        amount_paise: int,
        channel: str,
    ) -> None:
        """Add one cash-out observation. Must be called in observed_at order."""
        self._obs.setdefault(cluster_id, []).append(
            (observed_at_ts, location_id, cell_id, amount_paise, channel)
        )

    def snapshot_at(
        self,
        cluster_id: str,
        as_of_ts: float,
        cluster_lat: float | None = None,
        cluster_lon: float | None = None,
        cluster_radius_km: float = 5.0,
        unique_accounts: int = 1,
        now_ts: float | None = None,  # for recency_days calculation
    ) -> ObservationSnapshot:
        """Return the observation stats strictly as-of as_of_ts."""
        if now_ts is None:
            now_ts = as_of_ts

        obs = [o for o in self._obs.get(cluster_id, []) if o[0] <= as_of_ts]

        loc_counts: dict[str, int] = {}
        cell_counts: dict[str, int] = {}
        channel_counts: dict[str, int] = {}
        loc_latest: dict[str, float] = {}  # location_id -> latest observed_at_ts
        total_paise = 0

        for obs_ts, loc_id, cell_id, amount, channel in obs:
            loc_counts[loc_id] = loc_counts.get(loc_id, 0) + 1
            cell_counts[cell_id] = cell_counts.get(cell_id, 0) + 1
            channel_counts[channel] = channel_counts.get(channel, 0) + 1
            if loc_id not in loc_latest or obs_ts > loc_latest[loc_id]:
                loc_latest[loc_id] = obs_ts
            total_paise += amount

        _SECS_PER_DAY = 86_400.0
        loc_recency = {
            loc_id: max(0.0, (now_ts - latest_ts) / _SECS_PER_DAY)
            for loc_id, latest_ts in loc_latest.items()
        }

        return ObservationSnapshot(
            cashout_location_counts=loc_counts,
            cashout_cell_counts=cell_counts,
            cashout_location_recency=loc_recency,
            cashout_channel_counts=channel_counts,
            prior_cashout_count=len(obs),
            unique_accounts=unique_accounts,
            total_cashout_paise=total_paise,
            centroid_lat=cluster_lat,
            centroid_lon=cluster_lon,
            radius_km=cluster_radius_km,
        )


# ---------------------------------------------------------------------------
# TrainingSetBuilder
# ---------------------------------------------------------------------------


class TrainingSetBuilder:
    """Builds a time-ordered TrainingSet from replayed history.

    Invariant: the validation slice is always the most recent val_fraction
    of the data (by reported_at order), never randomly sampled. This is
    the only way to prevent leakage in a time-series setting.

    Usage:
        builder = TrainingSetBuilder(val_fraction=0.2)
        builder.add_complaint(complaint_ctx, candidates, actual_location_id)
        ts = builder.build(expected_hour=15.0)
    """

    def __init__(self, val_fraction: float = 0.2) -> None:
        if not 0.0 < val_fraction < 1.0:
            raise ValueError(f"val_fraction must be in (0, 1), got {val_fraction}")
        self._val_fraction = val_fraction
        # List of (reported_at_ts, ctx, candidates, actual_location_id)
        self._records: list[tuple[float, ClusterContext, list[Candidate], str]] = []

    def add_complaint(
        self,
        ctx: ClusterContext,
        candidates: list[Candidate],
        actual_location_id: str,
    ) -> None:
        """Add one complaint's candidates to the builder."""

        reported_at_ts = float(ctx.reported_at.timestamp())
        self._records.append((reported_at_ts, ctx, candidates, actual_location_id))

    def build(self, expected_hour: float = 15.0) -> TrainingSet:
        """Build the TrainingSet from all added complaints.

        Records are sorted by reported_at ascending before splitting.
        """
        import hashlib

        if not self._records:
            return TrainingSet(train_rows=[], val_rows=[], data_hash="")

        # Sort by reported_at ascending (time-based split, no leakage)
        records = sorted(self._records, key=lambda r: r[0])

        n_val = max(1, int(len(records) * self._val_fraction))
        train_records = records[: len(records) - n_val]
        val_records = records[len(records) - n_val :]

        def _make_rows(
            recs: list[tuple[float, ClusterContext, list[Candidate], str]],
        ) -> list[TrainingRow]:
            rows: list[TrainingRow] = []
            for _, ctx, candidates, actual_loc in recs:
                for cand in candidates:
                    feat = build_features(ctx, cand, expected_hour)
                    label = 1.0 if cand.location_id == actual_loc else 0.0
                    rows.append(TrainingRow(feature_row=feat, label=label))
            return rows

        train_rows = _make_rows(train_records)
        val_rows = _make_rows(val_records)

        # Data hash: SHA-256 of sorted complaint_ids in the entire dataset
        all_ids = sorted(str(r[1].complaint_id) for r in records)
        data_hash = hashlib.sha256("|".join(all_ids).encode()).hexdigest()

        return TrainingSet(train_rows=train_rows, val_rows=val_rows, data_hash=data_hash)


# ---------------------------------------------------------------------------
# Calibration helpers
# ---------------------------------------------------------------------------


def calibrate_scores(
    raw_scores: np.ndarray,
    labels: np.ndarray,
) -> CalibrationResult:
    """Fit an isotonic regression calibrator on the raw_scores / label pairs.

    Returns the fitted calibrator and reliability curve data for plotting.
    Must be called on the validation slice only (not the training slice).
    """
    raw_scores = np.asarray(raw_scores, dtype=float)
    labels = np.asarray(labels, dtype=float)

    brier_before = float(brier_score_loss(labels, raw_scores))

    calibrator = IsotonicRegression(out_of_bounds="clip")
    calibrator.fit(raw_scores, labels)

    cal_scores = calibrator.predict(raw_scores)
    brier_after = float(brier_score_loss(labels, cal_scores))

    n_bins = min(10, max(3, int(np.sqrt(len(labels)))))
    try:
        frac_pos, mean_pred = calibration_curve(
            labels, cal_scores, n_bins=n_bins, strategy="quantile"
        )
    except ValueError:
        frac_pos = np.array([float(labels.mean())])
        mean_pred = np.array([float(cal_scores.mean())])

    return CalibrationResult(
        calibrator=calibrator,
        brier_before=brier_before,
        brier_after=brier_after,
        fraction_of_positives=frac_pos.tolist(),
        mean_predicted_value=mean_pred.tolist(),
    )
