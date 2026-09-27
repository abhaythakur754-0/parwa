"""
Unit tests for CRMBridge.push_permanent_failure (BC-017).

Verifies that all 3 CRM adapters (Zendesk, HubSpot, Generic) correctly
reset the CRM ticket to its "open"/"new" state when AI gives up, and
include the right tags + internal notes for the human agent.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ══════════════════════════════════════════════════════════════════
# 1. CRMBridge.push_permanent_failure — static method dispatch
# ══════════════════════════════════════════════════════════════════


class TestCRMBridgeDispatch:
    """The CRMBridge static method should route to the correct adapter."""

    def test_dispatches_to_zendesk_adapter(self):
        from app.core.crm_bridge.crm_bridge import CRMBridge

        with patch(
            "app.core.crm_bridge.crm_bridge.ZendeskAdapter.push_permanent_failure_to_crm",
            new=AsyncMock(return_value={"success": True, "crm_status": "open"}),
        ) as mock_adapter:
            result = asyncio.run(CRMBridge.push_permanent_failure(
                provider="zendesk",
                ticket_id="ZD-1",
                attempts=3,
                failure_context={"last_quality": 0.4},
            ))
        assert result["success"] is True
        assert mock_adapter.await_count == 1

    def test_dispatches_to_hubspot_adapter(self):
        from app.core.crm_bridge.crm_bridge import CRMBridge

        with patch(
            "app.core.crm_bridge.crm_bridge.HubSpotAdapter.push_permanent_failure_to_crm",
            new=AsyncMock(return_value={"success": True, "crm_status": "1"}),
        ) as mock_adapter:
            result = asyncio.run(CRMBridge.push_permanent_failure(
                provider="hubspot",
                ticket_id="12345",
                attempts=3,
                failure_context={"last_quality": 0.4},
            ))
        assert result["success"] is True
        assert mock_adapter.await_count == 1

    def test_dispatches_to_generic_adapter_on_unknown_provider(self):
        from app.core.crm_bridge.crm_bridge import CRMBridge

        with patch(
            "app.core.crm_bridge.crm_bridge.GenericCRMAdapter.push_permanent_failure_to_crm",
            new=AsyncMock(return_value={"success": True, "crm_status": "new"}),
        ) as mock_adapter:
            result = asyncio.run(CRMBridge.push_permanent_failure(
                provider="custom_crm",  # not in registry → generic fallback
                ticket_id="CRM-1",
                attempts=3,
                failure_context={},
            ))
        assert result["success"] is True
        assert mock_adapter.await_count == 1

    def test_returns_failure_dict_on_exception(self):
        from app.core.crm_bridge.crm_bridge import CRMBridge

        with patch(
            "app.core.crm_bridge.crm_bridge.ZendeskAdapter.push_permanent_failure_to_crm",
            new=AsyncMock(side_effect=RuntimeError("network down")),
        ):
            result = asyncio.run(CRMBridge.push_permanent_failure(
                provider="zendesk",
                ticket_id="ZD-1",
                attempts=3,
                failure_context={},
            ))
        assert result["success"] is False
        assert "network down" in result["error"]
        assert result["crm_ticket_id"] == "ZD-1"


# ══════════════════════════════════════════════════════════════════
# 2. Zendesk adapter — resets to "open" + adds tags
# ══════════════════════════════════════════════════════════════════


class TestZendeskPermanentFailure:
    """Zendesk push_permanent_failure_to_crm resets ticket to 'open'."""

    def test_returns_open_status_on_success(self):
        from app.core.crm_bridge.crm_bridge import ZendeskAdapter

        adapter = ZendeskAdapter()
        # Mock httpx.AsyncClient
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.put = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(adapter.push_permanent_failure_to_crm(
                ticket_id="ZD-777",
                attempts=3,
                failure_context={
                    "last_quality": 0.45,
                    "failure_analysis": "Quality too low",
                    "what_was_tried": "Guidance flow with CoT + Reflexion",
                    "ticket_type": "refund_request",
                    "complexity": "medium",
                },
                config={"subdomain": "test", "api_key": "k", "email": "e"},
            ))
        assert result["success"] is True
        assert result["crm_status"] == "open"
        assert result["crm_provider"] == "zendesk"

        # Verify the PUT payload resets status to "open" + tags
        put_call = mock_client.put.call_args
        payload = put_call.kwargs["json"]
        assert payload["ticket"]["status"] == "open"
        assert "ai-cannot-resolve" in payload["ticket"]["tags"]
        assert "needs-human" in payload["ticket"]["tags"]
        assert payload["ticket"]["comment"]["public"] is False

    def test_returns_failure_on_missing_config(self):
        from app.core.crm_bridge.crm_bridge import ZendeskAdapter

        adapter = ZendeskAdapter()
        result = asyncio.run(adapter.push_permanent_failure_to_crm(
            ticket_id="ZD-777",
            attempts=3,
            failure_context={},
            config=None,
        ))
        assert result["success"] is False
        assert "No Zendesk config" in result["error"]

    def test_internal_note_includes_attempts_and_quality(self):
        from app.core.crm_bridge.crm_bridge import ZendeskAdapter

        adapter = ZendeskAdapter()
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.put = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            asyncio.run(adapter.push_permanent_failure_to_crm(
                ticket_id="ZD-777",
                attempts=3,
                failure_context={
                    "last_quality": 0.45,
                    "failure_analysis": "Quality too low",
                    "what_was_tried": "CoT",
                    "ticket_type": "refund_request",
                    "complexity": "medium",
                },
                config={"subdomain": "test", "api_key": "k", "email": "e"},
            ))
        put_call = mock_client.put.call_args
        note_body = put_call.kwargs["json"]["ticket"]["comment"]["body"]
        assert "3 times" in note_body
        assert "0.45" in note_body
        assert "refund_request" in note_body


# ══════════════════════════════════════════════════════════════════
# 3. HubSpot adapter — resets to pipeline stage 1 (New)
# ══════════════════════════════════════════════════════════════════


class TestHubSpotPermanentFailure:
    """HubSpot push_permanent_failure_to_crm resets to stage 1 (New)."""

    def test_returns_new_status_on_success(self):
        from app.core.crm_bridge.crm_bridge import HubSpotAdapter

        adapter = HubSpotAdapter()
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.patch = AsyncMock(return_value=mock_resp)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(adapter.push_permanent_failure_to_crm(
                ticket_id="12345",
                attempts=3,
                failure_context={
                    "last_quality": 0.4,
                    "failure_analysis": "low quality",
                    "what_was_tried": "guidance",
                    "ticket_type": "billing",
                    "complexity": "high",
                },
                config={"access_token": "tok"},
            ))
        assert result["success"] is True
        assert result["crm_status"] == "1"  # New stage

        # Verify the PATCH payload resets to stage 1
        patch_call = mock_client.patch.call_args
        payload = patch_call.kwargs["json"]
        assert payload["properties"]["hs_pipeline_stage"] == "1"
        assert payload["properties"]["hs_ticket_category"] == "PARWA_AI_CANNOT_RESOLVE"

    def test_returns_failure_on_missing_config(self):
        from app.core.crm_bridge.crm_bridge import HubSpotAdapter

        adapter = HubSpotAdapter()
        result = asyncio.run(adapter.push_permanent_failure_to_crm(
            ticket_id="12345",
            attempts=3,
            failure_context={},
            config=None,
        ))
        assert result["success"] is False
        assert "No HubSpot config" in result["error"]


# ══════════════════════════════════════════════════════════════════
# 4. Generic adapter — emits parwa.cannot_resolve webhook
# ══════════════════════════════════════════════════════════════════


class TestGenericPermanentFailure:
    """Generic adapter emits a parwa.cannot_resolve webhook event."""

    def test_emits_cannot_resolve_event(self):
        from app.core.crm_bridge.crm_bridge import GenericCRMAdapter

        adapter = GenericCRMAdapter()
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(adapter.push_permanent_failure_to_crm(
                ticket_id="CRM-1",
                attempts=3,
                failure_context={"last_quality": 0.4},
                config={"webhook_url": "https://example.com/hook"},
            ))
        assert result["success"] is True
        assert result["crm_status"] == "new"

        post_call = mock_client.post.call_args
        payload = post_call.kwargs["json"]
        assert payload["event"] == "parwa.cannot_resolve"
        assert payload["action"] == "reset_to_new"
        assert payload["attempts"] == 3

    def test_returns_failure_on_missing_webhook_url(self):
        from app.core.crm_bridge.crm_bridge import GenericCRMAdapter

        adapter = GenericCRMAdapter()
        result = asyncio.run(adapter.push_permanent_failure_to_crm(
            ticket_id="CRM-1",
            attempts=3,
            failure_context={},
            config=None,
        ))
        assert result["success"] is False
        assert "No webhook URL" in result["error"]


# ══════════════════════════════════════════════════════════════════
# 5. ABSTRACT METHOD PRESENT ON BASE CLASS
# ══════════════════════════════════════════════════════════════════


class TestAbstractContract:
    """Verify push_permanent_failure_to_crm is on the abstract base."""

    def test_abstract_method_exists_on_base(self):
        from app.core.crm_bridge.crm_bridge import CRMAdapter
        assert hasattr(CRMAdapter, "push_permanent_failure_to_crm")
        # It must be abstract
        assert getattr(
            CRMAdapter.push_permanent_failure_to_crm, "__isabstractmethod__", False
        ) is True

    def test_all_concrete_adapters_implement_it(self):
        from app.core.crm_bridge.crm_bridge import (
            ZendeskAdapter, HubSpotAdapter, GenericCRMAdapter,
        )
        for cls in (ZendeskAdapter, HubSpotAdapter, GenericCRMAdapter):
            # The concrete class should override the abstract method
            method = getattr(cls, "push_permanent_failure_to_crm")
            assert not getattr(method, "__isabstractmethod__", False), \
                f"{cls.__name__} did not override push_permanent_failure_to_crm"
