"""/ingest/* routers (DOC 2 §2.4). Routers only parse the request, resolve the module facade
and call one use case (DOC 3 M2 agent prompt hint: "routers only parse and call one use case");
no business logic here. Each route commits the UnitOfWork only after the facade call returns.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Depends, Request
from nakabandi_contracts.ingest import (
    CashOutObservationBatch,
    ComplaintBatch,
    HopBatch,
    IngestResponse,
    RegistryUpdate,
    Tick,
)

from nakabandi.alerting import SseEvent
from nakabandi.intake import IngestService
from nakabandi.intake.interfaces.deps import require_service_key
from nakabandi.shared import SimClock, SqlAlchemyUnitOfWork

router = APIRouter(prefix="/ingest", tags=["ingest"], dependencies=[Depends(require_service_key)])


def get_uow(request: Request) -> Iterator[SqlAlchemyUnitOfWork]:
    uow = SqlAlchemyUnitOfWork(request.app.state.session_factory)
    with uow:
        yield uow


def get_clock(request: Request) -> SimClock:
    return request.app.state.clock


def get_ingest_service(
    request: Request,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
    clock: SimClock = Depends(get_clock),
) -> IngestService:
    assert uow.session is not None
    # The bus is per unit of work, so an ObservationIngested subscriber (ReconcileOutcome)
    # writes on this request's own session.
    bus = request.app.state.event_bus_factory(uow.session)
    hooks = request.app.state.ingest_hooks_factory(uow.session, bus)
    return IngestService(uow.session, clock, bus, hooks)


@router.post("/registry")
def post_registry(
    update: RegistryUpdate,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
    service: IngestService = Depends(get_ingest_service),
) -> IngestResponse:
    response = service.ingest_registry(update)
    uow.commit()
    return response


@router.post("/complaints")
def post_complaints(
    batch: ComplaintBatch,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
    service: IngestService = Depends(get_ingest_service),
) -> IngestResponse:
    response = service.ingest_complaints(batch)
    uow.commit()
    return response


@router.post("/hops")
def post_hops(
    batch: HopBatch,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
    service: IngestService = Depends(get_ingest_service),
) -> IngestResponse:
    response = service.ingest_hops(batch)
    uow.commit()
    return response


@router.post("/cashout-observations")
@router.post("/cashouts")
def post_cashout_observations(
    batch: CashOutObservationBatch,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
    service: IngestService = Depends(get_ingest_service),
) -> IngestResponse:
    response = service.ingest_observations(batch)
    uow.commit()
    return response


@router.post("/tick")
def post_tick(
    tick: Tick,
    request: Request,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
    service: IngestService = Depends(get_ingest_service),
) -> IngestResponse:
    response = service.advance_clock(tick)
    uow.commit()
    # sim.time has no alert_id/scope: LC-5 sends it to every connected subscriber, same as
    # analytics' heat.version. This is the only source of the SSE event useStream.tsx listens
    # for to drive the on-screen sim clock; the :heartbeat comment carries no payload.
    request.app.state.sse_hub.publish(
        SseEvent(name="sim.time", data={"sim_time": response.sim_time.isoformat()})
    )
    return response
