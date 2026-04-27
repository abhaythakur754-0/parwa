"""
PARWA Agent API Routes (Week 14 Day 4 — F-095, F-096)

FastAPI router endpoints for agent provisioning and dynamic instruction
management.

Endpoints:
F-095: Agent Provisioning
- POST /api/agents/create              — Create agent from config
- GET  /api/agents                     — List agents
- GET  /api/agents/{id}                — Get agent detail
- POST /api/agents/{id}/setup/complete — Complete agent setup
- GET  /api/agents/{id}/setup          — Get setup status

F-096: Dynamic Instructions
- GET    /api/instructions/sets              — List instruction sets
- POST   /api/instructions/sets              — Create instruction set
- PUT    /api/instructions/sets/{id}         — Update instruction set
- POST   /api/instructions/sets/{id}/publish — Publish instruction set
- POST   /api/instructions/sets/{id}/archive — Archive instruction set
- GET    /api/instructions/sets/{id}/versions — Get version history
- POST   /api/instructions/ab-tests          — Create A/B test
- GET    /api/instructions/ab-tests          — List A/B tests
- GET    /api/instructions/ab-tests/{id}     — Get A/B test detail
- POST   /api/instructions/ab-tests/{id}/stop — Stop A/B test

Building Codes: BC-001 (tenant isolation), BC-007 (AI model),
               BC-008 (state management), BC-009 (approval), BC-011 (auth),
               BC-012 (structured error responses)
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_company_id,
    require_roles,
)
from app.exceptions import (
    AuthorizationError,
    ValidationError,
)
from app.logger import get_logger
from database.base import get_db
from database.models.core import User

logger = get_logger("agents_api")

router = APIRouter()


# ══════════════════════════════════════════════════════════════════
# F-095: Agent Provisioning Endpoints
# ══════════════════════════════════════════════════════════════════


@router.post("/api/agents/create")
async def create_agent(
    request: Request,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new AI agent from configuration.

    Validates name uniqueness, plan limits, and specialty configuration.
    Financial specialties are flagged for admin approval (BC-009).

    F-095: Agent Provisioning
    BC-001: Scoped by company_id.
    BC-009: Financial actions flagged for approval.
    BC-011: Requires authentication.
    """
    try:
        body = await request.json()
    except Exception:
        raise ValidationError(
            message="Invalid JSON body",
            details={
                "expected": {
                    "name": "string (required)",
                    "specialty": "string (required)",
                    "description": "string (optional)",
                    "channels": ["string array (optional)"],
                    "permission_level": "string (optional, default: standard)",
                    "base_model": "string (optional)",
                }
            },
        )

    name = body.get("name", "").strip()
    if not name:
        raise ValidationError(
            message="Agent name is required",
            details={"field": "name"},
        )

    specialty = body.get("specialty", "").strip()
    if not specialty:
        raise ValidationError(
            message="Agent specialty is required",
            details={"field": "specialty"},
        )

    # Validate specialty
    valid_specialties = [
        "billing_specialist", "returns_specialist", "technical_support",
        "general_support", "sales_assistant", "onboarding_guide",
        "vip_concierge", "feedback_collector", "custom",
    ]
    if specialty not in valid_specialties:
        raise ValidationError(
            message=f"Invalid specialty: {specialty}",
            details={
                "field": "specialty",
                "valid_specialties": valid_specialties,
            },
        )

    # Validate permission level
    permission_level = body.get("permission_level", "standard")
    valid_levels = ("basic", "standard", "advanced", "admin")
    if permission_level not in valid_levels:
        raise ValidationError(
            message=f"Invalid permission level: {permission_level}",
            details={"field": "permission_level", "valid_levels": list(valid_levels)},
        )

    # Validate channels
    channels = body.get("channels", ["chat"])
    valid_channels = {"chat", "email", "sms", "voice"}
    for ch in channels:
        if ch not in valid_channels:
            raise ValidationError(
                message=f"Invalid channel: {ch}",
                details={
                    "field": "channels",
                    "valid_channels": list(valid_channels),
                },
            )

    config = {
        "name": name,
        "specialty": specialty,
        "description": body.get("description"),
        "channels": channels,
        "permission_level": permission_level,
        "base_model": body.get("base_model"),
        "custom_permissions": body.get("custom_permissions"),
        "requires_approval": False,
    }

    try:
        from app.services.agent_provisioning_service import (
            get_agent_provisioning_service,
        )

        svc = get_agent_provisioning_service(company_id)
        result = svc.create_agent(
            user_id=str(user.id),
            config=config,
            db=db,
        )

        logger.info(
            "agent_created_api",
            company_id=company_id,
            agent_id=result["agent"]["id"],
            agent_name=name,
            user_id=str(user.id),
        )

        return result

    except (ValidationError, AuthorizationError):
        raise
    except Exception as exc:
        logger.error(
            "agent_create_api_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


@router.get("/api/agents")
async def list_agents(
    status: Optional[str] = Query(
        None,
        description="Filter by status (initializing, training, active, paused, deprovisioned, error)",
    ),
    limit: int = Query(
        20, ge=1, le=100,
        description="Pagination limit",
    ),
    offset: int = Query(
        0, ge=0,
        description="Pagination offset",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List agents for the current tenant.

    Returns all agents (or filtered by status) with pagination.

    F-095: Agent Provisioning
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.agent_provisioning_service import (
            get_agent_provisioning_service,
        )

        svc = get_agent_provisioning_service(company_id)
        result = svc.list_agents(
            db=db,
            status_filter=status,
            limit=limit,
            offset=offset,
        )

        return result

    except Exception as exc:
        logger.error(
            "agent_list_api_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


@router.get("/api/agents/{agent_id}")
async def get_agent_detail(
    agent_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get detailed agent status including setup progress.

    F-095: Agent Provisioning
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    if not agent_id or not agent_id.strip():
        raise ValidationError(
            message="agent_id is required",
            details={"field": "agent_id"},
        )

    try:
        from app.services.agent_provisioning_service import (
            get_agent_provisioning_service,
        )

        svc = get_agent_provisioning_service(company_id)
        result = svc.get_agent_status(
            agent_id=agent_id.strip(),
            db=db,
        )

        return result

    except (ValidationError, Exception) as exc:
        from app.exceptions import NotFoundError
        if isinstance(exc, NotFoundError):
            raise
        logger.error(
            "agent_detail_api_error",
            company_id=company_id,
            agent_id=agent_id,
            error=str(exc),
        )
        raise


@router.post("/api/agents/{agent_id}/setup/complete")
async def complete_agent_setup(
    agent_id: str,
    request: Request,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Complete agent setup and activate.

    Marks all remaining setup steps as completed and transitions
    the agent to "active" status.

    F-095: Agent Provisioning
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    if not agent_id or not agent_id.strip():
        raise ValidationError(
            message="agent_id is required",
            details={"field": "agent_id"},
        )

    try:
        body = await request.json()
    except Exception:
        body = {}

    configuration = body.get("configuration", {})

    try:
        from app.services.agent_provisioning_service import (
            get_agent_provisioning_service,
        )

        svc = get_agent_provisioning_service(company_id)
        result = svc.complete_setup(
            agent_id=agent_id.strip(),
            configuration=configuration,
            db=db,
        )

        logger.info(
            "agent_setup_completed_api",
            company_id=company_id,
            agent_id=agent_id,
            user_id=str(user.id),
        )

        return result

    except (ValidationError, Exception) as exc:
        from app.exceptions import NotFoundError
        if isinstance(exc, (ValidationError, NotFoundError)):
            raise
        logger.error(
            "agent_setup_complete_api_error",
            company_id=company_id,
            agent_id=agent_id,
            error=str(exc),
        )
        raise


@router.get("/api/agents/{agent_id}/setup")
async def get_agent_setup_status(
    agent_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the setup progress for an agent.

    Returns step-by-step status of the agent setup process.

    F-095: Agent Provisioning
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    if not agent_id or not agent_id.strip():
        raise ValidationError(
            message="agent_id is required",
            details={"field": "agent_id"},
        )

    try:
        from app.services.agent_provisioning_service import (
            get_agent_provisioning_service,
        )

        svc = get_agent_provisioning_service(company_id)
        result = svc.get_setup_status(
            agent_id=agent_id.strip(),
            db=db,
        )

        return result

    except (ValidationError, Exception) as exc:
        from app.exceptions import NotFoundError
        if isinstance(exc, NotFoundError):
            raise
        logger.error(
            "agent_setup_status_api_error",
            company_id=company_id,
            agent_id=agent_id,
            error=str(exc),
        )
        raise


# ══════════════════════════════════════════════════════════════════
# F-096: Dynamic Instruction Workflow Endpoints
# ══════════════════════════════════════════════════════════════════


@router.get("/api/instructions/sets")
async def list_instruction_sets(
    agent_id: str = Query(
        ...,
        description="Agent ID to list instruction sets for",
    ),
    status: Optional[str] = Query(
        None,
        description="Filter by status (draft, active, archived)",
    ),
    limit: int = Query(
        20, ge=1, le=100,
        description="Pagination limit",
    ),
    offset: int = Query(
        0, ge=0,
        description="Pagination offset",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List instruction sets for an agent.

    F-096: Dynamic Instructions
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.instruction_workflow_service import (
            get_instruction_workflow_service,
        )

        svc = get_instruction_workflow_service(company_id)
        result = svc.get_instruction_sets(
            agent_id=agent_id,
            db=db,
            status_filter=status,
            limit=limit,
            offset=offset,
        )

        return result

    except Exception as exc:
        logger.error(
            "instruction_sets_list_api_error",
            company_id=company_id,
            agent_id=agent_id,
            error=str(exc),
        )
        raise


@router.post("/api/instructions/sets")
async def create_instruction_set(
    request: Request,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new instruction set.

    Creates a draft instruction set with behavioral rules, tone
    guidelines, escalation triggers, and response templates.

    F-096: Dynamic Instructions
    BC-001: Scoped by company_id.
    BC-007: AI model behavioral instructions.
    BC-011: Requires authentication.
    """
    try:
        body = await request.json()
    except Exception:
        raise ValidationError(
            message="Invalid JSON body",
            details={
                "expected": {
                    "name": "string (required)",
                    "agent_id": "string (required)",
                    "instructions": {
                        "behavioral_rules": ["string array"],
                        "tone_guidelines": {"formality": "string", "empathy_level": "string"},
                        "escalation_triggers": ["string array"],
                        "response_templates": {"greeting": "string", "closing": "string"},
                        "prohibited_actions": ["string array"],
                        "confidence_thresholds": {"auto_approve": 90, "require_review": 70},
                    },
                    "is_default": "boolean (optional, default: false)",
                }
            },
        )

    name = body.get("name", "").strip()
    if not name:
        raise ValidationError(
            message="Instruction set name is required",
            details={"field": "name"},
        )

    agent_id = body.get("agent_id", "").strip()
    if not agent_id:
        raise ValidationError(
            message="agent_id is required",
            details={"field": "agent_id"},
        )

    instructions = body.get("instructions", {})
    is_default = body.get("is_default", False)

    try:
        from app.services.instruction_workflow_service import (
            get_instruction_workflow_service,
        )

        svc = get_instruction_workflow_service(company_id)
        result = svc.create_instruction_set(
            agent_id=agent_id,
            name=name,
            instructions=instructions,
            user_id=str(user.id),
            db=db,
            is_default=is_default,
        )

        logger.info(
            "instruction_set_created_api",
            company_id=company_id,
            set_id=result["id"],
            agent_id=agent_id,
            user_id=str(user.id),
        )

        return result

    except (ValidationError, Exception) as exc:
        from app.exceptions import NotFoundError
        if isinstance(exc, (ValidationError, NotFoundError)):
            raise
        logger.error(
            "instruction_set_create_api_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


@router.put("/api/instructions/sets/{set_id}")
async def update_instruction_set(
    set_id: str,
    request: Request,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a draft instruction set.

    Only draft instruction sets can be updated.

    F-096: Dynamic Instructions
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    if not set_id or not set_id.strip():
        raise ValidationError(
            message="set_id is required",
            details={"field": "set_id"},
        )

    try:
        body = await request.json()
    except Exception:
        raise ValidationError(
            message="Invalid JSON body",
            details={
                "expected": {
                    "name": "string (optional)",
                    "instructions": "object (optional)",
                    "change_summary": "string (optional)",
                }
            },
        )

    try:
        from app.services.instruction_workflow_service import (
            get_instruction_workflow_service,
        )

        svc = get_instruction_workflow_service(company_id)
        result = svc.update_instruction_set(
            set_id=set_id.strip(),
            updates=body,
            user_id=str(user.id),
            db=db,
        )

        logger.info(
            "instruction_set_updated_api",
            company_id=company_id,
            set_id=set_id,
            user_id=str(user.id),
        )

        return result

    except (ValidationError, Exception) as exc:
        from app.exceptions import NotFoundError
        if isinstance(exc, (ValidationError, NotFoundError)):
            raise
        logger.error(
            "instruction_set_update_api_error",
            company_id=company_id,
            set_id=set_id,
            error=str(exc),
        )
        raise


@router.post("/api/instructions/sets/{set_id}/publish")
async def publish_instruction_set(
    set_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Publish an instruction set.

    Creates a new version, deactivates previously active sets
    for the same agent, and sets this set to "active".

    F-096: Dynamic Instructions
    BC-001: Scoped by company_id.
    BC-008: State management.
    BC-011: Requires authentication.
    """
    if not set_id or not set_id.strip():
        raise ValidationError(
            message="set_id is required",
            details={"field": "set_id"},
        )

    try:
        from app.services.instruction_workflow_service import (
            get_instruction_workflow_service,
        )

        svc = get_instruction_workflow_service(company_id)
        result = svc.publish_instruction_set(
            set_id=set_id.strip(),
            user_id=str(user.id),
            db=db,
        )

        logger.info(
            "instruction_set_published_api",
            company_id=company_id,
            set_id=set_id,
            new_version=result["new_version"],
            user_id=str(user.id),
        )

        return result

    except (ValidationError, Exception) as exc:
        from app.exceptions import NotFoundError
        if isinstance(exc, (ValidationError, NotFoundError)):
            raise
        logger.error(
            "instruction_set_publish_api_error",
            company_id=company_id,
            set_id=set_id,
            error=str(exc),
        )
        raise


@router.post("/api/instructions/sets/{set_id}/archive")
async def archive_instruction_set(
    set_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Archive an instruction set.

    F-096: Dynamic Instructions
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    if not set_id or not set_id.strip():
        raise ValidationError(
            message="set_id is required",
            details={"field": "set_id"},
        )

    try:
        from app.services.instruction_workflow_service import (
            get_instruction_workflow_service,
        )

        svc = get_instruction_workflow_service(company_id)
        result = svc.archive_instruction_set(
            set_id=set_id.strip(),
            db=db,
        )

        logger.info(
            "instruction_set_archived_api",
            company_id=company_id,
            set_id=set_id,
        )

        return result

    except (ValidationError, Exception) as exc:
        from app.exceptions import NotFoundError
        if isinstance(exc, (ValidationError, NotFoundError)):
            raise
        logger.error(
            "instruction_set_archive_api_error",
            company_id=company_id,
            set_id=set_id,
            error=str(exc),
        )
        raise


@router.get("/api/instructions/sets/{set_id}/versions")
async def get_version_history(
    set_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get version history for an instruction set.

    Returns all historical versions with change summaries.

    F-096: Dynamic Instructions
    BC-001: Scoped by company_id.
    BC-008: Full version history.
    BC-011: Requires authentication.
    """
    if not set_id or not set_id.strip():
        raise ValidationError(
            message="set_id is required",
            details={"field": "set_id"},
        )

    try:
        from app.services.instruction_workflow_service import (
            get_instruction_workflow_service,
        )

        svc = get_instruction_workflow_service(company_id)
        result = svc.get_version_history(
            set_id=set_id.strip(),
            db=db,
        )

        return result

    except (ValidationError, Exception) as exc:
        from app.exceptions import NotFoundError
        if isinstance(exc, (ValidationError, NotFoundError)):
            raise
        logger.error(
            "instruction_versions_api_error",
            company_id=company_id,
            set_id=set_id,
            error=str(exc),
        )
        raise


# ══════════════════════════════════════════════════════════════════
# F-096: A/B Testing Endpoints
# ══════════════════════════════════════════════════════════════════


@router.post("/api/instructions/ab-tests")
async def create_ab_test(
    request: Request,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new A/B test between two instruction sets.

    Only one active A/B test per agent at a time.
    Returns HTTP 409 if a test is already running.

    F-096: Dynamic Instructions — A/B Testing
    BC-001: Scoped by company_id.
    BC-007: AI model optimization.
    BC-011: Requires authentication.
    """
    try:
        body = await request.json()
    except Exception:
        raise ValidationError(
            message="Invalid JSON body",
            details={
                "expected": {
                    "agent_id": "string (required)",
                    "set_a_id": "string (required)",
                    "set_b_id": "string (required)",
                    "traffic_split": "integer 0-100 (optional, default: 50)",
                    "success_metric": "string (optional: csat, resolution_rate, both)",
                    "duration_days": "integer 1-90 (optional, default: 14)",
                }
            },
        )

    agent_id = body.get("agent_id", "").strip()
    if not agent_id:
        raise ValidationError(
            message="agent_id is required",
            details={"field": "agent_id"},
        )

    set_a_id = body.get("set_a_id", "").strip()
    if not set_a_id:
        raise ValidationError(
            message="set_a_id is required",
            details={"field": "set_a_id"},
        )

    set_b_id = body.get("set_b_id", "").strip()
    if not set_b_id:
        raise ValidationError(
            message="set_b_id is required",
            details={"field": "set_b_id"},
        )

    traffic_split = body.get("traffic_split", 50)
    if not isinstance(traffic_split, int) or \
       traffic_split < 0 or traffic_split > 100:
        raise ValidationError(
            message="traffic_split must be an integer between 0 and 100",
            details={"field": "traffic_split"},
        )

    success_metric = body.get("success_metric", "csat")
    duration_days = body.get("duration_days", 14)
    if not isinstance(duration_days, int) or \
       duration_days < 1 or duration_days > 90:
        raise ValidationError(
            message="duration_days must be an integer between 1 and 90",
            details={"field": "duration_days"},
        )

    try:
        from app.services.instruction_workflow_service import (
            get_instruction_workflow_service,
        )

        svc = get_instruction_workflow_service(company_id)
        result = svc.create_ab_test(
            agent_id=agent_id,
            set_a_id=set_a_id,
            set_b_id=set_b_id,
            traffic_split=traffic_split,
            success_metric=success_metric,
            duration_days=duration_days,
            user_id=str(user.id),
            db=db,
        )

        logger.info(
            "ab_test_created_api",
            company_id=company_id,
            test_id=result["id"],
            agent_id=agent_id,
            user_id=str(user.id),
        )

        return result

    except (ValidationError, Exception) as exc:
        from app.exceptions import NotFoundError
        if isinstance(exc, (ValidationError, NotFoundError)):
            raise
        logger.error(
            "ab_test_create_api_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


@router.get("/api/instructions/ab-tests")
async def list_ab_tests(
    agent_id: str = Query(
        ...,
        description="Agent ID to list A/B tests for",
    ),
    status: Optional[str] = Query(
        None,
        description="Filter by status (running, completed, cancelled)",
    ),
    limit: int = Query(
        20, ge=1, le=100,
        description="Pagination limit",
    ),
    offset: int = Query(
        0, ge=0,
        description="Pagination offset",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List A/B tests for an agent.

    F-096: Dynamic Instructions — A/B Testing
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.instruction_workflow_service import (
            get_instruction_workflow_service,
        )

        svc = get_instruction_workflow_service(company_id)
        result = svc.list_ab_tests(
            agent_id=agent_id,
            db=db,
            status_filter=status,
            limit=limit,
            offset=offset,
        )

        return result

    except Exception as exc:
        logger.error(
            "ab_tests_list_api_error",
            company_id=company_id,
            agent_id=agent_id,
            error=str(exc),
        )
        raise


@router.get("/api/instructions/ab-tests/{test_id}")
async def get_ab_test_detail(
    test_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get A/B test detail with set names and evaluation.

    F-096: Dynamic Instructions — A/B Testing
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    if not test_id or not test_id.strip():
        raise ValidationError(
            message="test_id is required",
            details={"field": "test_id"},
        )

    try:
        from app.services.instruction_workflow_service import (
            get_instruction_workflow_service,
        )

        svc = get_instruction_workflow_service(company_id)
        result = svc.get_ab_test(
            test_id=test_id.strip(),
            db=db,
        )

        return result

    except (ValidationError, Exception) as exc:
        from app.exceptions import NotFoundError
        if isinstance(exc, (ValidationError, NotFoundError)):
            raise
        logger.error(
            "ab_test_detail_api_error",
            company_id=company_id,
            test_id=test_id,
            error=str(exc),
        )
        raise


@router.post("/api/instructions/ab-tests/{test_id}/stop")
async def stop_ab_test(
    test_id: str,
    request: Request,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stop an A/B test, optionally selecting a winner.

    If no winner is specified, the system auto-selects based on
    statistical evaluation (if significant).

    F-096: Dynamic Instructions — A/B Testing
    BC-001: Scoped by company_id.
    BC-007: AI model optimization.
    BC-011: Requires authentication.
    """
    if not test_id or not test_id.strip():
        raise ValidationError(
            message="test_id is required",
            details={"field": "test_id"},
        )

    try:
        body = await request.json()
    except Exception:
        body = {}

    winner_id = body.get("winner_id")

    try:
        from app.services.instruction_workflow_service import (
            get_instruction_workflow_service,
        )

        svc = get_instruction_workflow_service(company_id)
        result = svc.stop_ab_test(
            test_id=test_id.strip(),
            winner_id=winner_id,
            db=db,
        )

        logger.info(
            "ab_test_stopped_api",
            company_id=company_id,
            test_id=test_id,
            winner_id=result.get("winner_id"),
            user_id=str(user.id),
        )

        return result

    except (ValidationError, Exception) as exc:
        from app.exceptions import NotFoundError
        if isinstance(exc, (ValidationError, NotFoundError)):
            raise
        logger.error(
            "ab_test_stop_api_error",
            company_id=company_id,
            test_id=test_id,
            error=str(exc),
        )
        raise
