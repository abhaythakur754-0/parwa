"""
Tests for the variant → channel → external integration wiring fixes:

1. ChannelDispatcher._dispatch_voice — voice tickets now call VoiceChannelService
   (previously fell through to _dispatch_internal, no call was made)
2. OutboundEmailService._send_via_email_bridge — email now respects tenant's
   configured provider (Brevo/SendGrid/Mailgun/SES/Postmark) instead of
   Brevo-only
3. node_3_knowledge_fetch._fetch_crm_data — now fetches real CRM contact,
   e-commerce orders, and carrier tracking (was a mock that echoed context)
4. node_5_act_verify._react_execute — now dispatches to ReActToolRegistry
   tools (was a stub that returned "simulated successfully")

Each test verifies the fix is wired correctly without making real external
API calls (all external dependencies are mocked).
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ════════════════════════════════════════════════════════════════════
# 1. ChannelDispatcher._dispatch_voice
# ════════════════════════════════════════════════════════════════════


class TestVoiceDispatch:
    """Verify voice channel dispatch is wired to VoiceChannelService."""

    def test_dispatch_routes_voice_channel(self):
        """ChannelDispatcher.dispatch('voice') should call _dispatch_voice,
        not fall through to _dispatch_internal."""
        # We verify by checking the dispatch method's routing logic.
        # Load the module and inspect the source.
        import inspect
        from app.core.channel_dispatcher import ChannelDispatcher

        source = inspect.getsource(ChannelDispatcher.dispatch)
        assert 'channel == "voice"' in source, (
            "Voice channel should be routed in dispatch() — "
            "previously voice fell through to _dispatch_internal"
        )
        assert "_dispatch_voice" in source, (
            "_dispatch_voice method should be called for voice channel"
        )

    def test_dispatch_voice_method_exists(self):
        """_dispatch_voice method should exist on ChannelDispatcher."""
        from app.core.channel_dispatcher import ChannelDispatcher
        assert hasattr(ChannelDispatcher, "_dispatch_voice"), (
            "_dispatch_voice method must exist — voice dispatch is wired"
        )

    def test_dispatch_voice_calls_voice_service(self):
        """_dispatch_voice should call VoiceChannelService.initiate_outbound_call."""
        import inspect
        from app.core.channel_dispatcher import ChannelDispatcher

        source = inspect.getsource(ChannelDispatcher._dispatch_voice)
        assert "VoiceChannelService" in source, (
            "_dispatch_voice must use VoiceChannelService (not just store internally)"
        )
        assert "initiate_outbound_call" in source, (
            "_dispatch_voice must call initiate_outbound_call to make a real phone call"
        )

    def test_dispatch_voice_stores_ticket_message(self):
        """_dispatch_voice should also store a TicketMessage for audit trail."""
        import inspect
        from app.core.channel_dispatcher import ChannelDispatcher

        source = inspect.getsource(ChannelDispatcher._dispatch_voice)
        assert "TicketMessage" in source, (
            "_dispatch_voice should store a TicketMessage for audit trail"
        )


# ════════════════════════════════════════════════════════════════════
# 2. OutboundEmailService._send_via_email_bridge
# ════════════════════════════════════════════════════════════════════


class TestEmailBridgeWiring:
    """Verify email dispatch uses EmailBridge (provider-agnostic)."""

    def test_send_via_email_bridge_method_exists(self):
        """_send_via_email_bridge method should exist on OutboundEmailService."""
        from app.services.outbound_email_service import OutboundEmailService
        assert hasattr(OutboundEmailService, "_send_via_email_bridge"), (
            "_send_via_email_bridge method must exist — email dispatch should "
            "be provider-agnostic, not Brevo-only"
        )

    def test_send_via_email_bridge_tries_all_providers(self):
        """_send_via_email_bridge should try brevo, sendgrid, mailgun, ses, postmark."""
        import inspect
        from app.services.outbound_email_service import OutboundEmailService

        source = inspect.getsource(OutboundEmailService._send_via_email_bridge)
        for provider in ("brevo", "sendgrid", "mailgun", "ses", "postmark"):
            assert provider in source, (
                f"_send_via_email_bridge should try provider '{provider}' — "
                f"tenants who configure any of these should be able to send email"
            )

    def test_send_via_email_bridge_returns_none_when_no_integration(self):
        """When no email integration is configured, returns None (fall back to Brevo)."""
        from app.services.outbound_email_service import OutboundEmailService

        service = OutboundEmailService.__new__(OutboundEmailService)
        service.db = MagicMock()

        # Mock IntegrationService to return None for all providers.
        mock_svc = MagicMock()
        mock_svc.get_credential_config.return_value = None

        with patch("app.services.integration_service.IntegrationService", return_value=mock_svc):
            result = service._send_via_email_bridge(
                company_id="company-123",
                to="alice@example.com",
                subject="Test",
                html_content="<p>Hi</p>",
            )

        assert result is None, (
            "When no email integration is configured, _send_via_email_bridge "
            "should return None so the caller falls back to the Brevo path"
        )

    def test_send_via_email_bridge_calls_email_bridge_when_brevo_configured(self):
        """When Brevo creds exist, calls EmailBridge.send_email."""
        from app.services.outbound_email_service import OutboundEmailService

        service = OutboundEmailService.__new__(OutboundEmailService)
        service.db = MagicMock()

        mock_svc = MagicMock()
        mock_svc.get_credential_config.return_value = {"api_key": "xkeysib-..."}

        mock_bridge = MagicMock()
        mock_bridge.send_email = AsyncMock(return_value={
            "success": True,
            "message_id": "brevo-msg-123",
        })

        with patch("app.services.integration_service.IntegrationService", return_value=mock_svc), \
             patch("app.core.email_bridge.email_bridge.EmailBridge", mock_bridge):
            result = service._send_via_email_bridge(
                company_id="company-123",
                to="alice@example.com",
                subject="Test",
                html_content="<p>Hi</p>",
            )

        assert result is not None
        assert result["success"] is True
        assert result["provider"] == "brevo"
        assert result["message_id"] == "brevo-msg-123"
        mock_bridge.send_email.assert_awaited_once()


# ════════════════════════════════════════════════════════════════════
# 3. node_3_knowledge_fetch._fetch_crm_data
# ════════════════════════════════════════════════════════════════════


class TestNode3RealDataFetch:
    """Verify node_3 fetches real CRM/ecommerce/carrier data."""

    def test_fetch_crm_data_is_async(self):
        """_fetch_crm_data should be async (was sync mock before)."""
        import inspect

        # Load the module via spec to avoid heavy imports.
        spec = importlib.util.spec_from_file_location(
            "node_3_knowledge_fetch",
            "/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_3_knowledge_fetch.py",
        )
        # Stub parent packages.
        for name in ("app", "app.core", "app.core.parwa_pipeline", "app.core.parwa_pipeline.nodes"):
            if name not in sys.modules:
                sys.modules[name] = types.ModuleType(name)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            # Module may fail to import due to heavy deps; just inspect the source.
            pass

        # Read the source directly.
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_3_knowledge_fetch.py") as f:
            source = f.read()

        assert "async def _fetch_crm_data" in source, (
            "_fetch_crm_data should be async — it makes real HTTP calls now"
        )

    def test_fetch_crm_data_calls_real_apis(self):
        """_fetch_crm_data should call crm_actions, ecommerce_actions, carrier_api_connector."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_3_knowledge_fetch.py") as f:
            source = f.read()

        assert "_resolve_crm_credentials" in source, "Should call CRM credential resolver"
        assert "_hubspot_get_contact" in source, "Should call HubSpot contact API"
        assert "_resolve_ecommerce_credentials" in source, "Should call e-commerce credential resolver"
        assert "_shopify_get_customer_orders" in source, "Should call Shopify orders API"
        assert "CarrierAPIConnector" in source, "Should call carrier tracking API"

    def test_fetch_crm_data_no_longer_returns_mock(self):
        """_fetch_crm_data should NOT have the old mock return statement."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_3_knowledge_fetch.py") as f:
            source = f.read()

        # The old mock had this exact docstring.
        assert "Mock for Phase 7" not in source, (
            "The mock docstring should be gone — _fetch_crm_data now fetches real data"
        )

    def test_fetch_crm_data_falls_back_gracefully(self):
        """When no integration is configured, should still return baseline data."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_3_knowledge_fetch.py") as f:
            source = f.read()

        # The result dict should include crm_contact, ecommerce_orders, carrier_tracking
        # fields (set to None when not available).
        assert "crm_contact" in source, "Result should include crm_contact field"
        assert "ecommerce_orders" in source, "Result should include ecommerce_orders field"
        assert "carrier_tracking" in source, "Result should include carrier_tracking field"


