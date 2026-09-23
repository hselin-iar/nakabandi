"""Analytics application ports. Analytics reads other modules only through these, implemented in
main.py's wiring over the modules' facades (LC-10: it never touches their tables)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from nakabandi.analytics.domain.rollup import ForecastFacts
from nakabandi.shared import Id, SimTime


@dataclass(frozen=True, slots=True)
class AlertFacts:
    alert_id: Id
    complaint_id: Id  # the alert's complaint anchor
    target_id: Id  # a location id
    created_at: SimTime


@dataclass(frozen=True, slots=True)
class ComplaintFacts:
    category: str
    amount_paise: int


class ProjectionSource(Protocol):
    """Where a projector looks up what an ID-only event refers to (LC-3: events carry IDs)."""

    def alert_facts(self, alert_id: Id) -> AlertFacts | None: ...
    def forecast_facts(self, complaint_id: Id) -> ForecastFacts | None: ...
    def complaint_facts(self, complaint_id: Id) -> ComplaintFacts | None: ...


@dataclass(frozen=True, slots=True)
class CatalogCell:
    id: Id
    district_id: Id
    state_id: Id | None
    lat: float
    lon: float


@dataclass(frozen=True, slots=True)
class CatalogLocation:
    id: Id
    name: str
    cell_id: Id
    district_id: Id
    state_id: Id | None
    bank_id: Id
    lat: float
    lon: float


@dataclass(frozen=True, slots=True)
class GeoCatalog:
    """The registry as the heatmap needs it: what each target is, where, and under which
    district, state and bank (for roll-ups, scope and bbox filters)."""

    cells: dict[Id, CatalogCell] = field(default_factory=dict)
    locations: dict[Id, CatalogLocation] = field(default_factory=dict)
    district_names: dict[Id, str] = field(default_factory=dict)


class GeoCatalogPort(Protocol):
    def catalog(self) -> GeoCatalog: ...


@dataclass(frozen=True, slots=True)
class RollupDelta:
    """One contribution to add to a rollup row."""

    target_kind: str
    target_id: str
    hour_bucket: SimTime
    category: str
    amount_band: int
    confidence_band: int
    layer: str
    mass: float
    alert_count: int


@dataclass(frozen=True, slots=True)
class BucketSum:
    """A window query's result: the mass and alert count of one target in one hour."""

    target_kind: str
    target_id: str
    hour_bucket: SimTime
    mass: float
    alert_count: int


class RollupRepo(Protocol):
    def current_version(self) -> int: ...

    def add(self, deltas: list[RollupDelta]) -> int:
        """Add every delta to its row, stamp the touched rows with one new version, return it."""
        ...

    def window(
        self,
        *,
        layer: str,
        target_kind: str,
        from_bucket: SimTime,
        to_bucket: SimTime,
        category: str | None = None,
        amount_band: int | None = None,
        min_confidence_band: int | None = None,
    ) -> list[BucketSum]: ...
