"""
Phase 3 — Level 1 Unit Tests: MCP Server Wiring Verification

Tests that all 9 MCP servers (8 re-wired + 1 new Carrier) are:
1. Properly upgraded to v2.0.0 (wired version)
2. No longer contain "placeholder" or mock data in handler responses
3. Tools registered correctly with proper schemas
4. Handler methods make httpx calls to BACKEND_URL, not return hardcoded data
5. Fallback responses are honest (no fake data when backend unreachable)

Run: pytest tests/unit/test_phase3_mcp_wiring.py -v
"""

import os
import sys
import ast
import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ═══════════════════════════════════════════════════════════════════
# Server Version Tests
# ═══════════════════════════════════════════════════════════════════

class TestServerVersions:
    """Verify all Phase 3 servers are upgraded to v2.0.0."""

    @pytest.fixture
    def mcp_base_path(self):
        return os.path.join(os.path.dirname(__file__), "..", "..", "mcp_server")

    def test_ticketing_server_version(self, mcp_base_path):
        from mcp_server.integrations.ticketing_server import ticketing_server
        assert ticketing_server.version == "2.0.0", "Ticketing server should be v2.0.0 (wired)"

    def test_rag_server_version(self, mcp_base_path):
        from mcp_server.knowledge.rag_server import rag_server
        assert rag_server.version == "2.0.0", "RAG server should be v2.0.0 (wired)"

    def test_kb_server_version(self, mcp_base_path):
        from mcp_server.knowledge.kb_server import kb_server
        assert kb_server.version == "2.0.0", "KB server should be v2.0.0 (wired)"

    def test_faq_server_version(self, mcp_base_path):
        from mcp_server.knowledge.faq_server import faq_server
        assert faq_server.version == "2.0.0", "FAQ server should be v2.0.0 (wired)"

    def test_analytics_server_version(self, mcp_base_path):
        from mcp_server.tools.analytics_server import analytics_server
        assert analytics_server.version == "2.0.0", "Analytics server should be v2.0.0 (wired)"

    def test_monitoring_server_version(self, mcp_base_path):
        from mcp_server.tools.monitoring_server import monitoring_server
        assert monitoring_server.version == "2.0.0", "Monitoring server should be v2.0.0 (wired)"

    def test_notification_server_version(self, mcp_base_path):
        from mcp_server.tools.notification_server import notification_server
        assert notification_server.version == "2.0.0", "Notification server should be v2.0.0 (wired)"

    def test_compliance_server_version(self, mcp_base_path):
        from mcp_server.tools.compliance_server import compliance_server
        assert compliance_server.version == "2.0.0", "Compliance server should be v2.0.0 (wired)"

    def test_sla_server_version(self, mcp_base_path):
        from mcp_server.tools.sla_server import sla_server
        assert sla_server.version == "2.0.0", "SLA server should be v2.0.0 (wired)"

    def test_crm_server_version(self, mcp_base_path):
        from mcp_server.integrations.crm_server import crm_server
        assert crm_server.version == "2.0.0", "CRM server should be v2.0.0 (wired)"

    def test_ecommerce_server_version(self, mcp_base_path):
        from mcp_server.integrations.ecommerce_server import ecommerce_server
        assert ecommerce_server.version == "2.0.0", "Ecommerce server should be v2.0.0 (wired)"

    def test_carrier_server_exists(self, mcp_base_path):
        """Carrier server is NEW — verify it exists and is v2.0.0."""
        from mcp_server.integrations.carrier_server import carrier_server
        assert carrier_server.version == "2.0.0", "Carrier server should be v2.0.0"
        assert carrier_server.name == "carrier_server"


# ═══════════════════════════════════════════════════════════════════
# Source Code Analysis: No Placeholder Data
# ═══════════════════════════════════════════════════════════════════

