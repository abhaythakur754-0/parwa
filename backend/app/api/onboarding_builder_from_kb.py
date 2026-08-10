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

    # ── Step 2: Ask NVIDIA LLM what agents are needed ────────────
    # This is the KEY DIFFERENCE: we use KB + integrations, not tickets.
    detected_capabilities = await _detect_capabilities_from_onboarding(
        kb_context=kb_context,
        integrations=integrations,
    )

    logger.info(
        "onboarding_build_detected company=%s capabilities=%s",
        company_id, detected_capabilities,
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
    from app.core.builder_agent.builder_pipeline import run_builder_pipeline
    from app.core.builder_agent.builder_state import BuilderState

    # Initial state for the Builder pipeline
    state: BuilderState = {
        "tenant_id": company_id,
        "capability": capability,
        "query": kb_context[:1000] if kb_context else f"Create {capability} agent based on connected integrations",
        "force_rebuild": force_rebuild,
        # Pass KB context so DESIGN stage can include company-specific rules
        "kb_context": kb_context,
        # Pass integrations so Superglue knows what APIs are available
        "tenant_integrations": integrations,
    }

    # Run the full 4-stage pipeline (EXPLORE → DESIGN → VERIFY → REFINE)
    # The _finalize_agent step will also request Superglue tool generation
    # (tenant-namespaced automatically via namespaced_tool_id())
    await run_builder_pipeline(state)
