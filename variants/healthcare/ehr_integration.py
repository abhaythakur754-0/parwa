"""
EHR Integration Module.
Week 33, Builder 5: Healthcare HIPAA + Logistics

Electronic Health Record integration for major EHR providers.
"""

import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class EHRProvider(Enum):
    """Supported EHR providers."""
    EPIC = "epic"
    CERNER = "cerner"
    ATHENAHEALTH = "athenahealth"
    DRCHRONO = "drchrono"
    ALLSCRIPTS = "allscripts"
    NEXTGEN = "nextgen"
    ECW = "ecw"
    PRACTICE_FUSION = "practice_fusion"


class EHRAuthType(Enum):
    """EHR authentication types."""
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    SMART = "smart_on_fhir"
    HL7 = "hl7"


@dataclass
class EHRConnection:
    """EHR connection configuration."""
    provider: EHRProvider
    base_url: str
    auth_type: EHRAuthType
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    api_key: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    is_sandbox: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_connected(self) -> bool:
        """Check if connection is active."""
        if not self.access_token:
            return False
        if self.token_expires_at and datetime.utcnow() >= self.token_expires_at:
            return False
        return True


@dataclass
class EHRPatient:
    """EHR patient record."""
    patient_id: str
    mrn: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[Dict[str, str]] = None
    insurance: Optional[List[Dict[str, Any]]] = None
    primary_care_provider: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'patient_id': self.patient_id,
            'mrn': self.mrn,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'date_of_birth': self.date_of_birth,
            'gender': self.gender,
            'phone': self.phone,
            'email': self.email,
            'address': self.address,
            'insurance': self.insurance,
            'primary_care_provider': self.primary_care_provider,
            'metadata': self.metadata,
        }


