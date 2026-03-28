"""Client 006 Configuration - ShopMax Retail"""

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
    """Load and return client 006 configuration.

    Client 006 is a retail client using Mini PARWA variant.
    Extended business hours for retail operations (9am-9pm CST).

    Returns:
        ClientConfig: The client configuration object
    """
    return ClientConfig(
        client_id="client_006",
        client_name="ShopMax Retail",
        industry="retail",
        variant="mini",
        timezone="America/Chicago",
        business_hours=BusinessHours(
            start=time(9, 0),
            end=time(21, 0),  # 9 PM - extended retail hours
            timezone="America/Chicago"
        ),
        escalation_contacts=EscalationContact(
            email="support@shopmax-retail.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/SMXXXXX",
            phone="+1-555-0156"
        ),
        paddle_account_id="acc_shopmax006",
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
            resolution_hours=24,
            escalation_hours=2
        ),
        metadata={
            "website": "https://shopmax-retail.com",
            "support_email": "support@shopmax-retail.com",
            "billing_email": "billing@shopmax-retail.com",
            "founded": 2018,
            "employees": 200,
            "store_count": 45,
            "annual_revenue": "50M",
            "primary_market": "Midwest USA",
            "product_categories": [
                "Electronics",
                "Home & Garden",
                "Clothing",
                "Sports",
                "Beauty"
            ],
            "special_features": {
                "loyalty_program": True,
                "gift_cards": True,
                "store_pickup": True,
                "curbside_delivery": True
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
