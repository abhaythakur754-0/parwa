"""
PARWA SLA API - MF06, PS11, PS17 SLA Management Endpoints (Day 29)

Implements:
- MF06: SLA Policy CRUD
- PS11: SLA Breach detection and escalation
- PS17: SLA Approaching notification (75% threshold)

BC-001: All endpoints are tenant-isolated.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.api.deps import get_current_user, get_db, require_roles
from app.schemas.sla import (
    SLAPolicyCreate,
    SLAPolicyResponse,
    SLAPolicyUpdate,
    SLAStats,
    SLATimerResponse,
)
from app.services.sla_service import (
    DuplicateSLAPolicyError,
    SLAError,
    SLAPolicyNotFoundError,
    SLAService,
)
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/sla",
    tags=["sla"],
    dependencies=[Depends(require_roles("owner", "admin"))],
)


# ── SLA POLICY ENDPOINTS ─────────────────────────────────────────────────────


@router.post(
    "/policies",
    response_model=SLAPolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create SLA policy",
)
async def create_policy(
    data: SLAPolicyCreate,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Create a new SLA policy for a plan tier and priority combination.

    Each plan_tier × priority combination can have one active policy.
    """
    company_id = current_user.get("company_id")

    service = SLAService(db)

    try:
        policy = service.create_policy(
            company_id=company_id,
            plan_tier=data.plan_tier.value,
            priority=data.priority.value,
            first_response_minutes=data.first_response_minutes,
            resolution_minutes=data.resolution_minutes,
            update_frequency_minutes=data.update_frequency_minutes,
            is_active=data.is_active,
        )

        return SLAPolicyResponse(
            id=policy.id,
            company_id=policy.company_id,
            plan_tier=policy.plan_tier,
            priority=policy.priority,
            first_response_minutes=policy.first_response_minutes,
            resolution_minutes=policy.resolution_minutes,
            update_frequency_minutes=policy.update_frequency_minutes,
            is_active=policy.is_active,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )

    except DuplicateSLAPolicyError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except SLAError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/policies",
    response_model=List[SLAPolicyResponse],
    summary="List SLA policies",
)
async def list_policies(
    plan_tier: Optional[str] = None,
    priority: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    List SLA policies with optional filters.
    """
    company_id = current_user.get("company_id")

    service = SLAService(db)

    policies = service.list_policies(
        company_id=company_id,
        plan_tier=plan_tier,
        priority=priority,
        is_active=is_active,
    )

    return [
        SLAPolicyResponse(
            id=p.id,
            company_id=p.company_id,
            plan_tier=p.plan_tier,
            priority=p.priority,
            first_response_minutes=p.first_response_minutes,
            resolution_minutes=p.resolution_minutes,
            update_frequency_minutes=p.update_frequency_minutes,
            is_active=p.is_active,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in policies
    ]


@router.get(
    "/policies/{policy_id}",
    response_model=SLAPolicyResponse,
    summary="Get SLA policy",
)
async def get_policy(
    policy_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Get an SLA policy by ID.
    """
    company_id = current_user.get("company_id")

    service = SLAService(db)

    policy = service.get_policy(company_id, policy_id)

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SLA policy not found",
        )

    return SLAPolicyResponse(
        id=policy.id,
        company_id=policy.company_id,
        plan_tier=policy.plan_tier,
        priority=policy.priority,
        first_response_minutes=policy.first_response_minutes,
        resolution_minutes=policy.resolution_minutes,
        update_frequency_minutes=policy.update_frequency_minutes,
        is_active=policy.is_active,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


@router.put(
    "/policies/{policy_id}",
    response_model=SLAPolicyResponse,
    summary="Update SLA policy",
)
async def update_policy(
    policy_id: str,
    data: SLAPolicyUpdate,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Update an SLA policy.
    """
    company_id = current_user.get("company_id")

    service = SLAService(db)

    try:
        policy = service.update_policy(
            company_id=company_id,
            policy_id=policy_id,
            **data.model_dump(exclude_unset=True),
        )

        return SLAPolicyResponse(
            id=policy.id,
            company_id=policy.company_id,
            plan_tier=policy.plan_tier,
            priority=policy.priority,
            first_response_minutes=policy.first_response_minutes,
            resolution_minutes=policy.resolution_minutes,
            update_frequency_minutes=policy.update_frequency_minutes,
            is_active=policy.is_active,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )

    except SLAPolicyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SLA policy not found",
        )


@router.delete(
    "/policies/{policy_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete SLA policy",
)
async def delete_policy(
    policy_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Delete an SLA policy.
    """
    company_id = current_user.get("company_id")

    service = SLAService(db)

    try:
        service.delete_policy(company_id, policy_id)
        return {"deleted": True, "policy_id": policy_id}

    except SLAPolicyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SLA policy not found",
        )


@router.post(
    "/policies/seed",
    status_code=status.HTTP_201_CREATED,
    summary="Seed default SLA policies",
)
async def seed_default_policies(
    plan_tier: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Seed default SLA policies for the company.

    Default policies:
    - Starter: critical 1h/8h, high 4h/24h, medium 12h/48h, low 24h/72h
    - Growth: Half of Starter times
    - High: Half of Growth times
    """
    company_id = current_user.get("company_id")

    service = SLAService(db)

    created = service.seed_default_policies(company_id, plan_tier)

    return {
        "seeded": len(created),
        "policies": [
            {
                "id": p.id,
                "plan_tier": p.plan_tier,
                "priority": p.priority,
                "first_response_minutes": p.first_response_minutes,
                "resolution_minutes": p.resolution_minutes,
            }
            for p in created
        ],
    }


# ── SLA TIMER ENDPOINTS ──────────────────────────────────────────────────────


@router.get(
    "/tickets/{ticket_id}",
    response_model=SLATimerResponse,
    summary="Get SLA timer for ticket",
)
async def get_ticket_sla(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Get SLA timer status for a ticket.

    Returns time remaining, breach status, and approaching status.
    """
    company_id = current_user.get("company_id")

    service = SLAService(db)

    timer = service.get_timer(company_id, ticket_id)

    if not timer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SLA timer not found for ticket",
        )

    # Get ticket for resolution target
    from database.models.tickets import Ticket

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

    return SLATimerResponse(
        id=timer.id,
        ticket_id=timer.ticket_id,
        policy_id=timer.policy_id,
        first_response_at=timer.first_response_at,
        resolved_at=timer.resolved_at,
        breached_at=timer.breached_at,
        is_breached=timer.is_breached,
        created_at=timer.created_at,
        updated_at=timer.updated_at,
        resolution_target=ticket.resolution_target_at if ticket else None,
    )


# ── SLA BREACH ENDPOINTS ─────────────────────────────────────────────────────


@router.get(
    "/breached",
    summary="List breached SLA tickets (PS11)",
)
async def list_breached_tickets(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    List all tickets with breached SLA.

    PS11: Breached tickets should be escalated.
    """
    company_id = current_user.get("company_id")

    service = SLAService(db)

    tickets = service.get_breached_tickets(company_id, limit)

    return {
        "items": [
            {
                "id": t.id,
                "subject": t.subject,
                "status": t.status,
                "priority": t.priority,
                "assigned_to": t.assigned_to,
                "created_at": t.created_at,
                "sla_breached": t.sla_breached,
            }
            for t in tickets
        ],
        "total": len(tickets),
    }


@router.get(
    "/approaching",
    summary="List tickets approaching SLA breach (PS17)",
)
async def list_approaching_tickets(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    List tickets approaching SLA breach (75% threshold).

    PS17: Send warning notifications for these tickets.
    """
    company_id = current_user.get("company_id")

    service = SLAService(db)

    approaching = service.get_approaching_tickets(company_id, limit)

    return {
        "items": [
            {
                "ticket_id": item["ticket"].id,
                "subject": item["ticket"].subject,
                "status": item["ticket"].status,
                "priority": item["ticket"].priority,
                "assigned_to": item["ticket"].assigned_to,
                "percentage_elapsed": round(item["percentage"] * 100, 1),
                "created_at": item["ticket"].created_at,
            }
            for item in approaching
        ],
        "total": len(approaching),
    }


# ── SLA STATISTICS ENDPOINTS ─────────────────────────────────────────────────


@router.get(
    "/stats",
    response_model=SLAStats,
    summary="Get SLA statistics",
)
async def get_sla_stats(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Get SLA performance statistics for the company.

    Returns compliance rate, average times, and counts.
    """
    company_id = current_user.get("company_id")

    service = SLAService(db)

    stats = service.get_sla_stats(
        company_id=company_id,
        start_date=start_date,
        end_date=end_date,
    )

    return SLAStats(
        total_tickets=stats["total_tickets"],
        breached_count=stats["breached_count"],
        approaching_count=stats["approaching_count"],
        compliant_count=stats["compliant_count"],
        avg_first_response_minutes=stats["avg_first_response_minutes"],
        avg_resolution_minutes=stats["avg_resolution_minutes"],
    )
