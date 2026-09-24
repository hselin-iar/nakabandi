"""Unit tests for worldsim.core.real_seed (this session's demo-data follow-on).

Loads the real repo data/seed + data/geo CSVs (tests run with cwd at the repo root, same
convention as `_CFG_PATH = "config/sim.default.yaml"` elsewhere in this suite).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from worldsim.core.config import SimConfig
from worldsim.core.real_seed import load_real_registry
from worldsim.core.registry import build_registry
from worldsim.core.rng import rng_for

_CFG_PATH = "config/sim.default.yaml"
_DATA_DIR = Path("data/seed")
_STATES = {"UP", "MH", "HR", "JH"}


@pytest.fixture(scope="module")
def cfg() -> SimConfig:
    return SimConfig.from_yaml(_CFG_PATH)


def test_load_real_registry_returns_all_four_states(cfg: SimConfig):
    rng = rng_for(cfg.seed, "world")
    registry = load_real_registry(_DATA_DIR, _STATES, cfg, rng)
    assert registry is not None
    assert {d.state_id for d in registry.districts} == _STATES
    assert len(registry.districts) == 157  # 22 HR + 24 JH + 36 MH + 75 UP
    assert len(registry.locations) == 8504
    assert len(registry.units) == 970
    assert len(registry.banks) == 54


def test_load_real_registry_filters_to_one_state(cfg: SimConfig):
    rng = rng_for(cfg.seed, "world")
    registry = load_real_registry(_DATA_DIR, {"HR"}, cfg, rng)
    assert registry is not None
    assert {d.state_id for d in registry.districts} == {"HR"}
    assert all(loc.district_id.startswith("HR-") for loc in registry.locations)
    assert all(u.district_id.startswith("HR-") for u in registry.units)


def test_load_real_registry_returns_none_when_data_dir_missing(cfg: SimConfig):
    rng = rng_for(cfg.seed, "world")
    registry = load_real_registry(Path("data/does-not-exist"), _STATES, cfg, rng)
    assert registry is None


def test_every_location_bank_id_resolves(cfg: SimConfig):
    rng = rng_for(cfg.seed, "world")
    registry = load_real_registry(_DATA_DIR, _STATES, cfg, rng)
    assert registry is not None
    bank_ids = {b.id for b in registry.banks}
    unresolved = [loc.bank_id for loc in registry.locations if loc.bank_id not in bank_ids]
    assert unresolved == []


def test_every_location_and_unit_district_id_resolves(cfg: SimConfig):
    rng = rng_for(cfg.seed, "world")
    registry = load_real_registry(_DATA_DIR, _STATES, cfg, rng)
    assert registry is not None
    district_ids = {d.id for d in registry.districts}
    assert all(loc.district_id in district_ids for loc in registry.locations)
    assert all(u.district_id in district_ids for u in registry.units)


def test_cell_ids_are_well_formed(cfg: SimConfig):
    rng = rng_for(cfg.seed, "world")
    registry = load_real_registry(_DATA_DIR, _STATES, cfg, rng)
    assert registry is not None
    assert len(registry.cells) > 0
    for cell in registry.cells:
        assert cell.id.startswith("C")
        assert cell.grid_km > 0
        # every location claiming this cell must actually fall in that grid cell
    loc_cell_ids = {loc.cell_id for loc in registry.locations}
    cell_ids = {c.id for c in registry.cells}
    assert loc_cell_ids == cell_ids


def test_district_centroid_is_mean_of_its_locations(cfg: SimConfig):
    rng = rng_for(cfg.seed, "world")
    registry = load_real_registry(_DATA_DIR, _STATES, cfg, rng)
    assert registry is not None
    by_district = {d.id: d for d in registry.districts}
    lucknow = by_district["UP-LKO"]
    locs = [loc for loc in registry.locations if loc.district_id == "UP-LKO"]
    assert locs, "Lucknow should have at least one real location"
    expected_lat = sum(loc.lat for loc in locs) / len(locs)
    expected_lon = sum(loc.lon for loc in locs) / len(locs)
    assert lucknow.lat == pytest.approx(expected_lat, abs=1e-4)
    assert lucknow.lon == pytest.approx(expected_lon, abs=1e-4)


def test_build_registry_still_works_standalone(cfg: SimConfig):
    """registry.py's own synthetic generator is untouched and still callable directly."""
    rng = rng_for(cfg.seed, "world")
    registry = build_registry(cfg, rng)
    assert {d.state_id for d in registry.districts} == {"UP", "MH", "HR", "JH"}
    assert len(registry.banks) == 5
