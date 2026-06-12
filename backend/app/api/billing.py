"""
PARWA Phase 3 — Billing API Routes (UNIVERSAL — no Paddle coupling)

Endpoints for usage tracking, variant management, cost calculation,
overage estimation, and payment gateway registration.

CRITICAL RULES:
- Paddle is ONLY for PARWA's own subscription billing — clients can use ANY payment provider
- BC-001: All endpoints use company_id from JWT/header for tenant isolation
- BC-008: Never crash — all route handlers in try/except
- No mock data, no placeholder emails
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_company_id, get_audit_trail
from app.core.multi_variant_billing import MultiVariantBillingService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])

# ---------------------------------------------------------------------------
# Per-company billing service cache
# ---------------------------------------------------------------------------

_billing_services: Dict[str, MultiVariantBillingService] = {}


def _get_billing_service(company_id: str) -> MultiVariantBillingService:
    """Get or create a billing service for the given company."""
    if company_id not in _billing_services:
        _billing_services[company_id] = MultiVariantBillingService(company_id)
    return _billing_services[company_id]


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class AddVariantRequest(BaseModel):
    """Add a subscription variant."""
    variant: str = Field(..., description="Variant name: mini, parwa, or high")
    payment_provider: str = Field(default="paddle", description="Payment provider (paddle, stripe, paypal, razorpay, custom)")


class RemoveVariantRequest(BaseModel):
    """Remove a variant (placeholder for path param consistency)."""
    pass


class CostCalculationRequest(BaseModel):
    """Calculate monthly cost for given variants and add-ons."""
    variants: List[str] = Field(..., description="List of variant names")
    add_ons: Optional[List[str]] = Field(default=None, description="List of add-on names")


class OverageEstimateRequest(BaseModel):
    """Estimate overage for a variant."""
    variant: str = Field(..., description="Variant name")
    projected_tickets: int = Field(..., gt=0, description="Expected ticket count")


class RegisterGatewayRequest(BaseModel):
    """Register a payment gateway for the company."""
    provider: str = Field(..., description="Payment provider name (stripe, paypal, razorpay, paddle, custom)")
    credentials: Dict[str, Any] = Field(..., description="Provider-specific credentials (will be encrypted)")


# ---------------------------------------------------------------------------
# GET /billing/usage
# ---------------------------------------------------------------------------

@router.get("/usage")
def get_usage_summary(
    company_id: str = Depends(get_current_company_id),
) -> dict:
    """Get usage summary across all active variants.

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        service = _get_billing_service(company_id)
        summary = service.get_usage_summary()
        return {
            "status": "success",
            "company_id": company_id,
            "usage": summary,
        }
    except Exception as exc:
        logger.error("get_usage_summary failed for company_id=%s: %s", company_id, exc)
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
        }


# ---------------------------------------------------------------------------
# POST /billing/variant
# ---------------------------------------------------------------------------

@router.post("/variant")
def add_variant(
    body: AddVariantRequest,
    company_id: str = Depends(get_current_company_id),
) -> dict:
    """Add a variant subscription for the company.

    payment_provider defaults to 'paddle' for PARWA's own subscription billing.
    Clients can specify their own provider (stripe, paypal, etc.).

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        service = _get_billing_service(company_id)
        result = service.add_variant(
            variant=body.variant,
            payment_provider=body.payment_provider,
        )

        # Audit log
        try:
            audit = get_audit_trail()
            if audit:
                audit.log_action(
                    company_id=company_id,
                    user_id="api_user",
                    action="add_variant",
                    tool="billing",
                    details={
                        "variant": body.variant,
                        "payment_provider": body.payment_provider,
                    },
                    outcome="success" if result.get("status") == "success" else "failure",
                )
        except Exception:
            pass

        return {
            "status": result.get("status", "error"),
            "company_id": company_id,
            "result": result,
        }
    except Exception as exc:
        logger.error("add_variant failed for company_id=%s: %s", company_id, exc)
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
        }


# ---------------------------------------------------------------------------
# DELETE /billing/variant/{variant}
# ---------------------------------------------------------------------------

@router.delete("/variant/{variant}")
def remove_variant(
    variant: str,
    company_id: str = Depends(get_current_company_id),
) -> dict:
    """Remove a variant (scheduled for next billing cycle).

    Per D13: Variant downgrade = next cycle. Keep capacity until cycle ends.
    No proration, no partial refund.

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        service = _get_billing_service(company_id)
        result = service.remove_variant(variant=variant)

        # Audit log
        try:
            audit = get_audit_trail()
            if audit:
                audit.log_action(
                    company_id=company_id,
                    user_id="api_user",
                    action="remove_variant",
                    tool="billing",
                    details={"variant": variant},
                    outcome="success" if result.get("status") == "success" else "failure",
                )
        except Exception:
            pass

        return {
            "status": result.get("status", "error"),
            "company_id": company_id,
            "result": result,
        }
    except Exception as exc:
        logger.error("remove_variant failed for company_id=%s: %s", company_id, exc)
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
        }


