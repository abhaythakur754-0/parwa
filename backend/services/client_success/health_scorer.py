"""
Health Scorer Service

Calculates health scores (0-100) for clients using weighted scoring factors.
Provides trend analysis and health recommendations.
"""
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ScoreFactor(str, Enum):
    """Health score contributing factors."""
    ACTIVITY_LEVEL = "activity_level"
    ACCURACY = "accuracy"
    RESPONSE_TIME = "response_time"
    TICKET_RESOLUTION = "ticket_resolution"
    ENGAGEMENT = "engagement"


class TrendDirection(str, Enum):
    """Trend direction for health scores."""
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    CRITICAL = "critical"


@dataclass
class FactorScore:
    """Score for an individual factor."""
    factor: ScoreFactor
    score: float  # 0-100
    weight: float  # 0.0-1.0
    weighted_score: float
    trend: Optional[TrendDirection] = None
    recommendation: Optional[str] = None


@dataclass
class HealthScoreResult:
    """Complete health score result for a client."""
    client_id: str
    timestamp: datetime
    overall_score: float  # 0-100
    grade: str  # A, B, C, D, F
    factor_scores: List[FactorScore]
    trend: TrendDirection
    trend_description: str
    recommendations: List[str]
    risk_flags: List[str]


class HealthScorer:
    """
    Calculate health scores for clients.

    Uses weighted scoring factors:
    - Activity level: 20%
    - Accuracy: 30%
    - Response time: 20%
    - Ticket resolution: 20%
    - Engagement: 10%

    Provides trend analysis and actionable recommendations.
    """

    # Weight configuration for scoring factors
    FACTOR_WEIGHTS: Dict[ScoreFactor, float] = {
        ScoreFactor.ACTIVITY_LEVEL: 0.20,
        ScoreFactor.ACCURACY: 0.30,
        ScoreFactor.RESPONSE_TIME: 0.20,
        ScoreFactor.TICKET_RESOLUTION: 0.20,
        ScoreFactor.ENGAGEMENT: 0.10,
    }

    # Grade thresholds
    GRADE_THRESHOLDS: Dict[str, Tuple[float, float]] = {
        "A": (90, 100),
        "B": (80, 89.9),
        "C": (70, 79.9),
        "D": (60, 69.9),
        "F": (0, 59.9),
    }

    # Target values for normalization
    TARGETS = {
        ScoreFactor.ACTIVITY_LEVEL: 80.0,  # Target activity level
        ScoreFactor.ACCURACY: 90.0,  # Target accuracy rate
        ScoreFactor.RESPONSE_TIME: 2.0,  # Target response time (hours)
        ScoreFactor.TICKET_RESOLUTION: 85.0,  # Target resolution rate
        ScoreFactor.ENGAGEMENT: 75.0,  # Target engagement score
    }

    def __init__(self):
        """Initialize health scorer with historical data tracking."""
        self._score_history: Dict[str, List[HealthScoreResult]] = {}

    def calculate_score(
        self,
        client_id: str,
        activity_level: float,
        accuracy: float,
        response_time: float,
        ticket_resolution: float,
        engagement: float
    ) -> HealthScoreResult:
        """
        Calculate health score for a client.

        Args:
            client_id: Client identifier
            activity_level: Activity level score (0-100)
            accuracy: Accuracy rate (0-100)
            response_time: Average response time in hours
            ticket_resolution: Resolution rate (0-100)
            engagement: Engagement score (0-100)

        Returns:
            HealthScoreResult with complete scoring breakdown
        """
        # Calculate individual factor scores
        factor_scores = self._calculate_factor_scores(
            activity_level=activity_level,
            accuracy=accuracy,
            response_time=response_time,
            ticket_resolution=ticket_resolution,
            engagement=engagement
        )

        # Calculate weighted overall score
        overall_score = sum(fs.weighted_score for fs in factor_scores)

        # Determine grade
        grade = self._determine_grade(overall_score)

        # Analyze trend
        trend, trend_description = self._analyze_trend(client_id, overall_score)

        # Generate recommendations
        recommendations = self._generate_recommendations(factor_scores)

        # Identify risk flags
        risk_flags = self._identify_risk_flags(factor_scores, overall_score)

        result = HealthScoreResult(
            client_id=client_id,
            timestamp=datetime.utcnow(),
            overall_score=round(overall_score, 1),
            grade=grade,
            factor_scores=factor_scores,
            trend=trend,
            trend_description=trend_description,
            recommendations=recommendations,
            risk_flags=risk_flags
        )

        # Store in history
        if client_id not in self._score_history:
            self._score_history[client_id] = []
        self._score_history[client_id].append(result)

        logger.info(f"Health score for {client_id}: {overall_score:.1f} (Grade: {grade})")
        return result

    def _calculate_factor_scores(
        self,
        activity_level: float,
        accuracy: float,
        response_time: float,
        ticket_resolution: float,
        engagement: float
    ) -> List[FactorScore]:
        """
        Calculate individual factor scores with weights.
        """
        # Normalize response time (lower is better, target < 2 hours)
        # 0-2 hours = 100-80, 2-4 hours = 80-60, etc.
        if response_time <= 2:
            response_score = 100 - (response_time * 10)
        elif response_time <= 4:
            response_score = 80 - ((response_time - 2) * 10)
        elif response_time <= 8:
            response_score = 60 - ((response_time - 4) * 7.5)
        else:
            response_score = max(0, 30 - ((response_time - 8) * 3.75))

        factor_values = {
            ScoreFactor.ACTIVITY_LEVEL: min(100, max(0, activity_level)),
            ScoreFactor.ACCURACY: min(100, max(0, accuracy)),
            ScoreFactor.RESPONSE_TIME: max(0, response_score),
            ScoreFactor.TICKET_RESOLUTION: min(100, max(0, ticket_resolution)),
            ScoreFactor.ENGAGEMENT: min(100, max(0, engagement)),
        }

        factor_scores = []
        for factor, value in factor_values.items():
            weight = self.FACTOR_WEIGHTS[factor]
            weighted_score = value * weight

            recommendation = self._get_factor_recommendation(factor, value)

            fs = FactorScore(
                factor=factor,
                score=round(value, 1),
                weight=weight,
                weighted_score=round(weighted_score, 2),
                recommendation=recommendation
            )
            factor_scores.append(fs)

        return factor_scores

    def _determine_grade(self, score: float) -> str:
        """
        Determine letter grade from score.
        """
        for grade, (low, high) in self.GRADE_THRESHOLDS.items():
            if low <= score <= high:
                return grade
        return "F"

    def _analyze_trend(
        self,
        client_id: str,
        current_score: float
    ) -> Tuple[TrendDirection, str]:
        """
        Analyze health score trend.
        """
        history = self._score_history.get(client_id, [])

        if len(history) < 2:
            return TrendDirection.STABLE, "Insufficient data for trend analysis"

        # Compare with average of last 3 scores
        recent_scores = [h.overall_score for h in history[-3:]]
        avg_recent = sum(recent_scores) / len(recent_scores)

        diff = current_score - avg_recent

        if diff > 5:
            return TrendDirection.IMPROVING, f"Score improved by {diff:.1f} points"
        elif diff < -5:
            if current_score < 60:
                return TrendDirection.CRITICAL, f"Score dropped by {abs(diff):.1f} points - attention required"
            return TrendDirection.DECLINING, f"Score declined by {abs(diff):.1f} points"
        else:
            return TrendDirection.STABLE, "Score remains stable"

    def _get_factor_recommendation(
        self,
        factor: ScoreFactor,
        value: float
    ) -> Optional[str]:
        """
        Get recommendation for improving a factor score.
        """
        if value >= 80:
            return None  # No recommendation needed for good scores

        recommendations = {
            ScoreFactor.ACTIVITY_LEVEL: (
                "Increase client engagement through regular check-ins "
                "and feature adoption campaigns"
            ),
            ScoreFactor.ACCURACY: (
                "Review AI training data and knowledge base to improve "
                "response accuracy"
            ),
            ScoreFactor.RESPONSE_TIME: (
                "Optimize response workflows and consider additional "
                "automation for faster resolution"
            ),
            ScoreFactor.TICKET_RESOLUTION: (
                "Analyze escalation patterns and improve self-service "
                "options to boost resolution rate"
            ),
            ScoreFactor.ENGAGEMENT: (
                "Launch engagement initiatives and feature awareness "
                "campaigns to improve client interaction"
            ),
        }

        return recommendations.get(factor)

    def _generate_recommendations(
        self,
        factor_scores: List[FactorScore]
    ) -> List[str]:
        """
        Generate prioritized recommendations.
        """
        # Sort factors by score (lowest first) and weight (highest first)
        sorted_factors = sorted(
            factor_scores,
            key=lambda fs: (fs.score, -fs.weight)
        )

        recommendations = []
        for fs in sorted_factors:
            if fs.recommendation and fs.score < 80:
                recommendations.append(fs.recommendation)

        return recommendations[:3]  # Top 3 recommendations

    def _identify_risk_flags(
        self,
        factor_scores: List[FactorScore],
        overall_score: float
    ) -> List[str]:
        """
        Identify risk flags based on scores.
        """
        flags = []

        if overall_score < 60:
            flags.append("CRITICAL: Overall health score below threshold")

        for fs in factor_scores:
            if fs.factor == ScoreFactor.ACCURACY and fs.score < 70:
                flags.append(f"HIGH RISK: Low accuracy ({fs.score:.1f}%)")
            elif fs.factor == ScoreFactor.RESPONSE_TIME and fs.score < 50:
                flags.append(f"MEDIUM RISK: Slow response times")
            elif fs.factor == ScoreFactor.ACTIVITY_LEVEL and fs.score < 40:
                flags.append(f"HIGH RISK: Very low activity - potential churn")

        return flags

    def get_score_history(
        self,
        client_id: str,
        days: int = 30
    ) -> List[HealthScoreResult]:
        """
        Get historical health scores for a client.
        """
        history = self._score_history.get(client_id, [])
        return history[-days:] if history else []

    def get_score_trend_analysis(
        self,
        client_id: str
    ) -> Dict[str, Any]:
        """
        Get detailed trend analysis for a client's health scores.
        """
        history = self._score_history.get(client_id, [])

        if len(history) < 2:
            return {"status": "insufficient_data", "data_points": len(history)}

        scores = [h.overall_score for h in history]

        return {
            "client_id": client_id,
            "data_points": len(history),
            "first_score": scores[0],
            "latest_score": scores[-1],
            "highest_score": max(scores),
            "lowest_score": min(scores),
            "average_score": round(sum(scores) / len(scores), 1),
            "trend_direction": history[-1].trend.value,
            "improvement": round(scores[-1] - scores[0], 1),
        }

    def batch_calculate_scores(
        self,
        clients_data: List[Dict[str, Any]]
    ) -> List[HealthScoreResult]:
        """
        Calculate health scores for multiple clients.

        Args:
            clients_data: List of dicts with client_id and metric values

        Returns:
            List of HealthScoreResult for each client
        """
        results = []
        for client_data in clients_data:
            result = self.calculate_score(
                client_id=client_data["client_id"],
                activity_level=client_data.get("activity_level", 50),
                accuracy=client_data.get("accuracy", 80),
                response_time=client_data.get("response_time", 3.0),
                ticket_resolution=client_data.get("ticket_resolution", 75),
                engagement=client_data.get("engagement", 60)
            )
            results.append(result)

        return results

    def get_scoring_summary(self) -> Dict[str, Any]:
        """
        Get summary of all scored clients.
        """
        if not self._score_history:
            return {"clients_scored": 0}

        all_scores = []
        grade_distribution = {grade: 0 for grade in self.GRADE_THRESHOLDS.keys()}

        for client_id, history in self._score_history.items():
            if history:
                latest = history[-1]
                all_scores.append(latest.overall_score)
                grade_distribution[latest.grade] += 1

        return {
            "clients_scored": len(self._score_history),
            "average_score": round(sum(all_scores) / len(all_scores), 1)
                           if all_scores else 0,
            "grade_distribution": grade_distribution,
            "highest_score": max(all_scores) if all_scores else 0,
            "lowest_score": min(all_scores) if all_scores else 0,
        }
