"""
PARWA Auth Dependencies (BC-011)

FastAPI dependencies for route-level authentication and
authorization. Used as dependency injection in route handlers.

BC-001: Every authenticated request carries company_id.
BC-011: JWT verification on every protected endpoint.
"""

from typing import Optional

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from backend.app.core.auth import verify_access_token
from backend.app.exceptions import AuthenticationError
from backend.app.exceptions import AuthorizationError
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
