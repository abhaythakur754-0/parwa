"""
Generic API Executor — ONE function that calls ANY HTTP API.

This replaces ALL hardcoded functions (_execute_real_refund, etc).
The LLM decides what to call, this function executes it.

How it works:
  1. LLM says: "Call POST https://api.stripe.com/v1/refunds with {amount: 14900}"
  2. Executor loads the tenant's credentials for that integration
  3. Executor calls the API (httpx.request)
  4. Returns the result to the LLM

This is the "n8n type" executor — generic, works for ANY API.
No per-feature code needed.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("parwa.generic_executor")

HTTP_TIMEOUT = 30.0


async def execute_api_call(
    tenant_id: str,
    integration_type: str,
    method: str,
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute ANY API call using the tenant's stored credentials.

    Args:
        tenant_id: The tenant's company_id (for credential lookup)
        integration_type: Which integration to use (e.g. "stripe", "razorpay", "shopify")
        method: HTTP method (GET, POST, PUT, DELETE, PATCH)
        endpoint: API endpoint path (e.g. "/v1/refunds" or "/admin/orders/ORD-9999.json")
        params: Query parameters (optional)
        body: Request body (optional, for POST/PUT/PATCH)

    Returns:
        Dict with: success (bool), status_code (int), data (dict), error (str)

    Example:
        result = await execute_api_call(
            tenant_id="company_123",
            integration_type="stripe",
            method="POST",
            endpoint="/v1/refunds",
            body={"amount": 14900, "reason": "requested_by_customer"},
        )
        → Calls POST https://api.stripe.com/v1/refunds with Stripe auth
        → Returns {"success": True, "data": {"id": "re_xxx", "status": "succeeded"}}
    """
    try:
        # ── Load the tenant's credentials for this integration ──
        from database.base import SessionLocal
        from app.services.integration_service import IntegrationService

        db = SessionLocal()
        try:
            service = IntegrationService(db)
            creds = service.get_credential_config(tenant_id, integration_type)

            if not creds:
                return {
                    "success": False,
                    "error": f"Integration '{integration_type}' not connected. "
                             f"Connect it in Settings → Integrations.",
                    "status_code": 0,
                    "data": None,
                }

            # ── Build the request based on integration type ──
            url, headers, request_body = _build_request(
                integration_type, creds, method, endpoint, body
            )

            if not url:
                return {
                    "success": False,
                    "error": f"Unknown integration type: {integration_type}. "
                             f"Cannot build request.",
                    "status_code": 0,
                    "data": None,
                }

            logger.info(
                "generic_executor_call tenant=%s integration=%s method=%s url=%s",
                tenant_id, integration_type, method, url[:80],
            )

            # ── Execute the API call ──
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.request(
                    method=method.upper(),
                    url=url,
                    headers=headers,
                    params=params,
                    json=request_body if request_body and method.upper() != "GET" else None,
                    data=request_body if integration_type in ("stripe", "razorpay") and method.upper() != "GET" else None,
                )

            # ── Parse response ──
            try:
                response_data = response.json()
            except Exception:
                response_data = {"raw": response.text[:500]}

            success = response.status_code < 400

            logger.info(
                "generic_executor_result tenant=%s integration=%s status=%d success=%s",
                tenant_id, integration_type, response.status_code, success,
            )

            return {
                "success": success,
                "status_code": response.status_code,
                "data": response_data,
                "error": None if success else str(response_data.get("error", {}).get("message", response.text[:200])),
            }

        finally:
            db.close()

    except Exception as exc:
        logger.error(
            "generic_executor_error tenant=%s integration=%s error=%s",
            tenant_id, integration_type, str(exc)[:300],
        )
        return {
            "success": False,
            "error": str(exc)[:300],
            "status_code": 0,
            "data": None,
        }


