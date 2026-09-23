"""POST /alerts/{id}/outcome (DOC 3 S3): an officer marks what became of an alert."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from nakabandi.access import Principal, get_principal
from nakabandi.alerting.domain.outcome import Outcome
from nakabandi.alerting.interfaces.deps import build_service, get_uow

router = APIRouter(prefix="/alerts", tags=["alerts"])


class OutcomeIn(BaseModel):
    result: str  # hit | miss | late
    location_id: str | None = None
    reason: str | None = None


class OutcomeView(BaseModel):
    """LC-4 Outcome: { id, alert_id, result, source: officer|reconciled, at }."""

    id: str
    alert_id: str
    result: str
    source: str
    at: str


def outcome_view(o: Outcome) -> OutcomeView:
    return OutcomeView(
        id=o.id, alert_id=o.alert_id, result=o.result, source=o.source, at=o.decided_at.isoformat()
    )


@router.post("/{alert_id}/outcome", response_model=OutcomeView, status_code=201)
def mark_outcome(
    alert_id: str,
    body: OutcomeIn,
    request: Request,
    response: Response,
    principal: Principal = Depends(get_principal),
) -> OutcomeView:
    """201 for a new outcome, 200 for a repeat of the same (alert, result, location). 403 without
    MARK_OUTCOME or outside scope; 422 for an unknown result or a location not in the registry."""
    with get_uow(request) as uow:
        assert uow.session is not None
        svc = build_service(request, uow.session)
        outcome, created = svc.mark_outcome(
            principal, alert_id, body.result, body.location_id, body.reason
        )
        uow.commit()
    if not created:
        response.status_code = 200
    return outcome_view(outcome)
