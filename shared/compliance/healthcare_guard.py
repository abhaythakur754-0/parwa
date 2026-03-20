"""
PARWA Healthcare Guard.

Provides HIPAA compliance functionality including BAA (Business Associate
Agreement) verification, PHI (Protected Health Information) protection,
and healthcare-specific compliance checks.

Key Features:
- BAA verification and tracking
- PHI detection and protection
- Audit logging for healthcare
- Minimum necessary standard enforcement
- Patient rights management
"""
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timedelta
from enum import Enum
import re

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class BAAStatus(str, Enum):
    """Business Associate Agreement status."""
    ACTIVE = "active"
    PENDING = "pending"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    NOT_REQUIRED = "not_required"  # For non-healthcare clients


class PHIType(str, Enum):
    """Types of Protected Health Information."""
    NAME = "name"
    ADDRESS = "address"
    DATE = "date"  # Any date related to individual
    PHONE = "phone"
    FAX = "fax"
    EMAIL = "email"
    SSN = "ssn"
    MEDICAL_RECORD_NUMBER = "medical_record_number"
    HEALTH_PLAN_NUMBER = "health_plan_number"
    ACCOUNT_NUMBER = "account_number"
    LICENSE = "license"
    VEHICLE = "vehicle"
    DEVICE = "device"
    URL = "url"
    IP_ADDRESS = "ip_address"
    BIOMETRIC = "biometric"
    PHOTO = "photo"
    ANY_UNIQUE_IDENTIFIER = "any_unique_identifier"


class AccessPurpose(str, Enum):
    """Valid purposes for PHI access under HIPAA."""
    TREATMENT = "treatment"
    PAYMENT = "payment"
    HEALTHCARE_OPERATIONS = "healthcare_operations"
    PATIENT_REQUEST = "patient_request"
    LEGAL_REQUIREMENT = "legal_requirement"
    PUBLIC_HEALTH = "public_health"
    RESEARCH = "research"
    EMERGENCY = "emergency"


class HealthcareClientType(str, Enum):
    """Types of healthcare clients."""
    COVERED_ENTITY = "covered_entity"  # Healthcare provider, plan, clearinghouse
    BUSINESS_ASSOCIATE = "business_associate"  # Works with covered entities
    SUBCONTRACTOR = "subcontractor"  # Works with business associates
    NON_HEALTHCARE = "non_healthcare"  # Not in healthcare space


class BAARecord(BaseModel):
    """Business Associate Agreement record."""
    baa_id: str
    client_id: str
    client_name: str
    client_type: HealthcareClientType
    status: BAAStatus = BAAStatus.PENDING
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    terminated_date: Optional[datetime] = None
    permitted_uses: List[AccessPurpose] = Field(default_factory=list)
    permitted_disclosures: List[str] = Field(default_factory=list)
    security_safeguards: List[str] = Field(default_factory=list)
    breach_notification_required: bool = Field(default=True)
    audit_trail_required: bool = Field(default=True)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class PHICheckResult(BaseModel):
    """Result from PHI access check."""
    access_granted: bool = False
    client_id: str
    baa_status: BAAStatus
    phi_detected: bool = False
    phi_types_found: List[PHIType] = Field(default_factory=list)
    access_purpose: Optional[AccessPurpose] = None
    minimum_necessary_applied: bool = False
    redacted_fields: List[str] = Field(default_factory=list)
    violations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    audit_logged: bool = False
    processing_time_ms: float = Field(default=0)

    model_config = ConfigDict(use_enum_values=True)


class PHIField(BaseModel):
    """Definition of a PHI field."""
    field_name: str
    phi_type: PHIType
    patterns: List[str] = Field(default_factory=list)
    example_values: List[str] = Field(default_factory=list)
    min_necessary_context: str = "Need to know basis only"

    model_config = ConfigDict()


class HealthcareGuardConfig(BaseModel):
    """Configuration for Healthcare Guard."""
    baa_expiry_warning_days: int = Field(default=30)
    audit_all_phi_access: bool = Field(default=True)
    enforce_minimum_necessary: bool = Field(default=True)
    log_phi_to_external: bool = Field(default=False)  # NEVER log PHI externally
    redaction_style: str = Field(default="[PHI_REDACTED]")
    breach_notification_hours: int = Field(default=72)  # HIPAA requirement

    model_config = ConfigDict()


