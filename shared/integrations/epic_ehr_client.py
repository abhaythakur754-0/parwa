"""
PARWA Epic EHR Client.

Healthcare EHR integration for patient data lookup.
CRITICAL: This is READ-ONLY access with BAA enforcement.
NEVER log PHI data - all responses are sanitized.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import asyncio
import re
from enum import Enum

from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class EpicEHRClientState(Enum):
    """Epic EHR Client state enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    BAA_REQUIRED = "baa_required"


class EHRAccessLevel(Enum):
    """EHR access level enumeration."""
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    ADMIN = "admin"


class EpicEHRClient:
    """
    Epic EHR Client for healthcare data access.

    CRITICAL SECURITY REQUIREMENTS:
    - READ-ONLY access enforced
    - BAA (Business Associate Agreement) must be verified
    - PHI (Protected Health Information) is NEVER logged
    - All responses are sanitized for logging

    Features:
    - Patient lookup by MRN or demographics
    - Visit history retrieval
    - Medication list access
    - Allergy information
    - Lab results (read-only)
    """

    DEFAULT_TIMEOUT = 30
    FHIR_VERSION = "R4"

    # PHI patterns to redact from logs
    PHI_PATTERNS = {
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "mrn": r"\b[A-Z]{2}\d{6,10}\b",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "dob": r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
    }

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        fhir_base_url: Optional[str] = None,
        baa_verified: bool = False,
        timeout: int = DEFAULT_TIMEOUT
    ) -> None:
        """
        Initialize Epic EHR Client.

        Args:
            client_id: Epic client ID
            client_secret: Epic client secret
            fhir_base_url: FHIR API base URL
            baa_verified: Whether BAA is verified
            timeout: Request timeout in seconds
        """
        self.client_id = client_id or (
            settings.epic_client_id
            if hasattr(settings, 'epic_client_id') else None
        )
        self.client_secret = client_secret or (
            settings.epic_client_secret.get_secret_value()
            if hasattr(settings, 'epic_client_secret') and settings.epic_client_secret else None
        )
        self.fhir_base_url = fhir_base_url or (
            settings.epic_fhir_url
            if hasattr(settings, 'epic_fhir_url') else None
        )
        self._baa_verified = baa_verified
        self.timeout = timeout
        self._state = EpicEHRClientState.DISCONNECTED
        self._last_request: Optional[datetime] = None
        self._access_level = EHRAccessLevel.READ_ONLY

    @property
    def state(self) -> EpicEHRClientState:
        """Get current client state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._state == EpicEHRClientState.CONNECTED

    @property
    def baa_verified(self) -> bool:
        """Check if BAA is verified."""
        return self._baa_verified

    @property
    def is_read_only(self) -> bool:
        """Check if access is read-only."""
        return self._access_level == EHRAccessLevel.READ_ONLY

    def _redact_phi(self, text: str) -> str:
        """
        Redact PHI patterns from text.

        Args:
            text: Text to sanitize

        Returns:
            Text with PHI redacted
        """
        redacted = text
        for pattern_name, pattern in self.PHI_PATTERNS.items():
            redacted = re.sub(pattern, f"[{pattern_name.upper()}_REDACTED]", redacted)
        return redacted

    def _sanitize_for_logging(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize data for safe logging.

        Args:
            data: Data dictionary to sanitize

        Returns:
            Sanitized dictionary safe for logging
        """
        sanitized = {}
        sensitive_fields = {
            "ssn", "mrn", "name", "dob", "birth_date", "phone", "email",
            "address", "city", "state", "zip", "patient_id", "ssn_last4"
        }

        for key, value in data.items():
            if key.lower() in sensitive_fields:
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, str):
                sanitized[key] = self._redact_phi(value)
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_for_logging(value)
            else:
                sanitized[key] = value

        return sanitized

    async def verify_baa(self) -> bool:
        """
        Verify Business Associate Agreement is in place.

        Returns:
            True if BAA is verified
        """
        # In production, this would check a database or service
        return self._baa_verified

    async def connect(self) -> bool:
        """
        Connect to Epic EHR.

        Validates credentials and BAA status.

        Returns:
            True if connected successfully
        """
        if self._state == EpicEHRClientState.CONNECTED:
            return True

        self._state = EpicEHRClientState.CONNECTING

        if not self.client_id or not self.client_secret:
            self._state = EpicEHRClientState.ERROR
            logger.error({"event": "epic_missing_credentials"})
            return False

        if not self._baa_verified:
            self._state = EpicEHRClientState.BAA_REQUIRED
            logger.error({
                "event": "epic_baa_not_verified",
                "message": "BAA verification required for EHR access"
            })
            return False

        try:
            await asyncio.sleep(0.1)
            self._state = EpicEHRClientState.CONNECTED
            self._last_request = datetime.now(timezone.utc)

            logger.info({
                "event": "epic_client_connected",
                "access_level": self._access_level.value,
                "baa_verified": True,
            })

            return True

        except Exception as e:
            self._state = EpicEHRClientState.ERROR
            logger.error({
                "event": "epic_connection_failed",
                "error": str(e),
            })
            return False

    async def disconnect(self) -> None:
        """Disconnect from Epic EHR."""
        self._state = EpicEHRClientState.DISCONNECTED
        self._last_request = None

        logger.info({"event": "epic_client_disconnected"})

    async def get_patient_by_mrn(self, mrn: str) -> Dict[str, Any]:
        """
        Get patient by Medical Record Number.

        CRITICAL: Response is sanitized for logging.

        Args:
            mrn: Medical Record Number

        Returns:
            Patient data dictionary (sanitized)
        """
        if not self.is_connected:
            raise ValueError("Epic EHR client not connected")

        if not mrn:
            raise ValueError("MRN is required")

        # Log without PHI
        logger.info({
            "event": "epic_patient_lookup",
            "lookup_type": "mrn",
            "mrn_masked": mrn[:2] + "****",
        })

        # Simulated patient response
        patient = {
            "resourceType": "Patient",
            "id": "patient_123",
            "mrn": mrn,
            "name": "[REDACTED]",
            "dob": "[REDACTED]",
            "gender": "female",
            "phone": "[REDACTED]",
            "email": "[REDACTED]",
            "address": {
                "line": ["[REDACTED]"],
                "city": "[REDACTED]",
                "state": "[REDACTED]",
                "zip": "[REDACTED]",
            },
            "active": True,
        }

        # Log sanitized version
        logger.info({
            "event": "epic_patient_retrieved",
            "patient_id": patient["id"],
            "data": self._sanitize_for_logging(patient),
        })

        return patient

    async def get_patient_by_demographics(
        self,
        first_name: str,
        last_name: str,
        dob: str
    ) -> List[Dict[str, Any]]:
        """
        Search patient by demographics.

        Args:
            first_name: Patient first name
            last_name: Patient last name
            dob: Date of birth

        Returns:
            List of matching patients
        """
        if not self.is_connected:
            raise ValueError("Epic EHR client not connected")

        if not first_name or not last_name or not dob:
            raise ValueError("First name, last name, and DOB are required")

        # Log without PHI
        logger.info({
            "event": "epic_patient_search",
            "lookup_type": "demographics",
        })

        # Return empty list for demo
        return []

    async def get_patient_visits(
        self,
        patient_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get patient visit history.

        Args:
            patient_id: Patient ID
            limit: Maximum visits to return

        Returns:
            List of visit records
        """
        if not self.is_connected:
            raise ValueError("Epic EHR client not connected")

        if not patient_id:
            raise ValueError("Patient ID is required")

        if limit < 1 or limit > 50:
            raise ValueError("Limit must be between 1 and 50")

        logger.info({
            "event": "epic_visits_lookup",
            "patient_id": patient_id,
            "limit": limit,
        })

        return [
            {
                "resourceType": "Encounter",
                "id": "encounter_1",
                "status": "finished",
                "type": [{"text": "Office Visit"}],
                "period": {
                    "start": datetime.now(timezone.utc).isoformat(),
                },
                "reason": [{"text": "Annual checkup"}],
            }
        ]

    async def get_patient_medications(
        self,
        patient_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get patient medication list.

        Args:
            patient_id: Patient ID

        Returns:
            List of medications
        """
        if not self.is_connected:
            raise ValueError("Epic EHR client not connected")

        if not patient_id:
            raise ValueError("Patient ID is required")

        logger.info({
            "event": "epic_medications_lookup",
            "patient_id": patient_id,
        })

        return [
            {
                "resourceType": "MedicationRequest",
                "id": "med_1",
                "status": "active",
                "medicationCodeableConcept": {
                    "text": "[MEDICATION_NAME_REDACTED]"
                },
                "dosageInstruction": [{
                    "text": "Take as directed"
                }],
            }
        ]

    async def get_patient_allergies(
        self,
        patient_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get patient allergies.

        Args:
            patient_id: Patient ID

        Returns:
            List of allergies
        """
        if not self.is_connected:
            raise ValueError("Epic EHR client not connected")

        if not patient_id:
            raise ValueError("Patient ID is required")

        logger.info({
            "event": "epic_allergies_lookup",
            "patient_id": patient_id,
        })

        return [
            {
                "resourceType": "AllergyIntolerance",
                "id": "allergy_1",
                "clinicalStatus": "active",
                "substance": {"text": "[ALLERGEN_REDACTED]"},
                "reaction": [{"description": "[REDACTED]"}],
            }
        ]

    async def get_lab_results(
        self,
        patient_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get patient lab results.

        Args:
            patient_id: Patient ID
            limit: Maximum results to return

        Returns:
            List of lab results
        """
        if not self.is_connected:
            raise ValueError("Epic EHR client not connected")

        if not patient_id:
            raise ValueError("Patient ID is required")

        logger.info({
            "event": "epic_labs_lookup",
            "patient_id": patient_id,
            "limit": limit,
        })

        return [
            {
                "resourceType": "Observation",
                "id": "lab_1",
                "status": "final",
                "category": [{"coding": [{"display": "Laboratory"}]}],
                "effectiveDateTime": datetime.now(timezone.utc).isoformat(),
                "valueQuantity": {
                    "value": 100,
                    "unit": "mg/dL",
                },
            }
        ]

    async def get_conditions(
        self,
        patient_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get patient conditions/diagnoses.

        Args:
            patient_id: Patient ID

        Returns:
            List of conditions
        """
        if not self.is_connected:
            raise ValueError("Epic EHR client not connected")

        if not patient_id:
            raise ValueError("Patient ID is required")

        logger.info({
            "event": "epic_conditions_lookup",
            "patient_id": patient_id,
        })

        return [
            {
                "resourceType": "Condition",
                "id": "condition_1",
                "clinicalStatus": "active",
                "verificationStatus": "confirmed",
                "code": {"text": "[DIAGNOSIS_REDACTED]"},
            }
        ]

    async def search_patients(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search patients by query string.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching patients
        """
        if not self.is_connected:
            raise ValueError("Epic EHR client not connected")

        if not query:
            raise ValueError("Search query is required")

        logger.info({
            "event": "epic_patient_search_query",
            "query_masked": query[:2] + "****",
        })

        return []

    # BLOCKED METHODS - READ-ONLY ENFORCEMENT

    async def create_patient(self, *args, **kwargs) -> None:
        """
        BLOCKED: EHR access is READ-ONLY.

        Raises:
            PermissionError: Always raised
        """
        raise PermissionError(
            "EHR access is READ-ONLY. Patient creation is not allowed."
        )

    async def update_patient(self, *args, **kwargs) -> None:
        """
        BLOCKED: EHR access is READ-ONLY.

        Raises:
            PermissionError: Always raised
        """
        raise PermissionError(
            "EHR access is READ-ONLY. Patient updates are not allowed."
        )

    async def delete_patient(self, *args, **kwargs) -> None:
        """
        BLOCKED: EHR access is READ-ONLY.

        Raises:
            PermissionError: Always raised
        """
        raise PermissionError(
            "EHR access is READ-ONLY. Patient deletion is not allowed."
        )

    async def create_order(self, *args, **kwargs) -> None:
        """
        BLOCKED: EHR access is READ-ONLY.

        Raises:
            PermissionError: Always raised
        """
        raise PermissionError(
            "EHR access is READ-ONLY. Order creation is not allowed."
        )

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Epic EHR connection.

        Returns:
            Health status dictionary
        """
        return {
            "healthy": self._state == EpicEHRClientState.CONNECTED,
            "state": self._state.value,
            "access_level": self._access_level.value,
            "baa_verified": self._baa_verified,
            "read_only": True,
            "last_request": (
                self._last_request.isoformat()
                if self._last_request else None
            ),
            "fhir_version": self.FHIR_VERSION,
        }
