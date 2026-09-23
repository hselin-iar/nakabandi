"""GET /alerts, GET /alerts/{id}, POST /alerts/{id}/acknowledge (DOC 3 M4, LC-4).

All endpoints require authentication (get_principal).
GET /alerts respects scope (filtered by principal's scope).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from nakabandi.access import Principal, get_principal
from nakabandi.alerting.domain.action import Action
from nakabandi.alerting.domain.alert import Alert
from nakabandi.alerting.domain.delivery import Delivery
from nakabandi.alerting.interfaces.actions import ActionModel, action_view
from nakabandi.alerting.interfaces.deps import build_service, get_uow

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


class AlertDetailModel(AlertSummaryModel):
    timeline: list[TimelineEntryModel]
    deliveries: list[DeliveryModel]
    actions: list[ActionModel]
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
    allowed_actions: list[str],
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
        allowed_actions=allowed_actions,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=PageModel)
def list_alerts(
    request: Request,
    status: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
    principal: Principal = Depends(get_principal),
) -> PageModel:
    """GET /api/v1/alerts — paginated; filtered by principal scope (LC-4 Page<AlertSummary>)."""
    with get_uow(request) as uow:
        assert uow.session is not None
        svc = build_service(request, uow.session)
        alerts, next_cursor = svc.list_alerts(
            principal, status=status, cursor=cursor, limit=min(limit, 200)
        )
    return PageModel(items=[_summary(a) for a in alerts], next_cursor=next_cursor)


def _detail_for(svc, principal: Principal, alert: Alert) -> AlertDetailModel:  # noqa: ANN001
    return _detail(
        alert,
        svc.list_deliveries_for_alert(alert.id),
        svc.list_actions(alert.id),
        svc.allowed_actions(principal, alert),
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
