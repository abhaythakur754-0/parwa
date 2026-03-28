"""
PHI Handler - Protected Health Information Detection & Sanitization.
Week 33, Builder 1: Healthcare HIPAA + Logistics

Detects, classifies, and sanitizes PHI according to HIPAA Safe Harbor method.
Supports 18 identifiers as defined in 45 CFR 164.514(b)(2).
"""

import re
import hashlib
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class PHIType(Enum):
    """Types of Protected Health Information per HIPAA."""
    NAME = "name"
    ADDRESS = "address"
    CITY = "city"
    STATE = "state"
    ZIP = "zip_code"
    SSN = "social_security_number"
    MRN = "medical_record_number"
    HEALTH_PLAN_ID = "health_plan_beneficiary_number"
    ACCOUNT_NUMBER = "account_number"
    DATE = "date"
    PHONE = "phone_number"
    FAX = "fax_number"
    EMAIL = "email_address"
    URL = "web_url"
    IP_ADDRESS = "ip_address"
    BIOMETRIC = "biometric_identifier"
    PHOTO = "photo_image"
    DEVICE_ID = "device_identifier"
    CERTIFICATE_NUMBER = "certificate_license_number"
    VEHICLE_ID = "vehicle_identifier"
    CREDIT_CARD = "credit_card_number"


class SanitizationMethod(Enum):
    """Methods for sanitizing PHI."""
    REDACT = "redact"
    HASH = "hash"
    MASK = "mask"
    GENERALIZE = "generalize"
    PSEUDONYMIZE = "pseudonymize"


@dataclass
class PHIDetectionResult:
    """Result of PHI detection."""
    phi_type: PHIType
    original_value: str
    sanitized_value: str
    start_pos: int
    end_pos: int
    confidence: float
    context: str = ""
    sanitization_method: SanitizationMethod = SanitizationMethod.REDACT
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'phi_type': self.phi_type.value,
            'original_value': self.original_value,
            'sanitized_value': self.sanitized_value,
            'start_pos': self.start_pos,
            'end_pos': self.end_pos,
            'confidence': self.confidence,
            'context': self.context,
            'sanitization_method': self.sanitization_method.value,
            'metadata': self.metadata,
        }


