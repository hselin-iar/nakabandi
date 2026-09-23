"""BankWebhook: signed POST to the bank gateway simulator (DOC 3 M4, LC-6).

Signature = hex(HMAC-SHA256(secret, timestamp + "." + rawBody)); the timestamp is WALL-CLOCK
epoch seconds (LC-6). The same signing code runs against a local echo server and against
apps/bank-sim, so swapping the target changes nothing here (DOC 4 A8 STUB/MOCK STRATEGY)."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime

import httpx

from nakabandi.alerting.domain.delivery import Delivery
from nakabandi.alerting.domain.messages import DeliveryResult
from nakabandi.alerting.domain.signing import sign
from nakabandi.shared import SystemClock


class BankWebhook:
    def __init__(
        self,
        url: str | None,
        secret: str | None,
        *,
        timeout_s: float = 5.0,
        now_wall: Callable[[], datetime] = SystemClock().now,
        client: httpx.Client | None = None,
    ) -> None:
        self._url = url
        self._secret = secret
        self._timeout_s = timeout_s
        self._now = now_wall
        self._client = client

    def send(self, delivery: Delivery) -> DeliveryResult:
        if not self._url or not self._secret:
            return DeliveryResult(ok=False, error="bank webhook is not configured")
        raw_body = json.dumps(delivery.payload, separators=(",", ":"), sort_keys=True).encode()
        timestamp = str(int(self._now().timestamp()))
        headers = {
            "Content-Type": "application/json",
            "X-Nakabandi-Timestamp": timestamp,
            "X-Nakabandi-Signature": sign(self._secret, timestamp, raw_body),
            "Idempotency-Key": delivery.idempotency_key,
        }
        try:
            if self._client is not None:
                response = self._client.post(self._url, content=raw_body, headers=headers)
            else:
                with httpx.Client(timeout=self._timeout_s) as client:
                    response = client.post(self._url, content=raw_body, headers=headers)
        except httpx.HTTPError as exc:
            return DeliveryResult(ok=False, error=f"{type(exc).__name__}: {exc}")
        if response.status_code == 200:
            return DeliveryResult(ok=True, provider="bank-sim")
        return DeliveryResult(ok=False, error=f"bank responded {response.status_code}")
