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

# Configurable via env var.
# Default 10: allows tickets to flow through the pipeline like an assembly line.
# Fast providers (Groq) can process light calls for tickets 6-10 while slow
# providers (NVIDIA) are still working on hard calls for tickets 1-5.
MAX_CONCURRENT_PIPELINES = int(os.environ.get("MAX_CONCURRENT_PIPELINES", "10"))
_workers_started = False
_workers_lock = _threading_mod.Lock()






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
