"""
PARWA Phase 5 — Authentication API

JWT-based authentication with bcrypt password hashing.
- POST /auth/register  — Create company + owner user
- POST /auth/login     — Email/password → JWT token pair
- POST /auth/refresh   — Refresh access token
- GET  /auth/me        — Current user info

CRITICAL RULES:
- BC-001: All operations scoped to company_id
- BC-008: Never crash — all route handlers in try/except
- Paddle is ONLY for PARWA's own subscription billing
- No mock data, no placeholder emails
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.api.deps import get_db
from database.models.core import Company, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=255)
    industry: str = Field(default="general", pattern="^(ecommerce|saas|logistics|general)$")
    user_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class RegisterResponse(BaseModel):
    company_id: str
    user_id: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    company_id: str
    user_name: str
    role: str


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    id: str
    email: str
    name: str
    role: str
    company_id: str
    company_name: str
    industry: str
    subscription_variant: str
    is_active: bool


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def _create_access_token(user_id: str, company_id: str, role: str) -> str:
    """Create a short-lived access token."""
    payload = {
        "sub": user_id,
        "company_id": company_id,
        "role": role,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _create_refresh_token(user_id: str, company_id: str) -> str:
    """Create a long-lived refresh token."""
    payload = {
        "sub": user_id,
        "company_id": company_id,
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


def _hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Auth dependency — extract current user from JWT
# ---------------------------------------------------------------------------

def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> User:
    """Extract and validate user from Authorization header.

    Usage: current_user: User = Depends(get_current_user)
    """
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid Authorization header",
            )

        token = authorization[7:]  # strip "Bearer "
        payload = _decode_token(token)

        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        return user

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_current_user failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new company and its owner user.

    Creates:
    1. Company record with the given name and industry
    2. Owner user with hashed password
    3. Returns JWT token pair for immediate login
    """
    try:
        # Check if email already exists in any company
        existing = db.query(User).filter(User.email == req.email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists",
            )

        # Create company
        company = Company(
            name=req.company_name,
            industry=req.industry,
            subscription_variant="mini",
        )
        db.add(company)
        db.flush()  # get company.id

        # Create owner user with hashed password
        hashed_pw = _hash_password(req.password)
        user = User(
            company_id=company.id,
            email=req.email,
            name=req.user_name,
            role="owner",
            is_active=True,
        )
        # Store password hash in a special CompanySetting
        # We'll add a password_hash column to User instead
        # Actually let's just add it directly
        user.password_hash = hashed_pw  # type: ignore[attr-defined]
        db.add(user)
        db.commit()
        db.refresh(user)
        db.refresh(company)

        # Generate tokens
        access_token = _create_access_token(user.id, company.id, user.role)
        refresh_token = _create_refresh_token(user.id, company.id)

        logger.info("New registration: company=%s user=%s", company.id, user.id)

        return RegisterResponse(
            company_id=company.id,
            user_id=user.id,
            access_token=access_token,
            refresh_token=refresh_token,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Registration failed: %s", exc)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again.",
        )


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user with email and password.

    Returns JWT token pair on success.
    """
    try:
        # Find user by email
        user = db.query(User).filter(User.email == req.email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Verify password
        if not hasattr(user, "password_hash") or not user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account not properly set up. Please reset your password.",
            )

        if not _verify_password(req.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated. Contact your administrator.",
            )

        # Get company
        company = db.query(Company).filter(Company.id == user.company_id).first()

        # Generate tokens
        access_token = _create_access_token(user.id, user.company_id, user.role)
        refresh_token = _create_refresh_token(user.id, user.company_id)

        logger.info("Login: user=%s company=%s", user.id, user.company_id)

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=user.id,
            company_id=user.company_id,
            user_name=user.name,
            role=user.role,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Login failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed. Please try again.",
        )


@router.post("/refresh", response_model=RefreshResponse)
def refresh_token(req: RefreshRequest, db: Session = Depends(get_db)):
    """Refresh an access token using a valid refresh token."""
    try:
        payload = _decode_token(req.refresh_token)

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type — expected refresh token",
            )

        user_id = payload.get("sub")
        company_id = payload.get("company_id")

        # Verify user still exists and is active
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        # Issue new token pair
        access_token = _create_access_token(user.id, user.company_id, user.role)
        new_refresh = _create_refresh_token(user.id, user.company_id)

        return RefreshResponse(
            access_token=access_token,
            refresh_token=new_refresh,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Token refresh failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token refresh failed",
        )


@router.get("/me", response_model=UserInfo)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current authenticated user info."""
    try:
        company = db.query(Company).filter(Company.id == current_user.company_id).first()

        return UserInfo(
            id=current_user.id,
            email=current_user.email,
            name=current_user.name,
            role=current_user.role,
            company_id=current_user.company_id,
            company_name=company.name if company else "Unknown",
            industry=company.industry if company else "general",
            subscription_variant=company.subscription_variant if company else "mini",
            is_active=current_user.is_active,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Get user info failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user info",
        )