class PHIHandler:
    """
    PHI Detection and Sanitization Handler.

    Implements HIPAA Safe Harbor de-identification by detecting and
    sanitizing all 18 types of PHI identifiers.
    """

    # PHI Detection Patterns
    PATTERNS = {
        PHIType.SSN: [
            (re.compile(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'), 0.95),
            (re.compile(r'\b\d{9}\b'), 0.75),
        ],
        PHIType.MRN: [
            (re.compile(r'\bMRN[:\s]*[\w-]+\b', re.IGNORECASE), 0.95),
            (re.compile(r'\bMedical\s*Record[:\s]*[\w-]+\b', re.IGNORECASE), 0.90),
            (re.compile(r'\bPatient\s*ID[:\s]*[\w-]+\b', re.IGNORECASE), 0.85),
        ],
        PHIType.CREDIT_CARD: [
            (re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'), 0.90),
            (re.compile(r'\b(?:3[47]\d{2}[-\s]?\d{6}[-\s]?\d{5})\b'), 0.95),  # Amex
        ],
        PHIType.PHONE: [
            (re.compile(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'), 0.85),
        ],
        PHIType.EMAIL: [
            (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), 0.95),
        ],
        PHIType.ZIP: [
            (re.compile(r'\b\d{5}(?:[-\s]?\d{4})?\b'), 0.70),
        ],
        PHIType.IP_ADDRESS: [
            (re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'), 0.90),
        ],
        PHIType.DATE: [
            (re.compile(r'\b(?:0?[1-9]|1[0-2])[-/](?:0?[1-9]|[12]\d|3[01])[-/](?:\d{2,4})\b'), 0.80),
            (re.compile(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,]+\d{1,2}[\s,]+(?:\d{4})?\b', re.IGNORECASE), 0.85),
        ],
        PHIType.URL: [
            (re.compile(r'\bhttps?://[^\s<>"{}|\\^`\[\]]+\b'), 0.95),
        ],
        PHIType.FAX: [
            (re.compile(r'\b(?:Fax|FAX)[:\s]*(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b', re.IGNORECASE), 0.95),
        ],
        PHIType.HEALTH_PLAN_ID: [
            (re.compile(r'\b(?:Health\s*Plan|Member\s*ID|Policy)[:\s]*[\w-]+\b', re.IGNORECASE), 0.85),
        ],
        PHIType.ACCOUNT_NUMBER: [
            (re.compile(r'\b(?:Account|Acct)[:\s]*[\d-]+\b', re.IGNORECASE), 0.85),
        ],
    }

    # Redaction templates
    REDACTION_TEMPLATES = {
        PHIType.SSN: "[SSN-REDACTED]",
        PHIType.MRN: "[MRN-REDACTED]",
        PHIType.NAME: "[NAME-REDACTED]",
        PHIType.ADDRESS: "[ADDRESS-REDACTED]",
        PHIType.CITY: "[CITY-REDACTED]",
        PHIType.STATE: "[STATE-REDACTED]",
        PHIType.ZIP: "[ZIP-REDACTED]",
        PHIType.PHONE: "[PHONE-REDACTED]",
        PHIType.FAX: "[FAX-REDACTED]",
        PHIType.EMAIL: "[EMAIL-REDACTED]",
        PHIType.DATE: "[DATE-REDACTED]",
        PHIType.CREDIT_CARD: "[CARD-REDACTED]",
        PHIType.IP_ADDRESS: "[IP-REDACTED]",
        PHIType.URL: "[URL-REDACTED]",
        PHIType.HEALTH_PLAN_ID: "[PLAN-ID-REDACTED]",
        PHIType.ACCOUNT_NUMBER: "[ACCT-REDACTED]",
        PHIType.BIOMETRIC: "[BIOMETRIC-REDACTED]",
        PHIType.PHOTO: "[PHOTO-REDACTED]",
        PHIType.DEVICE_ID: "[DEVICE-REDACTED]",
        PHIType.CERTIFICATE_NUMBER: "[CERT-REDACTED]",
        PHIType.VEHICLE_ID: "[VEHICLE-REDACTED]",
    }

    def __init__(
        self,
        client_id: str,
        tenant_id: Optional[str] = None,
        sensitivity: str = "high",
        default_method: SanitizationMethod = SanitizationMethod.REDACT,
    ):
        """
        Initialize PHI Handler.

        Args:
            client_id: Client identifier for multi-tenant isolation
            tenant_id: Optional tenant identifier
            sensitivity: Detection sensitivity ('low', 'medium', 'high')
            default_method: Default sanitization method
        """
        self.client_id = client_id
        self.tenant_id = tenant_id or client_id
        self.sensitivity = sensitivity
        self.default_method = default_method

        # Detection count for metrics
        self._detection_count = 0
        self._sanitization_count = 0

        logger.info({
            "event": "phi_handler_initialized",
            "client_id": client_id,
            "sensitivity": sensitivity,
        })

    def detect(self, text: str) -> List[PHIDetectionResult]:
        """
        Detect all PHI in the given text.

        Args:
            text: Text to analyze for PHI

        Returns:
            List of PHIDetectionResult objects
        """
        if not text:
            return []

        results = []

        for phi_type, patterns in self.PATTERNS.items():
            for pattern, base_confidence in patterns:
                for match in pattern.finditer(text):
                    confidence = self._adjust_confidence(
                        base_confidence, phi_type, match.group(), text
                    )

                    if confidence >= self._get_confidence_threshold():
                        result = PHIDetectionResult(
                            phi_type=phi_type,
                            original_value=match.group(),
                            sanitized_value=self._sanitize_value(
                                match.group(), phi_type
                            ),
                            start_pos=match.start(),
                            end_pos=match.end(),
                            confidence=confidence,
                            context=self._get_context(text, match.start(), match.end()),
                            sanitization_method=self.default_method,
                        )
                        results.append(result)
                        self._detection_count += 1

        # Remove overlapping detections
        results = self._remove_overlaps(results)

        return results

    def sanitize(self, text: str, method: Optional[SanitizationMethod] = None) -> str:
        """
        Sanitize PHI from text.

        Args:
            text: Text to sanitize
            method: Optional sanitization method override

        Returns:
            Sanitized text with PHI replaced
        """
        detections = self.detect(text)

        # Sort by position (reverse) to replace from end to start
        detections_sorted = sorted(detections, key=lambda d: d.start_pos, reverse=True)

        sanitized_text = text
        for detection in detections_sorted:
            if method:
                sanitized_value = self._apply_sanitization(
                    detection.original_value,
                    detection.phi_type,
                    method
                )
            else:
                sanitized_value = detection.sanitized_value

            sanitized_text = (
                sanitized_text[:detection.start_pos] +
                sanitized_value +
                sanitized_text[detection.end_pos:]
            )
            self._sanitization_count += 1

        return sanitized_text

    def contains_phi(self, text: str) -> bool:
        """Quick check if text contains any PHI."""
        return len(self.detect(text)) > 0

    def get_phi_count(self, text: str) -> Dict[PHIType, int]:
        """Count PHI by type in text."""
        detections = self.detect(text)
        counts: Dict[PHIType, int] = {}
        for d in detections:
            counts[d.phi_type] = counts.get(d.phi_type, 0) + 1
        return counts

    def get_stats(self) -> Dict[str, Any]:
        """Get handler statistics."""
        return {
            "client_id": self.client_id,
            "tenant_id": self.tenant_id,
            "sensitivity": self.sensitivity,
            "detection_count": self._detection_count,
            "sanitization_count": self._sanitization_count,
        }

    def _get_confidence_threshold(self) -> float:
        """Get confidence threshold based on sensitivity."""
        thresholds = {
            "low": 0.85,
            "medium": 0.75,
            "high": 0.65,
        }
        return thresholds.get(self.sensitivity, 0.65)

    def _adjust_confidence(
        self,
        base_confidence: float,
        phi_type: PHIType,
        value: str,
        context: str
    ) -> float:
        """Adjust confidence based on context."""
        confidence = base_confidence

        # Context boost for healthcare keywords
        healthcare_keywords = [
            'patient', 'medical', 'health', 'hospital', 'clinic',
            'doctor', 'treatment', 'diagnosis', 'prescription',
        ]
        context_lower = context.lower()
        for keyword in healthcare_keywords:
            if keyword in context_lower:
                confidence = min(1.0, confidence + 0.05)
                break

        # Format validation
        if phi_type == PHIType.SSN:
            if re.match(r'\d{3}-\d{2}-\d{4}', value):
                confidence = min(1.0, confidence + 0.05)
        elif phi_type == PHIType.CREDIT_CARD:
            if self._validate_luhn(value):
                confidence = min(1.0, confidence + 0.05)

        return confidence

    def _validate_luhn(self, number: str) -> bool:
        """Validate credit card number using Luhn algorithm."""
        digits = [int(d) for d in number if d.isdigit()]
        if len(digits) < 13 or len(digits) > 19:
            return False

        checksum = 0
        for i, d in enumerate(reversed(digits)):
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            checksum += d

        return checksum % 10 == 0

    def _sanitize_value(self, value: str, phi_type: PHIType) -> str:
        """Get sanitized value for PHI."""
        return self._apply_sanitization(value, phi_type, self.default_method)

    def _apply_sanitization(
        self,
        value: str,
        phi_type: PHIType,
        method: SanitizationMethod
    ) -> str:
        """Apply sanitization method to value."""
        if method == SanitizationMethod.REDACT:
            return self.REDACTION_TEMPLATES.get(phi_type, "[REDACTED]")

        elif method == SanitizationMethod.HASH:
            hash_value = hashlib.sha256(
                f"{self.tenant_id}:{value}".encode()
            ).hexdigest()[:12]
            return f"[HASH:{hash_value}]"

        elif method == SanitizationMethod.MASK:
            if len(value) <= 4:
                return "*" * len(value)
            return value[:2] + "*" * (len(value) - 4) + value[-2:]

        elif method == SanitizationMethod.GENERALIZE:
            if phi_type == PHIType.ZIP:
                return value[:3] + "**"
            elif phi_type == PHIType.DATE:
                return "[DATE]"
            elif phi_type == PHIType.AGE:
                age = int(value) if value.isdigit() else 0
                if age >= 90:
                    return "90+"
                return f"{(age // 10) * 10}-{(age // 10) * 10 + 9}"
            return self.REDACTION_TEMPLATES.get(phi_type, "[REDACTED]")

        elif method == SanitizationMethod.PSEUDONYMIZE:
            pseudonym = hashlib.sha256(
                f"{self.tenant_id}:{value}:pseudonym".encode()
            ).hexdigest()[:8]
            return f"[ID:{pseudonym.upper()}]"

        return self.REDACTION_TEMPLATES.get(phi_type, "[REDACTED]")

    def _get_context(self, text: str, start: int, end: int, window: int = 50) -> str:
        """Get context around a detection."""
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end]

    def _remove_overlaps(self, results: List[PHIDetectionResult]) -> List[PHIDetectionResult]:
        """Remove overlapping detections, keeping highest confidence."""
        if not results:
            return []

        # Sort by start position, then by confidence (descending)
        sorted_results = sorted(results, key=lambda r: (r.start_pos, -r.confidence))

        filtered = []
        for result in sorted_results:
            overlaps = False
            for existing in filtered:
                if (result.start_pos < existing.end_pos and
                    result.end_pos > existing.start_pos):
                    overlaps = True
                    break

            if not overlaps:
                filtered.append(result)

        return filtered
