"""
Paddle API Client Tests (BC-002, BG-05)

Comprehensive tests for the PaddleClient covering:
1. Client initialization (sandbox/production modes, config storage)
2. Subscription CRUD operations
3. Customer management
4. Transaction retrieval
5. Price/variant queries
6. Invoice retrieval
7. Request retry with exponential backoff
8. Webhook HMAC-SHA256 signature verification
9. Rate limiting compliance (500 req/min)
10. Edge cases (timeouts, connection errors, client lifecycle)

BC-001: All tests are self-contained with no external dependencies
BC-002: Decimal precision for monetary values
"""

import hashlib
import hmac
import json
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4

import sys
sys.path.insert(0, '/home/z/my-project/parwa')


# =============================================================================
# Test Client Initialization
# =============================================================================

class TestPaddleClientInit:
    """Tests for PaddleClient.__init__ configuration."""

    def test_client_init_sandbox_mode(self):
        """
        Test that sandbox mode uses the sandbox API URL.

        When sandbox=True, base_url should be https://sandbox-api.paddle.com/
        """
        from backend.app.clients.paddle_client import (
            PaddleClient,
            PADDLE_SANDBOX_URL,
        )

        client = PaddleClient(api_key="test_key", sandbox=True)

        assert client.base_url == PADDLE_SANDBOX_URL
        assert client.sandbox is True

    def test_client_init_production_mode(self):
        """
        Test that production mode uses the production API URL.

        When sandbox=False, base_url should be https://api.paddle.com/
        """
        from backend.app.clients.paddle_client import (
            PaddleClient,
            PADDLE_PRODUCTION_URL,
        )

        client = PaddleClient(api_key="prod_key", sandbox=False)

        assert client.base_url == PADDLE_PRODUCTION_URL
        assert client.sandbox is False

    def test_client_init_stores_config(self):
        """
        Test that api_key, sandbox, and webhook_secret are stored correctly.

        Client must preserve all init parameters for later use.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(
            api_key="secret_key_123",
            client_token="tok_abc",
            sandbox=True,
            webhook_secret="whsec_def",
        )

        assert client.api_key == "secret_key_123"
        assert client.client_token == "tok_abc"
        assert client.sandbox is True
        assert client.webhook_secret == "whsec_def"
        assert client._request_times == []
        assert client._client is None


# =============================================================================
# Test Subscription Methods
# =============================================================================

class TestPaddleClientSubscriptions:
    """Tests for subscription-related API methods."""

    @pytest.mark.asyncio
    async def test_get_subscription_success(self):
        """
        Test get_subscription returns subscription data from API.

        Mocks _request to return a subscription object and verifies
        the subscription ID is returned correctly.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_response = {
            "data": {
                "id": "sub_123",
                "status": "active",
                "customer_id": "ctm_456",
                "current_billing_period": {
                    "starts_at": "2025-01-01T00:00:00Z",
                    "ends_at": "2025-02-01T00:00:00Z",
                },
            }
        }

        with patch.object(client, '_request', new_callable=AsyncMock, return_value=mock_response):
            result = await client.get_subscription("sub_123")

        assert result["data"]["id"] == "sub_123"
        assert result["data"]["status"] == "active"

    @pytest.mark.asyncio
    async def test_list_subscriptions_with_filters(self):
        """
        Test list_subscriptions passes correct query parameters.

        customer_id, status, per_page, and after should all be forwarded
        to _request as params.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_response = {
            "data": [
                {"id": "sub_1", "status": "active"},
                {"id": "sub_2", "status": "active"},
            ],
            "meta": {"has_more": False},
        }

        with patch.object(client, '_request', new_callable=AsyncMock, return_value=mock_response) as mock_req:
            result = await client.list_subscriptions(
                customer_id="ctm_789",
                status="active",
                per_page=25,
                after="sub_0",
            )

        # Verify _request was called with correct params
        mock_req.assert_called_once_with(
            "GET",
            "/subscriptions",
            params={
                "customer_id": "ctm_789",
                "status": "active",
                "per_page": 25,
                "after": "sub_0",
            },
        )
        assert len(result["data"]) == 2

    @pytest.mark.asyncio
    async def test_create_subscription_success(self):
        """
        Test create_subscription builds correct items structure.

        The items array must contain price_id and quantity matching
        Paddle's API requirements.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_response = {
            "data": {
                "id": "sub_new",
                "status": "active",
                "items": [{"price_id": "pri_abc", "quantity": 3}],
            }
        }

        with patch.object(client, '_request', new_callable=AsyncMock, return_value=mock_response) as mock_req:
            result = await client.create_subscription(
                customer_id="ctm_123",
                price_id="pri_abc",
                quantity=3,
            )

        # Verify the POST body includes items with correct structure
        call_kwargs = mock_req.call_args
        assert call_kwargs[0][0] == "POST"
        assert call_kwargs[0][1] == "/subscriptions"
        sent_data = call_kwargs[1]["json"]
        assert sent_data["customer_id"] == "ctm_123"
        assert sent_data["items"] == [{"price_id": "pri_abc", "quantity": 3}]
        assert result["data"]["id"] == "sub_new"

    @pytest.mark.asyncio
    async def test_update_subscription_success(self):
        """
        Test update_subscription sends PATCH to correct endpoint.

        kwargs should be forwarded as JSON body.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_response = {
            "data": {
                "id": "sub_123",
                "status": "active",
                "next_billing_period": {
                    "starts_at": "2025-03-01T00:00:00Z",
                    "ends_at": "2025-04-01T00:00:00Z",
                },
            }
        }

        with patch.object(client, '_request', new_callable=AsyncMock, return_value=mock_response) as mock_req:
            result = await client.update_subscription(
                subscription_id="sub_123",
                items=[{"price_id": "pri_new", "quantity": 1}],
                proration_billing_mode="prorated_immediately",
            )

        mock_req.assert_called_once_with(
            "PATCH",
            "/subscriptions/sub_123",
            json={
                "items": [{"price_id": "pri_new", "quantity": 1}],
                "proration_billing_mode": "prorated_immediately",
            },
        )
        assert result["data"]["id"] == "sub_123"

    @pytest.mark.asyncio
    async def test_cancel_subscription_immediate(self):
        """
        Test cancel_subscription with effective_from='immediately'.

        Should send POST to /subscriptions/{id}/cancel with the
        effective_from field set to 'immediately'.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_response = {
            "data": {
                "id": "sub_123",
                "status": "canceled",
                "effective_from": "immediately",
            }
        }

        with patch.object(client, '_request', new_callable=AsyncMock, return_value=mock_response) as mock_req:
            result = await client.cancel_subscription(
                subscription_id="sub_123",
                effective_from="immediately",
            )

        mock_req.assert_called_once_with(
            "POST",
            "/subscriptions/sub_123/cancel",
            json={"effective_from": "immediately"},
        )
        assert result["data"]["status"] == "canceled"

    @pytest.mark.asyncio
    async def test_cancel_subscription_next_period(self):
        """
        Test cancel_subscription with effective_from='next_billing_period'.

        Should send POST with reason field when provided.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_response = {
            "data": {
                "id": "sub_123",
                "status": "active",
                "scheduled_change": {
                    "action": "cancel",
                    "effective_at": "2025-02-01T00:00:00Z",
                },
            }
        }

        with patch.object(client, '_request', new_callable=AsyncMock, return_value=mock_response) as mock_req:
            result = await client.cancel_subscription(
                subscription_id="sub_123",
                effective_from="next_billing_period",
                reason="Downgrading to free tier",
            )

        mock_req.assert_called_once_with(
            "POST",
            "/subscriptions/sub_123/cancel",
            json={
                "effective_from": "next_billing_period",
                "reason": "Downgrading to free tier",
            },
        )
        assert result["data"]["scheduled_change"]["action"] == "cancel"


# =============================================================================
# Test Customer Methods
# =============================================================================

class TestPaddleClientCustomers:
    """Tests for customer-related API methods."""

    @pytest.mark.asyncio
    async def test_get_customer_success(self):
        """
        Test get_customer returns customer data by ID.

        Should call GET /customers/{customer_id}.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_response = {
            "data": {
                "id": "ctm_123",
                "email": "user@example.com",
                "name": "Jane Doe",
                "status": "active",
            }
        }

        with patch.object(client, '_request', new_callable=AsyncMock, return_value=mock_response) as mock_req:
            result = await client.get_customer("ctm_123")

        mock_req.assert_called_once_with("GET", "/customers/ctm_123")
        assert result["data"]["email"] == "user@example.com"
        assert result["data"]["name"] == "Jane Doe"

    @pytest.mark.asyncio
    async def test_list_customers_with_email_filter(self):
        """
        Test list_customers passes email as query parameter.

        The email filter is essential for looking up customers by
        email address before creating a new one.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_response = {
            "data": [
                {"id": "ctm_1", "email": "user@example.com"},
            ],
            "meta": {"has_more": False},
        }

        with patch.object(client, '_request', new_callable=AsyncMock, return_value=mock_response) as mock_req:
            result = await client.list_customers(
                email="user@example.com",
                per_page=10,
            )

        mock_req.assert_called_once_with(
            "GET",
            "/customers",
            params={
                "email": "user@example.com",
                "per_page": 10,
            },
        )
        assert len(result["data"]) == 1

    @pytest.mark.asyncio
    async def test_create_customer_success(self):
        """
        Test create_customer sends correct POST body.

        Should include email, name, and any extra kwargs.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_response = {
            "data": {
                "id": "ctm_new",
                "email": "new@example.com",
                "name": "New User",
                "custom_data": {"company_id": "comp_1"},
            }
        }

        with patch.object(client, '_request', new_callable=AsyncMock, return_value=mock_response) as mock_req:
            result = await client.create_customer(
                email="new@example.com",
                name="New User",
                custom_data={"company_id": "comp_1"},
            )

        mock_req.assert_called_once_with(
            "POST",
            "/customers",
            json={
                "email": "new@example.com",
                "name": "New User",
                "custom_data": {"company_id": "comp_1"},
            },
        )
        assert result["data"]["id"] == "ctm_new"


