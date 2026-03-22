"""
PARWA High Analytics Engine.

Advanced analytics engine for PARWA High variant providing:
- Insights generation from customer data
- Trend calculation and forecasting
- Anomaly detection
- Report generation

PARWA High Features:
- Heavy AI tier for sophisticated analysis
- Company-isolated data processing
- No PHI in analytics (security requirement)
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from uuid import UUID
from dataclasses import dataclass, field
import statistics

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Insight:
    """Represents an analytics insight."""
    insight_id: str
    category: str
    title: str
    description: str
    impact_score: float  # 0.0 to 1.0
    data_points: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Trend:
    """Represents a calculated trend."""
    metric_name: str
    direction: str  # "up", "down", "stable"
    change_percent: float
    confidence: float
    period: str
    data_points: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Anomaly:
    """Represents a detected anomaly."""
    anomaly_id: str
    metric: str
    expected_value: float
    actual_value: float
    deviation_score: float  # Standard deviations from mean
    severity: str  # "low", "medium", "high"
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AnalyticsEngine:
    """
    Advanced analytics engine for PARWA High variant.

    Provides comprehensive analytics capabilities:
    - Generate insights from customer and operational data
    - Calculate trends and forecasts
    - Identify anomalies in metrics
    - Generate detailed reports

    Security Requirements:
    - No PHI in analytics data
    - Company-isolated processing
    - Audit logging for all operations

    Example:
        engine = AnalyticsEngine(company_id=uuid)
        insights = await engine.generate_insights(customer_data)
        trends = await engine.calculate_trends(historical_data)
    """

    def __init__(
        self,
        company_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize Analytics Engine.

        Args:
            company_id: Company UUID for data isolation
        """
        self._company_id = company_id
        self._insights: Dict[str, Insight] = {}
        self._trends: Dict[str, Trend] = {}
        self._anomalies: Dict[str, Anomaly] = {}

        logger.info({
            "event": "analytics_engine_initialized",
            "company_id": str(company_id) if company_id else None,
            "variant": "parwa_high",
            "tier": "heavy",
        })

    async def generate_insights(
        self,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate insights from customer and operational data.

        Analyzes data to identify patterns, correlations, and
        actionable insights for business improvement.

        CRITICAL: No PHI data is processed in analytics.

        Args:
            data: Dict with:
                - customer_metrics: Customer-related metrics
                - operational_metrics: Operational data
                - time_period: Analysis period
                - previous_period: Optional comparison data

        Returns:
            Dict with:
                - insights: List of generated insights
                - summary: Overall summary
                - recommendations: Actionable recommendations
        """
        start_time = datetime.now(timezone.utc)

        customer_metrics = data.get("customer_metrics", {})
        operational_metrics = data.get("operational_metrics", {})
        time_period = data.get("time_period", "30d")

        insights: List[Insight] = []

        # Generate customer satisfaction insights
        if customer_metrics:
            csat_insight = self._analyze_csat(customer_metrics, time_period)
            if csat_insight:
                insights.append(csat_insight)

        # Generate resolution time insights
        if operational_metrics:
            resolution_insight = self._analyze_resolution_time(
                operational_metrics, time_period
            )
            if resolution_insight:
                insights.append(resolution_insight)

        # Generate volume insights
        volume_insight = self._analyze_volume(data, time_period)
        if volume_insight:
            insights.append(volume_insight)

        # Store insights
        for insight in insights:
            self._insights[insight.insight_id] = insight

        # Generate recommendations
        recommendations = self._generate_recommendations(insights)

        execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        logger.info({
            "event": "insights_generated",
            "company_id": str(self._company_id) if self._company_id else None,
            "insight_count": len(insights),
            "time_period": time_period,
            "execution_time_ms": execution_time,
        })

        return {
            "success": True,
            "insights": [
                {
                    "insight_id": i.insight_id,
                    "category": i.category,
                    "title": i.title,
                    "description": i.description,
                    "impact_score": i.impact_score,
                    "recommendations": i.recommendations,
                }
                for i in insights
            ],
            "summary": f"Generated {len(insights)} insights for period {time_period}",
            "recommendations": recommendations,
            "metadata": {
                "variant": "parwa_high",
                "tier": "heavy",
                "time_period": time_period,
                "execution_time_ms": execution_time,
            },
        }

    async def calculate_trends(
        self,
        historical_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate trends from historical data.

        Analyzes time-series data to identify trends,
        calculate change percentages, and forecast direction.

        Args:
            historical_data: List of data points with:
                - timestamp: ISO timestamp
                - metric_name: Name of the metric
                - value: Metric value

        Returns:
            Dict with:
                - trends: List of calculated trends
                - forecast: Short-term forecast
                - confidence: Overall confidence score
        """
        if not historical_data or len(historical_data) < 2:
            return {
                "success": False,
                "trends": [],
                "message": "Insufficient data for trend calculation",
            }

        trends: List[Trend] = []

        # Group data by metric
        metric_data: Dict[str, List[Dict[str, Any]]] = {}
        for point in historical_data:
            metric_name = point.get("metric_name", "unknown")
            if metric_name not in metric_data:
                metric_data[metric_name] = []
            metric_data[metric_name].append(point)

        # Calculate trend for each metric
        for metric_name, points in metric_data.items():
            if len(points) >= 2:
                trend = self._calculate_single_trend(metric_name, points)
                if trend:
                    trends.append(trend)
                    self._trends[f"{metric_name}_{datetime.now(timezone.utc).isoformat()}"] = trend

        # Calculate overall confidence
        confidence = self._calculate_trend_confidence(trends)

        logger.info({
            "event": "trends_calculated",
            "company_id": str(self._company_id) if self._company_id else None,
            "trend_count": len(trends),
            "confidence": confidence,
        })

        return {
            "success": True,
            "trends": [
                {
                    "metric_name": t.metric_name,
                    "direction": t.direction,
                    "change_percent": t.change_percent,
                    "confidence": t.confidence,
                    "period": t.period,
                }
                for t in trends
            ],
            "forecast": self._generate_forecast(trends),
            "confidence": confidence,
            "metadata": {
                "variant": "parwa_high",
                "tier": "heavy",
            },
        }

    async def identify_anomalies(
        self,
        data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Identify anomalies in metric data.

        Uses statistical methods to detect outliers and
        unusual patterns in the data.

        Args:
            data: List of metric data points

        Returns:
            List of detected anomalies with severity levels
        """
        if not data or len(data) < 5:
            return []

        anomalies: List[Anomaly] = []

        # Group by metric
        metric_values: Dict[str, List[float]] = {}
        metric_points: Dict[str, List[Dict[str, Any]]] = {}

        for point in data:
            metric_name = point.get("metric_name", "unknown")
            value = float(point.get("value", 0))

            if metric_name not in metric_values:
                metric_values[metric_name] = []
                metric_points[metric_name] = []

            metric_values[metric_name].append(value)
            metric_points[metric_name].append(point)

        # Detect anomalies using statistical methods
        for metric_name, values in metric_values.items():
            if len(values) >= 5:
                detected = self._detect_anomalies_for_metric(
                    metric_name, values, metric_points[metric_name]
                )
                anomalies.extend(detected)

        # Store anomalies
        for anomaly in anomalies:
            self._anomalies[anomaly.anomaly_id] = anomaly

        logger.info({
            "event": "anomalies_identified",
            "company_id": str(self._company_id) if self._company_id else None,
            "anomaly_count": len(anomalies),
            "high_severity_count": sum(1 for a in anomalies if a.severity == "high"),
        })

        return [
            {
                "anomaly_id": a.anomaly_id,
                "metric": a.metric,
                "expected_value": a.expected_value,
                "actual_value": a.actual_value,
                "deviation_score": a.deviation_score,
                "severity": a.severity,
                "detected_at": a.detected_at,
            }
            for a in anomalies
        ]

    async def generate_report(
        self,
        company_id: str,
        period: str
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive analytics report.

        Creates a detailed report combining insights, trends,
        and anomalies for the specified period.

        Args:
            company_id: Company identifier
            period: Report period (e.g., "7d", "30d", "90d")

        Returns:
            Dict with complete report data
        """
        report_id = f"report_{company_id}_{period}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        # Gather all analytics data
        relevant_insights = [
            i for i in self._insights.values()
            if period in i.description or i.category
        ]

        relevant_trends = list(self._trends.values())[-10:]  # Last 10 trends
        relevant_anomalies = list(self._anomalies.values())[-10:]  # Last 10 anomalies

        # Generate report summary
        summary = self._generate_report_summary(
            relevant_insights, relevant_trends, relevant_anomalies, period
        )

        logger.info({
            "event": "report_generated",
            "report_id": report_id,
            "company_id": company_id,
            "period": period,
            "insight_count": len(relevant_insights),
            "trend_count": len(relevant_trends),
            "anomaly_count": len(relevant_anomalies),
        })

        return {
            "success": True,
            "report_id": report_id,
            "company_id": company_id,
            "period": period,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "insights": [
                {
                    "insight_id": i.insight_id,
                    "category": i.category,
                    "title": i.title,
                    "description": i.description,
                    "impact_score": i.impact_score,
                }
                for i in relevant_insights
            ],
            "trends": [
                {
                    "metric_name": t.metric_name,
                    "direction": t.direction,
                    "change_percent": t.change_percent,
                }
                for t in relevant_trends
            ],
            "anomalies": [
                {
                    "metric": a.metric,
                    "severity": a.severity,
                    "actual_value": a.actual_value,
                }
                for a in relevant_anomalies
            ],
            "metadata": {
                "variant": "parwa_high",
                "tier": "heavy",
            },
        }

    def _analyze_csat(
        self,
        customer_metrics: Dict[str, Any],
        time_period: str
    ) -> Optional[Insight]:
        """Analyze customer satisfaction metrics."""
        csat_score = customer_metrics.get("csat_score", 0)
        nps_score = customer_metrics.get("nps_score", 0)
        feedback_count = customer_metrics.get("feedback_count", 0)

        if csat_score == 0 and nps_score == 0:
            return None

        impact_score = 0.5
        recommendations: List[str] = []

        if csat_score >= 4.5:
            title = "Excellent Customer Satisfaction"
            description = f"CSAT score of {csat_score:.1f} indicates high customer satisfaction"
            impact_score = 0.8
        elif csat_score >= 3.5:
            title = "Good Customer Satisfaction"
            description = f"CSAT score of {csat_score:.1f} shows solid performance"
            recommendations.append("Monitor feedback for improvement opportunities")
        else:
            title = "Customer Satisfaction Needs Attention"
            description = f"CSAT score of {csat_score:.1f} below target threshold"
            impact_score = 0.9
            recommendations.append("Investigate root causes of low satisfaction")
            recommendations.append("Implement customer feedback improvements")

        insight_id = f"insight_csat_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        return Insight(
            insight_id=insight_id,
            category="customer_satisfaction",
            title=title,
            description=description,
            impact_score=impact_score,
            data_points={
                "csat_score": csat_score,
                "nps_score": nps_score,
                "feedback_count": feedback_count,
            },
            recommendations=recommendations,
        )

    def _analyze_resolution_time(
        self,
        operational_metrics: Dict[str, Any],
        time_period: str
    ) -> Optional[Insight]:
        """Analyze resolution time metrics."""
        avg_resolution_time = operational_metrics.get("avg_resolution_time_minutes", 0)
        target_time = operational_metrics.get("target_time_minutes", 30)
        resolution_count = operational_metrics.get("resolution_count", 0)

        if avg_resolution_time == 0:
            return None

        impact_score = 0.5
        recommendations: List[str] = []

        if avg_resolution_time <= target_time:
            title = "Resolution Time On Target"
            description = f"Average resolution time of {avg_resolution_time:.1f} min meets target"
            impact_score = 0.7
        else:
            title = "Resolution Time Above Target"
            description = f"Average resolution time of {avg_resolution_time:.1f} min exceeds target of {target_time} min"
            impact_score = 0.8
            recommendations.append("Review escalation procedures")
            recommendations.append("Consider additional agent training")

        insight_id = f"insight_resolution_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        return Insight(
            insight_id=insight_id,
            category="operational_efficiency",
            title=title,
            description=description,
            impact_score=impact_score,
            data_points={
                "avg_resolution_time_minutes": avg_resolution_time,
                "target_time_minutes": target_time,
                "resolution_count": resolution_count,
            },
            recommendations=recommendations,
        )

    def _analyze_volume(
        self,
        data: Dict[str, Any],
        time_period: str
    ) -> Optional[Insight]:
        """Analyze ticket/contact volume."""
        customer_metrics = data.get("customer_metrics", {})
        operational_metrics = data.get("operational_metrics", {})

        ticket_count = operational_metrics.get("ticket_count", 0)
        previous_count = data.get("previous_period", {}).get("ticket_count", ticket_count)

        if ticket_count == 0:
            return None

        change = 0.0
        if previous_count > 0:
            change = ((ticket_count - previous_count) / previous_count) * 100

        impact_score = 0.5
        recommendations: List[str] = []

        if change > 20:
            title = "Significant Volume Increase"
            description = f"Ticket volume increased {change:.1f}% compared to previous period"
            impact_score = 0.85
            recommendations.append("Review staffing levels")
            recommendations.append("Monitor for capacity constraints")
        elif change < -20:
            title = "Volume Decrease"
            description = f"Ticket volume decreased {abs(change):.1f}% compared to previous period"
            impact_score = 0.6
            recommendations.append("Verify tracking systems")
        else:
            title = "Stable Volume"
            description = f"Ticket volume stable with {change:.1f}% change"

        insight_id = f"insight_volume_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        return Insight(
            insight_id=insight_id,
            category="volume_analysis",
            title=title,
            description=description,
            impact_score=impact_score,
            data_points={
                "ticket_count": ticket_count,
                "previous_count": previous_count,
                "change_percent": change,
            },
            recommendations=recommendations,
        )

    def _generate_recommendations(
        self,
        insights: List[Insight]
    ) -> List[str]:
        """Generate overall recommendations from insights."""
        all_recommendations: List[str] = []

        # Collect all recommendations
        for insight in insights:
            all_recommendations.extend(insight.recommendations)

        # Prioritize by impact score
        high_impact_insights = [i for i in insights if i.impact_score >= 0.8]
        for insight in high_impact_insights:
            all_recommendations.insert(0, f"Priority: {insight.title}")

        # Remove duplicates while preserving order
        seen = set()
        unique_recommendations = []
        for rec in all_recommendations:
            if rec not in seen:
                seen.add(rec)
                unique_recommendations.append(rec)

        return unique_recommendations[:10]  # Top 10 recommendations

    def _calculate_single_trend(
        self,
        metric_name: str,
        points: List[Dict[str, Any]]
    ) -> Optional[Trend]:
        """Calculate trend for a single metric."""
        if len(points) < 2:
            return None

        # Sort by timestamp
        sorted_points = sorted(
            points,
            key=lambda x: x.get("timestamp", "")
        )

        values = [float(p.get("value", 0)) for p in sorted_points]

        if len(values) < 2:
            return None

        first_value = values[0]
        last_value = values[-1]

        if first_value == 0:
            return None

        change_percent = ((last_value - first_value) / first_value) * 100

        if change_percent > 5:
            direction = "up"
        elif change_percent < -5:
            direction = "down"
        else:
            direction = "stable"

        # Calculate confidence based on data consistency
        confidence = 0.7
        if len(values) >= 5:
            try:
                std_dev = statistics.stdev(values)
                mean_val = statistics.mean(values)
                if mean_val != 0:
                    cv = std_dev / abs(mean_val)  # Coefficient of variation
                    confidence = max(0.5, min(0.95, 1.0 - cv))
            except statistics.StatisticsError:
                pass

        return Trend(
            metric_name=metric_name,
            direction=direction,
            change_percent=change_percent,
            confidence=confidence,
            period="analyzed_period",
            data_points=sorted_points,
        )

    def _calculate_trend_confidence(
        self,
        trends: List[Trend]
    ) -> float:
        """Calculate overall confidence in trend analysis."""
        if not trends:
            return 0.0

        confidences = [t.confidence for t in trends]
        return statistics.mean(confidences)

    def _generate_forecast(
        self,
        trends: List[Trend]
    ) -> Dict[str, Any]:
        """Generate short-term forecast from trends."""
        if not trends:
            return {"available": False}

        # Simple forecast based on trend directions
        up_trends = sum(1 for t in trends if t.direction == "up")
        down_trends = sum(1 for t in trends if t.direction == "down")

        if up_trends > down_trends:
            overall_direction = "improving"
        elif down_trends > up_trends:
            overall_direction = "declining"
        else:
            overall_direction = "stable"

        return {
            "available": True,
            "overall_direction": overall_direction,
            "up_trend_count": up_trends,
            "down_trend_count": down_trends,
            "stable_trend_count": len(trends) - up_trends - down_trends,
            "forecast_period": "7d",
        }

    def _detect_anomalies_for_metric(
        self,
        metric_name: str,
        values: List[float],
        points: List[Dict[str, Any]]
    ) -> List[Anomaly]:
        """Detect anomalies for a single metric."""
        anomalies: List[Anomaly] = []

        try:
            mean_val = statistics.mean(values)
            std_dev = statistics.stdev(values)

            if std_dev == 0:
                return []

            # Use 2 standard deviations as threshold
            threshold = 2.0

            for i, value in enumerate(values):
                z_score = abs(value - mean_val) / std_dev

                if z_score > threshold:
                    # Determine severity
                    if z_score > 3.0:
                        severity = "high"
                    elif z_score > 2.5:
                        severity = "medium"
                    else:
                        severity = "low"

                    anomaly_id = f"anomaly_{metric_name}_{i}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

                    anomalies.append(Anomaly(
                        anomaly_id=anomaly_id,
                        metric=metric_name,
                        expected_value=mean_val,
                        actual_value=value,
                        deviation_score=z_score,
                        severity=severity,
                    ))
        except statistics.StatisticsError:
            pass

        return anomalies

    def _generate_report_summary(
        self,
        insights: List[Insight],
        trends: List[Trend],
        anomalies: List[Anomaly],
        period: str
    ) -> str:
        """Generate executive summary for report."""
        parts = []

        parts.append(f"Analytics Report for period: {period}")
        parts.append(f"Generated {len(insights)} insights, {len(trends)} trends, and detected {len(anomalies)} anomalies.")

        # High impact insights
        high_impact = [i for i in insights if i.impact_score >= 0.8]
        if high_impact:
            parts.append(f"Key insights requiring attention: {', '.join(i.title for i in high_impact[:3])}")

        # Trend summary
        up_trends = sum(1 for t in trends if t.direction == "up")
        down_trends = sum(1 for t in trends if t.direction == "down")
        if trends:
            parts.append(f"Trend analysis: {up_trends} improving, {down_trends} declining metrics.")

        # Anomaly summary
        high_severity = [a for a in anomalies if a.severity == "high"]
        if high_severity:
            parts.append(f"Warning: {len(high_severity)} high-severity anomalies detected.")

        return " ".join(parts)

    def get_variant(self) -> str:
        """Get variant name."""
        return "parwa_high"

    def get_tier(self) -> str:
        """Get AI tier used."""
        return "heavy"
