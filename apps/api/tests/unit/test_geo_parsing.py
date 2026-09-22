"""Parses the registry snapshot's opaque bank/region/cell dict rows (DOC 2 §2.3 CORE ENTITIES;
packages/contracts/src/nakabandi_contracts/ingest.py: shape deferred to geo at Step A3)."""

from __future__ import annotations

import pytest
from nakabandi.geo.domain.parsing import parse_bank, parse_cell, parse_region
from nakabandi.shared import ValidationFailed


def test_parse_bank_round_trips_a_well_formed_row() -> None:
    bank = parse_bank({"id": "bank-1", "name": "SBI", "short_code": "SBI"}, 0)
    assert bank.id == "bank-1"
    assert bank.short_code == "SBI"


def test_parse_bank_rejects_a_missing_field() -> None:
    with pytest.raises(ValidationFailed) as exc_info:
        parse_bank({"id": "bank-1", "name": "SBI"}, 3)
    assert exc_info.value.code == "GEO_BANK_MISSING_FIELD"


def test_parse_region_accepts_state_and_district() -> None:
    assert parse_region({"id": "r1", "level": "state", "name": "UP"}, 0).level == "state"
    assert parse_region({"id": "r2", "level": "district", "name": "Lucknow"}, 1).level == "district"


def test_parse_region_rejects_an_unknown_level() -> None:
    with pytest.raises(ValidationFailed) as exc_info:
        parse_region({"id": "r1", "level": "county", "name": "?"}, 0)
    assert exc_info.value.code == "GEO_REGION_INVALID_LEVEL"


def test_parse_cell_round_trips_a_well_formed_row() -> None:
    cell = parse_cell(
        {
            "id": "cell-1",
            "grid_km": 5,
            "row": 1,
            "col": 2,
            "district_id": "d1",
            "centroid_lat": 26.85,
            "centroid_lon": 80.95,
        },
        0,
    )
    assert cell.row == 1 and cell.col == 2
