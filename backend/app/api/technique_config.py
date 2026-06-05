"""
Per-Tenant Technique Configuration Admin API (SG-17)

Provides REST endpoints for managing per-tenant technique configurations:
- GET  /api/techniques/config          — list all technique configs for a tenant
- PUT  /api/techniques/config/{id}     — enable/disable a technique for a tenant
- GET  /api/techniques/config/{id}     — get config for a specific technique
- GET  /api/techniques/config/prompts              — list available prompt templates
- GET  /api/techniques/config/prompts/{name}       — get template by name
- POST /api/techniques/config/prompts/render       — render a template with variables

BC-001: All data scoped by company_id.
BC-008: Never crashes.
"""

from __future__ import annotations

import copy
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.technique_router import (
    TechniqueID,
    TechniqueTier,
    TECHNIQUE_REGISTRY,
)
from app.logger import get_logger

logger = get_logger("technique_config_api")


# ── Prompt Template Service Singleton ──────────────────────────────

_prompt_template_service = None


def _get_prompt_template_service():
    """Lazy-load PromptTemplateService (BC-008: never crash)."""
    global _prompt_template_service
    if _prompt_template_service is None:
        try:
            from app.services.prompt_template_service import PromptTemplateService
            _prompt_template_service = PromptTemplateService()
        except Exception as exc:
            logger.error(
                "prompt_template_service_init_failed",
                error=str(exc),
            )
            _prompt_template_service = None
    return _prompt_template_service


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


class PromptTemplateResponse(BaseModel):
    """Response model for a single prompt template."""

    id: str
    name: str
    category: str
    description: str
    variables: List[str]
    version: int
    status: str
    is_default: bool
    variant_type: Optional[str] = None
    feature_id: Optional[str] = None
    usage_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PromptTemplateListResponse(BaseModel):
    """Response model for listing prompt templates."""

    company_id: str
    templates: List[PromptTemplateResponse]
    total: int


class RenderPromptRequest(BaseModel):
    """Request body for rendering a prompt template."""

    company_id: str = Field(..., min_length=1, description="Company ID")
    template_name: str = Field(..., min_length=1, description="Template name to render")
    variables: Dict[str, str] = Field(
        default_factory=dict,
        description="Variable name → value mapping for template rendering",
    )
    variant_type: Optional[str] = Field(
        None,
        description="Variant type filter (mini_parwa, parwa, parwa_high)",
    )
    version: Optional[int] = Field(
        None,
        description="Specific template version (None = latest)",
    )


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
        self, company_id: str, technique_id: str,
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
                "config_overrides": overrides
                if overrides is not None
                else {},
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
                "config_overrides": overrides
                if overrides is not None
                else {},
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
                    company_id, {},
                )

            result = []
            for tid, info in TECHNIQUE_REGISTRY.items():
                stored = company_configs.get(tid.value, {})
                result.append({
                    "technique_id": tid.value,
                    "technique_name": tid.name,
                    "tier": info.tier.value,
                    "description": info.description,
                    "enabled": stored.get("enabled", True),
                    "config_overrides": stored.get(
                        "config_overrides", {},
                    ),
                    "updated_at": stored.get("updated_at"),
                    "estimated_tokens": info.estimated_tokens,
                    "time_budget_ms": info.time_budget_ms,
                })

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
            TechniqueID(technique_id), "name", technique_id,
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
    "/prompts",
    response_model=PromptTemplateListResponse,
    responses={400: {"model": ErrorResponse}},
)
async def list_prompt_templates(
    company_id: str = Query(
        ...,
        min_length=1,
        description="Company ID (required)",
    ),
    category: Optional[str] = Query(
        None,
        description="Filter by template category (system_prompt, technique_prompt, guardrail_prompt, classification, response_generation, summarization, rag_context, custom)",
    ),
    status: Optional[str] = Query(
        None,
        description="Filter by status (draft, active, archived, deprecated)",
    ),
    variant_type: Optional[str] = Query(
        None,
        description="Filter by variant type (mini_parwa, parwa, parwa_high)",
    ),
):
    """
    List all prompt templates available to a tenant.

    Query params:
    - company_id (required): Tenant company identifier
    - category (optional): Filter by template category
    - status (optional): Filter by template status
    - variant_type (optional): Filter by variant association

    Returns company-specific templates and built-in defaults.
    Uses PromptTemplateService for template resolution.
    """
    try:
        service = _get_prompt_template_service()

        if service is None:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service unavailable",
                    "detail": "PromptTemplateService failed to initialize",
                },
            )

        templates = service.list_templates(
            company_id=company_id,
            category=category,
            status=status,
            variant_type=variant_type,
        )

        template_responses = [
            PromptTemplateResponse(
                id=t.id,
                name=t.name,
                category=t.category,
                description=t.description,
                variables=t.variables,
                version=t.version,
                status=t.status,
                is_default=t.is_default,
                variant_type=t.variant_type,
                feature_id=t.feature_id,
                usage_count=t.usage_count,
                created_at=t.created_at,
                updated_at=t.updated_at,
            ).model_dump()
            for t in templates
        ]

        return {
            "company_id": company_id,
            "templates": template_responses,
            "total": len(template_responses),
        }
    except Exception as exc:
        logger.error(
            "list_prompt_templates_error",
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
    "/prompts/{template_name}",
    responses={
        200: {"model": PromptTemplateResponse},
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def get_prompt_template(
    template_name: str,
    company_id: str = Query(
        ...,
        min_length=1,
        description="Company ID (required)",
    ),
    variant_type: Optional[str] = Query(
        None,
        description="Variant type filter (mini_parwa, parwa, parwa_high)",
    ),
    version: Optional[int] = Query(
        None,
        description="Specific template version (None = latest)",
    ),
):
    """
    Get a specific prompt template by name.

    Path params:
    - template_name: Name of the template (e.g. 'customer_support_system')

    Query params:
    - company_id (required): Tenant company identifier
    - variant_type (optional): Variant filter for override resolution
    - version (optional): Specific version number

    Resolution order: variant override → company custom → built-in default.
    """
    try:
        service = _get_prompt_template_service()

        if service is None:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service unavailable",
                    "detail": "PromptTemplateService failed to initialize",
                },
            )

        template = service.get_template(
            company_id=company_id,
            name=template_name,
            variant_type=variant_type,
            version=version,
        )

        return PromptTemplateResponse(
            id=template.id,
            name=template.name,
            category=template.category,
            description=template.description,
            variables=template.variables,
            version=template.version,
            status=template.status,
            is_default=template.is_default,
            variant_type=template.variant_type,
            feature_id=template.feature_id,
            usage_count=template.usage_count,
            created_at=template.created_at,
            updated_at=template.updated_at,
        ).model_dump()

    except Exception as exc:
        error_msg = str(exc)
        if "not found" in error_msg.lower():
            return JSONResponse(
                status_code=404,
                content={
                    "error": "Template not found",
                    "detail": error_msg,
                },
            )
        logger.error(
            "get_prompt_template_error",
            template_name=template_name,
            error=error_msg,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal error",
                "detail": error_msg,
            },
        )


