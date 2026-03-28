"""Client 020 Configuration - ImpactHope Nonprofit"""

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
    salesforce_np: bool = False
    mailchimp: bool = False
    stripe: bool = False
    donorbox: bool = False
    email: bool = False


@dataclass
class VariantLimits:
    """Variant-specific limits for Mini"""
    refund_limit: float = 50.0
    escalation_threshold: float = 0.60
    concurrent_calls: int = 2
    session_timeout_minutes: int = 30


@dataclass
class DonorConfig:
    """Donor management configuration"""
    enabled: bool = True
    donation_tiers: List[str] = field(default_factory=list)
    recurring_enabled: bool = True
    tax_receipts: bool = True
    volunteer_portal: bool = True


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
    donor: DonorConfig = field(default_factory=DonorConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    """Load and return client 020 configuration.

    Client 020 is a Nonprofit organization using Mini PARWA variant.
    Donor management, volunteer coordination support.
    Tax receipt automation for donations.

    Returns:
        ClientConfig: The client configuration object
    """
    return ClientConfig(
        client_id="client_020",
        client_name="ImpactHope Nonprofit",
        industry="nonprofit",
        variant="mini",
        timezone="America/Chicago",
        business_hours=BusinessHours(
            start=time(8, 0),
            end=time(18, 0),
            timezone="America/Chicago"
        ),
        escalation_contacts=EscalationContact(
            email="info@impacthope-nonprofit.org",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/IH020X",
            phone="+1-555-0120"
        ),
        paddle_account_id="acc_impacthope020",
        feature_flags=FeatureFlags(
            shadow_mode=True,
            auto_escalation=True,
            sentiment_analysis=True,
            knowledge_base_search=True,
            multi_language=False,
            voice_support=False
        ),
        sla=SLAConfig(
            first_response_hours=4,
            resolution_hours=48,
            escalation_hours=2
        ),
        integrations=IntegrationConfig(
            salesforce_np=True,
            mailchimp=True,
            stripe=True,
            donorbox=True,
            email=True
        ),
        variant_limits=VariantLimits(
            refund_limit=50.0,  # Mini limit
            escalation_threshold=0.60,
            concurrent_calls=2,  # Mini limit
            session_timeout_minutes=30
        ),
        donor=DonorConfig(
            enabled=True,
            donation_tiers=["bronze", "silver", "gold", "platinum", "diamond"],
            recurring_enabled=True,
            tax_receipts=True,
            volunteer_portal=True
        ),
        metadata={
            "website": "https://impacthope-nonprofit.org",
            "support_email": "info@impacthope-nonprofit.org",
            "donations_email": "donate@impacthope-nonprofit.org",
            "founded": 2010,
            "employees": 25,
            "volunteers": 500,
            "mission": "Empowering communities through education and sustainable development",
            "causes": [
                "education",
                "clean_water",
                "healthcare",
                "housing",
                "food_security",
                "environment"
            ],
            "active_donors": 5000,
            "annual_donations": "2M",
            "monthly_tickets": 300,
            "special_features": {
                "donation_tracking": True,
                "volunteer_scheduling": True,
                "event_management": True,
                "grant_tracking": True,
                "impact_reporting": True
            },
            "compliance": {
                "501c3": True,
                "charity_registrar": True,
                "annual_reporting": True
            }
        }
    )


def load_config_from_file(filepath: str) -> ClientConfig:
    """Load config from JSON file."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")
    with open(path) as f:
        data = json.load(f)
    return ClientConfig(**data)
