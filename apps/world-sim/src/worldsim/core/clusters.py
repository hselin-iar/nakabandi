"""clusters.py — MuleCluster model and build_clusters() (DOC 3 M1).

Pure; no I/O. Each cluster has:
  - accounts (each with issuing bank and home location)
  - a runner footprint (centre points, radius, size)
  - a channel mix
  - a timing mixture (inherits from global with cluster-level perturbation)
  - a lifetime and a cadence

Cluster ids: C-{index:04d} (e.g. C-0001).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np

from worldsim.core.config import SimConfig, TimingComponent, TimingConfig
from worldsim.core.registry import District, Location, Registry
from worldsim.core.rng import rng_for

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Account:
    id: str
    bank_id: str
    home_location_id: str | None  # nullable per LC-1 AccountIn


@dataclass(frozen=True)
class ClusterFootprint:
    """Runner footprint: where cash-outs tend to happen."""

    centre_lat: float
    centre_lon: float
    radius_km: float
    locality: Literal["district", "multi_district", "state", "multi_state"]


@dataclass
class MuleCluster:
    id: str
    district_id: str  # origin district (complaint source)
    accounts: list[Account]
    footprint: ClusterFootprint
    channel_mix: dict[str, float]  # {"ATM": 0.7, "BRANCH": 0.2, "AGENT": 0.1}
    timing: TimingConfig  # cluster-specific mixture (slightly perturbed)
    lifetime_days: float
    start_day: float  # fractional day into the sim when cluster becomes active
    is_bridge: bool = False  # True if shared accounts bridge another cluster
    bridge_partner_id: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LOCALITY_RADIUS_KM: dict[str, tuple[float, float]] = {
    # (min_km, max_km)
    "district": (5.0, 40.0),
    "multi_district": (30.0, 120.0),
    "state": (80.0, 300.0),
    "multi_state": (200.0, 800.0),
}


def _perturb_timing(base: TimingConfig, rng: np.random.Generator) -> TimingConfig:
    """Apply a small cluster-level perturbation to the global timing mixture."""
    new_components = []
    for comp in base.mixture:
        # perturb median by ±30% log-scale
        factor = math.exp(rng.normal(0, 0.15))
        new_median = float(np.clip(comp.lognormal_median_min * factor, 1.0, 10_080.0))
        new_components.append(
            TimingComponent(
                weight=comp.weight,
                component=comp.component,
                lognormal_median_min=new_median,
                lognormal_sigma=comp.lognormal_sigma,
            )
        )
    return TimingConfig(mixture=new_components)


def _normalise(mix: dict[str, float]) -> dict[str, float]:
    total = sum(mix.values())
    return {k: v / total for k, v in mix.items()}


# ---------------------------------------------------------------------------
# build_clusters
# ---------------------------------------------------------------------------


def build_clusters(
    cfg: SimConfig,
    registry: Registry,
    rng: np.random.Generator,
) -> list[MuleCluster]:
    """Build n_clusters MuleCluster objects seeded by cfg.seed.

    Steps:
    1. Select an origin district for each cluster (weighted by state_weights).
    2. Assign accounts (accounts_per_cluster, sampled from that district's locations).
    3. Build a runner footprint centred near the district with locality-based radius.
    4. Assign channel mix (global with cluster perturbation).
    5. Assign cluster-specific timing.
    6. Assign lifetime and start_day.
    7. Mark bridge accounts (bridge_rate fraction of second cluster's accounts overlap first).
    """
    n = cfg.world.n_clusters
    clusters: list[MuleCluster] = []

    # Normalised district weights from state weights
    state_weights_raw = cfg.geo.state_weights
    total_weight = sum(state_weights_raw.values())
    state_weights = {k: v / total_weight for k, v in state_weights_raw.items()}

    districts_by_state: dict[str, list[District]] = {}
    for d in registry.districts:
        districts_by_state.setdefault(d.state_id, []).append(d)

    # Build a flat list of (district, weight) for sampling
    flat_districts: list[District] = []
    flat_weights: list[float] = []
    for state_id, sw in state_weights.items():
        ds = districts_by_state.get(state_id, [])
        if not ds:
            continue
        per_district = sw / len(ds)
        for d in ds:
            flat_districts.append(d)
            flat_weights.append(per_district)

    flat_weights_arr = np.array(flat_weights)
    flat_weights_arr /= flat_weights_arr.sum()

    for idx in range(n):
        cluster_id = f"C-{idx:04d}"
        c_rng = rng_for(cfg.seed, "cluster", cluster_id)

        # 1. Origin district
        d_idx = int(c_rng.choice(len(flat_districts), p=flat_weights_arr))
        district = flat_districts[d_idx]

        # 2. Accounts
        n_accounts = max(
            2,
            int(
                c_rng.integers(
                    max(2, cfg.network.accounts_per_cluster // 2),
                    cfg.network.accounts_per_cluster + 1,
                )
            ),
        )
        district_locs = registry.locations_in(district.id)
        accounts: list[Account] = []
        for a_idx in range(n_accounts):
            bank_id = registry.banks[int(c_rng.integers(len(registry.banks)))].id
            home_loc: Location | None = (
                district_locs[int(c_rng.integers(len(district_locs)))] if district_locs else None
            )
            accounts.append(
                Account(
                    id=f"ACC-{cluster_id}-{a_idx:04d}",
                    bank_id=bank_id,
                    home_location_id=home_loc.id if home_loc else None,
                )
            )

        # 3. Footprint
        locality = cfg.footprint.locality
        r_min, r_max = _LOCALITY_RADIUS_KM[locality]
        radius_km = float(c_rng.uniform(r_min, r_max))
        # centre offset from district centroid
        offset_lat = c_rng.uniform(-0.3, 0.3)
        offset_lon = c_rng.uniform(-0.3, 0.3)
        footprint = ClusterFootprint(
            centre_lat=round(district.lat + offset_lat, 6),
            centre_lon=round(district.lon + offset_lon, 6),
            radius_km=radius_km,
            locality=locality,
        )

        # 4. Channel mix (global + cluster perturbation)
        base_mix = dict(cfg.channels.mix)
        raw_perturb = {k: v * float(c_rng.uniform(0.7, 1.3)) for k, v in base_mix.items()}
        channel_mix = _normalise(raw_perturb)

        # 5. Timing
        cluster_timing = _perturb_timing(cfg.timing, c_rng)

        # 6. Lifetime and start_day
        lifetime_days = float(
            c_rng.uniform(
                max(1.0, cfg.mule.lifetime_days * 0.5),
                cfg.mule.lifetime_days * 1.5,
            )
        )
        start_day = float(c_rng.uniform(0.0, max(0.0, cfg.world.days - 1.0)))

        clusters.append(
            MuleCluster(
                id=cluster_id,
                district_id=district.id,
                accounts=accounts,
                footprint=footprint,
                channel_mix=channel_mix,
                timing=cluster_timing,
                lifetime_days=lifetime_days,
                start_day=start_day,
            )
        )

    # 7. Bridge accounts (bridge_rate: share of cluster-1's accounts reused in cluster-0)
    if n >= 2 and cfg.network.bridge_rate > 0:
        b_rng = rng_for(cfg.seed, "bridge")
        src = clusters[0]
        dst = clusters[1]
        n_bridge = max(1, int(len(dst.accounts) * cfg.network.bridge_rate))
        bridge_accounts = b_rng.choice(len(src.accounts), size=n_bridge, replace=False)
        bridged = [src.accounts[i] for i in bridge_accounts]
        # inject into cluster-1's account list (creates genuine merges)
        new_accounts = list(dst.accounts) + bridged
        clusters[1] = MuleCluster(
            id=dst.id,
            district_id=dst.district_id,
            accounts=new_accounts,
            footprint=dst.footprint,
            channel_mix=dst.channel_mix,
            timing=dst.timing,
            lifetime_days=dst.lifetime_days,
            start_day=dst.start_day,
            is_bridge=True,
            bridge_partner_id=src.id,
        )

    return clusters
