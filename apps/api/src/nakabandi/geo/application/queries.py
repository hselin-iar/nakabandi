"""QueryRegions and QueryLocations (DOC 3 M3 geo application).

Scope arrives as plain ids (state, district, bank), never as an access Principal: the caller
(the router or the analytics adapter) maps a principal's scope, with access.authorize's
precedence, and geo only filters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from nakabandi.geo.domain.entities import Cell, Location, Region
from nakabandi.shared import ValidationFailed


@dataclass(frozen=True, slots=True)
class GeoScope:
    state_id: str | None = None
    district_id: str | None = None
    bank_id: str | None = None


class GeoReadRepo(Protocol):
    def all_regions(self) -> list[Region]: ...
    def all_cells(self) -> list[Cell]: ...
    def district_ids_of_state(self, state_id: str) -> list[str]: ...
    def query_locations(
        self,
        *,
        bbox: tuple[float, float, float, float] | None = None,
        kind: str | None = None,
        bank_id: str | None = None,
        district_ids: list[str] | None = None,
        after_id: str | None = None,
        limit: int = 500,
    ) -> list[Location]: ...


def parse_bbox(text: str) -> tuple[float, float, float, float]:
    """`min_lon,min_lat,max_lon,max_lat` -> a validated tuple (422 GEO_BBOX_INVALID otherwise)."""
    try:
        min_lon, min_lat, max_lon, max_lat = (float(p) for p in text.split(","))
    except ValueError as exc:
        raise ValidationFailed(
            "GEO_BBOX_INVALID", "bbox must be min_lon,min_lat,max_lon,max_lat"
        ) from exc
    if not (min_lon <= max_lon and min_lat <= max_lat):
        raise ValidationFailed("GEO_BBOX_INVALID", "bbox minimums must not exceed maximums")
    return min_lon, min_lat, max_lon, max_lat


class QueryRegions:
    def __init__(self, repo: GeoReadRepo) -> None:
        self._repo = repo

    def run(self, scope: GeoScope) -> list[Region]:
        """A district-scoped principal sees their district and its state; a state-scoped one their
        state and its districts; anyone else, everything. A bank scope sees all regions (they
        carry no data; the alerts and locations are what a bank scope restricts)."""
        regions = self._repo.all_regions()
        if scope.district_id is not None:
            district = next((r for r in regions if r.id == scope.district_id), None)
            keep = {scope.district_id}
            if district is not None and district.parent_id is not None:
                keep.add(district.parent_id)
            return [r for r in regions if r.id in keep]
        if scope.state_id is not None and scope.bank_id is None:
            return [r for r in regions if r.id == scope.state_id or r.parent_id == scope.state_id]
        return regions


class QueryLocations:
    def __init__(self, repo: GeoReadRepo) -> None:
        self._repo = repo

    def run(
        self,
        scope: GeoScope,
        *,
        bbox: tuple[float, float, float, float] | None = None,
        kind: str | None = None,
        bank_id: str | None = None,
        after_id: str | None = None,
        limit: int = 500,
    ) -> list[Location]:
        """Restricted like access.authorize: a bank scope sees only its own bank's locations, a
        district scope only its district's, a state scope only its state's. A requested bank_id
        can narrow further but never widen."""
        if scope.bank_id is not None:
            bank_id = scope.bank_id
        district_ids: list[str] | None = None
        if scope.bank_id is None and scope.district_id is not None:
            district_ids = [scope.district_id]
        elif scope.bank_id is None and scope.state_id is not None:
            district_ids = self._repo.district_ids_of_state(scope.state_id)
        return self._repo.query_locations(
            bbox=bbox,
            kind=kind,
            bank_id=bank_id,
            district_ids=district_ids,
            after_id=after_id,
            limit=limit,
        )
