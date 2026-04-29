"""
PARWA Jarvis Ops API Routes (Week 14 Day 2-3 — Jarvis Command Center)

FastAPI router endpoints for Week 14 Day 2-3 features:
- Quick Command Buttons (F-090)
- Error Panel (F-091)
- Train from Error (F-092)
- Self-Healing Orchestrator (F-093)
- Trust Preservation Protocol (F-094)

Endpoints:
- GET  /api/jarvis/quick-commands             — List quick commands
- POST /api/jarvis/quick-commands/{id}/execute  — Execute quick command
- GET  /api/jarvis/quick-commands/custom        — Get custom command configs
- PUT  /api/jarvis/quick-commands/custom/{id}    — Update custom command config
- GET  /api/errors/recent                       — Get recent errors
- GET  /api/errors/{error_id}                   — Get error detail
- POST /api/errors/{error_id}/dismiss          — Dismiss error
- GET  /api/errors/stats                        — Error statistics
- POST /api/errors/{error_id}/train            — Create training point
- GET  /api/training-points                     — List training points
- POST /api/training-points/{id}/review        — Review training point
- GET  /api/training-points/stats              — Training statistics
- GET  /api/jarvis/self-healing/status          — Self-healing status (F-093)
- GET  /api/jarvis/self-healing/history          — Healing event history (F-093)
- POST /api/jarvis/self-healing/trigger          — Trigger healing action (F-093)
- GET  /api/jarvis/self-healing/actions          — List healing actions (F-093)
- GET  /api/jarvis/trust-protocol/status        — Trust protocol status (F-094)
- POST /api/jarvis/trust-protocol/mode           — Set protocol mode (F-094)
- GET  /api/jarvis/trust-protocol/history        — Protocol transition history (F-094)
- GET  /api/jarvis/trust-protocol/recovery       — Recovery estimate (F-094)

Building Codes: BC-001 (tenant isolation), BC-005 (real-time),
               BC-011 (auth), BC-012 (error handling, structured responses)
"""

from typing import Optional

from app.api.deps import (
    get_company_id,
    get_current_user,
)
from app.exceptions import (
    AuthorizationError,
    ValidationError,
)
from app.logger import get_logger
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from database.base import get_db
from database.models.core import User

logger = get_logger("jarvis_ops_api")

router = APIRouter()


# ══════════════════════════════════════════════════════════════════
# F-090: Quick Command Buttons Endpoints
# ══════════════════════════════════════════════════════════════════


