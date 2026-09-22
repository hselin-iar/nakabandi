"""SimTime, Paise, Id aliases and conversion helpers (DOC 3 Shared Kernel, LC-2).

Defined independently of `nakabandi_contracts.ingest`'s SimTime: that package may not import
`nakabandi` (DOC 2 §2.6, contracts-are-leaf), so both sides implement the same LC-2 rule
(timezone-aware UTC; naive datetimes rejected everywhere) rather than sharing one symbol.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from nakabandi.shared.errors import ValidationFailed

SimTime = datetime
"""Timezone-aware UTC datetime. Naive datetimes are rejected everywhere (LC-2)."""

Paise = int
"""Money as integer paise. Never a float (LC-2)."""

Id = str
"""A ULID string, produced by `nakabandi.shared.ids.new_id` (LC-2)."""


def to_sim_time(value: datetime) -> SimTime:
    """Normalise a datetime to LC-2's SimTime: reject naive input, convert to UTC."""
    if value.tzinfo is None:
        raise ValidationFailed(
            "SIM_TIME_NAIVE", "A naive datetime was given where a timezone-aware one is required."
        )
    return value.astimezone(UTC)


def paise_from_inr(rupees: Decimal | float | int | str) -> Paise:
    """Convert a rupee amount to integer paise, rounding half up. Rejects negative amounts."""
    amount = Decimal(str(rupees)) * 100
    paise = int(amount.to_integral_value(rounding=ROUND_HALF_UP))
    if paise < 0:
        raise ValidationFailed("NEGATIVE_AMOUNT", "An amount may not be negative.")
    return paise