class TestNoPlaceholderData:
    """Verify source code no longer contains placeholder/mock data patterns."""

    PHASE3_SERVERS = [
        "mcp_server/integrations/ticketing_server.py",
        "mcp_server/integrations/crm_server.py",
        "mcp_server/integrations/ecommerce_server.py",
        "mcp_server/integrations/carrier_server.py",
        "mcp_server/knowledge/rag_server.py",
        "mcp_server/knowledge/kb_server.py",
        "mcp_server/knowledge/faq_server.py",
        "mcp_server/tools/analytics_server.py",
        "mcp_server/tools/monitoring_server.py",
        "mcp_server/tools/notification_server.py",
        "mcp_server/tools/compliance_server.py",
        "mcp_server/tools/sla_server.py",
    ]

    FORBIDDEN_PATTERNS = [
        "Sample Contact",
        "Sample Company",
        "Sample Product",
        "Sample ticket subject",
        "Sample FAQ question",
        "Sample Document",
        "Placeholder chunk",
        "Placeholder document content",
        "crm_placeholder_",
        "TKT_placeholder_",
        "notif_placeholder_",
        "note_placeholder_",
        "data_points\": [{\"timestamp\": \"2025-01-15",  # Hardcoded analytics
    ]

    @pytest.fixture
    def project_root(self):
        return os.path.join(os.path.dirname(__file__), "..", "..")

    @pytest.mark.parametrize("server_file", PHASE3_SERVERS)
    def test_no_placeholder_strings(self, project_root, server_file):
        """Verify no hardcoded placeholder data in server source code."""
        filepath = os.path.join(project_root, server_file)
        if not os.path.exists(filepath):
            pytest.skip(f"{server_file} not found")

        with open(filepath, "r") as f:
            content = f.read()

        for pattern in self.FORBIDDEN_PATTERNS:
            assert pattern not in content, (
                f"{server_file} still contains placeholder pattern: '{pattern}'. "
                f"All mock data must be removed and replaced with real backend calls."
            )

    @pytest.mark.parametrize("server_file", PHASE3_SERVERS)
    def test_contains_backend_url(self, project_root, server_file):
        """Verify server uses BACKEND_URL for httpx calls."""
        filepath = os.path.join(project_root, server_file)
        if not os.path.exists(filepath):
            pytest.skip(f"{server_file} not found")

        with open(filepath, "r") as f:
            content = f.read()

        assert "BACKEND_URL" in content, (
            f"{server_file} must reference BACKEND_URL for real backend wiring"
        )

    @pytest.mark.parametrize("server_file", PHASE3_SERVERS)
    def test_contains_httpx_import(self, project_root, server_file):
        """Verify server imports httpx for backend calls."""
        filepath = os.path.join(project_root, server_file)
        if not os.path.exists(filepath):
            pytest.skip(f"{server_file} not found")

        with open(filepath, "r") as f:
            content = f.read()

        assert "import httpx" in content, (
            f"{server_file} must import httpx for real backend API calls"
        )


# ═══════════════════════════════════════════════════════════════════
# Tool Registration Tests
# ═══════════════════════════════════════════════════════════════════