# Standard PHI field definitions
PHI_FIELD_DEFINITIONS: Dict[str, PHIField] = {
    "patient_name": PHIField(
        field_name="patient_name",
        phi_type=PHIType.NAME,
        patterns=[r"^[A-Z][a-z]+ [A-Z][a-z]+$"],
        example_values=["John Smith", "Jane Doe"],
        min_necessary_context="Use initials when full name not required",
    ),
    "ssn": PHIField(
        field_name="ssn",
        phi_type=PHIType.SSN,
        patterns=[r"^\d{3}-\d{2}-\d{4}$", r"^\d{9}$"],
        example_values=["123-45-6789", "123456789"],
        min_necessary_context="Last 4 digits only when full SSN not required",
    ),
    "medical_record_number": PHIField(
        field_name="medical_record_number",
        phi_type=PHIType.MEDICAL_RECORD_NUMBER,
        patterns=[r"^MRN\d+$", r"^\d{8,12}$"],
        example_values=["MRN12345678", "123456789"],
        min_necessary_context="Full MRN only for active treatment",
    ),
    "date_of_birth": PHIField(
        field_name="date_of_birth",
        phi_type=PHIType.DATE,
        patterns=[r"^\d{4}-\d{2}-\d{2}$", r"^\d{2}/\d{2}/\d{4}$"],
        example_values=["1990-01-15", "01/15/1990"],
        min_necessary_context="Age or year only when exact DOB not required",
    ),
    "diagnosis_code": PHIField(
        field_name="diagnosis_code",
        phi_type=PHIType.ANY_UNIQUE_IDENTIFIER,
        patterns=[r"^[A-Z]\d{2}(\.\d{1,2})?$"],  # ICD-10 format
        example_values=["J18.9", "E11.9"],
        min_necessary_context="General category only when specific code not required",
    ),
}