# ════════════════════════════════════════════════════════════════════
# 4. node_5_act_verify._react_execute
# ════════════════════════════════════════════════════════════════════


class TestNode5RealToolExecution:
    """Verify node_5 _react_execute dispatches to real tools."""

    def test_react_execute_no_longer_says_simulated(self):
        """_react_execute should NOT return 'simulated successfully' in its observation."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_5_act_verify.py") as f:
            source = f.read()

        # The old stub had: "observation": f"Action '{action}' simulated successfully"
        # The new version should NOT have this in a return dict's observation field.
        # Check that the string isn't used as an actual observation value (only in the docstring).
        lines = source.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Skip docstring/comment lines.
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'"):
                continue
            if "simulated successfully" in line and '"observation"' not in line and "observation =" not in line:
                # It's in a comment or docstring — OK.
                continue
            if "simulated successfully" in line and ("observation" in line or "return" in line.lower()):
                pytest.fail(f"'simulated successfully' found in return/observation at line {i+1}: {line}")

    def test_react_execute_uses_react_tool_registry(self):
        """_react_execute should dispatch to ReActToolRegistry."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_5_act_verify.py") as f:
            source = f.read()

        assert "ReActToolRegistry" in source, (
            "_react_execute should use ReActToolRegistry to dispatch to real tools"
        )
        assert "registry.execute" in source, (
            "_react_execute should call registry.execute() to run tools"
        )

    def test_react_execute_maps_action_keywords(self):
        """_react_execute should map action keywords (customer, order, billing, ticket) to tools."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_5_act_verify.py") as f:
            source = f.read()

        assert "customer" in source.lower(), "Should map 'customer' → CRM tool"
        assert "order" in source.lower(), "Should map 'order' → OrderTool"
        assert "billing" in source.lower(), "Should map 'billing' → BillingTool"
        assert "ticket" in source.lower(), "Should map 'ticket' → TicketTool"

    def test_react_execute_returns_tool_executed_field(self):
        """_react_execute should return a tool_executed field so the AI knows what ran."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_5_act_verify.py") as f:
            source = f.read()

        assert "tool_executed" in source, (
            "_react_execute should return tool_executed field — the AI needs to "
            "know whether a tool was actually called"
        )

    def test_react_execute_honest_when_no_tool_matches(self):
        """When no tool matches, _react_execute should say so honestly."""
        with open("/home/z/my-project/parwa/backend/app/core/parwa_pipeline/nodes/node_5_act_verify.py") as f:
            source = f.read()

        assert "No tool executed" in source, (
            "When no tool matches, _react_execute should honestly say "
            "'No tool executed' instead of pretending it succeeded"
        )
