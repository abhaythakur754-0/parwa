"""
PARWA Pricing Router (Day 6)

Endpoints for pricing variants by industry.

All public endpoints (no JWT required):
- GET  /api/pricing/industries - List available industries
- GET  /api/pricing/variants/{industry} - Get variants by industry
- POST /api/pricing/calculate - Calculate total pricing
- POST /api/pricing/validate - Validate and sign pricing selection (GAP-6-3 fix)

Based on ONBOARDING_SPEC.md Section 3 - Industry Variants
"""

import hashlib
import hmac
import html
import re
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, validator

router = APIRouter(prefix="/api/pricing", tags=["Pricing"])


# ── Security Helpers (GAP-6-1, GAP-6-3 fixes) ───────────────────────

def sanitize_input(value: str, max_length: int = 100) -> str:
    """Sanitize user input to prevent XSS (GAP-6-4 fix).
    
    - Strips HTML tags
    - Escapes HTML entities
    - Truncates to max_length
    """
    if not value:
        return ""
    # Remove any HTML tags
    value = re.sub(r'<[^>]*>', '', value)
    # Escape HTML entities
    value = html.escape(value)
    # Truncate
    return value[:max_length]


def validate_url(url: str) -> str:
    """Validate URL to prevent XSS and phishing (GAP-6-5 fix).
    
    - Only allows http:// and https:// protocols
    - Rejects javascript:, data:, file: protocols
    """
    if not url:
        return ""
    
    url = url.strip()
    
    # Check for dangerous protocols
    dangerous_protocols = ['javascript:', 'data:', 'file:', 'vbscript:', 'about:']
    url_lower = url.lower()
    for protocol in dangerous_protocols:
        if url_lower.startswith(protocol):
            raise ValueError(f"URL protocol not allowed: {protocol}")
    
    # Must start with http:// or https://
    if not (url_lower.startswith('http://') or url_lower.startswith('https://')):
        raise ValueError("URL must start with http:// or https://")
    
    # Basic URL length check
    if len(url) > 2000:
        raise ValueError("URL is too long (max 2000 characters)")
    
    return url


# ── Constants ───────────────────────────────────────────────────────

VALID_INDUSTRIES = ["ecommerce", "saas", "logistics", "others"]

INDUSTRY_INFO = {
    "ecommerce": {
        "name": "E-commerce",
        "description": "Online retail, marketplaces, D2C brands",
        "color": "teal",
    },
    "saas": {
        "name": "SaaS",
        "description": "Software companies, tech startups",
        "color": "blue",
    },
    "logistics": {
        "name": "Logistics",
        "description": "Shipping, warehousing, supply chain",
        "color": "orange",
    },
    "others": {
        "name": "Others",
        "description": "Finance, Education, Legal, and other industries",
        "color": "purple",
    },
}

