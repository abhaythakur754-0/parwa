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
from app.exceptions import (
    ValidationError,
    NotFoundError,
)


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

VALID_STATUSES = {"active", "completed", "paused", "inactive"}

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


# ══════════════════════════════════════════════════════════════════
# SG-21 / SG-22: EXTENDED SERVICE FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def get_all_agents(
    db: Session,
    status: str | None = None,
) -> list[AIAgentAssignment]:
    """List all agent assignments, optionally filtered by status.

    SG-22: Wraps list_agents for API layer compatibility.
    """
    return list_agents(db, status=status)


def get_agent_by_id(
    db: Session,
    agent_id: str,
) -> AIAgentAssignment:
    """Get a single agent by its UUID."""
    if not agent_id or not agent_id.strip():
        raise ValidationError(
            message="agent_id is required and cannot be empty",
        )
    agent = db.query(AIAgentAssignment).filter(
        AIAgentAssignment.id == agent_id.strip(),
    ).first()
    if agent is None:
        raise NotFoundError(
            message=f"Agent with id '{agent_id.strip()}' not found",
            details={"agent_id": agent_id.strip()},
        )
    return agent


def get_agent_for_feature(
    db: Session,
    feature_id: str,
) -> AIAgentAssignment | None:
    """Find which agent owns a specific feature.

    Searches all active agents' feature_ids JSON arrays
    for the given feature_id.

    Returns None if no agent owns the feature.
    """
    if not feature_id or not feature_id.strip():
        raise ValidationError(
            message="feature_id is required and cannot be empty",
        )

    fid = feature_id.strip()
    agents = db.query(AIAgentAssignment).filter(
        AIAgentAssignment.status == "active",
    ).all()

    for agent in agents:
        features = _parse_json_list(agent.feature_ids)
        for f in features:
            f_clean = f.strip() if isinstance(f, str) else str(f)
            if f_clean == fid:
                return agent

    return None


def create_agent(
    db: Session,
    agent_name: str,
    agent_role: str | None = None,
    feature_ids: list[str] | None = None,
    task_ids: list[str] | None = None,
) -> AIAgentAssignment:
    """Create a new agent assignment.

    SG-22: Alias for register_agent with explicit parameter names.
    Validates inputs and checks for duplicate agent names.
    """
    return register_agent(
        db=db,
        agent_name=agent_name,
        agent_role=agent_role,
        feature_ids=feature_ids,
        task_ids=task_ids,
    )


def update_agent_by_id(
    db: Session,
    agent_id: str,
    **kwargs: object,
) -> AIAgentAssignment:
    """Update an agent assignment by ID.

    Accepts any combination of: agent_name, agent_role,
    feature_ids (list), task_ids (list), status.
    """
    if not agent_id or not agent_id.strip():
        raise ValidationError(
            message="agent_id is required and cannot be empty",
        )

    agent = db.query(AIAgentAssignment).filter(
        AIAgentAssignment.id == agent_id.strip(),
    ).first()
    if agent is None:
        raise NotFoundError(
            message=f"Agent with id '{agent_id.strip()}' not found",
            details={"agent_id": agent_id.strip()},
        )

    allowed_fields = {
        "agent_name", "agent_role", "feature_ids",
        "task_ids", "status",
    }

    for field, value in kwargs.items():
        if field not in allowed_fields:
            raise ValidationError(
                message=(
                    f"Invalid field '{field}'. "
                    f"Allowed: {', '.join(sorted(allowed_fields))}"
                ),
            )

        if field == "agent_name":
            _validate_agent_name(str(value))
            agent.agent_name = str(value).strip()

        elif field == "agent_role":
            _validate_agent_role(str(value) if value else None)
            agent.agent_role = (
                str(value).strip() if value else None
            )

        elif field == "feature_ids":
            _validate_feature_ids(list(value))  # type: ignore[arg-type]
            agent.feature_ids = json.dumps(list(value))

        elif field == "task_ids":
            _validate_task_ids(list(value))  # type: ignore[arg-type]
            agent.task_ids = json.dumps(list(value))

        elif field == "status":
            _validate_status(str(value))
            agent.status = str(value)

    from datetime import datetime as dt
    agent.updated_at = dt.utcnow()
    db.commit()
    db.refresh(agent)
    return agent


def delete_agent(
    db: Session,
    agent_id: str,
) -> AIAgentAssignment:
    """Soft-delete an agent by setting status='inactive'."""
    if not agent_id or not agent_id.strip():
        raise ValidationError(
            message="agent_id is required and cannot be empty",
        )

    agent = db.query(AIAgentAssignment).filter(
        AIAgentAssignment.id == agent_id.strip(),
    ).first()
    if agent is None:
        raise NotFoundError(
            message=f"Agent with id '{agent_id.strip()}' not found",
            details={"agent_id": agent_id.strip()},
        )

    agent.status = "inactive"
    from datetime import datetime as dt
    agent.updated_at = dt.utcnow()
    db.commit()
    db.refresh(agent)
    return agent


