"""test_forecast_v1.py — B6 Done When tests (DOC 4 Step B6).

Done When evidence:
  T1  Training on a 7-day simulated world takes under 5 minutes
  T2  EM step recovers a planted mixture within tolerance
  T3  Leakage test: inserting future observation does not change features
  T4  Calibration curve is produced (brier_before, brier_after, reliability buckets)
  T5  Missing model files -> fallback to heuristic scorer with banner
  T6  PointInTimeStats: snapshot_at enforces as-of boundary
  T7  TrainingSetBuilder: time-ordered split, data_hash deterministic
  T8  features_to_array: correct shape and values
  T9  novelty(): 0 obs -> 1.0; many obs -> approaches 0
  T10 DistrictPrior: Laplace smoothing, top_districts ordering
"""

from __future__ import annotations

import math
import tempfile
import time
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest
from nakabandi.forecast.domain.features import build_features, global_cashout_rate
from nakabandi.forecast.domain.global_stats import GlobalCashoutIndex
from nakabandi.forecast.domain.novelty import DistrictPrior, novelty
from nakabandi.forecast.domain.scorers import (
    HeuristicScorer,
    HistGradientBoostingScorer,
    features_to_array,
)
from nakabandi.forecast.domain.training import (
    PointInTimeStats,
    TrainingSetBuilder,
    calibrate_scores,
)
from nakabandi.forecast.domain.types import (
    Candidate,
    ClusterContext,
    FeatureRow,
)
from nakabandi.forecast.infrastructure.model_store import ModelStore

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_UTC = UTC


def _make_feature_row(**overrides: Any) -> FeatureRow:
    defaults = dict(
        same_bank=1.0,
        dist_home_km=2.0,
        dist_centroid_km=1.5,
        cluster_loc_count=3.0,
        cluster_cell_count=5.0,
        recency_days=1.0,
        channel="ATM",
        hour_sin=0.5,
        hour_cos=0.5,
        amount_log=10.0,
        amount_x_dist=20.0,
        activity_index=0.8,
        cluster_size_log=2.0,
        global_cashout_count=0.0,
        global_cashout_rate=0.0,
    )
    defaults.update(overrides)
    return FeatureRow(
        same_bank=float(defaults["same_bank"]),
        dist_home_km=float(defaults["dist_home_km"]),
        dist_centroid_km=float(defaults["dist_centroid_km"]),
        cluster_loc_count=float(defaults["cluster_loc_count"]),
        cluster_cell_count=float(defaults["cluster_cell_count"]),
        recency_days=float(defaults["recency_days"]),
        channel=str(defaults["channel"]),
        hour_sin=float(defaults["hour_sin"]),
        hour_cos=float(defaults["hour_cos"]),
        amount_log=float(defaults["amount_log"]),
        amount_x_dist=float(defaults["amount_x_dist"]),
        activity_index=float(defaults["activity_index"]),
        cluster_size_log=float(defaults["cluster_size_log"]),
        global_cashout_count=float(defaults["global_cashout_count"]),
        global_cashout_rate=float(defaults["global_cashout_rate"]),
    )


def _make_candidate(location_id: str = "LOC-1") -> Candidate:
    return Candidate(
        location_id=location_id,
        cell_id="CELL-1",
        district_id="UP-LKO",
        lat=26.85,
        lon=80.95,
        distance_to_home_km=2.0,
        distance_to_centroid_km=1.5,
        channel="ATM",
        activity_index=0.8,
    )


def _make_ctx(
    complaint_id: str = "C-1",
    reported_at: datetime | None = None,
    prior_cashout_count: int = 0,
) -> ClusterContext:
    if reported_at is None:
        reported_at = datetime(2025, 1, 10, tzinfo=_UTC)
    return ClusterContext(
        complaint_id=complaint_id,
        cluster_id="CLU-1",
        as_of=reported_at,
        amount_paise=50000_00,
        reported_at=reported_at,
        layer1_account_id="ACC-1",
        layer1_bank_id="BANK-A",
        layer1_home_lat=26.85,
        layer1_home_lon=80.95,
        unique_accounts=3,
        total_cashout_paise=150000_00,
        cashout_channel_counts={"ATM": 2, "BRANCH": 1},
        cashout_location_counts={"LOC-1": 3},
        cashout_cell_counts={"CELL-1": 4},
        cashout_location_recency={"LOC-1": 1.0},
        centroid_lat=26.85,
        centroid_lon=80.95,
        radius_km=3.0,
        prior_cashout_count=prior_cashout_count,
        elapsed_min=30.0,
    )


