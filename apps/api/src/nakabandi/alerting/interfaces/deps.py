"""Shared wiring for alerting routers: build an AlertService on the request's own session."""

from __future__ import annotations

import secrets

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from nakabandi.alerting import AlertService
from nakabandi.shared import Settings, SqlAlchemyUnitOfWork, Unauthenticated, get_settings


def get_uow(request: Request) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(request.app.state.session_factory)


def build_service(request: Request, session: Session) -> AlertService:
    state = request.app.state
    return AlertService(
        session=session,
        clock=state.clock,
        policy=state.policy,
        scheduler=state.scheduler,
        role_permissions=state.role_permissions,
        sse_hub=state.sse_hub,
        lien_context=state.lien_context_factory(session),
        validate_lien=state.validate_lien_factory(session),
        scope_lookup=state.scope_lookup_factory(session),
        bus=state.event_bus_factory(session),
    )


def require_service_key(
    x_nakabandi_service_key: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """Machine clients (bank-sim) authenticate with the shared service key, the same header the
    /ingest/* routes use (intake/interfaces/deps.py)."""
    if x_nakabandi_service_key is None or not secrets.compare_digest(
        x_nakabandi_service_key, settings.service_api_key
    ):
        raise Unauthenticated("SERVICE_KEY_INVALID", "a valid X-Nakabandi-Service-Key is required")
