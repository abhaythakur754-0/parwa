"""
Unit Tests for PARWA Grafana Dashboards.

Tests cover:
- JSON validation for all dashboards
- Required panels present
- Datasource references correct
- Dashboard schema compliance

CRITICAL Tests:
- All dashboards load in Grafana without errors
- All required panels are present
- Datasource references are valid
"""
import pytest
import json
from pathlib import Path

from monitoring.grafana_dashboards import (
    load_dashboard,
    get_all_dashboards,
    validate_dashboard,
    get_dashboard_panels,
    get_datasource,
    DASHBOARD_FILES,
    DASHBOARD_DIR,
)


class TestDashboardFiles:
    """Tests for dashboard file existence and validity."""

    def test_dashboard_directory_exists(self):
        """Test that the dashboard directory exists."""
        assert DASHBOARD_DIR.exists(), f"Dashboard directory not found: {DASHBOARD_DIR}"

    def test_all_dashboard_files_exist(self):
        """Test that all dashboard files exist."""
        for name, filename in DASHBOARD_FILES.items():
            filepath = DASHBOARD_DIR / filename
            assert filepath.exists(), f"Dashboard file not found: {filepath}"

    def test_all_dashboards_are_valid_json(self):
        """Test that all dashboard files are valid JSON."""
        for name, filename in DASHBOARD_FILES.items():
            filepath = DASHBOARD_DIR / filename
            with open(filepath, "r") as f:
                try:
                    data = json.load(f)
                    assert isinstance(data, dict), f"{name} should be a JSON object"
                except json.JSONDecodeError as e:
                    pytest.fail(f"Invalid JSON in {filename}: {e}")


class TestMainDashboard:
    """Tests for main dashboard."""

    @pytest.fixture
    def dashboard(self):
        """Load the main dashboard."""
        return load_dashboard("main")

    def test_main_dashboard_loads(self, dashboard):
        """Test that main dashboard loads without errors."""
        assert dashboard is not None
        assert "dashboard" in dashboard

    def test_main_dashboard_has_required_fields(self, dashboard):
        """Test that main dashboard has required fields."""
        dash = dashboard["dashboard"]
        assert "title" in dash
        assert "uid" in dash
        assert "panels" in dash
        assert dash["title"] == "PARWA Main Dashboard"
        assert dash["uid"] == "parwa-main"

    def test_main_dashboard_has_system_overview_panels(self, dashboard):
        """Test that main dashboard has system overview panels."""
        panels = get_dashboard_panels(dashboard)
        panel_titles = [p.get("title", "") for p in panels]

        # Check for required panels
        assert "Request Rate" in panel_titles
        assert "Error Rate" in panel_titles
        assert "P95 Latency" in panel_titles

    def test_main_dashboard_has_agent_panels(self, dashboard):
        """Test that main dashboard has agent panels."""
        panels = get_dashboard_panels(dashboard)
        panel_titles = [p.get("title", "") for p in panels]

        assert "Active Agents by Variant" in panel_titles

    def test_main_dashboard_has_ticket_panels(self, dashboard):
        """Test that main dashboard has ticket panels."""
        panels = get_dashboard_panels(dashboard)
        panel_titles = [p.get("title", "") for p in panels]

        assert "Ticket Volume" in panel_titles
        assert "Resolution Rate" in panel_titles

    def test_main_dashboard_has_refund_panels(self, dashboard):
        """Test that main dashboard has refund panels."""
        panels = get_dashboard_panels(dashboard)
        panel_titles = [p.get("title", "") for p in panels]

        assert "Refund Processing Status" in panel_titles

    def test_main_dashboard_datasource_prometheus(self, dashboard):
        """Test that main dashboard uses Prometheus datasource."""
        datasource = get_datasource(dashboard)
        assert datasource == "Prometheus"


