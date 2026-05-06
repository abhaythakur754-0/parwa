"""
Context Integrator for Agent Lightning 94% Accuracy.

Integrates conversation context for better predictions.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ContextFeatures:
    """Features extracted from context."""
    turn_count: int = 0
    previous_intent: str = ""
    user_sentiment: float = 0.0
    escalation_history: bool = False
    refund_mentioned: bool = False
    manager_requested: bool = False
    avg_response_time: float = 0.0
    session_duration: float = 0.0


class ContextIntegrator:
    """
    Integrates conversation context into predictions.
    
    Features:
    - Conversation history
    - User preferences
    - Previous intents
    - Session context
    - Cross-turn context
    """
    
    def __init__(self, max_history: int = 10):
        """Initialize context integrator."""
        self.max_history = max_history
        self._session_contexts: Dict[str, List[Dict[str, Any]]] = {}
    
    def update_context(
        self,
        session_id: str,
        query: str,
        intent: str,
        confidence: float
    ) -> None:
        """Update session context with new turn."""
        if session_id not in self._session_contexts:
            self._session_contexts[session_id] = []
        
        context = {
            "query": query,
            "intent": intent,
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self._session_contexts[session_id].append(context)
        
        # Trim to max history
        if len(self._session_contexts[session_id]) > self.max_history:
            self._session_contexts[session_id] = self._session_contexts[session_id][-self.max_history:]
    
    def get_context_features(
        self,
        session_id: str
    ) -> ContextFeatures:
        """Extract features from session context."""
        history = self._session_contexts.get(session_id, [])
        
        if not history:
            return ContextFeatures()
        
        features = ContextFeatures(turn_count=len(history))
        
        # Previous intent
        if len(history) > 1:
            features.previous_intent = history[-2].get("intent", "")
        
        # Check history patterns
        all_queries = " ".join(h.get("query", "").lower() for h in history)
        
        features.escalation_history = any(
            word in all_queries for word in ["manager", "supervisor", "escalate"]
        )
        features.refund_mentioned = "refund" in all_queries
        features.manager_requested = "manager" in all_queries
        
        # Sentiment tracking
        negative_words = ["angry", "frustrated", "unacceptable", "terrible", "worst"]
        negative_count = sum(1 for word in negative_words if word in all_queries)
        features.user_sentiment = max(0, 1 - (negative_count * 0.2))
        
        return features
    
    def adjust_prediction(
        self,
        session_id: str,
        predicted_intent: str,
        confidence: float
    ) -> tuple:
        """
        Adjust prediction based on context.
        
        Returns:
            Tuple of (adjusted_intent, adjusted_confidence)
        """
        context = self.get_context_features(session_id)
        
        adjusted_intent = predicted_intent
        adjusted_confidence = confidence
        
        # Escalation boost if manager was previously requested
        if context.manager_requested and predicted_intent != "escalation":
            if confidence < 0.9:
                adjusted_intent = "escalation"
                adjusted_confidence = min(1.0, confidence + 0.3)
        
        # Refund context boost
        if context.refund_mentioned and predicted_intent in ["faq", "inquiry"]:
            adjusted_intent = "refund"
            adjusted_confidence = min(1.0, confidence + 0.2)
        
        # Low sentiment boost escalation confidence
        if context.user_sentiment < 0.5 and predicted_intent == "escalation":
            adjusted_confidence = min(1.0, confidence + 0.1)
        
        return adjusted_intent, adjusted_confidence
    
    def clear_session(self, session_id: str) -> None:
        """Clear session context."""
        if session_id in self._session_contexts:
            del self._session_contexts[session_id]
    
    def get_all_sessions(self) -> List[str]:
        """Get all active session IDs."""
        return list(self._session_contexts.keys())
