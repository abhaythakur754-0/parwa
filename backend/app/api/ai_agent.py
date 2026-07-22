"""
SG-21/SG-22: AI Agent Assignment API Router (BC-014)

Endpoints for managing AI build agent assignments.
Provides CRUD operations on the ai_agent_assignments table,
feature lookup, task decomposition summary, and default
agent seeding.

SECURITY: All endpoints require owner/admin role.
All endpoints are company-scoped via company_id (extracted
from the authenticated user). Every call is logged with
company_id for audit trail. The service layer enforces
company_id filtering on all DB queries (BC-001), ensuring
row-level multi-tenant isolation.

All responses use structured JSON (BC-012).
"""

import json
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_company_id, require_roles
from app.exceptions import NotFoundError
from database.base import get_db
from database.models.core import User
from app.services import agent_assignment_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai/agents", tags=["ai-agents"])


# ══════════════════════════════════════════════════════════════════
# REQUEST / RESPONSE SCHEMAS
# ══════════════════════════════════════════════════════════════════


class AgentCreateRequest(BaseModel):
    agent_name: str = Field(min_length=1, max_length=100)
    agent_role: Optional[str] = Field(None, max_length=100)
    feature_ids: Optional[List[str]] = None
    task_ids: Optional[List[str]] = None
    # Capability-aware routing (Phase: capability-aware Node 1)
    domain: Optional[str] = Field(None, max_length=100)
    capabilities: Optional[List[str]] = None
    instructions: Optional[str] = Field(None, max_length=10000)
    restrictions: Optional[str] = Field(None, max_length=10000)


class AgentUpdateRequest(BaseModel):
    agent_name: Optional[str] = Field(None, min_length=1, max_length=100)
    agent_role: Optional[str] = Field(None, max_length=100)
    feature_ids: Optional[List[str]] = None
    task_ids: Optional[List[str]] = None
    status: Optional[str] = Field(None, max_length=50)
    domain: Optional[str] = Field(None, max_length=100)
    capabilities: Optional[List[str]] = None
    instructions: Optional[str] = Field(None, max_length=10000)
    restrictions: Optional[str] = Field(None, max_length=10000)


# ══════════════════════════════════════════════════════════════════
# SERIALIZATION HELPERS
# ══════════════════════════════════════════════════════════════════


def _serialize_agent(agent, company_id: Optional[str] = None) -> dict:
    """Serialize an AIAgentAssignment ORM object to response dict.

    NOTE: Company scoping is enforced at both the API and
    service layers (BC-001). The serialized output does not
    include company_id directly, but every request that
    produces this payload has been validated against an
    authenticated company_id, and all service queries are
    filtered by company_id for row-level isolation.
    """
    def _parse_json_list(val, default):
        if val is None:
            return default
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
            return default
        except (json.JSONDecodeError, TypeError):
            return default

    return {
        "id": agent.id,
        "agent_name": agent.agent_name,
        "agent_role": agent.agent_role,
        "feature_ids": _parse_json_list(agent.feature_ids, []),
        "task_ids": _parse_json_list(agent.task_ids, []),
        "domain": getattr(agent, "domain", None),
        "capabilities": _parse_json_list(getattr(agent, "capabilities", None), []),
        "instructions": getattr(agent, "instructions", None),
        "restrictions": getattr(agent, "restrictions", None),
        "status": agent.status,
        "created_at": (
            agent.created_at.isoformat()
            if agent.created_at else None
        ),
        "updated_at": (
            agent.updated_at.isoformat()
            if agent.updated_at else None
        ),
    }


# ══════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════


@router.get("")
def list_agents(
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    status: Optional[str] = Query(None),
) -> dict:
    """List all agent assignments.

    Optionally filter by status (active, inactive, completed, paused).
    Requires owner or admin role.
    Company-scoped: company_id is extracted and logged for audit.
    """
    logger.info(
        "list_agents called | company_id=%s | status=%s",
        company_id, status,
    )
    agents = agent_assignment_service.get_all_agents(
        db, company_id=company_id, status=status,
    )
    return {
        "items": [_serialize_agent(a, company_id=company_id) for a in agents],
        "total": len(agents),
    }


