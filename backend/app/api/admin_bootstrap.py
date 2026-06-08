"""
PARWA Admin Bootstrap Endpoint

One-time setup endpoint to promote the first user to platform admin
and activate all 3 SaaS variants (Starter, Growth, High) on their account.

SECURITY: This endpoint is protected by a bootstrap secret that must be
set via the ADMIN_BOOTSTRAP_SECRET environment variable. After the first
successful bootstrap, the secret should be rotated or removed.

This endpoint should be removed or disabled in production after use.
"""

import os
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.exceptions import AuthenticationError, AuthorizationError, ValidationError
from database.base import get_db
from database.models.core import User, Company
from database.models.billing import Subscription
from database.models.variant_engine import VariantInstance

router = APIRouter(prefix="/api/admin", tags=["admin-bootstrap"])

# Bootstrap secret from environment - must be set to use this endpoint
_BOOTSTRAP_SECRET = os.environ.get("ADMIN_BOOTSTRAP_SECRET", "")


@router.post("/bootstrap")
def bootstrap_platform_admin(
    db: Session = Depends(get_db),
    authorization: str = Header(None),
    x_bootstrap_secret: str = Header(None, alias="X-Bootstrap-Secret"),
):
    """Promote the authenticated user to platform admin and activate all variants.

    This is a one-time setup endpoint for bootstrapping the first admin account.
    It requires:
    1. A valid JWT (user must already be registered)
    2. The X-Bootstrap-Secret header matching ADMIN_BOOTSTRAP_SECRET env var

    What it does:
    - Sets is_platform_admin=True on the user
    - Sets company subscription_tier='high' and subscription_status='active'
    - Creates a subscription record (high tier, 30-day period)
    - Creates 3 VariantInstance records (starter, growth, high)
    - Sets company mode to 'live'
    """

    # Security: Verify bootstrap secret
    if not _BOOTSTRAP_SECRET:
        raise AuthorizationError(
            message="Bootstrap endpoint is not configured. "
                    "Set ADMIN_BOOTSTRAP_SECRET environment variable.",
        )
    if not x_bootstrap_secret or x_bootstrap_secret != _BOOTSTRAP_SECRET:
        raise AuthorizationError(
            message="Invalid bootstrap secret",
        )

    # Get authenticated user
    if not authorization:
        raise AuthenticationError(message="Authorization header required")

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0] != "Bearer":
        raise AuthenticationError(
            message="Invalid authorization format. Use: Bearer <token>"
        )

    from app.core.auth import verify_access_token
    token = parts[1]
    payload = verify_access_token(token)

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError(message="Invalid token payload")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AuthenticationError(message="User not found")

    company = db.query(Company).filter(Company.id == user.company_id).first()
    if not company:
        raise AuthenticationError(message="Company not found")

    now = datetime.now(timezone.utc)

    # 1. Promote user to platform admin
    user.is_platform_admin = True

    # 2. Upgrade company to High tier (top tier - includes all features)
    company.subscription_tier = "high"
    company.subscription_status = "active"
    company.mode = "live"
    company.updated_at = now

    # 3. Create subscription record
    existing_sub = db.query(Subscription).filter(
        Subscription.company_id == company.id,
    ).first()

    if not existing_sub:
        subscription = Subscription(
            id=str(uuid.uuid4()),
            company_id=company.id,
            tier="high",
            status="active",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            cancel_at_period_end=False,
        )
        db.add(subscription)

    # 4. Create 3 VariantInstance records (one per variant)
    variant_configs = [
        {
            "variant_type": "starter",
            "instance_name": "Starter - Chat & Email Support",
            "channels": ["email", "chat"],
            "capacity": {
                "max_concurrent_tickets": 50,
                "token_budget_share_pct": 15,
                "priority_weight": 1,
            },
        },
        {
            "variant_type": "growth",
            "instance_name": "Growth - Multi-Channel Agent",
            "channels": ["email", "chat", "sms", "voice"],
            "capacity": {
                "max_concurrent_tickets": 200,
                "token_budget_share_pct": 35,
                "priority_weight": 2,
            },
        },
        {
            "variant_type": "high",
            "instance_name": "High - Senior AI Agent (Full Suite)",
            "channels": ["email", "chat", "sms", "voice", "social"],
            "capacity": {
                "max_concurrent_tickets": 500,
                "token_budget_share_pct": 50,
                "priority_weight": 3,
            },
        },
    ]

    import json

    for config in variant_configs:
        existing = db.query(VariantInstance).filter(
            VariantInstance.company_id == company.id,
            VariantInstance.variant_type == config["variant_type"],
        ).first()

        if not existing:
            instance = VariantInstance(
                id=str(uuid.uuid4()),
                company_id=company.id,
                instance_name=config["instance_name"],
                variant_type=config["variant_type"],
                status="active",
                channel_assignment=json.dumps(config["channels"]),
                capacity_config=json.dumps(config["capacity"]),
            )
            db.add(instance)

    db.commit()

    return {
        "message": "Bootstrap complete — account upgraded to platform admin with all 3 variants",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "is_platform_admin": True,
            "role": user.role,
        },
        "company": {
            "id": str(company.id),
            "name": company.name,
            "subscription_tier": "high",
            "subscription_status": "active",
            "mode": "live",
        },
        "variants_created": [c["variant_type"] for c in variant_configs],
        "note": "Please log out and log back in to get a fresh JWT with the updated plan claim.",
    }