# Industry variant data (could be moved to database later)
INDUSTRY_VARIANTS = {
    "ecommerce": [
        {
            "id": "ecom-order",
            "name": "Order Management",
            "description": "Order status, tracking, modifications",
            "tickets_per_month": 500,
            "price_per_month": 99,
            "features": [
                "Order status inquiries",
                "Tracking updates",
                "Order modifications",
                "Cancellation handling",
            ],
            "popular": True,
        },
        {
            "id": "ecom-returns",
            "name": "Returns & Refunds",
            "description": "Return requests, refund processing",
            "tickets_per_month": 200,
            "price_per_month": 49,
            "features": [
                "Return authorization",
                "Refund processing",
                "Exchange handling",
                "Store credit issuance",
            ],
            "popular": False,
        },
        {
            "id": "ecom-product",
            "name": "Product FAQ",
            "description": "Product questions, specifications",
            "tickets_per_month": 1000,
            "price_per_month": 79,
            "features": [
                "Product inquiries",
                "Specification questions",
                "Availability checks",
                "Recommendations",
            ],
            "popular": False,
        },
        {
            "id": "ecom-shipping",
            "name": "Shipping Inquiries",
            "description": "Delivery status, shipping options",
            "tickets_per_month": 300,
            "price_per_month": 59,
            "features": [
                "Shipping status",
                "Delivery estimates",
                "Carrier coordination",
                "Address changes",
            ],
            "popular": False,
        },
        {
            "id": "ecom-payment",
            "name": "Payment Issues",
            "description": "Failed payments, billing questions",
            "tickets_per_month": 150,
            "price_per_month": 39,
            "features": [
                "Payment failures",
                "Billing inquiries",
                "Invoice requests",
                "Promo code issues",
            ],
            "popular": False,
        },
    ],
    "saas": [
        {
            "id": "saas-tech",
            "name": "Technical Support",
            "description": "Bug reports, troubleshooting",
            "tickets_per_month": 400,
            "price_per_month": 129,
            "features": [
                "Bug triage",
                "Troubleshooting guides",
                "Known issues response",
                "Escalation routing",
            ],
            "popular": True,
        },
        {
            "id": "saas-billing",
            "name": "Billing Support",
            "description": "Subscription, invoice questions",
            "tickets_per_month": 200,
            "price_per_month": 69,
            "features": [
                "Subscription changes",
                "Invoice inquiries",
                "Refund requests",
                "Plan comparisons",
            ],
            "popular": False,
        },
        {
            "id": "saas-feature",
            "name": "Feature Requests",
            "description": "Feature questions, roadmap",
            "tickets_per_month": 300,
            "price_per_month": 89,
            "features": [
                "Feature inquiries",
                "Roadmap updates",
                "Workaround guidance",
                "Feedback collection",
            ],
            "popular": False,
        },
        {
            "id": "saas-api",
            "name": "API Support",
            "description": "API documentation, integration help",
            "tickets_per_month": 250,
            "price_per_month": 99,
            "features": [
                "API documentation",
                "Integration guidance",
                "Rate limit inquiries",
                "Webhook support",
            ],
            "popular": False,
        },
        {
            "id": "saas-account",
            "name": "Account Issues",
            "description": "Login, permissions, settings",
            "tickets_per_month": 350,
            "price_per_month": 79,
            "features": [
                "Account recovery",
                "Permission issues",
                "Settings help",
                "Team management",
            ],
            "popular": False,
        },
    ],
    "logistics": [
        {
            "id": "log-track",
            "name": "Tracking",
            "description": "Shipment tracking, status updates",
            "tickets_per_month": 800,
            "price_per_month": 89,
            "features": [
                "Real-time tracking",
                "Status notifications",
                "Exception alerts",
                "POD management",
            ],
            "popular": True,
        },
        {
            "id": "log-delivery",
            "name": "Delivery Issues",
            "description": "Missed deliveries, rescheduling",
            "tickets_per_month": 400,
            "price_per_month": 69,
            "features": [
                "Rescheduling",
                "Address corrections",
                "Redelivery requests",
                "Special instructions",
            ],
            "popular": False,
        },
        {
            "id": "log-warehouse",
            "name": "Warehouse Queries",
            "description": "Inventory, storage questions",
            "tickets_per_month": 300,
            "price_per_month": 59,
            "features": [
                "Inventory checks",
                "Storage inquiries",
                "Pick/pack status",
                "Stock alerts",
            ],
            "popular": False,
        },
        {
            "id": "log-fleet",
            "name": "Fleet Management",
            "description": "Driver coordination, vehicle issues",
            "tickets_per_month": 200,
            "price_per_month": 79,
            "features": [
                "Driver scheduling",
                "Vehicle status",
                "Route inquiries",
                "Maintenance alerts",
            ],
            "popular": False,
        },
        {
            "id": "log-customs",
            "name": "Customs & Documentation",
            "description": "Import/export, paperwork",
            "tickets_per_month": 150,
            "price_per_month": 99,
            "features": [
                "Customs clearance",
                "Document requests",
                "Compliance help",
                "Duty inquiries",
            ],
            "popular": False,
        },
    ],
    "others": [
        {
            "id": "other-general",
            "name": "General Support",
            "description": "General customer inquiries",
            "tickets_per_month": 500,
            "price_per_month": 79,
            "features": [
                "General inquiries",
                "Information requests",
                "Basic troubleshooting",
                "Call routing",
            ],
            "popular": True,
        },
        {
            "id": "other-email",
            "name": "Email Support",
            "description": "Email-based ticket handling",
            "tickets_per_month": 300,
            "price_per_month": 49,
            "features": [
                "Email triage",
                "Auto-responses",
                "Follow-up emails",
                "Template responses",
            ],
            "popular": False,
        },
        {
            "id": "other-chat",
            "name": "Chat Support",
            "description": "Live chat ticket handling",
            "tickets_per_month": 400,
            "price_per_month": 69,
            "features": [
                "Chat routing",
                "Quick responses",
                "Handoff protocols",
                "Chat transcripts",
            ],
            "popular": False,
        },
        {
            "id": "other-phone",
            "name": "Phone Support",
            "description": "Phone call ticket creation",
            "tickets_per_month": 200,
            "price_per_month": 89,
            "features": [
                "Call logging",
                "Callback scheduling",
                "Voicemail handling",
                "Call notes",
            ],
            "popular": False,
        },
    ],
}


