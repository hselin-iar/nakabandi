"""Public facade of the forecast module (DOC 3 M2, LC-4).

Exports:
  Forecaster              — generate(ctx, ..., as_of) -> Forecast
  Trainer                 — train(as_of_end) -> ModelVersionIds  (B6)
  ClusterContext          — data passed in by the pipeline
  Forecast                — the LC-4 result shape
  TimingForecast          — timing sub-object (shared with interception)
  LocationScorer          — port (evaluation baselines implement this)
  TimingModel             — port (evaluation baselines implement this)
  HeuristicScorer         — v0 scorer (fallback)
  HistGradientBoostingScorer — v1 scorer (B6)
  MixtureTimingModel      — timing model
  ModelStore              — joblib persistence (B6)
"""

from __future__ import annotations

from nakabandi.forecast.application.ports import ForecastRepo, ModelStorePort
from nakabandi.forecast.application.train import ModelVersionIds, TrainingDataPort, TrainModels
from nakabandi.forecast.application.use_cases import GenerateForecast
from nakabandi.forecast.domain.candidates import LocationInfo
from nakabandi.forecast.domain.features import BLOCKLIST, FEATURE_REGISTRY
from nakabandi.forecast.domain.global_stats import GlobalCashoutIndex
from nakabandi.forecast.domain.scorers import (
    HeuristicScorer,
    HistGradientBoostingScorer,
    LocationScorer,
)
from nakabandi.forecast.domain.timing import MixtureTimingModel, TimingModel
from nakabandi.forecast.domain.types import (
    ClusterContext,
    EvidenceStatement,
    Forecast,
    LevelForecast,
    TimingForecast,
)
from nakabandi.forecast.infrastructure.model_store import ModelStore
from nakabandi.shared import Id, Policy, SimTime

__all__ = [
    "Forecaster",
    "Trainer",
    "ClusterContext",
    "Forecast",
    "LevelForecast",
    "TimingForecast",
    "EvidenceStatement",
    "LocationInfo",
    "LocationScorer",
    "TimingModel",
    "HeuristicScorer",
    "HistGradientBoostingScorer",
    "MixtureTimingModel",
    "ModelStore",
    "ModelStorePort",
    "ModelVersionIds",
    "TrainModels",
    "TrainingDataPort",
    "FEATURE_REGISTRY",
    "GlobalCashoutIndex",
    "BLOCKLIST",
]


class Forecaster:
    """Façade: the ONLY forecast object other modules may import.

    Instantiate once at startup with repo and policy dependencies.
    Scorer and timing model are injectable (evaluation uses custom scorers).
    In B6+, pass model_store so the HGB scorer is loaded at startup.
    """

    def __init__(
        self,
        forecast_repo: ForecastRepo,
        policy: Policy,
        scorer: LocationScorer | None = None,
        timing_model: TimingModel | None = None,
        model_store: ModelStorePort | None = None,
    ) -> None:
        self._uc = GenerateForecast(
            forecast_repo=forecast_repo,
            policy=policy,
            scorer=scorer,
            timing_model=timing_model,
            model_store=model_store,
        )

    def generate(
        self,
        ctx: ClusterContext,
        all_locations: list[LocationInfo],
        home_district_id: Id,
        delays_min: list[float],
        as_of: SimTime,
    ) -> Forecast:
        """Generate and persist a Forecast for one complaint.

        Called by pipeline.ProcessComplaint only.
        """
        return self._uc.run(
            ctx=ctx,
            all_locations=all_locations,
            home_district_id=home_district_id,
            delays_min=delays_min,
            as_of=as_of,
        )


class Trainer:
    """Façade: trains and persists scorer + timing model (B6).

    Called by a scheduled job or the /train endpoint (Track A wires this up).
    data_port must be the real SQL implementation from infrastructure.
    """

    def __init__(
        self,
        data_port: TrainingDataPort,
        model_store: ModelStorePort,
        policy: Policy,
        val_fraction: float = 0.2,
    ) -> None:
        self._uc = TrainModels(
            data_port=data_port,
            model_store=model_store,
            policy=policy,
            val_fraction=val_fraction,
        )

    def train(self, as_of_end: SimTime) -> ModelVersionIds:
        """Train scorer + timing model and persist. Called by the scheduler."""
        return self._uc.run(as_of_end)
