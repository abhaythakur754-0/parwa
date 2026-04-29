"""
PARWA Auto-Response Generation API (Week 9, Day 8)

REST endpoints for AI-powered response generation, brand voice management,
response templates, token budgeting, AI ticket assignment, and rule-to-AI
migration toggles.

Endpoints:
  Response Generation:
    POST   /api/response/generate          — Generate auto-response
    POST   /api/response/generate/batch    — Batch generate responses

  Token Budget (F-156):
    GET    /api/response/budget/{id}                  — Budget status
    POST   /api/response/budget/{id}/initialize       — Initialize budget
    POST   /api/response/budget/{id}/check            — Check overflow

  Response Templates (F-155):
    POST   /api/response/templates                    — Create template
    GET    /api/response/templates                    — List templates
    GET    /api/response/templates/{id}               — Get template
    PUT    /api/response/templates/{id}               — Update template
    DELETE /api/response/templates/{id}               — Delete template
    POST   /api/response/templates/{id}/render        — Render template

  Brand Voice (F-154):
    GET    /api/brand-voice               — Get brand voice config
    POST   /api/brand-voice               — Create/update brand voice config
    DELETE /api/brand-voice               — Delete brand voice config
    POST   /api/brand-voice/check-prohibited  — Check prohibited words
    POST   /api/brand-voice/validate          — Validate response vs brand voice

  AI Assignment:
    POST   /api/assignment/ai             — AI ticket assignment
    GET    /api/assignment/agents         — Agent workload

  Migration (F-158):
    POST   /api/migration/status          — Migration status
    POST   /api/migration/toggle          — Enable/disable AI feature

BC-001: All operations scoped to company_id.
BC-008: try/except on every endpoint — never crash.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import (
    get_company_id,
    get_current_user,
    require_roles,
)
from app.exceptions import (
    NotFoundError,
    ValidationError,
)
from app.logger import get_logger
from database.models.core import User

logger = get_logger("response_api")


# ═══════════════════════════════════════════════════════════════════
# PYDANTIC SCHEMAS
# ═══════════════════════════════════════════════════════════════════


# ── Response Generation ──────────────────────────────────────────


class ResponseGenerationRequestSchema(BaseModel):
    """Schema for single response generation."""

    query: str = Field(..., min_length=1, description="Customer query text")
    conversation_id: str = Field(..., description="Conversation identifier")
    variant_type: str = Field(
        default="parwa",
        description="One of: mini_parwa, parwa, high_parwa",
    )
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    conversation_history: Optional[List[dict]] = Field(
        None,
        description="Prior messages in the conversation",
    )
    customer_metadata: Optional[dict] = Field(
        None,
        description="Extra customer context",
    )
    language: str = Field(default="en", description="Response language code")
    force_template_response: bool = Field(
        default=False,
        description="Force template-based response",
    )


class BatchGenerationItemSchema(BaseModel):
    """Single item in a batch generation request."""

    query: str = Field(..., min_length=1)
    conversation_id: str = Field(...)
    variant_type: str = Field(default="parwa")
    customer_id: Optional[str] = None
    conversation_history: Optional[List[dict]] = None
    customer_metadata: Optional[dict] = None
    language: str = Field(default="en")


class BatchGenerationRequestSchema(BaseModel):
    """Schema for batch response generation."""

    items: List[BatchGenerationItemSchema] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="List of generation requests (max 20)",
    )


# ── Token Budget ────────────────────────────────────────────────


class BudgetInitSchema(BaseModel):
    """Schema for initializing a token budget."""

    variant_type: str = Field(
        default="parwa",
        description="One of: mini_parwa, parwa, high_parwa",
    )


class OverflowCheckSchema(BaseModel):
    """Schema for checking token overflow."""

    estimated_tokens: int = Field(
        ...,
        gt=0,
        description="Estimated tokens for the next message",
    )


# ── Brand Voice ─────────────────────────────────────────────────


class BrandVoiceConfigSchema(BaseModel):
    """Schema for creating / updating brand voice config."""

    tone: str = Field(
        default="professional",
        description="professional | friendly | casual | empathetic | authoritative",
    )
    formality_level: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Formality from 0.0 (informal) to 1.0 (formal)",
    )
    prohibited_words: List[str] = Field(
        default_factory=list,
        description="Words banned from AI responses",
    )
    response_length_preference: str = Field(
        default="standard",
        description="concise | standard | detailed",
    )
    max_response_sentences: int = Field(
        default=10,
        ge=1,
        le=50,
    )
    min_response_sentences: int = Field(
        default=1,
        ge=1,
    )
    greeting_template: Optional[str] = Field(None)
    closing_template: Optional[str] = Field(None)
    emoji_usage: str = Field(
        default="minimal",
        description="none | minimal | moderate | liberal",
    )
    apology_style: str = Field(
        default="solution-focused",
        description="formal | empathetic | solution-focused",
    )
    escalation_tone: str = Field(
        default="calm",
        description="urgent | calm | reassuring",
    )
    brand_name: str = Field(default="PARWA")
    industry: str = Field(
        default="tech",
        description="tech | ecommerce | finance | education | legal | hospitality",
    )
    custom_instructions: Optional[str] = Field(None)


class BrandVoiceCheckProhibitedSchema(BaseModel):
    """Schema for checking text against prohibited words."""

    text: str = Field(..., min_length=1, description="Text to check")


class BrandVoiceValidateSchema(BaseModel):
    """Schema for validating a response against brand voice."""

    response_text: str = Field(
        ...,
        min_length=1,
        description="The response to validate",
    )
    sentiment_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Customer sentiment context",
    )


# ── Response Templates ──────────────────────────────────────────


class TemplateCreateSchema(BaseModel):
    """Schema for creating a response template."""

    name: str = Field(..., min_length=1, max_length=255)
    category: str = Field(
        ...,
        description="greeting | farewell | apology | escalation | refund | technical | billing | general | custom",
    )
    intent_types: List[str] = Field(default_factory=list)
    subject_template: str = Field(default="")
    body_template: str = Field(default="")
    language: str = Field(default="en")
    is_active: bool = Field(default=True)


class TemplateUpdateSchema(BaseModel):
    """Schema for updating a response template."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[str] = None
    intent_types: Optional[List[str]] = None
    subject_template: Optional[str] = None
    body_template: Optional[str] = None
    language: Optional[str] = None
    is_active: Optional[bool] = None