class TestMCPDashboard:
    """Tests for MCP dashboard."""

    @pytest.fixture
    def dashboard(self):
        """Load the MCP dashboard."""
        return load_dashboard("mcp")

    def test_mcp_dashboard_loads(self, dashboard):
        """Test that MCP dashboard loads without errors."""
        assert dashboard is not None
        assert "dashboard" in dashboard

    def test_mcp_dashboard_has_required_fields(self, dashboard):
        """Test that MCP dashboard has required fields."""
        dash = dashboard["dashboard"]
        assert "title" in dash
        assert "uid" in dash
        assert "panels" in dash
        assert dash["title"] == "PARWA MCP Servers Dashboard"
        assert dash["uid"] == "parwa-mcp"

    def test_mcp_dashboard_has_server_status_panel(self, dashboard):
        """Test that MCP dashboard has server status panel."""
        panels = get_dashboard_panels(dashboard)
        panel_titles = [p.get("title", "") for p in panels]

        assert "MCP Server Status Overview" in panel_titles

    def test_mcp_dashboard_has_response_times_panel(self, dashboard):
        """Test that MCP dashboard has response times panel."""
        panels = get_dashboard_panels(dashboard)
        panel_titles = [p.get("title", "") for p in panels]

        assert "MCP Response Times" in panel_titles

    def test_mcp_dashboard_has_error_rates_panel(self, dashboard):
        """Test that MCP dashboard has error rates panel."""
        panels = get_dashboard_panels(dashboard)
        panel_titles = [p.get("title", "") for p in panels]

        assert "MCP Error Rates" in panel_titles

    def test_mcp_dashboard_has_knowledge_server_panel(self, dashboard):
        """Test that MCP dashboard has knowledge server panel."""
        panels = get_dashboard_panels(dashboard)
        panel_titles = [p.get("title", "") for p in panels]

        assert "Knowledge Server Query Volume" in panel_titles

    def test_mcp_dashboard_has_integration_server_panel(self, dashboard):
        """Test that MCP dashboard has integration server panel."""
        panels = get_dashboard_panels(dashboard)
        panel_titles = [p.get("title", "") for p in panels]

        assert "Integration Server Call Volume" in panel_titles


class TestComplianceDashboard:
    """Tests for compliance dashboard."""

    @pytest.fixture
    def dashboard(self):
        """Load the compliance dashboard."""
        return load_dashboard("compliance")

    def test_compliance_dashboard_loads(self, dashboard):
        """Test that compliance dashboard loads without errors."""
        assert dashboard is not None
        assert "dashboard" in dashboard

    def test_compliance_dashboard_has_required_fields(self, dashboard):
        """Test that compliance dashboard has required fields."""
        dash = dashboard["dashboard"]
        assert dash["title"] == "PARWA Compliance Dashboard"
        assert dash["uid"] == "parwa-compliance"

    def test_compliance_dashboard_has_gdpr_panel(self, dashboard):
        """Test that compliance dashboard has GDPR panel."""
        panels = get_dashboard_panels(dashboard)
        panel_titles = [p.get("title", "") for p in panels]

        assert "GDPR Request Count" in panel_titles

    def test_compliance_dashboard_has_pii_audit_panel(self, dashboard):
        """Test that compliance dashboard has PII audit panel."""
        panels = get_dashboard_panels(dashboard)
        panel_titles = [p.get("title", "") for p in panels]

        assert "PII Access Audit Trail" in panel_titles

    def test_compliance_dashboard_has_hipaa_panel(self, dashboard):
        """Test that compliance dashboard has HIPAA panel."""
        panels = get_dashboard_panels(dashboard)
        panel_titles = [p.get("title", "") for p in panels]

        assert "HIPAA Compliance Score" in panel_titles

    def test_compliance_dashboard_has_healthcare_baa_panel(self, dashboard):
        """Test that compliance dashboard has Healthcare BAA panel."""
        panels = get_dashboard_panels(dashboard)
        panel_titles = [p.get("title", "") for p in panels]

        assert "Healthcare BAA Status" in panel_titles


