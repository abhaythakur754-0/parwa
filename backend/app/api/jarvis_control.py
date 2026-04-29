"""
PARWA Jarvis Control API Routes (Week 14 Day 1 — Jarvis Command Center)

FastAPI router endpoints for the Jarvis Command Center.

Endpoints:
- POST /api/jarvis/command — Parse and execute a Jarvis command (F-087)
- GET  /api/jarvis/commands — List available commands (F-087)
- GET  /api/system/status — Get system health status (F-088)
- GET  /api/system/status/history — Get status history (F-088)
- GET  /api/system/incidents — Get active incidents (F-088)
- POST /api/gsd/state/{ticket_id} — Get GSD state for ticket (F-089)
- GET  /api/gsd/sessions — List active GSD sessions (F-089)
- POST /api/gsd/force-transition — Force GSD transition, admin only (F-089)

Building Codes: BC-001 (tenant isolation), BC-011 (auth),
               BC-012 (error handling, structured responses)
"""

from datetime import datetime, timezone
from typing import Dict, Optional

from app.api.deps import (
    get_company_id,
    get_current_user,
    require_roles,
)
from app.exceptions import (
    ValidationError,
)
from app.logger import get_logger
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from database.base import get_db
from database.models.core import User

logger = get_logger("jarvis_control_api")

router = APIRouter()


# ══════════════════════════════════════════════════════════════════
# F-087: Jarvis Command Parser Endpoints
# ══════════════════════════════════════════════════════════════════


