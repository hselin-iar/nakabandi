"""POST /integrations/bank/callbacks (DOC 3 M4, LC-6). Service key required; no Principal."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from nakabandi.alerting import BankCallback
from nakabandi.alerting.interfaces.deps import build_service, get_uow, require_service_key

router = APIRouter(prefix="/integrations", tags=["integrations"])


class BankCallbackBody(BaseModel):
    request_id: str
    status: str  # applied | rejected | released, checked by the use case
    at_sim: datetime
    applied_amount_paise: int | None = None
    note: str | None = None


class BankCallbackAck(BaseModel):
    ack: bool
    applied: bool  # False: a duplicate, or older than the status already held


@router.post(
    "/bank/callbacks",
    response_model=BankCallbackAck,
    dependencies=[Depends(require_service_key)],
)
def bank_callback(body: BankCallbackBody, request: Request) -> BankCallbackAck:
    with get_uow(request) as uow:
        assert uow.session is not None
        svc = build_service(request, uow.session)
        result = svc.handle_bank_callback(BankCallback(**body.model_dump()))
        uow.commit()
    return BankCallbackAck(ack=True, applied=result.applied)
