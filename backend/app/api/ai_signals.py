"""
Signal Extraction API Endpoints (SG-13 / F-150)

REST endpoints for signal extraction and CLARA quality gate.

Parent: Week 9 Day 6 (Monday)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/ai/signals", tags=["Signal Extraction"])


# ── Request Models ────────────────────────────────────────────────────


class SignalExtractRequest(BaseModel):
    query: str = Field(..., min_length=1)
    company_id: str = Field(...)
    variant_type: str = Field(default="parwa")
    customer_tier: str = Field(default="free")
    turn_count: int = Field(default=0)
    previous_response_status: str = Field(default="none")
    conversation_history: Optional[List[str]] = Field(default=None)
    customer_metadata: Optional[Dict[str, Any]] = Field(default=None)


class BatchSignalRequest(BaseModel):
    requests: List[SignalExtractRequest] = Field(..., min_length=1, max_length=20)


class CLARAEvaluateRequest(BaseModel):
    response: str = Field(..., min_length=1)
    query: str = Field(...)
    company_id: str = Field(default="")
    customer_sentiment: float = Field(default=0.7, ge=0.0, le=1.0)
    brand_voice: Optional[Dict[str, Any]] = Field(default=None)


class SentimentTechniqueRequest(BaseModel):
    """Request body for sentiment → technique mapping (F-151)."""

    frustration_score: float = Field(
        ..., ge=0.0, le=100.0,
        description="Frustration score (0-100)",
    )
    sentiment_score: float = Field(
        ..., ge=0.0, le=1.0,
        description="Sentiment score (0.0-1.0, from signal extraction)",
    )
    urgency_level: str = Field(
        default="low",
        description="Urgency level: low, medium, high, critical",
    )
    customer_tier: str = Field(
        default="free",
        description="Customer tier: free, pro, enterprise, vip",
    )
    emotion: str = Field(
        default="neutral",
        description="Primary emotion classification",
    )
    is_vip: bool = Field(
        default=False,
        description="Whether the customer is VIP",
    )
    variant_type: str = Field(
        default="parwa",
        description="PARWA variant: mini_parwa, parwa, parwa_high",
    )
    company_id: str = Field(
        default="",
        description="Tenant identifier (BC-001)",
    )


# ── Singletons ────────────────────────────────────────────────────────

_extractor = None
_clara = None
_sentiment_mapper = None


def _get_extractor():
    global _extractor
    if _extractor is None:
        from app.core.signal_extraction import SignalExtractor
        _extractor = SignalExtractor()
    return _extractor


def _get_clara(brand_voice_config=None):
    global _clara
    if _clara is None or brand_voice_config is not None:
        from app.core.clara_quality_gate import CLARAQualityGate, BrandVoiceConfig
        bv = None
        if brand_voice_config:
            bv = BrandVoiceConfig(**brand_voice_config)
        _clara = CLARAQualityGate(brand_voice=bv)
    return _clara


def _get_sentiment_mapper():
    """Lazy-load SentimentTechniqueMapper (BC-008: never crash)."""
    global _sentiment_mapper
    if _sentiment_mapper is None:
        try:
            from app.services.sentiment_technique_mapper import SentimentTechniqueMapper
            _sentiment_mapper = SentimentTechniqueMapper()
        except Exception as exc:
            import logging
            logging.getLogger("signals_api").error(
                "sentiment_mapper_init_failed",
                error=str(exc),
            )
            _sentiment_mapper = None
    return _sentiment_mapper


# ── Endpoints ────────────────────────────────────────────────────────


@router.post("/extract")
async def extract_signals(req: SignalExtractRequest) -> Dict[str, Any]:
    """Extract 10 signals from a query (SG-13)."""
    from app.core.signal_extraction import SignalExtractionRequest

    extractor = _get_extractor()
    request = SignalExtractionRequest(
        query=req.query,
        company_id=req.company_id,
        variant_type=req.variant_type,
        customer_tier=req.customer_tier,
        turn_count=req.turn_count,
        previous_response_status=req.previous_response_status,
        conversation_history=req.conversation_history,
        customer_metadata=req.customer_metadata,
    )
    result = await extractor.extract(request)
    return result.to_dict()


@router.post("/batch")
async def batch_extract_signals(req: BatchSignalRequest) -> Dict[str, Any]:
    """Extract signals from multiple queries."""
    from app.core.signal_extraction import SignalExtractionRequest

    extractor = _get_extractor()
    results = []
    for r in req.requests:
        request = SignalExtractionRequest(
            query=r.query,
            company_id=r.company_id,
            variant_type=r.variant_type,
            customer_tier=r.customer_tier,
            turn_count=r.turn_count,
            previous_response_status=r.previous_response_status,
            conversation_history=r.conversation_history,
            customer_metadata=r.customer_metadata,
        )
        result = await extractor.extract(request)
        results.append(result.to_dict())
    return {"results": results, "count": len(results)}


@router.post("/clara")
async def evaluate_clara(req: CLARAEvaluateRequest) -> Dict[str, Any]:
    """Run CLARA quality gate on a response (F-150)."""
    clara = _get_clara(brand_voice_config=req.brand_voice)
    result = await clara.evaluate(
        response=req.response,
        query=req.query,
        company_id=req.company_id,
        customer_sentiment=req.customer_sentiment,
    )
    return {
        "overall_pass": result.overall_pass,
        "overall_score": result.overall_score,
        "pipeline_timed_out": result.pipeline_timed_out,
        "total_processing_time_ms": result.total_processing_time_ms,
        "final_response": result.final_response,
        "stages": [
            {
                "stage": s.stage.value,
                "result": s.result.value,
                "score": s.score,
                "issues": s.issues,
                "suggestions": s.suggestions,
                "processing_time_ms": s.processing_time_ms,
            }
            for s in result.stages
        ],
    }


@router.post("/sentiment-techniques")
async def map_sentiment_to_techniques(
    req: SentimentTechniqueRequest,
) -> Dict[str, Any]:
    """Map sentiment signals to recommended AI techniques (F-151).

    Uses SentimentTechniqueMapper to recommend techniques based on
    frustration score, sentiment score, urgency, customer tier,
    and VIP status. Applies variant-aware tier filtering (GAP-001).

    Returns:
        recommended_techniques: List of technique IDs
        technique_reasons: Dict mapping technique ID → reason
        priority_override: Whether to bypass normal selection
        escalation_recommended: Whether human escalation is recommended
        tone_adjustments: List of tone adjustment instructions
        blocked_techniques: Techniques blocked by variant tier limit
    """
    mapper = _get_sentiment_mapper()

    if mapper is None:
        return {
            "recommended_techniques": ["chain_of_thought"],
            "technique_reasons": {"chain_of_thought": "Fallback — mapper unavailable"},
            "priority_override": False,
            "escalation_recommended": False,
            "tone_adjustments": [],
            "variant_type": req.variant_type,
            "blocked_techniques": [],
            "_fallback_reason": "sentiment_mapper_unavailable",
        }

    try:
        result = mapper.map(
            frustration_score=req.frustration_score,
            sentiment_score=req.sentiment_score,
            urgency_level=req.urgency_level,
            customer_tier=req.customer_tier,
            emotion=req.emotion,
            is_vip=req.is_vip,
            variant_type=req.variant_type,
            company_id=req.company_id,
        )
        return result.to_dict()
    except Exception as exc:
        return {
            "recommended_techniques": ["chain_of_thought"],
            "technique_reasons": {"chain_of_thought": f"Fallback — {exc!s}"},
            "priority_override": False,
            "escalation_recommended": False,
            "tone_adjustments": [],
            "variant_type": req.variant_type,
            "blocked_techniques": [],
            "_fallback_reason": "internal_error",
        }


@router.get("/info")
async def signal_info() -> Dict[str, Any]:
    """Get signal extraction info and variant weights."""
    from app.core.signal_extraction import SignalExtractor

    extractor = SignalExtractor()
    return {
        "supported_signals": [
            "intent", "sentiment", "complexity", "monetary_value",
            "customer_tier", "turn_count", "previous_response_status",
            "reasoning_loop_detected", "resolution_path_count", "query_breadth",
        ],
        "variant_weights": extractor.VARIANT_WEIGHTS,
        "cache_ttl_seconds": extractor.CACHE_TTL_SECONDS,
    }
