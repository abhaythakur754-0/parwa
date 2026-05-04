"""
PARWA Onboarding Schemas (F-028 to F-035)

Pydantic models for onboarding request/response validation.

Week 6 Day 1: Post-Payment Details + Onboarding State
- UserDetailsRequest: Submit user details after payment
- UserDetailsResponse: User details data
- OnboardingStateResponse: Current onboarding state
- WorkEmailVerificationRequest: Send work email verification

BC-001: All responses include company_id for tenant context.
"""

import re
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator


# ── Shared Validators ──────────────────────────────────────────────

_EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


def _validate_email(email: str) -> str:
    """Validate email format."""
    if not email or not _EMAIL_REGEX.match(email):
        raise ValueError("Invalid email format")
    return email.strip().lower()


# ── Industry Options ────────────────────────────────────────────────

INDUSTRY_OPTIONS = [
    "saas",
    "ecommerce",
    "healthcare",
    "finance",
    "education",
    "real_estate",
    "manufacturing",
    "consulting",
    "agency",
    "nonprofit",
    "logistics",
    "hospitality",
    "retail",
    "other",
]

COMPANY_SIZE_OPTIONS = [
    "1_10",
    "11_50",
    "51_200",
    "201_500",
    "501_1000",
    "1000_plus",
]


# ── User Details Schemas (Day 1) ────────────────────────────────────


class UserDetailsRequest(BaseModel):
    """Request to submit/update user details after payment.

    Week 6 Day 1: Post-payment details collection.
    Required before user can proceed to onboarding wizard.
    """

    full_name: str = Field(min_length=2, max_length=100)
    company_name: str = Field(min_length=2, max_length=100)
    work_email: Optional[str] = Field(default=None, max_length=255)
    industry: str = Field(min_length=1, max_length=50)
    company_size: Optional[str] = Field(default=None, max_length=20)
    website: Optional[str] = Field(default=None, max_length=255)

    @field_validator("work_email")
    @classmethod
    def work_email_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        return _validate_email(v)

    @field_validator("industry")
    @classmethod
    def industry_must_be_valid(cls, v: str) -> str:
        if v not in INDUSTRY_OPTIONS:
            raise ValueError(
                f"Invalid industry. Must be one of: {', '.join(INDUSTRY_OPTIONS)}"
            )
        return v

    @field_validator("company_size")
    @classmethod
    def company_size_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        if v not in COMPANY_SIZE_OPTIONS:
            raise ValueError(
                f"Invalid company_size. Must be one of: {', '.join(COMPANY_SIZE_OPTIONS)}"
            )
        return v

    @field_validator("website")
    @classmethod
    def website_must_be_valid_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        # Basic URL validation
        if not v.startswith(("http://", "https://")):
            v = "https://" + v
        return v


class UserDetailsResponse(BaseModel):
    """Response with user details data."""

    id: str
    user_id: str
    company_id: str
    full_name: str
    company_name: str
    work_email: Optional[str] = None
    work_email_verified: bool = False
    industry: str
    company_size: Optional[str] = None
    website: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


class WorkEmailVerificationRequest(BaseModel):
    """Request to send work email verification."""

    work_email: str = Field(min_length=5, max_length=255)

    @field_validator("work_email")
    @classmethod
    def work_email_must_be_valid(cls, v: str) -> str:
        return _validate_email(v)


class WorkEmailVerificationResponse(BaseModel):
    """Response after sending work email verification."""

    message: str
    work_email: str


class VerifyWorkEmailRequest(BaseModel):
    """Request to verify work email with token."""

    token: str = Field(min_length=32, max_length=64)


# ── Onboarding State Schemas (Day 1) ─────────────────────────────────


class OnboardingStateResponse(BaseModel):
    """Response with current onboarding state.

    Week 6 Day 1: Get user's onboarding progress.
    Used to determine which step to show after payment.
    """

    id: Optional[str] = None
    user_id: str
    company_id: str
    current_step: int = 1
    completed_steps: List[int] = []
    status: str = "in_progress"

    # Progress flags
    details_completed: bool = False
    wizard_started: bool = False
    legal_accepted: bool = False
    first_victory_completed: bool = False

    # AI config
    ai_name: str = "Jarvis"
    ai_tone: str = "professional"
    ai_response_style: str = "concise"
    ai_greeting: Optional[str] = None

    # Timestamps
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Legal Consent Schemas (Day 3) ───────────────────────────────────


class LegalConsentRequest(BaseModel):
    """Request to accept legal consents (Step 2).

    Week 6 Day 3: Legal consent collection.
    All three must be accepted to proceed.
    """

    accept_terms: bool = Field(...)
    accept_privacy: bool = Field(...)
    accept_ai_data: bool = Field(...)

    @field_validator("accept_terms")
    @classmethod
    def terms_must_be_accepted(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Terms of Service must be accepted")
        return v

    @field_validator("accept_privacy")
    @classmethod
    def privacy_must_be_accepted(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Privacy Policy must be accepted")
        return v

    @field_validator("accept_ai_data")
    @classmethod
    def ai_data_must_be_accepted(cls, v: bool) -> bool:
        if not v:
            raise ValueError("AI Data Processing Agreement must be accepted")
        return v


class LegalConsentResponse(BaseModel):
    """Response after accepting legal consents."""

    message: str
    terms_accepted_at: Optional[str] = None
    privacy_accepted_at: Optional[str] = None
    ai_data_accepted_at: Optional[str] = None


# ── AI Config Schemas (Day 7) ───────────────────────────────────────


class AIConfigRequest(BaseModel):
    """Request to update AI personality config (Step 5).

    Week 6 Day 7: AI customization.
    """

    ai_name: str = Field(min_length=1, max_length=50, default="Jarvis")
    ai_tone: str = Field(max_length=20, default="professional")
    ai_response_style: str = Field(max_length=20, default="concise")
    ai_greeting: Optional[str] = Field(default=None, max_length=500)

    @field_validator("ai_tone")
    @classmethod
    def tone_must_be_valid(cls, v: str) -> str:
        valid_tones = ["professional", "friendly", "casual"]
        if v not in valid_tones:
            raise ValueError(
                f"Invalid ai_tone. Must be one of: {', '.join(valid_tones)}"
            )
        return v

    @field_validator("ai_response_style")
    @classmethod
    def style_must_be_valid(cls, v: str) -> str:
        valid_styles = ["concise", "detailed"]
        if v not in valid_styles:
            raise ValueError(
                f"Invalid ai_response_style. Must be one of: {', '.join(valid_styles)}"
            )
        return v


class AIConfigResponse(BaseModel):
    """Response with AI config."""

    ai_name: str
    ai_tone: str
    ai_response_style: str
    ai_greeting: Optional[str] = None


# ── Simple Response Schemas ─────────────────────────────────────────


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str


class StepCompleteResponse(BaseModel):
    """Response after completing a step."""

    message: str
    current_step: int
    completed_steps: List[int]