class TemplateRenderSchema(BaseModel):
    """Schema for rendering a template with variables."""

    variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value pairs to substitute into {{variable}} placeholders",
    )
    content_type: str = Field(
        default="text",
        description="text (auto-escape) or html (whitelist sanitise)",
    )


# ── AI Assignment ───────────────────────────────────────────────


class AIAssignmentRequestSchema(BaseModel):
    """Schema for AI-powered ticket assignment."""

    ticket_id: str = Field(..., description="Ticket to assign")
    variant_type: str = Field(default="parwa")
    intent_type: str = Field(default="general")
    priority: str = Field(default="medium", description="low | medium | high | urgent")
    sentiment_score: float = Field(default=0.5, ge=0.0, le=1.0)
    customer_tier: str = Field(default="basic", description="basic | pro | enterprise")
    conversation_history: Optional[List[dict]] = None
    skills_required: Optional[List[str]] = None
    max_candidates: int = Field(default=5, ge=1, le=20)


# ── Migration ───────────────────────────────────────────────────


class MigrationStatusSchema(BaseModel):
    """Schema for getting migration status."""

    feature: Optional[str] = Field(
        None,
        description="Optional: specific feature to check (classification | assignment)",
    )


class MigrationToggleSchema(BaseModel):
    """Schema for toggling AI features."""

    feature: str = Field(
        ...,
        description="classification | assignment",
    )
    enabled: bool = Field(..., description="Enable or disable the AI feature")
    mode: str = Field(
        default="shadow",
        description="Migration mode: static | shadow | canary | gradual | active",
    )
    percentage: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Traffic percentage for AI (canary/gradual modes)",
    )


# ═══════════════════════════════════════════════════════════════════
# SUB-ROUTERS
# ═══════════════════════════════════════════════════════════════════

