"""Client 003 Configuration - MediCare Health (Healthcare/HIPAA)"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import time
import json
from pathlib import Path


@dataclass
class BusinessHours:
    """Healthcare: 24/7 operations"""
    start: time
    end: time
    timezone: str
    is_24_7: bool = True


@dataclass
class EscalationContact:
    email: str
    slack_webhook: Optional[str] = None
    pagerduty_key: Optional[str] = None
    on_call_phone: Optional[str] = None
    emergency_line: Optional[str] = None


@dataclass
class FeatureFlags:
    shadow_mode: bool = True
    auto_escalation: bool = True
    sentiment_analysis: bool = True
    knowledge_base_search: bool = True
    multi_language: bool = True
    voice_support: bool = True
    api_integration: bool = True
    advanced_analytics: bool = True
    telehealth_integration: bool = True
    prescription_refill: bool = True


@dataclass
class SLAConfig:
    first_response_hours: int = 1  # Faster for healthcare
    resolution_hours: int = 4
    escalation_hours: int = 0.5  # 30 minutes for critical
    emergency_response_minutes: int = 5


@dataclass
class HIPAAConfig:
    enabled: bool = True
    baa_signed: bool = True
    baa_signed_date: str = "2026-01-15"
    phi_handling_enabled: bool = True
    audit_logging_enabled: bool = True
    encryption_at_rest: bool = True
    encryption_in_transit: bool = True
    minimum_necessary_enforced: bool = True
    data_retention_years: int = 7
    breach_notification_enabled: bool = True


@dataclass
class ComplianceConfig:
    hipaa: HIPAAConfig
    hitrust: bool = False
    soc2_enabled: bool = True
    gdpr_enabled: bool = False


@dataclass
class ClientConfig:
    client_id: str
    client_name: str
    industry: str
    variant: str
    timezone: str
    business_hours: BusinessHours
    escalation_contacts: EscalationContact
    paddle_account_id: Optional[str]
    feature_flags: FeatureFlags
    sla: SLAConfig
    compliance: ComplianceConfig
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    """Load and return client 003 configuration"""
    return ClientConfig(
        client_id="client_003",
        client_name="MediCare Health",
        industry="healthcare",
        variant="parwa_high",
        timezone="America/New_York",
        business_hours=BusinessHours(
            start=time(0, 0),  # 24/7
            end=time(23, 59),
            timezone="America/New_York",
            is_24_7=True
        ),
        escalation_contacts=EscalationContact(
            email="support@medicare-health.com",
            slack_webhook="https://hooks.slack.com/services/TZZZZZ/BZZZZZ/ZZZZZ",
            pagerduty_key="pd_key_healthcare789",
            on_call_phone="+1-555-0789",
            emergency_line="+1-555-0911"
        ),
        paddle_account_id="acc_hipaa_ghi789",
        feature_flags=FeatureFlags(
            shadow_mode=True,
            auto_escalation=True,
            sentiment_analysis=True,
            knowledge_base_search=True,
            multi_language=True,
            voice_support=True,
            api_integration=True,
            advanced_analytics=True,
            telehealth_integration=True,
            prescription_refill=True
        ),
        sla=SLAConfig(
            first_response_hours=1,
            resolution_hours=4,
            escalation_hours=0.5,
            emergency_response_minutes=5
        ),
        compliance=ComplianceConfig(
            hipaa=HIPAAConfig(
                enabled=True,
                baa_signed=True,
                baa_signed_date="2026-01-15",
                phi_handling_enabled=True,
                audit_logging_enabled=True,
                encryption_at_rest=True,
                encryption_in_transit=True,
                minimum_necessary_enforced=True,
                data_retention_years=7,
                breach_notification_enabled=True
            ),
            hitrust=False,
            soc2_enabled=True,
            gdpr_enabled=False
        ),
        metadata={
            "website": "https://medicare-health.com",
            "patient_portal": "https://patients.medicare-health.com",
            "provider_portal": "https://providers.medicare-health.com",
            "telehealth_url": "https://telehealth.medicare-health.com",
            "npi_number": "1234567890",
            "tax_id": "XX-XXXXXXX",
            "founded": 2015,
            "employees": 500,
            "patients_served": 50000,
            "locations": 12
        }
    )


def load_config_from_file(filepath: str) -> ClientConfig:
    """Load config from JSON file"""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")
    with open(path) as f:
        data = json.load(f)
    return ClientConfig(**data)