# ── Schemas ─────────────────────────────────────────────────────────


class IndustryResponse(BaseModel):
    """Industry info response."""

    id: str = Field(..., description="Industry identifier")
    name: str = Field(..., description="Industry display name")
    description: str = Field(..., description="Industry description")
    color: str = Field(..., description="Theme color for UI")


class VariantResponse(BaseModel):
    """Pricing variant response."""

    id: str = Field(..., description="Variant identifier")
    name: str = Field(..., description="Variant display name")
    description: str = Field(..., description="Variant description")
    tickets_per_month: int = Field(..., ge=0, description="Monthly ticket allowance")
    price_per_month: int = Field(..., ge=0, description="Monthly price in USD")
    features: List[str] = Field(default_factory=list, description="Included features")
    popular: bool = Field(default=False, description="Is this a popular/recommended variant?")


class CalculateRequest(BaseModel):
    """Calculate pricing request."""

    industry: str = Field(..., description="Industry identifier")
    variants: List[dict] = Field(
        ...,
        description="List of {id, quantity} objects",
    )

    @validator("industry")
    def validate_industry(cls, v: str) -> str:
        if v not in VALID_INDUSTRIES:
            raise ValueError(f"Invalid industry. Must be one of: {VALID_INDUSTRIES}")
        return v

    @validator("variants")
    def validate_variants(cls, v: List[dict]) -> List[dict]:
        if not v:
            raise ValueError("At least one variant is required")
        for item in v:
            if "id" not in item:
                raise ValueError("Each variant must have an 'id'")
            if "quantity" not in item:
                raise ValueError("Each variant must have a 'quantity'")
            if not isinstance(item["quantity"], int) or item["quantity"] < 0:
                raise ValueError("Quantity must be a non-negative integer")
            if item["quantity"] > 10:
                raise ValueError("Quantity cannot exceed 10 per variant")
        return v


class VariantSummary(BaseModel):
    """Summary of a selected variant."""

    id: str
    name: str
    quantity: int
    tickets_per_month: int
    price_per_month: int


class CalculateResponse(BaseModel):
    """Calculate pricing response."""

    industry: str
    variants: List[VariantSummary]
    total_tickets: int = Field(..., ge=0, description="Total monthly tickets")
    total_monthly: int = Field(..., ge=0, description="Total monthly cost in USD")
    annual_cost: int = Field(..., ge=0, description="Annual cost in USD")
    annual_savings: int = Field(..., ge=0, description="Savings with annual billing")


# ── Endpoints ───────────────────────────────────────────────────────


@router.get("/industries", response_model=List[IndustryResponse])
def get_industries() -> List[IndustryResponse]:
    """Get list of available industries.

    Returns all 4 supported industries with their metadata.
    """
    return [
        IndustryResponse(
            id=industry_id,
            name=info["name"],
            description=info["description"],
            color=info["color"],
        )
        for industry_id, info in INDUSTRY_INFO.items()
    ]


