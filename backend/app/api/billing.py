"""
Billing API Routes (F-021, F-025, F-026)

Endpoints for subscription and billing management:
- GET  /subscription - Get current subscription
- POST /subscription - Create new subscription
- PATCH /subscription - Upgrade/downgrade subscription
- DELETE /subscription - Cancel subscription
- POST /subscription/reactivate - Reactivate canceled subscription
- GET /proration/preview - Preview upgrade cost
- GET /proration/history - Get proration audit log

BC-001: All endpoints require company_id from JWT
BC-012: Structured JSON error responses
"""

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.app.schemas.billing import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionCancel,
    SubscriptionInfo,
    SubscriptionStatus,
    VariantType,
    ProrationResult,
    ProrationAudit,
)
from backend.app.services.subscription_service import (
    SubscriptionService,
    SubscriptionError,
    SubscriptionNotFoundError,
    SubscriptionAlreadyExistsError,
    InvalidVariantError,
    InvalidStatusTransitionError,
    get_subscription_service,
)
from backend.app.services.proration_service import (
    ProrationService,
    ProrationError,
    get_proration_service,
)

logger = logging.getLogger("parwa.api.billing")

router = APIRouter(prefix="/api/billing", tags=["billing"])


# ── Request/Response Models ───────────────────────────────────────────────

class UpgradePreviewRequest(BaseModel):
    """Request to preview upgrade cost."""
    new_variant: VariantType


class UpgradePreviewResponse(BaseModel):
    """Response for upgrade preview."""
    current_variant: VariantType
    new_variant: VariantType
    estimated_cost: Dict[str, Any]
    proration_preview: Optional[ProrationResult] = None
    message: str


class UpgradeResponse(BaseModel):
    """Response for upgrade."""
    subscription: SubscriptionInfo
    proration: Optional[Dict[str, Any]] = None
    audit_id: Optional[str] = None
    message: str


class DowngradeResponse(BaseModel):
    """Response for downgrade."""
    subscription: SubscriptionInfo
    scheduled_change: Optional[Dict[str, Any]] = None
    message: str


class CancelResponse(BaseModel):
    """Response for cancellation."""
    subscription: SubscriptionInfo
    cancellation: Dict[str, Any]
    message: str


class SubscriptionListResponse(BaseModel):
    """Response for subscription list."""
    subscription: Optional[SubscriptionInfo]
    has_subscription: bool


# ── Dependency Injection ──────────────────────────────────────────────────

def get_company_id(request: Request) -> UUID:
    """
    Extract company_id from request state.

    Set by JWT middleware after authentication.
    """
    company_id = request.state.company_id
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "unauthorized",
                "message": "Authentication required",
            },
        )
    return UUID(company_id)


def get_user_id(request: Request) -> Optional[UUID]:
    """Extract user_id from request state if available."""
    user_id = getattr(request.state, "user_id", None)
    return UUID(user_id) if user_id else None


# ── Subscription Endpoints ────────────────────────────────────────────────

@router.get("/subscription", response_model=SubscriptionListResponse)
async def get_subscription(
    request: Request,
    company_id: UUID = Depends(get_company_id),
) -> SubscriptionListResponse:
    """
    Get current subscription details.

    Returns subscription info if exists, otherwise returns has_subscription=false.
    """
    service = get_subscription_service()
    subscription = await service.get_subscription(company_id)

    return SubscriptionListResponse(
        subscription=subscription,
        has_subscription=subscription is not None,
    )


@router.post(
    "/subscription",
    response_model=SubscriptionInfo,
    status_code=status.HTTP_201_CREATED,
)
async def create_subscription(
    request: Request,
    data: SubscriptionCreate,
    company_id: UUID = Depends(get_company_id),
) -> SubscriptionInfo:
    """
    Create a new subscription.

    Args:
        data: SubscriptionCreate with variant and optional payment_method_id

    Returns:
        Created subscription info

    Raises:
        400: Company already has active subscription
        400: Invalid variant
    """
    service = get_subscription_service()

    try:
        subscription = await service.create_subscription(
            company_id=company_id,
            variant=data.variant.value,
            payment_method_id=data.payment_method_id,
        )
        return subscription

    except SubscriptionAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "subscription_exists",
                "message": str(e),
            },
        )
    except InvalidVariantError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_variant",
                "message": str(e),
            },
        )
    except SubscriptionError as e:
        logger.error("subscription_create_failed company_id=%s error=%s", company_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "subscription_error",
                "message": "Failed to create subscription",
            },
        )


