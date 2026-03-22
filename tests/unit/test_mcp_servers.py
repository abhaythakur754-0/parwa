"""
Unit tests for PARWA MCP Tool Servers.

Tests for:
- NotificationServer: User notifications
- ComplianceServer: GDPR and compliance checks
- SLAServer: SLA calculation and escalation

CRITICAL: All servers must respond within 2 seconds.
"""
import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_servers.base_server import MCPServerState, ToolResult
from mcp_servers.tools.notification_server import NotificationServer
from mcp_servers.tools.compliance_server import ComplianceServer
from mcp_servers.tools.sla_server import SLAServer


# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFICATION SERVER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestNotificationServer:
    """Tests for Notification MCP server."""

    @pytest.fixture
    def notification_server(self):
        """Create Notification server instance."""
        return NotificationServer()

    @pytest.mark.asyncio
    async def test_server_starts(self, notification_server):
        """Test Notification server starts correctly."""
        await notification_server.start()
        assert notification_server.is_running is True

    @pytest.mark.asyncio
    async def test_server_stops(self, notification_server):
        """Test Notification server stops correctly."""
        await notification_server.start()
        await notification_server.stop()
        assert notification_server.state == MCPServerState.STOPPED

    @pytest.mark.asyncio
    async def test_send_notification_returns_id(self, notification_server):
        """Test send_notification returns notification_id."""
        await notification_server.start()
        result = await notification_server.handle_tool_call(
            "send_notification",
            {
                "user_id": "user_123",
                "message": "Test notification",
                "channel": "email"
            }
        )
        assert result.success is True
        assert "notification_id" in result.data
        assert result.data["status"] == "success"

    @pytest.mark.asyncio
    async def test_send_notification_with_all_params(self, notification_server):
        """Test send_notification with all parameters."""
        await notification_server.start()
        result = await notification_server.handle_tool_call(
            "send_notification",
            {
                "user_id": "user_123",
                "message": "Test notification",
                "channel": "sms",
                "title": "Test Title",
                "priority": "high",
                "metadata": {"order_id": "ORD-001"}
            }
        )
        assert result.success is True
        assert result.data["channel"] == "sms"

    @pytest.mark.asyncio
    async def test_send_notification_missing_channel_fails(self, notification_server):
        """Test send_notification fails without channel."""
        await notification_server.start()
        result = await notification_server.handle_tool_call(
            "send_notification",
            {
                "user_id": "user_123",
                "message": "Test notification"
            }
        )
        assert result.success is False
        assert "Missing required parameter" in result.error

    @pytest.mark.asyncio
    async def test_send_bulk_notifications(self, notification_server):
        """Test send_bulk_notifications sends to multiple users."""
        await notification_server.start()
        result = await notification_server.handle_tool_call(
            "send_bulk_notifications",
            {
                "user_ids": ["user_1", "user_2", "user_3"],
                "message": "Bulk test notification",
                "channel": "email"
            }
        )
        assert result.success is True
        assert "summary" in result.data
        assert result.data["summary"]["sent"] >= 0

    @pytest.mark.asyncio
    async def test_send_bulk_notifications_empty_list(self, notification_server):
        """Test send_bulk_notifications with empty list."""
        await notification_server.start()
        result = await notification_server.handle_tool_call(
            "send_bulk_notifications",
            {
                "user_ids": [],
                "message": "Test",
                "channel": "email"
            }
        )
        assert result.success is True
        assert result.data["summary"]["sent"] == 0

    @pytest.mark.asyncio
    async def test_get_notification_preferences(self, notification_server):
        """Test get_notification_preferences returns defaults."""
        await notification_server.start()
        result = await notification_server.handle_tool_call(
            "get_notification_preferences",
            {"user_id": "user_123"}
        )
        assert result.success is True
        assert "preferences" in result.data
        assert "channels" in result.data["preferences"]

    @pytest.mark.asyncio
    async def test_update_notification_preferences(self, notification_server):
        """Test update_preferences updates user preferences."""
        await notification_server.start()

        # Update preferences
        result = await notification_server.handle_tool_call(
            "update_preferences",
            {
                "user_id": "user_123",
                "preferences": {
                    "channels": {"email": False, "sms": True}
                }
            }
        )
        assert result.success is True

        # Verify update
        verify_result = await notification_server.handle_tool_call(
            "get_notification_preferences",
            {"user_id": "user_123"}
        )
        assert verify_result.data["preferences"]["channels"]["email"] is False
        assert verify_result.data["preferences"]["channels"]["sms"] is True

    @pytest.mark.asyncio
    async def test_notification_response_time(self, notification_server):
        """CRITICAL: Notification server must respond within 2 seconds."""
        await notification_server.start()
        start = time.time()
        await notification_server.handle_tool_call(
            "send_notification",
            {"user_id": "user_1", "message": "Test", "channel": "email"}
        )
        elapsed = (time.time() - start) * 1000
        assert elapsed < 2000, f"Response took {elapsed}ms"

    @pytest.mark.asyncio
    async def test_notification_health_check(self, notification_server):
        """Test health check returns valid status."""
        await notification_server.start()
        health = await notification_server.health_check()
        assert health["healthy"] is True
        assert "send_notification" in health["tools"]


