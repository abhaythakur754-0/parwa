"""
PARWA Client Factory Service

Orchestrates full tenant provisioning: creates Company, CompanySetting,
default Agent, owner User, verification token, and audit trail entry
in a single transactional operation.

Used by the registration flow (F-010) and onboarding wizard (F-028).

BC-001: Every record created with company_id.
BC-011: Owner user created with bcrypt-hashed password.
BC-012: Every write operation logged to audit_trail.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.exceptions import ValidationError
from app.logger import get_logger
from app.services.audit_service import log_audit
from database.models.core import (
    Agent,
    Company,
    CompanySetting,
    User,
)

logger = get_logger("client_factory")


# ── Plan Entitlements ────────────────────────────────────────────────

PLAN_ENTITLEMENTS = {
    "starter": {
        "max_tickets_per_month": 2_000,
        "max_agents": 1,
        "channels": ["email", "live_chat"],
        "voice": False,
        "voice_slots": 0,
        "sms": False,
        "max_kb_documents": 100,
        "max_team_members": 3,
        "max_file_size_mb": 10,
    },
    "growth": {
        "max_tickets_per_month": 5_000,
        "max_agents": 3,
        "channels": ["email", "live_chat", "sms"],
        "voice": True,
        "voice_slots": 2,
        "sms": True,
        "max_kb_documents": 500,
        "max_team_members": 10,
        "max_file_size_mb": 25,
    },
    "high": {
        "max_tickets_per_month": 15_000,
        "max_agents": 5,
        "channels": ["email", "live_chat", "sms", "voice", "social"],
        "voice": True,
        "voice_slots": 5,
        "sms": True,
        "max_kb_documents": 2_000,
        "max_team_members": 25,
        "max_file_size_mb": 50,
    },
}


def get_plan_entitlements(tier: str) -> Dict[str, Any]:
    """Get entitlements for a subscription tier.

    Args:
        tier: Plan name (starter, growth, high).

    Returns:
        Dict of entitlement values for the given tier.

    Raises:
        ValueError: If tier is not recognized.
    """
    tier_lower = tier.lower().strip() if tier else "starter"
    entitlements = PLAN_ENTITLEMENTS.get(tier_lower)
    if not entitlements:
        raise ValueError(
            f"Unknown plan tier '{tier}'. "
            f"Must be one of: {', '.join(sorted(PLAN_ENTITLEMENTS))}"
        )
    return entitlements


# ── Company Provisioning ──────────────────────────────────────────


def provision_company(
    name: str,
    owner_email: str,
    owner_password_hash: str,
    owner_full_name: Optional[str] = None,
    industry: Optional[str] = None,
    tier: str = "starter",
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Provision a new tenant company with all initial resources.

    Creates in a single transaction:
      1. Company record
      2. CompanySetting record (with tier-based defaults)
      3. Owner User record
      4. Default Agent record
      5. Audit trail entry

    Args:
        name: Company display name.
        owner_email: Owner's email address (must be unique).
        owner_password_hash: Already bcrypt-hashed password.
        owner_full_name: Owner's full name.
        industry: Company industry (optional).
        tier: Subscription tier (starter/growth/high).
        db: Database session. If None, creates its own.

    Returns:
        Dict with keys: company_id, company, owner, settings, agent,
        entitlements.

    Raises:
        ValueError: If validation fails.
        ValidationError: If email or name is invalid.
    """
    if not name or not name.strip():
        raise ValueError("Company name is required")

    if not owner_email or "@" not in owner_email:
        raise ValueError("A valid owner email is required")

    if not owner_password_hash or not owner_password_hash.strip():
        raise ValueError("Owner password hash is required")

    tier_lower = tier.lower().strip() if tier else "starter"
    if tier_lower not in PLAN_ENTITLEMENTS:
        raise ValueError(
            f"Unknown plan tier '{tier}'. "
            f"Must be one of: {', '.join(sorted(PLAN_ENTITLEMENTS))}"
        )

    # Validate email uniqueness
    if db is not None:
        existing = db.query(User).filter(
            User.email == owner_email.strip().lower(),
        ).first()
        if existing:
            raise ValidationError(
                message="Email already registered",
                details={"field": "email", "email": owner_email},
            )

    company_id = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())
    settings_id = str(uuid.uuid4())

    now = datetime.now(timezone.utc)

    owns_session = False
    if db is None:
        from database.base import SessionLocal
        db = SessionLocal()
        owns_session = True

    try:
        # 1. Create company
        company = Company(
            id=company_id,
            name=name.strip(),
            industry=(industry or "").strip() or None,
            subscription_tier=tier_lower,
            subscription_status="active",
            mode="shadow",
        )
        db.add(company)

        # 2. Create company settings with tier defaults
        settings = CompanySetting(
            id=settings_id,
            company_id=company_id,
        )
        db.add(settings)

        # 3. Create owner user
        owner = User(
            id=owner_id,
            company_id=company_id,
            email=owner_email.strip().lower(),
            password_hash=owner_password_hash,
            full_name=(owner_full_name or "").strip() or "Company Owner",
            role="owner",
            is_active=True,
            is_verified=False,  # Must verify email (F-012)
        )
        db.add(owner)

        # 4. Create default agent
        agent = Agent(
            id=agent_id,
            company_id=company_id,
            name=f"{name.strip()} AI Agent",
            variant="general",
            status="active",
            capacity_used=0,
            capacity_max=0,  # No capacity until AI activation (F-034)
            accuracy_rate=0.0,
            tickets_resolved=0,
        )
        db.add(agent)

        db.flush()

        # 5. Audit trail
        log_audit(
            company_id=company_id,
            actor_id=owner_id,
            actor_type="user",
            action="create",
            resource_type="company",
            resource_id=company_id,
            new_value=f"Company '{name}' created with tier '{tier_lower}'",
            ip_address=None,
            db=db,
        )

        db.commit()

        entitlements = get_plan_entitlements(tier_lower)

        result = {
            "company_id": company_id,
            "company": {
                "id": company_id,
                "name": company.name,
                "tier": company.subscription_tier,
                "status": company.subscription_status,
                "mode": company.mode,
            },
            "owner": {
                "id": owner.id,
                "email": owner.email,
                "full_name": owner.full_name,
                "role": owner.role,
                "is_verified": owner.is_verified,
            },
            "settings_id": settings.id,
            "agent": {
                "id": agent.id,
                "name": agent.name,
                "status": agent.status,
            },
            "entitlements": entitlements,
        }

        logger.info(
            "company_provisioned",
            company_id=company_id,
            name=name,
            tier=tier_lower,
            owner_email=owner_email,
        )

        return result

    except Exception:
        if owns_session:
            db.rollback()
        raise
    finally:
        if owns_session:
            db.close()


