"""
NPS Tracker for SaaS Advanced Module.

Provides NPS tracking including:
- NPS survey distribution
- Score calculation (promoters, passives, detractors)
- Trend tracking over time
- Segmented NPS analysis
- Follow-up workflow for detractors
- Benchmark comparison
"""

from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import Counter
import logging

logger = logging.getLogger(__name__)


class NPSCategory(str, Enum):
    """NPS response categories."""
    PROMOTER = "promoter"  # 9-10
    PASSIVE = "passive"    # 7-8
    DETRACTOR = "detractor"  # 0-6


class SurveyStatus(str, Enum):
    """Survey status."""
    PENDING = "pending"
    SENT = "sent"
    RESPONDED = "responded"
    EXPIRED = "expired"
    OPTED_OUT = "opted_out"


@dataclass
class NPSResponse:
    """Represents an NPS survey response."""
    id: UUID = field(default_factory=uuid4)
    client_id: str = ""
    survey_id: UUID = field(default_factory=uuid4)
    score: int = 0
    category: NPSCategory = NPSCategory.PASSIVE
    comment: Optional[str] = None
    customer_segment: str = ""
    responded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    follow_up_sent: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "client_id": self.client_id,
            "survey_id": str(self.survey_id),
            "score": self.score,
            "category": self.category.value,
            "comment": self.comment,
            "customer_segment": self.customer_segment,
            "responded_at": self.responded_at.isoformat(),
            "follow_up_sent": self.follow_up_sent,
        }


@dataclass
class NPSSurvey:
    """Represents an NPS survey."""
    id: UUID = field(default_factory=uuid4)
    client_id: str = ""
    name: str = ""
    question: str = "How likely are you to recommend our product?"
    status: SurveyStatus = SurveyStatus.PENDING
    sent_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    responses: List[UUID] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "client_id": self.client_id,
            "name": self.name,
            "question": self.question,
            "status": self.status.value,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "response_count": len(self.responses),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class NPSMetrics:
    """NPS metrics for a period."""
    period_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc) - timedelta(days=30))
    period_end: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_responses: int = 0
    promoters: int = 0
    passives: int = 0
    detractors: int = 0
    nps_score: float = 0.0
    avg_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_responses": self.total_responses,
            "promoters": self.promoters,
            "passives": self.passives,
            "detractors": self.detractors,
            "nps_score": round(self.nps_score, 2),
            "avg_score": round(self.avg_score, 2),
            "promoter_percent": round(self.promoters / self.total_responses * 100, 2) if self.total_responses else 0,
            "passive_percent": round(self.passives / self.total_responses * 100, 2) if self.total_responses else 0,
            "detractor_percent": round(self.detractors / self.total_responses * 100, 2) if self.total_responses else 0,
        }


# Industry benchmarks
NPS_BENCHMARKS = {
    "saas": {"excellent": 50, "good": 30, "average": 15},
    "ecommerce": {"excellent": 60, "good": 40, "average": 25},
    "fintech": {"excellent": 55, "good": 35, "average": 20},
    "healthcare": {"excellent": 45, "good": 25, "average": 10},
    "default": {"excellent": 50, "good": 30, "average": 15},
}


