"""
Onboarding Agent Builder — PRODUCTION version.

Uses the REAL 4-stage Builder pipeline (EXPLORE → DESIGN → VERIFY → REFINE)
with Groq llama-3.1-8b-instant for reasoning.

User validation (2026-08-12): "llama-3.1-8b gives best results for ALL
pipeline tasks." Was NVIDIA GLM-5.2 but it took ~58s/call → onboarding
took 4+ min per agent. Now uses Groq: ~1s/call, 60x faster.

Flow:
  1. User connects CRM → POST /api/builder-agent/scan-and-build
  2. Scans recent tickets (last 30 days)
  3. Groq llama-3.1-8b classifies what capabilities are needed
  4. For each capability → runs full Builder pipeline (4 stages, Groq)
  5. Each agent gets tool mapping (checks connected integrations)
  6. Tests each agent against historical tickets
  7. Only stores TESTED agents in DB
  8. Node 1 looks up tested agents (instant, no building)

Builder uses Groq llama-3.1-8b-instant for ALL stages (user-validated).
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

from app.api.deps import get_current_user

logger = logging.getLogger("parwa.api.onboarding_builder")

router = APIRouter(prefix="/api/builder-agent", tags=["Builder Agent"])


class ScanAndBuildRequest(BaseModel):
    max_tickets_to_scan: int = 50  # DEPRECATED — now scans ALL last month's tickets (no limit)
    force_rebuild: bool = False


class ScanAndBuildResponse(BaseModel):
    status: str
    tickets_scanned: int
    capabilities_detected: List[str]
    agents_created: List[Dict[str, Any]]
    agents_skipped: List[str]
    errors: List[str]


# ── Tool Mapping is done DYNAMICALLY by Groq llama-3.1-8b ───────
# We do NOT hardcode capability→tool mappings (that's what competitors do).
# Instead, we tell llama-3.1-8b:
#   "Here are the tenant's connected integrations + available tools.
#    For this capability, which tool + action should the agent use?"
#
# llama-3.1-8b has the reasoning capability to map any capability to any
# integration dynamically — no hardcoded rules needed.


@router.post("/scan-and-build")
async def scan_and_build(
    request: ScanAndBuildRequest,
    current_user=Depends(get_current_user),
) -> Any:
    """Scan tickets + build agents AS A BACKGROUND TASK.

    Returns immediately with "building_started" status.
    The actual building runs in a background thread (NVIDIA 4-stage pipeline).
    Check /api/ai/agents to see agents as they're created.

    This prevents browser timeouts — the Builder takes 5-10 minutes.
    """
    import threading

    company_id = str(current_user.company_id)
    max_scan = request.max_tickets_to_scan
    force_rebuild = request.force_rebuild

    # ── Return immediately — building runs in background ──
    def _build_in_background():
        """Run the full Builder pipeline in a background thread."""
        try:
            import asyncio
            asyncio.run(_do_build(company_id, max_scan, force_rebuild))
        except Exception as exc:
            logger.error("background_build_failed company=%s err=%s", company_id, str(exc)[:300])

    # Start background thread
    t = threading.Thread(target=_build_in_background, daemon=True, name=f"builder-{company_id[:8]}")
    t.start()

    return {
        "status": "building_started",
        "message": "Agent building started in background. Check /api/ai/agents in 2-5 minutes.",
        "company_id": company_id,
    }


@router.post("/scan-and-build-sync")
async def scan_and_build_sync(
    request: ScanAndBuildRequest,
    current_user=Depends(get_current_user),
) -> Any:
    """Synchronous version of scan-and-build — runs _do_build directly.

    Same as scan-and-build but runs in the request thread (not background).
    Use this for debugging — you'll see the actual response/errors instead
    of waiting for a background task that might fail silently.
    """
    company_id = str(current_user.company_id)
    result = await _do_build(company_id, request.max_tickets_to_scan, request.force_rebuild)
    return result


async def _do_build(company_id: str, max_scan: int, force_rebuild: bool):
    """Actual building logic — runs in background thread."""
    try:
        from database.base import SessionLocal
        from database.models.tickets import Ticket, TicketMessage
        from database.models.variant_engine import AIAgentAssignment
        from database.models.core import Company

        db = SessionLocal()

        try:
            # ── Get tenant tier ──────────────────────────────────
            company = db.query(Company).filter(Company.id == company_id).first()
            tier = getattr(company, "plan", "parwa") if company else "parwa"

            # ── Step 1: Scan ALL tickets from last 30 days ─────
            # No limit — scan every ticket from the last month.
            # User request (2026-08-12): "just last month there is no limit
            # on number of ticket just last month tickets"
            from datetime import datetime, timezone, timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)

            tickets = db.query(Ticket).filter(
                Ticket.company_id == company_id,
                Ticket.created_at >= cutoff,
            ).all()  # NO LIMIT — scan all last month's tickets

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

            # ── Step 4: Groq classifies capabilities (ALL tickets) ──
            # Process tickets in chunks of 50 to handle large volumes.
            # Each chunk = 1 LLM call. Aggregates all capabilities.
            capabilities_detected = []

            if os.environ.get("GROQ_API_KEY"):
                from app.core.parwa_pipeline.llm_client import _call_groq_direct
                import re

                # Chunk tickets (50 per chunk) to fit in LLM context window
                CHUNK_SIZE = 50
                all_chunks = [ticket_texts[i:i+CHUNK_SIZE] for i in range(0, len(ticket_texts), CHUNK_SIZE)]
                logger.info(
                    "onboarding_builder: classifying %d tickets in %d chunks (chunk_size=%d)",
                    len(ticket_texts), len(all_chunks), CHUNK_SIZE,
                )

                for chunk_idx, chunk in enumerate(all_chunks):
                    classify_prompt = f"""Analyze these {len(chunk)} customer support tickets (batch {chunk_idx+1} of {len(all_chunks)}).
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
{json.dumps(chunk, indent=2)[:4000]}

