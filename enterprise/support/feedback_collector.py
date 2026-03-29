"""
Enterprise Support - Feedback Collector
Collect and manage enterprise feedback
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
import uuid


class FeedbackType(str, Enum):
    GENERAL = "general"
    TICKET = "ticket"
    FEATURE = "feature"
    BUG = "bug"
    IMPROVEMENT = "improvement"


class FeedbackRating(str, Enum):
    VERY_SATISFIED = "very_satisfied"
    SATISFIED = "satisfied"
    NEUTRAL = "neutral"
    DISSATISFIED = "dissatisfied"
    VERY_DISSATISFIED = "very_dissatisfied"


class EnterpriseFeedback(BaseModel):
    """Enterprise feedback"""
    feedback_id: str = Field(default_factory=lambda: f"fb_{uuid.uuid4().hex[:8]}")
    client_id: str
    feedback_type: FeedbackType = FeedbackType.GENERAL
    rating: FeedbackRating = FeedbackRating.NEUTRAL
    title: str
    content: str
    ticket_id: Optional[str] = None
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed: bool = False
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    response: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

    model_config = ConfigDict()


class FeedbackStats(BaseModel):
    """Feedback statistics"""
    client_id: str
    period_start: datetime
    period_end: datetime
    total_feedback: int = 0
    avg_rating: float = 0.0
    by_type: Dict[str, int] = Field(default_factory=dict)
    by_rating: Dict[str, int] = Field(default_factory=dict)

    model_config = ConfigDict()


class FeedbackCollector:
    """
    Collect and manage enterprise feedback.
    """

    RATING_SCORES = {
        FeedbackRating.VERY_SATISFIED: 5,
        FeedbackRating.SATISFIED: 4,
        FeedbackRating.NEUTRAL: 3,
        FeedbackRating.DISSATISFIED: 2,
        FeedbackRating.VERY_DISSATISFIED: 1
    }

    def __init__(self):
        self.feedback: Dict[str, EnterpriseFeedback] = {}

    def submit_feedback(
        self,
        client_id: str,
        title: str,
        content: str,
        feedback_type: FeedbackType = FeedbackType.GENERAL,
        rating: FeedbackRating = FeedbackRating.NEUTRAL,
        ticket_id: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> EnterpriseFeedback:
        """Submit feedback"""
        feedback = EnterpriseFeedback(
            client_id=client_id,
            title=title,
            content=content,
            feedback_type=feedback_type,
            rating=rating,
            ticket_id=ticket_id,
            tags=tags or []
        )

        self.feedback[feedback.feedback_id] = feedback
        return feedback

    def review_feedback(
        self,
        feedback_id: str,
        reviewed_by: str,
        response: Optional[str] = None
    ) -> bool:
        """Review feedback"""
        if feedback_id not in self.feedback:
            return False

        fb = self.feedback[feedback_id]
        fb.reviewed = True
        fb.reviewed_at = datetime.utcnow()
        fb.reviewed_by = reviewed_by
        fb.response = response

        return True

    def get_client_feedback(self, client_id: str) -> List[EnterpriseFeedback]:
        """Get all feedback for a client"""
        return [f for f in self.feedback.values() if f.client_id == client_id]

    def get_ticket_feedback(self, ticket_id: str) -> List[EnterpriseFeedback]:
        """Get feedback for a ticket"""
        return [f for f in self.feedback.values() if f.ticket_id == ticket_id]

    def get_unreviewed(self) -> List[EnterpriseFeedback]:
        """Get unreviewed feedback"""
        return [f for f in self.feedback.values() if not f.reviewed]

    def get_stats(
        self,
        client_id: str,
        period_start: datetime,
        period_end: datetime
    ) -> FeedbackStats:
        """Get feedback statistics"""
        client_feedback = [
            f for f in self.feedback.values()
            if f.client_id == client_id and period_start <= f.submitted_at <= period_end
        ]

        by_type: Dict[str, int] = {}
        by_rating: Dict[str, int] = {}

        total_score = 0
        for fb in client_feedback:
            by_type[fb.feedback_type.value] = by_type.get(fb.feedback_type.value, 0) + 1
            by_rating[fb.rating.value] = by_rating.get(fb.rating.value, 0) + 1
            total_score += self.RATING_SCORES[fb.rating]

        avg_rating = total_score / len(client_feedback) if client_feedback else 0

        return FeedbackStats(
            client_id=client_id,
            period_start=period_start,
            period_end=period_end,
            total_feedback=len(client_feedback),
            avg_rating=avg_rating,
            by_type=by_type,
            by_rating=by_rating
        )

    def get_satisfaction_score(self, client_id: str) -> float:
        """Get satisfaction score (0-100)"""
        client_feedback = self.get_client_feedback(client_id)
        if not client_feedback:
            return 0.0

        total_score = sum(self.RATING_SCORES[fb.rating] for fb in client_feedback)
        max_score = len(client_feedback) * 5

        return (total_score / max_score) * 100 if max_score > 0 else 0.0
