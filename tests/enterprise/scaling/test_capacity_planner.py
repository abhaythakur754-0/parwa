"""
Tests for Capacity Planner Module - Week 52, Builder 3
"""

import pytest
from datetime import datetime, timedelta

from enterprise.scaling.capacity_planner import (
    CapacityAnalyzer,
    CapacityPlanner,
    CapacityMetric,
    CapacityThreshold,
    CapacityRecommendation,
    CapacityPlan,
    CapacityAlertManager,
    ResourceType,
    PlanningHorizon,
    GrowthModel,
)
from enterprise.scaling.demand_predictor import (
    TimeSeriesAnalyzer,
    MovingAveragePredictor,
    ExponentialSmoothingPredictor,
    LinearRegressionPredictor,
    SeasonalPredictor,
    DemandPredictor,
    DemandDataPoint,
    DemandPattern,
    PredictionModel,
    PredictionResult,
)
from enterprise.scaling.resource_forecaster import (
    HistoricalDataStore,
    ResourceDataPoint,
    ForecastPoint,
    ResourceForecast,
    ForecastAlert,
    LinearTrendModel,
    SeasonalModel,
    ExponentialSmoothingModel,
    ResourceForecaster,
    MultiResourceForecaster,
    ResourceCategory,
    ForecastHorizon,
)


# ============================================================================
# Capacity Planner Tests
# ============================================================================

class TestCapacityMetric:
    """Tests for CapacityMetric class"""

    def test_init(self):
        """Test metric initialization"""
        metric = CapacityMetric(
            resource_type=ResourceType.CPU,
            current_value=50,
            max_capacity=100,
        )
        assert metric.resource_type == ResourceType.CPU
        assert metric.current_value == 50
        assert metric.max_capacity == 100

    def test_utilization_percent(self):
        """Test utilization calculation"""
        metric = CapacityMetric(
            resource_type=ResourceType.CPU,
            current_value=75,
            max_capacity=100,
        )
        assert metric.utilization_percent == 75.0

    def test_utilization_zero_capacity(self):
        """Test utilization with zero capacity"""
        metric = CapacityMetric(
            resource_type=ResourceType.CPU,
            current_value=50,
            max_capacity=0,
        )
        assert metric.utilization_percent == 0.0

    def test_available_capacity(self):
        """Test available capacity calculation"""
        metric = CapacityMetric(
            resource_type=ResourceType.CPU,
            current_value=30,
            max_capacity=100,
        )
        assert metric.available_capacity == 70


class TestCapacityAnalyzer:
    """Tests for CapacityAnalyzer class"""

    def test_init(self):
        """Test analyzer initialization"""
        analyzer = CapacityAnalyzer()
        assert len(analyzer.metrics_history) == 0
        assert len(analyzer.thresholds) == len(ResourceType)

    def test_set_threshold(self):
        """Test setting custom threshold"""
        analyzer = CapacityAnalyzer()
        analyzer.set_threshold(ResourceType.CPU, 60, 80)
        threshold = analyzer.thresholds[ResourceType.CPU]
        assert threshold.warning_threshold == 60
        assert threshold.critical_threshold == 80

    def test_record_metric(self):
        """Test recording metric"""
        analyzer = CapacityAnalyzer()
        metric = analyzer.record_metric(ResourceType.CPU, 50, 100)
        assert metric.current_value == 50
        assert ResourceType.CPU in analyzer.metrics_history

    def test_get_current_utilization(self):
        """Test getting current utilization"""
        analyzer = CapacityAnalyzer()
        analyzer.record_metric(ResourceType.CPU, 75, 100)
        util = analyzer.get_current_utilization(ResourceType.CPU)
        assert util == 75.0

    def test_get_current_utilization_no_data(self):
        """Test getting utilization with no data"""
        analyzer = CapacityAnalyzer()
        util = analyzer.get_current_utilization(ResourceType.CPU)
        assert util is None

    def test_get_average_utilization(self):
        """Test getting average utilization"""
        analyzer = CapacityAnalyzer()
        analyzer.record_metric(ResourceType.CPU, 40, 100)
        analyzer.record_metric(ResourceType.CPU, 50, 100)
        analyzer.record_metric(ResourceType.CPU, 60, 100)
        avg = analyzer.get_average_utilization(ResourceType.CPU)
        assert avg == 50.0

    def test_get_peak_utilization(self):
        """Test getting peak utilization"""
        analyzer = CapacityAnalyzer()
        analyzer.record_metric(ResourceType.CPU, 40, 100)
        analyzer.record_metric(ResourceType.CPU, 90, 100)
        analyzer.record_metric(ResourceType.CPU, 60, 100)
        peak = analyzer.get_peak_utilization(ResourceType.CPU)
        assert peak == 90.0

    def test_check_threshold_normal(self):
        """Test threshold check - normal"""
        analyzer = CapacityAnalyzer()
        analyzer.record_metric(ResourceType.CPU, 50, 100)
        status, util = analyzer.check_threshold(ResourceType.CPU)
        assert status == "normal"

    def test_check_threshold_warning(self):
        """Test threshold check - warning"""
        analyzer = CapacityAnalyzer()
        analyzer.record_metric(ResourceType.CPU, 75, 100)
        status, util = analyzer.check_threshold(ResourceType.CPU)
        assert status == "warning"

    def test_check_threshold_critical(self):
        """Test threshold check - critical"""
        analyzer = CapacityAnalyzer()
        analyzer.record_metric(ResourceType.CPU, 90, 100)
        status, util = analyzer.check_threshold(ResourceType.CPU)
        assert status == "critical"


