"""types.py — Forecast domain value objects (DOC 3 M2, LC-4).

All shapes here match the LC-4 wire format consumed by interception, alerting,
casework, analytics, and the web app.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from nakabandi_contracts.enums import Resolution

from nakabandi.shared import Id, SimTime


@dataclass(frozen=True)
class Candidate:
    """A scored location candidate (one cash-out target hypothesis)."""

    location_id: Id
    cell_id: Id
    district_id: Id
    lat: float
    lon: float
    distance_to_home_km: float
    distance_to_centroid_km: float
    channel: str  # expected cash-out channel
    activity_index: float  # from registry
    bank_id: str = ""  # issuing bank of the candidate location (for same_bank feature)


@dataclass(frozen=True)
class FeatureRow:
    """Feature vector for a single candidate (DOC 3 M2, FEATURE_REGISTRY)."""

    same_bank: float  # 1.0 if issuing bank matches candidate bank
    dist_home_km: float  # distance from layer-1 victim's home branch
    dist_centroid_km: float  # distance from cluster centroid
    cluster_loc_count: float  # how many prior cash-outs at this location
    cluster_cell_count: float  # how many prior cash-outs in this cell
    recency_days: float  # days since the most recent cash-out at this location
    channel: str  # channel label ("ATM", "BRANCH", "AGENT")
    hour_sin: float  # sin of expected cash-out hour (cyclical)
    hour_cos: float  # cos of expected cash-out hour (cyclical)
    amount_log: float  # log(1 + amount_paise)
    amount_x_dist: float  # amount_log × dist_home_km interaction
    activity_index: float  # location activity from registry
    cluster_size_log: float  # log(1 + cluster.unique_accounts)
    global_cashout_count: float = 0.0  # as-of cash-out count at this location, across ALL clusters
    global_cashout_rate: float = 0.0  # Laplace-smoothed global_cashout_count / global total


@dataclass
class RankedItem:
    """One item in a level forecast (id, probability, rank)."""

    id: Id
    prob: float
    rank: int


@dataclass(frozen=True)
class LevelForecast:
    """Forecast for one geographic resolution (district / cell / location)."""

    resolution: Resolution
    abstained: bool
    confidence: float
    items: list[RankedItem] = field(default_factory=list)


@dataclass(frozen=True)
class TimingForecast:
    """Conditional timing forecast from the MixtureTimingModel (LC-4 shape).

    All probabilities are conditional: P(T <= elapsed + h | T > elapsed).
    residual_mass = P(T > elapsed) — shared with interception.domain.probability.
    """

    weights: list[float]  # [w_fast, w_slow]
    medians_min: list[float]  # per-component median delays in minutes
    sigmas: list[float]  # per-component lognormal sigmas
    elapsed_min: float  # minutes since complaint was reported
    residual_mass: float  # P(T > elapsed)
    p30: float  # P(T <= elapsed+30 | T > elapsed)
    p60: float  # P(T <= elapsed+60 | T > elapsed)
    p120: float  # P(T <= elapsed+120 | T > elapsed)


@dataclass(frozen=True)
class EvidenceStatement:
    """One human-readable evidence item (rule-based, from explain())."""

    code: str  # stable machine code; S5 localises other languages from this
    params: dict[str, str] = field(default_factory=dict)
    text_en: str = ""  # English text filled by explain()


@dataclass(frozen=True)
class Forecast:
    """Full forecast for one complaint (LC-4 shape, DOC 3 M2).

    Probabilities must sum to 1 ± 1e-6 at every non-abstained level (asserted by Forecaster).
    """

    id: Id
    complaint_id: Id
    cluster_id: Id | None
    generated_at: SimTime
    model_versions: dict[str, str]  # {"scorer": ..., "timing": ...}
    levels: dict[str, LevelForecast]  # keyed by Resolution.value
    timing: TimingForecast
    confidence: float
    novelty: float
    stale: bool
    evidence: list[EvidenceStatement] = field(default_factory=list)


@dataclass(frozen=True)
class ClusterContext:
    """Snapshot of what the forecast domain knows about a cluster.

    All observations are bounded by as_of (LC-2 as-of rule).
    This is the ONLY thing passed to forecast domain functions — no I/O inside.
    """

    complaint_id: Id
    cluster_id: Id | None
    as_of: SimTime
    # Complaint details
    amount_paise: int
    reported_at: SimTime
    layer1_account_id: Id
    layer1_bank_id: str
    layer1_home_lat: float | None
    layer1_home_lon: float | None
    # Cluster stats (empty for novel clusters)
    unique_accounts: int
    total_cashout_paise: int
    cashout_channel_counts: dict[str, int]  # channel -> count
    cashout_location_counts: dict[Id, int]  # location_id -> count
    cashout_cell_counts: dict[Id, int]  # cell_id -> count
    cashout_location_recency: dict[Id, float]  # location_id -> days_since
    centroid_lat: float | None
    centroid_lon: float | None
    radius_km: float
    # Prior cash-out count for timing shrinkage
    prior_cashout_count: int
    # Elapsed time since complaint reported (for timing conditioning)
    elapsed_min: float
    # Global (cross-cluster) as-of cash-out density — the hotspot base-rate signal.
    # Unlike cashout_location_counts (this cluster only), these counts span every cluster's
    # cash-outs observed by `as_of`. Empty/zero for a build before any global stats are wired.
    global_cashout_location_counts: dict[Id, int] = field(default_factory=dict)
    global_cashout_total: int = 0  # total cash-outs, across all locations, observed by as_of
    global_n_locations: int = 0  # size of the location universe (Laplace smoothing denominator)