Connected integrations: {connected_integrations}

Return ONLY a JSON array of unique capability strings."""

                    try:
                        result = await _call_groq_direct(
                            messages=[{"role": "user", "content": classify_prompt}],
                            temperature=0.1,
                            max_tokens=200,
                            call_id=0,
                        )
                        json_match = re.search(r'\[.*?\]', result, re.DOTALL)
                        if json_match:
                            chunk_caps = json.loads(json_match.group())
                            capabilities_detected.extend(chunk_caps)
                    except Exception as exc:
                        logger.warning("chunk %d classification failed: %s", chunk_idx, str(exc)[:200])

                # Deduplicate
                capabilities_detected = list(set(capabilities_detected))

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
                if capability in existing_caps and not force_rebuild:
                    agents_skipped.append(capability)
                    continue

                logger.info(
                    "onboarding_builder: building agent for capability=%s (Groq 4-stage)",
                    capability,
                )

                # ── Run the Builder (REMOTE service — offloads to 2GB machine) ──
                # The local builder_pipeline.py is NOT deleted — kept as fallback.
                # Set BUILDER_FALLBACK_LOCAL=true to use local on remote failure.
                try:
                    from app.core.remote_builder_client import build_agent_with_fallback

                    # Build KB context from ticket texts for this capability
                    kb_context = ""
                    for t in ticket_texts:
                        if capability.replace("_", " ") in t["text"].lower():
                            kb_context = t["text"]
                            break
                    if not kb_context:
                        kb_context = ticket_texts[0]["text"] if ticket_texts else ""

                    builder_result = await build_agent_with_fallback(
                        tenant_id=company_id,
                        kb_context=kb_context,
                        integrations=connected_integrations,
                        capability=capability,
                    )

                    # Normalize: remote returns 'agent_config', local returns 'config'
                    # Make both available so downstream code works unchanged
                    if "agent_config" in builder_result and "config" not in builder_result:
                        builder_result["config"] = builder_result["agent_config"]

                    # --- LOCAL BUILDER (disabled — kept for fallback) ---
                    # To re-enable local building, set BUILDER_FALLBACK_LOCAL=true
                    # from app.core.builder_agent.builder_pipeline import run_builder_pipeline
                    # rep_query = kb_context[:500]
                    # builder_result = await run_builder_pipeline(
                    #     tenant_id=company_id, capability=capability,
                    #     query=rep_query, ticket_type=capability,
                    #     complexity="medium", tier=tier,
                    # )

                    if builder_result.get("status") == "complete":
                        agent_id = builder_result.get("agent_id")
                        config = builder_result.get("config", {})

                        # ── DYNAMIC tool mapping via NVIDIA GLM-5.2 ──
                        # Instead of hardcoded CAPABILITY_TO_TOOL_MAP,
                        # we ask GLM-5.2 to decide which tool to use
                        # based on what integrations the tenant has connected.
                        tool_mapping = {}
                        has_integration = False

                        if os.environ.get("GROQ_API_KEY") and connected_integrations:
                            from app.core.parwa_pipeline.llm_client import _call_groq_direct
                            import re

                            tool_prompt = f"""You are designing a customer support agent for: {capability}

The tenant has these integrations connected: {connected_integrations}

Available tools in the system:
- order_management: get_order, cancel_order, refund_order, update_shipping, get_order_status
- billing_system: get_invoice, apply_credit, process_payment, get_subscription_status, get_payment_history
- crm_integration: get_customer, update_customer
- ticket_system: get_ticket
- custom_connector: [tenant-defined custom API actions]

