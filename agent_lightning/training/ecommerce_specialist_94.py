"""
E-commerce Specialist for 94% Accuracy Target.

Enhanced e-commerce specialist with industry-specific patterns,
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
class EcommercePredictionResult:
    """Result of e-commerce prediction."""
    action: str
    tier: str
    confidence: float
    detected_intent: str
    entities: Dict[str, Any] = field(default_factory=dict)
    suggested_response: str = ""
    requires_escalation: bool = False


class EcommerceSpecialist94(CategorySpecialist):
    """
    Enhanced E-commerce Specialist with 94% accuracy target.

    Features:
    - Order status and tracking queries
    - Refund and return processing
    - Shipping inquiries and delivery issues
    - Product availability and recommendations
    - Discount and coupon handling
    - Cart recovery assistance
    - Escalation detection

    Accuracy Target: >=94% on e-commerce domain data
    """

    DOMAIN = "ecommerce"
    ACCURACY_THRESHOLD = 0.94

    # Industry-specific patterns for e-commerce
    PATTERNS = {
        "refund": [
            "refund", "money back", "return my money", "cancel my order",
            "reimbursement", "credit back", "chargeback", "get a refund"
        ],
        "shipping": [
            "shipping", "delivery", "track my order", "where is my package",
            "shipping status", "delivery date", "shipping cost", "expedited"
        ],
        "order_status": [
            "order status", "my order", "check order", "order number",
            "order #", "order details", "recent order", "order history"
        ],
        "product_inquiry": [
            "product", "item", "in stock", "available", "inventory",
            "size chart", "color options", "product details", "specs"
        ],
        "discount": [
            "discount", "coupon", "promo code", "promotion", "sale",
            "offer", "deal", "voucher", "save", "off"
        ],
        "returns": [
            "return", "exchange", "wrong size", "doesn't fit", "damaged",
            "defective", "not as described", "return policy", "exchange"
        ],
        "cart": [
            "cart", "checkout", "basket", "purchase", "buy now",
            "add to cart", "shopping cart", "complete order"
        ],
        "escalation": [
            "manager", "supervisor", "complaint", "unacceptable", "terrible",
            "worst", "speak to", "escalate", "outraged", "furious"
        ],
        "billing": [
            "billing", "invoice", "receipt", "charge", "payment",
            "charged twice", "overcharged", "bill me"
        ]
    }

    # Action weights for confidence calculation
    ACTION_WEIGHTS = {
        "refund": 1.8,
        "shipping": 1.2,
        "order_status": 1.0,
        "product_inquiry": 1.0,
        "discount": 1.0,
        "returns": 1.5,
        "cart": 1.0,
        "escalation": 2.5,
        "billing": 1.3,
    }

    # Heavy tier actions requiring more AI power
    HEAVY_ACTIONS = {"refund", "escalation", "returns", "complaint"}
    MEDIUM_ACTIONS = {"shipping", "billing", "product_inquiry"}

    def __init__(self):
        """Initialize the enhanced e-commerce specialist."""
        super().__init__(SpecialistType.ECOMMERCE)

        # Initialize with enhanced patterns
        self._patterns = {k: v.copy() for k, v in self.PATTERNS.items()}
        self._action_weights = self.ACTION_WEIGHTS.copy()

        # Response templates
        self._response_templates = self._build_response_templates()

        # Entity extraction patterns
        self._entity_patterns = self._build_entity_patterns()

        logger.info({
            "event": "ecommerce_specialist_94_initialized",
            "domain": self.DOMAIN,
            "accuracy_threshold": self.ACCURACY_THRESHOLD,
            "pattern_count": len(self._patterns)
        })

    def _build_response_templates(self) -> Dict[str, str]:
        """Build response templates for actions."""
        return {
            "refund": "I'll help you process your refund request. Let me look up your order.",
            "shipping": "Let me check the shipping status for you.",
            "order_status": "I'll look up your order status right away.",
            "product_inquiry": "I'd be happy to help with product information.",
            "discount": "Let me check what discounts are available for you.",
            "returns": "I can help you with your return or exchange request.",
            "cart": "I'll help you with your cart and checkout.",
            "escalation": "I understand you need to speak with a supervisor. Let me connect you.",
            "billing": "I'll help resolve your billing concern."
        }

    def _build_entity_patterns(self) -> Dict[str, re.Pattern]:
        """Build regex patterns for entity extraction."""
        return {
            "order_id": re.compile(r'order\s*#?\s*(\d{5,12})', re.IGNORECASE),
            "tracking_number": re.compile(r'tracking\s*#?\s*([A-Z0-9]{10,20})', re.IGNORECASE),
            "phone": re.compile(r'\b(\d{3}[-.]?\d{3}[-.]?\d{4})\b'),
            "email": re.compile(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'),
            "price": re.compile(r'\$\s*(\d+(?:\.\d{2})?)'),
            "quantity": re.compile(r'(\d+)\s*(?:items?|pieces?|units?)', re.IGNORECASE),
        }

    async def predict(self, query: str) -> Dict[str, Any]:
        """
        Predict action for e-commerce query with confidence scoring.

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
            matched_patterns = []

            for pattern in patterns:
                if pattern in query_lower:
                    score += 1.0
                    matched_patterns.append(pattern)

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
                "suggested_response": "How can I help you today?",
                "requires_escalation": False
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

        # Get suggested response
        suggested_response = self._response_templates.get(
            best_action, "How can I assist you?"
        )

        return {
            "action": best_action,
            "tier": tier,
            "confidence": round(confidence, 3),
            "detected_intent": best_action,
            "entities": entities,
            "suggested_response": suggested_response,
            "requires_escalation": requires_escalation
        }

    def _determine_tier(self, action: str, confidence: float) -> str:
        """Determine AI tier based on action and confidence."""
        if action in self.HEAVY_ACTIONS:
            return "heavy"
        elif action in self.MEDIUM_ACTIONS:
            return "medium"
        elif confidence < 0.6:
            # Low confidence may need more AI power
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
            "speak to manager", "supervisor", "legal action",
            "better business bureau", "attorney", "sue",
            "social media", "tweet", "facebook post",
            "never buying again", "worst experience"
        ]

        query_lower = query.lower()
        for trigger in escalation_triggers:
            if trigger in query_lower:
                return True

        return action == "escalation"

    async def train(self, samples: List[TrainingSample]) -> SpecialistMetrics:
        """
        Train specialist with e-commerce samples.

        Args:
            samples: Training samples for e-commerce domain

        Returns:
            Training metrics
        """
        # Extend patterns with training data
        for sample in samples:
            action = sample.expected_action
            if action not in self._patterns:
                self._patterns[action] = []

            # Extract keywords from query
            words = sample.query.lower().split()
            for word in words:
                if len(word) > 3 and word not in self._patterns[action]:
                    self._patterns[action].append(word)

        # Call parent train method
        metrics = await super().train(samples)

        # Log e-commerce specific metrics
        logger.info({
            "event": "ecommerce_specialist_94_trained",
            "samples": len(samples),
            "accuracy": metrics.accuracy,
            "passes_threshold": metrics.passes_threshold
        })

        return metrics

    def get_supported_actions(self) -> List[str]:
        """Get list of supported actions for e-commerce."""
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


def get_ecommerce_specialist_94() -> EcommerceSpecialist94:
    """
    Factory function to get e-commerce specialist instance.

    Returns:
        EcommerceSpecialist94 instance
    """
    return EcommerceSpecialist94()
