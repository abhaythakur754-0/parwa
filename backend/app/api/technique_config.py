"""
Per-Tenant Technique Configuration Admin API (SG-17)

Provides REST endpoints for managing per-tenant technique configurations:
- GET  /api/techniques/config          — list all technique configs for a tenant
- PUT  /api/techniques/config/{id}     — enable/disable a technique for a tenant
- GET  /api/techniques/config/{id}     — get config for a specific technique

BC-001: All data scoped by company_id.
BC-008: Never crashes.
"""

from __future__ import annotations

import copy
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.deps import require_roles
from app.core.technique_router import (
    TechniqueID,
    TechniqueTier,
    TECHNIQUE_REGISTRY,
)
from app.logger import get_logger

logger = get_logger("technique_config_api")


# ── Pydantic Models ────────────────────────────────────────────────


class TechniqueConfigResponse(BaseModel):
    """Response model for a single technique config."""

    technique_id: str
    technique_name: str
    tier: str
    description: str
    enabled: bool
    config_overrides: Dict[str, Any] = Field(default_factory=dict)
    updated_at: Optional[str] = None
    estimated_tokens: int = 0
    time_budget_ms: int = 0


class TechniqueConfigListResponse(BaseModel):
    """Response model for listing all technique configs."""

    company_id: str
    techniques: List[TechniqueConfigResponse]
    total: int


class UpdateTechniqueConfigRequest(BaseModel):
    """Request body for updating a technique config."""

    company_id: str = Field(..., min_length=1, description="Company ID")
    enabled: bool = Field(default=True, description="Enable/disable technique")
    config_overrides: Dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration overrides",
    )


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str
    detail: Optional[str] = None


# ── Technique Config Store ─────────────────────────────────────────


class TechniqueConfigStore:
    """
    In-memory store for per-company technique configurations.

    Structure: _configs[company_id][technique_id] = {
        enabled: bool,
        config_overrides: dict,
        updated_at: str (ISO timestamp),
    }

    BC-001: All data scoped by company_id.
    Thread-safe with threading.Lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._configs: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def get_config(
        self,
        company_id: str,
        technique_id: str,
    ) -> Dict[str, Any]:
        """
        Get configuration for a specific technique.

        Default: all techniques enabled for all companies.

        Args:
            company_id: Tenant company identifier.
            technique_id: Technique identifier.

        Returns:
            Dict with enabled, config_overrides, updated_at keys.
        """
        try:
            with self._lock:
                company_configs = self._configs.get(company_id, {})
                config = company_configs.get(
                    technique_id,
                    {
                        "enabled": True,
                        "config_overrides": {},
                        "updated_at": None,
                    },
                )
                return copy.deepcopy(config)
        except Exception:
            # BC-008: never crash
            return {
                "enabled": True,
                "config_overrides": {},
                "updated_at": None,
            }

    def set_config(
        self,
        company_id: str,
        technique_id: str,
        enabled: bool,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Set configuration for a specific technique.

        Args:
            company_id: Tenant company identifier.
            technique_id: Technique identifier.
            enabled: Whether the technique is enabled.
            overrides: Optional configuration overrides dict.

        Returns:
            Updated config dict.
        """
        try:
            now = datetime.now(timezone.utc).isoformat()
            config = {
                "enabled": enabled,
                "config_overrides": overrides if overrides is not None else {},
                "updated_at": now,
            }

            with self._lock:
                if company_id not in self._configs:
                    self._configs[company_id] = {}
                self._configs[company_id][technique_id] = config

            return config
        except Exception:
            # BC-008: never crash
            return {
                "enabled": enabled,
                "config_overrides": overrides if overrides is not None else {},
                "updated_at": None,
            }

    def list_configs(self, company_id: str) -> List[Dict[str, Any]]:
        """
        List all technique configurations for a company.

        Includes all techniques from TECHNIQUE_REGISTRY, with
        stored overrides applied where they exist.

        Args:
            company_id: Tenant company identifier.

        Returns:
            List of config dicts with technique_id, enabled,
            config_overrides, updated_at.
        """
        try:
            with self._lock:
                company_configs = self._configs.get(
                    company_id,
                    {},
                )

            result = []
            for tid, info in TECHNIQUE_REGISTRY.items():
                stored = company_configs.get(tid.value, {})
                result.append(
                    {
                        "technique_id": tid.value,
                        "technique_name": tid.name,
                        "tier": info.tier.value,
                        "description": info.description,
                        "enabled": stored.get("enabled", True),
                        "config_overrides": stored.get(
                            "config_overrides",
                            {},
                        ),
                        "updated_at": stored.get("updated_at"),
                        "estimated_tokens": info.estimated_tokens,
                        "time_budget_ms": info.time_budget_ms,
                    }
                )

            return result
        except Exception:
            # BC-008: never crash
            return []

    def reset_company(self, company_id: str) -> None:
        """
        Remove all configurations for a company.

        Args:
            company_id: Tenant company identifier.
        """
        try:
            with self._lock:
                self._configs.pop(company_id, None)
        except Exception:
            # BC-008: never crash
            pass


# ── Global Store Instance ──────────────────────────────────────────

_config_store = TechniqueConfigStore()


def get_config_store() -> TechniqueConfigStore:
    """Get the global TechniqueConfigStore instance."""
    return _config_store


# ── FastAPI Router ─────────────────────────────────────────────────

router = APIRouter(
    prefix="/api/techniques/config",
    tags=["Technique Config"],
    dependencies=[Depends(require_roles("owner", "admin"))],
)


