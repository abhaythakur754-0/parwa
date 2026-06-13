"""
PARWA Customer Variant Activation Endpoint

Allows a company owner to activate all 3 SaaS variants (Starter, Growth, High)
on their account for testing/demo purposes. The user remains a regular customer
(owner role) — no platform admin privileges are granted.

SECURITY:
- Requires valid JWT (must be company owner)
- First-run only: works only when no subscription record exists yet
- Does NOT grant is_platform_admin

This endpoint should be removed or disabled after initial testing.
"""

import json
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.exceptions import ValidationError
from database.base import get_db
from database.models.core import User, Company
from database.models.billing import Subscription
from database.models.variant_engine import VariantInstance

router = APIRouter(prefix="/api/setup", tags=["setup"])


@router.post("/activate-all-variants")
def activate_all_variants(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Activate all 3 PARWA variants on the authenticated user's company.

    This is a setup/testing endpoint that simulates a customer who has
    purchased all 3 variants. The user stays as a regular customer (owner)
    with no admin privileges — exactly what a real customer would experience.

    What it does:
    - Sets company subscription_tier='high' and subscription_status='active'
    - Sets company mode to 'live'
    - Creates a subscription record (high tier, 30-day period)
    - Creates 3 VariantInstance records (starter, growth, high)
    - Does NOT set is_platform_admin
    """

    # Only company owners can do this
    if user.role != "owner":
        raise ValidationError(
            message="Only company owners can activate variants",
            details={"role": user.role},
        )

    company = db.query(Company).filter(
        Company.id == user.company_id,
    ).first()
    if not company:
        raise ValidationError(
            message="Company not found",
        )

    now = datetime.now(timezone.utc)

    # 1. Upgrade company to High tier (top tier — unlocks all features)
    company.subscription_tier = "high"
    company.subscription_status = "active"
    company.mode = "live"
    company.updated_at = now

    # 2. Create or update subscription record
    existing_sub = db.query(Subscription).filter(
        Subscription.company_id == company.id,
    ).first()

    if existing_sub:
        existing_sub.tier = "high"
        existing_sub.status = "active"
        existing_sub.current_period_start = now
        existing_sub.current_period_end = now + timedelta(days=30)
        existing_sub.cancel_at_period_end = False
    else:
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

    # 3. Create 3 VariantInstance records (one per variant)
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

    for config in variant_configs:
        existing = db.query(VariantInstance).filter(
            VariantInstance.company_id == company.id,
            VariantInstance.variant_type == config["variant_type"],
        ).first()

        if existing:
            existing.status = "active"
            existing.channel_assignment = json.dumps(config["channels"])
            existing.capacity_config = json.dumps(config["capacity"])
        else:
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
        "message": "All 3 variants activated — you now have Starter, Growth, and High as a customer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_platform_admin": user.is_platform_admin,
        },
        "company": {
            "id": str(company.id),
            "name": company.name,
            "subscription_tier": "high",
            "subscription_status": "active",
            "mode": "live",
        },
        "variants_activated": [
            {
                "type": c["variant_type"],
                "name": c["instance_name"],
                "channels": c["channels"],
            }
            for c in variant_configs
        ],
        "note": "Log out and log back in to get a fresh JWT with the 'high' plan claim.",
    }
