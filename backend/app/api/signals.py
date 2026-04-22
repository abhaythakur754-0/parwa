"""
Signals API Endpoint

POST endpoint to extract signals from ticket text using SignalExtractor.
Returns ExtractedSignals as JSON.

Follows PARWA conventions:
- BC-001: company_id is a required field
- BC-008: Never crash — wrap everything in try/except

Parent: Week 9 Day 6 (Monday)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import require_roles
from app.logger import get_logger

logger = get_logger("signals_api")

router = APIRouter(
    prefix="/api/signals",
    tags=["Signals"],
    dependencies=[Depends(require_roles("owner", "admin"))],
)


# ── Request Model ──────────────────────────────────────────────────


class SignalRequest(BaseModel):
    """Request body for signal extraction."""

    query: str = Field(..., min_length=1, description="Ticket text")
    company_id: str = Field(..., description="Tenant company ID (BC-001)")
    variant_type: str = Field(
        default="parwa",
        description="PARWA variant: mini_parwa, parwa, parwa_high",
    )
    customer_tier: str = Field(
        default="free",
        description="Customer tier: free, pro, enterprise, vip",
    )
    turn_count: int = Field(
        default=0,
        ge=0,
        description="Number of conversation turns",
    )
    previous_response_status: str = Field(
        default="none",
        description="Previous response status: "
        "accepted, rejected, corrected, none",
    )
    conversation_history: Optional[List[str]] = Field(
        default=None,
        description="Previous conversation messages",
    )
    customer_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional customer metadata (e.g., tier, plan)",
    )


# ── Singleton ───────────────────────────────────────────────────────

_extractor = None


def _get_extractor():
    """Lazy-load SignalExtractor (BC-008: never crash)."""
    global _extractor  # noqa: PLW0603
    if _extractor is None:
        try:
            from app.core.signal_extraction import (
                SignalExtractor,
            )
            _extractor = SignalExtractor()
        except Exception as exc:
            logger.error(
                "signal_extractor_init_failed",
                error=str(exc),
            )
            _extractor = None
    return _extractor


# ── Endpoints ───────────────────────────────────────────────────────


@router.post("/extract")
async def extract_signals(req: SignalRequest) -> Dict[str, Any]:
    """Extract 10 real-time signals from a ticket query.

    Uses SignalExtractor from app.core.signal_extraction.
    Returns ExtractedSignals as JSON with intent, sentiment, complexity,
    monetary_value, customer_tier, turn_count,
    previous_response_status, reasoning_loop_detected,
    resolution_path_count, and query_breadth.

    BC-001: company_id is validated and passed to the extractor.
    BC-008: Returns a safe default result on any error.
    """
    extractor = _get_extractor()

    # BC-008: If extractor failed to initialize, return safe default
    if extractor is None:
        logger.error(
            "extract_signals_failed_no_extractor",
            company_id=req.company_id,
        )
        return _safe_default_signals("extractor_unavailable")

    try:
        from app.core.signal_extraction import (
            SignalExtractionRequest,
        )

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

    except Exception as exc:
        # BC-008: Never crash — log and return safe default
        logger.error(
            "extract_signals_failed",
            company_id=req.company_id,
            variant_type=req.variant_type,
            error=str(exc),
        )
        return _safe_default_signals("internal_error")


def _safe_default_signals(
    reason: str,
) -> Dict[str, Any]:
    """Return a safe default signals result (BC-008)."""
    return {
        "intent": "general",
        "sentiment": 0.5,
        "complexity": 0.5,
        "monetary_value": 0.0,
        "monetary_currency": None,
        "customer_tier": "free",
        "turn_count": 0,
        "previous_response_status": "none",
        "reasoning_loop_detected": False,
        "resolution_path_count": 1,
        "query_breadth": 0.5,
        "extraction_version": "1.0",
        "cached": False,
        "_fallback_reason": reason,
    }
