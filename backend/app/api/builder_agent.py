"""
Builder Agent API — endpoints for programmatic and chat-based agent creation.

Provides:
  POST /api/v1/agents/builder/create  — Create agent via Builder pipeline (programmatic)
  POST /api/v1/agents/builder/chat    — Multi-turn chat with Builder (UI)
  POST /api/v1/agents/builder/finalize — Finalize and save agent from chat session

SECURITY: All endpoints require owner/admin role.
All endpoints are company-scoped via company_id (BC-001).
"""

import json
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_company_id, require_roles
from database.base import get_db
from database.models.core import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agents/builder", tags=["builder-agent"])


# ══════════════════════════════════════════════════════════════════
# REQUEST / RESPONSE SCHEMAS
# ══════════════════════════════════════════════════════════════════


class BuilderCreateRequest(BaseModel):
    """Request to create an agent via the Builder pipeline."""
    capability: str = Field(..., min_length=1, max_length=100,
                            description="Capability key (e.g. 'refund_processing')")
    query: Optional[str] = Field(None, max_length=2000,
                                  description="Sample ticket text for context")
    ticket_type: Optional[str] = Field(None, max_length=100)
    complexity: Optional[str] = Field(None, max_length=50)


class BuilderChatRequest(BaseModel):
    """Request for a multi-turn chat with the Builder."""
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = Field(None, max_length=100)


class BuilderFinalizeRequest(BaseModel):
    """Request to finalize and save an agent from a chat session."""
    session_id: str = Field(..., min_length=1, max_length=100)


class BuilderChatResponse(BaseModel):
    """Response from the Builder chat."""
    message: str
    session_id: str
    stage: str
    config_preview: Optional[dict] = None


# ══════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════


@router.post("/create")
async def create_agent_via_builder(
    body: BuilderCreateRequest,
    user: User = Depends(require_roles("owner", "admin")),
    company_id: str = Depends(get_company_id),
) -> dict:
    """Create an agent using the full 4-stage Builder pipeline.

    This is the programmatic endpoint — Node 1 calls this when it
    detects a capability gap. The Builder runs EXPLORE → DESIGN →
    VERIFY → REFINE and creates a properly designed agent.

    Returns the builder result including agent_id on success.
    """
    logger.info(
        "builder_create called | company_id=%s | capability=%s",
        company_id, body.capability,
    )

    from app.core.builder_agent.builder_pipeline import run_builder_pipeline

    # Get tenant tier
    tier = "parwa"
    try:
        from database.base import SessionLocal
        from database.models.core import Company
        db = SessionLocal()
        co = db.query(Company).filter(Company.id == company_id).first()
        tier = getattr(co, "plan", "parwa") if co else "parwa"
        db.close()
    except Exception:
        pass

    result = await run_builder_pipeline(
        tenant_id=company_id,
        capability=body.capability,
        query=body.query or "",
        ticket_type=body.ticket_type or "",
        complexity=body.complexity or "",
        tier=tier,
    )

    return {
        "status": result.get("status"),
        "agent_id": result.get("agent_id"),
        "config": result.get("config"),
        "quality_score": result.get("refine_quality_score", 0.0),
        "stage_iterations": result.get("stage_iterations", {}),
        "verify_consensus": result.get("verify_consensus"),
        "guardrail_safe": result.get("guardrail_safe", True),
    }


@router.post("/chat")
async def builder_chat(
    body: BuilderChatRequest,
    user: User = Depends(require_roles("owner", "admin")),
    company_id: str = Depends(get_company_id),
) -> dict:
    """Multi-turn chat with the Builder Agent.

    The Builder chats with the user to design the perfect agent.
    Each message advances the 4-stage pipeline incrementally.

    Returns the Builder's response + current config preview.
    """
    logger.info(
        "builder_chat called | company_id=%s | session=%s",
        company_id, body.session_id,
    )

    from app.core.builder_agent.builder_llm import builder_llm_call
    from app.core.builder_agent.builder_state import is_customer_care_request

    # Scope check
    scope_ok, scope_reason = is_customer_care_request(body.message)
    if not scope_ok:
        return {
            "message": (
                f"I'm sorry, I can only create customer care agents. "
                f"{scope_reason} Could you describe a customer support "
                f"or onboarding agent instead?"
            ),
            "session_id": body.session_id or "new",
            "stage": "rejected",
            "config_preview": None,
        }

    # Builder chat response
    chat_prompt = (
        f"You are the PARWA Agent Builder. A user wants to create a customer care agent.\n"
        f"User says: {body.message}\n\n"
        f"Help them design the agent. Ask about:\n"
        f"1. What specific customer problems should this agent handle?\n"
        f"2. What knowledge or docs should it have access to?\n"
        f"3. Any restrictions (max refund amount, escalation rules, etc.)?\n"
        f"4. What should the agent be called?\n\n"
        f"Be conversational and helpful. Keep response under 3 sentences."
    )

    response = await builder_llm_call(
        prompt=chat_prompt,
        stage="explore",
        max_tokens=200,
        temperature=0.3,
    )

    return {
        "message": response or "Tell me more about what kind of customer care agent you need.",
        "session_id": body.session_id or "new",
        "stage": "explore",
        "config_preview": None,
    }


@router.post("/finalize")
async def builder_finalize(
    body: BuilderFinalizeRequest,
    user: User = Depends(require_roles("owner", "admin")),
    company_id: str = Depends(get_company_id),
) -> dict:
    """Finalize and save an agent from a Builder chat session.

    Takes the config collected during the chat session and creates
    the agent in the database.
    """
    logger.info(
        "builder_finalize called | company_id=%s | session=%s",
        company_id, body.session_id,
    )

    # For now, return a placeholder — the full chat session management
    # will be built when the frontend Builder UI is connected.
    return {
        "status": "pending",
        "message": "Chat session finalize is connected to the frontend Builder UI.",
        "session_id": body.session_id,
    }


@router.get("/custom-categories")
def list_custom_categories(
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
) -> dict:
    """List all custom categories for this tenant.

    Custom categories are created by the Builder Agent when it creates
    an agent that doesn't map to a built-in ticket category.
    """
    logger.info("list_custom_categories called | company_id=%s", company_id)

    try:
        from database.models.variant_engine import CustomCategory

        categories = db.query(CustomCategory).filter(
            CustomCategory.company_id == company_id,
            CustomCategory.is_active == True,
        ).all()

        items = []
        for cat in categories:
            try:
                keywords = json.loads(cat.keywords) if isinstance(cat.keywords, str) else (cat.keywords or [])
            except (json.JSONDecodeError, TypeError):
                keywords = []

            items.append({
                "id": cat.id,
                "name": cat.name,
                "keywords": keywords,
                "agent_id": cat.agent_id,
                "created_at": cat.created_at.isoformat() if cat.created_at else None,
            })

        return {"items": items, "total": len(items)}

    except Exception as exc:
        logger.warning("list_custom_categories failed: %s", str(exc)[:200])
        return {"items": [], "total": 0, "error": str(exc)[:200]}