@router.patch("/subscription", response_model=UpgradeResponse)
async def update_subscription(
    request: Request,
    data: SubscriptionUpdate,
    company_id: UUID = Depends(get_company_id),
) -> UpgradeResponse:
    """
    Update subscription (upgrade or downgrade).

    Upgrades:
    - Immediate
    - Prorated credit applied
    - Net charge calculated

    Downgrades:
    - Scheduled for next billing cycle
    - No proration needed
    - Access continues at current tier until then

    Args:
        data: SubscriptionUpdate with new variant

    Returns:
        Updated subscription with proration details (for upgrades)
        or scheduled change info (for downgrades)
    """
    sub_service = get_subscription_service()
    new_variant = data.variant.value

    # Determine if upgrade or downgrade
    current = await sub_service.get_subscription(company_id)
    if not current:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "subscription_not_found",
                "message": "No active subscription found",
            },
        )

    # Check if upgrade or downgrade
    tier_order = {"starter": 1, "growth": 2, "high": 3}
    is_upgrade = tier_order.get(new_variant, 0) > tier_order.get(
        current.variant.value, 0
    )

    try:
        if is_upgrade:
            result = await sub_service.upgrade_subscription(
                company_id=company_id,
                new_variant=new_variant,
            )
            return UpgradeResponse(
                subscription=result["subscription"],
                proration=result.get("proration"),
                audit_id=result.get("audit_id"),
                message=f"Successfully upgraded to {new_variant}",
            )
        else:
            result = await sub_service.downgrade_subscription(
                company_id=company_id,
                new_variant=new_variant,
            )
            return UpgradeResponse(
                subscription=result["subscription"],
                proration=None,
                audit_id=None,
                message=result.get("message", f"Downgrade to {new_variant} scheduled"),
            )

    except SubscriptionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "subscription_not_found",
                "message": str(e),
            },
        )
    except InvalidVariantError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_variant",
                "message": str(e),
            },
        )
    except SubscriptionError as e:
        logger.error("subscription_update_failed company_id=%s error=%s", company_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "subscription_error",
                "message": "Failed to update subscription",
            },
        )


@router.delete("/subscription", response_model=CancelResponse)
async def cancel_subscription(
    request: Request,
    data: SubscriptionCancel,
    company_id: UUID = Depends(get_company_id),
    user_id: Optional[UUID] = Depends(get_user_id),
) -> CancelResponse:
    """
    Cancel subscription.

    Netflix-style cancellation:
    - Default: Access continues until end of billing period
    - effective_immediately=true: Stop now (no refund)

    Args:
        data: SubscriptionCancel with reason and effective_immediately flag

    Returns:
        Cancellation details with access_until date
    """
    service = get_subscription_service()

    try:
        result = await service.cancel_subscription(
            company_id=company_id,
            reason=data.reason,
            effective_immediately=data.effective_immediately,
            user_id=user_id,
        )

        return CancelResponse(
            subscription=result["subscription"],
            cancellation=result["cancellation"],
            message=result["message"],
        )

    except SubscriptionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "subscription_not_found",
                "message": str(e),
            },
        )
    except SubscriptionError as e:
        logger.error("subscription_cancel_failed company_id=%s error=%s", company_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "subscription_error",
                "message": "Failed to cancel subscription",
            },
        )


@router.post("/subscription/reactivate", response_model=SubscriptionInfo)
async def reactivate_subscription(
    request: Request,
    company_id: UUID = Depends(get_company_id),
) -> SubscriptionInfo:
    """
    Reactivate a subscription pending cancellation.

    Only works for subscriptions that were canceled but still active
    (cancel_at_period_end=true).

    Returns:
        Reactivated subscription info
    """
    service = get_subscription_service()

    try:
        subscription = await service.reactivate_subscription(company_id)
        return subscription

    except InvalidStatusTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "cannot_reactivate",
                "message": str(e),
            },
        )
    except SubscriptionError as e:
        logger.error(
            "subscription_reactivate_failed company_id=%s error=%s",
            company_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "subscription_error",
                "message": "Failed to reactivate subscription",
            },
        )