@router.post(
    "/prompts/render",
    responses={
        200: {},
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def render_prompt_template(
    body: RenderPromptRequest,
):
    """
    Render a prompt template by substituting {{variables}}.

    Body:
    - company_id (required): Tenant company identifier
    - template_name (required): Name of the template to render
    - variables: Mapping of variable name → value
    - variant_type (optional): Variant filter for override resolution
    - version (optional): Specific version number

    Returns the rendered content with all {{var}} placeholders substituted.
    Missing variables are left as-is (BC-008 graceful degradation).
    """
    try:
        service = _get_prompt_template_service()

        if service is None:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service unavailable",
                    "detail": "PromptTemplateService failed to initialize",
                },
            )

        result = service.render_template(
            company_id=body.company_id,
            name=body.template_name,
            variables=body.variables,
            variant_type=body.variant_type,
            version=body.version,
        )

        return {
            "template_id": result.template_id,
            "template_name": result.template_name,
            "rendered_content": result.rendered_content,
            "variables_used": result.variables_used,
            "version": result.version,
            "rendered_at": result.rendered_at,
        }

    except Exception as exc:
        error_msg = str(exc)
        if "not found" in error_msg.lower():
            return JSONResponse(
                status_code=404,
                content={
                    "error": "Template not found",
                    "detail": error_msg,
                },
            )
        logger.error(
            "render_prompt_template_error",
            template_name=body.template_name,
            error=error_msg,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal error",
                "detail": error_msg,
            },
        )


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
            all_configs = [
                c for c in all_configs
                if c["tier"] == variant_type
            ]

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
        if technique_id not in {
            t.value for t in TechniqueID
        }:
            return JSONResponse(
                status_code=404,
                content={
                    "error": "Invalid technique_id",
                    "detail": (
                        f"Technique '{technique_id}' not found "
                        f"in TECHNIQUE_REGISTRY. "
                        f"Valid: "
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
                        f"and cannot be disabled. Tier 1 techniques are: "
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
        if technique_id not in {
            t.value for t in TechniqueID
        }:
            return JSONResponse(
                status_code=404,
                content={
                    "error": "Invalid technique_id",
                    "detail": (
                        f"Technique '{technique_id}' not found "
                        f"in TECHNIQUE_REGISTRY. "
                        f"Valid: "
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