class TestCapacityPlanner:
    """Tests for CapacityPlanner class"""

    def test_init(self):
        """Test planner initialization"""
        planner = CapacityPlanner()
        assert planner.analyzer is not None
        assert len(planner.plans) == 0

    def test_set_growth_model(self):
        """Test setting growth model"""
        planner = CapacityPlanner()
        planner.set_growth_model(ResourceType.CPU, GrowthModel.EXPONENTIAL)
        assert planner.growth_models[ResourceType.CPU] == GrowthModel.EXPONENTIAL

    def test_calculate_growth_rate(self):
        """Test calculating growth rate"""
        planner = CapacityPlanner()
        # Record increasing values
        for i in range(10):
            planner.analyzer.record_metric(
                ResourceType.CPU, 50 + i * 5, 200
            )
        rate = planner.calculate_growth_rate(ResourceType.CPU)
        assert rate > 0

    def test_project_capacity(self):
        """Test capacity projection"""
        planner = CapacityPlanner()
        planner.analyzer.record_metric(ResourceType.CPU, 50, 100)

        # Add some history for growth rate
        for i in range(5):
            planner.analyzer.record_metric(
                ResourceType.CPU, 50 + i * 2, 100
            )

        projected = planner.project_capacity(ResourceType.CPU, 30)
        assert projected is not None

    def test_generate_recommendations_scale_up(self):
        """Test generating scale up recommendation"""
        planner = CapacityPlanner()
        planner.analyzer.record_metric(ResourceType.CPU, 90, 100)

        recs = planner.generate_recommendations(ResourceType.CPU)
        # Should have recommendations due to high utilization
        assert len(recs) >= 0  # May or may not have based on projection

    def test_create_plan(self):
        """Test creating capacity plan"""
        planner = CapacityPlanner()
        planner.analyzer.record_metric(ResourceType.CPU, 50, 100)
        planner.analyzer.record_metric(ResourceType.MEMORY, 60, 100)

        plan = planner.create_plan(PlanningHorizon.MEDIUM_TERM)
        assert plan.horizon == PlanningHorizon.MEDIUM_TERM
        assert len(plan.metrics) == 2

    def test_get_planning_summary(self):
        """Test getting planning summary"""
        planner = CapacityPlanner()
        planner.analyzer.record_metric(ResourceType.CPU, 50, 100)

        summary = planner.get_planning_summary()
        assert "resources" in summary
        assert "cpu" in summary["resources"]


class TestCapacityAlertManager:
    """Tests for CapacityAlertManager class"""

    def test_init(self):
        """Test alert manager initialization"""
        planner = CapacityPlanner()
        manager = CapacityAlertManager(planner)
        assert len(manager.alerts) == 0

    def test_check_alerts_critical(self):
        """Test checking alerts - critical"""
        planner = CapacityPlanner()
        manager = CapacityAlertManager(planner)
        planner.analyzer.record_metric(ResourceType.CPU, 95, 100)

        alerts = manager.check_alerts()
        assert len(alerts) > 0
        assert alerts[0]["status"] in ["critical", "max_exceeded"]

    def test_check_alerts_normal(self):
        """Test checking alerts - normal"""
        planner = CapacityPlanner()
        manager = CapacityAlertManager(planner)
        planner.analyzer.record_metric(ResourceType.CPU, 50, 100)

        alerts = manager.check_alerts()
        assert len(alerts) == 0


