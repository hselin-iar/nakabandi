"""Property tests for worldsim (DOC 3 M1 testing plan — Property section).

Properties:
  P1. Events returned from World.step() are sorted by event_time.
  P2. observed_at >= event_at for every ObservedEvent.
  P3. Same seed and config give an identical event hash (determinism).
  P4. Different seeds give different hashes.
  P5. All cash-out event_times are strictly > their complaint event_time.
"""

from __future__ import annotations

import hashlib

import pytest
from worldsim.core.clusters import build_clusters
from worldsim.core.config import SimConfig
from worldsim.core.generator import CashOutTruth, ComplaintTruth, World
from worldsim.core.observe import ObservedCashOut, ObservedComplaint, ObservedHop, observe
from worldsim.core.registry import build_registry
from worldsim.core.rng import rng_for

_CFG_PATH = "config/sim.default.yaml"


def _make_world(cfg: SimConfig) -> World:
    rng = rng_for(cfg.seed, "world")
    registry = build_registry(cfg, rng)
    clusters = build_clusters(cfg, registry, rng)
    return World(cfg=cfg, registry=registry, clusters=clusters)


def _stream_hash(cfg: SimConfig) -> str:
    world = _make_world(cfg)
    hasher = hashlib.sha256()
    for day in range(cfg.world.days):
        events = world.step(float(day), float(day + 1))
        for e in events:
            hasher.update(repr(e).encode())
    return hasher.hexdigest()


@pytest.fixture(scope="module")
def cfg() -> SimConfig:
    return SimConfig.from_yaml(_CFG_PATH)


@pytest.fixture(scope="module")
def world_and_events(cfg: SimConfig):
    world = _make_world(cfg)
    all_events = []
    for day in range(cfg.world.days):
        all_events.extend(world.step(float(day), float(day + 1)))
    return world, all_events


# ---------------------------------------------------------------------------
# P1 — Events sorted by event_time within each step
# ---------------------------------------------------------------------------


def test_events_sorted_within_step(cfg: SimConfig):
    """Each step's event list must be sorted by event_time."""
    world = _make_world(cfg)
    for day in range(cfg.world.days):
        events = world.step(float(day), float(day + 1))
        times = [e.event_time for e in events]
        assert times == sorted(times), f"Events not sorted on day {day}"


# ---------------------------------------------------------------------------
# P2 — observed_at >= event_at for every ObservedEvent
# ---------------------------------------------------------------------------


def test_observed_at_gte_event_at(world_and_events, cfg: SimConfig):
    _, truth_events = world_and_events
    rng = rng_for(cfg.seed, "observe_prop")
    observed = observe(truth_events, cfg, rng)
    violations = []
    for ev in observed:
        if isinstance(ev, ObservedComplaint):
            event_at = ev.credited_at
            obs_at = ev.observed_at
        elif isinstance(ev, ObservedHop):
            event_at = ev.event_at
            obs_at = ev.observed_at
        elif isinstance(ev, ObservedCashOut):
            event_at = ev.event_at
            obs_at = ev.observed_at
        else:
            continue
        if obs_at < event_at - 1e-9:
            violations.append((type(ev).__name__, event_at, obs_at))
    assert not violations, f"observed_at < event_at violations: {violations[:5]}"


# ---------------------------------------------------------------------------
# P3 — Determinism: same seed → same hash
# ---------------------------------------------------------------------------


def test_same_seed_same_hash(cfg: SimConfig):
    h1 = _stream_hash(cfg)
    h2 = _stream_hash(cfg)
    assert h1 == h2, "Two runs with the same seed produced different hashes"


# ---------------------------------------------------------------------------
# P4 — Different seeds → different hashes
# ---------------------------------------------------------------------------


def test_different_seeds_differ(cfg: SimConfig):
    h_42 = _stream_hash(cfg)
    cfg_99 = cfg.model_copy(update={"seed": 99})
    h_99 = _stream_hash(cfg_99)
    assert h_42 != h_99, "Different seeds produced the same hash (collision)"


# ---------------------------------------------------------------------------
# P5 — Cash-out event_time > complaint event_time
# ---------------------------------------------------------------------------


def test_cashout_after_complaint(world_and_events):
    _, events = world_and_events
    # Build a map: complaint_ref -> complaint event_time
    complaint_times: dict[str, float] = {
        e.external_ref: e.event_time for e in events if isinstance(e, ComplaintTruth)
    }
    violations = []
    for e in events:
        if isinstance(e, CashOutTruth):
            c_time = complaint_times.get(e.complaint_ref)
            if c_time is not None and e.event_time <= c_time:
                violations.append((e.complaint_ref, c_time, e.event_time))
    assert not violations, f"Cash-out before complaint violations: {violations[:5]}"


# ---------------------------------------------------------------------------
# P6 — Amount paise > 0 everywhere
# ---------------------------------------------------------------------------


def test_all_amounts_positive(world_and_events):
    _, events = world_and_events
    for e in events:
        if hasattr(e, "amount_paise"):
            assert e.amount_paise > 0, f"Non-positive amount in {e}"
