"""
PARWA Sentiment Analyzer.

Analyzes customer sentiment to detect emotions like anger, frustration,
urgency, etc. Provides sentiment scores and routing recommendations.
"""
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class SentimentType(str, Enum):
    """Sentiment type enumeration."""
    ANGER = "anger"
    FRUSTRATION = "frustration"
    SADNESS = "sadness"
    HAPPINESS = "happiness"
    URGENCY = "urgency"
    CONFUSION = "confusion"
    GRATITUDE = "gratitude"
    NEUTRAL = "neutral"


class SentimentIntensity(str, Enum):
    """Sentiment intensity levels."""
    LOW = "low"           # 0-30
    MODERATE = "moderate" # 31-60
    HIGH = "high"         # 61-80
    CRITICAL = "critical" # 81-100


class SentimentResult(BaseModel):
    """
    Result from sentiment analysis.
    """
    text: str
    primary_sentiment: str = SentimentType.NEUTRAL.value
    sentiment_scores: Dict[str, float] = Field(default_factory=dict)
    intensity_score: float = Field(default=0.0, ge=0.0, le=100.0)
    intensity_level: str = SentimentIntensity.LOW.value
    requires_attention: bool = False
    routing_pathway: str = "standard"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class SentimentAnalyzerConfig(BaseModel):
    """
    Configuration for Sentiment Analyzer.
    """
    anger_threshold: float = Field(default=50.0, ge=0.0, le=100.0)
    frustration_threshold: float = Field(default=40.0, ge=0.0, le=100.0)
    urgency_threshold: float = Field(default=60.0, ge=0.0, le=100.0)
    critical_threshold: float = Field(default=75.0, ge=0.0, le=100.0)
    escalation_threshold: float = Field(default=80.0, ge=0.0, le=100.0)
    enable_logging: bool = Field(default=True)

    model_config = ConfigDict(use_enum_values=True)


