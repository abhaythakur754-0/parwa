"""
Onboarding Builder Agent — creates AI agents during onboarding using KB + integrations.

This is the KEY DIFFERENCE from the regular Builder Agent:
  - Regular Builder: scans recent TICKETS to detect patterns
  - Onboarding Builder: reads KB DOCS + connected INTEGRATIONS to detect what agents to create

This means a new tenant can complete onboarding and have working agents IMMEDIATELY,
without waiting for tickets to accumulate.

Flow:
  1. Admin finishes Step 2 (Connect Integrations) + Step 3 (Upload KB)
  2. PARWA calls POST /api/builder-agent/build-from-onboarding
  3. Backend reads tenant's KB documents (refund policy, SOPs, training manual)
  4. Backend reads tenant's connected integrations (Shopify, Stripe, etc.)
  5. NVIDIA LLM analyzes KB + integrations:
       "I see refund policy → need Refund Specialist agent"
       "I see Shopify connected → need Order Lookup agent"
       "I see scam SOP → need Scam Detection agent"
  6. For each agent needed:
       a. Generate agent config (instructions include company-specific rules from KB)
       b. Request Superglue to generate multi-step tool (tenant-namespaced)
       c. Save to DB
  7. Return list of created agents

Per-tenant isolation: every Superglue tool is prefixed with tenant_{company_id}__
so Tenant A's tools are completely separate from Tenant B's tools.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user

logger = logging.getLogger("parwa.api.onboarding_builder")

router = APIRouter(prefix="/api/builder-agent", tags=["Builder Agent"])


class BuildFromOnboardingRequest(BaseModel):
    """Request to start agent building from onboarding (KB + integrations)."""
    force_rebuild: bool = False  # if True, rebuild even if agents already exist


class BuildFromOnboardingResponse(BaseModel):
    status: str  # "building_started" | "already_built" | "error"
    message: str
    company_id: str
    estimated_seconds: int = 300  # ~5 minutes for full build


@router.post("/build-from-onboarding")
async def build_from_onboarding(
    request: BuildFromOnboardingRequest,
    current_user=Depends(get_current_user),
) -> Any:
    """Build AI agents from onboarding data (KB + integrations) — NOT from tickets.

    Returns immediately with "building_started" status. The actual building
    runs in a background thread (NVIDIA 4-stage pipeline + Superglue tool generation).

    This is the PREMIUM onboarding flow:
      - User uploads refund policy, SOPs, training manual
      - User connects Shopify + Stripe + Brevo
      - Click "Build my agents"
      - 5 minutes later → 5-10 specialized agents ready to solve tickets

    Per-tenant isolation: all Superglue tools are prefixed with tenant_{company_id}__
    so each tenant's tools are completely isolated.
    """
    company_id = str(current_user.company_id)
    force_rebuild = request.force_rebuild

    # ── Check if agents already exist ──────────────────────────────
    if not force_rebuild:
        try:
            from database.base import SessionLocal
            from database.models.variant_engine import AIAgentAssignment
            db = SessionLocal()
            try:
                existing_count = db.query(AIAgentAssignment).filter(
                    AIAgentAssignment.company_id == company_id,
                    AIAgentAssignment.status == "active",
                ).count()
                if existing_count >= 3:
                    return BuildFromOnboardingResponse(
                        status="already_built",
                        message=f"You already have {existing_count} active agents. Use force_rebuild=true to rebuild.",
                        company_id=company_id,
                        estimated_seconds=0,
                    )
            finally:
                db.close()
        except Exception as exc:
            logger.warning("check_existing_agents_failed: %s", str(exc)[:200])

    # ── Return immediately — building runs in background ───────────
    def _build_in_background():
        """Run the full onboarding builder in a background thread."""
        try:
            import asyncio
            asyncio.run(_do_build_from_onboarding(company_id, force_rebuild))
        except Exception as exc:
            logger.error(
                "background_onboarding_build_failed company=%s err=%s",
                company_id, str(exc)[:300],
            )

    t = threading.Thread(
        target=_build_in_background,
        daemon=True,
        name=f"onboarding-builder-{company_id[:8]}",
    )
    t.start()

    return BuildFromOnboardingResponse(
        status="building_started",
        message="Agent building started. Reading your KB + integrations to design specialized agents. Check /api/ai/agents in 3-5 minutes.",
        company_id=company_id,
        estimated_seconds=300,
    )


async def _do_build_from_onboarding(company_id: str, force_rebuild: bool) -> None:
    """The actual build logic — runs in background.

    1. Read KB documents for this tenant
    2. Read connected integrations
    3. Ask NVIDIA LLM: "What agents does this tenant need based on KB + integrations?"
    4. For each agent:
       a. Run full Builder pipeline (EXPLORE → DESIGN → VERIFY → REFINE)
       b. Request Superglue to generate multi-step tool (tenant-namespaced)
       c. Save to DB
    """
    logger.info("onboarding_build_start company=%s force=%s", company_id, force_rebuild)

    # ── Step 1: Gather onboarding context ────────────────────────
    kb_context = await _gather_kb_context(company_id)
    integrations = await _gather_integrations(company_id)

    if not kb_context and not integrations:
        logger.warning("onboarding_build_skip: no KB and no integrations company=%s", company_id)
        return

    # ── Step 2: Get capabilities from CRM analyser output ──────
    # The CRM analyser already analyzed the tenant's tickets and
    # recommended what agents/tools/integrations are needed.
    # We use THAT output directly — no need to re-detect with local LLM.
    #
    # If CRM analysis hasn't run yet, fall back to local detection.
    detected_capabilities = []

    # Try to get CRM analyser results from the status endpoint
    try:
        from app.core.crm_analyser_client import get_crm_analyser_url
        import httpx as _httpx

        crm_url = get_crm_analyser_url()
        if crm_url:
            # Check if there are any completed CRM analyses
            async with _httpx.AsyncClient(timeout=10.0) as client:
                # Get the latest completed analysis
                r = await client.get(
                    f"{crm_url}/api/crm-analyser/analyze",
                    params={"limit": 1, "status": "completed"},
                    timeout=10.0,
                )
                if r.status_code == 200:
                    data = r.json()
                    # Check if it's a list or single result
                    results = data if isinstance(data, list) else data.get("items", [data])
                    if results:
                        latest = results[0]
                        work_order = latest.get("work_order", {}) if isinstance(latest, dict) else {}
                        crm_agents = work_order.get("agents", [])
                        # Convert CRM agent names to capabilities
                        # CRM returns: "refund-specialist" → "refund_processing"
                        name_to_cap = {
                            "refund": "refund_processing",
                            "billing": "billing_inquiry",
                            "auth": "account_management",
                            "shipping": "shipping_delivery",
                            "technical": "technical_support",
                            "faq": "faq_general",
                            "complaint": "complaint_handling",
                            "fraud": "fraud_security",
                            "subscription": "subscription_management",
                            "order": "order_management",
                            "product": "product_information",
                            "appointment": "appointment_booking",
                            "invoice": "invoice_request",
                        }
                        for agent_name in crm_agents:
                            agent_lower = agent_name.lower()
                            for key, cap in name_to_cap.items():
                                if key in agent_lower and cap not in detected_capabilities:
                                    detected_capabilities.append(cap)
                                    break
    except Exception as exc:
        logger.warning("crm_result_fetch_failed: %s — using local detection", str(exc)[:200])

    # Fallback: if CRM didn't return capabilities, use local detection
    if not detected_capabilities:
        detected_capabilities = await _detect_capabilities_from_onboarding(
            kb_context=kb_context,
            integrations=integrations,
        )

    logger.info(
        "onboarding_build_detected company=%s capabilities=%s source=%s",
        company_id, detected_capabilities,
        "crm" if detected_capabilities else "local_fallback",
    )

    # ── Step 3: For each capability, run full Builder pipeline ───
    for capability in detected_capabilities:
        try:
            await _build_single_agent(
                company_id=company_id,
                capability=capability,
                kb_context=kb_context,
                integrations=integrations,
                force_rebuild=force_rebuild,
            )
        except Exception as exc:
            logger.error(
                "onboarding_build_agent_failed company=%s capability=%s err=%s",
                company_id, capability, str(exc)[:200],
            )

    logger.info("onboarding_build_complete company=%s", company_id)


async def _gather_kb_context(company_id: str) -> str:
    """Read all KB documents for this tenant and combine into a single context string.

    This is what the Builder LLM reads to understand the company's:
      - Refund policy
      - SOPs (scam checks, escalation rules)
      - Training manual
      - Any other uploaded docs
    """
    try:
        from database.base import SessionLocal
        from database.models.core import KnowledgeDocument, DocumentChunk
        db = SessionLocal()
        try:
            # Get all KB docs for this tenant
            docs = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.company_id == company_id,
            ).all()

            if not docs:
                return ""

            # Get chunks for each doc (chunks contain the actual text)
            chunks_text = []
            for doc in docs:
                chunks = db.query(DocumentChunk).filter(
                    DocumentChunk.document_id == doc.id,
                ).limit(20).all()  # cap at 20 chunks per doc to fit in LLM context
                for chunk in chunks:
                    chunks_text.append(f"[{doc.title}]\n{chunk.content}")

            # Combine into single context (cap at 8000 chars to fit LLM)
            full_context = "\n\n---\n\n".join(chunks_text)
            return full_context[:8000]
        finally:
            db.close()
    except Exception as exc:
        logger.warning("gather_kb_context_failed: %s", str(exc)[:200])
        return ""


async def _gather_integrations(company_id: str) -> List[Dict[str, Any]]:
    """Get all integrations the tenant has connected."""
    try:
        from database.base import SessionLocal
        from database.models.core import Integration
        db = SessionLocal()
        try:
            rows = db.query(Integration).filter(
                Integration.company_id == company_id,
            ).all()
            return [
                {
                    "type": getattr(i, "integration_type", getattr(i, "provider", "unknown")),
                    "status": getattr(i, "status", "unknown"),
                }
                for i in rows
            ]
        finally:
            db.close()
    except Exception as exc:
        logger.warning("gather_integrations_failed: %s", str(exc)[:200])
        return []


async def _detect_capabilities_from_onboarding(
    kb_context: str,
    integrations: List[Dict[str, Any]],
) -> List[str]:
    """Ask NVIDIA LLM what agents this tenant needs based on KB + integrations.

    Returns a list of capability keys (refund_processing, billing_inquiry, etc.)
    """
    from app.core.parwa_pipeline.llm_client import llm_call

    # Format the integration list for the prompt
    integ_text = ", ".join([i.get("type", "?") for i in integrations]) or "none connected"

    prompt = f"""You are analyzing a PARWA tenant's onboarding data to determine what AI agents they need.

