"""
SaaS Specialist for 94% Accuracy Target.

Enhanced SaaS specialist with industry-specific patterns,
confidence scoring, and async prediction support.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
import asyncio

from agent_lightning.training.category_specialists_94 import (
    CategorySpecialist,
    SpecialistType,
    TrainingSample,
    SpecialistMetrics,
)
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SaasPredictionResult:
    """Result of SaaS prediction."""
    action: str
    tier: str
    confidence: float
    detected_intent: str
    entities: Dict[str, Any] = field(default_factory=dict)
    suggested_response: str = ""
    requires_escalation: bool = False
    technical_complexity: str = "low"  # low, medium, high


class SaasSpecialist94(CategorySpecialist):
    """
    Enhanced SaaS Specialist with 94% accuracy target.

    Features:
    - Subscription management and billing
    - Account access and authentication
    - Technical support and troubleshooting
    - Feature requests and feedback
    - API and integration support
    - Usage and analytics queries
    - Escalation detection

    Accuracy Target: >=94% on SaaS domain data
    """

    DOMAIN = "saas"
    ACCURACY_THRESHOLD = 0.94

    # Industry-specific patterns for SaaS
    PATTERNS = {
        "billing": [
            "billing", "invoice", "charge", "payment", "subscription",
            "credit card", "overcharged", "refund", "receipt", "price",
            "plan", "upgrade", "downgrade", "pricing"
        ],
        "account": [
            "account", "login", "password", "access", "signup", "sign up",
            "sign in", "log in", "logout", "authentication", "2fa",
            "two-factor", "reset password", "forgot password", "locked out"
        ],
        "technical": [
            "error", "bug", "not working", "crash", "issue", "problem",
            "broken", "glitch", "slow", "loading", "timeout", "failed",
            "exception", "troubleshoot", "debug"
        ],
        "feature": [
            "feature", "how to", "use", "functionality", "guide", "tutorial",
            "help", "instruction", "learn", "documentation", "docs"
        ],
        "integration": [
            "integration", "api", "connect", "sync", "webhook", "zapier",
            "slack", "salesforce", "hubspot", "export", "import", "oauth"
        ],
        "usage": [
            "usage", "analytics", "report", "metrics", "dashboard",
            "statistics", "data", "insights", "activity", "history"
        ],
        "trial": [
            "trial", "demo", "free", "evaluation", "test", "try",
            "extend trial", "trial expired"
        ],
        "escalation": [
            "manager", "urgent", "critical", "enterprise", "priority",
            "speak to", "supervisor", "escalate", "production down"
        ],
        "security": [
            "security", "privacy", "data protection", "gdpr", "compliance",
            "audit", "permission", "role", "access control"
        ]
    }

    # Action weights for confidence calculation
    ACTION_WEIGHTS = {
        "billing": 1.4,
        "account": 1.3,
        "technical": 1.6,
        "feature": 1.0,
        "integration": 1.5,
        "usage": 1.0,
        "trial": 1.1,
        "escalation": 2.5,
        "security": 1.8,
    }

    # Heavy tier actions requiring more AI power
    HEAVY_ACTIONS = {"escalation", "technical", "security", "integration"}
    MEDIUM_ACTIONS = {"billing", "account", "trial"}

    def __init__(self):
        """Initialize the enhanced SaaS specialist."""
        super().__init__(SpecialistType.SAAS)

        # Initialize with enhanced patterns
        self._patterns = {k: v.copy() for k, v in self.PATTERNS.items()}
        self._action_weights = self.ACTION_WEIGHTS.copy()

        # Response templates
        self._response_templates = self._build_response_templates()

        # Entity extraction patterns
        self._entity_patterns = self._build_entity_patterns()

        # Technical complexity indicators
        self._complexity_indicators = self._build_complexity_indicators()

        logger.info({
            "event": "saas_specialist_94_initialized",
            "domain": self.DOMAIN,
            "accuracy_threshold": self.ACCURACY_THRESHOLD,
            "pattern_count": len(self._patterns)
        })

    def _build_response_templates(self) -> Dict[str, str]:
        """Build response templates for actions."""
        return {
            "billing": "I'll help you with your billing inquiry. Let me pull up your account.",
            "account": "I can help you with your account access.",
            "technical": "Let me help troubleshoot this technical issue.",
            "feature": "I'd be happy to help you with that feature.",
            "integration": "I'll assist you with your integration setup.",
            "usage": "Let me pull up your usage analytics.",
            "trial": "I can help with your trial account.",
            "escalation": "I understand this is urgent. Let me escalate this appropriately.",
            "security": "I take security concerns seriously. Let me help right away."
        }

    def _build_entity_patterns(self) -> Dict[str, re.Pattern]:
        """Build regex patterns for entity extraction."""
        return {
            "email": re.compile(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'),
            "plan_name": re.compile(r'(free|starter|pro|premium|enterprise|business)\s*(?:plan)?', re.IGNORECASE),
            "error_code": re.compile(r'error\s*#?\s*(\d{3,6})', re.IGNORECASE),
            "version": re.compile(r'v?(\d+\.\d+(?:\.\d+)?)'),
            "api_key": re.compile(r'api[_-]?key[:\s]*([a-zA-Z0-9]{20,})', re.IGNORECASE),
            "url": re.compile(r'https?://([a-zA-Z0-9.-]+(?:/[^\s]*)?)'),
        }

    def _build_complexity_indicators(self) -> Dict[str, List[str]]:
        """Build technical complexity indicators."""
        return {
            "high": [
                "api", "webhook", "oauth", "authentication error",
                "production", "database", "server", "integration failed",
                "timeout", "500 error", "ssl", "certificate"
            ],
            "medium": [
                "sync", "export", "import", "configuration", "settings",
                "permission", "role", "access denied", "not loading"
            ],
            "low": [
                "how to", "guide", "tutorial", "documentation", "help me",
                "where is", "can i", "is there"
            ]
        }

    async def predict(self, query: str) -> Dict[str, Any]:
        """
        Predict action for SaaS query with confidence scoring.

        Args:
            query: Customer query text

        Returns:
            Dict with action, tier, confidence, entities, and suggested response
        """
        query_lower = query.lower()
        scores: Dict[str, float] = {}

        # Score each action based on pattern matches
        for action, patterns in self._patterns.items():
            score = 0.0

            for pattern in patterns:
                if pattern in query_lower:
                    score += 1.0

            if score > 0:
                # Apply action weight
                scores[action] = score * self._action_weights.get(action, 1.0)

        if not scores:
            # Default for unrecognized queries
            return {
                "action": "general_inquiry",
                "tier": "light",
                "confidence": 0.5,
                "detected_intent": "general",
                "entities": {},
                "suggested_response": "How can I help you with your account today?",
                "requires_escalation": False,
                "technical_complexity": "low"
            }

        # Get best action
        best_action = max(scores, key=scores.get)

        # Calculate confidence (normalized to 0-1)
        raw_confidence = scores[best_action] / 5.0
        confidence = min(1.0, max(0.0, raw_confidence))

        # Boost confidence for multiple pattern matches
        if len([s for s in scores.values() if s > 0]) > 1:
            confidence = min(1.0, confidence + 0.1)

        # Determine tier
        tier = self._determine_tier(best_action, confidence)

        # Extract entities
        entities = self._extract_entities(query)

        # Check for escalation triggers
        requires_escalation = self._check_escalation_triggers(query, best_action)

        # Determine technical complexity
        technical_complexity = self._determine_technical_complexity(query)

        # Get suggested response
        suggested_response = self._response_templates.get(
            best_action, "How can I assist you with your account?"
        )

        return {
            "action": best_action,
            "tier": tier,
            "confidence": round(confidence, 3),
            "detected_intent": best_action,
            "entities": entities,
            "suggested_response": suggested_response,
            "requires_escalation": requires_escalation,
            "technical_complexity": technical_complexity
        }

    def _determine_tier(self, action: str, confidence: float) -> str:
        """Determine AI tier based on action and confidence."""
        if action in self.HEAVY_ACTIONS:
            return "heavy"
        elif action in self.MEDIUM_ACTIONS:
            return "medium"
        elif confidence < 0.6:
            return "medium"
        return "light"

    def _extract_entities(self, query: str) -> Dict[str, Any]:
        """Extract entities from query."""
        entities = {}

        for entity_name, pattern in self._entity_patterns.items():
            match = pattern.search(query)
            if match:
                entities[entity_name] = match.group(1)

        return entities

    def _check_escalation_triggers(self, query: str, action: str) -> bool:
        """Check if query requires escalation."""
        escalation_triggers = [
            "production down", "critical", "urgent",
            "speak to manager", "supervisor", "data loss",
            "security breach", "hacked", "unauthorized access"
        ]

        query_lower = query.lower()
        for trigger in escalation_triggers:
            if trigger in query_lower:
                return True

        return action == "escalation"

    def _determine_technical_complexity(self, query: str) -> str:
        """Determine technical complexity of the query."""
        query_lower = query.lower()

        for complexity, indicators in self._complexity_indicators.items():
            for indicator in indicators:
                if indicator in query_lower:
                    return complexity

        return "low"

    async def train(self, samples: List[TrainingSample]) -> SpecialistMetrics:
        """
        Train specialist with SaaS samples.

        Args:
            samples: Training samples for SaaS domain

        Returns:
            Training metrics
        """
        # Extend patterns with training data
        for sample in samples:
            action = sample.expected_action
            if action not in self._patterns:
                self._patterns[action] = []

            words = sample.query.lower().split()
            for word in words:
                if len(word) > 3 and word not in self._patterns[action]:
                    self._patterns[action].append(word)

        metrics = await super().train(samples)

        logger.info({
            "event": "saas_specialist_94_trained",
            "samples": len(samples),
            "accuracy": metrics.accuracy,
            "passes_threshold": metrics.passes_threshold
        })

        return metrics

    def get_supported_actions(self) -> List[str]:
        """Get list of supported actions for SaaS."""
        return list(self._patterns.keys())

    def get_confidence_for_action(self, query: str, action: str) -> float:
        """
        Get confidence score for a specific action.

        Args:
            query: Customer query
            action: Action to check confidence for

        Returns:
            Confidence score (0-1)
        """
        if action not in self._patterns:
            return 0.0

        query_lower = query.lower()
        matches = sum(1 for p in self._patterns[action] if p in query_lower)

        if matches == 0:
            return 0.0

        weight = self._action_weights.get(action, 1.0)
        confidence = min(1.0, (matches * weight) / 5.0)

        return round(confidence, 3)


def get_saas_specialist_94() -> SaasSpecialist94:
    """
    Factory function to get SaaS specialist instance.

    Returns:
        SaasSpecialist94 instance
    """
    return SaasSpecialist94()
