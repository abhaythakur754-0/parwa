"""Client 017 Configuration - QuickBite Delivery"""

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
    doordash_api: bool = False
    stripe: bool = False
    sms: bool = False
    ubereats_api: bool = False
    grubhub_api: bool = False


@dataclass
class VariantLimits:
    """Variant-specific limits for Mini"""
    refund_limit: float = 50.0
    escalation_threshold: float = 0.60
    concurrent_calls: int = 2
    session_timeout_minutes: int = 30


@dataclass
class RealTimeConfig:
    """Real-time order issue handling"""
    enabled: bool = True
    order_tracking: bool = True
    driver_communication: bool = True
    instant_refund_threshold: float = 25.0


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
    real_time: RealTimeConfig = field(default_factory=RealTimeConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    """Load and return client 017 configuration.

    Client 017 is a Food Delivery client using Mini PARWA variant.
    DoorDash API, Stripe, SMS integrations.
    Real-time order issue handling for fast resolution.

    Returns:
        ClientConfig: The client configuration object
    """
    return ClientConfig(
        client_id="client_017",
        client_name="QuickBite Delivery",
        industry="food_delivery",
        variant="mini",
        timezone="America/Los_Angeles",
        business_hours=BusinessHours(
            start=time(10, 0),
            end=time(23, 0),  # Late night delivery
            timezone="America/Los_Angeles"
        ),
        escalation_contacts=EscalationContact(
            email="support@quickbite-delivery.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/QB017X",
            phone="+1-555-0117"
        ),
        paddle_account_id="acc_quickbite017",
        feature_flags=FeatureFlags(
            shadow_mode=True,
            auto_escalation=True,
            sentiment_analysis=True,
            knowledge_base_search=True,
            multi_language=False,
            voice_support=False
        ),
        sla=SLAConfig(
            first_response_hours=0,  # Immediate for food
            resolution_hours=1,  # Same hour resolution
            escalation_hours=0
        ),
        integrations=IntegrationConfig(
            doordash_api=True,
            stripe=True,
            sms=True,
            ubereats_api=True,
            grubhub_api=True
        ),
        variant_limits=VariantLimits(
            refund_limit=50.0,  # Mini limit
            escalation_threshold=0.60,
            concurrent_calls=2,  # Mini limit
            session_timeout_minutes=30
        ),
        real_time=RealTimeConfig(
            enabled=True,
            order_tracking=True,
            driver_communication=True,
            instant_refund_threshold=25.0
        ),
        metadata={
            "website": "https://quickbite-delivery.com",
            "support_email": "support@quickbite-delivery.com",
            "billing_email": "payments@quickbite-delivery.com",
            "founded": 2021,
            "employees": 50,
            "service_areas": ["los_angeles", "san_francisco", "seattle"],
            "restaurant_partners": 500,
            "monthly_orders": 100000,
            "monthly_tickets": 3500,
            "average_order_value": 35,
            "peak_hours": ["11:30-13:30", "18:00-21:00"],
            "special_features": {
                "contactless_delivery": True,
                "real_time_tracking": True,
                "scheduled_orders": True,
                "group_orders": True,
                "subscription_service": True
            },
            "compliance": {
                "food_safety": True,
                "health_department": True,
                "pci_dss": True
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
