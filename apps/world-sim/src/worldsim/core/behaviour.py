"""behaviour.py — Location choice, cash-out splitting, channel selection (DOC 3 M1).

Pure functions; no I/O, no side effects.

  choose_locations(cluster, registry, n, rng) -> list[Location]
      Combines issuing-bank footprint and runner footprint; returns n candidate
      cash-out locations weighted by activity_index.

  split_under_caps(total_paise, accounts, caps, rng) -> list[tuple[Account, int]]
      Splits a total amount across accounts/cards never exceeding per-transaction
      and per-day ATM caps (in paise). Returns (account, amount_paise) pairs.

  pick_channel(channel_mix, rng) -> str
      Samples one channel from the cluster's mix.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from worldsim.core.config import CapsConfig

if TYPE_CHECKING:
    from worldsim.core.clusters import Account, MuleCluster
    from worldsim.core.registry import Location, Registry


_INR_TO_PAISE: int = 100


def choose_locations(
    cluster: MuleCluster,
    registry: Registry,
    n: int,
    rng: np.random.Generator,
) -> list[Location]:
    """Pick n cash-out locations for one cluster event.

    Candidates are drawn from:
      1. The cluster's home district (issuing-bank footprint).
      2. Locations within the runner footprint radius of the cluster centroid.

    Weighted by activity_index; with replacement when candidates are few.
    """

    candidates: list[Location] = []

    # Issuing-bank footprint: locations in the cluster's origin district
    home_locs = registry.locations_in(cluster.district_id)
    candidates.extend(home_locs)

    # Runner footprint: locations within radius_km of the footprint centre
    fp = cluster.footprint
    for loc in registry.locations:
        if loc.district_id == cluster.district_id:
            continue  # already included
        dist_km = _haversine_km(fp.centre_lat, fp.centre_lon, loc.lat, loc.lon)
        if dist_km <= fp.radius_km:
            candidates.append(loc)

    if not candidates:
        # Fallback: all locations (should not happen with a well-built registry)
        candidates = list(registry.locations)

    # Weight by activity_index (floor at 0.01 so every location is reachable)
    weights = np.array([max(loc.activity_index, 0.01) for loc in candidates])
    weights /= weights.sum()

    replace = len(candidates) < n
    idxs = rng.choice(len(candidates), size=n, replace=replace, p=weights)
    return [candidates[i] for i in idxs]


def split_under_caps(
    total_paise: int,
    accounts: list[Account],
    caps: CapsConfig,
    channel: str,
    rng: np.random.Generator,
) -> list[tuple[Account, int]]:
    """Split total_paise across accounts, never exceeding per-txn/per-day caps.

    Returns list of (account, amount_paise) pairs whose amounts sum to total_paise.
    Caps are enforced in INR then converted to paise.
    """
    if channel == "ATM":
        txn_cap_paise = caps.card_atm_daily_inr * _INR_TO_PAISE
    elif channel == "BRANCH":
        txn_cap_paise = caps.card_atm_daily_inr * _INR_TO_PAISE  # same limit in model
    else:  # AGENT (AEPS)
        txn_cap_paise = caps.aeps_txn_inr * _INR_TO_PAISE

    txn_cap_paise = max(txn_cap_paise, 1)
    result: list[tuple[Account, int]] = []
    remaining = total_paise

    # Shuffle accounts to avoid always draining the same one first
    account_order = list(accounts)
    rng.shuffle(account_order)  # type: ignore[arg-type]

    for account in account_order:
        if remaining <= 0:
            break
        amount = min(remaining, txn_cap_paise)
        if amount <= 0:
            continue
        result.append((account, int(amount)))
        remaining -= amount

    # If still remaining (e.g., all accounts maxed), distribute remainder
    if remaining > 0 and result:
        last_account, last_amount = result[-1]
        result[-1] = (last_account, last_amount + remaining)

    return result


def pick_channel(channel_mix: dict[str, float], rng: np.random.Generator) -> str:
    """Sample one channel from the cluster's mix dict."""
    channels = list(channel_mix.keys())
    weights = np.array(list(channel_mix.values()), dtype=float)
    weights /= weights.sum()
    idx = int(rng.choice(len(channels), p=weights))
    return channels[idx]


# ---------------------------------------------------------------------------
# Internal geometry helpers
# ---------------------------------------------------------------------------

_EARTH_RADIUS_KM: float = 6371.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + (
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))