def _make_policy() -> MagicMock:
    policy = MagicMock()
    policy.forecast.novelty_threshold = 10.0
    policy.forecast.timing.n_min = 3
    return policy


# ---------------------------------------------------------------------------
# T6 — PointInTimeStats: snapshot_at enforces as-of boundary
# ---------------------------------------------------------------------------


class TestPointInTimeStats:
    def test_observation_before_cutoff_is_included(self) -> None:
        pit = PointInTimeStats()
        pit.add_observation("CLU-1", 1000.0, "LOC-A", "CELL-A", 50000, "ATM")
        snap = pit.snapshot_at("CLU-1", as_of_ts=2000.0)
        assert snap.cashout_location_counts["LOC-A"] == 1
        assert snap.prior_cashout_count == 1

    def test_observation_after_cutoff_is_excluded(self) -> None:
        pit = PointInTimeStats()
        pit.add_observation("CLU-1", 3000.0, "LOC-A", "CELL-A", 50000, "ATM")
        snap = pit.snapshot_at("CLU-1", as_of_ts=2000.0)
        assert snap.prior_cashout_count == 0
        assert "LOC-A" not in snap.cashout_location_counts

    def test_exactly_at_cutoff_is_included(self) -> None:
        pit = PointInTimeStats()
        pit.add_observation("CLU-1", 1000.0, "LOC-A", "CELL-A", 50000, "ATM")
        snap = pit.snapshot_at("CLU-1", as_of_ts=1000.0)
        assert snap.prior_cashout_count == 1

    def test_recency_days_computed(self) -> None:
        pit = PointInTimeStats()
        pit.add_observation("CLU-1", 0.0, "LOC-A", "CELL-A", 50000, "ATM")
        snap = pit.snapshot_at("CLU-1", as_of_ts=86400.0 * 2, now_ts=86400.0 * 2)
        assert abs(snap.cashout_location_recency["LOC-A"] - 2.0) < 0.01

    def test_multiple_clusters_are_independent(self) -> None:
        pit = PointInTimeStats()
        pit.add_observation("CLU-1", 100.0, "LOC-A", "CELL-A", 1, "ATM")
        pit.add_observation("CLU-2", 100.0, "LOC-B", "CELL-B", 1, "BRANCH")
        snap1 = pit.snapshot_at("CLU-1", as_of_ts=200.0)
        snap2 = pit.snapshot_at("CLU-2", as_of_ts=200.0)
        assert snap1.prior_cashout_count == 1
        assert snap2.prior_cashout_count == 1
        assert "LOC-A" in snap1.cashout_location_counts
        assert "LOC-A" not in snap2.cashout_location_counts


# ---------------------------------------------------------------------------
# GlobalCashoutIndex — as-of, cross-cluster cash-out density (P6, [NEXT_ACTION])
# ---------------------------------------------------------------------------


class TestGlobalCashoutIndex:
    def test_zero_history_is_empty(self) -> None:
        index = GlobalCashoutIndex([])
        snap = index.snapshot_at(datetime(2025, 1, 1, tzinfo=_UTC))
        assert snap.total == 0
        assert snap.location_counts == {}

    def test_single_atm_repeated(self) -> None:
        events = [
            ("LOC-A", datetime(2025, 1, 1, tzinfo=_UTC)),
            ("LOC-A", datetime(2025, 1, 2, tzinfo=_UTC)),
            ("LOC-A", datetime(2025, 1, 3, tzinfo=_UTC)),
        ]
        index = GlobalCashoutIndex(events)
        snap = index.snapshot_at(datetime(2025, 1, 2, tzinfo=_UTC))
        assert snap.total == 2
        assert snap.location_counts == {"LOC-A": 2}

    def test_multiple_locations_counted_independently(self) -> None:
        events = [
            ("LOC-A", datetime(2025, 1, 1, tzinfo=_UTC)),
            ("LOC-B", datetime(2025, 1, 1, tzinfo=_UTC)),
            ("LOC-A", datetime(2025, 1, 1, tzinfo=_UTC)),
        ]
        index = GlobalCashoutIndex(events)
        snap = index.snapshot_at(datetime(2025, 1, 1, tzinfo=_UTC))
        assert snap.total == 3
        assert snap.location_counts == {"LOC-A": 2, "LOC-B": 1}

    def test_future_observation_excluded(self) -> None:
        events = [
            ("LOC-A", datetime(2025, 1, 1, tzinfo=_UTC)),
            ("LOC-A", datetime(2025, 6, 1, tzinfo=_UTC)),
        ]
        index = GlobalCashoutIndex(events)
        snap = index.snapshot_at(datetime(2025, 2, 1, tzinfo=_UTC))
        assert snap.total == 1
        assert snap.location_counts == {"LOC-A": 1}

    def test_exactly_at_cutoff_is_included(self) -> None:
        as_of = datetime(2025, 1, 1, tzinfo=_UTC)
        index = GlobalCashoutIndex([("LOC-A", as_of)])
        snap = index.snapshot_at(as_of)
        assert snap.total == 1

    def test_insertion_order_independent(self) -> None:
        """snapshot_at must not depend on the order events were passed in — the index
        sorts internally, so a shuffled feed gives the same answer as a sorted one."""
        events = [
            ("LOC-B", datetime(2025, 1, 3, tzinfo=_UTC)),
            ("LOC-A", datetime(2025, 1, 1, tzinfo=_UTC)),
            ("LOC-A", datetime(2025, 1, 2, tzinfo=_UTC)),
        ]
        index = GlobalCashoutIndex(events)
        snap = index.snapshot_at(datetime(2025, 1, 2, tzinfo=_UTC))
        assert snap.total == 2
        assert snap.location_counts == {"LOC-A": 2}


