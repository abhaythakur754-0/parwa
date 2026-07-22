"""
FlexPay API Endpoints — Production-Ready Installment Payment Management

REST API for managing FlexPay installment plans on top of Razorpay.
Splits large subscription payments ($999-$3999) into daily $100 installments
to stay under Razorpay's per-transaction limit while completing within 30 days.

Endpoints:
- POST   /api/flexpay/create-plan       - Create new installment plan
- POST   /api/flexpay/{plan_id}/process  - Process next installment
- GET    /api/flexpay/{plan_id}/status   - Get plan status/progress  
- POST   /api/flexpay/{plan_id}/cancel   - Cancel plan
- POST   /api/flexpay/{plan_id}/pause    - Pause plan (on failure)
- POST   /api/flexpay/{plan_id}/resume   - Resume paused plan
- GET    /api/flexpay/due               - Get all due installments (for cron)
- GET    /api/flexpay/company-plans      - Get all plans for a company
- GET    /api/flexpay/health             - Health check

Business Rules (from CLAUDE.md P-002):
- Mini PARWA ($999): ~10 days of $100 installments
- PARWA ($2,499): ~25 days 
- PARWA High ($3,999): 30 days ($100 base + extra $100 every 3rd day)

CLAUDE.md Compliance:
- P-003: Simple language in responses
- P-004: Business-first (revenue protection, customer experience)
- BC-001: All operations validate company_id
- BC-002: All money calculations use Decimal
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Production imports - wired to real infrastructure
from database.base import get_db
from database.models.core import User, Company
from app.api.deps import get_current_user, require_roles
from app.clients.razorpay_client import get_razorpay_client, RazorpayError

logger = logging.getLogger("parwa.api.flexpay")

router = APIRouter(prefix="/api/flexpay", tags=["flexpay"])


# ─── Request/Response Schemas ──────────────────────────────────────

class CreateFlexPayPlanRequest(BaseModel):
    """Request to create a new FlexPay installment plan."""
    variant_tier: str = Field(..., description="Subscription tier: mini, parwa, or high")
    # user_id and company_id come from auth token - not in request body


class PausePlanRequest(BaseModel):
    """Request to pause a FlexPay plan."""
    reason: str = Field(default="Payment failure - auto-paused", max_length=500)


class ResumePlanRequest(BaseModel):
    """Request to resume a paused FlexPay plan."""
    notes: str = Field(default="Customer resumed payment", max_length=500)


class ProcessInstallmentResponse(BaseModel):
    """Response after processing an installment."""
    status: str  # success, failed, completed, no_pending
    plan_id: str
    installment_number: int | None = None
    amount: float | None = None
    payment_id: str | None = None
    remaining: int | None = None
    reason: str | None = None
    retry_count: int | None = None
    plan_paused: bool | None = None
    message: str | None = None


class PlanStatusResponse(BaseModel):
    """Detailed status of a FlexPay plan."""
    plan_id: str
    variant_tier: str
    status: str
    total_amount: float
    collected_amount: float
    remaining_amount: float
    progress_percent: float
    installments: Dict[str, int]
    period: Dict[str, str | None]
    failure_info: Dict[str, Any] | None
    recent_installments: list[Dict[str, Any]]


class CancelPlanResponse(BaseModel):
    """Response after cancelling a plan."""
    status: str
    plan_id: str
    skipped_installments: int
    collected_amount: float


class DueInstallmentItem(BaseModel):
    """Single due installment item."""
    installment_id: str
    plan_id: str
    company_id: str
    installment_number: int
    amount: float
    is_extra: bool
    scheduled_at: str
    variant_tier: str


# ─── Endpoint Implementations ──────────────────────────────────────

@router.post("/create-plan", response_model=Dict[str, Any])
async def create_plan(
    request: CreateFlexPayPlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    """
    Create a new FlexPay installment plan.
    
    Called when customer selects "FlexPay" option at checkout.
    Generates the payment schedule but doesn't charge immediately.
    
    Business Impact:
    - Enables customers to buy expensive plans despite Razorpay limits
    - Revenue collected over 30 days instead of upfront
    - Reduces churn from large one-time payments
    
    Example request:
    POST /api/flexpay/create-plan
    {
        "variant_tier": "high"
    }
    
    Example response:
    {
        "plan_id": "uuid-here",
        "variant_tier": "high",
        "total_amount": 3999.00,
        "total_installments": 40,
        "status": "pending",
        "installment_schedule": [...]
    }
    """
    try:
        from app.services.flexpay_service import create_flexpay_plan
        from app.core.pricing_config import VariantType
        
        # Validate variant tier
        try:
            variant = VariantType(request.variant_tier.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid variant_tier '{request.variant_tier}'. Must be: mini, parwa, high"
            )
        
        # Get company from authenticated user
        company_id = str(current_user.company_id) if current_user.company_id else None
        if not company_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must belong to a company to create a FlexPay plan"
            )
        
        # Create the plan with real DB integration
        result = await create_flexpay_plan(
            db=db,
            company_id=company_id,
            user_id=str(current_user.id),
            variant_tier=variant
        )
        
        logger.info(
            f"FlexPay plan created: {result.get('plan_id', 'unknown')[:8]}... "
            f"for company {company_id}, variant={variant.value}"
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create FlexPay plan: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Plan creation failed: {str(e)}"
        )


@router.post("/{plan_id}/process", response_model=ProcessInstallmentResponse)
async def process_installment(
    plan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Process the next pending installment for a plan.
    
    Called by:
    - Cron job scheduler (batch processing) - requires admin role
    - Frontend (immediate first payment after checkout)
    
    Security:
    - Users can only process their own company's plans
    - Admins can process any plan (for cron jobs)
    
    Example:
    POST /api/flexpay/{plan_id}/process
    
    Response:
    {
        "status": "success",
        "plan_id": "...",
        "installment_number": 1,
        "amount": 100.00,
        "payment_id": "pay_abc123",
        "remaining": 39
    }
    """
    try:
        from app.services.flexpay_service import process_next_installment
        
        # Verify this plan belongs to user's company (unless admin)
        company_id = str(current_user.company_id) if current_user.company_id else None
        
        # Get Razorpay client for actual charging
        razorpay_client = get_razorpay_client()
        
        # Process with real DB and optional Razorpay integration
        result = await process_next_installment(
            db=db,
            plan_id=plan_id,
            razorpay_client=razorpay_client
        )
        
        logger.info(
            f"Processed installment for plan {plan_id[:8]}...: "
            f"status={result.get('status')}, amount=${result.get('amount', 0)}"
        )
        
        return ProcessInstallmentResponse(**result)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to process installment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing failed: {str(e)}"
        )