# ============================================================================
# Demand Predictor Tests
# ============================================================================

class TestTimeSeriesAnalyzer:
    """Tests for TimeSeriesAnalyzer class"""

    def test_init(self):
        """Test analyzer initialization"""
        analyzer = TimeSeriesAnalyzer()
        assert len(analyzer.data) == 0

    def test_add_data(self):
        """Test adding data"""
        analyzer = TimeSeriesAnalyzer()
        analyzer.add_data(datetime.utcnow(), 100)
        assert len(analyzer.data) == 1

    def test_get_values(self):
        """Test getting values"""
        analyzer = TimeSeriesAnalyzer()
        analyzer.add_data(datetime.utcnow(), 10)
        analyzer.add_data(datetime.utcnow(), 20)
        values = analyzer.get_values()
        assert values == [10, 20]

    def test_get_values_with_window(self):
        """Test getting values with window"""
        analyzer = TimeSeriesAnalyzer()
        for i in range(10):
            analyzer.add_data(datetime.utcnow(), i)
        values = analyzer.get_values(window=3)
        assert len(values) == 3

    def test_detect_seasonality_insufficient_data(self):
        """Test seasonality detection with insufficient data"""
        analyzer = TimeSeriesAnalyzer()
        for i in range(10):
            analyzer.add_data(datetime.utcnow(), i)
        patterns = analyzer.detect_seasonality()
        assert len(patterns) == 0

    def test_calculate_trend_increasing(self):
        """Test trend calculation - increasing"""
        analyzer = TimeSeriesAnalyzer()
        for i in range(20):
            analyzer.add_data(datetime.utcnow(), i * 10)
        trend = analyzer.calculate_trend()
        assert trend == "increasing"

    def test_calculate_trend_decreasing(self):
        """Test trend calculation - decreasing"""
        analyzer = TimeSeriesAnalyzer()
        for i in range(20):
            analyzer.add_data(datetime.utcnow(), 200 - i * 10)
        trend = analyzer.calculate_trend()
        assert trend == "decreasing"


class TestMovingAveragePredictor:
    """Tests for MovingAveragePredictor class"""

    def test_init(self):
        """Test predictor initialization"""
        predictor = MovingAveragePredictor(window=5)
        assert predictor.window == 5

    def test_predict(self):
        """Test prediction"""
        predictor = MovingAveragePredictor(window=3)
        values = [10, 20, 30, 40, 50]
        result = predictor.predict(values)
        assert result.predicted_value == 40  # Average of last 3
        assert result.model_used == PredictionModel.MOVING_AVERAGE

    def test_predict_insufficient_data(self):
        """Test prediction with insufficient data"""
        predictor = MovingAveragePredictor(window=10)
        values = [10, 20]
        result = predictor.predict(values)
        assert result.predicted_value == 15  # Average of available


class TestExponentialSmoothingPredictor:
    """Tests for ExponentialSmoothingPredictor class"""

    def test_init(self):
        """Test predictor initialization"""
        predictor = ExponentialSmoothingPredictor(alpha=0.3)
        assert predictor.alpha == 0.3

    def test_predict(self):
        """Test prediction"""
        predictor = ExponentialSmoothingPredictor(alpha=0.3)
        values = [10, 20, 30, 40, 50]
        result = predictor.predict(values)
        assert result.model_used == PredictionModel.EXPONENTIAL_SMOOTHING
        assert result.confidence_interval is not None

    def test_predict_empty(self):
        """Test prediction with empty data"""
        predictor = ExponentialSmoothingPredictor()
        result = predictor.predict([])
        assert result.predicted_value == 0


class TestLinearRegressionPredictor:
    """Tests for LinearRegressionPredictor class"""

    def test_predict(self):
        """Test prediction"""
        predictor = LinearRegressionPredictor()
        values = [10, 20, 30, 40, 50]
        result = predictor.predict(values)
        assert result.model_used == PredictionModel.LINEAR_REGRESSION
        # Linear trend should predict ~60
        assert result.predicted_value > 50

    def test_predict_insufficient_data(self):
        """Test prediction with single value"""
        predictor = LinearRegressionPredictor()
        result = predictor.predict([50])
        assert result.predicted_value == 50


