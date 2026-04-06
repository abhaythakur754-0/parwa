"""
PARWA Ticket Assignment API - F-050 Assignment Endpoints (Day 28)

Implements F-050: Ticket assignment API with:
- Score-based assignment preview
- Auto-assign based on rules
- Assignment rule management
- Manual reassignment

BC-001: All endpoints are tenant-isolated.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_db
from backend.app.services.assignment_service import AssignmentService, AssigneeType
from backend.app.exceptions import NotFoundError, ValidationError


router = APIRouter(prefix="/tickets", tags=["ticket-assignment"])

# Separate router for assignment rules
rules_router = APIRouter(prefix="/assignments/rules", tags=["assignment-rules"])


# ── SCHEMAS ────────────────────────────────────────────────────────────────

class AssignmentScoreResult(BaseModel):
    """Assignment score result."""
    user_id: str
    name: str
    score: float
    current_tickets: int


class AssignmentScoresResponse(BaseModel):
    """Assignment scores response."""
    ticket_id: str
    candidates: List[AssignmentScoreResult]
    recommended_assignee: Optional[AssignmentScoreResult]
    scoring_method: str


class AutoAssignResponse(BaseModel):
    """Auto-assign response."""
    ticket_id: str
    assigned: bool
    assignee_id: Optional[str]
    assignee_type: Optional[str]
    rule_id: Optional[str]
    rule_name: Optional[str]
    reason: Optional[str] = None


class ManualAssignRequest(BaseModel):
    """Manual assignment request."""
    assignee_id: str = Field(..., description="User ID to assign to")
    reason: Optional[str] = Field(None, description="Reason for assignment")


class ManualAssignResponse(BaseModel):
    """Manual assignment response."""
    ticket_id: str
    previous_assignee: Optional[str]
    new_assignee: str
    assigned_at: str


class UnassignResponse(BaseModel):
    """Unassign response."""
    ticket_id: str
    previous_assignee: Optional[str]
    unassigned: bool


class AssignmentHistoryItem(BaseModel):
    """Assignment history item."""
    id: str
    assignee_type: str
    assignee_id: Optional[str]
    reason: Optional[str]
    score: Optional[float]
    assigned_at: str


class AssignmentHistoryResponse(BaseModel):
    """Assignment history response."""
    ticket_id: str
    history: List[AssignmentHistoryItem]


class RuleCondition(BaseModel):
    """Rule condition schema."""
    priority: Optional[List[str]] = None
    category: Optional[List[str]] = None
    channel: Optional[List[str]] = None
    status: Optional[List[str]] = None


class RuleAction(BaseModel):
    """Rule action schema."""
    assign_to_user: Optional[str] = None
    assign_to_pool: Optional[str] = None
    assignee_type: str = "human"


class CreateRuleRequest(BaseModel):
    """Create rule request."""
    name: str = Field(..., min_length=1, max_length=255)
    conditions: Optional[Dict[str, Any]] = Field(default_factory=dict)
    action: Dict[str, Any]
    priority_order: int = Field(0, ge=0, le=1000)
    is_active: bool = True


class UpdateRuleRequest(BaseModel):
    """Update rule request."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    conditions: Optional[Dict[str, Any]] = None
    action: Optional[Dict[str, Any]] = None
    priority_order: Optional[int] = Field(None, ge=0, le=1000)
    is_active: Optional[bool] = None


class RuleResponse(BaseModel):
    """Rule response."""
    id: str
    name: str
    conditions: Dict[str, Any]
    action: Dict[str, Any]
    priority_order: int
    is_active: bool
    created_at: str
    updated_at: str


class RuleListResponse(BaseModel):
    """Rule list response."""
    items: List[RuleResponse]
    total: int


# ── TICKET ASSIGNMENT ENDPOINTS ────────────────────────────────────────────

