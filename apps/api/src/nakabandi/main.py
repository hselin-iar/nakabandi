"""NAKABANDI API composition root: wiring and lifespan tasks (DOC 2 §2.6).

The only file that imports several modules' facades AND their infrastructure wiring pieces
side by side: everywhere else, that is `pipeline`'s job (DOC 3 M2 "the ONLY place that calls
several module facades in sequence") or a router's (one facade per request).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from nakabandi.intake.interfaces.routers import router as intake_router
from nakabandi.shared import (
    SIM_CLOCK_EPOCH,
    DomainError,
    Policy,
    SimClock,
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


def create_app() -> FastAPI:
    configure_logging(json=get_settings().environment != "dev")

    settings = get_settings()
    Policy.load(settings.policy_path)  # aborts boot on a missing/invalid policy (LC-7)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_sqlite_engine(settings.database_url)
        create_all(engine)
        app.state.session_factory = make_session_factory(engine)
        app.state.clock = SimClock(start=SIM_CLOCK_EPOCH)
        yield

    app = FastAPI(title="NAKABANDI API", version="0.0.0", lifespan=lifespan)
    app.add_exception_handler(DomainError, _domain_error_handler)
    app.include_router(intake_router, prefix="/api/v1")
    return app


app = create_app()
