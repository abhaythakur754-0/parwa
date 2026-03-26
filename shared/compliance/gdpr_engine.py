"""
PARWA GDPR Engine.

Provides GDPR compliance functionality including data export (right to access),
data erasure (right to be forgotten), and PII management for customer data.

Key Features:
- Data portability exports (Article 20)
- Right to erasure (Article 17)
- PII masking and anonymization
- Consent record tracking
- Data retention management
"""
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import json

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger
from shared.core_functions.config import get_settings

logger = get_logger(__name__)


class GDPRRequestType(str, Enum):
    """Types of GDPR requests."""
    ACCESS = "access"  # Right to access (Article 15)
    PORTABILITY = "portability"  # Right to portability (Article 20)
    ERASURE = "erasure"  # Right to erasure (Article 17)
    RECTIFICATION = "rectification"  # Right to rectification (Article 16)
    RESTRICTION = "restriction"  # Right to restriction (Article 18)


class GDPRRequestStatus(str, Enum):
    """Status of GDPR request."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class PIIFieldType(str, Enum):
    """Types of PII fields."""
    NAME = "name"
    EMAIL = "email"
    PHONE = "phone"
    ADDRESS = "address"
    SSN = "ssn"
    PASSPORT = "passport"
    DATE_OF_BIRTH = "date_of_birth"
    FINANCIAL = "financial"
    HEALTH = "health"
    BIOMETRIC = "biometric"
    LOCATION = "location"
    IP_ADDRESS = "ip_address"
    COOKIE = "cookie"
    DEVICE_ID = "device_id"


class DataCategory(str, Enum):
    """Categories of personal data."""
    IDENTITY = "identity"
    CONTACT = "contact"
    FINANCIAL = "financial"
    BEHAVIORAL = "behavioral"
    TECHNICAL = "technical"
    COMMUNICATION = "communication"
    TRANSACTION = "transaction"


class GDPRRequest(BaseModel):
    """GDPR request model."""
    request_id: str
    request_type: GDPRRequestType
    user_id: str
    status: GDPRRequestStatus = GDPRRequestStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    processing_time_ms: float = Field(default=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class DataExport(BaseModel):
    """GDPR data export result."""
    request_id: str
    user_id: str
    export_version: str = "1.0"
    generated_at: datetime = Field(default_factory=datetime.now)
    data_categories: Dict[str, Any] = Field(default_factory=dict)
    data_sources: List[str] = Field(default_factory=list)
    total_records: int = Field(default=0)
    file_format: str = "json"
    checksum: Optional[str] = None
    expires_at: Optional[datetime] = None
    processing_time_ms: float = Field(default=0)

    model_config = ConfigDict()


class ErasureResult(BaseModel):
    """GDPR erasure result."""
    request_id: str
    user_id: str
    success: bool = False
    records_processed: int = Field(default=0)
    records_erased: int = Field(default=0)
    records_retained: int = Field(default=0)
    retention_reasons: List[str] = Field(default_factory=list)
    anonymized_fields: List[str] = Field(default_factory=list)
    processing_time_ms: float = Field(default=0)
    completed_at: Optional[datetime] = None

    model_config = ConfigDict()


class GDPREngineConfig(BaseModel):
    """Configuration for GDPR Engine."""
    retention_days: int = Field(default=365)
    export_expiry_days: int = Field(default=30)
    include_metadata: bool = Field(default=True)
    anonymize_instead_of_delete: bool = Field(default=True)
    require_verification: bool = Field(default=True)
    allowed_retention_reasons: List[str] = Field(
        default_factory=lambda: [
            "legal_obligation",
            "contract_performance",
            "legitimate_interest",
            "public_interest",
            "legal_claims",
        ]
    )

    model_config = ConfigDict()


class GDPREngine:
    """
    GDPR Compliance Engine for PARWA.

    Provides GDPR compliance functionality including data export,
    erasure, and PII management.

    Features:
    - Data portability exports
    - Right to erasure (soft-delete)
    - PII masking and anonymization
    - Consent tracking integration
    """

    # PII fields configuration
    PII_FIELDS: Dict[str, PIIFieldType] = {
        "email": PIIFieldType.EMAIL,
        "phone": PIIFieldType.PHONE,
        "first_name": PIIFieldType.NAME,
        "last_name": PIIFieldType.NAME,
        "address": PIIFieldType.ADDRESS,
        "city": PIIFieldType.ADDRESS,
        "zip": PIIFieldType.ADDRESS,
        "country": PIIFieldType.ADDRESS,
        "ssn": PIIFieldType.SSN,
        "date_of_birth": PIIFieldType.DATE_OF_BIRTH,
        "ip_address": PIIFieldType.IP_ADDRESS,
        "device_id": PIIFieldType.DEVICE_ID,
        "credit_card": PIIFieldType.FINANCIAL,
        "bank_account": PIIFieldType.FINANCIAL,
    }

    def __init__(
        self,
        config: Optional[GDPREngineConfig] = None,
        data_fetcher: Optional[Callable[[str], Dict[str, Any]]] = None,
        data_deleter: Optional[Callable[[str, List[str]], int]] = None
    ) -> None:
        """
        Initialize GDPR Engine.

        Args:
            config: Optional configuration override
            data_fetcher: Optional function to fetch user data
            data_deleter: Optional function to delete user data
        """
        self.config = config or GDPREngineConfig()
        self._data_fetcher = data_fetcher
        self._data_deleter = data_deleter

        # Load settings
        self._settings = get_settings()

        # Tracking
        self._exports_generated = 0
        self._erasures_completed = 0
        self._total_records_processed = 0
        self._total_processing_time = 0.0

        logger.info({
            "event": "gdpr_engine_initialized",
            "retention_days": self.config.retention_days,
            "anonymize_enabled": self.config.anonymize_instead_of_delete,
        })

    def create_access_request(
        self,
        user_id: str,
        request_type: GDPRRequestType = GDPRRequestType.ACCESS
    ) -> GDPRRequest:
        """
        Create a GDPR request for data access.

        Args:
            user_id: User identifier
            request_type: Type of GDPR request

        Returns:
            GDPRRequest tracking object
        """
        request_id = self._generate_request_id(user_id, request_type)

        request = GDPRRequest(
            request_id=request_id,
            request_type=request_type,
            user_id=user_id,
            status=GDPRRequestStatus.PENDING,
        )

        logger.info({
            "event": "gdpr_request_created",
            "request_id": request_id,
            "request_type": request_type.value,
            "user_id": user_id,
        })

        return request

    def export_user_data(
        self,
        user_id: str,
        request: Optional[GDPRRequest] = None,
        include_pii: bool = False
    ) -> DataExport:
        """
        Export all user data for GDPR portability.

        Args:
            user_id: User identifier
            request: Optional associated GDPR request
            include_pii: Whether to include PII (usually False)

        Returns:
            DataExport with all user data
        """
        start_time = datetime.now()
        request_id = request.request_id if request else self._generate_request_id(
            user_id, GDPRRequestType.PORTABILITY
        )

        # Fetch user data
        if self._data_fetcher:
            raw_data = self._data_fetcher(user_id)
        else:
            raw_data = self._mock_fetch_data(user_id)

        # Organize by data category
        categorized_data = self._categorize_data(raw_data)

        # Mask PII unless explicitly included
        if not include_pii:
            categorized_data = self._mask_pii_in_export(categorized_data)

        # Calculate totals
        total_records = sum(
            len(records) if isinstance(records, list) else 1
            for records in categorized_data.values()
        )

        # Generate checksum
        data_str = json.dumps(categorized_data, sort_keys=True, default=str)
        checksum = hashlib.sha256(data_str.encode()).hexdigest()

        # Set expiry
        expires_at = datetime.now() + timedelta(days=self.config.export_expiry_days)

        export = DataExport(
            request_id=request_id,
            user_id=user_id,
            data_categories=categorized_data,
            data_sources=list(categorized_data.keys()),
            total_records=total_records,
            checksum=checksum,
            expires_at=expires_at,
        )

        # Finalize
        export.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        self._exports_generated += 1
        self._total_records_processed += total_records
        self._total_processing_time += export.processing_time_ms

        logger.info({
            "event": "gdpr_export_completed",
            "request_id": request_id,
            "user_id": user_id,
            "total_records": total_records,
            "processing_time_ms": export.processing_time_ms,
        })

        return export

    def process_erasure_request(
        self,
        user_id: str,
        request: Optional[GDPRRequest] = None,
        retention_exceptions: Optional[List[str]] = None
    ) -> ErasureResult:
        """
        Process a GDPR erasure request (right to be forgotten).

        Args:
            user_id: User identifier
            request: Optional associated GDPR request
            retention_exceptions: Fields to retain with legal basis

        Returns:
            ErasureResult with deletion status
        """
        start_time = datetime.now()
        request_id = request.request_id if request else self._generate_request_id(
            user_id, GDPRRequestType.ERASURE
        )

        result = ErasureResult(
            request_id=request_id,
            user_id=user_id,
        )

        try:
            # Identify all data fields
            if self._data_fetcher:
                user_data = self._data_fetcher(user_id)
            else:
                user_data = self._mock_fetch_data(user_id)

            all_fields = self._get_all_fields(user_data)
            result.records_processed = len(all_fields)

            # Determine fields to retain
            exceptions = retention_exceptions or []
            fields_to_retain = self._validate_retention_exceptions(exceptions)
            result.retention_reasons = fields_to_retain.get("reasons", [])

            # Fields to erase/anonymize
            fields_to_process = [
                f for f in all_fields
                if f not in fields_to_retain.get("fields", [])
            ]

            if self.config.anonymize_instead_of_delete:
                # Anonymize PII fields
                result.anonymized_fields = [
                    f for f in fields_to_process
                    if f in self.PII_FIELDS
                ]
                result.records_erased = len(fields_to_process)

                if self._data_deleter:
                    deleted = self._data_deleter(user_id, fields_to_process)
                    result.records_erased = deleted
            else:
                # Hard delete
                if self._data_deleter:
                    deleted = self._data_deleter(user_id, fields_to_process)
                    result.records_erased = deleted
                else:
                    result.records_erased = len(fields_to_process)

            result.records_retained = len(fields_to_retain.get("fields", []))
            result.success = True

        except Exception as e:
            result.success = False
            logger.error({
                "event": "gdpr_erasure_failed",
                "request_id": request_id,
                "user_id": user_id,
                "error": str(e),
            })

        # Finalize
        result.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        result.completed_at = datetime.now()
        self._erasures_completed += 1
        self._total_processing_time += result.processing_time_ms

        logger.info({
            "event": "gdpr_erasure_completed",
            "request_id": request_id,
            "user_id": user_id,
            "success": result.success,
            "records_erased": result.records_erased,
            "records_retained": result.records_retained,
        })

        return result

    def mask_pii(
        self,
        data: Dict[str, Any],
        fields_to_mask: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Mask PII fields in data.

        Args:
            data: Data dictionary to mask
            fields_to_mask: Specific fields to mask (defaults to all PII)

        Returns:
            Data with PII masked
        """
        if not isinstance(data, dict):
            return data

        masked = data.copy()
        target_fields = fields_to_mask or list(self.PII_FIELDS.keys())

        def _mask_recursive(obj: Any, path: str = "") -> Any:
            if isinstance(obj, dict):
                return {
                    k: "[REDACTED]" if k.lower() in [f.lower() for f in target_fields]
                    else _mask_recursive(v, f"{path}.{k}" if path else k)
                    for k, v in obj.items()
                }
            elif isinstance(obj, list):
                return [_mask_recursive(item, f"{path}[]") for item in obj]
            return obj

        return _mask_recursive(masked)

    def anonymize_data(
        self,
        data: Dict[str, Any],
        method: str = "hash"
    ) -> Dict[str, Any]:
        """
        Anonymize PII in data using specified method.

        Args:
            data: Data to anonymize
            method: Anonymization method (hash, random, generalize)

        Returns:
            Anonymized data
        """
        if not isinstance(data, dict):
            return data

        anonymized = data.copy()

        for field_name in self.PII_FIELDS:
            if field_name in anonymized:
                value = anonymized[field_name]
                if value is None:
                    continue

                if method == "hash":
                    anonymized[field_name] = self._hash_value(str(value))
                elif method == "random":
                    anonymized[field_name] = self._random_replacement(
                        self.PII_FIELDS[field_name]
                    )
                elif method == "generalize":
                    anonymized[field_name] = self._generalize_value(
                        value, self.PII_FIELDS[field_name]
                    )

        return anonymized

    def check_retention(
        self,
        created_at: datetime,
        retention_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Check if data is within retention period.

        Args:
            created_at: When data was created
            retention_days: Override retention period

        Returns:
            Dict with retention status
        """
        days = retention_days or self.config.retention_days
        age_days = (datetime.now() - created_at).days

        return {
            "within_retention": age_days <= days,
            "age_days": age_days,
            "retention_days": days,
            "days_until_expiry": max(0, days - age_days),
            "should_delete": age_days > days,
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Get GDPR engine statistics.

        Returns:
            Dict with stats
        """
        return {
            "exports_generated": self._exports_generated,
            "erasures_completed": self._erasures_completed,
            "total_records_processed": self._total_records_processed,
            "total_processing_time_ms": self._total_processing_time,
            "average_processing_time_ms": (
                self._total_processing_time /
                (self._exports_generated + self._erasures_completed)
                if (self._exports_generated + self._erasures_completed) > 0 else 0
            ),
        }

    def _generate_request_id(
        self,
        user_id: str,
        request_type: GDPRRequestType
    ) -> str:
        """Generate unique request ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        hash_input = f"{user_id}:{request_type.value}:{timestamp}"
        short_hash = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        return f"GDPR-{request_type.value.upper()}-{short_hash}"

    def _mock_fetch_data(self, user_id: str) -> Dict[str, Any]:
        """Mock data fetcher for testing."""
        return {
            "identity": {
                "user_id": user_id,
                "email": "user@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "phone": "+1234567890",
            },
            "transactions": [
                {"id": "txn_001", "amount": 100.00, "date": "2024-01-15"},
                {"id": "txn_002", "amount": 250.00, "date": "2024-02-20"},
            ],
            "preferences": {
                "newsletter": True,
                "notifications": "email",
            },
            "technical": {
                "ip_address": "192.168.1.1",
                "device_id": "device_abc123",
                "last_login": "2024-03-01T10:30:00Z",
            },
        }

    def _categorize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Categorize data by GDPR categories."""
        categories = {
            DataCategory.IDENTITY.value: {},
            DataCategory.CONTACT.value: {},
            DataCategory.FINANCIAL.value: {},
            DataCategory.TECHNICAL.value: {},
            DataCategory.BEHAVIORAL.value: {},
            DataCategory.COMMUNICATION.value: {},
            DataCategory.TRANSACTION.value: {},
        }

        # Map fields to categories
        identity_fields = ["user_id", "first_name", "last_name", "date_of_birth"]
        contact_fields = ["email", "phone", "address", "city", "country"]
        financial_fields = ["credit_card", "bank_account", "transactions"]
        technical_fields = ["ip_address", "device_id", "user_agent"]

        for key, value in data.items():
            if key.lower() in identity_fields:
                categories[DataCategory.IDENTITY.value][key] = value
            elif key.lower() in contact_fields:
                categories[DataCategory.CONTACT.value][key] = value
            elif key.lower() in financial_fields or key == "transactions":
                categories[DataCategory.FINANCIAL.value][key] = value
            elif key.lower() in technical_fields:
                categories[DataCategory.TECHNICAL.value][key] = value
            else:
                categories[DataCategory.BEHAVIORAL.value][key] = value

        # Remove empty categories
        return {k: v for k, v in categories.items() if v}

    def _mask_pii_in_export(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Mask PII in export data."""
        return self.mask_pii(data)

    def _get_all_fields(self, data: Dict[str, Any], prefix: str = "") -> List[str]:
        """Get all field names recursively."""
        fields = []
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            fields.append(full_key)
            if isinstance(value, dict):
                fields.extend(self._get_all_fields(value, full_key))
        return fields

    def _validate_retention_exceptions(
        self,
        exceptions: List[str]
    ) -> Dict[str, Any]:
        """Validate retention exceptions against allowed reasons."""
        valid_fields = []
        reasons = []

        for exception in exceptions:
            if exception in self.config.allowed_retention_reasons:
                reasons.append(exception)

        return {
            "fields": valid_fields,
            "reasons": reasons,
        }

    def _hash_value(self, value: str) -> str:
        """Hash a value for anonymization."""
        return hashlib.sha256(value.encode()).hexdigest()[:16]

    def _random_replacement(self, field_type: PIIFieldType) -> str:
        """Generate random replacement for PII field."""
        replacements = {
            PIIFieldType.NAME: "[ANONYMIZED]",
            PIIFieldType.EMAIL: "anonymous@example.com",
            PIIFieldType.PHONE: "+0000000000",
            PIIFieldType.ADDRESS: "[ADDRESS REMOVED]",
            PIIFieldType.SSN: "XXX-XX-XXXX",
            PIIFieldType.DATE_OF_BIRTH: "XXXX-XX-XX",
            PIIFieldType.IP_ADDRESS: "0.0.0.0",
            PIIFieldType.DEVICE_ID: "[DEVICE_ANONYMIZED]",
            PIIFieldType.FINANCIAL: "[FINANCIAL_DATA_REMOVED]",
        }
        return replacements.get(field_type, "[REDACTED]")

    def _generalize_value(
        self,
        value: Any,
        field_type: PIIFieldType
    ) -> str:
        """Generalize a value (reduce specificity)."""
        if field_type == PIIFieldType.AGE or field_type == PIIFieldType.DATE_OF_BIRTH:
            # Generalize age to range
            if isinstance(value, (int, float)):
                age = int(value)
                if age < 18:
                    return "under_18"
                elif age < 25:
                    return "18-24"
                elif age < 35:
                    return "25-34"
                elif age < 45:
                    return "35-44"
                elif age < 55:
                    return "45-54"
                else:
                    return "55+"
        elif field_type == PIIFieldType.LOCATION:
            # Keep only country/region
            return str(value).split(",")[-1].strip() if "," in str(value) else "[LOCATION]"

        return "[GENERALIZED]"


def get_gdpr_engine() -> GDPREngine:
    """
    Get a default GDPREngine instance.

    Returns:
        GDPREngine instance
    """
    return GDPREngine()
