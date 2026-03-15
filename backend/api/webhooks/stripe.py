"""
PARWA Stripe Webhook Handler.

Processes Stripe webhooks for payments, invoices, refunds, and disputes.
All webhooks verify HMAC signature before processing.

CRITICAL: Refund webhooks create pending_approval records and NEVER 
call Stripe directly without explicit human approval.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import json
import uuid

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
router = APIRouter(prefix="/webhooks/stripe", tags=["Webhooks - Stripe"])
logger = get_logger(__name__)
settings = get_settings()


# --- Pydantic Schemas ---

class WebhookResponse(BaseModel):
    """Response schema for webhook processing."""
    status: str
    message: str
    processed_at: datetime
    event_type: Optional[str] = None
    event_id: Optional[str] = None


# --- Helper Functions ---

def verify_stripe_webhook(request_body: bytes, signature: str) -> bool:
    """
    Verify Stripe webhook HMAC signature.
    
    Stripe sends HMAC-SHA256 signature in Stripe-Signature header.
    Format: t=<timestamp>,v1=<signature>
    
    Args:
        request_body: Raw request body bytes
        signature: Signature from Stripe-Signature header
        
    Returns:
        bool: True if signature is valid
    """
    if not signature:
        return False
    
    webhook_secret = settings.stripe_webhook_secret
    if not webhook_secret:
        logger.error({"event": "stripe_webhook_secret_not_configured"})
        return False
    
    # Parse Stripe signature format: t=<timestamp>,v1=<signature>
    parts = {}
    for part in signature.split(","):
        if "=" in part:
            key, value = part.split("=", 1)
            parts[key] = value
    
    if "v1" not in parts:
        return False
    
    # Verify the signature
    return verify_hmac(request_body, parts["v1"], webhook_secret.get_secret_value())


async def get_company_by_stripe_account(
    db: AsyncSession,
    stripe_account_id: Optional[str]
) -> Optional[Company]:
    """
    Get company by Stripe account ID.
    
    Args:
        db: Database session
        stripe_account_id: Stripe account ID
        
    Returns:
        Company if found, None otherwise
    """
    # TODO: Add stripe_account_id field to Company model
    result = await db.execute(
        select(Company).where(Company.is_active == True)
    )
    companies = result.scalars().all()
    
    return companies[0] if companies else None


async def create_pending_approval(
    db: AsyncSession,
    company_id: uuid.UUID,
    event_type: str,
    event_data: Dict[str, Any]
) -> uuid.UUID:
    """
    Create a pending approval record for refund actions.
    
    This is CRITICAL - we NEVER call Stripe directly without human approval.
    
    Args:
        db: Database session
        company_id: Company UUID
        event_type: Type of event (e.g., "refund.requested")
        event_data: Full event data
        
    Returns:
        UUID of pending approval record
    """
    approval_id = uuid.uuid4()
    
    logger.info({
        "event": "pending_approval_created",
        "approval_id": str(approval_id),
        "company_id": str(company_id),
        "event_type": event_type,
        "note": "Refund requires explicit human approval before processing"
    })
    
    # TODO: Store in pending_approvals table when model is created
    
    return approval_id


# --- Webhook Endpoints ---

@router.post(
    "",
    response_model=WebhookResponse,
    summary="Handle all Stripe webhooks",
    description="Process all Stripe webhook events with HMAC verification."
)
async def handle_stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> WebhookResponse:
    """
    Handle Stripe webhook events.
    
    Verifies HMAC signature and routes to appropriate handler.
    CRITICAL: Refund events create pending_approval records only.
    
    Args:
        request: FastAPI request object
        db: Database session
        
    Returns:
        WebhookResponse with processing status
        
    Raises:
        HTTPException: 401 if HMAC verification fails
    """
    # Get raw body for HMAC verification
    body = await request.body()
    
    # Verify HMAC signature
    signature = request.headers.get("Stripe-Signature", "")
    if not verify_stripe_webhook(body, signature):
        logger.warning({
            "event": "stripe_webhook_hmac_failed",
        })
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )
    
    # Parse payload
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
    
    event_type = payload.get("type", "unknown")
    event_id = payload.get("id", "")
    event_data = payload.get("data", {}).get("object", {})
    
    # Get company (from Stripe account or connected account)
    stripe_account = payload.get("account") or event_data.get("account")
    
    company = await get_company_by_stripe_account(db, stripe_account)
    if not company:
        logger.warning({
            "event": "stripe_webhook_company_not_found",
            "stripe_account": stripe_account,
        })
        # Still process webhook, but log warning
    
    # Log the event
    logger.info({
        "event": "stripe_webhook_received",
        "company_id": str(company.id) if company else None,
        "stripe_event_type": event_type,
        "stripe_event_id": event_id,
    })
    
    # Handle specific event types
    if event_type == "payment_intent.succeeded":
        return await _handle_payment_succeeded(db, company, event_data, event_id)
    elif event_type == "invoice.paid":
        return await _handle_invoice_paid(db, company, event_data, event_id)
    elif event_type == "charge.refunded":
        return await _handle_refund(db, company, event_data, event_id)
    elif event_type == "customer.subscription.updated":
        return await _handle_subscription_updated(db, company, event_data, event_id)
    else:
        # Default handling for other events
        return WebhookResponse(
            status="accepted",
            message=f"Event {event_type} received and logged",
            processed_at=datetime.now(timezone.utc),
            event_type=event_type,
            event_id=event_id
        )


async def _handle_payment_succeeded(
    db: AsyncSession,
    company: Optional[Company],
    event_data: Dict[str, Any],
    event_id: str
) -> WebhookResponse:
    """Handle payment_intent.succeeded event."""
    logger.info({
        "event": "stripe_payment_succeeded",
        "company_id": str(company.id) if company else None,
        "payment_intent_id": event_data.get("id"),
        "amount": event_data.get("amount"),
        "currency": event_data.get("currency"),
    })
    
    return WebhookResponse(
        status="accepted",
        message="Payment success processed",
        processed_at=datetime.now(timezone.utc),
        event_type="payment_intent.succeeded",
        event_id=event_id
    )


async def _handle_invoice_paid(
    db: AsyncSession,
    company: Optional[Company],
    event_data: Dict[str, Any],
    event_id: str
) -> WebhookResponse:
    """Handle invoice.paid event."""
    logger.info({
        "event": "stripe_invoice_paid",
        "company_id": str(company.id) if company else None,
        "invoice_id": event_data.get("id"),
        "amount_paid": event_data.get("amount_paid"),
    })
    
    return WebhookResponse(
        status="accepted",
        message="Invoice paid processed",
        processed_at=datetime.now(timezone.utc),
        event_type="invoice.paid",
        event_id=event_id
    )


async def _handle_refund(
    db: AsyncSession,
    company: Optional[Company],
    event_data: Dict[str, Any],
    event_id: str
) -> WebhookResponse:
    """
    Handle charge.refunded event.
    
    CRITICAL: Creates pending_approval record for manual review.
    Does NOT process refund automatically.
    """
    if company:
        approval_id = await create_pending_approval(
            db=db,
            company_id=company.id,
            event_type="charge.refunded",
            event_data=event_data
        )
        
        logger.info({
            "event": "stripe_refund_pending_approval",
            "company_id": str(company.id),
            "approval_id": str(approval_id),
            "charge_id": event_data.get("id"),
            "amount_refunded": event_data.get("amount_refunded"),
            "note": "Refund created pending_approval - requires human approval"
        })
    
    return WebhookResponse(
        status="accepted",
        message="Refund event logged - pending approval required",
        processed_at=datetime.now(timezone.utc),
        event_type="charge.refunded",
        event_id=event_id
    )


async def _handle_subscription_updated(
    db: AsyncSession,
    company: Optional[Company],
    event_data: Dict[str, Any],
    event_id: str
) -> WebhookResponse:
    """Handle customer.subscription.updated event."""
    logger.info({
        "event": "stripe_subscription_updated",
        "company_id": str(company.id) if company else None,
        "subscription_id": event_data.get("id"),
        "status": event_data.get("status"),
    })
    
    return WebhookResponse(
        status="accepted",
        message="Subscription update processed",
        processed_at=datetime.now(timezone.utc),
        event_type="customer.subscription.updated",
        event_id=event_id
    )
