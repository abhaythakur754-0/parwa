"""
Jarvis Queue Worker — background thread that processes queued messages.

Same architecture as the ticket pipeline workers (pipeline_dispatcher.py):
  - Runs as daemon threads (survive HTTP request lifecycle)
  - Polls jarvis_message_queue table every 2 seconds
  - Processes 2 messages at a time (configurable via MAX_CONCURRENT_JARVIS)
  - Each worker runs in its own thread (no event loop blocking)

When a worker finds a 'pending' message:
  1. Mark it 'processing' (claim it)
  2. Call send_message() to generate response
  3. Save response + mark 'completed'
  4. Poll for next pending message

This replaces the synchronous semaphore approach, which froze when
sync DB calls blocked the FastAPI event loop.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("parwa.jarvis_queue_worker")

MAX_CONCURRENT_JARVIS = int(os.environ.get("MAX_CONCURRENT_JARVIS", "2"))
_workers_started = False
_workers_lock = threading.Lock()


def start_jarvis_queue_workers():
    """Start background worker threads that poll the jarvis_message_queue.

    Called once at application startup (main.py lifespan).
    Spawns MAX_CONCURRENT_JARVIS daemon threads, each polling the DB
    for pending messages.
    """
    global _workers_started
    with _workers_lock:
        if _workers_started:
            return
        _workers_started = True

    for worker_id in range(MAX_CONCURRENT_JARVIS):
        t = threading.Thread(
            target=_worker_loop,
            args=(worker_id,),
            daemon=True,
            name=f"jarvis-queue-worker-{worker_id}",
        )
        t.start()
        logger.info(
            "jarvis_queue_worker_started worker_id=%d (max=%d)",
            worker_id, MAX_CONCURRENT_JARVIS,
        )


def _worker_loop(worker_id: int):
    """Worker thread main loop — polls DB for pending messages."""
    from database.base import SessionLocal
    from database.models.jarvis import JarvisMessageQueue

    while True:
        try:
            db = SessionLocal()
            try:
                # Claim the next pending message (atomic)
                # SELECT ... FOR UPDATE SKIP LOCKED would be ideal, but
                # SQLite/Postgres compatibility — use status update instead
                pending = db.query(JarvisMessageQueue).filter(
                    JarvisMessageQueue.status == "pending"
                ).order_by(
                    JarvisMessageQueue.queued_at.asc()
                ).limit(1).with_for_update(skip_locked=True).first()

                if not pending:
                    db.close()
                    time.sleep(2)  # No work — wait 2s before polling again
                    continue

                # Claim it — mark as processing
                pending.status = "processing"
                pending.processing_started_at = datetime.now(timezone.utc)
                pending.worker_id = f"worker-{worker_id}"
                db.commit()

                message_id = pending.id
                logger.info(
                    "jarvis_queue_worker_claimed worker=%d message_id=%s",
                    worker_id, message_id[:8],
                )

            except Exception:
                db.close()
                time.sleep(2)
                continue
            finally:
                pass  # db stays open for processing

            # Process the message (in this thread, not blocking event loop)
            try:
                _process_message(db, pending)
            except Exception as exc:
                logger.error(
                    "jarvis_queue_worker_failed worker=%d message_id=%s err=%s",
                    worker_id, message_id[:8], str(exc)[:200],
                )
                # Mark as failed
                try:
                    pending.status = "failed"
                    pending.error_message = str(exc)[:500]
                    pending.completed_at = datetime.now(timezone.utc)
                    db.commit()
                except Exception:
                    pass

            db.close()

        except Exception as exc:
            logger.error("jarvis_queue_worker_crash worker=%d err=%s",
                         worker_id, str(exc)[:200])
            time.sleep(5)


def _process_message(db, queue_row):
    """Process a single queued Jarvis message.

    Calls send_message() to generate the response, then saves it.
    Runs in a worker thread — does NOT block the FastAPI event loop.
    """
    import json as _json

    # Create a new event loop for this thread (send_message is async)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # Get the session
        from app.services.jarvis_service import get_session, build_system_prompt
        from app.services.jarvis.chat import send_message, _parse_context
        session = get_session(db, queue_row.session_id, queue_row.user_id)

        # Build context
        ctx = _parse_context(session.context_json) if session else {}
        company_id = queue_row.company_id or ""

        # Call send_message (async — run in this thread's event loop)
        user_msg, ai_msg, knowledge = loop.run_until_complete(
            send_message(
                db=db,
                session_id=queue_row.session_id,
                user_id=queue_row.user_id,
                user_message=queue_row.message_content,
            )
        )

        # Save response to queue row
        queue_row.status = "completed"
        queue_row.response_content = ai_msg.content[:10000] if ai_msg else ""
        queue_row.completed_at = datetime.now(timezone.utc)

        # Save metadata
        if hasattr(ai_msg, 'metadata_json') and ai_msg.metadata_json:
            queue_row.response_metadata = ai_msg.metadata_json
        if knowledge:
            queue_row.knowledge_used = _json.dumps(knowledge)

        db.commit()

        logger.info(
            "jarvis_queue_worker_completed message_id=%s response_chars=%d",
            queue_row.id[:8], len(queue_row.response_content or ""),
        )

    finally:
        loop.close()