# =============================================================================
# Test Transaction Methods
# =============================================================================

class TestPaddleClientTransactions:
    """Tests for transaction-related API methods."""

    @pytest.mark.asyncio
    async def test_get_transaction_success(self):
        """
        Test get_transaction returns transaction data by ID.

        Should call GET /transactions/{transaction_id}.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_response = {
            "data": {
                "id": "txn_123",
                "status": "completed",
                "amount": "999.00",
                "currency": "USD",
                "customer_id": "ctm_456",
            }
        }

        with patch.object(client, '_request', new_callable=AsyncMock, return_value=mock_response) as mock_req:
            result = await client.get_transaction("txn_123")

        mock_req.assert_called_once_with("GET", "/transactions/txn_123")
        assert result["data"]["amount"] == "999.00"
        assert result["data"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_list_transactions_with_filters(self):
        """
        Test list_transactions passes subscription_id, customer_id,
        status, and pagination params correctly.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_response = {
            "data": [
                {"id": "txn_1", "status": "completed"},
            ],
            "meta": {"has_more": True, "next_cursor": "txn_cursor"},
        }

        with patch.object(client, '_request', new_callable=AsyncMock, return_value=mock_response) as mock_req:
            result = await client.list_transactions(
                subscription_id="sub_123",
                customer_id="ctm_456",
                status="completed",
                per_page=10,
                after="txn_cursor_prev",
            )

        mock_req.assert_called_once_with(
            "GET",
            "/transactions",
            params={
                "subscription_id": "sub_123",
                "customer_id": "ctm_456",
                "status": "completed",
                "per_page": 10,
                "after": "txn_cursor_prev",
            },
        )

    @pytest.mark.asyncio
    async def test_transaction_error_handling(self):
        """
        Test that get_transaction raises PaddleNotFoundError on 404.

        When a transaction doesn't exist, the client should raise
        a PaddleNotFoundError.
        """
        from backend.app.clients.paddle_client import (
            PaddleClient,
            PaddleNotFoundError,
        )

        client = PaddleClient(api_key="test_key", sandbox=True)

        with patch.object(
            client, '_request', new_callable=AsyncMock,
            side_effect=PaddleNotFoundError("Not found: /transactions/txn_missing"),
        ):
            with pytest.raises(PaddleNotFoundError):
                await client.get_transaction("txn_missing")


