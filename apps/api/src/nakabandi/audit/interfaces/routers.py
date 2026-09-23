"""GET /audit, GET /audit/verify (DOC 3 M5). Routers only parse, authorize and call the
audit facade; no business logic here.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Depends, Request
from nakabandi_contracts.enums import Permission
from pydantic import BaseModel

from nakabandi.access import AccessService, Principal, get_principal
from nakabandi.audit import AuditLog
from nakabandi.shared import SqlAlchemyUnitOfWork

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditEntryResponse(BaseModel):
    seq: int
    at: str
    actor_id: str
    actor_role: str
    action: str
    entity_type: str
    entity_id: str
    reason: str | None
    payload: dict


class VerifyResponse(BaseModel):
    ok: bool
    first_bad_seq: int | None
    head_hash: str | None


def get_uow(request: Request) -> Iterator[SqlAlchemyUnitOfWork]:
    uow = SqlAlchemyUnitOfWork(request.app.state.session_factory)
    with uow:
        yield uow


def get_access_service(
    request: Request, uow: SqlAlchemyUnitOfWork = Depends(get_uow)
) -> AccessService:
    assert uow.session is not None
    return AccessService(
        uow.session,
        request.app.state.clock,
        request.app.state.token_issuer,
        request.app.state.role_permissions,
    )


def get_audit_log(request: Request, uow: SqlAlchemyUnitOfWork = Depends(get_uow)) -> AuditLog:
    assert uow.session is not None
    return AuditLog(uow.session, request.app.state.clock)


@router.get("")
def list_audit(
    principal: Principal = Depends(get_principal),
    access: AccessService = Depends(get_access_service),
    audit: AuditLog = Depends(get_audit_log),
) -> list[AuditEntryResponse]:
    access.authorize(principal, Permission.VIEW_AUDIT)
    return [
        AuditEntryResponse(
            seq=e.seq,
            at=e.at.isoformat(),
            actor_id=e.actor_id,
            actor_role=e.actor_role,
            action=e.action,
            entity_type=e.entity_type,
            entity_id=e.entity_id,
            reason=e.reason,
            payload=e.payload,
        )
        for e in audit.list()
    ]


@router.get("/verify")
def verify_audit(
    principal: Principal = Depends(get_principal),
    access: AccessService = Depends(get_access_service),
    audit: AuditLog = Depends(get_audit_log),
) -> VerifyResponse:
    access.authorize(principal, Permission.VIEW_AUDIT)
    report = audit.verify()
    return VerifyResponse(
        ok=report.ok, first_bad_seq=report.first_bad_seq, head_hash=report.head_hash
    )
