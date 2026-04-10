"""
PARWA API Routes

All FastAPI routers are registered here.
"""

from fastapi import APIRouter

from app.api import auth, health, admin, api_keys, mfa, client, webhooks

# Day 26: Ticket API
from app.api import tickets

# Day 35: Public API (Landing Page)
from app.api import public

api_router = APIRouter()

# Register all routers
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(api_keys.router, prefix="/api-keys", tags=["api-keys"])
api_router.include_router(mfa.router, prefix="/mfa", tags=["mfa"])
api_router.include_router(client.router, prefix="/client", tags=["client"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])

# Day 26: Ticket routes
api_router.include_router(tickets.router, prefix="/v1", tags=["tickets"])

# Day 35: Public routes (Landing Page - no auth required)
api_router.include_router(public.router, tags=["public"])
