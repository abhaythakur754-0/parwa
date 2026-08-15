"""
CRM Analyser Client — calls the external CRM Analyser service.

This REPLACES the old shallow CRM analyzer (crm_analyzer_service.py)
which only did 1 LLM call on Render. The external service does deep
analysis (25-30 LLM calls) on its own machine with its own NVIDIA key.

User request (2026-08-12): "remove that code of crm analyser and connect
with this. directly include this in your code dont use render or any
other stuff"

FLOW:
  1. Render collects tenant's tickets from DB
  2. Sends them to external CRM Analyser via POST /api/crm-analyser/analyze
  3. Polls GET /api/crm-analyser/analyze?id=<request_id> until completed
  4. Returns work_order: {integrations, agents, tools} to build

The external service uses NVIDIA llama-3.1-8b-instruct for analysis.
Render does NOT use its own LLM — just calls the API.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("parwa.crm_analyser_client")

# Hardcoded URL — the CRM Analyser service (no env var needed).
# Uses NVIDIA llama-3.1-8b-instruct for deep analysis (25-30 LLM calls).
# Render does NOT use its own LLM — just calls this API.
DEFAULT_CRM_ANALYSER_URL = "https://preview-chat-448c1694-61bf-48c8-bac4-d207abd37b73.space-z.ai"


def get_crm_analyser_url() -> str:
    """Get the CRM Analyser service URL from env."""
    url = os.environ.get("CRM_ANALYSER_URL", DEFAULT_CRM_ANALYSER_URL)
    if not url:
        logger.warning("CRM_ANALYSER_URL not set — CRM analysis will fail")
    return url.rstrip("/")


async def analyze_crm_external(
    tickets: List[Dict[str, Any]],
    company_name: str = "Unknown",
    connected_integrations: Optional[List[str]] = None,
    poll_interval: float = 5.0,
    max_poll_attempts: int = 60,
) -> Dict[str, Any]:
    """Send tickets to external CRM Analyser and poll for results.

    Args:
        tickets: List of ticket dicts (subject, description, status, etc.)
        company_name: Name of the company being analyzed.
        connected_integrations: List of already-connected integration keys.
        poll_interval: How often to poll for status (seconds).
        max_poll_attempts: Max polling attempts before giving up.

    Returns:
        Work order dict with:
          - integrations: list of integration names to connect
          - agents: list of agent keys to build
          - tools: list of tool keys to create
          - tickets_scanned: total tickets analyzed
    """
    import httpx

    base_url = get_crm_analyser_url()
    if not base_url:
        return {
            "error": "CRM_ANALYSER_URL not configured",
            "integrations": [],
            "agents": [],
            "tools": [],
            "tickets_scanned": 0,
        }

    # Build the CRMSnapshot (matching the format the service expects)
    snapshot = {
        "source": "upload",
        "company_name": company_name,
        "fetched_at": datetime.now(timezone.utc).isoformat() + "Z",
        "tickets": tickets,
        "contacts": [],
        "deals": [],
        "orders": [],
        "data_profile": {
            "total_tickets": len(tickets),
            "total_contacts": 0,
            "total_deals": 0,
            "total_orders": 0,
            "has_products": False,
            "has_shipping_addresses": False,
            "has_payment_data": False,
            "has_email_campaigns": False,
            "has_ticket_data": len(tickets) > 0,
            "industries_detected": [],
            "payment_methods_seen": [],
        },
        "connected_integrations": connected_integrations or [],
    }

    logger.info(
        "crm_analyser_enqueue tickets=%d company=%s url=%s",
        len(tickets), company_name, base_url[:60],
    )

    # Step 1: Enqueue the analysis request
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            r = await client.post(
                f"{base_url}/api/crm-analyser/analyze",
                json={"source": "upload", "data": snapshot},
            )
            r.raise_for_status()
            enqueue_resp = r.json()
        except Exception as exc:
            logger.error("crm_analyser_enqueue_failed: %s", str(exc)[:200])
            return {
                "error": f"Failed to enqueue: {str(exc)[:100]}",
                "integrations": [],
                "agents": [],
                "tools": [],
                "tickets_scanned": len(tickets),
            }

    request_id = enqueue_resp.get("request_id")
    if not request_id:
        return {
            "error": "No request_id returned",
            "integrations": [],
            "agents": [],
            "tools": [],
            "tickets_scanned": len(tickets),
        }

    logger.info("crm_analyser_enqueued request_id=%s", request_id)

    # Step 2: Poll until completed
    async with httpx.AsyncClient(timeout=15.0) as client:
        for attempt in range(max_poll_attempts):
            await asyncio.sleep(poll_interval)

            try:
                r = await client.get(
                    f"{base_url}/api/crm-analyser/analyze",
                    params={"id": request_id},
                )
                r.raise_for_status()
                status_resp = r.json()
            except Exception as exc:
                logger.warning("crm_analyser_poll_failed attempt=%d: %s", attempt, str(exc)[:100])
                continue

            status = status_resp.get("status", {})
            state = status.get("status", "unknown")

            if state == "completed":
                result = status.get("result", {})
                work_order = result.get("work_order", {})
                logger.info(
                    "crm_analyser_completed tickets=%d integrations=%d agents=%d tools=%d",
                    result.get("tickets_scanned", 0),
                    len(work_order.get("integrations", [])),
                    len(work_order.get("agents", [])),
                    len(work_order.get("tools", [])),
                )
                return {
                    "integrations": work_order.get("integrations", []),
                    "agents": work_order.get("agents", []),
                    "tools": work_order.get("tools", []),
                    "tickets_scanned": result.get("tickets_scanned", len(tickets)),
                    "full_result": result,
                }

            elif state == "failed":
                error = status.get("error_message", "Unknown error")
                logger.error("crm_analyser_failed: %s", error[:200])
                return {
                    "error": error,
                    "integrations": [],
                    "agents": [],
                    "tools": [],
                    "tickets_scanned": len(tickets),
                }

            else:
                # Still processing
                batches = status.get("batches_done", 0)
                total = status.get("total_batches", 0)
                llm_calls = status.get("llm_calls_made", 0)
                logger.info(
                    "crm_analyser_processing attempt=%d batches=%d/%d llm_calls=%d",
                    attempt, batches, total, llm_calls,
                )

    # Timed out
    logger.warning("crm_analyser_timeout after %d attempts", max_poll_attempts)
    return {
        "error": f"Analysis timed out after {max_poll_attempts * poll_interval}s",
        "integrations": [],
        "agents": [],
        "tools": [],
        "tickets_scanned": len(tickets),
    }


def collect_tenant_tickets(db, company_id: str, days: int = 30) -> List[Dict[str, Any]]:
    """Collect tenant's tickets from Render's DB for CRM analysis.

    Fetches all tickets from the last N days and formats them
    as the CRMSnapshot expects.
    """
    from datetime import datetime, timezone, timedelta
    from database.models.tickets import Ticket, TicketMessage

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    tickets = db.query(Ticket).filter(
        Ticket.company_id == company_id,
        Ticket.created_at >= cutoff,
    ).all()

    result = []
    for t in tickets:
        # Get first customer message
        first_msg = db.query(TicketMessage).filter(
            TicketMessage.ticket_id == t.id,
            TicketMessage.role == "customer",
        ).order_by(TicketMessage.created_at.asc()).first()

        description = ""
        if first_msg:
            description = first_msg.content or ""
        if not description and t.subject:
            description = t.subject

        result.append({
            "id": str(t.id),
            "subject": t.subject or "",
            "description": description[:1000],
            "status": t.status or "open",
            "priority": t.priority or "medium",
            "type": "problem",
            "tags": [],
            "created_at": t.created_at.isoformat() if t.created_at else "",
            "requester": {
                "name": t.customer_name or "",
                "email": t.customer_email or "",
            },
        })

    return result