# =============================================================================
# Test Price Methods
# =============================================================================

class TestPaddleClientPrices:
    """Tests for price/variant API methods."""

    @pytest.mark.asyncio
    async def test_get_price_success(self):
        """
        Test get_price returns price/variant details by ID.

        Should call GET /prices/{price_id}.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_response = {
            "data": {
                "id": "pri_123",
                "product_id": "pro_456",
                "amount": "99900",
                "currency": "USD",
                "billing_cycle": {"interval": "month", "frequency": 1},
                "status": "active",
            }
        }

        with patch.object(client, '_request', new_callable=AsyncMock, return_value=mock_response) as mock_req:
            result = await client.get_price("pri_123")

        mock_req.assert_called_once_with("GET", "/prices/pri_123")
        assert result["data"]["amount"] == "99900"
        assert result["data"]["currency"] == "USD"

    @pytest.mark.asyncio
    async def test_list_prices_success(self):
        """
        Test list_prices passes product_id and pagination params.

        Should filter by product_id when provided.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_response = {
            "data": [
                {"id": "pri_1", "amount": "49900", "currency": "USD"},
                {"id": "pri_2", "amount": "99900", "currency": "USD"},
            ],
            "meta": {"has_more": False},
        }

        with patch.object(client, '_request', new_callable=AsyncMock, return_value=mock_response) as mock_req:
            result = await client.list_prices(
                product_id="pro_456",
                per_page=100,
            )

        mock_req.assert_called_once_with(
            "GET",
            "/prices",
            params={
                "product_id": "pro_456",
                "per_page": 100,
            },
        )
        assert len(result["data"]) == 2


