"""features.py — FEATURE_REGISTRY, BLOCKLIST, and build_features() (DOC 3 M2).

FEATURE_REGISTRY: canonical ordered list of feature names.
BLOCKLIST: names that can NEVER enter the registry (demographic / neighbourhood-profile terms).
build_features(ctx, cand) -> FeatureRow: pure function, no I/O.

BLOCKLIST test: any test_features.py must import BLOCKLIST and assert no name in
FEATURE_REGISTRY intersects it.
"""

from __future__ import annotations

import math

from nakabandi.forecast.domain.types import Candidate, ClusterContext, FeatureRow

# ---------------------------------------------------------------------------
# FEATURE_REGISTRY — canonical, ordered list of allowed feature names (LC-7).
# Any model MUST only use names from this list.
# ---------------------------------------------------------------------------
FEATURE_REGISTRY: tuple[str, ...] = (
    "same_bank",
    "dist_home_km",
    "dist_centroid_km",
    "cluster_loc_count",
    "cluster_cell_count",
    "recency_days",
    "channel",
    "hour_sin",
    "hour_cos",
    "amount_log",
    "amount_x_dist",
    "activity_index",
    "cluster_size_log",
)

# ---------------------------------------------------------------------------
# BLOCKLIST — names that may NEVER enter FEATURE_REGISTRY.
# Demographic or neighbourhood-profile terms that could encode protected
# characteristics or violate DOC 1 §1.5 ethics guardrails.
# ---------------------------------------------------------------------------
BLOCKLIST: frozenset[str] = frozenset(
    {
        # Demographic proxies
        "religion",
        "caste",
        "gender",
        "ethnicity",
        "age",
        "language",
        "nationality",
        "tribe",
        # Neighbourhood/socioeconomic
        "income",
        "poverty",
        "literacy",
        "slum",
        "wealthy",
        "neighbourhood_type",
        "population_density",
        "crime_rate",
        # Personal identifiers
        "name",
        "aadhaar",
        "pan",
        "voter_id",
        "phone",
        "dob",
    }
)


# ---------------------------------------------------------------------------
# build_features — pure function, no I/O
# ---------------------------------------------------------------------------


def build_features(
    ctx: ClusterContext,
    cand: Candidate,
    expected_hour: float = 12.0,
) -> FeatureRow:
    """Compute a FeatureRow for a single candidate.

    Parameters
    ----------
    ctx:
        Cluster context (as-of bounded, no future data).
    cand:
        The candidate location being scored.
    expected_hour:
        Expected cash-out hour (0–23); used for hour_sin/hour_cos cyclical encoding.
        Defaults to noon; the use case passes the value from the timing model or a prior.
    """
    # same_bank: 1 if candidate bank matches the layer-1 victim's issuing bank
    same_bank = 1.0 if cand.bank_id == ctx.layer1_bank_id else 0.0

    dist_home = cand.distance_to_home_km
    dist_centroid = cand.distance_to_centroid_km

    loc_count = float(ctx.cashout_location_counts.get(cand.location_id, 0))
    cell_count = float(ctx.cashout_cell_counts.get(cand.cell_id, 0))

    # recency_days: days since the most recent cash-out at this location.
    # NaN for locations the cluster has never visited — HGB handles NaN as a distinct
    # "missing" category and learns the optimal split direction from data (strictly
    # better than the previous 365-day sentinel which was far outside real support).
    _raw_recency = ctx.cashout_location_recency.get(cand.location_id)
    recency = float(_raw_recency) if _raw_recency is not None else float("nan")

    # Cyclical hour encoding
    hour_rad = 2 * math.pi * expected_hour / 24.0
    hour_sin = math.sin(hour_rad)
    hour_cos = math.cos(hour_rad)

    amount_log = math.log1p(float(ctx.amount_paise))
    amount_x_dist = amount_log * dist_home
    cluster_size_log = math.log1p(float(ctx.unique_accounts))

    return FeatureRow(
        same_bank=same_bank,
        dist_home_km=dist_home,
        dist_centroid_km=dist_centroid,
        cluster_loc_count=loc_count,
        cluster_cell_count=cell_count,
        recency_days=recency,
        channel=cand.channel,
        hour_sin=hour_sin,
        hour_cos=hour_cos,
        amount_log=amount_log,
        amount_x_dist=amount_x_dist,
        activity_index=cand.activity_index,
        cluster_size_log=cluster_size_log,
    )
