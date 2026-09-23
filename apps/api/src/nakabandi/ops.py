"""GET /system/metrics (DOC 2 §2.4, §2.7): what the Ops panel shows: throughput, stage latencies,
outbox depth, delivery failures. Wall-clock and process-local: it describes how the API is
running, not the simulated world. Requires SIM_CONTROL (demo_operator and admin)."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request
from nakabandi_contracts.enums import Permission
from pydantic import BaseModel

from nakabandi.access import Principal, authorize, get_principal
from nakabandi.shared import LatencySummary, SqlAlchemyUnitOfWork, SystemClock

router = APIRouter(prefix="/system", tags=["system"])

STAGE_PREFIX = "stage."


class LatencyView(BaseModel):
    count: int
    p50_ms: float
    p95_ms: float
    max_ms: float


class MetricsResponse(BaseModel):
    generated_at: str
    uptime_s: float
    events_per_second: float
    complaints_per_second: float
    stages: dict[str, LatencyView]
    http: LatencyView
    outbox: dict[str, int]
    delivery_failures: int
    streams: dict[str, int]


def _view(s: LatencySummary) -> LatencyView:
    return LatencyView(count=s.count, p50_ms=s.p50_ms, p95_ms=s.p95_ms, max_ms=s.max_ms)


@router.get("/metrics", response_model=MetricsResponse)
def system_metrics(
    request: Request, principal: Principal = Depends(get_principal)
) -> MetricsResponse:
    state = request.app.state
    authorize(principal, Permission.SIM_CONTROL, state.role_permissions)
    metrics = state.metrics
    now = SystemClock().now()
    with SqlAlchemyUnitOfWork(state.session_factory) as uow:
        assert uow.session is not None
        outbox = state.alert_service_factory(uow.session).outbox_stats()
    return MetricsResponse(
        generated_at=now.isoformat(),
        uptime_s=(now - state.started_at).total_seconds(),
        events_per_second=metrics.rate("events"),
        complaints_per_second=metrics.rate("complaints"),
        stages={
            name[len(STAGE_PREFIX) :]: _view(metrics.latency(name))
            for name in metrics.latency_names()
            if name.startswith(STAGE_PREFIX)
        },
        http=_view(metrics.latency("http.request")),
        outbox=outbox,
        delivery_failures=outbox.get("failed", 0) + outbox.get("dead", 0),
        streams={
            "open": state.stream_gate.open_streams,
            "max": state.stream_gate.max_streams,
        },
    )


class LatencyMiddleware:
    """Records how long each HTTP request took, as `http.request`. Plain ASGI, not
    BaseHTTPMiddleware: a long-lived SSE response must not be buffered or held open by it, and
    /stream is skipped anyway (its "latency" is the connection's lifetime)."""

    def __init__(self, app) -> None:  # noqa: ANN001
        self._app = app

    async def __call__(self, scope, receive, send) -> None:  # noqa: ANN001
        if scope["type"] != "http" or scope["path"].endswith("/stream"):
            await self._app(scope, receive, send)
            return
        start = time.perf_counter()
        try:
            await self._app(scope, receive, send)
        finally:
            metrics = getattr(scope["app"].state, "metrics", None)
            if metrics is not None:
                metrics.observe("http.request", time.perf_counter() - start)