@router.get("/api/jarvis/quick-commands")
async def list_quick_commands(
    category: Optional[str] = Query(
        None,
        description="Filter by category (system_ops, agent_mgmt, ticket_ops, analytics, emergency)",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List quick commands available for the current tenant.

    Returns all enabled quick commands, merged with tenant-specific
    customizations (labels, params, enable/disable). Grouped by category.

    F-090: Quick Command Buttons
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.quick_command_service import get_quick_commands

        result = get_quick_commands(
            company_id=company_id,
            db=db,
            category=category,
        )

        return result

    except Exception as exc:
        logger.error(
            "quick_commands_list_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


@router.post("/api/jarvis/quick-commands/{command_id}/execute")
async def execute_quick_command(
    command_id: str,
    request: Request,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute a quick command by ID.

    Looks up the command definition, optionally merges request body
    params, and delegates to the jarvis_command_parser.

    F-090: Quick Command Buttons
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    BC-012: Some commands require admin role.
    """
    try:
        from app.services.quick_command_service import (
            QUICK_COMMANDS,
            execute_quick_command,
        )

        # Check admin requirement
        cmd_def = next(
            (c for c in QUICK_COMMANDS if c["id"] == command_id),
            None,
        )
        if cmd_def and cmd_def.get("requires_admin"):
            if user.role not in ("owner", "admin"):
                raise AuthorizationError(
                    message="This command requires admin privileges",
                    details={"command_id": command_id},
                )

        # Parse optional params from request body
        params = {}
        try:
            body = await request.json()
            params = body.get("params", {})
        except Exception:
            pass

        result = execute_quick_command(
            command_id=command_id,
            company_id=company_id,
            db=db,
            params=params,
        )

        logger.info(
            "quick_command_executed",
            company_id=company_id,
            command_id=command_id,
            user_id=str(user.id),
        )

        return result

    except (AuthorizationError, ValidationError):
        raise
    except Exception as exc:
        logger.error(
            "quick_command_execute_error",
            company_id=company_id,
            command_id=command_id,
            error=str(exc),
        )
        raise


@router.get("/api/jarvis/quick-commands/custom")
async def get_custom_commands(
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all custom command configurations for the current tenant.

    F-090: Quick Command Buttons
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.quick_command_service import get_custom_commands

        configs = get_custom_commands(
            company_id=company_id,
            db=db,
        )

        return {"configs": configs, "total": len(configs)}

    except Exception as exc:
        logger.error(
            "custom_commands_get_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


@router.put("/api/jarvis/quick-commands/custom/{command_id}")
async def update_custom_command(
    command_id: str,
    request: Request,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update a custom command configuration.

    Allows tenants to enable/disable commands, set custom labels,
    and override parameters.

    F-090: Quick Command Buttons
    BC-001: Scoped by company_id.
    BC-011: Requires authentication (admin for some commands).
    """
    try:
        body = await request.json()
    except Exception:
        raise ValidationError(
            message="Invalid JSON body",
            details={
                "expected": {
                    "enabled": "boolean (optional)",
                    "custom_label": "string (optional)",
                    "custom_params": "object (optional)",
                }
            },
        )

    enabled = body.get("enabled")
    custom_label = body.get("custom_label")
    custom_params = body.get("custom_params")

    # Admin-only fields
    if enabled is False:
        if user.role not in ("owner", "admin"):
            raise AuthorizationError(
                message="Disabling commands requires admin privileges",
                details={"command_id": command_id},
            )

    try:
        from app.services.quick_command_service import update_custom_commands

        result = update_custom_commands(
            company_id=company_id,
            db=db,
            command_id=command_id,
            enabled=enabled,
            custom_label=custom_label,
            custom_params=custom_params,
        )

        logger.info(
            "custom_command_updated",
            company_id=company_id,
            command_id=command_id,
            user_id=str(user.id),
        )

        return result

    except (AuthorizationError, ValidationError):
        raise
    except Exception as exc:
        logger.error(
            "custom_command_update_error",
            company_id=company_id,
            command_id=command_id,
            error=str(exc),
        )
        raise


# ══════════════════════════════════════════════════════════════════
# F-091: Error Panel Endpoints
# ══════════════════════════════════════════════════════════════════


@router.get("/api/errors/recent")
async def get_recent_errors(
    limit: int = Query(
        5,
        ge=1,
        le=100,
        description="Number of errors to return (default 5)",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Pagination offset",
    ),
    severity: Optional[str] = Query(
        None,
        description="Filter by severity (debug, info, warning, error, critical)",
    ),
    subsystem: Optional[str] = Query(
        None,
        description="Filter by subsystem name",
    ),
    from_date: Optional[str] = Query(
        None,
        description="ISO 8601 start date filter",
    ),
    to_date: Optional[str] = Query(
        None,
        description="ISO 8601 end date filter",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get recent errors for the Error Panel.

    Returns non-dismissed errors with grouping for identical errors,
    plus error storm detection alerts.

    F-091: Error Panel
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.error_panel_service import get_recent_errors

        result = get_recent_errors(
            company_id=company_id,
            db=db,
            limit=limit,
            offset=offset,
            severity=severity,
            subsystem=subsystem,
            from_date=from_date,
            to_date=to_date,
        )

        return result

    except Exception as exc:
        logger.error(
            "errors_recent_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


@router.get("/api/errors/{error_id}")
async def get_error_detail(
    error_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full detail for a single error.

    Includes the complete stack trace and all metadata.

    F-091: Error Panel
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    if not error_id or not error_id.strip():
        raise ValidationError(
            message="error_id is required",
            details={"field": "error_id"},
        )

    try:
        from app.services.error_panel_service import get_error_detail

        result = get_error_detail(
            error_id=error_id,
            company_id=company_id,
            db=db,
        )

        if "error" in result and result.get("error") == "Error not found":
            from app.exceptions import NotFoundError

            raise NotFoundError(
                message="Error not found",
                details={"error_id": error_id},
            )

        return result

    except (ValidationError, Exception) as exc:
        from app.exceptions import NotFoundError

        if isinstance(exc, NotFoundError):
            raise
        logger.error(
            "error_detail_error",
            company_id=company_id,
            error_id=error_id,
            error=str(exc),
        )
        raise


@router.post("/api/errors/{error_id}/dismiss")
async def dismiss_error(
    error_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dismiss an error from the Error Panel.

    Soft-deletes the error (preserves in database for audit).
    The error will no longer appear in the panel.

    F-091: Error Panel
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    if not error_id or not error_id.strip():
        raise ValidationError(
            message="error_id is required",
            details={"field": "error_id"},
        )

    try:
        from app.services.error_panel_service import dismiss_error

        result = dismiss_error(
            error_id=error_id,
            company_id=company_id,
            user_id=str(user.id),
            db=db,
        )

        logger.info(
            "error_dismissed",
            company_id=company_id,
            error_id=error_id,
            dismissed_by=str(user.id),
        )

        return result

    except Exception as exc:
        logger.error(
            "error_dismiss_error",
            company_id=company_id,
            error_id=error_id,
            error=str(exc),
        )
        raise


@router.get("/api/errors/stats")
async def get_error_stats(
    hours: int = Query(
        24,
        ge=1,
        le=720,
        description="Time window in hours (default 24)",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get aggregated error statistics for the Error Panel.

    Returns counts by severity, subsystem, error type, and
    error storm detection alerts.

    F-091: Error Panel
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.error_panel_service import get_error_stats

        result = get_error_stats(
            company_id=company_id,
            db=db,
            hours=hours,
        )

        return result

    except Exception as exc:
        logger.error(
            "error_stats_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


# ══════════════════════════════════════════════════════════════════
# F-092: Train from Error Endpoints
# ══════════════════════════════════════════════════════════════════


@router.post("/api/errors/{error_id}/train")
async def create_training_from_error(
    error_id: str,
    request: Request,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a training data point from an error entry.

    Converts an error into a training data point for AI model
    improvement. PII is automatically redacted (BC-010).

    F-092: Train from Error
    BC-001: Scoped by company_id.
    BC-007: AI model training data.
    BC-010: PII redaction on training data.
    BC-011: Requires authentication.
    """
    if not error_id or not error_id.strip():
        raise ValidationError(
            message="error_id is required",
            details={"field": "error_id"},
        )

    try:
        body = await request.json()
    except Exception:
        body = {}

    ticket_id = body.get("ticket_id")
    correction_notes = body.get("correction_notes")
    expected_response = body.get("expected_response")
    source = body.get("source", "error_manual")

    try:
        from app.services.train_from_error_service import create_training_point

        result = create_training_point(
            company_id=company_id,
            db=db,
            error_id=error_id,
            created_by=str(user.id),
            ticket_id=ticket_id,
            correction_notes=correction_notes,
            expected_response=expected_response,
            source=source,
        )

        logger.info(
            "training_point_created_from_error",
            company_id=company_id,
            error_id=error_id,
            user_id=str(user.id),
        )

        return result

    except Exception as exc:
        logger.error(
            "train_from_error_create_error",
            company_id=company_id,
            error_id=error_id,
            error=str(exc),
        )
        raise


@router.get("/api/training-points")
async def list_training_points(
    limit: int = Query(
        20,
        ge=1,
        le=100,
        description="Pagination limit",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Pagination offset",
    ),
    status: Optional[str] = Query(
        None,
        description="Filter by status",
    ),
    source: Optional[str] = Query(
        None,
        description="Filter by source",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List training data points with optional filters.

    F-092: Train from Error
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.train_from_error_service import get_training_points

        result = get_training_points(
            company_id=company_id,
            db=db,
            limit=limit,
            offset=offset,
            status=status,
            source=source,
        )

        return result

    except Exception as exc:
        logger.error(
            "training_points_list_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


@router.post("/api/training-points/{training_point_id}/review")
async def review_training_point(
    training_point_id: str,
    request: Request,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Review a training data point (approve, reject, or needs revision).

    F-092: Train from Error
    BC-001: Scoped by company_id.
    BC-007: AI model training data pipeline.
    BC-011: Requires authentication.
    """
    if not training_point_id or not training_point_id.strip():
        raise ValidationError(
            message="training_point_id is required",
            details={"field": "training_point_id"},
        )

    try:
        body = await request.json()
    except Exception:
        raise ValidationError(
            message="Invalid JSON body",
            details={
                "expected": {
                    "action": "string (approved/rejected/needs_revision)",
                    "review_notes": "string (optional)",
                }
            },
        )

    action = body.get("action", "")
    review_notes = body.get("review_notes")

    if not action or action.strip() not in ("approved", "rejected", "needs_revision"):
        raise ValidationError(
            message="action is required and must be one of: approved, rejected, needs_revision",
            details={"field": "action"},
        )

    try:
        from app.services.train_from_error_service import review_training_point

        result = review_training_point(
            training_point_id=training_point_id,
            company_id=company_id,
            db=db,
            reviewer_id=str(user.id),
            action=action.strip(),
            review_notes=review_notes,
        )

        logger.info(
            "training_point_reviewed",
            company_id=company_id,
            training_point_id=training_point_id,
            action=action,
            reviewer_id=str(user.id),
        )

        return result

    except (ValidationError, Exception) as exc:
        if isinstance(exc, ValidationError):
            raise
        logger.error(
            "training_point_review_error",
            company_id=company_id,
            training_point_id=training_point_id,
            error=str(exc),
        )
        raise


@router.get("/api/training-points/stats")
async def get_training_stats(
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get aggregated training pipeline statistics.

    Returns counts by status, source, intent label, and
    review activity metrics.

    F-092: Train from Error
    BC-001: Scoped by company_id.
    BC-007: AI model training data pipeline.
    BC-011: Requires authentication.
    """
    try:
        from app.services.train_from_error_service import get_training_stats

        result = get_training_stats(
            company_id=company_id,
            db=db,
        )

        return result

    except Exception as exc:
        logger.error(
            "training_stats_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


# ══════════════════════════════════════════════════════════════════
# F-093: Self-Healing Orchestrator Endpoints
# ══════════════════════════════════════════════════════════════════


@router.get("/api/jarvis/self-healing/status")
async def get_self_healing_status(
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
):
    """Get the current self-healing orchestrator status.

    Returns active healings, 24h statistics, registered action count,
    and healing outcome breakdown.

    F-093: Self-Healing Orchestrator
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.self_healing_orchestrator import (
            get_self_healing_orchestrator,
        )

        orchestrator = get_self_healing_orchestrator(company_id)
        result = await orchestrator.get_healing_status()

        return result

    except Exception as exc:
        logger.error(
            "self_healing_status_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


@router.get("/api/jarvis/self-healing/history")
async def get_self_healing_history(
    limit: int = Query(
        50,
        ge=1,
        le=200,
        description="Number of events to return",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Pagination offset",
    ),
    action_name: Optional[str] = Query(
        None,
        description="Filter by healing action name",
    ),
    outcome: Optional[str] = Query(
        None,
        description="Filter by outcome (success/failed/requires_confirmation)",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
):
    """Get the self-healing event history.

    Returns a paginated list of healing events from the audit log,
    with optional filters by action name and outcome.

    F-093: Self-Healing Orchestrator
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.self_healing_orchestrator import (
            get_self_healing_orchestrator,
        )

        orchestrator = get_self_healing_orchestrator(company_id)
        result = await orchestrator.get_healing_history(
            limit=limit,
            offset=offset,
            action_name=action_name,
            outcome=outcome,
        )

        return result

    except Exception as exc:
        logger.error(
            "self_healing_history_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


@router.post("/api/jarvis/self-healing/trigger")
async def trigger_healing_action(
    request: Request,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
):
    """Manually trigger a healing action (admin only).

    Allows admins to force-trigger a specific healing action,
    bypassing the automatic cooldown period. The action is
    audit-logged with the admin's user ID.

    F-093: Self-Healing Orchestrator
    BC-001: Scoped by company_id.
    BC-011: Requires admin authentication.
    BC-012: Audit-logged.
    """
    if user.role not in ("owner", "admin"):
        raise AuthorizationError(
            message="Healing action triggers require admin privileges",
            details={"required_role": "admin"},
        )

    try:
        body = await request.json()
    except Exception:
        raise ValidationError(
            message="Invalid JSON body",
            details={
                "expected": {
                    "action_name": "string (required)",
                    "context": "object (optional)",
                }
            },
        )

    action_name = body.get("action_name")
    if not action_name or not action_name.strip():
        raise ValidationError(
            message="action_name is required",
            details={"field": "action_name"},
        )

    context = body.get("context")

    try:
        from app.services.self_healing_orchestrator import (
            get_self_healing_orchestrator,
        )

        orchestrator = get_self_healing_orchestrator(company_id)
        result = await orchestrator.manual_trigger(
            action_name=action_name.strip(),
            triggered_by=str(user.id),
            context=context,
        )

        if "error" in result and result.get("error"):
            from app.exceptions import NotFoundError

            raise NotFoundError(
                message=result["error"],
                details={
                    "action_name": action_name,
                    "available_actions": result.get(
                        "available_actions",
                        [],
                    ),
                },
            )

        logger.info(
            "self_healing_manual_trigger",
            company_id=company_id,
            action_name=action_name,
            user_id=str(user.id),
        )

        return result

    except (AuthorizationError, ValidationError, Exception) as exc:
        from app.exceptions import NotFoundError

        if isinstance(exc, (AuthorizationError, ValidationError, NotFoundError)):
            raise
        logger.error(
            "self_healing_trigger_error",
            company_id=company_id,
            action_name=action_name,
            error=str(exc),
        )
        raise


@router.get("/api/jarvis/self-healing/actions")
async def list_healing_actions(
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
):
    """List all registered self-healing actions.

    Returns the definition of each healing action including
    name, description, risk level, and whether it requires
    admin confirmation.

    F-093: Self-Healing Orchestrator
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.self_healing_orchestrator import (
            get_self_healing_orchestrator,
        )

        orchestrator = get_self_healing_orchestrator(company_id)
        actions = orchestrator.get_registered_actions()

        return {
            "actions": actions,
            "total": len(actions),
        }

    except Exception as exc:
        logger.error(
            "self_healing_actions_list_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


# ══════════════════════════════════════════════════════════════════
# F-094: Trust Preservation Protocol Endpoints
# ══════════════════════════════════════════════════════════════════


@router.get("/api/jarvis/trust-protocol/status")
async def get_trust_protocol_status(
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
):
    """Get the current trust preservation protocol status.

    Returns the current protocol mode (GREEN/AMBER/RED), subsystem
    health summary, and feature flags for the current mode.

    F-094: Trust Preservation Protocol
    BC-001: Scoped by company_id.
    BC-005: Real-time status.
    BC-011: Requires authentication.
    """
    try:
        from app.services.trust_preservation_service import (
            get_trust_preservation_service,
        )

        svc = get_trust_preservation_service(company_id)
        result = await svc.get_protocol_status()

        return result

    except Exception as exc:
        logger.error(
            "trust_protocol_status_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


@router.post("/api/jarvis/trust-protocol/mode")
async def set_trust_protocol_mode(
    request: Request,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
):
    """Manually set the trust protocol mode (admin only).

    Allows admins to override the automatic protocol evaluation.
    The manual override persists until an admin resets it or the
    next evaluation cycle clears it.

    F-094: Trust Preservation Protocol
    BC-001: Scoped by company_id.
    BC-005: Broadcasts via Socket.io.
    BC-011: Requires admin authentication.
    BC-012: Audit-logged.
    """
    if user.role not in ("owner", "admin"):
        raise AuthorizationError(
            message="Protocol mode changes require admin privileges",
            details={"required_role": "admin"},
        )

    try:
        body = await request.json()
    except Exception:
        raise ValidationError(
            message="Invalid JSON body",
            details={
                "expected": {
                    "mode": "string (green/amber/red, required)",
                    "reason": "string (optional, max 500 chars)",
                }
            },
        )

    mode = body.get("mode")
    reason = body.get("reason")

    if not mode or mode.lower().strip() not in ("green", "amber", "red"):
        raise ValidationError(
            message=("mode is required and must be one of: " "green, amber, red"),
            details={
                "field": "mode",
                "valid_modes": ["green", "amber", "red"],
            },
        )

    try:
        from app.services.trust_preservation_service import (
            get_trust_preservation_service,
        )

        svc = get_trust_preservation_service(company_id)
        result = await svc.set_protocol_mode(
            mode=mode.lower().strip(),
            set_by=str(user.id),
            reason=reason,
        )

        logger.info(
            "trust_protocol_mode_set",
            company_id=company_id,
            previous_mode=result.get("previous_mode"),
            new_mode=result.get("new_mode"),
            user_id=str(user.id),
            reason=reason,
        )

        return result

    except (AuthorizationError, ValidationError):
        raise
    except Exception as exc:
        logger.error(
            "trust_protocol_mode_set_error",
            company_id=company_id,
            mode=mode,
            error=str(exc),
        )
        raise


@router.get("/api/jarvis/trust-protocol/history")
async def get_trust_protocol_history(
    limit: int = Query(
        50,
        ge=1,
        le=200,
        description="Number of transitions to return",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
):
    """Get the trust protocol transition history.

    Returns a list of protocol mode transitions for audit and
    analysis.

    F-094: Trust Preservation Protocol
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    BC-012: Audit trail.
    """
    try:
        from app.services.trust_preservation_service import (
            get_trust_preservation_service,
        )

        svc = get_trust_preservation_service(company_id)
        result = await svc.get_protocol_history(limit=limit)

        return result

    except Exception as exc:
        logger.error(
            "trust_protocol_history_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


@router.get("/api/jarvis/trust-protocol/recovery")
async def get_trust_protocol_recovery(
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
):
    """Get estimated time to protocol recovery.

    Analyzes current system health to estimate when the protocol
    can transition back to a healthier mode. Includes progress
    percentage and critical subsystem issues.

    F-094: Trust Preservation Protocol
    BC-001: Scoped by company_id.
    BC-005: Real-time health evaluation.
    BC-011: Requires authentication.
    """
    try:
        from app.services.trust_preservation_service import (
            get_trust_preservation_service,
        )

        svc = get_trust_preservation_service(company_id)
        result = await svc.get_recovery_estimate()

        return result

    except Exception as exc:
        logger.error(
            "trust_protocol_recovery_error",
            company_id=company_id,
            error=str(exc),
        )
        raise
