"""Shared wiring for casework routers: build a CaseService on the request's own session, the one
way main.py builds it (mirrors alerting/interfaces/deps.py)."""

from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from nakabandi.casework import CaseService
from nakabandi.shared import SqlAlchemyUnitOfWork


def get_uow(request: Request) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(request.app.state.session_factory)


def build_service(request: Request, session: Session) -> CaseService:
    return request.app.state.case_service_factory(session)
