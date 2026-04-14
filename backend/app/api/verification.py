"""
PARWA Business Email Verification Router (Week 6 Day 10-11)

Endpoints for business email OTP verification.

Flow:
1. POST /api/verification/send-otp - Send 6-digit OTP to business email
2. POST /api/verification/verify-otp - Verify the OTP code

BC-001: All operations scoped to authenticated user's company_id.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.exceptions import ValidationError, RateLimitError
from app.logger import get_logger
from app.services.business_email_otp_service import (
    send_business_email_otp,
    verify_business_email_otp,
    check_business_email_verified,
)
from database.base import get_db
from database.models.core import User

logger = get_logger("verification_api")
router = APIRouter(prefix="/api/verification", tags=["Verification"])


# ── Request/Response Schemas ───────────────────────────────────────────────


class SendOTPRequest(BaseModel):
    """Request to send OTP to business email."""
    email: str = Field(..., description="Business email address to verify")
    
    @validator("email")
    def validate_email(cls, v: str) -> str:
        v = v.lower().strip()
        if not v or "@" not in v:
            raise ValueError("Invalid email address")
        return v


class SendOTPResponse(BaseModel):
    """Response after sending OTP."""
    message: str
    expires_in: int = Field(..., description="OTP expiry time in seconds")
    email: str


class VerifyOTPRequest(BaseModel):
    """Request to verify OTP code."""
    email: str = Field(..., description="Business email being verified")
    otp_code: str = Field(..., description="6-digit OTP code")
    
    @validator("email")
    def validate_email(cls, v: str) -> str:
        v = v.lower().strip()
        if not v or "@" not in v:
            raise ValueError("Invalid email address")
        return v
    
    @validator("otp_code")
    def validate_otp(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) != 6 or not v.isdigit():
            raise ValueError("OTP must be a 6-digit code")
        return v


class VerifyOTPResponse(BaseModel):
    """Response after verifying OTP."""
    status: str
    message: str
    email: str


class VerificationStatusResponse(BaseModel):
    """Response for verification status check."""
    email: str
    verified: bool


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.post(
    "/send-otp",
    response_model=SendOTPResponse,
)
def send_otp(
    body: SendOTPRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SendOTPResponse:
    """Send an OTP code to verify business email.
    
    Week 6 Day 10-11: Anti-scam verification step.
    
    Rate limited to 3 requests per hour per email.
    OTP expires in 10 minutes.
    
    Args:
        body: Email address to verify.
        user: Authenticated user.
        db: Database session.
        
    Returns:
        SendOTPResponse with message and expiry time.
        
    Raises:
        ValidationError: If email is not a business email.
        RateLimitError: If rate limited.
    """
    try:
        result = send_business_email_otp(
            db=db,
            email=body.email,
            user_id=user.id,
            company_id=user.company_id,
            user_name=user.full_name,
        )
        return SendOTPResponse(**result)
    except (ValidationError, RateLimitError):
        raise
    except Exception as exc:
        logger.error(
            "send_otp_unexpected_error",
            email=body.email,
            error=str(exc),
        )
        raise ValidationError(
            message="Failed to send verification code. Please try again.",
            details={"error": "unexpected_error"},
        )


@router.post(
    "/verify-otp",
    response_model=VerifyOTPResponse,
)
def verify_otp(
    body: VerifyOTPRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VerifyOTPResponse:
    """Verify the OTP code for business email.
    
    Week 6 Day 10-11: Completes business email verification.
    
    Max 5 verification attempts per OTP.
    
    Args:
        body: Email and OTP code.
        user: Authenticated user.
        db: Database session.
        
    Returns:
        VerifyOTPResponse with verification status.
        
    Raises:
        ValidationError: If OTP is invalid/expired.
    """
    try:
        result = verify_business_email_otp(
            db=db,
            email=body.email,
            otp_code=body.otp_code,
            company_id=user.company_id,
        )
        return VerifyOTPResponse(**result)
    except ValidationError:
        raise
    except Exception as exc:
        logger.error(
            "verify_otp_unexpected_error",
            email=body.email,
            error=str(exc),
        )
        raise ValidationError(
            message="Verification failed. Please try again.",
            details={"error": "unexpected_error"},
        )


@router.get(
    "/status/{email}",
    response_model=VerificationStatusResponse,
)
def get_verification_status(
    email: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VerificationStatusResponse:
    """Check if a business email has been verified.
    
    Args:
        email: Email address to check.
        user: Authenticated user.
        db: Database session.
        
    Returns:
        VerificationStatusResponse with verified status.
    """
    email = email.lower().strip()
    
    verified = check_business_email_verified(
        db=db,
        email=email,
        company_id=user.company_id,
    )
    
    return VerificationStatusResponse(
        email=email,
        verified=verified,
    )
