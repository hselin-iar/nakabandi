"""OutboxSms: the on-screen "SMS outbox" adapter (DOC 2 §2.2). It sends nothing off-machine; the
Delivery row with its rendered body, shown in the Outbox viewer, is the message."""

from __future__ import annotations

from nakabandi.alerting.domain.delivery import Delivery
from nakabandi.alerting.domain.messages import DeliveryResult


class OutboxSms:
    def send(self, delivery: Delivery) -> DeliveryResult:
        return DeliveryResult(ok=True, provider="outbox")
