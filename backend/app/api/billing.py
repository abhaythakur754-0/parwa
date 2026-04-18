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
from datetime import date, timedelta
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
    CompanyVariantCreate,
    CompanyVariantList,
    CompanyVariantInfo,
    EffectiveLimitsInfo,
    CancelFeedbackRequest,
    SaveOfferResponse,
    CancelConfirmRequest,
    ResubscriptionRequest,
    ResubscriptionResponse,
    RetentionStatusResponse,
    DataExportRequestResponse,
    DataExportDownloadResponse,
    PaymentMethodUpdateRequest,
    PaymentMethodUpdateResponse,
    PaymentFailureStatusResponse,
    MessageResponse,
    # Day 6 schemas
    TrialStartRequest,
    TrialStatusResponse,
    PauseResponse,
    ResumeResponse,
    PromoApplyRequest,
    PromoValidateResponse,
    PromoCodeInfo,
    PromoCodeCreateRequest,
    CurrencyResponse,
    TimezoneResponse,
    EnterpriseBillingRequest,
    ManualInvoiceRequest,
    InvoiceAmendmentRequest,
    InvoiceAmendmentInfo,
    SpendingSummary,
    ChannelBreakdown,
    SpendingTrend,
    BudgetAlert,
    VoiceUsageInfo,
    SmsUsageInfo,
    DashboardSummary,
    PlanComparison,
    VariantCatalog,
    VariantCatalogItem,
    EnhancedInvoiceHistory,
    PaymentSchedule,
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
from app.services.variant_addon_service import (
    VariantAddonService,
    VariantAddonError,
    get_variant_addon_service,
)
from app.services.data_retention_service import (
    DataRetentionService,
    DataExportNotFoundError,
    DataRetentionExpiredError,
    DataExportInProgressError,
)
from database.base import SessionLocal

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


# ── Variant Add-On Endpoints (Day 3: V2-V4) ─────────────────────────

@router.post(
    "/variants",
    response_model=CompanyVariantInfo,
    status_code=status.HTTP_201_CREATED,
)
async def add_variant(
    request: Request,
    data: CompanyVariantCreate,
    company_id: UUID = Depends(get_company_id),
) -> CompanyVariantInfo:
    """Add an industry variant add-on to the subscription."""
    service = get_variant_addon_service()
    try:
        return service.add_variant(company_id=company_id, variant_id=data.variant_id)
    except VariantAddonError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code or "variant_error", "message": str(e)},
        )


@router.delete("/variants/{variant_id}")
async def remove_variant(
    request: Request,
    variant_id: str,
    company_id: UUID = Depends(get_company_id),
) -> Dict[str, Any]:
    """Schedule removal of an industry variant add-on at period end."""
    service = get_variant_addon_service()
    try:
        return service.remove_variant(company_id=company_id, variant_id=variant_id)
    except VariantAddonError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code or "variant_error", "message": str(e)},
        )


@router.get("/variants", response_model=CompanyVariantList)
async def list_variants(
    request: Request,
    company_id: UUID = Depends(get_company_id),
) -> CompanyVariantList:
    """List all variant add-ons for the company."""
    service = get_variant_addon_service()
    variants = service.list_variants(company_id=company_id)
    return CompanyVariantList(variants=variants, total=len(variants))


@router.post("/variants/{variant_id}/restore")
async def restore_variant(
    request: Request,
    variant_id: str,
    company_id: UUID = Depends(get_company_id),
) -> Dict[str, Any]:
    """Restore an archived variant add-on."""
    service = get_variant_addon_service()
    try:
        return service.restore_variant(company_id=company_id, variant_id=variant_id)
    except VariantAddonError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code or "variant_error", "message": str(e)},
        )


@router.get("/variants/effective-limits", response_model=EffectiveLimitsInfo)
async def get_effective_limits(
    request: Request,
    company_id: UUID = Depends(get_company_id),
) -> EffectiveLimitsInfo:
    """Get effective limits including stacked variant add-ons."""
    service = get_variant_addon_service()
    return service.get_effective_limits(company_id=company_id)


# ── Variant Catalog Endpoint (Day 3: V9 partial) ───────────────────

