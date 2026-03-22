"""
Unit tests for Week 8 Day 3 MCP Tool Servers.

Tests for:
- EcommerceServer (order lookup, products, refund requests)
- CRMServer (contacts, interactions)
- AnalyticsServer (metrics, dashboards, reports)
- MonitoringServer (service status, alerts)

CRITICAL: Tests verify that refund requests create pending_approval,
NOT direct refund execution.
"""
import pytest
import asyncio
from datetime import datetime, timezone

from mcp_servers.integrations.ecommerce_server import EcommerceServer
from mcp_servers.integrations.crm_server import CRMServer
from mcp_servers.tools.analytics_server import AnalyticsServer
from mcp_servers.tools.monitoring_server import MonitoringServer


# ============================================================================
# EcommerceServer Tests
# ============================================================================

class TestEcommerceServer:
    """Tests for EcommerceServer MCP."""

    @pytest.fixture
    async def server(self):
        """Create and start EcommerceServer."""
        server = EcommerceServer()
        await server.start()
        yield server
        await server.stop()

    @pytest.mark.asyncio
    async def test_server_starts_successfully(self, server):
        """Test that EcommerceServer starts without errors."""
        assert server.is_running
        health = await server.health_check()
        assert health["healthy"] is True
        assert health["state"] == "running"

    @pytest.mark.asyncio
    async def test_server_responds_within_2_seconds(self, server):
        """Test that server responds within 2 seconds (CRITICAL requirement)."""
        import time
        start = time.time()
        await server.health_check()
        elapsed = time.time() - start
        assert elapsed < 2.0

    @pytest.mark.asyncio
    async def test_get_order_success(self, server):
        """Test getting an existing order."""
        result = await server.handle_tool_call("get_order", {"order_id": "ORD-001"})
        assert result.success is True
        assert "order" in result.data
        assert result.data["order"]["order_id"] == "ORD-001"

    @pytest.mark.asyncio
    async def test_get_order_not_found(self, server):
        """Test getting a non-existent order."""
        result = await server.handle_tool_call("get_order", {"order_id": "INVALID"})
        assert result.success is True
        assert result.data["status"] == "error"

    @pytest.mark.asyncio
    async def test_get_customer_success(self, server):
        """Test getting an existing customer."""
        result = await server.handle_tool_call(
            "get_customer", {"customer_id": "CUST-001"}
        )
        assert result.success is True
        assert "customer" in result.data
        assert result.data["customer"]["customer_id"] == "CUST-001"

    @pytest.mark.asyncio
    async def test_get_customer_not_found(self, server):
        """Test getting a non-existent customer."""
        result = await server.handle_tool_call(
            "get_customer", {"customer_id": "INVALID"}
        )
        assert result.success is True
        assert result.data["status"] == "error"

    @pytest.mark.asyncio
    async def test_search_products_returns_results(self, server):
        """Test product search returns results."""
        result = await server.handle_tool_call(
            "search_products", {"query": "widget"}
        )
        assert result.success is True
        assert "products" in result.data
        assert len(result.data["products"]) > 0

    @pytest.mark.asyncio
    async def test_search_products_with_limit(self, server):
        """Test product search with limit."""
        result = await server.handle_tool_call(
            "search_products", {"query": "widget", "limit": 2}
        )
        assert result.success is True
        assert len(result.data["products"]) <= 2

    @pytest.mark.asyncio
    async def test_get_inventory_all_products(self, server):
        """Test getting inventory for all products."""
        result = await server.handle_tool_call("get_inventory", {})
        assert result.success is True
        assert "inventory" in result.data
        assert result.data["total_products"] > 0

    @pytest.mark.asyncio
    async def test_get_inventory_specific_product(self, server):
        """Test getting inventory for specific product."""
        result = await server.handle_tool_call(
            "get_inventory", {"product_id": "PROD-001"}
        )
        assert result.success is True
        assert "inventory" in result.data
        assert result.data["inventory"]["product_id"] == "PROD-001"

    @pytest.mark.asyncio
    async def test_create_refund_request_creates_pending_approval(self, server):
        """CRITICAL: Refund request must create pending_approval, NOT execute."""
        result = await server.handle_tool_call(
            "create_refund_request",
            {
                "order_id": "ORD-001",
                "amount": 50.00,
                "reason": "Customer request"
            }
        )
        assert result.success is True
        assert result.data["status"] == "success"
        assert "refund_request" in result.data

        # CRITICAL: Status must be pending_approval
        refund = result.data["refund_request"]
        assert refund["status"] == "pending_approval"
        assert "approval_id" in refund
        assert "NOT been executed" in result.data["important"]

    @pytest.mark.asyncio
    async def test_create_refund_request_validates_amount(self, server):
        """Test that refund request validates amount against order total."""
        result = await server.handle_tool_call(
            "create_refund_request",
            {
                "order_id": "ORD-001",
                "amount": 99999.00,  # Exceeds order total
                "reason": "Test"
            }
        )
        assert result.success is True
        assert result.data["status"] == "error"
        assert "exceeds order total" in result.data["message"]

    @pytest.mark.asyncio
    async def test_create_refund_request_validates_order_exists(self, server):
        """Test that refund request validates order exists."""
        result = await server.handle_tool_call(
            "create_refund_request",
            {
                "order_id": "INVALID-ORDER",
                "amount": 50.00,
                "reason": "Test"
            }
        )
        assert result.success is True
        assert result.data["status"] == "error"

    @pytest.mark.asyncio
    async def test_tools_registered(self, server):
        """Test that all expected tools are registered."""
        expected_tools = [
            "get_order",
            "get_customer",
            "search_products",
            "get_inventory",
            "create_refund_request"
        ]
        for tool in expected_tools:
            assert tool in server.tools


