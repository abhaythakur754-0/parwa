"""
PARWA Approval API - Human-in-the-Loop Approval Management

Endpoints for:
- Listing and filtering approval queue entries (GET /api/approvals)
- Getting a single approval entry (GET /api/approvals/{id})
- Creating new approval requests from AI agents (POST /api/approvals)
- Approving or rejecting approval entries (PATCH /api/approvals/{id})
- Listing auto-approve rules (GET /api/approvals/rules)
- Creating auto-approve rules (POST /api/approvals/rules)

BC-001: All endpoints are tenant-isolated via company_id.
BC-002: All monetary fields use Decimal (never float).
BC-011: JWT verification on every protected endpoint.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_tenant_context
from database.base import get_db
from database.models.approval import ApprovalQueue, AutoApproveRule
from database.models.core import User
from app.schemas.approval import (
    ApprovalQueueCreate,
    ApprovalQueueResponse,
    ApprovalQueueUpdate,
    ApprovalStatus,
    AutoApproveRuleCreate,
    AutoApproveRuleResponse,
    RiskLevel,
)

router = APIRouter(prefix="/api/approvals", tags=["approvals"])
logger = logging.getLogger("parwa.approvals")


# ── Inline Request Schemas ────────────────────────────────────────────────────


class ApprovalStatusUpdateRequest(BaseModel):
    """Request body for PATCH /api/approvals/{id} — approve or reject."""

    status: ApprovalStatus = Field(
        ...,
        description="New status: 'approved' or 'rejected'",
    )
    reason: Optional[str] = Field(
        None,
        description="Optional reason for the decision",
    )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _approval_to_response(a: ApprovalQueue) -> ApprovalQueueResponse:
    """Convert an ApprovalQueue ORM object to a Pydantic response schema."""
    return ApprovalQueueResponse(
        id=str(a.id),
        company_id=str(a.company_id),
        session_id=str(a.session_id) if a.session_id else None,
        action_type=str(a.action_type),
        confidence_score=Decimal(str(a.confidence_score)) if a.confidence_score is not None else None,
        risk_level=RiskLevel(str(a.risk_level)) if a.risk_level else None,
        amount=Decimal(str(a.amount)) if a.amount is not None else None,
        reasoning=a.reasoning,
        response_data=a.response_data,
        status=ApprovalStatus(str(a.status)),
        batch_id=str(a.batch_id) if a.batch_id else None,
        created_at=a.created_at,
        resolved_at=a.resolved_at,
        resolved_by=str(a.resolved_by) if a.resolved_by else None,
    )


def _rule_to_response(r: AutoApproveRule) -> AutoApproveRuleResponse:
    """Convert an AutoApproveRule ORM object to a Pydantic response schema."""
    return AutoApproveRuleResponse(
        id=str(r.id),
        company_id=str(r.company_id),
        action_type=str(r.action_type),
        min_confidence=Decimal(str(r.min_confidence)),
        max_amount=Decimal(str(r.max_amount)) if r.max_amount is not None else None,
        risk_levels=r.risk_levels,
        is_active=r.is_active,
        created_by=str(r.created_by),
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Approval Queue Endpoints
# ══════════════════════════════════════════════════════════════════════════════


@router.get(
    "",
    response_model=List[ApprovalQueueResponse],
    summary="List approvals for the company",
)
async def list_approvals(
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by approval status (pending, approved, rejected, expired)",
    ),
    action_type: Optional[str] = Query(
        None,
        description="Filter by action type",
    ),
    batch_id: Optional[str] = Query(
        None,
        description="Filter by batch ID",
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    List all approval queue entries for the company.

    Supports optional filtering by status, action_type, and batch_id.
    BC-001: Results are scoped to the authenticated user's company.
    """
    company_id = current_user.company_id

    query = db.query(ApprovalQueue).filter(
        ApprovalQueue.company_id == company_id,
    )

    if status_filter:
        query = query.filter(ApprovalQueue.status == status_filter)

    if action_type:
        query = query.filter(ApprovalQueue.action_type == action_type)

    if batch_id:
        query = query.filter(ApprovalQueue.batch_id == batch_id)

    query = query.order_by(ApprovalQueue.created_at.desc())
    approvals = query.offset(offset).limit(limit).all()

    return [_approval_to_response(a) for a in approvals]