@router.get("/summary")
def get_summary(
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
) -> dict:
    """SG-21: Task decomposition summary.

    Returns total agents, features mapped, tasks mapped,
    per-agent breakdown, and coverage stats.
    Company-scoped: company_id is extracted and logged for audit.
    """
    logger.info(
        "get_summary called | company_id=%s",
        company_id,
    )
    summary = agent_assignment_service.get_task_decomposition_summary(
        db, company_id=company_id,
    )
    return summary


@router.get("/feature/{feature_id}")
def get_agent_for_feature(
    feature_id: str,
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
) -> dict:
    """Find which agent owns a specific feature.

    Returns the agent that owns the feature_id.
    Returns 404 if no agent owns the feature.
    Company-scoped: company_id is extracted and logged for audit.
    """
    logger.info(
        "get_agent_for_feature called | company_id=%s | feature_id=%s",
        company_id, feature_id,
    )
    agent = agent_assignment_service.get_agent_for_feature(
        db, company_id=company_id, feature_id=feature_id,
    )
    if agent is None:
        raise NotFoundError(
            message=(
                f"No agent found for feature '{feature_id}'"
            ),
            details={"feature_id": feature_id},
        )
    return _serialize_agent(agent, company_id=company_id)


@router.get("/{agent_id}")
def get_agent_detail(
    agent_id: str,
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
) -> dict:
    """Get single agent detail by ID.

    Company-scoped: company_id is extracted and logged for audit.
    """
    logger.info(
        "get_agent_detail called | company_id=%s | agent_id=%s",
        company_id, agent_id,
    )
    agent = agent_assignment_service.get_agent_by_id(
        db, company_id=company_id, agent_id=agent_id,
    )
    return _serialize_agent(agent, company_id=company_id)


@router.post("")
def create_agent(
    body: AgentCreateRequest,
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
) -> dict:
    """Create a new agent assignment.

    Company-scoped: company_id is extracted and logged for audit.
    """
    logger.info(
        "create_agent called | company_id=%s | agent_name=%s",
        company_id, body.agent_name,
    )
    agent = agent_assignment_service.create_agent(
        db=db,
        company_id=company_id,
        agent_name=body.agent_name,
        agent_role=body.agent_role,
        feature_ids=body.feature_ids,
        task_ids=body.task_ids,
        domain=body.domain,
        capabilities=body.capabilities,
        instructions=body.instructions,
        restrictions=body.restrictions,
    )
    return _serialize_agent(agent, company_id=company_id)


@router.put("/{agent_id}")
def update_agent(
    agent_id: str,
    body: AgentUpdateRequest,
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
) -> dict:
    """Update an agent assignment.

    Accepts partial updates for agent_name, agent_role,
    feature_ids, task_ids, and status.
    Company-scoped: company_id is extracted and logged for audit.
    """
    logger.info(
        "update_agent called | company_id=%s | agent_id=%s",
        company_id, agent_id,
    )
    data = body.model_dump(exclude_none=True)

    if not data:
        raise agent_assignment_service.ValidationError(
            message="No fields provided for update",
        )

    agent = agent_assignment_service.update_agent_by_id(
        db, company_id=company_id, agent_id=agent_id, **data,
    )
    return _serialize_agent(agent, company_id=company_id)


@router.delete("/{agent_id}")
def delete_agent(
    agent_id: str,
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
) -> dict:
    """Soft-delete an agent (set status='inactive').

    Company-scoped: company_id is extracted and logged for audit.
    """
    logger.info(
        "delete_agent called | company_id=%s | agent_id=%s",
        company_id, agent_id,
    )
    agent = agent_assignment_service.delete_agent(
        db, company_id=company_id, agent_id=agent_id,
    )
    return {
        "message": (
            f"Agent '{agent.agent_name}' deactivated successfully"
        ),
        "agent": _serialize_agent(agent, company_id=company_id),
    }


@router.post("/initialize")
def initialize_default_agents(
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
) -> dict:
    """Seed the 5 default build agents (idempotent).

    Only creates agents that don't already exist.
    Returns a summary of created vs existing agents.
    Company-scoped: company_id is extracted and logged for audit.
    """
    logger.info(
        "initialize_default_agents called | company_id=%s",
        company_id,
    )
    result = agent_assignment_service.initialize_default_agents(
        db, company_id=company_id,
    )
    return result


