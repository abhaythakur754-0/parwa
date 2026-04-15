"""
Billing API Routes (F-021, F-023, F-025, F-026)

Endpoints for subscription and billing management:
- GET  /subscription - Get current subscription
- POST /subscription - Create new subscription
- PATCH /subscription - Upgrade/downgrade subscription
- DELETE /subscription - Cancel subscription
- POST /subscription/reactivate - Reactivate canceled subscription
- GET /proration/preview - Preview upgrade cost
- GET /proration/history - Get proration audit log
- GET /invoices - List invoices
- GET /invoices/{id} - Get invoice details
- GET /invoices/{id}/pdf - Download invoice PDF
- GET /usage - Get current usage
- GET /usage/history - Get usage history
- GET /client-refunds - List client refunds
- POST /client-refunds - Create client refund request

BC-001: All endpoints require company_id from JWT
BC-012: Structured JSON error responses
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.schemas.billing import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionCancel,
    SubscriptionInfo,
    SubscriptionStatus,
    VariantType,
    ProrationResult,
    ProrationAudit,
)
from app.services.subscription_service import (
    SubscriptionService,
    SubscriptionError,
    SubscriptionNotFoundError,
    SubscriptionAlreadyExistsError,
    InvalidVariantError,
    InvalidStatusTransitionError,
    get_subscription_service,
)
from app.services.proration_service import (
    ProrationService,
    ProrationError,
    get_proration_service,
)
from app.services.invoice_service import (
    InvoiceService,
    InvoiceError,
    InvoiceNotFoundError,
    InvoiceAccessDeniedError,
    get_invoice_service,
)
from app.services.client_refund_service import (
    ClientRefundService,
    ClientRefundError,
    ClientRefundNotFoundError,
    get_client_refund_service,
)
from app.services.overage_service import (
    OverageService,
    get_overage_service,
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


# ── Invoice Endpoints ─────────────────────────────────────────────────────

class InvoiceListResponse(BaseModel):
    """Response for invoice list."""
    invoices: List[Dict[str, Any]]
    pagination: Dict[str, Any]


class InvoiceResponse(BaseModel):
    """Response for single invoice."""
    id: str
    company_id: str
    paddle_invoice_id: Optional[str]
    amount: str
    currency: str
    status: str
    invoice_date: Optional[str]
    due_date: Optional[str]
    paid_at: Optional[str]
    created_at: Optional[str]


@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    request: Request,
    company_id: UUID = Depends(get_company_id),
    page: int = 1,
    page_size: int = 20,
) -> InvoiceListResponse:
    """
    List invoices for the company.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page (max 50)

    Returns:
        Paginated list of invoices
    """
    service = get_invoice_service()
    result = await service.get_invoice_list(
        company_id=company_id,
        page=page,
        page_size=page_size,
    )
    return InvoiceListResponse(**result)


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    request: Request,
    invoice_id: str,
    company_id: UUID = Depends(get_company_id),
) -> InvoiceResponse:
    """
    Get single invoice details.

    Args:
        invoice_id: Invoice UUID

    Returns:
        Invoice details
    """
    service = get_invoice_service()

    try:
        invoice = await service.get_invoice(
            company_id=company_id,
            invoice_id=invoice_id,
        )
        return InvoiceResponse(**invoice)

    except InvoiceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "invoice_not_found",
                "message": str(e),
            },
        )
    except InvoiceAccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "access_denied",
                "message": str(e),
            },
        )


@router.get("/invoices/{invoice_id}/pdf")
async def get_invoice_pdf(
    request: Request,
    invoice_id: str,
    company_id: UUID = Depends(get_company_id),
) -> Response:
    """
    Download invoice PDF.

    Args:
        invoice_id: Invoice UUID

    Returns:
        PDF file download
    """
    service = get_invoice_service()

    try:
        pdf_bytes = await service.get_invoice_pdf(
            company_id=company_id,
            invoice_id=invoice_id,
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=invoice_{invoice_id}.pdf"
            },
        )

    except InvoiceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "invoice_not_found",
                "message": str(e),
            },
        )
    except InvoiceAccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "access_denied",
                "message": str(e),
            },
        )


# ── Usage Endpoints ────────────────────────────────────────────────────────

class UsageResponse(BaseModel):
    """Response for current usage."""
    current_month: str
    tickets_used: int
    ticket_limit: int
    overage_tickets: int
    overage_charges: str
    usage_percentage: float


class UsageHistoryResponse(BaseModel):
    """Response for usage history."""
    history: List[Dict[str, Any]]
    total: int


@router.get("/usage", response_model=UsageResponse)
async def get_current_usage(
    request: Request,
    company_id: UUID = Depends(get_company_id),
) -> UsageResponse:
    """
    Get current month's usage.

    Returns:
        Current usage with ticket count, limit, and overage
    """
    service = get_overage_service()

    usage = await service.get_current_usage(company_id)
    limit = await service.get_ticket_limit(company_id)

    tickets_used = usage.get("tickets_used", 0)
    ticket_limit = limit.get("limit", 2000)
    overage = max(0, tickets_used - ticket_limit)

    return UsageResponse(
        current_month=usage.get("month", date.today().strftime("%Y-%m")),
        tickets_used=tickets_used,
        ticket_limit=ticket_limit,
        overage_tickets=overage,
        overage_charges=str(Decimal(str(overage)) * Decimal("0.10")),
        usage_percentage=min(1.0, tickets_used / ticket_limit) if ticket_limit > 0 else 0,
    )


@router.get("/usage/history", response_model=UsageHistoryResponse)
async def get_usage_history(
    request: Request,
    company_id: UUID = Depends(get_company_id),
    months: int = 12,
) -> UsageHistoryResponse:
    """
    Get historical usage data.

    Args:
        months: Number of months to return (max 24)

    Returns:
        List of monthly usage records
    """
    service = get_overage_service()

    history = await service.get_usage_history(
        company_id=company_id,
        months=min(months, 24),
    )

    return UsageHistoryResponse(
        history=history,
        total=len(history),
    )


# ── Client Refund Endpoints ────────────────────────────────────────────────

class ClientRefundCreate(BaseModel):
    """Request to create a client refund."""
    amount: Decimal = Field(..., gt=0, description="Refund amount")
    currency: str = Field(default="USD", max_length=3)
    ticket_id: Optional[UUID] = None
    reason: Optional[str] = None


class ClientRefundResponse(BaseModel):
    """Response for client refund."""
    id: str
    company_id: str
    ticket_id: Optional[str]
    amount: str
    currency: str
    reason: str
    status: str
    processed_at: Optional[str]
    created_at: Optional[str]


class ClientRefundListResponse(BaseModel):
    """Response for client refund list."""
    refunds: List[Dict[str, Any]]
    pagination: Dict[str, Any]


class ClientRefundProcessRequest(BaseModel):
    """Request to process a refund."""
    external_ref: Optional[str] = None


@router.get("/client-refunds", response_model=ClientRefundListResponse)
async def list_client_refunds(
    request: Request,
    company_id: UUID = Depends(get_company_id),
    status_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> ClientRefundListResponse:
    """
    List client refund requests.

    PARWA clients refunding THEIR customers.

    Args:
        status_filter: Filter by status (pending/processed/failed/canceled)
        page: Page number
        page_size: Items per page

    Returns:
        Paginated list of refund requests
    """
    service = get_client_refund_service()
    result = service.list_refunds(
        company_id=company_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return ClientRefundListResponse(**result)


@router.post(
    "/client-refunds",
    response_model=ClientRefundResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_client_refund(
    request: Request,
    data: ClientRefundCreate,
    company_id: UUID = Depends(get_company_id),
) -> ClientRefundResponse:
    """
    Create a client refund request.

    This records when a PARWA client issues a refund
    to their customer (NOT PARWA refunding the client).

    Args:
        data: Refund details

    Returns:
        Created refund request
    """
    service = get_client_refund_service()

    try:
        refund = service.create_refund_request(
            company_id=company_id,
            amount=data.amount,
            currency=data.currency,
            ticket_id=data.ticket_id,
            reason=data.reason,
        )
        return ClientRefundResponse(**refund)

    except ClientRefundError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "refund_error",
                "message": str(e),
            },
        )


@router.post(
    "/client-refunds/{refund_id}/process",
    response_model=ClientRefundResponse,
)
async def process_client_refund(
    request: Request,
    refund_id: str,
    data: ClientRefundProcessRequest,
    company_id: UUID = Depends(get_company_id),
) -> ClientRefundResponse:
    """
    Mark a refund as processed.

    Called when the client confirms the refund was processed
    in their payment system.

    Args:
        refund_id: Refund UUID
        data: Process request with optional external reference

    Returns:
        Updated refund request
    """
    service = get_client_refund_service()

    try:
        refund = service.process_refund(
            company_id=company_id,
            refund_id=refund_id,
            external_ref=data.external_ref,
        )
        return ClientRefundResponse(**refund)

    except ClientRefundNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "refund_not_found",
                "message": str(e),
            },
        )
    except ClientRefundError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "refund_error",
                "message": str(e),
            },
        )


@router.get("/client-refunds/stats")
async def get_client_refund_stats(
    request: Request,
    company_id: UUID = Depends(get_company_id),
) -> Dict[str, Any]:
    """
    Get client refund statistics.

    Returns:
        Stats with counts and totals
    """
    service = get_client_refund_service()
    return service.get_refund_stats(company_id)
