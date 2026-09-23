"""/auth/* routers (DOC 2 §2.4, DOC 3 M5). Routers only parse the request, resolve the module
facade and call one use case; no business logic here. Each route commits the UnitOfWork only
after the facade call returns.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Depends, Request, Response
from nakabandi_contracts.enums import Role
from pydantic import BaseModel

from nakabandi.access import AccessService
from nakabandi.access.domain.principal import Principal
from nakabandi.access.interfaces.dependencies import SESSION_COOKIE_NAME, get_principal
from nakabandi.access.interfaces.rate_limit import (
    enforce_control_rate_limit,
    enforce_login_rate_limit,
)
from nakabandi.shared import DomainError, Forbidden, NotFound, SqlAlchemyUnitOfWork

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    user_id: str
    name: str
    role: str
    expires_at: str


class MeResponse(BaseModel):
    user_id: str
    name: str
    role: str
    scope: dict
    permissions: list[str]


class DemoUserResponse(BaseModel):
    username: str
    password: str
    role: str
    display_name: str


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


@router.post("/login", dependencies=[Depends(enforce_login_rate_limit)])
def login(
    body: LoginRequest,
    response: Response,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
    service: AccessService = Depends(get_access_service),
) -> LoginResponse:
    session = service.login(body.username, body.password)
    uow.commit()
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session.token,
        httponly=True,
        samesite="lax",
        expires=session.expires_at,
    )
    return LoginResponse(
        user_id=session.principal.user_id,
        name=session.principal.display_name,
        role=session.principal.role.value,
        expires_at=session.expires_at.isoformat(),
    )


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
    service: AccessService = Depends(get_access_service),
) -> Response:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is not None:
        try:
            principal = get_principal(request)
            service.logout(principal)
            uow.commit()
        except DomainError:
            pass  # already invalid/expired; nothing to audit
    response.delete_cookie(SESSION_COOKIE_NAME)
    return Response(status_code=204)


@router.get("/me")
def me(
    principal: Principal = Depends(get_principal),
    service: AccessService = Depends(get_access_service),
) -> MeResponse:
    permissions = service.permissions_for(principal.role)
    return MeResponse(
        user_id=principal.user_id,
        name=principal.display_name,
        role=principal.role.value,
        scope={
            "state_id": principal.scope.state_id,
            "district_id": principal.scope.district_id,
            "bank_id": principal.scope.bank_id,
        },
        permissions=sorted(p.value for p in permissions),
    )


@router.get("/check", dependencies=[Depends(enforce_control_rate_limit)])
def check(
    role: Role,
    principal: Principal = Depends(get_principal),
    service: AccessService = Depends(get_access_service),
) -> Response:
    if service.check_role(principal, role):
        return Response(status_code=204)
    raise Forbidden("ROLE_MISMATCH", f"principal does not hold role {role.value}")


@router.get("/demo-users")
def demo_users(
    request: Request, service: AccessService = Depends(get_access_service)
) -> list[DemoUserResponse]:
    """Quick-login accounts for demos. 404 when NAKABANDI_DEMO_USERS_ENABLED is false: a
    deployment that is not a demo must not publish credentials (DOC 2 §2.8 T19)."""
    if not request.app.state.settings.demo_users_enabled:
        raise NotFound("NOT_FOUND", "demo users are not enabled")
    return [
        DemoUserResponse(
            username=u.name, password=u.password, role=u.role.value, display_name=u.display_name
        )
        for u in service.list_demo_users()
    ]
