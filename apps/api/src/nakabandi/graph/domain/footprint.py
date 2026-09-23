"""footprint.py — Derive ClusterFootprint from location observations (DOC 3 M2).

Pure domain: takes pre-fetched data, returns a value object. No I/O.
"""

from __future__ import annotations

import math

from nakabandi.graph.domain.types import ClusterFootprint, LocationStat
from nakabandi.shared import Id


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres (Haversine formula)."""
    r = 6_371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def compute_footprint(
    location_stats: list[LocationStat],
    location_coords: dict[Id, tuple[float, float]],
    top_n: int = 10,
) -> ClusterFootprint | None:
    """Compute a ClusterFootprint from observation counts and coordinates.

    Parameters
    ----------
    location_stats:
        Observations at each location (as-of bounded by the caller).
    location_coords:
        {location_id: (lat, lon)}.  Locations absent from this dict are skipped.
    top_n:
        Maximum number of locations to include in `top_locations`.

    Returns None if there are no observations with known coordinates.
    """
    weighted_lat = 0.0
    weighted_lon = 0.0
    total_weight = 0

    present = [s for s in location_stats if s.location_id in location_coords]
    if not present:
        return None

    for stat in present:
        lat, lon = location_coords[stat.location_id]
        w = stat.observation_count
        weighted_lat += lat * w
        weighted_lon += lon * w
        total_weight += w

    centroid_lat = weighted_lat / total_weight
    centroid_lon = weighted_lon / total_weight

    # Spread: unweighted std of haversine distances from centroid
    distances = [
        _haversine_km(centroid_lat, centroid_lon, *location_coords[s.location_id]) for s in present
    ]
    if len(distances) > 1:
        mean_d = sum(distances) / len(distances)
        variance = sum((d - mean_d) ** 2 for d in distances) / len(distances)
        radius_km = math.sqrt(variance)
    else:
        radius_km = 0.0

    # Top locations by count
    sorted_stats = sorted(present, key=lambda s: s.observation_count, reverse=True)
    top_locations = [s.location_id for s in sorted_stats[:top_n]]

    return ClusterFootprint(
        centroid_lat=centroid_lat,
        centroid_lon=centroid_lon,
        radius_km=radius_km,
        top_locations=top_locations,
        sub_communities=[],
    )
