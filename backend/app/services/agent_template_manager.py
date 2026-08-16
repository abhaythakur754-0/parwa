"""
Agent Template Manager.

The "brain" that checks if a template exists → clones it (instant),
or builds a new one via external Builder (12 LLM calls).

User vision: "verify if it's in database, if yes don't make it again,
if not present then make it"

FLOW:
  1. CRM analysis recommends "refund_processing"
  2. get_or_create_template("refund_processing")
     → Check template table:
       → EXISTS → return template (0.1s, 0 LLM calls) ✅
       → NOT EXISTS → call external Builder (12 LLM calls, 30s)
         → save result as template
         → return new template
  3. clone_template_to_tenant(template, company_id)
     → Copy template fields to AIAgentAssignment
     → Add tenant's company_id (security)
     → Add tenant's superglue_tool_id (if any)
     → Add tenant's kb_context (if any)
     → 0.1s, 0 LLM calls

COST SAVINGS:
  100 tenants × 4 capabilities × 12 LLM calls = 4,800 calls (old)
  4 capabilities × 12 LLM calls = 48 calls (new — build once)
  100 tenants × 4 capabilities × 0 LLM calls = 0 (clone)
  TOTAL: 48 calls (was 4,800) = 99% savings
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

logger = logging.getLogger("parwa.template_manager")


async def get_or_create_template(
    db: Session,
    capability: str,
    kb_context: str = "",
    integrations: Optional[list] = None,
) -> Dict[str, Any]:
    """Get an existing template OR build a new one.

    Args:
        db: Database session.
        capability: The capability (e.g. "refund_processing").
        kb_context: Knowledge base text (used if building new template).
        integrations: List of integration names (used if building).

    Returns:
        Dict with template fields:
          - template_id
          - agent_name, capabilities, instructions, restrictions
          - default_approval_required, default_approval_threshold_cents
          - is_new (True if just built, False if reused)
    """
    from database.models.variant_engine import AgentTemplate

    # ── Step 1: Check if template exists (with advisory lock to prevent race) ──
    # Advisory lock prevents two tenants from building the same template
    # simultaneously (which would waste 12 LLM calls).
    from sqlalchemy import text as _advisory_text
    try:
        # Lock on capability hash (deterministic, prevents race)
        _lock_key = abs(hash(capability)) % (2**31)
        db.execute(_advisory_text(f"SELECT pg_advisory_lock({_lock_key})"))
    except Exception:
        pass  # SQLite doesn't support advisory locks — skip silently

    template = db.query(AgentTemplate).filter(
        AgentTemplate.capability == capability
    ).first()

    if template:
        # Template exists — REUSE (no LLM calls!)
        logger.info(
            "template_reused capability=%s times_used=%d",
            capability, template.times_used,
        )

        # Increment usage count
        template.times_used = (template.times_used or 0) + 1
        db.commit()

        # Release advisory lock
        try:
            db.execute(_advisory_text(f"SELECT pg_advisory_unlock({_lock_key})"))
        except Exception:
            pass

        return {
            "template_id": template.id,
            "agent_name": template.agent_name,
            "agent_role": template.agent_role,
            "domain": template.domain,
            "capabilities": json.loads(template.capabilities) if template.capabilities else [capability],
            "instructions": template.instructions,
            "restrictions": template.restrictions,
            "default_approval_required": template.default_approval_required,
            "default_approval_threshold_cents": template.default_approval_threshold_cents,
            "quality_score": template.quality_score,
            "stage_iterations": json.loads(template.stage_iterations) if template.stage_iterations else {},
            "is_new": False,  # ← REUSED, not built
        }

    # ── Step 2: Template doesn't exist — BUILD via external Builder ──
    logger.info(
        "template_not_found building new capability=%s via external builder",
        capability,
    )

    try:
        from app.core.remote_builder_client import build_agent_with_fallback
        builder_result = await build_agent_with_fallback(
            tenant_id="template_builder",  # not a real tenant — building template
            kb_context=kb_context or f"Create {capability} agent",
            integrations=integrations or [],
            capability=capability,
        )

        # Normalize: remote returns 'agent_config', local returns 'config'
        config = builder_result.get("agent_config", builder_result.get("config", {}))

        # ── Step 3: Save as template (shared for future tenants) ──
        # Default approval settings by capability
        risky_caps = ["refund_processing", "subscription_management",
                       "account_management", "order_cancellation"]
        default_approval = capability in risky_caps
        default_threshold = 100000 if capability == "refund_processing" else 0

        template = AgentTemplate(
            id=str(uuid4()),
            capability=capability,
            agent_name=config.get("agent_name", capability.replace("_", " ").title()),
            agent_role="template",
            domain=config.get("domain", "auto"),
            capabilities=json.dumps(config.get("capabilities", [capability])),
            instructions=config.get("instructions", ""),
            restrictions=config.get("restrictions", ""),
            default_approval_required=default_approval,
            default_approval_threshold_cents=default_threshold,
            quality_score=builder_result.get("quality_score", 0.85),
            stage_iterations=json.dumps(builder_result.get("stage_iterations", {})),
            created_by_build="external_builder",
            times_used=1,
        )
        db.add(template)
        db.commit()

        logger.info(
            "template_created capability=%s quality=%.2f — saved for reuse",
            capability, template.quality_score,
        )

        # Release advisory lock
        try:
            db.execute(_advisory_text(f"SELECT pg_advisory_unlock({_lock_key})"))
        except Exception:
            pass

        return {
            "template_id": template.id,
            "agent_name": template.agent_name,
            "agent_role": template.agent_role,
            "domain": template.domain,
            "capabilities": json.loads(template.capabilities),
            "instructions": template.instructions,
            "restrictions": template.restrictions,
            "default_approval_required": template.default_approval_required,
            "default_approval_threshold_cents": template.default_approval_threshold_cents,
            "quality_score": template.quality_score,
            "stage_iterations": json.loads(template.stage_iterations),
            "is_new": True,  # ← JUST BUILT
        }

    except Exception as exc:
        logger.error("template_build_failed capability=%s err=%s", capability, str(exc)[:200])
        raise RuntimeError(f"Template build failed for {capability}: {str(exc)[:100]}")


def clone_template_to_tenant(
    db: Session,
    template: Dict[str, Any],
    company_id: str,
    superglue_tool_id: Optional[str] = None,
    superglue_tool_status: str = "none",
    kb_context: str = "",
) -> str:
    """Clone a template to a tenant-specific AIAgentAssignment.

    This is INSTANT (0.1s, 0 LLM calls) — just a DB INSERT.
    The tenant gets their own instance with:
    - company_id scoped (security)
    - superglue_tool_id (their own API tools)
    - kb_context appended to instructions (their own policies)

    Args:
        db: Database session.
        template: Template dict from get_or_create_template().
        company_id: The tenant's company_id.
        superglue_tool_id: Tenant's Superglue tool ID (if any).
        superglue_tool_status: Status of the Superglue tool.
        kb_context: Tenant's KB text to append to instructions.

    Returns:
        The new agent_id (UUID string).
    """
    from database.models.variant_engine import AIAgentAssignment

    agent_id = str(uuid4())

    # Build instructions: template base + tenant's KB context
    instructions = template.get("instructions", "")
    if kb_context:
        instructions = f"{instructions}\n\n## Company Knowledge:\n{kb_context[:2000]}"

    agent = AIAgentAssignment(
        id=agent_id,
        company_id=company_id,
        agent_name=template.get("agent_name", "Agent"),
        agent_role="onboarding_built",
        domain=template.get("domain", "auto"),
        capabilities=json.dumps(template.get("capabilities", [])),
        instructions=instructions[:5000],
        restrictions=template.get("restrictions", ""),
        status="active",
        # Superglue tool linkage (tenant-specific)
        superglue_tool_id=superglue_tool_id,
        superglue_tool_status=superglue_tool_status,
        # Approval gates (from template defaults)
        approval_required=template.get("default_approval_required", False),
        approval_threshold_cents=template.get("default_approval_threshold_cents", 0),
    )
    db.add(agent)
    db.commit()

    logger.info(
        "template_cloned agent_id=%s company=%s capability=%s",
        agent_id[:8], company_id[:8], template.get("capabilities", [])[0] if template.get("capabilities") else "?",
    )

    return agent_id
