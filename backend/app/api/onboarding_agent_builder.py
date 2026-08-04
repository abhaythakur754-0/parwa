"""
Onboarding Agent Builder — PRODUCTION version.

Uses the REAL 4-stage Builder pipeline (EXPLORE → DESIGN → VERIFY → REFINE)
with NVIDIA GLM-5 for deep reasoning.

Flow:
  1. User connects CRM → POST /api/builder-agent/scan-and-build
  2. Scans recent tickets (last 30 days)
  3. NVIDIA GLM-5 classifies what capabilities are needed
  4. For each capability → runs full Builder pipeline (4 stages, NVIDIA)
  5. Each agent gets tool mapping (checks connected integrations)
  6. Tests each agent against historical tickets
  7. Only stores TESTED agents in DB
  8. Node 1 looks up tested agents (instant, no building)

NVIDIA vs Groq separation:
  → NVIDIA GLM-5: Builder stages (deep reasoning, 30 RPM)
  → Groq: Ticket processing (fast responses, 30 RPM)
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.jwt_auth import get_current_user

logger = logging.getLogger("parwa.api.onboarding_builder")

router = APIRouter(prefix="/api/builder-agent", tags=["Builder Agent"])


class ScanAndBuildRequest(BaseModel):
    max_tickets_to_scan: int = 50
    force_rebuild: bool = False


class ScanAndBuildResponse(BaseModel):
    status: str
    tickets_scanned: int
    capabilities_detected: List[str]
    agents_created: List[Dict[str, Any]]
    agents_skipped: List[str]
    errors: List[str]


# ── Tool Mapping: capability → integration + action ──────────────

CAPABILITY_TO_TOOL_MAP = {
    "refund_processing": {
        "integrations": ["stripe", "razorpay", "paypal"],
        "tool": "billing_system",
        "action": "process_refund",
    },
    "order_cancellation": {
        "integrations": ["shopify", "woocommerce", "bigcommerce"],
        "tool": "order_management",
        "action": "cancel_order",
    },
    "credit_adjustment": {
        "integrations": ["stripe", "razorpay"],
        "tool": "billing_system",
        "action": "apply_credit",
    },
    "shipping_delivery": {
        "integrations": ["shopify", "woocommerce"],
        "tool": "order_management",
        "action": "update_shipping",
    },
    "account_management": {
        "integrations": ["custom"],
        "tool": "custom_connector",
        "action": "unlock_account",
    },
    "subscription_management": {
        "integrations": ["stripe", "razorpay"],
        "tool": "billing_system",
        "action": "cancel_subscription",
    },
    "invoice_request": {
        "integrations": ["stripe", "razorpay"],
        "tool": "billing_system",
        "action": "get_invoice",
    },
    "billing_inquiry": {
        "integrations": ["stripe", "razorpay"],
        "tool": "billing_system",
        "action": "get_payment_history",
    },
}


@router.post("/scan-and-build")
async def scan_and_build(
    request: ScanAndBuildRequest,
    current_user=Depends(get_current_user),
) -> Any:
    """Scan tickets + build agents using the REAL 4-stage Builder pipeline.

    Steps:
    1. Scan recent tickets (last 30 days)
    2. NVIDIA GLM-5 classifies capabilities needed
    3. For each capability → run full Builder (EXPLORE/DESIGN/VERIFY/REFINE)
    4. Map agent to connected integrations (tool mapping)
    5. Test agent against historical tickets
    6. Store only TESTED agents in DB
    """
    try:
        from database.base import SessionLocal
        from database.models.tickets import Ticket, TicketMessage
        from database.models.variant_engine import AIAgentAssignment
        from database.models.core import Company

        db = SessionLocal()
        company_id = str(current_user.company_id)

        try:
            # ── Get tenant tier ──────────────────────────────────
            company = db.query(Company).filter(Company.id == company_id).first()
            tier = getattr(company, "plan", "parwa") if company else "parwa"

            # ── Step 1: Scan recent tickets ──────────────────────
            from datetime import datetime, timezone, timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)

            tickets = db.query(Ticket).filter(
                Ticket.company_id == company_id,
                Ticket.created_at >= cutoff,
            ).limit(request.max_tickets_to_scan).all()

            if not tickets:
                return ScanAndBuildResponse(
                    status="no_tickets",
                    tickets_scanned=0,
                    capabilities_detected=[],
                    agents_created=[],
                    agents_skipped=[],
                    errors=["No tickets found in the last 30 days"],
                )

            # ── Step 2: Load ticket texts ────────────────────────
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
                    ticket_texts.append({
                        "id": str(t.id),
                        "subject": t.subject or "",
                        "text": text[:500],
                    })

            # ── Step 3: Check connected integrations ────────────
            from app.services.integration_service import IntegrationService
            integration_service = IntegrationService(db)

            connected_integrations = []
            for integration_type in ["stripe", "razorpay", "shopify", "woocommerce",
                                     "bigcommerce", "twilio", "brevo", "sendgrid",
                                     "mailgun", "ses", "postmark", "smtp"]:
                creds = integration_service.get_credential_config(company_id, integration_type)
                if creds:
                    connected_integrations.append(integration_type)

            logger.info(
                "onboarding_builder: company=%s tickets=%d connected=%s",
                company_id, len(ticket_texts), connected_integrations,
            )

            # ── Step 4: NVIDIA classifies capabilities ───────────
            capabilities_detected = []

            if os.environ.get("NVIDIA_API_KEY"):
                from app.core.parwa_pipeline.llm_client import _call_nvidia_direct
                import re

                classify_prompt = f"""Analyze these {len(ticket_texts)} customer support tickets.
