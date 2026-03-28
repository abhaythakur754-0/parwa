"""
Tests for Data Aggregation and Visualization
Enterprise Analytics & Reporting - Week 44 Builders 4-5
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

from enterprise.analytics.data_aggregator import (
    DataAggregator,
    AggregationJob,
    AggregationResult,
    AggregationType,
    AggregationPeriod,
    MetricStore
)
from enterprise.analytics.chart_engine import (
    ChartEngine,
    ChartConfig,
    ChartAxis,
    ChartSeries,
    ChartData,
    ChartType,
    ColorScheme,
    VisualizationConfig
)


# Test Fixtures
@pytest.fixture
def data_aggregator():
    """Create a test data aggregator"""
    return DataAggregator()


@pytest.fixture
def metric_store():
    """Create a test metric store"""
    return MetricStore()


@pytest.fixture
def chart_engine():
    """Create a test chart engine"""
    return ChartEngine()


@pytest.fixture
def viz_config():
    """Create a test visualization config"""
    return VisualizationConfig()


# DataAggregator Tests
class TestDataAggregator:
    """Tests for DataAggregator"""
    
    def test_aggregator_initialization(self, data_aggregator):
        """Test aggregator initializes correctly"""
        assert data_aggregator is not None
    
    def test_register_source(self, data_aggregator):
        """Test registering a data source"""
        data_aggregator.register_source("test_source", {"data": []})
        
        assert "test_source" in data_aggregator._sources
    
    def test_create_job(self, data_aggregator):
        """Test creating an aggregation job"""
        job = data_aggregator.create_job(
            name="Test Job",
            source="test_source",
            aggregation_type=AggregationType.SUM,
            period=AggregationPeriod.DAILY,
            metrics=["tickets", "resolved"]
        )
        
        assert job.id is not None
        assert job.name == "Test Job"
        assert job.aggregation_type == AggregationType.SUM
    
    def test_get_job(self, data_aggregator):
        """Test getting an aggregation job"""
        created = data_aggregator.create_job(
            "Test", "src", AggregationType.AVG, AggregationPeriod.HOURLY, ["metric"]
        )
        
        retrieved = data_aggregator.get_job(created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
    
    def test_list_jobs(self, data_aggregator):
        """Test listing aggregation jobs"""
        data_aggregator.create_job("J1", "src", AggregationType.SUM, AggregationPeriod.DAILY, [])
        data_aggregator.create_job("J2", "src", AggregationType.AVG, AggregationPeriod.HOURLY, [])
        
        jobs = data_aggregator.list_jobs()
        assert len(jobs) == 2
    
    @pytest.mark.asyncio
    async def test_run_job(self, data_aggregator):
        """Test running an aggregation job"""
        job = data_aggregator.create_job(
            "Test", "src", AggregationType.SUM, AggregationPeriod.DAILY, ["tickets"]
        )
        
        result = await data_aggregator.run_job(job.id)
        
        assert result is not None
        assert result.job_id == job.id
    
    @pytest.mark.asyncio
    async def test_aggregate_sum(self, data_aggregator):
        """Test sum aggregation"""
        data = [
            {"category": "A", "value": 10},
            {"category": "A", "value": 20},
            {"category": "B", "value": 15}
        ]
        
        result = await data_aggregator.aggregate(
            data, AggregationType.SUM, "value", "category"
        )
        
        assert result["A"] == 30
        assert result["B"] == 15
    
    @pytest.mark.asyncio
    async def test_aggregate_avg(self, data_aggregator):
        """Test average aggregation"""
        data = [
            {"value": 10},
            {"value": 20},
            {"value": 30}
        ]
        
        result = await data_aggregator.aggregate(
            data, AggregationType.AVG, "value"
        )
        
        assert result["value"] == 20
    
    @pytest.mark.asyncio
    async def test_aggregate_count(self, data_aggregator):
        """Test count aggregation"""
        data = [{"value": 1}, {"value": 2}, {"value": 3}]
        
        result = await data_aggregator.aggregate(
            data, AggregationType.COUNT, "value"
        )
        
        assert result["value"] == 3
    
    @pytest.mark.asyncio
    async def test_aggregate_min_max(self, data_aggregator):
        """Test min/max aggregation"""
        data = [{"value": 10}, {"value": 5}, {"value": 20}]
        
        min_result = await data_aggregator.aggregate(data, AggregationType.MIN, "value")
        max_result = await data_aggregator.aggregate(data, AggregationType.MAX, "value")
        
        assert min_result["value"] == 5
        assert max_result["value"] == 20


# AggregationJob Tests
class TestAggregationJob:
    """Tests for AggregationJob"""
    
    def test_job_creation(self):
        """Test job can be created"""
        job = AggregationJob(
            id="job-1",
            name="Test",
            source="source",
            aggregation_type=AggregationType.SUM,
            period=AggregationPeriod.DAILY,
            metrics=["m1", "m2"]
        )
        
        assert job.id == "job-1"
        assert job.enabled is True
    
    def test_job_to_dict(self):
        """Test job serialization"""
        job = AggregationJob(
            id="j1",
            name="Test",
            source="src",
            aggregation_type=AggregationType.AVG,
            period=AggregationPeriod.WEEKLY,
            metrics=[]
        )
        
        data = job.to_dict()
        
        assert data["id"] == "j1"
        assert data["aggregation_type"] == "avg"
        assert data["period"] == "weekly"


# MetricStore Tests
class TestMetricStore:
    """Tests for MetricStore"""
    
    def test_store_metric(self, metric_store):
        """Test storing a metric"""
        metric_store.store("tickets", 100)
        
        assert "tickets" in metric_store._metrics
    
    def test_store_with_tags(self, metric_store):
        """Test storing metric with tags"""
        metric_store.store("response_time", 150, tags={"team": "support"})
        
        values = metric_store.get("response_time")
        assert len(values) == 1
        assert values[0]["tags"]["team"] == "support"
    
    def test_get_metric(self, metric_store):
        """Test getting metric values"""
        metric_store.store("test", 10)
        metric_store.store("test", 20)
        metric_store.store("test", 30)
        
        values = metric_store.get("test")
        
        assert len(values) == 3
    
    def test_get_metric_with_time_filter(self, metric_store):
        """Test getting metrics with time filter"""
        now = datetime.utcnow()
        metric_store.store("test", 10, timestamp=now - timedelta(hours=2))
        metric_store.store("test", 20, timestamp=now - timedelta(hours=1))
        metric_store.store("test", 30, timestamp=now)
        
        values = metric_store.get("test", start=now - timedelta(minutes=90))
        
        assert len(values) == 2
    
    def test_get_latest(self, metric_store):
        """Test getting latest metric"""
        metric_store.store("test", 10)
        metric_store.store("test", 20)
        
        latest = metric_store.get_latest("test")
        
        assert latest["value"] == 20
    
    def test_aggregate_stored_metrics(self, metric_store):
        """Test aggregating stored metrics"""
        metric_store.store("test", 10)
        metric_store.store("test", 20)
        metric_store.store("test", 30)
        
        result = metric_store.aggregate("test", AggregationType.SUM)
        
        assert result == 60


# ChartEngine Tests
class TestChartEngine:
    """Tests for ChartEngine"""
    
    def test_engine_initialization(self, chart_engine):
        """Test engine initializes correctly"""
        assert chart_engine is not None
    
    def test_create_chart(self, chart_engine):
        """Test creating a chart"""
        chart = chart_engine.create_chart(
            title="Test Chart",
            chart_type=ChartType.LINE
        )
        
        assert chart.id is not None
        assert chart.title == "Test Chart"
        assert chart.chart_type == ChartType.LINE
    
    def test_get_chart(self, chart_engine):
        """Test getting a chart"""
        created = chart_engine.create_chart("Test", ChartType.BAR)
        
        retrieved = chart_engine.get_chart(created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
    
    def test_add_series(self, chart_engine):
        """Test adding a series to chart"""
        chart = chart_engine.create_chart("Test", ChartType.LINE)
        
        series = chart_engine.add_series(chart.id, "Series 1", [1, 2, 3, 4, 5])
        
        assert series is not None
        assert series.name == "Series 1"
        assert len(chart.series) == 1
    
    def test_process_data(self, chart_engine):
        """Test processing raw data"""
        chart = chart_engine.create_chart("Test", ChartType.BAR)
        
        raw_data = [
            {"category": "A", "value": 10},
            {"category": "B", "value": 20},
            {"category": "A", "value": 15}
        ]
        
        result = chart_engine.process_data(chart.id, raw_data, "category", "value")
        
        assert len(result.labels) == 2  # A and B
        assert "A" in result.labels
    
    def test_render_chart(self, chart_engine):
        """Test rendering chart"""
        chart = chart_engine.create_chart("Test", ChartType.LINE)
        chart_engine.add_series(chart.id, "Data", [1, 2, 3])
        
        rendered = chart_engine.render(chart.id)
        
        assert "type" in rendered
        assert rendered["type"] == "line"
    
    def test_list_charts(self, chart_engine):
        """Test listing charts"""
        chart_engine.create_chart("C1", ChartType.LINE)
        chart_engine.create_chart("C2", ChartType.BAR)
        
        charts = chart_engine.list_charts()
        assert len(charts) == 2
    
    def test_delete_chart(self, chart_engine):
        """Test deleting a chart"""
        chart = chart_engine.create_chart("Test", ChartType.PIE)
        
        result = chart_engine.delete_chart(chart.id)
        
        assert result is True
        assert chart_engine.get_chart(chart.id) is None
    
    @pytest.mark.asyncio
    async def test_export_chart(self, chart_engine):
        """Test exporting chart"""
        chart = chart_engine.create_chart("Test", ChartType.LINE)
        
        exported = await chart_engine.export(chart.id)
        
        assert exported is not None
        assert "title" in exported


# ChartConfig Tests
class TestChartConfig:
    """Tests for ChartConfig"""
    
    def test_config_creation(self):
        """Test chart config can be created"""
        config = ChartConfig(
            id="chart-1",
            title="Test",
            chart_type=ChartType.BAR
        )
        
        assert config.id == "chart-1"
        assert config.show_legend is True
    
    def test_config_to_dict(self):
        """Test config serialization"""
        config = ChartConfig(
            id="c1",
            title="Test",
            chart_type=ChartType.LINE,
            color_scheme=ColorScheme.SEQUENTIAL
        )
        
        data = config.to_dict()
        
        assert data["id"] == "c1"
        assert data["chart_type"] == "line"
        assert data["color_scheme"] == "sequential"


# ChartAxis Tests
class TestChartAxis:
    """Tests for ChartAxis"""
    
    def test_axis_creation(self):
        """Test axis can be created"""
        axis = ChartAxis(label="X Axis", field="date")
        
        assert axis.label == "X Axis"
        assert axis.field == "date"
    
    def test_axis_to_dict(self):
        """Test axis serialization"""
        axis = ChartAxis(label="Value", field="amount", min=0, max=100)
        
        data = axis.to_dict()
        
        assert data["label"] == "Value"
        assert data["min"] == 0
        assert data["max"] == 100


# ChartSeries Tests
class TestChartSeries:
    """Tests for ChartSeries"""
    
    def test_series_creation(self):
        """Test series can be created"""
        series = ChartSeries(name="Series A", data=[1, 2, 3])
        
        assert series.name == "Series A"
        assert len(series.data) == 3
    
    def test_series_to_dict(self):
        """Test series serialization"""
        series = ChartSeries(name="Test", data=[10, 20], color="#ff0000")
        
        data = series.to_dict()
        
        assert data["name"] == "Test"
        assert data["color"] == "#ff0000"


# VisualizationConfig Tests
class TestVisualizationConfig:
    """Tests for VisualizationConfig"""
    
    def test_config_initialization(self, viz_config):
        """Test config initializes with presets"""
        assert len(viz_config._presets) > 0
    
    def test_get_preset(self, viz_config):
        """Test getting a preset"""
        preset = viz_config.get_preset("line_trend")
        
        assert preset is not None
        assert preset["chart_type"] == "line"
    
    def test_list_presets(self, viz_config):
        """Test listing presets"""
        presets = viz_config.list_presets()
        
        assert "line_trend" in presets
        assert "bar_comparison" in presets
        assert "pie_distribution" in presets
    
    def test_create_custom(self, viz_config):
        """Test creating custom config"""
        viz_config.create_custom("my_chart", {
            "chart_type": "custom",
            "custom_option": True
        })
        
        config = viz_config.get_config("my_chart")
        
        assert config is not None
        assert config["custom_option"] is True


# Enum Tests
class TestEnums:
    """Tests for enum values"""
    
    def test_aggregation_type(self):
        """Test AggregationType enum"""
        assert AggregationType.SUM.value == "sum"
        assert AggregationType.AVG.value == "avg"
        assert AggregationType.COUNT.value == "count"
    
    def test_aggregation_period(self):
        """Test AggregationPeriod enum"""
        assert AggregationPeriod.HOURLY.value == "hourly"
        assert AggregationPeriod.DAILY.value == "daily"
        assert AggregationPeriod.WEEKLY.value == "weekly"
    
    def test_chart_type(self):
        """Test ChartType enum"""
        assert ChartType.LINE.value == "line"
        assert ChartType.BAR.value == "bar"
        assert ChartType.PIE.value == "pie"
    
    def test_color_scheme(self):
        """Test ColorScheme enum"""
        assert ColorScheme.DEFAULT.value == "default"
        assert ColorScheme.SEQUENTIAL.value == "sequential"
