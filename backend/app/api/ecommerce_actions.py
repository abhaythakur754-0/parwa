"""
PARWA E-Commerce Actions Router — Real e-commerce tool invocations.

Fixes the fake-wired MCP `ecommerce_server` problem (same pattern as crm_actions):
  mcp_server/integrations/ecommerce_server.py called three backend endpoints
  that DON'T EXIST:
    POST /api/v1/integrations/ecommerce/order
    POST /api/v1/integrations/ecommerce/products
    POST /api/v1/integrations/ecommerce/customer-orders

  This router provides the three missing endpoints. They:
    1. Resolve the tenant's active e-commerce integration via IntegrationService
       (BC-001: scoped by company_id, returns None if no active integration).
    2. Call the real Shopify Admin API using the stored access_token + shop_domain
       (same credential pattern already used in integrations.py webhook registration).
    3. Return honest results: real data on success, structured "not_connected"
       status when no integration exists, "external_error" on provider failure.

  Endpoint inventory:
    POST /api/integrations/ecommerce/order           — look up order by ID
    POST /api/integrations/ecommerce/products         — search products by title
    POST /api/integrations/ecommerce/customer-orders  — list orders for a customer

BC-001: All operations scoped to authenticated user's company_id.
BC-002: Money fields returned as strings to preserve DECIMAL precision.
BC-012: No stack traces leak to clients; structured error responses.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.services.integration_service import IntegrationService
from database.base import get_db
from database.models.core import User

logger = logging.getLogger("parwa.api.ecommerce_actions")

router = APIRouter(prefix="/api/integrations/ecommerce", tags=["Integrations — E-Commerce Actions"])

# Shopify Admin API — same version used in integrations.py webhook registration.
SHOPIFY_API_VERSION = "2024-01"
SHOPIFY_TIMEOUT = 15.0


# ── Request / Response Schemas ────────────────────────────────────


class EcommerceOrderRequest(BaseModel):
    action: str = Field(default="get_order")
    platform: str = Field(default="shopify")
    order_id: str = Field(..., min_length=1)
    include_items: bool = True
    include_customer: bool = False
    company_id: Optional[str] = None  # Ignored — BC-001 always uses auth user's company.


class EcommerceProductsRequest(BaseModel):
    action: str = Field(default="search_products")
    platform: str = Field(default="shopify")
    query: str = Field(..., min_length=1)
    limit: int = Field(default=10, ge=1, le=250)  # Shopify page size cap is 250.
    company_id: Optional[str] = None


class EcommerceCustomerOrdersRequest(BaseModel):
    action: str = Field(default="get_customer_orders")
    platform: str = Field(default="shopify")
    customer_id: str = Field(..., min_length=1)
    limit: int = Field(default=20, ge=1, le=250)
    company_id: Optional[str] = None


class EcommerceActionResponse(BaseModel):
    """Standard response. Status: ok | not_connected | not_found | external_error."""

    status: str
    platform: str
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


# ── Credential resolution ─────────────────────────────────────────


def _resolve_ecommerce_credentials(
    db: Session,
    user: User,
    platform: str,
) -> Optional[Dict[str, Any]]:
    """Resolve the tenant's active e-commerce integration credentials.

    BC-001: ALWAYS scoped to the authenticated user's company_id. The request
    body's `company_id` field is accepted for MCP payload compatibility but is
    NEVER trusted.
    """
    company_id = str(user.company_id)
    service = IntegrationService(db)
    platform_key = (platform or "shopify").lower().strip()
    return service.get_credential_config(company_id, platform_key)


def _shopify_headers(access_token: str) -> Dict[str, str]:
    return {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }


def _shopify_base_url(shop_domain: str) -> str:
    """Build the Shopify Admin API base URL for a shop.

    Accepts shop_domain with or without https:// and with or without .myshopify.com.
    """
    domain = shop_domain.strip().rstrip("/")
    if not domain:
        return ""
    if domain.startswith("http://"):
        domain = domain[len("http://"):]
    elif domain.startswith("https://"):
        domain = domain[len("https://"):]
    if "/" in domain:
        domain = domain.split("/")[0]
    if not domain.endswith(".myshopify.com"):
        # Strip any path-like suffix; assume the user provided just the shop name.
        if "." not in domain:
            domain = f"{domain}.myshopify.com"
    return f"https://{domain}/admin/api/{SHOPIFY_API_VERSION}"


# ── Shopify API helpers ───────────────────────────────────────────


async def _shopify_get_order(
    client: httpx.AsyncClient,
    base_url: str,
    headers: Dict[str, str],
    *,
    order_id: str,
    include_items: bool,
    include_customer: bool,
) -> Dict[str, Any]:
    """Fetch a Shopify order by ID."""
    try:
        resp = await client.get(
            f"{base_url}/orders/{order_id}.json",
            headers=headers,
            params={
                "fields": ",".join(
                    ["id", "name", "email", "created_at", "total_price", "currency", "financial_status", "fulfillment_status"]
                    + (["line_items"] if include_items else [])
                    + (["customer"] if include_customer else [])
                ),
            },
        )
    except httpx.HTTPError as exc:
        return {"status": "external_error", "data": {}, "error": f"network_error: {exc}"}
    if resp.status_code == 404:
        return {"status": "not_found", "data": {}, "error": None}
    if resp.status_code >= 400:
        return {"status": "external_error", "data": {}, "error": f"shopify_{resp.status_code}: {resp.text[:200]}"}

    order = resp.json().get("order", {}) or {}
    return {"status": "ok", "data": _shape_shopify_order(order), "error": None}


def _shape_shopify_order(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize Shopify order object to a stable response shape."""
    return {
        "order_id": str(raw.get("id", "")),
        "order_name": raw.get("name", ""),
        "email": raw.get("email", ""),
        "created_at": raw.get("created_at", ""),
        "total_price": str(raw.get("total_price", "")),  # BC-002: money as string.
        "currency": raw.get("currency", ""),
        "financial_status": raw.get("financial_status", ""),
        "fulfillment_status": raw.get("fulfillment_status", ""),
        "line_items": raw.get("line_items", []) or [],
        "customer": raw.get("customer") or None,
        "raw": raw,
    }