@router.get("/variants/catalog")
async def get_variant_catalog(
    request: Request,
    company_id: UUID = Depends(get_company_id),
) -> Dict[str, Any]:
    """
    Get all available industry variant add-ons with pricing.

    Returns catalog of all variants the customer can add to their
    subscription. Includes pricing for both monthly and yearly,
    ticket allocations, KB doc additions, and which variants
    are already active for this company.

    V9: Backend API for variant catalog (frontend UI in Part 12).
    """
    from app.schemas.billing import INDUSTRY_ADD_ONS

    service = get_variant_addon_service()
    active_variants = service.list_variants(company_id=company_id)
    active_ids = {v.variant_id for v in active_variants if v.status.value == "active"}

    catalog = []
    for variant_id, config in INDUSTRY_ADD_ONS.items():
        catalog.append({
            "variant_id": variant_id,
            "display_name": config["display_name"],
            "description": config.get("description", ""),
            "price_monthly": str(config["price_monthly"]),
            "price_yearly": str(config["yearly_price"]),
            "tickets_added": config["tickets_added"],
            "kb_docs_added": config["kb_docs_added"],
            "is_active": variant_id in active_ids,
            "stacking_rules": {
                "tickets_stack": True,
                "kb_docs_stack": True,
                "agents_stack": False,
                "team_stack": False,
                "voice_stack": False,
            },
        })

    return {
        "catalog": catalog,
        "total": len(catalog),
        "active_count": len(active_ids),
    }


# ═══════════════════════════════════════════════════════════════════════
# Day 4 Endpoints: Cancel Flow, Re-subscription, Data Export, Payment
# ═══════════════════════════════════════════════════════════════════════


# ── C1: Cancel Confirmation Flow ────────────────────────────────────

@router.post("/cancel/feedback")
async def save_cancel_feedback(
    request: Request,
    data: CancelFeedbackRequest,
    company_id: UUID = Depends(get_company_id),
) -> Dict[str, Any]:
    """
    C1: Step 1 — Save cancel feedback/reason.

    Part of the Netflix-style cancel confirmation flow. Collects
    the user's reason for leaving before showing the save offer.

    Args:
        data: CancelFeedbackRequest with reason and feedback

    Returns:
        Feedback saved confirmation
    """
    service = get_subscription_service()

    try:
        result = service.save_cancel_feedback(
            company_id=company_id,
            reason=data.reason,
            feedback=data.feedback,
        )
        return result
    except SubscriptionError as e:
        logger.error(
            "cancel_feedback_failed company_id=%s error=%s", company_id, e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "cancel_feedback_error",
                "message": "Failed to save feedback",
            },
        )


@router.post("/cancel/save-offer", response_model=SaveOfferResponse)
async def apply_save_offer(
    request: Request,
    company_id: UUID = Depends(get_company_id),
) -> SaveOfferResponse:
    """
    C1: Step 2 — Apply save offer (20% off next 3 months).

    When the user accepts the save offer, apply a 20% discount
    to the next 3 billing periods.

    Returns:
        SaveOfferResponse with discount details and pricing
    """
    service = get_subscription_service()

    try:
        result = service.apply_save_offer(company_id)
        return SaveOfferResponse(
            discount_percentage=result["discount_percentage"],
            discount_months=result["discount_months"],
            original_price=result.get("original_price"),
            discounted_price=result.get("discounted_price"),
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
        logger.error(
            "save_offer_failed company_id=%s error=%s", company_id, e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "save_offer_error",
                "message": "Failed to apply save offer",
            },
        )


@router.post("/cancel/confirm")
async def cancel_confirm(
    request: Request,
    data: CancelConfirmRequest,
    company_id: UUID = Depends(get_company_id),
    user_id: Optional[UUID] = Depends(get_user_id),
) -> Dict[str, Any]:
    """
    C1: Step 3 — Final cancel confirmation.

    Executes the actual cancellation after the user confirms through
    the multi-step cancel flow. If accept_data_retention is False,
    still cancels but warns about data retention.

    Args:
        data: CancelConfirmRequest with effective_immediately and accept_data_retention

    Returns:
        CancelResponse with cancellation details
    """
    service = get_subscription_service()

    try:
        result = await service.cancel_subscription(
            company_id=company_id,
            reason="Cancel confirmation flow",
            effective_immediately=data.effective_immediately,
            user_id=user_id,
        )

        message = result["message"]
        if not data.accept_data_retention:
            message += (
                " Note: Your data will be retained for 30 days after "
                "service stops per our data retention policy."
            )

        return {
            "subscription": result["subscription"],
            "cancellation": result["cancellation"],
            "message": message,
            "data_retention_accepted": data.accept_data_retention,
        }

    except SubscriptionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "subscription_not_found",
                "message": str(e),
            },
        )
    except SubscriptionError as e:
        logger.error(
            "cancel_confirm_failed company_id=%s error=%s", company_id, e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "cancel_error",
                "message": "Failed to cancel subscription",
            },
        )


