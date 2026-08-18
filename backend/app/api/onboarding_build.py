"""
PARWA Onboarding Build Orchestrator — triggers agent + tool creation
from CRM Analyser results, with deduplication + status polling.

Flow:
  1. CRM Analyser returns {integrations, agents, tools}
  2. User connects recommended integrations (Phase 3)
  3. Frontend calls POST /api/onboarding-build/trigger
     → For each agent in analyser output:
       - Check if agent already exists for this tenant (dedup)
       - If not, create AIAgentAssignment row (status=pending)
       - Call generate_tool_for_agent() (Superglue creates the tool)
       - Update row with tool_id + status=active
  4. Frontend polls GET /api/onboarding-build/status until all agents ready
  5. Only then can user proceed to next onboarding step

BC-001: All agents scoped to company_id (tenant isolation).
Dedup: (company_id, agent_name) is the natural key — re-running analysis
       won't create duplicate agents for the same tenant.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core import superglue_client
from app.core.superglue_tool_generator import generate_tool_for_agent
from database.base import get_db
from database.models.core import User
from database.models.variant_engine import AIAgentAssignment
from database.models.crm_analysis import CRMAnalysisResult

logger = logging.getLogger("parwa.onboarding_build")
router = APIRouter(prefix="/api/onboarding-build", tags=["onboarding-build"])


# ── Models ────────────────────────────────────────────────────────────

class TriggerBuildRequest(BaseModel):
    analysis_result_id: Optional[str] = Field(default=None, description="CRMAnalysisResult ID. If omitted, uses latest.")


class AgentBuildStatus(BaseModel):
    agent_name: str
    agent_role: str
    status: str  # pending|active|failed|skipped
    superglue_tool_id: Optional[str] = None
    error: Optional[str] = None


class TriggerBuildResponse(BaseModel):
    triggered: bool
    total_agents: int
    created: int
    skipped_existing: int
    failed: int
    agents: List[AgentBuildStatus]


class BuildStatusResponse(BaseModel):
    company_id: str
    total_agents: int
    ready: int
    pending: int
    failed: int
    all_ready: bool
    agents: List[AgentBuildStatus]


# ── Trigger endpoint ──────────────────────────────────────────────────

@router.post("/trigger", response_model=TriggerBuildResponse)
async def trigger_build(
    req: TriggerBuildRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TriggerBuildResponse:
    """Trigger agent + tool creation from the latest CRM analysis.

    For each agent recommended by the CRM Analyser:
    1. Check if an agent with the same name already exists for this tenant (dedup)
    2. If exists + has active tool → skip (don't duplicate)
    3. If not → create AIAgentAssignment row + call generate_tool_for_agent()

    This is idempotent — calling it multiple times won't create duplicates.
    """
    tenant_id = str(user.company_id)

    # 1. Get the analysis result (latest for this tenant)
    analysis = None
    if req.analysis_result_id:
        analysis = db.query(CRMAnalysisResult).filter(
            CRMAnalysisResult.id == req.analysis_result_id,
            CRMAnalysisResult.company_id == tenant_id,
        ).first()
    else:
        analysis = db.query(CRMAnalysisResult).filter(
            CRMAnalysisResult.company_id == tenant_id,
        ).order_by(CRMAnalysisResult.created_at.desc()).first()

    if not analysis:
        raise HTTPException(status_code=404, detail="No CRM analysis found. Run analysis first.")

    # 2. Extract agents from recommendations
    # The analyser returns integrations as a list of names; we derive agents from them
    # Each integration becomes an agent specialized for that system
    recommendations = analysis.recommendations or []
    agent_statuses: List[AgentBuildStatus] = []
    created = 0
    skipped = 0
    failed = 0

    # Get tenant's connected integrations for tool generation context
    from database.models.integration import Integration
    connected_integrations = db.query(Integration).filter(
        Integration.company_id == tenant_id,
        Integration.status.in_(["connected", "verified"]),
    ).all()
    tenant_integrations_ctx = {
        i.integration_type: {"name": i.name, "status": i.status}
        for i in connected_integrations
    }

    for rec in recommendations:
        agent_name = rec.get("name", "Unknown") if isinstance(rec, dict) else str(rec)
        agent_role = f"{agent_name} Specialist"
        capabilities = _infer_capabilities(agent_name)

        # 3. Dedup check — does this agent already exist for this tenant?
        existing = db.query(AIAgentAssignment).filter(
            AIAgentAssignment.company_id == tenant_id,
            AIAgentAssignment.agent_name == agent_name,
        ).first()

        if existing and existing.superglue_tool_status == "active":
            agent_statuses.append(AgentBuildStatus(
                agent_name=agent_name,
                agent_role=agent_role,
                status="skipped",
                superglue_tool_id=existing.superglue_tool_id,
                error=None,
            ))
            skipped += 1
            continue

        # 4. Create/update the agent assignment row
        if existing:
            agent = existing
            agent.agent_role = agent_role
            agent.capabilities = json.dumps(capabilities)
            agent.superglue_tool_status = "pending"
        else:
            agent = AIAgentAssignment(
                company_id=tenant_id,
                agent_name=agent_name,
                agent_role=agent_role,
                domain=agent_name,
                capabilities=json.dumps(capabilities),
                instructions=f"Handle {agent_name}-related customer tickets.",
                restrictions="Only use approved Superglue tools. Follow tier guardrails.",
                feature_ids="[]",
                task_ids="[]",
                superglue_tool_status="pending",
            )
            db.add(agent)
        db.commit()
        db.refresh(agent)

        # 5. Call Superglue to generate the tool (async, may take 10-30s)
        try:
            result = await generate_tool_for_agent(
                agent_name=agent_name,
                agent_instructions=f"Handle {agent_name}-related customer tickets.",
                agent_capabilities=", ".join(capabilities),
                sample_ticket=None,
                tenant_integrations=tenant_integrations_ctx,
            )

            if result.get("success"):
                agent.superglue_tool_id = result.get("tool_id")
                agent.superglue_tool_status = "active"
                agent.superglue_tool_definition = json.dumps(result.get("tool_definition", {}))
                agent.superglue_tool_created_at = datetime.now(timezone.utc)
                db.commit()

                agent_statuses.append(AgentBuildStatus(
                    agent_name=agent_name,
                    agent_role=agent_role,
                    status="active",
                    superglue_tool_id=agent.superglue_tool_id,
                ))
                created += 1
            else:
                agent.superglue_tool_status = "failed"
                db.commit()
                agent_statuses.append(AgentBuildStatus(
                    agent_name=agent_name,
                    agent_role=agent_role,
                    status="failed",
                    error=result.get("error", "unknown"),
                ))
                failed += 1
        except Exception as exc:
            logger.warning("agent_build_failed name=%s: %s", agent_name, str(exc)[:200])
            agent.superglue_tool_status = "failed"
            db.commit()
            agent_statuses.append(AgentBuildStatus(
                agent_name=agent_name,
                agent_role=agent_role,
                status="failed",
                error=str(exc)[:150],
            ))
            failed += 1

    return TriggerBuildResponse(
        triggered=True,
        total_agents=len(recommendations),
        created=created,
        skipped_existing=skipped,
        failed=failed,
        agents=agent_statuses,
    )


# ── Status polling endpoint ───────────────────────────────────────────

@router.get("/status", response_model=BuildStatusResponse)
async def get_build_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BuildStatusResponse:
    """Get the current status of all agents for this tenant.

    Frontend polls this every 3 seconds after triggering a build.
    When all_ready=True, the user can proceed to the next onboarding step.
    """
    tenant_id = str(user.company_id)

    agents = db.query(AIAgentAssignment).filter(
        AIAgentAssignment.company_id == tenant_id,
    ).all()

    agent_statuses: List[AgentBuildStatus] = []
    ready = 0
    pending = 0
    failed = 0

    for a in agents:
        status = a.superglue_tool_status or "none"
        if status == "active":
            ready += 1
        elif status == "pending":
            pending += 1
        elif status == "failed":
            failed += 1

        agent_statuses.append(AgentBuildStatus(
            agent_name=a.agent_name,
            agent_role=a.agent_role or "",
            status=status,
            superglue_tool_id=a.superglue_tool_id,
        ))

    total = len(agents)
    all_ready = total > 0 and ready == total and failed == 0

    return BuildStatusResponse(
        company_id=tenant_id,
        total_agents=total,
        ready=ready,
        pending=pending,
        failed=failed,
        all_ready=all_ready,
        agents=agent_statuses,
    )


# ── Helper: infer agent capabilities from integration name ────────────

def _infer_capabilities(integration_name: str) -> List[str]:
    """Map an integration name to PARWA's capability vocabulary.

    This lets Node 1 route tickets to the right agent based on capability.
    """
    name_lower = integration_name.lower()

    capability_map = {
        "stripe": ["refund_processing", "billing_inquiry"],
        "razorpay": ["refund_processing", "billing_inquiry"],
        "paypal": ["refund_processing", "billing_inquiry"],
        "shopify": ["product_information", "shipping_delivery", "refund_processing"],
        "woocommerce": ["product_information", "shipping_delivery"],
        "gmail": ["faq_general"],
        "outlook": ["faq_general"],
        "slack": ["faq_general"],
        "hubspot": ["account_management", "faq_general"],
        "zendesk": ["faq_general", "technical_support"],
        "salesforce": ["account_management"],
        "github": ["technical_support"],
        "jira": ["technical_support"],
        "notion": ["faq_general"],
        "shipping": ["shipping_delivery"],
        "shipstation": ["shipping_delivery"],
    }

    for key, caps in capability_map.items():
        if key in name_lower:
            return caps

    return ["other"]
