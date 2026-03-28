"""Hallucination Detector Module - Week 55, Builder 3"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import logging
import re

logger = logging.getLogger(__name__)


class HallucinationType(Enum):
    FACTUAL = "factual"
    LOGICAL = "logical"
    INCONSISTENCY = "inconsistency"


@dataclass
class HallucinationResult:
    is_hallucination: bool
    hallucination_type: Optional[HallucinationType] = None
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


class HallucinationDetector:
    def __init__(self, confidence_threshold: float = 0.7):
        self.confidence_threshold = confidence_threshold
        self._patterns = {
            HallucinationType.FACTUAL: [
                r"\d{4}-\d{2}-\d{2}",  # Fake dates
                r"\b\d{3}-\d{2}-\d{4}\b",  # SSN-like patterns
            ],
            HallucinationType.LOGICAL: [
                r"therefore\s+\w+\s+is\s+not",
                r"because\s+.*\s+so\s+.*\s+not",
            ],
        }

    def detect(self, response: str, facts: Optional[List[str]] = None) -> HallucinationResult:
        evidence = []
        detected_types = []

        for h_type, patterns in self._patterns.items():
            for pattern in patterns:
                if re.search(pattern, response, re.IGNORECASE):
                    evidence.append(f"Pattern match: {pattern}")
                    detected_types.append(h_type)

        # Check for inconsistencies with provided facts
        if facts:
            for fact in facts:
                if fact.lower() in response.lower():
                    evidence.append(f"Fact verified: {fact[:50]}")

        is_hallucination = len(evidence) > 0 and len(detected_types) > 0
        confidence = min(1.0, len(evidence) * 0.3)

        return HallucinationResult(
            is_hallucination=is_hallucination,
            hallucination_type=detected_types[0] if detected_types else None,
            confidence=confidence,
            evidence=evidence,
        )

    def add_pattern(self, h_type: HallucinationType, pattern: str) -> None:
        if h_type not in self._patterns:
            self._patterns[h_type] = []
        self._patterns[h_type].append(pattern)

    def verify_fact(self, claim: str, knowledge_base: Dict[str, str]) -> bool:
        return any(claim.lower() in v.lower() for v in knowledge_base.values())
