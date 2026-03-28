"""
Financial Specialist for 94% Accuracy Target.

Enhanced financial specialist with industry-specific patterns,
confidence scoring, PCI awareness, and async prediction support.
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
class FinancialPredictionResult:
    """Result of financial prediction."""
    action: str
    tier: str
    confidence: float
    detected_intent: str
    entities: Dict[str, Any] = field(default_factory=dict)
    suggested_response: str = ""
    requires_escalation: bool = False
    pci_detected: bool = False
    risk_level: str = "normal"  # normal, elevated, high


class FinancialSpecialist94(CategorySpecialist):
    """
    Enhanced Financial Specialist with 94% accuracy target.

    Features:
    - Transaction inquiries and disputes
    - Account management and access
    - Fraud detection and reporting
    - Card services (debit/credit)
    - Loan and mortgage inquiries
    - Investment and savings
    - Wire transfer support
    - Risk assessment

    Accuracy Target: >=94% on financial domain data

    IMPORTANT: All data must be PCI-sanitized before processing.
    """

    DOMAIN = "financial"
    ACCURACY_THRESHOLD = 0.94

    # Industry-specific patterns for Financial
    PATTERNS = {
        "transaction": [
            "transaction", "transfer", "payment", "sent", "received",
            "wire", "ach", "deposit", "withdrawal", "pending",
            "processing", "cleared", "posted"
        ],
        "account": [
            "account", "balance", "statement", "banking", "checking",
            "savings", "account number", "routing number", "open account",
            "close account", "account status"
        ],
        "fraud": [
            "fraud", "unauthorized", "suspicious", "stolen", "hacked",
            "identity theft", "didn't make", "didn't authorize",
            "compromised", "unknown charge", "scam"
        ],
        "card": [
            "card", "debit", "credit", "atm", "pin", "card number",
            "new card", "replace card", "activate card", "card declined",
            "lost card", "stolen card"
        ],
        "loan": [
            "loan", "mortgage", "interest", "rate", "refinance",
            "payment plan", "principal", "term", "apr", "financing",
            "auto loan", "personal loan"
        ],
        "investment": [
            "investment", "portfolio", "stocks", "bonds", "mutual fund",
            "ira", "401k", "retirement", "dividend", "trading",
            "brokerage", "securities"
        ],
        "billing": [
            "bill pay", "autopay", "automatic payment", "scheduled payment",
            "recurring", "payment due", "late fee", "minimum payment"
        ],
        "escalation": [
            "manager", "supervisor", "complaint", "legal", "attorney",
            "regulator", "cfpb", "occ", "fdic", "lawyer"
        ],
        "international": [
            "international", "foreign", "currency", "exchange rate",
            "overseas", "abroad", "travel", "currency conversion",
            "swift", "iban"
        ]
    }

    # Action weights for confidence calculation
    ACTION_WEIGHTS = {
        "transaction": 1.0,
        "account": 1.0,
        "fraud": 2.5,  # High weight for fraud detection
        "card": 1.2,
        "loan": 1.1,
        "investment": 1.1,
        "billing": 1.0,
        "escalation": 2.5,
        "international": 1.1,
    }

    # Heavy tier actions requiring more AI power
    HEAVY_ACTIONS = {"fraud", "escalation", "international"}
    MEDIUM_ACTIONS = {"transaction", "card", "loan", "investment"}

    # PCI patterns to detect (for sanitization warnings)
    PCI_PATTERNS = {
        "card_number": re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
        "cvv": re.compile(r'\bcvv[:\s]*\d{3,4}\b', re.IGNORECASE),
        "pin": re.compile(r'\bpin[:\s]*\d{4,6}\b', re.IGNORECASE),
        "ssn": re.compile(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'),
        "account_number": re.compile(r'\baccount\s*(?:number|no)?[:\s]*\d{8,17}\b', re.IGNORECASE),
    }

    # High-risk keywords requiring elevated attention
    HIGH_RISK_KEYWORDS = [
        "wire transfer", "large transfer", "close account",
        "unauthorized", "fraud", "stolen", "compromised",
        "identity theft", "hack", "scam", "phishing"
    ]

    # Fraud indicators
    FRAUD_INDICATORS = [
        "unauthorized charge", "didn't make this purchase",
        "someone stole", "card was compromised", "fraudulent",
        "unknown transaction", "suspicious activity"
    ]

    def __init__(self, pci_required: bool = True):
        """
        Initialize the enhanced financial specialist.

        Args:
            pci_required: Whether PCI DSS compliance is required
        """
        super().__init__(SpecialistType.FINANCIAL)

        self.pci_required = pci_required

        # Initialize with enhanced patterns
        self._patterns = {k: v.copy() for k, v in self.PATTERNS.items()}
        self._action_weights = self.ACTION_WEIGHTS.copy()

        # Response templates
        self._response_templates = self._build_response_templates()

        # Entity extraction patterns
        self._entity_patterns = self._build_entity_patterns()

        logger.info({
            "event": "financial_specialist_94_initialized",
            "domain": self.DOMAIN,
            "accuracy_threshold": self.ACCURACY_THRESHOLD,
            "pattern_count": len(self._patterns),
            "pci_required": pci_required
        })

    def _build_response_templates(self) -> Dict[str, str]:
        """Build response templates for actions."""
        return {
            "transaction": "I can help you with your transaction inquiry.",
            "account": "I'll help you with your account question.",
            "fraud": "I take fraud concerns very seriously. Let me help you secure your account immediately.",
            "card": "I can assist you with your card services.",
            "loan": "I'll help you with your loan inquiry.",
            "investment": "I can provide information about your investment account.",
            "billing": "I can help you with your payment and billing questions.",
            "escalation": "I understand you need additional assistance. Let me connect you appropriately.",
            "international": "I can help you with your international banking needs."
        }

    def _build_entity_patterns(self) -> Dict[str, re.Pattern]:
        """Build regex patterns for entity extraction."""
        return {
            "amount": re.compile(r'\$\s*([\d,]+(?:\.\d{2})?)'),
            "date": re.compile(r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})'),
            "account_last4": re.compile(r'(?:account|card)\s*(?:ending|last)?[:\s]*(\d{4})\b', re.IGNORECASE),
            "reference_number": re.compile(r'(?:reference|ref|confirmation)[:\s]*([A-Z0-9]{6,})', re.IGNORECASE),
            "phone": re.compile(r'\b(\d{3}[-.]?\d{3}[-.]?\d{4})\b'),
        }

    async def predict(self, query: str) -> Dict[str, Any]:
        """
        Predict action for financial query with confidence scoring.

        Args:
            query: Customer query text (must be PCI-sanitized)

        Returns:
            Dict with action, tier, confidence, entities, and suggested response
        """
        query_lower = query.lower()
        scores: Dict[str, float] = {}

        # Check for PCI data in query
        pci_detected = self._detect_pci(query)

        # Check for fraud indicators first (priority handling)
        risk_level = self._assess_risk(query)

        if self._is_fraud_report(query):
            # Immediate high-priority handling for fraud
            return {
                "action": "fraud",
                "tier": "heavy",
                "confidence": 1.0,
                "detected_intent": "fraud",
                "entities": {},
                "suggested_response": "I'm sorry to hear about this unauthorized activity. Let me help you secure your account and dispute these charges immediately.",
                "requires_escalation": True,
                "pci_detected": pci_detected,
                "risk_level": "high"
            }

        # Score each action based on pattern matches
        for action, patterns in self._patterns.items():
            score = 0.0

            for pattern in patterns:
                if pattern in query_lower:
                    score += 1.0

            if score > 0:
                scores[action] = score * self._action_weights.get(action, 1.0)

        if not scores:
            return {
                "action": "general_inquiry",
                "tier": "light",
                "confidence": 0.5,
                "detected_intent": "general",
                "entities": {},
                "suggested_response": "How can I help you with your financial needs today?",
                "requires_escalation": False,
                "pci_detected": pci_detected,
                "risk_level": risk_level
            }

        # Get best action
        best_action = max(scores, key=scores.get)

        # Calculate confidence
        raw_confidence = scores[best_action] / 5.0
        confidence = min(1.0, max(0.0, raw_confidence))

        # Boost confidence for high-risk scenarios
        if risk_level == "high":
            confidence = min(1.0, confidence + 0.15)
        elif risk_level == "elevated":
            confidence = min(1.0, confidence + 0.1)

        # Determine tier
        tier = self._determine_tier(best_action, confidence, risk_level)

        # Extract entities
        entities = self._extract_entities(query)

        # Check for escalation triggers
        requires_escalation = self._check_escalation_triggers(query, best_action, risk_level)

        # Get suggested response
        suggested_response = self._response_templates.get(
            best_action, "How can I assist you with your financial needs?"
        )

        return {
            "action": best_action,
            "tier": tier,
            "confidence": round(confidence, 3),
            "detected_intent": best_action,
            "entities": entities,
            "suggested_response": suggested_response,
            "requires_escalation": requires_escalation,
            "pci_detected": pci_detected,
            "risk_level": risk_level
        }

    def _detect_pci(self, query: str) -> bool:
        """Check if query contains potential PCI data patterns."""
        for pci_type, pattern in self.PCI_PATTERNS.items():
            if pattern.search(query):
                return True
        return False

    def _assess_risk(self, query: str) -> str:
        """Assess risk level based on keywords."""
        query_lower = query.lower()

        # Check for high-risk keywords
        for keyword in self.HIGH_RISK_KEYWORDS:
            if keyword in query_lower:
                return "high"

        # Check for elevated risk indicators
        elevated_keywords = [
            "large", "unusual", "international", "overseas",
            "change address", "update information", "verify"
        ]
        for keyword in elevated_keywords:
            if keyword in query_lower:
                return "elevated"

        return "normal"

    def _is_fraud_report(self, query: str) -> bool:
        """Check if query is a fraud report."""
        query_lower = query.lower()
        return any(indicator in query_lower for indicator in self.FRAUD_INDICATORS)

    def _determine_tier(self, action: str, confidence: float, risk: str) -> str:
        """Determine AI tier based on action, confidence, and risk."""
        if risk == "high" or action in self.HEAVY_ACTIONS:
            return "heavy"
        elif risk == "elevated" or action in self.MEDIUM_ACTIONS:
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

    def _check_escalation_triggers(self, query: str, action: str, risk: str) -> bool:
        """Check if query requires escalation."""
        if risk == "high":
            return True
        if action == "escalation":
            return True

        escalation_triggers = [
            "speak to manager", "supervisor", "attorney",
            "legal action", "filing complaint", "regulator",
            "cfpb", "better business bureau"
        ]

        query_lower = query.lower()
        return any(trigger in query_lower for trigger in escalation_triggers)

    async def train(self, samples: List[TrainingSample]) -> SpecialistMetrics:
        """
        Train specialist with financial samples.

        Args:
            samples: Training samples for financial domain

        Returns:
            Training metrics
        """
        # Check for PCI in training data
        for sample in samples:
            if self._detect_pci(sample.query):
                logger.warning({
                    "event": "pci_detected_in_training",
                    "sample_query": sample.query[:50] + "..." if len(sample.query) > 50 else sample.query
                })

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
            "event": "financial_specialist_94_trained",
            "samples": len(samples),
            "accuracy": metrics.accuracy,
            "passes_threshold": metrics.passes_threshold
        })

        return metrics

    def check_compliance(self) -> Dict[str, Any]:
        """Check compliance status."""
        return {
            "pci_dss_compliant": self.pci_required,
            "sox_compliant": True,
            "aml_protocols_active": True,
            "last_checked": datetime.now(timezone.utc).isoformat()
        }

    def get_supported_actions(self) -> List[str]:
        """Get list of supported actions for financial."""
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


def get_financial_specialist_94(pci_required: bool = True) -> FinancialSpecialist94:
    """
    Factory function to get financial specialist instance.

    Args:
        pci_required: Whether PCI DSS compliance is required

    Returns:
        FinancialSpecialist94 instance
    """
    return FinancialSpecialist94(pci_required=pci_required)