def _build_request(
    integration_type: str,
    creds: Dict[str, Any],
    method: str,
    endpoint: str,
    body: Optional[Dict[str, Any]],
) -> tuple:
    """Build the URL + headers + body for a specific integration.

    Returns (url, headers, body) or (None, None, None) if unknown integration.

    Supported integrations:
      - stripe: api.stripe.com, Bearer auth, form-encoded body
      - razorpay: api.razorpay.com, Basic auth (key_id:key_secret)
      - shopify: {shop}.myshopify.com, X-Shopify-Access-Token header
      - twilio: api.twilio.com, Basic auth (sid:token)
      - brevo: api.brevo.com, api-key header
      - custom: uses base_url from creds
    """
    integration = integration_type.lower()
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    request_body = body

    # ── Stripe ──
    if integration == "stripe":
        api_key = creds.get("api_key", "")
        url = f"https://api.stripe.com{endpoint}"
        headers["Authorization"] = f"Bearer {api_key}"
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        # Stripe uses form-encoded, not JSON — convert body
        if body and method.upper() != "GET":
            request_body = body  # httpx will encode as form data
        return url, headers, request_body

    # ── Razorpay ──
    if integration == "razorpay":
        key_id = creds.get("key_id", creds.get("api_key", ""))
        key_secret = creds.get("key_secret", creds.get("api_secret", ""))
        url = f"https://api.razorpay.com{endpoint}"
        import base64
        auth_str = f"{key_id}:{key_secret}"
        encoded = base64.b64encode(auth_str.encode()).decode()
        headers["Authorization"] = f"Basic {encoded}"
        return url, headers, request_body

    # ── Shopify ──
    if integration == "shopify":
        shop_domain = creds.get("shop_domain", "")
        access_token = creds.get("access_token", "")
        url = f"https://{shop_domain}/admin{endpoint}"
        headers["X-Shopify-Access-Token"] = access_token
        return url, headers, request_body

    # ── Twilio ──
    if integration == "twilio":
        account_sid = creds.get("account_sid", "")
        auth_token = creds.get("auth_token", "")
        url = f"https://api.twilio.com{endpoint}"
        import base64
        auth_str = f"{account_sid}:{auth_token}"
        encoded = base64.b64encode(auth_str.encode()).decode()
        headers["Authorization"] = f"Basic {encoded}"
        return url, headers, request_body

    # ── Brevo ──
    if integration == "brevo":
        api_key = creds.get("api_key", "")
        url = f"https://api.brevo.com{endpoint}"
        headers["api-key"] = api_key
        return url, headers, request_body

    # ── Custom connector (tenant-defined) ──
    if integration in ("custom", "custom_api", "custom_connector"):
        base_url = creds.get("endpoint", creds.get("base_url", ""))
        api_key = creds.get("api_key", "")
        auth_type = creds.get("auth_type", "bearer")

        # Build endpoint URL
        if not endpoint.startswith("http"):
            url = f"{base_url}{endpoint}"
        else:
            url = endpoint

        # Build auth headers based on auth_type
        if auth_type == "bearer":
            headers["Authorization"] = f"Bearer {api_key}"
        elif auth_type == "api_key_header":
            header_name = creds.get("header_name", "X-API-Key")
            headers[header_name] = api_key
        elif auth_type == "basic_auth":
            import base64
            username = creds.get("username", "")
            password = creds.get("password", "")
            auth_str = f"{username}:{password}"
            encoded = base64.b64encode(auth_str.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"

        return url, headers, request_body

    # ── Unknown integration ──
    logger.warning("unknown_integration_type: %s", integration)
    return None, None, None


async def list_available_actions(tenant_id: str) -> Dict[str, Any]:
    """List all connected integrations + their available actions for a tenant.

    This is what the LLM sees to decide what tools it can use.

    Returns:
        {
            "stripe": {"connected": True, "actions": ["refund", "charge", "invoice", ...]},
            "shopify": {"connected": True, "actions": ["get_order", "cancel_order", ...]},
            "twilio": {"connected": True, "actions": ["send_sms", "make_call", ...]},
        }
    """
    try:
        from database.base import SessionLocal
        from app.services.integration_service import IntegrationService

        db = SessionLocal()
        try:
            service = IntegrationService(db)

            # Known integrations + their common actions
            integration_actions = {
                "stripe": {
                    "endpoints": [
                        "POST /v1/refunds — Process a refund",
                        "GET /v1/charges — List charges",
                        "GET /v1/customers/{id} — Get customer details",
                        "POST /v1/customers/{id}/balance_transactions — Apply credit",
                        "GET /v1/invoices — List invoices",
                        "DELETE /v1/subscriptions/{id} — Cancel subscription",
                        "POST /v1/subscriptions — Create subscription",
                    ],
                },
                "razorpay": {
                    "endpoints": [
                        "POST /v1/payments/{id}/refund — Process a refund",
                        "GET /v1/payments — List payments",
                        "GET /v1/invoices — List invoices",
                        "POST /v1/customers — Create customer",
                        "DELETE /v1/subscriptions/{id} — Cancel subscription",
                    ],
                },
                "shopify": {
                    "endpoints": [
                        "GET /api/2024-01/orders/{id}.json — Get order details",
                        "POST /api/2024-01/orders/{id}/cancel.json — Cancel order",
                        "GET /api/2024-01/orders.json — List orders",
                        "PUT /api/2024-01/orders/{id}.json — Update order (shipping address)",
                        "GET /api/2024-01/customers/{id}.json — Get customer details",
                    ],
                },
                "twilio": {
                    "endpoints": [
                        "POST /2010-04-01/Accounts/{sid}/Messages.json — Send SMS",
                        "POST /2010-04-01/Accounts/{sid}/Calls.json — Make voice call",
                    ],
                },
                "brevo": {
                    "endpoints": [
                        "POST /v3/smtp/email — Send email",
                        "GET /v3/contacts — List contacts",
                        "POST /v3/contacts — Create contact",
                    ],
                },
                "custom": {
                    "endpoints": [
                        "Any endpoint defined by the tenant's custom connector",
                    ],
                },
            }

            result = {}
            for integ_type in integration_actions.keys():
                creds = service.get_credential_config(tenant_id, integ_type)
                if creds:
                    result[integ_type] = {
                        "connected": True,
                        "actions": integration_actions[integ_type]["endpoints"],
                    }

            return result

        finally:
            db.close()

    except Exception as exc:
        logger.error("list_available_actions error: %s", str(exc)[:200])
        return {}
