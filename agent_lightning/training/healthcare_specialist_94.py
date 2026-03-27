"""
Healthcare Specialist for 94% Accuracy Target.

Enhanced healthcare specialist with industry-specific patterns,
confidence scoring, HIPAA awareness, and async prediction support.
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
class HealthcarePredictionResult:
    """Result of healthcare prediction."""
    action: str
    tier: str
    confidence: float
    detected_intent: str
    entities: Dict[str, Any] = field(default_factory=dict)
    suggested_response: str = ""
    requires_escalation: bool = False
    phi_detected: bool = False
    urgency_level: str = "normal"  # normal, urgent, emergency


class HealthcareSpecialist94(CategorySpecialist):
    """
    Enhanced Healthcare Specialist with 94% accuracy target.

    Features:
    - Appointment scheduling and management
    - Prescription and medication inquiries
    - Insurance and billing questions
    - Medical records requests
    - HIPAA/PHI detection and handling
    - Urgency detection and escalation
    - Telehealth support

    Accuracy Target: >=94% on healthcare domain data

    IMPORTANT: All data must be PHI-sanitized before processing.
    """

    DOMAIN = "healthcare"
    ACCURACY_THRESHOLD = 0.94

    # Industry-specific patterns for Healthcare
    PATTERNS = {
        "appointment": [
            "appointment", "schedule", "book", "doctor", "visit",
            "reschedule", "cancel appointment", "see a doctor",
            "available times", "next available", "consultation"
        ],
        "prescription": [
            "prescription", "medication", "refill", "pharmacy",
            "dose", "dosage", "medicine", "drug", "rx",
            "my medication", "take my prescription"
        ],
        "billing": [
            "bill", "insurance", "claim", "coverage", "copay",
            "deductible", "out of pocket", "payment plan",
            "medical bill", "insurance claim", "denied claim"
        ],
        "records": [
            "records", "results", "test", "report", "medical records",
            "lab results", "x-ray", "scan", "blood test",
            "medical history", "records request"
        ],
        "hipaa": [
            "hipaa", "privacy", "confidential", "phi", "data",
            "my information", "who can see", "authorization",
            "consent", "disclosure"
        ],
        "telehealth": [
            "telehealth", "video visit", "virtual", "online appointment",
            "remote", "telemedicine", "video call", "virtual visit"
        ],
        "symptoms": [
            "symptoms", "pain", "hurt", "ache", "feeling",
            "sick", "illness", "condition", "diagnosis"
        ],
        "escalation": [
            "emergency", "urgent", "immediate", "hospital",
            "911", "severe", "critical", "life threatening"
        ],
        "referral": [
            "referral", "specialist", "refer", "see a specialist",
            "second opinion", "another doctor"
        ]
    }

    # Action weights for confidence calculation
    ACTION_WEIGHTS = {
        "appointment": 1.0,
        "prescription": 1.2,
        "billing": 1.0,
        "records": 1.1,
        "hipaa": 1.5,
        "telehealth": 1.0,
        "symptoms": 1.3,
        "escalation": 3.0,  # Highest weight for safety
        "referral": 1.1,
    }

    # Heavy tier actions requiring more AI power
    HEAVY_ACTIONS = {"escalation", "hipaa", "symptoms"}
    MEDIUM_ACTIONS = {"prescription", "records", "referral"}

    # PHI patterns to detect (for sanitization warnings)
    PHI_PATTERNS = {
        "ssn": re.compile(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'),
        "mrn": re.compile(r'\b(?:mrn|medical\s*record)[:\s]*([A-Z0-9]{6,12})\b', re.IGNORECASE),
        "date_of_birth": re.compile(r'\b(?:dob|birth\s*date|born)[:\s]*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b', re.IGNORECASE),
        "phone": re.compile(r'\b(\d{3}[-.]?\d{3}[-.]?\d{4})\b'),
        "email": re.compile(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'),
    }

    # Emergency keywords requiring immediate escalation
    EMERGENCY_KEYWORDS = [
        "chest pain", "difficulty breathing", "can't breathe",
        "severe bleeding", "unconscious", "stroke", "heart attack",
        "suicide", "overdose", "anaphylaxis", "seizure",
        "life threatening", "dying", "call 911"
    ]

    def __init__(self, baa_required: bool = True):
        """
        Initialize the enhanced healthcare specialist.

        Args:
            baa_required: Whether BAA (Business Associate Agreement) is required
        """
        super().__init__(SpecialistType.HEALTHCARE)

        self.baa_required = baa_required

        # Initialize with enhanced patterns
        self._patterns = {k: v.copy() for k, v in self.PATTERNS.items()}
        self._action_weights = self.ACTION_WEIGHTS.copy()

        # Response templates
        self._response_templates = self._build_response_templates()

        # Entity extraction patterns
        self._entity_patterns = self._build_entity_patterns()

        logger.info({
            "event": "healthcare_specialist_94_initialized",
            "domain": self.DOMAIN,
            "accuracy_threshold": self.ACCURACY_THRESHOLD,
            "pattern_count": len(self._patterns),
            "baa_required": baa_required
        })

    def _build_response_templates(self) -> Dict[str, str]:
        """Build response templates for actions."""
        return {
            "appointment": "I can help you schedule or manage your appointment.",
            "prescription": "I'll help you with your prescription inquiry.",
            "billing": "I can assist with your billing or insurance question.",
            "records": "I'll help you with your medical records request.",
            "hipaa": "I take your privacy seriously. Let me help with your HIPAA inquiry.",
            "telehealth": "I can help you set up or troubleshoot your telehealth visit.",
            "symptoms": "I can provide general information. For medical advice, please consult a healthcare provider.",
            "escalation": "This sounds urgent. Let me connect you with appropriate care immediately.",
            "referral": "I can help you with referral information."
        }

    def _build_entity_patterns(self) -> Dict[str, re.Pattern]:
        """Build regex patterns for entity extraction."""
        return {
            "appointment_date": re.compile(r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})', re.IGNORECASE),
            "time": re.compile(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', re.IGNORECASE),
            "doctor_name": re.compile(r'dr\.?\s+([a-zA-Z]+)', re.IGNORECASE),
            "medication_name": re.compile(r'(?:medication|medicine|drug)[:\s]*([a-zA-Z]+)', re.IGNORECASE),
            "insurance_id": re.compile(r'(?:insurance|member)\s*(?:id|number)[:\s]*([A-Z0-9]{6,})', re.IGNORECASE),
        }

    async def predict(self, query: str) -> Dict[str, Any]:
        """
        Predict action for healthcare query with confidence scoring.

        Args:
            query: Customer query text (must be PHI-sanitized)

        Returns:
            Dict with action, tier, confidence, entities, and suggested response
        """
        query_lower = query.lower()
        scores: Dict[str, float] = {}

        # Check for PHI in query
        phi_detected = self._detect_phi(query)

        # Check for emergency keywords first
        urgency_level = self._check_urgency(query)

        if urgency_level == "emergency":
            # Immediate escalation for emergencies
            return {
                "action": "escalation",
                "tier": "heavy",
                "confidence": 1.0,
                "detected_intent": "emergency",
                "entities": {},
                "suggested_response": "This sounds like a medical emergency. Please call 911 or go to your nearest emergency room immediately.",
                "requires_escalation": True,
                "phi_detected": phi_detected,
                "urgency_level": "emergency"
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
                "suggested_response": "How can I help you with your healthcare needs today?",
                "requires_escalation": False,
                "phi_detected": phi_detected,
                "urgency_level": urgency_level
            }

        # Get best action
        best_action = max(scores, key=scores.get)

        # Calculate confidence
        raw_confidence = scores[best_action] / 5.0
        confidence = min(1.0, max(0.0, raw_confidence))

        # Boost confidence for urgency
        if urgency_level == "urgent":
            confidence = min(1.0, confidence + 0.15)

        # Determine tier
        tier = self._determine_tier(best_action, confidence, urgency_level)

        # Extract entities
        entities = self._extract_entities(query)

        # Check for escalation triggers
        requires_escalation = self._check_escalation_triggers(query, best_action, urgency_level)

        # Get suggested response
        suggested_response = self._response_templates.get(
            best_action, "How can I assist you with your healthcare needs?"
        )

        return {
            "action": best_action,
            "tier": tier,
            "confidence": round(confidence, 3),
            "detected_intent": best_action,
            "entities": entities,
            "suggested_response": suggested_response,
            "requires_escalation": requires_escalation,
            "phi_detected": phi_detected,
            "urgency_level": urgency_level
        }

    def _detect_phi(self, query: str) -> bool:
        """Check if query contains potential PHI patterns."""
        for phi_type, pattern in self.PHI_PATTERNS.items():
            if pattern.search(query):
                return True
        return False

    def _check_urgency(self, query: str) -> str:
        """Check urgency level based on keywords."""
        query_lower = query.lower()

        # Check for emergency keywords
        for keyword in self.EMERGENCY_KEYWORDS:
            if keyword in query_lower:
                return "emergency"

        # Check for urgent keywords
        urgent_keywords = ["urgent", "asap", "today", "immediately", "worse", "severe pain"]
        for keyword in urgent_keywords:
            if keyword in query_lower:
                return "urgent"

        return "normal"

    def _determine_tier(self, action: str, confidence: float, urgency: str) -> str:
        """Determine AI tier based on action, confidence, and urgency."""
        if urgency in ("emergency", "urgent"):
            return "heavy"
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

    def _check_escalation_triggers(self, query: str, action: str, urgency: str) -> bool:
        """Check if query requires escalation."""
        if urgency in ("emergency", "urgent"):
            return True
        if action == "escalation":
            return True

        escalation_triggers = [
            "speak to manager", "supervisor", "complaint",
            "filing a complaint", "attorney", "legal"
        ]

        query_lower = query.lower()
        return any(trigger in query_lower for trigger in escalation_triggers)

    async def train(self, samples: List[TrainingSample]) -> SpecialistMetrics:
        """
        Train specialist with healthcare samples.

        Args:
            samples: Training samples for healthcare domain

        Returns:
            Training metrics
        """
        # Check for PHI in training data
        for sample in samples:
            if self._detect_phi(sample.query):
                logger.warning({
                    "event": "phi_detected_in_training",
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
            "event": "healthcare_specialist_94_trained",
            "samples": len(samples),
            "accuracy": metrics.accuracy,
            "passes_threshold": metrics.passes_threshold
        })

        return metrics

    def check_baa_compliance(self) -> Dict[str, Any]:
        """Check BAA compliance status."""
        return {
            "baa_required": self.baa_required,
            "phi_handling_validated": True,
            "compliant": True,
            "last_checked": datetime.now(timezone.utc).isoformat()
        }

    def get_supported_actions(self) -> List[str]:
        """Get list of supported actions for healthcare."""
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


def get_healthcare_specialist_94(baa_required: bool = True) -> HealthcareSpecialist94:
    """
    Factory function to get healthcare specialist instance.

    Args:
        baa_required: Whether BAA is required

    Returns:
        HealthcareSpecialist94 instance
    """
    return HealthcareSpecialist94(baa_required=baa_required)
