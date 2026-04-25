"""
PARWA Demo API Endpoints

Pre-purchase demo experience for potential customers.
Variant-aware endpoints that let users test different PARWA tiers.

Endpoints:
- POST /api/demo/session - Create demo session
- GET /api/demo/session/{id} - Get demo session
- POST /api/demo/chat - Send message in demo
- GET /api/demo/scenarios - Get demo scenarios for variant
- GET /api/demo/variants - Get variant comparison
- POST /api/demo/complete - Complete demo session
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from enum import Enum

from app.logger import get_logger
from app.services.demo_service import (
    get_demo_service,
    DemoService,
    DemoVariant,
    DemoStatus,
)

logger = get_logger("demo_api")
router = APIRouter(prefix="/demo", tags=["demo"])


# ── Schemas ────────────────────────────────────────────────────────────────

class DemoVariantEnum(str, Enum):
    mini_parwa = "mini_parwa"
    parwa = "parwa"
    high_parwa = "high_parwa"


class CreateDemoSessionRequest(BaseModel):
    variant: DemoVariantEnum = DemoVariantEnum.parwa
    industry: str = Field(default="ecommerce", description="Industry for demo context")
    visitor_email: Optional[EmailStr] = None
    visitor_phone: Optional[str] = None


class DemoSessionResponse(BaseModel):
    session_id: str
    variant: str
    variant_display_name: str
    industry: str
    max_messages: int
    features: List[str]
    status: str
    message: str


class SendMessageRequest(BaseModel):
    session_id: str
    message: str = Field(..., min_length=1, max_length=2000)


class SendMessageResponse(BaseModel):
    success: bool
    ai_response: str
    confidence: float
    latency_ms: float
    features_used: List[str]
    remaining_messages: int
    variant_capabilities: Dict[str, Any]
    web_results: Optional[List[Dict[str, str]]] = None


class VariantCapabilities(BaseModel):
    variant: str
    display_name: str
    price_monthly: str
    max_demo_messages: int
    features: List[str]
    voice_enabled: bool
    web_search_enabled: bool
    image_gen_enabled: bool


class DemoScenario(BaseModel):
    id: str
    title: str
    difficulty: str
    preview: str
    talking_points: List[str]


class CompleteDemoResponse(BaseModel):
    success: bool
    message: str
    summary: Dict[str, Any]


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/session", response_model=DemoSessionResponse)
async def create_demo_session(request: CreateDemoSessionRequest):
    """
    Create a new demo session for a potential customer.

    This allows visitors to test PARWA capabilities before purchasing.
    The variant determines the features and message limits.
    """
    try:
        demo_service = get_demo_service()

        # Convert to internal enum
        variant_map = {
            DemoVariantEnum.mini_parwa: DemoVariant.MINI_PARWA,
            DemoVariantEnum.parwa: DemoVariant.PARWA,
            DemoVariantEnum.high_parwa: DemoVariant.HIGH_PARWA,
        }
        variant = variant_map.get(request.variant, DemoVariant.PARWA)

        # Create session
        session = demo_service.create_demo_session(
            variant=variant,
            industry=request.industry,
            visitor_email=request.visitor_email,
            visitor_phone=request.visitor_phone,
        )

        # Get capabilities
        from app.services.demo_service import VARIANT_DEMO_CAPABILITIES
        capabilities = VARIANT_DEMO_CAPABILITIES.get(variant, {})

        return DemoSessionResponse(
            session_id=session.session_id,
            variant=variant.value,
            variant_display_name=capabilities.get("display_name", "Parwa"),
            industry=session.industry,
            max_messages=capabilities.get("max_demo_messages", 20),
            features=capabilities.get("features", []),
            status=session.status.value,
            message="Demo session created! Start chatting to experience PARWA AI.",
        )

    except Exception as e:
        logger.error("create_demo_session_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create demo session")


@router.get("/session/{session_id}")
async def get_demo_session(session_id: str):
    """
    Get demo session details.
    """
    demo_service = get_demo_service()
    session = demo_service.get_demo_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Demo session not found")

    from app.services.demo_service import VARIANT_DEMO_CAPABILITIES
    capabilities = VARIANT_DEMO_CAPABILITIES.get(session.variant, {})

    return {
        "session_id": session.session_id,
        "variant": session.variant.value,
        "variant_display_name": capabilities.get("display_name", "Parwa"),
        "industry": session.industry,
        "status": session.status.value,
        "message_count": session.message_count,
        "max_messages": capabilities.get("max_demo_messages", 20),
        "remaining_messages": capabilities.get("max_demo_messages", 20) - session.message_count,
        "messages": session.messages[-20:],  # Last 20 messages
        "created_at": session.created_at.isoformat(),
        "visitor_email": session.visitor_email,
    }


@router.post("/chat", response_model=SendMessageResponse)
async def send_demo_message(request: SendMessageRequest):
    """
    Send a message in the demo session.

    The AI response is tailored to the variant capabilities:
    - Mini Parwa: Basic responses, simple routing
    - Parwa: Detailed responses, web search available
    - High Parwa: Premium responses, full features
    """
    demo_service = get_demo_service()

    result = demo_service.send_demo_message(
        session_id=request.session_id,
        message=request.message,
    )

    if not result.success:
        return SendMessageResponse(
            success=False,
            ai_response="",
            confidence=0.0,
            latency_ms=0.0,
            features_used=[],
            remaining_messages=0,
            variant_capabilities={"error": result.message},
        )

    variant_caps = result.variant_capabilities
    return SendMessageResponse(
        success=True,
        ai_response=result.ai_response,
        confidence=result.confidence,
        latency_ms=result.latency_ms,
        features_used=result.features_used,
        remaining_messages=variant_caps.get("remaining_messages", 0),
        variant_capabilities=variant_caps,
        web_results=variant_caps.get("web_results"),
    )


@router.get("/scenarios/{variant}/{industry}", response_model=List[DemoScenario])
async def get_demo_scenarios(variant: DemoVariantEnum, industry: str):
    """
    Get demo scenarios available for a variant and industry.

    Different variants have access to different numbers of scenarios:
    - Mini Parwa: 3 scenarios
    - Parwa: 10 scenarios
    - High Parwa: 20 scenarios
    """
    demo_service = get_demo_service()

    variant_map = {
        DemoVariantEnum.mini_parwa: DemoVariant.MINI_PARWA,
        DemoVariantEnum.parwa: DemoVariant.PARWA,
        DemoVariantEnum.high_parwa: DemoVariant.HIGH_PARWA,
    }

    scenarios = demo_service.get_demo_scenarios(
        variant=variant_map.get(variant, DemoVariant.PARWA),
        industry=industry,
    )

    return [DemoScenario(**s) for s in scenarios]


@router.get("/variants", response_model=Dict[str, VariantCapabilities])
async def get_variant_comparison():
    """
    Get comparison of all PARWA variants for the demo page.

    Returns pricing, features, and capabilities for each tier.
    """
    demo_service = get_demo_service()
    return demo_service.get_variant_comparison()


@router.post("/complete/{session_id}", response_model=CompleteDemoResponse)
async def complete_demo_session(session_id: str):
    """
    Complete a demo session and get results summary.

    Optionally sends follow-up email/SMS if contact info was provided.
    """
    demo_service = get_demo_service()
    result = demo_service.complete_demo_session(session_id)

    return CompleteDemoResponse(
        success=result.get("success", False),
        message=result.get("message", ""),
        summary=result.get("summary", {}),
    )


@router.post("/quick-demo")
async def quick_demo(request: Request):
    """
    Quick demo endpoint for landing page widget.

    Creates a session and sends a message in one call.
    No authentication required.
    """
    try:
        body = await request.json()
        message = body.get("message", "Hello!")
        variant = body.get("variant", "parwa")
        industry = body.get("industry", "ecommerce")

        demo_service = get_demo_service()

        # Create session
        variant_map = {
            "mini_parwa": DemoVariant.MINI_PARWA,
            "parwa": DemoVariant.PARWA,
            "high_parwa": DemoVariant.HIGH_PARWA,
        }

        session = demo_service.create_demo_session(
            variant=variant_map.get(variant, DemoVariant.PARWA),
            industry=industry,
        )

        # Send message
        result = demo_service.send_demo_message(
            session_id=session.session_id,
            message=message,
        )

        return JSONResponse({
            "success": result.success,
            "session_id": session.session_id,
            "reply": result.ai_response,
            "variant": session.variant.value,
            "remaining_messages": result.variant_capabilities.get("remaining_messages", 0),
        })

    except Exception as e:
        logger.error("quick_demo_failed", error=str(e))
        return JSONResponse(
            {"success": False, "error": "Demo unavailable. Please try again."},
            status_code=500,
        )
