"""Public facade of the alerting module: what other modules may import (DOC 3 M4).

AlertService is constructed per-request (like AccessService) on the caller's
SQLAlchemy session, so a raise_or_merge and its timeline entries share one transaction.

Exports:
  AlertService   — raise_or_merge, acknowledge, record_action, handle_bank_callback,
                   deliver_outbox, fire_due_timers, on_cluster_merged, rebuild_timers,
                   get_alert_for, list_alerts, list_actions, list_deliveries
  AlertResult    — result returned to pipeline Stage 5
  ActionIn, BankCallback, LienContext — inputs to record_action / handle_bank_callback and the
                   port main.py wires for hold validation
  SseHub         — shared hub (also used by analytics for heat.version)
  SseEvent       — typed event for broadcast
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Set
from datetime import datetime

from nakabandi_contracts.enums import Permission, Role
from sqlalchemy.orm import Session

from nakabandi.access import Principal, authorize
from nakabandi.alerting.application.acknowledge import AcknowledgeAlert
from nakabandi.alerting.application.bank_callback import (
    BankCallback,
    CallbackResult,
    HandleBankCallback,
)
from nakabandi.alerting.application.outbox import DeliverOutbox, EnqueueDeliveries
from nakabandi.alerting.application.ports import (
    LienContext,
    LienContextPort,
    LienValidator,
    NotificationChannel,
    TargetScopePort,
)
from nakabandi.alerting.application.raise_or_merge import AlertResult, RaiseOrMergeAlert
from nakabandi.alerting.application.record_action import ActionIn, RecordAction
from nakabandi.alerting.application.scope import scope_of
from nakabandi.alerting.application.timers import (
    EscalateAlert,
    ExpireAlert,
    RebuildTimers,
    ReviewLien,
)
from nakabandi.alerting.domain.action import Action, allowed_actions
from nakabandi.alerting.domain.alert import ACTIONABLE_STATUSES, Alert
from nakabandi.alerting.domain.delivery import Delivery, DeliveryChannel
from nakabandi.alerting.infrastructure.channels.sse_hub import SseEvent, SseHub
from nakabandi.alerting.infrastructure.render import FileTemplateRenderer
from nakabandi.alerting.infrastructure.repos import (
    SqlActionRepo,
    SqlAlertRepo,
    SqlDeliveryRepo,
)
from nakabandi.audit import AuditLog
from nakabandi.shared import (
    Clock,
    EventBus,
    Id,
    NotFound,
    Policy,
    Scheduler,
    SystemClock,
)

__all__ = [
    "AlertService",
    "AlertResult",
    "SseHub",
    "SseEvent",
    "ActionIn",
    "BankCallback",
    "CallbackResult",
    "LienContext",
    "LienContextPort",
    "LienValidator",
    "NotificationChannel",
    "Action",
    "Delivery",
    "DeliveryChannel",
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
        *,
        lien_context: LienContextPort | None = None,
        validate_lien: LienValidator | None = None,
        scope_lookup: TargetScopePort | None = None,
        bus: EventBus | None = None,
        now_wall: Callable[[], datetime] = SystemClock().now,
    ) -> None:
        self._repo = SqlAlertRepo(session)
        self._action_repo = SqlActionRepo(session)
        self._delivery_repo = SqlDeliveryRepo(session)
        self._clock = clock
        self._policy = policy
        self._scheduler = scheduler
        self._role_permissions = role_permissions
        self._hub = sse_hub

        # Build timer use cases (they share the same repo/clock/scheduler)
        self._escalate = EscalateAlert(self._repo, clock, scheduler)
        self._expire = ExpireAlert(self._repo, clock, scheduler)

        self._review = ReviewLien(self._repo, self._action_repo, clock, scheduler)
        self._lien_context = lien_context

        self._raise_or_merge = RaiseOrMergeAlert(
            alert_repo=self._repo,
            policy=policy,
            clock=clock,
            scheduler=scheduler,
            escalate_fn=self._escalate.schedule,
            expire_fn=self._expire.schedule,
            scope_lookup=scope_lookup,
            on_created=self._notify_banks,
        )
        self._acknowledge = AcknowledgeAlert(self._repo, policy, clock, role_permissions)
        self._rebuild_timers = RebuildTimers(
            alert_repo=self._repo,
            escalate=self._escalate,
            expire=self._expire,
            policy=policy,
            clock=clock,
            review=self._review,
            action_repo=self._action_repo,
        )
        self._enqueue = EnqueueDeliveries(self._delivery_repo, FileTemplateRenderer(), now_wall)
        audit = AuditLog(session, clock)
        self._record_action = RecordAction(
            alert_repo=self._repo,
            action_repo=self._action_repo,
            enqueue=self._enqueue,
            audit=audit,
            clock=clock,
            role_permissions=role_permissions,
            lien_context=lien_context,
            validate_lien=validate_lien,
            scheduler=scheduler,
            review=self._review,
            publish=bus.publish if bus is not None else (lambda _event: None),
        )
        self._bank_callback = HandleBankCallback(self._action_repo, self._repo, audit, clock)

    # ------------------------------------------------------------------
    # Pipeline interface (called by pipeline.ProcessComplaint Stage 5)
    # ------------------------------------------------------------------

    def raise_or_merge(self, forecast: object, assessments: list[object]) -> AlertResult:
        result = self._raise_or_merge.run(forecast, assessments)
        # Publish alert.created SSE for each newly raised alert
        for aid in result.alert_ids:
            self._publish_alert_event(
                "alert.created" if result.created else "alert.updated", aid, version=1
            )
        return result

    def _notify_banks(self, alert: Alert) -> None:
        """One informational alert_notice per account the alert's complaint reached (LC-6 masks
        account_ref on the wire). Queued in the same unit of work as the alert, sent by the
        outbox worker. Skipped when no intake lookup is wired (e.g. a pure unit test)."""
        if self._lien_context is None:
            return
        complaint_ref = self._lien_context.complaint_ref(alert.complaint_id)
        if complaint_ref is None:
            return
        now = self._clock.now()
        for traced in self._lien_context.traced_accounts(alert.complaint_id):
            self._enqueue.enqueue_alert_notice(
                alert_id=alert.id,
                bank_id=traced.bank_id,
                account_ref=traced.account_ref,
                complaint_ref=complaint_ref,
                sim_time=now,
            )

    def _publish_alert_event(
        self,
        name: str,
        alert_id: Id,
        *,
        version: int | None = None,
        data: dict | None = None,
    ) -> None:
        """Every alert event carries the alert's scope so the stream can filter by principal."""
        alert = self._repo.get_by_id(alert_id)
        self._hub.publish(
            SseEvent(
                name=name,
                data=data if data is not None else {"alert_id": alert_id, "version": version},
                alert_id=alert_id,
                scope_state_id=alert.scope_state_id if alert else None,
                scope_district_id=alert.scope_district_id if alert else None,
                scope_bank_id=alert.scope_bank_id if alert else None,
            )
        )

    # ------------------------------------------------------------------
    # Action: acknowledge
    # ------------------------------------------------------------------

    def acknowledge(self, principal: object, alert_id: str) -> Alert:
        alert = self._acknowledge.run(principal, alert_id)  # type: ignore[arg-type]
        self._publish_alert_event("alert.updated", alert.id, version=2)
        return alert

    # ------------------------------------------------------------------
    # Action: the human gate, and the bank's answer to it
    # ------------------------------------------------------------------

    def record_action(self, principal: object, alert_id: Id, action_in: ActionIn) -> Action:
        """Raises Forbidden after auditing the denial; the caller must commit in that case."""
        action = self._record_action.run(principal, alert_id, action_in)  # type: ignore[arg-type]
        self._publish_alert_event("alert.updated", alert_id, version=3)
        return action

    def handle_bank_callback(self, callback: BankCallback) -> CallbackResult:
        result = self._bank_callback.run(callback)
        if result.applied:
            self._publish_alert_event("alert.updated", result.action.alert_id, version=4)
        return result

    # ------------------------------------------------------------------
    # Outbox
    # ------------------------------------------------------------------

    def deliver_outbox(
        self, channels: Mapping[DeliveryChannel, NotificationChannel], now_wall: datetime
    ) -> int:
        """One worker pass (DOC 3 M4 DeliverOutbox.run_once). Publishes delivery.updated (LC-5)
        for every delivery it touched."""

        def _publish(delivery: Delivery) -> None:
            self._publish_alert_event(
                "delivery.updated",
                delivery.alert_id,
                data={"alert_id": delivery.alert_id, "delivery_id": delivery.id},
            )

        return DeliverOutbox(self._delivery_repo, channels, self._policy, _publish).run_once(
            now_wall
        )

    def list_deliveries(
        self,
        principal: Principal,
        *,
        status: str | None = None,
        channel: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Delivery], str | None]:
        """The outbox as one principal may see it: only deliveries of alerts in their scope."""
        return self._delivery_repo.list_page(
            status=status,
            channel=channel,
            cursor=cursor,
            limit=limit,
            **_scope_filter(principal),
        )

    def count_dead_deliveries(self) -> int:
        return self._delivery_repo.count_dead()

    def list_actions(self, alert_id: Id) -> list[Action]:
        return self._action_repo.list_for_alert(alert_id)

    def list_deliveries_for_alert(self, alert_id: Id) -> list[Delivery]:
        return self._delivery_repo.list_for_alert(alert_id)

    def allowed_actions(self, principal: Principal, alert: Alert) -> list[str]:
        """LC-4 AlertDetail.allowed_actions: what this principal may record on this alert now."""
        if alert.status not in ACTIONABLE_STATUSES:
            return []
        perms = self._role_permissions.get(principal.role, frozenset())
        return [t.value for t in allowed_actions(perms)]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_alert(self, alert_id: str) -> Alert | None:
        """Unscoped read for internal callers (the pipeline, timers). Routers use
        get_alert_for."""
        return self._repo.get_by_id(alert_id)

    def get_alert_for(self, principal: Principal, alert_id: Id) -> Alert:
        """The alert, if the principal may see it: VIEW_ALERTS and the alert inside their scope."""
        authorize(principal, Permission.VIEW_ALERTS, self._role_permissions)
        alert = self._repo.get_by_id(alert_id)
        if alert is None:
            raise NotFound("ALERT_NOT_FOUND", f"Alert {alert_id!r} not found")
        authorize(principal, Permission.VIEW_ALERTS, self._role_permissions, scope_of(alert))
        return alert

    def list_alerts(
        self,
        principal: Principal,
        *,
        status: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Alert], str | None]:
        authorize(principal, Permission.VIEW_ALERTS, self._role_permissions)
        return self._repo.list_by_scope(
            status=status, cursor=cursor, limit=limit, **_scope_filter(principal)
        )

    # ------------------------------------------------------------------
    # Timer management
    # ------------------------------------------------------------------

    def rebuild_timers(self) -> int:
        return self._rebuild_timers.run()

    def fire_due_timers(self) -> int:
        """One tick of the timer driver: re-register every live timer on THIS session (a timer
        registered during an earlier request is bound to that request's closed session), then
        fire what is due at the current sim time. Returns how many fired."""
        self.rebuild_timers()
        return self._scheduler.run_due(self._clock.now())

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


def _scope_filter(principal: Principal) -> dict[str, str | None]:
    """The repo filter for a principal's scope, with access.authorize's precedence: bank, then
    district, then state; an unrestricted principal filters nothing."""
    scope = principal.scope
    if scope.bank_id is not None:
        return {"bank_id": scope.bank_id}
    if scope.district_id is not None:
        return {"district_id": scope.district_id}
    if scope.state_id is not None:
        return {"state_id": scope.state_id}
    return {}