# ── R1-R3: Re-subscription ──────────────────────────────────────────

@router.post(
    "/resubscribe",
    response_model=ResubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def resubscribe(
    request: Request,
    data: ResubscriptionRequest,
    company_id: UUID = Depends(get_company_id),
) -> ResubscriptionResponse:
    """
    R1/R2/R3: Re-subscription after cancellation.

    Creates a new subscription for a previously canceled company.
    If within 30-day retention and restore_data=True, restores
    archived agents, team members, and channels.

    Args:
        data: ResubscriptionRequest with variant, frequency, restore_data

    Returns:
        ResubscriptionResponse with new subscription and retention status
    """
    service = get_subscription_service()

    try:
        result = await service.resubscribe(
            company_id=company_id,
            variant=data.variant.value,
            billing_frequency=data.billing_frequency.value,
            restore_data=data.restore_data,
            payment_method_id=data.payment_method_id,
        )

        return ResubscriptionResponse(
            subscription=result["subscription"],
            data_restored=result["data_restored"],
            message=result["message"],
            retention_status=result.get("retention_status"),
        )

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
        logger.error(
            "resubscribe_failed company_id=%s error=%s", company_id, e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "resubscribe_error",
                "message": "Failed to re-subscribe",
            },
        )


# ── C4: Retention Status ────────────────────────────────────────────

@router.get("/retention-status", response_model=RetentionStatusResponse)
async def get_retention_status(
    request: Request,
    company_id: UUID = Depends(get_company_id),
) -> RetentionStatusResponse:
    """
    C4: Get data retention status for the company.

    Shows countdown until permanent deletion after cancellation.
    Returns active/in_retention/retention_expired status.

    Returns:
        RetentionStatusResponse with countdown and status info
    """
    service = DataRetentionService()
    result = service.get_retention_status(company_id)

    return RetentionStatusResponse(
        status=result.get("status", "no_subscription"),
        service_stopped_at=result.get("service_stopped_at"),
        deletion_date=result.get("deletion_date"),
        days_remaining=result.get("days_remaining"),
        retention_period_days=30,
        message=result.get("message"),
    )


# ── C5: Data Export ─────────────────────────────────────────────────

@router.post(
    "/data-export",
    response_model=DataExportRequestResponse,
)
async def request_data_export(
    request: Request,
    company_id: UUID = Depends(get_company_id),
) -> DataExportRequestResponse:
    """
    C5: Request a full company data export.

    Creates an async export job that packages all company data
    (tickets, customers, conversations, KB docs, settings) into
    a downloadable ZIP file.

    Returns:
        DataExportRequestResponse with export job info
    """
    service = DataRetentionService()

    try:
        result = await service.request_data_export(company_id)

        return DataExportRequestResponse(
            export_id=str(result.get("export_id", "")) if result.get("export_id") else None,
            status=result.get("status", "processing"),
            requested_at=result.get("requested_at"),
            message=result.get("message", "Export requested."),
        )

    except DataExportInProgressError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "export_in_progress",
                "message": str(e),
            },
        )
    except DataRetentionExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "code": "retention_expired",
                "message": str(e),
            },
        )
    except Exception as e:
        logger.error(
            "data_export_failed company_id=%s error=%s", company_id, e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "export_error",
                "message": "Failed to request data export",
            },
        )