async def _shopify_search_products(
    client: httpx.AsyncClient,
    base_url: str,
    headers: Dict[str, str],
    *,
    query: str,
    limit: int,
) -> Dict[str, Any]:
    """Search Shopify products by title."""
    try:
        resp = await client.get(
            f"{base_url}/products.json",
            headers=headers,
            params={"title": query, "limit": limit},
        )
    except httpx.HTTPError as exc:
        return {"status": "external_error", "data": {}, "error": f"network_error: {exc}"}
    if resp.status_code >= 400:
        return {"status": "external_error", "data": {}, "error": f"shopify_{resp.status_code}: {resp.text[:200]}"}

    products = resp.json().get("products", []) or []
    shaped = [_shape_shopify_product(p) for p in products]
    return {"status": "ok", "data": {"products": shaped, "count": len(shaped)}, "error": None}


def _shape_shopify_product(raw: Dict[str, Any]) -> Dict[str, Any]:
    variants = raw.get("variants", []) or []
    return {
        "product_id": str(raw.get("id", "")),
        "title": raw.get("title", ""),
        "product_type": raw.get("product_type", ""),
        "vendor": raw.get("vendor", ""),
        "status": raw.get("status", ""),
        "variants_count": len(variants),
        "first_variant_price": str(variants[0].get("price", "")) if variants else None,
        "created_at": raw.get("created_at", ""),
    }


async def _shopify_get_customer_orders(
    client: httpx.AsyncClient,
    base_url: str,
    headers: Dict[str, str],
    *,
    customer_id: str,
    limit: int,
) -> Dict[str, Any]:
    """List Shopify orders for a customer."""
    try:
        resp = await client.get(
            f"{base_url}/customers/{customer_id}/orders.json",
            headers=headers,
            params={"limit": limit},
        )
    except httpx.HTTPError as exc:
        return {"status": "external_error", "data": {}, "error": f"network_error: {exc}"}
    if resp.status_code == 404:
        return {"status": "not_found", "data": {}, "error": None}
    if resp.status_code >= 400:
        return {"status": "external_error", "data": {}, "error": f"shopify_{resp.status_code}: {resp.text[:200]}"}

    orders = resp.json().get("orders", []) or []
    shaped = [_shape_shopify_order(o) for o in orders]
    return {"status": "ok", "data": {"orders": shaped, "count": len(shaped)}, "error": None}


