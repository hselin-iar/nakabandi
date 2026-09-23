"""DomainEvent base, EventBus, and the LC-3 payload classes (DOC 3 Shared Kernel).

Events carry IDs and small facts, never entities. Fan-out only: orchestration between modules
stays explicit in `pipeline`, never implicit through event handlers (DOC 3 LC-3 header note).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import structlog

from nakabandi.shared.types import Id, SimTime

logger = structlog.get_logger(__name__)


class HandlerError(Exception):
    """Raised by EventBus.publish after every handler has run, if any handler raised."""


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    event_id: Id
    occurred_at: SimTime


@dataclass(frozen=True, kw_only=True)
class ComplaintIngested(DomainEvent):
    complaint_id: Id


@dataclass(frozen=True, kw_only=True)
class HopsIngested(DomainEvent):
    complaint_ids: list[Id]


@dataclass(frozen=True, kw_only=True)
class ObservationIngested(DomainEvent):
    observation_ids: list[Id]


@dataclass(frozen=True, kw_only=True)
class ClusterUpdated(DomainEvent):
    cluster_id: Id


@dataclass(frozen=True, kw_only=True)
class ClusterMerged(DomainEvent):
    from_id: Id
    into_id: Id


@dataclass(frozen=True, kw_only=True)
class ForecastGenerated(DomainEvent):
    forecast_id: Id
    complaint_id: Id


@dataclass(frozen=True, kw_only=True)
class InterceptAssessed(DomainEvent):
    forecast_id: Id


@dataclass(frozen=True, kw_only=True)
class AlertRaised(DomainEvent):
    alert_id: Id


@dataclass(frozen=True, kw_only=True)
class AlertUpdated(DomainEvent):
    alert_id: Id
    change: str


@dataclass(frozen=True, kw_only=True)
class AlertEscalated(DomainEvent):
    alert_id: Id


@dataclass(frozen=True, kw_only=True)
class ActionRecorded(DomainEvent):
    action_id: Id
    alert_id: Id


@dataclass(frozen=True, kw_only=True)
class OutcomeRecorded(DomainEvent):
    alert_id: Id
    result: str


@dataclass(frozen=True, kw_only=True)
class TickAdvanced(DomainEvent):
    sim_time: SimTime


class EventBus:
    """Synchronous, in-process pub/sub. Handlers run in registration order."""

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[Callable[[DomainEvent], None]]] = {}

    def subscribe(
        self, event_type: type[DomainEvent], handler: Callable[[DomainEvent], None]
    ) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def publish(self, event: DomainEvent) -> None:
        """Runs every handler for this event's type, in order. An unknown event type (no
        subscribers) is a no-op. If any handler raises, it is logged, every remaining handler
        still runs, and a HandlerError is raised once all of them have."""
        handlers = self._handlers.get(type(event), [])
        failures: list[Exception] = []
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:  # noqa: BLE001 - deliberately broad: isolate handlers
                logger.exception(
                    "event_bus.handler.failed",
                    event_type=type(event).__name__,
                    handler=getattr(handler, "__qualname__", repr(handler)),
                )
                failures.append(exc)
        if failures:
            raise HandlerError(
                f"{len(failures)} handler(s) failed for {type(event).__name__}"
            ) from failures[0]
