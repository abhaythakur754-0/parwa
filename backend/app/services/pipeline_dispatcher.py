"""
Pipeline Dispatcher — triggers the 8-node PARWA pipeline on a ticket.

Two modes:
  1. EMERGENCY (critical priority tickets): runs SYNCHRONOUSLY in the
     current request thread so the customer gets an AI response in the
     same HTTP response. Skips the Celery queue.
  2. STANDARD (high / medium / low priority): enqueues a Celery task
     for async processing. Falls back to synchronous execution if
     Celery is unavailable (Redis down) so the system still works.

The dispatcher:
  1. Loads the ticket + first customer message from the DB
  2. Builds a PipelineV2State
  3. Runs the 8-node pipeline (Node 1 → Node 8)
  4. Stores the AI response as a TicketMessage (role="ai")
  5. Updates ticket.status → resolved | awaiting_human
  6. Writes cost/savings/confidence to ticket.metadata_json
  7. Triggers ChannelDispatcher to send the response to the customer
     (email reply / SMS / chat socket / voice)

Used by:
  - app/api/tickets.py:create_ticket — auto-triggers after commit
  - app/api/workflow.py:process_endpoint — manual re-trigger
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Coroutine, Dict, Optional

logger = logging.getLogger("parwa.pipeline_dispatcher")

# ── Priority constants ────────────────────────────────────────────────────
CRITICAL_PRIORITY = "critical"
EMERGENCY_PRIORITIES = {CRITICAL_PRIORITY}

# ── Database-backed worker pool (bulletproof, survives restarts) ────────
# Render starter plan has 512MB RAM and 1 CPU. Each pipeline uses ~40-50MB.
#
# ARCHITECTURE: DB-backed worker pool
# - 7 persistent worker threads run forever
# - Workers poll the DATABASE for tickets with status='open'
# - Worker claims a ticket atomically (UPDATE status='processing')
# - Worker runs the pipeline, then sets status='resolved' or 'awaiting_human'
# - If server crashes/restarts, unprocessed tickets are still in the DB
#   with status='open' → workers pick them up on next poll
#
# This is the same pattern used by Celery, RQ, Sidekiq — a durable queue
# backed by a database. No in-memory state, no lost tickets, no OOM.
import os
import threading as _threading_mod
import time as _time_mod

# Configurable via env var so it can be tuned without code changes.
#
# VERIFIED (2026-08-12): raised back to 10 after async Jarvis refactor.
#
# The original bottleneck was NOT memory — it was Jarvis using sync urllib
# which blocked the FastAPI event loop for 60s per call. Now that Jarvis
# is async (httpx), 10 concurrent tickets + Jarvis chat run side-by-side
# without stalling. Verified via concurrent test:
#   - Ticket creation: 12s (pipeline processing)
#   - Jarvis chat: 12s (full LLM response)
#   - Both ran in parallel, no blocking.
#
# Memory math for 512 MB Render Starter:
#   Base process: ~150 MB
#   10 workers: ~80 MB
#   10 concurrent tickets: ~100-150 MB
#   Jarvis + Redis + pools: ~60 MB
#   Total peak: ~390-440 MB < 512 MB ✅
#
# Each ticket is assigned to a specific provider to avoid rate-limit collisions.
# Rest queue in DB. Workers poll DB for 'open' tickets.
MAX_CONCURRENT_PIPELINES = int(os.environ.get("MAX_CONCURRENT_PIPELINES", "10"))
_workers_started = False
_workers_lock = _threading_mod.Lock()


# ═══════════════════════════════════════════════════════════════════════
# TICKET-TO-PROVIDER ASSIGNMENT
# ═══════════════════════════════════════════════════════════════════════
# Each ticket is assigned to a MAJOR provider (NVIDIA, Groq, Mistral, Gemini).
# All LLM calls for that ticket go to the assigned provider.
# If the major provider returns 429 → switch to BACKUP (Cerebras, Aion).
# After 60s (rate limit renews) → switch back to major provider.
#
# MAJOR PROVIDERS (primary — one ticket each):
#   1. NVIDIA (40 RPM)     — deep reasoning tickets
#   2. Groq (30 RPM)        — fast classification tickets
#   3. Mistral (60 RPM)     — medium/hard tickets
#   4. Gemini (30 RPM)      — chat/new request tickets
#
# BACKUP PROVIDERS (when major is 429'd):
#   5. Cerebras (5 RPM)
#   6. Aion Labs (15 RPM)
# ═══════════════════════════════════════════════════════════════════════

import threading as _t




def _claim_next_ticket():
    """Atomically claim the next 'open' ticket from the database.
    
    Uses SELECT ... FOR UPDATE SKIP LOCKED to claim a ticket without
    blocking other workers. Sets status='processing' so no other worker
    picks the same ticket.
    
    Returns (ticket_id, company_id, channel) or None if no tickets.
    """
    try:
        from database.base import SessionLocal
        from sqlalchemy import text
        
        db = SessionLocal()
        try:
            # ── Priority-based queue: process HIGH priority first ──
            # Priority order: critical > high > medium > low
            # Within same priority: oldest first (updated_at ASC)
            # This ensures urgent tickets (refunds, account locked) are
            # processed before low-priority ones (invoice requests, FAQs)
            result = db.execute(text(
                "UPDATE tickets SET status = 'processing', updated_at = NOW() "
                "WHERE id = ("
                "  SELECT id FROM tickets "
                "  WHERE status = 'open' "
                "  ORDER BY "
                "    CASE priority "
                "      WHEN 'critical' THEN 1 "
                "      WHEN 'high' THEN 2 "
                "      WHEN 'medium' THEN 3 "
                "      WHEN 'low' THEN 4 "
                "      ELSE 5 "
                "    END, "
                "    updated_at ASC "
                "  FOR UPDATE SKIP LOCKED "
                "  LIMIT 1"
                ") "
                "RETURNING id, company_id, channel"
            ))
            row = result.fetchone()
            db.commit()
            if row:
                return str(row[0]), str(row[1]), str(row[2]) if row[2] else "email"
            return None
        finally:
            db.close()
    except Exception as exc:
        logger.warning("claim_next_ticket_error: %s", str(exc)[:200])
        return None


def _start_pipeline_workers():
    """Start the persistent DB-backed worker pool (called once on startup)."""
    global _workers_started
    with _workers_lock:
        if _workers_started:
            return
        _workers_started = True

        def _worker(worker_id: int):
            """Persistent worker — polls DB for open tickets and processes them.

            RETRY LOGIC for rate-limited LLM calls:
            - When pipeline fails with "all providers exhausted" (rate limited),
              the ticket is put BACK in the queue (status='open') with a retry count.
            - After 3 failed retries, it's escalated to awaiting_human (so it's not lost).
            - Between retries, the worker sleeps 60s to let rate limits renew.
            - This means: tickets WAIT for credits to renew instead of being escalated.
            """
            MAX_RETRIES = 3  # Max retries before escalating to human
            RATE_LIMIT_WAIT = 60  # Seconds to wait for rate limit to renew (Groq 30 RPM = 60s cycle)

            while True:
                try:
                    claim = _claim_next_ticket()
                    if claim:
                        ticket_id, company_id, channel = claim
                        
                        # ── AWARE TICKET PICKUP ──────────────────────────
                        # Before processing, check if tenant has the agents/tools
                        # to solve this ticket. If not, mark 'review_needed' instead
                        # of picking it up + escalating to human after wasting LLM calls.
                        # This is the user's vision: "our product should have the awareness
                        # based on that we should select the ticket"
                        awareness = _check_tenant_awareness(ticket_id, company_id)
                        if not awareness["can_solve"]:
                            # Tenant doesn't have the agents/tools to solve this.
                            # Leave it for admin review instead of failing in pipeline.
                            _mark_ticket_for_review(ticket_id, company_id, awareness["reason"])
                            logger.info(
                                "worker_%d ticket=%s marked review_needed (%s)",
                                worker_id, ticket_id[:8], awareness["reason"][:80],
                            )
                            # Move to next ticket without running pipeline
                            continue

                        try:
                            logger.info(
                                "worker_%d claimed ticket=%s (awareness: %d agents, %d tools)",
                                worker_id, ticket_id[:8],
                                awareness["agent_count"], awareness["tool_count"],
                            )
                            _run_pipeline_sync(ticket_id, company_id, channel)
                        except Exception as exc:
                            err_msg = str(exc)[:300]
                            logger.error(
                                "worker_%d pipeline_error ticket=%s err=%s",
                                worker_id, ticket_id[:8], err_msg[:200],
                            )

                            # ── Check if this is a rate-limit failure (retryable) ──
                            is_rate_limit = (
                                "all providers exhausted" in err_msg.lower()
                                or "rate limit" in err_msg.lower()
                                or "429" in err_msg
                            )

                            try:
                                from database.base import SessionLocal
                                from database.models.tickets import Ticket
                                import json as _json
                                db = SessionLocal()
                                try:
                                    ticket = db.query(Ticket).filter(
                                        Ticket.id == ticket_id
                                    ).first()
                                    if ticket and ticket.status == "processing":
                                        # Get current retry count from metadata
                                        meta = {}
                                        try:
                                            meta = _json.loads(ticket.metadata_json or "{}")
                                        except Exception:
                                            meta = {}
                                        retry_count = meta.get("pipeline_retry_count", 0)

                                        if is_rate_limit and retry_count < MAX_RETRIES:
                                            # ── RETRY: put ticket back in queue ──
                                            # Rate limit will renew in ~60s, then
                                            # a worker will pick this ticket up again
                                            meta["pipeline_retry_count"] = retry_count + 1
                                            meta["last_retry_reason"] = "rate_limited"
                                            meta["next_retry_after"] = RATE_LIMIT_WAIT
                                            ticket.status = "open"  # back in queue
                                            ticket.awaiting_human = False
                                            # Update updated_at so this ticket goes to the END of the
                                            # queue (not the front). The claim query uses
                                            # ORDER BY created_at ASC, but we want rate-limited
                                            # tickets to be retried AFTER other tickets, not
                                            # immediately reclaimed by the same worker.
                                            from datetime import datetime, timezone
                                            ticket.updated_at = datetime.now(timezone.utc)
                                            ticket.metadata_json = _json.dumps(meta)
                                            db.commit()
                                            logger.info(
                                                "worker_%d ticket=%s RETRY %d/%d (rate limited, waiting %ds)",
                                                worker_id, ticket_id[:8],
                                                retry_count + 1, MAX_RETRIES, RATE_LIMIT_WAIT,
                                            )
                                            # NOTE: Do NOT sleep here — just put the ticket back in
                                            # the queue and let the worker claim the NEXT available
                                            # ticket immediately. The rate-limited ticket will be
                                            # retried when a worker picks it up again (by then the
                                            # rate limit will have renewed naturally).
                                            #
                                            # The old code slept 60s here, which blocked the worker
                                            # from processing other tickets → queue got stuck.
                                        else:
                                            # ── ESCALATE: max retries reached or non-retryable error ──
                                            ticket.status = "awaiting_human"
                                            ticket.awaiting_human = True
                                            meta["escalation_reason"] = (
                                                "max_retries_exceeded" if is_rate_limit
                                                else "pipeline_error"
                                            )
                                            meta["pipeline_error"] = err_msg[:200]
                                            ticket.metadata_json = _json.dumps(meta)
                                            db.commit()
                                            logger.info(
                                                "worker_%d ticket=%s ESCALATED to human (retries=%d, rate_limited=%s)",
                                                worker_id, ticket_id[:8],
                                                retry_count, is_rate_limit,
                                            )
                                finally:
                                    db.close()
                            except:
                                pass
                    else:
                        # No tickets to process — sleep briefly
                        _time_mod.sleep(2)
                except Exception as exc:
                    logger.error("worker_%d crash: %s", worker_id, str(exc)[:200])
                    _time_mod.sleep(5)

        for i in range(MAX_CONCURRENT_PIPELINES):
            t = _threading_mod.Thread(
                target=_worker, args=(i,), daemon=True,
                name=f"pipeline-worker-{i}",
            )
            t.start()
        logger.info(
            "db_backed_worker_pool_started: %d workers polling DB",
            MAX_CONCURRENT_PIPELINES,
        )


def _run_async_safely(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run an async coroutine from sync code AND return its result.

    Handles two cases:
    1. No running event loop in current thread → use ``asyncio.run``.
    2. Running event loop in current thread (e.g. FastAPI/uvicorn) →
       dispatch to a fresh worker thread that has no loop, run there,
       and return the result. This avoids the
       ``RuntimeError: asyncio.run() cannot be called from a running event loop``
       crash.

    Used by _push_to_crm_outbound to call async CRMBridge methods from
    the sync pipeline dispatcher context.
    """
    try:
        asyncio.get_running_loop()
        result_holder: Dict[str, Any] = {}

        def _worker() -> None:
            try:
                result_holder["value"] = asyncio.run(coro)
            except Exception as exc:  # noqa: BLE001
                result_holder["error"] = exc

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join()
        if "error" in result_holder:
            raise result_holder["error"]
        return result_holder.get("value")
    except RuntimeError:
        return asyncio.run(coro)