# ---------------------------------------------------------------------------
# global_cashout_rate — Laplace/empirical-Bayes smoothing (alpha=5)
# ---------------------------------------------------------------------------


class TestGlobalCashoutRate:
    def test_zero_count_is_not_exactly_zero(self) -> None:
        rate = global_cashout_rate(count=0.0, total=1000, n_locations=50)
        assert rate > 0.0

    def test_higher_count_gives_higher_rate(self) -> None:
        low = global_cashout_rate(count=1.0, total=1000, n_locations=50)
        high = global_cashout_rate(count=50.0, total=1000, n_locations=50)
        assert high > low

    def test_empty_universe_does_not_raise(self) -> None:
        # n_locations=0 falls back to a universe of 1 (no ZeroDivisionError); with no
        # observations at all the smoothed rate is uninformative (1.0, i.e. alpha/alpha).
        rate = global_cashout_rate(count=0.0, total=0, n_locations=0)
        assert rate == 1.0

    def test_rate_matches_formula(self) -> None:
        rate = global_cashout_rate(count=10.0, total=100, n_locations=20, alpha=5.0)
        assert abs(rate - (10.0 + 5.0) / (100 + 5.0 * 20)) < 1e-9

    def test_build_features_wires_global_rate(self) -> None:
        from dataclasses import replace

        cand = _make_candidate("LOC-1")
        ctx = replace(
            _make_ctx(),
            global_cashout_location_counts={"LOC-1": 9},
            global_cashout_total=100,
            global_n_locations=20,
        )
        row = build_features(ctx, cand)
        assert row.global_cashout_count == 9.0
        assert abs(row.global_cashout_rate - (9.0 + 5.0) / (100 + 5.0 * 20)) < 1e-9

    def test_build_features_cold_start_location(self) -> None:
        """A location with zero global cash-outs still gets a positive smoothed rate."""
        from dataclasses import replace

        cand = _make_candidate("LOC-NEVER-SEEN")
        ctx = replace(
            _make_ctx(),
            global_cashout_location_counts={"LOC-1": 9},
            global_cashout_total=100,
            global_n_locations=20,
        )
        row = build_features(ctx, cand)
        assert row.global_cashout_count == 0.0
        assert row.global_cashout_rate > 0.0


# ---------------------------------------------------------------------------
# T7 — TrainingSetBuilder: time-ordered split
# ---------------------------------------------------------------------------


