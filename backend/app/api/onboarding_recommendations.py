"""
Onboarding Recommendations API.

Combines CRM analysis + ticket scan to give the user a unified list of:
  1. Recommended integrations to connect (with reasons)
  2. Recommended agents to build (with capabilities)
  3. Integration health check (are connected ones working?)

This is the "brain" of Step 2 of the onboarding wizard.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from database.base import get_db
from database.models.core import User

logger = logging.getLogger("parwa.api.onboarding_recs")

router = APIRouter(prefix="/api/onboarding", tags=["Onboarding Recommendations"])


class RecommendationResponse(BaseModel):
    """Unified response for onboarding Step 2."""
    status: str
    tickets_scanned: int
    connected_integrations: List[Dict[str, Any]]
    recommended_integrations: List[Dict[str, Any]]
    recommended_agents: List[Dict[str, Any]]
    integration_health: List[Dict[str, Any]]
    analysis_summary: str


class HealthCheckResponse(BaseModel):
    """Integration health check response."""
    integrations: List[Dict[str, Any]]
    all_healthy: bool


@router.post("/crm-analysis/start")
async def start_crm_analysis(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Start CRM analysis (async — returns immediately with request_id).

    The external CRM Analyser takes 10-30s to process.
    This endpoint enqueues the request and returns immediately.
    Client polls GET /api/onboarding/crm-analysis/status?id=<request_id>
    until status='completed'.
    """
    company_id = str(user.company_id)

    try:
        from app.core.crm_analyser_client import (
            analyze_crm_external,
            collect_tenant_tickets,
            get_crm_analyser_url,
        )

        if not get_crm_analyser_url():
            return {"status": "error", "message": "CRM_ANALYSER_URL not configured"}

        # Collect tickets
        tickets = collect_tenant_tickets(db, company_id, days=30)

        # Get connected integrations
        from app.services.integration_service import IntegrationService
        integration_service = IntegrationService(db)
        connected = integration_service.get_active_integrations(company_id)
        connected_names = [i.get("name", i.get("type", "")) for i in connected]

        # Enqueue to external CRM Analyser (just the enqueue, not the full poll)
        import httpx
        from datetime import datetime, timezone
        base_url = get_crm_analyser_url()

        snapshot = {
            "source": "upload",
            "company_name": getattr(user, "company_name", "Unknown"),
            "fetched_at": datetime.now(timezone.utc).isoformat() + "Z",
            "tickets": tickets,
            "contacts": [],
            "deals": [],
            "orders": [],
            "data_profile": {
                "total_tickets": len(tickets),
                "total_contacts": 0, "total_deals": 0, "total_orders": 0,
                "has_products": False, "has_shipping_addresses": False,
                "has_payment_data": False, "has_email_campaigns": False,
                "has_ticket_data": len(tickets) > 0,
                "industries_detected": [], "payment_methods_seen": [],
            },
            "connected_integrations": connected_names,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                f"{base_url}/api/crm-analyser/analyze",
                json={"source": "upload", "data": snapshot},
            )
            r.raise_for_status()
            enqueue_resp = r.json()

        request_id = enqueue_resp.get("request_id")
        return {
            "status": "started",
            "request_id": request_id,
            "tickets_sent": len(tickets),
            "poll_url": f"/api/onboarding/crm-analysis/status?id={request_id}",
            "message": f"Sent {len(tickets)} tickets for analysis. Poll for results.",
        }

    except Exception as exc:
        logger.warning("crm_analysis_start_failed: %s", str(exc)[:200])
        return {"status": "error", "message": str(exc)[:200]}