# ── Response Generation & Budget Router ──────────────────────────

response_router = APIRouter(
    prefix="/api/response",
    tags=["response"],
)

# ── Brand Voice Router ──────────────────────────────────────────

brand_voice_router = APIRouter(
    prefix="/api/brand-voice",
    tags=["brand-voice"],
)

# ── AI Assignment Router ────────────────────────────────────────

assignment_router = APIRouter(
    prefix="/api/assignment",
    tags=["assignment"],
)

# ── Migration Router ────────────────────────────────────────────

migration_router = APIRouter(
    prefix="/api/migration",
    tags=["migration"],
)


# ═══════════════════════════════════════════════════════════════════
# 1. RESPONSE GENERATION
# ═══════════════════════════════════════════════════════════════════


@response_router.post("/generate", summary="Generate auto-response")
async def generate_response(
    request: ResponseGenerationRequestSchema,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Generate an AI-powered response for a customer query.

    Combines sentiment analysis, RAG retrieval, brand voice, and CLARA
    quality gate to produce a high-quality, brand-consistent response.
    """
    try:
        from app.core.response_generator import (
            ResponseGenerator,
            ResponseGenerationRequest,
        )

        generator = ResponseGenerator()
        req = ResponseGenerationRequest(
            query=request.query,
            company_id=company_id,
            conversation_id=request.conversation_id,
            variant_type=request.variant_type,
            customer_id=request.customer_id,
            conversation_history=request.conversation_history,
            customer_metadata=request.customer_metadata,
            language=request.language,
        )
        result = await generator.generate(req)
        return {
            "status": "ok",
            "data": result.to_dict() if hasattr(result, "to_dict") else asdict(result),
        }

    except (ValidationError, NotFoundError) as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.to_dict(),
        )
    except Exception as exc:
        logger.error(
            "response_generate_failed",
            extra={"company_id": company_id, "error": str(exc)},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to generate response")


@response_router.post("/generate/batch", summary="Batch generate responses")
async def generate_batch_responses(
    request: BatchGenerationRequestSchema,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Generate responses for multiple tickets at once.

    Processes up to 20 items concurrently. Each item gets its own
    sentiment analysis, RAG retrieval, and CLARA quality gate.
    Returns an array of results (including partial failures).
    """
    try:
        from app.core.response_generator import (
            ResponseGenerator,
            ResponseGenerationRequest,
        )

        generator = ResponseGenerator()
        results: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        for idx, item in enumerate(request.items):
            try:
                req = ResponseGenerationRequest(
                    query=item.query,
                    company_id=company_id,
                    conversation_id=item.conversation_id,
                    variant_type=item.variant_type,
                    customer_id=item.customer_id,
                    conversation_history=item.conversation_history,
                    customer_metadata=item.customer_metadata,
                    language=item.language,
                )
                result = await generator.generate(req)
                results.append(
                    {
                        "index": idx,
                        "conversation_id": item.conversation_id,
                        "data": (
                            result.to_dict()
                            if hasattr(result, "to_dict")
                            else asdict(result)
                        ),
                    }
                )
            except Exception as item_exc:
                logger.warning(
                    "batch_item_failed",
                    extra={
                        "index": idx,
                        "conversation_id": item.conversation_id,
                        "error": str(item_exc),
                    },
                )
                errors.append(
                    {
                        "index": idx,
                        "conversation_id": item.conversation_id,
                        "error": str(item_exc),
                    }
                )

        return {
            "status": "ok" if not errors else "partial",
            "data": {
                "total": len(request.items),
                "succeeded": len(results),
                "failed": len(errors),
                "results": results,
                "errors": errors if errors else None,
            },
        }

    except Exception as exc:
        logger.error(
            "batch_generate_failed",
            extra={"company_id": company_id, "error": str(exc)},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Batch generation failed")


# ═══════════════════════════════════════════════════════════════════
# 2. TOKEN BUDGET (F-156)
# ═══════════════════════════════════════════════════════════════════


@response_router.get(
    "/budget/{conversation_id}",
    summary="Get token budget status",
)
async def get_token_budget(
    conversation_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get current token budget status for a conversation.

    Returns usage stats, remaining capacity, percentage used, and a
    warning level (normal / warning / critical / exhausted).
    """
    try:
        from app.services.token_budget_service import TokenBudgetService

        service = TokenBudgetService()
        status = await service.get_budget_status(conversation_id)
        return {"status": "ok", "data": asdict(status)}

    except Exception as exc:
        logger.error(
            "token_budget_status_failed",
            extra={
                "conversation_id": conversation_id,
                "company_id": company_id,
                "error": str(exc),
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to get budget status")


@response_router.post(
    "/budget/{conversation_id}/initialize",
    summary="Initialize token budget",
)
async def initialize_budget(
    conversation_id: str,
    request: BudgetInitSchema,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Initialize token budget for a conversation.

    Sets max tokens based on variant type and resets used/reserved
    counters. Idempotent — safe to call multiple times.
    """
    try:
        from app.services.token_budget_service import TokenBudgetService

        service = TokenBudgetService()
        budget = await service.initialize_budget(
            conversation_id,
            company_id,
            request.variant_type,
        )
        return {"status": "ok", "data": asdict(budget)}

    except Exception as exc:
        logger.error(
            "token_budget_init_failed",
            extra={
                "conversation_id": conversation_id,
                "company_id": company_id,
                "error": str(exc),
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to initialize budget")


@response_router.post(
    "/budget/{conversation_id}/check",
    summary="Check token overflow",
)
async def check_overflow(
    conversation_id: str,
    request: OverflowCheckSchema,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Check if estimated tokens would overflow the budget.

    Returns whether the tokens can fit, remaining capacity,
    overflow amount, and whether truncation is needed.
    """
    try:
        from app.services.token_budget_service import TokenBudgetService

        service = TokenBudgetService()
        result = await service.check_overflow(
            conversation_id,
            request.estimated_tokens,
        )
        return {"status": "ok", "data": asdict(result)}

    except Exception as exc:
        logger.error(
            "overflow_check_failed",
            extra={
                "conversation_id": conversation_id,
                "company_id": company_id,
                "error": str(exc),
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Overflow check failed")


# ═══════════════════════════════════════════════════════════════════
# 3. RESPONSE TEMPLATES (F-155)
# ═══════════════════════════════════════════════════════════════════


@response_router.post("/templates", summary="Create response template", status_code=201)
async def create_template(
    request: TemplateCreateSchema,
    company_id: str = Depends(get_company_id),
    user: User = Depends(require_roles("owner", "admin")),
) -> Dict[str, Any]:
    """Create a new response template.

    Supports {{variable}} placeholders in subject and body.
    """
    try:
        from app.services.response_template_service import ResponseTemplateService

        service = ResponseTemplateService()
        template = await service.create_template(
            company_id=company_id,
            template_data=request.model_dump(),
        )
        return {
            "status": "ok",
            "data": (
                template.to_dict() if hasattr(template, "to_dict") else asdict(template)
            ),
        }

    except (ValidationError, NotFoundError) as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.to_dict(),
        )
    except Exception as exc:
        logger.error(
            "template_create_failed",
            extra={"company_id": company_id, "error": str(exc)},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to create template")


@response_router.get("/templates", summary="List response templates")
async def list_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    language: Optional[str] = Query(None, description="Filter by language"),
    active_only: bool = Query(True, description="Only return active templates"),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """List response templates for the authenticated company.

    Supports optional filters for category and language.
    """
    try:
        from app.services.response_template_service import ResponseTemplateService

        service = ResponseTemplateService()
        templates = await service.list_templates(
            company_id=company_id,
            category=category,
            language=language,
            active_only=active_only,
        )
        return {
            "status": "ok",
            "data": {
                "items": [
                    t.to_dict() if hasattr(t, "to_dict") else asdict(t)
                    for t in templates
                ],
                "total": len(templates),
            },
        }

    except Exception as exc:
        logger.error(
            "template_list_failed",
            extra={"company_id": company_id, "error": str(exc)},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to list templates")


@response_router.get("/templates/{template_id}", summary="Get response template")
async def get_template(
    template_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get a single response template by ID."""
    try:
        from app.services.response_template_service import ResponseTemplateService

        service = ResponseTemplateService()
        template = await service.get_template(template_id, company_id)
        return {
            "status": "ok",
            "data": (
                template.to_dict() if hasattr(template, "to_dict") else asdict(template)
            ),
        }

    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.to_dict())
    except Exception as exc:
        logger.error(
            "template_get_failed",
            extra={
                "template_id": template_id,
                "company_id": company_id,
                "error": str(exc),
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to get template")


@response_router.put("/templates/{template_id}", summary="Update response template")
async def update_template(
    template_id: str,
    request: TemplateUpdateSchema,
    company_id: str = Depends(get_company_id),
    user: User = Depends(require_roles("owner", "admin")),
) -> Dict[str, Any]:
    """Update an existing response template.

    Only provided fields are updated; omitted fields retain their
    current values.
    """
    try:
        from app.services.response_template_service import ResponseTemplateService

        service = ResponseTemplateService()
        updates = request.model_dump(exclude_unset=True)
        template = await service.update_template(
            template_id,
            company_id,
            updates,
        )
        return {
            "status": "ok",
            "data": (
                template.to_dict() if hasattr(template, "to_dict") else asdict(template)
            ),
        }

    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.to_dict())
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.to_dict())
    except Exception as exc:
        logger.error(
            "template_update_failed",
            extra={
                "template_id": template_id,
                "company_id": company_id,
                "error": str(exc),
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to update template")


@response_router.delete("/templates/{template_id}", summary="Delete response template")
async def delete_template(
    template_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(require_roles("owner", "admin")),
) -> Dict[str, Any]:
    """Delete a response template."""
    try:
        from app.services.response_template_service import ResponseTemplateService

        service = ResponseTemplateService()
        deleted = await service.delete_template(template_id, company_id)
        return {
            "status": "ok",
            "data": {"deleted": deleted, "template_id": template_id},
        }

    except Exception as exc:
        logger.error(
            "template_delete_failed",
            extra={
                "template_id": template_id,
                "company_id": company_id,
                "error": str(exc),
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to delete template")


@response_router.post(
    "/templates/{template_id}/render",
    summary="Render template with variables",
)
async def render_template(
    template_id: str,
    request: TemplateRenderSchema,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Render a template by substituting {{variable}} placeholders.

    All variable values are sanitised to prevent XSS injection
    (GAP-010 FIX).
    """
    try:
        from app.services.response_template_service import ResponseTemplateService

        service = ResponseTemplateService()
        rendered = await service.render_template(
            template_id=template_id,
            company_id=company_id,
            variables=request.variables,
            content_type=request.content_type,
        )
        return {
            "status": "ok",
            "data": {
                "template_id": template_id,
                "rendered": rendered,
            },
        }

    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.to_dict())
    except Exception as exc:
        logger.error(
            "template_render_failed",
            extra={
                "template_id": template_id,
                "company_id": company_id,
                "error": str(exc),
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to render template")


# ═══════════════════════════════════════════════════════════════════
# 4. BRAND VOICE (F-154)
# ═══════════════════════════════════════════════════════════════════


@brand_voice_router.get("", summary="Get brand voice config")
async def get_brand_voice(
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get the current brand voice configuration for the company.

    Returns defaults if no config has been set yet.
    """
    try:
        from app.services.brand_voice_service import BrandVoiceService

        service = BrandVoiceService()
        config = await service.get_config(company_id)
        return {
            "status": "ok",
            "data": (
                asdict(config) if hasattr(config, "__dataclass_fields__") else config
            ),
        }

    except (ValidationError, NotFoundError) as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.to_dict(),
        )
    except Exception as exc:
        logger.error(
            "brand_voice_get_failed",
            extra={"company_id": company_id, "error": str(exc)},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to get brand voice config")


@brand_voice_router.post("", summary="Create or update brand voice config")
async def upsert_brand_voice(
    request: BrandVoiceConfigSchema,
    company_id: str = Depends(get_company_id),
    user: User = Depends(require_roles("owner", "admin")),
) -> Dict[str, Any]:
    """Create or update the brand voice configuration for the company.

    If a config already exists, it is updated with the provided
    fields. If not, a new one is created using industry defaults
    for any fields not explicitly set.
    """
    try:
        from app.services.brand_voice_service import BrandVoiceService

        service = BrandVoiceService()
        config_data = request.model_dump(exclude_unset=True)

        # Try update first, fall back to create
        try:
            config = await service.update_config(company_id, config_data)
        except (NotFoundError, Exception):
            config = await service.create_config(company_id, config_data)

        return {
            "status": "ok",
            "data": (
                asdict(config) if hasattr(config, "__dataclass_fields__") else config
            ),
        }

    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.to_dict())
    except Exception as exc:
        logger.error(
            "brand_voice_upsert_failed",
            extra={"company_id": company_id, "error": str(exc)},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to save brand voice config")


@brand_voice_router.delete("", summary="Delete brand voice config")
async def delete_brand_voice(
    company_id: str = Depends(get_company_id),
    user: User = Depends(require_roles("owner", "admin")),
) -> Dict[str, Any]:
    """Delete the brand voice configuration for the company.

    After deletion, the system falls back to industry defaults.
    """
    try:
        from app.services.brand_voice_service import BrandVoiceService

        service = BrandVoiceService()
        deleted = await service.delete_config(company_id)
        return {
            "status": "ok",
            "data": {"deleted": deleted},
        }

    except Exception as exc:
        logger.error(
            "brand_voice_delete_failed",
            extra={"company_id": company_id, "error": str(exc)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Failed to delete brand voice config"
        )


@brand_voice_router.post(
    "/check-prohibited",
    summary="Check text for prohibited words",
)
async def check_prohibited_words(
    request: BrandVoiceCheckProhibitedSchema,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Check text for prohibited words with l33t-speak normalization.

    GAP-021 FIX: Text is normalized before checking to catch
    variants like 'd4mn', 'h3ll', 'f*ck', etc.
    """
    try:
        from app.services.brand_voice_service import BrandVoiceService

        service = BrandVoiceService()
        result = await service.check_prohibited_words(
            text=request.text,
            company_id=company_id,
        )
        return {
            "status": "ok",
            "data": asdict(result),
        }

    except Exception as exc:
        logger.error(
            "brand_voice_check_prohibited_failed",
            extra={"company_id": company_id, "error": str(exc)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to check prohibited words",
        )


@brand_voice_router.post(
    "/validate",
    summary="Validate response against brand voice",
)
async def validate_brand_voice(
    request: BrandVoiceValidateSchema,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Validate a response against the company's brand voice rules.

    Returns a brand voice adherence score (0-1), list of
    violations, warnings, and suggested fixes.
    """
    try:
        from app.services.brand_voice_service import BrandVoiceService

        service = BrandVoiceService()
        config = await service.get_config(company_id)
        result = await service.validate_response(
            response_text=request.response_text,
            config=config,
            sentiment_score=request.sentiment_score,
        )
        return {
            "status": "ok",
            "data": asdict(result),
        }

    except (ValidationError, NotFoundError) as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.to_dict(),
        )
    except Exception as exc:
        logger.error(
            "brand_voice_validate_failed",
            extra={"company_id": company_id, "error": str(exc)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to validate response",
        )


# ═══════════════════════════════════════════════════════════════════
# 5. AI ASSIGNMENT
# ═══════════════════════════════════════════════════════════════════


@assignment_router.post("/ai", summary="AI ticket assignment")
async def ai_assign_ticket(
    request: AIAssignmentRequestSchema,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Assign a ticket using AI-based scoring.

    Considers sentiment, priority, customer tier, agent skills,
    and current workload to recommend the best agent.
    """
    try:
        from app.core.ai_assignment_engine import (
            AIAssignmentEngine,
            TicketAssignmentRequest,
        )

        engine = AIAssignmentEngine()
        req = TicketAssignmentRequest(
            ticket_id=request.ticket_id,
            company_id=company_id,
            variant_type=request.variant_type,
            intent_type=request.intent_type,
            priority=request.priority,
            sentiment_score=request.sentiment_score,
            customer_tier=request.customer_tier,
            conversation_history=request.conversation_history,
            skills_required=request.skills_required,
            max_candidates=request.max_candidates,
        )
        result = await engine.assign_ticket(req)
        return {
            "status": "ok",
            "data": asdict(result),
        }

    except (ValidationError, NotFoundError) as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.to_dict(),
        )
    except Exception as exc:
        logger.error(
            "ai_assignment_failed",
            extra={
                "company_id": company_id,
                "ticket_id": request.ticket_id,
                "error": str(exc),
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="AI assignment failed")


@assignment_router.get("/agents", summary="Get agent workload")
async def get_agent_workload(
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get current workload for all agents in the company.

    Returns agent IDs, names, active ticket counts, capacity, and
    availability status. Used to populate the assignment dashboard.
    """
    try:
        from app.services.assignment_service import AssignmentService

        service = AssignmentService(None, company_id)
        workload = service.get_agent_workload()
        return {
            "status": "ok",
            "data": workload,
        }

    except Exception as exc:
        logger.error(
            "agent_workload_failed",
            extra={"company_id": company_id, "error": str(exc)},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to get agent workload")


# ═══════════════════════════════════════════════════════════════════
# 6. MIGRATION (F-158)
# ═══════════════════════════════════════════════════════════════════


@migration_router.post("/status", summary="Get migration status")
async def get_migration_status(
    request: MigrationStatusSchema = MigrationStatusSchema(),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get the current rule-to-AI migration status for the company.

    Returns migration mode, AI rule percentage, static vs AI rule
    counts, and migration metrics.
    """
    try:
        from app.services.rule_migration_service import RuleMigrationService

        service = RuleMigrationService(db=None, company_id=company_id)
        status = service.get_migration_status()

        if request.feature:
            # Return feature-specific status if requested
            feature_status = {
                "feature": request.feature,
                "mode": status.get("mode", "static"),
                "enabled": status.get("migration_enabled", False),
            }
            return {"status": "ok", "data": feature_status}

        return {"status": "ok", "data": status}

    except Exception as exc:
        logger.error(
            "migration_status_failed",
            extra={"company_id": company_id, "error": str(exc)},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to get migration status")


@migration_router.post("/toggle", summary="Enable/disable AI feature")
async def toggle_migration(
    request: MigrationToggleSchema,
    company_id: str = Depends(get_company_id),
    user: User = Depends(require_roles("owner", "admin")),
) -> Dict[str, Any]:
    """Enable or disable AI for classification or assignment.

    Controls the migration mode for a specific feature:
      - classification: AI-based ticket classification
      - assignment: AI-based ticket assignment

    Modes:
      - static: All hardcoded rules (default)
      - shadow: AI evaluates but doesn't apply
      - canary: AI applied for X% of requests
      - gradual: Percentage increases over time
      - active: AI rules fully active
    """
    try:
        from app.services.rule_migration_service import RuleMigrationService

        valid_features = {"classification", "assignment"}
        if request.feature not in valid_features:
            raise ValidationError(
                message=(
                    f"Invalid feature '{request.feature}'. "
                    f"Must be one of: {', '.join(sorted(valid_features))}"
                ),
            )

        service = RuleMigrationService(db=None, company_id=company_id)

        if request.enabled:
            result = service.enable_migration(
                mode=request.mode,
                percentage=request.percentage,
            )
        else:
            result = service.rollback()

        return {
            "status": "ok",
            "data": {
                **result,
                "feature": request.feature,
                "enabled": request.enabled,
            },
        }

    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.to_dict())
    except Exception as exc:
        logger.error(
            "migration_toggle_failed",
            extra={
                "company_id": company_id,
                "feature": request.feature,
                "error": str(exc),
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to toggle migration")


# ═══════════════════════════════════════════════════════════════════
# COMBINED ROUTER
# ═══════════════════════════════════════════════════════════════════

router = APIRouter()
"""Combined router that includes all sub-routers.

Include this in your FastAPI app:

    from app.api.response import router as response_api
    app.include_router(response_api)
"""

router.include_router(response_router)
router.include_router(brand_voice_router)
router.include_router(assignment_router)
router.include_router(migration_router)
