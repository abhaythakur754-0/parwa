"""
PARWA TRIVYA Tier 2 Trigger Detector.

Analyzes queries to determine which Tier 2 reasoning techniques
should be applied based on query characteristics and complexity.
"""
from typing import Optional, Dict, Any, List, Set
from enum import Enum
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class TriggerType(str, Enum):
    """Types of T2 technique triggers."""
    CHAIN_OF_THOUGHT = "chain_of_thought"
    REACT = "react"
    REVERSE_THINKING = "reverse_thinking"
    STEP_BACK = "step_back"
    THREAD_OF_THOUGHT = "thread_of_thought"
    NONE = "none"


class TriggerResult(BaseModel):
    """Result from trigger detection."""
    query: str
    triggered_techniques: List[TriggerType] = Field(default_factory=list)
    primary_technique: TriggerType = TriggerType.NONE
    complexity_indicators: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str = ""
    processing_time_ms: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class TriggerPatterns:
    """Pattern definitions for trigger detection."""

    # Decision-making patterns
    DECISION_PATTERNS = [
        "should i", "which one", "choose between", "decide",
        "better option", "best choice", "recommend", "prefer",
        "difference between", "compare", "versus", "vs",
    ]

    # Multi-step patterns
    MULTI_STEP_PATTERNS = [
        "how do i", "how to", "steps to", "process for",
        "guide me", "walk me through", "explain how",
        "what are the steps", "procedure", "instructions",
    ]

    # Problem-solving patterns
    PROBLEM_PATTERNS = [
        "why is", "what's wrong", "not working", "error",
        "problem with", "issue", "troubleshoot", "fix",
        "resolve", "debug", "diagnose",
    ]

    # Tool/action patterns (for ReAct)
    ACTION_PATTERNS = [
        "check my", "look up", "find my", "get my",
        "show me my", "what's my", "can you access",
        "retrieve", "fetch", "search for",
    ]

    # Goal-oriented patterns (for reverse thinking)
    GOAL_PATTERNS = [
        "i want to", "i need to", "goal is", "trying to achieve",
        "how can i get to", "target", "objective", "aim is",
    ]

    # Abstract/conceptual patterns (for step-back)
    ABSTRACT_PATTERNS = [
        "understand", "concept of", "what is", "explain the",
        "principle", "theory", "why does", "how come",
        "what causes", "fundamental",
    ]

    # Exploration patterns (for thread of thought)
    EXPLORATION_PATTERNS = [
        "tell me about", "explore", "elaborate", "more details",
        "expand on", "dig deeper", "all aspects", "comprehensive",
        "thorough", "in-depth",
    ]


