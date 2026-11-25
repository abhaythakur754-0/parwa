"""
Legacy Razorpay checkout endpoints.

The former backend endpoints accepted caller-controlled amounts and verified only
an HMAC signature without checking provider capture status or persisting an
order-to-user record. They are intentionally disabled. Use the authenticated
Next.js Razorpay checkout routes, which apply server-owned plan pricing and
verify the captured payment against the stored user-owned order.
"""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/razorpay", tags=["razorpay-checkout"])


@router.post("/create-order")
async def create_order():
    raise HTTPException(
        status_code=410,
        detail="Legacy Razorpay order creation is disabled. Use the authenticated application checkout endpoint.",
    )


@router.post("/verify-payment")
async def verify_payment():
    raise HTTPException(
        status_code=410,
        detail="Legacy Razorpay verification is disabled. Use the authenticated application checkout endpoint.",
    )