# ============================================================================
# CRMServer Tests
# ============================================================================

class TestCRMServer:
    """Tests for CRMServer MCP."""

    @pytest.fixture
    async def server(self):
        """Create and start CRMServer."""
        server = CRMServer()
        await server.start()
        yield server
        await server.stop()

    @pytest.mark.asyncio
    async def test_server_starts_successfully(self, server):
        """Test that CRMServer starts without errors."""
        assert server.is_running
        health = await server.health_check()
        assert health["healthy"] is True

    @pytest.mark.asyncio
    async def test_server_responds_within_2_seconds(self, server):
        """Test that server responds within 2 seconds."""
        import time
        start = time.time()
        await server.health_check()
        elapsed = time.time() - start
        assert elapsed < 2.0

    @pytest.mark.asyncio
    async def test_get_contact_success(self, server):
        """Test getting an existing contact."""
        result = await server.handle_tool_call(
            "get_contact", {"contact_id": "CONT-001"}
        )
        assert result.success is True
        assert "contact" in result.data
        assert result.data["contact"]["contact_id"] == "CONT-001"

    @pytest.mark.asyncio
    async def test_get_contact_not_found(self, server):
        """Test getting a non-existent contact."""
        result = await server.handle_tool_call(
            "get_contact", {"contact_id": "INVALID"}
        )
        assert result.success is True
        assert result.data["status"] == "error"

    @pytest.mark.asyncio
    async def test_search_contacts_returns_results(self, server):
        """Test contact search returns results."""
        result = await server.handle_tool_call(
            "search_contacts", {"query": "john"}
        )
        assert result.success is True
        assert "contacts" in result.data

    @pytest.mark.asyncio
    async def test_search_contacts_by_company(self, server):
        """Test contact search by company."""
        result = await server.handle_tool_call(
            "search_contacts", {"query": "tech corp"}
        )
        assert result.success is True
        assert len(result.data["contacts"]) > 0

    @pytest.mark.asyncio
    async def test_create_contact_success(self, server):
        """Test creating a new contact."""
        result = await server.handle_tool_call(
            "create_contact",
            {
                "data": {
                    "email": "new.contact@example.com",
                    "name": "New Contact",
                    "company": "Test Company"
                }
            }
        )
        assert result.success is True
        assert "contact" in result.data
        assert result.data["contact"]["email"] == "new.contact@example.com"

    @pytest.mark.asyncio
    async def test_create_contact_duplicate_email(self, server):
        """Test creating contact with duplicate email fails."""
        result = await server.handle_tool_call(
            "create_contact",
            {
                "data": {
                    "email": "john.doe@example.com",  # Existing email
                    "name": "Duplicate Contact"
                }
            }
        )
        assert result.success is True
        assert result.data["status"] == "error"
        assert "already exists" in result.data["message"]

    @pytest.mark.asyncio
    async def test_update_contact_success(self, server):
        """Test updating a contact."""
        result = await server.handle_tool_call(
            "update_contact",
            {
                "contact_id": "CONT-001",
                "data": {"title": "Senior Manager"}
            }
        )
        assert result.success is True
        assert result.data["contact"]["title"] == "Senior Manager"

    @pytest.mark.asyncio
    async def test_update_contact_not_found(self, server):
        """Test updating a non-existent contact."""
        result = await server.handle_tool_call(
            "update_contact",
            {
                "contact_id": "INVALID",
                "data": {"title": "Manager"}
            }
        )
        assert result.success is True
        assert result.data["status"] == "error"

    @pytest.mark.asyncio
    async def test_get_interaction_history_success(self, server):
        """Test getting interaction history."""
        result = await server.handle_tool_call(
            "get_interaction_history", {"contact_id": "CONT-001"}
        )
        assert result.success is True
        assert "interactions" in result.data

    @pytest.mark.asyncio
    async def test_tools_registered(self, server):
        """Test that all expected tools are registered."""
        expected_tools = [
            "get_contact",
            "search_contacts",
            "create_contact",
            "update_contact",
            "get_interaction_history"
        ]
        for tool in expected_tools:
            assert tool in server.tools


