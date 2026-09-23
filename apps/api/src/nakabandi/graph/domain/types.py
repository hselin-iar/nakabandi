"""types.py — Graph domain value objects (DOC 3 M2, LC-2).

These are pure data carriers; no I/O, no database imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from nakabandi.shared import Id, Paise, SimTime


@dataclass(frozen=True)
class ClusterResolution:
    """Result of ClusterIndex.resolve()."""

    cluster_id: Id
    """The surviving (canonical) cluster id after all unions."""
    merged_from: list[Id] = field(default_factory=list)
    """Previous cluster ids absorbed during this resolution (may be empty)."""
    is_new: bool = False
    """True when a brand-new cluster was created (no prior record)."""


@dataclass(frozen=True)
class LocationStat:
    """Observation count at a single location, as of a given time."""

    location_id: Id
    cell_id: Id
    district_id: Id
    observation_count: int
    total_paise: Paise


@dataclass(frozen=True)
class ClusterFootprint:
    """Geographic footprint of a cluster (as_of-bounded snapshot).

    centroid_lat / centroid_lon: weighted mean of all observed cash-out positions.
    radius_km: approximate spread (std of haversine distances from centroid).
    top_locations: up to 10 most-observed location ids.
    """

    centroid_lat: float
    centroid_lon: float
    radius_km: float
    top_locations: list[Id] = field(default_factory=list)
    sub_communities: list[list[Id]] = field(default_factory=list)
    """Louvain sub-community membership lists (annotated by RefineCommunities; may be empty)."""


@dataclass(frozen=True)
class PointInTimeStats:
    """Cluster statistics observable as of a specific moment (LC-2 as-of rule).

    observation_count: total cash-out observations with observed_at <= as_of.
    total_paise: sum of all observed cash-out amounts.
    complaint_count: complaints with reported_event_at <= as_of.
    unique_accounts: distinct account ids in this cluster.
    last_seen_at: most recent observed_at (None if no observations yet).
    """

    observation_count: int
    total_paise: Paise
    complaint_count: int
    unique_accounts: int
    last_seen_at: SimTime | None


@dataclass(frozen=True)
class ClusterContext:
    """Everything the forecast domain may see for one cluster at one moment.

    Passed by value — no lazy loading, no database references.  All fields
    are bounded by as_of (LC-2).
    """

    cluster_id: Id
    as_of: SimTime
    stats: PointInTimeStats
    footprint: ClusterFootprint | None
    location_stats: list[LocationStat] = field(default_factory=list)
