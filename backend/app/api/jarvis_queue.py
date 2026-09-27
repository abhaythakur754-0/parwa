"""
Jarvis DB-Backed Message Queue API.

Instead of processing Jarvis chat synchronously (which freezes the server
when 3+ users chat concurrently), this queue:

  1. POST /api/jarvis/queue/message
     → INSERTs message into jarvis_message_queue table (instant, ~5ms)
     → Returns {message_id, queue_position, status: 'pending'}
     → Client polls GET /api/jarvis/queue/{message_id} for response

  2. GET /api/jarvis/queue/{message_id}
     → Returns current status + response (when ready)
     → status: 'pending' | 'processing' | 'completed' | 'failed'

  3. Background workers (started in main.py) poll the queue:
     → SELECT * WHERE status='pending' ORDER BY queued_at LIMIT 2
     → Process 2 at a time (configurable via MAX_CONCURRENT_JARVIS)
     → Call send_message() to generate response
     → UPDATE row with response, status='completed'

This is the SAME architecture as the ticket pipeline (10 workers polling
DB), which handles 10 concurrent tickets without freezing.

User vision (2026-08-12): 'it can handle unlimited number of request
as its storing in the database'
"""
from __future__ import annotations

import logging
from typing import Any, Dict
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from database.base import get_db
from database.models.core import User
from database.models.jarvis import JarvisMessageQueue

logger = logging.getLogger("parwa.api.jarvis_queue")

router = APIRouter(prefix="/api/jarvis/queue", tags=["Jarvis Queue"])


class QueueMessageRequest(BaseModel):
    """Request to enqueue a Jarvis chat message."""
    session_id: str = Field(..., description="Jarvis session ID")
    content: str = Field(..., min_length=1, max_length=5000,
                         description="User's message")


class QueueMessageResponse(BaseModel):
    """Response when message is enqueued."""
    message_id: str
    status: str  # 'pending'
    queue_position: int
    estimated_wait_seconds: int
    poll_url: str


class QueueStatusResponse(BaseModel):
    """Response when polling for message status."""
    message_id: str
    status: str  # 'pending' | 'processing' | 'completed' | 'failed'
    queue_position: int | None
    response: str | None
    metadata: Dict[str, Any] | None
    knowledge_used: list | None
    error: str | None
    queued_at: str | None
    completed_at: str | None


@router.post("/message", response_model=QueueMessageResponse)
async def enqueue_message(
    body: QueueMessageRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QueueMessageResponse:
    """Enqueue a Jarvis chat message for async processing.

    INSERTs the message into the database queue (instant, ~5ms).
    Background workers process it and save the response.
    Client polls GET /api/jarvis/queue/{message_id} for the response.

    This replaces the synchronous POST /api/jarvis/message endpoint,
    which froze when 3+ users chatted concurrently due to sync DB calls
    blocking the event loop.
    """
    message_id = str(uuid4())

    # Calculate queue position (how many pending messages are ahead)
    pending_count = db.query(JarvisMessageQueue).filter(
        JarvisMessageQueue.status == "pending"
    ).count()
    queue_position = pending_count + 1

    # Estimate wait time: each message takes ~4s, 2 workers process at once
    estimated_wait = (queue_position // 2) * 4

    # INSERT into queue (instant, no LLM call)
    queue_row = JarvisMessageQueue(
        id=message_id,
        company_id=str(user.company_id) if user.company_id else None,
        user_id=str(user.id),
        session_id=body.session_id,
        message_content=body.content,
        status="pending",
        queue_position=queue_position,
    )
    db.add(queue_row)
    db.commit()

    logger.info(
        "jarvis_queue_enqueued message_id=%s position=%d estimated_wait=%ds",
        message_id[:8], queue_position, estimated_wait,
    )

    return QueueMessageResponse(
        message_id=message_id,
        status="pending",
        queue_position=queue_position,
        estimated_wait_seconds=estimated_wait,
        poll_url=f"/api/jarvis/queue/{message_id}",
    )


@router.get("/{message_id}", response_model=QueueStatusResponse)
async def get_queue_status(
    message_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QueueStatusResponse:
    """Poll for the status of a queued Jarvis message.

    Returns the current status:
    - 'pending': still in queue, waiting for worker
    - 'processing': worker is generating the response
    - 'completed': response is ready (in 'response' field)
    - 'failed': error occurred (in 'error' field)

    Client should poll this every 1-2 seconds until status is
    'completed' or 'failed'.
    """
    queue_row = db.query(JarvisMessageQueue).filter(
        JarvisMessageQueue.id == message_id,
        JarvisMessageQueue.user_id == str(user.id),  # security check
    ).first()

    if not queue_row:
        raise HTTPException(status_code=404, detail="Message not found")

    import json as _json

    return QueueStatusResponse(
        message_id=queue_row.id,
        status=queue_row.status,
        queue_position=queue_row.queue_position,
        response=queue_row.response_content if queue_row.status == "completed" else None,
        metadata=_json.loads(queue_row.response_metadata) if queue_row.response_metadata else None,
        knowledge_used=_json.loads(queue_row.knowledge_used) if queue_row.knowledge_used else None,
        error=queue_row.error_message,
        queued_at=queue_row.queued_at.isoformat() if queue_row.queued_at else None,
        completed_at=queue_row.completed_at.isoformat() if queue_row.completed_at else None,
    )
