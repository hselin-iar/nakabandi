"""POST /alerts/{id}/actions (DOC 3 M4, LC-4 ActionIn). Requires a Principal."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from nakabandi_contracts.enums import ActionType
from pydantic import BaseModel, Field

from nakabandi.access import Principal, get_principal
from nakabandi.alerting import ActionIn
from nakabandi.alerting.domain.action import Action
from nakabandi.alerting.interfaces.deps import build_service, get_uow
from nakabandi.shared import Forbidden

router = APIRouter(prefix="/alerts", tags=["alerts"])


class ActionInModel(BaseModel):
    type: ActionType
    reason: str | None = None
    params: dict = Field(default_factory=dict)


class ActionModel(BaseModel):
    id: str
    alert_id: str
    type: str
    status: str
    actor_role: str
    at: str
    params: dict
    reason: str | None = None
    applied_amount_paise: int | None = None


def action_view(action: Action) -> ActionModel:
    return ActionModel(
        id=action.id,
        alert_id=action.alert_id,
        type=action.type.value,
        status=action.status.value,
        actor_role=action.actor_role,
        at=action.at.isoformat(),
        params=action.params,
        reason=action.reason,
        applied_amount_paise=action.applied_amount_paise,
    )


@router.post("/{alert_id}/actions", response_model=ActionModel, status_code=201)
def record_action(
    alert_id: str,
    body: ActionInModel,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> ActionModel:
    """403 FORBIDDEN_PERMISSION (audited as denied), 409 INVALID_TRANSITION, 422 LIEN_INVALID."""
    with get_uow(request) as uow:
        assert uow.session is not None
        svc = build_service(request, uow.session)
        try:
            action = svc.record_action(
                principal,
                alert_id,
                ActionIn(type=body.type, reason=body.reason, params=body.params),
            )
        except Forbidden:
            uow.commit()  # keep the "action.denied" audit entry RecordAction just appended
            raise
        uow.commit()
    return action_view(action)
