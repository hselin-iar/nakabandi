"""Public facade of the forecast module (DOC 3 M2, LC-4).

Exports:
  Forecaster          — generate(ctx, all_locations, home_district_id,
                          delays_min, as_of) -> Forecast
  ClusterContext      — data passed in by the pipeline
  Forecast            — the LC-4 result shape
  TimingForecast      — timing sub-object (shared with interception)
  LocationScorer      — port (evaluation baselines implement this)
  TimingModel         — port (evaluation baselines implement this)
  HeuristicScorer     — v0 scorer
  MixtureTimingModel  — v0 timing model
"""

from __future__ import annotations

from nakabandi.forecast.application.ports import ForecastRepo
from nakabandi.forecast.application.use_cases import GenerateForecast
from nakabandi.forecast.domain.candidates import LocationInfo
from nakabandi.forecast.domain.features import BLOCKLIST, FEATURE_REGISTRY
from nakabandi.forecast.domain.scorers import HeuristicScorer, LocationScorer
from nakabandi.forecast.domain.timing import MixtureTimingModel, TimingModel
from nakabandi.forecast.domain.types import (
    ClusterContext,
    EvidenceStatement,
    Forecast,
    LevelForecast,
    TimingForecast,
)
from nakabandi.shared import Id, Policy, SimTime

__all__ = [
    "Forecaster",
    "ClusterContext",
    "Forecast",
    "LevelForecast",
    "TimingForecast",
    "EvidenceStatement",
    "LocationInfo",
    "LocationScorer",
    "TimingModel",
    "HeuristicScorer",
    "MixtureTimingModel",
    "FEATURE_REGISTRY",
    "BLOCKLIST",
]


class Forecaster:
    """Façade: the ONLY forecast object other modules may import.

    Instantiate once at startup with repo and policy dependencies.
    Scorer and timing model are injectable (evaluation uses custom scorers).
    """

    def __init__(
        self,
        forecast_repo: ForecastRepo,
        policy: Policy,
        scorer: LocationScorer | None = None,
        timing_model: TimingModel | None = None,
    ) -> None:
        self._uc = GenerateForecast(
            forecast_repo=forecast_repo,
            policy=policy,
            scorer=scorer,
            timing_model=timing_model,
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
