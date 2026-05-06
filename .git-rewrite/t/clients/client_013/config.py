"""Client 013 Configuration - SecureLife Insurance"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import time
import json
from pathlib import Path


@dataclass
class BusinessHours:
    """Business hours configuration"""
    start: time
    end: time
    timezone: str


@dataclass
class EscalationContact:
    """Escalation contact information"""
    email: str
    slack_webhook: Optional[str] = None
    phone: Optional[str] = None


@dataclass
class FeatureFlags:
    """Feature flags for client"""
    shadow_mode: bool = True
    auto_escalation: bool = True
    sentiment_analysis: bool = True
    knowledge_base_search: bool = True
    multi_language: bool = False
    voice_support: bool = False


@dataclass
class SLAConfig:
    """SLA configuration"""
    first_response_hours: int = 4
    resolution_hours: int = 24
    escalation_hours: int = 2


@dataclass
class IntegrationConfig:
    """Third-party integrations"""
    salesforce: bool = False
    twilio: bool = False
    email: bool = False
    guidewire: bool = False
    duck_creek: bool = False


@dataclass
class VariantLimits:
    """Variant-specific limits"""
    refund_limit: float = 500.0
    escalation_threshold: float = 0.25
    concurrent_calls: int = 10
    session_timeout_minutes: int = 15  # Security requirement


@dataclass
class ComplianceConfig:
    """Compliance requirements for insurance"""
    sox: bool = False
    naic: bool = False  # National Association of Insurance Commissioners
    state_regulations: List[str] = field(default_factory=list)
    audit_logging: bool = True
    data_retention_years: int = 7


@dataclass
class ClientConfig:
    """Main client configuration"""
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
    integrations: IntegrationConfig = field(default_factory=IntegrationConfig)
    variant_limits: VariantLimits = field(default_factory=VariantLimits)
    compliance: ComplianceConfig = field(default_factory=ComplianceConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    """Load and return client 013 configuration.

    Client 013 is an Insurance client using PARWA High variant.
    SOX compliance and state insurance regulations.
    Salesforce, Twilio integrations for policy management.
    15-minute session timeout for security.

    Returns:
        ClientConfig: The client configuration object
    """
    return ClientConfig(
        client_id="client_013",
        client_name="SecureLife Insurance",
        industry="insurance",
        variant="high",
        timezone="America/New_York",
        business_hours=BusinessHours(
            start=time(8, 0),
            end=time(18, 0),  # 6 PM
            timezone="America/New_York"
        ),
        escalation_contacts=EscalationContact(
            email="claims@securelife-insurance.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/SL013X",
            phone="+1-555-0113"
        ),
        paddle_account_id="acc_securelife013",
        feature_flags=FeatureFlags(
            shadow_mode=True,
            auto_escalation=True,
            sentiment_analysis=True,
            knowledge_base_search=True,
            multi_language=True,
            voice_support=True
        ),
        sla=SLAConfig(
            first_response_hours=2,
            resolution_hours=48,  # Complex claims take longer
            escalation_hours=1
        ),
        integrations=IntegrationConfig(
            salesforce=True,
            twilio=True,
            email=True,
            guidewire=True,
            duck_creek=False
        ),
        variant_limits=VariantLimits(
            refund_limit=500.0,  # Premium refunds
            escalation_threshold=0.25,
            concurrent_calls=10,
            session_timeout_minutes=15  # Security requirement
        ),
        compliance=ComplianceConfig(
            sox=True,
            naic=True,
            state_regulations=[
                "NY", "CA", "TX", "FL", "PA", "IL", "OH", "GA", "NC", "MI"
            ],
            audit_logging=True,
            data_retention_years=7
        ),
        metadata={
            "website": "https://securelife-insurance.com",
            "support_email": "claims@securelife-insurance.com",
            "billing_email": "premiums@securelife-insurance.com",
            "founded": 1985,
            "employees": 1200,
            "policy_types": [
                "auto",
                "home",
                "life",
                "health",
                "disability",
                "long_term_care"
            ],
            "active_policies": 250000,
            "monthly_tickets": 4500,
            "average_claim_value": 3500,
            "licensed_states": 50,
            "special_features": {
                "online_claims": True,
                "mobile_app": True,
                "telemedicine": True,
                "roadside_assistance": True,
                "identity_protection": True
            },
            "compliance": {
                "sox": True,
                "naic": True,
                "hipaa": True,  # Health policies
                "glba": True,   # Financial privacy
                "state_insurance": True
            }
        }
    )


def load_config_from_file(filepath: str) -> ClientConfig:
    """Load config from JSON file.

    Args:
        filepath: Path to the JSON config file

    Returns:
        ClientConfig: The loaded configuration

    Raises:
        FileNotFoundError: If the config file doesn't exist
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")
    with open(path) as f:
        data = json.load(f)
    return ClientConfig(**data)