# ── Proration Endpoints ───────────────────────────────────────────────────

@router.post("/proration/preview", response_model=UpgradePreviewResponse)
async def preview_upgrade(
    request: Request,
    data: UpgradePreviewRequest,
    company_id: UUID = Depends(get_company_id),
) -> UpgradePreviewResponse:
    """
    Preview upgrade cost before committing.

    Shows:
    - Estimated proration credit
    - New charge amount
    - Net cost

    Args:
        data: UpgradePreviewRequest with target variant

    Returns:
        Detailed cost preview
    """
    sub_service = get_subscription_service()
    proration_service = get_proration_service()

    # Get current subscription
    current = await sub_service.get_subscription(company_id)
    if not current:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "subscription_not_found",
                "message": "No active subscription found",
            },
        )

    current_variant = current.variant.value
    new_variant = data.new_variant.value

    # Check if upgrade
    tier_order = {"starter": 1, "growth": 2, "high": 3}
    if tier_order.get(new_variant, 0) <= tier_order.get(current_variant, 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "not_upgrade",
                "message": f"{new_variant} is not an upgrade from {current_variant}",
            },
        )

    # Calculate preview
    from datetime import datetime, timezone

    billing_start = current.current_period_start
    billing_end = current.current_period_end

    if billing_start and billing_end:
        # Ensure timezone-aware
        if billing_start.tzinfo is None:
            billing_start = billing_start.replace(tzinfo=timezone.utc)
        if billing_end.tzinfo is None:
            billing_end = billing_end.replace(tzinfo=timezone.utc)

        proration = await proration_service.calculate_upgrade_proration(
            company_id=company_id,
            old_variant=current_variant,
            new_variant=new_variant,
            billing_cycle_start=billing_start.date(),
            billing_cycle_end=billing_end.date(),
        )

        estimate = {
            "unused_credit": str(proration.unused_amount),
            "new_charge": str(proration.new_charge),
            "net_cost": str(proration.net_charge),
            "days_remaining": proration.days_remaining,
        }
    else:
        # No billing period info - use estimate
        estimate = await proration_service.estimate_upgrade_cost(
            old_variant=current_variant,
            new_variant=new_variant,
            days_remaining=15,  # Assume mid-period
            days_in_period=30,
        )
        estimate = {k: str(v) for k, v in estimate.items()}
        proration = None

    return UpgradePreviewResponse(
        current_variant=current.variant,
        new_variant=data.new_variant,
        estimated_cost=estimate,
        proration_preview=proration,
        message=f"Upgrade from {current_variant} to {new_variant}",
    )


@router.get("/proration/history")
async def get_proration_history(
    request: Request,
    company_id: UUID = Depends(get_company_id),
    limit: int = 12,
) -> Dict[str, Any]:
    """
    Get proration audit history.

    Shows all variant changes with calculated proration amounts.

    Args:
        limit: Maximum records to return (default 12)

    Returns:
        List of proration audit records
    """
    proration_service = get_proration_service()

    history = await proration_service.get_proration_audit_log(
        company_id=company_id,
        limit=min(limit, 50),  # Cap at 50
    )

    return {
        "history": history,
        "total": len(history),
    }


# ── Status Endpoint ────────────────────────────────────────────────────────

@router.get("/status")
async def get_billing_status(
    request: Request,
    company_id: UUID = Depends(get_company_id),
) -> Dict[str, Any]:
    """
    Get overall billing status for the company.

    Returns subscription status, current usage, and any pending changes.
    """
    sub_service = get_subscription_service()

    subscription = await sub_service.get_subscription(company_id)
    status_value = await sub_service.get_subscription_status(company_id)

    return {
        "subscription_status": status_value,
        "has_subscription": subscription is not None,
        "variant": subscription.variant.value if subscription else None,
        "cancel_at_period_end": subscription.cancel_at_period_end if subscription else False,
        "current_period_end": subscription.current_period_end if subscription else None,
    }
