"""
PARWA High Generate Insights Task.

Task for generating analytics insights in PARWA High.
Provides insight generation, trend analysis, and risk scoring.
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone

from variants.parwa_high.agents.analytics_agent import ParwaHighAnalyticsAgent
from variants.parwa_high.config import ParwaHighConfig, get_parwa_high_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


@dataclass
class InsightResult:
    """Individual insight result."""
    insight_type: str
    title: str
    description: str
    confidence: float
    recommendations: List[str] = field(default_factory=list)


@dataclass
class GenerateInsightsResult:
    """Result from generate insights task."""
    success: bool
    insights: List[InsightResult] = field(default_factory=list)
    risk_score: float = 0.0
    trends: Dict[str, Any] = field(default_factory=dict)
    company_id: str = ""
    period: str = ""
    message: str = ""
    generated_at: str = ""


class GenerateInsightsTask:
    """
    Task for generating analytics insights.

    CRITICAL: Returns {insights, risk_score, trends}

    Uses ParwaHighAnalyticsAgent to:
    - Generate insights from data
    - Calculate risk scores
    - Identify trends

    Example:
        task = GenerateInsightsTask()
        result = await task.execute("company_123", "last_30_days")
    """

    def __init__(
        self,
        parwa_high_config: Optional[ParwaHighConfig] = None,
        agent_id: str = "generate_insights_task"
    ) -> None:
        """
        Initialize generate insights task.

        Args:
            parwa_high_config: PARWA High configuration
            agent_id: Agent identifier
        """
        self._config = parwa_high_config or get_parwa_high_config()
        self._agent = ParwaHighAnalyticsAgent(agent_id=agent_id)

    async def execute(
        self,
        company_id: str,
        period: str = "last_30_days"
    ) -> GenerateInsightsResult:
        """
        Execute insight generation.

        CRITICAL: Returns {insights, risk_score, trends}

        Args:
            company_id: Company identifier
            period: Time period for analysis

        Returns:
            GenerateInsightsResult with insights and risk score
        """
        logger.info({
            "event": "generate_insights_task_started",
            "company_id": company_id,
            "period": period,
            "variant": "parwa_high",
        })

        # Get metrics for the company
        metrics_response = await self._agent.get_metrics(company_id=company_id)

        # Generate insights from metrics data
        data = {
            "data_type": "general",
            "period": period,
            "metrics": list(metrics_response.data.get("metrics", {}).keys()) if metrics_response.success else [],
        }
        insights_response = await self._agent.generate_insights(data=data)

        if not insights_response.success:
            return GenerateInsightsResult(
                success=False,
                company_id=company_id,
                period=period,
                message=insights_response.message,
                generated_at=datetime.now(timezone.utc).isoformat(),
            )

        # Parse insights
        insights_data = insights_response.data.get("insights", [])
        insights = [
            InsightResult(
                insight_type=i.get("type", "unknown"),
                title=i.get("title", ""),
                description=i.get("description", ""),
                confidence=i.get("confidence", 0.0),
                recommendations=i.get("recommendations", []),
            )
            for i in insights_data
        ]

        # Calculate overall risk score (based on metrics)
        risk_score = self._calculate_risk_score(metrics_response.data.get("metrics", {}))

        # Extract trends
        trends = self._extract_trends(insights_data)

        logger.info({
            "event": "generate_insights_task_completed",
            "company_id": company_id,
            "insight_count": len(insights),
            "risk_score": risk_score,
        })

        return GenerateInsightsResult(
            success=True,
            insights=insights,
            risk_score=risk_score,
            trends=trends,
            company_id=company_id,
            period=period,
            message=f"Generated {len(insights)} insights",
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _calculate_risk_score(self, metrics: Dict[str, Any]) -> float:
        """
        Calculate overall risk score from metrics.

        Args:
            metrics: Company metrics

        Returns:
            Risk score between 0.0 (low risk) and 1.0 (high risk)
        """
        risk = 0.0

        # Escalation rate increases risk
        escalation = metrics.get("escalation_rate", {})
        if escalation.get("value", 0) > 15:
            risk += 0.3
        elif escalation.get("value", 0) > 10:
            risk += 0.15

        # Resolution rate decreases risk
        resolution = metrics.get("resolution_rate", {})
        if resolution.get("value", 100) < 80:
            risk += 0.25
        elif resolution.get("value", 100) < 90:
            risk += 0.1

        # Customer satisfaction decreases risk
        satisfaction = metrics.get("customer_satisfaction", {})
        if satisfaction.get("value", 5) < 3.5:
            risk += 0.25
        elif satisfaction.get("value", 5) < 4.0:
            risk += 0.1

        return min(1.0, risk)

    def _extract_trends(self, insights: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract trends from insights.

        Args:
            insights: List of insight data

        Returns:
            Dict with trend information
        """
        trends = {}

        for insight in insights:
            if insight.get("type") == "trend":
                data = insight.get("data", {})
                trends[insight.get("title", "unknown")] = {
                    "direction": data.get("trend_direction", "stable"),
                    "growth_rate": data.get("growth_rate", 0),
                }
            elif insight.get("type") == "prediction":
                data = insight.get("data", {})
                trends["prediction"] = {
                    "predicted_change": data.get("predicted_change", 0),
                    "confidence": data.get("confidence_interval", []),
                }

        return trends

    def get_task_name(self) -> str:
        """Get task name."""
        return "generate_insights"

    def get_variant(self) -> str:
        """Get variant name."""
        return "parwa_high"

    def get_tier(self) -> str:
        """Get tier used."""
        return "heavy"