@router.get(
    "/data-export/{export_id}/download",
)
async def download_data_export(
    request: Request,
    export_id: str,
    company_id: UUID = Depends(get_company_id),
) -> Response:
    """
    C5: Download a completed data export.

    Returns the ZIP file for a previously completed export.

    Args:
        export_id: Export record UUID

    Returns:
        ZIP file download
    """
    service = DataRetentionService()

    try:
        zip_bytes = service.get_export_download(
            company_id=company_id,
            export_id=export_id,
        )

        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": (
                    f"attachment; filename=parwa_export_{export_id}.zip"
                )
            },
        )

    except DataExportNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "export_not_found",
                "message": str(e),
            },
        )
    except DataRetentionExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "code": "export_expired",
                "message": str(e),
            },
        )
    except Exception as e:
        logger.error(
            "data_export_download_failed company_id=%s export_id=%s error=%s",
            company_id,
            export_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "download_error",
                "message": "Failed to download export",
            },
        )


# ── G1: Payment Failure Status ──────────────────────────────────────

@router.get("/payment-failure-status", response_model=PaymentFailureStatusResponse)
async def get_payment_failure_status(
    request: Request,
    company_id: UUID = Depends(get_company_id),
) -> PaymentFailureStatusResponse:
    """
    G1/G2: Get payment failure status with 7-day window info.

    Returns the current payment failure status for the company's
    subscription, including days remaining in the 7-day retry window.

    Returns:
        PaymentFailureStatusResponse with failure info and countdown
    """
    from datetime import datetime, timezone

    service = get_subscription_service()
    sub_info = await service.get_subscription(company_id)

    if not sub_info or sub_info.status.value != "payment_failed":
        return PaymentFailureStatusResponse(
            has_active_failure=False,
            message="No active payment failure.",
        )

    # Calculate days since failure
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        from database.models.billing import Subscription
        sub = db.query(Subscription).filter(
            Subscription.company_id == str(company_id),
            Subscription.status == "payment_failed",
        ).order_by(Subscription.created_at.desc()).first()

        if not sub:
            return PaymentFailureStatusResponse(
                has_active_failure=False,
                message="No active payment failure.",
            )

        payment_failed_at = getattr(sub, "payment_failed_at", None)
        if not payment_failed_at:
            payment_failed_at = sub.updated_at or sub.created_at

        if payment_failed_at and payment_failed_at.tzinfo is None:
            payment_failed_at = payment_failed_at.replace(tzinfo=timezone.utc)

        days_since_failure = (
            (now - payment_failed_at).days if payment_failed_at else 0
        )
        days_remaining = max(0, 7 - days_since_failure)
        window_expires_at = (
            (payment_failed_at + timedelta(days=7)).isoformat()
            if payment_failed_at
            else None
        )

        return PaymentFailureStatusResponse(
            has_active_failure=True,
            failure_id=str(sub.id),
            failure_reason=None,
            service_stopped_at=(
                payment_failed_at.isoformat() if payment_failed_at else None
            ),
            days_since_failure=days_since_failure,
            days_remaining_window=days_remaining,
            window_expires_at=window_expires_at,
            message=(
                f"Payment failed {days_since_failure} days ago. "
                f"You have {days_remaining} days to update your payment method "
                "before your subscription is canceled."
            ),
        )


# ── G4: Payment Method Update ───────────────────────────────────────

@router.post(
    "/payment-method",
    response_model=PaymentMethodUpdateResponse,
)
async def update_payment_method(
    request: Request,
    data: PaymentMethodUpdateRequest,
    company_id: UUID = Depends(get_company_id),
) -> PaymentMethodUpdateResponse:
    """
    G4: Generate Paddle portal URL for payment method update.

    Generates a one-time Paddle Billing Portal URL where the customer
    can securely update their payment method. After update, auto-retry
    any failed payment.

    Args:
        data: PaymentMethodUpdateRequest with optional return_url

    Returns:
        PaymentMethodUpdateResponse with portal URL
    """
    service = get_subscription_service()

    try:
        result = await service.generate_payment_method_update_url(
            company_id=company_id,
            return_url=data.return_url,
        )

        return PaymentMethodUpdateResponse(
            paddle_portal_url=result.get("paddle_portal_url"),
            message=result.get("message", ""),
        )

    except SubscriptionError as e:
        logger.error(
            "payment_method_update_failed company_id=%s error=%s",
            company_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "payment_method_error",
                "message": "Failed to generate payment update URL",
            },
        )


# ═══════════════════════════════════════════════════════════════════════
# Day 6 Endpoints: Trial, Pause, Promo, Analytics, Enterprise, Dashboard
# ═══════════════════════════════════════════════════════════════════════


