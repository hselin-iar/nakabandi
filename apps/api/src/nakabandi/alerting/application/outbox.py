"""EnqueueDeliveries and DeliverOutbox (DOC 3 M4; DOC 2 §2.2 background processing).

Delivery is the only asynchronous part of the alert path: rows are written in the same unit of
work as the thing that caused them, and the worker sends them later, so a slow provider can never
delay an alert (DOC 2 §2.1). Failures never fail a request; they become Delivery rows.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime

import structlog

from nakabandi.alerting.application.ports import DeliveryRepo, NotificationChannel, TemplateRenderer
from nakabandi.alerting.domain.action import Action
from nakabandi.alerting.domain.delivery import (
    Delivery,
    DeliveryChannel,
    DeliveryStatus,
    WebhookKind,
)
from nakabandi.alerting.domain.messages import DeliveryResult, mask_last4
from nakabandi.shared import Id, Policy, new_id

logger = structlog.get_logger(__name__)


class EnqueueDeliveries:
    def __init__(
        self,
        delivery_repo: DeliveryRepo,
        renderer: TemplateRenderer,
        now_wall: Callable[[], datetime],
    ) -> None:
        self._repo = delivery_repo
        self._renderer = renderer
        self._now_wall = now_wall

    def enqueue_hold_request(
        self,
        action: Action,
        *,
        alert_id: Id,
        bank_id: str,
        account_ref: str,
        complaint_ref: str,
        disputed_paise: int,
        proposed_paise: int,
        expires_at_sim: datetime,
        review_at_sim: datetime,
        sim_time: datetime,
    ) -> Delivery:
        """The ONLY code path that creates a hold_request delivery, and it takes the Action
        that authorised it. Called by RecordAction and nothing else."""
        if action.type.value != "request_hold":
            raise ValueError("hold_request deliveries are created only for request_hold actions")
        payload = {
            "kind": WebhookKind.HOLD_REQUEST.value,
            "request_id": action.id,
            "alert_ref": alert_id,
            "bank_id": bank_id,
            "account_ref": account_ref,
            "complaint_ref": complaint_ref,
            "sim_time": sim_time.isoformat(),
            "disputed_amount_paise": disputed_paise,
            "proposed_lien_paise": proposed_paise,
            "expires_at_sim": expires_at_sim.isoformat(),
            "review_at_sim": review_at_sim.isoformat(),
            "requested_by_role": action.actor_role,
        }
        body = self._renderer.render(
            "hold_request",
            "en",
            bank_id=bank_id,
            account_ref=mask_last4(account_ref),
            complaint_ref=complaint_ref,
            proposed_rupees=f"{proposed_paise / 100:.2f}",
            disputed_rupees=f"{disputed_paise / 100:.2f}",
            expires_at=expires_at_sim.isoformat(),
            review_at=review_at_sim.isoformat(),
            requested_by_role=action.actor_role,
        )
        return self._add(
            alert_id=alert_id,
            action_id=action.id,
            channel=DeliveryChannel.WEBHOOK,
            webhook_kind=WebhookKind.HOLD_REQUEST,
            recipient=f"bank:{bank_id}",
            body=body,
            payload=payload,
            idempotency_key=f"hold_request:{action.id}",
        )

    def enqueue_alert_notice(
        self,
        *,
        alert_id: Id,
        account_id: Id,
        bank_id: str,
        account_ref: str,
        complaint_ref: str,
        sim_time: datetime,
    ) -> Delivery:
        """Informational notice to a bank nodal contact; account_ref is masked on the wire too
        (LC-6: "account_ref masked for alert_notice")."""
        masked = mask_last4(account_ref)
        payload = {
            "kind": WebhookKind.ALERT_NOTICE.value,
            "request_id": new_id(),
            "alert_ref": alert_id,
            "bank_id": bank_id,
            "account_ref": masked,
            "complaint_ref": complaint_ref,
            "sim_time": sim_time.isoformat(),
        }
        body = self._renderer.render(
            "alert_notice",
            "en",
            bank_id=bank_id,
            account_ref=masked,
            complaint_ref=complaint_ref,
        )
        return self._add(
            alert_id=alert_id,
            action_id=None,
            channel=DeliveryChannel.WEBHOOK,
            webhook_kind=WebhookKind.ALERT_NOTICE,
            recipient=f"bank:{bank_id}",
            body=body,
            payload=payload,
            # keyed by the ACCOUNT, not its masked ref: two accounts of one bank can share their
            # last four digits (or be shorter than four), and the key must stay unique
            idempotency_key=f"alert_notice:{alert_id}:{account_id}",
        )

    def _add(
        self,
        *,
        alert_id: Id,
        action_id: Id | None,
        channel: DeliveryChannel,
        webhook_kind: WebhookKind | None,
        recipient: str,
        body: str,
        payload: dict,
        idempotency_key: str,
    ) -> Delivery:
        now = self._now_wall()
        delivery = Delivery(
            id=new_id(),
            alert_id=alert_id,
            action_id=action_id,
            channel=channel,
            webhook_kind=webhook_kind,
            recipient=recipient,
            rendered_body=body,
            payload=payload,
            idempotency_key=idempotency_key,
            status=DeliveryStatus.PENDING,
            attempts=0,
            next_attempt_at=now,
            created_at=now,
        )
        self._repo.add(delivery)
        return delivery


class DeliverOutbox:
    """The worker body: one pass over the deliveries that are due (DOC 3 M4 run_once)."""

    def __init__(
        self,
        delivery_repo: DeliveryRepo,
        channels: Mapping[DeliveryChannel, NotificationChannel],
        policy: Policy,
        on_update: Callable[[Delivery], None] | None = None,
    ) -> None:
        self._repo = delivery_repo
        self._channels = channels
        self._max_attempts = policy.alerting.delivery.max_attempts
        self._base_s = policy.alerting.delivery.backoff_s
        self._on_update = on_update

    def run_once(self, now_wall: datetime) -> int:
        """Send every due delivery. Returns how many were attempted. One failing delivery never
        stops the others."""
        attempted = 0
        for delivery in self._repo.list_due(now_wall):
            attempted += 1
            channel = self._channels.get(delivery.channel)
            if channel is None:
                result = DeliveryResult(ok=False, error=f"no adapter for {delivery.channel.value}")
            else:
                try:
                    result = channel.send(delivery)
                except Exception as exc:  # adapters should not raise; a bug must not stop the pass
                    logger.exception("outbox.channel.raised", delivery_id=delivery.id)
                    result = DeliveryResult(ok=False, error=f"{type(exc).__name__}: {exc}")
            if result.ok:
                delivery.mark_sent(now_wall, result.provider)
            else:
                delivery.mark_failed(
                    now_wall,
                    result.error or "unknown error",
                    max_attempts=self._max_attempts,
                    base_s=self._base_s,
                )
                if delivery.status is DeliveryStatus.DEAD:
                    logger.error(
                        "outbox.delivery.dead",
                        delivery_id=delivery.id,
                        alert_id=delivery.alert_id,
                        channel=delivery.channel.value,
                        last_error=delivery.last_error,
                    )
            self._repo.save(delivery)
            if self._on_update is not None:
                self._on_update(delivery)
        return attempted
