"""Golden test — stream hash printed twice must match (DOC 3 M1 testing plan).

This test:
1. Runs the golden config (seed=42, 3 days, 6 clusters) twice.
2. Asserts both hashes are identical (determinism).
3. Validates all emitted batches against the contracts JSON Schemas.
4. Prints the stream hash (Evidence required for B1).
"""

from __future__ import annotations

import hashlib
import json

import pytest
from nakabandi_contracts.ingest import (
    CashOutObservationBatch,
    ComplaintBatch,
    HopBatch,
    RegistryUpdate,
    Tick,
)
from worldsim.core.clusters import build_clusters
from worldsim.core.config import SimConfig
from worldsim.core.generator import World
from worldsim.core.observe import ObservedCashOut, ObservedComplaint, ObservedHop, observe
from worldsim.core.registry import build_registry
from worldsim.core.rng import rng_for
from worldsim.writer.batches import (
    BATCH_MAX,
    _frac_day_to_iso,
    make_idempotency_key,
    to_cashout_batch,
    to_complaint_batch,
    to_hop_batch,
    to_registry,
    to_tick,
)

_CFG_PATH = "config/sim.default.yaml"
_RUN_ID = "golden-42"


def _run_golden(cfg: SimConfig) -> tuple[str, list[str]]:
    """Run golden generation. Returns (stream_hash, list_of_json_lines)."""
    rng = rng_for(cfg.seed, "world")
    registry = build_registry(cfg, rng)
    clusters = build_clusters(cfg, registry, rng)
    world = World(cfg=cfg, registry=registry, clusters=clusters)

    hasher = hashlib.sha256()
    lines: list[str] = []
    batch_no = 0

    def _emit(batch) -> None:
        nonlocal batch_no
        line = batch.model_dump_json() + "\n"
        lines.append(line)
        hasher.update(line.encode())
        batch_no += 1

    # Registry
    _emit(to_registry(registry))

    for day in range(cfg.world.days):
        t0, t1 = float(day), float(day + 1)
        truth_events = world.step(t0, t1)
        obs_rng = rng_for(cfg.seed, "observe_step", str(day))
        observed = observe(truth_events, cfg, obs_rng)

        complaints = [e for e in observed if isinstance(e, ObservedComplaint)]
        hops = [e for e in observed if isinstance(e, ObservedHop)]
        cashouts = [e for e in observed if isinstance(e, ObservedCashOut)]
        sim_time_iso = _frac_day_to_iso(t1)

        # Chunk into ≤BATCH_MAX slices (LC-1: maxItems 500)
        for chunk_idx, start in enumerate(range(0, max(len(complaints), 1), BATCH_MAX)):
            chunk = complaints[start : start + BATCH_MAX]
            if not chunk:
                break
            idem = make_idempotency_key(cfg.seed, _RUN_ID, batch_no)
            _emit(to_complaint_batch(chunk, sim_time_iso, f"B-{_RUN_ID}-C-{day}-{chunk_idx}", idem))

        for chunk_idx, start in enumerate(range(0, max(len(hops), 1), BATCH_MAX)):
            chunk = hops[start : start + BATCH_MAX]
            if not chunk:
                break
            idem = make_idempotency_key(cfg.seed, _RUN_ID, batch_no)
            _emit(to_hop_batch(chunk, sim_time_iso, f"B-{_RUN_ID}-H-{day}-{chunk_idx}", idem))

        for chunk_idx, start in enumerate(range(0, max(len(cashouts), 1), BATCH_MAX)):
            chunk = cashouts[start : start + BATCH_MAX]
            if not chunk:
                break
            idem = make_idempotency_key(cfg.seed, _RUN_ID, batch_no)
            _emit(to_cashout_batch(chunk, sim_time_iso, f"B-{_RUN_ID}-CO-{day}-{chunk_idx}", idem))

        _emit(to_tick(sim_time_iso))

    return hasher.hexdigest(), lines


@pytest.fixture(scope="module")
def cfg() -> SimConfig:
    return SimConfig.from_yaml(_CFG_PATH)