class TriggerDetector:
    """
    Trigger Detector for TRIVYA Tier 2.

    Analyzes query characteristics to determine which T2 techniques
    should be applied. T2 techniques are conditional and only fire
    when the query complexity or type warrants deeper reasoning.

    Features:
    - Pattern-based trigger detection
    - Multi-technique support
    - Confidence scoring
    - Composable with T1 pipeline
    """

    def __init__(
        self,
        enable_all_techniques: bool = True,
        min_confidence_threshold: float = 0.5,
        max_techniques_per_query: int = 2
    ) -> None:
        """
        Initialize Trigger Detector.

        Args:
            enable_all_techniques: Whether all techniques are available
            min_confidence_threshold: Minimum confidence to trigger
            max_techniques_per_query: Max T2 techniques to apply
        """
        self.enable_all_techniques = enable_all_techniques
        self.min_confidence = min_confidence_threshold
        self.max_techniques = max_techniques_per_query

        # Performance tracking
        self._queries_analyzed = 0
        self._total_processing_time = 0.0

        logger.info({
            "event": "trigger_detector_initialized",
            "min_confidence": min_confidence_threshold,
            "max_techniques": max_techniques_per_query,
        })

    def detect(
        self,
        query: str,
        context: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> TriggerResult:
        """
        Detect which T2 techniques should fire for a query.

        Args:
            query: User query text
            context: Optional context from T1 (CLARA)
            conversation_history: Optional conversation history

        Returns:
            TriggerResult with triggered techniques and reasoning

        Raises:
            ValueError: If query is empty
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        start_time = datetime.now()
        query_lower = query.lower().strip()

        # Analyze query for patterns
        indicators = self._analyze_patterns(query_lower)

        # Determine triggered techniques
        triggered = self._determine_triggers(indicators)

        # Select primary technique
        primary = self._select_primary(triggered, indicators)

        # Build result
        result = TriggerResult(
            query=query,
            triggered_techniques=triggered[:self.max_techniques],
            primary_technique=primary,
            complexity_indicators=indicators,
            confidence=indicators.get("overall_confidence", 0.0),
            reasoning=self._build_reasoning(triggered, indicators),
        )

        # Finalize
        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        self._queries_analyzed += 1
        self._total_processing_time += result.processing_time_ms

        logger.info({
            "event": "trigger_detection_complete",
            "triggered_count": len(triggered),
            "primary_technique": primary.value,
            "confidence": result.confidence,
            "processing_time_ms": result.processing_time_ms,
        })

        return result

    def should_fire_t2(
        self,
        query: str,
        complexity_score: Optional[float] = None
    ) -> bool:
        """
        Determine if any T2 technique should fire.

        Args:
            query: User query text
            complexity_score: Optional pre-computed complexity

        Returns:
            True if T2 should fire
        """
        if not query or not query.strip():
            return False

        query_lower = query.lower().strip()

        # Check for any trigger patterns
        has_decision = any(p in query_lower for p in TriggerPatterns.DECISION_PATTERNS)
        has_multi_step = any(p in query_lower for p in TriggerPatterns.MULTI_STEP_PATTERNS)
        has_problem = any(p in query_lower for p in TriggerPatterns.PROBLEM_PATTERNS)
        has_action = any(p in query_lower for p in TriggerPatterns.ACTION_PATTERNS)
        has_goal = any(p in query_lower for p in TriggerPatterns.GOAL_PATTERNS)

        # Check complexity score if provided
        high_complexity = complexity_score is not None and complexity_score > 0.7

        return any([has_decision, has_multi_step, has_problem, has_action, has_goal, high_complexity])

    def get_stats(self) -> Dict[str, Any]:
        """
        Get trigger detector statistics.

        Returns:
            Dict with stats
        """
        return {
            "queries_analyzed": self._queries_analyzed,
            "total_processing_time_ms": self._total_processing_time,
            "average_processing_time_ms": (
                self._total_processing_time / self._queries_analyzed
                if self._queries_analyzed > 0 else 0
            ),
        }

    def _analyze_patterns(self, query: str) -> Dict[str, Any]:
        """
        Analyze query for trigger patterns.

        Args:
            query: Lowercase query

        Returns:
            Dict with pattern matches
        """
        indicators = {
            "decision_needed": [],
            "multi_step": [],
            "problem_solving": [],
            "action_required": [],
            "goal_oriented": [],
            "abstract_reasoning": [],
            "exploration": [],
            "overall_confidence": 0.0,
        }

        # Check each pattern category
        for pattern in TriggerPatterns.DECISION_PATTERNS:
            if pattern in query:
                indicators["decision_needed"].append(pattern)

        for pattern in TriggerPatterns.MULTI_STEP_PATTERNS:
            if pattern in query:
                indicators["multi_step"].append(pattern)

        for pattern in TriggerPatterns.PROBLEM_PATTERNS:
            if pattern in query:
                indicators["problem_solving"].append(pattern)

        for pattern in TriggerPatterns.ACTION_PATTERNS:
            if pattern in query:
                indicators["action_required"].append(pattern)

        for pattern in TriggerPatterns.GOAL_PATTERNS:
            if pattern in query:
                indicators["goal_oriented"].append(pattern)

        for pattern in TriggerPatterns.ABSTRACT_PATTERNS:
            if pattern in query:
                indicators["abstract_reasoning"].append(pattern)

        for pattern in TriggerPatterns.EXPLORATION_PATTERNS:
            if pattern in query:
                indicators["exploration"].append(pattern)

        # Calculate overall confidence
        total_matches = sum(
            len(v) for k, v in indicators.items()
            if isinstance(v, list)
        )
        indicators["overall_confidence"] = min(1.0, total_matches * 0.15)

        return indicators

    def _determine_triggers(
        self,
        indicators: Dict[str, Any]
    ) -> List[TriggerType]:
        """
        Determine which techniques to trigger.

        Args:
            indicators: Pattern analysis results

        Returns:
            List of triggered techniques
        """
        triggered = []

        # Decision queries -> Chain of Thought or Step Back
        if indicators["decision_needed"]:
            triggered.append(TriggerType.CHAIN_OF_THOUGHT)

        # Action queries -> ReAct
        if indicators["action_required"]:
            triggered.append(TriggerType.REACT)

        # Goal-oriented -> Reverse Thinking
        if indicators["goal_oriented"]:
            triggered.append(TriggerType.REVERSE_THINKING)

        # Abstract queries -> Step Back
        if indicators["abstract_reasoning"]:
            triggered.append(TriggerType.STEP_BACK)

        # Exploration queries -> Thread of Thought
        if indicators["exploration"]:
            triggered.append(TriggerType.THREAD_OF_THOUGHT)

        # Multi-step or problem -> Chain of Thought
        if indicators["multi_step"] or indicators["problem_solving"]:
            if TriggerType.CHAIN_OF_THOUGHT not in triggered:
                triggered.append(TriggerType.CHAIN_OF_THOUGHT)

        return triggered

    def _select_primary(
        self,
        triggered: List[TriggerType],
        indicators: Dict[str, Any]
    ) -> TriggerType:
        """
        Select the primary technique to use.

        Args:
            triggered: List of triggered techniques
            indicators: Pattern analysis results

        Returns:
            Primary TriggerType
        """
        if not triggered:
            return TriggerType.NONE

        # Priority ordering
        priority = [
            (TriggerType.REACT, indicators.get("action_required", [])),
            (TriggerType.CHAIN_OF_THOUGHT, indicators.get("decision_needed", [])),
            (TriggerType.REVERSE_THINKING, indicators.get("goal_oriented", [])),
            (TriggerType.STEP_BACK, indicators.get("abstract_reasoning", [])),
            (TriggerType.THREAD_OF_THOUGHT, indicators.get("exploration", [])),
        ]

        # Return highest priority with matches
        for technique, matches in priority:
            if technique in triggered and matches:
                return technique

        # Default to first triggered
        return triggered[0] if triggered else TriggerType.NONE

    def _build_reasoning(
        self,
        triggered: List[TriggerType],
        indicators: Dict[str, Any]
    ) -> str:
        """
        Build reasoning explanation for triggers.

        Args:
            triggered: Triggered techniques
            indicators: Pattern analysis

        Returns:
            Reasoning string
        """
        if not triggered:
            return "No T2 techniques triggered - query appears simple"

        reasons = []
        if indicators["decision_needed"]:
            reasons.append("decision-making detected")
        if indicators["action_required"]:
            reasons.append("action/tools needed")
        if indicators["goal_oriented"]:
            reasons.append("goal-oriented query")
        if indicators["abstract_reasoning"]:
            reasons.append("abstract reasoning required")
        if indicators["exploration"]:
            reasons.append("exploration requested")
        if indicators["multi_step"]:
            reasons.append("multi-step process")
        if indicators["problem_solving"]:
            reasons.append("problem-solving needed")

        return f"Triggered: {', '.join(t.value for t in triggered)}. Reasons: {'; '.join(reasons)}"
