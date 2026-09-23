"""SQLAlchemy repositories for geo (DOC 3 LC-9: repositories obtain the active session from the
UnitOfWork; they never commit()). `merge()` gives idempotent upsert-by-primary-key semantics.
An IntegrityError (e.g. a location referencing an unknown bank_id) is caught per row inside a
SAVEPOINT so the rest of the registry snapshot still applies, and re-raised as a ValidationFailed
so the application layer can report it in `rejected[]` without knowing about SQLAlchemy.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nakabandi.geo.domain.entities import Bank, Cell, Location, Region, Unit
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
