"""train.py — TrainModels use case (DOC 3 M2 B6).

TrainModels.run(as_of_end):
  1. Fetches all complaint contexts and observed cash-out locations up to as_of_end.
  2. Builds a time-ordered TrainingSet via TrainingSetBuilder (leakage-free).
  3. Fits HistGradientBoostingScorer (train slice) + isotonic calibration (val slice).
  4. Fits MixtureTimingModel on observed delay distributions.
  5. Persists both models via ModelStore.
  6. Returns ModelVersionIds (scorer_id, timing_id).

This use case reads data through injected port interfaces (no direct DB imports).
Training on a 7-day world should take well under 5 minutes at simulator scale.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from nakabandi.forecast.application.ports import ModelStorePort
from nakabandi.forecast.domain.scorers import HistGradientBoostingScorer
from nakabandi.forecast.domain.timing import MixtureTimingModel
from nakabandi.forecast.domain.training import TrainingSetBuilder
from nakabandi.forecast.domain.types import Candidate, ClusterContext
from nakabandi.shared import Policy, SimTime

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelVersionIds:
    """IDs of the persisted model versions produced by TrainModels."""

    scorer_id: str
    timing_id: str
    training_rows: int
    val_rows: int
    elapsed_s: float


class TrainingDataPort:
    """Abstract port — overridden in infrastructure by the real SQL implementation.

    The real implementation fetches:
      complaint_records() -> list of (ClusterContext, list[Candidate], actual_location_id)
      delay_records()     -> list of (delay_min: float, cluster_type: str)

    We define the interface here so TrainModels is pure application logic.
    """

    def complaint_records(
        self, as_of_end: SimTime
    ) -> list[tuple[ClusterContext, list[Candidate], str]]:
        """Return (ctx, candidates, actual_location_id) for every complaint up to as_of_end."""
        raise NotImplementedError

    def delay_records(self, as_of_end: SimTime) -> list[float]:
        """Return observed cash-out delay in minutes for every complaint up to as_of_end."""
        raise NotImplementedError


class TrainModels:
    """Orchestrate Forecast v1 training.

    No I/O inside domain functions; all data is fetched via TrainingDataPort
    before calling the scorers and timing domain functions.
    """

    def __init__(
        self,
        data_port: TrainingDataPort,
        model_store: ModelStorePort,
        policy: Policy,
        val_fraction: float = 0.2,
    ) -> None:
        self._data = data_port
        self._store = model_store
        self._policy = policy
        self._val_fraction = val_fraction

    def run(self, as_of_end: SimTime) -> ModelVersionIds:
        """Train scorer + timing model, persist both, return version IDs."""
        t0 = time.monotonic()
        logger.info("train_models.start as_of_end=%s", as_of_end.isoformat())

        # 1. Fetch training data
        complaint_records = self._data.complaint_records(as_of_end)
        delay_records = self._data.delay_records(as_of_end)

        logger.info(
            "train_models.data_fetched complaints=%d delays=%d",
            len(complaint_records),
            len(delay_records),
        )

        # 2. Build time-ordered TrainingSet
        builder = TrainingSetBuilder(val_fraction=self._val_fraction)
        for ctx, candidates, actual_loc in complaint_records:
            builder.add_complaint(ctx, candidates, actual_loc)
        training_set = builder.build()

        n_train = len(training_set.train_rows)
        n_val = len(training_set.val_rows)
        logger.info("train_models.split train=%d val=%d", n_train, n_val)

        # 3. Fit scorer
        scorer = HistGradientBoostingScorer()
        train_feat = [r.feature_row for r in training_set.train_rows]
        train_labels = [r.label for r in training_set.train_rows]
        val_feat = [r.feature_row for r in training_set.val_rows]
        val_labels = [r.label for r in training_set.val_rows]

        cal_result = scorer.fit_with_calibration(train_feat, train_labels, val_feat, val_labels)
        logger.info(
            "train_models.scorer_fitted brier_before=%.4f brier_after=%.4f",
            cal_result.brier_before,
            cal_result.brier_after,
        )

        # 4. Fit timing model (uses delay_records; EM already implemented in MixtureTimingModel)
        timing_model: MixtureTimingModel
        n_min = self._policy.forecast.timing.n_min
        if len(delay_records) >= n_min:
            timing_model = MixtureTimingModel.fit(delay_records, self._policy)
            logger.info("train_models.timing_fitted n_delays=%d", len(delay_records))
        else:
            timing_model = MixtureTimingModel(policy=self._policy, n_obs=len(delay_records))
            logger.warning(
                "train_models.timing_insufficient n=%d min=%d — using global prior",
                len(delay_records),
                n_min,
            )

        # 5. Persist models
        scorer_id = self._store.save_scorer(
            scorer,
            training_set.data_hash,
            as_of_end,
            brier_before=cal_result.brier_before,
            brier_after=cal_result.brier_after,
        )
        timing_id = self._store.save_timing(timing_model, training_set.data_hash, as_of_end)

        elapsed = time.monotonic() - t0
        logger.info(
            "train_models.done scorer_id=%s timing_id=%s elapsed_s=%.2f",
            scorer_id,
            timing_id,
            elapsed,
        )

        return ModelVersionIds(
            scorer_id=scorer_id,
            timing_id=timing_id,
            training_rows=n_train,
            val_rows=n_val,
            elapsed_s=elapsed,
        )
