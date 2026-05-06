"""
Demand Predictor Module - Week 52, Builder 3
Demand prediction using ML-based forecasting
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import logging
import math
import statistics

logger = logging.getLogger(__name__)


class PredictionModel(Enum):
    """Prediction model type"""
    MOVING_AVERAGE = "moving_average"
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"
    LINEAR_REGRESSION = "linear_regression"
    ARIMA = "arima"
    SEASONAL = "seasonal"


class SeasonalityType(Enum):
    """Seasonality pattern type"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


@dataclass
class DemandDataPoint:
    """Single demand data point"""
    timestamp: datetime
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PredictionResult:
    """Result of a prediction"""
    predicted_value: float
    confidence_interval: Tuple[float, float]
    confidence: float
    model_used: PredictionModel
    timestamp: datetime = field(default_factory=datetime.utcnow)
    features_used: List[str] = field(default_factory=list)


@dataclass
class DemandPattern:
    """Identified demand pattern"""
    pattern_type: str
    period: int  # Period in hours
    amplitude: float
    peak_times: List[int]  # Hours of peak demand
    trough_times: List[int]  # Hours of low demand
    confidence: float


class TimeSeriesAnalyzer:
    """
    Analyzes time series data for patterns.
    """

    def __init__(self):
        self.data: List[DemandDataPoint] = []

    def add_data(
        self,
        timestamp: datetime,
        value: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a data point"""
        point = DemandDataPoint(
            timestamp=timestamp,
            value=value,
            metadata=metadata or {},
        )
        self.data.append(point)
        # Keep sorted by timestamp
        self.data.sort(key=lambda x: x.timestamp)

    def get_values(self, window: Optional[int] = None) -> List[float]:
        """Get values as list"""
        if window:
            return [d.value for d in self.data[-window:]]
        return [d.value for d in self.data]

    def detect_seasonality(self) -> List[DemandPattern]:
        """Detect seasonal patterns in the data"""
        patterns = []

        if len(self.data) < 24:
            return patterns

        values = self.get_values()

        # Check for hourly pattern
        hourly_pattern = self._detect_periodic_pattern(values, 24)
        if hourly_pattern:
            patterns.append(DemandPattern(
                pattern_type="hourly",
                period=1,
                amplitude=hourly_pattern["amplitude"],
                peak_times=hourly_pattern["peaks"],
                trough_times=hourly_pattern["troughs"],
                confidence=hourly_pattern["confidence"],
            ))

        # Check for daily pattern
        if len(values) >= 168:  # 7 days of hourly data
            daily_pattern = self._detect_periodic_pattern(values, 24)
            if daily_pattern:
                patterns.append(DemandPattern(
                    pattern_type="daily",
                    period=24,
                    amplitude=daily_pattern["amplitude"],
                    peak_times=daily_pattern["peaks"],
                    trough_times=daily_pattern["troughs"],
                    confidence=daily_pattern["confidence"],
                ))

        # Check for weekly pattern
        if len(values) >= 672:  # 4 weeks of hourly data
            weekly_pattern = self._detect_periodic_pattern(values, 168)
            if weekly_pattern:
                patterns.append(DemandPattern(
                    pattern_type="weekly",
                    period=168,
                    amplitude=weekly_pattern["amplitude"],
                    peak_times=weekly_pattern["peaks"],
                    trough_times=weekly_pattern["troughs"],
                    confidence=weekly_pattern["confidence"],
                ))

        return patterns

    def _detect_periodic_pattern(
        self,
        values: List[float],
        period: int,
    ) -> Optional[Dict[str, Any]]:
        """Detect a pattern with specific period"""
        if len(values) < period * 2:
            return None

        # Group by period position
        groups = [[] for _ in range(period)]
        for i, value in enumerate(values):
            groups[i % period].append(value)

        # Calculate average for each position
        averages = [statistics.mean(g) if g else 0 for g in groups]

        # Find peaks and troughs
        avg_value = statistics.mean(averages)
        peaks = [i for i, a in enumerate(averages) if a > avg_value * 1.2]
        troughs = [i for i, a in enumerate(averages) if a < avg_value * 0.8]

        # Calculate amplitude
        amplitude = (max(averages) - min(averages)) / 2 if averages else 0

        # Calculate confidence based on consistency
        if len(peaks) > 0 and len(troughs) > 0:
            confidence = min(1.0, amplitude / avg_value * 2) if avg_value > 0 else 0
        else:
            confidence = 0

        return {
            "amplitude": amplitude,
            "peaks": peaks,
            "troughs": troughs,
            "confidence": confidence,
        }

    def calculate_trend(self) -> str:
        """Calculate overall trend direction"""
        if len(self.data) < 10:
            return "unknown"

        values = self.get_values()
        n = len(values)

        # Simple linear regression
        x = list(range(n))
        y = values

        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi * xi for xi in x)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)

        if slope > 0.01 * statistics.mean(values):
            return "increasing"
        elif slope < -0.01 * statistics.mean(values):
            return "decreasing"
        return "stable"


class MovingAveragePredictor:
    """
    Simple moving average predictor.
    """

    def __init__(self, window: int = 10):
        self.window = window

    def predict(self, values: List[float]) -> PredictionResult:
        """Predict next value using moving average"""
        if len(values) < self.window:
            avg = statistics.mean(values) if values else 0
        else:
            avg = statistics.mean(values[-self.window:])

        # Calculate confidence interval
        if len(values) >= 2:
            stdev = statistics.stdev(values[-self.window:]) if len(values) >= self.window else statistics.stdev(values)
            ci = (avg - 1.96 * stdev, avg + 1.96 * stdev)
        else:
            ci = (avg * 0.8, avg * 1.2)

        return PredictionResult(
            predicted_value=avg,
            confidence_interval=ci,
            confidence=0.6 if len(values) >= self.window else 0.3,
            model_used=PredictionModel.MOVING_AVERAGE,
        )


class ExponentialSmoothingPredictor:
    """
    Exponential smoothing predictor.
    """

    def __init__(self, alpha: float = 0.3):
        self.alpha = alpha
        self._smoothed_value: Optional[float] = None

    def predict(self, values: List[float]) -> PredictionResult:
        """Predict next value using exponential smoothing"""
        if not values:
            return PredictionResult(
                predicted_value=0,
                confidence_interval=(0, 0),
                confidence=0,
                model_used=PredictionModel.EXPONENTIAL_SMOOTHING,
            )

        # Calculate smoothed value
        smoothed = values[0]
        for value in values[1:]:
            smoothed = self.alpha * value + (1 - self.alpha) * smoothed

        self._smoothed_value = smoothed

        # Calculate confidence interval
        errors = []
        prev_smoothed = values[0]
        for value in values[1:]:
            pred = self.alpha * prev_smoothed + (1 - self.alpha) * prev_smoothed
            errors.append(abs(value - pred))
            prev_smoothed = self.alpha * value + (1 - self.alpha) * prev_smoothed

        if errors:
            mean_error = statistics.mean(errors)
            ci = (smoothed - mean_error * 1.5, smoothed + mean_error * 1.5)
        else:
            ci = (smoothed * 0.8, smoothed * 1.2)

        return PredictionResult(
            predicted_value=smoothed,
            confidence_interval=ci,
            confidence=0.7,
            model_used=PredictionModel.EXPONENTIAL_SMOOTHING,
        )


class LinearRegressionPredictor:
    """
    Linear regression predictor.
    """

    def predict(self, values: List[float]) -> PredictionResult:
        """Predict next value using linear regression"""
        if len(values) < 2:
            avg = values[0] if values else 0
            return PredictionResult(
                predicted_value=avg,
                confidence_interval=(avg * 0.5, avg * 1.5),
                confidence=0.3,
                model_used=PredictionModel.LINEAR_REGRESSION,
            )

        n = len(values)
        x = list(range(n))
        y = values

        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi * xi for xi in x)

        denom = n * sum_x2 - sum_x * sum_x
        if denom == 0:
            slope = 0
            intercept = statistics.mean(values)
        else:
            slope = (n * sum_xy - sum_x * sum_y) / denom
            intercept = (sum_y - slope * sum_x) / n

        # Predict next value
        predicted = slope * n + intercept

        # Calculate residuals for confidence interval
        predictions = [slope * i + intercept for i in range(n)]
        residuals = [abs(y[i] - predictions[i]) for i in range(n)]
        mean_residual = statistics.mean(residuals) if residuals else 0

        ci = (predicted - mean_residual * 2, predicted + mean_residual * 2)

        return PredictionResult(
            predicted_value=predicted,
            confidence_interval=ci,
            confidence=0.75,
            model_used=PredictionModel.LINEAR_REGRESSION,
        )


class SeasonalPredictor:
    """
    Seasonal pattern predictor.
    """

    def __init__(self, period: int = 24):
        self.period = period
        self._seasonal_factors: List[float] = []

    def fit(self, values: List[float]) -> None:
        """Fit seasonal factors from historical data"""
        if len(values) < self.period:
            self._seasonal_factors = [1.0] * self.period
            return

        # Calculate average
        avg = statistics.mean(values)

        # Calculate seasonal factors
        factors = []
        for i in range(self.period):
            seasonal_values = [values[j] for j in range(i, len(values), self.period)]
            if seasonal_values:
                factors.append(statistics.mean(seasonal_values) / avg if avg > 0 else 1.0)
            else:
                factors.append(1.0)

        self._seasonal_factors = factors

    def predict(self, values: List[float], steps_ahead: int = 1) -> PredictionResult:
        """Predict next value using seasonal pattern"""
        if not self._seasonal_factors:
            self.fit(values)

        # Get base trend (using linear regression)
        if len(values) >= 2:
            n = len(values)
            x = list(range(n))
            y = values
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(xi * yi for xi, yi in zip(x, y))
            sum_x2 = sum(xi * xi for xi in x)

            denom = n * sum_x2 - sum_x * sum_x
            if denom != 0:
                slope = (n * sum_xy - sum_x * sum_y) / denom
                intercept = (sum_y - slope * sum_x) / n
            else:
                slope = 0
                intercept = statistics.mean(values)

            base_value = slope * (n + steps_ahead - 1) + intercept
        else:
            base_value = statistics.mean(values) if values else 0

        # Apply seasonal factor
        seasonal_idx = (len(values) + steps_ahead - 1) % self.period
        seasonal_factor = self._seasonal_factors[seasonal_idx] if self._seasonal_factors else 1.0

        predicted = base_value * seasonal_factor

        return PredictionResult(
            predicted_value=predicted,
            confidence_interval=(predicted * 0.85, predicted * 1.15),
            confidence=0.8,
            model_used=PredictionModel.SEASONAL,
        )


class DemandPredictor:
    """
    Main demand prediction engine.
    """

    def __init__(self, default_model: PredictionModel = PredictionModel.EXPONENTIAL_SMOOTHING):
        self.default_model = default_model
        self.analyzer = TimeSeriesAnalyzer()
        self._predictors = {
            PredictionModel.MOVING_AVERAGE: MovingAveragePredictor(),
            PredictionModel.EXPONENTIAL_SMOOTHING: ExponentialSmoothingPredictor(),
            PredictionModel.LINEAR_REGRESSION: LinearRegressionPredictor(),
            PredictionModel.SEASONAL: SeasonalPredictor(),
        }

    def add_data(
        self,
        timestamp: datetime,
        value: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add demand data point"""
        self.analyzer.add_data(timestamp, value, metadata)

    def add_batch(self, data: List[Tuple[datetime, float]]) -> None:
        """Add multiple data points"""
        for timestamp, value in data:
            self.add_data(timestamp, value)

    def predict(
        self,
        model: Optional[PredictionModel] = None,
        steps_ahead: int = 1,
    ) -> PredictionResult:
        """Make a prediction"""
        model = model or self.default_model
        values = self.analyzer.get_values()

        if model == PredictionModel.SEASONAL:
            predictor = self._predictors[model]
            return predictor.predict(values, steps_ahead)
        else:
            predictor = self._predictors.get(model)
            if predictor:
                return predictor.predict(values)

        # Fallback to moving average
        return self._predictors[PredictionModel.MOVING_AVERAGE].predict(values)

    def predict_range(
        self,
        steps: int,
        model: Optional[PredictionModel] = None,
    ) -> List[PredictionResult]:
        """Predict multiple steps ahead"""
        predictions = []
        values = self.analyzer.get_values()

        for i in range(1, steps + 1):
            pred = self.predict(model, steps_ahead=i)
            predictions.append(pred)

        return predictions

    def detect_patterns(self) -> List[DemandPattern]:
        """Detect demand patterns"""
        return self.analyzer.detect_seasonality()

    def get_trend(self) -> str:
        """Get current trend"""
        return self.analyzer.calculate_trend()

    def get_forecast_summary(self, hours_ahead: int = 24) -> Dict[str, Any]:
        """Get summary forecast"""
        predictions = self.predict_range(hours_ahead)
        values = [p.predicted_value for p in predictions]

        return {
            "trend": self.get_trend(),
            "patterns": [p.pattern_type for p in self.detect_patterns()],
            "predictions": {
                "min": min(values) if values else 0,
                "max": max(values) if values else 0,
                "avg": statistics.mean(values) if values else 0,
                "confidence": statistics.mean([p.confidence for p in predictions]),
            },
            "data_points": len(self.analyzer.data),
        }
