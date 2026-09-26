"""observe.py — Observation lag; converts TruthEvents to ObservedEvents (DOC 3 M1).

observe(events, cfg, rng) -> list[ObservedEvent]

Guarantee (asserted + tested): observed_at >= event_at for every event.

Observed times:
  - ComplaintTruth: observed at reported_event_at = event_time + report_lag
  - HopTruth: observed together with the complaint (same observed_at)
  - CashOutTruth: observed at event_time + observation_lag (sampled from cfg.lag)

ObservedEvent is a union type that maps to the LC-1 batch shapes via writer/batches.py.
Times are fractional days (floats); writer converts to ISO-8601 strings.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from worldsim.core.config import SimConfig
from worldsim.core.generator import CashOutTruth, ComplaintTruth, HopTruth, TruthEvent

# ---------------------------------------------------------------------------
# ObservedEvent types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ObservedComplaint:
    external_ref: str
    cluster_id: str | None
    account_id: str
    bank_id: str
    home_location_id: str | None
    district_id: str
    category: str
    amount_paise: int
    credited_at: float  # event_time (fractional days)
    reported_event_at: float  # == credited_at (simplification; victim reports same day)
    observed_at: float  # >= reported_event_at (lag applied)
    is_innocent: bool


@dataclass(frozen=True)
class ObservedHop:
    complaint_ref: str
    from_account_id: str
    to_account_id: str
    from_bank_id: str
    to_bank_id: str
    amount_paise: int
    layer: int
    event_at: float
    observed_at: float  # >= event_at


@dataclass(frozen=True)
class ObservedCashOut:
    complaint_ref: str
    account_id: str
    bank_id: str
    location_id: str
    channel: str
    amount_paise: int
    event_at: float
    observed_at: float  # >= event_at


ObservedEvent = ObservedComplaint | ObservedHop | ObservedCashOut


# ---------------------------------------------------------------------------
# observe()
# ---------------------------------------------------------------------------

_DAYS_PER_HOUR: float = 1.0 / 24.0


def observe(
    events: list[TruthEvent],
    cfg: SimConfig,
    rng: np.random.Generator,
) -> list[ObservedEvent]:
    """Apply observation lag and return ObservedEvents sorted by observed_at.

    Invariant: observed_at >= event_at for EVERY returned event.
    """
    # Pre-compute observation lag for all events in one draw
    lag_min_h = cfg.lag.min
    lag_med_h = cfg.lag.median
    lag_max_h = cfg.lag.max

    # Triangular distribution for lag (min, mode=median, max) in hours
    n = len(events)
    if n == 0:
        return []

    # Use the caller's own rng (each caller seeds it uniquely per day/tick — cli.py's
    # "observe_step"/day, runner.py's "live_observe"/tick). Reseeding here from `n` alone
    # (event count) instead made every call with the same count draw an identical lag
    # sequence, silently defeating that per-call uniqueness.
    lags_h = rng.triangular(lag_min_h, lag_med_h, lag_max_h, size=n)
    lags_days = lags_h * _DAYS_PER_HOUR  # convert hours → days

    # Index complaints by ref so hops can share their observed_at
    complaint_observed_at: dict[str, float] = {}
    result: list[ObservedEvent] = []

    for i, event in enumerate(events):
        lag = float(lags_days[i])

        if isinstance(event, ComplaintTruth):
            reported_at = event.event_time  # simplification
            obs_at = max(reported_at, event.event_time + lag)  # guarantee >= event_time
            assert obs_at >= event.event_time, "observe invariant violated for complaint"
            complaint_observed_at[event.external_ref] = obs_at
            result.append(
                ObservedComplaint(
                    external_ref=event.external_ref,
                    cluster_id=event.cluster_id,
                    account_id=event.account_id,
                    bank_id=event.bank_id,
                    home_location_id=None,  # not in truth; registry lookup would be needed
                    district_id=event.district_id,
                    category=event.category,
                    amount_paise=event.amount_paise,
                    credited_at=event.event_time,
                    reported_event_at=reported_at,
                    observed_at=obs_at,
                    is_innocent=event.is_innocent,
                )
            )

        elif isinstance(event, HopTruth):
            # Hops observed together with their complaint; reuse if already seen
            obs_at = complaint_observed_at.get(
                event.complaint_ref,
                event.event_time + lag,
            )
            obs_at = max(obs_at, event.event_time)
            assert obs_at >= event.event_time, "observe invariant violated for hop"
            result.append(
                ObservedHop(
                    complaint_ref=event.complaint_ref,
                    from_account_id=event.from_account_id,
                    to_account_id=event.to_account_id,
                    from_bank_id=event.from_bank_id,
                    to_bank_id=event.to_bank_id,
                    amount_paise=event.amount_paise,
                    layer=event.layer,
                    event_at=event.event_time,
                    observed_at=obs_at,
                )
            )

        elif isinstance(event, CashOutTruth):
            obs_at = max(event.event_time, event.event_time + lag)
            assert obs_at >= event.event_time, "observe invariant violated for cash-out"
            result.append(
                ObservedCashOut(
                    complaint_ref=event.complaint_ref,
                    account_id=event.account_id,
                    bank_id=event.bank_id,
                    location_id=event.location_id,
                    channel=event.channel,
                    amount_paise=event.amount_paise,
                    event_at=event.event_time,
                    observed_at=obs_at,
                )
            )

    # Sort by observed_at
    result.sort(key=lambda e: e.observed_at if hasattr(e, "observed_at") else 0.0)
    return result