class SentimentAnalyzer:
    """
    Sentiment Analyzer for customer messages.

    Detects emotions and provides routing recommendations:
    - Anger detection → High pathway
    - Frustration detection → Medium pathway
    - Urgency detection → Priority handling
    - Gratitude detection → Positive feedback

    Features:
    - Pattern-based emotion detection
    - Intensity scoring (0-100)
    - Routing pathway recommendations
    - Attention flagging for critical cases
    """

    # Anger patterns (high weight)
    ANGER_PATTERNS = [
        r"\b(angry|furious|outraged|pissed|mad|livid)\b",
        r"\b(hate|despise|disgusted|disgusting)\b",
        r"\b(terrible|awful|horrible|worst|pathetic)\b",
        r"\b(ridiculous|unacceptable|incompetent|useless)\b",
        r"\b(scam|fraud|cheat|stole|stealing)\b",
        r"\b(never.*again|done.*with|finished.*with)\b",
        r"\b(sue|lawsuit|lawyer|attorney|legal.*action)\b",
        r"\b BBB|better business bureau",
        r"\bcomplaint\b",
        r"!{2,}",  # Multiple exclamation marks
        r"\b(wtf|wth|bs|bullshit)\b",
    ]

    # Frustration patterns (medium weight)
    FRUSTRATION_PATTERNS = [
        r"\b(frustrated|annoyed|irritated|fed up|sick of)\b",
        r"\b(tired|exhausted|drained|overwhelmed)\b",
        r"\b(not working|doesn'?t work|won'?t work|broken)\b",
        r"\b(again|still|repeatedly|multiple times)\b",
        r"\b(waiting.*for|on hold|hours|days)\b",
        r"\b(no one|nobody|someone.*should|where.*is)\b",
        r"\b(tried.*everything|nothing.*works|at my wits)\b",
        r"\b(waste.*time|wasting.*time|wasted)\b",
    ]

    # Urgency patterns
    URGENCY_PATTERNS = [
        r"\b(urgent|emergency|immediately|asap|right now)\b",
        r"\b(critical|crucial|vital|important|priority)\b",
        r"\b(deadline|time.*sensitive|today|tonight)\b",
        r"\b(need.*help|need.*assistance|please.*help)\b",
        r"\b(locked out|can'?t access|account.*frozen)\b",
        r"\b(charged.*wrong|unauthorized|fraudulent)\b",
        r"\b(money|payment|refund|charge)\b",
    ]

    # Sadness patterns
    SADNESS_PATTERNS = [
        r"\b(sad|depressed|disappointed|upset|unhappy)\b",
        r"\b(hurt|hurtful|heartbroken|devastated)\b",
        r"\b(cry|crying|tears|miserable)\b",
        r"\b(sorry|apologize|apology|regret)\b",
        r"\b(loss|lost|miss|missing)\b",
    ]

    # Happiness patterns
    HAPPINESS_PATTERNS = [
        r"\b(happy|glad|pleased|delighted|thrilled)\b",
        r"\b(great|excellent|amazing|wonderful|fantastic)\b",
        r"\b(love|loved|awesome|perfect|best)\b",
        r"\b(thank|thanks|grateful|appreciate|appreciated)\b",
        r"\b(excited|excited|looking forward)\b",
    ]

    # Confusion patterns
    CONFUSION_PATTERNS = [
        r"\b(confused|confusing|don'?t understand|can'?t figure)\b",
        r"\b(how do|how to|what do|where do|when do)\b",
        r"\b(help me|explain|clarify|unclear)\b",
        r"\b(not sure|unsure|don'?t know|clueless)\b",
        r"\b\?.*\?",  # Multiple questions
    ]

    # Gratitude patterns
    GRATITUDE_PATTERNS = [
        r"\b(thank you|thanks|thx|appreciate|grateful)\b",
        r"\b(you'?re the best|awesome|amazing|fantastic)\b",
        r"\b(helped me|solved|fixed|resolved)\b",
        r"\b(great service|great help|very helpful)\b",
    ]

    def __init__(
        self,
        config: Optional[SentimentAnalyzerConfig] = None
    ) -> None:
        """
        Initialize Sentiment Analyzer.

        Args:
            config: Analyzer configuration
        """
        self.config = config or SentimentAnalyzerConfig()

        # Statistics tracking
        self._analyses_performed = 0
        self._attention_flagged = 0
        self._emotion_counts: Dict[str, int] = {}

        logger.info({
            "event": "sentiment_analyzer_initialized",
            "anger_threshold": self.config.anger_threshold,
            "critical_threshold": self.config.critical_threshold,
        })

    def analyze(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> SentimentResult:
        """
        Analyze sentiment of text.

        Args:
            text: Text to analyze
            context: Additional context (previous messages, customer info)

        Returns:
            SentimentResult with analysis

        Raises:
            ValueError: If text is empty
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        text_lower = text.lower().strip()

        # Score each emotion
        scores = self._calculate_emotion_scores(text_lower)

        # Determine primary sentiment
        primary_sentiment = self._determine_primary_sentiment(scores)

        # Calculate intensity score
        intensity_score = self._calculate_intensity_score(scores)

        # Determine intensity level
        intensity_level = self._get_intensity_level(intensity_score)

        # Check if requires attention
        requires_attention = self._check_attention(
            primary_sentiment,
            intensity_score,
            scores
        )

        # Determine routing pathway
        routing_pathway = self._determine_routing_pathway(
            primary_sentiment,
            intensity_score,
            requires_attention
        )

        # Calculate confidence
        confidence = self._calculate_confidence(scores, text_lower)

        result = SentimentResult(
            text=text[:200] + "..." if len(text) > 200 else text,
            primary_sentiment=primary_sentiment,
            sentiment_scores=scores,
            intensity_score=intensity_score,
            intensity_level=intensity_level,
            requires_attention=requires_attention,
            routing_pathway=routing_pathway,
            confidence=confidence,
            metadata={
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
                "text_length": len(text),
                "context": context,
            }
        )

        # Update stats
        self._analyses_performed += 1
        if requires_attention:
            self._attention_flagged += 1
        self._emotion_counts[primary_sentiment] = (
            self._emotion_counts.get(primary_sentiment, 0) + 1
        )

        if self.config.enable_logging:
            log_level = "warning" if requires_attention else "info"
            getattr(logger, log_level)({
                "event": "sentiment_analyzed",
                "primary_sentiment": primary_sentiment,
                "intensity_score": intensity_score,
                "routing_pathway": routing_pathway,
                "requires_attention": requires_attention,
            })

        return result

    def analyze_batch(
        self,
        texts: List[str]
    ) -> List[SentimentResult]:
        """
        Analyze sentiment for multiple texts.

        Args:
            texts: List of texts to analyze

        Returns:
            List of SentimentResult
        """
        results = []
        for text in texts:
            try:
                result = self.analyze(text)
                results.append(result)
            except Exception as e:
                logger.error({
                    "event": "sentiment_analysis_failed",
                    "text_preview": text[:50] if text else None,
                    "error": str(e),
                })
                # Append neutral result for failed analyses
                results.append(SentimentResult(
                    text=text[:200] if text else "",
                    primary_sentiment=SentimentType.NEUTRAL.value,
                ))
        return results

    def get_stats(self) -> Dict[str, Any]:
        """
        Get analyzer statistics.

        Returns:
            Dict with stats
        """
        return {
            "analyses_performed": self._analyses_performed,
            "attention_flagged": self._attention_flagged,
            "attention_rate": (
                self._attention_flagged / self._analyses_performed
                if self._analyses_performed > 0 else 0
            ),
            "emotion_distribution": dict(self._emotion_counts),
            "config": self.config.model_dump(),
        }

    def _calculate_emotion_scores(self, text: str) -> Dict[str, float]:
        """
        Calculate emotion scores for text.

        Args:
            text: Lowercase text

        Returns:
            Dict mapping emotion to score (0-100)
        """
        import re

        scores = {}

        # Count pattern matches for each emotion
        anger_count = sum(
            1 for p in self.ANGER_PATTERNS
            if re.search(p, text, re.IGNORECASE)
        )
        frustration_count = sum(
            1 for p in self.FRUSTRATION_PATTERNS
            if re.search(p, text, re.IGNORECASE)
        )
        urgency_count = sum(
            1 for p in self.URGENCY_PATTERNS
            if re.search(p, text, re.IGNORECASE)
        )
        sadness_count = sum(
            1 for p in self.SADNESS_PATTERNS
            if re.search(p, text, re.IGNORECASE)
        )
        happiness_count = sum(
            1 for p in self.HAPPINESS_PATTERNS
            if re.search(p, text, re.IGNORECASE)
        )
        confusion_count = sum(
            1 for p in self.CONFUSION_PATTERNS
            if re.search(p, text, re.IGNORECASE)
        )
        gratitude_count = sum(
            1 for p in self.GRATITUDE_PATTERNS
            if re.search(p, text, re.IGNORECASE)
        )

        # Convert counts to scores (0-100)
        # Anger has higher weight
        scores[SentimentType.ANGER.value] = min(100, anger_count * 25)
        scores[SentimentType.FRUSTRATION.value] = min(100, frustration_count * 15)
        scores[SentimentType.URGENCY.value] = min(100, urgency_count * 20)
        scores[SentimentType.SADNESS.value] = min(100, sadness_count * 20)
        scores[SentimentType.HAPPINESS.value] = min(100, happiness_count * 20)
        scores[SentimentType.CONFUSION.value] = min(100, confusion_count * 15)
        scores[SentimentType.GRATITUDE.value] = min(100, gratitude_count * 25)

        # Neutral is inverse of other emotions
        max_other = max(
            scores.get(SentimentType.ANGER.value, 0),
            scores.get(SentimentType.FRUSTRATION.value, 0),
            scores.get(SentimentType.URGENCY.value, 0),
            scores.get(SentimentType.SADNESS.value, 0),
        )
        scores[SentimentType.NEUTRAL.value] = max(0, 100 - max_other * 1.5)

        return scores

    def _determine_primary_sentiment(
        self,
        scores: Dict[str, float]
    ) -> str:
        """
        Determine primary sentiment from scores.

        Args:
            scores: Emotion scores

        Returns:
            Primary sentiment string
        """
        if not scores:
            return SentimentType.NEUTRAL.value

        # Filter out very low scores
        significant_scores = {
            k: v for k, v in scores.items()
            if v >= 10
        }

        if not significant_scores:
            return SentimentType.NEUTRAL.value

        return max(significant_scores, key=significant_scores.get)

    def _calculate_intensity_score(
        self,
        scores: Dict[str, float]
    ) -> float:
        """
        Calculate overall intensity score.

        Args:
            scores: Emotion scores

        Returns:
            Intensity score (0-100)
        """
        # Weight negative emotions more heavily
        negative_weight = 1.5
        neutral_weight = 0.5

        negative_emotions = [
            SentimentType.ANGER.value,
            SentimentType.FRUSTRATION.value,
            SentimentType.SADNESS.value,
        ]

        total_score = 0.0
        for emotion, score in scores.items():
            if emotion in negative_emotions:
                total_score += score * negative_weight
            elif emotion == SentimentType.NEUTRAL.value:
                total_score += score * neutral_weight
            else:
                total_score += score

        # Normalize to 0-100
        return min(100.0, max(0.0, total_score / 5))

    def _get_intensity_level(self, score: float) -> str:
        """
        Get intensity level from score.

        Args:
            score: Intensity score

        Returns:
            Intensity level string
        """
        if score >= 81:
            return SentimentIntensity.CRITICAL.value
        elif score >= 61:
            return SentimentIntensity.HIGH.value
        elif score >= 31:
            return SentimentIntensity.MODERATE.value
        else:
            return SentimentIntensity.LOW.value

    def _check_attention(
        self,
        primary_sentiment: str,
        intensity_score: float,
        scores: Dict[str, float]
    ) -> bool:
        """
        Check if sentiment requires attention.

        Args:
            primary_sentiment: Primary emotion
            intensity_score: Overall intensity
            scores: All emotion scores

        Returns:
            True if attention required
        """
        # Critical intensity always requires attention
        if intensity_score >= self.config.critical_threshold:
            return True

        # High anger score requires attention
        anger_score = scores.get(SentimentType.ANGER.value, 0)
        if anger_score >= self.config.anger_threshold:
            return True

        # Escalation threshold
        if intensity_score >= self.config.escalation_threshold:
            return True

        # Combination of negative emotions
        frustration_score = scores.get(SentimentType.FRUSTRATION.value, 0)
        urgency_score = scores.get(SentimentType.URGENCY.value, 0)

        if (anger_score + frustration_score + urgency_score) >= 100:
            return True

        return False

    def _determine_routing_pathway(
        self,
        primary_sentiment: str,
        intensity_score: float,
        requires_attention: bool
    ) -> str:
        """
        Determine routing pathway based on sentiment.

        Args:
            primary_sentiment: Primary emotion
            intensity_score: Overall intensity
            requires_attention: Attention flag

        Returns:
            Routing pathway string
        """
        # High anger → PARWA High pathway
        if primary_sentiment == SentimentType.ANGER.value:
            if intensity_score >= self.config.critical_threshold:
                return "escalation"
            return "high"

        # Frustration + high intensity → medium/high
        if primary_sentiment == SentimentType.FRUSTRATION.value:
            if intensity_score >= self.config.anger_threshold:
                return "high"
            return "medium"

        # Urgency → priority handling
        if primary_sentiment == SentimentType.URGENCY.value:
            return "priority"

        # Attention required → elevated pathway
        if requires_attention:
            return "elevated"

        # Happiness/gratitude → standard
        if primary_sentiment in [
            SentimentType.HAPPINESS.value,
            SentimentType.GRATITUDE.value
        ]:
            return "standard"

        # Confusion → helpful pathway
        if primary_sentiment == SentimentType.CONFUSION.value:
            return "guided"

        # Default standard
        return "standard"

    def _calculate_confidence(
        self,
        scores: Dict[str, float],
        text: str
    ) -> float:
        """
        Calculate confidence in sentiment analysis.

        Args:
            scores: Emotion scores
            text: Analyzed text

        Returns:
            Confidence score (0-1)
        """
        # Base confidence on text length
        length_factor = min(1.0, len(text) / 50)

        # Factor in score separation
        sorted_scores = sorted(scores.values(), reverse=True)
        if len(sorted_scores) >= 2:
            separation = (sorted_scores[0] - sorted_scores[1]) / 100
            separation_factor = min(1.0, separation * 2)
        else:
            separation_factor = 0.5

        # Combine factors
        confidence = (length_factor * 0.4 + separation_factor * 0.6)

        return round(confidence, 2)
