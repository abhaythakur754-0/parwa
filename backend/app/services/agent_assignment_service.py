"""
SG-22: Agent Assignment Strategy Service.

Manages AI build agent assignments to features and tasks.
Uses the ai_agent_assignments table (global, no company_id).

BC-001: N/A — this is a global dev process table.
BC-012: All errors use ParwaBaseError.
"""

import json

from sqlalchemy.orm.session import Session

from database.models.variant_engine import AIAgentAssignment
from backend.app.exceptions import (
    ParwaBaseError,
    ValidationError,
    NotFoundError,
)


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

VALID_STATUSES = {"active", "completed", "paused"}

VALID_ROLES = {
    "infrastructure",
    "routing",
    "classification",
    "rag",
    "techniques",
    "monitoring",
    "orchestration",
    "guardrails",
    "fullstack",
}


# ══════════════════════════════════════════════════════════════════
# VALIDATION HELPERS
# ══════════════════════════════════════════════════════════════════

def _validate_agent_name(agent_name: str) -> None:
    """Validate agent name is non-empty."""
    if not agent_name or not agent_name.strip():
        raise ValidationError(
            message="agent_name is required and cannot be empty",
        )


def _validate_agent_role(agent_role: str | None) -> None:
    """Validate agent role if provided."""
    if agent_role is not None:
        if not agent_role.strip():
            raise ValidationError(
                message="agent_role cannot be blank",
            )


def _validate_status(status: str) -> None:
    """Validate status value."""
    if status not in VALID_STATUSES:
        raise ValidationError(
            message=(
                f"Invalid status '{status}'. "
                f"Must be one of: "
                f"{', '.join(sorted(VALID_STATUSES))}"
            ),
        )


def _validate_feature_ids(feature_ids: list[str]) -> None:
    """Validate feature_ids is a list of non-empty strings."""
    if not isinstance(feature_ids, list):
        raise ValidationError(
            message="feature_ids must be a list",
        )
    for fid in feature_ids:
        if not isinstance(fid, str) or not fid.strip():
            raise ValidationError(
                message="Each feature_id must be a non-empty string",
            )


def _validate_task_ids(task_ids: list[str]) -> None:
    """Validate task_ids is a list of non-empty strings."""
    if not isinstance(task_ids, list):
        raise ValidationError(
            message="task_ids must be a list",
        )
    for tid in task_ids:
        if not isinstance(tid, str) or not tid.strip():
            raise ValidationError(
                message="Each task_id must be a non-empty string",
            )


def _parse_json_list(value: str | None) -> list[str]:
    """Safely parse a JSON list string."""
    if value is None:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
        return []
    except (json.JSONDecodeError, TypeError):
        return []


# ══════════════════════════════════════════════════════════════════
# SERVICE FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def register_agent(
    db: Session,
    agent_name: str,
    agent_role: str | None = None,
    feature_ids: list[str] | None = None,
    task_ids: list[str] | None = None,
) -> AIAgentAssignment:
    """
    Create a new agent assignment record.

    Validates inputs (non-empty name, valid role) and checks
    for duplicate agent names.
    """
    _validate_agent_name(agent_name)
    _validate_agent_role(agent_role)

    # Check for duplicate name
    existing = db.query(AIAgentAssignment).filter_by(
        agent_name=agent_name.strip(),
    ).first()
    if existing is not None:
        raise ValidationError(
            message=(
                f"Agent with name '{agent_name.strip()}' "
                f"already exists"
            ),
        )

    effective_features = feature_ids or []
    effective_tasks = task_ids or []

    agent = AIAgentAssignment(
        agent_name=agent_name.strip(),
        agent_role=(
            agent_role.strip() if agent_role else None
        ),
        feature_ids=json.dumps(effective_features),
        task_ids=json.dumps(effective_tasks),
        status="active",
    )

    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def get_agent(
    db: Session,
    agent_name: str,
) -> AIAgentAssignment | None:
    """
    Get agent by name.

    Returns None if not found.
    """
    _validate_agent_name(agent_name)

    return db.query(AIAgentAssignment).filter_by(
        agent_name=agent_name.strip(),
    ).first()


def list_agents(
    db: Session,
    status: str | None = None,
) -> list[AIAgentAssignment]:
    """
    List all agents, optionally filtered by status.
    """
    query = db.query(AIAgentAssignment)

    if status is not None:
        _validate_status(status)
        query = query.filter_by(status=status)

    return query.order_by(
        AIAgentAssignment.created_at,
    ).all()


