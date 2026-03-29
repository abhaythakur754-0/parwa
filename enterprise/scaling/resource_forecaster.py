"""
Resource Forecaster Module - Week 52, Builder 3
Resource forecasting engine for capacity planning
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import logging
import math
import statistics

logger = logging.getLogger(__name__)


class ForecastType(Enum):
    """Type of forecast"""
    POINT = "point"
    INTERVAL = "interval"
    DISTRIBUTION = "distribution"


class ForecastHorizon(Enum):
    """Forecast time horizon"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class ResourceCategory(Enum):
    """Resource category for forecasting"""
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    MEMORY = "memory"


@dataclass
class ResourceDataPoint:
    """Resource usage data point"""
    timestamp: datetime
    value: float
    category: ResourceCategory
    allocated: float = 0.0
    used: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ForecastPoint:
    """Single forecast point"""
    timestamp: datetime
    predicted_value: float
    lower_bound: float
    upper_bound: float
    confidence: float


@dataclass
class ResourceForecast:
    """Complete resource forecast"""
    category: ResourceCategory
    horizon: ForecastHorizon
    created_at: datetime = field(default_factory=datetime.utcnow)
    points: List[ForecastPoint] = field(default_factory=list)
    model_type: str = ""
    accuracy_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ForecastAlert:
    """Alert for forecast issues"""
    category: ResourceCategory
    alert_type: str
    timestamp: datetime
    message: str
    severity: str  # info, warning, critical
    predicted_value: float
    threshold: float