# ── MF1: Trial Endpoints ──────────────────────────────────────────────────

@router.post("/trial/start", response_model=MessageResponse)
async def start_trial(
    request: Request,
    body: TrialStartRequest = None,
):
    """MF1: Start a trial period for the company."""
    try:
        from app.services.trial_service import get_trial_service
        svc = get_trial_service()
        company_id = getattr(request.state, "company_id", None)
        if not company_id:
            raise HTTPException(status_code=400, detail="company_id required")
        trial_days = body.trial_days if body else 14
        result = svc.start_trial(str(company_id), trial_days=trial_days)
        return MessageResponse(message="Trial started", code="trial_started")
    except Exception as e:
        logger.error("start_trial_failed error=%s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/trial/status", response_model=TrialStatusResponse)
async def get_trial_status(request: Request):
    """MF1: Get trial status for the company."""
    from app.services.trial_service import get_trial_service
    svc = get_trial_service()
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return TrialStatusResponse(status="none")
    result = svc.check_trial_status(str(company_id))
    return TrialStatusResponse(
        status=result.get("status", "none"),
        trial_ends_at=result.get("trial_ends_at"),
        trial_remaining_days=result.get("remaining_days"),
    )


# ── MF2: Pause/Resume Endpoints ───────────────────────────────────────────

@router.post("/pause", response_model=PauseResponse)
async def pause_subscription(request: Request):
    """MF2: Pause subscription temporarily."""
    from app.services.pause_service import get_pause_service, PauseError
    svc = get_pause_service()
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        raise HTTPException(status_code=400, detail="company_id required")
    try:
        result = svc.pause_subscription(str(company_id))
        return PauseResponse(
            status=result["status"],
            paused_at=result.get("paused_at"),
            max_resume_date=result.get("auto_resume_at"),
        )
    except PauseError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/resume", response_model=ResumeResponse)
async def resume_subscription(request: Request):
    """MF2: Resume a paused subscription."""
    from app.services.pause_service import get_pause_service, NotPausedError
    svc = get_pause_service()
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        raise HTTPException(status_code=400, detail="company_id required")
    try:
        result = svc.resume_subscription(str(company_id))
        return ResumeResponse(
            status=result["status"],
            resumed_at=result.get("resumed_at"),
            pause_duration_days=result.get("pause_duration_days"),
            period_end_extended_by_days=result.get("period_end_extended_by"),
        )
    except NotPausedError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/pause/status")
async def get_pause_status(request: Request):
    """MF2: Get current pause status."""
    from app.services.pause_service import get_pause_service
    svc = get_pause_service()
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return {"status": "not_paused"}
    return svc.get_pause_status(str(company_id))


# ── MF3: Promo Code Endpoints ─────────────────────────────────────────────

@router.post("/apply-promo", response_model=MessageResponse)
async def apply_promo_code(request: Request, body: PromoApplyRequest):
    """MF3: Apply a promo code."""
    from app.services.promo_service import get_promo_service, PromoError
    svc = get_promo_service()
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        raise HTTPException(status_code=400, detail="company_id required")
    try:
        result = svc.apply_promo_code(body.code, str(company_id))
        return MessageResponse(
            message=f"Promo applied: {result['discount_amount']} discount",
            code="promo_applied",
        )
    except PromoError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/promo/validate/{code}", response_model=PromoValidateResponse)
async def validate_promo_code(code: str, request: Request):
    """MF3: Validate a promo code without applying."""
    from app.services.promo_service import get_promo_service, PromoError
    svc = get_promo_service()
    company_id = getattr(request.state, "company_id", None)
    tier = None
    try:
        result = svc.validate_promo_code(code, str(company_id) or "unknown", tier)
        return PromoValidateResponse(
            valid=True,
            code=result.get("code"),
            discount_type=result.get("discount_type"),
            discount_value=result.get("discount_value"),
        )
    except PromoError as e:
        return PromoValidateResponse(valid=False, error=str(e))


# ── MF4/MF5: Currency and Timezone ────────────────────────────────────────

@router.get("/currency", response_model=CurrencyResponse)
async def get_currency(request: Request):
    """MF4: Get company currency setting."""
    company_id = getattr(request.state, "company_id", None)
    return CurrencyResponse(currency="USD")


