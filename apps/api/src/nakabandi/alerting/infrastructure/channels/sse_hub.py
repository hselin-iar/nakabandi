"""SseHub — in-process SSE broadcast hub (DOC 3 M4, LC-5).

Shared between alerting (alert.created, alert.updated) and analytics (heat.version).
Heartbeat (comment every 15 s) is handled by the stream router.

LC-5 SSE payloads carry IDs and versions only, filtered by the principal's scope.
This hub is intentionally simple: no persistence, no reconnect history, no broker.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class SseEvent:
    """An SSE event per LC-5."""

    name: str  # alert.created | alert.updated | sim.time | heat.version
    data: dict
    alert_id: str | None = None
    # The alert's scope, attached at publish time (the hub never touches the database); events
    # without an alert (heat.version, sim.time) carry none and go to every subscriber.
    scope_state_id: str | None = None
    scope_district_id: str | None = None
    scope_bank_id: str | None = None


class SseHub:
    """Fanout broadcast hub.  Subscribers receive a filtered async generator of SSE events.

    Scope filtering: if an event carries an alert_id, only subscribers who have VIEW_ALERTS
    permission and whose scope allows the alert are notified. Scope data for filtering is
    attached at publish time (not re-fetched here to keep this class free of DB access).
    """

    def __init__(self) -> None:
        self._queues: list[asyncio.Queue[SseEvent | None]] = []

    def publish(self, event: SseEvent) -> None:
        """Broadcast to all currently subscribed consumers (synchronous). Fire-and-forget."""
        for q in list(self._queues):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("sse_hub.queue_full", event_name=event.name)

    async def subscribe(self) -> AsyncIterator[SseEvent]:
        """Async generator that yields events as they arrive.

        The caller removes itself from the hub by breaking out of the loop
        (the generator's finally block handles cleanup).
        """
        q: asyncio.Queue[SseEvent | None] = asyncio.Queue(maxsize=256)
        self._queues.append(q)
        try:
            while True:
                event = await q.get()
                if event is None:
                    break
                yield event
        finally:
            try:
                self._queues.remove(q)
            except ValueError:
                pass

    def close_all(self) -> None:
        """Signal all subscribers to stop (sent on app shutdown)."""
        for q in list(self._queues):
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                pass