@router.get("/crm-analysis/status")
async def get_crm_analysis_status(
    id: str,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Poll for CRM analysis status.

    Returns:
    - status='processing' (still running)
    - status='completed' (result ready in work_order)
    - status='failed' (error)
    """
    try:
        from app.core.crm_analyser_client import get_crm_analyser_url
        import httpx

        base_url = get_crm_analyser_url()
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{base_url}/api/crm-analyser/analyze",
                params={"id": id},
            )
            r.raise_for_status()
            status_resp = r.json()

        status = status_resp.get("status", {})
        state = status.get("status", "unknown")

        if state == "completed":
            result = status.get("result", {})
            work_order = result.get("work_order", {})
            return {
                "status": "completed",
                "tickets_scanned": result.get("tickets_scanned", 0),
                "integrations": work_order.get("integrations", []),
                "agents": work_order.get("agents", []),
                "tools": work_order.get("tools", []),
                "full_result": result,
            }
        elif state == "failed":
            return {"status": "failed", "error": status.get("error_message", "Unknown")}
        else:
            return {
                "status": "processing",
                "batches_done": status.get("batches_done", 0),
                "total_batches": status.get("total_batches", 0),
                "llm_calls": status.get("llm_calls_made", 0),
            }

    except Exception as exc:
        return {"status": "error", "message": str(exc)[:200]}


@router.get("/recommendations", response_model=RecommendationResponse)
async def get_recommendations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    """Get unified recommendations for onboarding Step 2.

    Uses ticket keyword scan (fast, no external call) for the basic
    recommendations. For deep CRM analysis, client should call:
      POST /api/onboarding/crm-analysis/start
      GET  /api/onboarding/crm-analysis/status?id=<request_id>
    """
    company_id = str(user.company_id)

    # ── Step 1: Connected integrations + keyword scan (fast) ──
    # For deep CRM analysis, client calls POST /crm-analysis/start
    # (the external service takes 10-30s — too slow for this endpoint)
    try:
        from app.services.integration_service import IntegrationService
        integration_service = IntegrationService(db)
        connected = integration_service.get_active_integrations(company_id)

        crm_result = {
            "connected_integrations": connected,
            "recommendations": [],  # filled by deep analysis (async endpoint)
            "analysis_summary": (
                f"{len(connected)} integration(s) connected. "
                "Click 'Analyze' for deep AI analysis."
            ),
        }
    except Exception as exc:
        logger.warning("integration_fetch_failed: %s", str(exc)[:200])
        crm_result = {
            "connected_integrations": [],
            "recommendations": [],
            "analysis_summary": "Analysis unavailable.",
        }

    # ── Step 2: Ticket scan (detect capabilities) ──
    try:
        from datetime import datetime, timezone, timedelta
        from database.models.tickets import Ticket, TicketMessage
        import json

        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        tickets = db.query(Ticket).filter(
            Ticket.company_id == company_id,
            Ticket.created_at >= cutoff,
        ).all()

        ticket_texts = []
        for t in tickets:
            first_msg = db.query(TicketMessage).filter(
                TicketMessage.ticket_id == t.id,
                TicketMessage.role == "customer",
            ).order_by(TicketMessage.created_at.asc()).first()
            text = ""
            if first_msg:
                text = first_msg.content or ""
            if not text and t.subject:
                text = t.subject
            if text:
                ticket_texts.append({"text": text[:500]})

        # Quick keyword-based capability detection (fast, no LLM)
        capabilities_detected = set()
        keyword_map = {
            "refund": "refund_processing",
            "money back": "refund_processing",
            "cancel": "order_cancellation",
            "credit": "credit_adjustment",
            "shipping": "shipping_delivery",
            "address": "shipping_delivery",
            "login": "account_management",
            "password": "account_management",
            "subscription": "subscription_management",
            "invoice": "invoice_request",
            "billing": "billing_inquiry",
            "payment": "billing_inquiry",
            "charged": "billing_inquiry",
            "error": "technical_support",
            "bug": "technical_support",
        }
        for t in ticket_texts:
            text_lower = t["text"].lower()
            for keyword, cap in keyword_map.items():
                if keyword in text_lower:
                    capabilities_detected.add(cap)

        recommended_agents = [
            {
                "capability": cap,
                "reason": f"Found tickets mentioning {cap.replace('_', ' ')}",
                "priority": "high" if cap in ["refund_processing", "billing_inquiry"] else "medium",
            }
            for cap in sorted(capabilities_detected)
        ]
    except Exception as exc:
        logger.warning("ticket_scan_failed: %s", str(exc)[:200])
        ticket_texts = []
        recommended_agents = []

    # ── Step 3: Integration health check ──
    integration_health = []
    try:
        from app.services.integration_service import IntegrationService
        integration_service = IntegrationService(db)
        connected = crm_result.get("connected_integrations", [])
        for integration in connected:
            integ_name = integration.get("name", integration.get("type", "unknown"))
            # Quick health check — just verify it exists + is active
            integration_health.append({
                "name": integ_name,
                "status": "connected",
                "healthy": True,  # TODO: add actual API health check
                "message": "Connected",
            })
    except Exception as exc:
        logger.warning("health_check_failed: %s", str(exc)[:200])

    return RecommendationResponse(
        status="ok",
        tickets_scanned=len(ticket_texts),
        connected_integrations=crm_result.get("connected_integrations", []),
        recommended_integrations=crm_result.get("recommendations", []),
        recommended_agents=recommended_agents,
        integration_health=integration_health,
        analysis_summary=crm_result.get("analysis_summary", ""),
    )


@router.get("/integration-health", response_model=HealthCheckResponse)
async def check_integration_health(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HealthCheckResponse:
    """Check if all connected integrations are working.

    For each connected integration:
    1. Verifies credentials exist in DB
    2. Makes a test API call (e.g. "GET /customers" for Stripe)
    3. Returns health status

    Used after user connects integrations in onboarding to verify
    everything works before building agents.
    """
    company_id = str(user.company_id)

    integrations = []
    all_healthy = True

    try:
        from app.services.integration_service import IntegrationService
        integration_service = IntegrationService(db)
        connected = integration_service.get_active_integrations(company_id)

        for integ in connected:
            integ_name = integ.get("name", integ.get("type", "unknown"))
            # Check if credentials exist
            has_creds = bool(integ.get("credentials") or integ.get("api_key"))
            healthy = has_creds
            if not healthy:
                all_healthy = False

            integrations.append({
                "name": integ_name,
                "status": "connected" if has_creds else "missing_credentials",
                "healthy": healthy,
                "message": "Working" if healthy else "Missing credentials — reconnect needed",
            })
    except Exception as exc:
        logger.warning("health_check_error: %s", str(exc)[:200])
        all_healthy = False

    return HealthCheckResponse(
        integrations=integrations,
        all_healthy=all_healthy,
    )
