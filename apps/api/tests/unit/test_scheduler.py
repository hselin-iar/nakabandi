"""Scheduler ordering, replace, cancel, exception isolation (DOC 3 Shared Kernel TESTING PLAN)."""

from datetime import UTC, datetime, timedelta

from nakabandi.shared import Scheduler


def _t(minutes: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=minutes)


def test_run_due_fires_in_time_order() -> None:
    scheduler = Scheduler()
    fired: list[str] = []
    scheduler.call_at("b", _t(2), lambda: fired.append("b"))
    scheduler.call_at("a", _t(1), lambda: fired.append("a"))
    scheduler.call_at("c", _t(3), lambda: fired.append("c"))
    count = scheduler.run_due(_t(3))
    assert fired == ["a", "b", "c"]
    assert count == 3


def test_run_due_only_fires_due_timers() -> None:
    scheduler = Scheduler()
    fired: list[str] = []
    scheduler.call_at("soon", _t(1), lambda: fired.append("soon"))
    scheduler.call_at("later", _t(10), lambda: fired.append("later"))
    count = scheduler.run_due(_t(5))
    assert fired == ["soon"]
    assert count == 1
    # the still-pending timer fires once its time comes
    assert scheduler.run_due(_t(10)) == 1
    assert fired == ["soon", "later"]


def test_call_at_replaces_same_key() -> None:
    scheduler = Scheduler()
    fired: list[str] = []
    scheduler.call_at("k", _t(1), lambda: fired.append("first"))
    scheduler.call_at("k", _t(2), lambda: fired.append("second"))
    count = scheduler.run_due(_t(5))
    assert fired == ["second"]
    assert count == 1


def test_cancel_removes_the_timer() -> None:
    scheduler = Scheduler()
    fired: list[str] = []
    scheduler.call_at("k", _t(1), lambda: fired.append("k"))
    scheduler.cancel("k")
    assert scheduler.run_due(_t(5)) == 0
    assert fired == []


def test_exception_in_one_timer_does_not_stop_the_rest() -> None:
    scheduler = Scheduler()
    fired: list[str] = []

    def boom() -> None:
        raise RuntimeError("timer blew up")

    scheduler.call_at("bad", _t(1), boom)
    scheduler.call_at("good", _t(2), lambda: fired.append("good"))
    count = scheduler.run_due(_t(5))
    assert fired == ["good"]
    assert count == 2  # both timers counted as fired, even though one raised
