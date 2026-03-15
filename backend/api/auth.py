"""
PARWA Authentication API Routes.
Provides endpoints for user registration, login, token refresh, and logout.
Uses JWT for authentication with Redis-based token blacklisting.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db
from backend.models.user import User, RoleEnum
from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger
from shared.core_functions.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    sanitize_input,
    validate_email,
    verify_password,
)
from security.rate_limiter import RateLimiter

# Initialize router and logger
router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = get_logger(__name__)
settings = get_settings()
security = HTTPBearer()


# --- Pydantic Schemas ---

class UserRegisterRequest(BaseModel):
    """Request schema for user registration."""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, max_length=128, description="User's password")
    company_id: uuid.UUID = Field(..., description="ID of the company user belongs to")
    role: RoleEnum = Field(default=RoleEnum.viewer, description="User's role")


class UserLoginRequest(BaseModel):
    """Request schema for user login."""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


class TokenRefreshRequest(BaseModel):
    """Request schema for token refresh."""
    refresh_token: str = Field(..., description="Valid refresh token")


class AuthResponse(BaseModel):
    """Response schema for successful authentication."""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: Optional[str] = Field(None, description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    user_id: uuid.UUID = Field(..., description="User's unique ID")
    email: str = Field(..., description="User's email address")
    role: str = Field(..., description="User's role")


class MessageResponse(BaseModel):
    """Generic message response schema."""
    message: str = Field(..., description="Response message")


class UserProfileResponse(BaseModel):
    """Response schema for user profile data."""
    id: uuid.UUID
    email: str
    role: str
    company_id: uuid.UUID
    is_active: bool
    created_at: datetime


# --- Helper Functions ---

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Extract and validate the current user from JWT token.

    Args:
        credentials: HTTP Bearer credentials containing the JWT token.
        db: Async database session.

    Returns:
        User: The authenticated user instance.

    Raises:
        HTTPException: If token is invalid, expired, or user not found.
    """
    token = credentials.credentials

    try:
        payload = decode_access_token(token, settings.secret_key.get_secret_value())
    except ValueError as e:
        logger.warning({"event": "token_decode_failed", "error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if token is blacklisted
    if await is_token_blacklisted(token):
        logger.warning({"event": "blacklisted_token_used", "user_id": payload.get("sub")})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from database
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


async def blacklist_token(token: str) -> bool:
    """
    Add a token to the Redis blacklist.

    Args:
        token: The JWT token to blacklist.

    Returns:
        bool: True if successfully blacklisted, False otherwise.
    """
    from shared.utils.cache import Cache

    try:
        cache = Cache()
        # Store token in blacklist for 24 hours (typical token lifetime)
        await cache.set(f"blacklist:{token}", "1", expire=86400)
        await cache.close()
        logger.info({"event": "token_blacklisted"})
        return True
    except Exception as e:
        logger.error({"event": "blacklist_failed", "error": str(e)})
        return False


async def is_token_blacklisted(token: str) -> bool:
    """
    Check if a token is in the Redis blacklist.

    Args:
        token: The JWT token to check.

    Returns:
        bool: True if token is blacklisted, False otherwise.
    """
    from shared.utils.cache import Cache

    try:
        cache = Cache()
        exists = await cache.exists(f"blacklist:{token}")
        await cache.close()
        return exists
    except Exception as e:
        logger.error({"event": "blacklist_check_failed", "error": str(e)})
        # Fail open - don't block users if Redis is down
        return False


# --- API Endpoints ---

@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with email and password."
)
async def register(
    request: UserRegisterRequest,
    db: AsyncSession = Depends(get_db)
) -> AuthResponse:
    """
    Register a new user.

    Creates a new user account with the provided email, password, and company
    association. Returns JWT tokens for immediate authentication.

    Args:
        request: User registration data including email, password, company_id, and role.
        db: Async database session.

    Returns:
        AuthResponse: JWT tokens and user information.

    Raises:
        HTTPException: 409 if email already exists, 400 for validation errors.
    """
    # Sanitize email input
    email = sanitize_input(request.email.lower())

    # Check if user already exists
    existing_result = await db.execute(select(User).where(User.email == email))
    existing_user = existing_result.scalar_one_or_none()

    if existing_user:
        logger.warning({"event": "registration_duplicate_email", "email": email})
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Hash password
    try:
        password_hash = hash_password(request.password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Create new user
    new_user = User(
        company_id=request.company_id,
        email=email,
        password_hash=password_hash,
        role=request.role,
        is_active=True,
    )

    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)

    # Generate tokens
    token_data = {
        "sub": str(new_user.id),
        "email": new_user.email,
        "role": new_user.role.value,
        "company_id": str(new_user.company_id),
    }

    access_token = create_access_token(
        data=token_data,
        secret_key=settings.secret_key.get_secret_value(),
        expires_delta=timedelta(hours=1),
    )

    refresh_token = create_access_token(
        data={**token_data, "type": "refresh"},
        secret_key=settings.secret_key.get_secret_value(),
        expires_delta=timedelta(days=7),
    )

    logger.info({
        "event": "user_registered",
        "user_id": str(new_user.id),
        "email": email,
        "company_id": str(request.company_id),
    })

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=new_user.id,
        email=new_user.email,
        role=new_user.role.value,
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="User login",
    description="Authenticate user and return JWT tokens."
)
async def login(
    request: UserLoginRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db)
) -> AuthResponse:
    """
    Authenticate a user and return JWT tokens.

    Validates email and password credentials. Implements rate limiting
    to prevent brute force attacks.

    Args:
        request: User login credentials.
        http_request: FastAPI request object for rate limiting.
        db: Async database session.

    Returns:
        AuthResponse: JWT tokens and user information.

    Raises:
        HTTPException: 401 for invalid credentials, 429 for rate limit exceeded.
    """
    # Rate limiting: 5 attempts per minute per IP
    rate_limiter = RateLimiter()
    client_ip = http_request.client.host if http_request.client else "unknown"
    rate_key = f"login:{client_ip}"

    is_allowed = await rate_limiter.is_allowed(rate_key, limit=5, window=60)
    await rate_limiter.close()

    if not is_allowed:
        logger.warning({"event": "login_rate_limited", "ip": client_ip})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )

    # Sanitize and normalize email
    email = sanitize_input(request.email.lower())

    # Fetch user by email
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    # Check if user exists and is active
    if not user or not user.is_active:
        logger.warning({"event": "login_failed", "email": email, "reason": "user_not_found"})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    if not verify_password(request.password, user.password_hash):
        logger.warning({"event": "login_failed", "email": email, "reason": "invalid_password"})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate tokens
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value,
        "company_id": str(user.company_id),
    }

    access_token = create_access_token(
        data=token_data,
        secret_key=settings.secret_key.get_secret_value(),
        expires_delta=timedelta(hours=1),
    )

    refresh_token = create_access_token(
        data={**token_data, "type": "refresh"},
        secret_key=settings.secret_key.get_secret_value(),
        expires_delta=timedelta(days=7),
    )

    logger.info({
        "event": "user_logged_in",
        "user_id": str(user.id),
        "email": email,
        "company_id": str(user.company_id),
    })

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        email=user.email,
        role=user.role.value,
    )


