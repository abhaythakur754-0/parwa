"""
Feature Extractor for ML Router
Extracts text, context, temporal, and metadata features
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class FeatureSet:
    """Container for extracted features"""
    text_features: Dict[str, float] = field(default_factory=dict)
    context_features: Dict[str, Any] = field(default_factory=dict)
    temporal_features: Dict[str, Any] = field(default_factory=dict)
    metadata_features: Dict[str, Any] = field(default_factory=dict)
    normalized_features: Dict[str, float] = field(default_factory=dict)
    feature_importance: Dict[str, float] = field(default_factory=dict)


class FeatureExtractor:
    """
    Extract features from queries for ML classification.
    Supports text, context, temporal, and metadata features.
    """
    
    # Feature importance weights (for feature importance tracking)
    IMPORTANCE_WEIGHTS = {
        'text_length': 0.1,
        'word_count': 0.15,
        'has_question': 0.08,
        'urgency_score': 0.2,
        'entity_count': 0.12,
        'sentiment': 0.1,
        'time_of_day': 0.05,
        'day_of_week': 0.05,
        'channel': 0.08,
        'priority': 0.07,
    }
    
    # Urgency indicators
    URGENCY_PATTERNS = [
        r'\b(?:urgent|emergency|asap|immediately|critical|now)\b',
        r'\b(?:right now|right away|this minute)\b',
        r'!',
    ]
    
    # Question patterns
    QUESTION_PATTERNS = [
        r'\?',
        r'\b(?:what|where|when|why|how|who|which|can|could|would|should|is|are|do|does)\b',
    ]
    
    # Entity patterns (order_id, product, amount)
    ENTITY_PATTERNS = {
        'order_id': r'[A-Z]{2,3}-\d{4,8}|\d{8,12}',
        'amount': r'\$[\d,]+\.?\d*|\d+\s*(?:dollars?|USD|€|£)',
        'email': r'[\w\.-]+@[\w\.-]+\.\w+',
        'phone': r'\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        'product': r'\b(?:product|item|order)\s*[A-Z0-9-]+\b',
    }
    
    def __init__(self):
        self._feature_stats: Dict[str, List[float]] = {}
        self._normalization_params: Dict[str, Dict[str, float]] = {}
    
    def extract(
        self, 
        query: str, 
        context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> FeatureSet:
        """
        Extract all features from a query.
        
        Args:
            query: User query text
            context: Context information (user history, client type)
            metadata: Metadata (priority, channel)
            
        Returns:
            FeatureSet with all extracted features
        """
        feature_set = FeatureSet()
        
        # Extract text features
        feature_set.text_features = self._extract_text_features(query)
        
        # Extract context features
        feature_set.context_features = self._extract_context_features(context or {})
        
        # Extract temporal features
        feature_set.temporal_features = self._extract_temporal_features()
        
        # Extract metadata features
        feature_set.metadata_features = self._extract_metadata_features(metadata or {})
        
        # Normalize features
        feature_set.normalized_features = self._normalize_features(feature_set)
        
        # Set feature importance
        feature_set.feature_importance = self.IMPORTANCE_WEIGHTS.copy()
        
        return feature_set
    
    def _extract_text_features(self, query: str) -> Dict[str, float]:
        """Extract text-based features."""
        features = {}
        
        # Basic text features
        features['text_length'] = float(len(query))
        features['word_count'] = float(len(query.split()))
        features['avg_word_length'] = (
            sum(len(w) for w in query.split()) / max(1, len(query.split()))
        )
        
        # Question features
        has_question = any(
            re.search(p, query, re.IGNORECASE) 
            for p in self.QUESTION_PATTERNS
        )
        features['has_question'] = 1.0 if has_question else 0.0
        
        # Urgency features
        urgency_matches = sum(
            len(re.findall(p, query, re.IGNORECASE))
            for p in self.URGENCY_PATTERNS
        )
        features['urgency_score'] = min(1.0, urgency_matches / 3.0)
        
        # Entity features
        entity_count = 0
        for entity_type, pattern in self.ENTITY_PATTERNS.items():
            matches = re.findall(pattern, query)
            if matches:
                entity_count += len(matches)
        features['entity_count'] = float(entity_count)
        
        # Punctuation features
        features['exclamation_count'] = float(query.count('!'))
        features['question_mark_count'] = float(query.count('?'))
        
        # Sentiment indicator (simple)
        positive_words = ['thank', 'great', 'good', 'helpful', 'appreciate']
        negative_words = ['bad', 'terrible', 'hate', 'angry', 'frustrated', 'disappointed']
        
        positive_count = sum(1 for w in positive_words if w in query.lower())
        negative_count = sum(1 for w in negative_words if w in query.lower())
        
        features['sentiment'] = (positive_count - negative_count) / 5.0
        
        return features
    
    def _extract_context_features(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract context-based features."""
        features = {}
        
        # User history features
        features['user_total_queries'] = context.get('user_total_queries', 0)
        features['user_avg_resolution_time'] = context.get('avg_resolution_time', 0)
        
        # Client features
        features['client_type'] = context.get('client_type', 'standard')
        features['client_tier'] = context.get('client_tier', 'basic')
        
        # Conversation features
        features['conversation_turn'] = context.get('conversation_turn', 1)
        features['previous_escalations'] = context.get('previous_escalations', 0)
        
        # Resolution history
        features['recent_resolved'] = context.get('recent_resolved', 0)
        features['recent_unresolved'] = context.get('recent_unresolved', 0)
        
        return features
    
    def _extract_temporal_features(self) -> Dict[str, Any]:
        """Extract temporal features."""
        now = datetime.now()
        
        features = {
            'hour_of_day': now.hour,
            'day_of_week': now.weekday(),
            'is_weekend': 1 if now.weekday() >= 5 else 0,
            'is_business_hours': 1 if 9 <= now.hour <= 17 else 0,
            'time_segment': self._get_time_segment(now.hour),
        }
        
        return features
    
    def _get_time_segment(self, hour: int) -> str:
        """Get time segment from hour."""
        if 6 <= hour < 12:
            return 'morning'
        elif 12 <= hour < 17:
            return 'afternoon'
        elif 17 <= hour < 21:
            return 'evening'
        else:
            return 'night'
    
    def _extract_metadata_features(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata features."""
        features = {
            'priority': metadata.get('priority', 'normal'),
            'channel': metadata.get('channel', 'web'),
            'language': metadata.get('language', 'en'),
            'source': metadata.get('source', 'direct'),
        }
        
        # Priority score
        priority_scores = {'low': 0.25, 'normal': 0.5, 'high': 0.75, 'urgent': 1.0}
        features['priority_score'] = priority_scores.get(
            features['priority'], 0.5
        )
        
        # Channel score
        channel_scores = {'web': 0.5, 'mobile': 0.6, 'api': 0.7, 'email': 0.4}
        features['channel_score'] = channel_scores.get(
            features['channel'], 0.5
        )
        
        return features
    
    def _normalize_features(self, feature_set: FeatureSet) -> Dict[str, float]:
        """Normalize all features to 0-1 range."""
        normalized = {}
        
        # Normalize text features
        tf = feature_set.text_features
        normalized['text_length_norm'] = min(1.0, tf.get('text_length', 0) / 500.0)
        normalized['word_count_norm'] = min(1.0, tf.get('word_count', 0) / 100.0)
        normalized['urgency_norm'] = tf.get('urgency_score', 0)
        normalized['entity_count_norm'] = min(1.0, tf.get('entity_count', 0) / 5.0)
        normalized['sentiment_norm'] = (tf.get('sentiment', 0) + 1) / 2  # -1 to 1 -> 0 to 1
        
        # Normalize context features
        cf = feature_set.context_features
        normalized['queries_norm'] = min(1.0, cf.get('user_total_queries', 0) / 100.0)
        normalized['turn_norm'] = min(1.0, cf.get('conversation_turn', 1) / 10.0)
        normalized['escalation_norm'] = min(1.0, cf.get('previous_escalations', 0) / 5.0)
        
        # Normalize temporal features
        tfeat = feature_set.temporal_features
        normalized['hour_norm'] = tfeat.get('hour_of_day', 12) / 24.0
        normalized['day_norm'] = tfeat.get('day_of_week', 0) / 6.0
        
        # Normalize metadata features
        mf = feature_set.metadata_features
        normalized['priority_norm'] = mf.get('priority_score', 0.5)
        normalized['channel_norm'] = mf.get('channel_score', 0.5)
        
        return normalized
    
    def get_feature_vector(self, feature_set: FeatureSet) -> List[float]:
        """Get normalized feature vector for ML model."""
        return list(feature_set.normalized_features.values())
    
    def get_feature_names(self) -> List[str]:
        """Get list of feature names."""
        return [
            'text_length_norm',
            'word_count_norm',
            'urgency_norm',
            'entity_count_norm',
            'sentiment_norm',
            'queries_norm',
            'turn_norm',
            'escalation_norm',
            'hour_norm',
            'day_norm',
            'priority_norm',
            'channel_norm',
        ]
    
    def update_stats(self, feature_set: FeatureSet) -> None:
        """Update feature statistics for normalization."""
        for name, value in feature_set.normalized_features.items():
            if name not in self._feature_stats:
                self._feature_stats[name] = []
            self._feature_stats[name].append(value)
            
            # Keep only last 1000 values
            if len(self._feature_stats[name]) > 1000:
                self._feature_stats[name] = self._feature_stats[name][-1000:]
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores."""
        return self.IMPORTANCE_WEIGHTS.copy()
