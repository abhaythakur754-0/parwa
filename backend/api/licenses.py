"""
PARWA License Management API Routes.

Provides endpoints for license activation, validation, listing, and updates.
All endpoints require authentication and enforce tier-based access control.

Dependencies:
- backend/models/license.py (License ORM model)
- backend/models/subscription.py (Subscription ORM model)
- backend/schemas/license.py (Pydantic schemas)
- shared/core_functions/config.py (Settings)
- backend/app/database.py (Database session)
"""
import uuid
import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db
from backend.models.license import License
from backend.models.subscription import Subscription
from backend.schemas.license import (
    LicenseCreate,
    LicenseUpdate,
    LicenseResponse,
)
from shared.core_functions.logger import get_logger
from shared.core_functions.config import get_settings

logger = get_logger("licenses_api")
settings = get_settings()

router = APIRouter(prefix="/licenses", tags=["licenses"])


# Tier limits configuration
TIER_LIMITS = {
    "mini": {
        "max_calls": 2,
        "max_users": 1,
        "can_recommend": False,
        "can_execute_refunds": False,
        "agent_lightning": False,
    },
    "parwa": {
        "max_calls": 3,
        "max_users": 5,
        "can_recommend": True,
        "can_execute_refunds": False,
        "agent_lightning": True,
    },
    "parwa_high": {
        "max_calls": 5,
        "max_users": 20,
        "can_recommend": True,
        "can_execute_refunds": True,
        "agent_lightning": True,
        "video_support": True,
        "churn_prediction": True,
        "strategic_bi": True,
    },
}


def generate_license_key() -> str:
    """
    Generate a unique license key.

    Returns:
        A 32-character license key in format XXXX-XXXX-XXXX-XXXX.
    """
    import secrets
    parts = [secrets.token_hex(2).upper() for _ in range(4)]
    return "-".join(parts)


