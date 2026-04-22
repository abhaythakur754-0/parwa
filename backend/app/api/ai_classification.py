"""
AI Classification API Endpoints (F-062 / F-149)

REST endpoints for AI-powered intent classification and
intent × technique mapping.

Parent: Week 9 Day 6 (Monday)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import require_roles

router = APIRouter(
    prefix="/api/ai/classification",
    tags=["AI Classification"],
    dependencies=[Depends(require_roles("owner", "admin"))],
)


# ── Request/Response Models ───────────────────────────────────────────


class ClassifyRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to classify")
    company_id: str = Field(..., description="Tenant company ID")
    variant_type: str = Field(default="parwa", description="PARWA variant type")
    use_ai: bool = Field(default=True, description="Use AI classification if available")


class BatchClassifyRequest(BaseModel):
    texts: List[str] = Field(..., min_length=1, max_length=20)
    company_id: str = Field(...)
    variant_type: str = Field(default="parwa")
    use_ai: bool = Field(default=True)


# ── Singletons ────────────────────────────────────────────────────────

_engine = None
_mapper = None


def _get_engine():
    global _engine
    if _engine is None:
        from app.core.classification_engine import ClassificationEngine
        _engine = ClassificationEngine()
    return _engine


def _get_mapper():
    global _mapper
    if _mapper is None:
        from app.services.intent_technique_mapper import IntentTechniqueMapper
        _mapper = IntentTechniqueMapper()
    return _mapper


# ── Endpoints ────────────────────────────────────────────────────────


@router.post("/classify")
async def classify_text(req: ClassifyRequest) -> Dict[str, Any]:
    """Classify text into primary + secondary intents (F-062)."""
    engine = _get_engine()
    result = await engine.classify(
        text=req.text,
        company_id=req.company_id,
        variant_type=req.variant_type,
        use_ai=req.use_ai,
    )
    return {
        "primary_intent": result.primary_intent,
        "primary_confidence": result.primary_confidence,
        "secondary_intents": [
            {"intent": i, "confidence": c}
            for i, c in result.secondary_intents
        ],
        "all_scores": result.all_scores,
        "classification_method": result.classification_method,
        "processing_time_ms": result.processing_time_ms,
        "model_used": result.model_used,
    }


@router.get("/intents")
async def list_intents() -> Dict[str, Any]:
    """List all supported intent types."""
    from app.core.classification_engine import IntentType
    intents = [t.value for t in IntentType]
    return {"intents": intents, "count": len(intents)}


@router.post("/batch")
async def batch_classify(req: BatchClassifyRequest) -> Dict[str, Any]:
    """Classify multiple texts in one request."""
    engine = _get_engine()
    results = []
    for text in req.texts:
        result = await engine.classify(
            text=text,
            company_id=req.company_id,
            variant_type=req.variant_type,
            use_ai=req.use_ai,
        )
        results.append({
            "text": text[:100],
            "primary_intent": result.primary_intent,
            "primary_confidence": result.primary_confidence,
            "secondary_intents": [
                {"intent": i, "confidence": c}
                for i, c in result.secondary_intents
            ],
            "classification_method": result.classification_method,
        })
    return {"results": results, "count": len(results)}


@router.get("/mapping/{intent}")
async def get_intent_mapping(
    intent: str,
    variant_type: str = Query(default="parwa"),
) -> Dict[str, Any]:
    """Get technique mapping for a specific intent (F-149)."""
    mapper = _get_mapper()
    result = mapper.map_intent(intent=intent, variant_type=variant_type)
    return {
        "intent": result.intent,
        "variant_type": result.variant_type,
        "selected_techniques": [t.value for t in result.selected_techniques],
        "selected_tiers": [t.value for t in result.selected_tiers],
        "fallback_applied": result.fallback_applied,
        "blocked_techniques": result.blocked_techniques,
    }


@router.get("/mappings")
async def get_all_mappings(
    variant_type: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """Get all intent → technique mappings, optionally filtered by variant."""
    mapper = _get_mapper()
    all_mappings = mapper.get_all_mappings()

    if variant_type:
        filtered = {}
        for intent, mapping in all_mappings.items():
            result = mapper.map_intent(intent=intent, variant_type=variant_type)
            filtered[intent] = {
                "selected_techniques": [t.value for t in result.selected_techniques],
                "selected_tiers": [t.value for t in result.selected_tiers],
                "fallback_applied": result.fallback_applied,
                "blocked_count": len(result.blocked_techniques),
            }
        return {"mappings": filtered, "variant_type": variant_type, "count": len(filtered)}

    return {
        "mappings": {
            intent: {
                "techniques": m.recommended_techniques,
                "tiers": m.recommended_tiers,
                "trigger_conditions": m.trigger_conditions,
            }
            for intent, m in all_mappings.items()
        },
        "count": len(all_mappings),
    }


@router.get("/templates")
async def list_prompt_templates(
    intent: Optional[str] = Query(default=None),
    response_type: Optional[str] = Query(default=None),
    variant_type: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """List prompt templates (SG-25), optionally filtered."""
    from app.services.intent_prompt_templates import PromptTemplateRegistry

    registry = PromptTemplateRegistry()

    if intent and response_type:
        template = registry.get_template(intent, response_type, variant_type or "parwa")
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        return {
            "template_id": template.template_id,
            "intent": template.intent,
            "response_type": template.response_type,
            "system_prompt": template.system_prompt[:200] + "...",
            "tone_instructions": template.tone_instructions,
            "variant_access": template.variant_access,
            "few_shot_count": len(template.few_shot_examples),
        }

    templates = registry.list_all_templates()

    if intent:
        templates = [t for t in templates if t["intent"] == intent]
    if response_type:
        templates = [t for t in templates if t["response_type"] == response_type]
    if variant_type:
        templates = [
            t for t in templates
            if variant_type in t["variant_access"]
        ]

    return {"templates": templates, "count": len(templates)}
