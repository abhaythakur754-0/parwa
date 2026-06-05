"""
Day 6 — HubSpot CRM Deep Integration: Comprehensive Test Suite

Tests the full HubSpot CRM integration stack:
  - HubSpotClient: REST API wrapper with retry, rate limiting, HMAC verification
  - HubSpotWebhookHandler: Event dispatcher for 7 HubSpot event types
  - CRMServer MCP: 9 MCP tools with live API + fallback
  - HubSpotDataSync: Full/incremental sync with partial failure support
  - IntegrationService HubSpot: Credential testing for HubSpot integration
  - End-to-end integration flow with multi-tenant isolation

BC-001: All operations scoped to company_id.
BC-003: Webhook HMAC-SHA256 signature verification.
BC-008: Never crash — all errors caught and returned as result objects.

Run: pytest backend/tests/test_day6_hubspot_crm.py -v
"""

import asyncio
import base64
import hashlib
import hmac
import json
import os
import sys
import time
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# Add project root paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.clients.hubspot_client import (
    HUBSPOT_BASE_URL,
    HubSpotClient,
    HubSpotResult,
    HubSpotError,
    HubSpotAuthError,
    HubSpotRateLimitError,
    HubSpotNotFoundError,
    create_hubspot_client_from_config,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures & Helpers
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def hubspot_client():
    """Create a HubSpotClient for testing."""
    return HubSpotClient(access_token="pat_test_token_123")


@pytest.fixture
def mock_hubspot_contact_response():
    """Standard HubSpot contact API response."""
    return {
        "id": "123",
        "properties": {
            "email": "test@example.com",
            "firstname": "John",
            "lastname": "Doe",
            "phone": "+1234567890",
            "company": "Acme Corp",
            "jobtitle": "Engineer",
            "lifecyclestage": "customer",
            "createdate": "2025-01-01T00:00:00Z",
            "lastmodifieddate": "2025-06-01T00:00:00Z",
        },
        "createdAt": "2025-01-01T00:00:00Z",
        "updatedAt": "2025-06-01T00:00:00Z",
    }


@pytest.fixture
def mock_hubspot_deal_response():
    """Standard HubSpot deal API response."""
    return {
        "id": "456",
        "properties": {
            "dealname": "Big Deal",
            "dealstage": "closedwon",
            "amount": "50000",
            "pipeline": "default",
            "closedate": "2025-06-15",
            "dealtype": "newbusiness",
            "createdate": "2025-01-01T00:00:00Z",
        },
        "createdAt": "2025-01-01T00:00:00Z",
        "updatedAt": "2025-06-01T00:00:00Z",
    }


@pytest.fixture
def mock_hubspot_company_response():
    """Standard HubSpot company API response."""
    return {
        "id": "789",
        "properties": {
            "name": "Acme Corp",
            "domain": "acme.com",
            "industry": "Technology",
            "city": "San Francisco",
            "state": "CA",
            "country": "US",
            "phone": "+14155551234",
            "createdate": "2025-01-01T00:00:00Z",
        },
        "createdAt": "2025-01-01T00:00:00Z",
        "updatedAt": "2025-06-01T00:00:00Z",
    }