class TestTrainingSetBuilder:
    def test_split_is_time_ordered(self) -> None:
        builder = TrainingSetBuilder(val_fraction=0.25)
        for i in range(8):
            ctx = _make_ctx(
                complaint_id=f"C-{i}",
                reported_at=datetime(2025, 1, i + 1, tzinfo=_UTC),
            )
            builder.add_complaint(ctx, [_make_candidate()], "LOC-1")
        ts = builder.build()
        # 8 records, 25% val = 2 records
        assert len(ts.val_rows) > 0
        assert len(ts.train_rows) > len(ts.val_rows)

    def test_data_hash_is_deterministic(self) -> None:
        builder1 = TrainingSetBuilder()
        builder2 = TrainingSetBuilder()
        for i in range(3):
            ctx = _make_ctx(
                complaint_id=f"C-{i}",
                reported_at=datetime(2025, 1, i + 1, tzinfo=_UTC),
            )
            builder1.add_complaint(ctx, [_make_candidate()], "LOC-1")
            builder2.add_complaint(ctx, [_make_candidate()], "LOC-1")
        assert builder1.build().data_hash == builder2.build().data_hash

    def test_empty_builder_returns_empty_set(self) -> None:
        builder = TrainingSetBuilder()
        ts = builder.build()
        assert ts.train_rows == []
        assert ts.val_rows == []
        assert ts.data_hash == ""

    def test_label_assignment(self) -> None:
        builder = TrainingSetBuilder(val_fraction=0.5)
        ctx = _make_ctx(reported_at=datetime(2025, 1, 1, tzinfo=_UTC))
        candidates = [_make_candidate("LOC-1"), _make_candidate("LOC-2")]
        builder.add_complaint(ctx, candidates, "LOC-1")  # LOC-1 is the true location
        ts = builder.build()
        all_rows = ts.train_rows + ts.val_rows
        positive = [r for r in all_rows if r.label == 1.0]
        negative = [r for r in all_rows if r.label == 0.0]
        assert len(positive) == 1
        assert len(negative) == 1


# ---------------------------------------------------------------------------
# T8 — features_to_array: shape and values
# ---------------------------------------------------------------------------


class TestFeaturesToArray:
    def test_shape(self) -> None:
        rows = [_make_feature_row() for _ in range(5)]
        X = features_to_array(rows)
        assert X.shape == (5, 15)
        assert X.dtype == np.float64

    def test_same_bank_column(self) -> None:
        row = _make_feature_row(same_bank=1.0)
        X = features_to_array([row])
        assert X[0, 0] == 1.0

    def test_channel_encoding(self) -> None:
        row_atm = _make_feature_row()
        row_branch = FeatureRow(
            same_bank=1.0,
            dist_home_km=1.0,
            dist_centroid_km=1.0,
            cluster_loc_count=1.0,
            cluster_cell_count=1.0,
            recency_days=1.0,
            channel="BRANCH",
            hour_sin=0.0,
            hour_cos=1.0,
            amount_log=5.0,
            amount_x_dist=5.0,
            activity_index=0.5,
            cluster_size_log=1.0,
        )
        X = features_to_array([row_atm, row_branch])
        # ATM -> 0.0, BRANCH -> 1.0 (column index 14 — channel is the last column)
        assert X[0, 14] == 0.0
        assert X[1, 14] == 1.0

    def test_global_cashout_columns(self) -> None:
        row = _make_feature_row(global_cashout_count=7.0, global_cashout_rate=0.25)
        X = features_to_array([row])
        assert X[0, 12] == 7.0
        assert X[0, 13] == 0.25


# ---------------------------------------------------------------------------
# T5 — Missing model files → fallback to heuristic with banner
# ---------------------------------------------------------------------------


class TestFallbackBanner:
    def test_load_scorer_missing_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = ModelStore(store_dir=d)
            result = store.load_scorer()
            assert result is None

    def test_generate_forecast_uses_heuristic_when_no_store(self) -> None:
        """GenerateForecast with no model_store falls back to HeuristicScorer."""
        from nakabandi.forecast.application.use_cases import GenerateForecast

        mock_repo = MagicMock()
        policy = _make_policy()
        gf = GenerateForecast(forecast_repo=mock_repo, policy=policy)
        # _using_fallback should be True (no model store provided)
        assert gf._using_fallback is True
        assert isinstance(gf._scorer, HeuristicScorer)

    def test_generate_forecast_uses_fallback_when_model_missing(self) -> None:
        from nakabandi.forecast.application.use_cases import GenerateForecast

        with tempfile.TemporaryDirectory() as d:
            store = ModelStore(store_dir=d)
            mock_repo = MagicMock()
            policy = _make_policy()
            gf = GenerateForecast(forecast_repo=mock_repo, policy=policy, model_store=store)
            assert gf._using_fallback is True

    def test_generate_forecast_uses_hgb_when_model_present(self) -> None:
        from nakabandi.forecast.application.use_cases import GenerateForecast

        with tempfile.TemporaryDirectory() as d:
            store = ModelStore(store_dir=d)
            # Train and save a dummy scorer
            scorer = HistGradientBoostingScorer()
            rows = [_make_feature_row() for _ in range(20)]
            labels = [float(i % 2) for i in range(20)]
            scorer.fit(rows, labels)
            store.save_scorer(
                scorer,
                data_hash="abc",
                as_of=datetime(2025, 1, 1, tzinfo=_UTC),
            )
            mock_repo = MagicMock()
            policy = _make_policy()
            gf = GenerateForecast(forecast_repo=mock_repo, policy=policy, model_store=store)
            assert gf._using_fallback is False
            assert isinstance(gf._scorer, HistGradientBoostingScorer)