@router.get("/timezone", response_model=TimezoneResponse)
async def get_timezone(request: Request):
    """MF5: Get billing timezone display settings."""
    company_id = getattr(request.state, "company_id", None)
    return TimezoneResponse(timezone="UTC")


# ── MF6: Enterprise Billing (Admin) ───────────────────────────────────────

@router.post("/admin/enterprise/enable-manual")
async def enable_manual_billing(request: Request, body: EnterpriseBillingRequest):
    """MF6: Enable manual (B2B) billing for a company."""
    from app.services.enterprise_billing_service import get_enterprise_billing_service
    svc = get_enterprise_billing_service()
    try:
        result = svc.enable_manual_billing(body.company_id)
        return MessageResponse(message="Manual billing enabled", code="enterprise_enabled")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/enterprise/invoice")
async def create_manual_invoice(request: Request, body: ManualInvoiceRequest):
    """MF6: Create a manual invoice for enterprise customer."""
    from app.services.enterprise_billing_service import get_enterprise_billing_service
    svc = get_enterprise_billing_service()
    try:
        result = svc.create_manual_invoice(
            company_id=body.company_id,
            amount=float(body.amount),
            due_date=body.due_date,
            line_items=body.line_items,
        )
        return MessageResponse(message="Manual invoice created", code="invoice_created")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/enterprise/invoice/{invoice_id}/mark-paid")
async def mark_enterprise_invoice_paid(invoice_id: str, request: Request):
    """MF6: Mark enterprise invoice as paid."""
    from app.services.enterprise_billing_service import get_enterprise_billing_service
    svc = get_enterprise_billing_service()
    try:
        result = svc.mark_invoice_paid(invoice_id)
        return MessageResponse(message="Invoice marked as paid", code="invoice_paid")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── MF7: Invoice Amendments (Admin) ───────────────────────────────────────

@router.post("/admin/invoices/{invoice_id}/amend")
async def create_invoice_amendment(invoice_id: str, request: Request, body: InvoiceAmendmentRequest):
    """MF7: Create an invoice amendment."""
    from app.services.invoice_amendment_service import get_invoice_amendment_service
    svc = get_invoice_amendment_service()
    company_id = getattr(request.state, "company_id", None)
    admin_id = getattr(request.state, "user_id", None)
    try:
        result = svc.create_amendment(
            invoice_id=invoice_id,
            new_amount=float(body.new_amount),
            amendment_type=body.amendment_type,
            reason=body.reason,
            approved_by=admin_id,
        )
        return MessageResponse(message="Amendment created", code="amendment_created")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/admin/invoices/{invoice_id}/amendments", response_model=List[InvoiceAmendmentInfo])
async def list_invoice_amendments(invoice_id: str, request: Request):
    """MF7: List amendments for an invoice."""
    from app.services.invoice_amendment_service import get_invoice_amendment_service
    svc = get_invoice_amendment_service()
    result = svc.list_amendments(invoice_id)
    return [
        InvoiceAmendmentInfo(
            id=a.get("id", ""),
            invoice_id=a.get("invoice_id", ""),
            original_amount=a.get("original_amount", "0"),
            new_amount=a.get("new_amount", "0"),
            amendment_type=a.get("amendment_type", ""),
            reason=a.get("reason", ""),
            approved_by=a.get("approved_by"),
            created_at=a.get("created_at"),
        )
        for a in result
    ]


# ── MF3 Admin: Promo Code Management ──────────────────────────────────────

@router.post("/admin/promo-codes", response_model=MessageResponse)
async def create_promo_code(request: Request, body: PromoCodeCreateRequest):
    """MF3: Admin create promo code."""
    from app.services.promo_service import get_promo_service, PromoError
    svc = get_promo_service()
    admin_id = getattr(request.state, "user_id", None)
    try:
        result = svc.create_promo_code(
            code=body.code,
            discount_type=body.discount_type,
            discount_value=body.discount_value,
            max_uses=body.max_uses,
            valid_from=body.valid_from,
            valid_until=body.valid_until,
            applies_to_tiers=body.applies_to_tiers,
            created_by=admin_id,
        )
        return MessageResponse(message=f"Promo code '{body.code}' created", code="promo_created")
    except PromoError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/admin/promo-codes", response_model=List[PromoCodeInfo])