TENANT'S KNOWLEDGE BASE (their refund policy, SOPs, training manuals, etc.):
{kb_context[:5000] if kb_context else "(no KB documents uploaded yet)"}

TENANT'S CONNECTED INTEGRATIONS:
{integ_text}

Based on the above, what AI agents should this tenant have?

Available capabilities (pick from this list):
  - refund_processing       (handles refunds, chargebacks, money-back)
  - billing_inquiry         (handles billing questions, invoices, payment failures)
  - subscription_management (handles cancellations, upgrades, downgrades)
  - order_management        (handles order status, tracking, returns)
  - account_management      (handles login issues, password resets, account changes)
  - technical_support       (handles tech issues, bugs, how-to)
  - complaint_handling      (handles complaints, escalations)
  - fraud_security          (handles scam reports, suspicious activity)
  - shipping_delivery       (handles shipping, tracking, delivery issues)
  - product_information    (handles product questions, pricing, features)
  - faq_general            (handles general questions)
  - appointment_booking    (handles scheduling, appointments) — only if calendar integration

Respond with ONLY a JSON array of capability keys, max 6 agents:
["refund_processing", "billing_inquiry", "faq_general"]

Pick only capabilities that make sense based on:
1. What the KB mentions (refund policy → refund_processing, etc.)
2. What integrations are connected (Stripe → refund_processing, Shopify → order_management)
3. Don't pick more than 6 — quality over quantity."""

    try:
        response = await llm_call(prompt, max_tokens=300, temperature=0.2)

        # Parse JSON array from response
        import re
        match = re.search(r'\[.*\]', response or "", re.DOTALL)
        if match:
            capabilities = json.loads(match.group())
            # Validate against the allowed list
            allowed = {
                "refund_processing", "billing_inquiry", "subscription_management",
                "order_management", "account_management", "technical_support",
                "complaint_handling", "fraud_security", "shipping_delivery",
                "product_information", "faq_general", "appointment_booking",
            }
            valid = [c for c in capabilities if c in allowed]
            # Always include faq_general as a fallback
            if "faq_general" not in valid:
                valid.append("faq_general")
            return valid[:6]  # cap at 6

        # Fallback: default capabilities
        return ["faq_general", "billing_inquiry"]
    except Exception as exc:
        logger.warning("detect_capabilities_failed: %s", str(exc)[:200])
        return ["faq_general"]