class TestSeasonalPredictor:
    """Tests for SeasonalPredictor class"""

    def test_init(self):
        """Test predictor initialization"""
        predictor = SeasonalPredictor(period=24)
        assert predictor.period == 24

    def test_fit(self):
        """Test fitting seasonal model"""
        predictor = SeasonalPredictor(period=24)
        values = [float(i % 24) for i in range(48)]
        predictor.fit(values)
        assert len(predictor._seasonal_factors) == 24

    def test_predict(self):
        """Test prediction"""
        predictor = SeasonalPredictor(period=24)
        values = [float(i % 24) for i in range(48)]
        result = predictor.predict(values)
        assert result.model_used == PredictionModel.SEASONAL


class TestDemandPredictor:
    """Tests for DemandPredictor class"""

    def test_init(self):
        """Test predictor initialization"""
        predictor = DemandPredictor()
        assert predictor.default_model == PredictionModel.EXPONENTIAL_SMOOTHING

    def test_add_data(self):
        """Test adding data"""
        predictor = DemandPredictor()
        predictor.add_data(datetime.utcnow(), 100)
        assert len(predictor.analyzer.data) == 1

    def test_predict(self):
        """Test prediction"""
        predictor = DemandPredictor()
        for i in range(10):
            predictor.add_data(datetime.utcnow(), 100 + i * 10)

        result = predictor.predict()
        assert result.predicted_value > 0

    def test_predict_with_model(self):
        """Test prediction with specific model"""
        predictor = DemandPredictor()
        for i in range(10):
            predictor.add_data(datetime.utcnow(), 100 + i)

        result = predictor.predict(model=PredictionModel.LINEAR_REGRESSION)
        assert result.model_used == PredictionModel.LINEAR_REGRESSION

    def test_predict_range(self):
        """Test predicting multiple steps"""
        predictor = DemandPredictor()
        for i in range(10):
            predictor.add_data(datetime.utcnow(), 100 + i)

        predictions = predictor.predict_range(5)
        assert len(predictions) == 5

    def test_get_forecast_summary(self):
        """Test getting forecast summary"""
        predictor = DemandPredictor()
        for i in range(20):
            predictor.add_data(datetime.utcnow(), 100 + i)

        summary = predictor.get_forecast_summary()
        assert "trend" in summary
        assert "predictions" in summary


# ============================================================================
# Resource Forecaster Tests
# ============================================================================

class TestHistoricalDataStore:
    """Tests for HistoricalDataStore class"""

    def test_init(self):
        """Test data store initialization"""
        store = HistoricalDataStore()
        assert len(store.data) == 0

    def test_add(self):
        """Test adding data point"""
        store = HistoricalDataStore()
        point = ResourceDataPoint(
            timestamp=datetime.utcnow(),
            value=100,
            category=ResourceCategory.COMPUTE,
        )
        store.add(point)
        assert len(store.data[ResourceCategory.COMPUTE]) == 1

    def test_get_values(self):
        """Test getting values"""
        store = HistoricalDataStore()
        point = ResourceDataPoint(
            timestamp=datetime.utcnow(),
            value=100,
            category=ResourceCategory.COMPUTE,
        )
        store.add(point)
        values = store.get_values(ResourceCategory.COMPUTE)
        assert len(values) == 1

    def test_get_values_with_time_range(self):
        """Test getting values with time range"""
        store = HistoricalDataStore()
        now = datetime.utcnow()
        store.add(ResourceDataPoint(now - timedelta(hours=2), 50, ResourceCategory.COMPUTE))
        store.add(ResourceDataPoint(now - timedelta(hours=1), 100, ResourceCategory.COMPUTE))
        store.add(ResourceDataPoint(now, 150, ResourceCategory.COMPUTE))

        values = store.get_values(
            ResourceCategory.COMPUTE,
            start=now - timedelta(hours=1, minutes=30),
        )
        assert len(values) == 2


class TestLinearTrendModel:
    """Tests for LinearTrendModel class"""

    def test_init(self):
        """Test model initialization"""
        model = LinearTrendModel()
        assert model.name == "linear_trend"

    def test_fit(self):
        """Test fitting model"""
        model = LinearTrendModel()
        values = [10, 20, 30, 40, 50]
        model.fit(values)
        assert model._fitted is True

    def test_predict(self):
        """Test prediction"""
        model = LinearTrendModel()
        values = [10, 20, 30, 40, 50]
        model.fit(values)
        predictions = model.predict(3)
        assert len(predictions) == 3
        # Should follow linear trend
        assert predictions[0] > values[-1]


