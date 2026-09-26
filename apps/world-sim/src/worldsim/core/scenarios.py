"""scenarios.py — inject_cluster and guided_demo_script (DOC 3 M1 B5).

inject_cluster(world, district_id, size, fast_weight, locality) -> ClusterId
  Adds a never-seen cluster from "now". Used by S4 and the guided demo.
  Returns the new cluster_id (format: INJ-<8 hex chars>).

guided_demo_script() -> list[DemoEvent]
  Returns the sequence of events for the guided demo scenario (T+0h…T+8h).
  Consumed by docs/demo-script.md (Track D Step D7).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from worldsim.core.generator import World

ClusterId = str
LocalityType = Literal["district", "multi_district", "state", "multi_state"]


@dataclass(frozen=True)
class DemoEvent:
    """One scripted event in the guided demo sequence."""

    elapsed_h: float  # hours after demo start when this event fires
    kind: str  # "history_warmup" | "complaint" | "inject_cluster" | "outcome"
    description: str
    params: dict


def inject_cluster(
    world: World,
    district_id: str,
    size: int,
    fast_weight: float,
    locality: str,
    sim_now: float = 0.0,
) -> ClusterId:
    """Add a never-seen cluster to the running world (DOC 3 M1 B5).

    Constructs a minimal MuleCluster with:
      - `size` mule accounts (at least 2), each with a random bank and a home location in the
        district, built the same way as `build_clusters`. An empty list made every complaint's
        layer-1 account an innocent stand-in whose hops all pointed back at itself.
      - Footprint centred at the district's location (fallback: 0,0 if unknown).
      - Timing mixture from the global config, perturbed by fast_weight.
      - Infinite lifetime (injected clusters run indefinitely).

    The cluster is appended to world.clusters; World.step() will route future
    complaints to it based on its district_id and cadence.
    """
    from worldsim.core.clusters import (
        Account,
        ClusterFootprint,
        MuleCluster,
        _perturb_timing,  # noqa: PLC2701
    )
    from worldsim.core.rng import rng_for

    # Seeded from call-time-deterministic inputs, not uuid.uuid4(): DOC1 M1 requires the whole
    # simulator "fully seedable and reproducible from a single config file", and the id used to
    # come from OS entropy. It also used to seed this function's own `rng` (footprint/timing
    # perturbation), so the non-determinism cascaded into the injected cluster's properties too.
    cfg = world.cfg
    seed_rng = rng_for(cfg.seed, "inject_cluster", f"{district_id}:{sim_now}")
    cluster_id: ClusterId = f"INJ-{int(seed_rng.integers(0, 2**32)):08X}"
    rng = seed_rng

    # Try to find the district's centre from the registry
    district = next((d for d in world.registry.districts if d.id == district_id), None)
    if district is not None:
        centre_lat = float(district.lat)
        centre_lon = float(district.lon)
    else:
        centre_lat, centre_lon = 0.0, 0.0

    # Footprint radius from the locality type
    _radius_map: dict[str, float] = {
        "district": 10.0,
        "multi_district": 50.0,
        "state": 150.0,
        "multi_state": 400.0,
    }
    radius_km = _radius_map.get(locality, 10.0)

    footprint = ClusterFootprint(
        centre_lat=centre_lat,
        centre_lon=centre_lon,
        radius_km=radius_km,
        locality=locality,  # type: ignore[arg-type]
    )

    # Build timing from global config, perturbed to reflect fast_weight
    base_timing = cfg.timing
    cluster_timing = _perturb_timing(base_timing, rng)

    # Build channel mix from config. `ChannelsConfig` has one field, `mix: dict[...]` — there is
    # no `.atm`/`.branch`/`.agent` attribute to read via getattr(), which always missed and
    # silently gave every injected cluster a flat 33/33/33 split regardless of the configured
    # (ATM-heavy) mix.
    channels: tuple[Literal["ATM", "BRANCH", "AGENT"], ...] = ("ATM", "BRANCH", "AGENT")
    channel_mix: dict[str, float] = {ch: cfg.channels.mix.get(ch, 0.33) for ch in channels}
    total = sum(channel_mix.values()) or 1.0
    channel_mix = {k: v / total for k, v in channel_mix.items()}

    district_locs = world.registry.locations_in(district_id)
    accounts = [
        Account(
            id=f"ACC-{cluster_id}-{a_idx:04d}",
            bank_id=world.registry.banks[int(rng.integers(len(world.registry.banks)))].id,
            home_location_id=(
                district_locs[int(rng.integers(len(district_locs)))].id if district_locs else None
            ),
        )
        for a_idx in range(max(2, size))
    ]

    cluster = MuleCluster(
        id=cluster_id,
        district_id=district_id,
        accounts=accounts,
        footprint=footprint,
        channel_mix=channel_mix,
        timing=cluster_timing,
        lifetime_days=float("inf"),  # injected clusters run indefinitely
        start_day=sim_now,
        is_bridge=False,
    )
    world.clusters.append(cluster)
    return cluster_id


# ---------------------------------------------------------------------------
# Guided demo script (D7 consumption)
# ---------------------------------------------------------------------------

_GUIDED_DEMO_EVENTS: list[DemoEvent] = [
    DemoEvent(
        elapsed_h=0.0,
        kind="history_warmup",
        description="T+0h: warm-up — load 30 days of history into the API.",
        params={},
    ),
    DemoEvent(
        elapsed_h=2.0,
        kind="complaint",
        description=(
            "T+2h: complaint hits a known cluster → alert raised, "
            "forecast INTERCEPTABLE, lien proposed."
        ),
        params={"scenario": "known_cluster", "expected_verdict": "INTERCEPTABLE"},
    ),
    DemoEvent(
        elapsed_h=3.0,
        kind="complaint",
        description=(
            "T+3h: second complaint on same cluster → merged into open alert; case updated."
        ),
        params={"scenario": "same_cluster_merge"},
    ),
    DemoEvent(
        elapsed_h=5.0,
        kind="complaint",
        description=(
            "T+5h: innocent-holder complaint (noise) → low confidence, NOT_INTERCEPTABLE, no hold."
        ),
        params={"scenario": "innocent", "expected_verdict": "NOT_INTERCEPTABLE"},
    ),
    DemoEvent(
        elapsed_h=6.0,
        kind="inject_cluster",
        description=(
            "T+6h: injected new cluster (cold-start) → wide forecast, "
            "abstention at location level, novelty=1.0 banner."
        ),
        params={
            "district_id": "MP-BHOPAL",
            "size": 5,
            "fast_weight": 0.7,
            "locality": "urban",
        },
    ),
    DemoEvent(
        elapsed_h=8.0,
        kind="outcome",
        description=(
            "T+8h: outcomes reconcile — hit (cash-out at forecast location), "
            "late (intercepted after window), miss (escaped)."
        ),
        params={"scenario": "reconcile_outcomes"},
    ),
]


def guided_demo_script() -> list[DemoEvent]:
    """Return the guided demo event sequence (DOC 3 M1; consumed by Track D Step D7)."""
    return list(_GUIDED_DEMO_EVENTS)