def _build_response(
    technique_id: str,
    info: Any,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a TechniqueConfigResponse dict from registry + stored config."""
    return TechniqueConfigResponse(
        technique_id=technique_id,
        technique_name=getattr(
            TechniqueID(technique_id),
            "name",
            technique_id,
        ),
        tier=info.tier.value,
        description=info.description,
        enabled=config.get("enabled", True),
        config_overrides=config.get("config_overrides", {}),
        updated_at=config.get("updated_at"),
        estimated_tokens=info.estimated_tokens,
        time_budget_ms=info.time_budget_ms,
    ).model_dump()


@router.get(
    "",
    response_model=TechniqueConfigListResponse,
    responses={400: {"model": ErrorResponse}},
)
async def list_technique_configs(
    company_id: str = Query(
        ...,
        min_length=1,
        description="Company ID (required)",
    ),
    variant_type: Optional[str] = Query(
        None,
        description="Filter by tier (tier_1, tier_2, tier_3)",
    ),
):
    """
    List all technique configurations for a tenant.

    Query params:
    - company_id (required): Tenant company identifier
    - variant_type (optional): Filter by tier (tier_1, tier_2, tier_3)

    Returns all techniques from TECHNIQUE_REGISTRY with their
    enabled/disabled status and any per-tenant overrides.
    """
    try:
        store = get_config_store()
        all_configs = store.list_configs(company_id)

        # Filter by tier if requested
        if variant_type is not None:
            valid_tiers = {t.value for t in TechniqueTier}
            if variant_type not in valid_tiers:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "Invalid variant_type",
                        "detail": f"Must be one of {valid_tiers}",
                    },
                )
            all_configs = [c for c in all_configs if c["tier"] == variant_type]

        technique_responses = [
            TechniqueConfigResponse(**c).model_dump() for c in all_configs
        ]

        # Return plain dict to avoid Pydantic class identity issues
        return {
            "company_id": company_id,
            "techniques": technique_responses,
            "total": len(technique_responses),
        }
    except Exception as exc:
        logger.error(
            "list_technique_configs_error",
            error=str(exc),
        )
        return ErrorResponse(
            error="Internal error",
            detail=str(exc),
        )


@router.put(
    "/{technique_id}",
    response_model=TechniqueConfigResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def update_technique_config(
    technique_id: str,
    body: UpdateTechniqueConfigRequest,
):
    """
    Enable/disable a technique for a tenant.

    Body:
    - company_id (required): Tenant company identifier
    - enabled: Whether the technique is enabled
    - config_overrides: Optional configuration overrides

    Validates:
    - technique_id exists in TECHNIQUE_REGISTRY
    - company_id is not empty
    - BC-009: Tier 1 techniques cannot be disabled
    """
    try:
        # Validate technique_id exists
        if technique_id not in {t.value for t in TechniqueID}:
            return JSONResponse(
                status_code=404,
                content={
                    "error": "Invalid technique_id",
                    "detail": (
                        f"Technique '{technique_id}' not found "
                        "in TECHNIQUE_REGISTRY. "
                        "Valid: "
                        f"{[t.value for t in TechniqueID]}"
                    ),
                },
            )

        # BC-009: Tier 1 techniques cannot be disabled
        info = TECHNIQUE_REGISTRY[TechniqueID(technique_id)]
        if info.tier == TechniqueTier.TIER_1 and not body.enabled:
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Tier 1 techniques cannot be disabled",
                    "detail": (
                        f"Technique '{technique_id}' is Tier 1 (always-active) "
                        "and cannot be disabled. Tier 1 techniques are: "
                        f"{[t.value for t in TechniqueID if TECHNIQUE_REGISTRY[t].tier == TechniqueTier.TIER_1]}"
                    ),
                },
            )

        # Validate company_id
        if not body.company_id or not body.company_id.strip():
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Invalid company_id",
                    "detail": "company_id must not be empty",
                },
            )

        store = get_config_store()
        config = store.set_config(
            company_id=body.company_id,
            technique_id=technique_id,
            enabled=body.enabled,
            overrides=body.config_overrides,
        )

        info = TECHNIQUE_REGISTRY[TechniqueID(technique_id)]
        return _build_response(technique_id, info, config)

    except Exception as exc:
        logger.error(
            "update_technique_config_error",
            technique_id=technique_id,
            error=str(exc),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal error",
                "detail": str(exc),
            },
        )


@router.get(
    "/{technique_id}",
    response_model=TechniqueConfigResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def get_technique_config(
    technique_id: str,
    company_id: str = Query(
        ...,
        min_length=1,
        description="Company ID (required)",
    ),
):
    """
    Get configuration for a specific technique.

    Query params:
    - company_id (required): Tenant company identifier

    Returns the technique config with current settings and overrides.
    """
    try:
        # Validate technique_id exists
        if technique_id not in {t.value for t in TechniqueID}:
            return JSONResponse(
                status_code=404,
                content={
                    "error": "Invalid technique_id",
                    "detail": (
                        f"Technique '{technique_id}' not found "
                        "in TECHNIQUE_REGISTRY. "
                        "Valid: "
                        f"{[t.value for t in TechniqueID]}"
                    ),
                },
            )

        # Validate company_id
        if not company_id or not company_id.strip():
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Invalid company_id",
                    "detail": "company_id must not be empty",
                },
            )

        store = get_config_store()
        config = store.get_config(
            company_id=company_id,
            technique_id=technique_id,
        )

        info = TECHNIQUE_REGISTRY[TechniqueID(technique_id)]
        return _build_response(technique_id, info, config)

    except Exception as exc:
        logger.error(
            "get_technique_config_error",
            technique_id=technique_id,
            error=str(exc),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal error",
                "detail": str(exc),
            },
        )