def dispatch_pipeline_for_ticket(
    ticket_id: str,
    company_id: str,
    priority: str,
    channel: str,
    sync: Optional[bool] = None,
) -> Dict[str, Any]:
    """Trigger the 8-node pipeline on a ticket.

    Args:
        ticket_id: The ticket to process.
        company_id: Tenant ID for isolation.
        priority: Ticket priority (critical | high | medium | low).
            Critical tickets are processed SYNCHRONOUSLY (emergency path).
            Others are dispatched to Celery (async), with sync fallback.
        channel: Ticket channel (email | chat | sms | voice).
        sync: Force sync (True) or async (False). If None, auto-decides
            based on priority.

    Returns:
        Dict with keys: status (sync|async|error), ticket_id, message_id?
    """
    if sync is None:
        # FORCE_SYNC_PIPELINE defaults to true — Celery worker isn't running
        # on Render free tier. Sync mode is slower but RELIABLE.
        # Set FORCE_SYNC_PIPELINE=false to use Celery (requires worker service).
        import os
        if os.environ.get("FORCE_SYNC_PIPELINE", "true").lower() in ("1", "true", "yes"):
            sync = True
        else:
            sync = priority in EMERGENCY_PRIORITIES

    if sync:
        # ── DB-backed dispatch (bulletproof for high volume) ──
        # The ticket is already saved in the DB with status='open' by the
        # ticket creation endpoint. The 7 persistent workers are polling
        # the DB for 'open' tickets and will pick this one up within 2 seconds.
        #
        # No in-memory queue, no thread-per-ticket, no lost tickets on restart.
        # Just start the worker pool (idempotent — only starts once).
        _start_pipeline_workers()
        return {
            "status": "queued",
            "ticket_id": ticket_id,
            "message": f"Ticket queued in DB ({MAX_CONCURRENT_PIPELINES} workers polling)",
        }

    # ── Async path: try Celery first, fall back to sync ──────────────
    try:
        from app.tasks.celery_app import app as celery_app
        task = celery_app.send_task(
            "parwa.run_pipeline_for_ticket",
            kwargs={"ticket_id": ticket_id, "company_id": company_id, "channel": channel},
        )
        return {
            "status": "async",
            "ticket_id": ticket_id,
            "task_id": task.id,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "pipeline_celery_dispatch_failed_falling_back_to_sync",
            extra={
                "ticket_id": ticket_id,
                "company_id": company_id,
                "error": str(exc)[:200],
            },
        )
        # Sync fallback — use the same DB-backed worker pool
        _start_pipeline_workers()
        return {
            "status": "queued",
            "ticket_id": ticket_id,
            "message": "Ticket queued in DB (Celery fallback)",
        }