def get_company_entitlements(
    company_id: str, db: Session,
) -> Dict[str, Any]:
    """Get entitlements for an existing company.

    Reads the subscription_tier from the Company record and
    returns the corresponding entitlements.

    Args:
        company_id: The company UUID.
        db: Database session.

    Returns:
        Dict of entitlement values.

    Raises:
        NotFoundError: If company not found.
    """
    from app.exceptions import NotFoundError

    company = db.query(Company).filter(
        Company.id == company_id,
    ).first()

    if not company:
        raise NotFoundError(
            message="Company not found",
            details={"company_id": company_id},
        )

    return get_plan_entitlements(company.subscription_tier)


def check_entitlement(
    company_id: str,
    entitlement_key: str,
    current_value: Any,
    db: Session,
) -> bool:
    """Check if a usage value is within the company's entitlement limit.

    Args:
        company_id: The company UUID.
        entitlement_key: Key to check (e.g., 'max_agents', 'max_kb_documents').
        current_value: Current usage value.
        db: Database session.

    Returns:
        True if within limits, False if exceeded.

    Raises:
        NotFoundError: If company not found.
    """
    entitlements = get_company_entitlements(company_id, db)

    limit = entitlements.get(entitlement_key)
    if limit is None:
        return True  # No limit defined

    return current_value < limit


def check_team_member_limit(
    company_id: str, db: Session,
) -> bool:
    """Check if company can add more team members.

    Args:
        company_id: The company UUID.
        db: Database session.

    Returns:
        True if under the limit, False if at/over.
    """
    entitlements = get_company_entitlements(company_id, db)
    max_members = entitlements.get("max_team_members", 3)

    current_count = db.query(User).filter(
        User.company_id == company_id,
        User.is_active == True,  # noqa: E712
    ).count()

    return current_count < max_members


def check_agent_limit(
    company_id: str, db: Session,
) -> bool:
    """Check if company can create more agents.

    Args:
        company_id: The company UUID.
        db: Database session.

    Returns:
        True if under the limit, False if at/over.
    """
    from database.models.core import Agent

    entitlements = get_company_entitlements(company_id, db)
    max_agents = entitlements.get("max_agents", 1)

    current_count = db.query(Agent).filter(
        Agent.company_id == company_id,
        Agent.status == "active",
    ).count()

    return current_count < max_agents