# ── Auto-Create Agents from Job Description ──────────────────────────

class AutoCreateRequest(BaseModel):
    """Request body for auto-creating agents from a job description."""
    job_description: str = Field(..., min_length=50, max_length=10000,
                                  description="Full text of the job description / role spec")
    industry: Optional[str] = Field(None, max_length=100,
                                     description="Optional industry hint (e.g. 'Hospitality', 'E-commerce')")


@router.post("/auto-create")
async def auto_create_agents(
    body: AutoCreateRequest,
    user: User = Depends(require_roles("owner", "admin")),
    company_id: str = Depends(get_company_id),
) -> dict:
    """Analyze a job description with an LLM and suggest 2-5 agents.

    The LLM reads the JD and proposes a set of specialized agents that
    together cover the responsibilities described. Each suggestion
    includes: agent_name, domain, capabilities (list), instructions
    (system prompt), and restrictions (rules).

    Returns the suggestions ONLY — does NOT persist them. The frontend
    shows them for review, then the user clicks "Create" on each one
    (or "Create All") which hits the normal POST /api/ai/agents endpoint.
    """
    import json as _json
    from app.core.parwa_pipeline.llm_client import llm_call

    logger.info(
        "auto_create_agents called | company_id=%s | jd_len=%d",
        company_id, len(body.job_description),
    )

    prompt = f"""You are an AI agent architect for a customer support SaaS platform called PARWA.

A client has pasted a JOB DESCRIPTION for a customer service role at their company.
Your job is to analyze the JD and design a set of 3-5 SPECIALIZED AI agents that
together can handle the FULL customer lifecycle — not just the happy path in the JD.

IMPORTANT: JDs describe the happy path (booking, answering questions, providing info).
But real customers also have problems: refunds, cancellations, complaints, billing
errors, accessibility issues, overbooking, defective products. Your agent set MUST
cover these edge cases too, even if the JD doesn't mention them.

Think about what can go WRONG in this industry and make sure there's an agent for it.

Each agent should:
- Have a clear, narrow specialty (not generic "customer service")
- Cover a distinct area so there's minimal overlap
- Together cover ALL responsibilities in the JD PLUS common problem scenarios
- Include at least one agent for refunds/cancellations/complaints (every industry needs this)

Return a JSON array (no markdown, no explanation — JUST the JSON array) where each
element has:
{{
  "agent_name": "short descriptive name (e.g. 'Hotel Booking Specialist', 'Cancellation & Refund Agent')",
  "domain": "industry/domain (e.g. 'Hospitality', 'E-commerce')",
  "capabilities": ["comma", "separated", "list", "of", "what", "it", "handles"],
  "instructions": "2-4 sentence system prompt telling the AI how to behave",
  "restrictions": "natural-language rules it must follow (what NOT to do, when to escalate)"
}}

JOB DESCRIPTION:
{body.job_description}

{f"INDUSTRY HINT: {body.industry}" if body.industry else ""}

Return ONLY the JSON array. No markdown fences, no explanation."""

    try:
        raw = await llm_call(prompt, max_tokens=2000, temperature=0.4)
    except Exception as exc:  # noqa: BLE001
        logger.error("auto_create_agents LLM failed: %s", str(exc)[:200])
        return {
            "status": "error",
            "message": f"LLM analysis failed: {str(exc)[:200]}",
            "suggestions": [],
        }

    # Parse the LLM response — strip markdown fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        # Remove ```json ... ``` fences
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    try:
        suggestions = _json.loads(cleaned)
    except _json.JSONDecodeError:
        # Try to extract the array from surrounding text
        import re
        match = re.search(r'\[.*\]', cleaned, re.DOTALL)
        if match:
            try:
                suggestions = _json.loads(match.group(0))
            except _json.JSONDecodeError:
                return {
                    "status": "error",
                    "message": "LLM returned malformed JSON",
                    "raw_response": cleaned[:500],
                    "suggestions": [],
                }
        else:
            return {
                "status": "error",
                "message": "LLM returned no JSON array",
                "raw_response": cleaned[:500],
                "suggestions": [],
            }

    # Validate + normalize each suggestion
    # Apply non-LLM techniques to enhance the suggestions
    import re as _re
    jd_lower = body.job_description.lower()

    # Scan JD for capability patterns (non-LLM)
    jd_capabilities = []
    capability_patterns = {
        "refund_processing": [r"\brefund\b", r"\bmoney.back\b", r"\bchargeback\b"],
        "billing_inquiry": [r"\bbilling\b", r"\binvoice\b", r"\bpayment\b", r"\bcharge\b"],
        "technical_support": [r"\btechnical\b", r"\btroubleshoot\b", r"\bapi\b", r"\bbug\b"],
        "complaint_handling": [r"\bcomplaint\b", r"\bescalat\b", r"\bdisput\b"],
        "fraud_security": [r"\bfraud\b", r"\bscam\b", r"\bunauthorized\b", r"\bstolen\b"],
        "shipping_delivery": [r"\bshipping\b", r"\bdelivery\b", r"\btracking\b", r"\blogistics\b"],
        "booking_reservation": [r"\bbook\b", r"\breserv\b", r"\bappointment\b"],
        "account_management": [r"\baccount\b", r"\bpassword\b", r"\blogin\b", r"\bprofil\b"],
        "product_information": [r"\bproduct\b", r"\bspec\b", r"\bfeature\b", r"\brecommend\b"],
        "vip_enterprise": [r"\bvip\b", r"\benterprise\b", r"\bpremium\b"],
        "legal_review": [r"\blegal\b", r"\blawsuit\b", r"\battorney\b", r"\bcompliance\b"],
        "cancellation": [r"\bcancel\b", r"\bterminat\b"],
    }
    for cap, patterns in capability_patterns.items():
        for pattern in patterns:
            if _re.search(pattern, jd_lower):
                jd_capabilities.append(cap)
                break

    # Scan JD for complexity/escalation keywords (non-LLM)
    escalation_in_jd = any(kw in jd_lower for kw in [
        "escalate", "manager", "supervisor", "legal", "lawsuit",
        "compliance", "emergency", "urgent",
    ])

    # Scan JD for sales keywords (non-LLM)
    sales_in_jd = any(kw in jd_lower for kw in [
        "sales", "upsell", "cross-sell", "recommend", "brand ambassador",
        "product expert", "guide customers",
    ])

    validated = []
    for s in suggestions:
        if not isinstance(s, dict):
            continue
        name = str(s.get("agent_name", "")).strip()
        if not name:
            continue

        # Get the agent's capabilities
        agent_caps = (
            s["capabilities"] if isinstance(s.get("capabilities"), list)
            else [c.strip() for c in str(s.get("capabilities", "")).split(",") if c.strip()]
        )

        # Non-LLM enhancement: add JD-detected capabilities the agent is missing
        for cap in jd_capabilities:
            cap_words = set(cap.replace("_", " ").split())
            agent_has = any(
                cap_words & set(c.lower().replace("_", " ").split())
                for c in agent_caps
            )
            if not agent_has and cap not in agent_caps:
                agent_caps.append(cap)

        # Non-LLM enhancement: add restrictions based on escalation keywords
        restrictions = str(s.get("restrictions", "")).strip()
        if escalation_in_jd and "escalat" not in restrictions.lower():
            restrictions += " Always escalate legal threats, lawsuits, and compliance issues to human."
        if sales_in_jd and "competitor" not in restrictions.lower():
            restrictions += " Never share competitor pricing. Focus on own product value."

        # Non-LLM enhancement: add tier-based restrictions
        restrictions += " If unsure or lacking verified information, pause for human guidance."

        validated.append({
            "agent_name": name,
            "domain": str(s.get("domain", body.industry or "General")).strip(),
            "capabilities": agent_caps,
            "instructions": str(s.get("instructions", "")).strip(),
            "restrictions": restrictions,
        })

    logger.info(
        "auto_create_agents success | company_id=%s | suggestions=%d",
        company_id, len(validated),
    )

    return {
        "status": "ok",
        "suggestions": validated,
        "count": len(validated),
    }