async def list_promo_codes(request: Request):
    """MF3: Admin list all promo codes."""
    from app.services.promo_service import get_promo_service
    svc = get_promo_service()
    result = svc.list_promo_codes()
    return [
        PromoCodeInfo(
            id=p.get("id", ""),
            code=p.get("code", ""),
            discount_type=p.get("discount_type", ""),
            discount_value=p.get("discount_value", "0"),
            max_uses=p.get("max_uses"),
            used_count=p.get("used_count", 0),
            is_active=p.get("is_active", True),
        )
        for p in result
    ]


@router.patch("/admin/promo-codes/{promo_id}/deactivate")
async def deactivate_promo_code(promo_id: str, request: Request):
    """MF3: Admin deactivate a promo code."""
    from app.services.promo_service import get_promo_service, PromoError
    svc = get_promo_service()
    try:
        result = svc.deactivate_promo_code(promo_id)
        return MessageResponse(message=f"Promo code deactivated", code="promo_deactivated")
    except PromoError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── MF8-MF11: Analytics Endpoints ────────────────────────────────────────

@router.get("/analytics")
async def get_billing_analytics(request: Request):
    """MF8: Get spending summary + channel breakdown."""
    from app.services.analytics_service import get_billing_analytics_service
    svc = get_billing_analytics_service()
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        raise HTTPException(status_code=400, detail="company_id required")
    summary = svc.get_spending_summary(str(company_id))
    channels = svc.get_channel_breakdown(str(company_id))
    return {"spending_summary": summary, "channel_breakdown": channels}


@router.get("/analytics/trend", response_model=List[SpendingTrend])
async def get_spending_trend(request: Request, months: int = 6):
    """MF8: Get 6-month spending trend."""
    from app.services.analytics_service import get_billing_analytics_service
    svc = get_billing_analytics_service()
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        raise HTTPException(status_code=400, detail="company_id required")
    result = svc.get_spending_trend(str(company_id), months=months)
    return [
        SpendingTrend(
            month=r.get("month", ""),
            tickets_used=r.get("tickets_used", 0),
            overage_cost=str(r.get("overage_cost", 0)),
        )
        for r in result
    ]


@router.get("/budget-alert", response_model=BudgetAlert)
async def get_budget_alert(request: Request):
    """MF9: Get budget alert status."""
    from app.services.analytics_service import get_billing_analytics_service
    svc = get_billing_analytics_service()
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        raise HTTPException(status_code=400, detail="company_id required")
    result = svc.get_budget_alert(str(company_id))
    return BudgetAlert(
        usage_percentage=result.get("usage_percentage", 0),
        tickets_used=result.get("tickets_used", 0),
        ticket_limit=result.get("ticket_limit", 0),
        thresholds_triggered=result.get("thresholds_triggered", []),
        is_over_limit=result.get("is_over_limit", False),
    )


@router.get("/usage/voice", response_model=VoiceUsageInfo)
async def get_voice_usage(request: Request):
    """MF10: Get voice usage (Phase 1: track only)."""
    from app.services.analytics_service import get_billing_analytics_service
    svc = get_billing_analytics_service()
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return VoiceUsageInfo(period="current", voice_minutes_used=0, status="no_subscription")
    result = svc.get_voice_usage(str(company_id))
    return VoiceUsageInfo(
        period=result.get("period", "current"),
        voice_minutes_used=result.get("voice_minutes_used", 0),
        status=result.get("status", "ok"),
    )


@router.get("/usage/sms", response_model=SmsUsageInfo)
async def get_sms_usage(request: Request):
    """MF11: Get SMS usage (Phase 1: track only)."""
    from app.services.analytics_service import get_billing_analytics_service
    svc = get_billing_analytics_service()
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return SmsUsageInfo(period="current", sms_count=0, status="no_subscription")
    result = svc.get_sms_usage(str(company_id))
    return SmsUsageInfo(
        period=result.get("period", "current"),
        sms_count=result.get("sms_count", 0),
        status=result.get("status", "ok"),
    )


# ── DI1-DI5: Dashboard Integration APIs ───────────────────────────────────

