"""
Paddle API Client (BC-002, BG-05)

Implements the official Paddle API for:
- Subscription management (create, get, update, cancel)
- Customer management
- Transaction/invoice retrieval
- Price/variant information

API Docs: https://developer.paddle.com/api-reference/overview

Features:
- Automatic retry with exponential backoff
- Rate limiting compliance
- HMAC signature verification for webhooks
- Sandbox/Production mode switching
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx

from app.config import get_settings

logger = logging.getLogger("parwa.clients.paddle")

# Paddle API base URLs
PADDLE_SANDBOX_URL = "https://sandbox-api.paddle.com/"
PADDLE_PRODUCTION_URL = "https://api.paddle.com/"

# Rate limiting: Paddle allows 500 requests/minute
RATE_LIMIT_REQUESTS = 500
RATE_LIMIT_WINDOW = 60  # seconds

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds
RETRY_MAX_DELAY = 30


class PaddleError(Exception):
    """Base exception for Paddle API errors."""
    pass


class PaddleAuthError(PaddleError):
    """Authentication error (401/403)."""
    pass


class PaddleRateLimitError(PaddleError):
    """Rate limit exceeded (429)."""
    pass


class PaddleNotFoundError(PaddleError):
    """Resource not found (404)."""
    pass


class PaddleValidationError(PaddleError):
    """Validation error (400/422)."""
    pass


class PaddleClient:
    """
    Paddle API Client for subscription and billing management.

    Usage:
        client = get_paddle_client()
        subscription = await client.get_subscription("sub_123")
    """

    def __init__(
        self,
        api_key: str,
        client_token: Optional[str] = None,
        sandbox: bool = True,
        webhook_secret: Optional[str] = None,
    ):
        self.api_key = api_key
        self.client_token = client_token
        self.sandbox = sandbox
        self.webhook_secret = webhook_secret
        self.base_url = PADDLE_SANDBOX_URL if sandbox else PADDLE_PRODUCTION_URL

        # Rate limiting state
        self._request_times: List[float] = []
        self._rate_limit_wait: float = 0

        # HTTP client (created lazily)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _check_rate_limit(self) -> None:
        """Check and enforce rate limiting.

        NOTE: This is a synchronous pre-check. Actual waiting happens
        asynchronously in _request() to avoid blocking the event loop.
        """
        now = time.time()
        # Remove requests outside the window
        self._request_times = [
            t for t in self._request_times
            if now - t < RATE_LIMIT_WINDOW
        ]
        if len(self._request_times) >= RATE_LIMIT_REQUESTS:
            # Mark that we need to wait — actual wait in _request()
            wait_time = RATE_LIMIT_WINDOW - (now - self._request_times[0]) + 1
            logger.warning("paddle_rate_limit_wait seconds=%d", wait_time)
            self._rate_limit_wait = wait_time
        else:
            self._rate_limit_wait = 0
        self._request_times.append(now)

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to Paddle API.

        Includes automatic retry with exponential backoff.
        All sleeps use asyncio.sleep() to avoid blocking the event loop.
        """
        self._check_rate_limit()

        # Async rate limit wait (non-blocking)
        if self._rate_limit_wait > 0:
            await asyncio.sleep(self._rate_limit_wait)
            self._rate_limit_wait = 0

        url = urljoin(self.base_url, endpoint)
        client = await self._get_client()

        last_error: Optional[Exception] = None

        for attempt in range(MAX_RETRIES):
            try:
                response = await client.request(method, url, **kwargs)

                # Success
                if response.status_code < 400:
                    return response.json()

                # Handle specific errors
                if response.status_code == 401:
                    raise PaddleAuthError("Invalid API key")
                if response.status_code == 403:
                    raise PaddleAuthError("Permission denied")
                if response.status_code == 404:
                    raise PaddleNotFoundError(f"Not found: {endpoint}")
                if response.status_code == 422:
                    error_data = response.json()
                    raise PaddleValidationError(
                        error_data.get("error", {}).get("message", "Validation failed")
                    )
                if response.status_code == 429:
                    # Rate limited - wait and retry (non-blocking)
                    retry_after = int(response.headers.get("Retry-After", RETRY_BASE_DELAY))
                    logger.warning("paddle_rate_limited retry_after=%d", retry_after)
                    await asyncio.sleep(retry_after)
                    continue

                # Other errors - retry for 5xx
                if response.status_code >= 500:
                    last_error = PaddleError(f"Server error: {response.status_code}")
                else:
                    last_error = PaddleError(f"API error: {response.status_code}")

            except httpx.TimeoutException as e:
                last_error = PaddleError(f"Request timeout: {e}")
            except httpx.RequestError as e:
                last_error = PaddleError(f"Request failed: {e}")

            # Exponential backoff before retry (non-blocking)
            if attempt < MAX_RETRIES - 1:
                delay = min(RETRY_BASE_DELAY * (2 ** attempt), RETRY_MAX_DELAY)
                logger.warning(
                    "paddle_retry attempt=%d delay=%d error=%s",
                    attempt + 1,
                    delay,
                    str(last_error),
                )
                await asyncio.sleep(delay)

        raise last_error or PaddleError("Unknown error")

    # ── Subscription Methods ─────────────────────────────────────────

    async def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Get subscription details by ID.

        API: GET /subscriptions/{subscription_id}
        """
        return await self._request("GET", f"/subscriptions/{subscription_id}")

    async def list_subscriptions(
        self,
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
        per_page: int = 50,
        after: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List subscriptions with optional filters.

        API: GET /subscriptions
        """
        params: Dict[str, Any] = {"per_page": per_page}
        if customer_id:
            params["customer_id"] = customer_id
        if status:
            params["status"] = status
        if after:
            params["after"] = after

        return await self._request("GET", "/subscriptions", params=params)

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        quantity: int = 1,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Create a new subscription.

        API: POST /subscriptions

        Args:
            customer_id: Paddle customer ID
            price_id: Paddle price/variant ID
            quantity: Number of seats/units
        """
        data = {
            "customer_id": customer_id,
            "items": [{"price_id": price_id, "quantity": quantity}],
            **kwargs,
        }
        return await self._request("POST", "/subscriptions", json=data)

    async def update_subscription(
        self,
        subscription_id: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Update subscription (plan change, etc.).

        API: PATCH /subscriptions/{subscription_id}
        """
        return await self._request(
            "PATCH", f"/subscriptions/{subscription_id}", json=kwargs
        )

    async def cancel_subscription(
        self,
        subscription_id: str,
        effective_from: str = "next_billing_period",
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Cancel a subscription.

        API: POST /subscriptions/{subscription_id}/cancel

        Args:
            subscription_id: Paddle subscription ID
            effective_from: When to cancel ("immediately" or "next_billing_period")
            reason: Optional cancellation reason
        """
        data = {"effective_from": effective_from}
        if reason:
            data["reason"] = reason
        return await self._request(
            "POST", f"/subscriptions/{subscription_id}/cancel", json=data
        )

    async def pause_subscription(
        self,
        subscription_id: str,
        resume_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Pause a subscription.

        API: POST /subscriptions/{subscription_id}/pause
        """
        data = {}
        if resume_at:
            data["resume_at"] = resume_at
        return await self._request(
            "POST", f"/subscriptions/{subscription_id}/pause", json=data
        )

    async def resume_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Resume a paused subscription.

        API: POST /subscriptions/{subscription_id}/resume
        """
        return await self._request(
            "POST", f"/subscriptions/{subscription_id}/resume", json={}
        )

    # ── Customer Methods ─────────────────────────────────────────────

    async def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """
        Get customer details by ID.

        API: GET /customers/{customer_id}
        """
        return await self._request("GET", f"/customers/{customer_id}")

    async def list_customers(
        self,
        email: Optional[str] = None,
        per_page: int = 50,
        after: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List customers with optional filters.

        API: GET /customers
        """
        params: Dict[str, Any] = {"per_page": per_page}
        if email:
            params["email"] = email
        if after:
            params["after"] = after

        return await self._request("GET", "/customers", params=params)

    async def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Create a new customer.

        API: POST /customers
        """
        data = {"email": email, **kwargs}
        if name:
            data["name"] = name
        return await self._request("POST", "/customers", json=data)

    # ── Transaction Methods ───────────────────────────────────────────

    async def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """
        Get transaction details by ID.

        API: GET /transactions/{transaction_id}
        """
        return await self._request("GET", f"/transactions/{transaction_id}")

    async def list_transactions(
        self,
        subscription_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
        per_page: int = 50,
        after: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List transactions with optional filters.

        API: GET /transactions
        """
        params: Dict[str, Any] = {"per_page": per_page}
        if subscription_id:
            params["subscription_id"] = subscription_id
        if customer_id:
            params["customer_id"] = customer_id
        if status:
            params["status"] = status
        if after:
            params["after"] = after

        return await self._request("GET", "/transactions", params=params)

    async def create_transaction(
        self,
        customer_id: str,
        items: List[Dict[str, Any]],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Create a one-time transaction (charge) in Paddle.

        API: POST /transactions

        Args:
            customer_id: Paddle customer ID
            items: List of {"price_id": str, "quantity": int} dicts
        """
        data = {
            "customer_id": customer_id,
            "items": items,
            **kwargs,
        }
        return await self._request("POST", "/transactions", json=data)

    # ── Price Methods ────────────────────────────────────────────────

    async def get_price(self, price_id: str) -> Dict[str, Any]:
        """
        Get price/variant details by ID.

        API: GET /prices/{price_id}
        """
        return await self._request("GET", f"/prices/{price_id}")

    async def list_prices(
        self,
        product_id: Optional[str] = None,
        per_page: int = 50,
        after: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List prices with optional filters.

        API: GET /prices
        """
        params: Dict[str, Any] = {"per_page": per_page}
        if product_id:
            params["product_id"] = product_id
        if after:
            params["after"] = after

        return await self._request("GET", "/prices", params=params)

    # ── Invoice Methods ───────────────────────────────────────────────

    async def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """
        Get invoice details by ID.

        API: GET /invoices/{invoice_id}
        """
        return await self._request("GET", f"/invoices/{invoice_id}")

    async def get_invoice_pdf(self, invoice_id: str) -> bytes:
        """
        Download invoice PDF.

        API: GET /invoices/{invoice_id}/pdf
        """
        url = urljoin(self.base_url, f"/invoices/{invoice_id}/pdf")
        client = await self._get_client()

        response = await client.request("GET", url)
        response.raise_for_status()
        return response.content

    async def list_invoices(
        self,
        subscription_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
        per_page: int = 50,
        after: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List invoices with optional filters.

        API: GET /invoices
        """
        params: Dict[str, Any] = {"per_page": per_page}
        if subscription_id:
            params["subscription_id"] = subscription_id
        if customer_id:
            params["customer_id"] = customer_id
        if status:
            params["status"] = status
        if after:
            params["after"] = after

        return await self._request("GET", "/invoices", params=params)

    # ── Report Methods ───────────────────────────────────────────────

    async def get_report(self, report_id: str) -> Dict[str, Any]:
        """
        Get report details by ID.

        API: GET /reports/{report_id}
        """
        return await self._request("GET", f"/reports/{report_id}")

    # ── Webhook Verification ───────────────────────────────────────────

    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
    ) -> bool:
        """
        Verify Paddle webhook signature using HMAC-SHA256.

        Paddle Billing API uses the format: ts={timestamp};h1={hash}
        The hash is HMAC-SHA256 of '{timestamp}:{payload}' using the
        webhook secret as the key.

        We also reject signatures older than 5 minutes to prevent
        replay attacks.

        Args:
            payload: Raw request body bytes
            signature: Value from 'paddle_signature' header

        Returns:
            True if signature is valid and timestamp is fresh, False otherwise
        """
        if not self.webhook_secret:
            logger.warning("paddle_webhook_no_secret")
            return False

        try:
            # Parse Paddle signature format: ts={timestamp};h1={hash}
            parts = {}
            for part in signature.split(";"):
                key, _, value = part.partition("=")
                parts[key.strip()] = value.strip()

            ts_str = parts.get("ts")
            h1_hash = parts.get("h1")

            if not ts_str or not h1_hash:
                logger.warning(
                    "paddle_webhook_invalid_format sig=%s",
                    signature[:50],
                )
                return False

            # Verify timestamp is within 5 minutes (replay attack prevention)
            try:
                ts = int(ts_str)
            except ValueError:
                logger.warning(
                    "paddle_webhook_invalid_timestamp ts=%s",
                    ts_str,
                )
                return False

            current_time = int(time.time())
            if abs(current_time - ts) > 300:  # 5 minutes
                logger.warning(
                    "paddle_webhook_expired ts=%d current=%d diff=%d",
                    ts, current_time, abs(current_time - ts),
                )
                return False

            # Compute HMAC-SHA256 of '{timestamp}:{payload}'
            signed_payload = f"{ts_str}:".encode() + payload
            expected = hmac.new(
                self.webhook_secret.encode(),
                signed_payload,
                hashlib.sha256,
            ).hexdigest()

            # Use constant-time comparison to prevent timing attacks
            return hmac.compare_digest(h1_hash, expected)

        except Exception as exc:
            logger.warning(
                "paddle_webhook_verify_error error=%s",
                str(exc),
            )
            return False

    def parse_webhook_event(self, payload: bytes) -> Dict[str, Any]:
        """
        Parse and validate a webhook payload.

        Args:
            payload: Raw request body bytes

        Returns:
            Parsed event dict with keys:
            - event_type: Paddle event type
            - event_id: Unique event ID
            - occurred_at: Event timestamp
            - data: Event data
        """
        data = json.loads(payload)

        # Paddle Billing format
        return {
            "event_type": data.get("event_type", data.get("event_type")),
            "event_id": data.get("event_id", data.get("id")),
            "occurred_at": data.get("occurred_at", data.get("created_at")),
            "notification_id": data.get("notification_id"),
            "data": data.get("data", {}),
        }


# ── Factory Function ────────────────────────────────────────────────────

_paddle_client: Optional[PaddleClient] = None


def get_paddle_client() -> PaddleClient:
    """
    Get the Paddle client singleton.

    Configured from environment variables:
    - PADDLE_API_KEY: API key (required)
    - PADDLE_CLIENT_TOKEN: Client token (optional, for frontend)
    - PADDLE_WEBHOOK_SECRET: Webhook signing secret (required for webhooks)
    - ENVIRONMENT: "production" for live, anything else for sandbox
    """
    global _paddle_client

    if _paddle_client is None:
        settings = get_settings()

        # Determine sandbox mode
        sandbox = settings.ENVIRONMENT != "production"

        _paddle_client = PaddleClient(
            api_key=settings.PADDLE_API_KEY,
            client_token=settings.PADDLE_CLIENT_TOKEN,
            sandbox=sandbox,
            webhook_secret=settings.PADDLE_WEBHOOK_SECRET,
        )

        logger.info(
            "paddle_client_initialized sandbox=%s",
            sandbox,
        )

    return _paddle_client


async def close_paddle_client() -> None:
    """Close the Paddle client (for shutdown)."""
    global _paddle_client
    if _paddle_client:
        await _paddle_client.close()
        _paddle_client = None
