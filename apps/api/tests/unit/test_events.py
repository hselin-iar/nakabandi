"""EventBus ordering and aggregated error (DOC 3 Shared Kernel TESTING PLAN and EDGE CASES)."""

from datetime import UTC, datetime

import pytest
from nakabandi.shared import DomainEvent, EventBus, HandlerError
from nakabandi.shared.events import AlertRaised, TickAdvanced


def _event() -> AlertRaised:
    return AlertRaised(
        event_id="evt-1", occurred_at=datetime(2026, 1, 1, tzinfo=UTC), alert_id="a1"
    )


def test_handlers_run_in_registration_order() -> None:
    bus = EventBus()
    order: list[str] = []
    bus.subscribe(AlertRaised, lambda e: order.append("first"))
    bus.subscribe(AlertRaised, lambda e: order.append("second"))
    bus.publish(_event())
    assert order == ["first", "second"]


def test_unknown_event_type_is_a_no_op() -> None:
    bus = EventBus()
    bus.publish(_event())  # no subscribers at all; must not raise


def test_a_failing_handler_still_lets_the_rest_run_then_raises() -> None:
    bus = EventBus()
    ran: list[str] = []

    def bad(e: DomainEvent) -> None:
        raise RuntimeError("handler blew up")

    bus.subscribe(AlertRaised, bad)
    bus.subscribe(AlertRaised, lambda e: ran.append("second"))
    with pytest.raises(HandlerError):
        bus.publish(_event())
    assert ran == ["second"]


def test_different_event_types_are_independent() -> None:
    bus = EventBus()
    seen: list[str] = []
    bus.subscribe(TickAdvanced, lambda e: seen.append("tick"))
    bus.publish(_event())  # AlertRaised: no subscriber for this type
    assert seen == []
