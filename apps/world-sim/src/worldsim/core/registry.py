"""Registry — synthetic location and unit data for the four demo states (DOC 3 M1).

build_registry(cfg, rng) -> Registry

Pure; no I/O. Places banks, ATM/branch/agent locations inside the four demo state
districts using hard-coded district centroids (no network required), fills gaps with
synthetic points (source="synthetic"), assigns grid cells and activity_index in [0,1]
per location, and places response units.

District centroids cover: UP, MH, RJ, HR — the four demo states.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from worldsim.core.config import SimConfig
from worldsim.core.rng import rng_for

# ---------------------------------------------------------------------------
# Public types (pure data; no imports from nakabandi.*)
# ---------------------------------------------------------------------------

LocationKind = Literal["ATM", "BRANCH", "AGENT"]
UnitKind = Literal["cyber_cell", "station", "patrol"]
AreaType = Literal["urban", "semi_urban", "rural"]
Source = Literal["osm", "synthetic"]


@dataclass(frozen=True)
class Bank:
    id: str
    name: str
    state_id: str


@dataclass(frozen=True)
class Location:
    id: str
    kind: LocationKind
    bank_id: str
    lat: float
    lon: float
    district_id: str
    cell_id: str
    source: Source
    display_name: str
    area_type: AreaType
    activity_index: float  # [0, 1]


@dataclass(frozen=True)
class Unit:
    id: str
    kind: UnitKind
    district_id: str
    lat: float
    lon: float
    status: str


@dataclass(frozen=True)
class District:
    id: str
    state_id: str
    name: str
    lat: float  # centroid
    lon: float


@dataclass(frozen=True)
class Cell:
    id: str
    lat: float
    lon: float
    district_id: str


@dataclass
class Registry:
    banks: list[Bank]
    locations: list[Location]
    units: list[Unit]
    districts: list[District]
    cells: list[Cell]
    # indexes built at construction time
    _loc_by_id: dict[str, Location] = field(default_factory=dict, repr=False, compare=False)
    _locs_by_district: dict[str, list[Location]] = field(
        default_factory=dict, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        self._loc_by_id = {loc.id: loc for loc in self.locations}
        for loc in self.locations:
            self._locs_by_district.setdefault(loc.district_id, []).append(loc)

    def location(self, loc_id: str) -> Location:
        return self._loc_by_id[loc_id]

    def locations_in(self, district_id: str) -> list[Location]:
        return self._locs_by_district.get(district_id, [])


# ---------------------------------------------------------------------------
# Hard-coded district data (four demo states — no network needed)
# Centroids from public GIS data (approximate).
# ---------------------------------------------------------------------------

_DISTRICTS: list[dict] = [
    # Uttar Pradesh
    {"id": "UP-LKO", "state_id": "UP", "name": "Lucknow", "lat": 26.85, "lon": 80.95},
    {"id": "UP-KNP", "state_id": "UP", "name": "Kanpur", "lat": 26.47, "lon": 80.33},
    {"id": "UP-AGR", "state_id": "UP", "name": "Agra", "lat": 27.18, "lon": 78.01},
    {"id": "UP-GZB", "state_id": "UP", "name": "Ghaziabad", "lat": 28.67, "lon": 77.45},
    # Maharashtra
    {"id": "MH-MUM", "state_id": "MH", "name": "Mumbai", "lat": 19.08, "lon": 72.88},
    {"id": "MH-PUN", "state_id": "MH", "name": "Pune", "lat": 18.52, "lon": 73.86},
    {"id": "MH-NAG", "state_id": "MH", "name": "Nagpur", "lat": 21.15, "lon": 79.09},
    {"id": "MH-NAS", "state_id": "MH", "name": "Nashik", "lat": 20.00, "lon": 73.79},
    # Rajasthan
    {"id": "RJ-JPR", "state_id": "RJ", "name": "Jaipur", "lat": 26.92, "lon": 75.79},
    {"id": "RJ-JDH", "state_id": "RJ", "name": "Jodhpur", "lat": 26.29, "lon": 73.02},
    {"id": "RJ-AJM", "state_id": "RJ", "name": "Ajmer", "lat": 26.45, "lon": 74.64},
    {"id": "RJ-UDR", "state_id": "RJ", "name": "Udaipur", "lat": 24.58, "lon": 73.68},
    # Haryana
    {"id": "HR-GGN", "state_id": "HR", "name": "Gurugram", "lat": 28.46, "lon": 77.03},
    {"id": "HR-FBD", "state_id": "HR", "name": "Faridabad", "lat": 28.41, "lon": 77.31},
    {"id": "HR-AMB", "state_id": "HR", "name": "Ambala", "lat": 30.38, "lon": 76.78},
    {"id": "HR-HIS", "state_id": "HR", "name": "Hisar", "lat": 29.15, "lon": 75.72},
]

_BANKS: list[dict] = [
    {"id": "SBI", "name": "State Bank of India", "state_id": "*"},
    {"id": "PNB", "name": "Punjab National Bank", "state_id": "*"},
    {"id": "HDFC", "name": "HDFC Bank", "state_id": "*"},
    {"id": "ICICI", "name": "ICICI Bank", "state_id": "*"},
    {"id": "BOB", "name": "Bank of Baroda", "state_id": "*"},
]

# Grid: ~0.25° cells (~27 km side)
_CELL_SIZE_DEG: float = 0.25


def _cell_id(lat: float, lon: float) -> str:
    row = math.floor(lat / _CELL_SIZE_DEG)
    col = math.floor(lon / _CELL_SIZE_DEG)
    return f"C{row:+05d}_{col:+05d}"


def _cell_centroid(lat: float, lon: float) -> tuple[float, float]:
    row = math.floor(lat / _CELL_SIZE_DEG)
    col = math.floor(lon / _CELL_SIZE_DEG)
    return (
        (row + 0.5) * _CELL_SIZE_DEG,
        (col + 0.5) * _CELL_SIZE_DEG,
    )


def _area_type(rng: np.random.Generator, district_name: str) -> AreaType:
    """Assign area type based on district name heuristics + random residual."""
    big_cities = {
        "Mumbai",
        "Pune",
        "Lucknow",
        "Kanpur",
        "Jaipur",
        "Gurugram",
        "Faridabad",
        "Ghaziabad",
        "Agra",
        "Nagpur",
    }
    if district_name in big_cities:
        weights = [0.70, 0.20, 0.10]  # urban-heavy
    else:
        weights = [0.30, 0.45, 0.25]  # semi-urban-heavy
    idx = rng.choice(3, p=weights)
    return ("urban", "semi_urban", "rural")[idx]


def build_registry(cfg: SimConfig, rng: np.random.Generator) -> Registry:
    """Place banks, locations (ATM/BRANCH/AGENT), and units over the four demo states.

    Every location has a deterministic id, grid cell, and activity_index.
    No I/O; no calls to nakabandi.*.
    """
    districts = [District(**d) for d in _DISTRICTS]
    banks = [Bank(**b) for b in _BANKS]
    bank_ids = [b.id for b in banks]

    n_locs_per_district = cfg.footprint.size_per_cluster  # reuse as density proxy
    kinds: list[LocationKind] = ["ATM", "BRANCH", "AGENT"]
    kind_weights = [
        cfg.channels.mix.get("ATM", 0.33),
        cfg.channels.mix.get("BRANCH", 0.33),
        cfg.channels.mix.get("AGENT", 0.34),
    ]

    locations: list[Location] = []
    cells_seen: dict[str, Cell] = {}

    for district in districts:
        d_rng = rng_for(cfg.seed, "registry", district.id)
        # scatter points around district centroid (±0.5°)
        lats = district.lat + d_rng.uniform(-0.5, 0.5, size=n_locs_per_district)
        lons = district.lon + d_rng.uniform(-0.5, 0.5, size=n_locs_per_district)
        for i, (lat, lon) in enumerate(zip(lats, lons, strict=False)):
            kind_idx = d_rng.choice(3, p=kind_weights)
            kind: LocationKind = kinds[kind_idx]
            bank_id = bank_ids[d_rng.integers(len(bank_ids))]
            area = _area_type(d_rng, district.name)
            activity = float(d_rng.beta(2, 3))  # [0,1], skewed low
            cid = _cell_id(lat, lon)
            if cid not in cells_seen:
                clat, clon = _cell_centroid(lat, lon)
                cells_seen[cid] = Cell(id=cid, lat=clat, lon=clon, district_id=district.id)
            loc = Location(
                id=f"LOC-{district.id}-{i:04d}",
                kind=kind,
                bank_id=bank_id,
                lat=round(lat, 6),
                lon=round(lon, 6),
                district_id=district.id,
                cell_id=cid,
                source="synthetic",
                display_name=f"{kind} {bank_id} {district.name} {i}",
                area_type=area,
                activity_index=round(activity, 4),
            )
            locations.append(loc)

    # Response units: one cyber_cell + 2 stations per district
    units: list[Unit] = []
    for district in districts:
        u_rng = rng_for(cfg.seed, "units", district.id)
        units.append(
            Unit(
                id=f"UNIT-{district.id}-CC",
                kind="cyber_cell",
                district_id=district.id,
                lat=round(district.lat + u_rng.uniform(-0.05, 0.05), 6),
                lon=round(district.lon + u_rng.uniform(-0.05, 0.05), 6),
                status="active",
            )
        )
        for j in range(2):
            units.append(
                Unit(
                    id=f"UNIT-{district.id}-ST{j}",
                    kind="station",
                    district_id=district.id,
                    lat=round(district.lat + u_rng.uniform(-0.3, 0.3), 6),
                    lon=round(district.lon + u_rng.uniform(-0.3, 0.3), 6),
                    status="active",
                )
            )

    return Registry(
        banks=banks,
        locations=locations,
        units=units,
        districts=districts,
        cells=list(cells_seen.values()),
    )