@router.post(
    "/refresh",
    response_model=AuthResponse,
    summary="Refresh access token",
    description="Get a new access token using a valid refresh token."
)
async def refresh_token(
    request: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db)
) -> AuthResponse:
    """
    Refresh an access token.

    Validates the provided refresh token and issues a new access token.

    Args:
        request: Contains the refresh token.
        db: Async database session.

    Returns:
        AuthResponse: New JWT access token.

    Raises:
        HTTPException: 401 if refresh token is invalid or expired.
    """
    try:
        payload = decode_access_token(
            request.refresh_token,
            settings.secret_key.get_secret_value()
        )
    except ValueError as e:
        logger.warning({"event": "refresh_token_invalid", "error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify it's a refresh token
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if token is blacklisted
    if await is_token_blacklisted(request.refresh_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate new access token
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value,
        "company_id": str(user.company_id),
    }

    new_access_token = create_access_token(
        data=token_data,
        secret_key=settings.secret_key.get_secret_value(),
        expires_delta=timedelta(hours=1),
    )

    logger.info({
        "event": "token_refreshed",
        "user_id": str(user.id),
    })

    return AuthResponse(
        access_token=new_access_token,
        user_id=user.id,
        email=user.email,
        role=user.role.value,
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="User logout",
    description="Invalidate the current access token."
)
async def logout(
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> MessageResponse:
    """
    Logout the current user.

    Adds the current access token to a Redis blacklist, effectively
    invalidating it for future requests.

    Args:
        current_user: The authenticated user (injected via dependency).
        credentials: HTTP Bearer credentials containing the JWT token.

    Returns:
        MessageResponse: Success message confirming logout.
    """
    token = credentials.credentials

    # Add token to blacklist
    success = await blacklist_token(token)

    if not success:
        logger.error({"event": "logout_failed", "user_id": str(current_user.id)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to logout. Please try again.",
        )

    logger.info({
        "event": "user_logged_out",
        "user_id": str(current_user.id),
        "email": current_user.email,
    })

    return MessageResponse(message="Successfully logged out")


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current user profile",
    description="Retrieve the authenticated user's profile information."
)
async def get_profile(
    current_user: User = Depends(get_current_user)
) -> UserProfileResponse:
    """
    Get the current user's profile.

    Returns the authenticated user's profile information including
    their role, company association, and account status.

    Args:
        current_user: The authenticated user (injected via dependency).

    Returns:
        UserProfileResponse: User profile data.
    """
    logger.info({
        "event": "profile_retrieved",
        "user_id": str(current_user.id),
    })

    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role.value,
        company_id=current_user.company_id,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )
