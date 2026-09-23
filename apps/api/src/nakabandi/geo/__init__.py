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
from nakabandi.geo.domain.grid import cell_id_for
from nakabandi.geo.domain.spatial import GeoPoint, NearestResult, SpatialIndex
from nakabandi.geo.infrastructure.repositories import (
    SqlBankRepo,
    SqlCellRepo,
    SqlLocationRepo,
    SqlRegionRepo,
    SqlUnitRepo,
)

__all__ = [
    "GeoService",
    "ApplyRegistryResult",
    "GeoPoint",
    "NearestResult",
    "SpatialIndex",
    "cell_id_for",
]


class GeoService:
    """Façade: the ONLY geo object other modules may import.

    Constructed with either a SQLAlchemy Session (for intake/uow writes) or a repository
    object (for read queries).
    """

    def __init__(self, session_or_repo: Session | object) -> None:
        if isinstance(session_or_repo, Session):
            self._session: Session | None = session_or_repo
            self._apply_registry: ApplyRegistry | None = ApplyRegistry(
                bank_repo=SqlBankRepo(session_or_repo),
                region_repo=SqlRegionRepo(session_or_repo),
                cell_repo=SqlCellRepo(session_or_repo),
                location_repo=SqlLocationRepo(session_or_repo),
                unit_repo=SqlUnitRepo(session_or_repo),
            )
            self._repo: object = None
        else:
            self._session = None
            self._apply_registry = None
            self._repo = session_or_repo

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

    def spatial_index(self, version: str | None = None) -> SpatialIndex:
        """Return the BallTree index, rebuilding if the registry version changed."""
        if self._index is None or version != self._index_version:
            if self._repo is None:
                raise RuntimeError("GeoService has no repo configured for spatial index")
            points = self._repo.all_location_points()  # type: ignore[attr-defined]
            self._index = SpatialIndex.build(points)
            self._index_version = version
        return self._index

    def regions(self) -> list[dict]:  # type: ignore[type-arg]
        """Return the list of region dicts (id, name, state_id, lat, lon)."""
        if self._repo is None:
            raise RuntimeError("GeoService has no repo configured for regions")
        return self._repo.all_regions()  # type: ignore[attr-defined]

    def locations(
        self,
        *,
        bbox: tuple[float, float, float, float] | None = None,
        kind: str | None = None,
        bank_id: str | None = None,
        limit: int = 500,
    ) -> list[dict]:  # type: ignore[type-arg]
        """Return locations filtered by bounding box, kind, or bank."""
        if self._repo is None:
            raise RuntimeError("GeoService has no repo configured for locations")
        return self._repo.query_locations(  # type: ignore[attr-defined]
            bbox=bbox, kind=kind, bank_id=bank_id, limit=limit
        )
