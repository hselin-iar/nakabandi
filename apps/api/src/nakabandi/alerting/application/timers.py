"""EscalateAlert, ExpireAlert, ReviewLien: the alert clock (DOC 3 M4 timers.py).

DATABASE-DRIVEN, not scheduler-driven. Each `fire_due()` asks the database which alerts are due at
the current sim time (an indexed query) and acts on those only. Nothing is registered in memory,
so there is nothing to rebuild after a restart (DOC 3 M4 edge case: "Process restart:
RebuildTimers recreates escalation, expiry and lien-review timers") and no timer is bound to a
request's session. An earlier version registered a timer per alert and re-registered ALL of them
on every tick; the A11 stress run showed that starving the ingest path at a few thousand alerts.

Due-ness is a pure function of an alert's own fields and the sim clock:
  escalate  OPEN and window_start + escalate_after_min <= now
  expire    OPEN / ESCALATED / ACKNOWLEDGED and expires_at <= now (ACTIONED never expires)
  review    a pending or applied hold whose review_at <= now, once
"""

from __future__ import annotations

from datetime import datetime, timedelta

import structlog
from nakabandi_contracts.enums import AlertStatus

from nakabandi.alerting.application.ports import ActionRepo, AlertRepo
from nakabandi.alerting.domain.action import ActionStatus
from nakabandi.alerting.domain.alert import Alert, TimelineEntry
from nakabandi.shared import Clock, Policy, new_id

logger = structlog.get_logger(__name__)

BATCH = 200
"""At most this many alerts are acted on per class per tick, so one tick after a long time jump
stays short; the next tick takes the next batch."""


class EscalateAlert:
    """OPEN -> ESCALATED once an alert has gone unattended for escalate_after_min."""

    def __init__(self, alert_repo: AlertRepo, clock: Clock, policy: Policy) -> None:
        self._repo = alert_repo
        self._clock = clock
        self._policy = policy

    def fire_due(self) -> int:
        cutoff = self._clock.now() - timedelta(minutes=self._policy.alerting.escalate_after_min)
        ids = self._repo.list_escalation_due_ids(cutoff, BATCH)
        for alert_id in ids:
            self._fire(alert_id)
        return len(ids)

    def _fire(self, alert_id: str) -> None:
        alert: Alert | None = self._repo.get_by_id(alert_id)
        if alert is None or alert.status != AlertStatus.OPEN:
            return
        entry = TimelineEntry(
            id=new_id(),
            alert_id=alert.id,
            at=self._clock.now(),
            kind="escalated",
            actor_id=None,
            text_code="alert.escalated",
            text_params={},
        )
        try:
            alert.transition(AlertStatus.ESCALATED, entry)
            self._repo.save(alert)
            logger.info("alerting.escalated", alert_id=alert_id)
        except Exception:
            logger.exception("alerting.escalate.failed", alert_id=alert_id)


class ExpireAlert:
    """-> EXPIRED once an alert's window and grace are over and nobody acted on it."""

    def __init__(self, alert_repo: AlertRepo, clock: Clock) -> None:
        self._repo = alert_repo
        self._clock = clock

    def fire_due(self) -> int:
        ids = self._repo.list_expiry_due_ids(self._clock.now(), BATCH)
        for alert_id in ids:
            self._fire(alert_id)
        return len(ids)

    def _fire(self, alert_id: str) -> None:
        alert: Alert | None = self._repo.get_by_id(alert_id)
        if alert is None or alert.status in (AlertStatus.CLOSED, AlertStatus.EXPIRED):
            return
        entry = TimelineEntry(
            id=new_id(),
            alert_id=alert.id,
            at=self._clock.now(),
            kind="expired",
            actor_id=None,
            text_code="alert.expired",
            text_params={},
        )
        try:
            alert.transition(AlertStatus.EXPIRED, entry)
            self._repo.save(alert)
            logger.info("alerting.expired", alert_id=alert_id)
        except Exception:
            logger.exception("alerting.expire.failed", alert_id=alert_id)


class ReviewLien:
    """At a hold's review time, put a "review due" line on its alert's timeline.

    DOC 3 names the timer (timers.py: ReviewLien; LC-6 review_at_sim; lien.review_hours) but not
    what it does. The minimal safe reading: a lien needs a magistrate's review by review_at, so
    the alert's timeline shows it is due. It changes no status and sends nothing; whoever wants
    more (a reminder delivery, an escalation) adds it deliberately."""

    def __init__(self, alert_repo: AlertRepo, action_repo: ActionRepo, clock: Clock) -> None:
        self._alerts = alert_repo
        self._actions = action_repo
        self._clock = clock

    def fire_due(self) -> int:
        now = self._clock.now()
        fired = 0
        for action in self._actions.list_active_holds():  # holds are few; review_at is in params
            review_at = action.params.get("review_at")
            if isinstance(review_at, str) and datetime.fromisoformat(review_at) <= now:
                fired += self._fire(action.id)
        return fired

    def _fire(self, action_id: str) -> int:
        action = self._actions.get_by_id(action_id)
        if action is None or action.status not in (ActionStatus.PENDING, ActionStatus.APPLIED):
            return 0  # rejected or released: nothing left to review
        alert: Alert | None = self._alerts.get_by_id(action.alert_id)
        if alert is None:
            return 0
        if any(
            e.text_code == "alert.hold.review_due" and e.text_params.get("action_id") == action_id
            for e in alert.timeline
        ):
            return 0  # already noted: a review is noted once
        alert.timeline.append(
            TimelineEntry(
                id=new_id(),
                alert_id=alert.id,
                at=self._clock.now(),
                kind="lien_review_due",
                actor_id=None,
                text_code="alert.hold.review_due",
                text_params={"action_id": action_id},
            )
        )
        self._alerts.save(alert)
        logger.info("alerting.lien_review_due", alert_id=alert.id, action_id=action_id)
        return 1
