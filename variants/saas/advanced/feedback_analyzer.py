"""
Feedback Analyzer for SaaS Advanced Module.

Provides feedback analysis including:
- Sentiment analysis on feedback
- Theme extraction
- Urgency classification
- Trend detection
- Feedback aggregation
- Customer segment analysis
- Actionable insight generation
"""

from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import Counter
import logging
import re

logger = logging.getLogger(__name__)


class SentimentType(str, Enum):
    """Sentiment types."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class UrgencyLevel(str, Enum):
    """Urgency classification."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FeedbackSource(str, Enum):
    """Feedback sources."""
    TICKET = "ticket"
    EMAIL = "email"
    CHAT = "chat"
    SURVEY = "survey"
    REVIEW = "review"
    SOCIAL = "social"
    NPS = "nps"
    OTHER = "other"


@dataclass
class FeedbackItem:
    """Represents a feedback item."""
    id: UUID = field(default_factory=uuid4)
    client_id: str = ""
    content: str = ""
    source: FeedbackSource = FeedbackSource.TICKET
    sentiment: SentimentType = SentimentType.NEUTRAL
    sentiment_score: float = 0.5
    urgency: UrgencyLevel = UrgencyLevel.LOW
    themes: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None
    customer_segment: str = ""
    action_required: bool = False
    action_items: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "client_id": self.client_id,
            "content": self.content[:200] + "..." if len(self.content) > 200 else self.content,
            "source": self.source.value,
            "sentiment": self.sentiment.value,
            "sentiment_score": round(self.sentiment_score, 3),
            "urgency": self.urgency.value,
            "themes": self.themes,
            "keywords": self.keywords,
            "created_at": self.created_at.isoformat(),
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "customer_segment": self.customer_segment,
            "action_required": self.action_required,
            "action_items": self.action_items,
        }


@dataclass
class FeedbackInsight:
    """Represents an actionable insight from feedback."""
    id: UUID = field(default_factory=uuid4)
    insight_type: str = ""
    title: str = ""
    description: str = ""
    confidence: float = 0.0
    affected_customers: int = 0
    related_themes: List[str] = field(default_factory=list)
    recommendation: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "insight_type": self.insight_type,
            "title": self.title,
            "description": self.description,
            "confidence": round(self.confidence, 3),
            "affected_customers": self.affected_customers,
            "related_themes": self.related_themes,
            "recommendation": self.recommendation,
            "created_at": self.created_at.isoformat(),
        }


# Sentiment keywords
POSITIVE_KEYWORDS = [
    "great", "excellent", "amazing", "fantastic", "love", "awesome",
    "helpful", "intuitive", "easy", "fast", "reliable", "perfect",
    "recommend", "satisfied", "happy", "best", "wonderful", "impressed",
]

NEGATIVE_KEYWORDS = [
    "terrible", "awful", "horrible", "hate", "worst", "disappointed",
    "frustrating", "slow", "broken", "bug", "error", "issue", "problem",
    "difficult", "confusing", "expensive", "waste", "unreliable", "poor",
]

# Theme keywords mapping
THEME_KEYWORDS = {
    "performance": ["slow", "fast", "speed", "performance", "lag", "loading"],
    "usability": ["intuitive", "confusing", "easy", "difficult", "ui", "ux", "interface"],
    "features": ["feature", "missing", "need", "want", "add", "functionality"],
    "pricing": ["expensive", "price", "cost", "value", "worth", "cheaper"],
    "support": ["support", "help", "response", "service", "customer service"],
    "reliability": ["bug", "error", "crash", "reliable", "stable", "downtime"],
    "integration": ["integrate", "api", "connection", "sync", "export", "import"],
    "onboarding": ["setup", "onboard", "getting started", "learn", "tutorial"],
}

# Urgency keywords
CRITICAL_KEYWORDS = ["critical", "urgent", "emergency", "blocking", "down", "security"]
HIGH_KEYWORDS = ["important", "asap", "quickly", "soon", "priority", "major"]