@router.get("/variants/{industry}", response_model=List[VariantResponse])
def get_variants(industry: str) -> List[VariantResponse]:
    """Get pricing variants for a specific industry.

    Args:
        industry: Industry identifier (ecommerce, saas, logistics, others)

    Returns:
        List of available variants for the industry

    Raises:
        404: If industry is not found
    """
    if industry not in VALID_INDUSTRIES:
        raise HTTPException(
            status_code=404,
            detail=f"Industry '{industry}' not found. Valid industries: {VALID_INDUSTRIES}",
        )

    variants = INDUSTRY_VARIANTS.get(industry, [])
    return [
        VariantResponse(
            id=v["id"],
            name=v["name"],
            description=v["description"],
            tickets_per_month=v["tickets_per_month"],
            price_per_month=v["price_per_month"],
            features=v["features"],
            popular=v.get("popular", False),
        )
        for v in variants
    ]


@router.post("/calculate", response_model=CalculateResponse)
def calculate_pricing(body: CalculateRequest) -> CalculateResponse:
    """Calculate total pricing for selected variants.

    Validates that all variant IDs belong to the specified industry
    and calculates totals.

    Args:
        body: CalculateRequest with industry and variant selections

    Returns:
        CalculateResponse with totals and breakdown

    Raises:
        400: If variant IDs don't match industry
    """
    # Get valid variant IDs for this industry
    industry_variants = INDUSTRY_VARIANTS.get(body.industry, [])
    valid_ids = {v["id"]: v for v in industry_variants}

    # Validate all variant IDs
    for item in body.variants:
        if item["id"] not in valid_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Variant '{item['id']}' not found in industry '{body.industry}'",
            )

    # Calculate totals
    variant_summaries = []
    total_tickets = 0
    total_monthly = 0

    for item in body.variants:
        if item["quantity"] <= 0:
            continue

        variant = valid_ids[item["id"]]
        qty = item["quantity"]

        tickets = variant["tickets_per_month"] * qty
        price = variant["price_per_month"] * qty

        total_tickets += tickets
        total_monthly += price

        variant_summaries.append(
            VariantSummary(
                id=variant["id"],
                name=variant["name"],
                quantity=qty,
                tickets_per_month=tickets,
                price_per_month=price,
            )
        )

    # Calculate annual (with 2 months free)
    annual_cost = total_monthly * 10
    annual_savings = total_monthly * 2

    return CalculateResponse(
        industry=body.industry,
        variants=variant_summaries,
        total_tickets=total_tickets,
        total_monthly=total_monthly,
        annual_cost=annual_cost,
        annual_savings=annual_savings,
    )


# ── GAP-6-3 Fix: Validate Endpoint ───────────────────────────────────