def get_task_decomposition_summary(db: Session) -> dict:
    """SG-21: Return task decomposition summary.

    Computes:
    - total_agents: number of active agents
    - total_features_mapped: unique features across all active agents
    - total_tasks_mapped: unique tasks across all active agents
    - agents: per-agent breakdown with feature/task counts
    - coverage_stats: agent distribution overview
    """
    active_agents = list_agents(db, status="active")

    all_features: set[str] = set()
    all_tasks: set[str] = set()
    agent_breakdown = []

    for agent in active_agents:
        features = _parse_json_list(agent.feature_ids)
        tasks = _parse_json_list(agent.task_ids)

        unique_features = set()
        for f in features:
            f_clean = f.strip() if isinstance(f, str) else str(f)
            if f_clean:
                unique_features.add(f_clean)
                all_features.add(f_clean)

        unique_tasks = set()
        for t in tasks:
            t_clean = t.strip() if isinstance(t, str) else str(t)
            if t_clean:
                unique_tasks.add(t_clean)
                all_tasks.add(t_clean)

        agent_breakdown.append({
            "id": agent.id,
            "agent_name": agent.agent_name,
            "agent_role": agent.agent_role,
            "feature_count": len(unique_features),
            "task_count": len(unique_tasks),
            "feature_ids": sorted(unique_features),
            "task_ids": sorted(unique_tasks),
            "status": agent.status,
        })

    # Find features assigned to multiple agents
    feature_agent_count: dict[str, list[str]] = {}
    for ab in agent_breakdown:
        for fid in ab["feature_ids"]:
            feature_agent_count.setdefault(fid, []).append(
                ab["agent_name"],
            )
    overlapping_features = {
        fid: names
        for fid, names in feature_agent_count.items()
        if len(names) > 1
    }

    return {
        "total_agents": len(active_agents),
        "total_features_mapped": len(all_features),
        "total_tasks_mapped": len(all_tasks),
        "agents": agent_breakdown,
        "coverage_stats": {
            "features_per_agent": {
                ab["agent_name"]: ab["feature_count"]
                for ab in agent_breakdown
            },
            "tasks_per_agent": {
                ab["agent_name"]: ab["task_count"]
                for ab in agent_breakdown
            },
            "overlapping_features": overlapping_features,
            "avg_features_per_agent": round(
                len(all_features)
                / max(len(active_agents), 1),
                1,
            ),
        },
    }


# ── Default Agent Definitions ───────────────────────────────────

_DEFAULT_AGENTS = [
    {
        "agent_name": "Agent 1",
        "agent_role": "Infrastructure",
        "feature_ids": [
            "F-055", "F-056", "F-064",
            "SG-28", "SG-32", "SG-33", "SG-15",
        ],
        "task_ids": ["SG-30"],
    },
    {
        "agent_name": "Agent 2",
        "agent_role": "Routing & Classification",
        "feature_ids": [
            "F-054", "SG-03", "F-059", "SG-04",
            "F-050", "SG-06", "SG-11", "F-053",
            "F-060", "SG-18", "SG-07", "SG-08",
            "SG-10", "SG-02", "BC-013",
        ],
        "task_ids": [],
    },
    {
        "agent_name": "Agent 3",
        "agent_role": "Safety & Guardrails",
        "feature_ids": [
            "SG-05", "F-057", "SG-36", "SG-27",
            "F-058", "SG-09", "F-067", "F-068", "F-069",
        ],
        "task_ids": [],
    },
    {
        "agent_name": "Agent 4",
        "agent_role": "Optimization & Data",
        "feature_ids": [
            "SG-35", "SG-21", "SG-22", "SG-24",
            "SG-25", "SG-26", "F-061", "SG-12", "SG-17",
        ],
        "task_ids": [],
    },
    {
        "agent_name": "Agent 5",
        "agent_role": "Operations & Monitoring",
        "feature_ids": [
            "SG-38", "SG-19", "SG-20", "SG-13",
            "SG-16", "SG-29", "SG-23", "SG-31",
            "SG-34", "SG-14",
        ],
        "task_ids": [],
    },
]


def initialize_default_agents(db: Session) -> dict:
    """SG-22: Seed the 5 default build agents (idempotent).

    Creates default agents only if they do not already exist.
    Returns a summary of created vs existing agents.
    """
    created = []
    existing = []

    for spec in _DEFAULT_AGENTS:
        name = spec["agent_name"]
        agent = db.query(AIAgentAssignment).filter_by(
            agent_name=name,
        ).first()

        if agent is not None:
            existing.append(name)
        else:
            new_agent = AIAgentAssignment(
                agent_name=name,
                agent_role=spec["agent_role"],
                feature_ids=json.dumps(spec["feature_ids"]),
                task_ids=json.dumps(spec["task_ids"]),
                status="active",
            )
            db.add(new_agent)
            created.append(name)

    if created:
        db.commit()

    return {
        "created": created,
        "already_existed": existing,
        "total_default_agents": len(_DEFAULT_AGENTS),
        "total_created": len(created),
    }
