"""EscalateAlert, ExpireAlert, RebuildTimers (DOC 3 M4 timers.py).

Timers use the injected Scheduler and Clock.
RebuildTimers recreates escalation and expiry timers from open alerts at boot
(DOC 3 M4 edge case: "Process restart: RebuildTimers recreates escalation, expiry ...").
"""

from __future__ import annotations

from datetime import datetime

import structlog
from nakabandi_contracts.enums import AlertStatus

from nakabandi.alerting.application.ports import ActionRepo, AlertRepo
from nakabandi.alerting.application.reconcile import ReconcileOutcome
from nakabandi.alerting.domain.action import ActionStatus
from nakabandi.alerting.domain.alert import Alert, TimelineEntry
from nakabandi.shared import Clock, Policy, Scheduler, SimTime, new_id

logger = structlog.get_logger(__name__)


class EscalateAlert:
    """Transition OPEN → ESCALATED when the escalation timer fires."""

    def __init__(self, alert_repo: AlertRepo, clock: Clock, scheduler: Scheduler) -> None:
        self._repo = alert_repo
        self._clock = clock
        self._scheduler = scheduler

    def schedule(self, alert_id: str, at: SimTime) -> None:
        """Register an escalation timer for this alert."""
        self._scheduler.call_at(
            key=f"escalate:{alert_id}",
            at=at,
            fn=lambda: self._fire(alert_id),
        )

    def _fire(self, alert_id: str) -> None:
        alert: Alert | None = self._repo.get_by_id(alert_id)
        if alert is None or alert.status != AlertStatus.OPEN:
            return
        now = self._clock.now()
        entry = TimelineEntry(
            id=new_id(),
            alert_id=alert.id,
            at=now,
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
    """Transition → EXPIRED when the expiry timer fires."""

    def __init__(self, alert_repo: AlertRepo, clock: Clock, scheduler: Scheduler) -> None:
        self._repo = alert_repo
        self._clock = clock
        self._scheduler = scheduler

    def schedule(self, alert_id: str, at: SimTime) -> None:
        """Register an expiry timer for this alert."""
        self._scheduler.call_at(
            key=f"expire:{alert_id}",
            at=at,
            fn=lambda: self._fire(alert_id),
        )

    def _fire(self, alert_id: str) -> None:
        alert: Alert | None = self._repo.get_by_id(alert_id)
        if alert is None or alert.status in (AlertStatus.CLOSED, AlertStatus.EXPIRED):
            return
        now = self._clock.now()
        entry = TimelineEntry(
            id=new_id(),
            alert_id=alert.id,
            at=now,
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

    def __init__(
        self, alert_repo: AlertRepo, action_repo: ActionRepo, clock: Clock, scheduler: Scheduler
    ) -> None:
        self._alerts = alert_repo
        self._actions = action_repo
        self._clock = clock
        self._scheduler = scheduler

    def schedule(self, action_id: str, at: SimTime) -> None:
        self._scheduler.call_at(key=f"review:{action_id}", at=at, fn=lambda: self._fire(action_id))

    def _fire(self, action_id: str) -> None:
        action = self._actions.get_by_id(action_id)
        if action is None or action.status not in (ActionStatus.PENDING, ActionStatus.APPLIED):
            return  # rejected or released: nothing left to review
        alert: Alert | None = self._alerts.get_by_id(action.alert_id)
        if alert is None:
            return
        if any(
            e.text_code == "alert.hold.review_due" and e.text_params.get("action_id") == action_id
            for e in alert.timeline
        ):
            return  # already noted (a rebuild can register the same timer twice)
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


class RebuildTimers:
    """Recreate in-memory escalation and expiry timers from open alerts at process boot.

    DOC 3 M4 edge case: "Process restart: RebuildTimers recreates escalation,
    expiry and lien-review timers from open alerts."
    """

    def __init__(
        self,
        alert_repo: AlertRepo,
        escalate: EscalateAlert,
        expire: ExpireAlert,
        policy: Policy,
        clock: Clock,
        review: ReviewLien | None = None,
        action_repo: ActionRepo | None = None,
        reconcile: ReconcileOutcome | None = None,
    ) -> None:
        self._repo = alert_repo
        self._escalate = escalate
        self._expire = expire
        self._policy = policy
        self._clock = clock
        self._review = review
        self._actions = action_repo
        self._reconcile = reconcile

    def run(self) -> int:
        """Rebuild timers for all open/escalated alerts. Returns count rebuilt."""
        from datetime import timedelta

        open_alerts: list[Alert] = self._repo.list_open()
        escalate_after = timedelta(minutes=self._policy.alerting.escalate_after_min)
        rebuilt = 0

        for alert in open_alerts:
            # Only OPEN alerts get an escalation timer (ESCALATED ones already past it)
            # An overdue timer is still registered: it fires on the next run_due, so a restart
            # (or a tick that jumped past several deadlines) never silently drops it.
            if alert.status == AlertStatus.OPEN:
                self._escalate.schedule(alert.id, alert.window_start + escalate_after)

            # Every non-terminal alert gets an expiry timer
            self._expire.schedule(alert.id, alert.expires_at)

            rebuilt += 1

        # Miss timers cover every alert still without a reconciled outcome, whatever its status: an
        # expired or closed alert still gets its miss (or its late hit) decided.
        if self._reconcile is not None:
            for alert in self._repo.list_awaiting_outcome():
                self._reconcile.schedule_miss(alert)

        # Lien-review timers live on actions, not on alerts (an actioned alert is not "open")
        if self._review is not None and self._actions is not None:
            for action in self._actions.list_active_holds():
                review_at = action.params.get("review_at")
                if isinstance(review_at, str):
                    self._review.schedule(action.id, datetime.fromisoformat(review_at))

        logger.info("alerting.timers.rebuilt", count=rebuilt)
        return rebuilt
