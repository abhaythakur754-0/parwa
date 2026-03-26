"""
PARWA Billing API Routes.
Provides endpoints for subscription management, invoices, payment methods, and usage tracking.
All data is company-scoped for RLS compliance.
CRITICAL: Stripe is NEVER called without a pending_approval record existing first.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db
from backend.models.subscription import Subscription
from backend.models.company import Company, PlanTierEnum
from backend.models.user import User, RoleEnum
from backend.models.usage_log import UsageLog, AITier
from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger
from shared.core_functions.security import decode_access_token
from shared.utils.cache import Cache

# Expose Cache for testing
__all__ = ["router", "mask_stripe_id", "validate_plan_tier", "PLAN_PRICING", "is_token_blacklisted", "Cache"]

# Initialize router and logger
router = APIRouter(prefix="/billing", tags=["Billing"])
logger = get_logger(__name__)
settings = get_settings()
security = HTTPBearer()


# --- Plan Tier Pricing Configuration ---

PLAN_PRICING = {
    "mini": {"monthly_cents": 100000, "max_calls": 2, "sms": False, "refund_execution": False},
    "parwa": {"monthly_cents": 250000, "max_calls": 3, "sms": True, "refund_execution": True},
    "parwa_high": {"monthly_cents": 450000, "max_calls": 5, "sms": True, "refund_execution": True},
}


# --- Pydantic Schemas ---

class SubscriptionResponse(BaseModel):
    """Response schema for subscription details."""
    id: uuid.UUID = Field(..., description="Subscription ID")
    company_id: uuid.UUID = Field(..., description="Company ID")
    plan_tier: str = Field(..., description="Current plan tier")
    status: str = Field(..., description="Subscription status")
    current_period_start: datetime = Field(..., description="Billing period start")
    current_period_end: datetime = Field(..., description="Billing period end")
    amount_cents: int = Field(..., description="Monthly amount in cents")
    currency: str = Field(default="usd", description="Currency code")
    stripe_subscription_id: Optional[str] = Field(None, description="Stripe subscription ID (masked)")


class SubscriptionUpdateRequest(BaseModel):
    """Request schema for updating subscription tier."""
    plan_tier: str = Field(..., description="New plan tier (mini, parwa, parwa_high)")


class SubscriptionUpdateResponse(BaseModel):
    """Response schema for subscription update."""
    message: str = Field(..., description="Update status message")
    old_tier: str = Field(..., description="Previous plan tier")
    new_tier: str = Field(..., description="New plan tier")
    requires_payment: bool = Field(..., description="Whether additional payment is required")
    prorated_amount_cents: Optional[int] = Field(None, description="Prorated difference in cents")


class InvoiceItem(BaseModel):
    """Schema for invoice line item."""
    description: str = Field(..., description="Item description")
    amount_cents: int = Field(..., description="Amount in cents")
    quantity: int = Field(default=1, description="Quantity")


class InvoiceResponse(BaseModel):
    """Response schema for invoice details."""
    id: uuid.UUID = Field(..., description="Invoice ID")
    company_id: uuid.UUID = Field(..., description="Company ID")
    subscription_id: uuid.UUID = Field(..., description="Associated subscription ID")
    amount_cents: int = Field(..., description="Total amount in cents")
    currency: str = Field(default="usd", description="Currency code")
    status: str = Field(..., description="Invoice status")
    due_date: datetime = Field(..., description="Payment due date")
    paid_at: Optional[datetime] = Field(None, description="When invoice was paid")
    items: List[InvoiceItem] = Field(default_factory=list, description="Invoice line items")
    created_at: datetime = Field(..., description="Invoice creation date")


class InvoiceListResponse(BaseModel):
    """Response schema for invoice list."""
    invoices: List[InvoiceResponse] = Field(..., description="List of invoices")
    total_count: int = Field(..., description="Total number of invoices")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Items per page")


class PaymentMethodRequest(BaseModel):
    """Request schema for adding a payment method."""
    payment_method_type: str = Field(default="card", description="Payment method type")
    token: str = Field(..., description="Payment provider token (mocked)")
    is_default: bool = Field(default=False, description="Set as default payment method")


class PaymentMethodResponse(BaseModel):
    """Response schema for payment method."""
    id: uuid.UUID = Field(..., description="Payment method ID")
    type: str = Field(..., description="Payment method type")
    last_four: str = Field(..., description="Last 4 digits (masked)")
    expiry_month: Optional[int] = Field(None, description="Expiry month")
    expiry_year: Optional[int] = Field(None, description="Expiry year")
    is_default: bool = Field(..., description="Is default payment method")


class UsageLimit(BaseModel):
    """Schema for usage limit information."""
    tier: str = Field(..., description="Current plan tier")
    max_calls: int = Field(..., description="Maximum concurrent calls allowed")
    sms_enabled: bool = Field(..., description="SMS feature enabled")
    refund_execution: bool = Field(..., description="Refund execution enabled")


class UsageStats(BaseModel):
    """Schema for usage statistics."""
    total_requests: int = Field(..., description="Total API requests")
    total_tokens: int = Field(..., description="Total tokens used")
    light_tier_requests: int = Field(default=0, description="Light tier request count")
    medium_tier_requests: int = Field(default=0, description="Medium tier request count")
    heavy_tier_requests: int = Field(default=0, description="Heavy tier request count")
    error_count: int = Field(default=0, description="Error count")
    avg_latency_ms: Optional[float] = Field(None, description="Average latency")


class UsageResponse(BaseModel):
    """Response schema for usage information."""
    company_id: uuid.UUID = Field(..., description="Company ID")
    billing_period_start: datetime = Field(..., description="Billing period start")
    billing_period_end: datetime = Field(..., description="Billing period end")
    limits: UsageLimit = Field(..., description="Plan limits")
    usage: UsageStats = Field(..., description="Current usage statistics")
    usage_percentage: float = Field(..., description="Usage as percentage of typical allocation")


class MessageResponse(BaseModel):
    """Generic message response schema."""
    message: str = Field(..., description="Response message")


# --- Helper Functions ---

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Extract and validate the current user from JWT token.

    Args:
        credentials: HTTP Bearer credentials containing the JWT token.
        db: Async database session.

    Returns:
        User: The authenticated user instance.

    Raises:
        HTTPException: If token is invalid, expired, or user not found.
    """
    token = credentials.credentials

    try:
        payload = decode_access_token(token, settings.secret_key.get_secret_value())
    except ValueError as e:
        logger.warning({"event": "token_decode_failed", "error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if token is blacklisted
    if await is_token_blacklisted(token):
        logger.warning({"event": "blacklisted_token_used", "user_id": payload.get("sub")})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from database
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


async def is_token_blacklisted(token: str) -> bool:
    """
    Check if a token is in the Redis blacklist.

    Args:
        token: The JWT token to check.

    Returns:
        bool: True if token is blacklisted, False otherwise.
    """
    try:
        cache = Cache()
        exists = await cache.exists(f"blacklist:{token}")
        await cache.close()
        return exists
    except Exception as e:
        logger.error({"event": "blacklist_check_failed", "error": str(e)})
        return False


def require_manager_role(user: User) -> None:
    """
    Validate that user has manager or admin role.

    Args:
        user: The user to validate.

    Raises:
        HTTPException: If user lacks required permissions.
    """
    # Handle both string and enum role values
    user_role = user.role.value if isinstance(user.role, RoleEnum) else user.role
    valid_roles = [RoleEnum.admin.value, RoleEnum.manager.value]
    
    if user_role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers or admins can perform this action",
        )


def mask_stripe_id(stripe_id: Optional[str]) -> Optional[str]:
    """
    Mask a Stripe ID for safe display.

    Args:
        stripe_id: The full Stripe ID.

    Returns:
        Optional[str]: Masked ID showing only last 4 characters.
    """
    if not stripe_id:
        return None
    if len(stripe_id) < 4:
        return "***"
    return f"***{stripe_id[-4:]}"


def validate_plan_tier(plan_tier: str) -> str:
    """
    Validate plan tier value.

    Args:
        plan_tier: The plan tier to validate.

    Returns:
        str: Validated plan tier.

    Raises:
        HTTPException: If plan tier is invalid.
    """
    valid_tiers = ["mini", "parwa", "parwa_high"]
    if plan_tier not in valid_tiers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan tier. Must be one of: {', '.join(valid_tiers)}",
        )
    return plan_tier


