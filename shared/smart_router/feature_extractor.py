"""
PARWA Feature Extractor for ML Classifier.

Extracts features from query text for ML-based routing decisions.
"""
from typing import Dict, List, Any, Optional
import re
from collections import Counter

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class FeatureExtractor:
    """
    Extract features from customer queries for ML classification.
    
    Features include:
    - Text statistics (length, word count, etc.)
    - Sentiment indicators
    - Complexity patterns
    - Domain-specific features
    """

    # Escalation keywords
    ESCALATION_KEYWORDS = [
        "manager", "supervisor", "speak to", "real person", "human",
        "complaint", "escalat", "unacceptable", "terrible", "worst",
        "attorney", "lawyer", "legal", "sue", "court", "better business bureau"
    ]

    # Refund/payment keywords
    REFUND_KEYWORDS = [
        "refund", "money back", "return", "credit", "reimburse",
        "chargeback", "dispute", "unauthorized charge", "wrong amount"
    ]

    # Technical keywords
    TECHNICAL_KEYWORDS = [
        "error", "bug", "crash", "not working", "broken", "failed",
        "glitch", "issue", "problem", "stuck", "frozen", "timeout"
    ]

    # Simple FAQ keywords
    FAQ_KEYWORDS = [
        "hours", "location", "contact", "phone", "email", "address",
        "price", "cost", "shipping", "delivery", "track", "status"
    ]

    # Negative sentiment words
    NEGATIVE_WORDS = [
        "angry", "frustrated", "disappointed", "upset", "furious",
        "outraged", "annoyed", "irritated", "dissatisfied", "unhappy",
        "hate", "terrible", "awful", "horrible", "disgusting", "never"
    ]

    # Positive sentiment words
    POSITIVE_WORDS = [
        "great", "awesome", "excellent", "amazing", "wonderful",
        "fantastic", "love", "perfect", "best", "thank", "appreciate"
    ]

    def extract(self, query: str) -> Dict[str, float]:
        """
        Extract all features from a query.

        Args:
            query: Customer query text

        Returns:
            Dict of feature names to values
        """
        if not query:
            return self._empty_features()

        features = {}

        # Text statistics
        features.update(self._text_statistics(query))

        # Pattern matches
        features.update(self._pattern_features(query))

        # Sentiment features
        features.update(self._sentiment_features(query))

        # Punctuation features
        features.update(self._punctuation_features(query))

        # Domain features
        features.update(self._domain_features(query))

        return features

    def _empty_features(self) -> Dict[str, float]:
        """Return empty feature dict for empty queries."""
        return {
            "text_length": 0.0, "word_count": 0.0, "avg_word_length": 0.0,
            "escalation_score": 0.0, "refund_score": 0.0, "technical_score": 0.0,
            "faq_score": 0.0, "sentiment_score": 0.0, "question_count": 0.0,
            "exclamation_count": 0.0, "caps_ratio": 0.0, "urgency_score": 0.0
        }

    def _text_statistics(self, query: str) -> Dict[str, float]:
        """Extract text statistics."""
        words = query.split()
        word_count = len(words)
        text_length = len(query)

        return {
            "text_length": float(text_length),
            "word_count": float(word_count),
            "avg_word_length": float(sum(len(w) for w in words) / max(word_count, 1)),
            "sentence_count": float(len(re.split(r'[.!?]+', query))),
            "char_diversity": float(len(set(query.lower())) / max(text_length, 1)),
        }

    def _pattern_features(self, query: str) -> Dict[str, float]:
        """Extract pattern-based features."""
        query_lower = query.lower()

        escalation_score = sum(1 for kw in self.ESCALATION_KEYWORDS if kw in query_lower)
        refund_score = sum(1 for kw in self.REFUND_KEYWORDS if kw in query_lower)
        technical_score = sum(1 for kw in self.TECHNICAL_KEYWORDS if kw in query_lower)
        faq_score = sum(1 for kw in self.FAQ_KEYWORDS if kw in query_lower)

        return {
            "escalation_score": float(escalation_score),
            "refund_score": float(refund_score),
            "technical_score": float(technical_score),
            "faq_score": float(faq_score),
        }

    def _sentiment_features(self, query: str) -> Dict[str, float]:
        """Extract sentiment features."""
        query_lower = query.lower()
        words = set(query_lower.split())

        negative_count = sum(1 for w in self.NEGATIVE_WORDS if w in query_lower)
        positive_count = sum(1 for w in self.POSITIVE_WORDS if w in query_lower)

        # Sentiment score: negative = -1 to 0, positive = 0 to 1
        total_sentiment_words = max(negative_count + positive_count, 1)
        sentiment_score = (positive_count - negative_count) / total_sentiment_words

        return {
            "sentiment_score": float(sentiment_score),
            "negative_word_count": float(negative_count),
            "positive_word_count": float(positive_count),
        }

    def _punctuation_features(self, query: str) -> Dict[str, float]:
        """Extract punctuation-based features."""
        question_count = query.count('?')
        exclamation_count = query.count('!')
        caps_count = sum(1 for c in query if c.isupper())
        caps_ratio = caps_count / max(len(query), 1)

        # Multiple punctuation indicates urgency
        multiple_punct = len(re.findall(r'[!?]{2,}', query))

        return {
            "question_count": float(question_count),
            "exclamation_count": float(exclamation_count),
            "caps_ratio": float(caps_ratio),
            "multiple_punctuation": float(multiple_punct),
            "urgency_score": float(exclamation_count + multiple_punct * 2 + (caps_ratio > 0.3) * 2),
        }

    def _domain_features(self, query: str) -> Dict[str, float]:
        """Extract domain-specific features."""
        query_lower = query.lower()

        # Time-related urgency
        time_urgent = any(phrase in query_lower for phrase in [
            "asap", "urgent", "immediately", "right now", "today", "emergency"
        ])

        # Money-related
        money_related = any(phrase in query_lower for phrase in [
            "$", "dollar", "payment", "charge", "bill", "invoice", "cost"
        ])

        # Account-related
        account_related = any(phrase in query_lower for phrase in [
            "account", "login", "password", "access", "subscription", "membership"
        ])

        return {
            "time_urgency": float(time_urgent),
            "money_related": float(money_related),
            "account_related": float(account_related),
        }

    def extract_batch(self, queries: List[str]) -> List[Dict[str, float]]:
        """
        Extract features from multiple queries.

        Args:
            queries: List of query texts

        Returns:
            List of feature dicts
        """
        return [self.extract(q) for q in queries]

    def get_feature_names(self) -> List[str]:
        """Get list of all feature names."""
        return list(self._empty_features().keys()) + [
            "sentence_count", "char_diversity", "negative_word_count",
            "positive_word_count", "multiple_punctuation", "time_urgency",
            "money_related", "account_related"
        ]