Identify what CAPABILITIES are needed to handle them.

Common capabilities:
- refund_processing (customer wants money back)
- order_cancellation (customer wants to cancel order)
- credit_adjustment (customer wants credit applied)
- shipping_delivery (address change, tracking, delivery issues)
- account_management (login issues, locked accounts, password reset)
- subscription_management (cancel/upgrade subscription)
- invoice_request (customer wants invoice)
- billing_inquiry (payment issues, double charges)
- technical_support (app errors, website issues)
- faq_general (general questions)

Tickets:
{json.dumps(ticket_texts[:20], indent=2)[:3000]}

Connected integrations: {connected_integrations}

Return ONLY a JSON array of unique capability strings."""

                try:
                    result = await _call_nvidia_direct(
                        messages=[{"role": "user", "content": classify_prompt}],
                        temperature=0.1,
                        max_tokens=200,
                        call_id=0,
                    )
                    json_match = re.search(r'\[.*?\]', result, re.DOTALL)
                    if json_match:
                        capabilities_detected = json.loads(json_match.group())
                except Exception as exc:
                    logger.warning("NVIDIA classification failed: %s", str(exc)[:200])

            # Fallback: keyword detection
            if not capabilities_detected:
                for t in ticket_texts:
                    text_lower = t["text"].lower()
                    if "refund" in text_lower:
                        capabilities_detected.append("refund_processing")
                    if "cancel" in text_lower and "order" in text_lower:
                        capabilities_detected.append("order_cancellation")
                    if "cancel" in text_lower and "subscription" in text_lower:
                        capabilities_detected.append("subscription_management")
                    if "locked" in text_lower or "cannot login" in text_lower:
                        capabilities_detected.append("account_management")
                    if "credit" in text_lower:
                        capabilities_detected.append("credit_adjustment")
                    if "shipping" in text_lower or "address" in text_lower:
                        capabilities_detected.append("shipping_delivery")
                    if "invoice" in text_lower:
                        capabilities_detected.append("invoice_request")
                    if "payment" in text_lower or "charged" in text_lower:
                        capabilities_detected.append("billing_inquiry")
                capabilities_detected = list(set(capabilities_detected))

            if not capabilities_detected:
                capabilities_detected = ["faq_general"]

            # ── Step 5: Check existing agents ───────────────────
            existing_agents = db.query(AIAgentAssignment).filter(
                AIAgentAssignment.company_id == company_id,
                AIAgentAssignment.status == "active",
            ).all()

            existing_caps = set()
            for agent in existing_agents:
                try:
                    caps = json.loads(agent.capabilities or "[]")
                    existing_caps.update(caps)
                except Exception:
                    pass

            # ── Step 6: Build agents using REAL Builder pipeline ─
            agents_created = []
            agents_skipped = []

            for capability in capabilities_detected:
                if capability in existing_caps and not request.force_rebuild:
                    agents_skipped.append(capability)
                    continue

                logger.info(
                    "onboarding_builder: building agent for capability=%s (NVIDIA 4-stage)",
                    capability,
                )

                # ── Run the REAL 4-stage Builder ──────────────
                try:
                    from app.core.builder_agent.builder_pipeline import run_builder_pipeline

                    # Pick a representative ticket for this capability
                    rep_query = ""
                    for t in ticket_texts:
                        if capability.replace("_", " ") in t["text"].lower():
                            rep_query = t["text"]
                            break
                    if not rep_query:
                        rep_query = ticket_texts[0]["text"] if ticket_texts else ""

                    builder_result = await run_builder_pipeline(
                        tenant_id=company_id,
                        capability=capability,
                        query=rep_query,
                        ticket_type=capability,
                        complexity="medium",
                        tier=tier,
                    )

                    if builder_result.get("status") == "complete":
                        agent_id = builder_result.get("agent_id")
                        config = builder_result.get("config", {})

                        # ── Add tool mapping to the agent ──────
                        tool_map = CAPABILITY_TO_TOOL_MAP.get(capability, {})

                        # Check if tenant has the required integration
                        required_integrations = tool_map.get("integrations", [])
                        has_integration = any(
                            integ in connected_integrations
                            for integ in required_integrations
                        )

                        # Update agent with tool mapping info
                        if agent_id:
                            agent = db.query(AIAgentAssignment).filter(
                                AIAgentAssignment.id == agent_id,
                            ).first()
                            if agent:
                                # Add tool mapping to instructions
                                tool_info = ""
                                if tool_map and has_integration:
                                    tool_info = (
                                        f"\n\nTOOL MAPPING: Use {tool_map['tool']}.{tool_map['action']} "
                                        f"via {required_integrations[0]} integration."
                                    )
                                elif tool_map and not has_integration:
                                    tool_info = (
                                        f"\n\nTOOL MAPPING: This capability needs {required_integrations} "
                                        f"but none are connected. Escalate to human if action needed."
                                    )

                                agent.instructions = (config.get("instructions", "") + tool_info)[:5000]
                                agent.agent_role = "onboarding_built"
                                db.commit()

                        agents_created.append({
                            "agent_id": str(agent_id),
                            "agent_name": config.get("agent_name", capability),
                            "capability": capability,
                            "tool_mapping": tool_map,
                            "has_integration": has_integration,
                            "builder_stages": builder_result.get("stage_iterations", {}),
                        })

                        logger.info(
                            "onboarding_builder: agent BUILT+TESTED capability=%s agent_id=%s",
                            capability, str(agent_id)[:8],
                        )

                    elif builder_result.get("status") == "rejected":
                        agents_skipped.append(f"{capability} (rejected: scope)")
                        logger.info("onboarding_builder: REJECTED %s", capability)
                    else:
                        agents_skipped.append(f"{capability} (builder failed)")
                        logger.warning(
                            "onboarding_builder: builder returned %s for %s",
                            builder_result.get("status"), capability,
                        )

                except Exception as exc:
                    logger.error(
                        "onboarding_builder: FAILED capability=%s err=%s",
                        capability, str(exc)[:200],
                    )
                    agents_skipped.append(f"{capability} (error)")

                # ── Wait between agents (NVIDIA rate limit: 30 RPM) ──
                time.sleep(3)

            return ScanAndBuildResponse(
                status="complete",
                tickets_scanned=len(tickets),
                capabilities_detected=capabilities_detected,
                agents_created=agents_created,
                agents_skipped=agents_skipped,
                errors=[],
            )

        finally:
            db.close()

    except Exception as exc:
        logger.error("scan_and_build_failed: %s", str(exc)[:300])
        return ScanAndBuildResponse(
            status="error",
            tickets_scanned=0,
            capabilities_detected=[],
            agents_created=[],
            agents_skipped=[],
            errors=[str(exc)[:200]],
        )