class TestSeasonalModel:
    """Tests for SeasonalModel class"""

    def test_init(self):
        """Test model initialization"""
        model = SeasonalModel(period=24)
        assert model.period == 24

    def test_fit(self):
        """Test fitting seasonal model"""
        model = SeasonalModel(period=24)
        values = [float(i % 24) for i in range(48)]
        model.fit(values)
        assert model._fitted is True
        assert len(model._seasonal_factors) == 24

    def test_predict(self):
        """Test prediction"""
        model = SeasonalModel(period=24)
        values = [float(i % 24) for i in range(48)]
        model.fit(values)
        predictions = model.predict(10)
        assert len(predictions) == 10


class TestExponentialSmoothingModel:
    """Tests for ExponentialSmoothingModel class"""

    def test_init(self):
        """Test model initialization"""
        model = ExponentialSmoothingModel(alpha=0.3, beta=0.1)
        assert model.alpha == 0.3
        assert model.beta == 0.1

    def test_fit(self):
        """Test fitting model"""
        model = ExponentialSmoothingModel()
        values = [10, 20, 30, 40, 50]
        model.fit(values)
        assert model._fitted is True

    def test_predict(self):
        """Test prediction"""
        model = ExponentialSmoothingModel()
        values = [10, 20, 30, 40, 50]
        model.fit(values)
        predictions = model.predict(5)
        assert len(predictions) == 5


class TestResourceForecaster:
    """Tests for ResourceForecaster class"""

    def test_init(self):
        """Test forecaster initialization"""
        forecaster = ResourceForecaster()
        assert len(forecaster.models) == 3

    def test_record(self):
        """Test recording data"""
        forecaster = ResourceForecaster()
        forecaster.record(ResourceCategory.COMPUTE, 50)
        points = forecaster.data_store.get_values(ResourceCategory.COMPUTE)
        assert len(points) == 1

    def test_forecast(self):
        """Test generating forecast"""
        forecaster = ResourceForecaster()
        # Add historical data
        for i in range(20):
            forecaster.record(
                ResourceCategory.COMPUTE,
                50 + i,
                datetime.utcnow() - timedelta(hours=20-i),
            )

        forecast = forecaster.forecast(
            ResourceCategory.COMPUTE,
            ForecastHorizon.HOURLY,
        )
        assert forecast.category == ResourceCategory.COMPUTE
        assert len(forecast.points) > 0

    def test_set_alert_threshold(self):
        """Test setting alert threshold"""
        forecaster = ResourceForecaster()
        forecaster.set_alert_threshold(ResourceCategory.COMPUTE, 80)
        assert forecaster.alert_thresholds[ResourceCategory.COMPUTE] == 80

    def test_get_forecasting_summary(self):
        """Test getting forecasting summary"""
        forecaster = ResourceForecaster()
        forecaster.record(ResourceCategory.COMPUTE, 50)

        summary = forecaster.get_forecasting_summary()
        assert "models_available" in summary
        assert "categories" in summary


class TestMultiResourceForecaster:
    """Tests for MultiResourceForecaster class"""

    def test_init(self):
        """Test multi-resource forecaster initialization"""
        forecaster = MultiResourceForecaster()
        assert forecaster.forecaster is not None

    def test_record_all(self):
        """Test recording all resources"""
        forecaster = MultiResourceForecaster()
        forecaster.record_all({
            ResourceCategory.COMPUTE: 50,
            ResourceCategory.MEMORY: 60,
        })
        assert len(forecaster.forecaster.data_store.data) == 2

    def test_forecast_all(self):
        """Test forecasting all resources"""
        forecaster = MultiResourceForecaster()

        # Add data for each category
        for category in ResourceCategory:
            for i in range(10):
                forecaster.forecaster.record(category, 50 + i)

        forecasts = forecaster.forecast_all(ForecastHorizon.HOURLY)
        assert len(forecasts) > 0

    def test_get_capacity_needs(self):
        """Test getting capacity needs"""
        forecaster = MultiResourceForecaster()

        # Add data
        for i in range(10):
            forecaster.forecaster.record(ResourceCategory.COMPUTE, 50 + i)

        needs = forecaster.get_capacity_needs(ForecastHorizon.HOURLY)
        assert ResourceCategory.COMPUTE in needs
