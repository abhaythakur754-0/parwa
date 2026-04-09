"""
Classification API Endpoint

POST endpoint to classify ticket text using ClassificationEngine.
Returns IntentResult as JSON.

Follows PARWA conventions:
- BC-001: company_id is the first parameter to engine.classify()
- BC-008: Never crash — wrap everything in try/except

Parent: Week 9 Day 6 (Monday)
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.app.logger import get_logger

logger = get_logger("classification_api")

router = APIRouter(
    prefix="/api/classification",
    tags=["Classification"],
)


# ── Request Model ──────────────────────────────────────────────────


class ClassifyRequest(BaseModel):
    """Request body for text classification."""

    text: str = Field(..., min_length=1, description="Text to classify")
    company_id: str = Field(..., description="Tenant company ID (BC-001)")
    variant_type: str = Field(
        default="parwa",
        description="PARWA variant: mini_parwa, parwa, parwa_high",
    )
    use_ai: bool = Field(
        default=True,
        description="Use AI classification if available",
    )


# ── Singleton ───────────────────────────────────────────────────────

_engine = None


def _get_engine():
    """Lazy-load ClassificationEngine (BC-008: never crash)."""
    global _engine  # noqa: PLW0603
    if _engine is None:
        try:
            from backend.app.core.classification_engine import (
                ClassificationEngine,
            )
            _engine = ClassificationEngine()
        except Exception as exc:
            logger.error(
                "classification_engine_init_failed",
                error=str(exc),
            )
            _engine = None
    return _engine


# ── Endpoints ───────────────────────────────────────────────────────


@router.post("/classify")
async def classify_text(req: ClassifyRequest) -> Dict[str, Any]:
    """Classify ticket text into primary + secondary intents.

    Uses ClassificationEngine from backend.app.core.classification_engine.
    Returns IntentResult as JSON with primary_intent, primary_confidence,
    secondary_intents, all_scores, classification_method, and
    processing_time_ms.

    BC-001: company_id is the first parameter to engine.classify().
    BC-008: Returns a safe default result on any error.
    """
    engine = _get_engine()

    # BC-008: If engine failed to initialize, return safe default
    if engine is None:
        logger.error(
            "classify_failed_no_engine",
            company_id=req.company_id,
        )
        return _safe_default_result("engine_unavailable")

    try:
        # BC-001: company_id is the FIRST parameter
        result = await engine.classify(
            company_id=req.company_id,
            text=req.text,
            variant_type=req.variant_type,
            use_ai=req.use_ai,
        )

        return {
            "primary_intent": result.primary_intent,
            "primary_confidence": result.primary_confidence,
            "secondary_intents": [
                {"intent": intent, "confidence": confidence}
                for intent, confidence in result.secondary_intents
            ],
            "all_scores": result.all_scores,
            "classification_method": result.classification_method,
            "processing_time_ms": result.processing_time_ms,
            "model_used": result.model_used,
        }

    except Exception as exc:
        # BC-008: Never crash — log and return safe default
        logger.error(
            "classify_failed",
            company_id=req.company_id,
            variant_type=req.variant_type,
            error=str(exc),
        )
        return _safe_default_result("internal_error")


def _safe_default_result(reason: str) -> Dict[str, Any]:
    """Return a safe default classification result (BC-008)."""
    return {
        "primary_intent": "general",
        "primary_confidence": 0.0,
        "secondary_intents": [],
        "all_scores": {},
        "classification_method": "fallback",
        "processing_time_ms": 0.0,
        "model_used": None,
        "_fallback_reason": reason,
    }
