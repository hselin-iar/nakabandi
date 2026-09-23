"""ProviderSms with automatic fallback to OutboxSms (DOC 3 M4 edge case: "Provider SMS failure:
automatic fallback adapter; delivery shows channel=sms, provider=outbox")."""

from __future__ import annotations

import httpx

from nakabandi.alerting.domain.delivery import Delivery
from nakabandi.alerting.domain.messages import DeliveryResult
from nakabandi.alerting.infrastructure.channels.sms_outbox import OutboxSms


class ProviderSms:
    """POSTs {to, body} as JSON to a sandbox provider endpoint with a bearer key. Unconfigured
    counts as a failure so the composite below falls back."""

    def __init__(self, url: str | None, api_key: str | None, *, timeout_s: float = 5.0) -> None:
        self._url = url
        self._api_key = api_key
        self._timeout_s = timeout_s

    def send(self, delivery: Delivery) -> DeliveryResult:
        if not self._url or not self._api_key:
            return DeliveryResult(ok=False, error="sms provider is not configured")
        try:
            with httpx.Client(timeout=self._timeout_s) as client:
                response = client.post(
                    self._url,
                    json={"to": delivery.recipient, "body": delivery.rendered_body},
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
        except httpx.HTTPError as exc:
            return DeliveryResult(ok=False, error=f"{type(exc).__name__}: {exc}")
        if 200 <= response.status_code < 300:
            return DeliveryResult(ok=True, provider="sms-sandbox")
        return DeliveryResult(ok=False, error=f"provider responded {response.status_code}")


class SmsWithFallback:
    def __init__(self, primary: ProviderSms, fallback: OutboxSms) -> None:
        self._primary = primary
        self._fallback = fallback

    def send(self, delivery: Delivery) -> DeliveryResult:
        result = self._primary.send(delivery)
        if result.ok:
            return result
        return self._fallback.send(delivery)
