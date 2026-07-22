"""
PARWA Carrier Actions Router — Real shipping carrier tool invocations.

Fixes the fake-wired MCP `carrier_server` problem:
  mcp_server/integrations/carrier_server.py called four backend endpoints
  that DON'T EXIST:
    POST /api/v1/carrier/detect
    POST /api/v1/carrier/track
    POST /api/v1/carrier/detect-delays
    POST /api/v1/carrier/compensation

  Plus: the MCP server was silently falling back to fake "success" responses
  when the backend was unreachable — including a confidence-0.8 carrier guess
  from local pattern matching that looked like real detection.

  This router delegates to the existing CarrierAPIConnector
  (backend/app/core/carrier_api_connector.py), which already implements:
    - Auto-carrier detection from tracking number format (FedEx/UPS/DHL/USPS)
    - Real carrier API queries (returns "not_configured" when keys absent)
    - Delay detection with carrier-specific thresholds
    - Compensation calculation per shipping tier

  Endpoint inventory:
    POST /api/integrations/carrier/detect          — detect carrier from tracking number
    POST /api/integrations/carrier/track           — track a shipment
    POST /api/integrations/carrier/detect-delays   — detect shipping delays
    POST /api/integrations/carrier/compensation    — calculate refund compensation

BC-001: All operations scoped to authenticated user's company_id.
BC-012: No stack traces leak; structured error responses.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.carrier_api_connector import CarrierAPIConnector
from database.base import get_db
from database.models.core import User

logger = logging.getLogger("parwa.api.carrier_actions")

router = APIRouter(prefix="/api/integrations/carrier", tags=["Integrations — Carrier Actions"])

# Singleton connector — compiles tracking-number regex patterns once at startup.
_connector = CarrierAPIConnector()


# ── Request / Response Schemas ────────────────────────────────────


class CarrierDetectRequest(BaseModel):
    tracking_number: str = Field(..., min_length=1)


class CarrierTrackRequest(BaseModel):
    tracking_number: str = Field(..., min_length=1)
    carrier_id: Optional[str] = Field(default=None, description="Optional carrier hint; auto-detected if absent.")


class CarrierDetectDelaysRequest(BaseModel):
    tracking_number: str = Field(..., min_length=1)
    carrier_id: Optional[str] = None


class CarrierCompensationRequest(BaseModel):
    tracking_number: str = Field(..., min_length=1)
    shipping_cost: float = Field(default=0.0, ge=0)
    service_tier: str = Field(default="standard")
    carrier_id: Optional[str] = None


class CarrierActionResponse(BaseModel):
    """Standard response. Status: ok | not_configured | not_found | external_error."""

    status: str
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────


@router.post("/detect", response_model=CarrierActionResponse)
async def carrier_detect(
    body: CarrierDetectRequest,
    user: User = Depends(get_current_user),
) -> CarrierActionResponse:
    """Detect the shipping carrier from a tracking number.

    Uses compiled regex patterns — no external API call, so this works
    even when carrier API credentials are not configured.
    """
    result = _connector.detect_carrier(body.tracking_number)
    # detect_carrier returns {"carrier_id": "unknown", ...} when no pattern matches.
    if result.get("carrier_id") == "unknown":
        return CarrierActionResponse(
            status="not_found",
            data=result,
            error=f"No carrier pattern matched tracking number '{body.tracking_number[:32]}'.",
        )
    return CarrierActionResponse(status="ok", data=result, error=None)


@router.post("/track", response_model=CarrierActionResponse)
async def carrier_track(
    body: CarrierTrackRequest,
    user: User = Depends(get_current_user),
) -> CarrierActionResponse:
    """Track a shipment by tracking number.

    Delegates to CarrierAPIConnector.track_shipment, which queries the real
    carrier API if credentials are configured, or returns a "not_configured"
    status honestly otherwise (NO random/fake data).
    """
    result = await _connector.track_shipment(
        company_id=str(user.company_id),
        tracking_number=body.tracking_number,
        carrier_id=body.carrier_id,
    )
    status_value = result.get("status", "external_error")
    # CarrierAPIConnector uses "not_configured" when no carrier API keys are set.
    if status_value in ("not_configured", "no_credentials"):
        return CarrierActionResponse(status="not_configured", data=result, error=result.get("message", "Carrier API not configured."))
    if status_value in ("not_found", "unknown_tracking"):
        return CarrierActionResponse(status="not_found", data=result, error=None)
    if status_value in ("error", "failed"):
        return CarrierActionResponse(status="external_error", data=result, error=result.get("message", "Carrier API error."))
    return CarrierActionResponse(status="ok", data=result, error=None)


@router.post("/detect-delays", response_model=CarrierActionResponse)
async def carrier_detect_delays(
    body: CarrierDetectDelaysRequest,
    user: User = Depends(get_current_user),
) -> CarrierActionResponse:
    """Detect shipping delays by comparing actual tracking status against expected timelines.

    Two-step: first track the shipment, then run delay detection on the result.
    """
    tracking = await _connector.track_shipment(
        company_id=str(user.company_id),
        tracking_number=body.tracking_number,
        carrier_id=body.carrier_id,
    )
    status_value = tracking.get("status")
    if status_value in ("not_configured", "no_credentials"):
        return CarrierActionResponse(
            status="not_configured", data={},
            error="Carrier API not configured. Connect a carrier integration in Settings → Integrations.",
        )
    if status_value in ("error", "failed"):
        return CarrierActionResponse(
            status="external_error", data=tracking,
            error=tracking.get("message", "Carrier API error during tracking."),
        )

    delays = _connector.detect_delays(
        company_id=str(user.company_id),
        tracking_result=tracking,
    )
    return CarrierActionResponse(status="ok", data=delays, error=None)


@router.post("/compensation", response_model=CarrierActionResponse)
async def carrier_calculate_compensation(
    body: CarrierCompensationRequest,
    user: User = Depends(get_current_user),
) -> CarrierActionResponse:
    """Calculate shipping refund compensation for delayed shipments.

    Three-step: track → detect delays → calculate compensation.
    Returns eligible=False, amount=0 when no delay is detected.
    """
    tracking = await _connector.track_shipment(
        company_id=str(user.company_id),
        tracking_number=body.tracking_number,
        carrier_id=body.carrier_id,
    )
    status_value = tracking.get("status")
    if status_value in ("not_configured", "no_credentials"):
        return CarrierActionResponse(
            status="not_configured", data={},
            error="Carrier API not configured. Connect a carrier integration in Settings → Integrations.",
        )
    if status_value in ("error", "failed"):
        return CarrierActionResponse(
            status="external_error", data=tracking,
            error=tracking.get("message", "Carrier API error during tracking."),
        )

    delays = _connector.detect_delays(
        company_id=str(user.company_id),
        tracking_result=tracking,
    )
    compensation = _connector.calculate_compensation(
        company_id=str(user.company_id),
        tracking_result=tracking,
        delay_result=delays,
        shipping_cost=body.shipping_cost,
        service_tier=body.service_tier,
    )
    return CarrierActionResponse(status="ok", data=compensation, error=None)
