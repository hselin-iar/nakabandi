"""NAKABANDI API composition root: wiring and lifespan tasks (DOC 2 §2.6).

The only file that imports several modules' facades AND their infrastructure wiring pieces
side by side: everywhere else, that is `pipeline`'s job (DOC 3 M2 "the ONLY place that calls
several module facades in sequence") or a router's (one facade per request).
"""

from __future__ import annotations

from collections.abc import Mapping, Set
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from nakabandi_contracts.enums import Permission, Role

from nakabandi.access import AccessService
from nakabandi.access.infrastructure.tokens import JwtTokenIssuer
from nakabandi.access.interfaces.rate_limit import LoginAttempts
from nakabandi.access.interfaces.routers import router as access_router
from nakabandi.alerting import AlertService, SseHub
from nakabandi.alerting.interfaces.alerts import router as alerts_router
from nakabandi.alerting.interfaces.stream import router as stream_router
from nakabandi.audit.interfaces.routers import router as audit_router
from nakabandi.intake.interfaces.routers import router as intake_router
from nakabandi.shared import (
    SIM_CLOCK_EPOCH,
    DomainError,
    Policy,
    Scheduler,
    SimClock,
    SqlAlchemyUnitOfWork,
    get_settings,
    message_for,
)
from nakabandi.shared.infrastructure.db import (
    create_all,
    create_sqlite_engine,
    make_session_factory,
)
from nakabandi.shared.logging import configure_logging


def _domain_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Translates any DomainError to the error JSON shape (DOC 2 §2.4): developer detail
    (`exc.message`, from the raising module) stays out of the response; only the user-facing
    text from `message_for` does. Never a stack trace."""
    assert isinstance(exc, DomainError)
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error": {
                "code": exc.code,
                "message": message_for(exc.code),
                "details": exc.details,
            }
        },
    )


def _role_permissions(policy: Policy) -> Mapping[Role, Set[Permission]]:
    return {
        Role(role): frozenset(Permission(p) for p in perms)
        for role, perms in policy.access.permissions.items()
    }


def create_app() -> FastAPI:
    configure_logging(json=get_settings().environment != "dev")

    settings = get_settings()
    policy = Policy.load(settings.policy_path)  # aborts boot on a missing/invalid policy (LC-7)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_sqlite_engine(settings.database_url)
        create_all(engine)
        app.state.session_factory = make_session_factory(engine)
        app.state.clock = SimClock(start=SIM_CLOCK_EPOCH)
        app.state.token_issuer = JwtTokenIssuer(settings.jwt_secret)
        app.state.role_permissions = _role_permissions(policy)
        app.state.login_attempts = LoginAttempts()
        app.state.policy = policy
        app.state.scheduler = Scheduler()
        app.state.sse_hub = SseHub()

        with SqlAlchemyUnitOfWork(app.state.session_factory) as uow:
            assert uow.session is not None
            AccessService(
                uow.session, app.state.clock, app.state.token_issuer, app.state.role_permissions
            ).seed_demo_users()
            uow.commit()

        # Rebuild alerting timers from any existing open alerts (DOC 3 M4 RebuildTimers)
        with SqlAlchemyUnitOfWork(app.state.session_factory) as uow:
            assert uow.session is not None
            AlertService(
                session=uow.session,
                clock=app.state.clock,
                policy=policy,
                scheduler=app.state.scheduler,
                role_permissions=app.state.role_permissions,
                sse_hub=app.state.sse_hub,
            ).rebuild_timers()

        yield

        # Shutdown: signal SSE subscribers to close
        app.state.sse_hub.close_all()

    app = FastAPI(title="NAKABANDI API", version="0.0.0", lifespan=lifespan)
    app.add_exception_handler(DomainError, _domain_error_handler)
    app.include_router(intake_router, prefix="/api/v1")
    app.include_router(access_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")
    app.include_router(alerts_router, prefix="/api/v1")
    app.include_router(stream_router, prefix="/api/v1")

    @app.get("/api/v1/system/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # The built SPA (DOC 2 hosted topology: "/ -> api container, SPA static files"). Registered
    # last so /api/v1/* above always matches first; Settings.static_dir is unset outside the
    # Docker image (Dockerfile.api builds apps/web and sets STATIC_DIR), so local dev and tests
    # never try to mount a directory that does not exist.
    if settings.static_dir is not None and settings.static_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="spa")

    return app


app = create_app()
