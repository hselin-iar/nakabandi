"""validate_complaint(), normalise_ref() (DOC 3 M2 FUNCTION & CLASS DESIGN). Pure: no I/O.

validate_complaint re-asserts the LC-1 business rules at the domain layer (amount > 0,
credited_at <= reported_event_at <= observed_at, layer1 account present) independent of
`nakabandi_contracts.ingest.ComplaintIn`'s own pydantic validators, so the rule holds for any
future caller that builds a ComplaintIn without going through the wire parser (e.g. the seed
CLI already does, but DOC 3 states this as a domain-level rule, not a request-parsing detail).
"""

from __future__ import annotations

from nakabandi_contracts.ingest import ComplaintIn

from nakabandi.shared import ValidationFailed


def validate_complaint(c: ComplaintIn) -> None:
    if c.amount_paise <= 0:
        raise ValidationFailed("COMPLAINT_AMOUNT_NOT_POSITIVE", "amount_paise must be > 0")
    if not (c.credited_at <= c.reported_event_at <= c.observed_at):
        raise ValidationFailed(
            "COMPLAINT_TIME_ORDER",
            "credited_at <= reported_event_at <= observed_at must hold",
        )
    if c.layer1_account is None:
        raise ValidationFailed("COMPLAINT_LAYER1_ACCOUNT_MISSING", "layer1_account is required")


def normalise_ref(ref: str) -> str:
    """Account refs are compared case- and whitespace-insensitively so the same account
    reported with different casing or stray whitespace resolves to one Account row."""
    return ref.strip().upper()