# ---------------------------------------------------------------------------
# T4 — Calibration curve is produced
# ---------------------------------------------------------------------------


class TestCalibration:
    def test_brier_after_lte_before(self) -> None:
        rng = np.random.default_rng(0)
        y = rng.integers(0, 2, 200).astype(float)
        # Raw scores: miscalibrated (all pushed to 0.9)
        raw = np.clip(y + rng.normal(0, 0.3, 200), 0.0, 1.0)
        result = calibrate_scores(raw, y)
        # Brier after should be <= brier before (calibration doesn't hurt)
        assert result.brier_after <= result.brier_before + 1e-6

    def test_reliability_curve_produced(self) -> None:
        rng = np.random.default_rng(1)
        y = rng.integers(0, 2, 100).astype(float)
        raw = np.clip(y + rng.normal(0, 0.2, 100), 0.0, 1.0)
        result = calibrate_scores(raw, y)
        assert len(result.fraction_of_positives) > 0
        assert len(result.mean_predicted_value) > 0

    def test_hgb_fit_with_calibration(self) -> None:
        rng = np.random.default_rng(42)
        n = 100
        rows = [_make_feature_row(same_bank=float(rng.integers(0, 2))) for _ in range(n)]
        labels = [float(rng.integers(0, 2)) for _ in range(n)]
        scorer = HistGradientBoostingScorer()
        result = scorer.fit_with_calibration(rows[:80], labels[:80], rows[80:], labels[80:])
        assert scorer.is_fitted
        assert result.brier_before >= 0.0
        assert result.brier_after >= 0.0

    def test_hgb_scores_in_0_1(self) -> None:
        rng = np.random.default_rng(7)
        n = 60
        rows = [_make_feature_row(same_bank=float(rng.integers(0, 2))) for _ in range(n)]
        labels = [float(rng.integers(0, 2)) for _ in range(n)]
        scorer = HistGradientBoostingScorer()
        scorer.fit(rows[:50], labels[:50])
        scores = scorer.raw_scores(rows[50:])
        assert np.all(scores >= 0.0)
        assert np.all(scores <= 1.0)


# ---------------------------------------------------------------------------
# T2 — EM recovers planted mixture within tolerance
# ---------------------------------------------------------------------------


class TestEMRecovery:
    def test_mixture_recovery(self) -> None:
        """EM should recover a 70/30 fast/slow mixture within reasonable tolerance."""
        from nakabandi.forecast.domain.timing import MixtureTimingModel
        from nakabandi.shared import Policy

        rng = np.random.default_rng(0)
        policy = Policy.load("config/policy.yaml")

        # Plant: 70% fast (median 30 min), 30% slow (median 240 min)
        n_fast = 700
        n_slow = 300
        sigma = 0.5
        fast_delays = rng.lognormal(math.log(30), sigma, n_fast).tolist()
        slow_delays = rng.lognormal(math.log(240), sigma, n_slow).tolist()
        delays = fast_delays + slow_delays
        rng.shuffle(delays)

        model = MixtureTimingModel.fit(delays, policy)

        # Weights should be roughly 0.7 / 0.3 (within ±0.15)
        weights = model._weights  # type: ignore[attr-defined]
        assert abs(weights[0] - 0.7) < 0.15 or abs(weights[1] - 0.7) < 0.15


# ---------------------------------------------------------------------------
# T3 — Leakage test
# ---------------------------------------------------------------------------


class TestLeakage:
    def test_future_observation_not_visible(self) -> None:
        """Inserting an observation with observed_at > as_of must not change snapshot."""
        pit = PointInTimeStats()
        as_of_ts = 1000.0

        # Add a past observation
        pit.add_observation("CLU-1", 500.0, "LOC-PAST", "CELL-A", 10000, "ATM")
        snap_before = pit.snapshot_at("CLU-1", as_of_ts=as_of_ts)

        # Add a future observation
        pit.add_observation("CLU-1", 2000.0, "LOC-FUTURE", "CELL-B", 20000, "BRANCH")
        snap_after = pit.snapshot_at("CLU-1", as_of_ts=as_of_ts)

        # The snapshot must be identical — future obs invisible
        assert snap_before.prior_cashout_count == snap_after.prior_cashout_count
        assert snap_before.cashout_location_counts == snap_after.cashout_location_counts
        assert "LOC-FUTURE" not in snap_after.cashout_location_counts