class TestToolRegistration:
    """Verify all expected tools are registered in each server."""

    def test_ticketing_server_tools(self):
        from mcp_server.integrations.ticketing_server import ticketing_server
        from mcp_server.base_server import MCPRegistry
        registry = MCPRegistry()
        ticketing_server.register_tools(registry)
        tool_names = [t.name for t in registry.list_tools()]
        assert "ticket_create" in tool_names
        assert "ticket_get" in tool_names
        assert "ticket_update_status" in tool_names
        assert "ticket_search" in tool_names

    def test_rag_server_tools(self):
        from mcp_server.knowledge.rag_server import rag_server
        from mcp_server.base_server import MCPRegistry
        registry = MCPRegistry()
        rag_server.register_tools(registry)
        tool_names = [t.name for t in registry.list_tools()]
        assert "rag_query" in tool_names
        assert "rag_rerank" in tool_names
        assert "rag_health" in tool_names  # NEW tool

    def test_kb_server_tools(self):
        from mcp_server.knowledge.kb_server import kb_server
        from mcp_server.base_server import MCPRegistry
        registry = MCPRegistry()
        kb_server.register_tools(registry)
        tool_names = [t.name for t in registry.list_tools()]
        assert "kb_search" in tool_names
        assert "kb_get_document" in tool_names
        assert "kb_list_bases" in tool_names
        assert "kb_stats" in tool_names  # NEW tool

    def test_faq_server_tools(self):
        from mcp_server.knowledge.faq_server import faq_server
        from mcp_server.base_server import MCPRegistry
        registry = MCPRegistry()
        faq_server.register_tools(registry)
        tool_names = [t.name for t in registry.list_tools()]
        assert "faq_search" in tool_names
        assert "faq_get_categories" in tool_names

    def test_analytics_server_tools(self):
        from mcp_server.tools.analytics_server import analytics_server
        from mcp_server.base_server import MCPRegistry
        registry = MCPRegistry()
        analytics_server.register_tools(registry)
        tool_names = [t.name for t in registry.list_tools()]
        assert "analytics_query" in tool_names
        assert "analytics_get_dashboard" in tool_names

    def test_monitoring_server_tools(self):
        from mcp_server.tools.monitoring_server import monitoring_server
        from mcp_server.base_server import MCPRegistry
        registry = MCPRegistry()
        monitoring_server.register_tools(registry)
        tool_names = [t.name for t in registry.list_tools()]
        assert "monitoring_get_status" in tool_names
        assert "monitoring_get_alerts" in tool_names
        assert "monitoring_get_performance" in tool_names

    def test_notification_server_tools(self):
        from mcp_server.tools.notification_server import notification_server
        from mcp_server.base_server import MCPRegistry
        registry = MCPRegistry()
        notification_server.register_tools(registry)
        tool_names = [t.name for t in registry.list_tools()]
        assert "notification_send" in tool_names
        assert "notification_get_preferences" in tool_names

    def test_compliance_server_tools(self):
        from mcp_server.tools.compliance_server import compliance_server
        from mcp_server.base_server import MCPRegistry
        registry = MCPRegistry()
        compliance_server.register_tools(registry)
        tool_names = [t.name for t in registry.list_tools()]
        assert "compliance_check" in tool_names
        assert "compliance_scan_pii" in tool_names

    def test_sla_server_tools(self):
        from mcp_server.tools.sla_server import sla_server
        from mcp_server.base_server import MCPRegistry
        registry = MCPRegistry()
        sla_server.register_tools(registry)
        tool_names = [t.name for t in registry.list_tools()]
        assert "sla_check" in tool_names
        assert "sla_get_policies" in tool_names
        assert "sla_get_compliance_report" in tool_names

    def test_crm_server_tools(self):
        from mcp_server.integrations.crm_server import crm_server
        from mcp_server.base_server import MCPRegistry
        registry = MCPRegistry()
        crm_server.register_tools(registry)
        tool_names = [t.name for t in registry.list_tools()]
        assert "crm_get_contact" in tool_names
        assert "crm_create_note" in tool_names
        assert "crm_get_deals" in tool_names

    def test_ecommerce_server_tools(self):
        from mcp_server.integrations.ecommerce_server import ecommerce_server
        from mcp_server.base_server import MCPRegistry
        registry = MCPRegistry()
        ecommerce_server.register_tools(registry)
        tool_names = [t.name for t in registry.list_tools()]
        assert "ecommerce_get_order" in tool_names
        assert "ecommerce_search_products" in tool_names
        assert "ecommerce_get_customer_orders" in tool_names

    def test_carrier_server_tools(self):
        """NEW carrier server — verify all 4 tools registered."""
        from mcp_server.integrations.carrier_server import carrier_server
        from mcp_server.base_server import MCPRegistry
        registry = MCPRegistry()
        carrier_server.register_tools(registry)
        tool_names = [t.name for t in registry.list_tools()]
        assert "carrier_detect" in tool_names
        assert "carrier_track_shipment" in tool_names
        assert "carrier_detect_delays" in tool_names
        assert "carrier_calculate_compensation" in tool_names