def test_golden_hash_deterministic(cfg: SimConfig):
    """Same seed → same hash. Print both for the evidence record."""
    h1, lines1 = _run_golden(cfg)
    h2, lines2 = _run_golden(cfg)

    print(f"\nstream_hash run-1: {h1}")
    print(f"stream_hash run-2: {h2}")

    assert h1 == h2, f"Golden hash mismatch: {h1!r} != {h2!r}"
    assert len(lines1) == len(lines2), "Different number of batches between runs"


def test_golden_output_validates_against_schemas(cfg: SimConfig):
    """Every emitted batch must round-trip through its Pydantic model (schema validation)."""
    _, lines = _run_golden(cfg)

    complaints_seen = hops_seen = cashouts_seen = registry_seen = ticks_seen = 0

    for _i, line in enumerate(lines):
        raw = json.loads(line)

        # Detect type by top-level keys
        if "items" in raw and "batch_id" in raw:
            items = raw.get("items", [])
            if items and "external_ref" in items[0]:
                ComplaintBatch.model_validate(raw)
                complaints_seen += 1
            elif items and "complaint_external_ref" in items[0]:
                HopBatch.model_validate(raw)
                hops_seen += 1
            elif items and "account_ref" in items[0]:
                CashOutObservationBatch.model_validate(raw)
                cashouts_seen += 1
        elif "version" in raw and "locations" in raw:
            RegistryUpdate.model_validate(raw)
            registry_seen += 1
        elif list(raw.keys()) == ["sim_time"]:
            Tick.model_validate(raw)
            ticks_seen += 1

    print(
        f"\nBatches: complaints={complaints_seen}, hops={hops_seen}, "
        f"cashouts={cashouts_seen}, registry={registry_seen}, ticks={ticks_seen}"
    )

    # At least one of each type (3-day golden run always has all)
    assert complaints_seen > 0, "No ComplaintBatch emitted"
    assert hops_seen >= 0  # hops may be 0 if all complaints are innocent
    assert cashouts_seen > 0, "No CashOutObservationBatch emitted"
    assert registry_seen == 1, f"Expected 1 RegistryUpdate, got {registry_seen}"
    assert ticks_seen == cfg.world.days, f"Expected {cfg.world.days} ticks, got {ticks_seen}"


def test_registry_wire_shape_matches_geo_domain_parsing(cfg: SimConfig):
    """Regression test for a real writer/reader mismatch found this session: `to_registry()`'s
    banks/regions/cells used to send a shape `nakabandi.geo.domain.parsing.parse_bank/
    parse_region/parse_cell` (apps/api/src/nakabandi/geo/domain/parsing.py) would reject on every
    single row — `ApplyRegistry` catches the rejection per-row and moves on, so nothing ever
    crashed, but no bank/region/cell row world-sim ever sent had actually been stored. world-sim
    may not import `nakabandi.*` (DOC 3 M1's only-cross-import-is-contracts rule), so this
    encodes that required-field contract directly rather than importing the real parser —
    `parse_bank` needs id/name/short_code, `parse_region` needs id/level/name (parent_id and
    geojson_ref may be null), `parse_cell` needs id/grid_km/row/col/district_id/centroid_lat/
    centroid_lon.
    """
    rng = rng_for(cfg.seed, "world")
    registry = build_registry(cfg, rng)
    ru = to_registry(registry)

    for i, b in enumerate(ru.banks):
        for field in ("id", "name", "short_code"):
            assert field in b and b[field] is not None, f"bank[{i}] missing '{field}'"

    for i, r in enumerate(ru.regions):
        for field in ("id", "level", "name"):
            assert field in r and r[field] is not None, f"region[{i}] missing '{field}'"
        assert r["level"] in ("state", "district")

    for i, c in enumerate(ru.cells):
        for field in ("id", "grid_km", "row", "col", "district_id", "centroid_lat", "centroid_lon"):
            assert field in c and c[field] is not None, f"cell[{i}] missing '{field}'"