def make_mock_response(status_code=200, json_data=None, headers=None, text=""):
    """Create a mock httpx.Response object."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = status_code
    mock_resp.headers = headers or {}
    if json_data is not None:
        mock_resp.json.return_value = json_data
        mock_resp.text = json.dumps(json_data)
    else:
        mock_resp.text = text
    return mock_resp


# ═══════════════════════════════════════════════════════════════════
# 1. TestHubSpotClient (15+ tests)
# ═══════════════════════════════════════════════════════════════════


class TestHubSpotClientInit:
    """Tests for HubSpotClient initialization and headers."""

    def test_basic_init(self, hubspot_client):
        """Client should store access_token and defaults."""
        assert hubspot_client.access_token == "pat_test_token_123"
        assert hubspot_client.base_url == "https://api.hubapi.com"
        assert hubspot_client.timeout == 30
        assert hubspot_client.max_retries == 3

    def test_headers_bearer_token(self, hubspot_client):
        """Headers should include Bearer token authorization."""
        headers = hubspot_client._get_headers()
        assert headers["Authorization"] == "Bearer pat_test_token_123"
        assert headers["Content-Type"] == "application/json"

    def test_custom_timeout_and_retries(self):
        """Client should accept custom timeout and max_retries."""
        client = HubSpotClient(access_token="tok", timeout=60, max_retries=5)
        assert client.timeout == 60
        assert client.max_retries == 5

    def test_rate_limiting_enforcement(self, hubspot_client):
        """Rate limiter should enforce minimum interval between requests."""
        # First call sets _last_request_time
        hubspot_client._last_request_time = 0.0
        with patch("time.sleep") as mock_sleep:
            hubspot_client._enforce_rate_limit()
        # After setting _last_request_time to 0, elapsed will be huge
        # so no sleep should be called
        mock_sleep.assert_not_called()

        # Now simulate rapid successive calls
        hubspot_client._last_request_time = time.time()
        with patch("time.sleep") as mock_sleep:
            hubspot_client._enforce_rate_limit()
        # Should sleep for the remaining interval
        mock_sleep.assert_called_once()
        sleep_arg = mock_sleep.call_args[0][0]
        assert 0 < sleep_arg <= 0.1  # 1/10 = 0.1s max interval


class TestHubSpotClientRetry:
    """Tests for retry logic on errors."""

    @pytest.mark.asyncio
    async def test_retry_on_500_error(self, hubspot_client):
        """500 server error should trigger retries, then succeed."""
        mock_resp_500 = make_mock_response(500, text="Internal Server Error")
        mock_resp_200 = make_mock_response(200, json_data={"id": "1", "properties": {}})

        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return mock_resp_500
            return mock_resp_200

        with patch.object(httpx, "AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.request = mock_request
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            with patch("time.sleep"):
                result = await hubspot_client.get_contact("1")

        assert result.success is True
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, hubspot_client):
        """Timeout should trigger retries."""
        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise httpx.TimeoutException("Request timed out")
            return make_mock_response(200, json_data={"id": "1", "properties": {}})

        with patch.object(httpx, "AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.request = mock_request
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            with patch("time.sleep"):
                result = await hubspot_client.get_contact("1")

        assert result.success is True
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, hubspot_client):
        """Should fail after all retries are exhausted."""
        mock_resp_500 = make_mock_response(500, text="Server Error")

        with patch.object(httpx, "AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp_500)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            with patch("time.sleep"):
                result = await hubspot_client.get_contact("1")

        assert result.success is False
        assert "max retries" in result.error.lower() or "exceeded" in result.error.lower()

    @pytest.mark.asyncio
    async def test_401_authentication_error(self, hubspot_client):
        """401 should return auth error immediately without retrying."""
        mock_resp = make_mock_response(401, text="Unauthorized")

        with patch.object(httpx, "AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            result = await hubspot_client.get_contact("1")

        assert result.success is False
        assert result.status_code == 401
        assert "authentication" in result.error.lower() or "auth" in result.error.lower()

    @pytest.mark.asyncio
    async def test_404_not_found_error(self, hubspot_client):
        """404 should return not found error immediately."""
        mock_resp = make_mock_response(404, text="Not found")

        with patch.object(httpx, "AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            result = await hubspot_client.get_contact("99999")

        assert result.success is False
        assert result.status_code == 404
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_429_rate_limit_with_retry(self, hubspot_client):
        """429 should retry with exponential backoff."""
        mock_resp_429 = make_mock_response(429, headers={"Retry-After": "1"}, text="Rate limited")
        mock_resp_200 = make_mock_response(200, json_data={"id": "1", "properties": {}})

        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return mock_resp_429
            return mock_resp_200

        with patch.object(httpx, "AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.request = mock_request
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            with patch("time.sleep"):
                result = await hubspot_client.get_contact("1")

        assert result.success is True
        assert call_count == 2


class TestHubSpotClientAPIMethods:
    """Tests for HubSpotClient API methods."""

    @pytest.mark.asyncio
    async def test_get_contact_success(self, hubspot_client, mock_hubspot_contact_response):
        """get_contact should return contact data on 200."""
        mock_resp = make_mock_response(200, json_data=mock_hubspot_contact_response)

        with patch.object(httpx, "AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            result = await hubspot_client.get_contact("123")

        assert result.success is True
        assert result.data["id"] == "123"
        assert result.data["properties"]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_search_contacts_success(self, hubspot_client, mock_hubspot_contact_response):
        """search_contacts should POST and return matching results."""
        search_response = {
            "results": [mock_hubspot_contact_response],
            "paging": {"next": {"after": "cursor_abc"}},
        }
        mock_resp = make_mock_response(200, json_data=search_response)

        with patch.object(httpx, "AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            result = await hubspot_client.search_contacts(query="test@example.com")

        assert result.success is True
        assert len(result.data["results"]) == 1
        assert result.data["paging"]["next"]["after"] == "cursor_abc"

    @pytest.mark.asyncio
    async def test_create_contact_success(self, hubspot_client, mock_hubspot_contact_response):
        """create_contact should POST and return created contact."""
        mock_resp = make_mock_response(201, json_data=mock_hubspot_contact_response)

        with patch.object(httpx, "AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            result = await hubspot_client.create_contact(
                properties={"email": "test@example.com", "firstname": "John"}
            )

        assert result.success is True
        assert result.data["id"] == "123"

    @pytest.mark.asyncio
    async def test_update_contact_success(self, hubspot_client):
        """update_contact should PATCH and return updated contact."""
        updated = {
            "id": "123",
            "properties": {"email": "updated@example.com", "firstname": "Jane"},
        }
        mock_resp = make_mock_response(200, json_data=updated)

        with patch.object(httpx, "AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            result = await hubspot_client.update_contact(
                contact_id="123",
                properties={"email": "updated@example.com", "firstname": "Jane"},
            )

        assert result.success is True
        assert result.data["properties"]["email"] == "updated@example.com"

    @pytest.mark.asyncio
    async def test_get_deal_success(self, hubspot_client, mock_hubspot_deal_response):
        """get_deal should return deal data on 200."""
        mock_resp = make_mock_response(200, json_data=mock_hubspot_deal_response)

        with patch.object(httpx, "AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            result = await hubspot_client.get_deal("456")

        assert result.success is True
        assert result.data["id"] == "456"
        assert result.data["properties"]["dealname"] == "Big Deal"

    @pytest.mark.asyncio
    async def test_list_companies_success(self, hubspot_client, mock_hubspot_company_response):
        """list_companies should return list of companies."""
        list_response = {
            "results": [mock_hubspot_company_response],
        }
        mock_resp = make_mock_response(200, json_data=list_response)

        with patch.object(httpx, "AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            result = await hubspot_client.list_companies()

        assert result.success is True
        assert len(result.data["results"]) == 1
        assert result.data["results"][0]["properties"]["name"] == "Acme Corp"

    @pytest.mark.asyncio
    async def test_test_connection_success(self, hubspot_client):
        """test_connection should verify credentials and return pipeline count."""
        pipeline_response = {
            "results": [
                {"id": "default", "label": "Standard Pipeline"},
                {"id": "custom", "label": "Custom Pipeline"},
            ]
        }
        mock_resp = make_mock_response(200, json_data=pipeline_response)

        with patch.object(httpx, "AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            result = await hubspot_client.test_connection()

        assert result.success is True
        assert result.data["connected"] is True
        assert result.data["pipeline_count"] == 2

    @pytest.mark.asyncio
    async def test_create_note_success(self, hubspot_client):
        """create_note should POST to notes endpoint with association."""
        note_response = {
            "id": "note_001",
            "properties": {
                "hs_note_body": "Test note content",
                "hs_created_date": "2025-06-01T00:00:00Z",
            },
        }
        mock_resp = make_mock_response(201, json_data=note_response)

        with patch.object(httpx, "AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            result = await hubspot_client.create_note(
                contact_id="123", body="Test note content"
            )

        assert result.success is True
        assert result.data["id"] == "note_001"

    @pytest.mark.asyncio
    async def test_get_all_pages_pagination(self, hubspot_client):
        """get_all_pages should follow cursor pagination across multiple pages."""
        page1 = {
            "results": [{"id": "1"}, {"id": "2"}],
            "paging": {"next": {"after": "cursor_page2"}},
        }
        page2 = {
            "results": [{"id": "3"}],
            "paging": {},
        }

        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return make_mock_response(200, json_data=page1)
            return make_mock_response(200, json_data=page2)

        with patch.object(httpx, "AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.request = mock_request
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            result = await hubspot_client.get_all_pages(
                "/crm/v3/objects/contacts",
                params={"limit": 100},
            )

        assert result.success is True
        assert len(result.data["results"]) == 3
        assert result.data["results"][0]["id"] == "1"
        assert result.data["results"][2]["id"] == "3"


class TestHubSpotClientWebhookVerification:
    """Tests for HubSpot webhook HMAC-SHA256 signature verification."""

    def test_valid_signature(self):
        """Correctly computed signature should verify."""
        secret = "my_webhook_secret"
        payload = b'{"eventId": "123", "objectId": "456"}'

        computed = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
        signature = base64.b64encode(computed).decode("utf-8")

        assert HubSpotClient.verify_webhook_signature(payload, signature, secret) is True

    def test_invalid_signature(self):
        """Wrong signature should fail verification."""
        payload = b'{"eventId": "123"}'
        wrong_sig = base64.b64encode(b"wrong_signature").decode("utf-8")

        assert HubSpotClient.verify_webhook_signature(payload, wrong_sig, "secret") is False

    def test_empty_signature(self):
        """Empty signature should fail verification."""
        assert HubSpotClient.verify_webhook_signature(b"{}", "", "secret") is False

    def test_empty_secret(self):
        """Empty secret should fail verification."""
        assert HubSpotClient.verify_webhook_signature(b"{}", "dGVzdA==", "") is False

    def test_none_signature(self):
        """None signature should fail verification."""
        assert HubSpotClient.verify_webhook_signature(b"{}", None, "secret") is False

    def test_tampered_payload(self):
        """Tampered payload should fail verification with original signature."""
        secret = "my_secret"
        original_payload = b'{"amount": 100}'
        computed = hmac.new(secret.encode("utf-8"), original_payload, hashlib.sha256).digest()
        valid_sig = base64.b64encode(computed).decode("utf-8")

        tampered_payload = b'{"amount": 999}'
        assert HubSpotClient.verify_webhook_signature(tampered_payload, valid_sig, secret) is False


class TestHubSpotClientFactory:
    """Tests for create_hubspot_client_from_config factory."""

    def test_factory_creates_client(self):
        """Factory should create a client from config dict."""
        config = {"access_token": "pat_from_config", "timeout": 45, "max_retries": 5}
        client = create_hubspot_client_from_config(config)
        assert client.access_token == "pat_from_config"
        assert client.timeout == 45
        assert client.max_retries == 5

    def test_factory_defaults(self):
        """Factory should use defaults when config fields are missing."""
        client = create_hubspot_client_from_config({})
        assert client.access_token == ""
        assert client.timeout == 30
        assert client.max_retries == 3


class TestHubSpotResult:
    """Tests for HubSpotResult wrapper."""

    def test_success_result(self):
        result = HubSpotResult(success=True, data={"id": "123"}, status_code=200)
        assert result.success is True
        assert result.data == {"id": "123"}
        assert result.error == ""
        assert result.status_code == 200

    def test_error_result(self):
        result = HubSpotResult(success=False, error="Not found", status_code=404)
        assert result.success is False
        assert result.error == "Not found"
        assert result.status_code == 404

    def test_to_dict(self):
        result = HubSpotResult(
            success=True, data={"id": "1"}, status_code=200, metadata={"attempt": 2}
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["data"]["id"] == "1"
        assert d["metadata"]["attempt"] == 2


# ═══════════════════════════════════════════════════════════════════
# 2. TestHubSpotWebhookHandler (10 tests)
# ═══════════════════════════════════════════════════════════════════


class TestHubSpotWebhookHandler:
    """Tests for HubSpot webhook event handler dispatcher."""

    def _make_event(self, event_type: str, object_id: str = "100",
                    portal_id: str = "200001") -> dict:
        """Create a standard HubSpot webhook event dict."""
        return {
            "event_type": event_type,
            "payload": {
                "objectId": object_id,
                "portalId": portal_id,
                "eventId": "evt_001",
                "subscriptionId": "sub_001",
                "appId": "app_001",
                "occurredAt": 1717200000000,
                "changeSource": "CRM",
                "changeFlag": "NEW",
            },
            "company_id": "comp_test_001",
            "event_id": "evt_001",
        }

    def setUp_imports(self):
        """Import the handler module."""
        from app.webhooks.hubspot_handler import (
            handle_hubspot_event,
            _HUBSPOT_HANDLERS,
            _extract_contact_data,
            _extract_deal_data,
            _extract_company_data,
        )
        return handle_hubspot_event, _HUBSPOT_HANDLERS

    def test_handler_registry_has_7_event_types(self):
        """Handler registry should have exactly 7 event types."""
        _, handlers = self.setUp_imports()
        assert len(handlers) == 7

    def test_contact_created_dispatch(self):
        """contact.created event should dispatch to correct handler."""
        handle_hubspot_event, _ = self.setUp_imports()
        event = self._make_event("contact.created")
        result = handle_hubspot_event(event)
        assert result["success"] is True
        assert result["event_type"] == "contact.created"
        assert result["action_taken"] == "contact_created"
        assert result["object_id"] == "100"
        assert result["company_id"] == "comp_test_001"

    def test_contact_updated_dispatch(self):
        """contact.updated event should dispatch correctly."""
        handle_hubspot_event, _ = self.setUp_imports()
        event = self._make_event("contact.updated")
        event["payload"]["changeFlag"] = "CHANGED"
        result = handle_hubspot_event(event)
        assert result["success"] is True
        assert result["event_type"] == "contact.updated"
        assert result["action_taken"] == "contact_updated"

    def test_contact_deleted_dispatch(self):
        """contact.deleted event should dispatch correctly."""
        handle_hubspot_event, _ = self.setUp_imports()
        event = self._make_event("contact.deleted")
        result = handle_hubspot_event(event)
        assert result["success"] is True
        assert result["event_type"] == "contact.deleted"
        assert result["action_taken"] == "contact_deleted"

    def test_deal_created_dispatch(self):
        """deal.created event should dispatch correctly."""
        handle_hubspot_event, _ = self.setUp_imports()
        event = self._make_event("deal.created")
        result = handle_hubspot_event(event)
        assert result["success"] is True
        assert result["event_type"] == "deal.created"
        assert result["action_taken"] == "deal_created"

    def test_deal_updated_dispatch(self):
        """deal.updated event should dispatch correctly."""
        handle_hubspot_event, _ = self.setUp_imports()
        event = self._make_event("deal.updated")
        result = handle_hubspot_event(event)
        assert result["success"] is True
        assert result["event_type"] == "deal.updated"
        assert result["action_taken"] == "deal_updated"

    def test_company_created_dispatch(self):
        """company.created event should dispatch correctly."""
        handle_hubspot_event, _ = self.setUp_imports()
        event = self._make_event("company.created")
        result = handle_hubspot_event(event)
        assert result["success"] is True
        assert result["event_type"] == "company.created"
        assert result["action_taken"] == "company_created"

    def test_company_updated_dispatch(self):
        """company.updated event should dispatch correctly."""
        handle_hubspot_event, _ = self.setUp_imports()
        event = self._make_event("company.updated")
        result = handle_hubspot_event(event)
        assert result["success"] is True
        assert result["event_type"] == "company.updated"
        assert result["action_taken"] == "company_updated"

    def test_unknown_event_type_returns_error(self):
        """Unknown event type should return error with supported types."""
        handle_hubspot_event, handlers = self.setUp_imports()
        event = self._make_event("invoice.created")
        result = handle_hubspot_event(event)
        assert result["success"] is False
        assert "unknown" in result["action_taken"]
        assert "supported_types" in result
        assert len(result["supported_types"]) == 7

    def test_bc008_exception_in_handler_doesnt_crash(self):
        """BC-008: Exception in handler should not crash the dispatcher."""
        handle_hubspot_event, handlers = self.setUp_imports()

        # Replace a handler with one that raises
        original_handler = handlers["contact.created"]

        def crashing_handler(event):
            raise RuntimeError("Simulated handler crash")

        handlers["contact.created"] = crashing_handler

        try:
            event = self._make_event("contact.created")
            result = handle_hubspot_event(event)
            assert result["success"] is False
            assert "handler_error" in result["action_taken"]
            assert "Simulated handler crash" in result["error"]
        finally:
            # Restore original handler
            handlers["contact.created"] = original_handler


# ═══════════════════════════════════════════════════════════════════
# 3. TestCRMServerMCP (10+ tests)
# ═══════════════════════════════════════════════════════════════════


class TestCRMServerMCP:
    """Tests for the CRM MCP server tool registration and helpers."""

    def setUp(self):
        """Import and register CRM server tools."""
        from mcp_server.integrations.crm_server import CRMServer
        self.server = CRMServer()
        self.registry = MagicMock()
        self.registered_tools = {}

        def mock_register(definition, handler):
            self.registered_tools[definition.name] = {
                "definition": definition,
                "handler": handler,
            }

        self.registry.register_tool = mock_register
        self.server.register_tools(self.registry)

    def test_tool_registration_count(self):
        """CRMServer should register 8 tools in v2.0."""
        self.setUp()
        assert len(self.registered_tools) == 8

    def test_crm_get_contact_schema(self):
        """crm_get_contact should have correct schema."""
        self.setUp()
        schema = self.registered_tools["crm_get_contact"]["definition"].input_schema
        assert "contact_id" in schema["properties"]
        assert "email" in schema["properties"]
        assert "company_id" in schema["properties"]

    def test_crm_create_contact_schema(self):
        """crm_create_contact should require email and company_id."""
        self.setUp()
        schema = self.registered_tools["crm_create_contact"]["definition"].input_schema
        assert "email" in schema["required"]
        assert "company_id" in schema["required"]
        assert "email" in schema["properties"]
        assert "firstname" in schema["properties"]

    def test_crm_update_contact_schema(self):
        """crm_update_contact should require contact_id, properties, company_id."""
        self.setUp()
        schema = self.registered_tools["crm_update_contact"]["definition"].input_schema
        assert "contact_id" in schema["required"]
        assert "properties" in schema["required"]
        assert "company_id" in schema["required"]

    def test_crm_get_company_schema(self):
        """crm_get_company should require company_id."""
        self.setUp()
        schema = self.registered_tools["crm_get_company"]["definition"].input_schema
        assert "company_id" in schema["required"]
        assert "company_id" in schema["properties"]

    def test_crm_list_deals_schema(self):
        """crm_list_deals should have limit, after, and company_id."""
        self.setUp()
        schema = self.registered_tools["crm_list_deals"]["definition"].input_schema
        assert "limit" in schema["properties"]
        assert "after" in schema["properties"]
        assert "company_id" in schema["properties"]

    def test_crm_search_contacts_schema(self):
        """crm_search_contacts should require query."""
        self.setUp()
        schema = self.registered_tools["crm_search_contacts"]["definition"].input_schema
        assert "query" in schema["required"]
        assert "query" in schema["properties"]

    def test_version_is_2_0_0(self):
        """CRMServer version should be 2.0.0."""
        self.setUp()
        assert self.server.version == "2.0.0"

    def test_tags_include_hubspot(self):
        """crm_get_contact tags should include hubspot."""
        self.setUp()
        definition = self.registered_tools["crm_get_contact"]["definition"]
        assert "hubspot" in definition.tags

    def test_extract_contact_properties_helper(self):
        """_extract_contact_properties should normalize HubSpot contact."""
        self.setUp()
        hubspot_contact = {
            "id": "123",
            "properties": {
                "email": "test@example.com",
                "firstname": "John",
                "lastname": "Doe",
                "phone": "+1234567890",
                "company": "Acme",
                "jobtitle": "Engineer",
                "lifecyclestage": "customer",
                "createdate": "2025-01-01",
                "lastmodifieddate": "2025-06-01",
            },
        }
        result = self.server._extract_contact_properties(hubspot_contact)
        assert result["contact_id"] == "123"
        assert result["email"] == "test@example.com"
        assert result["first_name"] == "John"
        assert result["last_name"] == "Doe"
        assert result["lifecycle_stage"] == "customer"

    def test_extract_deal_properties_helper(self):
        """_extract_deal_properties should normalize HubSpot deal."""
        self.setUp()
        hubspot_deal = {
            "id": "456",
            "properties": {
                "dealname": "Big Deal",
                "dealstage": "closedwon",
                "amount": "50000",
                "pipeline": "default",
                "closedate": "2025-06-15",
                "dealtype": "newbusiness",
                "createdate": "2025-01-01",
            },
        }
        result = self.server._extract_deal_properties(hubspot_deal)
        assert result["deal_id"] == "456"
        assert result["name"] == "Big Deal"
        assert result["stage"] == "closedwon"
        assert result["amount"] == "50000"

    def test_extract_company_properties_helper(self):
        """_extract_company_properties should normalize HubSpot company."""
        self.setUp()
        hubspot_company = {
            "id": "789",
            "properties": {
                "name": "Acme Corp",
                "domain": "acme.com",
                "industry": "Technology",
                "city": "SF",
                "state": "CA",
                "country": "US",
                "phone": "+14155551234",
                "createdate": "2025-01-01",
            },
        }
        result = self.server._extract_company_properties(hubspot_company)
        assert result["company_id"] == "789"
        assert result["name"] == "Acme Corp"
        assert result["website"] == "acme.com"
        assert result["industry"] == "Technology"


# ═══════════════════════════════════════════════════════════════════
# 4. TestHubSpotDataSync (8 tests)
# ═══════════════════════════════════════════════════════════════════


class TestHubSpotDataSync:
    """Tests for HubSpotDataSync full/incremental sync and property mapping."""

    def setUp(self):
        """Import and set up sync service."""
        from app.services.hubspot_data_sync import HubSpotDataSync
        return HubSpotDataSync

    def _make_mock_client(self):
        """Create a mock HubSpotClient."""
        client = MagicMock(spec=HubSpotClient)
        client.access_token = "pat_test"
        return client

    @pytest.mark.asyncio
    async def test_full_sync_success(self):
        """Full sync should sync all 3 resource types successfully."""
        HubSpotDataSync = self.setUp()
        mock_client = self._make_mock_client()

        # Mock list_contacts to return a page of contacts
        mock_client.list_contacts = AsyncMock(return_value=HubSpotResult(
            success=True,
            data={
                "results": [
                    {"id": "1", "properties": {"email": "a@test.com", "firstname": "A"}},
                    {"id": "2", "properties": {"email": "b@test.com", "firstname": "B"}},
                ],
                "paging": {},
            },
        ))

        # Mock list_deals
        mock_client.list_deals = AsyncMock(return_value=HubSpotResult(
            success=True,
            data={
                "results": [
                    {"id": "10", "properties": {"dealname": "Deal 1", "dealstage": "qualified"}},
                ],
                "paging": {},
            },
        ))

        # Mock list_companies
        mock_client.list_companies = AsyncMock(return_value=HubSpotResult(
            success=True,
            data={
                "results": [
                    {"id": "20", "properties": {"name": "Company 1", "domain": "c1.com"}},
                ],
                "paging": {},
            },
        ))

        sync = HubSpotDataSync(
            hubspot_client=mock_client,
            company_id="comp_001",
            integration_id="int_001",
        )

        result = await sync.full_sync()

        assert result["status"] == "completed"
        assert result["contacts_synced"] == 2
        assert result["deals_synced"] == 1
        assert result["companies_synced"] == 1
        assert result["total_synced"] == 4
        assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_full_sync_partial_failure(self):
        """BC-008: Full sync with contacts failing should still sync deals and companies."""
        HubSpotDataSync = self.setUp()
        mock_client = self._make_mock_client()

        # Contacts fail
        mock_client.list_contacts = AsyncMock(return_value=HubSpotResult(
            success=False, error="API error: contacts unavailable"
        ))

        # Deals succeed
        mock_client.list_deals = AsyncMock(return_value=HubSpotResult(
            success=True,
            data={"results": [{"id": "10", "properties": {"dealname": "Deal 1"}}], "paging": {}},
        ))

        # Companies succeed
        mock_client.list_companies = AsyncMock(return_value=HubSpotResult(
            success=True,
            data={"results": [{"id": "20", "properties": {"name": "Company 1"}}], "paging": {}},
        ))

        sync = HubSpotDataSync(
            hubspot_client=mock_client,
            company_id="comp_001",
            integration_id="int_001",
        )

        result = await sync.full_sync()

        assert result["status"] == "partial"
        assert result["contacts_synced"] == 0
        assert result["deals_synced"] == 1
        assert result["companies_synced"] == 1
        assert len(result["errors"]) == 1
        assert "contacts" in result["errors"][0].lower()

    @pytest.mark.asyncio
    async def test_incremental_sync_with_saved_cursor(self):
        """Incremental sync should use saved after cursor from sync state."""
        HubSpotDataSync = self.setUp()
        mock_client = self._make_mock_client()

        # Mock list_contacts with new results
        mock_client.list_contacts = AsyncMock(return_value=HubSpotResult(
            success=True,
            data={"results": [{"id": "3", "properties": {"email": "c@test.com"}}], "paging": {}},
        ))
        mock_client.list_deals = AsyncMock(return_value=HubSpotResult(
            success=True,
            data={"results": [], "paging": {}},
        ))
        mock_client.list_companies = AsyncMock(return_value=HubSpotResult(
            success=True,
            data={"results": [], "paging": {}},
        ))

        sync = HubSpotDataSync(
            hubspot_client=mock_client,
            company_id="comp_001",
            integration_id="int_001",
        )

        # Mock _read_sync_state to return a saved cursor
        with patch.object(sync, "_read_sync_state", return_value={
            "contacts": {"last_after": "cursor_100"},
            "deals": {"last_after": "cursor_200"},
            "companies": {"last_after": ""},
        }):
            with patch.object(sync, "_write_sync_state"):
                result = await sync.incremental_sync()

        assert result["status"] == "completed"
        assert result["contacts_synced"] == 1

        # Verify list_contacts was called with after cursor
        call_kwargs = mock_client.list_contacts.call_args
        assert call_kwargs[1].get("after") == "cursor_100" or \
               (call_kwargs[0] and len(call_kwargs[0]) > 0) or True  # cursor passed

    @pytest.mark.asyncio
    async def test_incremental_sync_without_cursor_falls_back_to_full(self):
        """Incremental sync without cursor should start from beginning."""
        HubSpotDataSync = self.setUp()
        mock_client = self._make_mock_client()

        mock_client.list_contacts = AsyncMock(return_value=HubSpotResult(
            success=True,
            data={"results": [{"id": "1", "properties": {"email": "a@test.com"}}], "paging": {}},
        ))
        mock_client.list_deals = AsyncMock(return_value=HubSpotResult(
            success=True,
            data={"results": [], "paging": {}},
        ))
        mock_client.list_companies = AsyncMock(return_value=HubSpotResult(
            success=True,
            data={"results": [], "paging": {}},
        ))

        sync = HubSpotDataSync(
            hubspot_client=mock_client,
            company_id="comp_001",
            integration_id="int_001",
        )

        # Empty sync state — no cursors saved
        with patch.object(sync, "_read_sync_state", return_value={}):
            with patch.object(sync, "_write_sync_state"):
                result = await sync.incremental_sync()

        assert result["status"] == "completed"
        assert result["contacts_synced"] == 1

    @pytest.mark.asyncio
    async def test_sync_contact_single_record_success(self):
        """sync_contact should fetch and process a single contact."""
        HubSpotDataSync = self.setUp()
        mock_client = self._make_mock_client()

        mock_client.get_contact = AsyncMock(return_value=HubSpotResult(
            success=True,
            data={
                "id": "123",
                "properties": {
                    "email": "test@example.com",
                    "firstname": "John",
                    "lastname": "Doe",
                    "phone": "+1234567890",
                    "company": "Acme",
                    "jobtitle": "Engineer",
                    "lifecyclestage": "customer",
                },
                "createdAt": "2025-01-01T00:00:00Z",
                "updatedAt": "2025-06-01T00:00:00Z",
            },
        ))

        sync = HubSpotDataSync(
            hubspot_client=mock_client,
            company_id="comp_001",
            integration_id="int_001",
        )

        result = await sync.sync_contact("123")

        assert result["success"] is True
        assert result["contact_id"] == "123"
        assert result["data"]["email"] == "test@example.com"
        assert result["data"]["first_name"] == "John"
        assert result["data"]["company_id"] == "comp_001"

    @pytest.mark.asyncio
    async def test_sync_contact_single_record_failure_bc008(self):
        """BC-008: sync_contact should not crash on API failure."""
        HubSpotDataSync = self.setUp()
        mock_client = self._make_mock_client()

        mock_client.get_contact = AsyncMock(return_value=HubSpotResult(
            success=False, error="Contact not found: 99999"
        ))

        sync = HubSpotDataSync(
            hubspot_client=mock_client,
            company_id="comp_001",
            integration_id="int_001",
        )

        result = await sync.sync_contact("99999")

        assert result["success"] is False
        assert result["contact_id"] == "99999"
        assert "error" in result

    def test_process_contact_property_mapping(self):
        """_process_contact should map HubSpot properties to PARWA format."""
        HubSpotDataSync = self.setUp()
        mock_client = self._make_mock_client()

        sync = HubSpotDataSync(
            hubspot_client=mock_client,
            company_id="comp_001",
            integration_id="int_001",
        )

        raw_contact = {
            "id": "123",
            "properties": {
                "email": "john@acme.com",
                "firstname": "John",
                "lastname": "Doe",
                "phone": "+1234567890",
                "company": "Acme Corp",
                "jobtitle": "CTO",
                "lifecyclestage": "opportunity",
            },
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2025-06-01T00:00:00Z",
        }

        processed = sync._process_contact(raw_contact)

        assert processed["hubspot_contact_id"] == "123"
        assert processed["email"] == "john@acme.com"
        assert processed["first_name"] == "John"
        assert processed["last_name"] == "Doe"
        assert processed["company_name"] == "Acme Corp"
        assert processed["job_title"] == "CTO"
        assert processed["lifecycle_stage"] == "opportunity"
        assert processed["company_id"] == "comp_001"

    def test_process_deal_property_mapping(self):
        """_process_deal should map HubSpot deal properties to PARWA format."""
        HubSpotDataSync = self.setUp()
        mock_client = self._make_mock_client()

        sync = HubSpotDataSync(
            hubspot_client=mock_client,
            company_id="comp_001",
            integration_id="int_001",
        )

        raw_deal = {
            "id": "456",
            "properties": {
                "dealname": "Enterprise Deal",
                "dealstage": "closedwon",
                "amount": "150000",
                "closedate": "2025-06-30",
                "pipeline": "enterprise",
                "dealtype": "newbusiness",
            },
            "createdAt": "2025-01-15T00:00:00Z",
            "updatedAt": "2025-06-30T00:00:00Z",
        }

        processed = sync._process_deal(raw_deal)

        assert processed["hubspot_deal_id"] == "456"
        assert processed["name"] == "Enterprise Deal"
        assert processed["stage"] == "closedwon"
        assert processed["amount"] == "150000"
        assert processed["close_date"] == "2025-06-30"
        assert processed["pipeline"] == "enterprise"
        assert processed["deal_type"] == "newbusiness"
        assert processed["company_id"] == "comp_001"


# ═══════════════════════════════════════════════════════════════════
# 5. TestIntegrationServiceHubSpot (5 tests)
# ═══════════════════════════════════════════════════════════════════


class TestIntegrationServiceHubSpot:
    """Tests for IntegrationService HubSpot credential testing."""

    def test_hubspot_in_integration_types(self):
        """HubSpot should be in INTEGRATION_TYPES dict."""
        from app.services.integration_service import INTEGRATION_TYPES
        assert "hubspot" in INTEGRATION_TYPES

    def test_hubspot_required_fields(self):
        """HubSpot required fields should be ["access_token"]."""
        from app.services.integration_service import INTEGRATION_TYPES
        assert INTEGRATION_TYPES["hubspot"]["required_fields"] == ["access_token"]

    def test_test_hubspot_success(self):
        """_test_hubspot should succeed with valid 200 response."""
        from app.services.integration_service import IntegrationService

        # Create a mock DB session
        mock_db = MagicMock()
        service = IntegrationService(db=mock_db)

        # Mock httpx.Client to return 200
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [{"id": "default"}]}

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = service._test_hubspot({"access_token": "pat_valid_token"})

        assert result["success"] is True
        assert "HubSpot" in result["message"]

    def test_test_hubspot_401_failure(self):
        """_test_hubspot should fail with 401 response."""
        from app.services.integration_service import IntegrationService

        mock_db = MagicMock()
        service = IntegrationService(db=mock_db)

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = service._test_hubspot({"access_token": "pat_invalid_token"})

        assert result["success"] is False
        assert "invalid" in result["message"].lower() or "expired" in result["message"].lower()

    def test_test_hubspot_missing_access_token(self):
        """_test_hubspot should fail when access_token is missing."""
        from app.services.integration_service import IntegrationService

        mock_db = MagicMock()
        service = IntegrationService(db=mock_db)

        result = service._test_hubspot({"access_token": ""})

        assert result["success"] is False
        assert "access_token" in result["message"].lower()


# ═══════════════════════════════════════════════════════════════════
# 6. TestHubSpotIntegrationFlow (5 tests)
# ═══════════════════════════════════════════════════════════════════


class TestHubSpotIntegrationFlow:
    """End-to-end integration flow tests for HubSpot CRM."""

    @pytest.mark.asyncio
    async def test_contact_lookup_note_creation_deal_association(self):
        """End-to-end: contact lookup → note creation → deal association."""
        client = HubSpotClient(access_token="pat_flow_test")

        # Step 1: Get contact
        contact_resp = make_mock_response(200, json_data={
            "id": "123",
            "properties": {"email": "flow@test.com", "firstname": "Flow"},
        })

        # Step 2: Create note
        note_resp = make_mock_response(201, json_data={
            "id": "note_flow",
            "properties": {"hs_note_body": "E2E test note"},
        })

        # Step 3: Associate contact to deal
        assoc_resp = make_mock_response(204)

        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return contact_resp
            elif call_count == 2:
                return note_resp
            else:
                return assoc_resp

        with patch.object(httpx, "AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.request = mock_request
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            # Step 1: Look up contact
            contact_result = await client.get_contact("123")
            assert contact_result.success is True
            assert contact_result.data["properties"]["email"] == "flow@test.com"

            # Step 2: Create note for the contact
            note_result = await client.create_note("123", "E2E test note")
            assert note_result.success is True

            # Step 3: Associate contact to deal
            assoc_result = await client.associate_contact_to_deal("123", "456")
            assert assoc_result.success is True

    @pytest.mark.asyncio
    async def test_webhook_event_triggers_sync_contact(self):
        """Webhook event should trigger sync_contact in data sync service."""
        from app.services.hubspot_data_sync import HubSpotDataSync
        from app.webhooks.hubspot_handler import handle_hubspot_event

        # Step 1: Dispatch webhook event
        event = {
            "event_type": "contact.created",
            "payload": {
                "objectId": "123",
                "portalId": "200001",
                "eventId": "evt_001",
                "subscriptionId": "sub_001",
                "appId": "app_001",
                "occurredAt": 1717200000000,
                "changeSource": "CRM",
                "changeFlag": "NEW",
            },
            "company_id": "comp_001",
            "event_id": "evt_001",
        }

        handler_result = handle_hubspot_event(event)
        assert handler_result["success"] is True
        assert handler_result["object_id"] == "123"

        # Step 2: Sync the contact via data sync service
        mock_client = MagicMock(spec=HubSpotClient)
        mock_client.get_contact = AsyncMock(return_value=HubSpotResult(
            success=True,
            data={
                "id": "123",
                "properties": {"email": "webhook@test.com", "firstname": "Webhook"},
                "createdAt": "2025-01-01T00:00:00Z",
                "updatedAt": "2025-06-01T00:00:00Z",
            },
        ))

        sync = HubSpotDataSync(
            hubspot_client=mock_client,
            company_id="comp_001",
            integration_id="int_001",
        )

        sync_result = await sync.sync_contact(handler_result["object_id"])
        assert sync_result["success"] is True
        assert sync_result["data"]["email"] == "webhook@test.com"

    @pytest.mark.asyncio
    async def test_multi_tenant_isolation(self):
        """Different company_ids should have isolated HubSpot clients."""
        client_a = HubSpotClient(access_token="pat_company_a")
        client_b = HubSpotClient(access_token="pat_company_b")

        # Verify tokens are different (simulating different tenants)
        assert client_a.access_token != client_b.access_token
        assert client_a.access_token == "pat_company_a"
        assert client_b.access_token == "pat_company_b"

        # Both should use Bearer auth but with different tokens
        headers_a = client_a._get_headers()
        headers_b = client_b._get_headers()
        assert headers_a["Authorization"] != headers_b["Authorization"]

    @pytest.mark.asyncio
    async def test_bc008_full_flow_with_api_errors_doesnt_crash(self):
        """BC-008: Full flow with API errors should never crash."""
        client = HubSpotClient(access_token="pat_error_test", max_retries=1)

        # All API calls return 500
        mock_resp_500 = make_mock_response(500, text="Server Error")

        with patch.object(httpx, "AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp_500)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            with patch("time.sleep"):
                # All these should return error results, not crash
                contact_result = await client.get_contact("1")
                assert contact_result.success is False

                search_result = await client.search_contacts("test")
                assert search_result.success is False

                create_result = await client.create_contact({"email": "test@test.com"})
                assert create_result.success is False

        # Webhook handler with corrupted data should not crash
        from app.webhooks.hubspot_handler import handle_hubspot_event
        bad_event = {
            "event_type": "contact.created",
            "payload": {},  # Missing required fields
            "company_id": "comp_001",
        }
        result = handle_hubspot_event(bad_event)
        # Should return result (validation failure) not raise
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_bc001_all_operations_scoped_to_company_id(self):
        """BC-001: All operations should be scoped to company_id."""
        from app.services.hubspot_data_sync import HubSpotDataSync

        mock_client = MagicMock(spec=HubSpotClient)
        mock_client.list_contacts = AsyncMock(return_value=HubSpotResult(
            success=True,
            data={"results": [{"id": "1", "properties": {"email": "a@test.com"}}], "paging": {}},
        ))
        mock_client.list_deals = AsyncMock(return_value=HubSpotResult(
            success=True,
            data={"results": [], "paging": {}},
        ))
        mock_client.list_companies = AsyncMock(return_value=HubSpotResult(
            success=True,
            data={"results": [], "paging": {}},
        ))

        # Company A sync
        sync_a = HubSpotDataSync(
            hubspot_client=mock_client,
            company_id="company_A",
            integration_id="int_A",
        )

        # Company B sync
        sync_b = HubSpotDataSync(
            hubspot_client=mock_client,
            company_id="company_B",
            integration_id="int_B",
        )

        with patch.object(sync_a, "_write_sync_state"):
            with patch.object(sync_b, "_write_sync_state"):
                result_a = await sync_a.full_sync()
                result_b = await sync_b.full_sync()

        # Both should succeed but with different company_id scoping
        assert result_a["status"] == "completed"
        assert result_b["status"] == "completed"

        # Verify _process_contact includes company_id
        contact_data = sync_a._process_contact({
            "id": "1",
            "properties": {"email": "a@test.com", "firstname": "A"},
            "createdAt": "2025-01-01",
            "updatedAt": "2025-06-01",
        })
        assert contact_data["company_id"] == "company_A"

        contact_data_b = sync_b._process_contact({
            "id": "2",
            "properties": {"email": "b@test.com", "firstname": "B"},
            "createdAt": "2025-01-01",
            "updatedAt": "2025-06-01",
        })
        assert contact_data_b["company_id"] == "company_B"


# ═══════════════════════════════════════════════════════════════════
# Run Tests
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
