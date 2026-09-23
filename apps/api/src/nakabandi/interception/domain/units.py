"""units.py — UnitIndex: BallTree over law-enforcement unit positions (DOC 3 M6).

Pure domain; no I/O.  Mirrors geo.domain.spatial but specialised for units,
not registry locations, and adds the UnitEta result type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NamedTuple


class Unit(NamedTuple):
    id: str
    kind: str  # e.g. "police_station", "cyber_cell"
    lat: float
    lon: float


@dataclass(frozen=True)
class UnitEta:
    """A unit with its estimated travel time to a target location."""

    unit_id: str
    unit_kind: str
    eta_min: float


class UnitIndex:
    """BallTree-backed index of law-enforcement unit positions.

    Build once on startup from the loaded unit registry; rebuild if units change.
    """

    def __init__(self, units: list[Unit], tree: Any, radians_coords: Any) -> None:
        self._units = units
        self._tree: Any = tree
        self._coords: Any = radians_coords

    @classmethod
    def build(cls, units: list[Unit]) -> UnitIndex:
        """Build a haversine BallTree from a list of Unit positions.

        Raises ValueError if units is empty (caller must handle NO_UNITS case).
        """
        if not units:
            raise ValueError("UnitIndex.build: cannot build an empty index — no units in registry")
        import numpy as np
        from sklearn.neighbors import BallTree  # type: ignore[import-untyped]

        coords = np.radians([[u.lat, u.lon] for u in units])
        tree = BallTree(coords, metric="haversine")
        return cls(units=units, tree=tree, radians_coords=coords)

    def nearest(self, lat: float, lon: float, k: int = 3) -> list[UnitEta]:
        """Return up to k nearest units with raw haversine distances only.

        The caller (HaversineEstimator) converts distance → ETA using policy.
        """
        import numpy as np

        k = min(k, len(self._units))
        query = np.radians([[lat, lon]])
        dists, indices = self._tree.query(query, k=k)
        return [
            UnitEta(
                unit_id=self._units[int(i)].id,
                unit_kind=self._units[int(i)].kind,
                eta_min=float(d) * 6_371.0,  # store raw km; HaversineEstimator adds factors
            )
            for d, i in zip(dists[0], indices[0], strict=False)
        ]

    def is_empty(self) -> bool:
        return len(self._units) == 0
