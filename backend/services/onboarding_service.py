"""
Onboarding Service Layer

Business logic for new client onboarding.
Handles company setup, user creation, and welcome workflows.
All methods are company-scoped for RLS compliance.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone
from enum import Enum
import secrets
import re

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from backend.models.company import Company, PlanTierEnum
from backend.models.user import User, RoleEnum
from backend.models.subscription import Subscription
from backend.models.audit_trail import AuditTrail
from shared.core_functions.logger import get_logger
from shared.core_functions.security import hash_password

logger = get_logger(__name__)


class OnboardingStep(str, Enum):
    """Onboarding steps enumeration."""
    COMPANY_INFO = "company_info"
    ADMIN_USER = "admin_user"
    SUBSCRIPTION = "subscription"
    INTEGRATION = "integration"
    TRAINING = "training"
    COMPLETE = "complete"


ONBOARDING_STEPS = [
    OnboardingStep.COMPANY_INFO,
    OnboardingStep.ADMIN_USER,
    OnboardingStep.SUBSCRIPTION,
    OnboardingStep.INTEGRATION,
    OnboardingStep.TRAINING,
    OnboardingStep.COMPLETE,
]

# Mapping between OnboardingStep tier names and PlanTierEnum
TIER_MAPPING = {
    "mini": PlanTierEnum.mini,
    "parwa": PlanTierEnum.parwa,
    "parwa_high": PlanTierEnum.parwa_high,
}


class OnboardingService:
    """
    Service class for onboarding business logic.
    
    Provides onboarding workflow management, company setup,
    and initial configuration.
    All methods enforce company-scoped data access (RLS).
    """
    
    def __init__(self, db: AsyncSession, company_id: Optional[UUID] = None):
        """
        Initialize onboarding service.
        
        Args:
            db: Async database session
            company_id: Optional company UUID (None for new onboarding)
        """
        if db is None:
            raise ValueError("Database session is required")
        self.db = db
        self.company_id = company_id
    
    async def start_onboarding(
        self,
        company_name: str,
        admin_email: str,
        admin_name: str,
        initial_tier: str = "mini"
    ) -> Dict[str, Any]:
        """
        Initialize onboarding for a new company.
        
        Creates company record and starts onboarding workflow.
        
        Args:
            company_name: Name of the company
            admin_email: Email of the admin user
            admin_name: Name of the admin user
            initial_tier: Initial subscription tier
            
        Returns:
            Dict with:
            - company_id: UUID
            - onboarding_token: str
            - current_step: OnboardingStep
            - steps_completed: List[str]
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Validate required fields
        if not company_name or not company_name.strip():
            raise ValueError("Company name is required")
        if not admin_email or not self._validate_email(admin_email):
            raise ValueError("Valid admin email is required")
        if not admin_name or not admin_name.strip():
            raise ValueError("Admin name is required")
        
        # Validate tier
        if initial_tier not in TIER_MAPPING:
            raise ValueError(f"Invalid tier: {initial_tier}. Must be one of {list(TIER_MAPPING.keys())}")
        
        # Create company
        company = Company(
            name=company_name.strip(),
            industry="pending",  # Will be set in company_info step
            plan_tier=TIER_MAPPING[initial_tier],
            is_active=True,
        )
        
        self.db.add(company)
        await self.db.flush()
        await self.db.refresh(company)
        
        # Update company_id for subsequent operations
        self.company_id = company.id
        
        # Generate onboarding token
        onboarding_token = secrets.token_urlsafe(32)
        
        # Log audit
        await self._log_audit(
            action="onboarding_started",
            entity_type="company",
            entity_id=company.id,
            changes={"company_name": company_name, "initial_tier": initial_tier}
        )
        
        logger.info({
            "event": "onboarding_started",
            "company_id": str(company.id),
            "company_name": company_name,
            "initial_tier": initial_tier,
        })
        
        return {
            "company_id": company.id,
            "onboarding_token": onboarding_token,
            "current_step": OnboardingStep.COMPANY_INFO.value,
            "steps_completed": [],
        }
    
    async def complete_onboarding_step(
        self,
        step: OnboardingStep,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Mark an onboarding step as complete.
        
        Args:
            step: The step to complete
            data: Data for the step
            
        Returns:
            Dict with:
            - success: bool
            - current_step: OnboardingStep
            - steps_completed: List[str]
            - next_step: Optional[OnboardingStep]
        """
        if self.company_id is None:
            raise ValueError("Company ID is required to complete onboarding step")
        
        # Get company
        result = await self.db.execute(
            select(Company).where(Company.id == self.company_id)
        )
        company = result.scalar_one_or_none()
        
        if not company:
            raise ValueError("Company not found")
        
        # Get current steps completed (stored as JSON or comma-separated string)
        steps_completed = getattr(company, 'steps_completed', []) or []
        if isinstance(steps_completed, str):
            steps_completed = steps_completed.split(',') if steps_completed else []
        
        # Add step to completed if not already there
        if step.value not in steps_completed:
            steps_completed.append(step.value)
        
        # Calculate next step
        current_step_index = ONBOARDING_STEPS.index(step)
        next_step = None
        if current_step_index + 1 < len(ONBOARDING_STEPS):
            next_step = ONBOARDING_STEPS[current_step_index + 1]
        
        # Update company
        company.updated_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        
        # Log audit
        await self._log_audit(
            action="onboarding_step_completed",
            entity_type="company",
            entity_id=company.id,
            changes={"step": step.value, "data": data}
        )
        
        logger.info({
            "event": "onboarding_step_completed",
            "company_id": str(self.company_id),
            "step": step.value,
        })
        
        return {
            "success": True,
            "current_step": next_step.value if next_step else OnboardingStep.COMPLETE.value,
            "steps_completed": steps_completed,
            "next_step": next_step.value if next_step else None,
        }
    
    async def get_onboarding_status(self) -> Dict[str, Any]:
        """
        Get current onboarding progress.
        
        Returns:
            Dict with:
            - company_id: UUID
            - status: str (pending, in_progress, complete)
            - current_step: OnboardingStep
            - steps_completed: List[str]
            - steps_remaining: List[str]
            - progress_percentage: float
        """
        if self.company_id is None:
            raise ValueError("Company ID is required")
        
        # Get company
        result = await self.db.execute(
            select(Company).where(Company.id == self.company_id)
        )
        company = result.scalar_one_or_none()
        
        if not company:
            raise ValueError("Company not found")
        
        # Get steps completed
        steps_completed = getattr(company, 'steps_completed', []) or []
        if isinstance(steps_completed, str):
            steps_completed = steps_completed.split(',') if steps_completed else []
        
        # Determine current step
        if not steps_completed:
            current_step = OnboardingStep.COMPANY_INFO
        else:
            last_completed = steps_completed[-1]
            try:
                last_step = OnboardingStep(last_completed)
                idx = ONBOARDING_STEPS.index(last_step)
                current_step = ONBOARDING_STEPS[idx + 1] if idx + 1 < len(ONBOARDING_STEPS) else OnboardingStep.COMPLETE
            except (ValueError, IndexError):
                current_step = OnboardingStep.COMPANY_INFO
        
        # Calculate remaining steps
        steps_remaining = [s.value for s in ONBOARDING_STEPS if s.value not in steps_completed]
        
        # Calculate progress
        progress = (len(steps_completed) / len(ONBOARDING_STEPS)) * 100
        
        # Determine status
        if len(steps_completed) == 0:
            status = "pending"
        elif OnboardingStep.COMPLETE.value in steps_completed:
            status = "complete"
        else:
            status = "in_progress"
        
        return {
            "company_id": self.company_id,
            "status": status,
            "current_step": current_step.value,
            "steps_completed": steps_completed,
            "steps_remaining": steps_remaining,
            "progress_percentage": round(progress, 1),
        }
    
    async def setup_company_defaults(self) -> Dict[str, Any]:
        """
        Set up default settings for new company.
        
        Returns:
            Dict with default settings created
        """
        if self.company_id is None:
            raise ValueError("Company ID is required")
        
        # Default settings
        defaults = {
            "timezone": "UTC",
            "language": "en",
            "currency": "USD",
            "notification_preferences": {
                "email": True,
                "sms": False,
                "push": True,
            },
            "ai_settings": {
                "confidence_threshold": 0.85,
                "auto_approve_enabled": False,
            },
        }
        
        logger.info({
            "event": "company_defaults_set",
            "company_id": str(self.company_id),
            "defaults": defaults,
        })
        
        return {
            "company_id": self.company_id,
            "defaults": defaults,
        }
    
    async def create_admin_user(
        self,
        email: str,
        name: str,
        password: str
    ) -> Dict[str, Any]:
        """
        Create first admin user for company.
        
        Args:
            email: Admin email
            name: Admin name
            password: Initial password (will be hashed)
            
        Returns:
            Dict with:
            - user_id: UUID
            - email: str
            - role: UserRole
            - temp_password: bool
        """
        if self.company_id is None:
            raise ValueError("Company ID is required")
        
        # Validate inputs
        if not email or not self._validate_email(email):
            raise ValueError("Valid email is required")
        if not name or not name.strip():
            raise ValueError("Name is required")
        if not password or len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        
        # Check if user already exists
        result = await self.db.execute(
            select(User).where(User.email == email.lower())
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise ValueError("User with this email already exists")
        
        # Hash password
        password_hash = hash_password(password)
        
        # Create user
        user = User(
            company_id=self.company_id,
            email=email.lower(),
            password_hash=password_hash,
            role=RoleEnum.admin,
            is_active=True,
        )
        
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        
        # Log audit
        await self._log_audit(
            action="admin_user_created",
            entity_type="user",
            entity_id=user.id,
            changes={"email": email, "name": name, "role": "admin"}
        )
        
        logger.info({
            "event": "admin_user_created",
            "company_id": str(self.company_id),
            "user_id": str(user.id),
            "email": email,
        })
        
        return {
            "user_id": user.id,
            "email": user.email,
            "role": user.role.value,
            "temp_password": True,
        }
    
    async def initialize_subscription(
        self,
        tier: str,
        billing_email: str
    ) -> Dict[str, Any]:
        """
        Set up initial subscription.
        
        Creates subscription record in trial status.
        
        Args:
            tier: Subscription tier
            billing_email: Email for billing
            
        Returns:
            Dict with subscription details
        """
        if self.company_id is None:
            raise ValueError("Company ID is required")
        
        # Validate tier
        if tier not in TIER_MAPPING:
            raise ValueError(f"Invalid tier: {tier}")
        
        # Validate billing email
        if not billing_email or not self._validate_email(billing_email):
            raise ValueError("Valid billing email is required")
        
        # Calculate amounts based on tier
        tier_pricing = {
            "mini": 1000,
            "parwa": 2500,
            "parwa_high": 4500,
        }
        
        amount_cents = tier_pricing.get(tier, 1000) * 100
        
        # Create subscription (trialing status)
        now = datetime.now(timezone.utc)
        
        subscription = Subscription(
            company_id=self.company_id,
            stripe_subscription_id=None,  # Will be set after Stripe integration
            plan_tier=tier,
            status="trialing",
            current_period_start=now,
            current_period_end=now,  # Will be updated after payment
            amount_cents=amount_cents,
            currency="usd",
        )
        
        self.db.add(subscription)
        await self.db.flush()
        await self.db.refresh(subscription)
        
        # Log audit
        await self._log_audit(
            action="subscription_initialized",
            entity_type="subscription",
            entity_id=subscription.id,
            changes={"tier": tier, "billing_email": billing_email}
        )
        
        logger.info({
            "event": "subscription_initialized",
            "company_id": str(self.company_id),
            "subscription_id": str(subscription.id),
            "tier": tier,
        })
        
        return {
            "subscription_id": subscription.id,
            "tier": tier,
            "status": subscription.status,
            "amount_cents": amount_cents,
            "currency": "usd",
            "billing_email": billing_email,
        }
    
    async def send_welcome_email(
        self,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Trigger welcome email (mocked in development).
        
        In production, this would queue an email via Brevo/SendGrid.
        
        Args:
            user_id: User UUID to send email to
            
        Returns:
            Dict with:
            - sent: bool
            - email: str
            - message: str
        """
        if self.company_id is None:
            raise ValueError("Company ID is required")
        
        # Get user
        result = await self.db.execute(
            select(User).where(
                and_(
                    User.id == user_id,
                    User.company_id == self.company_id
                )
            )
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError("User not found")
        
        # In development, mock sending
        # In production, this would call an email service
        
        logger.info({
            "event": "welcome_email_sent",
            "company_id": str(self.company_id),
            "user_id": str(user_id),
            "email": user.email,
        })
        
        return {
            "sent": True,
            "email": user.email,
            "message": "Welcome email sent successfully",
        }
    
    async def validate_onboarding_data(
        self,
        step: OnboardingStep,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate onboarding form data.
        
        Args:
            step: The step being validated
            data: Data to validate
            
        Returns:
            Dict with:
            - valid: bool
            - errors: List[str]
        """
        errors = []
        
        if step == OnboardingStep.COMPANY_INFO:
            if not data.get("name") or not data.get("name", "").strip():
                errors.append("Company name is required")
            if not data.get("industry") or not data.get("industry", "").strip():
                errors.append("Industry is required")
        
        elif step == OnboardingStep.ADMIN_USER:
            if not data.get("email") or not self._validate_email(data.get("email", "")):
                errors.append("Valid email is required")
            if not data.get("name") or not data.get("name", "").strip():
                errors.append("Name is required")
            if not data.get("password") or len(data.get("password", "")) < 8:
                errors.append("Password must be at least 8 characters")
        
        elif step == OnboardingStep.SUBSCRIPTION:
            if data.get("tier") not in TIER_MAPPING:
                errors.append("Valid subscription tier is required")
            if not data.get("billing_email") or not self._validate_email(data.get("billing_email", "")):
                errors.append("Valid billing email is required")
        
        elif step == OnboardingStep.INTEGRATION:
            # Integration step is optional
            pass
        
        elif step == OnboardingStep.TRAINING:
            # Training step is optional
            pass
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }
    
    async def get_onboarding_progress_percentage(self) -> float:
        """
        Calculate onboarding progress percentage.
        
        Returns:
            Float between 0.0 and 100.0
        """
        if self.company_id is None:
            return 0.0
        
        # Get company
        result = await self.db.execute(
            select(Company).where(Company.id == self.company_id)
        )
        company = result.scalar_one_or_none()
        
        if not company:
            return 0.0
        
        # Get steps completed
        steps_completed = getattr(company, 'steps_completed', []) or []
        if isinstance(steps_completed, str):
            steps_completed = steps_completed.split(',') if steps_completed else []
        
        progress = (len(steps_completed) / len(ONBOARDING_STEPS)) * 100
        
        return round(progress, 1)
    
    def _validate_email(self, email: str) -> bool:
        """
        Validate email format.
        
        Args:
            email: Email address to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not email:
            return False
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    async def _log_audit(
        self,
        action: str,
        entity_type: str,
        entity_id: UUID,
        changes: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log audit trail entry.
        
        Args:
            action: Action performed
            entity_type: Entity type (company, user, subscription, etc.)
            entity_id: Entity UUID
            changes: Optional dict of changes
        """
        if self.company_id is None:
            return
        
        audit = AuditTrail(
            company_id=self.company_id,
            ticket_id=None,
            actor="onboarding_service",
            action=action,
            details={
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "changes": changes or {},
            },
            previous_hash=None,
            entry_hash="",  # Will be computed by model
        )
        
        self.db.add(audit)
        # Don't flush - let the caller handle commit
