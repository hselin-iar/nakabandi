"""real_seed.py — loads world-sim's registry from the real curated CSVs in data/seed and
data/geo, instead of registry.py's synthetic generator (DOC 3 M1, this session's demo-data
follow-on).

`load_real_registry` is the only function here that does file I/O — kept out of registry.py so
that module stays exactly what its own docstring says ("Pure; no I/O"). Returns None (not an
exception) when the CSV directory doesn't exist, so callers can fall back to the synthetic
generator without special-casing a missing-data environment (offline sandboxes, CI images that
don't ship data/, etc.).

districts.csv has no lat/lon of its own (no geometry column at all) — a district's centroid is
derived here as the mean of its own locations' coordinates, not a separately-sourced value.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING

from worldsim.core.registry import (
    GRID_KM,
    Bank,
    Cell,
    District,
    Location,
    Registry,
    Unit,
    _cell_id,
    _cell_row_col,
)

if TYPE_CHECKING:
    import numpy as np

    from worldsim.core.config import SimConfig

_SEED_FILES = ("banks.csv", "districts.csv", "response_units.csv")
_GEO_FILE = "atm_branch_agent_locations.csv"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_real_registry(
    data_dir: Path,
    states: set[str],
    cfg: SimConfig,  # noqa: ARG001 — kept for a uniform signature with build_registry callers
    rng: np.random.Generator,  # noqa: ARG001 — no randomness needed; kept for signature parity
) -> Registry | None:
    """Build a Registry from the real seed CSVs, filtered to `states`.

    `data_dir` is expected to contain `data/seed/{banks,districts,response_units}.csv` as
    siblings, and `data/geo/atm_branch_agent_locations.csv` one directory up under `geo/`
    (mirrors the repo's actual data/seed + data/geo layout). Returns None if any required file
    is missing, so the caller can fall back to the synthetic generator.
    """
    seed_dir = data_dir
    geo_dir = data_dir.parent / "geo"
    paths = [seed_dir / name for name in _SEED_FILES] + [geo_dir / _GEO_FILE]
    if not all(p.is_file() for p in paths):
        return None

    banks_rows = _read_csv(seed_dir / "banks.csv")
    districts_rows = [r for r in _read_csv(seed_dir / "districts.csv") if r["state_code"] in states]
    district_ids = {r["district_id"] for r in districts_rows}
    location_rows = [r for r in _read_csv(geo_dir / _GEO_FILE) if r["district_id"] in district_ids]
    unit_rows = [
        r for r in _read_csv(seed_dir / "response_units.csv") if r["district_id"] in district_ids
    ]

    banks = [
        Bank(id=r["bank_id"], name=r["name"], state_id="*", short_code=r["short_code"])
        for r in banks_rows
    ]

    # District centroids: districts.csv carries no geometry, so derive each one as the mean
    # position of its own locations (locations do carry real lat/lon).
    lat_sum: dict[str, float] = {}
    lon_sum: dict[str, float] = {}
    count: dict[str, int] = {}
    for r in location_rows:
        did = r["district_id"]
        lat_sum[did] = lat_sum.get(did, 0.0) + float(r["lat"])
        lon_sum[did] = lon_sum.get(did, 0.0) + float(r["lon"])
        count[did] = count.get(did, 0) + 1

    districts: list[District] = []
    for r in districts_rows:
        did = r["district_id"]
        n = count.get(did, 0)
        # A district with zero locations (possible for a sparsely-covered rural district) falls
        # back to 0.0, 0.0 — visibly wrong on a map rather than silently plausible, so it's easy
        # to spot rather than mistaken for a real centroid.
        centroid_lat = lat_sum[did] / n if n else 0.0
        centroid_lon = lon_sum[did] / n if n else 0.0
        districts.append(
            District(
                id=did,
                state_id=r["state_code"],
                state_name=r["state_name"],
                name=r["district_name"],
                lat=round(centroid_lat, 6),
                lon=round(centroid_lon, 6),
            )
        )

    locations: list[Location] = []
    cells_seen: dict[str, Cell] = {}
    for r in location_rows:
        lat, lon = float(r["lat"]), float(r["lon"])
        cid = _cell_id(lat, lon)
        if cid not in cells_seen:
            crow, ccol = _cell_row_col(lat, lon)
            cells_seen[cid] = Cell(
                id=cid,
                lat=lat,
                lon=lon,
                district_id=r["district_id"],
                grid_km=GRID_KM,
                row=crow,
                col=ccol,
            )
        locations.append(
            Location(
                id=r["location_id"],
                kind=r["kind"],  # type: ignore[arg-type]
                bank_id=r["bank_id"],
                lat=lat,
                lon=lon,
                district_id=r["district_id"],
                cell_id=cid,
                source=r["source"],  # type: ignore[arg-type]
                display_name=r["display_name"],
                area_type=r["area_type"],  # type: ignore[arg-type]
                activity_index=float(r["activity_index"]),
            )
        )

    units = [
        Unit(
            id=r["unit_id"],
            kind=r["kind"],  # type: ignore[arg-type]
            district_id=r["district_id"],
            lat=float(r["lat"]),
            lon=float(r["lon"]),
            status=r["status"],
        )
        for r in unit_rows
    ]

    return Registry(
        banks=banks,
        locations=locations,
        units=units,
        districts=districts,
        cells=list(cells_seen.values()),
    )
