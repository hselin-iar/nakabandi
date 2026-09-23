"""GET /analytics/heatmap, /analytics/timeseries, /analytics/live-metrics (DOC 3 M3 interfaces).

The heatmap answers with an ETag built from the rollup version and everything else the answer
depends on, so an unchanged map is a 304. Invalid filters are a 422 with field details; an empty
result is an empty list, never an error."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from nakabandi.access import Principal, get_principal
from nakabandi.analytics import AnalyticsService, HeatFilters, Layer, Level
from nakabandi.geo import parse_bbox
from nakabandi.shared import SqlAlchemyUnitOfWork, to_sim_time
from nakabandi.wiring import GeoCatalogAdapter

router = APIRouter(prefix="/analytics", tags=["analytics"])


class HeatCellView(BaseModel):
    id: str
    kind: str
    name: str | None
    lat: float
    lon: float
    value: float
    alert_count: int


class LegendView(BaseModel):
    min: float
    max: float
    unit: str
    note: str


class HeatmapResponse(BaseModel):
    """LC-4 HeatmapResponse."""

    layer: str
    level: str
    generated_at: str
    version: int
    cells: list[HeatCellView]
    suppressed_count: int
    legend: LegendView


class TimePointView(BaseModel):
    hour: str
    value: float
    alert_count: int


class TimeseriesResponse(BaseModel):
    layer: str
    from_: str
    to: str
    version: int
    points: list[TimePointView]


class LiveMetricsResponse(BaseModel):
    generated_at: str
    version: int
    window_hours: float
    alert_count: int
    expected_mass: float
    active_locations: int


def _filters(
    layer: Layer = Layer.LIVE,
    level: Level = Level.CELL,
    from_: datetime | None = None,
    to: datetime | None = None,
    state: str | None = None,
    district: str | None = None,
    category: str | None = None,
    amount_band: int | None = None,
    min_confidence: float | None = None,
    bbox: str | None = None,
) -> HeatFilters:
    return HeatFilters(
        layer=layer,
        level=level,
        from_=to_sim_time(from_) if from_ else None,
        to=to_sim_time(to) if to else None,
        state=state,
        district=district,
        category=category,
        amount_band=amount_band,
        min_confidence=min_confidence,
        bbox=parse_bbox(bbox) if bbox else None,
    )


def _service(request: Request, session) -> AnalyticsService:  # noqa: ANN001
    st = request.app.state
    return AnalyticsService(
        session,
        policy=st.policy,
        clock=st.clock,
        role_permissions=st.role_permissions,
        catalog=GeoCatalogAdapter(session),
    )


@router.get("/heatmap", response_model=HeatmapResponse)
def heatmap(
    request: Request,
    response: Response,
    from_: datetime | None = None,
    layer: Layer = Layer.LIVE,
    level: Level = Level.CELL,
    to: datetime | None = None,
    state: str | None = None,
    district: str | None = None,
    category: str | None = None,
    amount_band: int | None = None,
    min_confidence: float | None = None,
    bbox: str | None = None,
    principal: Principal = Depends(get_principal),
) -> Response | HeatmapResponse:
    filters = _filters(
        layer, level, from_, to, state, district, category, amount_band, min_confidence, bbox
    )
    with SqlAlchemyUnitOfWork(request.app.state.session_factory) as uow:
        assert uow.session is not None
        svc = _service(request, uow.session)
        result = svc.heatmap(filters, principal)  # authorizes and validates first
        etag = svc.etag(filters, principal)
    headers = {"ETag": etag, "Cache-Control": "no-cache"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    response.headers.update(headers)
    return HeatmapResponse(
        layer=result.layer,
        level=result.level,
        generated_at=result.generated_at.isoformat(),
        version=result.version,
        cells=[HeatCellView(**vars_of(c)) for c in result.cells],
        suppressed_count=result.suppressed_count,
        legend=LegendView(
            min=result.legend.min,
            max=result.legend.max,
            unit=result.legend.unit,
            note=result.legend.note,
        ),
    )


@router.get("/timeseries", response_model=TimeseriesResponse)
def timeseries(
    request: Request,
    from_: datetime | None = None,
    layer: Layer = Layer.LIVE,
    to: datetime | None = None,
    state: str | None = None,
    district: str | None = None,
    category: str | None = None,
    amount_band: int | None = None,
    min_confidence: float | None = None,
    bbox: str | None = None,
    principal: Principal = Depends(get_principal),
) -> TimeseriesResponse:
    filters = _filters(
        layer, Level.CELL, from_, to, state, district, category, amount_band, min_confidence, bbox
    )
    with SqlAlchemyUnitOfWork(request.app.state.session_factory) as uow:
        assert uow.session is not None
        result = _service(request, uow.session).timeseries(filters, principal)
    return TimeseriesResponse(
        layer=result.layer,
        from_=result.from_.isoformat(),
        to=result.to.isoformat(),
        version=result.version,
        points=[
            TimePointView(hour=p.hour.isoformat(), value=p.value, alert_count=p.alert_count)
            for p in result.points
        ],
    )


@router.get("/live-metrics", response_model=LiveMetricsResponse)
def live_metrics(
    request: Request, principal: Principal = Depends(get_principal)
) -> LiveMetricsResponse:
    with SqlAlchemyUnitOfWork(request.app.state.session_factory) as uow:
        assert uow.session is not None
        m = _service(request, uow.session).live_metrics(principal)
    return LiveMetricsResponse(
        generated_at=m.generated_at.isoformat(),
        version=m.version,
        window_hours=m.window_hours,
        alert_count=m.alert_count,
        expected_mass=m.expected_mass,
        active_locations=m.active_locations,
    )


def vars_of(cell) -> dict:  # noqa: ANN001
    return {
        "id": cell.id,
        "kind": cell.kind,
        "name": cell.name,
        "lat": cell.lat,
        "lon": cell.lon,
        "value": cell.value,
        "alert_count": cell.alert_count,
    }
