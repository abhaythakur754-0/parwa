"""
SG-21/SG-22: AI Agent Assignment API Router (BC-014)

Endpoints for managing AI build agent assignments.
Provides CRUD operations on the ai_agent_assignments table,
feature lookup, task decomposition summary, and default
agent seeding.

SECURITY: All endpoints require owner/admin role.
This is a global table (no company_id — for dev process).

All responses use structured JSON (BC-012).
"""

import json
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.api.deps import require_roles
from backend.app.exceptions import NotFoundError
from database.base import get_db
from database.models.core import User
from backend.app.services import agent_assignment_service

router = APIRouter(prefix="/api/ai/agents", tags=["ai-agents"])


# ══════════════════════════════════════════════════════════════════
# REQUEST / RESPONSE SCHEMAS
# ══════════════════════════════════════════════════════════════════


class AgentCreateRequest(BaseModel):
    agent_name: str = Field(min_length=1, max_length=100)
    agent_role: Optional[str] = Field(None, max_length=100)
    feature_ids: Optional[List[str]] = None
    task_ids: Optional[List[str]] = None


class AgentUpdateRequest(BaseModel):
    agent_name: Optional[str] = Field(None, min_length=1, max_length=100)
    agent_role: Optional[str] = Field(None, max_length=100)
    feature_ids: Optional[List[str]] = None
    task_ids: Optional[List[str]] = None
    status: Optional[str] = Field(None, max_length=50)


# ══════════════════════════════════════════════════════════════════
# SERIALIZATION HELPERS
# ══════════════════════════════════════════════════════════════════


def _serialize_agent(agent) -> dict:
    """Serialize an AIAgentAssignment ORM object to response dict."""
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
    status: Optional[str] = Query(None),
) -> dict:
    """List all agent assignments.

    Optionally filter by status (active, inactive, completed, paused).
    Requires owner or admin role.
    """
    agents = agent_assignment_service.get_all_agents(
        db, status=status,
    )
    return {
        "items": [_serialize_agent(a) for a in agents],
        "total": len(agents),
    }


@router.get("/summary")
def get_summary(
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    """SG-21: Task decomposition summary.

    Returns total agents, features mapped, tasks mapped,
    per-agent breakdown, and coverage stats.
    """
    summary = agent_assignment_service.get_task_decomposition_summary(db)
    return summary


@router.get("/feature/{feature_id}")
def get_agent_for_feature(
    feature_id: str,
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    """Find which agent owns a specific feature.

    Returns the agent that owns the feature_id.
    Returns 404 if no agent owns the feature.
    """
    agent = agent_assignment_service.get_agent_for_feature(
        db, feature_id=feature_id,
    )
    if agent is None:
        raise NotFoundError(
            message=(
                f"No agent found for feature '{feature_id}'"
            ),
            details={"feature_id": feature_id},
        )
    return _serialize_agent(agent)


@router.get("/{agent_id}")
def get_agent_detail(
    agent_id: str,
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    """Get single agent detail by ID."""
    agent = agent_assignment_service.get_agent_by_id(db, agent_id)
    return _serialize_agent(agent)


@router.post("")
def create_agent(
    body: AgentCreateRequest,
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    """Create a new agent assignment."""
    agent = agent_assignment_service.create_agent(
        db=db,
        agent_name=body.agent_name,
        agent_role=body.agent_role,
        feature_ids=body.feature_ids,
        task_ids=body.task_ids,
    )
    return _serialize_agent(agent)


@router.put("/{agent_id}")
def update_agent(
    agent_id: str,
    body: AgentUpdateRequest,
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    """Update an agent assignment.

    Accepts partial updates for agent_name, agent_role,
    feature_ids, task_ids, and status.
    """
    data = body.model_dump(exclude_none=True)

    if not data:
        raise agent_assignment_service.ValidationError(
            message="No fields provided for update",
        )

    agent = agent_assignment_service.update_agent_by_id(
        db, agent_id=agent_id, **data,
    )
    return _serialize_agent(agent)


@router.delete("/{agent_id}")
def delete_agent(
    agent_id: str,
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    """Soft-delete an agent (set status='inactive')."""
    agent = agent_assignment_service.delete_agent(db, agent_id)
    return {
        "message": (
            f"Agent '{agent.agent_name}' deactivated successfully"
        ),
        "agent": _serialize_agent(agent),
    }


@router.post("/initialize")
def initialize_default_agents(
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    """Seed the 5 default build agents (idempotent).

    Only creates agents that don't already exist.
    Returns a summary of created vs existing agents.
    """
    result = agent_assignment_service.initialize_default_agents(db)
    return result
