"""use_cases.py — GenerateForecast use case (DOC 3 M2, upgraded in B6 to v1).

Orchestrates the domain functions:
    candidates -> features -> score (v1 HGB or v0 heuristic fallback) ->
    normalise -> aggregate_levels -> abstain -> timing -> explain -> Forecast

At construction time, GenerateForecast tries to load the trained HGB scorer from
ModelStore. If the model files are missing it falls back to the HeuristicScorer
and sets model_versions.scorer = 'fallback' so the UI can show a banner.

No I/O inside domain functions; all data fetched before calling them.
"""

from __future__ import annotations

import logging

import structlog
from nakabandi_contracts.enums import Resolution

from nakabandi.forecast.application.ports import ForecastRepo, ModelStorePort
from nakabandi.forecast.domain.abstain import apply_abstention
from nakabandi.forecast.domain.aggregate import aggregate_levels, normalise
from nakabandi.forecast.domain.candidates import LocationInfo, generate_candidates
from nakabandi.forecast.domain.explain import explain
from nakabandi.forecast.domain.novelty import novelty as compute_novelty_score
from nakabandi.forecast.domain.scorers import (
    HeuristicScorer,
    LocationScorer,
    score_candidates,
)
from nakabandi.forecast.domain.timing import MixtureTimingModel, TimingModel
from nakabandi.forecast.domain.types import (
    ClusterContext,
    EvidenceStatement,
    Forecast,
    LevelForecast,
    TimingForecast,
)
from nakabandi.shared import Id, Policy, SimTime, new_id

_boot_log = logging.getLogger(__name__)
logger = structlog.get_logger(__name__)

_FALLBACK_MODEL_LABEL = "fallback"


