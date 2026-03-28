"""
Tests for Dashboard Framework
Enterprise Analytics & Reporting - Week 44 Builder 1
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import json

from enterprise.analytics.dashboard_framework import (
    DashboardManager,
    DashboardConfig,
    DashboardStatus,
    WidgetConfig,
    WidgetType,
    LayoutType
)
from enterprise.analytics.widget_library import (
    WidgetFactory,
    WidgetLibrary,
    BaseWidget,
    KPICardWidget,
    ChartWidget,
    TableWidget,
    GaugeWidget,
    WidgetData
)
from enterprise.analytics.dashboard_storage import (
    DashboardStorage,
    StorageConfig
)


# Test Fixtures
@pytest.fixture
def dashboard_manager():
    """Create a test dashboard manager"""
    return DashboardManager()


@pytest.fixture
def widget_config():
    """Create a test widget configuration"""
    return WidgetConfig(
        widget_id="widget-1",
        widget_type=WidgetType.KPI_CARD,
        title="Test Widget",
        position={"x": 0, "y": 0, "width": 4, "height": 2}
    )


@pytest.fixture
def dashboard_storage():
    """Create a test dashboard storage"""
    config = StorageConfig(storage_type="memory")
    storage = DashboardStorage(config)
    storage.initialize()
    return storage


@pytest.fixture
def widget_library():
    """Create a test widget library"""
    return WidgetLibrary()


# DashboardManager Tests
class TestDashboardManager:
    """Tests for DashboardManager"""
    
    def test_manager_initialization(self, dashboard_manager):
        """Test manager initializes correctly"""
        assert dashboard_manager is not None
        assert len(dashboard_manager._dashboards) == 0
    
    def test_create_dashboard(self, dashboard_manager):
        """Test dashboard creation"""
        dashboard = dashboard_manager.create_dashboard(
            name="Test Dashboard",
            description="Test description"
        )
        
        assert dashboard.id is not None
        assert dashboard.name == "Test Dashboard"
        assert dashboard.status == DashboardStatus.DRAFT
        assert len(dashboard.widgets) == 0
    
    def test_get_dashboard(self, dashboard_manager):
        """Test getting a dashboard"""
        created = dashboard_manager.create_dashboard(name="Test")
        retrieved = dashboard_manager.get_dashboard(created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
    
    def test_get_nonexistent_dashboard(self, dashboard_manager):
        """Test getting a non-existent dashboard"""
        result = dashboard_manager.get_dashboard("nonexistent")
        assert result is None
    
    def test_list_dashboards(self, dashboard_manager):
        """Test listing dashboards"""
        dashboard_manager.create_dashboard(name="Dashboard 1")
        dashboard_manager.create_dashboard(name="Dashboard 2")
        
        dashboards = dashboard_manager.list_dashboards()
        assert len(dashboards) == 2
    
    def test_list_dashboards_by_owner(self, dashboard_manager):
        """Test filtering dashboards by owner"""
        dashboard_manager.create_dashboard(name="D1", owner_id="user1")
        dashboard_manager.create_dashboard(name="D2", owner_id="user2")
        
        dashboards = dashboard_manager.list_dashboards(owner_id="user1")
        assert len(dashboards) == 1
    
    def test_update_dashboard(self, dashboard_manager):
        """Test updating a dashboard"""
        dashboard = dashboard_manager.create_dashboard(name="Test")
        
        updated = dashboard_manager.update_dashboard(
            dashboard.id,
            name="Updated Name",
            description="New description"
        )
        
        assert updated.name == "Updated Name"
        assert updated.description == "New description"
    
    def test_delete_dashboard(self, dashboard_manager):
        """Test deleting a dashboard"""
        dashboard = dashboard_manager.create_dashboard(name="Test")
        
        result = dashboard_manager.delete_dashboard(dashboard.id)
        assert result is True
        
        retrieved = dashboard_manager.get_dashboard(dashboard.id)
        assert retrieved is None
    
    def test_publish_dashboard(self, dashboard_manager):
        """Test publishing a dashboard"""
        dashboard = dashboard_manager.create_dashboard(name="Test")
        
        published = dashboard_manager.publish_dashboard(dashboard.id)
        
        assert published.status == DashboardStatus.PUBLISHED
    
    def test_archive_dashboard(self, dashboard_manager):
        """Test archiving a dashboard"""
        dashboard = dashboard_manager.create_dashboard(name="Test")
        
        archived = dashboard_manager.archive_dashboard(dashboard.id)
        
        assert archived.status == DashboardStatus.ARCHIVED
    
    def test_share_dashboard(self, dashboard_manager):
        """Test sharing a dashboard"""
        dashboard = dashboard_manager.create_dashboard(name="Test")
        
        shared = dashboard_manager.share_dashboard(dashboard.id, ["user1", "user2"])
        
        assert len(shared.shared_with) == 2
        assert "user1" in shared.shared_with
    
    def test_unshare_dashboard(self, dashboard_manager):
        """Test unsharing a dashboard"""
        dashboard = dashboard_manager.create_dashboard(name="Test")
        dashboard_manager.share_dashboard(dashboard.id, ["user1", "user2"])
        
        unshared = dashboard_manager.unshare_dashboard(dashboard.id, ["user1"])
        
        assert len(unshared.shared_with) == 1
        assert "user1" not in unshared.shared_with
    
    def test_duplicate_dashboard(self, dashboard_manager):
        """Test duplicating a dashboard"""
        original = dashboard_manager.create_dashboard(name="Original")
        
        duplicate = dashboard_manager.duplicate_dashboard(original.id, "Copy")
        
        assert duplicate is not None
        assert duplicate.name == "Copy"
        assert duplicate.id != original.id
    
    def test_save_as_template(self, dashboard_manager):
        """Test saving dashboard as template"""
        dashboard = dashboard_manager.create_dashboard(name="Test")
        
        template = dashboard_manager.save_as_template(dashboard.id, "My Template")
        
        assert template is not None
        assert template.name == "My Template"
        assert template.id.startswith("template_")
    
    def test_create_from_template(self, dashboard_manager):
        """Test creating dashboard from template"""
        original = dashboard_manager.create_dashboard(name="Original")
        template = dashboard_manager.save_as_template(original.id, "Template")
        
        new_dashboard = dashboard_manager.create_from_template(
            template.id,
            "From Template",
            owner_id="user1"
        )
        
        assert new_dashboard is not None
        assert new_dashboard.name == "From Template"
    
    def test_list_templates(self, dashboard_manager):
        """Test listing templates"""
        dashboard = dashboard_manager.create_dashboard(name="Test")
        dashboard_manager.save_as_template(dashboard.id, "Template 1")
        
        templates = dashboard_manager.list_templates()
        assert len(templates) == 1
    
    def test_export_dashboard(self, dashboard_manager):
        """Test exporting dashboard as JSON"""
        dashboard = dashboard_manager.create_dashboard(name="Test")
        
        exported = dashboard_manager.export_dashboard(dashboard.id)
        
        assert exported is not None
        data = json.loads(exported)
        assert data["name"] == "Test"
    
    def test_import_dashboard(self, dashboard_manager):
        """Test importing dashboard from JSON"""
        json_data = json.dumps({
            "name": "Imported Dashboard",
            "description": "Test import",
            "layout_type": "grid",
            "columns": 12,
            "widgets": []
        })
        
        imported = dashboard_manager.import_dashboard(json_data, owner_id="user1")
        
        assert imported is not None
        assert imported.name == "Imported Dashboard"


# DashboardConfig Tests
class TestDashboardConfig:
    """Tests for DashboardConfig"""
    
    def test_dashboard_config_creation(self):
        """Test dashboard config can be created"""
        config = DashboardConfig(
            id="test-id",
            name="Test Dashboard"
        )
        
        assert config.id == "test-id"
        assert config.name == "Test Dashboard"
        assert config.status == DashboardStatus.DRAFT
    
    def test_add_widget(self, widget_config):
        """Test adding widget to dashboard"""
        dashboard = DashboardConfig(
            id="test-id",
            name="Test"
        )
        
        dashboard.add_widget(widget_config)
        
        assert len(dashboard.widgets) == 1
    
    def test_remove_widget(self, widget_config):
        """Test removing widget from dashboard"""
        dashboard = DashboardConfig(
            id="test-id",
            name="Test"
        )
        dashboard.add_widget(widget_config)
        
        result = dashboard.remove_widget(widget_config.widget_id)
        
        assert result is True
        assert len(dashboard.widgets) == 0
    
    def test_get_widget(self, widget_config):
        """Test getting widget from dashboard"""
        dashboard = DashboardConfig(
            id="test-id",
            name="Test"
        )
        dashboard.add_widget(widget_config)
        
        retrieved = dashboard.get_widget(widget_config.widget_id)
        
        assert retrieved is not None
        assert retrieved.widget_id == widget_config.widget_id
    
    def test_dashboard_to_dict(self):
        """Test dashboard serialization"""
        dashboard = DashboardConfig(
            id="test-id",
            name="Test Dashboard",
            description="Test description"
        )
        
        data = dashboard.to_dict()
        
        assert data["id"] == "test-id"
        assert data["name"] == "Test Dashboard"
        assert "created_at" in data


# WidgetConfig Tests
class TestWidgetConfig:
    """Tests for WidgetConfig"""
    
    def test_widget_config_creation(self):
        """Test widget config can be created"""
        config = WidgetConfig(
            widget_id="w1",
            widget_type=WidgetType.KPI_CARD,
            title="Test Widget",
            position={"x": 0, "y": 0, "width": 4, "height": 2}
        )
        
        assert config.widget_id == "w1"
        assert config.widget_type == WidgetType.KPI_CARD
    
    def test_widget_config_to_dict(self):
        """Test widget config serialization"""
        config = WidgetConfig(
            widget_id="w1",
            widget_type=WidgetType.BAR_CHART,
            title="Test",
            position={"x": 0, "y": 0, "width": 6, "height": 3}
        )
        
        data = config.to_dict()
        
        assert data["widget_id"] == "w1"
        assert data["widget_type"] == "bar_chart"
        assert data["position"]["width"] == 6


# WidgetFactory Tests
class TestWidgetFactory:
    """Tests for WidgetFactory"""
    
    def test_create_kpi_widget(self):
        """Test creating KPI card widget"""
        widget = WidgetFactory.create_widget(
            widget_type="kpi_card",
            widget_id="w1",
            title="KPI Test",
            metric_name="test_metric"
        )
        
        assert widget is not None
        assert widget.widget_type == "kpi_card"
    
    def test_create_chart_widget(self):
        """Test creating chart widget"""
        widget = WidgetFactory.create_widget(
            widget_type="line_chart",
            widget_id="w1",
            title="Chart Test",
            x_axis="date",
            y_axis=["value"]
        )
        
        assert widget is not None
    
    def test_create_table_widget(self):
        """Test creating table widget"""
        widget = WidgetFactory.create_widget(
            widget_type="table",
            widget_id="w1",
            title="Table Test",
            columns=[{"field": "id", "header": "ID"}]
        )
        
        assert widget is not None
    
    def test_create_gauge_widget(self):
        """Test creating gauge widget"""
        widget = WidgetFactory.create_widget(
            widget_type="gauge",
            widget_id="w1",
            title="Gauge Test",
            min_value=0,
            max_value=100
        )
        
        assert widget is not None
    
    def test_list_widget_types(self):
        """Test listing widget types"""
        types = WidgetFactory.list_widget_types()
        
        assert "kpi_card" in types
        assert "line_chart" in types
        assert "table" in types
    
    def test_create_unknown_widget_type(self):
        """Test creating unknown widget type"""
        widget = WidgetFactory.create_widget(
            widget_type="unknown",
            widget_id="w1",
            title="Test"
        )
        
        assert widget is None


# KPICardWidget Tests
class TestKPICardWidget:
    """Tests for KPICardWidget"""
    
    @pytest.mark.asyncio
    async def test_fetch_data(self):
        """Test fetching KPI data"""
        widget = KPICardWidget(
            widget_id="w1",
            title="Test KPI",
            metric_name="test_metric",
            unit="items"
        )
        
        data = await widget.fetch_data(value=100, previous_value=90)
        
        assert data.data["value"] == 100
        assert data.data["change"] == 10
    
    def test_render(self):
        """Test rendering KPI widget"""
        widget = KPICardWidget(
            widget_id="w1",
            title="Test KPI",
            metric_name="test",
            unit="%"
        )
        
        rendered = widget.render()
        
        assert rendered["type"] == "kpi_card"
        assert rendered["title"] == "Test KPI"


# ChartWidget Tests
class TestChartWidget:
    """Tests for ChartWidget"""
    
    @pytest.mark.asyncio
    async def test_fetch_chart_data(self):
        """Test fetching chart data"""
        widget = ChartWidget(
            widget_id="w1",
            title="Test Chart",
            chart_type="line_chart",
            x_axis="date",
            y_axis=["value"]
        )
        
        data = await widget.fetch_data(
            labels=["Jan", "Feb", "Mar"],
            series={"value": [10, 20, 30]}
        )
        
        assert len(data.data["labels"]) == 3
        assert len(data.data["datasets"]) == 1


# TableWidget Tests
class TestTableWidget:
    """Tests for TableWidget"""
    
    @pytest.mark.asyncio
    async def test_fetch_table_data(self):
        """Test fetching table data"""
        widget = TableWidget(
            widget_id="w1",
            title="Test Table",
            columns=[
                {"field": "id", "header": "ID"},
                {"field": "name", "header": "Name"}
            ]
        )
        
        data = await widget.fetch_data(
            rows=[{"id": 1, "name": "Test"}],
            total_rows=1
        )
        
        assert len(data.data["rows"]) == 1
        assert data.data["total_rows"] == 1


# GaugeWidget Tests
class TestGaugeWidget:
    """Tests for GaugeWidget"""
    
    @pytest.mark.asyncio
    async def test_fetch_gauge_data(self):
        """Test fetching gauge data"""
        widget = GaugeWidget(
            widget_id="w1",
            title="Test Gauge",
            min_value=0,
            max_value=100
        )
        
        data = await widget.fetch_data(value=75)
        
        assert data.data["value"] == 75
        assert data.data["percentage"] == 75


# WidgetLibrary Tests
class TestWidgetLibrary:
    """Tests for WidgetLibrary"""
    
    def test_list_presets(self, widget_library):
        """Test listing presets"""
        presets = widget_library.list_presets()
        
        assert len(presets) > 0
        assert "tickets_open" in presets
    
    def test_get_preset(self, widget_library):
        """Test getting a preset"""
        preset = widget_library.get_preset("tickets_open")
        
        assert preset is not None
        assert preset["type"] == "kpi_card"
    
    def test_create_from_preset(self, widget_library):
        """Test creating widget from preset"""
        widget = widget_library.create_from_preset("tickets_open", "w1")
        
        assert widget is not None
        assert widget.title == "Open Tickets"
    
    def test_register_preset(self, widget_library):
        """Test registering custom preset"""
        widget_library.register_preset("custom_kpi", {
            "type": "kpi_card",
            "title": "Custom KPI",
            "metric_name": "custom"
        })
        
        preset = widget_library.get_preset("custom_kpi")
        assert preset is not None


# DashboardStorage Tests
class TestDashboardStorage:
    """Tests for DashboardStorage"""
    
    def test_storage_initialization(self, dashboard_storage):
        """Test storage initializes correctly"""
        assert dashboard_storage._initialized is True
    
    def test_save_dashboard(self, dashboard_storage):
        """Test saving dashboard"""
        result = dashboard_storage.save_dashboard("d1", {"name": "Test"})
        
        assert result is True
    
    def test_load_dashboard(self, dashboard_storage):
        """Test loading dashboard"""
        dashboard_storage.save_dashboard("d1", {"name": "Test"})
        
        data = dashboard_storage.load_dashboard("d1")
        
        assert data is not None
        assert data["name"] == "Test"
    
    def test_delete_dashboard(self, dashboard_storage):
        """Test deleting dashboard"""
        dashboard_storage.save_dashboard("d1", {"name": "Test"})
        
        result = dashboard_storage.delete_dashboard("d1")
        
        assert result is True
        assert dashboard_storage.load_dashboard("d1") is None
    
    def test_list_dashboards(self, dashboard_storage):
        """Test listing dashboards"""
        dashboard_storage.save_dashboard("d1", {"name": "Test 1"})
        dashboard_storage.save_dashboard("d2", {"name": "Test 2"})
        
        ids = dashboard_storage.list_dashboards()
        
        assert len(ids) == 2
    
    def test_widget_data_cache(self, dashboard_storage):
        """Test widget data caching"""
        dashboard_storage.save_widget_data("d1", "w1", {"value": 100})
        
        data = dashboard_storage.load_widget_data("d1", "w1")
        
        assert data is not None
        assert data["value"] == 100
    
    def test_get_storage_stats(self, dashboard_storage):
        """Test getting storage stats"""
        stats = dashboard_storage.get_storage_stats()
        
        assert "storage_type" in stats
        assert "initialized" in stats


# Enum Tests
class TestEnums:
    """Tests for enum values"""
    
    def test_dashboard_status(self):
        """Test DashboardStatus enum"""
        assert DashboardStatus.DRAFT.value == "draft"
        assert DashboardStatus.PUBLISHED.value == "published"
        assert DashboardStatus.ARCHIVED.value == "archived"
    
    def test_widget_type(self):
        """Test WidgetType enum"""
        assert WidgetType.KPI_CARD.value == "kpi_card"
        assert WidgetType.LINE_CHART.value == "line_chart"
        assert WidgetType.TABLE.value == "table"
    
    def test_layout_type(self):
        """Test LayoutType enum"""
        assert LayoutType.GRID.value == "grid"
        assert LayoutType.FLEX.value == "flex"
