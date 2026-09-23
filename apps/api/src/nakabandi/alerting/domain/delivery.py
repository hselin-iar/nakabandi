"""Delivery entity and retry arithmetic (DOC 3 M4 DeliverOutbox, DOC 2 §2.3 Delivery).

Every timestamp on a Delivery is WALL-CLOCK time: retry backoff and "sent at" are transport
concerns, like LC-6's webhook timestamp window, never the simulated timeline (DOC 2 §2.4).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from nakabandi.shared import Id

# DOC 3 M4: "exponential backoff (5 s, 10 s, ... capped 5 min)". The 5 s base is
# alerting.delivery.backoff_s in policy.yaml (LC-7); the cap is stated only in prose, with no
# LC-7 key, so it is a named constant here rather than an invented policy key.
BACKOFF_CAP_S = 300.0


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"  # failed, will retry at next_attempt_at
    DEAD = "dead"  # gave up after alerting.delivery.max_attempts


class DeliveryChannel(StrEnum):
    SSE = "sse"
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"


class WebhookKind(StrEnum):
    ALERT_NOTICE = "alert_notice"
    HOLD_REQUEST = "hold_request"


def backoff_seconds(attempts: int, base_s: float) -> float:
    """Delay before the next try after `attempts` failures: base, 2x base, 4x base ... capped."""
    return min(base_s * (2 ** max(attempts - 1, 0)), BACKOFF_CAP_S)


@dataclass(slots=True)
class Delivery:
    id: Id
    alert_id: Id
    action_id: Id | None
    channel: DeliveryChannel
    webhook_kind: WebhookKind | None
    recipient: str
    rendered_body: str  # masked identifiers only; what the Outbox viewer shows
    payload: dict  # channel wire content; never returned by any view
    idempotency_key: str
    status: DeliveryStatus
    attempts: int
    next_attempt_at: datetime
    created_at: datetime
    provider: str | None = None
    last_error: str | None = None
    sent_at: datetime | None = None

    def __post_init__(self) -> None:
        # "Nothing but RecordAction may create a hold_request delivery": one can never exist
        # without the Action that authorised it (DOC 3 M4 integration test).
        if self.webhook_kind is WebhookKind.HOLD_REQUEST and self.action_id is None:
            raise ValueError("a hold_request delivery requires an action_id")

    def mark_sent(self, now: datetime, provider: str | None) -> None:
        self.status = DeliveryStatus.SENT
        self.attempts += 1
        self.sent_at = now
        self.last_error = None
        if provider is not None:
            self.provider = provider

    def mark_failed(self, now: datetime, error: str, *, max_attempts: int, base_s: float) -> None:
        self.attempts += 1
        self.last_error = error
        if self.attempts >= max_attempts:
            self.status = DeliveryStatus.DEAD
            return
        self.status = DeliveryStatus.FAILED
        delay = backoff_seconds(self.attempts, base_s)
        self.next_attempt_at = datetime.fromtimestamp(now.timestamp() + delay, tz=now.tzinfo)
