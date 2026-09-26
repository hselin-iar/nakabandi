"""GET /stream — Server-Sent Events (LC-5).

Events:
  alert.created {alert_id, version}
  alert.updated {alert_id, version}
  sim.time {sim_time}                 (emitted by intake's POST /ingest/tick; passthrough here)
  heat.version {version}              (emitted by analytics; passthrough here)
Heartbeat: comment `:heartbeat` every 15 s (LC-5).
Events are filtered by the principal's scope (VIEW_ALERTS required).
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from nakabandi_contracts.enums import Permission

from nakabandi.access import Principal, Scope, authorize, get_principal
from nakabandi.alerting.infrastructure.channels.sse_hub import SseEvent, SseHub
from nakabandi.shared import Forbidden

router = APIRouter(tags=["stream"])

HEARTBEAT_INTERVAL_S = 15


@router.get("/stream")
async def stream(
    request: Request,
    principal: Principal = Depends(get_principal),
) -> StreamingResponse:
    """GET /api/v1/stream — text/event-stream per LC-5."""

    hub: SseHub = request.app.state.sse_hub
    role_permissions = request.app.state.role_permissions
    authorize(principal, Permission.VIEW_ALERTS, role_permissions)  # 403 before the stream opens
    gate = request.app.state.stream_gate
    if not gate.try_open():  # the hosted cap (DOC 2 §2.7: at most 25 concurrent streams)
        raise HTTPException(
            status_code=503, detail="too many open streams", headers={"Retry-After": "30"}
        )

    async def event_generator():
        subscription = hub.subscribe()
        heartbeat_task = asyncio.create_task(_heartbeat_loop(hub))
        try:
            async for event in subscription:
                if not event_visible(principal, event, role_permissions):
                    continue
                # Yield the SSE-formatted event string
                data_str = json.dumps(event.data)
                yield f"event: {event.name}\ndata: {data_str}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            heartbeat_task.cancel()
            gate.closed()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def event_visible(principal: Principal, event: SseEvent, role_permissions) -> bool:  # noqa: ANN001
    """LC-5: "Events are filtered by the principal's scope". An event about no alert (heat.version,
    sim.time) is for everyone; one about an alert goes only to principals whose scope holds it."""
    if event.alert_id is None:
        return True
    try:
        authorize(
            principal,
            Permission.VIEW_ALERTS,
            role_permissions,
            Scope(
                state_id=event.scope_state_id,
                district_id=event.scope_district_id,
                bank_id=event.scope_bank_id,
            ),
        )
    except Forbidden:
        return False
    return True


async def _heartbeat_loop(hub: SseHub) -> None:
    """Emit an empty `:heartbeat` comment to keep connections alive (LC-5: every 15 s).
    The sim clock itself is carried by the separate `sim.time` event, published by
    intake's POST /ingest/tick router each time world-sim advances the clock — not by
    this heartbeat, which only resets the client's inactivity timer."""
    from nakabandi.alerting.infrastructure.channels.sse_hub import SseEvent

    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL_S)
        hub.publish(SseEvent(name=":heartbeat", data={}))
