"""Client 009 Configuration - HomeFind Realty

Real Estate client for property listings and agent support.
"""

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
    multi_language: bool = True
    voice_support: bool = False


@dataclass
class SLAConfig:
    """SLA configuration"""
    first_response_hours: int = 2
    resolution_hours: int = 24
    escalation_hours: int = 4


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
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    """Load and return client 009 configuration.

    Client 009 is a real estate client using PARWA Junior variant.
    Supporting property listings, buyer/seller inquiries, and agent coordination.

    Returns:
        ClientConfig: The client configuration object
    """
    return ClientConfig(
        client_id="client_009",
        client_name="HomeFind Realty",
        industry="real_estate",
        variant="parwa_junior",
        timezone="America/Los_Angeles",
        business_hours=BusinessHours(
            start=time(8, 0),
            end=time(20, 0),
            timezone="America/Los_Angeles"
        ),
        escalation_contacts=EscalationContact(
            email="support@homefindrealty.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/REXXX",
            phone="+1-555-0159"
        ),
        paddle_account_id="acc_homefind009",
        feature_flags=FeatureFlags(
            shadow_mode=True,
            auto_escalation=True,
            sentiment_analysis=True,
            knowledge_base_search=True,
            multi_language=True,
            voice_support=False
        ),
        sla=SLAConfig(
            first_response_hours=2,
            resolution_hours=24,
            escalation_hours=4
        ),
        metadata={
            "website": "https://homefindrealty.com",
            "support_email": "support@homefindrealty.com",
            "billing_email": "billing@homefindrealty.com",
            "founded": 2010,
            "employees": 75,
            "active_listings": 500,
            "agents": 50,
            "offices": 5,
            "markets_served": [
                "Los Angeles",
                "San Francisco",
                "San Diego",
                "Seattle",
                "Portland"
            ],
            "property_types": [
                "Residential",
                "Commercial",
                "Luxury",
                "Investment",
                "Land"
            ],
            "services": {
                "buyer_representation": True,
                "seller_representation": True,
                "property_management": True,
                "mortgage_referral": True,
                "title_services": True
            },
            "average_sale_price": 750000,
            "annual_transactions": 1200
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
