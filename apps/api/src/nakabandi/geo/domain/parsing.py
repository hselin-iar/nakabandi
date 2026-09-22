"""Parses the registry snapshot's bank/region/cell rows into geo entities.

LC-1's `RegistryUpdate.banks/regions/cells` are opaque `list[dict]`: DOC 3 LC-1 names the field
but not a shape ("Track A refines these when geo/intake first consume them (Step A3)",
packages/contracts/src/nakabandi_contracts/ingest.py). Field lists here follow DOC 2 §2.3's
CORE ENTITIES for Region, Bank and Cell. Kept internal to geo rather than promoted into LC-1,
since only geo consumes these rows (world-sim writes RegistryUpdate against the existing LC-1
`dict` shape unchanged).

Pure: raises ValidationFailed on a missing or wrong-typed field, never touches I/O.
"""

from __future__ import annotations

from typing import Any

from nakabandi.geo.domain.entities import Bank, Cell, Region
from nakabandi.shared import Id, ValidationFailed

_VALID_REGION_LEVELS = {"state", "district"}


def _require(raw: dict[str, Any], field: str, index: int, kind: str) -> Any:
    if field not in raw or raw[field] is None:
        raise ValidationFailed(
            f"GEO_{kind.upper()}_MISSING_FIELD", f"{kind} item {index} is missing '{field}'"
        )
    return raw[field]


def parse_bank(raw: dict[str, Any], index: int) -> Bank:
    return Bank(
        id=Id(_require(raw, "id", index, "bank")),
        name=str(_require(raw, "name", index, "bank")),
        short_code=str(_require(raw, "short_code", index, "bank")),
    )


def parse_region(raw: dict[str, Any], index: int) -> Region:
    level = str(_require(raw, "level", index, "region"))
    if level not in _VALID_REGION_LEVELS:
        valid = sorted(_VALID_REGION_LEVELS)
        raise ValidationFailed(
            "GEO_REGION_INVALID_LEVEL",
            f"region item {index} has level '{level}', must be one of {valid}",
        )
    return Region(
        id=Id(_require(raw, "id", index, "region")),
        level=level,
        name=str(_require(raw, "name", index, "region")),
        parent_id=raw.get("parent_id"),
        geojson_ref=raw.get("geojson_ref"),
    )


def parse_cell(raw: dict[str, Any], index: int) -> Cell:
    return Cell(
        id=Id(_require(raw, "id", index, "cell")),
        grid_km=float(_require(raw, "grid_km", index, "cell")),
        row=int(_require(raw, "row", index, "cell")),
        col=int(_require(raw, "col", index, "cell")),
        district_id=Id(_require(raw, "district_id", index, "cell")),
        centroid_lat=float(_require(raw, "centroid_lat", index, "cell")),
        centroid_lon=float(_require(raw, "centroid_lon", index, "cell")),
    )