# ---------------------------------------------------------------------------
# GET /billing/cost
# ---------------------------------------------------------------------------

@router.get("/cost")
def calculate_monthly_cost(
    variants: str = "",  # comma-separated
    add_ons: str = "",   # comma-separated
    company_id: str = Depends(get_current_company_id),
) -> dict:
    """Calculate monthly cost. Pure math, no API calls, no AI.

    Per D7: Pure math calculation based on pricing configuration.
    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        service = _get_billing_service(company_id)

        variant_list = [v.strip() for v in variants.split(",") if v.strip()] if variants else []
        addon_list = [a.strip() for a in add_ons.split(",") if a.strip()] if add_ons else None

        result = service.calculate_monthly_cost(
            variants=variant_list,
            add_ons=addon_list,
        )

        return {
            "status": result.get("status", "error"),
            "company_id": company_id,
            "cost": result,
        }
    except Exception as exc:
        logger.error("calculate_monthly_cost failed for company_id=%s: %s", company_id, exc)
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
        }


# ---------------------------------------------------------------------------
# POST /billing/overage/estimate
# ---------------------------------------------------------------------------

@router.post("/overage/estimate")
def estimate_overage(
    body: OverageEstimateRequest,
    company_id: str = Depends(get_current_company_id),
) -> dict:
    """Estimate overage cost for a variant.

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        service = _get_billing_service(company_id)
        result = service.estimate_overage(
            variant=body.variant,
            projected_tickets=body.projected_tickets,
        )

        return {
            "status": result.get("status", "error"),
            "company_id": company_id,
            "estimate": result,
        }
    except Exception as exc:
        logger.error("estimate_overage failed for company_id=%s: %s", company_id, exc)
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
        }


# ---------------------------------------------------------------------------
# GET /billing/gateways
# ---------------------------------------------------------------------------

@router.get("/gateways")
def list_payment_gateways(
    company_id: str = Depends(get_current_company_id),
) -> dict:
    """List registered payment gateways for the company.

    UNIVERSAL: Clients can use ANY payment provider, not just Paddle.
    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        service = _get_billing_service(company_id)
        gateways = service.payment_gateway.list_gateways()

        return {
            "status": "success",
            "company_id": company_id,
            "gateways": gateways,
            "supported_providers": list(service.payment_gateway.SUPPORTED_PROVIDERS),
        }
    except Exception as exc:
        logger.error("list_payment_gateways failed for company_id=%s: %s", company_id, exc)
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
            "gateways": [],
        }


# ---------------------------------------------------------------------------
# POST /billing/gateways
# ---------------------------------------------------------------------------

@router.post("/gateways")
def register_payment_gateway(
    body: RegisterGatewayRequest,
    company_id: str = Depends(get_current_company_id),
) -> dict:
    """Register a payment gateway for the company.

    UNIVERSAL: Clients can use ANY payment provider (stripe, paypal,
    razorpay, paddle, custom). Paddle is the default for PARWA's own
    subscription billing only.

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        service = _get_billing_service(company_id)
        success = service.payment_gateway.register_gateway(
            provider=body.provider,
            credentials=body.credentials,
        )

        # Audit log
        try:
            audit = get_audit_trail()
            if audit:
                audit.log_action(
                    company_id=company_id,
                    user_id="api_user",
                    action="register_payment_gateway",
                    tool="billing",
                    details={"provider": body.provider},
                    outcome="success" if success else "failure",
                )
        except Exception:
            pass

        return {
            "status": "success" if success else "error",
            "company_id": company_id,
            "provider": body.provider,
            "message": (
                f"Payment gateway '{body.provider}' registered successfully"
                if success
                else f"Failed to register gateway '{body.provider}'"
            ),
        }
    except Exception as exc:
        logger.error("register_payment_gateway failed for company_id=%s: %s", company_id, exc)
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
        }