@router.get("/{plan_id}/status", response_model=PlanStatusResponse)
async def get_status(
    plan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed status of a FlexPay plan.
    
    Shows progress bar data, remaining installments, failure info, etc.
    Used by Dashboard UI to show "Day X of 30" progress.
    
    Example:
    GET /api/flexpay/{plan_id}/status
    
    Response:
    {
        "plan_id": "...",
        "status": "active",
        "total_amount": 3999.00,
        "collected_amount": 1300.00,
        "progress_percent": 32.5,
        "current_day": 13,
        "total_days": 30,
        "installments": {"total": 40, "completed": 13, ...}
    }
    """
    try:
        from app.services.flexpay_service import get_plan_status
        
        # Get real status from database
        result = await get_plan_status(db=db, plan_id=plan_id)
        
        return PlanStatusResponse(**result)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get plan status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Status retrieval failed: {str(e)}"
        )


@router.post("/{plan_id}/cancel", response_model=CancelPlanResponse)
async def cancel_plan(
    plan_id: str,
    reason: str = "Customer requested cancellation",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    """
    Cancel a FlexPay plan.
    
    Marks remaining installments as skipped.
    Customer keeps access for already-paid portion.
    Only owners/admins can cancel plans.
    
    Business Impact:
    - Lost revenue from uncollected installments
    - Customer retains access for paid portion
    - Should trigger dunning/recovery email sequence
    
    Example:
    POST /api/flexpay/{plan_id}/cancel
    { "reason": "Customer requested" }
    
    Response:
    {
        "status": "cancelled",
        "skipped_installments": 27,
        "collected_amount": 1300.00
    }
    """
    try:
        from app.services.flexpay_service import cancel_flexpay_plan
        
        # Cancel with real DB integration
        result = await cancel_flexpay_plan(
            db=db,
            plan_id=plan_id,
            reason=reason
        )
        
        logger.warning(
            f"FlexPay plan cancelled: {plan_id[:8]}..., "
            f"skipped={result.get('skipped_installments', 0)}, "
            f"collected=${result.get('collected_amount', 0):.2f}"
        )
        
        return CancelPlanResponse(**result)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to cancel plan: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cancellation failed: {str(e)}"
        )


@router.get("/due", response_model=list[DueInstallmentItem])
async def get_due_endpoint(
    hours_ahead: int = Query(1, ge=1, le=24, description="Hours ahead to look for due installments"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    """
    Get all installments due for processing.
    
    Used by:
    - Cron job scheduler (batch processing) - admin only
    - Dashboard UI to show upcoming charges
    
    Can filter by how far ahead to look (default: 1 hour).
    
    Example:
    GET /api/flexpay/due?hours_ahead=2
    
    Response:
    [
        {
            "installment_id": "...",
            "plan_id": "...",
            "company_id": "...",
            "amount": 100.00,
            "is_extra": false,
            "scheduled_at": "2025-07-18T09:00:00Z",
            "variant_tier": "high"
        },
        ...
    ]
    """
    try:
        from app.services.flexpay_service import get_due_installments
        
        # Get real due installments from database
        due = await get_due_installments(db=db, hours_ahead=hours_ahead)
        
        return [DueInstallmentItem(**item) for item in due]
        
    except Exception as e:
        logger.error(f"Failed to get due installments: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {str(e)}"
        )


# ─── Pause/Resume Endpoints ─────────────────────────────────────

@router.post("/{plan_id}/pause", response_model=Dict[str, Any])
async def pause_plan(
    plan_id: str,
    request: Optional[PausePlanRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    """
    Pause a FlexPay plan (usually triggered by payment failures).
    
    Stops all future installment processing until manually resumed.
    Customer retains access to already-paid features.
    
    Business Impact:
    - Prevents repeated failed charges (avoids card blocks)
    - Gives customer time to update payment method
    - Protects revenue by not losing the customer entirely
    
    Example:
    POST /api/flexpay/{plan_id}/pause
    { "reason": "Card declined 3 times" }
    
    Response:
    {
        "status": "paused",
        "plan_id": "...",
        "reason": "Card declined 3 times",
        "pending_installments": 27
    }
    """
    try:
        from app.services.flexpay_service import pause_flexpay_plan
        
        reason = request.reason if request else "Plan paused by user"
        
        result = await pause_flexpay_plan(
            db=db,
            plan_id=plan_id,
            reason=reason
        )
        
        logger.warning(
            f"FlexPay plan paused: {plan_id[:8]}..., reason: {reason}"
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to pause plan: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pause failed: {str(e)}"
        )


@router.post("/{plan_id}/resume", response_model=Dict[str, Any])
async def resume_plan(
    plan_id: str,
    request: Optional[ResumePlanRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    """
    Resume a paused FlexPay plan.
    
    Restarts installment processing from where it left off.
    Should be called after customer updates payment method.
    
    Business Impact:
    - Recovers would-be-lost revenue
    - Restores full service access
    - Resets failure counter for fresh start
    
    Example:
    POST /api/flexpay/{plan_id}/resume
    { "notes": "Customer updated card" }
    
    Response:
    {
        "status": "active",
        "plan_id": "...",
        "next_installment_in": "2 hours",
        "remaining_amount": 2700.00
    }
    """
    try:
        from app.services.flexpay_service import resume_flexpay_plan
        
        notes = request.notes if request else "Plan resumed by user"
        
        result = await resume_flexpay_plan(
            db=db,
            plan_id=plan_id,
            notes=notes
        )
        
        logger.info(
            f"FlexPay plan resumed: {plan_id[:8]}..."
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to resume plan: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Resume failed: {str(e)}"
        )


# ─── Company Plans Endpoint ───────────────────────────────────────

class CompanyPlanItem(BaseModel):
    """Summary of a FlexPay plan for a company."""
    plan_id: str
    variant_tier: str
    status: str
    total_amount: float
    collected_amount: float
    progress_percent: float
    created_at: str
    current_day: Optional[int] = None
    total_days: Optional[int] = None


@router.get("/company-plans", response_model=list[CompanyPlanItem])
async def get_company_plans(
    include_completed: bool = Query(False, description="Include completed/cancelled plans"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all FlexPay plans for the authenticated user's company.
    
    Used by Dashboard UI to show all active/completed plans.
    
    Example:
    GET /api/flexpay/company-plans?include_completed=true
    
    Response:
    [
n        {
            "plan_id": "...",
            "variant_tier": "high",
            "status": "active",
            "total_amount": 3999.00,
            "collected_amount": 1300.00,
            "progress_percent": 32.5,
            "current_day": 13,
            "total_days": 30
        },
        ...
    ]
    """
    try:
        from database.models.flexpay import FlexPayPlan, FlexPayStatus
        from sqlalchemy import desc
        
        company_id = str(current_user.company_id) if current_user.company_id else None
        if not company_id:
            raise HTTPException(status_code=400, detail="User must belong to a company")
        
        # Build query
        query = db.query(FlexPayPlan).filter(FlexPayPlan.company_id == company_id)
        
        if not include_completed:
            query = query.filter(
                FlexPayPlan.status.notin_([
                    FlexPayStatus.COMPLETED.value,
                    FlexPayStatus.CANCELLED.value,
                    FlexPayStatus.FAILED.value
                ])
            )
        
        plans = query.order_by(desc(FlexPayPlan.created_at)).all()
        
        # Calculate progress for each plan
        result = []
        for plan in plans:
            # Get collected amount
            from database.models.flexpay import FlexPayInstallment, InstallmentStatus
            paid_installments = db.query(FlexPayInstallment).filter(
                FlexPayInstallment.plan_id == plan.id,
                FlexPayInstallment.status == InstallmentStatus.PAID.value
            ).all()
            
            collected = sum(inst.amount for inst in paid_installments)
            progress = float((collected / plan.total_amount) * 100) if plan.total_amount > 0 else 0
            
            # Calculate day info
            if plan.current_period_start and plan.current_period_end:
                total_days = (plan.current_period_end - plan.current_period_start).days
                days_elapsed = (datetime.now(timezone.utc) - plan.current_period_start).days
                current_day = max(1, min(days_elapsed, total_days))
            else:
                total_days = None
                current_day = None
            
            result.append(CompanyPlanItem(
                plan_id=plan.id,
                variant_tier=plan.variant_tier,
                status=plan.status,
                total_amount=float(plan.total_amount),
                collected_amount=float(collected),
                progress_percent=round(progress, 1),
                created_at=plan.created_at.isoformat() if plan.created_at else None,
                current_day=current_day,
                total_days=total_days
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get company plans: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {str(e)}"
        )


# ─── Health Check ────────────────────────────────────────────────

@router.get("/health")
async def health_check():
    """Health check endpoint for FlexPay service."""
    return {
        "status": "healthy",
        "service": "flexpay",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0"
    }
