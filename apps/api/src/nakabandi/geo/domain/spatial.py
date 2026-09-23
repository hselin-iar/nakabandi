"""spatial.py — SpatialIndex: BallTree-backed nearest-neighbour and radius search (DOC 3 M3).

Uses scikit-learn's BallTree with the haversine metric.  Offline-safe: no network calls.

Usage
-----
    index = SpatialIndex.build(points)   # points: list of (id, lat, lon)
    neighbours = index.nearest(lat, lon, k=3)
    within = index.within_radius(lat, lon, km=10.0)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    pass


class GeoPoint(NamedTuple):
    id: str
    lat: float
    lon: float


@dataclass(frozen=True)
class NearestResult:
    point: GeoPoint
    distance_km: float


class SpatialIndex:
    """BallTree wrapper for haversine nearest-neighbour and radius queries.

    Build once per registry version; re-build when the registry changes.
    """

    def __init__(self, points: list[GeoPoint], tree: Any, radians_coords: Any) -> None:
        self._points = points
        self._tree: Any = tree  # sklearn BallTree (not type-stubbed)
        self._coords: Any = radians_coords  # numpy array (N, 2) in radians

    @classmethod
    def build(cls, points: list[GeoPoint]) -> SpatialIndex:
        """Build a BallTree from a list of GeoPoints.

        Raises ImportError if scikit-learn is not available.
        Raises ValueError if points is empty.
        """
        if not points:
            raise ValueError("SpatialIndex.build: cannot build an empty index")
        import numpy as np
        from sklearn.neighbors import BallTree  # type: ignore[import-untyped]

        coords = np.radians([[p.lat, p.lon] for p in points])
        tree = BallTree(coords, metric="haversine")
        return cls(points=points, tree=tree, radians_coords=coords)

    def nearest(self, lat: float, lon: float, k: int = 3) -> list[NearestResult]:
        """Return the k nearest GeoPoints with their haversine distances in km."""
        import numpy as np

        k = min(k, len(self._points))
        query = np.radians([[lat, lon]])
        dists, indices = self._tree.query(query, k=k)
        return [
            NearestResult(
                point=self._points[int(i)],
                distance_km=float(d) * 6_371.0,
            )
            for d, i in zip(dists[0], indices[0], strict=False)
        ]

    def within_radius(self, lat: float, lon: float, km: float) -> list[NearestResult]:
        """Return all GeoPoints within km kilometres, sorted by distance."""
        import numpy as np

        radius_rad = km / 6_371.0
        query = np.radians([[lat, lon]])
        indices, dists = self._tree.query_radius(query, r=radius_rad, return_distance=True)
        results = [
            NearestResult(
                point=self._points[int(i)],
                distance_km=float(d) * 6_371.0,
            )
            for i, d in zip(indices[0], dists[0], strict=False)
        ]
        return sorted(results, key=lambda r: r.distance_km)