class TestSLADashboard:
    """Tests for SLA dashboard."""

    @pytest.fixture
    def dashboard(self):
        """Load the SLA dashboard."""
        return load_dashboard("sla")

    def test_sla_dashboard_loads(self, dashboard):
        """Test that SLA dashboard loads without errors."""
        assert dashboard is not None
        assert "dashboard" in dashboard

    def test_sla_dashboard_has_required_fields(self, dashboard):
        """Test that SLA dashboard has required fields."""
        dash = dashboard["dashboard"]
        assert dash["title"] == "PARWA SLA Dashboard"
        assert dash["uid"] == "parwa-sla"

    def test_sla_dashboard_has_breach_count_panel(self, dashboard):
        """Test that SLA dashboard has breach count panel."""
        panels = get_dashboard_panels(dashboard)
        panel_titles = [p.get("title", "") for p in panels]

        assert "SLA Breach Count" in panel_titles

    def test_sla_dashboard_has_compliance_panel(self, dashboard):
        """Test that SLA dashboard has compliance panel."""
        panels = get_dashboard_panels(dashboard)
        panel_titles = [p.get("title", "") for p in panels]

        assert "SLA Compliance Percentage" in panel_titles

    def test_sla_dashboard_has_response_time_panel(self, dashboard):
        """Test that SLA dashboard has response time panel."""
        panels = get_dashboard_panels(dashboard)
        panel_titles = [p.get("title", "") for p in panels]

        assert "Response Time by Priority" in panel_titles

    def test_sla_dashboard_has_escalation_panel(self, dashboard):
        """Test that SLA dashboard has escalation panel."""
        panels = get_dashboard_panels(dashboard)
        panel_titles = [p.get("title", "") for p in panels]

        assert "Escalation Phase Distribution" in panel_titles


class TestQualityDashboard:
    """Tests for quality dashboard."""

    @pytest.fixture
    def dashboard(self):
        """Load the quality dashboard."""
        return load_dashboard("quality")

    def test_quality_dashboard_loads(self, dashboard):
        """Test that quality dashboard loads without errors."""
        assert dashboard is not None
        assert "dashboard" in dashboard

    def test_quality_dashboard_has_required_fields(self, dashboard):
        """Test that quality dashboard has required fields."""
        dash = dashboard["dashboard"]
        assert dash["title"] == "PARWA Quality Coach Dashboard"
        assert dash["uid"] == "parwa-quality"

    def test_quality_dashboard_has_accuracy_score_panel(self, dashboard):
        """Test that quality dashboard has accuracy score panel."""
        panels = get_dashboard_panels(dashboard)
        panel_titles = [p.get("title", "") for p in panels]

        assert "Average Quality Scores" in panel_titles or "Accuracy" in panel_titles

    def test_quality_dashboard_has_empathy_score_panel(self, dashboard):
        """Test that quality dashboard has empathy score panel."""
        panels = get_dashboard_panels(dashboard)
        panel_titles = [p.get("title", "") for p in panels]

        assert "Average Empathy Score" in panel_titles

    def test_quality_dashboard_has_efficiency_score_panel(self, dashboard):
        """Test that quality dashboard has efficiency score panel."""
        panels = get_dashboard_panels(dashboard)
        panel_titles = [p.get("title", "") for p in panels]

        assert "Average Efficiency Score" in panel_titles

    def test_quality_dashboard_has_trend_panel(self, dashboard):
        """Test that quality dashboard has trend panel."""
        panels = get_dashboard_panels(dashboard)
        panel_titles = [p.get("title", "") for p in panels]

        assert "Quality Trend Over Time" in panel_titles