@router.post("/api/jarvis/command")
async def parse_jarvis_command(
    request: Request,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Parse and execute a natural language Jarvis command.

    Accepts a free-text command from an operator and returns
    a structured action. Optionally auto-executes if confidence
    is above threshold.

    F-087: Jarvis Command Parser
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    try:
        body = await request.json()
    except Exception:
        raise ValidationError(
            message="Invalid JSON body",
            details={"expected": {"command": "string"}},
        )

    command_text = body.get("command", "")
    if not command_text or not command_text.strip():
        raise ValidationError(
            message="Command text is required",
            details={"field": "command"},
        )

    context = body.get("context")
    auto_execute = body.get("auto_execute", False)

    try:
        from app.core.jarvis_command_parser import get_command_parser

        parser = get_command_parser()
        parsed = parser.parse(command_text, context)

        # Build response
        result = {
            "command_type": parsed.command_type,
            "original_command": parsed.original_command,
            "params": parsed.params,
            "confidence": parsed.confidence,
            "requires_confirmation": parsed.requires_confirmation,
            "execution_summary": parsed.execution_summary,
            "aliases_matched": parsed.aliases_matched,
            "auto_execute_eligible": parser.should_auto_execute(parsed),
            "executed": False,
            "executed_at": None,
            "execution_result": None,
        }

        # Auto-execute if requested and eligible
        if auto_execute and parser.should_auto_execute(parsed):
            exec_result = await _execute_command(
                parsed,
                company_id,
                user,
                db,
            )
            result["executed"] = True
            result["executed_at"] = datetime.now(
                timezone.utc,
            ).isoformat()
            result["execution_result"] = exec_result

        logger.info(
            "jarvis_command_parsed",
            company_id=company_id,
            user_id=str(user.id),
            command_type=parsed.command_type,
            confidence=parsed.confidence,
        )

        return result

    except Exception as exc:
        logger.error(
            "jarvis_command_parse_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


@router.get("/api/jarvis/commands")
async def list_jarvis_commands(
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
):
    """List all available Jarvis commands with metadata.

    Returns all registered commands grouped by category with
    descriptions, aliases, parameters, and example invocations.

    F-087: Jarvis Command Parser
    BC-011: Requires authentication.
    """
    try:
        from app.core.jarvis_command_parser import get_command_parser

        parser = get_command_parser()
        commands = parser.get_available_commands()

        # Group by category
        categories = {}
        for cmd in commands:
            cat = cmd.get("category", "other")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(cmd)

        return {
            "commands": commands,
            "total": len(commands),
            "categories": categories,
        }

    except Exception as exc:
        logger.error(
            "jarvis_commands_list_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


# ══════════════════════════════════════════════════════════════════
# F-088: System Status Service Endpoints
# ══════════════════════════════════════════════════════════════════


@router.get("/api/system/status")
async def get_system_status(
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
):
    """Get the full system health status.

    Returns aggregated health data for all PARWA subsystems:
    LLM providers, Redis, PostgreSQL, Celery queues, integrations.

    F-088: System Status Service
    BC-001: Scoped by company_id.
    BC-005: Real-time health data.
    BC-011: Requires authentication.
    """
    try:
        from app.services.system_status_service import (
            get_system_status_service,
        )

        service = get_system_status_service(company_id)
        status = await service.get_system_status()

        return status

    except Exception as exc:
        logger.error(
            "system_status_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


@router.get("/api/system/status/history")
async def get_status_history(
    from_timestamp: Optional[str] = Query(
        None,
        description="ISO 8601 start time",
    ),
    to_timestamp: Optional[str] = Query(
        None,
        description="ISO 8601 end time",
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum data points",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
):
    """Get historical system status data for charting.

    Returns time-series data points suitable for rendering
    health status charts.

    F-088: System Status Service
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.system_status_service import (
            get_system_status_service,
        )

        service = get_system_status_service(company_id)
        history = await service.get_status_history(
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            limit=limit,
        )

        return history

    except Exception as exc:
        logger.error(
            "system_status_history_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


@router.get("/api/system/incidents")
async def get_active_incidents(
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
):
    """Get all active (unresolved) system incidents.

    System incidents are automatically detected when subsystems
    transition from healthy to degraded or unhealthy.

    F-088: System Status Service
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.system_status_service import (
            get_system_status_service,
        )

        service = get_system_status_service(company_id)
        incidents = await service.get_active_incidents()

        return incidents

    except Exception as exc:
        logger.error(
            "system_incidents_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


# ══════════════════════════════════════════════════════════════════
# F-089: GSD Debug Terminal Service Endpoints
# ══════════════════════════════════════════════════════════════════


@router.post("/api/gsd/state/{ticket_id}")
async def get_gsd_state(
    ticket_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current GSD state for a ticket.

    Reads from Redis (primary), in-memory (fallback), or
    database (last resort) per BC-008.

    F-089: GSD Debug Terminal Service
    BC-001: Scoped by company_id.
    BC-008: Multi-source fallback for state reads.
    BC-011: Requires authentication.
    """
    if not ticket_id or not ticket_id.strip():
        raise ValidationError(
            message="ticket_id is required",
            details={"field": "ticket_id"},
        )

    try:
        from app.services.gsd_terminal_service import (
            get_gsd_terminal_service,
        )

        service = get_gsd_terminal_service(company_id, db=db)
        state = await service.get_gsd_state(ticket_id)

        logger.info(
            "gsd_state_retrieved",
            company_id=company_id,
            ticket_id=ticket_id,
            user_id=str(user.id),
            state=state.get("current_state"),
            source=state.get("source"),
        )

        return state

    except Exception as exc:
        logger.error(
            "gsd_state_error",
            company_id=company_id,
            ticket_id=ticket_id,
            error=str(exc),
        )
        raise


@router.get("/api/gsd/sessions")
async def list_gsd_sessions(
    agent_id: Optional[str] = Query(
        None,
        description="Filter by agent ID",
    ),
    stuck_only: bool = Query(
        False,
        description="Only return stuck sessions",
    ),
    limit: int = Query(
        100,
        ge=1,
        le=500,
        description="Maximum sessions to return",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Pagination offset",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List active GSD sessions.

    Optionally filter by agent ID or only stuck sessions.
    Sorted by duration descending (longest-running first).

    F-089: GSD Debug Terminal Service
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.gsd_terminal_service import (
            get_gsd_terminal_service,
        )

        service = get_gsd_terminal_service(company_id, db=db)
        sessions = await service.list_active_sessions(
            agent_id=agent_id,
            stuck_only=stuck_only,
            limit=limit,
            offset=offset,
        )

        return sessions

    except Exception as exc:
        logger.error(
            "gsd_sessions_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


@router.post("/api/gsd/force-transition")
async def force_gsd_transition(
    request: Request,
    company_id: str = Depends(get_company_id),
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
):
    """Force-transition a stuck GSD session. Admin only.

    Overrides the normal state machine to move a stuck session
    to a target state. This action is audit-logged.

    F-089: GSD Debug Terminal Service
    BC-001: Scoped by company_id.
    BC-008: State management with graceful handling.
    BC-011: Admin-only, audit-logged.
    """
    try:
        body = await request.json()
    except Exception:
        raise ValidationError(
            message="Invalid JSON body",
            details={
                "expected": {
                    "ticket_id": "string",
                    "target_state": "string",
                    "reason": "string",
                }
            },
        )

    ticket_id = body.get("ticket_id", "")
    target_state = body.get("target_state", "")
    reason = body.get("reason", "")

    if not ticket_id or not ticket_id.strip():
        raise ValidationError(
            message="ticket_id is required",
            details={"field": "ticket_id"},
        )
    if not target_state or not target_state.strip():
        raise ValidationError(
            message="target_state is required",
            details={"field": "target_state"},
        )
    if not reason or not reason.strip():
        raise ValidationError(
            message="reason is required for audit logging",
            details={"field": "reason"},
        )

    try:
        from app.services.gsd_terminal_service import (
            get_gsd_terminal_service,
        )

        service = get_gsd_terminal_service(company_id, db=db)
        result = await service.force_transition(
            ticket_id=ticket_id,
            target_state=target_state,
            reason=reason,
            actor_id=str(user.id),
        )

        logger.info(
            "gsd_force_transition_completed",
            company_id=company_id,
            ticket_id=ticket_id,
            actor_id=str(user.id),
            previous_state=result.get("previous_state"),
            new_state=result.get("new_state"),
            audit_log_id=result.get("audit_log_id"),
        )

        return result

    except Exception as exc:
        logger.error(
            "gsd_force_transition_error",
            company_id=company_id,
            ticket_id=ticket_id,
            error=str(exc),
        )
        raise


# ══════════════════════════════════════════════════════════════════
# COMMAND EXECUTION HELPER
# ══════════════════════════════════════════════════════════════════


async def _execute_command(
    parsed,
    company_id: str,
    user: User,
    db: Session,
) -> Dict:
    """Execute a parsed command and return the result.

    Routes to the appropriate service based on command_type.
    """
    from app.core.jarvis_command_parser import ParsedCommand

    if not isinstance(parsed, ParsedCommand):
        return {"error": "Invalid parsed command"}

    cmd_type = parsed.command_type
    params = {p["name"]: p["value"] for p in parsed.params}

    try:
        # System status commands
        if cmd_type == "show_status":
            from app.services.system_status_service import (
                get_system_status_service,
            )

            service = get_system_status_service(company_id)
            return await service.get_system_status()

        # Ticket commands
        if cmd_type == "list_tickets":
            from app.services.ticket_service import TicketService

            svc = TicketService(db, company_id)
            tickets = svc.list_tickets(
                status=params.get("status"),
                limit=int(params.get("limit", 20)),
            )
            return {"tickets": [str(t.id) for t in tickets]}

        if cmd_type == "get_ticket":
            tid = params.get("ticket_id", "")
            from app.services.ticket_service import TicketService

            svc = TicketService(db, company_id)
            ticket = svc.get_ticket(tid)
            return {"ticket_id": str(ticket.id), "status": str(ticket.status)}

        # Agent commands
        if cmd_type == "list_agents":
            try:
                from database.models.core import User

                members = (
                    db.query(User)
                    .filter(
                        User.company_id == company_id,
                        User.is_active is True,  # noqa: E712
                    )
                    .all()
                )
                agents = [
                    {
                        "id": str(m.id),
                        "email": m.email,
                        "full_name": getattr(m, "full_name", None),
                        "role": str(m.role),
                    }
                    for m in members
                ]
                return {"agents": agents, "total": len(agents)}
            except Exception as agent_err:
                logger.error(
                    "jarvis_list_agents_error",
                    company_id=company_id,
                    error=str(agent_err),
                )
                return {"error": str(agent_err)[:200]}

        # Queue commands
        if cmd_type == "list_queues":
            try:
                from app.tasks.celery_app import app as celery_app

                inspect = celery_app.control.inspect()
                active = inspect.active_queues() or {}
                queues = {}
                for worker_name, queue_list in active.items():
                    queues[worker_name] = [
                        {"name": q.get("name"), "routing_key": q.get("routing_key")}
                        for q in queue_list
                    ]
                return {"queues": queues, "workers": list(queues.keys())}
            except Exception as queue_err:
                logger.error(
                    "jarvis_list_queues_error",
                    company_id=company_id,
                    error=str(queue_err),
                )
                return {"error": str(queue_err)[:200]}

        # Incident commands
        if cmd_type == "list_incidents":
            from app.services.system_status_service import (
                get_system_status_service,
            )

            service = get_system_status_service(company_id)
            return await service.get_active_incidents()

        # Analytics
        if cmd_type in ("show_analytics", "query_analytics"):
            try:
                from app.services.analytics_service import (
                    get_billing_analytics_service,
                )

                analytics_svc = get_billing_analytics_service()
                summary = analytics_svc.get_spending_summary(company_id)
                budget = analytics_svc.get_budget_alert(company_id)
                return {
                    "spending": summary,
                    "budget_alert": budget,
                    "params": params,
                }
            except Exception as analytics_err:
                logger.error(
                    "jarvis_analytics_error",
                    company_id=company_id,
                    error=str(analytics_err),
                )
                # Fallback: simple ticket counts by status
                try:
                    from sqlalchemy import func

                    from database.models.ticket import Ticket

                    status_counts = (
                        db.query(Ticket.status, func.count(Ticket.id))
                        .filter(Ticket.company_id == company_id)
                        .group_by(Ticket.status)
                        .all()
                    )
                    return {
                        "ticket_counts_by_status": {
                            str(s): c for s, c in status_counts
                        },
                        "fallback": True,
                        "params": params,
                    }
                except Exception as fallback_err:
                    return {"error": str(fallback_err)[:200], "params": params}

        # Help
        if cmd_type == "help":
            from app.core.jarvis_command_parser import get_command_parser

            parser = get_command_parser()
            commands = parser.get_available_commands()
            return {
                "total_commands": len(commands),
                "message": "Type a command to execute",
            }

        return {
            "message": f"Command '{cmd_type}' acknowledged",
            "params": params,
        }

    except Exception as exc:
        logger.warning(
            "jarvis_command_execute_error",
            company_id=company_id,
            command_type=cmd_type,
            error=str(exc),
        )
        return {"error": str(exc)[:200]}