def _run_pipeline_sync(
    ticket_id: str,
    company_id: str,
    channel: str,
) -> Dict[str, Any]:
    """Run the pipeline synchronously and persist the AI response.

    Returns:
        Dict with status, ticket_id, message_id, ai_response (truncated).
    """
    from database.base import SessionLocal
    from database.models.tickets import Ticket, TicketMessage, Customer

    db = SessionLocal()
    try:
        # ── Load ticket ────────────────────────────────────────────────
        ticket = db.query(Ticket).filter(
            Ticket.id == ticket_id,
            Ticket.company_id == company_id,
        ).first()
        if not ticket:
            logger.error("pipeline_ticket_not_found", extra={"ticket_id": ticket_id})
            return {"status": "error", "ticket_id": ticket_id, "error": "Ticket not found"}

        # ── Load first customer message as the query ──────────────────
        first_msg = db.query(TicketMessage).filter(
            TicketMessage.ticket_id == ticket_id,
            TicketMessage.role == "customer",
        ).order_by(TicketMessage.created_at.asc()).first()

        query_text = ""
        if first_msg:
            query_text = first_msg.content or ""
        if not query_text and ticket.subject:
            query_text = ticket.subject
        if not query_text:
            query_text = "(no customer query provided)"

        # ── Load customer context ─────────────────────────────────────
        customer: Optional[Customer] = None
        if ticket.customer_id:
            customer = db.query(Customer).filter(
                Customer.id == ticket.customer_id,
                Customer.company_id == company_id,
            ).first()

        customer_context: Dict[str, Any] = {
            "customer_id": ticket.customer_id or "",
            "email": customer.email if customer else "",
            "name": customer.name if customer else "",
            "phone": customer.phone if customer else "",
            "account_tier": "parwa",
        }

        # ── Build pipeline state ──────────────────────────────────────
        try:
            from app.core.parwa_pipeline.state_v2 import PipelineV2State
        except ImportError:
            # state_v2 is a TypedDict — just use a plain dict
            PipelineV2State = dict  # type: ignore[assignment]

        initial_state: PipelineV2State = {
            "ticket_id": ticket_id,
            "tenant_id": company_id,
            "query": query_text,
            "channel_type": channel,
            "customer_context": customer_context,
            "metadata": {
                "source": "dashboard_create",
                "ticket_id": ticket_id,
                "priority": ticket.priority,
                "category": ticket.category or "",
                "subject": ticket.subject or "",
            },
        }

        # ── Run the 8-node pipeline ───────────────────────────────────
        import asyncio
        from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline, get_checkpointer

        graph = build_parwa_pipeline()
        compiled = graph.compile(checkpointer=get_checkpointer())
        pipeline_config = {"configurable": {"thread_id": ticket_id}}

        try:
            # graph_v2's compiled.ainvoke is async. We may be in sync or
            # async context — handle both.
            try:
                asyncio.get_running_loop()
                # Already in a loop — run in a worker thread to avoid
                # "asyncio.run() cannot be called from a running event loop"
                import threading
                result_holder: Dict[str, Any] = {}

                def _worker() -> None:
                    try:
                        result_holder["value"] = asyncio.run(compiled.ainvoke(initial_state, config=pipeline_config))
                    except Exception as exc:  # noqa: BLE001
                        result_holder["error"] = exc

                t = threading.Thread(target=_worker, daemon=True)
                t.start()
                t.join()
                if "error" in result_holder:
                    raise result_holder["error"]
                result = dict(result_holder["value"])
            except RuntimeError:
                # No running loop — safe to use asyncio.run
                result = dict(asyncio.run(compiled.ainvoke(initial_state, config=pipeline_config)))
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "pipeline_execution_failed",
                extra={
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "error": str(exc)[:300],
                },
            )
            # ── Fallback: write a contextual AI message so the ticket still
            # has a response and doesn't get stuck in "open" forever.
            ai_response_text = (
                f"Thank you for contacting us regarding \"{ticket.subject or 'your inquiry'}\". "
                f"I've received your message and a human agent will follow up with you shortly. "
                f"Your ticket has been logged and is being tracked."
            )
            _persist_ai_response(
                db=db,
                ticket=ticket,
                ai_response_text=ai_response_text,
                ai_response_html=f"<p>{ai_response_text}</p>",
                confidence=None,
                model_used="fallback",
                cost_per_ticket=0.0,
                savings_per_ticket=0.0,
                status="awaiting_human",
            )

            # ── Gap 3: Dispatch fallback message to customer channel ──
            # Previously this only wrote to the DB — the customer never
            # received the email/SMS/chat notification. Now we dispatch
            # via ChannelDispatcher so the customer actually gets told
            # their ticket was received and is being escalated.
            try:
                from app.core.channel_dispatcher import ChannelDispatcher
                dispatcher = ChannelDispatcher(db)
                dispatcher.dispatch(
                    company_id=company_id,
                    ticket_id=ticket_id,
                    ai_response_html=f"<p>{ai_response_text}</p>",
                    ai_response_text=ai_response_text,
                    role="ai",
                    model_used="fallback",
                    confidence=None,
                )
            except Exception as dispatch_exc:  # noqa: BLE001
                logger.warning(
                    "channel_dispatch_failed_fallback",
                    extra={
                        "ticket_id": ticket_id,
                        "channel": channel,
                        "error": str(dispatch_exc)[:200],
                    },
                )

            # CRM outbound push runs even on fallback — the tenant's CRM
            # should still know about the ticket even if AI couldn't resolve
            # it. Status will be "escalated" in the CRM.
            crm_create_result = _push_to_crm_outbound(
                db=db,
                ticket_id=ticket_id,
                company_id=company_id,
                subject=ticket.subject or "Customer Support Ticket",
                description=query_text,
                customer_email=customer.email if customer else "",
                customer_name=customer.name if customer else "",
                priority=ticket.priority,
                category=ticket.category or "",
                ai_response_text=ai_response_text,
                ai_response_html=f"<p>{ai_response_text}</p>",
                ticket_status="awaiting_human",
                model_used="fallback",
            )

            return {
                "status": "error",
                "ticket_id": ticket_id,
                "error": str(exc)[:200],
                "fallback": True,
                "crm_pushed": crm_create_result.get("success", False),
                "crm_ticket_id": crm_create_result.get("crm_ticket_id", ""),
                "crm_provider": crm_create_result.get("crm_provider", ""),
            }

        # ── Handle pipeline interrupt (node paused to ask a question) ──
        if "__interrupt__" in result:
            interrupt_data = result["__interrupt__"]
            question_text = ""
            customer_text = ""  # Customer-facing message (separate from internal question)
            if isinstance(interrupt_data, list) and interrupt_data:
                val = interrupt_data[0].value if hasattr(interrupt_data[0], 'value') else interrupt_data[0]
                if isinstance(val, dict):
                    question_text = val.get("question", str(val))
                    customer_text = val.get("customer_message", "")  # May be absent for older interrupts
                else:
                    question_text = str(val)
            # Customer sees the friendly message; falls back to question if absent
            display_text = customer_text or question_text

            # ── Check if display_text contains internal vocabulary ──
            # If the interrupt came from a node that doesn't set customer_message
            # (e.g. Node 4/7 when KB docs are missing), the question text itself
            # may contain internal vocabulary. Replace with escalation template.
            _INTERNAL_MARKERS = (
                "gsd goals", "knowledge base documents", "can you provide guidance",
                "no ai agent claims", "relevant doc(s) found", "gaps:",
                "push it back to the crm", "action=escalate_human",
            )
            if any(marker in display_text.lower() for marker in _INTERNAL_MARKERS):
                customer_name = customer.name if customer else "Valued Customer"
                display_text = (
                    f"Dear {customer_name},\n\n"
                    f"Thank you for your patience. We want to let you know that "
                    f"your case ({ticket_id}) has been escalated to our "
                    f"specialist team for further review.\n\n"
                    f"A dedicated team member will contact you within 2 hours "
                    f"with an update and next steps.\n\n"
                    f"We understand the urgency of your request and are "
                    f"prioritising it accordingly.\n\n"
                    f"Kind regards,\n"
                    f"Support Team"
                )
                logger.info(
                    "replaced_interrupt_internal_vocab ticket=%s original=%s",
                    ticket_id, str(question_text)[:100],
                )

            logger.info("pipeline_interrupted ticket=%s question=%s", ticket_id, str(question_text)[:100])
            _persist_ai_response(
                db=db, ticket=ticket, ai_response_text=display_text,
                ai_response_html=f"<p>{display_text}</p>",
                confidence=None, model_used="parwa_interrupt",
                cost_per_ticket=0.0, savings_per_ticket=0.0,
                status="awaiting_human",
            )
            return {"status": "interrupted", "ticket_id": ticket_id, "question": question_text, "message": "Pipeline paused — waiting for guidance to resume."}

        # ── Extract pipeline result fields ────────────────────────────
        # ── Handle pipeline interrupt (node paused to ask a question) ──
        # When a node calls interrupt(), the pipeline PAUSES (Approach A).
        # The ticket is marked awaiting_human and the AI's question is saved
        # so the escalations page can show it + let human/variant answer.
        if result.get("pipeline_interrupted"):
            interrupt_question = result.get("interrupt_question", "")
            logger.info(
                "pipeline_interrupted ticket=%s question=%s",
                ticket_id, str(interrupt_question)[:100],
            )
            # Save the question as a ticket message so it's visible
            _persist_ai_response(
                db=db,
                ticket=ticket,
                ai_response_text=interrupt_question,
                ai_response_html=f"<p>{interrupt_question}</p>",
                confidence=None,
                model_used="parwa_interrupt",
                cost_per_ticket=0.0,
                savings_per_ticket=0.0,
                status="awaiting_human",
            )
            # Save pipeline state snapshot to DB so resume can restore it
            try:
                import json as _json
                from database.models.variant_engine import PipelineStateSnapshot
                snapshot = PipelineStateSnapshot(
                    company_id=company_id,
                    ticket_id=ticket_id,
                    current_node="interrupted",
                    state_data=_json.dumps(result, default=str)[:100000],
                    snapshot_type="checkpoint",
                )
                db.add(snapshot)
                db.commit()
            except Exception as exc:
                logger.warning("pipeline_state_snapshot_save_failed: %s", str(exc)[:150])
            return {
                "status": "interrupted",
                "ticket_id": ticket_id,
                "question": interrupt_question,
                "message": "Pipeline paused — waiting for guidance to resume.",
            }

        ai_response_text = (
            result.get("final_response")
            or result.get("response")
            or ""
        )
        # ── Gap 2: Use polished escalation template when AI escalates ──
        # When the pipeline escalates (force_human_handoff, cove_blocked, or
        # non-resolved status) and either (a) no final_response was set, or
        # (b) the final_response contains internal vocabulary that shouldn't
        # be shown to customers, use the "Your Case Has Been Escalated"
        # template text instead.
        force_human = result.get("force_human_handoff", False)
        cove_blocked = result.get("cove_blocked", False)
        pipeline_status_raw = result.get("status", "resolved")
        is_escalating = force_human or cove_blocked or pipeline_status_raw != "resolved"

        # Check if the AI response contains internal vocabulary that customers
        # shouldn't see (GSD goals, KB doc counts, guidance requests, etc.)
        _INTERNAL_MARKERS = (
            "gsd goals", "knowledge base documents", "can you provide guidance",
            "no ai agent claims", "relevant doc(s) found", "gaps:",
            "push it back to the crm", "action=escalate_human",
        )
        _looks_internal = bool(ai_response_text) and any(
            marker in ai_response_text.lower() for marker in _INTERNAL_MARKERS
        )

        if is_escalating and (not ai_response_text or _looks_internal):
            customer_name = customer.name if customer else "Valued Customer"
            ai_response_text = (
                f"Dear {customer_name},\n\n"
                f"Thank you for your patience. We want to let you know that "
                f"your case ({ticket_id}) has been escalated to our "
                f"specialist team for further review.\n\n"
                f"A dedicated team member will contact you within 2 hours "
                f"with an update and next steps.\n\n"
                f"We understand the urgency of your request and are "
                f"prioritising it accordingly.\n\n"
                f"Kind regards,\n"
                f"Support Team"
            )
            if _looks_internal:
                logger.info(
                    "replaced_internal_vocabulary_with_template ticket=%s original_preview=%s",
                    ticket_id, str(result.get("final_response", ""))[:100],
                )
        ai_response_html = result.get("final_response_html") or f"<p>{ai_response_text}</p>"
        pipeline_status = result.get("status", "resolved")
        confidence = result.get("confidence")
        if confidence is not None:
            try:
                confidence = float(confidence)
                # Confidence may be 0-1 or 0-100; normalize to 0-100
                if confidence <= 1.0:
                    confidence = confidence * 100.0
            except (TypeError, ValueError):  # noqa: BLE001
                confidence = None
        model_used = result.get("model_used") or result.get("variant") or "parwa"
        cost = result.get("cost_usd") or result.get("cost") or 0.0
        try:
            cost = float(cost)
        except (TypeError, ValueError):  # noqa: BLE001
            cost = 0.0
        # Savings = (typical human agent cost $12.50) - AI cost
        savings = max(0.0, 12.5 - cost)

        # ── Persist AI response as TicketMessage + update ticket ──────
        # Honor force_human_handoff from Node 5 (legal/sensitive intent):
        # even if the pipeline reports "resolved", legal threats must wait
        # for human review before being marked resolved.
        # (force_human already extracted above for template logic)

        # Extract CRM/ecommerce/carrier data from pipeline state so it
        # can be persisted to the ticket's metadata_json — the dashboard
        # Customer Context Panel reads this to show the human agent what
        # data the AI used (orders, CRM profile, tracking, custom API data).
        crm_data = result.get("crm_data", {})

        logger.info(
            "pipeline_dispatcher_force_human_check ticket=%s force_human=%s pipeline_status=%s result_keys=%s",
            ticket_id, force_human, pipeline_status, list(result.keys())[:15],
        )
        if force_human:
            pipeline_status = "awaiting_human"

        # ── Gap 4: Create Escalation Vault entry for mid-pipeline escalations ──
        # Previously only Node 8 failures created a vault entry. Mid-pipeline
        # escalations (Node 1 legal keywords, Node 4 low confidence, Node 4.5
        # CoVe blocked, Node 5 force_human_handoff) only set the ticket status
        # to awaiting_human — the human agent had no vault context on the
        # Escalations dashboard. Now we create a vault entry for ALL escalations
        # so the human agent sees the full pipeline context.
        if force_human or cove_blocked or pipeline_status == "escalated":
            try:
                from app.core.escalation_vault.vault_manager import VaultManager
                # Build a minimal state dict for the vault (the full result
                # dict has all the pipeline state we need)
                vault_state = dict(result)
                vault_state.setdefault("tenant_id", company_id)
                vault_state.setdefault("ticket_id", ticket_id)
                vault_state.setdefault("query", query_text)
                # VaultManager.save_escalation_from_pipeline is async — use
                # _run_async_safely to call it from this sync function.
                vault_record = _run_async_safely(
                    VaultManager.save_escalation_from_pipeline(
                        state=vault_state,
                        escalation_context={
                            "failure_analysis": (
                                f"Mid-pipeline escalation: force_human={force_human}, "
                                f"cove_blocked={cove_blocked}, pipeline_status={pipeline_status}"
                            ),
                            "previous_attempts": [],
                        },
                        escalation_source="dispatcher_mid_pipeline",
                    )
                )
                if vault_record:
                    logger.info(
                        "vault_entry_created_mid_pipeline ticket=%s vault_id=%s",
                        ticket_id, vault_record.get("escalation_id", "?")[:8],
                    )
            except Exception as vault_exc:  # noqa: BLE001
                logger.warning(
                    "vault_save_failed_mid_pipeline ticket=%s err=%s",
                    ticket_id, str(vault_exc)[:200],
                )

        new_status = "resolved" if pipeline_status == "resolved" else "awaiting_human"
        _persist_ai_response(
            db=db,
            ticket=ticket,
            ai_response_text=str(ai_response_text)[:6000],
            ai_response_html=str(ai_response_html)[:12000],
            confidence=confidence,
            model_used=str(model_used),
            cost_per_ticket=cost,
            savings_per_ticket=savings,
            status=new_status,
            crm_data=crm_data,
        )

        # ── Dispatch to channel (email / chat / sms / voice) ─────────
        try:
            from app.core.channel_dispatcher import ChannelDispatcher
            dispatcher = ChannelDispatcher(db)
            dispatcher.dispatch(
                company_id=company_id,
                ticket_id=ticket_id,
                ai_response_html=str(ai_response_html)[:12000],
                ai_response_text=str(ai_response_text)[:6000],
                role="ai",
                model_used=str(model_used),
                confidence=confidence,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "channel_dispatch_failed",
                extra={
                    "ticket_id": ticket_id,
                    "channel": channel,
                    "error": str(exc)[:200],
                },
            )

        # ── CRM outbound push (Option B) ─────────────────────────────
        # For manually-created tickets (source=dashboard_create), the ticket
        # did NOT come from a CRM webhook — so state["metadata"] has no
        # crm_ticket_id. If the tenant has a CRM integration configured
        # (hubspot / zendesk / generic), we CREATE a new ticket in their CRM
        # and push the AI response back to it. This way the tenant's human
        # support team has full visibility into AI-resolved tickets.
        #
        # If no integration is configured → skip silently (current behavior).
        # If CRM API fails → log warning + persist crm_create_status to
        # ticket metadata; the Parwa ticket is already resolved, so we do
        # NOT propagate the exception.
        crm_create_result = _push_to_crm_outbound(
            db=db,
            ticket_id=ticket_id,
            company_id=company_id,
            subject=ticket.subject or "Customer Support Ticket",
            description=query_text,
            customer_email=customer.email if customer else "",
            customer_name=customer.name if customer else "",
            priority=ticket.priority,
            category=ticket.category or "",
            ai_response_text=str(ai_response_text)[:6000],
            ai_response_html=str(ai_response_html)[:12000],
            ticket_status=new_status,
            model_used=str(model_used),
        )

        logger.info(
            "pipeline_completed_sync",
            extra={
                "ticket_id": ticket_id,
                "company_id": company_id,
                "status": new_status,
                "confidence": confidence,
                "cost_usd": cost,
                "model_used": model_used,
                "crm_pushed": crm_create_result.get("success", False),
                "crm_ticket_id": crm_create_result.get("crm_ticket_id", ""),
            },
        )

        return {
            "status": "sync",
            "ticket_id": ticket_id,
            "ai_response": str(ai_response_text)[:200],
            "confidence": confidence,
            "cost_per_ticket": cost,
            "new_ticket_status": new_status,
            "crm_pushed": crm_create_result.get("success", False),
            "crm_ticket_id": crm_create_result.get("crm_ticket_id", ""),
            "crm_provider": crm_create_result.get("crm_provider", ""),
        }

    finally:
        db.close()


