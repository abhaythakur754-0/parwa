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

# Week 10.5 Day 17: Technique Configuration Admin API
from app.api import technique_config

# Week 6 Day 2: Jarvis Onboarding Chat API
from app.api import jarvis

# Week 14 Day 1: Jarvis Command Center API
from app.api import jarvis_control

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

# Week 10.5 Day 17: Technique configuration routes
api_router.include_router(
    technique_config.router, prefix="/api/techniques", tags=["technique-config"]
)

# Week 6 Day 2: Jarvis onboarding chat routes
api_router.include_router(jarvis.router, tags=["jarvis"])

# Week 14 Day 1: Jarvis Command Center routes
api_router.include_router(jarvis_control.router, tags=["jarvis-control"])
