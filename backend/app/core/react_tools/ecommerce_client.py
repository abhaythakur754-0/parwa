"""
E-Commerce Client for React Tools — wires Node 5 to real Shopify data.

When a tenant has connected Shopify (via onboarding → integrations),
this client calls the real Shopify Admin API and returns real order data.

When no integration is connected, returns None — the caller (OrderTool)
then returns an honest "not connected" error instead of mock data.

Reuses:
  - IntegrationService.get_credential_config() for credential lookup
  - Same Shopify API version + URL patterns as app/api/ecommerce_actions.py
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("parwa.react_tools.ecommerce_client")

SHOPIFY_API_VERSION = "2024-01"
SHOPIFY_TIMEOUT = 15.0


def _build_shopify_base_url(shop_domain: str) -> str:
    """Build Shopify Admin API base URL from shop domain."""
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
        if "." not in domain:
            domain = f"{domain}.myshopify.com"
    return f"https://{domain}/admin/api/{SHOPIFY_API_VERSION}"


def _get_credentials(company_id: str) -> Optional[Dict[str, Any]]:
    """Look up the tenant's Shopify integration credentials.

    Returns None when no integration is connected.
    """
    try:
        from database.base import SessionLocal
        from app.services.integration_service import IntegrationService

        db = SessionLocal()
        try:
            creds = IntegrationService(db).get_credential_config(company_id, "shopify")
            if creds and creds.get("access_token") and creds.get("shop_domain"):
                return creds
            return None
        finally:
            db.close()
    except Exception as exc:
        logger.warning("credential_lookup_failed company_id=%s error=%s", company_id, str(exc)[:200])
        return None


def _shape_order(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize Shopify order to a stable response shape."""
    return {
        "order_id": str(raw.get("id", "")),
        "order_name": raw.get("name", ""),
        "email": raw.get("email", ""),
        "created_at": raw.get("created_at", ""),
        "total_price": str(raw.get("total_price", "")),
        "currency": raw.get("currency", ""),
        "financial_status": raw.get("financial_status", ""),
        "fulfillment_status": raw.get("fulfillment_status", ""),
        "line_items": raw.get("line_items", []) or [],
        "customer": raw.get("customer") or None,
    }


async def fetch_real_order(company_id: str, order_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single order from the tenant's connected Shopify store.

    Returns:
        - Dict with order data on success
        - None when Shopify is not connected OR order not found OR API error
    """
    creds = _get_credentials(company_id)
    if not creds:
        return None

    base_url = _build_shopify_base_url(creds["shop_domain"])
    if not base_url:
        return None

    headers = {
        "X-Shopify-Access-Token": creds["access_token"],
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=SHOPIFY_TIMEOUT) as client:
            resp = await client.get(
                f"{base_url}/orders/{order_id}.json",
                headers=headers,
                params={
                    "fields": "id,name,email,created_at,total_price,currency,financial_status,fulfillment_status,line_items,customer",
                },
            )
        if resp.status_code == 200:
            order = resp.json().get("order", {}) or {}
            return _shape_order(order)
        if resp.status_code == 404:
            logger.info("shopify_order_not_found order_id=%s", order_id)
            return None
        logger.warning("shopify_api_error status=%s body=%s", resp.status_code, resp.text[:200])
        return None
    except Exception as exc:
        logger.warning("shopify_call_failed order_id=%s error=%s", order_id, str(exc)[:200])
        return None


async def fetch_real_orders(
    company_id: str,
    limit: int = 10,
    status: Optional[str] = None,
) -> Optional[List[Dict[str, Any]]]:
    """Fetch a list of orders from the tenant's connected Shopify store.

    Returns:
        - List of order dicts on success
        - None when Shopify is not connected OR API error
    """
    creds = _get_credentials(company_id)
    if not creds:
        return None

    base_url = _build_shopify_base_url(creds["shop_domain"])
    if not base_url:
        return None

    headers = {
        "X-Shopify-Access-Token": creds["access_token"],
        "Content-Type": "application/json",
    }

    params: Dict[str, Any] = {"limit": min(max(limit, 1), 250)}
    if status and status != "all":
        params["financial_status"] = status

    try:
        async with httpx.AsyncClient(timeout=SHOPIFY_TIMEOUT) as client:
            resp = await client.get(
                f"{base_url}/orders.json",
                headers=headers,
                params=params,
            )
        if resp.status_code == 200:
            orders = resp.json().get("orders", []) or []
            return [_shape_order(o) for o in orders]
        logger.warning("shopify_list_error status=%s body=%s", resp.status_code, resp.text[:200])
        return None
    except Exception as exc:
        logger.warning("shopify_list_failed error=%s", str(exc)[:200])
        return None


async def is_connected(company_id: str) -> bool:
    """Check if the tenant has a Shopify integration connected."""
    return _get_credentials(company_id) is not None
