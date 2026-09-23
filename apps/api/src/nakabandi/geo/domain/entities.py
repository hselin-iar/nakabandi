"""Geo domain entities (DOC 2 §2.3 CORE ENTITIES, geo section; DOC 3 LC-10 table ownership).

Plain dataclasses: no SQLAlchemy, no pydantic. Infrastructure maps these to ORM rows and back.
"""

from __future__ import annotations

from dataclasses import dataclass

from nakabandi.shared import Id


@dataclass(slots=True)
class Region:
    id: Id
    level: str  # "state" | "district"
    name: str
    parent_id: Id | None
    geojson_ref: str | None


@dataclass(slots=True)
class Bank:
    id: Id
    name: str
    short_code: str


@dataclass(slots=True)
class Cell:
    id: Id
    grid_km: float
    row: int
    col: int
    district_id: Id
    centroid_lat: float
    centroid_lon: float


@dataclass(slots=True)
class Location:
    id: Id
    kind: str  # "ATM" | "BRANCH" | "AGENT"
    bank_id: Id
    lat: float
    lon: float
    district_id: Id
    cell_id: Id
    source: str  # "osm" | "synthetic"
    display_name: str
    area_type: str  # "urban" | "semi_urban" | "rural"
    activity_index: float


@dataclass(slots=True)
class Unit:
    id: Id
    kind: str  # "cyber_cell" | "station" | "patrol"
    district_id: Id
    lat: float
    lon: float
    status: str
    speed_profile: str | None
