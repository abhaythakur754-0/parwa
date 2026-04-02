"""
PARWA Company Service (F06)

Business logic for company profile, settings, team management,
and password changes.

BC-001: All queries filtered by company_id.
BC-011: bcrypt cost 12 for password hashing.
BC-012: Structured error responses.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from backend.app.exceptions import (
    AuthorizationError,
    NotFoundError,
    ValidationError,
)
from backend.app.logger import get_logger
from database.models.core import Company, CompanySetting, User
from shared.utils.security import hash_password, verify_password

logger = get_logger("company_service")

# Role hierarchy for authorization checks
_ROLE_HIERARCHY = {"owner": 4, "admin": 3, "agent": 2, "viewer": 1}


def get_company_profile(
    company_id: str, db: Session,
) -> Company:
    """Get company profile by ID.

    BC-001: Filtered by company_id.

    Args:
        company_id: The company UUID.
        db: Database session.

    Returns:
        Company object.

    Raises:
        NotFoundError: If company not found.
    """
    company = db.query(Company).filter(
        Company.id == company_id,
    ).first()
    if not company:
        raise NotFoundError(
            message="Company not found",
            details={"company_id": company_id},
        )
    return company


def update_company_profile(
    company_id: str,
    data: Dict[str, Any],
    db: Session,
) -> Company:
    """Update company profile fields.

    Only updates fields that are provided in data.

    BC-001: Filtered by company_id.

    Args:
        company_id: The company UUID.
        data: Dict of fields to update.
        db: Database session.

    Returns:
        Updated Company object.

    Raises:
        NotFoundError: If company not found.
    """
    company = db.query(Company).filter(
        Company.id == company_id,
    ).first()
    if not company:
        raise NotFoundError(
            message="Company not found",
            details={"company_id": company_id},
        )

    for field, value in data.items():
        if value is not None and hasattr(company, field):
            setattr(company, field, value)

    company.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(company)

    logger.info(
        "company_profile_updated",
        company_id=company_id,
        fields=list(data.keys()),
    )

    return company


def get_company_settings(
    company_id: str, db: Session,
) -> CompanySetting:
    """Get company settings, auto-creating with defaults if needed.

    BC-001: Filtered by company_id.

    Args:
        company_id: The company UUID.
        db: Database session.

    Returns:
        CompanySetting object.
    """
    settings = db.query(CompanySetting).filter(
        CompanySetting.company_id == company_id,
    ).first()

    if not settings:
        # Use merge to handle race condition: if two concurrent
        # requests both try to create, the second merge will
        # fetch the existing row instead of failing.
        settings = CompanySetting(company_id=company_id)
        db.add(settings)
        try:
            db.commit()
            db.refresh(settings)
            logger.info(
                "company_settings_auto_created",
                company_id=company_id,
            )
        except Exception:
            db.rollback()
            settings = db.query(CompanySetting).filter(
                CompanySetting.company_id == company_id,
            ).first()

    return settings


def update_company_settings(
    company_id: str,
    data: Dict[str, Any],
    db: Session,
) -> CompanySetting:
    """Update company settings.

    Lists (prohibited_phrases, pii_patterns, custom_regex,
    intent_labels, custom_rules, assignment_rules) are stored
    as JSON strings in the DB.

    Dicts (confidence_thresholds) are stored as JSON strings.

    BC-001: Filtered by company_id.

    Args:
        company_id: The company UUID.
        data: Dict of fields to update.
        db: Database session.

    Returns:
        Updated CompanySetting object.

    Raises:
        NotFoundError: If company not found.
    """
    company = db.query(Company).filter(
        Company.id == company_id,
    ).first()
    if not company:
        raise NotFoundError(
            message="Company not found",
            details={"company_id": company_id},
        )

    settings = db.query(CompanySetting).filter(
        CompanySetting.company_id == company_id,
    ).first()

    if not settings:
        settings = CompanySetting(company_id=company_id)
        db.add(settings)
        try:
            db.flush()
        except Exception:
            db.rollback()
            settings = db.query(CompanySetting).filter(
                CompanySetting.company_id == company_id,
            ).first()

    _JSON_LIST_FIELDS = [
        "prohibited_phrases", "pii_patterns", "custom_regex",
        "intent_labels", "custom_rules", "assignment_rules",
    ]
    _JSON_DICT_FIELDS = ["confidence_thresholds"]

    for field, value in data.items():
        if value is None:
            continue
        if not hasattr(settings, field):
            continue

        if field in _JSON_LIST_FIELDS and isinstance(value, list):
            setattr(settings, field, json.dumps(value))
        elif field in _JSON_DICT_FIELDS and isinstance(value, dict):
            setattr(settings, field, json.dumps(value))
        elif field == "ooo_status":
            if hasattr(value, 'value'):
                setattr(settings, field, value.value)
            else:
                setattr(settings, field, str(value))
        else:
            setattr(settings, field, value)

    settings.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(settings)

    logger.info(
        "company_settings_updated",
        company_id=company_id,
        fields=list(data.keys()),
    )

    return settings


def change_password(
    user: User,
    current_password: str,
    new_password: str,
    db: Session,
) -> None:
    """Change a user's password.

    Verifies current password with bcrypt, hashes new password
    with bcrypt cost 12.

    BC-011: bcrypt cost 12.

    Args:
        user: The User object.
        current_password: Plain-text current password.
        new_password: Plain-text new password (already validated).
        db: Database session.

    Raises:
        ValidationError: If current password is incorrect.
    """
    if not verify_password(current_password, user.password_hash):
        raise ValidationError(
            message="Current password is incorrect",
            details={"field": "current_password"},
        )

    user.password_hash = hash_password(new_password)
    user.updated_at = datetime.utcnow()
    db.commit()

    logger.info(
        "password_changed",
        user_id=user.id,
        company_id=user.company_id,
    )


def get_team_members(
    company_id: str,
    db: Session,
    page: int = 1,
    per_page: int = 20,
) -> Tuple[List[User], int]:
    """Get paginated list of team members for a company.

    BC-001: Filtered by company_id.

    Args:
        company_id: The company UUID.
        db: Database session.
        page: Page number (1-indexed).
        per_page: Items per page (max 100).

    Returns:
        Tuple of (users list, total count).
    """
    per_page = min(per_page, 100)
    offset = (page - 1) * per_page

    query = db.query(User).filter(
        User.company_id == company_id,
    )

    total = query.count()
    users = query.order_by(User.created_at.asc()).offset(
        offset,
    ).limit(per_page).all()

    return users, total


def update_team_member(
    company_id: str,
    user_id: str,
    data: Dict[str, Any],
    actor: User,
    db: Session,
) -> User:
    """Update a team member's role or active status.

    Only owner/admin can change roles. Cannot change own role
    to lower. Company must have at least 1 owner.

    BC-001: Filtered by company_id.

    Args:
        company_id: The company UUID.
        user_id: The target user UUID.
        data: Dict with 'role' and/or 'is_active'.
        actor: The user performing the action.
        db: Database session.

    Returns:
        Updated User object.

    Raises:
        NotFoundError: If user not found in company.
        AuthorizationError: If actor lacks permissions.
        ValidationError: If business rules violated.
    """
    target = db.query(User).filter(
        User.id == user_id,
        User.company_id == company_id,
    ).first()

    if not target:
        raise NotFoundError(
            message="Team member not found",
            details={"user_id": user_id},
        )

    # Check permissions: only owner/admin can update roles
    actor_level = _ROLE_HIERARCHY.get(actor.role, 0)
    if actor_level < _ROLE_HIERARCHY.get("admin", 3):
        raise AuthorizationError(
            message="Only owners and admins can manage "
                    "team members",
            details={
                "required_role": "owner or admin",
                "user_role": actor.role,
            },
        )

    # Handle role change
    if "role" in data and data["role"] is not None:
        new_role = data["role"]
        if isinstance(new_role, str):
            new_role_val = new_role
        elif hasattr(new_role, "value"):
            new_role_val = new_role.value
        else:
            new_role_val = str(new_role)

        # Cannot change own role
        if actor.id == target.id:
            raise ValidationError(
                message="Cannot change your own role",
                details={"field": "role"},
            )

        # Check if target is owner and we'd be demoting
        if target.role == "owner" and new_role_val != "owner":
            owner_count = db.query(User).filter(
                User.company_id == company_id,
                User.role == "owner",
                User.is_active == True,  # noqa: E712
            ).count()

            if owner_count <= 1:
                raise ValidationError(
                    message="Company must have at least one "
                            "owner",
                    details={"field": "role"},
                )

        # Actor cannot assign a role higher than their own
        target_level = _ROLE_HIERARCHY.get(new_role_val, 0)
        if target_level > actor_level:
            raise AuthorizationError(
                message="Cannot assign a role higher than "
                        "your own",
                details={
                    "target_role": new_role_val,
                    "actor_role": actor.role,
                },
            )

        target.role = new_role_val

    # Handle is_active change
    if "is_active" in data and data["is_active"] is not None:
        new_active = data["is_active"]

        if not new_active and target.role == "owner":
            owner_count = db.query(User).filter(
                User.company_id == company_id,
                User.role == "owner",
                User.is_active == True,  # noqa: E712
            ).count()

            if owner_count <= 1:
                raise ValidationError(
                    message=(
                        "Cannot deactivate the last owner"
                    ),
                    details={"field": "is_active"},
                )

        target.is_active = new_active

    target.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(target)

    logger.info(
        "team_member_updated",
        company_id=company_id,
        target_user_id=user_id,
        actor_user_id=actor.id,
        changes=list(data.keys()),
    )

    return target


def remove_team_member(
    company_id: str,
    user_id: str,
    actor: User,
    db: Session,
) -> None:
    """Soft-delete a team member (set is_active=False).

    Cannot remove the last owner.

    BC-001: Filtered by company_id.

    Args:
        company_id: The company UUID.
        user_id: The target user UUID.
        actor: The user performing the action.
        db: Database session.

    Raises:
        NotFoundError: If user not found in company.
        AuthorizationError: If actor lacks permissions.
        ValidationError: If business rules violated.
    """
    target = db.query(User).filter(
        User.id == user_id,
        User.company_id == company_id,
    ).first()

    if not target:
        raise NotFoundError(
            message="Team member not found",
            details={"user_id": user_id},
        )

    # Check permissions
    actor_level = _ROLE_HIERARCHY.get(actor.role, 0)
    if actor_level < _ROLE_HIERARCHY.get("admin", 3):
        raise AuthorizationError(
            message="Only owners and admins can remove "
                    "team members",
            details={
                "required_role": "owner or admin",
                "user_role": actor.role,
            },
        )

    # Cannot remove self
    if actor.id == target.id:
        raise ValidationError(
            message="Cannot remove yourself from the team",
        )

    # Cannot remove last owner
    if target.role == "owner":
        owner_count = db.query(User).filter(
            User.company_id == company_id,
            User.role == "owner",
            User.is_active == True,  # noqa: E712
        ).count()

        if owner_count <= 1:
            raise ValidationError(
                message="Cannot remove the last owner",
                details={"field": "role"},
            )

    target.is_active = False
    target.updated_at = datetime.utcnow()
    db.commit()

    logger.info(
        "team_member_removed",
        company_id=company_id,
        target_user_id=user_id,
        actor_user_id=actor.id,
    )
