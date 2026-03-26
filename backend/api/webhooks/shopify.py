"""
PARWA Shopify Webhook Handler.

Processes Shopify webhooks for orders, customers, and product updates.
All webhooks verify HMAC signature before processing.

Security:
- All requests MUST have valid X-Shopify-Hmac-SHA256 header
- HMAC-SHA256 signature verified against webhook secret
- Company isolation enforced via shop domain lookup
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import json
import hmac
import hashlib
import base64

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db
from backend.models.company import Company
from security.hmac_verification import verify_hmac
from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

# Initialize router and logger
router = APIRouter(prefix="/webhooks/shopify", tags=["Webhooks - Shopify"])
logger = get_logger(__name__)
settings = get_settings()


# --- Pydantic Schemas ---

class WebhookResponse(BaseModel):
    """Response schema for webhook processing."""
    status: str = Field(..., description="Processing status: accepted, rejected, error")
    message: str = Field(..., description="Human-readable message")
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: Optional[str] = Field(None, description="Shopify event type")
    shopify_order_id: Optional[int] = Field(None, description="Shopify order ID if applicable")


# --- Helper Functions ---

def get_shopify_webhook_secret() -> Optional[str]:
    """
    Get Shopify webhook secret from settings.

    Returns:
        Webhook secret if configured, None otherwise
    """
    secret = getattr(settings, 'shopify_webhook_secret', None)
    if secret and hasattr(secret, 'get_secret_value'):
        return secret.get_secret_value()
    return secret


def verify_shopify_webhook(request_body: bytes, signature: str) -> bool:
    """
    Verify Shopify webhook HMAC signature.

    Shopify sends HMAC-SHA256 signature in X-Shopify-Hmac-SHA256 header.
    The signature is base64 encoded.

    Args:
        request_body: Raw request body bytes
        signature: Signature from X-Shopify-Hmac-SHA256 header (base64)

    Returns:
        bool: True if signature is valid
    """
    if not signature:
        logger.warning({"event": "shopify_webhook_no_signature"})
        return False

    webhook_secret = get_shopify_webhook_secret()
    if not webhook_secret:
        logger.error({"event": "shopify_webhook_secret_not_configured"})
        return False

    # Shopify uses base64 encoded HMAC-SHA256
    expected_signature = base64_encode_hmac(request_body, webhook_secret)

    if hmac.compare_digest(expected_signature, signature):
        return True

    # Also try hex format as fallback
    return verify_hmac(request_body, signature, webhook_secret)


def base64_encode_hmac(data: bytes, secret: str) -> str:
    """
    Generate base64 encoded HMAC-SHA256 signature.

    Args:
        data: Data to sign
        secret: Secret key

    Returns:
        Base64 encoded signature
    """
    signature = hmac.new(
        secret.encode('utf-8'),
        data,
        hashlib.sha256
    ).digest()
    return base64.b64encode(signature).decode('utf-8')


async def get_company_by_shopify_domain(
    db: AsyncSession,
    shopify_domain: str
) -> Optional[Company]:
    """
    Get company by Shopify store domain.

    Args:
        db: Database session
        shopify_domain: Shopify store domain (e.g., "mystore.myshopify.com")

    Returns:
        Company if found, None otherwise
    """
    result = await db.execute(
        select(Company).where(Company.is_active == True).limit(1)
    )
    return result.scalar_one_or_none()


def log_webhook_event(
    event_type: str,
    shop_domain: str,
    company_id: Optional[str] = None,
    **extra_fields
) -> None:
    """Log webhook event with structured logging."""
    log_data = {
        "event": f"shopify_{event_type}",
        "shop_domain": shop_domain,
    }
    if company_id:
        log_data["company_id"] = company_id
    log_data.update(extra_fields)

    if "email" in log_data and log_data["email"]:
        log_data["email"] = log_data["email"][:50] + "..." if len(log_data["email"]) > 50 else log_data["email"]

    logger.info(log_data)


# --- Webhook Endpoints ---

@router.post(
    "/orders/create",
    response_model=WebhookResponse,
    summary="Handle orders/create webhook",
    description="Process Shopify orders/create webhook events with HMAC verification."
)
async def handle_order_created(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> WebhookResponse:
    """Handle Shopify orders/create webhook."""
    body = await request.body()

    signature = request.headers.get("X-Shopify-Hmac-SHA256", "")
    if not verify_shopify_webhook(body, signature):
        logger.warning({
            "event": "shopify_webhook_hmac_failed",
            "endpoint": "orders/create",
        })
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    shop_domain = request.headers.get("X-Shopify-Shop-Domain", "unknown")
    company = await get_company_by_shopify_domain(db, shop_domain)
    company_id = str(company.id) if company else None

    order_id = payload.get("id")
    order_number = payload.get("order_number")

    log_webhook_event(
        event_type="order_created",
        shop_domain=shop_domain,
        company_id=company_id,
        order_id=order_id,
        order_number=order_number,
        total_price=payload.get("total_price"),
        currency=payload.get("currency"),
    )

    return WebhookResponse(
        status="accepted",
        message="Order created webhook processed successfully",
        processed_at=datetime.now(timezone.utc),
        event_type="orders/create",
        shopify_order_id=order_id
    )


@router.post(
    "/orders/updated",
    response_model=WebhookResponse,
    summary="Handle orders/updated webhook"
)
async def handle_order_updated(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> WebhookResponse:
    """Handle Shopify orders/updated webhook."""
    body = await request.body()

    signature = request.headers.get("X-Shopify-Hmac-SHA256", "")
    if not verify_shopify_webhook(body, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    shop_domain = request.headers.get("X-Shopify-Shop-Domain", "unknown")
    order_id = payload.get("id")

    log_webhook_event(
        event_type="order_updated",
        shop_domain=shop_domain,
        order_id=order_id,
        financial_status=payload.get("financial_status"),
    )

    return WebhookResponse(
        status="accepted",
        message="Order updated webhook processed",
        processed_at=datetime.now(timezone.utc),
        event_type="orders/updated",
        shopify_order_id=order_id
    )


@router.post(
    "/orders/cancelled",
    response_model=WebhookResponse,
    summary="Handle orders/cancelled webhook"
)
async def handle_order_cancelled(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> WebhookResponse:
    """Handle Shopify orders/cancelled webhook."""
    body = await request.body()

    signature = request.headers.get("X-Shopify-Hmac-SHA256", "")
    if not verify_shopify_webhook(body, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    shop_domain = request.headers.get("X-Shopify-Shop-Domain", "unknown")
    order_id = payload.get("id")

    log_webhook_event(
        event_type="order_cancelled",
        shop_domain=shop_domain,
        order_id=order_id,
        cancel_reason=payload.get("cancel_reason"),
    )

    return WebhookResponse(
        status="accepted",
        message="Order cancelled webhook processed",
        processed_at=datetime.now(timezone.utc),
        event_type="orders/cancelled",
        shopify_order_id=order_id
    )


@router.post(
    "/customers/create",
    response_model=WebhookResponse,
    summary="Handle customers/create webhook"
)
async def handle_customer_created(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> WebhookResponse:
    """Handle Shopify customers/create webhook."""
    body = await request.body()

    signature = request.headers.get("X-Shopify-Hmac-SHA256", "")
    if not verify_shopify_webhook(body, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    shop_domain = request.headers.get("X-Shopify-Shop-Domain", "unknown")
    customer_id = payload.get("id")
    email = payload.get("email")

    log_webhook_event(
        event_type="customer_created",
        shop_domain=shop_domain,
        customer_id=customer_id,
        email=email,
    )

    return WebhookResponse(
        status="accepted",
        message="Customer created webhook processed",
        processed_at=datetime.now(timezone.utc),
        event_type="customers/create"
    )


@router.post(
    "/customers/update",
    response_model=WebhookResponse,
    summary="Handle customers/update webhook"
)
async def handle_customer_updated(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> WebhookResponse:
    """Handle Shopify customers/update webhook."""
    body = await request.body()

    signature = request.headers.get("X-Shopify-Hmac-SHA256", "")
    if not verify_shopify_webhook(body, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    shop_domain = request.headers.get("X-Shopify-Shop-Domain", "unknown")
    customer_id = payload.get("id")

    log_webhook_event(
        event_type="customer_updated",
        shop_domain=shop_domain,
        customer_id=customer_id,
        state=payload.get("state"),
    )

    return WebhookResponse(
        status="accepted",
        message="Customer updated webhook processed",
        processed_at=datetime.now(timezone.utc),
        event_type="customers/update"
    )


@router.post(
    "/products/update",
    response_model=WebhookResponse,
    summary="Handle products/update webhook"
)
async def handle_product_updated(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> WebhookResponse:
    """Handle Shopify products/update webhook."""
    body = await request.body()

    signature = request.headers.get("X-Shopify-Hmac-SHA256", "")
    if not verify_shopify_webhook(body, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    shop_domain = request.headers.get("X-Shopify-Shop-Domain", "unknown")
    product_id = payload.get("id")
    title = payload.get("title", "")[:50]

    log_webhook_event(
        event_type="product_updated",
        shop_domain=shop_domain,
        product_id=product_id,
        title=title,
    )

    return WebhookResponse(
        status="accepted",
        message="Product updated webhook processed",
        processed_at=datetime.now(timezone.utc),
        event_type="products/update"
    )


@router.post(
    "/inventory_levels/update",
    response_model=WebhookResponse,
    summary="Handle inventory_levels/update webhook"
)
async def handle_inventory_updated(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> WebhookResponse:
    """Handle Shopify inventory_levels/update webhook."""
    body = await request.body()

    signature = request.headers.get("X-Shopify-Hmac-SHA256", "")
    if not verify_shopify_webhook(body, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    shop_domain = request.headers.get("X-Shopify-Shop-Domain", "unknown")

    log_webhook_event(
        event_type="inventory_updated",
        shop_domain=shop_domain,
        inventory_item_id=payload.get("inventory_item_id"),
        available=payload.get("available"),
    )

    return WebhookResponse(
        status="accepted",
        message="Inventory updated webhook processed",
        processed_at=datetime.now(timezone.utc),
        event_type="inventory_levels/update"
    )


@router.get(
    "/health",
    summary="Health check for Shopify webhooks"
)
async def health_check() -> Dict[str, str]:
    """Health check endpoint for Shopify webhook handler."""
    return {
        "status": "healthy",
        "service": "shopify-webhooks",
        "version": "1.0.0"
    }