# =============================================================================
# Test Invoice Methods
# =============================================================================

class TestPaddleClientInvoices:
    """Tests for invoice API methods."""

    @pytest.mark.asyncio
    async def test_list_invoices_success(self):
        """
        Test list_invoices passes subscription_id, customer_id, status,
        and pagination params correctly.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_response = {
            "data": [
                {
                    "id": "inv_123",
                    "status": "paid",
                    "amount": "999.00",
                    "currency": "USD",
                },
            ],
            "meta": {"has_more": False},
        }

        with patch.object(client, '_request', new_callable=AsyncMock, return_value=mock_response) as mock_req:
            result = await client.list_invoices(
                subscription_id="sub_123",
                customer_id="ctm_456",
                status="paid",
                per_page=10,
                after="inv_cursor",
            )

        mock_req.assert_called_once_with(
            "GET",
            "/invoices",
            params={
                "subscription_id": "sub_123",
                "customer_id": "ctm_456",
                "status": "paid",
                "per_page": 10,
                "after": "inv_cursor",
            },
        )
        assert len(result["data"]) == 1
        assert result["data"][0]["status"] == "paid"

    @pytest.mark.asyncio
    async def test_get_invoice_success(self):
        """
        Test get_invoice returns invoice data by ID.

        Should call GET /invoices/{invoice_id}.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_response = {
            "data": {
                "id": "inv_123",
                "status": "paid",
                "amount": "999.00",
                "currency": "USD",
                "subscription_id": "sub_456",
                "invoice_number": "INV-2025-001",
            }
        }

        with patch.object(client, '_request', new_callable=AsyncMock, return_value=mock_response) as mock_req:
            result = await client.get_invoice("inv_123")

        mock_req.assert_called_once_with("GET", "/invoices/inv_123")
        assert result["data"]["invoice_number"] == "INV-2025-001"
        assert result["data"]["amount"] == "999.00"


# =============================================================================
# Test Request Retry Logic
# =============================================================================