@dataclass
class EHRAppointment:
    """EHR appointment record."""
    appointment_id: str
    patient_id: str
    provider_id: str
    appointment_type: str
    scheduled_time: datetime
    duration_minutes: int = 15
    status: str = "scheduled"
    location: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class EHRIntegration:
    """
    EHR Integration Hub for healthcare systems.

    Provides unified interface for connecting to various EHR systems
    including Epic, Cerner, and others via FHIR/HL7 standards.
    """

    # Provider configurations
    PROVIDER_CONFIGS = {
        EHRProvider.EPIC: {
            "auth_type": EHRAuthType.SMART,
            "fhir_version": "R4",
            "supports_bulk": True,
        },
        EHRProvider.CERNER: {
            "auth_type": EHRAuthType.OAUTH2,
            "fhir_version": "R4",
            "supports_bulk": True,
        },
        EHRProvider.ATHENAHEALTH: {
            "auth_type": EHRAuthType.OAUTH2,
            "fhir_version": "R4",
            "supports_bulk": False,
        },
    }

    def __init__(
        self,
        client_id: str,
        provider: EHRProvider,
        connection: Optional[EHRConnection] = None,
    ):
        """
        Initialize EHR Integration.

        Args:
            client_id: Client identifier
            provider: EHR provider type
            connection: Optional connection configuration
        """
        self.client_id = client_id
        self.provider = provider
        self._connection = connection

        # Cached data
        self._patients: Dict[str, EHRPatient] = {}
        self._appointments: Dict[str, EHRAppointment] = {}

        # Metrics
        self._api_calls = 0
        self._last_sync: Optional[datetime] = None

        logger.info({
            "event": "ehr_integration_initialized",
            "client_id": client_id,
            "provider": provider.value,
        })

    def connect(
        self,
        base_url: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> EHRConnection:
        """
        Connect to EHR system.

        Args:
            base_url: EHR base URL
            client_id: OAuth client ID
            client_secret: OAuth client secret
            api_key: API key for simple auth

        Returns:
            EHRConnection object
        """
        config = self.PROVIDER_CONFIGS.get(self.provider, {})

        self._connection = EHRConnection(
            provider=self.provider,
            base_url=base_url,
            auth_type=config.get("auth_type", EHRAuthType.OAUTH2),
            client_id=client_id,
            client_secret=client_secret,
            api_key=api_key,
            access_token="mock_token_for_demo",
            token_expires_at=datetime.utcnow() + timedelta(seconds=3600),  # 1 hour
        )

        logger.info({
            "event": "ehr_connected",
            "provider": self.provider.value,
            "base_url": base_url,
        })

        return self._connection

    def disconnect(self) -> bool:
        """Disconnect from EHR."""
        if self._connection:
            self._connection.access_token = None
            self._connection.refresh_token = None

        logger.info({
            "event": "ehr_disconnected",
            "provider": self.provider.value,
        })

        return True

    def get_patient(
        self,
        patient_id: str,
    ) -> Optional[EHRPatient]:
        """
        Get patient by ID.

        Args:
            patient_id: Patient identifier

        Returns:
            EHRPatient or None
        """
        if not self._connection or not self._connection.is_connected:
            raise ConnectionError("Not connected to EHR")

        self._api_calls += 1

        # Check cache
        if patient_id in self._patients:
            return self._patients[patient_id]

        # Mock patient for demo
        patient = EHRPatient(
            patient_id=patient_id,
            mrn=f"MRN{patient_id.zfill(8)}",
            first_name="Demo",
            last_name="Patient",
            date_of_birth="1990-01-15",
            gender="unknown",
        )

        self._patients[patient_id] = patient

        logger.info({
            "event": "ehr_patient_fetched",
            "patient_id": patient_id,
            "provider": self.provider.value,
        })

        return patient

    def search_patients(
        self,
        query: str,
        limit: int = 20,
    ) -> List[EHRPatient]:
        """
        Search for patients.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching patients
        """
        if not self._connection or not self._connection.is_connected:
            raise ConnectionError("Not connected to EHR")

        self._api_calls += 1

        # Mock search results
        results = []
        for i in range(min(limit, 5)):
            patient = EHRPatient(
                patient_id=f"P{10000 + i}",
                mrn=f"MRN{10000 + i}",
                first_name=f"Patient{i}",
                last_name="Demo",
            )
            results.append(patient)
            self._patients[patient.patient_id] = patient

        return results

    def get_appointments(
        self,
        patient_id: Optional[str] = None,
        provider_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[EHRAppointment]:
        """
        Get appointments.

        Args:
            patient_id: Filter by patient
            provider_id: Filter by provider
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            List of appointments
        """
        if not self._connection or not self._connection.is_connected:
            raise ConnectionError("Not connected to EHR")

        self._api_calls += 1

        # Mock appointments
        appointments = []
        base_time = datetime.utcnow().replace(hour=9, minute=0, second=0)

        for i in range(5):
            appt = EHRAppointment(
                appointment_id=f"APT{10000 + i}",
                patient_id=patient_id or f"P{10000 + i}",
                provider_id=provider_id or "DR001",
                appointment_type="Office Visit",
                scheduled_time=base_time + i * timedelta(hours=1),
                duration_minutes=15,
                status="scheduled",
            )
            appointments.append(appt)
            self._appointments[appt.appointment_id] = appt

        return appointments

    def create_appointment(
        self,
        patient_id: str,
        provider_id: str,
        appointment_type: str,
        scheduled_time: datetime,
        duration_minutes: int = 15,
        reason: Optional[str] = None,
    ) -> EHRAppointment:
        """
        Create a new appointment.

        Args:
            patient_id: Patient ID
            provider_id: Provider ID
            appointment_type: Type of appointment
            scheduled_time: Scheduled time
            duration_minutes: Duration in minutes
            reason: Reason for visit

        Returns:
            Created appointment
        """
        if not self._connection or not self._connection.is_connected:
            raise ConnectionError("Not connected to EHR")

        self._api_calls += 1

        appointment = EHRAppointment(
            appointment_id=f"APT{len(self._appointments) + 10000}",
            patient_id=patient_id,
            provider_id=provider_id,
            appointment_type=appointment_type,
            scheduled_time=scheduled_time,
            duration_minutes=duration_minutes,
            reason=reason,
            status="scheduled",
        )

        self._appointments[appointment.appointment_id] = appointment

        logger.info({
            "event": "ehr_appointment_created",
            "appointment_id": appointment.appointment_id,
            "patient_id": patient_id,
        })

        return appointment

    def cancel_appointment(
        self,
        appointment_id: str,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Cancel an appointment.

        Args:
            appointment_id: Appointment ID
            reason: Cancellation reason

        Returns:
            Success status
        """
        if appointment_id in self._appointments:
            self._appointments[appointment_id].status = "cancelled"
            self._api_calls += 1

            logger.info({
                "event": "ehr_appointment_cancelled",
                "appointment_id": appointment_id,
                "reason": reason,
            })

            return True

        return False

    def get_medical_records(
        self,
        patient_id: str,
        record_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get patient medical records.

        Args:
            patient_id: Patient ID
            record_type: Optional filter by type

        Returns:
            List of medical records
        """
        if not self._connection or not self._connection.is_connected:
            raise ConnectionError("Not connected to EHR")

        self._api_calls += 1

        # Mock records
        records = [
            {
                "record_id": f"REC{patient_id}_001",
                "type": "lab_result",
                "date": datetime.utcnow().isoformat(),
                "description": "Complete Blood Count",
                "status": "final",
            },
            {
                "record_id": f"REC{patient_id}_002",
                "type": "vital_signs",
                "date": datetime.utcnow().isoformat(),
                "description": "Blood Pressure: 120/80",
                "status": "final",
            },
        ]

        if record_type:
            records = [r for r in records if r.get("type") == record_type]

        return records

    def sync_data(self) -> Dict[str, Any]:
        """
        Sync data from EHR.

        Returns:
            Sync statistics
        """
        self._last_sync = datetime.utcnow()

        logger.info({
            "event": "ehr_data_synced",
            "client_id": self.client_id,
            "provider": self.provider.value,
        })

        return {
            "synced_at": self._last_sync.isoformat(),
            "patients_cached": len(self._patients),
            "appointments_cached": len(self._appointments),
            "api_calls": self._api_calls,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get integration statistics."""
        return {
            "client_id": self.client_id,
            "provider": self.provider.value,
            "is_connected": self._connection.is_connected if self._connection else False,
            "patients_cached": len(self._patients),
            "appointments_cached": len(self._appointments),
            "api_calls": self._api_calls,
            "last_sync": self._last_sync.isoformat() if self._last_sync else None,
        }


# Import timedelta for use in methods
from datetime import timedelta
