"""priority(), queue_key() and rank_and_cap() (DOC 3 M4 budget.py — pure, seeded, deterministic).

Every cap and share comes from policy (alerting.budget_per_shift, shift_hours,
exploration_share); nothing is hard-coded here."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TypeVar

from nakabandi.shared import Policy, SimTime

if TYPE_CHECKING:
    from nakabandi.alerting.domain.alert import Alert


class Rankable(Protocol):
    """What ranking needs of an alert: nothing more. A queue is ranked from a few columns, not from
    whole alerts with their timelines (the A11 stress run: loading full alerts to re-rank a queue
    was the cost that grew with every alert raised)."""

    id: str
    priority: float
    created_at: SimTime
    budget_rank: int | None
    is_deferred: bool
    is_probe: bool


@dataclass(slots=True)
class QueueEntry:
    id: str
    priority: float
    created_at: SimTime
    budget_rank: int | None
    is_deferred: bool
    is_probe: bool


def priority(confidence: float, amount_paise: int, interception_probability: float) -> float:
    """DOC 3 M4: priority = confidence x log1p(amount) x interception_probability."""
    return confidence * math.log1p(max(amount_paise, 0)) * interception_probability


def shift_index(at: SimTime, policy: Policy) -> int:
    """Which shift (a policy.alerting.shift_hours-long slice of sim time) `at` falls in."""
    return int(at.timestamp() // (policy.alerting.shift_hours * 3600))


def queue_key(alert: Alert, policy: Policy) -> tuple[str, int]:
    """The queue an alert competes in: (jurisdiction, shift). The jurisdiction is the target's
    district, the district officers' queue, the first recipient of every alert (DOC 3 M4 routing);
    an alert whose district is unknown queues under "unscoped"."""
    return (alert.scope_district_id or "unscoped", shift_index(alert.created_at, policy))


def exploration_draw(alert_id: str, seed: str = "") -> float:
    """A deterministic draw in [0, 1) from the alert id (and an optional seed): the same alert
    always gets the same number, so a replay promotes the same probes."""
    digest = hashlib.md5(f"{seed}:{alert_id}".encode()).hexdigest()  # noqa: S324 - not security
    return (int(digest, 16) % 10_000) / 10_000.0


R = TypeVar("R", bound=Rankable)


def rank_and_cap(alerts: Sequence[R], policy: Policy, seed: str = "") -> list[R]:
    """Rank ONE queue's alerts (highest priority first; ties by age, then id) and apply the shift
    budget: the top `budget_per_shift` are visible, the rest are deferred (budget_rank > cap) and
    stay reachable under Backlog. With probability `exploration_share` a deferred alert is
    promoted with is_probe=True, drawn from its id, so the choice is reproducible.

    Sets budget_rank, is_deferred and is_probe in place and returns the alerts in rank order."""
    cap = policy.alerting.budget_per_shift
    share = policy.alerting.exploration_share
    ranked = sorted(alerts, key=lambda a: (-a.priority, a.created_at, a.id))
    for rank, alert in enumerate(ranked, start=1):
        alert.budget_rank = rank
        if rank <= cap:
            alert.is_deferred, alert.is_probe = False, False
        elif exploration_draw(alert.id, seed) < share:
            alert.is_deferred, alert.is_probe = False, True
        else:
            alert.is_deferred, alert.is_probe = True, False
    return ranked