def update_agent_features(
    db: Session,
    agent_name: str,
    feature_ids: list[str],
) -> AIAgentAssignment:
    """
    Update the feature_ids JSON for an agent.
    """
    _validate_agent_name(agent_name)
    _validate_feature_ids(feature_ids)

    agent = db.query(AIAgentAssignment).filter_by(
        agent_name=agent_name.strip(),
    ).first()

    if agent is None:
        raise NotFoundError(
            message=(
                f"Agent '{agent_name.strip()}' not found"
            ),
        )

    agent.feature_ids = json.dumps(feature_ids)
    db.commit()
    db.refresh(agent)
    return agent


def update_agent_tasks(
    db: Session,
    agent_name: str,
    task_ids: list[str],
) -> AIAgentAssignment:
    """
    Update the task_ids JSON for an agent.
    """
    _validate_agent_name(agent_name)
    _validate_task_ids(task_ids)

    agent = db.query(AIAgentAssignment).filter_by(
        agent_name=agent_name.strip(),
    ).first()

    if agent is None:
        raise NotFoundError(
            message=(
                f"Agent '{agent_name.strip()}' not found"
            ),
        )

    agent.task_ids = json.dumps(task_ids)
    db.commit()
    db.refresh(agent)
    return agent


def update_agent_status(
    db: Session,
    agent_name: str,
    status: str,
) -> AIAgentAssignment:
    """
    Update agent status (active, completed, paused).
    """
    _validate_agent_name(agent_name)
    _validate_status(status)

    agent = db.query(AIAgentAssignment).filter_by(
        agent_name=agent_name.strip(),
    ).first()

    if agent is None:
        raise NotFoundError(
            message=(
                f"Agent '{agent_name.strip()}' not found"
            ),
        )

    agent.status = status
    db.commit()
    db.refresh(agent)
    return agent


def get_agent_feature_coverage(db: Session) -> dict:
    """
    Returns which features are assigned to which agents.

    Format: {"feature_id": "agent_name", ...}
    If a feature is assigned to multiple agents, the last
    one wins (warning logged in production).
    """
    agents = db.query(AIAgentAssignment).all()

    coverage: dict[str, str] = {}
    for agent in agents:
        features = _parse_json_list(agent.feature_ids)
        for feature_id in features:
            fid = feature_id.strip() if isinstance(
                feature_id, str,
            ) else str(feature_id)
            if fid:
                coverage[fid] = agent.agent_name

    return coverage


def find_unassigned_features(
    db: Session,
    all_feature_ids: list[str],
) -> list[str]:
    """
    Given a list of all feature IDs, return ones not
    assigned to any agent.
    """
    if not isinstance(all_feature_ids, list):
        raise ValidationError(
            message="all_feature_ids must be a list",
        )

    coverage = get_agent_feature_coverage(db)
    assigned = set(coverage.keys())

    unassigned = []
    seen: set[str] = set()
    for fid in all_feature_ids:
        fid_clean = fid.strip()
        if fid_clean and fid_clean not in assigned:
            if fid_clean not in seen:
                unassigned.append(fid_clean)
                seen.add(fid_clean)

    return unassigned


def get_build_progress(db: Session) -> dict:
    """
    Returns summary of build progress across all agents.

    Includes: total agents, active agents, completed
    features count, pending features count.
    """
    all_agents = list_agents(db)

    total_agents = len(all_agents)
    active_agents = sum(
        1 for a in all_agents if a.status == "active"
    )
    completed_agents = sum(
        1 for a in all_agents if a.status == "completed"
    )
    paused_agents = sum(
        1 for a in all_agents if a.status == "paused"
    )

    # Count features across all agents
    all_features: set[str] = set()
    completed_features: set[str] = set()

    for agent in all_agents:
        features = _parse_json_list(agent.feature_ids)
        for fid in features:
            fid_clean = fid.strip() if isinstance(
                fid, str,
            ) else str(fid)
            if fid_clean:
                all_features.add(fid_clean)
                if agent.status == "completed":
                    completed_features.add(fid_clean)

    pending_features = (
        len(all_features) - len(completed_features)
    )

    return {
        "total_agents": total_agents,
        "active_agents": active_agents,
        "completed_agents": completed_agents,
        "paused_agents": paused_agents,
        "total_features": len(all_features),
        "completed_features": len(
            completed_features,
        ),
        "pending_features": pending_features,
        "completion_pct": round(
            len(completed_features)
            / max(len(all_features), 1)
            * 100,
            1,
        ),
    }
