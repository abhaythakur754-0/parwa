"""
Feature Engineering for Agent Lightning 94% Training.

Extracts and processes features for model training.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field
import re

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FeatureConfig:
    """Configuration for feature extraction."""
    max_ngram_size: int = 3
    include_sentiment: bool = True
    include_entities: bool = True
    include_temporal: bool = True
    normalize_features: bool = True
    feature_dim: int = 256


class FeatureEngineer:
    """
    Feature engineering for Agent Lightning.
    
    Extracts features including:
    - Text features (TF-IDF, embeddings)
    - N-gram features
    - Sentiment features
    - Entity features
    - Context features
    """
    
    def __init__(self, config: Optional[FeatureConfig] = None):
        """Initialize feature engineer."""
        self.config = config or FeatureConfig()
        self._feature_names: List[str] = []
        self._feature_importance: Dict[str, float] = {}
        
        # Escalation patterns
        self._escalation_patterns = [
            r"manager", r"supervisor", r"unacceptable", r"ridiculous",
            r"worst", r"terrible", r"awful", r"horrible", r"scam",
            r"lawyer", r"attorney", r"legal", r"bbb", r"ftc"
        ]
        
        # Refund patterns
        self._refund_patterns = [
            r"refund", r"money back", r"credit", r"reimburse",
            r"chargeback", r"dispute", r"return"
        ]
        
        # Technical patterns
        self._technical_patterns = [
            r"error", r"bug", r"crash", r"not working", r"broken",
            r"issue", r"problem", r"failed", r"glitch"
        ]
    
    def extract_features(self, query: str) -> Dict[str, float]:
        """
        Extract features from query.
        
        Args:
            query: Customer query text
            
        Returns:
            Dictionary of feature name to value
        """
        features = {}
        
        # Text statistics
        features.update(self._extract_text_stats(query))
        
        # N-gram features
        features.update(self._extract_ngram_features(query))
        
        # Pattern features
        features.update(self._extract_pattern_features(query))
        
        # Sentiment features
        if self.config.include_sentiment:
            features.update(self._extract_sentiment_features(query))
        
        # Entity features
        if self.config.include_entities:
            features.update(self._extract_entity_features(query))
        
        # Temporal features
        if self.config.include_temporal:
            features.update(self._extract_temporal_features())
        
        # Store feature names
        if not self._feature_names:
            self._feature_names = list(features.keys())
        
        return features
    
    def extract_batch(
        self,
        queries: List[str]
    ) -> List[Dict[str, float]]:
        """
        Extract features for multiple queries.
        
        Args:
            queries: List of query texts
            
        Returns:
            List of feature dictionaries
        """
        return [self.extract_features(q) for q in queries]
    
    def get_feature_vector(
        self,
        query: str
    ) -> List[float]:
        """
        Get ordered feature vector for query.
        
        Args:
            query: Customer query text
            
        Returns:
            Ordered list of feature values
        """
        features = self.extract_features(query)
        return [features.get(name, 0.0) for name in self._feature_names]
    
    def _extract_text_stats(self, query: str) -> Dict[str, float]:
        """Extract text statistics."""
        words = query.split()
        chars = len(query)
        
        return {
            "word_count": float(len(words)),
            "char_count": float(chars),
            "avg_word_length": float(sum(len(w) for w in words) / len(words)) if words else 0.0,
            "question_mark": float("?" in query),
            "exclamation_mark": float("!" in query),
            "uppercase_ratio": float(sum(1 for c in query if c.isupper()) / chars) if chars > 0 else 0.0,
        }
    
    def _extract_ngram_features(self, query: str) -> Dict[str, float]:
        """Extract n-gram features."""
        features = {}
        words = query.lower().split()
        
        # Unigrams
        unigrams = set(words)
        features["unique_words"] = float(len(unigrams))
        
        # Bigrams
        bigrams = ["_".join(words[i:i+2]) for i in range(len(words)-1)]
        features["bigram_count"] = float(len(bigrams))
        
        # Trigrams
        trigrams = ["_".join(words[i:i+3]) for i in range(len(words)-2)]
        features["trigram_count"] = float(len(trigrams))
        
        return features
    
    def _extract_pattern_features(self, query: str) -> Dict[str, float]:
        """Extract pattern-based features."""
        query_lower = query.lower()
        features = {}
        
        # Escalation score
        escalation_matches = sum(
            1 for p in self._escalation_patterns
            if re.search(p, query_lower)
        )
        features["escalation_score"] = float(escalation_matches)
        
        # Refund score
        refund_matches = sum(
            1 for p in self._refund_patterns
            if re.search(p, query_lower)
        )
        features["refund_score"] = float(refund_matches)
        
        # Technical score
        technical_matches = sum(
            1 for p in self._technical_patterns
            if re.search(p, query_lower)
        )
        features["technical_score"] = float(technical_matches)
        
        return features
    
    def _extract_sentiment_features(self, query: str) -> Dict[str, float]:
        """Extract sentiment features (rule-based)."""
        query_lower = query.lower()
        
        # Positive words
        positive_words = [
            "thank", "great", "excellent", "good", "helpful",
            "appreciate", "wonderful", "amazing", "perfect"
        ]
        
        # Negative words
        negative_words = [
            "bad", "terrible", "awful", "horrible", "worst",
            "disappointed", "frustrated", "angry", "unhappy"
        ]
        
        positive_count = sum(1 for w in positive_words if w in query_lower)
        negative_count = sum(1 for w in negative_words if w in query_lower)
        
        return {
            "positive_sentiment": float(positive_count),
            "negative_sentiment": float(negative_count),
            "sentiment_polarity": float(positive_count - negative_count),
        }
    
    def _extract_entity_features(self, query: str) -> Dict[str, float]:
        """Extract entity features."""
        features = {}
        
        # Order ID pattern
        order_id_pattern = r"[A-Z0-9]{8,}"
        order_ids = re.findall(order_id_pattern, query)
        features["has_order_id"] = float(len(order_ids) > 0)
        
        # Amount pattern
        amount_pattern = r"\$\d+\.?\d*|\d+\.\d{2}"
        amounts = re.findall(amount_pattern, query)
        features["has_amount"] = float(len(amounts) > 0)
        
        # Date pattern
        date_pattern = r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
        dates = re.findall(date_pattern, query)
        features["has_date"] = float(len(dates) > 0)
        
        return features
    
    def _extract_temporal_features(self) -> Dict[str, float]:
        """Extract temporal features from current time."""
        now = datetime.now(timezone.utc)
        
        return {
            "hour_of_day": float(now.hour),
            "day_of_week": float(now.weekday()),
            "is_business_hours": float(9 <= now.hour <= 17),
            "is_weekend": float(now.weekday() >= 5),
        }
    
    def set_feature_importance(
        self,
        importance: Dict[str, float]
    ) -> None:
        """Set feature importance scores."""
        self._feature_importance = importance
    
    def get_top_features(
        self,
        n: int = 10
    ) -> List[Tuple[str, float]]:
        """Get top N most important features."""
        sorted_features = sorted(
            self._feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_features[:n]
    
    def get_feature_names(self) -> List[str]:
        """Get ordered feature names."""
        return self._feature_names.copy()


def extract_features(
    query: str,
    config: Optional[FeatureConfig] = None
) -> Dict[str, float]:
    """
    Quick function to extract features.
    
    Args:
        query: Query text
        config: Optional feature config
        
    Returns:
        Feature dictionary
    """
    engineer = FeatureEngineer(config)
    return engineer.extract_features(query)