def _persist_ai_response(
    db,
    ticket,
    ai_response_text: str,
    ai_response_html: str,
    confidence: Optional[float],
    model_used: str,
    cost_per_ticket: float,
    savings_per_ticket: float,
    status: str,
    crm_data: Optional[dict] = None,
) -> str:
    """Persist the AI response as a TicketMessage + update ticket fields.

    Args:
        db: SQLAlchemy session.
        ticket: Ticket model instance (will be mutated + committed).
        ai_response_text: Plain-text AI response.
        ai_response_html: HTML version of the response.
        confidence: 0-100 confidence score, or None.
        model_used: Model / variant name.
        cost_per_ticket: AI cost in USD.
        savings_per_ticket: Human-agent cost avoided (USD).
        status: New ticket status ("resolved" or "awaiting_human").

    Returns:
        The new TicketMessage ID.
    """
    from database.models.tickets import TicketMessage

    # ── Idempotency check: if an AI message already exists for this
    # ticket (e.g. written by ChannelDispatcher during Node 6.5 delivery),
    # skip the insert and return the existing message ID. This prevents
    # the duplicate-message bug where both the pipeline dispatcher AND
    # the channel dispatcher persist the same AI response.
    existing = (
        db.query(TicketMessage)
        .filter(
            TicketMessage.ticket_id == ticket.id,
            TicketMessage.role == "ai",
        )
        .order_by(TicketMessage.created_at.desc())
        .first()
    )
    if existing:
        # Still update ticket fields (status, timestamps) but don't insert
        # a duplicate AI message.
        now = datetime.now(timezone.utc)
        ticket.status = status
        ticket.variant_version = model_used
        ticket.awaiting_human = (status == "awaiting_human")
        if not ticket.first_response_at:
            ticket.first_response_at = now
        if status == "resolved" and not ticket.closed_at:
            ticket.closed_at = now
        ticket.updated_at = now
        try:
            db.commit()
        except Exception:
            db.rollback()
        return str(existing.id)

    message_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # ── Create the AI TicketMessage ──────────────────────────────────
    ai_msg = TicketMessage(
        id=message_id,
        ticket_id=ticket.id,
        company_id=ticket.company_id,
        role="ai",
        content=ai_response_text,
        channel=ticket.channel,
        ai_confidence=confidence,
        variant_version=model_used,
        metadata_json=json.dumps({
            "ai_response_html": ai_response_html,
            "model_used": model_used,
            "cost_per_ticket": cost_per_ticket,
            "savings_per_ticket": savings_per_ticket,
        }),
        created_at=now,
    )
    db.add(ai_msg)

    # ── Update ticket fields ─────────────────────────────────────────
    ticket.status = status
    ticket.variant_version = model_used
    ticket.awaiting_human = (status == "awaiting_human")
    if not ticket.first_response_at:
        ticket.first_response_at = now
    if status == "resolved" and not ticket.closed_at:
        ticket.closed_at = now
    ticket.updated_at = now

    # ── Write cost/savings/confidence into ticket metadata ───────────
    metadata = {}
    if ticket.metadata_json:
        try:
            metadata = json.loads(ticket.metadata_json)
        except (json.JSONDecodeError, TypeError):
            metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["cost_per_ticket"] = cost_per_ticket
    metadata["savings_per_ticket"] = savings_per_ticket
    if confidence is not None:
        metadata["ai_confidence"] = confidence
    metadata["model_used"] = model_used
    metadata["pipeline_completed_at"] = now.isoformat()

    # Persist CRM/ecommerce/carrier data so the dashboard Customer Context
    # Panel can display what the AI saw (orders, CRM profile, tracking, etc.)
    if crm_data and isinstance(crm_data, dict):
        # Only save non-None values (skip empty fields)
        context = {}
        for k, v in crm_data.items():
            if v is not None:
                context[k] = v
        if context:
            # Truncate to avoid exceeding column size — keep first 2000 chars
            context_str = json.dumps(context)
            if len(context_str) > 2000:
                context_str = context_str[:2000]
            metadata["customer_context"] = json.loads(context_str)
    ticket.metadata_json = json.dumps(metadata)

    db.commit()
    return message_id


