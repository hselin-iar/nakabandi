"""EscalateAlert, ExpireAlert, RebuildTimers (DOC 3 M4 timers.py).

Timers use the injected Scheduler and Clock.
RebuildTimers recreates escalation and expiry timers from open alerts at boot
(DOC 3 M4 edge case: "Process restart: RebuildTimers recreates escalation, expiry ...").
"""

from __future__ import annotations

import structlog
from nakabandi_contracts.enums import AlertStatus

from nakabandi.alerting.application.ports import AlertRepo
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
    ) -> None:
        self._repo = alert_repo
        self._escalate = escalate
        self._expire = expire
        self._policy = policy
        self._clock = clock

    def run(self) -> int:
        """Rebuild timers for all open/escalated alerts. Returns count rebuilt."""
        from datetime import timedelta

        open_alerts: list[Alert] = self._repo.list_open()
        now = self._clock.now()
        escalate_after = timedelta(minutes=self._policy.alerting.escalate_after_min)
        rebuilt = 0

        for alert in open_alerts:
            # Only OPEN alerts get an escalation timer (ESCALATED ones already past it)
            if alert.status == AlertStatus.OPEN:
                escalate_at = alert.window_start + escalate_after
                if escalate_at > now:
                    self._escalate.schedule(alert.id, escalate_at)

            # Every non-terminal alert gets an expiry timer
            if alert.expires_at > now:
                self._expire.schedule(alert.id, alert.expires_at)

            rebuilt += 1

        logger.info("alerting.timers.rebuilt", count=rebuilt)
        return rebuilt
