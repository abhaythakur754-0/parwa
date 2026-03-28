"""Client 015 Configuration - HomeFind Realty"""

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
    calendly: bool = False
    email: bool = False
    zillow: bool = False
    mls: bool = False
    docu_sign: bool = False


@dataclass
class VariantLimits:
    """Variant-specific limits"""
    refund_limit: float = 100.0
    escalation_threshold: float = 0.50
    concurrent_calls: int = 5
    session_timeout_minutes: int = 30


@dataclass
class LeadRoutingConfig:
    """Lead routing configuration"""
    enabled: bool = True
    round_robin: bool = True
    by_region: bool = True
    by_property_type: bool = True
    auto_assign: bool = True
    sla_minutes: int = 15


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
    lead_routing: LeadRoutingConfig = field(default_factory=LeadRoutingConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    """Load and return client 015 configuration.

    Client 015 is a Real Estate (PropTech) client using PARWA Junior variant.
    Lead routing for property inquiries.
    Salesforce, Calendly integrations for agent scheduling.
    $100 refund limit for application fees.

    Returns:
        ClientConfig: The client configuration object
    """
    return ClientConfig(
        client_id="client_015",
        client_name="HomeFind Realty",
        industry="real_estate_proptech",
        variant="junior",
        timezone="America/Chicago",
        business_hours=BusinessHours(
            start=time(8, 0),
            end=time(20, 0),  # 8 PM - extended hours for home buyers
            timezone="America/Chicago"
        ),
        escalation_contacts=EscalationContact(
            email="info@homefind-realty.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/HF015X",
            phone="+1-555-0115"
        ),
        paddle_account_id="acc_homefind015",
        feature_flags=FeatureFlags(
            shadow_mode=True,
            auto_escalation=True,
            sentiment_analysis=True,
            knowledge_base_search=True,
            multi_language=True,  # Diverse buyer population
            voice_support=True
        ),
        sla=SLAConfig(
            first_response_hours=2,
            resolution_hours=48,
            escalation_hours=2
        ),
        integrations=IntegrationConfig(
            salesforce=True,
            calendly=True,
            email=True,
            zillow=True,
            mls=True,
            docu_sign=True
        ),
        variant_limits=VariantLimits(
            refund_limit=100.0,  # Application fees
            escalation_threshold=0.50,
            concurrent_calls=5,
            session_timeout_minutes=30
        ),
        lead_routing=LeadRoutingConfig(
            enabled=True,
            round_robin=True,
            by_region=True,
            by_property_type=True,
            auto_assign=True,
            sla_minutes=15
        ),
        metadata={
            "website": "https://homefind-realty.com",
            "support_email": "info@homefind-realty.com",
            "billing_email": "finance@homefind-realty.com",
            "founded": 2012,
            "employees": 75,
            "property_types": [
                "residential",
                "commercial",
                "luxury",
                "rentals",
                "new_construction",
                "land"
            ],
            "active_agents": 50,
            "active_listings": 500,
            "monthly_inquiries": 3500,
            "monthly_tickets": 800,
            "average_property_value": 350000,
            "regions_served": ["midwest", "texas", "florida", "arizona"],
            "special_features": {
                "virtual_tours": True,
                "mortgage_pre_approval": True,
                "home_warranty": True,
                "property_management": True,
                "relocation_services": True
            },
            "compliance": {
                "fair_housing": True,
                "respa": True,  # Real estate settlement
                "mls_compliance": True,
                "state_licensing": True
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