def _push_to_crm_outbound(
    db,
    ticket_id: str,
    company_id: str,
    subject: str,
    description: str,
    customer_email: str,
    customer_name: str,
    priority: str,
    category: str,
    ai_response_text: str,
    ai_response_html: str,
    ticket_status: str,
    model_used: str,
) -> Dict[str, Any]:
    """Create a new ticket in the tenant's CRM + push the AI response to it.

    Called after the Parwa ticket is resolved and the AI response is
    persisted. If the tenant has no CRM integration configured, returns
    {success: False, skipped: True, reason: "no_crm_integration"}. If the
    CRM API fails, returns {success: False, error: "..."} but does NOT
    raise — the Parwa ticket is already resolved and the customer already
    has the AI response via their channel.

    On success, the new crm_ticket_id is persisted to
    ticket.metadata_json["crm_ticket_id"] so the Parwa UI can deep-link
    to the CRM ticket.

    Args:
        db: SQLAlchemy session (used to load Integration + update Ticket metadata).
        ticket_id: Parwa ticket ID.
        company_id: Tenant scope.
        subject: Ticket subject (sent to CRM).
        description: First customer message (sent to CRM as content).
        customer_email: Customer email (for CRM contact association).
        customer_name: Customer name.
        priority: Ticket priority (critical/high/medium/low).
        category: Ticket category.
        ai_response_text: AI response plain text (pushed as reply to CRM ticket).
        ai_response_html: AI response HTML.
        ticket_status: "resolved" or "awaiting_human" — pushed to CRM.
        model_used: AI model name for the internal note.

    Returns:
        Dict with: success (bool), skipped (bool, optional), crm_ticket_id,
        crm_provider, error, crm_ticket_url.
    """
    from database.models.tickets import Ticket
    from app.services.integration_service import IntegrationService
    from app.core.crm_bridge.crm_bridge import CRMBridge

    svc = IntegrationService(db)

    # ── Find the tenant's active CRM integration ─────────────────────
    # Try HubSpot first (most common), then Zendesk, then generic.
    crm_provider: Optional[str] = None
    crm_config: Optional[Dict[str, Any]] = None
    for provider in ("hubspot", "zendesk", "generic"):
        cfg = svc.get_credential_config(company_id, provider)
        if cfg:
            crm_provider = provider
            crm_config = cfg
            break

    if not crm_provider:
        # Tenant has no CRM integration — skip silently. This is the
        # common case for email-only / chat-only tenants.
        return {
            "success": False,
            "skipped": True,
            "reason": "no_crm_integration",
        }

    # ── Step 1: Create the ticket in the CRM ─────────────────────────
    create_result = _run_async_safely(CRMBridge.create_ticket(
        provider=crm_provider,
        subject=subject,
        content=description,
        customer_email=customer_email,
        customer_name=customer_name,
        priority=priority,
        category=category,
        config=crm_config,
    ))

    if not create_result.get("success"):
        logger.warning(
            "crm_outbound_create_failed",
            extra={
                "ticket_id": ticket_id,
                "company_id": company_id,
                "crm_provider": crm_provider,
                "error": str(create_result.get("error", ""))[:200],
            },
        )
        # Persist failure status to ticket metadata so the dashboard
        # can show "CRM sync failed" without breaking the resolve flow.
        _persist_crm_status_to_metadata(
            db=db,
            ticket_id=ticket_id,
            crm_provider=crm_provider,
            crm_ticket_id=None,
            crm_create_status="failed",
            crm_push_status="skipped",
            crm_error=str(create_result.get("error", ""))[:300],
        )
        return create_result

    crm_ticket_id = create_result.get("crm_ticket_id", "")
    logger.info(
        "crm_outbound_create_success",
        extra={
            "ticket_id": ticket_id,
            "company_id": company_id,
            "crm_provider": crm_provider,
            "crm_ticket_id": crm_ticket_id,
        },
    )

    # ── Step 2: Push the AI response to the new CRM ticket ───────────
    # Map Parwa status → CRM status:
    #   resolved       → "resolved"
    #   awaiting_human → "escalated"
    crm_status = "resolved" if ticket_status == "resolved" else "escalated"
    internal_note = (
        f"Ticket auto-resolved by PARWA AI (model={model_used}). "
        f"Original Parwa ticket ID: {ticket_id}. "
        f"Status: {ticket_status}."
    )

    push_result = _run_async_safely(CRMBridge.push_response(
        provider=crm_provider,
        ticket_id=crm_ticket_id,
        response=ai_response_text,
        status=crm_status,
        internal_note=internal_note,
        config=crm_config,
    ))

    push_success = push_result.get("success", False)
    if not push_success:
        logger.warning(
            "crm_outbound_push_failed",
            extra={
                "ticket_id": ticket_id,
                "crm_ticket_id": crm_ticket_id,
                "crm_provider": crm_provider,
                "error": str(push_result.get("error", ""))[:200],
            },
        )

    # ── Step 3: Persist CRM IDs + status to ticket metadata ──────────
    _persist_crm_status_to_metadata(
        db=db,
        ticket_id=ticket_id,
        crm_provider=crm_provider,
        crm_ticket_id=crm_ticket_id,
        crm_create_status="success",
        crm_push_status="success" if push_success else "failed",
        crm_ticket_url=create_result.get("crm_ticket_url", ""),
    )

    return {
        "success": True,
        "crm_ticket_id": crm_ticket_id,
        "crm_provider": crm_provider,
        "crm_ticket_url": create_result.get("crm_ticket_url", ""),
        "push_success": push_success,
    }