# ============================================================================
# AnalyticsServer Tests
# ============================================================================

class TestAnalyticsServer:
    """Tests for AnalyticsServer MCP."""

    @pytest.fixture
    async def server(self):
        """Create and start AnalyticsServer."""
        server = AnalyticsServer()
        await server.start()
        yield server
        await server.stop()

    @pytest.mark.asyncio
    async def test_server_starts_successfully(self, server):
        """Test that AnalyticsServer starts without errors."""
        assert server.is_running
        health = await server.health_check()
        assert health["healthy"] is True

    @pytest.mark.asyncio
    async def test_server_responds_within_2_seconds(self, server):
        """Test that server responds within 2 seconds."""
        import time
        start = time.time()
        await server.health_check()
        elapsed = time.time() - start
        assert elapsed < 2.0

    @pytest.mark.asyncio
    async def test_get_metrics_success(self, server):
        """Test getting metrics by names."""
        result = await server.handle_tool_call(
            "get_metrics",
            {"metric_names": ["revenue_total", "orders_count"]}
        )
        assert result.success is True
        assert "metrics" in result.data
        assert "revenue_total" in result.data["metrics"]
        assert "orders_count" in result.data["metrics"]

    @pytest.mark.asyncio
    async def test_get_metrics_with_time_range(self, server):
        """Test getting metrics with time range filter."""
        result = await server.handle_tool_call(
            "get_metrics",
            {
                "metric_names": ["revenue_total"],
                "time_range": {
                    "start": "2026-03-01T00:00:00Z",
                    "end": "2026-03-21T00:00:00Z"
                }
            }
        )
        assert result.success is True
        assert "time_range" in result.data

    @pytest.mark.asyncio
    async def test_get_metrics_not_found(self, server):
        """Test getting non-existent metrics."""
        result = await server.handle_tool_call(
            "get_metrics", {"metric_names": ["invalid_metric"]}
        )
        assert result.success is True
        assert result.data["not_found"] is not None

    @pytest.mark.asyncio
    async def test_get_dashboard_data_success(self, server):
        """Test getting dashboard data."""
        result = await server.handle_tool_call(
            "get_dashboard_data", {"dashboard_id": "dashboard-sales"}
        )
        assert result.success is True
        assert "dashboard" in result.data
        assert result.data["dashboard"]["dashboard_id"] == "dashboard-sales"

    @pytest.mark.asyncio
    async def test_get_dashboard_data_not_found(self, server):
        """Test getting non-existent dashboard."""
        result = await server.handle_tool_call(
            "get_dashboard_data", {"dashboard_id": "invalid-dashboard"}
        )
        assert result.success is True
        assert result.data["status"] == "error"

    @pytest.mark.asyncio
    async def test_run_report_sales(self, server):
        """Test running a sales report."""
        result = await server.handle_tool_call(
            "run_report", {"report_type": "sales"}
        )
        assert result.success is True
        assert "report" in result.data
        assert result.data["report"]["type"] == "sales"
        assert "total_revenue" in result.data["report"]["data"]

    @pytest.mark.asyncio
    async def test_run_report_support(self, server):
        """Test running a support report."""
        result = await server.handle_tool_call(
            "run_report", {"report_type": "support"}
        )
        assert result.success is True
        assert result.data["report"]["type"] == "support"
        assert "total_tickets" in result.data["report"]["data"]

    @pytest.mark.asyncio
    async def test_run_report_customers(self, server):
        """Test running a customers report."""
        result = await server.handle_tool_call(
            "run_report", {"report_type": "customers"}
        )
        assert result.success is True
        assert "total_customers" in result.data["report"]["data"]

    @pytest.mark.asyncio
    async def test_run_report_products(self, server):
        """Test running a products report."""
        result = await server.handle_tool_call(
            "run_report", {"report_type": "products"}
        )
        assert result.success is True
        assert "total_products" in result.data["report"]["data"]

    @pytest.mark.asyncio
    async def test_get_realtime_stats(self, server):
        """Test getting real-time statistics."""
        result = await server.handle_tool_call("get_realtime_stats", {})
        assert result.success is True
        assert "stats" in result.data
        assert "services" in result.data["stats"]
        assert "system" in result.data["stats"]

    @pytest.mark.asyncio
    async def test_tools_registered(self, server):
        """Test that all expected tools are registered."""
        expected_tools = [
            "get_metrics",
            "get_dashboard_data",
            "run_report",
            "get_realtime_stats"
        ]
        for tool in expected_tools:
            assert tool in server.tools


