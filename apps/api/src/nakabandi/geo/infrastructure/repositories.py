"""SQLAlchemy repositories for geo (DOC 3 LC-9: repositories obtain the active session from the
UnitOfWork; they never commit()). `merge()` gives idempotent upsert-by-primary-key semantics.
An IntegrityError (e.g. a location referencing an unknown bank_id) is caught per row inside a
SAVEPOINT so the rest of the registry snapshot still applies, and re-raised as a ValidationFailed
so the application layer can report it in `rejected[]` without knowing about SQLAlchemy.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nakabandi.geo.domain.entities import Bank, Cell, Location, Region, Unit
from nakabandi.geo.domain.spatial import GeoPoint
from nakabandi.geo.infrastructure.models import (
    BankModel,
    CellModel,
    LocationModel,
    RegionModel,
    UnitModel,
)
from nakabandi.shared import ValidationFailed


def _upsert(session: Session, model: object, code: str) -> None:
    try:
        with session.begin_nested():
            session.merge(model)
    except IntegrityError as exc:
        raise ValidationFailed(code, str(exc.orig)) from exc


class SqlBankRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, bank: Bank) -> None:
        _upsert(
            self._session,
            BankModel(id=bank.id, name=bank.name, short_code=bank.short_code),
            "GEO_BANK_INTEGRITY",
        )


class SqlRegionRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, region: Region) -> None:
        _upsert(
            self._session,
            RegionModel(
                id=region.id,
                level=region.level,
                name=region.name,
                parent_id=region.parent_id,
                geojson_ref=region.geojson_ref,
            ),
            "GEO_REGION_INTEGRITY",
        )


class SqlCellRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, cell: Cell) -> None:
        _upsert(
            self._session,
            CellModel(
                id=cell.id,
                grid_km=cell.grid_km,
                row=cell.row,
                col=cell.col,
                district_id=cell.district_id,
                centroid_lat=cell.centroid_lat,
                centroid_lon=cell.centroid_lon,
            ),
            "GEO_CELL_INTEGRITY",
        )


class SqlLocationRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, location: Location) -> None:
        _upsert(
            self._session,
            LocationModel(
                id=location.id,
                kind=location.kind,
                bank_id=location.bank_id,
                lat=location.lat,
                lon=location.lon,
                district_id=location.district_id,
                cell_id=location.cell_id,
                source=location.source,
                display_name=location.display_name,
                area_type=location.area_type,
                activity_index=location.activity_index,
            ),
            "GEO_LOCATION_INTEGRITY",
        )

    def exists(self, location_id: str) -> bool:
        return self._session.get(LocationModel, location_id) is not None


class SqlUnitRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, unit: Unit) -> None:
        _upsert(
            self._session,
            UnitModel(
                id=unit.id,
                kind=unit.kind,
                district_id=unit.district_id,
                lat=unit.lat,
                lon=unit.lon,
                status=unit.status,
                speed_profile=unit.speed_profile,
            ),
            "GEO_UNIT_INTEGRITY",
        )


# ---------------------------------------------------------------------------
# Read side (DOC 3 M3: QueryRegions, QueryLocations, the analytics catalog, the spatial index)
# ---------------------------------------------------------------------------


def _region(row: RegionModel) -> Region:
    return Region(
        id=row.id,
        level=row.level,
        name=row.name,
        parent_id=row.parent_id,
        geojson_ref=row.geojson_ref,
    )


def _cell(row: CellModel) -> Cell:
    return Cell(
        id=row.id,
        grid_km=row.grid_km,
        row=row.row,
        col=row.col,
        district_id=row.district_id,
        centroid_lat=row.centroid_lat,
        centroid_lon=row.centroid_lon,
    )


def _location(row: LocationModel) -> Location:
    return Location(
        id=row.id,
        kind=row.kind,
        bank_id=row.bank_id,
        lat=row.lat,
        lon=row.lon,
        district_id=row.district_id,
        cell_id=row.cell_id,
        source=row.source,
        display_name=row.display_name,
        area_type=row.area_type,
        activity_index=row.activity_index,
    )


class SqlGeoReadRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def all_regions(self) -> list[Region]:
        return [
            _region(r) for r in self._session.scalars(select(RegionModel).order_by(RegionModel.id))
        ]

    def all_cells(self) -> list[Cell]:
        return [_cell(r) for r in self._session.scalars(select(CellModel).order_by(CellModel.id))]

    def district_ids_of_state(self, state_id: str) -> list[str]:
        return list(
            self._session.scalars(select(RegionModel.id).where(RegionModel.parent_id == state_id))
        )

    def query_locations(
        self,
        *,
        bbox: tuple[float, float, float, float] | None = None,
        kind: str | None = None,
        bank_id: str | None = None,
        district_ids: list[str] | None = None,
        after_id: str | None = None,
        limit: int = 500,
    ) -> list[Location]:
        """Ordered by id (a keyset for paging); bbox = (min_lon, min_lat, max_lon, max_lat)."""
        q = select(LocationModel)
        if bbox is not None:
            min_lon, min_lat, max_lon, max_lat = bbox
            q = q.where(
                LocationModel.lon >= min_lon,
                LocationModel.lon <= max_lon,
                LocationModel.lat >= min_lat,
                LocationModel.lat <= max_lat,
            )
        if kind is not None:
            q = q.where(LocationModel.kind == kind)
        if bank_id is not None:
            q = q.where(LocationModel.bank_id == bank_id)
        if district_ids is not None:
            q = q.where(LocationModel.district_id.in_(district_ids))
        if after_id is not None:
            q = q.where(LocationModel.id > after_id)
        q = q.order_by(LocationModel.id).limit(limit)
        return [_location(r) for r in self._session.scalars(q)]

    def all_location_points(self) -> list[GeoPoint]:
        return [
            GeoPoint(id=r.id, lat=r.lat, lon=r.lon)
            for r in self._session.scalars(select(LocationModel).order_by(LocationModel.id))
        ]
