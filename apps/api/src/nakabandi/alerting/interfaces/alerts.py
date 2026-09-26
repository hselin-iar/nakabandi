"""GET /alerts, GET /alerts/{id}, POST /alerts/{id}/acknowledge (DOC 3 M4, LC-4).

All endpoints require authentication (get_principal).
GET /alerts respects scope (filtered by principal's scope).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from nakabandi.access import Principal, get_principal
from nakabandi.alerting.domain.action import Action
from nakabandi.alerting.domain.alert import Alert
from nakabandi.alerting.domain.delivery import Delivery
from nakabandi.alerting.domain.outcome import Outcome
from nakabandi.alerting.interfaces.actions import ActionModel, action_view
from nakabandi.alerting.interfaces.deps import build_service, get_uow
from nakabandi.alerting.interfaces.outcomes import OutcomeView, outcome_view

router = APIRouter(prefix="/alerts", tags=["alerts"])


# ---------------------------------------------------------------------------
# Response models (LC-4 AlertSummary / AlertDetail)
# ---------------------------------------------------------------------------


class AlertSummaryModel(BaseModel):
    id: str
    cluster_ref: str
    target: dict  # {kind, id, name}
    severity: str
    confidence: float
    status: str
    is_deferred: bool
    is_probe: bool
    window_start: str
    window_end: str
    expires_at: str
    ladder_level: str
    created_at: str
    masked: bool


class TimelineEntryModel(BaseModel):
    at: str
    kind: str
    actor_id: str | None
    text_code: str
    text_params: dict


class DeliveryModel(BaseModel):
    """LC-4 AlertDetail.deliveries: { channel, status, attempts, sent_at?, rendered_body? }."""

    channel: str
    status: str
    attempts: int
    sent_at: str | None
    rendered_body: str | None


class RankedItemModel(BaseModel):
    id: str
    prob: float
    rank: int


class LevelForecastModel(BaseModel):
    resolution: str
    abstained: bool
    confidence: float
    items: list[RankedItemModel]


class TimingForecastModel(BaseModel):
    weights: list[float]
    medians_min: list[float]
    sigmas: list[float]
    elapsed_min: float
    residual_mass: float
    p30: float
    p60: float
    p120: float


class EvidenceModel(BaseModel):
    code: str
    params: dict[str, str]
    text_en: str


class ForecastModel(BaseModel):
    """LC-4 Forecast."""

    id: str
    complaint_id: str
    cluster_id: str | None
    generated_at: str
    model_versions: dict[str, str]
    levels: dict[str, LevelForecastModel]
    timing: TimingForecastModel
    confidence: float
    novelty: float
    stale: bool
    evidence: list[EvidenceModel]


class BestUnitModel(BaseModel):
    unit_id: str
    unit_kind: str
    eta_min: float
    lat: float
    lon: float


class ProportionalityModel(BaseModel):
    disputed_paise: int
    proposed_paise: int
    ratio: float
    expires_at: str
    review_at: str
    magistrate_report_reminder: bool
    complaint_ref: str


class InterceptAssessmentModel(BaseModel):
    """LC-4 InterceptAssessment."""

    id: str
    forecast_id: str
    target: dict[str, str]
    channel: str
    window_min: float
    best_unit: BestUnitModel | None
    interception_probability: float
    verdict: str
    ladder_level: str
    reason_code: str
    reason_params: dict[str, str]
    proportionality: ProportionalityModel | None


def _forecast_view(f) -> ForecastModel:  # noqa: ANN001
    return ForecastModel(
        id=f.id,
        complaint_id=f.complaint_id,
        cluster_id=f.cluster_id,
        generated_at=f.generated_at.isoformat(),
        model_versions=dict(f.model_versions),
        levels={
            key: LevelForecastModel(
                resolution=str(lv.resolution.value),
                abstained=lv.abstained,
                confidence=lv.confidence,
                items=[RankedItemModel(id=i.id, prob=i.prob, rank=i.rank) for i in lv.items],
            )
            for key, lv in f.levels.items()
        },
        timing=TimingForecastModel(
            weights=list(f.timing.weights),
            medians_min=list(f.timing.medians_min),
            sigmas=list(f.timing.sigmas),
            elapsed_min=f.timing.elapsed_min,
            residual_mass=f.timing.residual_mass,
            p30=f.timing.p30,
            p60=f.timing.p60,
            p120=f.timing.p120,
        ),
        confidence=f.confidence,
        novelty=f.novelty,
        stale=f.stale,
        evidence=[
            EvidenceModel(code=e.code, params=dict(e.params), text_en=e.text_en) for e in f.evidence
        ],
    )


def _assessment_view(a) -> InterceptAssessmentModel:  # noqa: ANN001
    p = a.proportionality
    return InterceptAssessmentModel(
        id=a.id,
        forecast_id=a.forecast_id,
        target={"kind": a.target.kind, "id": a.target.id},
        channel=a.channel,
        window_min=a.window_min,
        best_unit=(
            BestUnitModel(
                unit_id=a.best_unit.unit_id,
                unit_kind=a.best_unit.unit_kind,
                eta_min=a.best_unit.eta_min,
                lat=a.best_unit.lat,
                lon=a.best_unit.lon,
            )
            if a.best_unit
            else None
        ),
        interception_probability=a.interception_probability,
        verdict=str(a.verdict.value),
        ladder_level=str(a.ladder_level.value),
        reason_code=a.reason_code,
        reason_params=dict(a.reason_params),
        proportionality=(
            ProportionalityModel(
                disputed_paise=p.disputed_paise,
                proposed_paise=p.proposed_paise,
                ratio=p.ratio,
                expires_at=p.expires_at.isoformat(),
                review_at=p.review_at.isoformat(),
                magistrate_report_reminder=p.magistrate_report_reminder,
                complaint_ref=p.complaint_ref,
            )
            if p
            else None
        ),
    )


class AlertDetailModel(AlertSummaryModel):
    forecast: ForecastModel | None  # the forecast that last fed this alert (LC-4)
    interception: list[InterceptAssessmentModel]
    timeline: list[TimelineEntryModel]
    deliveries: list[DeliveryModel]
    actions: list[ActionModel]
    outcomes: list[OutcomeView]  # officer and reconciled rows; the alert shows both (DOC 3 S3)
    allowed_actions: list[str]


class PageModel(BaseModel):
    items: list[AlertSummaryModel]
    next_cursor: str | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _summary(alert: Alert) -> AlertSummaryModel:
    return AlertSummaryModel(
        id=alert.id,
        cluster_ref=alert.cluster_ref,
        target={"kind": alert.target_kind, "id": alert.target_id, "name": alert.target_name},
        severity=alert.severity.value,
        confidence=alert.confidence,
        status=alert.status.value,
        is_deferred=alert.is_deferred,
        is_probe=alert.is_probe,
        window_start=alert.window_start.isoformat(),
        window_end=alert.window_end.isoformat(),
        expires_at=alert.expires_at.isoformat(),
        ladder_level=alert.ladder_level.value,
        created_at=alert.created_at.isoformat(),
        masked=alert.masked,
    )


def _detail(
    alert: Alert,
    deliveries: list[Delivery],
    actions: list[Action],
    outcomes: list[Outcome],
    allowed_actions: list[str],
    forecast: object | None = None,
    assessments: list[object] | None = None,
) -> AlertDetailModel:
    tl = [
        TimelineEntryModel(
            at=e.at.isoformat(),
            kind=e.kind,
            actor_id=e.actor_id,
            text_code=e.text_code,
            text_params=e.text_params,
        )
        for e in alert.timeline
    ]
    s = _summary(alert)
    return AlertDetailModel(
        **s.model_dump(),
        forecast=_forecast_view(forecast) if forecast is not None else None,
        interception=[_assessment_view(a) for a in assessments or []],
        timeline=tl,
        deliveries=[
            DeliveryModel(
                channel=d.channel.value,
                status=d.status.value,
                attempts=d.attempts,
                sent_at=d.sent_at.isoformat() if d.sent_at else None,
                rendered_body=d.rendered_body,
            )
            for d in deliveries
        ],
        actions=[action_view(a) for a in actions],
        outcomes=[outcome_view(o) for o in outcomes],
        allowed_actions=allowed_actions,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=PageModel)
def list_alerts(
    request: Request,
    status: str | None = None,
    view: Literal["queue", "backlog", "all", "review"] = "queue",
    cursor: str | None = None,
    limit: int = 50,
    principal: Principal = Depends(get_principal),
) -> PageModel:
    """GET /api/v1/alerts — paginated; filtered by principal scope (LC-4 Page<AlertSummary>).

    `view`: "queue" (default) is what the alert budget shows; "backlog" the deferred alerts that
    stay reachable; "all" both; "review" the officer's uncertainty-ordered feedback queue."""
    with get_uow(request) as uow:
        assert uow.session is not None
        svc = build_service(request, uow.session)
        alerts, next_cursor = svc.list_alerts(
            principal, status=status, view=view, cursor=cursor, limit=min(limit, 200)
        )
    return PageModel(items=[_summary(a) for a in alerts], next_cursor=next_cursor)