class ValidateRequest(BaseModel):
    """Validate pricing selection request (GAP-6-3)."""

    industry: str = Field(..., description="Industry identifier")
    variants: List[dict] = Field(
        ...,
        description="List of {id, quantity} objects",
    )
    # For "others" industry
    other_industry_name: Optional[str] = Field(None, description="Custom industry name")
    company_name: Optional[str] = Field(None, description="Company name")
    company_website: Optional[str] = Field(None, description="Company website")

    @validator("industry")
    def validate_industry(cls, v: str) -> str:
        if v not in VALID_INDUSTRIES:
            raise ValueError(f"Invalid industry. Must be one of: {VALID_INDUSTRIES}")
        return v

    @validator("variants")
    def validate_variants(cls, v: List[dict]) -> List[dict]:
        if not v:
            raise ValueError("At least one variant is required")
        for item in v:
            if "id" not in item:
                raise ValueError("Each variant must have an 'id'")
            if "quantity" not in item:
                raise ValueError("Each variant must have a 'quantity'")
            if not isinstance(item["quantity"], int) or item["quantity"] < 0:
                raise ValueError("Quantity must be a non-negative integer")
            if item["quantity"] > 10:
                raise ValueError("Quantity cannot exceed 10 per variant")
        return v

    @validator("other_industry_name")
    def validate_other_industry_name(cls, v: Optional[str], values: dict) -> Optional[str]:
        if values.get("industry") == "others" and not v:
            raise ValueError("other_industry_name is required for 'others' industry")
        if v:
            return sanitize_input(v, max_length=100)
        return v

    @validator("company_name")
    def validate_company_name(cls, v: Optional[str], values: dict) -> Optional[str]:
        if values.get("industry") == "others" and not v:
            raise ValueError("company_name is required for 'others' industry")
        if v:
            return sanitize_input(v, max_length=100)
        return v

    @validator("company_website")
    def validate_company_website(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return validate_url(v)
        return v


class ValidateResponse(BaseModel):
    """Validated pricing selection response with signed token."""

    valid: bool = Field(..., description="Is the selection valid?")
    industry: str
    variants: List[VariantSummary]
    total_tickets: int
    total_monthly: int
    annual_cost: int
    annual_savings: int
    # For "others" industry
    other_industry_name: Optional[str] = None
    company_name: Optional[str] = None
    company_website: Optional[str] = None
    # Server-side validation token (GAP-6-1, GAP-6-3)
    validation_token: str = Field(..., description="Signed token for checkout")
    expires_at: int = Field(..., description="Token expiration timestamp (epoch)")


# Simple signing key (in production, use proper secret management)
PRICING_SIGNING_KEY = "parwa_pricing_validation_key_v1"
TOKEN_VALIDITY_SECONDS = 3600  # 1 hour


def _generate_validation_token(data: dict) -> tuple[str, int]:
    """Generate a signed validation token.
    
    Creates an HMAC signature of the pricing data with expiration.
    """
    expires_at = int(time.time()) + TOKEN_VALIDITY_SECONDS
    
    # Create signature payload
    payload = f"{data['industry']}:{data['total_monthly']}:{expires_at}"
    for v in data["variants"]:
        payload += f":{v['id']}:{v['quantity']}"
    
    # Generate HMAC signature
    signature = hmac.new(
        PRICING_SIGNING_KEY.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    
    # Token format: signature:expires_at
    token = f"{signature}:{expires_at}"
    return token, expires_at


@router.post("/validate", response_model=ValidateResponse)
def validate_pricing(body: ValidateRequest) -> ValidateResponse:
    """Validate and sign pricing selection (GAP-6-3 fix).
    
    This endpoint:
    1. Validates the pricing selection server-side
    2. Sanitizes user inputs (GAP-6-4, GAP-6-5)
    3. Generates a signed token for checkout
    4. Returns validated pricing with token
    
    The checkout flow should use the validation_token, not client-side data,
    to ensure pricing integrity.
    """
    # Get valid variant IDs for this industry
    industry_variants = INDUSTRY_VARIANTS.get(body.industry, [])
    valid_ids = {v["id"]: v for v in industry_variants}

    # Validate all variant IDs belong to the industry
    for item in body.variants:
        if item["id"] not in valid_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Variant '{item['id']}' not found in industry '{body.industry}'",
            )

    # Calculate totals (server-side, not trusting client)
    variant_summaries = []
    total_tickets = 0
    total_monthly = 0

    for item in body.variants:
        if item["quantity"] <= 0:
            continue

        variant = valid_ids[item["id"]]
        qty = item["quantity"]

        tickets = variant["tickets_per_month"] * qty
        price = variant["price_per_month"] * qty

        total_tickets += tickets
        total_monthly += price

        variant_summaries.append(
            VariantSummary(
                id=variant["id"],
                name=variant["name"],
                quantity=qty,
                tickets_per_month=tickets,
                price_per_month=price,
            )
        )

    # Validate at least one variant selected
    if not variant_summaries:
        raise HTTPException(
            status_code=400,
            detail="At least one variant must have quantity > 0",
        )

    # Calculate annual
    annual_cost = total_monthly * 10
    annual_savings = total_monthly * 2

    # Generate validation token
    token_data = {
        "industry": body.industry,
        "variants": [{"id": v.id, "quantity": v.quantity} for v in variant_summaries],
        "total_monthly": total_monthly,
    }
    validation_token, expires_at = _generate_validation_token(token_data)

    return ValidateResponse(
        valid=True,
        industry=body.industry,
        variants=variant_summaries,
        total_tickets=total_tickets,
        total_monthly=total_monthly,
        annual_cost=annual_cost,
        annual_savings=annual_savings,
        other_industry_name=body.other_industry_name,
        company_name=body.company_name,
        company_website=body.company_website,
        validation_token=validation_token,
        expires_at=expires_at,
    )