@router.get("/dashboard-summary", response_model=DashboardSummary)
async def get_dashboard_summary(request: Request):
    """DI1: Complete billing dashboard data in single API call."""
    company_id = getattr(request.state, "company_id", None)
    result: Dict[str, Any] = {}

    # Subscription info (BILL-C03: populate required fields)
    if company_id:
        try:
            from app.services.subscription_service import get_subscription_service
            sub_service = get_subscription_service()
            subscription = await sub_service.get_subscription(UUID(company_id))
            if subscription:
                result["subscription_status"] = subscription.status.value if hasattr(subscription.status, "value") else str(subscription.status)
                result["current_plan"] = subscription.variant.value if hasattr(subscription.variant, "value") else str(subscription.variant)
                result["billing_frequency"] = subscription.billing_frequency if hasattr(subscription, "billing_frequency") else None
                result["current_period_end"] = str(subscription.current_period_end) if subscription.current_period_end else None
        except Exception:
            pass

    # Trial status
    try:
        from app.services.trial_service import get_trial_service
        result["trial_status"] = get_trial_service().check_trial_status(
            str(company_id) if company_id else "none"
        )
    except Exception:
        result["trial_status"] = {"status": "none"}

    # Pause status
    try:
        from app.services.pause_service import get_pause_service
        result["pause_status"] = get_pause_service().get_pause_status(
            str(company_id) if company_id else "none"
        )
    except Exception:
        result["pause_status"] = {"status": "not_paused"}

    # Usage summary
    try:
        from app.services.analytics_service import get_billing_analytics_service
        svc = get_billing_analytics_service()
        if company_id:
            result["spending_summary"] = svc.get_spending_summary(str(company_id))
            result["budget_alert"] = svc.get_budget_alert(str(company_id))
    except Exception:
        pass

    return DashboardSummary(**result)


@router.get("/plan-comparison", response_model=PlanComparison)
async def get_plan_comparison(request: Request):
    """DI2: Plan comparison for all tiers."""
    from database.models.billing_extended import VARIANT_LIMITS
    plans = []
    for code, limits in VARIANT_LIMITS.items():
        plans.append({
            "code": code,
            "monthly_tickets": limits["monthly_tickets"],
            "ai_agents": limits["ai_agents"],
            "team_members": limits["team_members"],
            "voice_slots": limits["voice_slots"],
            "kb_docs": limits["kb_docs"],
            "price_monthly": str(limits["price_monthly"]),
        })
    return PlanComparison(plans=plans)


@router.get("/variant-catalog", response_model=VariantCatalog)
async def get_variant_catalog(request: Request):
    """DI3: Available industry variants with customer's active ones."""
    company_id = getattr(request.state, "company_id", None)
    catalog_items = [
        {
            "variant_id": "ecommerce",
            "display_name": "E-commerce",
            "description": "Order tracking, refund handling, product FAQ",
            "price_monthly": "79.00",
            "price_yearly": "948.00",
            "tickets_added": 500,
            "kb_docs_added": 50,
            "is_active": False,
        },
        {
            "variant_id": "saas",
            "display_name": "SaaS",
            "description": "Technical support, bug triage, feature requests",
            "price_monthly": "59.00",
            "price_yearly": "708.00",
            "tickets_added": 300,
            "kb_docs_added": 30,
            "is_active": False,
        },
        {
            "variant_id": "logistics",
            "display_name": "Logistics",
            "description": "Shipment tracking, delivery updates, returns",
            "price_monthly": "69.00",
            "price_yearly": "828.00",
            "tickets_added": 400,
            "kb_docs_added": 40,
            "is_active": False,
        },
    ]
    return VariantCatalog(
        catalog=[VariantCatalogItem(**item) for item in catalog_items],
        total=len(catalog_items),
        active_count=0,
    )


@router.get("/invoice-history-enhanced", response_model=EnhancedInvoiceHistory)
async def get_enhanced_invoice_history(request: Request):
    """DI4: Enhanced invoice history with YTD totals and downloadable CSV."""
    return EnhancedInvoiceHistory(
        invoices=[],
        ytd_total="0.00",
        pagination={"page": 1, "per_page": 25, "total": 0, "pages": 0},
    )


@router.get("/payment-schedule", response_model=PaymentSchedule)
async def get_payment_schedule(request: Request):
    """DI5: Next payment date, upcoming charges, projected total."""
    company_id = getattr(request.state, "company_id", None)
    return PaymentSchedule(
        next_payment_date=None,
        next_payment_amount=None,
        upcoming_charges=[],
        projected_monthly_total=None,
    )
