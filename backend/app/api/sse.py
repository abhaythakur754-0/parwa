"""
Jarvis API — SSE Streaming Endpoint (GSD Terminal)

GET /api/jarvis/stream — Server-Sent Events for pipeline execution.

When a chat command arrives, the streaming endpoint pushes real-time
events as the 3-node pipeline progresses through SENSE → EVALUATE → NOTIFY.

Uses asyncio.Queue + Event pattern so any number of SSE clients can
subscribe and receive events simultaneously.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

logger = logging.getLogger("jarvis.api.sse")

router = APIRouter(tags=["SSE"])


# ── Global Stream Hub ──────────────────────────────────────────
# All SSE clients share a single per-tenant queue.  When a chat
# command runs, events are pushed here.

class _StreamHub:
    """Central hub that fans-out pipeline events to all SSE subscribers."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, tenant_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers.setdefault(tenant_id, []).append(q)
        return q

    def unsubscribe(self, tenant_id: str, q: asyncio.Queue) -> None:
        subs = self._subscribers.get(tenant_id, [])
        if q in subs:
            subs.remove(q)

    async def publish(self, tenant_id: str, event: dict) -> None:
        dead: list[asyncio.Queue] = []
        for q in self._subscribers.get(tenant_id, []):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self.unsubscribe(tenant_id, q)


stream_hub = _StreamHub()


# ── Helper: publish a typed SSE payload ────────────────────────

async def emit_pipeline_event(
    tenant_id: str,
    event_type: str,
    data: Dict[str, Any],
) -> None:
    """Push a pipeline event to all SSE subscribers for a tenant.

    Event types: init, sense_start, sense_complete, evaluate_start,
    evaluate_complete, notify_start, notify_complete, done, error.
    """
    payload = {
        "event": event_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await stream_hub.publish(tenant_id, payload)


# ── SSE Generator ──────────────────────────────────────────────

async def _event_generator(tenant_id: str, q: asyncio.Queue):
    """Yield SSE-formatted lines from the queue until disconnect."""
    try:
        # Send initial connection event
        yield f"event: connected\ndata: {json.dumps({'tenant_id': tenant_id})}\n\n"

        while True:
            try:
                payload = await asyncio.wait_for(q.get(), timeout=30.0)
                event_type = payload.get("event", "message")
                yield f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"
            except asyncio.TimeoutError:
                # Heartbeat to keep connection alive
                yield f"event: heartbeat\ndata: {json.dumps({'ts': datetime.now(timezone.utc).isoformat()})}\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        stream_hub.unsubscribe(tenant_id, q)


# ── Endpoint ───────────────────────────────────────────────────

@router.get("/stream")
async def jarvis_stream(
    tenant_id: str = Query(default="default_tenant", description="Tenant to stream events for"),
):
    """Server-Sent Events stream for GSD Terminal.

    Connect and receive real-time pipeline events:
      - init: pipeline starting
      - sense_start / sense_complete
      - evaluate_start / evaluate_complete
      - notify_start / notify_complete
      - done: pipeline finished
      - error: pipeline error
    """
    q = stream_hub.subscribe(tenant_id)
    return StreamingResponse(
        _event_generator(tenant_id, q),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
