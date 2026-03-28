"""
Response Quality Scoring Module

This module provides comprehensive response quality scoring for AI-generated responses.
It includes multiple quality metrics and a configurable scoring system.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
import re
import math


class QualityMetric(Enum):
    """Enumeration of quality metrics for response evaluation."""
    RELEVANCE = "relevance"
    COHERENCE = "coherence"
    ACCURACY = "accuracy"
    HELPFULNESS = "helpfulness"


class QualityLevel(Enum):
    """Quality level classification based on scores."""
    EXCELLENT = "excellent"  # 90-100
    GOOD = "good"          # 70-89
    ACCEPTABLE = "acceptable"  # 50-69
    POOR = "poor"          # 30-49
    UNACCEPTABLE = "unacceptable"  # 0-29


@dataclass
class QualityScore:
    """
    Dataclass representing quality scores for a response.
    
    Attributes:
        overall: Overall quality score (0-100)
        per_metric: Dictionary of per-metric scores
        level: Quality level classification
        timestamp: When the score was calculated
        metadata: Additional metadata about the scoring
    """
    overall: float
    per_metric: Dict[QualityMetric, float] = field(default_factory=dict)
    level: QualityLevel = QualityLevel.ACCEPTABLE
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate quality level based on overall score."""
        if self.overall >= 90:
            self.level = QualityLevel.EXCELLENT
        elif self.overall >= 70:
            self.level = QualityLevel.GOOD
        elif self.overall >= 50:
            self.level = QualityLevel.ACCEPTABLE
        elif self.overall >= 30:
            self.level = QualityLevel.POOR
        else:
            self.level = QualityLevel.UNACCEPTABLE
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert quality score to dictionary representation."""
        return {
            "overall": self.overall,
            "per_metric": {m.value: v for m, v in self.per_metric.items()},
            "level": self.level.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
    
    def get_metric_score(self, metric: QualityMetric) -> float:
        """Get score for a specific metric."""
        return self.per_metric.get(metric, 0.0)
    
    def is_passing(self, threshold: float = 50.0) -> bool:
        """Check if the score meets the passing threshold."""
        return self.overall >= threshold


@dataclass
class ScoringThreshold:
    """
    Configuration for scoring thresholds.
    
    Attributes:
        minimum_score: Minimum acceptable score
        excellent_threshold: Threshold for excellent quality
        good_threshold: Threshold for good quality
        acceptable_threshold: Threshold for acceptable quality
        metric_weights: Weights for each metric in overall score calculation
    """
    minimum_score: float = 50.0
    excellent_threshold: float = 90.0
    good_threshold: float = 70.0
    acceptable_threshold: float = 50.0
    metric_weights: Dict[QualityMetric, float] = field(default_factory=lambda: {
        QualityMetric.RELEVANCE: 0.25,
        QualityMetric.COHERENCE: 0.25,
        QualityMetric.ACCURACY: 0.25,
        QualityMetric.HELPFULNESS: 0.25
    })
    
    def get_weight(self, metric: QualityMetric) -> float:
        """Get weight for a specific metric."""
        return self.metric_weights.get(metric, 0.25)
    
    def validate(self) -> bool:
        """Validate that weights sum to approximately 1.0."""
        total_weight = sum(self.metric_weights.values())
        return abs(total_weight - 1.0) < 0.01


class ResponseQualityScorer:
    """
    Main class for scoring response quality.
    
    This class provides methods to evaluate AI-generated responses
    across multiple quality dimensions.
    """
    
    def __init__(self, threshold: Optional[ScoringThreshold] = None):
        """
        Initialize the response quality scorer.
        
        Args:
            threshold: Scoring threshold configuration. Uses defaults if not provided.
        """
        self.threshold = threshold or ScoringThreshold()
        self._scorers: Dict[QualityMetric, Callable] = {
            QualityMetric.RELEVANCE: self._score_relevance,
            QualityMetric.COHERENCE: self._score_coherence,
            QualityMetric.ACCURACY: self._score_accuracy,
            QualityMetric.HELPFULNESS: self._score_helpfulness,
        }
        self._history: List[QualityScore] = []
    
    def score(
        self,
        response: str,
        context: Optional[str] = None,
        expected_facts: Optional[List[str]] = None,
        metrics: Optional[List[QualityMetric]] = None
    ) -> QualityScore:
        """
        Score a response across multiple quality dimensions.
        
        Args:
            response: The AI-generated response to score
            context: Optional context for relevance evaluation
            expected_facts: Optional list of facts that should be present
            metrics: Optional list of specific metrics to evaluate
        
        Returns:
            QualityScore object with overall and per-metric scores
        """
        if not response or not response.strip():
            return QualityScore(
                overall=0.0,
                per_metric={m: 0.0 for m in (metrics or list(QualityMetric))},
                metadata={"error": "Empty response"}
            )
        
        metrics_to_score = metrics or list(QualityMetric)
        per_metric: Dict[QualityMetric, float] = {}
        
        for metric in metrics_to_score:
            scorer = self._scorers.get(metric)
            if scorer:
                if metric == QualityMetric.ACCURACY and expected_facts:
                    score = scorer(response, expected_facts)
                elif metric == QualityMetric.RELEVANCE and context:
                    score = scorer(response, context)
                else:
                    score = scorer(response)
                per_metric[metric] = score
        
        # Calculate weighted overall score
        overall = self._calculate_overall(per_metric)
        
        quality_score = QualityScore(
            overall=overall,
            per_metric=per_metric,
            metadata={
                "response_length": len(response),
                "context_provided": context is not None,
                "expected_facts_provided": expected_facts is not None
            }
        )
        
        self._history.append(quality_score)
        return quality_score
    
    def _calculate_overall(self, per_metric: Dict[QualityMetric, float]) -> float:
        """Calculate weighted overall score from per-metric scores."""
        if not per_metric:
            return 0.0
        
        total_weight = 0.0
        weighted_sum = 0.0
        
        for metric, score in per_metric.items():
            weight = self.threshold.get_weight(metric)
            weighted_sum += score * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        return min(100.0, max(0.0, weighted_sum / total_weight))
    
    def _score_relevance(self, response: str, context: Optional[str] = None) -> float:
        """
        Score relevance of response to the context.
        
        Evaluates how well the response addresses the query or context.
        """
        if not context:
            # Without context, use heuristics
            return self._relevance_heuristics(response)
        
        # Check keyword overlap
        context_words = set(re.findall(r'\b\w+\b', context.lower()))
        response_words = set(re.findall(r'\b\w+\b', response.lower()))
        
        if not context_words:
            return 50.0
        
        overlap = len(context_words & response_words)
        relevance_ratio = overlap / len(context_words)
        
        # Scale to 0-100
        return min(100.0, relevance_ratio * 150)
    
    def _relevance_heuristics(self, response: str) -> float:
        """Apply heuristics for relevance when no context is available."""
        score = 50.0  # Base score
        
        # Check for generic/placeholder content
        generic_phrases = ["i don't know", "i'm not sure", "as an ai", "i cannot"]
        response_lower = response.lower()
        
        for phrase in generic_phrases:
            if phrase in response_lower:
                score -= 10
        
        # Check for substantive content
        words = response.split()
        if len(words) > 50:
            score += 10
        if len(words) > 100:
            score += 5
        
        return min(100.0, max(0.0, score))
    
    def _score_coherence(self, response: str) -> float:
        """
        Score coherence of the response.
        
        Evaluates logical flow, structure, and readability.
        """
        if not response.strip():
            return 0.0
        
        score = 100.0
        sentences = re.split(r'[.!?]+', response)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return 0.0
        
        # Check average sentence length (too long or too short is bad)
        avg_length = sum(len(s.split()) for s in sentences) / len(sentences)
        if avg_length < 5:
            score -= 20
        elif avg_length > 40:
            score -= 15
        
        # Check for repeated content
        unique_sentences = set(s.lower() for s in sentences)
        repetition_ratio = 1 - (len(unique_sentences) / len(sentences))
        score -= repetition_ratio * 30
        
        # Check for transition words (improves coherence)
        transition_words = ["however", "therefore", "additionally", "furthermore", 
                          "moreover", "consequently", "meanwhile", "similarly"]
        transition_count = sum(1 for w in transition_words if w in response.lower())
        score += min(10, transition_count * 2)
        
        # Check for proper punctuation
        if not response.endswith(('.', '!', '?')):
            score -= 5
        
        return min(100.0, max(0.0, score))
    
    def _score_accuracy(self, response: str, expected_facts: Optional[List[str]] = None) -> float:
        """
        Score accuracy of the response.
        
        Evaluates factual correctness based on expected facts.
        """
        if not expected_facts:
            return 75.0  # Default score when no facts to check
        
        response_lower = response.lower()
        matched_facts = 0
        
        for fact in expected_facts:
            fact_lower = fact.lower()
            # Check if fact or key parts are present
            if fact_lower in response_lower:
                matched_facts += 1
            else:
                # Check for partial matches on key terms
                fact_words = set(fact_lower.split())
                response_words = set(response_lower.split())
                if len(fact_words & response_words) >= len(fact_words) * 0.5:
                    matched_facts += 0.5
        
        accuracy_ratio = matched_facts / len(expected_facts)
        return min(100.0, accuracy_ratio * 100)
    
    def _score_helpfulness(self, response: str) -> float:
        """
        Score helpfulness of the response.
        
        Evaluates whether the response provides actionable, useful information.
        """
        if not response.strip():
            return 0.0
        
        score = 50.0  # Base score
        response_lower = response.lower()
        
        # Check for actionable language
        actionable_patterns = [
            r'you can', r'you should', r'try to', r'make sure',
            r'ensure that', r'consider', r'recommend', r'suggest',
            r'follow these', r'steps to', r'how to'
        ]
        for pattern in actionable_patterns:
            if re.search(pattern, response_lower):
                score += 5
        
        # Check for examples
        if re.search(r'for example|rfor instance|such as|e\.g\.', response_lower):
            score += 10
        
        # Check for unhelpful patterns
        unhelpful_patterns = [
            r'i cannot (help|assist|provide)',
            r'i (don\'t|do not) have (access|information)',
            r'please contact',
            r'consult with'
        ]
        for pattern in unhelpful_patterns:
            if re.search(pattern, response_lower):
                score -= 10
        
        # Check for specific information (numbers, dates, names)
        if re.search(r'\d+', response):
            score += 5
        
        return min(100.0, max(0.0, score))
    
    def get_history(self, limit: int = 10) -> List[QualityScore]:
        """Get recent scoring history."""
        return self._history[-limit:]
    
    def get_average_score(self) -> float:
        """Get average score from history."""
        if not self._history:
            return 0.0
        return sum(s.overall for s in self._history) / len(self._history)
    
    def clear_history(self) -> None:
        """Clear scoring history."""
        self._history = []
    
    def add_custom_scorer(
        self,
        metric: QualityMetric,
        scorer: Callable[[str], float]
    ) -> None:
        """
        Add or replace a custom scorer for a metric.
        
        Args:
            metric: The metric to add scorer for
            scorer: Callable that takes response and returns score
        """
        self._scorers[metric] = scorer
    
    def batch_score(
        self,
        responses: List[str],
        contexts: Optional[List[str]] = None,
        expected_facts_list: Optional[List[List[str]]] = None
    ) -> List[QualityScore]:
        """
        Score multiple responses in batch.
        
        Args:
            responses: List of responses to score
            contexts: Optional list of contexts (one per response)
            expected_facts_list: Optional list of expected facts lists
        
        Returns:
            List of QualityScore objects
        """
        results = []
        for i, response in enumerate(responses):
            context = contexts[i] if contexts and i < len(contexts) else None
            expected_facts = (expected_facts_list[i] if expected_facts_list 
                            and i < len(expected_facts_list) else None)
            results.append(self.score(response, context, expected_facts))
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about scoring history."""
        if not self._history:
            return {
                "total_scores": 0,
                "average_score": 0.0,
                "min_score": 0.0,
                "max_score": 0.0,
                "pass_rate": 0.0
            }
        
        scores = [s.overall for s in self._history]
        passing = sum(1 for s in self._history if s.is_passing(self.threshold.minimum_score))
        
        # Calculate per-metric averages
        metric_averages = {}
        for metric in QualityMetric:
            metric_scores = [s.get_metric_score(metric) for s in self._history]
            if metric_scores:
                metric_averages[metric.value] = sum(metric_scores) / len(metric_scores)
        
        return {
            "total_scores": len(self._history),
            "average_score": sum(scores) / len(scores),
            "min_score": min(scores),
            "max_score": max(scores),
            "pass_rate": passing / len(self._history),
            "metric_averages": metric_averages,
            "level_distribution": self._get_level_distribution()
        }
    
    def _get_level_distribution(self) -> Dict[str, int]:
        """Get distribution of quality levels in history."""
        distribution = {level.value: 0 for level in QualityLevel}
        for score in self._history:
            distribution[score.level.value] += 1
        return distribution
