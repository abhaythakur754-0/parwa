"""
Enterprise Analytics - Trend Analyzer
Analyze trends in enterprise support metrics
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class TrendDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


class TrendResult(BaseModel):
    """Trend analysis result"""
    metric_name: str
    direction: TrendDirection
    change_percent: float
    confidence: float
    prediction: Optional[float] = None

    model_config = ConfigDict()


class TrendAnalyzer:
    """
    Analyze trends in enterprise support metrics.
    """

    def __init__(self, client_id: str):
        self.client_id = client_id

    def analyze_trend(
        self,
        metric_name: str,
        historical_data: List[float]
    ) -> TrendResult:
        """Analyze trend for a metric"""
        if len(historical_data) < 2:
            return TrendResult(
                metric_name=metric_name,
                direction=TrendDirection.STABLE,
                change_percent=0.0,
                confidence=0.0
            )

        # Calculate change
        first_value = historical_data[0]
        last_value = historical_data[-1]
        change = ((last_value - first_value) / first_value) * 100 if first_value != 0 else 0

        # Determine direction
        if change > 5:
            direction = TrendDirection.UP
        elif change < -5:
            direction = TrendDirection.DOWN
        else:
            direction = TrendDirection.STABLE

        # Calculate confidence based on data consistency
        confidence = min(1.0, len(historical_data) / 30.0)

        # Predict next value (simple linear extrapolation)
        avg_change = (last_value - historical_data[-2]) if len(historical_data) > 1 else 0
        prediction = last_value + avg_change

        return TrendResult(
            metric_name=metric_name,
            direction=direction,
            change_percent=round(change, 2),
            confidence=round(confidence, 2),
            prediction=round(prediction, 2)
        )

    def analyze_all(
        self,
        metrics_data: Dict[str, List[float]]
    ) -> Dict[str, TrendResult]:
        """Analyze all metrics"""
        results = {}
        for metric_name, data in metrics_data.items():
            results[metric_name] = self.analyze_trend(metric_name, data)
        return results

    def get_forecast(
        self,
        metric_name: str,
        historical_data: List[float],
        periods: int = 7
    ) -> List[float]:
        """Get forecast for next periods"""
        if len(historical_data) < 2:
            return [historical_data[-1]] * periods if historical_data else []

        # Simple moving average forecast
        avg_change = sum(
            historical_data[i] - historical_data[i-1]
            for i in range(1, len(historical_data))
        ) / (len(historical_data) - 1)

        last_value = historical_data[-1]
        forecast = []
        for i in range(periods):
            forecast.append(last_value + avg_change * (i + 1))

        return forecast
