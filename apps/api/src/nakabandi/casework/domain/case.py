"""case.py — Case domain entity and its build inputs (DOC 3 S1; pure, no I/O).

Account refs are stored unmasked here; masking for non-LEA roles (DOC 3 S1 "masked refs") happens
at the interfaces boundary via access.mask_ref, the one canonical masking function (LC-2 as-of and
LC-10 table-ownership stay in the modules that own the underlying data; Case is a read-side view).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from nakabandi.shared import Id, Paise, SimTime


@dataclass(frozen=True, slots=True)
class ComplaintFact:
    """One complaint whose money reached this cluster (input to build_case)."""

    id: Id
    external_ref: str
    victim_district_id: Id
    amount_paise: Paise
    reported_event_at: SimTime
    touched_account_ids: tuple[Id, ...]


@dataclass(frozen=True, slots=True)
class AccountFact:
    """One account in the cluster (input to build_case)."""

    account_id: Id
    account_ref: str
    bank_id: str


@dataclass(frozen=True, slots=True)
class ClusterSnapshot:
    """The graph facade's view of a cluster, as much as build_case needs of it (DOC 3 S1
    "cluster_view"; mirrors graph.ClusterContext without importing graph's own type)."""

    cluster_id: Id
    as_of: SimTime
    complaint_count: int
    total_paise: Paise
    last_seen_at: SimTime | None
    top_locations: tuple[tuple[Id, int], ...]
    """(location_id, observation_count), already ranked by the graph facade."""
    sub_communities: tuple[tuple[Id, ...], ...]


@dataclass(frozen=True, slots=True)
class ClusterNode:
    id: Id
    kind: str
    account_ref: str
    bank_id: str


@dataclass(frozen=True, slots=True)
class ClusterEdge:
    from_id: Id
    to_id: Id
    amount_paise: Paise


@dataclass(frozen=True, slots=True)
class ClusterGraph:
    """DOC 3 S1 GET /clusters/{id}. `novelty` is not yet wired to the forecast facade (see
    docs/state/track-a.md Learnings [A12]) and is always 0.0 pending that cross-track hookup."""

    cluster_ref: Id
    size: int
    status: str
    novelty: float
    nodes: list[ClusterNode] = field(default_factory=list)
    edges: list[ClusterEdge] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class AccountRef:
    account_id: Id
    account_ref: str
    bank_id: str
    complaint_count: int


@dataclass(frozen=True, slots=True)
class LocationHit:
    location_id: Id
    count: int
    last_at: SimTime


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    at: SimTime
    kind: str
    text: str


@dataclass(frozen=True, slots=True)
class Case:
    """DOC 3 S1 Case: one cluster's bundled view for casework."""

    id: Id
    cluster_ref: Id
    complaint_count: int
    victim_count: int
    total_paise: Paise
    first_seen: SimTime
    last_seen: SimTime
    accounts: list[AccountRef] = field(default_factory=list)
    top_locations: list[LocationHit] = field(default_factory=list)
    sub_communities: list[list[Id]] = field(default_factory=list)
    timeline: list[TimelineEntry] = field(default_factory=list)
    brief_md: str = ""
    single_complaint: bool = False
    built_at: SimTime | None = None
    """When this row was last (re)built — not last_seen (event activity); drives the debounce and
    the UI's "updated at" (DOC 3 S1 error-handling strategy)."""