def _persist_crm_status_to_metadata(
    db,
    ticket_id: str,
    crm_provider: Optional[str],
    crm_ticket_id: Optional[str],
    crm_create_status: str,
    crm_push_status: str,
    crm_error: str = "",
    crm_ticket_url: str = "",
) -> None:
    """Persist CRM sync status into ticket.metadata_json.

    This is best-effort: if it fails, the ticket is still resolved —
    we just lose the CRM link in the dashboard.
    """
    try:
        from database.models.tickets import Ticket
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            return

        metadata: Dict[str, Any] = {}
        if ticket.metadata_json:
            try:
                metadata = json.loads(ticket.metadata_json)
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}

        metadata["crm_provider"] = crm_provider or ""
        if crm_ticket_id:
            metadata["crm_ticket_id"] = crm_ticket_id
        metadata["crm_create_status"] = crm_create_status
        metadata["crm_push_status"] = crm_push_status
        if crm_error:
            metadata["crm_error"] = crm_error
        if crm_ticket_url:
            metadata["crm_ticket_url"] = crm_ticket_url
        metadata["crm_synced_at"] = datetime.now(timezone.utc).isoformat()

        ticket.metadata_json = json.dumps(metadata)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "crm_metadata_persist_failed",
            extra={"ticket_id": ticket_id, "error": str(exc)[:200]},
        )


