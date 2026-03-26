"""Client 011 Configuration - RetailPro E-commerce"""

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
    shopify: bool = False
    stripe: bool = False
    zendesk: bool = False
    salesforce: bool = False
    twilio: bool = False
    slack: bool = False
    intercom: bool = False


@dataclass
class VariantLimits:
    """Variant-specific limits"""
    refund_limit: float = 150.0
    escalation_threshold: float = 0.40
    concurrent_calls: int = 5
    session_timeout_minutes: int = 30


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
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    """Load and return client 011 configuration.

    Client 011 is a Retail E-commerce client using PARWA Junior variant.
    Shopify, Stripe, Zendesk integrations for multi-channel retail.
    Extended business hours 9am-9pm EST.

    Returns:
        ClientConfig: The client configuration object
    """
    return ClientConfig(
        client_id="client_011",
        client_name="RetailPro E-commerce",
        industry="retail_ecommerce",
        variant="junior",
        timezone="America/New_York",
        business_hours=BusinessHours(
            start=time(9, 0),
            end=time(21, 0),  # 9 PM - extended retail hours
            timezone="America/New_York"
        ),
        escalation_contacts=EscalationContact(
            email="support@retailpro-ecom.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/RP011X",
            phone="+1-555-0111"
        ),
        paddle_account_id="acc_retailpro011",
        feature_flags=FeatureFlags(
            shadow_mode=True,
            auto_escalation=True,
            sentiment_analysis=True,
            knowledge_base_search=True,
            multi_language=True,  # International customers
            voice_support=True
        ),
        sla=SLAConfig(
            first_response_hours=2,  # Fast retail response
            resolution_hours=24,
            escalation_hours=1
        ),
        integrations=IntegrationConfig(
            shopify=True,
            stripe=True,
            zendesk=True,
            salesforce=False,
            twilio=True,
            slack=True,
            intercom=False
        ),
        variant_limits=VariantLimits(
            refund_limit=150.0,
            escalation_threshold=0.40,
            concurrent_calls=5,
            session_timeout_minutes=30
        ),
        metadata={
            "website": "https://retailpro-ecom.com",
            "support_email": "support@retailpro-ecom.com",
            "billing_email": "billing@retailpro-ecom.com",
            "founded": 2019,
            "employees": 150,
            "product_categories": [
                "Fashion",
                "Electronics",
                "Home Decor",
                "Beauty",
                "Sports"
            ],
            "sales_channels": [
                "web",
                "mobile_app",
                "marketplace",
                "social_commerce"
            ],
            "average_order_value": 85,
            "monthly_tickets": 3500,
            "peak_seasons": ["black_friday", "cyber_monday", "christmas"],
            "special_features": {
                "loyalty_program": True,
                "gift_cards": True,
                "store_pickup": True,
                "international_shipping": True,
                "subscription_boxes": True
            },
            "compliance": {
                "pci_dss": True,
                "gdpr": True,  # EU customers
                "ccpa": True   # California customers
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
