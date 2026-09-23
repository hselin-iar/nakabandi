"""Public facade of the geo module: what other modules may import (DOC 3).

GeoService is constructed on the caller's active SQLAlchemy session, so an IngestRegistry batch
and its ApplyRegistry effects share one transaction/UnitOfWork (LC-9). Only `apply_registry` is
built at Step A3; `regions`, `locations`, `cell_of` and `spatial_index` (DOC 3 M3) land at
Step A9 (Analytics Read Model & Heatmap API) alongside the geo query endpoints.

Exports:
  GeoService               — apply_registry(), cell_of(), spatial_index(), regions(), locations()
  ApplyRegistryResult      — result of applying registry snapshot
  GeoPoint, NearestResult  — value objects
  SpatialIndex             — spatial index structure
  cell_id_for              — pure helper (used by analytics directly, no service overhead)
"""

from __future__ import annotations

from typing import Any

from nakabandi_contracts.ingest import RegistryLocation, RegistryUnit
from sqlalchemy.orm import Session

from nakabandi.geo.application.apply_registry import ApplyRegistry, ApplyRegistryResult
from nakabandi.geo.application.queries import (
    GeoScope,
    QueryLocations,
    QueryRegions,
    parse_bbox,
)
from nakabandi.geo.domain.entities import Cell, Location, Region
from nakabandi.geo.domain.grid import cell_id_for
from nakabandi.geo.domain.spatial import GeoPoint, NearestResult, SpatialIndex
from nakabandi.geo.infrastructure.repositories import (
    SqlBankRepo,
    SqlCellRepo,
    SqlGeoReadRepo,
    SqlLocationRepo,
    SqlRegionRepo,
    SqlUnitRepo,
)
from nakabandi.geo.infrastructure.scope_lookup import LocationScope, LocationScopeLookup

__all__ = [
    "GeoService",
    "GeoScope",
    "Region",
    "Cell",
    "Location",
    "parse_bbox",
    "LocationScope",
    "LocationScopeLookup",
    "ApplyRegistryResult",
    "GeoPoint",
    "NearestResult",
    "SpatialIndex",
    "cell_id_for",
]


class GeoService:
    """Façade: the ONLY geo object other modules may import.

    Constructed on the caller's SQLAlchemy Session, so writes (apply_registry) and reads
    (regions, cells, locations, spatial_index) share the caller's unit of work.
    """

    def __init__(self, session: Session) -> None:
        self._session: Session | None = session
        self._apply_registry: ApplyRegistry | None = ApplyRegistry(
            bank_repo=SqlBankRepo(session),
            region_repo=SqlRegionRepo(session),
            cell_repo=SqlCellRepo(session),
            location_repo=SqlLocationRepo(session),
            unit_repo=SqlUnitRepo(session),
        )
        self._index: SpatialIndex | None = None
        self._index_version: str | None = None

    def apply_registry(
        self,
        *,
        banks: list[dict[str, Any]],
        regions: list[dict[str, Any]],
        cells: list[dict[str, Any]],
        locations: list[RegistryLocation],
        units: list[RegistryUnit],
    ) -> ApplyRegistryResult:
        if self._apply_registry is None:
            raise RuntimeError("GeoService was not initialized with a SQLAlchemy session")
        return self._apply_registry.run(
            banks=banks, regions=regions, cells=cells, locations=locations, units=units
        )

    # ------------------------------------------------------------------
    # M3 public API
    # ------------------------------------------------------------------

    def cell_of(self, lat: float, lon: float, grid_km: float = 5.0) -> str:
        """Return the grid cell id for a coordinate pair."""
        return cell_id_for(lat, lon, grid_km)

    def _read(self) -> SqlGeoReadRepo:
        if self._session is None:
            raise RuntimeError("GeoService was not initialized with a SQLAlchemy session")
        return SqlGeoReadRepo(self._session)

    def spatial_index(self, version: str | None = None) -> SpatialIndex:
        """The BallTree over every registered location, rebuilt when `version` changes."""
        if self._index is None or version != self._index_version:
            self._index = SpatialIndex.build(self._read().all_location_points())
            self._index_version = version
        return self._index

    def regions(self, scope: GeoScope | None = None) -> list[Region]:
        return QueryRegions(self._read()).run(scope or GeoScope())

    def cells(self) -> list[Cell]:
        return self._read().all_cells()

    def locations(
        self,
        scope: GeoScope | None = None,
        *,
        bbox: tuple[float, float, float, float] | None = None,
        kind: str | None = None,
        bank_id: str | None = None,
        after_id: str | None = None,
        limit: int = 500,
    ) -> list[Location]:
        """Locations inside `scope`, optionally narrowed by bbox / kind / bank, ordered by id."""
        return QueryLocations(self._read()).run(
            scope or GeoScope(),
            bbox=bbox,
            kind=kind,
            bank_id=bank_id,
            after_id=after_id,
            limit=limit,
        )
