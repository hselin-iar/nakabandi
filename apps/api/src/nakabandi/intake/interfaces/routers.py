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
    uow: SqlAlchemyUnitOfWork = Depends(get_uow), clock: SimClock = Depends(get_clock)
) -> IngestService:
    assert uow.session is not None
    return IngestService(uow.session, clock)


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
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
    service: IngestService = Depends(get_ingest_service),
) -> IngestResponse:
    response = service.advance_clock(tick)
    uow.commit()
    return response