For the capability "{capability}", which tool + action should this agent use?
Consider what the tenant has connected. If no matching integration is connected,
say "no_tool" and the agent will recommend instead of execute.

Return JSON:
{{
  "tool": "tool_name",
  "action": "action_name",
  "integration": "integration_name",
  "can_execute": true_or_false,
  "reasoning": "why this tool"
}}"""

                            try:
                                tool_result = await _call_groq_direct(
                                    messages=[{"role": "user", "content": tool_prompt}],
                                    temperature=0.1,
                                    max_tokens=200,
                                    call_id=0,
                                )
                                json_match = re.search(r'\{.*\}', tool_result, re.DOTALL)
                                if json_match:
                                    tool_mapping = json.loads(json_match.group())
                                    has_integration = tool_mapping.get("can_execute", False)
                            except Exception as exc:
                                logger.warning("Groq tool mapping failed for %s: %s", capability, str(exc)[:200])

                        # Save agent to Render database (per tenant)
                        # The remote builder creates the agent config, but we need
                        # to store it in OUR database so Node 1 can find it.
                        if agent_id:
                            agent = db.query(AIAgentAssignment).filter(
                                AIAgentAssignment.id == agent_id,
                            ).first()

                            if not agent:
                                # Agent doesn't exist in Render DB — CREATE it
                                # (remote builder returned the config, we save locally)
                                tool_info = ""
                                if tool_mapping and has_integration:
                                    tool_info = (
                                        f"\n\nTOOL MAPPING (determined by AI): "
                                        f"Use {tool_mapping.get('tool', '?')}.{tool_mapping.get('action', '?')} "
                                        f"via {tool_mapping.get('integration', '?')} integration. "
                                        f"Reason: {tool_mapping.get('reasoning', '')}"
                                    )
                                elif tool_mapping and not has_integration:
                                    tool_info = (
                                        f"\n\nTOOL MAPPING (determined by AI): No matching integration "
                                        f"connected for this capability. Escalate to human if action needed. "
                                        f"Reason: {tool_mapping.get('reasoning', '')}"
                                    )

                                # Create new agent in Render's database
                                # Save Superglue tool linkage so Node 5 can
                                # execute tools (search DB, call APIs, etc.)
                                # when this agent handles a ticket.
                                agent = AIAgentAssignment(
                                    id=agent_id,
                                    company_id=company_id,
                                    agent_name=config.get("agent_name", capability),
                                    agent_role="onboarding_built",
                                    domain=config.get("domain", "auto"),
                                    capabilities=json.dumps(config.get("capabilities", [capability])),
                                    instructions=(config.get("instructions", "") + tool_info)[:5000],
                                    restrictions=config.get("restrictions", ""),
                                    status="active",
                                    # ── Superglue tool linkage ──
                                    # The external builder creates Superglue tools
                                    # (multi-step API chains for searching databases,
                                    # processing refunds, etc.) and returns the tool_id.
                                    # Node 5 calls execute_tool(superglue_tool_id)
                                    # when a ticket routes to this agent.
                                    superglue_tool_id=builder_result.get("superglue_tool_id"),
                                    superglue_tool_status=builder_result.get("superglue_tool_status", "none"),
                                    # ── Approval gates ──
                                    # Risky capabilities (refund, cancel sub) require
                                    # admin approval before tool executes.
                                    approval_required=capability in [
                                        "refund_processing",
                                        "subscription_management",
                                        "account_management",
                                        "order_cancellation",
                                    ],
                                    approval_threshold_cents=100000 if capability == "refund_processing" else 0,
                                )
                                db.add(agent)
                                db.commit()
                                logger.info(
                                    "onboarding_builder: agent SAVED to DB capability=%s agent_id=%s",
                                    capability, str(agent_id)[:8],
                                )
                            else:
                                # Agent exists — update with tool mapping
                                tool_info = ""
                                if tool_mapping and has_integration:
                                    tool_info = (
                                        f"\n\nTOOL MAPPING (determined by AI): "
                                        f"Use {tool_mapping.get('tool', '?')}.{tool_mapping.get('action', '?')} "
                                        f"via {tool_mapping.get('integration', '?')} integration. "
                                        f"Reason: {tool_mapping.get('reasoning', '')}"
                                    )
                                elif tool_mapping and not has_integration:
                                    tool_info = (
                                        f"\n\nTOOL MAPPING (determined by AI): No matching integration "
                                        f"connected for this capability. Escalate to human if action needed. "
                                        f"Reason: {tool_mapping.get('reasoning', '')}"
                                    )

                                agent.instructions = (config.get("instructions", "") + tool_info)[:5000]
                                agent.agent_role = "onboarding_built"
                                db.commit()

                        agents_created.append({
                            "agent_id": str(agent_id),
                            "agent_name": config.get("agent_name", capability),
                            "capability": capability,
                            "tool_mapping": tool_mapping,
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
