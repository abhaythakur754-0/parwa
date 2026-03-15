"""
PARWA Webhook Handlers.

This package contains webhook handlers for third-party integrations.
All webhooks verify HMAC signatures before processing.
"""
from fastapi import APIRouter

from backend.api.webhooks.shopify import router as shopify_router
from backend.api.webhooks.stripe import router as stripe_router

# Combined router for all webhooks
router = APIRouter()
router.include_router(shopify_router)
router.include_router(stripe_router)

__all__ = ["router", "shopify_router", "stripe_router"]