@router.post(
    "/{ticket_id}/assign/score",
    response_model=AssignmentScoresResponse,
    summary="Get assignment scores",
)
async def get_assignment_scores(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Get assignment scores for all candidates.

    F-050: Preview who should be assigned based on scoring.
    Week 4: Rule-based scoring.
    Week 9: AI-based scoring.
    """
    company_id = current_user.get("company_id")

    service = AssignmentService(db, company_id)

    try:
        result = service.get_assignment_scores(ticket_id)

        return AssignmentScoresResponse(
            ticket_id=result["ticket_id"],
            candidates=[
                AssignmentScoreResult(**c) for c in result["candidates"]
            ],
            recommended_assignee=(
                AssignmentScoreResult(**result["recommended_assignee"])
                if result["recommended_assignee"] else None
            ),
            scoring_method=result["scoring_method"],
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/{ticket_id}/assign/auto",
    response_model=AutoAssignResponse,
    summary="Auto-assign ticket",
)
async def auto_assign_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Auto-assign ticket based on rules.

    F-050: Automatic assignment using rules engine.
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    service = AssignmentService(db, company_id)

    try:
        result = service.auto_assign(ticket_id, user_id)
        return AutoAssignResponse(**result)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/{ticket_id}/assign",
    response_model=ManualAssignResponse,
    summary="Manually assign ticket",
)
async def manually_assign_ticket(
    ticket_id: str,
    data: ManualAssignRequest,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Manually assign ticket to a specific user.

    F-050: Manual assignment override.
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    service = AssignmentService(db, company_id)

    try:
        result = service.assign_to_user(
            ticket_id=ticket_id,
            assignee_id=data.assignee_id,
            reason=data.reason,
            assigned_by=user_id,
        )
        return ManualAssignResponse(**result)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete(
    "/{ticket_id}/assign",
    response_model=UnassignResponse,
    summary="Unassign ticket",
)
async def unassign_ticket(
    ticket_id: str,
    reason: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Unassign a ticket.

    F-050: Remove assignment from ticket.
    """
    company_id = current_user.get("company_id")
    user_id = current_user.get("user_id")

    service = AssignmentService(db, company_id)

    try:
        result = service.unassign(
            ticket_id=ticket_id,
            reason=reason,
            user_id=user_id,
        )
        return UnassignResponse(**result)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/{ticket_id}/assign/history",
    response_model=AssignmentHistoryResponse,
    summary="Get assignment history",
)
async def get_assignment_history(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Get assignment history for a ticket.

    F-050: Full history of all assignments.
    """
    company_id = current_user.get("company_id")

    service = AssignmentService(db, company_id)

    history = service.get_assignment_history(ticket_id)

    return AssignmentHistoryResponse(
        ticket_id=ticket_id,
        history=[AssignmentHistoryItem(**h) for h in history],
    )


# ── ASSIGNMENT RULES ENDPOINTS ─────────────────────────────────────────────

@rules_router.get(
    "",
    response_model=RuleListResponse,
    summary="List assignment rules",
)
async def list_assignment_rules(
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """List all assignment rules.

    F-050: View assignment rules configuration.
    """
    company_id = current_user.get("company_id")

    service = AssignmentService(db, company_id)

    rules = service.list_rules(include_inactive=include_inactive)

    return RuleListResponse(
        items=[RuleResponse(**r) for r in rules],
        total=len(rules),
    )


@rules_router.post(
    "",
    response_model=RuleResponse,
    status_code=201,
    summary="Create assignment rule",
)
async def create_assignment_rule(
    data: CreateRuleRequest,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Create an assignment rule.

    F-050: Add custom assignment rule.
    Rules are evaluated in priority_order (lower = higher priority).
    """
    company_id = current_user.get("company_id")

    service = AssignmentService(db, company_id)

    try:
        rule = service.create_rule(
            name=data.name,
            conditions=data.conditions or {},
            action=data.action,
            priority_order=data.priority_order,
            is_active=data.is_active,
        )

        return RuleResponse(
            id=rule.id,
            name=rule.name,
            conditions=(
                rule.conditions
                if isinstance(rule.conditions, dict)
                else eval(rule.conditions)
            ),
            action=(
                rule.action
                if isinstance(rule.action, dict)
                else eval(rule.action)
            ),
            priority_order=rule.priority_order,
            is_active=rule.is_active,
            created_at=rule.created_at.isoformat(),
            updated_at=rule.updated_at.isoformat(),
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@rules_router.put(
    "/{rule_id}",
    response_model=RuleResponse,
    summary="Update assignment rule",
)
async def update_assignment_rule(
    rule_id: str,
    data: UpdateRuleRequest,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Update an assignment rule.

    F-050: Modify existing assignment rule.
    """
    company_id = current_user.get("company_id")

    service = AssignmentService(db, company_id)

    try:
        rule = service.update_rule(
            rule_id=rule_id,
            name=data.name,
            conditions=data.conditions,
            action=data.action,
            priority_order=data.priority_order,
            is_active=data.is_active,
        )

        return RuleResponse(
            id=rule.id,
            name=rule.name,
            conditions=(
                rule.conditions
                if isinstance(rule.conditions, dict)
                else eval(rule.conditions)
            ),
            action=(
                rule.action
                if isinstance(rule.action, dict)
                else eval(rule.action)
            ),
            priority_order=rule.priority_order,
            is_active=rule.is_active,
            created_at=rule.created_at.isoformat(),
            updated_at=rule.updated_at.isoformat(),
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@rules_router.delete(
    "/{rule_id}",
    summary="Delete assignment rule",
)
async def delete_assignment_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Dict[str, bool]:
    """Delete an assignment rule.

    F-050: Remove assignment rule.
    """
    company_id = current_user.get("company_id")

    service = AssignmentService(db, company_id)

    try:
        deleted = service.delete_rule(rule_id)
        return {"deleted": deleted}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