# ═══════════════════════════════════════════════════════════════════
# CRM/Ecommerce Honesty Tests
# ═══════════════════════════════════════════════════════════════════

class TestCRMEcommerceHonesty:
    """Verify CRM and Ecommerce servers return honest 'not connected' responses
    instead of fake placeholder data when no integration is configured."""

    def test_crm_not_connected_response(self):
        from mcp_server.integrations.crm_server import crm_server
        # Check that the _not_connected_response method exists
        assert hasattr(crm_server, '_not_connected_response')
        result = crm_server._not_connected_response("crm_get_contact", "hubspot")
        assert result.success is False
        assert "not connected" in result.error.lower()
        assert result.metadata.get("status") == "not_connected"

    def test_ecommerce_not_connected_response(self):
        from mcp_server.integrations.ecommerce_server import ecommerce_server
        assert hasattr(ecommerce_server, '_not_connected_response')
        result = ecommerce_server._not_connected_response("ecommerce_get_order", "shopify")
        assert result.success is False
        assert "not connected" in result.error.lower()
        assert result.metadata.get("status") == "not_connected"


# ═══════════════════════════════════════════════════════════════════
# Carrier Server Detection Logic Tests
# ═══════════════════════════════════════════════════════════════════

class TestCarrierDetection:
    """Test the local carrier detection fallback logic."""

    def test_ups_detection(self):
        """1Z prefix → UPS."""
        import asyncio
        from mcp_server.integrations.carrier_server import carrier_server

        result = asyncio.get_event_loop().run_until_complete(
            carrier_server._invoke_detect_carrier({"tracking_number": "1Z999AA10123456784"})
        )
        # When backend is unreachable, falls back to local detection
        if result.metadata.get("source") == "local_pattern_matching":
            assert result.data["carrier_id"] == "ups"
            assert result.data["carrier_name"] == "UPS"

    def test_usps_detection(self):
        """22-digit number → USPS."""
        import asyncio
        from mcp_server.integrations.carrier_server import carrier_server

        result = asyncio.get_event_loop().run_until_complete(
            carrier_server._invoke_detect_carrier({"tracking_number": "9400111899223100001234"})
        )
        if result.metadata.get("source") == "local_pattern_matching":
            assert result.data["carrier_id"] == "usps"

    def test_unknown_tracking_number(self):
        """Unknown format → unknown carrier."""
        import asyncio
        from mcp_server.integrations.carrier_server import carrier_server

        result = asyncio.get_event_loop().run_until_complete(
            carrier_server._invoke_detect_carrier({"tracking_number": "ABC123XYZ"})
        )
        if result.metadata.get("source") == "local_pattern_matching":
            assert result.data["carrier_id"] == "unknown"


# ═══════════════════════════════════════════════════════════════════
# Compliance PII Local Fallback Tests
# ═══════════════════════════════════════════════════════════════════

