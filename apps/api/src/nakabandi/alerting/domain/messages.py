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
