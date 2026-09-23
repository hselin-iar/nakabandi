"""Implementations of graph, forecast, interception and alerting facades for pipeline testing.

SWAPPED AT SYNC 3 (DOC 4 §4.1a, §4.1b MP3):
  - graph: real ClusterIndex (Track B Step B2)
  - forecast: real Forecast / LevelForecast / TimingForecast / EvidenceStatement (Track B Step B4)
  - interception: real InterceptAssessment / TargetRef / BestUnit / ladder_level / verdict_from
    (Track B Step B3)
  - alerting: StubAlertService (Track A Step A7 builds real AlertService)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nakabandi.forecast.domain.types import (
    EvidenceStatement,
    Forecast,
    LevelForecast,
    RankedItem,
    TimingForecast,
)
from nakabandi.graph.domain.cluster_index import ClusterIndex
from nakabandi.graph.domain.types import ClusterResolution
from nakabandi.interception.domain.ladder import ladder_level
from nakabandi.interception.domain.types import (
    BestUnit,
    InterceptAssessment,
    TargetRef,
)
from nakabandi.interception.domain.verdict import verdict_from
from nakabandi.shared import Id, Policy, SimTime, new_id
from nakabandi_contracts.enums import Channel, Resolution

# ---------------------------------------------------------------------------
# Policy loader
# ---------------------------------------------------------------------------


def _load_policy() -> Policy:
    p = Path(__file__).resolve().parents[4] / "config" / "policy.yaml"
    if not p.exists():
        p = Path("config/policy.yaml")
    return Policy.load(p)


# ---------------------------------------------------------------------------
# Shared canned LC-4 helpers
# ---------------------------------------------------------------------------


def _make_timing_forecast(now: SimTime) -> TimingForecast:
    """LC-4 TimingForecast shape using real forecast domain type."""
    return TimingForecast(
        weights=[0.6, 0.4],
        medians_min=[20.0, 90.0],
        sigmas=[0.4, 0.6],
        elapsed_min=5.0,
        residual_mass=0.92,
        p30=0.45,
        p60=0.68,
        p120=0.85,
    )


# ---------------------------------------------------------------------------
# Graph: real ClusterIndex (Track B Step B2)
# ---------------------------------------------------------------------------


@dataclass
class StubClusterContext:
    cluster_id: Id
    complaint_id: Id
    as_of: SimTime


class StubClusterService:
    """Cluster service for pipeline testing.

    Backed by real ClusterIndex (Track B Step B2) to resolve accounts into clusters.
    """

    def __init__(self, index: ClusterIndex | None = None) -> None:
        self._index = index or ClusterIndex({})

    def resolve(self, accounts: list[str], as_of: SimTime) -> ClusterResolution:
        return self._index.resolve(accounts)

    def context_for(
        self,
        complaint_id: Id,
        cluster_id: Id,
        as_of: SimTime,
    ) -> StubClusterContext:
        return StubClusterContext(cluster_id=cluster_id, complaint_id=complaint_id, as_of=as_of)


# ---------------------------------------------------------------------------
# Forecast: real Forecast domain types (Track B Step B4)
# ---------------------------------------------------------------------------


class StubForecaster:
    """Forecaster producing real LC-4 Forecast domain objects (Track B Step B4)."""

    def generate(
        self,
        ctx: StubClusterContext,
        as_of: SimTime,
    ) -> Forecast:
        now = as_of
        levels = {
            Resolution.DISTRICT.value: LevelForecast(
                resolution=Resolution.DISTRICT,
                abstained=False,
                confidence=0.72,
                items=[RankedItem(id="d1", prob=0.72, rank=1)],
            ),
            Resolution.CELL.value: LevelForecast(
                resolution=Resolution.CELL,
                abstained=False,
                confidence=0.55,
                items=[RankedItem(id="cell-1", prob=0.55, rank=1)],
            ),
            Resolution.LOCATION.value: LevelForecast(
                resolution=Resolution.LOCATION,
                abstained=False,
                confidence=0.41,
                items=[RankedItem(id="loc-1", prob=0.41, rank=1)],
            ),
        }
        return Forecast(
            id=new_id(),
            complaint_id=ctx.complaint_id,
            cluster_id=ctx.cluster_id,
            generated_at=now,
            model_versions={"scorer": "heuristic-v0", "timing": "mixture-v0"},
            levels=levels,
            timing=_make_timing_forecast(now),
            confidence=0.72,
            novelty=0.12,
            stale=False,
            evidence=[
                EvidenceStatement(
                    code="CLUSTER_HISTORY",
                    params={"count": "3"},
                    text_en="Cluster has 3 prior cash-outs in this cell.",
                )
            ],
        )


# ---------------------------------------------------------------------------
# Interception: real InterceptAssessment domain types & rules (Track B Step B3)
# ---------------------------------------------------------------------------


class StubInterceptor:
    """Interceptor producing real LC-4 InterceptAssessment domain objects (Track B Step B3)."""

    def __init__(self, policy: Policy | None = None) -> None:
        self._policy = policy or _load_policy()

    def assess(
        self,
        forecast: Forecast,
        complaint_id: Id,
        now: SimTime,
    ) -> list[InterceptAssessment]:
        verdict = verdict_from(
            p=0.55,
            policy=self._policy,
        )
        level = ladder_level(
            channel=Channel.ATM.value,
            verdict=verdict,
            confidence=forecast.confidence,
            policy=self._policy,
        )
        return [
            InterceptAssessment(
                id=new_id(),
                forecast_id=forecast.id,
                target=TargetRef(kind="location", id="loc-1"),
                channel=Channel.ATM.value,
                window_min=30.0,
                best_unit=BestUnit(unit_id="unit-1", unit_kind="cyber_cell", eta_min=12.0),
                interception_probability=0.55,
                verdict=verdict,
                ladder_level=level,
                reason_code="MARGINAL_PROBABILITY",
                reason_params={"p": "0.55"},
                proportionality=None,
            )
        ]


# ---------------------------------------------------------------------------
# Alerting stub (remains stub until Step A7)
# ---------------------------------------------------------------------------


@dataclass
class StubAlertResult:
    """Returned by StubAlertService.raise_or_merge."""

    alert_id: Id
    action: str  # "raised" | "merged"
    complaint_id: Id


class StubAlertService:
    """Stub for nakabandi.alerting.AlertService.raise_or_merge().

    Raises a new alert for every forecast and tracks the raised alert_ids so
    the golden test can assert on them.
    """

    def __init__(self) -> None:
        self.raised: list[StubAlertResult] = []

    def raise_or_merge(
        self,
        forecast: Forecast,
        assessments: list[InterceptAssessment],
    ) -> StubAlertResult:
        result = StubAlertResult(
            alert_id=new_id(),
            action="raised",
            complaint_id=forecast.complaint_id,
        )
        self.raised.append(result)
        return result
