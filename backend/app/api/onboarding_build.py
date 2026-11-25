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
from app.core.superglue_tool_generator import agent_tool_lock, generate_tool_for_agent
from database.base import get_db
from database.models.core import User
from database.models.variant_engine import AIAgentAssignment
from database.models.crm_analysis import CRMAnalysisResult

logger = logging.getLogger("parwa.onboarding_build")
router = APIRouter(prefix="/api/onboarding-build", tags=["onboarding-build"])

# Starter agents for brand-new tenants: no ticket history + no connected
# integrations yet means the analyser has nothing to learn from. Without a
# fallback, zero agents get built and /status can never report all_ready=True
# — onboarding deadlocks at verify. This guarantees the build always runs.
STARTER_AGENT_PACK = {
    "Refund Specialist": ["refund_processing", "billing_inquiry"],
    "Order & Shipping Specialist": ["order_cancellation", "shipping_delivery", "product_information"],
    "Billing Specialist": ["billing_inquiry", "invoice_request"],
    "Account Support Specialist": ["account_management", "subscription_management"],
    "Technical Support Specialist": ["technical_support"],
    "General Support Specialist": ["faq_general"],
}


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

    # CRM analysis stores integration recommendations separately from the
    # support agents required to handle ticket capabilities.
    recommendations = (analysis.data_profile or {}).get("recommended_agents") or []
    if not isinstance(recommendations, list) or not recommendations:
        recommendations = [
            {"name": name, "capabilities": capabilities, "priority": "medium"}
            for name, capabilities in STARTER_AGENT_PACK.items()
        ]

    agent_statuses: List[AgentBuildStatus] = []
    created = 0
    skipped = 0
    failed = 0

    # Tools are generated against this tenant's VERIFIED data sources only.
    from database.models.integration import Integration, DBConnection
    connected_integrations = db.query(Integration).filter(
        Integration.company_id == tenant_id,
        Integration.status.in_(["verified", "active"]),
    ).all()
    tenant_integrations_ctx = {
        i.integration_type: {
            "name": i.name,
            "status": i.status,
            "system_id": i.integration_type,
        }
        for i in connected_integrations
    }

    connected_databases = db.query(DBConnection).filter(
        DBConnection.company_id == tenant_id,
        DBConnection.status == "verified",
    ).all()
    for db_conn in connected_databases:
        try:
            schema = json.loads(db_conn.schema_analysis) if db_conn.schema_analysis else None
        except (json.JSONDecodeError, TypeError):
            schema = None
        if schema and schema.get("source") != "fallback":
            db_integration = next(
                (item for item in connected_integrations if item.name == db_conn.name),
                None,
            )
            db_system_id = db_integration.integration_type if db_integration else db_conn.name
            tenant_integrations_ctx[f"database:{db_system_id}"] = {
                "name": db_conn.name,
                "status": db_conn.status,
                "system_id": db_system_id,
                "db_type": db_conn.db_type,
                "readonly": True,
                "schema": schema,
                "schema_ready": True,
            }

    if not tenant_integrations_ctx:
        raise HTTPException(
            status_code=409,
            detail="Connect and verify at least one integration or database before building agents.",
        )

    logger.info(
        "onboarding_build_scope tenant=%s verified_sources=%d agents=%d",
        tenant_id, len(tenant_integrations_ctx), len(recommendations),
    )

    for rec in recommendations:
        if isinstance(rec, dict):
            raw_name = (
                rec.get("name")
                or rec.get("agent_name")
                or rec.get("key")
                or rec.get("capability")
                or "General Support Specialist"
            )
            agent_name = str(raw_name).replace("_", " ").strip().title()
            agent_role = str(rec.get("role") or agent_name)
            raw_capabilities = rec.get("capabilities")
            if isinstance(raw_capabilities, list):
                capabilities = [str(item) for item in raw_capabilities if str(item).strip()]
            elif rec.get("capability"):
                capabilities = [str(rec["capability"])]
            else:
                capabilities = _infer_capabilities(agent_name)
            agent_reason = str(rec.get("reason") or "")
            agent_instructions = str(
                rec.get("instructions")
                or f"Handle {agent_name}-related customer tickets. {agent_reason}".strip()
            )
        else:
            agent_name = str(rec).replace("_", " ").strip().title()
            agent_role = agent_name
            capabilities = _infer_capabilities(agent_name)
            agent_instructions = f"Handle {agent_name}-related customer tickets."

        if not agent_name:
            continue

        # 3. Dedup check — does this agent already exist for this tenant?
        existing = db.query(AIAgentAssignment).filter(
            AIAgentAssignment.company_id == tenant_id,
            AIAgentAssignment.agent_name == agent_name,
        ).first()

        if existing and existing.superglue_tool_status == "active":
            existing_tool_ok = bool(
                existing.superglue_tool_id
                and await superglue_client.verify_tool_exists(
                    existing.superglue_tool_id, tenant_id=tenant_id
                )
            )
            if existing_tool_ok:
                agent_statuses.append(AgentBuildStatus(
                    agent_name=agent_name,
                    agent_role=agent_role,
                    status="skipped",
                    superglue_tool_id=existing.superglue_tool_id,
                    error=None,
                ))
                skipped += 1
                continue
            existing.superglue_tool_status = "pending"
            existing.superglue_tool_id = None
            db.commit()

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
                instructions=agent_instructions,
                restrictions="Only use approved Superglue tools. Follow tier guardrails.",
                feature_ids="[]",
                task_ids="[]",
                superglue_tool_status="pending",
            )
            db.add(agent)
        db.commit()
        db.refresh(agent)

        # 5. Call Superglue to generate the tool (async, may take 10-30s)
        # CONCURRENCY FIX (2026-09-27): agent_tool_lock + active re-check —
        # double-submit of onboarding used to create duplicate Superglue
        # tools for the same agent (one linked, one orphaned).
        try:
            async with agent_tool_lock(f"{tenant_id}:{agent.id}"):
                db.refresh(agent)  # another request may have finished while we waited
                if (
                    agent.superglue_tool_id
                    and agent.superglue_tool_status == "active"
                    and await superglue_client.verify_tool_exists(
                        agent.superglue_tool_id, tenant_id=tenant_id
                    )
                ):
                    logger.info(
                        "superglue_tool_reuse (onboarding) | tenant=%s | agent=%s | tool_id=%s "
                        "— verified existing tool, skipping duplicate generation",
                        tenant_id, agent_name, agent.superglue_tool_id,
                    )
                    result = {
                        "success": True,
                        "tool_id": agent.superglue_tool_id,
                        "tool_definition": json.loads(agent.superglue_tool_definition or "{}"),
                    }
                else:
                    agent.superglue_tool_id = None
                    agent.superglue_tool_status = "pending"
                    db.commit()
                    result = await generate_tool_for_agent(
                        agent_name=agent_name,
                        agent_instructions=agent_instructions,
                        agent_capabilities=", ".join(capabilities),
                        sample_ticket=None,
                        tenant_integrations=tenant_integrations_ctx,
                        tenant_id=tenant_id,
                    )

            if result.get("success"):
                generated_tool_id = result.get("tool_id")
                tool_exists = bool(
                    generated_tool_id
                    and await superglue_client.verify_tool_exists(
                        generated_tool_id, tenant_id=tenant_id
                    )
                )
                if not tool_exists:
                    result = {
                        "success": False,
                        "error": "Generated tool could not be verified in this tenant's Superglue workspace",
                    }

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
