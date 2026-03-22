"""
PARWA Intent Classifier.

Classifies user intent from natural language commands.
Provides intent recognition, confidence scoring, and entity extraction.

Supported Intents:
- provision: Add/remove agents
- pause: Pause operations (refunds, etc.)
- escalate: Escalate tickets
- status: Get system status
- help: Get help information
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field
import re

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class Intent(str, Enum):
    """Supported intent types."""
    PROVISION = "provision"
    DEPROVISION = "deprovision"
    PAUSE = "pause"
    RESUME = "resume"
    ESCALATE = "escalate"
    STATUS = "status"
    HELP = "help"
    UNKNOWN = "unknown"


class EntityType(str, Enum):
    """Types of entities that can be extracted."""
    COUNT = "count"
    VARIANT = "variant"
    TICKET_ID = "ticket_id"
    REASON = "reason"
    SCOPE = "scope"


@dataclass
class Entity:
    """Represents an extracted entity."""
    type: EntityType
    value: Any
    confidence: float
    raw_text: str
    position: Tuple[int, int] = (0, 0)


class ClassificationResult(BaseModel):
    """Result of intent classification."""
    intent: str
    confidence: float
    entities: Dict[str, Any] = Field(default_factory=dict)
    original_text: str
    suggestions: List[str] = Field(default_factory=list)
    classified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict()


class IntentClassifier:
    """
    Intent classification service.

    Classifies natural language commands into intents
    and extracts relevant entities.

    Supported Intents:
    - provision: Add agents
    - pause: Pause operations
    - escalate: Escalate tickets
    - status: Get system status
    - help: Get help

    Example:
        classifier = IntentClassifier()
        result = classifier.classify("Add 2 Mini")
        # result.intent == "provision"
        # result.entities == {"count": 2, "type": "mini"}
    """

    # Intent patterns with keywords and regex
    INTENT_PATTERNS = {
        Intent.PROVISION: {
            "keywords": ["add", "create", "provision", "spin up", "new", "launch"],
            "patterns": [
                r"add\s+(\d+)?\s*(mini|parwa|high|agent)?",
                r"provision\s+(\d+)?\s*(mini|parwa|high)?",
                r"spin\s+up\s+(\d+)?\s*(mini|parwa|high)?",
                r"create\s+(\d+)?\s*(mini|parwa|high)?\s*agent",
            ]
        },
        Intent.DEPROVISION: {
            "keywords": ["remove", "delete", "deprovision", "terminate"],
            "patterns": [
                r"remove\s+(\d+)?\s*(mini|parwa|high|agent)?",
                r"delete\s+(\d+)?\s*(mini|parwa|high)?",
                r"deprovision\s+(\d+)?\s*(mini|parwa|high)?",
            ]
        },
        Intent.PAUSE: {
            "keywords": ["pause", "stop", "halt", "freeze", "disable"],
            "patterns": [
                r"pause\s+(all\s+)?refunds?",
                r"stop\s+(all\s+)?refunds?",
                r"halt\s+(all\s+)?refunds?",
            ]
        },
        Intent.RESUME: {
            "keywords": ["resume", "enable", "restart", "unfreeze", "continue"],
            "patterns": [
                r"resume\s+(all\s+)?refunds?",
                r"enable\s+(all\s+)?refunds?",
                r"restart\s+(all\s+)?refunds?",
            ]
        },
        Intent.ESCALATE: {
            "keywords": ["escalate", "bump", "raise", "priority"],
            "patterns": [
                r"escalate\s+(ticket\s+)?(\d+)",
                r"bump\s+(ticket\s+)?(\d+)",
                r"raise\s+(ticket\s+)?(\d+)",
            ]
        },
        Intent.STATUS: {
            "keywords": ["status", "how", "doing", "report", "health"],
            "patterns": [
                r"(system\s+)?status",
                r"how\s+(are\s+we\s+)?doing",
                r"health\s+check",
                r"status\s+report",
            ]
        },
        Intent.HELP: {
            "keywords": ["help", "commands", "usage", "what can"],
            "patterns": [
                r"help",
                r"commands",
                r"what\s+can\s+you\s+do",
                r"usage",
            ]
        },
    }

    # Entity extraction patterns
    ENTITY_PATTERNS = {
        EntityType.COUNT: r"\b(\d+)\b",
        EntityType.VARIANT: r"\b(mini|parwa|high|parwa_high)\b",
        EntityType.TICKET_ID: r"\b(ticket[-_]?\d+|\d{4,})\b",
    }

    # Variant mappings for normalization
    VARIANT_MAPPINGS = {
        "mini": "mini",
        "parwa": "parwa",
        "junior": "parwa",
        "high": "parwa_high",
        "parwa_high": "parwa_high",
        "enterprise": "parwa_high",
    }

    def __init__(self) -> None:
        """Initialize Intent Classifier."""
        self._classification_count = 0
        self._intent_counts: Dict[str, int] = {}

        logger.info({
            "event": "intent_classifier_initialized",
            "intents": [i.value for i in Intent]
        })

    def classify(self, text: str) -> ClassificationResult:
        """
        Classify intent from text.

        Args:
            text: Natural language text

        Returns:
            ClassificationResult with intent, confidence, entities

        Example:
            >>> result = classifier.classify("Add 2 Mini")
            >>> result.intent
            'provision'
            >>> result.entities
            {'count': 2, 'type': 'mini'}
        """
        if not text or not text.strip():
            return self._unknown_result(text)

        # Normalize text
        normalized = text.strip().lower()
        original = text.strip()

        # Score each intent
        scores: Dict[Intent, float] = {}

        for intent, config in self.INTENT_PATTERNS.items():
            score = self._score_intent(normalized, config)
            scores[intent] = score

        # Get best intent
        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]

        # Require minimum confidence
        if best_score < 0.3:
            result = self._unknown_result(original)
            result["suggestions"] = self._generate_suggestions(normalized)
            return ClassificationResult(**result)

        # Extract entities
        entities = self._extract_entities(normalized, best_intent)

        # Build result
        result = ClassificationResult(
            intent=best_intent.value,
            confidence=best_score,
            entities=entities,
            original_text=original,
            suggestions=[]
        )

        # Update stats
        self._classification_count += 1
        self._intent_counts[best_intent.value] = \
            self._intent_counts.get(best_intent.value, 0) + 1

        logger.info({
            "event": "intent_classified",
            "text": normalized,
            "intent": best_intent.value,
            "confidence": best_score,
            "entities": entities
        })

        return result

    def _score_intent(
        self,
        text: str,
        config: Dict[str, Any]
    ) -> float:
        """
        Score how well text matches an intent.

        Args:
            text: Normalized text
            config: Intent configuration

        Returns:
            Confidence score between 0 and 1
        """
        score = 0.0

        # Check keyword matches
        keywords = config.get("keywords", [])
        keyword_matches = sum(1 for kw in keywords if kw in text)
        if keyword_matches > 0:
            score += min(0.4, keyword_matches * 0.15)

        # Check pattern matches
        patterns = config.get("patterns", [])
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                score += 0.4
                break

        # Boost for specific phrases
        if any(kw in text for kw in keywords[:3]):
            score += 0.2

        return min(1.0, score)

    def _extract_entities(
        self,
        text: str,
        intent: Intent
    ) -> Dict[str, Any]:
        """
        Extract entities from text.

        Args:
            text: Normalized text
            intent: Detected intent

        Returns:
            Dict of extracted entities
        """
        entities: Dict[str, Any] = {}

        if intent == Intent.PROVISION or intent == Intent.DEPROVISION:
            # Extract count
            count_match = re.search(self.ENTITY_PATTERNS[EntityType.COUNT], text)
            if count_match:
                entities["count"] = int(count_match.group(1))
            else:
                entities["count"] = 1  # Default to 1

            # Extract variant
            variant_match = re.search(
                self.ENTITY_PATTERNS[EntityType.VARIANT], text, re.IGNORECASE
            )
            if variant_match:
                raw_variant = variant_match.group(1).lower()
                entities["type"] = self.VARIANT_MAPPINGS.get(raw_variant, "mini")

        elif intent == Intent.PAUSE or intent == Intent.RESUME:
            entities["scope"] = "all" if "all" in text else "single"

        elif intent == Intent.ESCALATE:
            # Extract ticket ID
            ticket_match = re.search(
                self.ENTITY_PATTERNS[EntityType.TICKET_ID], text, re.IGNORECASE
            )
            if ticket_match:
                entities["ticket_id"] = ticket_match.group(1)

            # Extract reason if present
            reason_match = re.search(r"(?:because|reason:?)\s+(.+)", text)
            if reason_match:
                entities["reason"] = reason_match.group(1).strip()

        elif intent == Intent.STATUS:
            entities["detail_level"] = "full" if "full" in text else "summary"

        return entities

    def _unknown_result(self, text: str) -> Dict[str, Any]:
        """Generate result for unknown intent."""
        return {
            "intent": Intent.UNKNOWN.value,
            "confidence": 0.0,
            "entities": {},
            "original_text": text,
            "suggestions": ["Type 'help' for available commands"]
        }

    def _generate_suggestions(self, text: str) -> List[str]:
        """Generate command suggestions based on partial input."""
        suggestions = []

        if "refund" in text:
            suggestions.extend(["pause all refunds", "resume all refunds"])

        if "agent" in text or "mini" in text or "parwa" in text:
            suggestions.extend(["add 1 mini", "add 2 parwa"])

        if "ticket" in text or "escalate" in text:
            suggestions.append("escalate ticket 123")

        if "status" in text:
            suggestions.append("system status")

        suggestions.append("help")

        return suggestions[:5]

    def classify_batch(self, texts: List[str]) -> List[ClassificationResult]:
        """
        Classify multiple texts at once.

        Args:
            texts: List of texts to classify

        Returns:
            List of ClassificationResults
        """
        return [self.classify(text) for text in texts]

    def get_supported_intents(self) -> List[str]:
        """Get list of supported intents."""
        return [intent.value for intent in Intent]

    def get_intent_examples(self, intent: Intent) -> List[str]:
        """
        Get example texts for an intent.

        Args:
            intent: Intent to get examples for

        Returns:
            List of example texts
        """
        examples = {
            Intent.PROVISION: [
                "Add 2 Mini agents",
                "Provision 5 PARWA",
                "Spin up 1 High",
            ],
            Intent.DEPROVISION: [
                "Remove 2 Mini agents",
                "Deprovision 1 PARWA",
            ],
            Intent.PAUSE: [
                "Pause all refunds",
                "Stop refunds",
            ],
            Intent.RESUME: [
                "Resume all refunds",
                "Enable refunds",
            ],
            Intent.ESCALATE: [
                "Escalate ticket 123",
                "Escalate #456",
            ],
            Intent.STATUS: [
                "System status",
                "How are we doing",
            ],
            Intent.HELP: [
                "Help",
                "Show commands",
            ],
        }
        return examples.get(intent, [])

    def get_stats(self) -> Dict[str, Any]:
        """
        Get classifier statistics.

        Returns:
            Dict with classification stats
        """
        return {
            "total_classifications": self._classification_count,
            "intent_counts": self._intent_counts,
            "supported_intents": self.get_supported_intents()
        }


def get_intent_classifier() -> IntentClassifier:
    """
    Get an IntentClassifier instance.

    Returns:
        IntentClassifier instance
    """
    return IntentClassifier()