class TestDashboardValidation:
    """Tests for dashboard validation functions."""

    def test_validate_dashboard_success(self):
        """Test successful dashboard validation."""
        dashboard = {
            "dashboard": {
                "title": "Test Dashboard",
                "uid": "test-uid",
                "panels": [{"title": "Test Panel"}]
            },
            "overwrite": True
        }

        assert validate_dashboard(dashboard) is True

    def test_validate_dashboard_missing_dashboard(self):
        """Test validation fails with missing dashboard field."""
        dashboard = {"overwrite": True}

        with pytest.raises(ValueError, match="Missing required field: dashboard"):
            validate_dashboard(dashboard)

    def test_validate_dashboard_missing_title(self):
        """Test validation fails with missing title."""
        dashboard = {
            "dashboard": {
                "uid": "test-uid",
                "panels": []
            },
            "overwrite": True
        }

        with pytest.raises(ValueError, match="Missing required dashboard field: title"):
            validate_dashboard(dashboard)

    def test_validate_dashboard_missing_panels(self):
        """Test validation fails with missing panels."""
        dashboard = {
            "dashboard": {
                "title": "Test",
                "uid": "test-uid"
            },
            "overwrite": True
        }

        with pytest.raises(ValueError, match="Missing required dashboard field: panels"):
            validate_dashboard(dashboard)

    def test_validate_dashboard_empty_panels(self):
        """Test validation fails with empty panels."""
        dashboard = {
            "dashboard": {
                "title": "Test",
                "uid": "test-uid",
                "panels": []
            },
            "overwrite": True
        }

        with pytest.raises(ValueError, match="at least one panel"):
            validate_dashboard(dashboard)

    def test_validate_dashboard_panels_not_list(self):
        """Test validation fails when panels is not a list."""
        dashboard = {
            "dashboard": {
                "title": "Test",
                "uid": "test-uid",
                "panels": "not a list"
            },
            "overwrite": True
        }

        with pytest.raises(ValueError, match="Panels must be a list"):
            validate_dashboard(dashboard)


class TestDashboardLoading:
    """Tests for dashboard loading functions."""

    def test_load_dashboard_invalid_name(self):
        """Test loading dashboard with invalid name."""
        with pytest.raises(ValueError, match="Invalid dashboard name"):
            load_dashboard("invalid_dashboard")

    def test_get_all_dashboards(self):
        """Test getting all dashboards."""
        dashboards = get_all_dashboards()

        assert isinstance(dashboards, dict)
        assert len(dashboards) >= 5  # Should have at least 5 dashboards

    def test_get_dashboard_panels(self):
        """Test getting dashboard panels."""
        dashboard = load_dashboard("main")
        panels = get_dashboard_panels(dashboard)

        assert isinstance(panels, list)
        assert len(panels) > 0

        # Each panel should have required fields
        for panel in panels:
            assert "id" in panel
            assert "title" in panel
            assert "type" in panel

    def test_get_datasource(self):
        """Test getting datasource from dashboard."""
        dashboard = load_dashboard("main")
        datasource = get_datasource(dashboard)

        assert datasource == "Prometheus"


class TestDashboardPanelTypes:
    """Tests for dashboard panel types."""

    def test_main_dashboard_has_correct_panel_types(self):
        """Test main dashboard has correct panel types."""
        dashboard = load_dashboard("main")
        panels = get_dashboard_panels(dashboard)

        panel_types = {p.get("type") for p in panels}

        # Should have timeseries panels
        assert "timeseries" in panel_types or "graph" in panel_types
        # Should have stat panels
        assert "stat" in panel_types

    def test_mcp_dashboard_has_correct_panel_types(self):
        """Test MCP dashboard has correct panel types."""
        dashboard = load_dashboard("mcp")
        panels = get_dashboard_panels(dashboard)

        panel_types = {p.get("type") for p in panels}

        # Should have stat panels for server status
        assert "stat" in panel_types
        # Should have timeseries for metrics
        assert "timeseries" in panel_types

    def test_compliance_dashboard_has_correct_panel_types(self):
        """Test compliance dashboard has correct panel types."""
        dashboard = load_dashboard("compliance")
        panels = get_dashboard_panels(dashboard)

        panel_types = {p.get("type") for p in panels}

        # Should have timeseries panels
        assert "timeseries" in panel_types
        # Should have piechart for distribution
        assert "piechart" in panel_types

    def test_sla_dashboard_has_correct_panel_types(self):
        """Test SLA dashboard has correct panel types."""
        dashboard = load_dashboard("sla")
        panels = get_dashboard_panels(dashboard)

        panel_types = {p.get("type") for p in panels}

        # Should have gauge for compliance
        assert "gauge" in panel_types
        # Should have timeseries for trends
        assert "timeseries" in panel_types

    def test_quality_dashboard_has_correct_panel_types(self):
        """Test quality dashboard has correct panel types."""
        dashboard = load_dashboard("quality")
        panels = get_dashboard_panels(dashboard)

        panel_types = {p.get("type") for p in panels}

        # Should have gauge for scores
        assert "gauge" in panel_types
        # Should have timeseries for trends
        assert "timeseries" in panel_types
