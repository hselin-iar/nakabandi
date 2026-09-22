"""types.py and errors.py: the small pieces every other module leans on (DOC 3 Shared Kernel)."""

from datetime import UTC, datetime

import pytest
from nakabandi.shared import ValidationFailed, message_for, paise_from_inr, to_sim_time


def test_to_sim_time_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationFailed):
        to_sim_time(datetime(2026, 1, 1))  # noqa: DTZ001 - deliberately naive, testing rejection


def test_to_sim_time_accepts_aware_datetime() -> None:
    aware = datetime(2026, 1, 1, tzinfo=UTC)
    assert to_sim_time(aware) == aware


def test_paise_from_inr_rounds_half_up() -> None:
    assert paise_from_inr("10.005") == 1001
    assert paise_from_inr(50) == 5000


def test_paise_from_inr_rejects_negative() -> None:
    with pytest.raises(ValidationFailed):
        paise_from_inr(-1)


def test_message_for_unknown_code_falls_back() -> None:
    assert message_for("SOME_CODE_NOBODY_REGISTERED") == message_for("NOT_A_REAL_CODE_EITHER")


def test_domain_error_carries_code_and_details() -> None:
    err = ValidationFailed("BAD_FIELD", "field is bad", details=[{"field": "x"}])
    assert err.http_status == 422
    assert err.code == "BAD_FIELD"
    assert err.details == [{"field": "x"}]
