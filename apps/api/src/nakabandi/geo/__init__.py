"""Public facade of the geo module: what other modules may import (DOC 3 M3).

Exports:
  GeoService       — regions(), locations(), cell_of(), spatial_index()
  GeoPoint, NearestResult  — value objects
  cell_id_for      — pure helper (used by analytics directly, no service overhead)
"""

from __future__ import annotations

from nakabandi.geo.domain.grid import cell_id_for
from nakabandi.geo.domain.spatial import GeoPoint, NearestResult, SpatialIndex

__all__ = [
    "GeoService",
    "GeoPoint",
    "NearestResult",
    "SpatialIndex",
    "cell_id_for",
]


class GeoService:
    """Façade: the ONLY geo object other modules may import.

    Wraps the domain functions and the repository behind one entry point.
    The BallTree index is built lazily and cached until the registry version
    changes.
    """

    def __init__(self, repo: object) -> None:
        # `repo` is a GeoRepo instance (defined in geo/infrastructure/repositories.py).
        # Typed as `object` here to avoid importing infrastructure from the facade.
        self._repo = repo
        self._index: SpatialIndex | None = None
        self._index_version: str | None = None

    # ------------------------------------------------------------------
    # M3 public API
    # ------------------------------------------------------------------

    def cell_of(self, lat: float, lon: float, grid_km: float = 5.0) -> str:
        """Return the grid cell id for a coordinate pair."""
        return cell_id_for(lat, lon, grid_km)

    def spatial_index(self, version: str | None = None) -> SpatialIndex:
        """Return the BallTree index, rebuilding if the registry version changed."""
        if self._index is None or version != self._index_version:
            points = self._repo.all_location_points()  # type: ignore[attr-defined]
            self._index = SpatialIndex.build(points)
            self._index_version = version
        return self._index

    def regions(self) -> list[dict]:  # type: ignore[type-arg]
        """Return the list of region dicts (id, name, state_id, lat, lon)."""
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
        return self._repo.query_locations(  # type: ignore[attr-defined]
            bbox=bbox, kind=kind, bank_id=bank_id, limit=limit
        )