async def get_current_company_id(
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    """
    Dependency to extract and validate company ID from authentication.

    This is a placeholder that should be replaced with actual JWT validation
    when auth is fully implemented. For now, returns a test company ID.

    Args:
        db: Async database session.

    Returns:
        UUID of the authenticated user's company.

    Raises:
        HTTPException: If authentication fails.
    """
    # TODO: Replace with actual JWT token validation
    # For now, return a test company ID for development
    # This will be properly implemented in auth.py integration
    test_company_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    return test_company_id


@router.post(
    "/activate",
    response_model=LicenseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Activate a license key for a company",
)
async def activate_license(
    license_key: str,
    company_id: uuid.UUID = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
) -> LicenseResponse:
    """
    Activate a license key for a company.

    Validates the license key format, checks if it's already activated,
    and associates it with the company if valid.

    Args:
        license_key: The license key to activate.
        company_id: The company ID (from authentication).
        db: Async database session.

    Returns:
        The activated license details.

    Raises:
        HTTPException: 400 if license key format is invalid.
        HTTPException: 404 if license key not found.
        HTTPException: 409 if license already activated.
    """
    # Input validation
    if not license_key or len(license_key) < 10:
        logger.warning({
            "event": "license_activation_failed",
            "reason": "invalid_key_format",
            "company_id": str(company_id),
        })
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid license key format",
        )

    try:
        # Check if license exists
        result = await db.execute(
            select(License).where(License.license_key == license_key)
        )
        license_obj = result.scalar_one_or_none()

        if not license_obj:
            logger.warning({
                "event": "license_activation_failed",
                "reason": "key_not_found",
                "company_id": str(company_id),
            })
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="License key not found",
            )

        # Check if already activated
        if license_obj.company_id is not None:
            logger.warning({
                "event": "license_activation_failed",
                "reason": "already_activated",
                "license_id": str(license_obj.id),
                "company_id": str(company_id),
            })
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="License key already activated",
            )

        # Activate the license
        license_obj.company_id = company_id
        license_obj.status = "active"
        license_obj.issued_at = datetime.datetime.now(datetime.timezone.utc)

        await db.flush()
        await db.refresh(license_obj)

        logger.info({
            "event": "license_activated",
            "license_id": str(license_obj.id),
            "company_id": str(company_id),
            "tier": license_obj.tier,
        })

        return LicenseResponse.model_validate(license_obj)

    except HTTPException:
        raise
    except Exception as e:
        logger.error({
            "event": "license_activation_error",
            "error": str(e),
            "company_id": str(company_id),
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate license",
        )


@router.get(
    "/validate",
    response_model=dict,
    summary="Validate license status",
)
async def validate_license(
    license_key: Optional[str] = None,
    company_id: uuid.UUID = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Validate a license status.

    Checks if the license is valid, active, and not expired.
    Returns tier information and limits.

    Args:
        license_key: Optional license key to validate. If not provided,
                     validates the company's active license.
        company_id: The company ID (from authentication).
        db: Async database session.

    Returns:
        Dict with validation result, tier, and limits.

    Raises:
        HTTPException: 404 if no license found.
    """
    try:
        query = select(License).where(License.company_id == company_id)

        if license_key:
            query = query.where(License.license_key == license_key)

        result = await db.execute(query)
        license_obj = result.scalar_one_or_none()

        if not license_obj:
            logger.warning({
                "event": "license_validation_failed",
                "reason": "not_found",
                "company_id": str(company_id),
            })
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No license found for company",
            )

        # Check if license is valid
        is_valid = license_obj.is_valid()

        # Check expiry
        is_expired = False
        if license_obj.expires_at:
            is_expired = license_obj.expires_at < datetime.datetime.now(
                datetime.timezone.utc
            )

        # Get tier limits
        tier_limits = TIER_LIMITS.get(license_obj.tier, TIER_LIMITS["mini"])

        response = {
            "valid": is_valid,
            "license_id": str(license_obj.id),
            "tier": license_obj.tier,
            "status": license_obj.status,
            "expires_at": license_obj.expires_at.isoformat() if license_obj.expires_at else None,
            "is_expired": is_expired,
            "limits": tier_limits,
        }

        logger.info({
            "event": "license_validated",
            "license_id": str(license_obj.id),
            "company_id": str(company_id),
            "valid": is_valid,
            "tier": license_obj.tier,
        })

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error({
            "event": "license_validation_error",
            "error": str(e),
            "company_id": str(company_id),
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate license",
        )


@router.get(
    "/",
    response_model=List[LicenseResponse],
    summary="List all licenses for authenticated company",
)
async def list_licenses(
    company_id: uuid.UUID = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
) -> List[LicenseResponse]:
    """
    List all licenses for the authenticated company.

    Returns all licenses associated with the company, including
    active, suspended, and expired licenses.

    Args:
        company_id: The company ID (from authentication).
        db: Async database session.

    Returns:
        List of license objects.
    """
    try:
        result = await db.execute(
            select(License)
            .where(License.company_id == company_id)
            .order_by(License.created_at.desc())
        )
        licenses = result.scalars().all()

        logger.info({
            "event": "licenses_listed",
            "company_id": str(company_id),
            "count": len(licenses),
        })

        return [LicenseResponse.model_validate(lic) for lic in licenses]

    except Exception as e:
        logger.error({
            "event": "licenses_list_error",
            "error": str(e),
            "company_id": str(company_id),
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve licenses",
        )


@router.put(
    "/{license_id}",
    response_model=LicenseResponse,
    summary="Update license settings",
)
async def update_license(
    license_id: uuid.UUID,
    update_data: LicenseUpdate,
    company_id: uuid.UUID = Depends(get_current_company_id),
    db: AsyncSession = Depends(get_db),
) -> LicenseResponse:
    """
    Update license settings.

    Allows updating license tier, status, and max seats.
    Only the license owner company can update the license.

    Args:
        license_id: The UUID of the license to update.
        update_data: The fields to update.
        company_id: The company ID (from authentication).
        db: Async database session.

    Returns:
        The updated license details.

    Raises:
        HTTPException: 404 if license not found.
        HTTPException: 403 if not authorized to update.
        HTTPException: 400 if tier downgrade has active subscription.
    """
    try:
        # Find the license
        result = await db.execute(
            select(License).where(
                and_(
                    License.id == license_id,
                    License.company_id == company_id,
                )
            )
        )
        license_obj = result.scalar_one_or_none()

        if not license_obj:
            logger.warning({
                "event": "license_update_failed",
                "reason": "not_found",
                "license_id": str(license_id),
                "company_id": str(company_id),
            })
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="License not found",
            )

        # Check for tier downgrade restrictions
        if update_data.tier and update_data.tier != license_obj.tier:
            # Check if there's an active subscription at higher tier
            sub_result = await db.execute(
                select(Subscription).where(
                    and_(
                        Subscription.company_id == company_id,
                        Subscription.status == "active",
                    )
                )
            )
            active_subscription = sub_result.scalar_one_or_none()

            if active_subscription:
                logger.warning({
                    "event": "license_update_failed",
                    "reason": "active_subscription",
                    "license_id": str(license_id),
                    "company_id": str(company_id),
                })
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot change tier with active subscription. Cancel subscription first.",
                )

        # Apply updates
        update_fields = update_data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            setattr(license_obj, field, value)

        await db.flush()
        await db.refresh(license_obj)

        logger.info({
            "event": "license_updated",
            "license_id": str(license_id),
            "company_id": str(company_id),
            "updated_fields": list(update_fields.keys()),
        })

        return LicenseResponse.model_validate(license_obj)

    except HTTPException:
        raise
    except Exception as e:
        logger.error({
            "event": "license_update_error",
            "error": str(e),
            "license_id": str(license_id),
            "company_id": str(company_id),
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update license",
        )


@router.get(
    "/tier-limits/{tier}",
    response_model=dict,
    summary="Get tier limits for a specific tier",
)
async def get_tier_limits(tier: str) -> dict:
    """
    Get the limits and features for a specific tier.

    Args:
        tier: The tier name (mini, parwa, parwa_high).

    Returns:
        Dict with tier limits and features.

    Raises:
        HTTPException: 400 if tier is invalid.
    """
    if tier not in TIER_LIMITS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier: {tier}. Must be one of: mini, parwa, parwa_high",
        )

    return {
        "tier": tier,
        "limits": TIER_LIMITS[tier],
    }
