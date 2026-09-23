"""OutboundMessage (DOC 3 M4 — channel-agnostic content model)."""

from __future__ import annotations

from dataclasses import dataclass, field

from nakabandi.shared import Id


@dataclass(frozen=True, slots=True)
class OutboundMessage:
    """Content sent to a notification channel. Channels are responsible for formatting."""

    kind: str  # alert_notice | hold_request | escalation_notice
    alert_id: Id
    recipient_user_id: Id
    locale: str  # "en"
    body: str
    deep_link: str
    masked_refs: list[str] = field(default_factory=list)
    subject: str | None = None


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    """What a channel adapter reports back. Adapters only send; the outbox decides what a
    failure means (retry, dead-letter) and turns it into a Delivery row update."""

    ok: bool
    provider: str | None = None
    error: str | None = None


def mask_last4(ref: str) -> str:
    """Fixed masking for stored, recipient-independent bodies: identifiers are never written
    unmasked into a rendered_body (DOC 4 A8 drift warning)."""
    return f"****{ref[-4:]}" if len(ref) > 4 else "****"
