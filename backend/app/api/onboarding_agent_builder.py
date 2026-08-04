"""
Onboarding Agent Builder — Scans tickets + builds agents using NVIDIA GLM-5.

When a user connects their CRM, this scans their recent tickets to understand
what capabilities they need, then builds specialized agents using NVIDIA's
GLM-5.2 model (separate from Groq which handles ticket processing).

Flow:
  1. User connects CRM (Stripe, Shopify, etc.)
  2. POST /api/builder-agent/scan-and-build
  3. Scans recent tickets (last 30 days)
  4. Classifies what capabilities are needed
  5. Builds agents one by one using NVIDIA GLM-5
  6. Stores all agents in DB (persistent)
  7. Node 1 just looks up agents (instant, no building during tickets)
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.jwt_auth import get_current_user

logger = logging.getLogger("parwa.api.builder_agent")

router = APIRouter(prefix="/api/builder-agent", tags=["Builder Agent"])


class ScanAndBuildRequest(BaseModel):
    """Request to scan tickets and build agents."""
    max_tickets_to_scan: int = 50
    force_rebuild: bool = False


class ScanAndBuildResponse(BaseModel):
    """Response from scan-and-build."""
    status: str
    tickets_scanned: int
    capabilities_detected: List[str]
    agents_created: List[Dict[str, Any]]
    agents_skipped: List[str]
    errors: List[str]


@router.post("/scan-and-build")
async def scan_and_build(
    request: ScanAndBuildRequest,
    current_user=Depends(get_current_user),
) -> Any:
    """Scan recent tickets + build agents using NVIDIA GLM-5.

    This runs AFTER the user connects their CRM during onboarding.
    It scans recent tickets to understand what the tenant needs,
    then builds specialized agents and stores them in the DB.

    NVIDIA GLM-5 is used for the heavy reasoning (agent design).
    Groq is reserved for ticket processing (fast responses).
    """
    try:
        from database.base import SessionLocal
        from database.models.tickets import Ticket, TicketMessage
        from database.models.variant_engine import AIAgentAssignment
        from app.core.parwa_pipeline.llm_client import _call_nvidia_direct

        db = SessionLocal()
        company_id = str(current_user.company_id)

        try:
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

            # ── Step 2: Load ticket messages for classification ──
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
                    ticket_texts.append({"id": str(t.id), "subject": t.subject or "", "text": text[:500]})

            # ── Step 3: Ask NVIDIA GLM-5 to classify capabilities ──
            capabilities_detected = []
            if ticket_texts and os.environ.get("NVIDIA_API_KEY"):
                classify_prompt = f"""Analyze these {len(ticket_texts)} customer support tickets and identify 
what CAPABILITIES are needed to handle them. Return ONLY a JSON list of capability names.

Common capabilities: refund_processing, billing_inquiry, technical_support, 
faq_general, complaint_handling, account_management, fraud_security, 
shipping_delivery, product_information, order_cancellation, credit_adjustment,
address_change, subscription_management, invoice_request

Tickets:
{json.dumps(ticket_texts[:20], indent=2)[:3000]}

Return ONLY a JSON array of unique capability strings, nothing else."""

                try:
                    result = await _call_nvidia_direct(
                        messages=[{"role": "user", "content": classify_prompt}],
                        temperature=0.1,
                        max_tokens=200,
                        call_id=0,
                    )
                    # Parse the JSON list from the response
                    import re
                    json_match = re.search(r'\[.*?\]', result, re.DOTALL)
                    if json_match:
                        capabilities_detected = json.loads(json_match.group())
                except Exception as exc:
                    logger.warning("NVIDIA classification failed: %s", str(exc)[:200])
                    # Fallback: use simple keyword detection
                    for t in ticket_texts:
                        text_lower = t["text"].lower()
                        if "refund" in text_lower:
                            capabilities_detected.append("refund_processing")
                        if "cancel" in text_lower:
                            capabilities_detected.append("order_cancellation")
                        if "locked" in text_lower or "login" in text_lower:
                            capabilities_detected.append("account_management")
                        if "credit" in text_lower:
                            capabilities_detected.append("credit_adjustment")
                        if "shipping" in text_lower or "address" in text_lower:
                            capabilities_detected.append("shipping_delivery")
                        if "invoice" in text_lower:
                            capabilities_detected.append("invoice_request")
                    capabilities_detected = list(set(capabilities_detected))

            if not capabilities_detected:
                capabilities_detected = ["faq_general"]  # Default

            # ── Step 4: Check existing agents ────────────────────
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

            # ── Step 5: Build agents for NEW capabilities ─────────
            agents_created = []
            agents_skipped = []

            for capability in capabilities_detected:
                if capability in existing_caps and not request.force_rebuild:
                    agents_skipped.append(capability)
                    continue

                # ── Build agent using NVIDIA GLM-5 ──
                agent_name = capability.replace("_", " ").title()

                # Use NVIDIA for agent design (heavy reasoning)
                if os.environ.get("NVIDIA_API_KEY"):
                    design_prompt = f"""Design a customer support agent for the capability: {capability}

This agent will handle customer tickets related to {capability}.
Create:
1. A clear instruction for the agent (how to handle these tickets)
2. Restrictions (what the agent should NOT do)
3. What tools/integrations it might need

Return JSON:
{{
  "instructions": "...",
  "restrictions": "...",
  "required_tools": ["stripe", "shopify", ...]
}}"""

                    try:
                        design_result = await _call_nvidia_direct(
                            messages=[{"role": "user", "content": design_prompt}],
                            temperature=0.3,
                            max_tokens=500,
                            call_id=0,
                        )
                        import re
                        json_match = re.search(r'\{.*\}', design_result, re.DOTALL)
                        if json_match:
                            design = json.loads(json_match.group())
                            instructions = design.get("instructions", f"Handle {capability} tickets using KB.")
                            restrictions = design.get("restrictions", "If unsure, escalate to human.")
                        else:
                            instructions = f"Handle {agent_name} tickets using the knowledge base docs. Be professional and concise."
                            restrictions = "If unsure or lacking verified information, escalate to human."
                    except Exception as exc:
                        logger.warning("NVIDIA agent design failed for %s: %s", capability, str(exc)[:200])
                        instructions = f"Handle {agent_name} tickets using the knowledge base docs."
                        restrictions = "If unsure, escalate to human."
                else:
                    instructions = f"Handle {agent_name} tickets using the knowledge base docs."
                    restrictions = "If unsure, escalate to human."

                # ── Store agent in DB ──
                agent = AIAgentAssignment(
                    id=str(uuid.uuid4()),
                    company_id=company_id,
                    agent_name=f"{agent_name} Agent",
                    agent_role="onboarding_created",
                    feature_ids="[]",
                    task_ids="[]",
                    domain="customer_care",
                    capabilities=json.dumps([capability]),
                    instructions=instructions[:5000],
                    restrictions=restrictions[:5000],
                    status="active",
                )
                db.add(agent)
                db.commit()

                agents_created.append({
                    "agent_id": str(agent.id),
                    "agent_name": agent.agent_name,
                    "capability": capability,
                })

                logger.info(
                    "onboarding_agent_created agent=%s capability=%s company=%s",
                    agent.agent_name, capability, company_id,
                )

                # ── Wait between NVIDIA calls (rate limit safety) ──
                time.sleep(2)

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