# --- API Endpoints ---

@router.get(
    "/subscription",
    response_model=SubscriptionResponse,
    summary="Get current subscription",
    description="Retrieve the current subscription details for the user's company."
)
async def get_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> SubscriptionResponse:
    """
    Get current subscription details.

    Returns the active subscription for the user's company including
    plan tier, billing period, and status.

    Args:
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        SubscriptionResponse: Current subscription details.

    Raises:
        HTTPException: 404 if no active subscription found.
    """
    company_id = current_user.company_id

    # Fetch active subscription
    result = await db.execute(
        select(Subscription)
        .where(
            and_(
                Subscription.company_id == company_id,
                Subscription.status == "active"
            )
        )
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found for your company",
        )

    logger.info({
        "event": "subscription_retrieved",
        "user_id": str(current_user.id),
        "company_id": str(company_id),
        "subscription_id": str(subscription.id),
    })

    return SubscriptionResponse(
        id=subscription.id,
        company_id=subscription.company_id,
        plan_tier=subscription.plan_tier,
        status=subscription.status,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        amount_cents=subscription.amount_cents,
        currency=subscription.currency,
        stripe_subscription_id=mask_stripe_id(subscription.stripe_subscription_id),
    )


@router.put(
    "/subscription",
    response_model=SubscriptionUpdateResponse,
    summary="Update subscription tier",
    description="Update the subscription plan tier. Requires manager or admin role."
)
async def update_subscription(
    request: SubscriptionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> SubscriptionUpdateResponse:
    """
    Update subscription tier.

    Changes the company's subscription plan tier. Downgrades take effect
    at the end of the billing period. Upgrades are immediate with prorated billing.

    CRITICAL: Stripe is NOT called directly. A pending_approval record must exist
    before any payment processing occurs.

    Args:
        request: Contains the new plan tier.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        SubscriptionUpdateResponse: Update confirmation and billing details.

    Raises:
        HTTPException: 403 if not authorized, 404 if no subscription found.
    """
    # Validate permissions
    require_manager_role(current_user)

    # Validate new tier
    new_tier = validate_plan_tier(request.plan_tier)
    company_id = current_user.company_id

    # Fetch current subscription
    result = await db.execute(
        select(Subscription)
        .where(
            and_(
                Subscription.company_id == company_id,
                Subscription.status == "active"
            )
        )
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found",
        )

    old_tier = subscription.plan_tier

    if old_tier == new_tier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Already on {new_tier} plan",
        )

    # Calculate prorated amount
    old_price = PLAN_PRICING.get(old_tier, {}).get("monthly_cents", 0)
    new_price = PLAN_PRICING.get(new_tier, {}).get("monthly_cents", 0)
    prorated_amount = new_price - old_price

    is_upgrade = new_price > old_price

    # Log the tier change request
    # NOTE: We do NOT call Stripe here. The pending_approval workflow handles payment.
    logger.info({
        "event": "subscription_tier_change_requested",
        "user_id": str(current_user.id),
        "company_id": str(company_id),
        "old_tier": old_tier,
        "new_tier": new_tier,
        "prorated_amount_cents": prorated_amount,
        "requires_payment": is_upgrade,
    })

    # For downgrades, update immediately (takes effect at period end in real impl)
    # For upgrades, require payment approval first
    if not is_upgrade:
        subscription.plan_tier = new_tier
        subscription.amount_cents = new_price
        await db.flush()

    return SubscriptionUpdateResponse(
        message="Subscription update processed. Payment approval required." if is_upgrade else "Subscription updated successfully.",
        old_tier=old_tier,
        new_tier=new_tier,
        requires_payment=is_upgrade,
        prorated_amount_cents=prorated_amount if is_upgrade else None,
    )


