"""Outcome entity and classify_outcome() (DOC 3 M4 ReconcileOutcome — pure, no I/O).

Outcomes are decided by the timers for misses; by incoming observations for hits/late.
LC-10: alerting owns the outcomes table.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from nakabandi.shared import Id, Policy, SimTime

if TYPE_CHECKING:
    from nakabandi.alerting.domain.alert import Alert


class OutcomeResult(StrEnum):
    HIT = "hit"
    LATE = "late"
    MISS = "miss"


class OutcomeSource(StrEnum):
    OFFICER = "officer"  # an investigating officer marked it (MarkOutcome)
    RECONCILED = "reconciled"  # decided by ReconcileOutcome from data or a timer


@dataclass(slots=True)
class Outcome:
    id: Id
    alert_id: Id
    result: str  # hit | late | miss
    observation_id: Id | None
    decided_at: SimTime
    source: str = OutcomeSource.RECONCILED.value
    actor_id: Id | None = None  # the officer, for source=officer
    location_id: Id | None = None  # the cash-out location an officer confirmed
    reason: str | None = None


def classify_outcome(
    alert: Alert,
    observation_at: SimTime | None,
    decided_at: SimTime,
    observation_id: Id | None,
    policy: Policy,
    outcome_id: Id,
) -> Outcome | None:
    """Classify a reconciliation outcome per DOC 3 M4 ReconcileOutcome.

    DOC 3 M4:
      hit:  observation within [window_start, window_end]
      late: after window_end within outcome.grace_hours
      miss: window_end + grace passed with none (decided by timers, not this function)

    Returns None if the observation is beyond the grace window (ignored).
    """
    if observation_at is None:
        # Timer-driven miss
        return Outcome(
            id=outcome_id,
            alert_id=alert.id,
            result="miss",
            observation_id=None,
            decided_at=decided_at,
        )

    # observation-driven: within window → hit; within grace → late; else ignore
    from datetime import timedelta

    grace_delta = timedelta(hours=policy.outcome.grace_hours)

    if alert.window_start <= observation_at <= alert.window_end:
        result = "hit"
    elif alert.window_end < observation_at <= alert.window_end + grace_delta:
        result = "late"
    else:
        return None  # outside grace window; ignore

    return Outcome(
        id=outcome_id,
        alert_id=alert.id,
        result=result,
        observation_id=observation_id,
        decided_at=decided_at,
    )
