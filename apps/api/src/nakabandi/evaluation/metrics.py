"""metrics.py — Pure metric functions for the evaluation harness (DOC 3 B7).

All functions here are pure: no I/O, no database. They take plain Python
sequences / numpy arrays and return a scalar or a small data structure.

DSA (domain seam) rule: metrics know nothing about databases or configs.
Every function that returns a rate also returns n (sample size) so callers
can apply the n < 30 guard before storing rows.

Hand-computed fixture values for test_evaluation.py:
  hit_rate_at_k(preds=[[A, B], [C, D]], truth=[{A}, {E}], k=1)
    → forecast 0: top-1 = A ∈ {A} → hit; forecast 1: top-1 = C ∉ {E} → miss
    → hit_rate = 0.5

  precision_at_k(preds=[[A, B], [C, D]], truth=[{A, B}, {E}], k=2)
    → forecast 0: top-2 = {A, B} ∩ {A, B} / 2 = 1.0; forecast 1: 0.0
    → precision = 0.5
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from nakabandi.evaluation.config import BinStat, CurvePoint, LeadTimeStats, ShareStats

# ---------------------------------------------------------------------------
# n < 30 guard
# ---------------------------------------------------------------------------

_MIN_N = 30


def _guard(n: int, value: float) -> float:
    """Return value if n >= 30, else NaN (caller stores as NaN and filters)."""
    return value if n >= _MIN_N else math.nan


# ---------------------------------------------------------------------------
# Location metrics
# ---------------------------------------------------------------------------


def hit_rate_at_k(
    preds: Sequence[Sequence[str]],
    truth: Sequence[set[str]],
    k: int,
) -> tuple[float, int]:
    """Share of forecasts whose top-k contains ≥1 true cash-out location.

    Forecasts with empty truth sets are excluded (no-cashout complaints).

    Returns (rate, n). rate is NaN when n < 30.
    """
    hits = 0
    n = 0
    for ranked, true_locs in zip(preds, truth, strict=False):
        if not true_locs:
            continue  # no-cashout: excluded from hit rate
        n += 1
        if set(ranked[:k]) & true_locs:
            hits += 1
    rate = hits / n if n > 0 else math.nan
    return _guard(n, rate), n


def precision_at_k(
    preds: Sequence[Sequence[str]],
    truth: Sequence[set[str]],
    k: int,
) -> tuple[float, int]:
    """Mean fraction of top-k that are true cash-out locations.

    Forecasts with empty truth sets are excluded.

    Returns (rate, n). rate is NaN when n < 30.
    """
    precisions: list[float] = []
    for ranked, true_locs in zip(preds, truth, strict=False):
        if not true_locs:
            continue
        top_k = ranked[:k]
        if not top_k:
            precisions.append(0.0)
            continue
        precisions.append(len(set(top_k) & true_locs) / len(top_k))
    n = len(precisions)
    rate = float(np.mean(precisions)) if precisions else math.nan
    return _guard(n, rate), n


# ---------------------------------------------------------------------------
# Timing metrics
# ---------------------------------------------------------------------------


def lead_time_minutes(
    alert_times: Sequence[float],
    hit_event_times: Sequence[float],
) -> LeadTimeStats:
    """Median / p10 / p90 of (hit_event_time - alert_time) in minutes.

    Only pairs where the alert preceded the event (lead_time > 0) are included.
    Returns a LeadTimeStats with n=0 when no valid pairs exist.
    """
    leads = [ev - al for al, ev in zip(alert_times, hit_event_times, strict=False) if ev > al]
    n = len(leads)
    if n == 0:
        return LeadTimeStats(median=math.nan, p10=math.nan, p90=math.nan, n=0)
    arr = np.array(leads, dtype=float)
    return LeadTimeStats(
        median=float(np.median(arr)),
        p10=float(np.percentile(arr, 10)),
        p90=float(np.percentile(arr, 90)),
        n=n,
    )


# ---------------------------------------------------------------------------
# Calibration metrics
# ---------------------------------------------------------------------------


def brier_score(probs: Sequence[float], outcomes: Sequence[int]) -> tuple[float, int]:
    """Mean squared error between predicted probabilities and binary outcomes.

    Returns (brier, n). brier is NaN when n < 30.
    """
    p = np.array(probs, dtype=float)
    y = np.array(outcomes, dtype=float)
    n = len(p)
    score = float(np.mean((p - y) ** 2))
    return _guard(n, score), n


def reliability_curve(
    probs: Sequence[float],
    outcomes: Sequence[int],
    bins: int = 10,
) -> list[BinStat]:
    """Reliability (calibration) curve: fraction_of_positives vs mean_predicted.

    Returns one BinStat per non-empty bin.
    """
    p = np.array(probs, dtype=float)
    y = np.array(outcomes, dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    result: list[BinStat] = []
    for lo, hi in zip(edges[:-1], edges[1:], strict=False):
        mask = (p >= lo) & (p < hi) if hi < 1.0 else (p >= lo) & (p <= hi)
        n_bin = int(mask.sum())
        if n_bin == 0:
            continue
        result.append(
            BinStat(
                bin_lower=float(lo),
                bin_upper=float(hi),
                fraction_of_positives=float(y[mask].mean()),
                mean_predicted_value=float(p[mask].mean()),
                n=n_bin,
            )
        )
    return result


# ---------------------------------------------------------------------------
# Interception metrics
# ---------------------------------------------------------------------------


def interceptable_share(
    assessments: Sequence[bool],  # model said interceptable
    true_delays_min: Sequence[float],  # oracle: actual delay to cash-out
    true_etas_min: Sequence[float],  # oracle: min dispatch ETA
) -> ShareStats:
    """Precision and recall of the interceptable flag against oracle truth.

    Truth = cash-out delay > ETA (there was time to intercept).
    Returns ShareStats with NaN values when n_predicted < 30 or n_true < 30.
    """
    pred = np.array(assessments, dtype=bool)
    true_interceptable = np.array(
        [d > e for d, e in zip(true_delays_min, true_etas_min, strict=False)], dtype=bool
    )
    n_pred = int(pred.sum())
    n_true = int(true_interceptable.sum())

    if n_pred == 0:
        prec = math.nan
    else:
        prec = float((pred & true_interceptable).sum() / n_pred)

    if n_true == 0:
        rec = math.nan
    else:
        rec = float((pred & true_interceptable).sum() / n_true)

    prec = _guard(n_pred, prec)
    rec = _guard(n_true, rec)
    return ShareStats(precision=prec, recall=rec, n_predicted=n_pred, n_true=n_true)


def dispatches_per_interception(
    assessments: Sequence[bool],
    outcomes_intercepted: Sequence[bool],
) -> tuple[float, int]:
    """Mean number of dispatches needed per confirmed interception.

    Dispatches = number of True assessments; interceptions = True outcomes
    where the model flagged them. Returns (rate, n_dispatches).
    """
    dispatches = sum(1 for a in assessments if a)
    true_hits = sum(1 for a, o in zip(assessments, outcomes_intercepted, strict=False) if a and o)
    if true_hits == 0:
        return math.nan, dispatches
    return _guard(true_hits, dispatches / true_hits), dispatches


def false_hold_rate(
    assessments: Sequence[bool],
    truth_is_mule: Sequence[bool],
) -> tuple[float, int]:
    """False hold rate per 1,000 alerts: holds issued on innocent accounts.

    Returns (rate_per_1000, n_holds).
    """
    n_holds = sum(1 for a in assessments if a)
    false_holds = sum(1 for a, m in zip(assessments, truth_is_mule, strict=False) if a and not m)
    if n_holds == 0:
        return math.nan, 0
    rate = false_holds / n_holds * 1000.0
    return _guard(n_holds, rate), n_holds


# ---------------------------------------------------------------------------
# Cold-start curve
# ---------------------------------------------------------------------------

_COLD_START_BUCKETS = [
    ("0", lambda n: n == 0),
    ("1-3", lambda n: 1 <= n <= 3),
    ("4+", lambda n: n >= 4),
]


def cold_start_curve(
    prior_counts: Sequence[int],
    hits_at_k: Sequence[bool],
) -> list[CurvePoint]:
    """Hit-rate@k broken down by prior cash-out count per cluster.

    prior_counts: number of prior cash-outs observed for the cluster at forecast time
    hits_at_k:    whether the forecast contained a true cash-out in top-k

    Returns one CurvePoint per bucket that has ≥1 sample.
    """
    result: list[CurvePoint] = []
    for label, pred in _COLD_START_BUCKETS:
        indices = [i for i, n in enumerate(prior_counts) if pred(n)]
        if not indices:
            continue
        bucket_hits = sum(1 for i in indices if hits_at_k[i])
        n = len(indices)
        rate = bucket_hits / n
        result.append(CurvePoint(bucket=label, hit_rate_at_k=_guard(n, rate), n=n))
    return result


# ---------------------------------------------------------------------------
# Abstention metrics
# ---------------------------------------------------------------------------


def abstention_rate(n_total: int, n_abstained: int) -> tuple[float, int]:
    """Fraction of forecasts that abstained on at least one resolution level.

    Returns (rate, n_total).
    """
    if n_total == 0:
        return math.nan, 0
    return n_abstained / n_total, n_total
