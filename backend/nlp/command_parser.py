"""
PARWA Command Parser.

Natural language command parser for admin operations.
Extracts structured commands from natural language text.

CRITICAL Test Cases:
- "Add 2 Mini" → {action: "provision", count: 2, type: "mini"}
- "Pause all refunds" → {action: "pause_refunds", scope: "all"}
- "Escalate ticket 123" → {action: "escalate", ticket_id: "123"}
"""
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import re

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class IntentType(str, Enum):
    """Types of intents the parser can identify."""
    PROVISION = "provision"
    DEPROVISION = "deprovision"
    PAUSE_REFUNDS = "pause_refunds"
    RESUME_REFUNDS = "resume_refunds"
    ESCALATE = "escalate"
    STATUS = "status"
    HELP = "help"
    UNKNOWN = "unknown"


@dataclass
class ParsedCommand:
    """Represents a parsed command from natural language."""
    action: str
    intent: IntentType
    confidence: float
    entities: Dict[str, Any] = field(default_factory=dict)
    original_text: str = ""
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "action": self.action,
            "intent": self.intent.value,
            "confidence": self.confidence,
            "entities": self.entities,
            "original_text": self.original_text,
            "suggestions": self.suggestions,
        }


class CommandParser:
    """
    Natural language command parser.

    Parses natural language commands into structured actions.

    CRITICAL Test Cases:
    - "Add 2 Mini" → {action: "provision", count: 2, type: "mini"}
    - "Pause all refunds" → {action: "pause_refunds", scope: "all"}
    - "Escalate ticket 123" → {action: "escalate", ticket_id: "123"}

    Features:
    - Intent classification
    - Entity extraction
    - Confidence scoring
    - Suggestion generation

    Example:
        parser = CommandParser()
        result = parser.parse("Add 2 Mini")
        # result.action == "provision"
        # result.entities == {"count": 2, "type": "mini"}
    """

    # Intent patterns with regex and keywords
    INTENT_PATTERNS = {
        IntentType.PROVISION: [
            r"add\s+(\d+)\s*(mini|parwa|high|agent)",
            r"provision\s+(\d+)\s*(mini|parwa|high|agent)",
            r"spin\s+up\s+(\d+)\s*(mini|parwa|high)",
            r"create\s+(\d+)\s*(mini|parwa|high)\s*agent",
            r"new\s+(mini|parwa|high)\s*agent",
            r"add\s+(?:a\s+)?(mini|parwa|high)",
        ],
        IntentType.DEPROVISION: [
            r"remove\s+(\d+)\s*(mini|parwa|high|agent)",
            r"deprovision\s+(\d+)\s*(mini|parwa|high)",
            r"delete\s+(\d+)\s*(mini|parwa|high)\s*agent",
            r"remove\s+(?:the\s+)?(mini|parwa|high)\s*agent",
        ],
        IntentType.PAUSE_REFUNDS: [
            r"pause\s+(?:all\s+)?refunds?",
            r"stop\s+(?:all\s+)?refunds?",
            r"halt\s+(?:all\s+)?refunds?",
            r"freeze\s+(?:all\s+)?refunds?",
            r"block\s+(?:all\s+)?refunds?",
            r"disable\s+(?:all\s+)?refunds?",
        ],
        IntentType.RESUME_REFUNDS: [
            r"resume\s+(?:all\s+)?refunds?",
            r"enable\s+(?:all\s+)?refunds?",
            r"restart\s+(?:all\s+)?refunds?",
            r"unfreeze\s+(?:all\s+)?refunds?",
            r"allow\s+(?:all\s+)?refunds?",
        ],
        IntentType.ESCALATE: [
            r"escalate\s+(?:ticket\s+)?(\d+)",
            r"escalate\s+(?:the\s+)?ticket\s+(\d+)",
            r"escalate\s+#?(\d+)",
            r"bump\s+(?:ticket\s+)?(\d+)",
            r"raise\s+(?:ticket\s+)?(\d+)",
        ],
        IntentType.STATUS: [
            r"(?:get\s+)?system\s+status",
            r"(?:what\s+is\s+)?the\s+status",
            r"status\s+report",
            r"check\s+status",
            r"how\s+(?:are\s+we\s+)?doing",
        ],
        IntentType.HELP: [
            r"help(?:\s+me)?",
            r"what\s+can\s+you\s+do",
            r"commands?",
            r"show\s+(?:me\s+)?(?:the\s+)?commands",
            r"usage",
        ],
    }

    # Variant type mappings
    VARIANT_MAPPINGS = {
        "mini": "mini",
        "parwa": "parwa",
        "junior": "parwa",
        "high": "parwa_high",
        "parwa_high": "parwa_high",
        "enterprise": "parwa_high",
        "agent": "mini",  # Default to mini
    }

    def __init__(self) -> None:
        """Initialize Command Parser."""
        logger.info({
            "event": "command_parser_initialized",
            "intent_types": [i.value for i in IntentType],
        })

    def parse(self, text: str) -> ParsedCommand:
        """
        Parse natural language command.

        CRITICAL Test Cases:
        - "Add 2 Mini" → {action: "provision", count: 2, type: "mini"}
        - "Pause all refunds" → {action: "pause_refunds", scope: "all"}
        - "Escalate ticket 123" → {action: "escalate", ticket_id: "123"}

        Args:
            text: Natural language command text

        Returns:
            ParsedCommand with action, entities, and confidence
        """
        if not text or not text.strip():
            return ParsedCommand(
                action="unknown",
                intent=IntentType.UNKNOWN,
                confidence=0.0,
                original_text=text,
                suggestions=["Type 'help' for available commands"],
            )

        # Normalize text
        normalized = text.strip().lower()
        original = text.strip()

        # Try to match each intent pattern
        best_match: Optional[Dict[str, Any]] = None
        best_confidence = 0.0

        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, normalized, re.IGNORECASE)
                if match:
                    confidence = self._calculate_confidence(
                        intent, normalized, match
                    )
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = {
                            "intent": intent,
                            "match": match,
                            "pattern": pattern,
                        }

        # If no match found, return unknown with suggestions
        if not best_match:
            logger.info({
                "event": "command_parse_unknown",
                "text": normalized,
            })
            return ParsedCommand(
                action="unknown",
                intent=IntentType.UNKNOWN,
                confidence=0.0,
                original_text=original,
                suggestions=self._generate_suggestions(normalized),
            )

        # Extract entities and build result
        intent = best_match["intent"]
        match = best_match["match"]

        entities = self._extract_entities(intent, match, normalized)
        action = self._get_action(intent, entities)

        logger.info({
            "event": "command_parsed",
            "text": normalized,
            "intent": intent.value,
            "action": action,
            "entities": entities,
            "confidence": best_confidence,
        })

        return ParsedCommand(
            action=action,
            intent=intent,
            confidence=best_confidence,
            entities=entities,
            original_text=original,
            suggestions=[],
        )

    def _calculate_confidence(
        self,
        intent: IntentType,
        text: str,
        match: re.Match
    ) -> float:
        """
        Calculate confidence score for a match.

        Args:
            intent: Matched intent
            text: Normalized text
            match: Regex match object

        Returns:
            Confidence score between 0.0 and 1.0
        """
        base_confidence = 0.7

        # Boost for exact pattern match
        matched_text = match.group(0)
        coverage = len(matched_text) / len(text)
        base_confidence += coverage * 0.15

        # Boost for specific intents
        if intent in [IntentType.PROVISION, IntentType.PAUSE_REFUNDS, IntentType.ESCALATE]:
            base_confidence += 0.1

        # Cap at 1.0
        return min(1.0, base_confidence)

    def _extract_entities(
        self,
        intent: IntentType,
        match: re.Match,
        text: str
    ) -> Dict[str, Any]:
        """
        Extract entities from matched text.

        Args:
            intent: Matched intent
            match: Regex match object
            text: Normalized text

        Returns:
            Dict of extracted entities
        """
        entities: Dict[str, Any] = {}

        if intent == IntentType.PROVISION:
            # Extract count and type
            groups = match.groups()
            if len(groups) >= 2:
                # Pattern: "add 2 mini" -> count=2, type=mini
                count_str, variant_str = groups[0], groups[1]
                entities["count"] = int(count_str) if count_str.isdigit() else 1
                entities["type"] = self.VARIANT_MAPPINGS.get(
                    variant_str.lower(), "mini"
                )
            elif len(groups) == 1:
                # Pattern: "add mini" -> count=1, type=mini
                variant_str = groups[0]
                entities["count"] = 1
                entities["type"] = self.VARIANT_MAPPINGS.get(
                    variant_str.lower(), "mini"
                )

        elif intent == IntentType.DEPROVISION:
            groups = match.groups()
            if len(groups) >= 2:
                count_str, variant_str = groups[0], groups[1]
                entities["count"] = int(count_str) if count_str.isdigit() else 1
                entities["type"] = self.VARIANT_MAPPINGS.get(
                    variant_str.lower(), "mini"
                )

        elif intent == IntentType.PAUSE_REFUNDS:
            entities["scope"] = "all"
            entities["duration"] = None  # Until manually resumed

        elif intent == IntentType.RESUME_REFUNDS:
            entities["scope"] = "all"

        elif intent == IntentType.ESCALATE:
            groups = match.groups()
            if groups:
                ticket_id = groups[0]
                entities["ticket_id"] = ticket_id
            # Extract reason if present
            reason_match = re.search(r"(?:because|due to|reason:?)\s+(.+)", text)
            if reason_match:
                entities["reason"] = reason_match.group(1).strip()

        elif intent == IntentType.STATUS:
            entities["detail_level"] = "summary"

        elif intent == IntentType.HELP:
            entities["topic"] = None

        return entities

    def _get_action(
        self,
        intent: IntentType,
        entities: Dict[str, Any]
    ) -> str:
        """
        Get action name from intent and entities.

        Args:
            intent: Matched intent
            entities: Extracted entities

        Returns:
            Action string
        """
        action_map = {
            IntentType.PROVISION: "provision",
            IntentType.DEPROVISION: "deprovision",
            IntentType.PAUSE_REFUNDS: "pause_refunds",
            IntentType.RESUME_REFUNDS: "resume_refunds",
            IntentType.ESCALATE: "escalate",
            IntentType.STATUS: "get_status",
            IntentType.HELP: "show_help",
            IntentType.UNKNOWN: "unknown",
        }
        return action_map.get(intent, "unknown")

    def _generate_suggestions(self, text: str) -> List[str]:
        """
        Generate command suggestions for unrecognized input.

        Args:
            text: Original text

        Returns:
            List of suggested commands
        """
        suggestions = []

        # Check for partial matches
        if "refund" in text:
            suggestions.append("pause all refunds")
            suggestions.append("resume all refunds")

        if "agent" in text or "mini" in text or "parwa" in text:
            suggestions.append("add 1 mini")
            suggestions.append("add 2 parwa")
            suggestions.append("add 1 high")

        if "ticket" in text or "escalate" in text:
            suggestions.append("escalate ticket 123")

        if "status" in text:
            suggestions.append("system status")

        # Always include help
        suggestions.append("help")

        return suggestions[:5]  # Limit to 5 suggestions

    def parse_batch(
        self,
        texts: List[str]
    ) -> List[ParsedCommand]:
        """
        Parse multiple commands at once.

        Args:
            texts: List of command texts

        Returns:
            List of ParsedCommand objects
        """
        return [self.parse(text) for text in texts]

    def get_available_intents(self) -> List[str]:
        """Get list of available intent types."""
        return [intent.value for intent in IntentType]

    def get_examples(self) -> Dict[str, List[str]]:
        """
        Get example commands for each intent.

        Returns:
            Dict mapping intent to example commands
        """
        return {
            IntentType.PROVISION.value: [
                "Add 2 Mini",
                "Provision 5 PARWA agents",
                "Spin up 1 High",
            ],
            IntentType.DEPROVISION.value: [
                "Remove 2 Mini",
                "Deprovision 1 PARWA",
            ],
            IntentType.PAUSE_REFUNDS.value: [
                "Pause all refunds",
                "Stop refunds",
            ],
            IntentType.RESUME_REFUNDS.value: [
                "Resume all refunds",
                "Enable refunds",
            ],
            IntentType.ESCALATE.value: [
                "Escalate ticket 123",
                "Escalate #456",
            ],
            IntentType.STATUS.value: [
                "System status",
                "What is the status",
            ],
            IntentType.HELP.value: [
                "Help",
                "Show commands",
            ],
        }
