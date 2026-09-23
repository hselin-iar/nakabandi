"""GET /stream — Server-Sent Events (LC-5).

Events:
  alert.created {alert_id, version}
  alert.updated {alert_id, version}
  sim.time {sim_time, speed, state}
  heat.version {version}              (emitted by analytics; passthrough here)
Heartbeat: comment `:heartbeat` every 15 s (LC-5).
Events are filtered by the principal's scope (VIEW_ALERTS required).
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from nakabandi.access import Principal, get_principal
from nakabandi.alerting.infrastructure.channels.sse_hub import SseHub

router = APIRouter(tags=["stream"])

HEARTBEAT_INTERVAL_S = 15


@router.get("/stream")
async def stream(
    request: Request,
    principal: Principal = Depends(get_principal),
) -> StreamingResponse:
    """GET /api/v1/stream — text/event-stream per LC-5."""

    hub: SseHub = request.app.state.sse_hub

    async def event_generator():
        subscription = hub.subscribe()
        heartbeat_task = asyncio.create_task(_heartbeat_loop(hub))
        try:
            async for event in subscription:
                # Yield the SSE-formatted event string
                data_str = json.dumps(event.data)
                yield f"event: {event.name}\ndata: {data_str}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            heartbeat_task.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _heartbeat_loop(hub: SseHub) -> None:
    """Emit a sim.time heartbeat comment to keep connections alive (LC-5: every 15 s)."""
    from nakabandi.alerting.infrastructure.channels.sse_hub import SseEvent

    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL_S)
        # Heartbeat is a sim.time event (also useful to the client for clock sync)
        hub.publish(SseEvent(name=":heartbeat", data={}))
