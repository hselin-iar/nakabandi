"""Recipient dataclass and route() stub (DOC 3 M4).

Full routing logic (district officers, state investigator, I4C analysts, bank nodal contact)
requires the geo directory populated by Track D (D5). The stub returns an empty list with a
debug log so tests can run and the pipeline can make progress.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from nakabandi.alerting.domain.alert import Alert

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Recipient:
    user_id: str
    role: str
    channel: str  # "sse" | "email" | "sms"
    locale: str = "en"


def route(alert: Alert, directory: object) -> list[Recipient]:
    """Return recipients for an alert notification.

    Stub: returns empty list until geo directory is populated (Track D, Sync 4).
    Real routing: district officers of the target district, the state investigator,
    I4C analysts, and the bank nodal contact (informational only).
    """
    logger.debug(
        "alerting.routing.stub",
        alert_id=alert.id,
        target_id=alert.target_id,
    )
    return []