class TestPaddleRequestRetry:
    """Tests for automatic retry with exponential backoff."""

    @pytest.mark.asyncio
    async def test_request_retries_on_500(self):
        """
        Test that _request retries with exponential backoff on 500 errors.

        Should sleep with delays of 2, 4 seconds (RETRY_BASE_DELAY * 2^n)
        before exhausting retries and raising the error.
        """
        from backend.app.clients.paddle_client import PaddleClient, PaddleError

        client = PaddleClient(api_key="test_key", sandbox=True)

        # Mock httpx response with 500 status
        mock_response_500 = MagicMock()
        mock_response_500.status_code = 500
        mock_response_500.json.return_value = {"error": "Internal Server Error"}

        # Mock the HTTP client
        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.request = AsyncMock(return_value=mock_response_500)

        client._client = mock_http_client

        with patch.object(client, '_check_rate_limit'):
            with patch('backend.app.clients.paddle_client.time.sleep') as mock_sleep:
                with pytest.raises(PaddleError, match="Server error: 500"):
                    await client._request("GET", "/subscriptions/sub_123")

        # Should have retried MAX_RETRIES (3) times, sleeping between each
        assert mock_sleep.call_count == 3
        # Check exponential backoff: 2, 4, 8 (but last attempt has no sleep after)
        sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
        assert sleep_calls[0] == 2  # 2^0 * RETRY_BASE_DELAY
        assert sleep_calls[1] == 4  # 2^1 * RETRY_BASE_DELAY
        assert sleep_calls[2] == 8  # 2^2 * RETRY_BASE_DELAY

    @pytest.mark.asyncio
    async def test_request_raises_auth_error_on_401(self):
        """
        Test that _request raises PaddleAuthError immediately on 401.

        Authentication errors should NOT trigger retries.
        """
        from backend.app.clients.paddle_client import PaddleClient, PaddleAuthError

        client = PaddleClient(api_key="bad_key", sandbox=True)

        mock_response_401 = MagicMock()
        mock_response_401.status_code = 401

        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.request = AsyncMock(return_value=mock_response_401)

        client._client = mock_http_client

        with patch.object(client, '_check_rate_limit'):
            with pytest.raises(PaddleAuthError, match="Invalid API key"):
                await client._request("GET", "/subscriptions/sub_123")

        # Should have made exactly 1 call (no retries for auth errors)
        assert mock_http_client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_request_raises_not_found_on_404(self):
        """
        Test that _request raises PaddleNotFoundError immediately on 404.

        Not-found errors should NOT trigger retries.
        """
        from backend.app.clients.paddle_client import PaddleClient, PaddleNotFoundError

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_response_404 = MagicMock()
        mock_response_404.status_code = 404

        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.request = AsyncMock(return_value=mock_response_404)

        client._client = mock_http_client

        with patch.object(client, '_check_rate_limit'):
            with pytest.raises(PaddleNotFoundError, match="Not found"):
                await client._request("GET", "/subscriptions/sub_missing")

        assert mock_http_client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_request_rate_limit_handling(self):
        """
        Test that _request sleeps and retries on 429 rate limit responses.

        Should honor Retry-After header from Paddle.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key", sandbox=True)

        # First call: 429 rate limited, second call: success
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {"Retry-After": "5"}
        mock_response_429.json.return_value = {"error": "Rate limited"}

        mock_response_ok = MagicMock()
        mock_response_ok.status_code = 200
        mock_response_ok.json.return_value = {"data": {"id": "sub_123"}}

        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.request = AsyncMock(
            side_effect=[mock_response_429, mock_response_ok]
        )

        client._client = mock_http_client

        with patch.object(client, '_check_rate_limit'):
            with patch('backend.app.clients.paddle_client.time.sleep') as mock_sleep:
                result = await client._request("GET", "/subscriptions/sub_123")

        assert result["data"]["id"] == "sub_123"
        # Should have slept once for Retry-After value (5 seconds)
        # Plus the backoff sleep after the rate limit
        assert mock_sleep.call_count >= 1


# =============================================================================
# Test Webhook Verification
# =============================================================================

class TestPaddleWebhookVerification:
    """Tests for webhook signature verification and event parsing."""

    def test_verify_webhook_signature_valid(self):
        """
        Test verify_webhook_signature returns True for valid HMAC-SHA256.

        Generates a correct signature using the same secret and payload
        to verify the client's verification logic.
        """
        from backend.app.clients.paddle_client import PaddleClient

        secret = "whsec_test_secret_123"
        payload = b'{"event_type": "subscription.activated", "event_id": "evt_001"}'

        # Generate valid HMAC-SHA256 signature
        expected_sig = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        client = PaddleClient(
            api_key="test_key",
            sandbox=True,
            webhook_secret=secret,
        )

        result = client.verify_webhook_signature(payload, expected_sig)

        assert result is True

    def test_verify_webhook_signature_invalid(self):
        """
        Test verify_webhook_signature returns False for invalid signature.

        A tampered payload or wrong signature must be rejected.
        """
        from backend.app.clients.paddle_client import PaddleClient

        secret = "whsec_test_secret_123"
        payload = b'{"event_type": "subscription.activated"}'
        invalid_signature = "deadbeef00badc0ffee000000000000"

        client = PaddleClient(
            api_key="test_key",
            sandbox=True,
            webhook_secret=secret,
        )

        result = client.verify_webhook_signature(payload, invalid_signature)

        assert result is False

    def test_verify_webhook_signature_no_secret(self):
        """
        Test verify_webhook_signature returns False when no secret configured.

        Client created without webhook_secret should always return False.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(
            api_key="test_key",
            sandbox=True,
            webhook_secret=None,
        )

        payload = b'{"event_type": "subscription.activated"}'

        result = client.verify_webhook_signature(payload, "any_signature")

        assert result is False

    def test_parse_webhook_event(self):
        """
        Test parse_webhook_event extracts correct dict structure.

        Should return a dict with event_type, event_id, occurred_at,
        notification_id, and data keys.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key", sandbox=True)

        payload = json.dumps({
            "event_type": "subscription.activated",
            "event_id": "evt_001",
            "occurred_at": "2025-01-15T10:30:00Z",
            "notification_id": "ntf_abc",
            "data": {
                "id": "sub_123",
                "status": "active",
                "customer_id": "ctm_456",
            },
        }).encode()

        result = client.parse_webhook_event(payload)

        assert result["event_type"] == "subscription.activated"
        assert result["event_id"] == "evt_001"
        assert result["occurred_at"] == "2025-01-15T10:30:00Z"
        assert result["notification_id"] == "ntf_abc"
        assert result["data"]["id"] == "sub_123"
        assert result["data"]["status"] == "active"


# =============================================================================
# Test Rate Limiting
# =============================================================================

class TestPaddleRateLimiting:
    """Tests for Paddle's 500 requests/minute rate limit enforcement."""

    @patch('backend.app.clients.paddle_client.time.sleep')
    @patch('backend.app.clients.paddle_client.time.time', return_value=0.0)
    def test_rate_limit_allows_under_threshold(self, mock_time, mock_sleep):
        """
        Test that 499 requests within the window are allowed without sleeping.

        The client should only block when reaching the 500th request.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key", sandbox=True)
        # Simulate 499 previous requests all at time 0
        client._request_times = [0.0] * 499

        client._check_rate_limit()

        # Should NOT have called sleep since we're under threshold
        assert mock_sleep.call_count == 0
        # Should have added the new request timestamp
        assert len(client._request_times) == 500

    @patch('backend.app.clients.paddle_client.time.sleep')
    @patch('backend.app.clients.paddle_client.time.time', return_value=0.0)
    def test_rate_limit_blocks_at_threshold(self, mock_time, mock_sleep):
        """
        Test that the 500th request triggers a wait.

        When _request_times has 500 entries all within the window,
        _check_rate_limit should call time.sleep to wait.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key", sandbox=True)
        # Simulate 500 previous requests all at time 0
        client._request_times = [0.0] * 500

        client._check_rate_limit()

        # Should have called sleep to wait for the rate limit window
        assert mock_sleep.call_count == 1
        # After sleeping, a new timestamp should be appended
        assert len(client._request_times) == 501


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestPaddleEdgeCases:
    """Tests for edge cases, timeouts, and connection errors."""

    @pytest.mark.asyncio
    async def test_close_client_closes_httpx(self):
        """
        Test that close() properly closes the underlying httpx.AsyncClient.

        After closing, _client should be set to None.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.aclose = AsyncMock()
        client._client = mock_http_client

        await client.close()

        mock_http_client.aclose.assert_called_once()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_request_timeout_handling(self):
        """
        Test that httpx.TimeoutException triggers retry with backoff.

        Network timeouts should not immediately raise; the client
        should retry with exponential backoff.
        """
        import httpx
        from backend.app.clients.paddle_client import PaddleClient, PaddleError

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.request = AsyncMock(
            side_effect=httpx.TimeoutException("Connection timed out")
        )

        client._client = mock_http_client

        with patch.object(client, '_check_rate_limit'):
            with patch('backend.app.clients.paddle_client.time.sleep') as mock_sleep:
                with pytest.raises(PaddleError, match="Request timeout"):
                    await client._request("GET", "/subscriptions/sub_123")

        # Should have retried MAX_RETRIES times
        assert mock_http_client.request.call_count == 3
        assert mock_sleep.call_count == 3

    @pytest.mark.asyncio
    async def test_request_connection_error(self):
        """
        Test that httpx.RequestError (network failures) triggers retry.

        Connection refused, DNS failures, etc. should trigger retry
        with exponential backoff before raising PaddleError.
        """
        import httpx
        from backend.app.clients.paddle_client import PaddleClient, PaddleError

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.request = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        client._client = mock_http_client

        with patch.object(client, '_check_rate_limit'):
            with patch('backend.app.clients.paddle_client.time.sleep') as mock_sleep:
                with pytest.raises(PaddleError, match="Request failed"):
                    await client._request("GET", "/subscriptions/sub_123")

        # Should have retried MAX_RETRIES times
        assert mock_http_client.request.call_count == 3
        assert mock_sleep.call_count == 3

    @pytest.mark.asyncio
    async def test_request_success_no_retry(self):
        """
        Test that a successful request (200) returns immediately.

        A 200 response should not trigger any retries or sleep calls.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_response_ok = MagicMock()
        mock_response_ok.status_code = 200
        mock_response_ok.json.return_value = {"data": {"id": "sub_123"}}

        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.request = AsyncMock(return_value=mock_response_ok)

        client._client = mock_http_client

        with patch.object(client, '_check_rate_limit'):
            with patch('backend.app.clients.paddle_client.time.sleep') as mock_sleep:
                result = await client._request("GET", "/subscriptions/sub_123")

        assert result["data"]["id"] == "sub_123"
        # Single request, no retries, no sleep
        assert mock_http_client.request.call_count == 1
        assert mock_sleep.call_count == 0

    @pytest.mark.asyncio
    async def test_request_validation_error_on_422(self):
        """
        Test that a 422 response raises PaddleValidationError immediately.

        Validation errors from Paddle should not trigger retries.
        """
        from backend.app.clients.paddle_client import PaddleClient, PaddleValidationError

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_response_422 = MagicMock()
        mock_response_422.status_code = 422
        mock_response_422.json.return_value = {
            "error": {"code": "validation_error", "message": "Invalid quantity"},
        }

        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.request = AsyncMock(return_value=mock_response_422)

        client._client = mock_http_client

        with patch.object(client, '_check_rate_limit'):
            with pytest.raises(PaddleValidationError, match="Invalid quantity"):
                await client._request("POST", "/subscriptions", json={"bad": "data"})

        assert mock_http_client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_request_403_raises_auth_error(self):
        """
        Test that a 403 response raises PaddleAuthError for permission denied.

        Permission errors should not trigger retries.
        """
        from backend.app.clients.paddle_client import PaddleClient, PaddleAuthError

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_response_403 = MagicMock()
        mock_response_403.status_code = 403

        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.request = AsyncMock(return_value=mock_response_403)

        client._client = mock_http_client

        with patch.object(client, '_check_rate_limit'):
            with pytest.raises(PaddleAuthError, match="Permission denied"):
                await client._request("GET", "/admin/endpoint")

        assert mock_http_client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_pause_subscription_success(self):
        """
        Test pause_subscription sends POST with optional resume_at.

        Should call POST /subscriptions/{id}/pause with resume_at
        when provided.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_response = {
            "data": {
                "id": "sub_123",
                "status": "paused",
                "paused_at": "2025-01-15T00:00:00Z",
            }
        }

        with patch.object(client, '_request', new_callable=AsyncMock, return_value=mock_response) as mock_req:
            result = await client.pause_subscription(
                subscription_id="sub_123",
                resume_at="2025-02-15T00:00:00Z",
            )

        mock_req.assert_called_once_with(
            "POST",
            "/subscriptions/sub_123/pause",
            json={"resume_at": "2025-02-15T00:00:00Z"},
        )
        assert result["data"]["status"] == "paused"

    @pytest.mark.asyncio
    async def test_resume_subscription_success(self):
        """
        Test resume_subscription sends POST to resume endpoint.

        Should call POST /subscriptions/{id}/resume.
        """
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key", sandbox=True)

        mock_response = {
            "data": {
                "id": "sub_123",
                "status": "active",
            }
        }

        with patch.object(client, '_request', new_callable=AsyncMock, return_value=mock_response) as mock_req:
            result = await client.resume_subscription("sub_123")

        mock_req.assert_called_once_with(
            "POST",
            "/subscriptions/sub_123/resume",
            json={},
        )
        assert result["data"]["status"] == "active"
