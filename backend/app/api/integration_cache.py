"""
PARWA Integration Cache API — Phase 7 Endpoints

Exposes cache operations for integration data:
- GET /integration-cache/stats/{integration_type} — Cache statistics
- POST /integration-cache/invalidate — Invalidate cache entries
- GET /integration-cache/health — Cache health for all integrations

BC-001: All endpoints are tenant-scoped via auth middleware.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from database.models.core import User
from app.services.integration_cache_service import IntegrationCacheService


router = APIRouter(prefix="/integration-cache", tags=["integration-cache"])


class CacheInvalidateRequest(BaseModel):
    """Request to invalidate cache entries."""
    integration_type: str = Field(
        ...,
        description="Integration type to invalidate (e.g. 'hubspot')"
    )
    endpoint: Optional[str] = Field(
        None,
        description="Optional specific endpoint to invalidate"
    )
    cache_key: Optional[str] = Field(
        None,
        description="Optional specific cache key to invalidate"
    )
    reason: Optional[str] = Field(
        None,
        description="Reason for invalidation (for audit log)"
    )


@router.get(
    "/stats/{integration_type}",
    summary="Get cache statistics for an integration",
)
async def get_cache_stats(
    integration_type: str,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get cache statistics for a specific integration.

    Returns count of cached entries, memory usage estimate, etc.
    """
    company_id = current_user.company_id
    service = IntegrationCacheService(company_id=company_id)

    return await service.get_cache_stats(integration_type)


@router.post(
    "/invalidate",
    summary="Invalidate integration cache",
)
async def invalidate_cache(
    data: CacheInvalidateRequest,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Invalidate cache entries for an integration.

    Can invalidate:
    - All cache for an integration (endpoint=None)
    - All cache for an endpoint (cache_key=None)
    - A specific cache entry (both provided)

    Per Phase 7: Cache invalidation on integration disconnect.
    """
    company_id = current_user.company_id
    service = IntegrationCacheService(company_id=company_id)

    result = await service.invalidate(
        integration_type=data.integration_type,
        endpoint=data.endpoint,
        cache_key=data.cache_key,
    )

    return {
        "success": result,
        "integration_type": data.integration_type,
        "endpoint": data.endpoint,
        "cache_key": data.cache_key,
    }


@router.get(
    "/health",
    summary="Cache health for all integrations",
)
async def get_cache_health(
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get cache health overview for all tenant integrations.

    Returns cache status for each connected integration.
    """
    from app.core.redis import redis_health_check

    company_id = current_user.company_id

    # Check Redis health
    redis_health = await redis_health_check()

    return {
        "company_id": company_id,
        "redis": redis_health,
        "cache_enabled": redis_health.get("status") == "healthy",
    }
