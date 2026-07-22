"""
Razorpay Standard Checkout API

Endpoints:
  POST /api/razorpay/create-order   — Create order via Razorpay API
  POST /api/razorpay/verify-payment — Verify payment signature
"""

import hashlib
import hmac
import base64
import logging
from typing import Any, Dict

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import get_settings
from database.base import get_db
from database.models.core import User

logger = logging.getLogger("parwa.api.razorpay_checkout")

router = APIRouter(prefix="/api/razorpay", tags=["razorpay-checkout"])

RAZORPAY_API_BASE = "https://api.razorpay.com/v1"


# ── Schemas ────────────────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    amount: int = Field(..., ge=100, description="Amount in paise (min 100)")
    currency: str = Field("INR", max_length=3)
    receipt: str = Field("", max_length=40)


class CreateOrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class VerifyPaymentResponse(BaseModel):
    status: str
    message: str


# ── Helpers ────────────────────────────────────────────────────────

def _get_auth_header() -> str:
    s = get_settings()
    credentials = f"{s.RAZORPAY_KEY_ID}:{s.RAZORPAY_KEY_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


# ── Endpoints ──────────────────────────────────────────────────────

@router.post("/create-order", response_model=CreateOrderResponse)
async def create_order(
    body: CreateOrderRequest,
    user: User = Depends(get_current_user),
) -> CreateOrderResponse:
    """Create a Razorpay order.

    Calls Razorpay API: POST https://api.razorpay.com/v1/orders
    Returns order_id, amount, currency.
    """
    if body.amount < 100:
        raise HTTPException(status_code=400, detail="Amount must be at least 100 paise")

    s = get_settings()
    if not s.RAZORPAY_KEY_ID or not s.RAZORPAY_KEY_SECRET:
        raise HTTPException(status_code=500, detail="Razorpay keys not configured")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{RAZORPAY_API_BASE}/orders",
                headers={
                    "Authorization": _get_auth_header(),
                    "Content-Type": "application/json",
                },
                json={
                    "amount": body.amount,
                    "currency": body.currency,
                    "receipt": body.receipt or f"parwa_{user.id[:8]}",
                },
            )

        if response.status_code == 401:
            raise HTTPException(status_code=401, detail="Razorpay authentication failed")
        if response.status_code >= 400:
            error_data = response.json()
            raise HTTPException(
                status_code=500,
                detail=f"Razorpay error: {error_data.get('error', {}).get('description', 'Unknown error')}"
            )

        data = response.json()
        return CreateOrderResponse(
            order_id=data["id"],
            amount=data["amount"],
            currency=data["currency"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_order failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to create order: {str(e)}")


@router.post("/verify-payment", response_model=VerifyPaymentResponse)
async def verify_payment(
    body: VerifyPaymentRequest,
    user: User = Depends(get_current_user),
) -> VerifyPaymentResponse:
    """Verify Razorpay payment signature.

    Algorithm: HMAC-SHA256(order_id + "|" + payment_id, KEY_SECRET)
    Compare generated signature with razorpay_signature.
    Returns success only if signatures match.
    """
    s = get_settings()
    if not s.RAZORPAY_KEY_SECRET:
        raise HTTPException(status_code=500, detail="Razorpay keys not configured")

    if not body.razorpay_order_id or not body.razorpay_payment_id or not body.razorpay_signature:
        raise HTTPException(status_code=400, detail="Missing required fields")

    # Generate expected signature
    message = f"{body.razorpay_order_id}|{body.razorpay_payment_id}"
    expected_signature = hmac.new(
        s.RAZORPAY_KEY_SECRET.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()

    # Compare signatures
    if not hmac.compare_digest(expected_signature, body.razorpay_signature):
        raise HTTPException(status_code=400, detail="Signature mismatch — payment NOT verified")

    logger.info(
        "Payment verified: order=%s payment=%s user=%s",
        body.razorpay_order_id, body.razorpay_payment_id, user.id,
    )

    return VerifyPaymentResponse(
        status="success",
        message="Payment verified successfully",
    )