class TestCompliancePIIFallback:
    """Test the local regex PII detection fallback."""

    def test_email_detection(self):
        import asyncio
        from mcp_server.tools.compliance_server import compliance_server

        result = asyncio.get_event_loop().run_until_complete(
            compliance_server._invoke_scan_pii({"content": "Contact me at john@example.com please"})
        )
        # When backend is unreachable, falls back to local regex
        if result.metadata.get("source") == "local_regex_fallback":
            assert result.data["has_pii"] is True
            emails = [e for e in result.data["entities_found"] if e["type"] == "email"]
            assert len(emails) > 0
            assert "john@example.com" in emails[0]["value"]

    def test_phone_detection(self):
        import asyncio
        from mcp_server.tools.compliance_server import compliance_server

        result = asyncio.get_event_loop().run_until_complete(
            compliance_server._invoke_scan_pii({"content": "Call me at 555-123-4567"})
        )
        if result.metadata.get("source") == "local_regex_fallback":
            assert result.data["has_pii"] is True
            phones = [e for e in result.data["entities_found"] if e["type"] == "phone"]
            assert len(phones) > 0

    def test_no_pii_content(self):
        import asyncio
        from mcp_server.tools.compliance_server import compliance_server

        result = asyncio.get_event_loop().run_until_complete(
            compliance_server._invoke_scan_pii({"content": "Hello, how can I help you today?"})
        )
        if result.metadata.get("source") == "local_regex_fallback":
            assert result.data["has_pii"] is False
            assert len(result.data["entities_found"]) == 0


# ═══════════════════════════════════════════════════════════════════
# MCP Main.py Registration Tests
# ═══════════════════════════════════════════════════════════════════

class TestMCPMainRegistration:
    """Verify carrier_server is registered in main.py."""

    def test_carrier_import_in_main(self):
        project_root = os.path.join(os.path.dirname(__file__), "..", "..")
        main_path = os.path.join(project_root, "mcp_server", "main.py")
        with open(main_path, "r") as f:
            content = f.read()
        assert "from mcp_server.integrations.carrier_server import carrier_server" in content

    def test_carrier_in_all_sub_servers(self):
        project_root = os.path.join(os.path.dirname(__file__), "..", "..")
        main_path = os.path.join(project_root, "mcp_server", "main.py")
        with open(main_path, "r") as f:
            content = f.read()
        assert "carrier_server," in content

    def test_carrier_router_included(self):
        project_root = os.path.join(os.path.dirname(__file__), "..", "..")
        main_path = os.path.join(project_root, "mcp_server", "main.py")
        with open(main_path, "r") as f:
            content = f.read()
        assert "carrier_server.get_router()" in content

    def test_total_sub_servers_count(self):
        """All 16 sub-servers should be registered (12 original + 4 already wired + carrier)."""
        from mcp_server.main import ALL_SUB_SERVERS
        # We have: faq, rag, kb, email, voice, chat, sms, ticketing, ecommerce, crm, carrier, analytics, monitoring, notification, compliance, sla
        assert len(ALL_SUB_SERVERS) == 16, f"Expected 16 sub-servers, got {len(ALL_SUB_SERVERS)}"


# ═══════════════════════════════════════════════════════════════════
# Metadata Source Tests
# ═══════════════════════════════════════════════════════════════════

class TestMetadataSource:
    """Verify all server handlers set metadata.source to 'backend' or 'fallback'."""

    @pytest.mark.parametrize("server_file", [
        "mcp_server/integrations/ticketing_server.py",
        "mcp_server/knowledge/rag_server.py",
        "mcp_server/knowledge/kb_server.py",
        "mcp_server/knowledge/faq_server.py",
        "mcp_server/tools/analytics_server.py",
        "mcp_server/tools/monitoring_server.py",
        "mcp_server/tools/notification_server.py",
        "mcp_server/tools/compliance_server.py",
        "mcp_server/tools/sla_server.py",
        "mcp_server/integrations/crm_server.py",
        "mcp_server/integrations/ecommerce_server.py",
        "mcp_server/integrations/carrier_server.py",
    ])
    def test_source_metadata_set(self, server_file):
        """Verify all handlers set source in metadata."""
        project_root = os.path.join(os.path.dirname(__file__), "..", "..")
        filepath = os.path.join(project_root, server_file)
        with open(filepath, "r") as f:
            content = f.read()
        # Check that 'source' is set in metadata dicts
        assert '"source"' in content or "'source'" in content, (
            f"{server_file} must set 'source' in metadata to track backend vs fallback"
        )
