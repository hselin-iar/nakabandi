"""NAKABANDI API composition root: wiring and lifespan tasks (DOC 2 §2.6).

The only file that imports several modules' facades AND their infrastructure wiring pieces
side by side: everywhere else, that is `pipeline`'s job (DOC 3 M2 "the ONLY place that calls
several module facades in sequence") or a router's (one facade per request).
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Mapping, Set
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from nakabandi_contracts.enums import Permission, Role
from sqlalchemy.orm import Session

from nakabandi.access import AccessService
from nakabandi.access.infrastructure.tokens import JwtTokenIssuer
from nakabandi.access.interfaces.rate_limit import LoginAttempts
from nakabandi.access.interfaces.routers import router as access_router
from nakabandi.alerting import AlertService, DeliveryChannel, SseEvent, SseHub
from nakabandi.alerting.infrastructure.channels.email_smtp import SmtpEmail
from nakabandi.alerting.infrastructure.channels.sms_outbox import OutboxSms
from nakabandi.alerting.infrastructure.channels.sms_provider import ProviderSms, SmsWithFallback
from nakabandi.alerting.infrastructure.channels.webhook_bank import BankWebhook
from nakabandi.alerting.interfaces.actions import router as actions_router
from nakabandi.alerting.interfaces.alerts import router as alerts_router
from nakabandi.alerting.interfaces.integrations import router as integrations_router
from nakabandi.alerting.interfaces.outbox_view import router as outbox_router
from nakabandi.alerting.interfaces.stream import router as stream_router
from nakabandi.analytics import AnalyticsService
from nakabandi.analytics.interfaces.routers import router as analytics_router
from nakabandi.audit.interfaces.routers import router as audit_router
from nakabandi.forecast.infrastructure.repositories import metadata as forecast_metadata
from nakabandi.geo import LocationScopeLookup
from nakabandi.geo.interfaces.routers import router as geo_router
from nakabandi.intake import LienContextLookup
from nakabandi.intake.interfaces.routers import router as intake_router
from nakabandi.interception import Interceptor
from nakabandi.interception.infrastructure.repositories import SqlAssessmentRepo, SqlUnitRepo
from nakabandi.shared import (
    SIM_CLOCK_EPOCH,
    DomainError,
    EventBus,
    Policy,
    Scheduler,
    SimClock,
    SqlAlchemyUnitOfWork,
    SystemClock,
    get_settings,
    message_for,
)
from nakabandi.shared.infrastructure.db import (
    create_all,
    create_sqlite_engine,
    make_session_factory,
)
from nakabandi.shared.logging import configure_logging
from nakabandi.wiring import GeoCatalogAdapter, ProjectionSourceAdapter

logger = structlog.get_logger(__name__)


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


OUTBOX_POLL_S = 1.0  # how often the in-process outbox worker looks for due deliveries
TIMER_POLL_S = 1.0  # how often the timer driver fires timers that are due at the sim time


def create_app() -> FastAPI:
    configure_logging(json=get_settings().environment != "dev")

    settings = get_settings()
    policy = Policy.load(settings.policy_path)  # aborts boot on a missing/invalid policy (LC-7)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_sqlite_engine(settings.database_url)
        create_all(engine)
        # forecast's tables sit on their own MetaData (Track B), which create_all does not see
        forecast_metadata.create_all(engine)
        app.state.session_factory = make_session_factory(engine)
        app.state.clock = SimClock(start=SIM_CLOCK_EPOCH)
        app.state.token_issuer = JwtTokenIssuer(settings.jwt_secret)
        app.state.role_permissions = _role_permissions(policy)
        app.state.login_attempts = LoginAttempts()
        app.state.policy = policy
        app.state.scheduler = Scheduler()
        app.state.sse_hub = SseHub()

        # One EventBus per unit of work (LC-3): subscribers such as the analytics projector write
        # on the publisher's own session, so their rows commit or roll back with the alert or
        # forecast they describe. `bus_registrars` is the list of subscribers; each is called with
        # the fresh bus and that session.
        def register_analytics(bus: EventBus, session: Session) -> None:
            AnalyticsService(
                session,
                policy=policy,
                clock=app.state.clock,
                role_permissions=app.state.role_permissions,
                catalog=GeoCatalogAdapter(session),
                source=ProjectionSourceAdapter(session),
                publish_version=lambda v: app.state.sse_hub.publish(
                    SseEvent(name="heat.version", data={"version": v})
                ),
            ).register_projectors(bus)

        app.state.bus_registrars = [register_analytics]

        def event_bus_for(session: Session) -> EventBus:
            bus = EventBus()
            for register in app.state.bus_registrars:
                register(bus, session)
            return bus

        app.state.event_bus_factory = event_bus_for
        app.state.lien_context_factory = LienContextLookup
        app.state.scope_lookup_factory = LocationScopeLookup
        app.state.validate_lien_factory = lambda session: (
            Interceptor(SqlUnitRepo(session), SqlAssessmentRepo(session), policy).validate_lien
        )
        app.state.outbox_channels = {
            DeliveryChannel.EMAIL: SmtpEmail(settings.smtp_host, settings.smtp_port),
            DeliveryChannel.SMS: SmsWithFallback(
                ProviderSms(settings.sms_provider_url, settings.sms_provider_key), OutboxSms()
            ),
            DeliveryChannel.WEBHOOK: BankWebhook(
                settings.bank_webhook_url, settings.webhook_secret
            ),
        }

        def run_outbox_once() -> int:
            """One DeliverOutbox pass on its own unit of work (DOC 3 M4 run_once, wall clock)."""
            with SqlAlchemyUnitOfWork(app.state.session_factory) as uow:
                assert uow.session is not None
                sent = AlertService(
                    session=uow.session,
                    clock=app.state.clock,
                    policy=policy,
                    scheduler=app.state.scheduler,
                    role_permissions=app.state.role_permissions,
                    sse_hub=app.state.sse_hub,
                ).deliver_outbox(app.state.outbox_channels, SystemClock().now())
                uow.commit()
            return sent

        app.state.run_outbox_once = run_outbox_once

        def run_timers_once() -> int:
            """One timer tick on its own unit of work, so every timer it fires is bound to a
            session that is open (DOC 3 M4 RebuildTimers; the tick re-registers before firing)."""
            with SqlAlchemyUnitOfWork(app.state.session_factory) as uow:
                assert uow.session is not None
                fired = AlertService(
                    session=uow.session,
                    clock=app.state.clock,
                    policy=policy,
                    scheduler=app.state.scheduler,
                    role_permissions=app.state.role_permissions,
                    sse_hub=app.state.sse_hub,
                ).fire_due_timers()
                uow.commit()
            return fired

        app.state.run_timers_once = run_timers_once

        async def timer_worker() -> None:
            while True:
                await asyncio.sleep(TIMER_POLL_S)
                try:
                    await asyncio.to_thread(run_timers_once)
                except Exception:  # one bad tick must not stop the driver
                    logger.exception("timers.worker.tick_failed")

        timers = asyncio.create_task(timer_worker()) if settings.timer_worker_enabled else None

        async def outbox_worker() -> None:
            while True:
                await asyncio.sleep(OUTBOX_POLL_S)
                try:
                    await asyncio.to_thread(run_outbox_once)
                except Exception:  # one bad pass must not stop the worker
                    logger.exception("outbox.worker.pass_failed")

        worker = asyncio.create_task(outbox_worker()) if settings.outbox_worker_enabled else None

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

        # Shutdown: stop the outbox worker and timer driver, then signal SSE subscribers to close
        for task in (worker, timers):
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        app.state.sse_hub.close_all()

    app = FastAPI(title="NAKABANDI API", version="0.0.0", lifespan=lifespan)
    app.add_exception_handler(DomainError, _domain_error_handler)
    app.include_router(intake_router, prefix="/api/v1")
    app.include_router(geo_router, prefix="/api/v1")
    app.include_router(analytics_router, prefix="/api/v1")
    app.include_router(access_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")
    app.include_router(alerts_router, prefix="/api/v1")
    app.include_router(actions_router, prefix="/api/v1")
    app.include_router(integrations_router, prefix="/api/v1")
    app.include_router(outbox_router, prefix="/api/v1")
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
