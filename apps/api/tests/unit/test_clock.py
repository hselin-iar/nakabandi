"""SimClock monotonicity (DOC 3 Shared Kernel TESTING PLAN and EDGE CASES)."""

from datetime import UTC, datetime, timedelta

from nakabandi.shared import SimClock, SystemClock


def _t(minutes: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=minutes)


def test_advance_to_moves_time_forward() -> None:
    clock = SimClock(start=_t(0))
    clock.advance_to(_t(5))
    assert clock.now() == _t(5)


def test_advance_to_backwards_is_ignored() -> None:
    clock = SimClock(start=_t(10))
    clock.advance_to(_t(5))
    assert clock.now() == _t(10)


def test_advance_to_same_time_is_ignored() -> None:
    clock = SimClock(start=_t(10))
    clock.advance_to(_t(10))
    assert clock.now() == _t(10)


def test_system_clock_is_timezone_aware_utc() -> None:
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)