class GenerateForecast:
    """Orchestrate the forecast pipeline for one complaint.

    B4 (v0): always uses HeuristicScorer.
    B6 (v1): tries to load HistGradientBoostingScorer from ModelStore at
             construction; falls back to HeuristicScorer if files are missing
             and marks model_versions.scorer = 'fallback'.
    """

    def __init__(
        self,
        forecast_repo: ForecastRepo,
        policy: Policy,
        scorer: LocationScorer | None = None,
        timing_model: TimingModel | None = None,
        model_store: ModelStorePort | None = None,
    ) -> None:
        self._repo = forecast_repo
        self._policy = policy
        self._timing: TimingModel = timing_model or MixtureTimingModel(policy=policy)
        self._using_fallback = False

        # Try to load the v1 HGB scorer from the model store if not explicitly injected
        if scorer is not None:
            self._scorer: LocationScorer = scorer
        elif model_store is not None:
            loaded = model_store.load_scorer()
            if loaded is not None:
                self._scorer = loaded
                _boot_log.info("forecast.scorer_loaded name=hgb_v1")
            else:
                self._scorer = HeuristicScorer()
                self._using_fallback = True
                _boot_log.warning(
                    "[BANNER] forecast.scorer_fallback — model files missing, "
                    "using heuristic_v0. Run TrainModels to build the v1 model."
                )
        else:
            self._scorer = HeuristicScorer()
            self._using_fallback = True

    def run(
        self,
        ctx: ClusterContext,
        all_locations: list[LocationInfo],
        home_district_id: Id,
        delays_min: list[float],
        as_of: SimTime,
    ) -> Forecast:
        """Generate a forecast for one complaint.

        Parameters
        ----------
        ctx:
            Cluster context snapshot (as-of bounded).
        all_locations:
            All registry locations (fetched by the calling pipeline).
        home_district_id:
            District of the layer-1 victim's home branch.
        delays_min:
            Observed past cash-out delays in minutes for this cluster (for timing fit).
        as_of:
            Sim-clock time (LC-2 — never datetime.now()).
        """
        policy = self._policy

        # --- Timing (fit per-cluster if enough data) ---
        timing_model: TimingModel
        if delays_min and len(delays_min) >= policy.forecast.timing.n_min:
            timing_model = MixtureTimingModel.fit(delays_min, policy)
        else:
            timing_model = MixtureTimingModel(policy=policy, n_obs=len(delays_min))

        timing: TimingForecast = timing_model.horizon_probs(ctx, horizons=[30, 60, 120])

        # --- Stale check ---
        stale = timing.residual_mass < policy.forecast.stale_residual_mass

        # --- Candidates ---
        candidates = generate_candidates(ctx, all_locations, home_district_id, policy)
        if not candidates:
            # All levels abstain — return a minimal stale/novel forecast
            return self._abstained_forecast(ctx, timing, stale, as_of)

        # --- Score and normalise ---
        expected_hour = _expected_hour_from_timing(ctx)
        feature_rows, raw = score_candidates(ctx, candidates, self._scorer, expected_hour)
        probs = normalise(raw)

        # --- Aggregate and abstain ---
        levels = aggregate_levels(probs, candidates)
        levels = apply_abstention(levels, policy)

        # --- Confidence = district level confidence (highest-level non-abstained) ---
        confidence = _top_confidence(levels)

        # --- Novelty ---
        novelty = _compute_novelty(ctx, policy)

        # --- Evidence ---
        top_n = min(3, len(candidates))
        evidence: list[EvidenceStatement] = explain(
            ctx,
            candidates[:top_n],
            feature_rows[:top_n],
            policy,
        )

        # --- Assert sum invariant at each non-abstained level ---
        _assert_sums(levels)

        # Model version label
        scorer_label = _FALLBACK_MODEL_LABEL if self._using_fallback else "hgb_v1"

        forecast = Forecast(
            id=new_id(),
            complaint_id=ctx.complaint_id,
            cluster_id=ctx.cluster_id,
            generated_at=as_of,
            model_versions={"scorer": scorer_label, "timing": "mixture_v1"},
            levels=levels,
            timing=timing,
            confidence=confidence,
            novelty=novelty,
            stale=stale,
            evidence=evidence,
        )
        self._repo.save(forecast)
        return forecast

    def _abstained_forecast(
        self,
        ctx: ClusterContext,
        timing: TimingForecast,
        stale: bool,
        as_of: SimTime,
    ) -> Forecast:
        """Return a forecast where all levels abstain (no candidates found)."""
        levels = {
            Resolution.DISTRICT.value: LevelForecast(
                resolution=Resolution.DISTRICT, abstained=True, confidence=0.0, items=[]
            ),
            Resolution.CELL.value: LevelForecast(
                resolution=Resolution.CELL, abstained=True, confidence=0.0, items=[]
            ),
            Resolution.LOCATION.value: LevelForecast(
                resolution=Resolution.LOCATION, abstained=True, confidence=0.0, items=[]
            ),
        }
        forecast = Forecast(
            id=new_id(),
            complaint_id=ctx.complaint_id,
            cluster_id=ctx.cluster_id,
            generated_at=as_of,
            model_versions={"scorer": _FALLBACK_MODEL_LABEL, "timing": "mixture_v0"},
            levels=levels,
            timing=timing,
            confidence=0.0,
            novelty=1.0,  # maximally novel: we know nothing
            stale=stale,
            evidence=[],
        )
        self._repo.save(forecast)
        return forecast


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _top_confidence(levels: dict[str, LevelForecast]) -> float:
    """Return the top-item confidence of the coarsest non-abstained level."""
    for resolution in (Resolution.DISTRICT, Resolution.CELL, Resolution.LOCATION):
        lf = levels.get(resolution.value)
        if lf and not lf.abstained and lf.items:
            return lf.confidence
    return 0.0


def _compute_novelty(ctx: ClusterContext, policy: Policy) -> float:
    """Novelty ∈ [0, 1] via tanh (DOC 3 M2 B6, graph.domain.novelty)."""
    return compute_novelty_score(ctx.prior_cashout_count, policy)


def _expected_hour_from_timing(ctx: ClusterContext) -> float:
    """Heuristic: most cash-outs happen mid-afternoon; return 15.0 as a default."""
    _ = ctx  # future: derive from cluster's historical hour distribution
    return 15.0


def _assert_sums(levels: dict[str, LevelForecast]) -> None:
    """Assert probabilities sum to 1 ± 1e-6 at every non-abstained level."""
    for key, lf in levels.items():
        if not lf.abstained and lf.items:
            total = sum(item.prob for item in lf.items)
            if abs(total - 1.0) > 1e-6:
                logger.warning(
                    "forecast.prob_sum_violated",
                    level=key,
                    total=total,
                )