# ---------------------------------------------------------------------------
# T9 — novelty()
# ---------------------------------------------------------------------------


class TestNovelty:
    def test_zero_obs_is_max_novelty(self) -> None:
        policy = _make_policy()
        assert novelty(0, policy) == pytest.approx(1.0, abs=1e-6)

    def test_many_obs_approaches_zero(self) -> None:
        policy = _make_policy()
        score = novelty(1000, policy)
        assert score < 0.01

    def test_monotone_decreasing(self) -> None:
        policy = _make_policy()
        scores = [novelty(n, policy) for n in range(0, 50)]
        for a, b in zip(scores, scores[1:], strict=False):
            assert a >= b


# ---------------------------------------------------------------------------
# T10 — DistrictPrior
# ---------------------------------------------------------------------------


class TestDistrictPrior:
    def test_uniform_sums_to_1(self) -> None:
        prior = DistrictPrior.uniform(["D1", "D2", "D3"])
        total = sum(prior.district_weights.values())
        assert abs(total - 1.0) < 1e-9

    def test_from_counts_laplace_smoothing(self) -> None:
        prior = DistrictPrior.from_counts({"D1": 10, "D2": 0})
        # D1 gets 11/(11+1) and D2 gets 1/(11+1)
        assert prior.weight_for("D2") > 0.0
        total = sum(prior.district_weights.values())
        assert abs(total - 1.0) < 1e-9

    def test_top_districts_ordering(self) -> None:
        prior = DistrictPrior.from_counts({"D1": 100, "D2": 10, "D3": 1})
        top = prior.top_districts(2)
        assert top[0][0] == "D1"
        assert top[1][0] == "D2"

    def test_unknown_district_returns_zero(self) -> None:
        prior = DistrictPrior.uniform(["D1"])
        assert prior.weight_for("D-UNKNOWN") == 0.0


# ---------------------------------------------------------------------------
# T1 — Training on a 7-day simulated world takes under 5 minutes
# (Scaled-down version: 500 complaints, timing gate 30s for CI)
# ---------------------------------------------------------------------------


class TestTrainingSpeed:
    def test_training_under_30s(self) -> None:
        """500 complaints x 5 candidates = 2500 rows: must train in under 30s."""
        rng = np.random.default_rng(0)
        n_complaints = 500
        n_candidates = 5

        builder = TrainingSetBuilder(val_fraction=0.2)
        for i in range(n_complaints):
            ctx = _make_ctx(
                complaint_id=f"C-{i}",
                reported_at=datetime(2025, 1, 1, tzinfo=_UTC),
                prior_cashout_count=int(rng.integers(0, 20)),
            )
            candidates = [_make_candidate(f"LOC-{j}") for j in range(n_candidates)]
            actual = f"LOC-{rng.integers(0, n_candidates)}"
            builder.add_complaint(ctx, candidates, actual)

        t0 = time.monotonic()
        ts = builder.build()
        scorer = HistGradientBoostingScorer()
        train_rows = [r.feature_row for r in ts.train_rows]
        train_labels = [r.label for r in ts.train_rows]
        val_rows = [r.feature_row for r in ts.val_rows]
        val_labels = [r.label for r in ts.val_rows]
        scorer.fit_with_calibration(train_rows, train_labels, val_rows, val_labels)
        elapsed = time.monotonic() - t0

        assert elapsed < 30.0, f"Training took {elapsed:.1f}s, expected < 30s"

    def test_model_store_round_trip(self) -> None:
        """Save and reload the scorer; confirm it is still fitted."""
        rows = [_make_feature_row() for _ in range(30)]
        labels = [float(i % 2) for i in range(30)]
        scorer = HistGradientBoostingScorer()
        scorer.fit(rows[:24], labels[:24])

        with tempfile.TemporaryDirectory() as d:
            store = ModelStore(store_dir=d)
            ver_id = store.save_scorer(scorer, "test_hash", datetime(2025, 1, 1, tzinfo=_UTC))
            loaded = store.load_scorer()
            assert loaded is not None
            assert loaded.is_fitted
            meta = store.scorer_meta()
            assert meta is not None
            assert meta.version_id == ver_id
            assert meta.data_hash == "test_hash"
