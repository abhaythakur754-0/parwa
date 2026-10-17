"""
CRM Resolution Service — the HumanReplacement + self-learning loop.

Why this exists (2026-01 product decision):
  The old flow parked tickets on `awaiting_human` — if no human was on
  shift the ticket stalled forever and resolution time ballooned. Humans
  are being replaced completely. Now, when the AI can't resolve a ticket,
  the dispatcher marks it `crm_pending` and opens a request in the
  tenant's CRM. When that request is resolved (CRM webhook, or the owner
  recording it in the dashboard), THIS service:

  1. Relays the resolution to the customer as an AI message (their channel)
  2. Marks the Parwa ticket resolved
  3. TEACHES the AI: writes the (customer question → working resolution)
     pattern into the AI Wiki (Section A) via write_ticket_pattern —
     the same store Node 3.5 (few-shot) and Node 3 (knowledge fetch)
     already read. Next time a similar ticket arrives, the pipeline
     finds this pattern and resolves it autonomously.

Memory-footprint note (512MB Render plan): "self-learning" here is
retrieval-augmented memory, not model fine-tuning — one wiki row per
resolution in Supabase Postgres, recalled by the existing wiki search.
No local models, no embeddings infra, well within 512MB.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("parwa.services.crm_resolution")


class CRMResolutionService:
    """Ingest a CRM (or dashboard-recorded) resolution into a Parwa ticket."""

    @staticmethod
    def resolve_ticket(
        db,
        ticket,
        resolution_text: str,
        resolved_by: str = "crm",
        source: str = "crm_webhook",
        notify_customer: bool = True,
        learn: bool = True,
    ) -> Dict[str, Any]:
        """Apply a resolution to a crm_pending (or legacy awaiting_human) ticket.

        Args:
            db: SQLAlchemy session.
            ticket: Ticket model instance (must belong to caller's tenant).
            resolution_text: How the issue was solved (customer-appropriate wording).
            resolved_by: Free-text attribution (CRM agent name / "dashboard").
            source: "crm_webhook" | "dashboard_record" | "crm_poll".
            notify_customer: Relay the resolution to the customer channel.
            learn: Write the resolution pattern to the AI Wiki (the learning step).

        Returns:
            {status, ticket_id, learned (bool), wiki_key, message_id}
        """
        from database.models.tickets import TicketMessage
        from app.core.email_utils import strip_reasoning

        text = strip_reasoning((resolution_text or "").strip())
        if not text or len(text) < 5:
            return {"status": "error", "ticket_id": str(ticket.id),
                    "message": "resolution text is empty"}

        if ticket.status == "resolved":
            return {"status": "already_resolved", "ticket_id": str(ticket.id)}

        now = datetime.now(timezone.utc)
        message_id: Optional[str] = None

        # ── 1. Relay the resolution to the customer as an AI message ──
        if notify_customer:
            try:
                message_id = str(__import__("uuid").uuid4())
                db.add(TicketMessage(
                    id=message_id,
                    ticket_id=ticket.id,
                    company_id=ticket.company_id,
                    role="ai",
                    content=text[:6000],
                    channel=ticket.channel,
                    variant_version=f"crm_resolution:{resolved_by}"[:100],
                    metadata_json='{"source": "%s"}' % source,
                    created_at=now,
                ))
            except Exception as exc:  # noqa: BLE001
                logger.warning("crm_resolution_message_failed ticket=%s err=%s",
                               str(ticket.id)[:8], str(exc)[:150])
                message_id = None

        # ── 2. Mark the ticket resolved ────────────────────────────────
        ticket.status = "resolved"
        ticket.awaiting_human = False
        ticket.resolved_at = now
        if not ticket.closed_at:
            ticket.closed_at = now
        ticket.updated_at = now

        try:
            import json as _json
            meta: Dict[str, Any] = {}
            if ticket.metadata_json:
                try:
                    meta = _json.loads(ticket.metadata_json)
                except Exception:  # noqa: BLE001
                    meta = {}
            if isinstance(meta, dict):
                meta["crm_resolution"] = {
                    "resolved_by": resolved_by[:100],
                    "source": source,
                    "resolved_at": now.isoformat(),
                    "learned": learn,
                }
                ticket.metadata_json = _json.dumps(meta)
        except Exception as exc:  # noqa: BLE001
            logger.warning("crm_resolution_metadata_failed ticket=%s err=%s",
                           str(ticket.id)[:8], str(exc)[:150])

        db.commit()

        # ── 3. THE LEARNING STEP — teach the AI wiki ───────────────────
        wiki_key = None
        if learn:
            wiki_key = CRMResolutionService.learn_from_resolution(db, ticket, text)

        # ── 4. Deliver to the customer's channel (email/sms/chat) ─────
        if notify_customer and message_id:
            try:
                from app.core.channel_dispatcher import ChannelDispatcher
                dispatcher = ChannelDispatcher(db)
                dispatcher.dispatch(
                    company_id=ticket.company_id,
                    ticket_id=str(ticket.id),
                    ai_response_html=f"<p>{text[:6000]}</p>",
                    ai_response_text=text[:6000],
                    role="ai",
                    model_used="crm_resolution",
                    confidence=None,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("crm_resolution_dispatch_failed ticket=%s err=%s",
                               str(ticket.id)[:8], str(exc)[:150])

        logger.info(
            "crm_resolution_applied ticket=%s source=%s learned=%s wiki_key=%s",
            str(ticket.id)[:8], source, learn, wiki_key,
        )
        return {
            "status": "resolved",
            "ticket_id": str(ticket.id),
            "message_id": message_id,
            "learned": learn and wiki_key is not None,
            "wiki_key": wiki_key,
        }

    @staticmethod
    def learn_from_resolution(db, ticket, resolution_text: str) -> Optional[str]:
        """Write (question → resolution) into AI Wiki Section A.

        Reuses the exact store the pipeline reads from, so the very next
        similar ticket benefits — this is the whole self-learning loop.
        Non-fatal: a wiki failure never blocks the ticket resolution.
        """
        try:
            from database.models.tickets import TicketMessage
            from app.core.parwa_pipeline.ai_wiki_store import get_wiki_store

            first_msg = (
                db.query(TicketMessage)
                .filter(TicketMessage.ticket_id == ticket.id, TicketMessage.role == "customer")
                .order_by(TicketMessage.created_at.asc())
                .first()
            )
            query_text = (first_msg.content if first_msg else "") or (ticket.subject or "")

            ticket_type = (
                getattr(ticket, "classification_type", None)
                or getattr(ticket, "category", None)
                or "general"
            )

            entry = get_wiki_store().write_ticket_pattern(
                tenant_id=str(ticket.company_id),
                ticket_type=str(ticket_type),
                query=query_text[:1000],
                complexity="medium",
                techniques_used=["CRM_Learning", "HumanReplacement"],
                quality_score=0.9,
                answer_summary=resolution_text[:500],
                tier="parwa",
            )
            if entry:
                logger.info("crm_learning_written ticket=%s wiki_key=%s",
                            str(ticket.id)[:8], entry.entry_key)
                return entry.entry_key
        except Exception as exc:  # noqa: BLE001
            logger.warning("crm_learning_write_failed ticket=%s err=%s",
                           str(ticket.id)[:8], str(exc)[:200])
        return None

    @staticmethod
    def find_ticket_by_crm_id(db, crm_ticket_id: str):
        """Locate a Parwa ticket by its CRM reference in metadata_json."""
        from database.models.tickets import Ticket

        if not crm_ticket_id:
            return None
        return (
            db.query(Ticket)
            .filter(Ticket.metadata_json.contains(f'"crm_ticket_id":"{crm_ticket_id}"'))
            .order_by(Ticket.created_at.desc())
            .first()
        )