class HistoricalDataStore:
    """
    Stores and manages historical resource data.
    """

    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        self.data: Dict[ResourceCategory, List[ResourceDataPoint]] = {}

    def add(self, point: ResourceDataPoint) -> None:
        """Add a data point"""
        if point.category not in self.data:
            self.data[point.category] = []

        self.data[point.category].append(point)

        # Enforce max history
        if len(self.data[point.category]) > self.max_history:
            self.data[point.category] = self.data[point.category][-self.max_history:]

    def get_values(
        self,
        category: ResourceCategory,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[ResourceDataPoint]:
        """Get values for a time range"""
        points = self.data.get(category, [])

        if start:
            points = [p for p in points if p.timestamp >= start]
        if end:
            points = [p for p in points if p.timestamp <= end]

        return points

    def get_aggregated(
        self,
        category: ResourceCategory,
        aggregation: str = "avg",
        window_hours: int = 1,
    ) -> List[Tuple[datetime, float]]:
        """Get aggregated data by time window"""
        points = self.data.get(category, [])
        if not points:
            return []

        # Group by window
        window = timedelta(hours=window_hours)
        aggregated = []
        current_window_start = points[0].timestamp.replace(
            minute=0, second=0, microsecond=0
        )

        while current_window_start <= points[-1].timestamp:
            window_end = current_window_start + window
            window_points = [
                p for p in points
                if current_window_start <= p.timestamp < window_end
            ]

            if window_points:
                values = [p.value for p in window_points]
                if aggregation == "avg":
                    value = statistics.mean(values)
                elif aggregation == "max":
                    value = max(values)
                elif aggregation == "min":
                    value = min(values)
                elif aggregation == "sum":
                    value = sum(values)
                else:
                    value = statistics.mean(values)

                aggregated.append((current_window_start, value))

            current_window_start = window_end

        return aggregated


class ForecastModel:
    """
    Base forecasting model.
    """

    def __init__(self, name: str):
        self.name = name
        self._fitted = False

    def fit(self, values: List[float]) -> None:
        """Fit the model to data"""
        raise NotImplementedError

    def predict(self, steps: int) -> List[float]:
        """Predict future values"""
        raise NotImplementedError

    def get_confidence_interval(
        self,
        predicted: float,
        values: List[float],
    ) -> Tuple[float, float]:
        """Calculate confidence interval"""
        if not values:
            return (predicted * 0.8, predicted * 1.2)

        stdev = statistics.stdev(values) if len(values) >= 2 else predicted * 0.1
        return (predicted - 1.96 * stdev, predicted + 1.96 * stdev)


class LinearTrendModel(ForecastModel):
    """
    Linear trend forecasting model.
    """

    def __init__(self):
        super().__init__("linear_trend")
        self.slope = 0.0
        self.intercept = 0.0
        self._values: List[float] = []

    def fit(self, values: List[float]) -> None:
        """Fit linear model"""
        self._values = values
        if len(values) < 2:
            self.intercept = values[0] if values else 0
            self.slope = 0
            self._fitted = True
            return

        n = len(values)
        x = list(range(n))

        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(xi * yi for xi, yi in zip(x, values))
        sum_x2 = sum(xi * xi for xi in x)

        denom = n * sum_x2 - sum_x * sum_x
        if denom != 0:
            self.slope = (n * sum_xy - sum_x * sum_y) / denom
            self.intercept = (sum_y - self.slope * sum_x) / n
        else:
            self.intercept = statistics.mean(values)
            self.slope = 0

        self._fitted = True

    def predict(self, steps: int) -> List[float]:
        """Predict using linear trend"""
        if not self._fitted:
            return [0] * steps

        n = len(self._values)
        return [self.slope * (n + i) + self.intercept for i in range(steps)]


class SeasonalModel(ForecastModel):
    """
    Seasonal forecasting model.
    """

    def __init__(self, period: int = 24):
        super().__init__("seasonal")
        self.period = period
        self._seasonal_factors: List[float] = []
        self._trend_model = LinearTrendModel()
        self._values: List[float] = []

    def fit(self, values: List[float]) -> None:
        """Fit seasonal model"""
        self._values = values
        self._trend_model.fit(values)

        if len(values) < self.period:
            self._seasonal_factors = [1.0] * self.period
            self._fitted = True
            return

        # Calculate seasonal factors
        avg = statistics.mean(values)
        factors = []
        for i in range(self.period):
            seasonal_values = [values[j] for j in range(i, len(values), self.period)]
            if seasonal_values:
                factors.append(statistics.mean(seasonal_values) / avg if avg > 0 else 1.0)
            else:
                factors.append(1.0)

        self._seasonal_factors = factors
        self._fitted = True

    def predict(self, steps: int) -> List[float]:
        """Predict with seasonality"""
        if not self._fitted:
            return [0] * steps

        trend = self._trend_model.predict(steps)
        predictions = []

        n = len(self._values)
        for i, t in enumerate(trend):
            seasonal_idx = (n + i) % self.period
            factor = self._seasonal_factors[seasonal_idx] if self._seasonal_factors else 1.0
            predictions.append(t * factor)

        return predictions


class ExponentialSmoothingModel(ForecastModel):
    """
    Exponential smoothing forecasting model.
    """

    def __init__(self, alpha: float = 0.3, beta: float = 0.1):
        super().__init__("exponential_smoothing")
        self.alpha = alpha
        self.beta = beta
        self._level = 0.0
        self._trend = 0.0
        self._values: List[float] = []

    def fit(self, values: List[float]) -> None:
        """Fit exponential smoothing model"""
        self._values = values
        if not values:
            self._fitted = True
            return

        self._level = values[0]
        self._trend = values[1] - values[0] if len(values) > 1 else 0

        for value in values[1:]:
            prev_level = self._level
            self._level = self.alpha * value + (1 - self.alpha) * (self._level + self._trend)
            self._trend = self.beta * (self._level - prev_level) + (1 - self.beta) * self._trend

        self._fitted = True

    def predict(self, steps: int) -> List[float]:
        """Predict using exponential smoothing"""
        if not self._fitted:
            return [0] * steps

        return [self._level + self._trend * (i + 1) for i in range(steps)]


class ResourceForecaster:
    """
    Main resource forecasting engine.
    """

    def __init__(self):
        self.data_store = HistoricalDataStore()
        self.models: Dict[str, ForecastModel] = {
            "linear": LinearTrendModel(),
            "seasonal": SeasonalModel(),
            "exponential": ExponentialSmoothingModel(),
        }
        self.default_model = "exponential"
        self.alert_thresholds: Dict[ResourceCategory, float] = {}

    def set_alert_threshold(
        self,
        category: ResourceCategory,
        threshold: float,
    ) -> None:
        """Set alert threshold for a resource category"""
        self.alert_thresholds[category] = threshold

    def record(
        self,
        category: ResourceCategory,
        value: float,
        timestamp: Optional[datetime] = None,
        allocated: float = 0.0,
        used: float = 0.0,
    ) -> None:
        """Record resource usage"""
        point = ResourceDataPoint(
            timestamp=timestamp or datetime.utcnow(),
            value=value,
            category=category,
            allocated=allocated,
            used=used,
        )
        self.data_store.add(point)

    def forecast(
        self,
        category: ResourceCategory,
        horizon: ForecastHorizon,
        model_name: Optional[str] = None,
    ) -> ResourceForecast:
        """Generate resource forecast"""
        model_name = model_name or self.default_model
        model = self.models.get(model_name)

        if not model:
            model = self.models[self.default_model]

        # Get historical data
        points = self.data_store.get_values(category)
        if not points:
            return ResourceForecast(
                category=category,
                horizon=horizon,
                model_type=model_name,
            )

        values = [p.value for p in points]
        model.fit(values)

        # Determine number of steps based on horizon
        steps_map = {
            ForecastHorizon.HOURLY: 24,
            ForecastHorizon.DAILY: 7,
            ForecastHorizon.WEEKLY: 4,
            ForecastHorizon.MONTHLY: 12,
        }
        steps = steps_map[horizon]

        predictions = model.predict(steps)

        # Create forecast points
        forecast_points = []
        base_time = datetime.utcnow()

        interval_map = {
            ForecastHorizon.HOURLY: timedelta(hours=1),
            ForecastHorizon.DAILY: timedelta(days=1),
            ForecastHorizon.WEEKLY: timedelta(weeks=1),
            ForecastHorizon.MONTHLY: timedelta(days=30),
        }
        interval = interval_map[horizon]

        for i, pred in enumerate(predictions):
            lower, upper = model.get_confidence_interval(pred, values)
            confidence = max(0, 1 - (upper - lower) / (pred * 2 if pred else 1))

            forecast_points.append(ForecastPoint(
                timestamp=base_time + interval * (i + 1),
                predicted_value=max(0, pred),
                lower_bound=max(0, lower),
                upper_bound=max(0, upper),
                confidence=min(1.0, confidence),
            ))

        return ResourceForecast(
            category=category,
            horizon=horizon,
            points=forecast_points,
            model_type=model_name,
            accuracy_score=self._calculate_accuracy(model, values),
        )

    def _calculate_accuracy(
        self,
        model: ForecastModel,
        values: List[float],
    ) -> float:
        """Calculate model accuracy using backtesting"""
        if len(values) < 10:
            return 0.5

        # Use last 20% for testing
        split = int(len(values) * 0.8)
        train = values[:split]
        test = values[split:]

        model.fit(train)
        predictions = model.predict(len(test))

        # Calculate MAPE
        errors = []
        for actual, predicted in zip(test, predictions):
            if actual != 0:
                errors.append(abs(actual - predicted) / actual)

        if errors:
            mape = statistics.mean(errors)
            return max(0, 1 - mape)
        return 0.5

    def check_forecast_alerts(
        self,
        forecast: ResourceForecast,
    ) -> List[ForecastAlert]:
        """Check forecast for alert conditions"""
        alerts = []
        threshold = self.alert_thresholds.get(forecast.category)

        if threshold is None:
            return alerts

        for point in forecast.points:
            if point.predicted_value > threshold:
                severity = "critical" if point.predicted_value > threshold * 1.2 else "warning"
                alerts.append(ForecastAlert(
                    category=forecast.category,
                    alert_type="threshold_exceeded",
                    timestamp=point.timestamp,
                    message=f"Resource {forecast.category.value} predicted to exceed threshold",
                    severity=severity,
                    predicted_value=point.predicted_value,
                    threshold=threshold,
                ))

        return alerts

    def get_forecasting_summary(self) -> Dict[str, Any]:
        """Get summary of forecasting status"""
        summary = {
            "categories": {},
            "models_available": list(self.models.keys()),
            "default_model": self.default_model,
        }

        for category in ResourceCategory:
            points = self.data_store.get_values(category)
            if points:
                values = [p.value for p in points]
                summary["categories"][category.value] = {
                    "data_points": len(points),
                    "latest_value": values[-1],
                    "avg_value": statistics.mean(values),
                    "max_value": max(values),
                    "min_value": min(values),
                }

        return summary


class MultiResourceForecaster:
    """
    Forecaster for multiple resources simultaneously.
    """

    def __init__(self):
        self.forecaster = ResourceForecaster()

    def record_all(
        self,
        values: Dict[ResourceCategory, float],
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Record values for all resources"""
        for category, value in values.items():
            self.forecaster.record(category, value, timestamp)

    def forecast_all(
        self,
        horizon: ForecastHorizon,
    ) -> Dict[ResourceCategory, ResourceForecast]:
        """Generate forecasts for all resources"""
        forecasts = {}
        for category in ResourceCategory:
            forecast = self.forecaster.forecast(category, horizon)
            if forecast.points:
                forecasts[category] = forecast
        return forecasts

    def get_capacity_needs(
        self,
        horizon: ForecastHorizon,
        safety_margin: float = 0.2,
    ) -> Dict[ResourceCategory, float]:
        """Calculate capacity needs with safety margin"""
        forecasts = self.forecast_all(horizon)
        needs = {}

        for category, forecast in forecasts.items():
            if forecast.points:
                # Use maximum predicted value with safety margin
                max_predicted = max(p.predicted_value for p in forecast.points)
                needs[category] = max_predicted * (1 + safety_margin)

        return needs