def _detail_for(svc, principal: Principal, alert: Alert) -> AlertDetailModel:  # noqa: ANN001
    return _detail(
        alert,
        svc.list_deliveries_for_alert(alert.id),
        svc.list_actions(alert.id),
        svc.list_outcomes(alert.id),
        svc.allowed_actions(principal, alert),
        svc.forecast_for(alert),
        svc.assessments_for(alert),
    )


@router.get("/{alert_id}", response_model=AlertDetailModel)
def get_alert(
    alert_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> AlertDetailModel:
    """GET /api/v1/alerts/{id} — AlertDetail (LC-4); 403 outside the principal's scope."""
    with get_uow(request) as uow:
        assert uow.session is not None
        svc = build_service(request, uow.session)
        alert = svc.get_alert_for(principal, alert_id)
        return _detail_for(svc, principal, alert)


@router.post("/{alert_id}/acknowledge", response_model=AlertDetailModel)
def acknowledge_alert(
    alert_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> AlertDetailModel:
    """POST /api/v1/alerts/{id}/acknowledge — transitions to acknowledged."""
    with get_uow(request) as uow:
        assert uow.session is not None
        svc = build_service(request, uow.session)
        alert = svc.acknowledge(principal, alert_id)
        uow.commit()
        return _detail_for(svc, principal, alert)
