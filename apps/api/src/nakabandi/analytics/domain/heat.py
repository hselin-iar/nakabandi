"""Query-side value objects for the heatmap (DOC 3 M3 HeatmapResponse, LC-4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from nakabandi.shared import SimTime


class Layer(StrEnum):
    LIVE = "live"
    POTENTIAL = "potential"


class Level(StrEnum):
    DISTRICT = "district"
    CELL = "cell"
    LOCATION = "location"


@dataclass(frozen=True, slots=True)
class HeatFilters:
    """DOC 3 M3 filters. `cluster_id` (LEA roles) is not offered: a rollup is keyed without a
    cluster, so it cannot be honoured without a per-alert ledger (a DOC 2 change)."""

    layer: Layer = Layer.LIVE
    level: Level = Level.CELL
    from_: datetime | None = None  # defaults to `to` minus 24 h (live layer only)
    to: datetime | None = None  # defaults to the sim clock's now
    state: str | None = None
    district: str | None = None
    category: str | None = None
    amount_band: int | None = None
    min_confidence: float | None = None
    bbox: tuple[float, float, float, float] | None = None  # min_lon, min_lat, max_lon, max_lat


@dataclass(frozen=True, slots=True)
class HeatCell:
    id: str
    kind: str  # "district" | "cell" | "location"
    name: str | None
    lat: float
    lon: float
    value: float
    alert_count: int


@dataclass(frozen=True, slots=True)
class Legend:
    min: float
    max: float
    unit: str
    note: str


@dataclass(frozen=True, slots=True)
class HeatmapResult:
    layer: str
    level: str
    generated_at: SimTime
    version: int
    cells: list[HeatCell]
    suppressed_count: int
    legend: Legend


@dataclass(frozen=True, slots=True)
class TimePoint:
    hour: SimTime
    value: float
    alert_count: int


@dataclass(frozen=True, slots=True)
class TimeseriesResult:
    layer: str
    from_: SimTime
    to: SimTime
    version: int
    points: list[TimePoint]


@dataclass(frozen=True, slots=True)
class LiveMetricsResult:
    generated_at: SimTime
    version: int
    window_hours: float
    alert_count: int
    expected_mass: float
    active_locations: int
