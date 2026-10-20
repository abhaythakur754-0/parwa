"""Phase 3 — Auto-retry escalated tickets when the missing connection arrives.

When a ticket escalated with `escalation_type=missing_connection`, the
structured ask (escalation_ask) names the capability the AI was missing
("a payment gateway integration", "a shipping / carrier integration", …)
and, since Phase 1, that ask lives on the ticket metadata. This service
closes the loop: the moment the tenant connects a matching integration,
the tickets that were WAITING for it are transitioned back to `open`
(reason: auto_retry) so the persistent worker pool re-runs the full
pipeline — this time with the tool it was missing.

Outcome handling reuses every existing path:
  - Retry resolves it → pipeline result flows through
    _push_to_crm_outbound → resolution lands on the ORIGINAL CRM ticket
    (push_response) and the customer is answered.
  - Retry fails again → normal escalation → crm_pending again, ask
    refreshed, returned to the CRM team. No ticket is ever lost.
  - Thrash guard: each ticket records its auto_retry count in metadata;
    after MAX_AUTO_RETRIES it stays with the human.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("parwa.services.auto_retry")

MAX_AUTO_RETRIES = 3
MAX_TICKETS_PER_EVENT = 20
_SCAN_CAP = 200

# IntegrationCategory → substrings of the escalation_ask capability text.
# Mirrors escalation_ask._ACTION_CAPABILITIES; if you add a capability
# there, add its category keyword here so Phase 3 can match it.
_CATEGORY_KEYWORDS: Dict[str, tuple] = {
    "payments": ("payment gateway", "billing integration"),
    "shipping": ("shipping / carrier",),
    "ecommerce": ("ecommerce / store",),
    "crm": ("crm integration",),
    "productivity": ("scheduling",),
    "inventory": ("inventory",),  # custom catalogs may use this value
}


def retry_tickets_for_integration(
    db,
    company_id: str,
    integration_type: str,
    category: str = "",
) -> Dict[str, Any]:
    """Requeue crm_pending tickets whose escalation ask matches this integration.

    Non-fatal by design: any failure is logged and returned in the summary —
    connecting an integration must NEVER fail because the retry sweep hiccuped.
    """
    summary: Dict[str, Any] = {
        "integration_type": integration_type,
        "category": category,
        "matched": 0,
        "retried": 0,
        "skipped_max_retries": 0,
        "ticket_ids": [],
        "error": None,
    }
    try:
        from database.models.tickets import Ticket
        from app.services.pipeline_dispatcher import dispatch_pipeline_for_ticket

        itype = (integration_type or "").lower().strip()
        keywords = _CATEGORY_KEYWORDS.get((category or "").lower().strip(), ())

        rows = (
            db.query(Ticket)
            .filter(
                Ticket.company_id == company_id,
                Ticket.status == "crm_pending",
                # Cheap SQL prefilter on the VALUE only — json.dumps spacing
                # differs between writers ("key": "v" vs "key":"v"), so the
                # exact _extract_ask parse below is the real gate.
                Ticket.metadata_json.contains('"missing_connection"'),
            )
            .order_by(Ticket.updated_at.asc())
            .limit(_SCAN_CAP)
            .all()
        )

        for ticket in rows:
            if summary["retried"] >= MAX_TICKETS_PER_EVENT:
                break
            ask = _extract_ask(ticket)
            if ask is None:
                continue
            if not _ask_matches(ask, keywords, itype):
                continue

            retries_done = _auto_retry_count(ticket)
            if retries_done >= MAX_AUTO_RETRIES:
                summary["skipped_max_retries"] += 1
                continue

            if _requeue_ticket(db, ticket, integration_type, category, retries_done):
                try:
                    dispatch_pipeline_for_ticket(
                        ticket_id=str(ticket.id),
                        company_id=str(company_id),
                        priority=str(ticket.priority or "medium"),
                        channel=str(ticket.channel or "email"),
                        sync=True,  # DB-backed queue: workers poll for status='open'
                    )
                    summary["retried"] += 1
                    summary["ticket_ids"].append(str(ticket.id))
                    logger.info(
                        "auto_retry_queued ticket=%s integration=%s try=%d",
                        str(ticket.id)[:8], itype, retries_done + 1,
                    )
                except Exception as exc:  # noqa: BLE001 — dispatch is best-effort
                    logger.warning("auto_retry_dispatch_failed ticket=%s err=%s",
                                   str(ticket.id)[:8], str(exc)[:150])
        return summary
    except Exception as exc:  # noqa: BLE001 — never break the connect flow
        logger.error("auto_retry_sweep_failed company=%s err=%s",
                     str(company_id)[:8], str(exc)[:200])
        summary["error"] = str(exc)[:300]
        return summary


def _extract_ask(ticket) -> Optional[Dict[str, Any]]:
    """Parse escalation_ask from metadata; None unless a missing_connection ask."""
    try:
        meta = json.loads(ticket.metadata_json or "{}")
        if not isinstance(meta, dict):
            return None
        if meta.get("escalation_type") != "missing_connection":
            return None
        ask = meta.get("escalation_ask")
        return ask if isinstance(ask, dict) and ask else None
    except (json.JSONDecodeError, TypeError):
        return None


def _ask_matches(ask: Dict[str, Any], keywords: tuple, integration_type: str) -> bool:
    """Does the ask's missing capability match the newly connected integration?

    Two ways to match: category keywords ("payment gateway" ← payments) or
    the provider name appearing in the ask text (the ask names examples like
    "Razorpay, Stripe" — connecting exactly one of those matches directly).
    """
    haystack = " ".join(
        str(ask.get(k, "") or "")
        for k in ("capability", "needed_from_team", "problem")
    ).lower()
    if not haystack.strip():
        return False
    if any(kw in haystack for kw in keywords):
        return True
    return bool(integration_type) and integration_type in haystack


def _auto_retry_count(ticket) -> int:
    try:
        meta = json.loads(ticket.metadata_json or "{}")
        info = meta.get("auto_retry") if isinstance(meta, dict) else None
        if isinstance(info, dict):
            return int(info.get("count", 0) or 0)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return 0


def _requeue_ticket(db, ticket, integration_type: str, category: str,
                    previous_count: int) -> bool:
    """crm_pending → open (auto_retry) + record the attempt in metadata."""
    try:
        from app.services.ticket_state_machine import TicketStateMachine, TicketStatus

        TicketStateMachine(db, str(ticket.company_id)).transition(
            ticket,
            to_status=TicketStatus.open,
            reason="auto_retry",
        )
    except Exception as exc:  # noqa: BLE001 — illegal transition (e.g. raced) → skip
        logger.warning("auto_retry_transition_failed ticket=%s err=%s",
                       str(ticket.id)[:8], str(exc)[:150])
        return False

    try:
        meta: Dict[str, Any] = {}
        try:
            meta = json.loads(ticket.metadata_json or "{}")
            if not isinstance(meta, dict):
                meta = {}
        except (json.JSONDecodeError, TypeError):
            meta = {}
        meta["auto_retry"] = {
            "count": previous_count + 1,
            "integration": integration_type[:100],
            "category": category[:50],
            "at": datetime.now(timezone.utc).isoformat(),
        }
        ticket.metadata_json = json.dumps(meta)
        db.commit()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("auto_retry_metadata_failed ticket=%s err=%s",
                       str(ticket.id)[:8], str(exc)[:150])
        db.rollback()
        return False
