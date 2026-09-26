"""candidates.py — generate_candidates(ctx, index, policy) -> list[Candidate] (DOC 3 M2).

Builds the candidate location set for one complaint:
  1. Locations within policy.candidates.radius_km of the home branch.
  2. Locations within radius_km of the cluster centroid.
  3. Top cells by cluster cashout history (same-cell locations).
  4. Same-bank locations in the home district.
  5. Merge, de-duplicate, cap at policy.candidates.max by ascending distance.

Widening: if the set is empty, multiply the radius by policy.candidates.widen_factor and retry.
Pure domain function — no I/O.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from nakabandi.forecast.domain.types import Candidate, ClusterContext
from nakabandi.shared import Id, Policy


@dataclass(frozen=True)
class LocationInfo:
    """Minimal registry info the candidate generator needs per location."""

    id: Id
    cell_id: Id
    district_id: Id
    bank_id: str
    lat: float
    lon: float
    channel: str
    activity_index: float


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.asin(math.sqrt(a))


def _within_radius(
    locations: list[LocationInfo], lat: float, lon: float, radius_km: float
) -> list[tuple[LocationInfo, float]]:
    """Return (location, distance_km) pairs within radius_km."""
    return [
        (loc, _haversine_km(lat, lon, loc.lat, loc.lon))
        for loc in locations
        if _haversine_km(lat, lon, loc.lat, loc.lon) <= radius_km
    ]


def generate_candidates(
    ctx: ClusterContext,
    all_locations: list[LocationInfo],
    home_district_id: Id,
    policy: Policy,
) -> list[Candidate]:
    """Generate and cap a list of cash-out location candidates.

    Parameters
    ----------
    ctx:
        Cluster context (pure data; no I/O).
    all_locations:
        All registry locations available to the forecast domain.
    home_district_id:
        The district of the layer-1 victim's home branch.
    policy:
        Loaded policy (reads forecast.candidates.*).
    """
    radius = policy.forecast.candidates.radius_km
    max_cands = policy.forecast.candidates.max
    widen_factor = policy.forecast.candidates.widen_factor

    seen_ids: set[Id] = set()
    # (loc, dist_home, dist_centroid, priority)  — lower priority = higher importance
    # 0 = home-radius  1 = centroid-radius  2 = cluster-history  3 = bank-footprint
    pool: list[tuple[LocationInfo, float, float, int]] = []

    def _add(loc: LocationInfo, dist_home: float, dist_centroid: float, priority: int) -> None:
        if loc.id not in seen_ids:
            seen_ids.add(loc.id)
            pool.append((loc, dist_home, dist_centroid, priority))

    def _collect(radius_km: float) -> None:
        home_lat = ctx.layer1_home_lat
        home_lon = ctx.layer1_home_lon
        c_lat = ctx.centroid_lat
        c_lon = ctx.centroid_lon

        # 1. Near home branch
        if home_lat is not None and home_lon is not None:
            for loc, d in _within_radius(all_locations, home_lat, home_lon, radius_km):
                dist_centroid = (
                    _haversine_km(c_lat, c_lon, loc.lat, loc.lon)
                    if c_lat is not None and c_lon is not None
                    else 0.0
                )
                _add(loc, d, dist_centroid, 0)

        # 2. Near centroid
        if c_lat is not None and c_lon is not None:
            for loc, d in _within_radius(all_locations, c_lat, c_lon, radius_km):
                dist_home = (
                    _haversine_km(home_lat, home_lon, loc.lat, loc.lon)
                    if home_lat is not None and home_lon is not None
                    else 0.0
                )
                _add(loc, dist_home, d, 1)

        # 3. Top cells by cluster history
        top_cells = sorted(ctx.cashout_cell_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        top_cell_ids = {cell_id for cell_id, _ in top_cells}
        for loc in all_locations:
            if loc.cell_id in top_cell_ids:
                d_home = (
                    _haversine_km(home_lat, home_lon, loc.lat, loc.lon)
                    if home_lat is not None and home_lon is not None
                    else 0.0
                )
                d_centroid = (
                    _haversine_km(c_lat, c_lon, loc.lat, loc.lon)
                    if c_lat is not None and c_lon is not None
                    else 0.0
                )
                _add(loc, d_home, d_centroid, 2)

        # 4. Same-bank locations in the home district
        layer1_bank = ctx.layer1_bank_id
        for loc in all_locations:
            if loc.bank_id == layer1_bank and loc.district_id == home_district_id:
                d_home = (
                    _haversine_km(home_lat, home_lon, loc.lat, loc.lon)
                    if home_lat is not None and home_lon is not None
                    else 0.0
                )
                d_centroid = (
                    _haversine_km(c_lat, c_lon, loc.lat, loc.lon)
                    if c_lat is not None and c_lon is not None
                    else 0.0
                )
                _add(loc, d_home, d_centroid, 3)

    _collect(radius)

    # Widen once if empty
    if not pool:
        _collect(radius * widen_factor)

    # Sort by (priority_tier, dist_home) so cluster-history and bank-footprint candidates
    # survive the max-cap even when the proximity passes already fill it.
    pool.sort(key=lambda t: (t[3], t[1]))

    # Cap
    capped = pool[:max_cands]

    return [
        Candidate(
            location_id=loc.id,
            cell_id=loc.cell_id,
            district_id=loc.district_id,
            lat=loc.lat,
            lon=loc.lon,
            distance_to_home_km=d_home,
            distance_to_centroid_km=d_centroid,
            channel=loc.channel,
            activity_index=loc.activity_index,
            bank_id=loc.bank_id,
        )
        for loc, d_home, d_centroid, _priority in capped
    ]
