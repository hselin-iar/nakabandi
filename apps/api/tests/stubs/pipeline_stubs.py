"""Stub implementations of graph, forecast, interception and alerting facades.

These return canned deterministic outputs that satisfy the LC-4 shapes so the
pipeline can run end-to-end before the real modules are built (DOC 4 A6
STUB/MOCK STRATEGY).  Each stub is keyed on a deterministic input (complaint_id
or cluster_id) so the golden test can assert specific values.

SWAP ORDER: replace stubs one at a time and rerun the golden test after each swap.
  - graph stub → real ClusterService (Sync 3, after B2)
  - forecast stub → real Forecaster (Sync 3, after B3)
  - interception stub → real Interceptor (Sync 3, after B4)
  - alerting stub → real AlertService (Sync 3, after A7)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nakabandi.shared import Id, SimTime, new_id

# ---------------------------------------------------------------------------
# Shared canned LC-4 helpers
# ---------------------------------------------------------------------------


def _make_timing_forecast(now: SimTime) -> dict[str, Any]:
    """LC-4 TimingForecast shape — deterministic canned values."""
    return {
        "weights": [0.6, 0.4],
        "medians_min": [20.0, 90.0],
        "sigmas": [0.4, 0.6],
        "elapsed_min": 5.0,
        "residual_mass": 0.92,
        "p30": 0.45,
        "p60": 0.68,
        "p120": 0.85,
    }


def _make_level_forecast(resolution: str, items: list[dict]) -> dict[str, Any]:
    """LC-4 LevelForecast shape."""
    return {
        "resolution": resolution,
        "abstained": False,
        "confidence": 0.72,
        "items": items,
    }


# ---------------------------------------------------------------------------
# Graph stub
# ---------------------------------------------------------------------------


@dataclass
class StubClusterResolution:
    cluster_id: Id
    merged_from: list[Id] = field(default_factory=list)


@dataclass
class StubClusterContext:
    cluster_id: Id
    complaint_id: Id
    as_of: SimTime


class StubClusterService:
    """Stub for nakabandi.graph.ClusterService.

    resolve() groups complaints by their layer1_account_id prefix to produce
    deterministic clusters without a real union-find.
    context_for() returns a lightweight context object.
    """

    def __init__(self) -> None:
        self._account_to_cluster: dict[str, Id] = {}

    def resolve(self, accounts: list[str], as_of: SimTime) -> StubClusterResolution:
        # Use first account as cluster key; union by earliest account
        key = accounts[0] if accounts else "unknown"
        if key not in self._account_to_cluster:
            self._account_to_cluster[key] = new_id()
        return StubClusterResolution(cluster_id=self._account_to_cluster[key])

    def context_for(
        self,
        complaint_id: Id,
        cluster_id: Id,
        as_of: SimTime,
    ) -> StubClusterContext:
        return StubClusterContext(cluster_id=cluster_id, complaint_id=complaint_id, as_of=as_of)


# ---------------------------------------------------------------------------
# Forecast stub
# ---------------------------------------------------------------------------


@dataclass
class StubForecast:
    """LC-4 Forecast shape as a dataclass (pipeline reads .id, .confidence, .stale)."""

    id: Id
    complaint_id: Id
    cluster_id: Id | None
    generated_at: SimTime
    model_versions: dict[str, str]
    levels: dict[str, Any]
    timing: dict[str, Any]
    confidence: float
    novelty: float
    stale: bool
    evidence: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "complaint_id": self.complaint_id,
            "cluster_id": self.cluster_id,
            "generated_at": self.generated_at.isoformat(),
            "model_versions": self.model_versions,
            "levels": self.levels,
            "timing": self.timing,
            "confidence": self.confidence,
            "novelty": self.novelty,
            "stale": self.stale,
            "evidence": self.evidence,
        }


class StubForecaster:
    """Stub for nakabandi.forecast.Forecaster.

    generate() returns a non-stale forecast with canned LC-4 shape values.
    """

    def generate(
        self,
        ctx: StubClusterContext,
        as_of: SimTime,
    ) -> StubForecast:
        now = as_of
        return StubForecast(
            id=new_id(),
            complaint_id=ctx.complaint_id,
            cluster_id=ctx.cluster_id,
            generated_at=now,
            model_versions={"scorer": "stub-v0", "timing": "stub-v0"},
            levels={
                "district": _make_level_forecast(
                    "district",
                    [{"id": "d1", "prob": 0.72, "rank": 1}],
                ),
                "cell": _make_level_forecast(
                    "cell",
                    [{"id": "cell-1", "prob": 0.55, "rank": 1}],
                ),
                "location": _make_level_forecast(
                    "location",
                    [{"id": "loc-1", "prob": 0.41, "rank": 1}],
                ),
            },
            timing=_make_timing_forecast(now),
            confidence=0.72,
            novelty=0.12,
            stale=False,
            evidence=[
                {
                    "code": "CLUSTER_HISTORY",
                    "params": {"count": 3},
                    "text_en": "Cluster has 3 prior cash-outs in this cell.",
                }
            ],
        )


# ---------------------------------------------------------------------------
# Interception stub
# ---------------------------------------------------------------------------


@dataclass
class StubInterceptAssessment:
    """LC-4 InterceptAssessment shape."""

    id: Id
    forecast_id: Id
    target: dict[str, str]
    channel: str
    window_min: float
    best_unit: dict[str, Any] | None
    interception_probability: float
    verdict: str
    ladder_level: str
    reason_code: str
    reason_params: dict[str, Any]
    proportionality: dict[str, Any] | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "forecast_id": self.forecast_id,
            "target": self.target,
            "channel": self.channel,
            "window_min": self.window_min,
            "best_unit": self.best_unit,
            "interception_probability": self.interception_probability,
            "verdict": self.verdict,
            "ladder_level": self.ladder_level,
            "reason_code": self.reason_code,
            "reason_params": self.reason_params,
            "proportionality": self.proportionality,
        }


class StubInterceptor:
    """Stub for nakabandi.interception.Interceptor.assess().

    Returns one MARGINAL assessment with a canned L2 ladder level.
    """

    def assess(
        self,
        forecast: StubForecast,
        complaint_id: Id,
        now: SimTime,
    ) -> list[StubInterceptAssessment]:
        return [
            StubInterceptAssessment(
                id=new_id(),
                forecast_id=forecast.id,
                target={"kind": "location", "id": "loc-1"},
                channel="ATM",
                window_min=30.0,
                best_unit={"id": "unit-1", "kind": "cyber_cell", "eta_min": 12.0},
                interception_probability=0.55,
                verdict="MARGINAL",
                ladder_level="L2",
                reason_code="MARGINAL_PROBABILITY",
                reason_params={"p": 0.55},
                proportionality=None,
            )
        ]


# ---------------------------------------------------------------------------
# Alerting stub
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
        forecast: StubForecast,
        assessments: list[StubInterceptAssessment],
    ) -> StubAlertResult:
        result = StubAlertResult(
            alert_id=new_id(),
            action="raised",
            complaint_id=forecast.complaint_id,
        )
        self.raised.append(result)
        return result
