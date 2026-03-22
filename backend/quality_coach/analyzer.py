"""
Quality Analyzer for Customer Support Conversations.

Uses ZAI SDK (LLM) to analyze conversation quality and provide scores
for accuracy, empathy, and efficiency.

CRITICAL: Scores accuracy/empathy/efficiency (0-100) for each interaction.

Features:
- Analyze conversation quality
- Score accuracy (correctness of information)
- Score empathy (emotional intelligence)
- Score efficiency (resolution effectiveness)
- Generate improvement recommendations
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
import json

from shared.core_functions.logger import get_logger

# Import ZAI SDK for LLM
try:
    from z_ai_web_dev_sdk import ZAI
except ImportError:
    ZAI = None

logger = get_logger(__name__)


class QualityLevel(str, Enum):
    """Quality level classification."""
    EXCELLENT = "excellent"  # 90-100
    GOOD = "good"  # 70-89
    ACCEPTABLE = "acceptable"  # 50-69
    POOR = "poor"  # 25-49
    CRITICAL = "critical"  # 0-24


@dataclass
class QualityScores:
    """Quality scores for a conversation."""
    accuracy_score: float = 0.0
    empathy_score: float = 0.0
    efficiency_score: float = 0.0
    overall_score: float = 0.0
    level: QualityLevel = QualityLevel.ACCEPTABLE


@dataclass
class QualityAnalysisResult:
    """Result of quality analysis."""
    interaction_id: str
    company_id: str
    scores: QualityScores
    recommendations: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    areas_for_improvement: List[str] = field(default_factory=list)
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_response: Optional[str] = None


class QualityAnalyzer:
    """
    AI-powered Quality Analyzer for customer support conversations.

    Uses ZAI SDK (LLM) to analyze conversation quality and provide
    actionable insights for improvement.

    CRITICAL: Provides scores for accuracy, empathy, and efficiency.

    Example:
        analyzer = QualityAnalyzer()
        result = await analyzer.analyze_conversation("interaction_123")
        print(result.scores.accuracy_score)  # 0-100
        print(result.scores.empathy_score)   # 0-100
        print(result.scores.efficiency_score) # 0-100
    """

    # Quality thresholds
    EXCELLENT_THRESHOLD = 90
    GOOD_THRESHOLD = 70
    ACCEPTABLE_THRESHOLD = 50
    POOR_THRESHOLD = 25

    # Low quality alert threshold
    LOW_QUALITY_THRESHOLD = 50

    def __init__(
        self,
        use_llm: bool = True
    ) -> None:
        """
        Initialize Quality Analyzer.

        Args:
            use_llm: Whether to use LLM for analysis (default True)
        """
        self.use_llm = use_llm
        self._interactions: Dict[str, Dict[str, Any]] = {}
        self._analyses: Dict[str, QualityAnalysisResult] = {}

        # Initialize ZAI SDK
        self._zai = None
        if use_llm and ZAI is not None:
            try:
                import asyncio
                self._zai = asyncio.get_event_loop().run_until_complete(ZAI.create())
                logger.info({
                    "event": "quality_analyzer_llm_initialized",
                    "provider": "ZAI SDK"
                })
            except Exception as e:
                logger.warning({
                    "event": "quality_analyzer_llm_init_failed",
                    "error": str(e),
                    "fallback": "Using rule-based analysis"
                })
                self._zai = None

        logger.info({
            "event": "quality_analyzer_initialized",
            "use_llm": use_llm,
            "llm_available": self._zai is not None
        })

    async def analyze_conversation(
        self,
        interaction_id: str,
        conversation: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a conversation for quality metrics.

        CRITICAL: Returns scores for accuracy, empathy, efficiency.

        Args:
            interaction_id: Interaction/conversation identifier
            conversation: Optional conversation data (will use stored if not provided)

        Returns:
            Dict with quality analysis including:
            - accuracy_score: float (0-100)
            - empathy_score: float (0-100)
            - efficiency_score: float (0-100)
            - overall_score: float (0-100)
            - recommendations: list of improvement suggestions
        """
        logger.info({
            "event": "quality_analysis_started",
            "interaction_id": interaction_id
        })

        # Get conversation data
        if conversation is None:
            conversation = self._interactions.get(interaction_id, {})

        # Try LLM-based analysis first
        if self._zai is not None:
            try:
                result = await self._analyze_with_llm(interaction_id, conversation)
                if result:
                    self._analyses[interaction_id] = result
                    return self._result_to_dict(result)
            except Exception as e:
                logger.warning({
                    "event": "llm_analysis_failed",
                    "interaction_id": interaction_id,
                    "error": str(e),
                    "fallback": "Using rule-based analysis"
                })

        # Fallback to rule-based analysis
        result = await self._analyze_with_rules(interaction_id, conversation)
        self._analyses[interaction_id] = result

        logger.info({
            "event": "quality_analysis_completed",
            "interaction_id": interaction_id,
            "overall_score": result.scores.overall_score
        })

        return self._result_to_dict(result)

    async def _analyze_with_llm(
        self,
        interaction_id: str,
        conversation: Dict[str, Any]
    ) -> Optional[QualityAnalysisResult]:
        """
        Analyze conversation using LLM via ZAI SDK.

        Args:
            interaction_id: Interaction identifier
            conversation: Conversation data

        Returns:
            QualityAnalysisResult or None if failed
        """
        if self._zai is None:
            return None

        # Build prompt for quality analysis
        messages = conversation.get("messages", [])
        company_id = conversation.get("company_id", "default")

        prompt = self._build_analysis_prompt(messages)

        try:
            completion = await self._zai.chat.completions.create({
                "messages": [
                    {
                        "role": "system",
                        "content": """You are a quality assurance analyst for customer support conversations.
Analyze the conversation and provide scores (0-100) for:
1. Accuracy: Correctness of information provided
2. Empathy: Emotional intelligence and customer care
3. Efficiency: Resolution effectiveness and time management

Respond in JSON format:
{
  "accuracy_score": <0-100>,
  "empathy_score": <0-100>,
  "efficiency_score": <0-100>,
  "overall_score": <0-100>,
  "recommendations": ["recommendation1", "recommendation2"],
  "strengths": ["strength1", "strength2"],
  "areas_for_improvement": ["area1", "area2"]
}"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.3
            })

            response_text = "{}"
            if completion and completion.choices:
                response_text = completion.choices[0].message.content or "{}"

            # Parse response
            scores_data = self._parse_llm_response(response_text)

            scores = QualityScores(
                accuracy_score=scores_data.get("accuracy_score", 75.0),
                empathy_score=scores_data.get("empathy_score", 75.0),
                efficiency_score=scores_data.get("efficiency_score", 75.0),
                overall_score=scores_data.get("overall_score", 75.0)
            )
            scores.level = self._get_quality_level(scores.overall_score)

            result = QualityAnalysisResult(
                interaction_id=interaction_id,
                company_id=company_id,
                scores=scores,
                recommendations=scores_data.get("recommendations", []),
                strengths=scores_data.get("strengths", []),
                areas_for_improvement=scores_data.get("areas_for_improvement", []),
                raw_response=response_text
            )

            logger.info({
                "event": "llm_analysis_completed",
                "interaction_id": interaction_id,
                "accuracy": scores.accuracy_score,
                "empathy": scores.empathy_score,
                "efficiency": scores.efficiency_score
            })

            return result

        except Exception as e:
            logger.error({
                "event": "llm_analysis_error",
                "interaction_id": interaction_id,
                "error": str(e)
            })
            return None

    def _build_analysis_prompt(
        self,
        messages: List[Dict[str, Any]]
    ) -> str:
        """Build analysis prompt from messages."""
        if not messages:
            return "No conversation to analyze."

        conversation_text = "\n".join([
            f"{m.get('role', 'unknown')}: {m.get('content', '')}"
            for m in messages
        ])

        return f"""Analyze this customer support conversation:

{conversation_text}

Provide quality scores and recommendations."""

    def _parse_llm_response(
        self,
        response: str
    ) -> Dict[str, Any]:
        """Parse LLM response to extract scores."""
        try:
            # Try to extract JSON from response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                return json.loads(json_str)
        except Exception:
            pass

        # Return defaults
        return {
            "accuracy_score": 75.0,
            "empathy_score": 75.0,
            "efficiency_score": 75.0,
            "overall_score": 75.0,
            "recommendations": [],
            "strengths": [],
            "areas_for_improvement": []
        }

    async def _analyze_with_rules(
        self,
        interaction_id: str,
        conversation: Dict[str, Any]
    ) -> QualityAnalysisResult:
        """
        Analyze conversation using rule-based approach.

        Args:
            interaction_id: Interaction identifier
            conversation: Conversation data

        Returns:
            QualityAnalysisResult
        """
        messages = conversation.get("messages", [])
        company_id = conversation.get("company_id", "default")

        # Calculate scores based on rules
        accuracy_score = await self.score_accuracy(conversation)
        empathy_score = await self.score_empathy(conversation)
        efficiency_score = await self.score_efficiency(conversation)

        # Calculate overall score (weighted average)
        overall_score = (
            accuracy_score * 0.4 +
            empathy_score * 0.3 +
            efficiency_score * 0.3
        )

        scores = QualityScores(
            accuracy_score=accuracy_score,
            empathy_score=empathy_score,
            efficiency_score=efficiency_score,
            overall_score=overall_score
        )
        scores.level = self._get_quality_level(overall_score)

        # Generate recommendations
        recommendations = self._generate_recommendations(scores)

        result = QualityAnalysisResult(
            interaction_id=interaction_id,
            company_id=company_id,
            scores=scores,
            recommendations=recommendations,
            strengths=self._identify_strengths(scores),
            areas_for_improvement=self._identify_improvements(scores)
        )

        return result

    async def score_accuracy(
        self,
        interaction: Dict[str, Any]
    ) -> float:
        """
        Score accuracy (correctness of information).

        Args:
            interaction: Interaction data

        Returns:
            Score 0-100
        """
        base_score = 80.0

        messages = interaction.get("messages", [])
        if not messages:
            return base_score

        # Check for resolution
        if interaction.get("resolved"):
            base_score += 10

        # Check for escalation (might indicate complexity)
        if interaction.get("escalated"):
            base_score -= 5

        # Check message count (too many might indicate confusion)
        if len(messages) > 20:
            base_score -= 5

        # Check for follow-up needed
        if interaction.get("follow_up_needed"):
            base_score -= 5

        return min(100, max(0, base_score))

    async def score_empathy(
        self,
        interaction: Dict[str, Any]
    ) -> float:
        """
        Score empathy (emotional intelligence).

        Args:
            interaction: Interaction data

        Returns:
            Score 0-100
        """
        base_score = 75.0

        messages = interaction.get("messages", [])
        if not messages:
            return base_score

        # Check for positive sentiment
        sentiment = interaction.get("sentiment", "neutral")
        if sentiment == "positive":
            base_score += 10
        elif sentiment == "negative":
            base_score -= 5

        # Check for customer satisfaction
        satisfaction = interaction.get("customer_satisfaction")
        if satisfaction:
            if satisfaction >= 4:  # Out of 5
                base_score += 10
            elif satisfaction < 3:
                base_score -= 10

        # Check for apology/acknowledgment keywords
        text = " ".join([m.get("content", "") for m in messages]).lower()
        empathy_keywords = ["sorry", "apologize", "understand", "frustrating", "help"]
        keyword_count = sum(1 for kw in empathy_keywords if kw in text)
        base_score += min(5, keyword_count * 2)

        return min(100, max(0, base_score))

    async def score_efficiency(
        self,
        interaction: Dict[str, Any]
    ) -> float:
        """
        Score efficiency (resolution effectiveness).

        Args:
            interaction: Interaction data

        Returns:
            Score 0-100
        """
        base_score = 75.0

        # Check resolution time
        resolution_time_minutes = interaction.get("resolution_time_minutes", 0)
        if resolution_time_minutes > 0:
            if resolution_time_minutes < 5:
                base_score += 15
            elif resolution_time_minutes < 15:
                base_score += 10
            elif resolution_time_minutes < 30:
                base_score += 5
            elif resolution_time_minutes > 60:
                base_score -= 10
            elif resolution_time_minutes > 120:
                base_score -= 15

        # Check if resolved in first contact
        if interaction.get("first_contact_resolution"):
            base_score += 10

        # Check message count efficiency
        messages = interaction.get("messages", [])
        if len(messages) > 0:
            if len(messages) <= 4:
                base_score += 10
            elif len(messages) <= 8:
                base_score += 5
            elif len(messages) > 15:
                base_score -= 5

        return min(100, max(0, base_score))

    def _get_quality_level(
        self,
        score: float
    ) -> QualityLevel:
        """Determine quality level from score."""
        if score >= self.EXCELLENT_THRESHOLD:
            return QualityLevel.EXCELLENT
        elif score >= self.GOOD_THRESHOLD:
            return QualityLevel.GOOD
        elif score >= self.ACCEPTABLE_THRESHOLD:
            return QualityLevel.ACCEPTABLE
        elif score >= self.POOR_THRESHOLD:
            return QualityLevel.POOR
        return QualityLevel.CRITICAL

    def _generate_recommendations(
        self,
        scores: QualityScores
    ) -> List[str]:
        """Generate improvement recommendations."""
        recommendations = []

        if scores.accuracy_score < 70:
            recommendations.append("Review knowledge base for accurate information")

        if scores.empathy_score < 70:
            recommendations.append("Practice active listening techniques")

        if scores.efficiency_score < 70:
            recommendations.append("Focus on quicker resolution paths")

        if scores.overall_score < 60:
            recommendations.append("Consider additional training session")

        return recommendations

    def _identify_strengths(
        self,
        scores: QualityScores
    ) -> List[str]:
        """Identify conversation strengths."""
        strengths = []

        if scores.accuracy_score >= 85:
            strengths.append("Provided accurate information")
        if scores.empathy_score >= 85:
            strengths.append("Demonstrated strong empathy")
        if scores.efficiency_score >= 85:
            strengths.append("Resolved efficiently")

        return strengths

    def _identify_improvements(
        self,
        scores: QualityScores
    ) -> List[str]:
        """Identify areas for improvement."""
        areas = []

        if scores.accuracy_score < 70:
            areas.append("Information accuracy needs improvement")
        if scores.empathy_score < 70:
            areas.append("Empathy could be enhanced")
        if scores.efficiency_score < 70:
            areas.append("Resolution efficiency can be improved")

        return areas

    def _result_to_dict(
        self,
        result: QualityAnalysisResult
    ) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "success": True,
            "interaction_id": result.interaction_id,
            "company_id": result.company_id,
            "accuracy_score": result.scores.accuracy_score,
            "empathy_score": result.scores.empathy_score,
            "efficiency_score": result.scores.efficiency_score,
            "overall_score": result.scores.overall_score,
            "quality_level": result.scores.level.value,
            "recommendations": result.recommendations,
            "strengths": result.strengths,
            "areas_for_improvement": result.areas_for_improvement,
            "analyzed_at": result.analyzed_at.isoformat()
        }

    def register_interaction(
        self,
        interaction_id: str,
        company_id: str,
        messages: List[Dict[str, Any]],
        **kwargs
    ) -> None:
        """Register an interaction for analysis."""
        self._interactions[interaction_id] = {
            "interaction_id": interaction_id,
            "company_id": company_id,
            "messages": messages,
            **kwargs
        }

    def get_analysis(
        self,
        interaction_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get previous analysis for an interaction."""
        result = self._analyses.get(interaction_id)
        if result:
            return self._result_to_dict(result)
        return None

    def get_low_quality_interactions(
        self,
        company_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get interactions with low quality scores."""
        low_quality = []

        for result in self._analyses.values():
            if result.scores.overall_score < self.LOW_QUALITY_THRESHOLD:
                if company_id is None or result.company_id == company_id:
                    low_quality.append(self._result_to_dict(result))

        return low_quality

    def get_status(self) -> Dict[str, Any]:
        """Get analyzer status."""
        return {
            "use_llm": self.use_llm,
            "llm_available": self._zai is not None,
            "total_interactions": len(self._interactions),
            "total_analyses": len(self._analyses),
            "low_quality_threshold": self.LOW_QUALITY_THRESHOLD
        }


def get_quality_analyzer(use_llm: bool = True) -> QualityAnalyzer:
    """
    Get a QualityAnalyzer instance.

    Args:
        use_llm: Whether to use LLM for analysis

    Returns:
        QualityAnalyzer instance
    """
    return QualityAnalyzer(use_llm=use_llm)
