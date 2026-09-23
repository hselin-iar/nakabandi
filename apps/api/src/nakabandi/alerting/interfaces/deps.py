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
    """The alert service for this request's session, built the one way main.py builds it."""
    return request.app.state.alert_service_factory(session)


def require_service_key(
    x_nakabandi_service_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """Machine clients (bank-sim) authenticate with the shared service key, sent either as the
    X-Nakabandi-Service-Key header (what /ingest/* uses, intake/interfaces/deps.py) or as
    `Authorization: Bearer <key>` (what apps/bank-sim's callback sends). LC-6 says only "service
    key", so both are accepted; either way the same secret, compared in constant time."""
    key = x_nakabandi_service_key
    if key is None and authorization and authorization.startswith("Bearer "):
        key = authorization[len("Bearer ") :].strip()
    if key is None or not secrets.compare_digest(key, settings.service_api_key):
        raise Unauthenticated(
            "SERVICE_KEY_INVALID", "a valid service key (header or Bearer token) is required"
        )
