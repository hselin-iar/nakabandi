"""validate_complaint() and normalise_ref() (DOC 3 M2 FUNCTION & CLASS DESIGN)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from nakabandi.intake.domain.validation import normalise_ref, validate_complaint
from nakabandi.shared import ValidationFailed
from nakabandi_contracts.ingest import AccountIn, ComplaintIn

NOW = datetime.fromisoformat("2026-01-15T10:00:00+05:30")


def _complaint() -> ComplaintIn:
    return ComplaintIn.model_validate(
        dict(
            external_ref="c1",
            category="upi_phishing",
            amount_paise=100,
            victim_district_id="d1",
            credited_at=NOW,
            reported_event_at=NOW + timedelta(minutes=1),
            observed_at=NOW + timedelta(minutes=2),
            layer1_account=AccountIn(account_ref="acc-1", bank_id="bank-1"),
        )
    )


def test_a_well_formed_complaint_passes() -> None:
    validate_complaint(_complaint())  # does not raise


def test_normalise_ref_strips_and_uppercases() -> None:
    assert normalise_ref("  acc-1 ") == "ACC-1"


def test_normalise_ref_is_idempotent() -> None:
    assert normalise_ref(normalise_ref("Acc-1")) == normalise_ref("Acc-1")


def test_validate_complaint_is_a_defense_in_depth_check() -> None:
    # ComplaintIn.model_validate() already enforces amount > 0 (Field(gt=0)) and time order
    # (a model_validator); model_copy(update=...) does not re-run validators, so this proves
    # validate_complaint (DOC 3 M2) asserts the same LC-1 rule independently, for a caller that
    # builds a ComplaintIn without going through pydantic validation.
    bad = _complaint().model_copy(update={"amount_paise": -1})
    with pytest.raises(ValidationFailed):
        validate_complaint(bad)
