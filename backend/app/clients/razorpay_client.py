"""
Razorpay API Client — HTTP client using httpx (no SDK dependency).
Handles: create plan, create/get/cancel/update subscription, create customer, verify webhook.
"""
import base64, hashlib, hmac, logging
from typing import Any, Dict, Optional
import httpx
from app.config import get_settings

logger = logging.getLogger("parwa.clients.razorpay")
RAZORPAY_API_BASE = "https://api.razorpay.com/v1"
MAX_RETRIES = 3

class RazorpayError(Exception): pass
class RazorpayAuthError(RazorpayError): pass
class RazorpayNotFoundError(RazorpayError): pass
class RazorpayValidationError(RazorpayError): pass

class RazorpayClient:
    def __init__(self, key_id: str = "", key_secret: str = ""):
        s = get_settings()
        self.key_id = key_id or s.RAZORPAY_KEY_ID
        self.key_secret = key_secret or s.RAZORPAY_KEY_SECRET

    def _auth_header(self) -> str:
        credentials = f"{self.key_id}:{self.key_secret}"
        return f"Basic {base64.b64encode(credentials.encode()).decode()}"

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": self._auth_header(), "Content-Type": "application/json"}

    async def _request(self, method: str, path: str, json_body=None, params=None) -> Dict[str, Any]:
        url = f"{RAZORPAY_API_BASE}{path}"
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.request(method=method, url=url, headers=self._headers(), json=json_body, params=params)
                if response.status_code < 400:
                    return response.json()
                try:
                    err_body = response.json()
                    err_msg = err_body.get("error", {}).get("description", response.text)
                except Exception:
                    err_msg = response.text
                if response.status_code in (400, 422):
                    raise RazorpayValidationError(err_msg)
                if response.status_code in (401, 403):
                    raise RazorpayAuthError(err_msg)
                if response.status_code == 404:
                    raise RazorpayNotFoundError(err_msg)
                last_exc = RazorpayError(f"HTTP {response.status_code}: {err_msg}")
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_exc = RazorpayError(f"Network error: {e}")
            if attempt < MAX_RETRIES - 1:
                import asyncio; await asyncio.sleep(2 ** attempt)
        raise last_exc or RazorpayError("Max retries exceeded")

    async def create_plan(self, name, amount, currency, period, description=""):
        return await self._request("POST", "/plans", json_body={"item": {"name": name, "amount": amount, "currency": currency, "description": description}, "period": period})

    async def get_plan(self, plan_id):
        return await self._request("GET", f"/plans/{plan_id}")

    async def create_subscription(self, plan_id, customer_id, total_count=0, quantity=1, notes=None):
        body = {"plan_id": plan_id, "customer_id": customer_id, "quantity": quantity, "total_count": total_count}
        if notes: body["notes"] = notes
        return await self._request("POST", "/subscriptions", json_body=body)

    async def get_subscription(self, subscription_id):
        return await self._request("GET", f"/subscriptions/{subscription_id}")

    async def cancel_subscription(self, subscription_id, cancel_at_cycle_end=True):
        return await self._request("POST", f"/subscriptions/{subscription_id}/cancel", json_body={"cancel_at_cycle_end": 1 if cancel_at_cycle_end else 0})

    async def update_subscription(self, subscription_id, quantity=None, plan_id=None, notes=None):
        body = {}
        if quantity is not None: body["quantity"] = quantity
        if plan_id is not None: body["plan_id"] = plan_id
        if notes: body["notes"] = notes
        if not body: raise RazorpayValidationError("No update fields provided")
        return await self._request("PATCH", f"/subscriptions/{subscription_id}", json_body=body)

    async def create_customer(self, name, email, contact="", notes=None):
        body = {"name": name, "email": email}
        if contact: body["contact"] = contact
        if notes: body["notes"] = notes
        return await self._request("POST", "/customers", json_body=body)

    def verify_webhook_signature(self, webhook_body: str, razorpay_signature: str) -> bool:
        s = get_settings()
        secret = s.RAZORPAY_WEBHOOK_SECRET
        if not secret:
            logger.error("RAZORPAY_WEBHOOK_SECRET not set — cannot verify webhook")
            return False
        expected = hmac.new(secret.encode(), webhook_body.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, razorpay_signature)

    # ── Tokenized Card Charging (FlexPay daily installments) ──────────────
    # These methods charge a customer's stored card token without
    # requiring them to re-enter card details.

    async def create_payment(self, amount: int, currency: str, customer_id: str,
                              token: str, description: str = "",
                              notes: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a payment using a stored card token.

        Razorpay API: POST /v1/payments
        Charges the customer's tokenized card immediately (auto-capture).

        Args:
            amount: Amount in smallest currency unit (cents for USD).
            currency: "USD" or "INR".
            customer_id: Razorpay customer ID (from create_customer).
            token: Card token (from checkout tokenization).
            description: Payment description.
            notes: Optional metadata.

        Returns:
            Razorpay payment object with id, status, amount, etc.

        Raises:
            RazorpayError on failure.
        """
        body = {
            "amount": amount,
            "currency": currency,
            "customer_id": customer_id,
            "token": token,
            "description": description,
            "method": "card",
        }
        if notes:
            body["notes"] = notes
        return await self._request("POST", "/payments", json_body=body)

    async def capture_payment(self, payment_id: str, amount: int,
                               currency: str) -> Dict[str, Any]:
        """Capture an authorized payment.

        Razorpay API: POST /v1/payments/{id}/capture
        Used when a payment was created with auto-capture=false.

        Args:
            payment_id: Payment ID from create_payment response.
            amount: Amount to capture (cents for USD).
            currency: "USD" or "INR".

        Returns:
            Updated payment object with status="captured".
        """
        return await self._request(
            "POST", f"/payments/{payment_id}/capture",
            json_body={"amount": amount, "currency": currency}
        )

    async def get_payment(self, payment_id: str) -> Dict[str, Any]:
        """Get payment status from Razorpay.

        Args:
            payment_id: Payment ID to check.

        Returns:
            Payment object with status, amount, error_code, etc.
        """
        return await self._request("GET", f"/payments/{payment_id}")

    async def create_order(self, amount: int, currency: str,
                           receipt: str = "", notes: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a Razorpay order (for checkout flow).

        Razorpay API: POST /v1/orders

        Args:
            amount: Amount in smallest currency unit (cents for USD).
            currency: "USD" or "INR".
            receipt: Optional receipt ID.
            notes: Optional metadata.

        Returns:
            Order object with id, amount, currency, status.
        """
        body = {
            "amount": amount,
            "currency": currency,
        }
        if receipt:
            body["receipt"] = receipt
        if notes:
            body["notes"] = notes
        return await self._request("POST", "/orders", json_body=body)

_client_instance = None
def get_razorpay_client() -> RazorpayClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = RazorpayClient()
    return _client_instance
