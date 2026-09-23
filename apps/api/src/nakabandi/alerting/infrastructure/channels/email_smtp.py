"""SmtpEmail: SMTP when configured (Mailpit locally), otherwise recorded only (DOC 2 §2.2:
"Email via SMTP when configured ... and ALWAYS recorded with its rendered body")."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from nakabandi.alerting.domain.delivery import Delivery
from nakabandi.alerting.domain.messages import DeliveryResult


class SmtpEmail:
    def __init__(
        self, host: str | None, port: int = 1025, sender: str = "alerts@nakabandi.invalid"
    ) -> None:
        self._host = host
        self._port = port
        self._sender = sender

    def send(self, delivery: Delivery) -> DeliveryResult:
        if not self._host:
            # No SMTP configured: the Delivery row's rendered_body IS the record.
            return DeliveryResult(ok=True, provider="outbox")
        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = delivery.recipient
        message["Subject"] = f"NAKABANDI alert {delivery.alert_id}"
        message.set_content(delivery.rendered_body)
        try:
            with smtplib.SMTP(self._host, self._port, timeout=5) as smtp:
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            return DeliveryResult(ok=False, error=f"{type(exc).__name__}: {exc}")
        return DeliveryResult(ok=True, provider="smtp")
