"""uncertainty() and review-queue ordering (DOC 3 S3 alerting/domain/uncertainty.py — pure).

Active learning: ask the officer about the alerts the model is least sure of, because their label
teaches the most."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nakabandi_contracts.enums import Severity

if TYPE_CHECKING:
    from nakabandi.alerting.domain.alert import Alert

_SEVERITY_ORDER = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2, Severity.CRITICAL: 3}


def uncertainty(confidence: float) -> float:
    """1 - |2c - 1|: 1.0 at c = 0.5, falling to 0 at c = 0 and c = 1."""
    return 1.0 - abs(2.0 * confidence - 1.0)


def order_review_queue(alerts: list[Alert]) -> list[Alert]:
    """Most uncertain first; ties by severity (higher first), then oldest first, then id.

    Uncertainty is rounded before comparing: 0.3 and 0.7 are equally uncertain, but in floating
    point they differ in the last bit, which would silently defeat the severity tie-break."""
    return sorted(
        alerts,
        key=lambda a: (
            -round(uncertainty(a.confidence), 9),
            -_SEVERITY_ORDER[a.severity],
            a.created_at,
            a.id,
        ),
    )
