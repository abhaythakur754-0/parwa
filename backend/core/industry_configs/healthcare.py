"""
PARWA Healthcare Industry Configuration.

Configuration for healthcare providers with HIPAA compliance.
CRITICAL: BAA (Business Associate Agreement) required.

Key Requirements:
- BAA verification mandatory
- PHI (Protected Health Information) handling restricted
- Faster SLA for healthcare (1 hour)
- Audit logging required
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class HealthcareConfig(BaseModel):
    """
    Healthcare industry configuration with HIPAA compliance.

    CRITICAL: BAA (Business Associate Agreement) required for all
    healthcare clients before processing any PHI.

    Attributes:
        industry_type: Industry identifier
        requires_baa: BAA requirement flag (always True)
        phi_handling: PHI handling mode
        supported_channels: Available support channels
        sla_response_hours: Maximum response time (1 hour for healthcare)
    """

    model_config = ConfigDict()

    industry_type: str = Field(
        default="healthcare",
        description="Industry type identifier"
    )
    requires_baa: bool = Field(
        default=True,
        description="CRITICAL: BAA required for healthcare clients"
    )
    phi_handling: str = Field(
        default="restricted",
        description="PHI handling mode"
    )
    supported_channels: List[str] = Field(
        default=["faq", "email", "voice"],
        description="Supported support channels"
    )
    sla_response_hours: int = Field(
        default=1,
        description="SLA response time in hours (faster for healthcare)"
    )
    hipaa_compliance_enabled: bool = Field(
        default=True,
        description="Enable HIPAA compliance features"
    )
    audit_all_access: bool = Field(
        default=True,
        description="Audit all data access"
    )
    encryption_at_rest: bool = Field(
        default=True,
        description="Require encryption at rest"
    )
    encryption_in_transit: bool = Field(
        default=True,
        description="Require encryption in transit"
    )
    min_necessary_enabled: bool = Field(
        default=True,
        description="Enforce minimum necessary standard"
    )
    breach_notification_hours: int = Field(
        default=72,
        description="Hours to notify of breach (HIPAA requirement)"
    )
    auto_escalation_threshold: float = Field(
        default=0.5,
        description="Threshold for auto-escalation"
    )

    # Internal BAA tracking
    _baa_registry: Dict[str, Dict[str, Any]] = {}

    def get_config(self) -> Dict[str, Any]:
        """
        Get full configuration as dictionary.

        Returns:
            Dict containing all configuration values
        """
        return {
            "industry_type": self.industry_type,
            "requires_baa": self.requires_baa,
            "phi_handling": self.phi_handling,
            "supported_channels": self.supported_channels,
            "sla_response_hours": self.sla_response_hours,
            "hipaa_compliance_enabled": self.hipaa_compliance_enabled,
            "audit_all_access": self.audit_all_access,
            "encryption_at_rest": self.encryption_at_rest,
            "encryption_in_transit": self.encryption_in_transit,
            "min_necessary_enabled": self.min_necessary_enabled,
            "breach_notification_hours": self.breach_notification_hours,
            "auto_escalation_threshold": self.auto_escalation_threshold,
            "features": self.get_features(),
            "integrations": self.get_integrations(),
            "compliance_requirements": self.get_compliance_requirements(),
        }

    def get_features(self) -> List[str]:
        """
        Get list of enabled features for healthcare.

        Returns:
            List of feature names
        """
        return [
            "appointment_scheduling",
            "prescription_refill",
            "test_results",
            "insurance_verification",
            "patient_portal",
            "telehealth_support",
            "hipaa_auditing",
            "phi_protection",
            "secure_messaging",
            "ehr_integration",
        ]

    def get_integrations(self) -> List[str]:
        """
        Get list of supported integrations for healthcare.

        Returns:
            List of HIPAA-compliant integration names
        """
        return [
            "epic",
            "cerner",
            "athenahealth",
            "drchrono",
            "practice_fusion",
            "zoom_healthcare",
            "doxy_me",
            "hipaa_email",
            "secure_sms",
        ]

    def get_compliance_requirements(self) -> Dict[str, Any]:
        """
        Get HIPAA compliance requirements.

        Returns:
            Dict with compliance requirements
        """
        return {
            "baa_required": True,
            "phi_encryption": "AES-256",
            "audit_log_retention_years": 6,
            "access_control": "role_based",
            "breach_notification_hours": 72,
            "risk_assessment_required": True,
            "security_training_required": True,
            "incident_response_plan": True,
        }

    def get_channel_config(self, channel: str) -> Dict[str, Any]:
        """
        Get configuration for a specific channel.

        Args:
            channel: Channel name (faq, email, voice)

        Returns:
            Channel-specific configuration with security requirements
        """
        channel_configs = {
            "faq": {
                "enabled": True,
                "response_time_seconds": 2,
                "max_questions_per_session": 15,
                "phi_safe_only": True,
            },
            "email": {
                "enabled": True,
                "response_time_hours": 1,
                "template_support": True,
                "encryption_required": True,
                "secure_gateway": True,
            },
            "voice": {
                "enabled": True,
                "answer_time_seconds": 4,
                "ivr_enabled": False,
                "recording_disclosure": True,
                "encryption_required": True,
                "phi_mode": "restricted",
            },
        }
        return channel_configs.get(channel, {"enabled": False})

    def validate_channel(self, channel: str) -> bool:
        """
        Validate if a channel is supported.

        Args:
            channel: Channel name to validate

        Returns:
            True if channel is supported
        """
        return channel.lower() in [c.lower() for c in self.supported_channels]

    def check_baa(self, company_id: str) -> bool:
        """
        Verify BAA exists for a company.

        CRITICAL: Must return True before processing any PHI.

        Args:
            company_id: Company identifier to check

        Returns:
            True if valid BAA exists
        """
        baa_record = self._baa_registry.get(company_id)

        if not baa_record:
            logger.warning({
                "event": "baa_check_failed",
                "company_id": company_id,
                "reason": "No BAA on file"
            })
            return False

        if baa_record.get("status") != "active":
            logger.warning({
                "event": "baa_check_failed",
                "company_id": company_id,
                "reason": f"BAA status: {baa_record.get('status')}"
            })
            return False

        # Check expiry
        expiry = baa_record.get("expiry_date")
        if expiry and datetime.fromisoformat(expiry) < datetime.utcnow():
            logger.warning({
                "event": "baa_check_failed",
                "company_id": company_id,
                "reason": "BAA expired"
            })
            return False

        return True

    def register_baa(
        self,
        company_id: str,
        baa_id: str,
        effective_date: datetime,
        expiry_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Register a BAA for a company.

        Args:
            company_id: Company identifier
            baa_id: BAA document identifier
            effective_date: When BAA became effective
            expiry_date: Optional expiry date

        Returns:
            BAA record
        """
        baa_record = {
            "baa_id": baa_id,
            "company_id": company_id,
            "status": "active",
            "effective_date": effective_date.isoformat(),
            "expiry_date": expiry_date.isoformat() if expiry_date else None,
            "registered_at": datetime.utcnow().isoformat(),
        }

        self._baa_registry[company_id] = baa_record

        logger.info({
            "event": "baa_registered",
            "company_id": company_id,
            "baa_id": baa_id
        })

        return baa_record

    def revoke_baa(self, company_id: str, reason: str) -> Dict[str, Any]:
        """
        Revoke a BAA for a company.

        Args:
            company_id: Company identifier
            reason: Reason for revocation

        Returns:
            Updated BAA record
        """
        if company_id not in self._baa_registry:
            return {"error": "No BAA on file"}

        self._baa_registry[company_id]["status"] = "revoked"
        self._baa_registry[company_id]["revoked_at"] = datetime.utcnow().isoformat()
        self._baa_registry[company_id]["revocation_reason"] = reason

        logger.warning({
            "event": "baa_revoked",
            "company_id": company_id,
            "reason": reason
        })

        return self._baa_registry[company_id]

    def get_baa_status(self, company_id: str) -> Dict[str, Any]:
        """
        Get BAA status for a company.

        Args:
            company_id: Company identifier

        Returns:
            BAA status information
        """
        baa_record = self._baa_registry.get(company_id)

        if not baa_record:
            return {
                "company_id": company_id,
                "baa_exists": False,
                "status": "not_found"
            }

        return {
            "company_id": company_id,
            "baa_exists": True,
            "status": baa_record.get("status"),
            "effective_date": baa_record.get("effective_date"),
            "expiry_date": baa_record.get("expiry_date"),
            "is_valid": self.check_baa(company_id)
        }
