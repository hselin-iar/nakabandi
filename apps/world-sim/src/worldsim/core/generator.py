"""generator.py — World and World.step() (DOC 3 M1).

The central simulation engine. Pure; no I/O, no wall clock.

  World          holds clusters, registry, config; drives generation
  TruthEvent     internal truth (never leaves world-sim except via oracle API)
  World.step(t0, t1) -> list[TruthEvent]   generate events in (t0, t1]

Numeric convention throughout:
  - Times are floats: fractional days from sim epoch (day 0.0)
  - Paise are integers
  - Cluster/account ids are strings

Invariants asserted in tests:
  - Events returned sorted by event_time
  - Every cash-out event has event_time > complaint event_time
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from worldsim.core.behaviour import choose_locations, pick_channel, split_under_caps
from worldsim.core.clusters import Account, MuleCluster
from worldsim.core.config import SimConfig
from worldsim.core.registry import Registry
from worldsim.core.rng import rng_for
from worldsim.core.timing import sample_delay_array

# ---------------------------------------------------------------------------
# TruthEvent types (internal; NEVER imported by nakabandi.*)
# ---------------------------------------------------------------------------

ComplaintCategory = Literal["digital_arrest", "investment_scam", "upi_phishing", "task_job_scam"]
_CATEGORIES: list[ComplaintCategory] = [
    "digital_arrest",
    "investment_scam",
    "upi_phishing",
    "task_job_scam",
]


@dataclass(frozen=True)
class ComplaintTruth:
    external_ref: str
    cluster_id: str | None  # None = innocent (noise)
    account_id: str
    bank_id: str
    district_id: str
    category: ComplaintCategory
    amount_paise: int
    event_time: float  # fractional day
    is_innocent: bool = False


@dataclass(frozen=True)
class HopTruth:
    complaint_ref: str
    from_account_id: str
    to_account_id: str
    from_bank_id: str
    to_bank_id: str
    amount_paise: int
    layer: int
    event_time: float
    cluster_id: str | None


@dataclass(frozen=True)
class CashOutTruth:
    complaint_ref: str
    account_id: str
    bank_id: str
    location_id: str
    channel: str
    amount_paise: int
    event_time: float  # event_time > complaint event_time (asserted)
    cluster_id: str | None


TruthEvent = ComplaintTruth | HopTruth | CashOutTruth


# ---------------------------------------------------------------------------
# World
# ---------------------------------------------------------------------------


@dataclass
class World:
    """Simulation world. Call step(t0, t1) to advance."""

    cfg: SimConfig
    registry: Registry
    clusters: list[MuleCluster]
    # Real relative shares for the four ComplaintCategory values (real_seed.load_category_weights),
    # set by the caller (cli.py's _build_world does the CSV I/O; this module stays pure). Empty
    # means "uniform" — the previous, unweighted behaviour.
    category_weights: dict[str, float] = field(default_factory=dict)
    # internal counters (mutable)
    _complaint_counter: int = field(default=0, repr=False)
    _hop_counter: int = field(default=0, repr=False)

    def step(self, t0: float, t1: float) -> list[TruthEvent]:
        """Generate all truth events for the interval (t0, t1].

        Returns events sorted by event_time.
        No I/O; pure generation.
        """
        assert t0 <= t1, f"step requires t0 <= t1, got {t0} > {t1}"
        if t0 == t1:
            return []

        events: list[TruthEvent] = []
        interval_days = t1 - t0
        step_rng = rng_for(self.cfg.seed, "step", f"{t0:.6f}")

        # --- Complaint volume (Poisson) ---
        lambda_ = self.cfg.load.complaints_per_day * interval_days
        n_complaints = int(step_rng.poisson(lambda_))

        # --- State weights for geography ---
        state_weights_raw = self.cfg.geo.state_weights
        total = sum(state_weights_raw.values())
        state_ids = list(state_weights_raw.keys())
        state_probs = np.array([state_weights_raw[s] / total for s in state_ids])

        # Map districts to states
        district_by_state: dict[str, list[str]] = {}
        for d in self.registry.districts:
            district_by_state.setdefault(d.state_id, []).append(d.id)

        # --- Generate complaint times (uniform in interval) ---
        complaint_times = np.sort(step_rng.uniform(t0, t1, size=n_complaints))

        for _i, ctime in enumerate(complaint_times):
            self._complaint_counter += 1
            ext_ref = f"EXT-{self._complaint_counter:08d}"

            # Is this complaint innocent? (layer-1 account is not a mule)
            is_innocent = step_rng.random() < self.cfg.noise.innocent_layer1_rate
            cluster: MuleCluster | None = None

            if not is_innocent:
                # Assign to an active cluster
                active = [
                    c for c in self.clusters if c.start_day <= ctime < c.start_day + c.lifetime_days
                ]
                if active:
                    idx = int(step_rng.integers(len(active)))
                    cluster = active[idx]

            # Geography: pick state then district
            state_idx = int(step_rng.choice(len(state_ids), p=state_probs))
            chosen_state = state_ids[state_idx]
            dists_in_state = district_by_state.get(chosen_state, [])
            if not dists_in_state:
                dists_in_state = [d.id for d in self.registry.districts]
            district_id = dists_in_state[int(step_rng.integers(len(dists_in_state)))]

            # Layer-1 account: from cluster if mule, else synthetic innocent account
            if cluster and cluster.accounts:
                l1_account = cluster.accounts[int(step_rng.integers(len(cluster.accounts)))]
            else:
                l1_account = Account(
                    id=f"INNO-{ext_ref}",
                    bank_id=self.registry.banks[
                        int(step_rng.integers(len(self.registry.banks)))
                    ].id,
                    home_location_id=None,
                )

            # Amount: lognormal
            mean_ln = math.log(self.cfg.amounts.mean_paise)
            sigma_ln = self.cfg.amounts.shape_sigma
            amount_paise = int(max(1, math.exp(step_rng.normal(mean_ln, sigma_ln))))

            # Category: real relative shares among the four locked categories when
            # `category_weights` was loaded from data/seed/complaint_category_priors.csv
            # (real_seed.load_category_weights); uniform otherwise (no I/O in this module).
            if self.category_weights:
                probs = [self.category_weights[c] for c in _CATEGORIES]
                cat_idx = int(step_rng.choice(len(_CATEGORIES), p=probs))
            else:
                cat_idx = int(step_rng.integers(len(_CATEGORIES)))
            category: ComplaintCategory = _CATEGORIES[cat_idx]

            complaint = ComplaintTruth(
                external_ref=ext_ref,
                cluster_id=cluster.id if cluster else None,
                account_id=l1_account.id,
                bank_id=l1_account.bank_id,
                district_id=district_id,
                category=category,
                amount_paise=amount_paise,
                event_time=float(ctime),
                is_innocent=is_innocent,
            )
            events.append(complaint)

            if is_innocent or cluster is None:
                continue

            # --- Hops (2..layers_max layers) ---
            n_hops = int(
                step_rng.integers(
                    self.cfg.network.layers_min,
                    self.cfg.network.layers_max + 1,
                )
            )
            prev_account = l1_account
            hop_amount = amount_paise
            for layer in range(1, n_hops + 1):
                self._hop_counter += 1
                if cluster.accounts:
                    to_account = cluster.accounts[int(step_rng.integers(len(cluster.accounts)))]
                else:
                    to_account = l1_account
                hop = HopTruth(
                    complaint_ref=ext_ref,
                    from_account_id=prev_account.id,
                    to_account_id=to_account.id,
                    from_bank_id=prev_account.bank_id,
                    to_bank_id=to_account.bank_id,
                    amount_paise=hop_amount,
                    layer=layer,
                    event_time=float(ctime),  # hops happen near complaint time
                    cluster_id=cluster.id,
                )
                events.append(hop)
                prev_account = to_account
                # Amount decays slightly through layers (mule takes cut)
                hop_amount = max(1, int(hop_amount * step_rng.uniform(0.85, 1.0)))

            # --- Cash-outs ---
            channel = pick_channel(cluster.channel_mix, step_rng)
            splits = split_under_caps(
                amount_paise,
                cluster.accounts,
                self.cfg.caps,
                channel,
                step_rng,
            )
            # Draw one delay per split
            n_splits = len(splits)
            delays = sample_delay_array(cluster.timing, step_rng, n_splits)
            cash_out_locs = choose_locations(cluster, self.registry, n_splits, step_rng)

            for (cashout_account, cashout_amount), delay_min, loc in zip(
                splits, delays, cash_out_locs, strict=False
            ):
                cashout_time = float(ctime) + delay_min / (24 * 60)  # convert min → days
                cashout = CashOutTruth(
                    complaint_ref=ext_ref,
                    account_id=cashout_account.id,
                    bank_id=cashout_account.bank_id,
                    location_id=loc.id,
                    channel=channel,
                    amount_paise=int(cashout_amount),
                    event_time=cashout_time,
                    cluster_id=cluster.id,
                )
                events.append(cashout)

        # Sort by event_time (required by observe() and tests)
        events.sort(key=lambda e: e.event_time)
        return events