async def _build_single_agent(
    company_id: str,
    capability: str,
    kb_context: str,
    integrations: List[Dict[str, Any]],
    force_rebuild: bool,
) -> None:
    """Build a single agent for a capability using the full Builder pipeline.

    Includes the KB context so the agent's instructions reflect the company's
    specific rules (not generic).
    """
    # ── REMOTE BUILDER (offloads to 2GB service, saves Render RAM) ──
    # The local builder_pipeline.py is NOT deleted — kept as fallback.
    # Set BUILDER_FALLBACK_LOCAL=true to use local on remote failure.
    from app.core.remote_builder_client import build_agent_with_fallback
    import asyncio

    # Extract integration names for the remote builder
    integration_names = [i.get("name", "") for i in integrations if i.get("name")]

    # Call the remote builder service (30-60s, runs on separate machine)
    result = await build_agent_with_fallback(
        tenant_id=company_id,
        kb_context=kb_context or f"Create {capability} agent",
        integrations=integration_names,
        capability=capability,
    )

    # Normalize: remote returns 'agent_config', local returns 'config'
    if "agent_config" in result and "config" not in result:
        result["config"] = result["agent_config"]

    # ── Save agent to DB (if not already exists) ──
    config = result.get("config", {})
    from database.base import SessionLocal
    from database.models.variant_engine import AIAgentAssignment
    _db = SessionLocal()
    try:
        # Check if agent already exists for this capability (skip if exists)
        existing = _db.query(AIAgentAssignment).filter(
            AIAgentAssignment.company_id == company_id,
            AIAgentAssignment.status == "active",
        ).all()
        already_exists = False
        for a in existing:
            try:
                caps = json.loads(a.capabilities or "[]")
                if capability in caps:
                    already_exists = True
                    break
            except Exception:
                pass

        if not already_exists:
            # Create new agent
            import uuid as _uuid
            agent = AIAgentAssignment(
                id=str(_uuid.uuid4()),
                company_id=company_id,
                agent_name=config.get("agent_name", capability.replace("_", " ").title()),
                agent_role="onboarding_built",
                capabilities=json.dumps(config.get("capabilities", [capability])),
                instructions=config.get("instructions", "")[:5000],
                restrictions=config.get("restrictions", ""),
                status="active",
                superglue_tool_status="none",
            )
            _db.add(agent)
            _db.commit()
            logger.info("onboarding_build: agent saved capability=%s", capability)

            # ── Create Superglue tool for this agent (if not already exists) ──
            # Check if agent already has a tool linked
            if agent.superglue_tool_id and agent.superglue_tool_status == "active":
                logger.info("onboarding_build: tool already linked capability=%s — skipping", capability)
            else:
              try:
                from app.core.superglue_tool_generator import generate_tool_for_agent
                tool_result = await generate_tool_for_agent(
                    agent_name=config.get("agent_name", capability),
                    agent_instructions=config.get("instructions", ""),
                    agent_capabilities=capability,
                    sample_ticket=kb_context[:500] if kb_context else "",
                    tenant_integrations={i.get("type", ""): i.get("config", {}) for i in integrations},
                )
                if tool_result.get("success") and tool_result.get("tool_id"):
                    agent.superglue_tool_id = tool_result["tool_id"]
                    agent.superglue_tool_status = "active"
                    _db.commit()
                    logger.info(
                        "onboarding_build: superglue tool created capability=%s tool_id=%s",
                        capability, tool_result["tool_id"][:30],
                    )
                else:
                    agent.superglue_tool_status = "failed"
                    _db.commit()
                    logger.warning(
                        "onboarding_build: superglue tool failed capability=%s err=%s",
                        capability, tool_result.get("error", "unknown")[:100],
                    )
              except Exception as sg_exc:
                logger.warning("onboarding_build: superglue failed capability=%s err=%s",
                               capability, str(sg_exc)[:200])
                agent.superglue_tool_status = "failed"
                _db.commit()
        else:
            logger.info("onboarding_build: agent already exists capability=%s — skipping", capability)
    finally:
        _db.close()

    # --- LOCAL BUILDER (deleted — using remote builder only) ---
