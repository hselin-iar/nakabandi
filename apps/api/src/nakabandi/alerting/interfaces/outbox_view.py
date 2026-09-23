"""GET /outbox: the in-app Outbox viewer (DOC 2 §2.2; DOC 4 A8). Shows rendered bodies (masked
identifiers only) and delivery state, including dead letters. Never returns the wire payload."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from nakabandi_contracts.enums import Permission
from pydantic import BaseModel

from nakabandi.access import Principal, authorize, get_principal
from nakabandi.alerting.interfaces.deps import build_service, get_uow

router = APIRouter(prefix="/outbox", tags=["outbox"])


class DeliveryView(BaseModel):
    id: str
    alert_id: str
    action_id: str | None
    channel: str
    provider: str | None
    webhook_kind: str | None
    recipient: str
    status: str
    attempts: int
    next_attempt_at: str
    created_at: str
    sent_at: str | None
    last_error: str | None
    rendered_body: str


class OutboxPage(BaseModel):
    items: list[DeliveryView]
    next_cursor: str | None
    dead_count: int


@router.get("", response_model=OutboxPage)
def list_outbox(
    request: Request,
    status: str | None = None,
    channel: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
    principal: Principal = Depends(get_principal),
) -> OutboxPage:
    authorize(principal, Permission.VIEW_ALERTS, request.app.state.role_permissions)
    with get_uow(request) as uow:
        assert uow.session is not None
        svc = build_service(request, uow.session)
        items, next_cursor = svc.list_deliveries(
            status=status, channel=channel, cursor=cursor, limit=min(limit, 200)
        )
        dead = svc.count_dead_deliveries()
    return OutboxPage(
        items=[
            DeliveryView(
                id=d.id,
                alert_id=d.alert_id,
                action_id=d.action_id,
                channel=d.channel.value,
                provider=d.provider,
                webhook_kind=d.webhook_kind.value if d.webhook_kind else None,
                recipient=d.recipient,
                status=d.status.value,
                attempts=d.attempts,
                next_attempt_at=d.next_attempt_at.isoformat(),
                created_at=d.created_at.isoformat(),
                sent_at=d.sent_at.isoformat() if d.sent_at else None,
                last_error=d.last_error,
                rendered_body=d.rendered_body,
            )
            for d in items
        ],
        next_cursor=next_cursor,
        dead_count=dead,
    )