# ═══════════════════════════════════════════════════════════════════════════════
# COMPLIANCE SERVER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestComplianceServer:
    """Tests for Compliance MCP server."""

    @pytest.fixture
    def compliance_server(self):
        """Create Compliance server instance."""
        return ComplianceServer()

    @pytest.mark.asyncio
    async def test_server_starts(self, compliance_server):
        """Test Compliance server starts correctly."""
        await compliance_server.start()
        assert compliance_server.is_running is True

    @pytest.mark.asyncio
    async def test_check_compliance_returns_status(self, compliance_server):
        """Test check_compliance returns compliance status."""
        await compliance_server.start()
        result = await compliance_server.handle_tool_call(
            "check_compliance",
            {
                "action": "data_export",
                "context": {"user_id": "user_123"},
                "jurisdiction": "EU"
            }
        )
        assert result.success is True
        assert "compliant" in result.data

    @pytest.mark.asyncio
    async def test_check_compliance_with_consent_requirement(self, compliance_server):
        """Test check_compliance for consent-required actions."""
        await compliance_server.start()
        result = await compliance_server.handle_tool_call(
            "check_compliance",
            {
                "action": "marketing_email",
                "context": {},
                "user_id": "user_123"
            }
        )
        assert result.success is True
        assert "requires_consent" in result.data

    @pytest.mark.asyncio
    async def test_check_compliance_missing_action_fails(self, compliance_server):
        """Test check_compliance fails without action."""
        await compliance_server.start()
        result = await compliance_server.handle_tool_call(
            "check_compliance",
            {"context": {}}
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_get_jurisdiction_rules(self, compliance_server):
        """Test get_jurisdiction_rules returns rules."""
        await compliance_server.start()
        result = await compliance_server.handle_tool_call(
            "get_jurisdiction_rules",
            {"jurisdiction": "EU"}
        )
        assert result.success is True
        assert "jurisdiction" in result.data

    @pytest.mark.asyncio
    async def test_get_jurisdiction_rules_unknown(self, compliance_server):
        """Test get_jurisdiction_rules for unknown jurisdiction."""
        await compliance_server.start()
        result = await compliance_server.handle_tool_call(
            "get_jurisdiction_rules",
            {"jurisdiction": "UNKNOWN"}
        )
        # May return error or default
        assert result.success is True

    @pytest.mark.asyncio
    async def test_gdpr_export(self, compliance_server):
        """Test gdpr_export exports user data."""
        await compliance_server.start()
        result = await compliance_server.handle_tool_call(
            "gdpr_export",
            {"user_id": "user_123"}
        )
        assert result.success is True
        assert "request_id" in result.data
        assert "user_id" in result.data

    @pytest.mark.asyncio
    async def test_gdpr_export_with_pii(self, compliance_server):
        """Test gdpr_export with PII inclusion."""
        await compliance_server.start()
        result = await compliance_server.handle_tool_call(
            "gdpr_export",
            {
                "user_id": "user_123",
                "include_pii": True
            }
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_gdpr_delete(self, compliance_server):
        """Test gdpr_delete deletes user data."""
        await compliance_server.start()
        result = await compliance_server.handle_tool_call(
            "gdpr_delete",
            {"user_id": "user_123"}
        )
        assert result.success is True
        assert "request_id" in result.data
        assert "records_processed" in result.data

    @pytest.mark.asyncio
    async def test_gdpr_delete_with_retention(self, compliance_server):
        """Test gdpr_delete with retention exceptions."""
        await compliance_server.start()
        result = await compliance_server.handle_tool_call(
            "gdpr_delete",
            {
                "user_id": "user_123",
                "retention_exceptions": ["legal_obligation"]
            }
        )
        assert result.success is True
        assert "records_retained" in result.data

    @pytest.mark.asyncio
    async def test_compliance_response_time(self, compliance_server):
        """CRITICAL: Compliance server must respond within 2 seconds."""
        await compliance_server.start()
        start = time.time()
        await compliance_server.handle_tool_call(
            "check_compliance",
            {"action": "data_export", "context": {}}
        )
        elapsed = (time.time() - start) * 1000
        assert elapsed < 2000


# ═══════════════════════════════════════════════════════════════════════════════
# SLA SERVER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSLAServer:
    """Tests for SLA MCP server."""

    @pytest.fixture
    def sla_server(self):
        """Create SLA server instance."""
        return SLAServer()

    @pytest.mark.asyncio
    async def test_server_starts(self, sla_server):
        """Test SLA server starts correctly."""
        await sla_server.start()
        assert sla_server.is_running is True

    @pytest.mark.asyncio
    async def test_calculate_sla_returns_status(self, sla_server):
        """Test calculate_sla returns SLA status."""
        await sla_server.start()
        result = await sla_server.handle_tool_call(
            "calculate_sla",
            {
                "ticket_id": "TKT-001",
                "tier": "standard"
            }
        )
        assert result.success is True
        assert "overall_status" in result.data
        assert "sla_results" in result.data

    @pytest.mark.asyncio
    async def test_calculate_sla_critical_tier(self, sla_server):
        """Test calculate_sla for critical tier."""
        await sla_server.start()
        result = await sla_server.handle_tool_call(
            "calculate_sla",
            {
                "ticket_id": "TKT-001",
                "tier": "critical",
                "is_vip": True
            }
        )
        assert result.success is True
        assert result.data["tier"] == "critical"
        assert result.data["is_vip"] is True

    @pytest.mark.asyncio
    async def test_calculate_sla_with_created_at(self, sla_server):
        """Test calculate_sla with custom created_at."""
        await sla_server.start()
        created = (datetime.now() - timedelta(hours=3)).isoformat()
        result = await sla_server.handle_tool_call(
            "calculate_sla",
            {
                "ticket_id": "TKT-NEW",
                "tier": "high",
                "created_at": created
            }
        )
        assert result.success is True
        assert "time_elapsed_hours" in result.data["sla_results"]["first_response"]

    @pytest.mark.asyncio
    async def test_get_breach_predictions(self, sla_server):
        """Test get_breach_predictions returns predictions."""
        await sla_server.start()
        result = await sla_server.handle_tool_call(
            "get_breach_predictions",
            {"time_horizon_hours": 24}
        )
        assert result.success is True
        assert "predictions" in result.data
        assert isinstance(result.data["predictions"], list)

    @pytest.mark.asyncio
    async def test_get_breach_predictions_with_filters(self, sla_server):
        """Test get_breach_predictions with filters."""
        await sla_server.start()
        result = await sla_server.handle_tool_call(
            "get_breach_predictions",
            {
                "time_horizon_hours": 48,
                "min_probability": 0.8,
                "tiers": ["critical", "high"]
            }
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_escalate_ticket(self, sla_server):
        """Test escalate_ticket creates escalation."""
        await sla_server.start()
        result = await sla_server.handle_tool_call(
            "escalate_ticket",
            {
                "ticket_id": "TKT-001",
                "reason": "SLA breach imminent"
            }
        )
        assert result.success is True
        assert "escalation_id" in result.data

    @pytest.mark.asyncio
    async def test_escalate_ticket_with_level(self, sla_server):
        """Test escalate_ticket with escalation level."""
        await sla_server.start()
        result = await sla_server.handle_tool_call(
            "escalate_ticket",
            {
                "ticket_id": "TKT-001",
                "reason": "Customer complaint",
                "escalation_level": "manager"
            }
        )
        assert result.success is True
        assert result.data["level"] == "manager"

    @pytest.mark.asyncio
    async def test_escalate_ticket_missing_reason_fails(self, sla_server):
        """Test escalate_ticket fails without reason."""
        await sla_server.start()
        result = await sla_server.handle_tool_call(
            "escalate_ticket",
            {"ticket_id": "TKT-001"}
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_sla_response_time(self, sla_server):
        """CRITICAL: SLA server must respond within 2 seconds."""
        await sla_server.start()
        start = time.time()
        await sla_server.handle_tool_call(
            "calculate_sla",
            {"ticket_id": "TKT-001"}
        )
        elapsed = (time.time() - start) * 1000
        assert elapsed < 2000

    @pytest.mark.asyncio
    async def test_sla_health_check(self, sla_server):
        """Test health check returns valid status."""
        await sla_server.start()
        health = await sla_server.health_check()
        assert health["healthy"] is True
        assert "calculate_sla" in health["tools"]


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestToolServersIntegration:
    """Integration tests for all tool servers."""

    @pytest.mark.asyncio
    async def test_all_servers_start(self):
        """Test all tool servers can start."""
        servers = [NotificationServer(), ComplianceServer(), SLAServer()]

        for server in servers:
            await server.start()
            assert server.is_running is True
            await server.stop()

    @pytest.mark.asyncio
    async def test_all_servers_have_required_tools(self):
        """Test all servers have their required tools."""
        notification = NotificationServer()
        compliance = ComplianceServer()
        sla = SLAServer()

        assert "send_notification" in notification.tools
        assert "send_bulk_notifications" in notification.tools
        assert "get_notification_preferences" in notification.tools
        assert "update_preferences" in notification.tools

        assert "check_compliance" in compliance.tools
        assert "get_jurisdiction_rules" in compliance.tools
        assert "gdpr_export" in compliance.tools
        assert "gdpr_delete" in compliance.tools

        assert "calculate_sla" in sla.tools
        assert "get_breach_predictions" in sla.tools
        assert "escalate_ticket" in sla.tools

    @pytest.mark.asyncio
    async def test_all_servers_respond_within_2_seconds(self):
        """CRITICAL: All servers must respond within 2 seconds."""
        servers = [
            (NotificationServer(), "send_notification",
             {"user_id": "u1", "message": "test", "channel": "email"}),
            (ComplianceServer(), "check_compliance",
             {"action": "data_export", "context": {}}),
            (SLAServer(), "calculate_sla", {"ticket_id": "TKT-001"}),
        ]

        for server, tool, params in servers:
            await server.start()
            start = time.time()
            await server.handle_tool_call(tool, params)
            elapsed = (time.time() - start) * 1000
            assert elapsed < 2000, f"{server.name} took {elapsed}ms"
            await server.stop()

    @pytest.mark.asyncio
    async def test_compliance_to_sla_workflow(self):
        """Test compliance check followed by SLA escalation."""
        compliance = ComplianceServer()
        sla = SLAServer()

        await compliance.start()
        await sla.start()

        # Check compliance for data export
        compliance_result = await compliance.handle_tool_call(
            "check_compliance",
            {"action": "data_export", "context": {"user_id": "u1"}}
        )
        assert compliance_result.success is True

        # Calculate SLA for a ticket
        sla_result = await sla.handle_tool_call(
            "calculate_sla",
            {"ticket_id": "TKT-001", "tier": "high"}
        )
        assert sla_result.success is True

        await compliance.stop()
        await sla.stop()