@router.get(
    "/invoices",
    response_model=InvoiceListResponse,
    summary="List invoices",
    description="Retrieve a paginated list of invoices for the company."
)
async def list_invoices(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> InvoiceListResponse:
    """
    List invoices for the company.

    Returns a paginated list of invoices with optional status filtering.

    Args:
        page: Page number for pagination.
        page_size: Number of items per page.
        status_filter: Optional status filter (draft, open, paid, void).
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        InvoiceListResponse: Paginated list of invoices.
    """
    company_id = current_user.company_id
    offset = (page - 1) * page_size

    # Build mock invoices (in production, these would come from a invoices table)
    # For now, return mock data based on subscription
    result = await db.execute(
        select(Subscription)
        .where(Subscription.company_id == company_id)
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    subscription = result.scalar_one_or_none()

    invoices = []
    if subscription:
        # Generate mock invoices for the last 3 billing periods
        for i in range(3):
            invoice_id = uuid.uuid4()
            due_date = subscription.current_period_end
            paid_at = due_date if i > 0 else None  # First invoice is unpaid

            invoice = InvoiceResponse(
                id=invoice_id,
                company_id=company_id,
                subscription_id=subscription.id,
                amount_cents=subscription.amount_cents,
                currency=subscription.currency,
                status="paid" if paid_at else "open",
                due_date=due_date,
                paid_at=paid_at,
                items=[
                    InvoiceItem(
                        description=f"PARWA {subscription.plan_tier} subscription",
                        amount_cents=subscription.amount_cents,
                        quantity=1,
                    )
                ],
                created_at=subscription.current_period_start,
            )

            # Apply status filter
            if status_filter and invoice.status != status_filter:
                continue

            invoices.append(invoice)

    logger.info({
        "event": "invoices_listed",
        "user_id": str(current_user.id),
        "company_id": str(company_id),
        "count": len(invoices),
    })

    return InvoiceListResponse(
        invoices=invoices,
        total_count=len(invoices),
        page=page,
        page_size=page_size,
    )


@router.get(
    "/invoices/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Get invoice details",
    description="Retrieve details for a specific invoice."
)
async def get_invoice(
    invoice_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> InvoiceResponse:
    """
    Get invoice details.

    Returns detailed information about a specific invoice.

    Args:
        invoice_id: The UUID of the invoice.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        InvoiceResponse: Invoice details.

    Raises:
        HTTPException: 404 if invoice not found.
    """
    company_id = current_user.company_id

    # Fetch subscription for mock invoice generation
    result = await db.execute(
        select(Subscription)
        .where(Subscription.company_id == company_id)
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found for invoice",
        )

    # Return mock invoice (in production, fetch from invoices table)
    logger.info({
        "event": "invoice_retrieved",
        "user_id": str(current_user.id),
        "company_id": str(company_id),
        "invoice_id": str(invoice_id),
    })

    return InvoiceResponse(
        id=invoice_id,
        company_id=company_id,
        subscription_id=subscription.id,
        amount_cents=subscription.amount_cents,
        currency=subscription.currency,
        status="open",
        due_date=subscription.current_period_end,
        paid_at=None,
        items=[
            InvoiceItem(
                description=f"PARWA {subscription.plan_tier} subscription",
                amount_cents=subscription.amount_cents,
                quantity=1,
            )
        ],
        created_at=subscription.current_period_start,
    )


@router.post(
    "/payment-method",
    response_model=PaymentMethodResponse,
    summary="Add payment method",
    description="Add a new payment method to the company account. Payment processing is mocked."
)
async def add_payment_method(
    request: PaymentMethodRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> PaymentMethodResponse:
    """
    Add a payment method.

    Adds a new payment method to the company's billing account.
    Payment processing is mocked - no actual Stripe calls are made.

    CRITICAL: This endpoint does NOT call Stripe. Payment methods are
    stored via secure token and require approval workflow for charges.

    Args:
        request: Payment method details including provider token.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        PaymentMethodResponse: Added payment method details.

    Raises:
        HTTPException: 403 if not authorized.
    """
    # Validate permissions
    require_manager_role(current_user)

    # Validate payment method type
    valid_types = ["card", "bank_account"]
    if request.payment_method_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid payment method type. Must be one of: {', '.join(valid_types)}",
        )

    # Mock payment method creation
    # In production, this would create a pending_approval record before any Stripe call
    payment_method_id = uuid.uuid4()

    logger.info({
        "event": "payment_method_added",
        "user_id": str(current_user.id),
        "company_id": str(current_user.company_id),
        "payment_method_id": str(payment_method_id),
        "type": request.payment_method_type,
        "is_default": request.is_default,
        # Note: Never log the actual token
    })

    return PaymentMethodResponse(
        id=payment_method_id,
        type=request.payment_method_type,
        last_four="4242",  # Mock last 4 digits
        expiry_month=12,
        expiry_year=2025,
        is_default=request.is_default,
    )


@router.get(
    "/usage",
    response_model=UsageResponse,
    summary="Get usage statistics",
    description="Retrieve current usage statistics and plan limits."
)
async def get_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UsageResponse:
    """
    Get usage statistics and plan limits.

    Returns current usage statistics including API requests, tokens,
    and feature availability based on the company's plan tier.

    Args:
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        UsageResponse: Usage statistics and limits.

    Raises:
        HTTPException: 404 if no subscription found.
    """
    company_id = current_user.company_id

    # Fetch current subscription
    sub_result = await db.execute(
        select(Subscription)
        .where(
            and_(
                Subscription.company_id == company_id,
                Subscription.status == "active"
            )
        )
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    subscription = sub_result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found",
        )

    plan_tier = subscription.plan_tier
    plan_config = PLAN_PRICING.get(plan_tier, PLAN_PRICING["mini"])

    # Fetch usage logs for current billing period
    usage_result = await db.execute(
        select(
            UsageLog.ai_tier,
            func.sum(UsageLog.request_count).label("total_requests"),
            func.sum(UsageLog.token_count).label("total_tokens"),
            func.sum(UsageLog.error_count).label("total_errors"),
            func.avg(UsageLog.avg_latency_ms).label("avg_latency"),
        )
        .where(
            and_(
                UsageLog.company_id == company_id,
                UsageLog.log_date >= subscription.current_period_start.date(),
                UsageLog.log_date <= subscription.current_period_end.date(),
            )
        )
        .group_by(UsageLog.ai_tier)
    )
    usage_rows = usage_result.all()

    # Aggregate usage by tier
    tier_usage = {tier.value: {"requests": 0, "tokens": 0} for tier in AITier}
    total_requests = 0
    total_tokens = 0
    total_errors = 0
    avg_latency = None

    for row in usage_rows:
        tier = row.ai_tier.value if row.ai_tier else "light"
        tier_usage[tier]["requests"] = row.total_requests or 0
        tier_usage[tier]["tokens"] = row.total_tokens or 0
        total_requests += row.total_requests or 0
        total_tokens += row.total_tokens or 0
        total_errors += row.total_errors or 0
        if row.avg_latency:
            avg_latency = row.avg_latency

    # Calculate usage percentage (based on typical allocation)
    # Assume 100,000 tokens per month as baseline for "full usage"
    baseline_tokens = 100000
    usage_percentage = (total_tokens / baseline_tokens * 100) if baseline_tokens > 0 else 0.0

    logger.info({
        "event": "usage_retrieved",
        "user_id": str(current_user.id),
        "company_id": str(company_id),
        "total_requests": total_requests,
        "total_tokens": total_tokens,
    })

    return UsageResponse(
        company_id=company_id,
        billing_period_start=subscription.current_period_start,
        billing_period_end=subscription.current_period_end,
        limits=UsageLimit(
            tier=plan_tier,
            max_calls=plan_config["max_calls"],
            sms_enabled=plan_config["sms"],
            refund_execution=plan_config["refund_execution"],
        ),
        usage=UsageStats(
            total_requests=total_requests,
            total_tokens=total_tokens,
            light_tier_requests=tier_usage["light"]["requests"],
            medium_tier_requests=tier_usage["medium"]["requests"],
            heavy_tier_requests=tier_usage["heavy"]["requests"],
            error_count=total_errors,
            avg_latency_ms=round(avg_latency, 2) if avg_latency else None,
        ),
        usage_percentage=round(usage_percentage, 2),
    )