# ── Endpoints ─────────────────────────────────────────────────────


@router.post("/order", response_model=EcommerceActionResponse)
async def ecommerce_get_order(
    body: EcommerceOrderRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EcommerceActionResponse:
    """Look up an e-commerce order by platform order ID."""
    creds = _resolve_ecommerce_credentials(db, user, body.platform)
    if not creds or not creds.get("access_token") or not creds.get("shop_domain"):
        return EcommerceActionResponse(
            status="not_connected",
            platform=body.platform,
            data={},
            error=f"E-commerce platform '{body.platform}' is not connected for this tenant.",
        )

    base_url = _shopify_base_url(creds["shop_domain"])
    if not base_url:
        return EcommerceActionResponse(
            status="external_error",
            platform=body.platform,
            data={},
            error="Stored shop_domain is invalid. Reconnect the Shopify integration.",
        )

    headers = _shopify_headers(creds["access_token"])
    async with httpx.AsyncClient(timeout=SHOPIFY_TIMEOUT) as client:
        result = await _shopify_get_order(
            client, base_url, headers,
            order_id=body.order_id,
            include_items=body.include_items,
            include_customer=body.include_customer,
        )
    return EcommerceActionResponse(
        status=result["status"], platform=body.platform,
        data=result["data"], error=result["error"],
    )


@router.post("/products", response_model=EcommerceActionResponse)
async def ecommerce_search_products(
    body: EcommerceProductsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EcommerceActionResponse:
    """Search for products on the connected e-commerce platform."""
    creds = _resolve_ecommerce_credentials(db, user, body.platform)
    if not creds or not creds.get("access_token") or not creds.get("shop_domain"):
        return EcommerceActionResponse(
            status="not_connected", platform=body.platform, data={},
            error=f"E-commerce platform '{body.platform}' is not connected for this tenant.",
        )

    base_url = _shopify_base_url(creds["shop_domain"])
    if not base_url:
        return EcommerceActionResponse(
            status="external_error", platform=body.platform, data={},
            error="Stored shop_domain is invalid. Reconnect the Shopify integration.",
        )

    headers = _shopify_headers(creds["access_token"])
    async with httpx.AsyncClient(timeout=SHOPIFY_TIMEOUT) as client:
        result = await _shopify_search_products(
            client, base_url, headers, query=body.query, limit=body.limit,
        )
    return EcommerceActionResponse(
        status=result["status"], platform=body.platform,
        data=result["data"], error=result["error"],
    )


@router.post("/customer-orders", response_model=EcommerceActionResponse)
async def ecommerce_get_customer_orders(
    body: EcommerceCustomerOrdersRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EcommerceActionResponse:
    """List orders for a specific e-commerce customer."""
    creds = _resolve_ecommerce_credentials(db, user, body.platform)
    if not creds or not creds.get("access_token") or not creds.get("shop_domain"):
        return EcommerceActionResponse(
            status="not_connected", platform=body.platform, data={},
            error=f"E-commerce platform '{body.platform}' is not connected for this tenant.",
        )

    base_url = _shopify_base_url(creds["shop_domain"])
    if not base_url:
        return EcommerceActionResponse(
            status="external_error", platform=body.platform, data={},
            error="Stored shop_domain is invalid. Reconnect the Shopify integration.",
        )

    headers = _shopify_headers(creds["access_token"])
    async with httpx.AsyncClient(timeout=SHOPIFY_TIMEOUT) as client:
        result = await _shopify_get_customer_orders(
            client, base_url, headers, customer_id=body.customer_id, limit=body.limit,
        )
    return EcommerceActionResponse(
        status=result["status"], platform=body.platform,
        data=result["data"], error=result["error"],
    )
