"""GET /geo/regions and GET /geo/locations (DOC 3 M3 interfaces). Authenticated; restricted to the
principal's scope. Location points are served by bbox, kind and bank with a cap and keyset paging
(DOC 3 M3 PERFORMANCE: "Location points are served by bbox with a cap")."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from nakabandi_contracts.enums import LocationKind, Permission
from pydantic import BaseModel

from nakabandi.access import Principal, authorize, get_principal
from nakabandi.geo import GeoScope, GeoService, parse_bbox
from nakabandi.shared import SqlAlchemyUnitOfWork

router = APIRouter(prefix="/geo", tags=["geo"])

MAX_LOCATIONS_PER_REQUEST = 2000


class RegionView(BaseModel):
    id: str
    level: str
    name: str
    parent_id: str | None
    geojson_ref: str | None


class LocationView(BaseModel):
    id: str
    kind: str
    bank_id: str
    lat: float
    lon: float
    district_id: str
    cell_id: str
    display_name: str
    area_type: str


class LocationPage(BaseModel):
    items: list[LocationView]
    next_cursor: str | None


def geo_scope_of(principal: Principal) -> GeoScope:
    s = principal.scope
    return GeoScope(state_id=s.state_id, district_id=s.district_id, bank_id=s.bank_id)


def _uow(request: Request) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(request.app.state.session_factory)


@router.get("/regions", response_model=list[RegionView])
def list_regions(
    request: Request, principal: Principal = Depends(get_principal)
) -> list[RegionView]:
    authorize(principal, Permission.VIEW_ALERTS, request.app.state.role_permissions)
    with _uow(request) as uow:
        assert uow.session is not None
        regions = GeoService(uow.session).regions(geo_scope_of(principal))
    return [RegionView(**vars_of(r)) for r in regions]


@router.get("/locations", response_model=LocationPage)
def list_locations(
    request: Request,
    bbox: str | None = None,
    kind: LocationKind | None = None,
    bank_id: str | None = None,
    cursor: str | None = None,
    limit: int = 500,
    principal: Principal = Depends(get_principal),
) -> LocationPage:
    authorize(principal, Permission.VIEW_ALERTS, request.app.state.role_permissions)
    limit = max(1, min(limit, MAX_LOCATIONS_PER_REQUEST))
    with _uow(request) as uow:
        assert uow.session is not None
        rows = GeoService(uow.session).locations(
            geo_scope_of(principal),
            bbox=parse_bbox(bbox) if bbox else None,
            kind=kind.value if kind else None,
            bank_id=bank_id,
            after_id=cursor,
            limit=limit + 1,
        )
    has_more = len(rows) > limit
    rows = rows[:limit]
    return LocationPage(
        items=[
            LocationView(
                id=r.id,
                kind=r.kind,
                bank_id=r.bank_id,
                lat=r.lat,
                lon=r.lon,
                district_id=r.district_id,
                cell_id=r.cell_id,
                display_name=r.display_name,
                area_type=r.area_type,
            )
            for r in rows
        ],
        next_cursor=rows[-1].id if has_more and rows else None,
    )


def vars_of(region) -> dict:  # noqa: ANN001
    return {
        "id": region.id,
        "level": region.level,
        "name": region.name,
        "parent_id": region.parent_id,
        "geojson_ref": region.geojson_ref,
    }
