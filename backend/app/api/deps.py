"""
PARWA Auth Dependencies (BC-011)

FastAPI dependencies for route-level authentication and
authorization. Used as dependency injection in route handlers.

BC-001: Every authenticated request carries company_id.
BC-011: JWT verification on every protected endpoint.
"""

from typing import Dict, Optional

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.auth import verify_access_token
from app.exceptions import AuthenticationError
from app.exceptions import AuthorizationError
from database.base import get_db
from database.models.core import User, Company


def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """Extract and validate JWT from Authorization header.

    BC-011: Every protected endpoint uses this dependency.
    Sets company_id on the token for downstream tenant checks.

    Args:
        authorization: The Authorization header value.
        db: Database session.

    Returns:
        Authenticated User object.

    Raises:
        AuthenticationError: If token is missing or invalid.
    """
    if not authorization:
        raise AuthenticationError(
            message="Authorization header required"
        )

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0] != "Bearer":
        raise AuthenticationError(
            message="Invalid authorization format. "
                    "Use: Bearer <token>"
        )

    token = parts[1]
    payload = verify_access_token(token)

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError(
            message="Invalid token payload"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AuthenticationError(
            message="User not found"
        )

    if not user.is_active:
        raise AuthenticationError(
            message="Account is disabled"
        )

    # Store user info for downstream dependencies
    user._token_payload = payload  # type: ignore[attr-defined]

    return user


def get_current_company(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Company:
    """Fetch the authenticated user's company.

    BC-001: Every user belongs to exactly one company.

    Args:
        user: Authenticated user (from get_current_user).
        db: Database session.

    Returns:
        Company object.

    Raises:
        AuthenticationError: If company not found.
    """
    company = db.query(Company).filter(
        Company.id == user.company_id
    ).first()

    if not company:
        raise AuthenticationError(
            message="Company not found for user"
        )

    return company


def require_roles(*roles: str):
    """Factory dependency that checks user role.

    Usage:
        @router.get("/admin/stuff")
        async def admin_stuff(
            user: User = Depends(require_roles("owner", "admin")),
        ):
            ...

    Args:
        *roles: Allowed role names.

    Returns:
        Dependency function.
    """
    def checker(
        user: User = Depends(get_current_user),
    ) -> User:
        if user.role not in roles:
            raise AuthorizationError(
                message="Insufficient permissions",
                details={
                    "required_role": roles,
                    "user_role": user.role,
                },
            )
        return user

    return checker


def get_company_id(
    user: User = Depends(get_current_user),
) -> str:
    """Extract company_id from authenticated user.

    BC-001: Every user belongs to exactly one company.

    Args:
        user: Authenticated user (from get_current_user).

    Returns:
        Company ID string.

    Raises:
        AuthenticationError: If user has no company.
    """
    if not user.company_id:
        raise AuthenticationError(
            message="User has no associated company"
        )
    return str(user.company_id)


# Pre-defined role groups for common access patterns
ALL_ROLES = ("owner", "admin", "agent", "viewer")
MANAGEMENT_ROLES = ("owner", "admin")
OPERATIONAL_ROLES = ("owner", "admin", "agent")


def require_management(*override_roles):
    """Owner/Admin only — for billing, settings, integrations, dangerous operations."""
    roles = override_roles if override_roles else MANAGEMENT_ROLES
    return require_roles(*roles)


def require_operational(*override_roles):
    """Owner/Admin/Agent — for ticket ops, customer management, training."""
    roles = override_roles if override_roles else OPERATIONAL_ROLES
    return require_roles(*roles)


def optional_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Extract user from JWT if present, else return None.

    For endpoints that work for both authenticated and
    anonymous users.

    Args:
        authorization: The Authorization header value.
        db: Database session.

    Returns:
        User object or None.
    """
    if not authorization:
        return None

    try:
        return get_current_user(authorization, db)
    except AuthenticationError:
        return None


def get_tenant_context(
    request: Request,
    user: User = Depends(get_current_user),
) -> Dict[str, str]:
    """Extract tenant context from request and authenticated user.

    BC-001: Every request carries company_id for tenant isolation.
    Returns a dict with company_id for use in service layer.

    Args:
        request: The incoming request.
        user: Authenticated user (from get_current_user).

    Returns:
        Dict with company_id.
    """
    return {
        "company_id": str(user.company_id),
        "user_id": str(user.id),
        "role": user.role,
    }
