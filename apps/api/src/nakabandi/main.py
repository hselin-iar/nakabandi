"""NAKABANDI API composition root: wiring and lifespan tasks (DOC 2 §2.6).

The only file that imports several modules' facades AND their infrastructure wiring pieces
side by side: everywhere else, that is `pipeline`'s job (DOC 3 M2 "the ONLY place that calls
several module facades in sequence") or a router's (one facade per request).
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import Mapping, Set
from contextlib import asynccontextmanager
from datetime import timedelta

import httpx
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
from nakabandi.alerting.interfaces.outcomes import router as outcomes_router
from nakabandi.alerting.interfaces.stream import router as stream_router
from nakabandi.analytics import AnalyticsService
from nakabandi.analytics.interfaces.routers import router as analytics_router
from nakabandi.audit.interfaces.routers import router as audit_router
from nakabandi.casework import CaseService
from nakabandi.casework.evidence.file_store import LocalFileStore
from nakabandi.casework.interfaces.routers import router as casework_router
from nakabandi.forecast import ModelStore
from nakabandi.geo import LocationScopeLookup
from nakabandi.geo.interfaces.routers import router as geo_router
from nakabandi.graph import CashOutFact, ClusterService
from nakabandi.graph.infrastructure.repositories import SqlClusterRepo
from nakabandi.intake import IngestHooks, LienContextLookup, latest_ingest_sim_time
from nakabandi.intake.infrastructure.repositories import SqlComplaintRepo
from nakabandi.intake.interfaces.routers import router as intake_router
from nakabandi.interception import Interceptor
from nakabandi.interception.infrastructure.repositories import (
    SqlAssessmentRepo,
    SqlUnitRepo,
)
from nakabandi.live_pipeline import RegistryCache, build_pipeline
from nakabandi.maintenance import (
    AutoPause,
    ResetReport,
    StreamGate,
    create_schema,
    reset_database,
    seconds_until,
)
from nakabandi.ops import LatencyMiddleware
from nakabandi.ops import router as ops_router
from nakabandi.pipeline import RetryUnprocessed
from nakabandi.shared import (
    SIM_CLOCK_EPOCH,
    ClusterMerged,
    DomainError,
    EventBus,
    MeteredEventBus,
    Metrics,
    ObservationIngested,
    Policy,
    SimClock,
    SlidingWindowLimiter,
    SqlAlchemyUnitOfWork,
    SystemClock,
    get_settings,
    message_for,
)
from nakabandi.shared.infrastructure.db import (
    create_sqlite_engine,
    make_session_factory,
)
from nakabandi.shared.logging import configure_logging
from nakabandi.wiring import (
    AlertDetailSourceAdapter,
    CaseworkClusterSource,
    CaseworkComplaintSource,
    GeoCatalogAdapter,
    GraphConfirmedCashOut,
    ObservationSourceAdapter,
    ProjectionSourceAdapter,
)

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
AUTO_PAUSE_POLL_S = 30.0  # how often auto-pause checks for viewers
RETRY_EVERY_TICKS = 300  # RetryUnprocessed runs every 5 minutes (DOC 3 M2)


def create_app() -> FastAPI:
    configure_logging(json=get_settings().environment != "dev")

    settings = get_settings()
    policy = Policy.load(settings.policy_path)  # aborts boot on a missing/invalid policy (LC-7)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_sqlite_engine(settings.database_url)
        create_schema(engine)
        app.state.session_factory = make_session_factory(engine)
        app.state.clock = SimClock(start=SIM_CLOCK_EPOCH)
        app.state.token_issuer = JwtTokenIssuer(settings.jwt_secret)
        app.state.role_permissions = _role_permissions(policy)
        app.state.login_attempts = LoginAttempts()
        app.state.settings = settings
        app.state.started_at = SystemClock().now()
        app.state.metrics = Metrics()
        # Hosted-demo protections (DOC 2 §2.7). Each is off unless configured (or hosted_demo).
        app.state.control_limiter = SlidingWindowLimiter(
            settings.effective_control_rate_per_min, timedelta(minutes=1)
        )
        app.state.stream_gate = StreamGate(settings.effective_max_sse_streams)
        app.state.maintenance = threading.Lock()  # held while the nightly reset runs
        app.state.policy = policy
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

        def alert_service_for(session: Session, bus: EventBus | None = None) -> AlertService:
            """THE way an AlertService is built for a unit of work (routes, the pipeline and the
            bus subscribers all use it), so they can never drift apart."""
            return AlertService(
                session=session,
                clock=app.state.clock,
                policy=policy,
                role_permissions=app.state.role_permissions,
                sse_hub=app.state.sse_hub,
                lien_context=LienContextLookup(session),
                validate_lien=app.state.validate_lien_factory(session),
                scope_lookup=LocationScopeLookup(session),
                observations=ObservationSourceAdapter(session),
                confirmed=GraphConfirmedCashOut(session, app.state.event_bus_factory),
                detail_source=AlertDetailSourceAdapter(session),
                bus=bus if bus is not None else app.state.event_bus_factory(session),
            )

        app.state.alert_service_factory = alert_service_for
        app.state.registry_cache = RegistryCache()
        app.state.evidence_file_store = LocalFileStore(settings.evidence_store_path)
        # scripts/train.py writes here; GenerateForecast.load_scorer()/load_timing() read it at
        # forecast time. Missing files just fall back to the heuristic scorer with a boot
        # warning — a fresh checkout with no models/ directory yet still boots fine.
        app.state.model_store = ModelStore(settings.model_store_dir)

        def case_service_for(session: Session, bus: EventBus | None = None) -> CaseService:
            """THE way a CaseService is built for a unit of work (DOC 3 A12, mirrors
            alert_service_for)."""
            return CaseService(
                session,
                clock=app.state.clock,
                cluster_source=CaseworkClusterSource(session),
                complaint_source=CaseworkComplaintSource(session),
                alert_source=alert_service_for(session, bus),
                role_permissions=app.state.role_permissions,
                file_store=app.state.evidence_file_store,
                debounce_min=policy.casework.bundle_debounce_min,
                font_path=settings.evidence_font_path,
            )

        app.state.case_service_factory = case_service_for

        def register_reconcile(bus: EventBus, session: Session) -> None:
            """ReconcileOutcome listens for ingested cash-outs (DOC 3 M4 on_observation)."""
            alert_service_for(session, bus).register_subscribers(bus)

        def register_casework(bus: EventBus, session: Session) -> None:
            """BundleCluster listens for ClusterUpdated, debounced (DOC 3 S1)."""
            case_service_for(session, bus).register_subscribers(bus)

        def register_graph(bus: EventBus, session: Session) -> None:
            """Keep each cluster's location affinity current as cash-outs are observed, and
            re-key alerts when clusters merge (ClusterMerged, DOC 3 M4 edge case)."""
            cluster = ClusterService(SqlClusterRepo(session), bus)
            intake = LienContextLookup(session)

            def on_observations(event: ObservationIngested) -> None:
                registry = app.state.registry_cache.get(session)
                facts = []
                for obs in intake.observation_summaries(event.observation_ids):
                    loc = registry.by_id.get(obs.location_id)
                    if loc is not None and obs.observed_at is not None:
                        facts.append(
                            CashOutFact(
                                account_id=obs.account_id,
                                location_id=loc.id,
                                cell_id=loc.cell_id,
                                district_id=loc.district_id,
                                amount_paise=obs.amount_paise,
                                observed_at=obs.observed_at,
                            )
                        )
                cluster.apply_cashouts(facts, app.state.clock.now())

            def on_merge(event: ClusterMerged) -> None:
                alert_service_for(session, bus).on_cluster_merged(event.from_id, event.into_id)

            def safe(handler):  # noqa: ANN001, ANN202
                """A subscriber is fan-out: if it fails it is logged and the publisher (graph's
                resolve, intake's ingest) carries on. graph publishes unguarded, so one failing
                subscriber would otherwise fail the whole stage."""

                def guarded(event):  # noqa: ANN001, ANN202
                    try:
                        handler(event)
                    except Exception:
                        logger.exception("event.subscriber.failed", handler=handler.__name__)

                return guarded

            bus.subscribe(ObservationIngested, safe(on_observations))  # type: ignore[arg-type]
            bus.subscribe(ClusterMerged, safe(on_merge))  # type: ignore[arg-type]

        app.state.bus_registrars = [
            register_analytics,
            register_reconcile,
            register_graph,
            register_casework,
        ]
        app.state.observation_source_factory = ObservationSourceAdapter

        def pipeline_for(session: Session, bus: EventBus):  # noqa: ANN202
            return build_pipeline(
                session,
                policy=policy,
                bus=bus,
                registry_cache=app.state.registry_cache,
                alert_service=alert_service_for(session, bus),
                model_store=app.state.model_store,
                metrics=app.state.metrics,
            )

        app.state.pipeline_factory = pipeline_for

        def ingest_hooks_for(session: Session, bus: EventBus) -> IngestHooks:
            """The chain is CALLED after an ingest, explicitly (DOC 2 §2.1), on the request's own
            session: a posted complaint yields its forecast and alert in the same request."""

            def on_complaints(ids: list[str]) -> None:
                app.state.metrics.incr("complaints", len(ids))
                pipeline = pipeline_for(session, bus)
                for complaint_id in ids:
                    pipeline.run(complaint_id, app.state.clock.now())

            def on_hops(complaint_ids: list[str]) -> None:
                """Transfers that arrive after their complaint may join clusters, and a bigger
                cluster changes the forecast: re-run the chain for those complaints (DOC 3 M2
                RefreshOpenAlerts: "new hops may have changed the picture"). The alert merges."""
                pipeline = pipeline_for(session, bus)
                for complaint_id in complaint_ids:
                    pipeline.run(complaint_id, app.state.clock.now(), refresh=True)

            return IngestHooks(
                on_complaints=on_complaints,
                on_hops=on_hops,
                on_registry=app.state.registry_cache.invalidate,
            )

        app.state.ingest_hooks_factory = ingest_hooks_for

        def event_bus_for(session: Session) -> EventBus:
            bus = MeteredEventBus(app.state.metrics)
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
                sent = alert_service_for(uow.session).deliver_outbox(
                    app.state.outbox_channels, SystemClock().now()
                )
                uow.commit()
            return sent

        app.state.run_outbox_once = run_outbox_once

        def run_timers_once() -> int:
            """One timer tick on its own unit of work, so every timer it fires is bound to a
            session that is open (DOC 3 M4 RebuildTimers; the tick re-registers before firing)."""
            with SqlAlchemyUnitOfWork(app.state.session_factory) as uow:
                assert uow.session is not None
                fired = alert_service_for(uow.session).fire_due_timers()
                uow.commit()
            return fired

        app.state.run_timers_once = run_timers_once

        def run_retry_once() -> int:
            """RetryUnprocessed (DOC 3 M2): every complaint a failed stage left `unprocessed` goes
            through the chain again, on its own unit of work. Returns how many now succeeded."""
            with SqlAlchemyUnitOfWork(app.state.session_factory) as uow:
                assert uow.session is not None
                bus = app.state.event_bus_factory(uow.session)
                pipeline = pipeline_for(uow.session, bus)
                results = RetryUnprocessed(
                    SqlComplaintRepo(uow.session),
                    pipeline,  # type: ignore[arg-type]
                ).run(app.state.clock.now())
                uow.commit()
            return sum(1 for r in results if r.ok)

        app.state.run_retry_once = run_retry_once

        async def timer_worker() -> None:
            ticks = 0
            while True:
                await asyncio.sleep(TIMER_POLL_S)
                ticks += 1
                if app.state.maintenance.locked():
                    continue
                try:
                    await asyncio.to_thread(run_timers_once)
                    if ticks % RETRY_EVERY_TICKS == 0:
                        await asyncio.to_thread(run_retry_once)
                except Exception:  # one bad tick must not stop the driver
                    logger.exception("timers.worker.tick_failed")

        timers = asyncio.create_task(timer_worker()) if settings.timer_worker_enabled else None

        async def outbox_worker() -> None:
            while True:
                await asyncio.sleep(OUTBOX_POLL_S)
                if app.state.maintenance.locked():
                    continue  # the nightly reset is rebuilding the database
                try:
                    await asyncio.to_thread(run_outbox_once)
                except Exception:  # one bad pass must not stop the worker
                    logger.exception("outbox.worker.pass_failed")

        worker = asyncio.create_task(outbox_worker()) if settings.outbox_worker_enabled else None

        # The SimClock lives in memory: after a restart resume from the newest ingested batch, so
        # timers rebuilt from the database fire relative to where the world actually stopped.
        with SqlAlchemyUnitOfWork(app.state.session_factory) as uow:
            assert uow.session is not None
            resumed_at = latest_ingest_sim_time(uow.session)
        if resumed_at is not None:
            app.state.clock.advance_to(resumed_at)
            logger.info("clock.restored", sim_time=resumed_at.isoformat())

        def seed_users(session: Session) -> None:
            AccessService(
                session, app.state.clock, app.state.token_issuer, app.state.role_permissions
            ).seed_demo_users()

        with SqlAlchemyUnitOfWork(app.state.session_factory) as uow:
            assert uow.session is not None
            seed_users(uow.session)
            uow.commit()

        def run_reset_now() -> ResetReport:
            """The nightly reset (DOC 2 §2.7): restore the seeded world. Workers pause while it
            runs; in-memory state that belongs to the old world is dropped with it."""
            with app.state.maintenance:
                report = reset_database(
                    engine,
                    app.state.session_factory,
                    app.state.clock,
                    settings.seed_file,
                    seed_users,
                )
                app.state.registry_cache.invalidate()
                if settings.sim_control_url:
                    try:
                        httpx.post(
                            f"{settings.sim_control_url.rstrip('/')}/reset", json={}, timeout=10
                        )
                    except httpx.HTTPError:
                        logger.warning("reset.world_sim_unreachable")
            return report

        app.state.run_reset_now = run_reset_now

        auto_pause = AutoPause(
            app.state.stream_gate, settings.sim_control_url, settings.effective_auto_pause_after_min
        )
        app.state.auto_pause = auto_pause

        async def auto_pause_worker() -> None:
            while True:
                await asyncio.sleep(AUTO_PAUSE_POLL_S)
                try:
                    await asyncio.to_thread(auto_pause.tick)
                except Exception:
                    logger.exception("auto_pause.tick_failed")

        reset_at = settings.effective_nightly_reset_at

        async def nightly_reset_worker() -> None:
            assert reset_at is not None
            while True:
                await asyncio.sleep(seconds_until(reset_at, SystemClock().now()))
                try:
                    await asyncio.to_thread(run_reset_now)
                except Exception:
                    logger.exception("reset.failed")

        extra_tasks = []
        if auto_pause.enabled:
            extra_tasks.append(asyncio.create_task(auto_pause_worker()))
        if reset_at is not None:
            extra_tasks.append(asyncio.create_task(nightly_reset_worker()))

        # Complaints a crash left unprocessed are retried at boot (DOC 3 M2)
        try:
            run_retry_once()
        except Exception:
            logger.exception("retry.boot.failed")

        yield

        # Shutdown: stop the outbox worker and timer driver, then signal SSE subscribers to close
        for task in (worker, timers, *extra_tasks):
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        app.state.sse_hub.close_all()

    app = FastAPI(title="NAKABANDI API", version="0.0.0", lifespan=lifespan)
    app.add_exception_handler(DomainError, _domain_error_handler)
    app.add_middleware(LatencyMiddleware)
    app.include_router(intake_router, prefix="/api/v1")
    app.include_router(geo_router, prefix="/api/v1")
    app.include_router(analytics_router, prefix="/api/v1")
    app.include_router(access_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")
    app.include_router(alerts_router, prefix="/api/v1")
    app.include_router(actions_router, prefix="/api/v1")
    app.include_router(outcomes_router, prefix="/api/v1")
    app.include_router(integrations_router, prefix="/api/v1")
    app.include_router(outbox_router, prefix="/api/v1")
    app.include_router(stream_router, prefix="/api/v1")
    app.include_router(ops_router, prefix="/api/v1")
    app.include_router(casework_router, prefix="/api/v1")

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