# ════════════════════════════════════════════════════════════════════════════
# AWARE TICKET PICKUP — check if tenant can solve this ticket
# ════════════════════════════════════════════════════════════════════════════
# User vision: "our product should have the awareness based on that we should
# select the ticket and then update the CRM"
#
# Before processing a ticket, we check:
#   1. Does tenant have at least 1 active AI agent?
#   2. Does that agent have a linked Superglue tool (for action tickets)?
#   3. Does tenant have KB documents (for FAQ tickets)?
#
# If NONE of these exist → mark ticket 'review_needed' instead of
# picking it up + failing + escalating to human after wasting LLM calls.
# This prevents the "select all tickets then escalate to humans" anti-pattern.


def _check_tenant_awareness(ticket_id: str, company_id: str) -> dict:
    """Check if tenant has the agents/tools/KB to solve this ticket.

    Returns:
        {
            "can_solve": bool,
            "reason": str,
            "agent_count": int,
            "tool_count": int,
            "has_kb": bool,
        }
    """
    try:
        from database.base import SessionLocal
        from database.models.variant_engine import AIAgentAssignment
        from database.models.onboarding import KnowledgeDocument
        from database.models.tickets import Ticket
        import json as _json

        db = SessionLocal()
        try:
            # Get the ticket to see what kind of ticket it is
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if not ticket:
                return {"can_solve": False, "reason": "ticket not found",
                        "agent_count": 0, "tool_count": 0, "has_kb": False}

            # Count active agents for this tenant
            agents = db.query(AIAgentAssignment).filter(
                AIAgentAssignment.company_id == company_id,
                AIAgentAssignment.status == "active",
            ).all()
            agent_count = len(agents)

            # Count agents that have linked Superglue tools (action-capable)
            tool_count = sum(1 for a in agents if a.superglue_tool_id and a.superglue_tool_status == "active")

            # Check if tenant has KB documents
            kb_count = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.company_id == company_id,
            ).count()
            has_kb = kb_count > 0

            # Decision logic:
            # - If tenant has 0 agents AND 0 KB → can't solve anything
            # - If tenant has agents but no tools + no KB → can only acknowledge
            # - If ticket needs an action (refund/cancel) but no tools → can't solve
            # - Otherwise → can solve
            if agent_count == 0 and not has_kb:
                return {
                    "can_solve": False,
                    "reason": "tenant has 0 agents and 0 KB documents - onboarding incomplete",
                    "agent_count": 0,
                    "tool_count": 0,
                    "has_kb": False,
                }

            # Check if ticket text suggests an action that needs a tool
            ticket_text = (ticket.subject or "") + " " + (ticket.description or "")
            ticket_text = ticket_text.lower()
            action_keywords = ["refund", "cancel", "chargeback", "delete account",
                               "block card", "stop subscription", "process return"]
            needs_action = any(kw in ticket_text for kw in action_keywords)

            if needs_action and tool_count == 0:
                return {
                    "can_solve": False,
                    "reason": f"ticket needs action ({'refund/cancel'}) but tenant has 0 active tools",
                    "agent_count": agent_count,
                    "tool_count": 0,
                    "has_kb": has_kb,
                }

            # Tenant can solve this ticket
            return {
                "can_solve": True,
                "reason": "ok",
                "agent_count": agent_count,
                "tool_count": tool_count,
                "has_kb": has_kb,
            }
        finally:
            db.close()
    except Exception as exc:
        # On error, default to "can solve" so we don't block all tickets
        logger.warning("awareness_check_error ticket=%s err=%s", ticket_id[:8], str(exc)[:200])
        return {"can_solve": True, "reason": "awareness check failed - allowing",
                "agent_count": 0, "tool_count": 0, "has_kb": False}


def _mark_ticket_for_review(ticket_id: str, company_id: str, reason: str) -> None:
    """Mark a ticket as 'review_needed' so admin sees it needs attention.

    Instead of picking the ticket up + failing + escalating, we leave it
    in a 'review_needed' state where admin can:
      - See why PARWA couldn't auto-solve it
      - Build the missing tool/agent
      - Then re-queue the ticket
    """
    try:
        from database.base import SessionLocal
        from database.models.tickets import Ticket
        import json as _json

        db = SessionLocal()
        try:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if ticket:
                ticket.status = "review_needed"
                # Add reason to metadata so admin sees why
                meta = {}
                try:
                    meta = _json.loads(ticket.metadata_json or "{}")
                except Exception:
                    meta = {}
                meta["review_reason"] = reason
                meta["review_needed_at"] = str(datetime.now(timezone.utc))
                ticket.metadata_json = _json.dumps(meta)
                ticket.awaiting_human = True
                db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.warning("mark_ticket_review_error ticket=%s err=%s", ticket_id[:8], str(exc)[:200])