class HealthcareGuard:
    """
    Healthcare Compliance Guard for PARWA.

    Provides HIPAA compliance functionality including BAA verification,
    PHI protection, and healthcare-specific compliance checks.

    Features:
    - BAA verification and tracking
    - PHI detection and protection
    - Minimum necessary enforcement
    - Audit logging
    """

    # PHI detection patterns
    PHI_PATTERNS = {
        PHIType.SSN: [
            re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            re.compile(r"\b\d{9}\b"),
        ],
        PHIType.PHONE: [
            re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
            re.compile(r"\(\d{3}\)\s*\d{3}[-.]?\d{4}"),
        ],
        PHIType.EMAIL: [
            re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        ],
        PHIType.MEDICAL_RECORD_NUMBER: [
            re.compile(r"\bMRN[\d]+\b", re.IGNORECASE),
            re.compile(r"\b[A-Z]{2}\d{8,}\b"),
        ],
        PHIType.DATE: [
            re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
            re.compile(r"\b\d{2}/\d{2}/\d{4}\b"),
            re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b", re.IGNORECASE),
        ],
        PHIType.HEALTH_PLAN_NUMBER: [
            re.compile(r"\b[A-Z]{2,3}\d{9,}\b"),
        ],
    }

    # Fields that should never be logged
    NEVER_LOG_FIELDS: Set[str] = {
        "ssn", "social_security_number", "tax_id",
        "diagnosis", "diagnosis_code", "icd_code",
        "medication", "prescription", "drug",
        "lab_result", "test_result", "pathology",
        "medical_history", "health_history",
        "mental_health", "psychiatric",
        "hiv_status", "hiv_test", "aids",
        "substance_abuse", "addiction", "rehab",
        "genetic", "dna", "genomic",
    }

    def __init__(
        self,
        config: Optional[HealthcareGuardConfig] = None
    ) -> None:
        """
        Initialize Healthcare Guard.

        Args:
            config: Optional configuration override
        """
        self.config = config or HealthcareGuardConfig()

        # BAA tracking
        self._baa_records: Dict[str, BAARecord] = {}

        # Statistics
        self._checks_performed = 0
        self._accesses_granted = 0
        self._accesses_denied = 0
        self._phi_detections = 0
        self._total_processing_time = 0.0

        logger.info({
            "event": "healthcare_guard_initialized",
            "audit_enabled": self.config.audit_all_phi_access,
            "minimum_necessary_enabled": self.config.enforce_minimum_necessary,
        })

    def register_baa(self, baa: BAARecord) -> BAARecord:
        """
        Register a Business Associate Agreement.

        Args:
            baa: BAA record to register

        Returns:
            Registered BAA record
        """
        self._baa_records[baa.client_id] = baa

        logger.info({
            "event": "baa_registered",
            "baa_id": baa.baa_id,
            "client_id": baa.client_id,
            "client_type": baa.client_type,
            "status": baa.status,
        })

        return baa

    def verify_baa(
        self,
        client_id: str,
        check_expiry: bool = True
    ) -> Dict[str, Any]:
        """
        Verify BAA status for a client.

        Args:
            client_id: Client identifier
            check_expiry: Whether to check expiry

        Returns:
            Dict with verification result
        """
        baa = self._baa_records.get(client_id)

        if not baa:
            return {
                "valid": False,
                "reason": "No BAA on file",
                "status": BAAStatus.NOT_REQUIRED,
            }

        if baa.status != BAAStatus.ACTIVE:
            return {
                "valid": False,
                "reason": f"BAA status is {baa.status}",
                "status": baa.status,
            }

        if check_expiry and baa.expiry_date:
            if datetime.now() > baa.expiry_date:
                return {
                    "valid": False,
                    "reason": "BAA has expired",
                    "status": BAAStatus.EXPIRED,
                }

            # Check for upcoming expiry
            days_until_expiry = (baa.expiry_date - datetime.now()).days
            if days_until_expiry <= self.config.baa_expiry_warning_days:
                logger.warning({
                    "event": "baa_expiring_soon",
                    "client_id": client_id,
                    "days_until_expiry": days_until_expiry,
                })

        return {
            "valid": True,
            "baa": baa,
            "status": baa.status,
        }

    def check_phi_access(
        self,
        client_id: str,
        data: Dict[str, Any],
        purpose: AccessPurpose,
        user_role: Optional[str] = None,
        requested_fields: Optional[List[str]] = None
    ) -> PHICheckResult:
        """
        Check if PHI access is permitted.

        Args:
            client_id: Client identifier
            data: Data to check for PHI
            purpose: Purpose of access
            user_role: Optional user role for minimum necessary
            requested_fields: Specific fields requested

        Returns:
            PHICheckResult with access decision
        """
        start_time = datetime.now()

        result = PHICheckResult(
            client_id=client_id,
            baa_status=BAAStatus.NOT_REQUIRED,
            access_purpose=purpose,
        )

        violations = []
        warnings = []

        # Verify BAA
        baa_check = self.verify_baa(client_id)

        if not baa_check.get("valid"):
            result.baa_status = baa_check.get("status", BAAStatus.NOT_REQUIRED)
            violations.append(f"BAA verification failed: {baa_check.get('reason')}")

        baa = baa_check.get("baa")

        # Check if purpose is permitted
        if baa and purpose not in baa.permitted_uses:
            warnings.append(
                f"Purpose '{purpose.value}' not in permitted uses for this BAA"
            )

        # Detect PHI in data
        phi_types = self._detect_phi(data)
        result.phi_detected = len(phi_types) > 0
        result.phi_types_found = list(phi_types)

        if result.phi_detected:
            self._phi_detections += 1

        # Apply minimum necessary standard
        if self.config.enforce_minimum_necessary and result.phi_detected:
            redacted = self._apply_minimum_necessary(
                data, purpose, requested_fields
            )
            result.redacted_fields = redacted
            result.minimum_necessary_applied = len(redacted) > 0

        # Determine access
        result.access_granted = len(violations) == 0

        # Audit logging
        if self.config.audit_all_phi_access and result.phi_detected:
            self._audit_phi_access(client_id, purpose, result)
            result.audit_logged = True

        # Finalize
        result.violations = violations
        result.warnings = warnings
        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000

        self._checks_performed += 1
        if result.access_granted:
            self._accesses_granted += 1
        else:
            self._accesses_denied += 1
        self._total_processing_time += result.processing_time_ms

        logger.info({
            "event": "phi_access_check",
            "client_id": client_id,
            "access_granted": result.access_granted,
            "phi_detected": result.phi_detected,
            "purpose": purpose.value,
        })

        return result

    def detect_phi_in_text(self, text: str) -> List[PHIType]:
        """
        Detect PHI types present in text.

        Args:
            text: Text to analyze

        Returns:
            List of PHI types detected
        """
        detected = set()

        for phi_type, patterns in self.PHI_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(text):
                    detected.add(phi_type)

        return list(detected)

    def redact_phi(
        self,
        data: Dict[str, Any],
        fields_to_redact: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Redact PHI from data.

        Args:
            data: Data to redact
            fields_to_redact: Specific fields (defaults to all PHI)

        Returns:
            Data with PHI redacted
        """
        if not isinstance(data, dict):
            return data

        target_fields = set(fields_to_redact or self.NEVER_LOG_FIELDS)
        target_fields.update(self.NEVER_LOG_FIELDS)

        def _redact_recursive(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {
                    k: (
                        self.config.redaction_style
                        if k.lower() in target_fields or k.lower() in [f.lower() for f in target_fields]
                        else _redact_recursive(v)
                    )
                    for k, v in obj.items()
                }
            elif isinstance(obj, list):
                return [_redact_recursive(item) for item in obj]
            return obj

        return _redact_recursive(data)

    def is_safe_to_log(self, data: Dict[str, Any]) -> bool:
        """
        Check if data is safe to log (no PHI).

        Args:
            data: Data to check

        Returns:
            True if safe to log
        """
        # Check for PHI fields
        data_str = str(data).lower()
        for field in self.NEVER_LOG_FIELDS:
            if field in data_str:
                return False

        # Check with patterns
        phi_types = self.detect_phi_in_text(str(data))
        return len(phi_types) == 0

    def create_safe_log_entry(
        self,
        data: Dict[str, Any],
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a PHI-safe log entry.

        Args:
            data: Original data
            context: Optional context description

        Returns:
            Safe dict for logging
        """
        safe_data = self.redact_phi(data)

        return {
            "context": context or "healthcare_data",
            "safe_fields": list(safe_data.keys()),
            "phi_redacted": self.is_safe_to_log(data) is False,
            "timestamp": datetime.now().isoformat(),
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Get Healthcare Guard statistics.

        Returns:
            Dict with stats
        """
        return {
            "checks_performed": self._checks_performed,
            "accesses_granted": self._accesses_granted,
            "accesses_denied": self._accesses_denied,
            "phi_detections": self._phi_detections,
            "baa_records": len(self._baa_records),
            "total_processing_time_ms": self._total_processing_time,
            "average_processing_time_ms": (
                self._total_processing_time / self._checks_performed
                if self._checks_performed > 0 else 0
            ),
        }

    def _detect_phi(self, data: Dict[str, Any]) -> Set[PHIType]:
        """Detect PHI types in data."""
        detected = set()

        def _check_recursive(obj: Any) -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    # Check field name
                    key_lower = k.lower()
                    for field_name, phi_field in PHI_FIELD_DEFINITIONS.items():
                        if field_name in key_lower or key_lower in self.NEVER_LOG_FIELDS:
                            detected.add(phi_field.phi_type)

                    # Check value
                    if isinstance(v, str):
                        phi_in_text = self.detect_phi_in_text(v)
                        detected.update(phi_in_text)
                    else:
                        _check_recursive(v)

            elif isinstance(obj, list):
                for item in obj:
                    _check_recursive(item)

        _check_recursive(data)
        return detected

    def _apply_minimum_necessary(
        self,
        data: Dict[str, Any],
        purpose: AccessPurpose,
        requested_fields: Optional[List[str]]
    ) -> List[str]:
        """Apply minimum necessary standard."""
        redacted = []

        # High-sensitivity fields that require explicit justification
        high_sensitivity = {
            "ssn", "mental_health", "hiv_status",
            "substance_abuse", "genetic", "psychiatric",
        }

        # For non-treatment purposes, redact high-sensitivity
        if purpose != AccessPurpose.TREATMENT:
            for field in high_sensitivity:
                if field in str(data).lower():
                    redacted.append(field)

        # If specific fields requested, redact others
        if requested_fields:
            all_fields = set(self._get_all_fields(data))
            requested_set = set(f.lower() for f in requested_fields)
            for field in all_fields:
                if field.lower() not in requested_set:
                    if any(hs in field.lower() for hs in high_sensitivity):
                        redacted.append(field)

        return redacted

    def _get_all_fields(self, data: Dict[str, Any], prefix: str = "") -> List[str]:
        """Get all field names recursively."""
        fields = []
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            fields.append(full_key)
            if isinstance(value, dict):
                fields.extend(self._get_all_fields(value, full_key))
        return fields

    def _audit_phi_access(
        self,
        client_id: str,
        purpose: AccessPurpose,
        result: PHICheckResult
    ) -> None:
        """Audit PHI access for HIPAA compliance."""
        # NEVER log actual PHI - only metadata
        logger.info({
            "event": "phi_access_audit",
            "client_id": client_id,
            "purpose": purpose.value,
            "access_granted": result.access_granted,
            "phi_types_detected": [t.value for t in result.phi_types_found],
            "minimum_necessary_applied": result.minimum_necessary_applied,
            "timestamp": datetime.now().isoformat(),
        })


def get_healthcare_guard() -> HealthcareGuard:
    """
    Get a default HealthcareGuard instance.

    Returns:
        HealthcareGuard instance
    """
    return HealthcareGuard()