class NPSTracker:
    """
    Tracks Net Promoter Score for SaaS customers.

    Features:
    - Survey distribution
    - Score calculation
    - Trend tracking
    - Segmented analysis
    - Detractor follow-up
    - Benchmark comparison
    """

    def __init__(
        self,
        client_id: str = "",
        industry: str = "saas"
    ):
        """
        Initialize NPS tracker.

        Args:
            client_id: Client identifier
            industry: Industry for benchmarking
        """
        self.client_id = client_id
        self.industry = industry

        self._surveys: Dict[str, NPSSurvey] = {}
        self._responses: Dict[str, NPSResponse] = {}
        self._metrics_history: List[NPSMetrics] = []

    async def create_survey(
        self,
        name: str = "NPS Survey",
        question: str = "How likely are you to recommend our product?",
        expires_in_days: int = 14
    ) -> NPSSurvey:
        """
        Create a new NPS survey.

        Args:
            name: Survey name
            question: Survey question
            expires_in_days: Days until expiration

        Returns:
            Created NPSSurvey
        """
        survey = NPSSurvey(
            client_id=self.client_id,
            name=name,
            question=question,
            expires_at=datetime.now(timezone.utc) + timedelta(days=expires_in_days),
        )

        self._surveys[str(survey.id)] = survey

        logger.info(
            "NPS survey created",
            extra={
                "client_id": self.client_id,
                "survey_id": str(survey.id),
            }
        )

        return survey

    async def distribute_survey(
        self,
        survey_id: UUID,
        recipient_count: int = 100
    ) -> Dict[str, Any]:
        """
        Distribute survey to customers.

        Args:
            survey_id: Survey to distribute
            recipient_count: Number of recipients

        Returns:
            Dict with distribution result
        """
        survey = self._surveys.get(str(survey_id))
        if not survey:
            raise ValueError(f"Survey {survey_id} not found")

        survey.status = SurveyStatus.SENT
        survey.sent_at = datetime.now(timezone.utc)

        logger.info(
            "NPS survey distributed",
            extra={
                "client_id": self.client_id,
                "survey_id": str(survey_id),
                "recipient_count": recipient_count,
            }
        )

        return {
            "distributed": True,
            "survey_id": str(survey_id),
            "sent_at": survey.sent_at.isoformat(),
            "recipient_count": recipient_count,
        }

    async def record_response(
        self,
        survey_id: UUID,
        score: int,
        comment: Optional[str] = None,
        customer_segment: str = ""
    ) -> NPSResponse:
        """
        Record an NPS response.

        Args:
            survey_id: Survey ID
            score: NPS score (0-10)
            comment: Optional comment
            customer_segment: Customer segment

        Returns:
            Created NPSResponse
        """
        survey = self._surveys.get(str(survey_id))
        if not survey:
            raise ValueError(f"Survey {survey_id} not found")

        # Validate score
        if not 0 <= score <= 10:
            raise ValueError("Score must be between 0 and 10")

        # Categorize
        if score >= 9:
            category = NPSCategory.PROMOTER
        elif score >= 7:
            category = NPSCategory.PASSIVE
        else:
            category = NPSCategory.DETRACTOR

        response = NPSResponse(
            client_id=self.client_id,
            survey_id=survey_id,
            score=score,
            category=category,
            comment=comment,
            customer_segment=customer_segment,
        )

        self._responses[str(response.id)] = response
        survey.responses.append(response.id)

        logger.info(
            "NPS response recorded",
            extra={
                "client_id": self.client_id,
                "survey_id": str(survey_id),
                "score": score,
                "category": category.value,
            }
        )

        return response

    async def calculate_score(
        self,
        survey_id: Optional[UUID] = None,
        period_days: Optional[int] = None
    ) -> NPSMetrics:
        """
        Calculate NPS score.

        Args:
            survey_id: Optional specific survey
            period_days: Optional period filter

        Returns:
            NPSMetrics
        """
        responses = list(self._responses.values())

        # Filter by survey
        if survey_id:
            responses = [r for r in responses if r.survey_id == survey_id]

        # Filter by period
        if period_days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)
            responses = [r for r in responses if r.responded_at >= cutoff]

        if not responses:
            return NPSMetrics()

        # Count categories
        promoters = sum(1 for r in responses if r.category == NPSCategory.PROMOTER)
        passives = sum(1 for r in responses if r.category == NPSCategory.PASSIVE)
        detractors = sum(1 for r in responses if r.category == NPSCategory.DETRACTOR)
        total = len(responses)

        # Calculate NPS
        nps = ((promoters - detractors) / total) * 100

        # Calculate average score
        avg = sum(r.score for r in responses) / total

        metrics = NPSMetrics(
            total_responses=total,
            promoters=promoters,
            passives=passives,
            detractors=detractors,
            nps_score=nps,
            avg_score=avg,
        )

        self._metrics_history.append(metrics)

        return metrics

    async def track_trends(
        self,
        periods: int = 6
    ) -> Dict[str, Any]:
        """
        Track NPS trends over time.

        Args:
            periods: Number of periods to analyze

        Returns:
            Dict with trend analysis
        """
        if len(self._metrics_history) < 2:
            return {
                "trend": "insufficient_data",
                "periods_analyzed": len(self._metrics_history),
            }

        recent = self._metrics_history[-periods:]

        scores = [m.nps_score for m in recent]

        # Calculate trend
        if len(scores) >= 2:
            first_half = sum(scores[:len(scores)//2]) / (len(scores)//2 or 1)
            second_half = sum(scores[len(scores)//2:]) / (len(scores) - len(scores)//2 or 1)

            if second_half > first_half + 5:
                trend = "improving"
            elif second_half < first_half - 5:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "periods_analyzed": len(recent),
            "current_nps": scores[-1] if scores else 0,
            "average_nps": round(sum(scores) / len(scores), 2),
            "highest_nps": max(scores),
            "lowest_nps": min(scores),
            "score_history": [round(s, 2) for s in scores],
        }

    async def segment_analysis(
        self,
        segment_by: str = "customer_segment"
    ) -> Dict[str, Any]:
        """
        Analyze NPS by segment.

        Args:
            segment_by: Segment dimension

        Returns:
            Dict with segmented analysis
        """
        segments = {}

        for response in self._responses.values():
            segment = getattr(response, segment_by, "unknown")
            if segment not in segments:
                segments[segment] = {
                    "responses": [],
                    "scores": [],
                    "promoters": 0,
                    "passives": 0,
                    "detractors": 0,
                }

            segments[segment]["responses"].append(response)
            segments[segment]["scores"].append(response.score)

            if response.category == NPSCategory.PROMOTER:
                segments[segment]["promoters"] += 1
            elif response.category == NPSCategory.PASSIVE:
                segments[segment]["passives"] += 1
            else:
                segments[segment]["detractors"] += 1

        # Calculate segment NPS
        for segment, data in segments.items():
            total = len(data["responses"])
            data["nps"] = round(
                ((data["promoters"] - data["detractors"]) / total) * 100, 2
            ) if total > 0 else 0
            data["avg_score"] = round(sum(data["scores"]) / total, 2) if total > 0 else 0
            data["response_count"] = total
            del data["responses"]
            del data["scores"]

        return {
            "segment_by": segment_by,
            "segments": segments,
            "segment_count": len(segments),
        }

    async def trigger_detractor_followup(
        self,
        response_id: UUID
    ) -> Dict[str, Any]:
        """
        Trigger follow-up for detractor.

        Args:
            response_id: Response to follow up

        Returns:
            Dict with follow-up details
        """
        response = self._responses.get(str(response_id))
        if not response:
            raise ValueError(f"Response {response_id} not found")

        if response.category != NPSCategory.DETRACTOR:
            return {
                "triggered": False,
                "reason": "not_a_detractor",
            }

        if response.follow_up_sent:
            return {
                "triggered": False,
                "reason": "already_followed_up",
            }

        response.follow_up_sent = True

        logger.info(
            "Detractor follow-up triggered",
            extra={
                "client_id": self.client_id,
                "response_id": str(response_id),
                "score": response.score,
            }
        )

        return {
            "triggered": True,
            "response_id": str(response_id),
            "score": response.score,
            "comment": response.comment,
            "follow_up_action": "Schedule customer success call",
        }

    async def compare_to_benchmark(self) -> Dict[str, Any]:
        """
        Compare NPS to industry benchmark.

        Returns:
            Dict with benchmark comparison
        """
        metrics = await self.calculate_score()
        benchmarks = NPS_BENCHMARKS.get(self.industry, NPS_BENCHMARKS["default"])

        current_nps = metrics.nps_score

        if current_nps >= benchmarks["excellent"]:
            performance = "excellent"
            percentile = 90
        elif current_nps >= benchmarks["good"]:
            performance = "good"
            percentile = 70
        elif current_nps >= benchmarks["average"]:
            performance = "average"
            percentile = 50
        else:
            performance = "below_average"
            percentile = 25

        return {
            "current_nps": round(current_nps, 2),
            "industry": self.industry,
            "benchmark": benchmarks,
            "performance": performance,
            "estimated_percentile": percentile,
            "gap_to_excellent": round(benchmarks["excellent"] - current_nps, 2),
            "gap_to_good": round(benchmarks["good"] - current_nps, 2),
        }

    async def get_responses(
        self,
        survey_id: Optional[UUID] = None,
        category: Optional[NPSCategory] = None
    ) -> List[NPSResponse]:
        """Get responses with optional filters."""
        responses = list(self._responses.values())

        if survey_id:
            responses = [r for r in responses if r.survey_id == survey_id]

        if category:
            responses = [r for r in responses if r.category == category]

        return responses

    async def get_detractor_responses(self) -> List[NPSResponse]:
        """Get all detractor responses."""
        return [
            r for r in self._responses.values()
            if r.category == NPSCategory.DETRACTOR
        ]

    async def get_survey(self, survey_id: UUID) -> Optional[NPSSurvey]:
        """Get survey by ID."""
        return self._surveys.get(str(survey_id))


# Export for testing
__all__ = [
    "NPSTracker",
    "NPSSurvey",
    "NPSResponse",
    "NPSMetrics",
    "NPSCategory",
    "SurveyStatus",
    "NPS_BENCHMARKS",
]