class FeedbackAnalyzer:
    """
    Analyzes customer feedback for insights.

    Features:
    - Sentiment analysis
    - Theme extraction
    - Urgency classification
    - Trend detection
    - Aggregation
    - Segment analysis
    - Insight generation
    """

    def __init__(self, client_id: str = ""):
        """
        Initialize feedback analyzer.

        Args:
            client_id: Client identifier
        """
        self.client_id = client_id
        self._feedback: Dict[str, FeedbackItem] = {}
        self._insights: Dict[str, FeedbackInsight] = {}

    async def analyze_sentiment(
        self,
        content: str
    ) -> Dict[str, Any]:
        """
        Analyze sentiment of feedback content.

        Args:
            content: Feedback text

        Returns:
            Dict with sentiment analysis
        """
        content_lower = content.lower()

        positive_count = sum(1 for kw in POSITIVE_KEYWORDS if kw in content_lower)
        negative_count = sum(1 for kw in NEGATIVE_KEYWORDS if kw in content_lower)

        total = positive_count + negative_count
        if total == 0:
            sentiment = SentimentType.NEUTRAL
            score = 0.5
        else:
            score = positive_count / total
            if score >= 0.7:
                sentiment = SentimentType.POSITIVE
            elif score <= 0.3:
                sentiment = SentimentType.NEGATIVE
            elif abs(score - 0.5) < 0.2:
                sentiment = SentimentType.MIXED
            else:
                sentiment = SentimentType.NEUTRAL

        return {
            "sentiment": sentiment.value,
            "score": round(score, 3),
            "positive_keywords": positive_count,
            "negative_keywords": negative_count,
        }

    async def extract_themes(
        self,
        content: str
    ) -> Dict[str, Any]:
        """
        Extract themes from feedback.

        Args:
            content: Feedback text

        Returns:
            Dict with theme analysis
        """
        content_lower = content.lower()
        detected_themes = []
        theme_scores = {}

        for theme, keywords in THEME_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in content_lower)
            if matches > 0:
                detected_themes.append(theme)
                theme_scores[theme] = matches

        # Sort by score
        sorted_themes = sorted(
            theme_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return {
            "themes": detected_themes,
            "primary_theme": sorted_themes[0][0] if sorted_themes else None,
            "theme_scores": dict(sorted_themes),
        }

    async def classify_urgency(
        self,
        content: str,
        source: FeedbackSource = FeedbackSource.TICKET
    ) -> Dict[str, Any]:
        """
        Classify urgency level.

        Args:
            content: Feedback text
            source: Feedback source

        Returns:
            Dict with urgency classification
        """
        content_lower = content.lower()

        urgency = UrgencyLevel.LOW
        factors = []

        # Check critical keywords
        for kw in CRITICAL_KEYWORDS:
            if kw in content_lower:
                urgency = UrgencyLevel.CRITICAL
                factors.append(f"critical_keyword:{kw}")

        # Check high urgency keywords
        if urgency != UrgencyLevel.CRITICAL:
            for kw in HIGH_KEYWORDS:
                if kw in content_lower:
                    urgency = UrgencyLevel.HIGH
                    factors.append(f"high_keyword:{kw}")

        # Source-based urgency boost
        if source == FeedbackSource.NPS:
            # Check if detractor (NPS < 7)
            if "detractor" in content_lower:
                if urgency == UrgencyLevel.LOW:
                    urgency = UrgencyLevel.MEDIUM
                factors.append("detractor_feedback")

        return {
            "urgency": urgency.value,
            "factors": factors,
        }

    async def process_feedback(
        self,
        content: str,
        source: FeedbackSource = FeedbackSource.TICKET,
        customer_segment: str = ""
    ) -> FeedbackItem:
        """
        Process a feedback item.

        Args:
            content: Feedback text
            source: Feedback source
            customer_segment: Customer segment

        Returns:
            Processed FeedbackItem
        """
        # Analyze sentiment
        sentiment_result = await self.analyze_sentiment(content)

        # Extract themes
        theme_result = await self.extract_themes(content)

        # Classify urgency
        urgency_result = await self.classify_urgency(content, source)

        # Extract keywords
        keywords = await self._extract_keywords(content)

        # Determine if action required
        action_required = (
            sentiment_result["sentiment"] == "negative" and
            urgency_result["urgency"] in ["high", "critical"]
        )

        # Generate action items
        action_items = []
        if action_required:
            action_items = await self._generate_action_items(
                content, theme_result["themes"], urgency_result["urgency"]
            )

        feedback = FeedbackItem(
            client_id=self.client_id,
            content=content,
            source=source,
            sentiment=SentimentType(sentiment_result["sentiment"]),
            sentiment_score=sentiment_result["score"],
            urgency=UrgencyLevel(urgency_result["urgency"]),
            themes=theme_result["themes"],
            keywords=keywords,
            processed_at=datetime.now(timezone.utc),
            customer_segment=customer_segment,
            action_required=action_required,
            action_items=action_items,
        )

        self._feedback[str(feedback.id)] = feedback

        logger.info(
            "Feedback processed",
            extra={
                "client_id": self.client_id,
                "feedback_id": str(feedback.id),
                "sentiment": sentiment_result["sentiment"],
                "urgency": urgency_result["urgency"],
            }
        )

        return feedback

    async def detect_trends(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Detect feedback trends over time.

        Args:
            days: Number of days to analyze

        Returns:
            Dict with trend analysis
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        recent = [
            f for f in self._feedback.values()
            if f.created_at >= cutoff
        ]

        if len(recent) < 5:
            return {
                "detected": False,
                "reason": "insufficient_data",
                "feedback_count": len(recent),
            }

        # Sentiment trends
        sentiments = [f.sentiment.value for f in recent]
        sentiment_counts = Counter(sentiments)

        # Theme trends
        all_themes = []
        for f in recent:
            all_themes.extend(f.themes)
        theme_counts = Counter(all_themes)

        # Urgency trends
        urgencies = [f.urgency.value for f in recent]
        urgency_counts = Counter(urgencies)

        # Calculate trends
        avg_sentiment = sum(f.sentiment_score for f in recent) / len(recent)

        # Compare to previous period
        prev_cutoff = cutoff - timedelta(days=days)
        prev_feedback = [
            f for f in self._feedback.values()
            if prev_cutoff <= f.created_at < cutoff
        ]

        if prev_feedback:
            prev_avg_sentiment = sum(f.sentiment_score for f in prev_feedback) / len(prev_feedback)
            sentiment_change = avg_sentiment - prev_avg_sentiment
        else:
            sentiment_change = 0

        trend_direction = "stable"
        if sentiment_change > 0.1:
            trend_direction = "improving"
        elif sentiment_change < -0.1:
            trend_direction = "declining"

        return {
            "detected": True,
            "period_days": days,
            "feedback_count": len(recent),
            "sentiment": {
                "average_score": round(avg_sentiment, 3),
                "change": round(sentiment_change, 3),
                "trend": trend_direction,
                "distribution": dict(sentiment_counts),
            },
            "top_themes": dict(theme_counts.most_common(5)),
            "urgency_distribution": dict(urgency_counts),
            "action_required_count": sum(1 for f in recent if f.action_required),
        }

    async def aggregate_feedback(
        self,
        group_by: str = "theme"
    ) -> Dict[str, Any]:
        """
        Aggregate feedback by dimension.

        Args:
            group_by: Dimension to group by (theme, sentiment, source, urgency)

        Returns:
            Dict with aggregated feedback
        """
        groups = {}

        for feedback in self._feedback.values():
            if group_by == "theme":
                keys = feedback.themes if feedback.themes else ["other"]
            elif group_by == "sentiment":
                keys = [feedback.sentiment.value]
            elif group_by == "source":
                keys = [feedback.source.value]
            elif group_by == "urgency":
                keys = [feedback.urgency.value]
            else:
                keys = ["all"]

            for key in keys:
                if key not in groups:
                    groups[key] = {
                        "count": 0,
                        "avg_sentiment": [],
                        "action_required": 0,
                    }
                groups[key]["count"] += 1
                groups[key]["avg_sentiment"].append(feedback.sentiment_score)
                if feedback.action_required:
                    groups[key]["action_required"] += 1

        # Calculate averages
        for key, data in groups.items():
            data["avg_sentiment"] = round(
                sum(data["avg_sentiment"]) / len(data["avg_sentiment"]), 3
            )

        return {
            "group_by": group_by,
            "groups": groups,
            "total_feedback": len(self._feedback),
        }

    async def analyze_segments(self) -> Dict[str, Any]:
        """
        Analyze feedback by customer segment.

        Returns:
            Dict with segment analysis
        """
        segments = {}

        for feedback in self._feedback.values():
            segment = feedback.customer_segment or "unknown"
            if segment not in segments:
                segments[segment] = {
                    "count": 0,
                    "sentiments": [],
                    "themes": [],
                    "action_required": 0,
                }

            segments[segment]["count"] += 1
            segments[segment]["sentiments"].append(feedback.sentiment_score)
            segments[segment]["themes"].extend(feedback.themes)
            if feedback.action_required:
                segments[segment]["action_required"] += 1

        # Calculate segment metrics
        for segment, data in segments.items():
            data["avg_sentiment"] = round(
                sum(data["sentiments"]) / len(data["sentiments"]), 3
            )
            data["top_themes"] = Counter(data["themes"]).most_common(3)
            del data["sentiments"]

        return {
            "segments": segments,
            "segment_count": len(segments),
        }

    async def generate_insights(
        self,
        min_feedback: int = 5
    ) -> List[FeedbackInsight]:
        """
        Generate actionable insights from feedback.

        Args:
            min_feedback: Minimum feedback to generate insight

        Returns:
            List of FeedbackInsight
        """
        insights = []

        # Analyze negative feedback patterns
        negative = [
            f for f in self._feedback.values()
            if f.sentiment == SentimentType.NEGATIVE
        ]

        if len(negative) >= min_feedback:
            # Theme-based insights
            theme_counter = Counter()
            for f in negative:
                theme_counter.update(f.themes)

            for theme, count in theme_counter.most_common(3):
                if count >= 3:
                    insight = FeedbackInsight(
                        insight_type="negative_theme",
                        title=f"Recurring {theme} issues",
                        description=f"{count} customers reported negative experiences with {theme}",
                        confidence=min(count / len(negative), 1.0),
                        affected_customers=count,
                        related_themes=[theme],
                        recommendation=f"Investigate and address {theme}-related issues",
                    )
                    insights.append(insight)
                    self._insights[str(insight.id)] = insight

        # Analyze urgent feedback
        urgent = [
            f for f in self._feedback.values()
            if f.urgency in [UrgencyLevel.HIGH, UrgencyLevel.CRITICAL]
        ]

        if len(urgent) >= 3:
            insight = FeedbackInsight(
                insight_type="urgent_pattern",
                title="High urgency feedback pattern",
                description=f"{len(urgent)} pieces of feedback require immediate attention",
                confidence=0.85,
                affected_customers=len(urgent),
                related_themes=list(set(t for f in urgent for t in f.themes))[:3],
                recommendation="Review and prioritize urgent feedback resolution",
            )
            insights.append(insight)
            self._insights[str(insight.id)] = insight

        logger.info(
            "Insights generated",
            extra={
                "client_id": self.client_id,
                "insight_count": len(insights),
            }
        )

        return insights

    async def get_feedback(
        self,
        feedback_id: UUID
    ) -> Optional[FeedbackItem]:
        """Get feedback by ID."""
        return self._feedback.get(str(feedback_id))

    async def get_insights(self) -> List[FeedbackInsight]:
        """Get all generated insights."""
        return list(self._insights.values())

    async def get_actionable_feedback(self) -> List[FeedbackItem]:
        """Get feedback requiring action."""
        return [
            f for f in self._feedback.values()
            if f.action_required
        ]

    async def _extract_keywords(self, content: str) -> List[str]:
        """Extract keywords from content."""
        words = re.findall(r'\b[a-z]{4,}\b', content.lower())
        word_counts = Counter(words)

        # Filter common words
        common_words = {"this", "that", "with", "from", "have", "been", "were", "they", "their", "would"}
        filtered = {
            word: count for word, count in word_counts.items()
            if word not in common_words and count >= 1
        }

        return list(filtered.keys())[:10]

    async def _generate_action_items(
        self,
        content: str,
        themes: List[str],
        urgency: str
    ) -> List[str]:
        """Generate action items for feedback."""
        actions = []

        if urgency in ["high", "critical"]:
            actions.append("Escalate to product team for immediate review")

        for theme in themes:
            if theme == "performance":
                actions.append("Investigate performance issues")
            elif theme == "usability":
                actions.append("Review UX/UI for improvements")
            elif theme == "support":
                actions.append("Follow up with support team")
            elif theme == "pricing":
                actions.append("Review pricing concerns")

        return actions[:3]


# Export for testing
__all__ = [
    "FeedbackAnalyzer",
    "FeedbackItem",
    "FeedbackInsight",
    "SentimentType",
    "UrgencyLevel",
    "FeedbackSource",
    "POSITIVE_KEYWORDS",
    "NEGATIVE_KEYWORDS",
    "THEME_KEYWORDS",
]
