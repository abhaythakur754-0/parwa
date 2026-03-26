"""
PARWA Webhook Handlers.

This package contains webhook handlers for third-party integrations.
All webhooks verify HMAC signatures before processing.
"""
from fastapi import APIRouter

# Lazy import to avoid sqlalchemy dependency during testing
# Individual routers can be imported directly when needed
router = APIRouter()

# Lazy-load routers when the module is used
def _include_routers():
    """Include all webhook routers lazily."""
    try:
        from backend.api.webhooks.shopify import router as shopify_router
        from backend.api.webhooks.stripe import router as stripe_router
        router.include_router(shopify_router)
        router.include_router(stripe_router)
    except ImportError:
        pass  # Allow tests to run without sqlalchemy

__all__ = ["router"]
