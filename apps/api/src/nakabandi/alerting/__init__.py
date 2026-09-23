"""Public facade of the alerting module: what other modules may import (DOC 3 M4).

AlertService is constructed per-request (like AccessService) on the caller's
SQLAlchemy session, so a raise_or_merge and its timeline entries share one transaction.

Exports:
  AlertService   — raise_or_merge, acknowledge, on_cluster_merged, rebuild_timers,
                   get_alert, list_alerts
  AlertResult    — result returned to pipeline Stage 5
  SseHub         — shared hub (also used by analytics for heat.version)
  SseEvent       — typed event for broadcast
"""

from __future__ import annotations

from collections.abc import Mapping, Set

from nakabandi_contracts.enums import Permission, Role
from sqlalchemy.orm import Session

from nakabandi.alerting.application.acknowledge import AcknowledgeAlert
from nakabandi.alerting.application.raise_or_merge import AlertResult, RaiseOrMergeAlert
from nakabandi.alerting.application.timers import EscalateAlert, ExpireAlert, RebuildTimers
from nakabandi.alerting.domain.alert import Alert
from nakabandi.alerting.infrastructure.channels.sse_hub import SseEvent, SseHub
from nakabandi.alerting.infrastructure.repos import SqlAlertRepo
from nakabandi.shared import Clock, Policy, Scheduler

__all__ = [
    "AlertService",
    "AlertResult",
    "SseHub",
    "SseEvent",
]


class AlertService:
    """Façade: the ONLY alerting object other modules may import.

    Instantiated per-request on the caller's session (so operations share the
    caller's unit of work) or once at startup for hub/scheduler access.
    """

    def __init__(
        self,
        session: Session,
        clock: Clock,
        policy: Policy,
        scheduler: Scheduler,
        role_permissions: Mapping[Role, Set[Permission]],
        sse_hub: SseHub,
    ) -> None:
        self._repo = SqlAlertRepo(session)
        self._clock = clock
        self._policy = policy
        self._scheduler = scheduler
        self._role_permissions = role_permissions
        self._hub = sse_hub

        # Build timer use cases (they share the same repo/clock/scheduler)
        self._escalate = EscalateAlert(self._repo, clock, scheduler)
        self._expire = ExpireAlert(self._repo, clock, scheduler)

        self._raise_or_merge = RaiseOrMergeAlert(
            alert_repo=self._repo,
            policy=policy,
            clock=clock,
            scheduler=scheduler,
            escalate_fn=self._escalate.schedule,
            expire_fn=self._expire.schedule,
        )
        self._acknowledge = AcknowledgeAlert(self._repo, policy, clock, role_permissions)
        self._rebuild_timers = RebuildTimers(
            alert_repo=self._repo,
            escalate=self._escalate,
            expire=self._expire,
            policy=policy,
            clock=clock,
        )

    # ------------------------------------------------------------------
    # Pipeline interface (called by pipeline.ProcessComplaint Stage 5)
    # ------------------------------------------------------------------

    def raise_or_merge(self, forecast: object, assessments: list[object]) -> AlertResult:
        result = self._raise_or_merge.run(forecast, assessments)
        # Publish alert.created SSE for each newly raised alert
        for aid in result.alert_ids:
            self._hub.publish(
                SseEvent(
                    name="alert.created" if result.created else "alert.updated",
                    data={"alert_id": aid, "version": 1},
                    alert_id=aid,
                )
            )
        return result

    # ------------------------------------------------------------------
    # Action: acknowledge
    # ------------------------------------------------------------------

    def acknowledge(self, principal: object, alert_id: str) -> Alert:
        alert = self._acknowledge.run(principal, alert_id)  # type: ignore[arg-type]
        self._hub.publish(
            SseEvent(
                name="alert.updated",
                data={"alert_id": alert.id, "version": 2},
                alert_id=alert.id,
            )
        )
        return alert

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_alert(self, alert_id: str) -> Alert | None:
        return self._repo.get_by_id(alert_id)

    def list_alerts(
        self,
        principal: object,
        *,
        status: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Alert], str | None]:
        return self._repo.list_by_scope(status=status, cursor=cursor, limit=limit)

    # ------------------------------------------------------------------
    # Timer management
    # ------------------------------------------------------------------

    def rebuild_timers(self) -> int:
        return self._rebuild_timers.run()

    # ------------------------------------------------------------------
    # Cluster merge re-keying (DOC 3 M4 edge case)
    # ------------------------------------------------------------------

    def on_cluster_merged(self, from_cluster_id: str, into_cluster_id: str) -> None:
        """Re-key dedup_keys when two clusters merge (ClusterMerged event).

        Finds open alerts belonging to from_cluster_id, updates their cluster_ref
        and dedup_key to use into_cluster_id. If two open alerts now share the same
        dedup_key, closes the newer one as merged (DOC 3 M4 edge case).
        """
        from nakabandi_contracts.enums import AlertStatus

        from nakabandi.alerting.domain.alert import TimelineEntry
        from nakabandi.alerting.domain.dedup import dedup_key as mk_dk
        from nakabandi.shared import new_id

        now = self._clock.now()
        open_alerts = [a for a in self._repo.list_open() if a.cluster_ref == from_cluster_id]

        seen_keys: dict[str, Alert] = {}  # new_dedup_key -> first (older) alert

        for alert in sorted(open_alerts, key=lambda a: a.created_at):
            new_dk = mk_dk(into_cluster_id, alert.target_kind, alert.target_id)
            alert.cluster_ref = into_cluster_id
            alert.dedup_key = new_dk

            if new_dk in seen_keys:
                # Collision: close this (newer) alert as merged into the older one
                entry = TimelineEntry(
                    id=new_id(),
                    alert_id=alert.id,
                    at=now,
                    kind="closed",
                    actor_id=None,
                    text_code="alert.cluster_merged_close",
                    text_params={"into": seen_keys[new_dk].id},
                )
                alert.transition(AlertStatus.CLOSED, entry)
            else:
                seen_keys[new_dk] = alert

            self._repo.save(alert)