@router.get(
    "/rules",
    response_model=List[AutoApproveRuleResponse],
    summary="List auto-approve rules",
)
async def list_rules(
    is_active: Optional[bool] = Query(
        None,
        description="Filter by active status",
    ),
    action_type: Optional[str] = Query(
        None,
        description="Filter by action type",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    List all auto-approve rules for the company.

    BC-001: Results are scoped to the authenticated user's company.
    """
    company_id = current_user.company_id

    query = db.query(AutoApproveRule).filter(
        AutoApproveRule.company_id == company_id,
    )

    if is_active is not None:
        query = query.filter(AutoApproveRule.is_active == is_active)

    if action_type:
        query = query.filter(AutoApproveRule.action_type == action_type)

    rules = query.order_by(AutoApproveRule.created_at.desc()).all()

    return [_rule_to_response(r) for r in rules]


@router.get(
    "/{approval_id}",
    response_model=ApprovalQueueResponse,
    summary="Get a single approval",
)
async def get_approval(
    approval_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get a single approval queue entry by ID.

    BC-001: Only returns approvals belonging to the user's company.
    """
    company_id = current_user.company_id

    approval = (
        db.query(ApprovalQueue)
        .filter(
            ApprovalQueue.id == approval_id,
            ApprovalQueue.company_id == company_id,
        )
        .first()
    )

    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval not found",
        )

    return _approval_to_response(approval)


@router.post(
    "",
    response_model=ApprovalQueueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new approval request",
)
async def create_approval(
    data: ApprovalQueueCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Create a new approval queue entry.

    Typically called by AI agents to submit actions requiring human approval.
    BC-001: company_id is taken from the authenticated user.
    BC-002: Amount fields use Decimal.
    """
    company_id = current_user.company_id

    # Check for auto-approve rules that match this request
    # If a matching active rule exists, auto-approve the entry
    auto_approved = False
    if data.action_type and data.status == ApprovalStatus.PENDING:
        matching_rules = (
            db.query(AutoApproveRule)
            .filter(
                AutoApproveRule.company_id == company_id,
                AutoApproveRule.action_type == data.action_type,
                AutoApproveRule.is_active == True,  # noqa: E712
            )
            .all()
        )

        for rule in matching_rules:
            # Check confidence threshold
            if data.confidence_score is not None and rule.min_confidence is not None:
                if Decimal(str(data.confidence_score)) < Decimal(str(rule.min_confidence)):
                    continue

            # Check max amount
            if data.amount is not None and rule.max_amount is not None:
                if Decimal(str(data.amount)) > Decimal(str(rule.max_amount)):
                    continue

            # Check risk level
            if data.risk_level and rule.risk_levels:
                allowed_risks = [r.strip().lower() for r in rule.risk_levels.split(",")]
                if data.risk_level.value.lower() not in allowed_risks:
                    continue

            # All checks passed — auto-approve
            auto_approved = True
            break

    approval = ApprovalQueue(
        company_id=company_id,
        session_id=data.session_id,
        action_type=data.action_type,
        confidence_score=float(data.confidence_score) if data.confidence_score is not None else None,
        risk_level=data.risk_level.value if data.risk_level else None,
        amount=float(data.amount) if data.amount is not None else None,
        reasoning=data.reasoning,
        response_data=data.response_data,
        status="approved" if auto_approved else data.status.value,
        batch_id=data.batch_id,
        resolved_at=datetime.now(timezone.utc) if auto_approved else None,
        resolved_by=current_user.id if auto_approved else None,
    )

    db.add(approval)
    db.flush()

    if auto_approved:
        logger.info(
            "approval_auto_approved",
            extra={
                "approval_id": str(approval.id),
                "company_id": company_id,
                "action_type": data.action_type,
            },
        )

    return _approval_to_response(approval)


@router.patch(
    "/{approval_id}",
    response_model=ApprovalQueueResponse,
    summary="Update approval status (approve/reject)",
)
async def update_approval_status(
    approval_id: str,
    data: ApprovalStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Approve or reject an approval queue entry.

    Only pending approvals can be updated. Once approved or rejected,
    the entry cannot be changed again.

    BC-001: Only approvals belonging to the user's company can be updated.
    """
    company_id = current_user.company_id

    approval = (
        db.query(ApprovalQueue)
        .filter(
            ApprovalQueue.id == approval_id,
            ApprovalQueue.company_id == company_id,
        )
        .first()
    )

    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval not found",
        )

    if approval.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Approval is already {approval.status} and cannot be changed",
        )

    if data.status not in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status must be 'approved' or 'rejected'",
        )

    now = datetime.now(timezone.utc)

    approval.status = data.status.value
    approval.resolved_at = now
    approval.resolved_by = current_user.id

    # If a reason was provided, append it to the reasoning field
    if data.reason:
        existing_reasoning = approval.reasoning or ""
        separator = "\n\n" if existing_reasoning else ""
        approval.reasoning = (
            f"{existing_reasoning}{separator}"
            f"[{data.status.value.upper()}] {data.reason}"
        )

    db.flush()

    logger.info(
        "approval_status_updated",
        extra={
            "approval_id": str(approval.id),
            "company_id": company_id,
            "new_status": data.status.value,
            "resolved_by": str(current_user.id),
        },
    )

    return _approval_to_response(approval)


# ══════════════════════════════════════════════════════════════════════════════
# Auto-Approve Rule Endpoints
# ══════════════════════════════════════════════════════════════════════════════


@router.post(
    "/rules",
    response_model=AutoApproveRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an auto-approve rule",
)
async def create_rule(
    data: AutoApproveRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Create a new auto-approve rule.

    Auto-approve rules allow certain AI actions to be automatically approved
    without human review, based on confidence score, amount, and risk level.

    BC-001: company_id is taken from the authenticated user.
    BC-002: Monetary fields use Decimal.
    """
    company_id = current_user.company_id

    # Check for duplicate active rule with same action_type
    existing = (
        db.query(AutoApproveRule)
        .filter(
            AutoApproveRule.company_id == company_id,
            AutoApproveRule.action_type == data.action_type,
            AutoApproveRule.is_active == True,  # noqa: E712
        )
        .first()
    )

    if existing and data.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"An active auto-approve rule already exists for "
                f"action_type '{data.action_type}'. Deactivate the existing "
                f"rule before creating a new one."
            ),
        )

    rule = AutoApproveRule(
        company_id=company_id,
        action_type=data.action_type,
        min_confidence=float(data.min_confidence),
        max_amount=float(data.max_amount) if data.max_amount is not None else None,
        risk_levels=data.risk_levels or "low",
        is_active=data.is_active,
        created_by=current_user.id,
    )

    db.add(rule)
    db.flush()

    logger.info(
        "auto_approve_rule_created",
        extra={
            "rule_id": str(rule.id),
            "company_id": company_id,
            "action_type": data.action_type,
            "is_active": data.is_active,
        },
    )

    return _rule_to_response(rule)