# ============================================================================
# MonitoringServer Tests
# ============================================================================

class TestMonitoringServer:
    """Tests for MonitoringServer MCP."""

    @pytest.fixture
    async def server(self):
        """Create and start MonitoringServer."""
        server = MonitoringServer()
        await server.start()
        yield server
        await server.stop()

    @pytest.mark.asyncio
    async def test_server_starts_successfully(self, server):
        """Test that MonitoringServer starts without errors."""
        assert server.is_running
        health = await server.health_check()
        assert health["healthy"] is True

    @pytest.mark.asyncio
    async def test_server_responds_within_2_seconds(self, server):
        """Test that server responds within 2 seconds."""
        import time
        start = time.time()
        await server.health_check()
        elapsed = time.time() - start
        assert elapsed < 2.0

    @pytest.mark.asyncio
    async def test_get_service_status_all(self, server):
        """Test getting status of all services."""
        result = await server.handle_tool_call("get_service_status", {})
        assert result.success is True
        assert "services" in result.data
        assert "summary" in result.data
        assert result.data["summary"]["total"] > 0

    @pytest.mark.asyncio
    async def test_get_service_status_specific(self, server):
        """Test getting status of a specific service."""
        result = await server.handle_tool_call(
            "get_service_status", {"service_id": "api-gateway"}
        )
        assert result.success is True
        assert "service" in result.data
        assert result.data["service"]["service_id"] == "api-gateway"

    @pytest.mark.asyncio
    async def test_get_service_status_not_found(self, server):
        """Test getting status of non-existent service."""
        result = await server.handle_tool_call(
            "get_service_status", {"service_id": "invalid-service"}
        )
        assert result.success is True
        assert result.data["status"] == "error"

    @pytest.mark.asyncio
    async def test_get_alerts_all(self, server):
        """Test getting all alerts."""
        result = await server.handle_tool_call("get_alerts", {})
        assert result.success is True
        assert "alerts" in result.data

    @pytest.mark.asyncio
    async def test_get_alerts_by_severity(self, server):
        """Test getting alerts filtered by severity."""
        result = await server.handle_tool_call(
            "get_alerts", {"severity": "warning"}
        )
        assert result.success is True
        # All returned alerts should have severity 'warning'
        for alert in result.data["alerts"]:
            assert alert["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_acknowledge_alert_success(self, server):
        """Test acknowledging an alert."""
        result = await server.handle_tool_call(
            "acknowledge_alert",
            {
                "alert_id": "ALT-001",
                "acknowledged_by": "admin@example.com"
            }
        )
        assert result.success is True
        assert result.data["alert"]["acknowledged"] is True
        assert result.data["alert"]["acknowledged_by"] == "admin@example.com"

    @pytest.mark.asyncio
    async def test_acknowledge_alert_not_found(self, server):
        """Test acknowledging non-existent alert."""
        result = await server.handle_tool_call(
            "acknowledge_alert",
            {
                "alert_id": "INVALID",
                "acknowledged_by": "admin@example.com"
            }
        )
        assert result.success is True
        assert result.data["status"] == "error"

    @pytest.mark.asyncio
    async def test_get_metrics_system(self, server):
        """Test getting system metrics."""
        result = await server.handle_tool_call(
            "get_metrics", {"metric_type": "system"}
        )
        assert result.success is True
        assert "metrics" in result.data
        assert "system" in result.data["metrics"]
        assert "cpu" in result.data["metrics"]["system"]

    @pytest.mark.asyncio
    async def test_get_metrics_application(self, server):
        """Test getting application metrics."""
        result = await server.handle_tool_call(
            "get_metrics", {"metric_type": "application"}
        )
        assert result.success is True
        assert "application" in result.data["metrics"]
        assert "requests" in result.data["metrics"]["application"]

    @pytest.mark.asyncio
    async def test_get_metrics_all(self, server):
        """Test getting all metrics."""
        result = await server.handle_tool_call("get_metrics", {})
        assert result.success is True
        assert "system" in result.data["metrics"]
        assert "application" in result.data["metrics"]

    @pytest.mark.asyncio
    async def test_tools_registered(self, server):
        """Test that all expected tools are registered."""
        expected_tools = [
            "get_service_status",
            "get_alerts",
            "acknowledge_alert",
            "get_metrics"
        ]
        for tool in expected_tools:
            assert tool in server.tools


# ============================================================================
# Integration Tests
# ============================================================================

class TestDay3Integration:
    """Integration tests for Day 3 servers."""

    @pytest.fixture
    async def servers(self):
        """Create and start all Day 3 servers."""
        ecommerce = EcommerceServer()
        crm = CRMServer()
        analytics = AnalyticsServer()
        monitoring = MonitoringServer()

        await ecommerce.start()
        await crm.start()
        await analytics.start()
        await monitoring.start()

        yield {
            "ecommerce": ecommerce,
            "crm": crm,
            "analytics": analytics,
            "monitoring": monitoring
        }

        await ecommerce.stop()
        await crm.stop()
        await analytics.stop()
        await monitoring.stop()

    @pytest.mark.asyncio
    async def test_all_servers_start_successfully(self, servers):
        """Test that all Day 3 servers start without errors."""
        for name, server in servers.items():
            assert server.is_running, f"{name} should be running"

    @pytest.mark.asyncio
    async def test_all_servers_respond_within_2_seconds(self, servers):
        """CRITICAL: All servers must respond within 2 seconds."""
        import time
        for name, server in servers.items():
            start = time.time()
            await server.health_check()
            elapsed = time.time() - start
            assert elapsed < 2.0, f"{name} took {elapsed}s (max 2s)"

    @pytest.mark.asyncio
    async def test_order_to_crm_workflow(self, servers):
        """Test workflow: Get order → Look up customer in CRM."""
        ecommerce = servers["ecommerce"]
        crm = servers["crm"]

        # Get order
        order_result = await ecommerce.handle_tool_call(
            "get_order", {"order_id": "ORD-001"}
        )
        assert order_result.success is True

        customer_id = order_result.data["order"]["customer_id"]

        # Get contact from CRM (customer_id maps to contact_id for this test)
        contact_result = await crm.handle_tool_call(
            "get_contact", {"contact_id": f"CONT-{customer_id.split('-')[1]}"}
        )
        # This test demonstrates the workflow concept
        # In production, customer_id would directly map to contact_id

    @pytest.mark.asyncio
    async def test_refund_creates_pending_approval_not_executed(self, servers):
        """CRITICAL: Refund must create pending_approval, never execute directly."""
        ecommerce = servers["ecommerce"]

        result = await ecommerce.handle_tool_call(
            "create_refund_request",
            {
                "order_id": "ORD-001",
                "amount": 50.00,
                "reason": "Customer satisfaction"
            }
        )

        assert result.success is True
        # CRITICAL ASSERTION: Status must be pending_approval
        assert result.data["refund_request"]["status"] == "pending_approval"
        # CRITICAL: Message must indicate NOT executed
        assert "NOT been executed" in result.data["important"]

    @pytest.mark.asyncio
    async def test_monitoring_tracks_all_services(self, servers):
        """Test that monitoring server tracks all MCP services."""
        monitoring = servers["monitoring"]

        result = await monitoring.handle_tool_call("get_service_status", {})
        assert result.success is True

        # Should have multiple services registered
        assert result.data["summary"]["total"] >= 5
