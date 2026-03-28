"""Client 024 Configuration - Daily Herald Media"""

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
    stripe: bool = True
    mailchimp: bool = True
    wordpress: bool = True
    email: bool = True


@dataclass
class VariantLimits:
    """Variant-specific limits for PARWA Junior"""
    refund_limit: float = 50.0
    escalation_threshold: float = 0.50
    concurrent_calls: int = 5
    session_timeout_minutes: int = 30


@dataclass
class MediaConfig:
    """Media/News specific configuration"""
    enabled: bool = True
    subscription_management: bool = True
    content_inquiries: bool = True
    advertising_support: bool = True
    editorial_escalation: bool = True
    correction_requests: bool = True


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
    media: MediaConfig = field(default_factory=MediaConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    """Load and return client 024 configuration.

    Client 024 is a Media & Publishing company using PARWA Junior variant.
    Subscription management, content inquiries, advertising support.
    Digital and print media.

    Returns:
        ClientConfig: The client configuration object
    """
    return ClientConfig(
        client_id="client_024",
        client_name="Daily Herald Media",
        industry="media_publishing",
        variant="parwa_junior",
        timezone="America/New_York",
        business_hours=BusinessHours(
            start=time(6, 0),  # Early for news
            end=time(22, 0),
            timezone="America/New_York"
        ),
        escalation_contacts=EscalationContact(
            email="support@dailyherald-media.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/IH024X",
            phone="+1-555-0124"
        ),
        paddle_account_id="acc_dailyherald024",
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
        integrations=IntegrationConfig(
            stripe=True,
            mailchimp=True,
            wordpress=True,
            email=True
        ),
        variant_limits=VariantLimits(
            refund_limit=50.0,  # Subscription refunds
            escalation_threshold=0.50,
            concurrent_calls=5,
            session_timeout_minutes=30
        ),
        media=MediaConfig(
            enabled=True,
            subscription_management=True,
            content_inquiries=True,
            advertising_support=True,
            editorial_escalation=True,
            correction_requests=True
        ),
        metadata={
            "website": "https://dailyherald-media.com",
            "support_email": "support@dailyherald-media.com",
            "newsroom_email": "newsroom@dailyherald-media.com",
            "advertising_email": "ads@dailyherald-media.com",
            "founded": 1920,
            "employees": 450,
            "daily_circulation": 200000,
            "digital_subscribers": 150000,
            "description": "Regional newspaper and digital media company",
            "publications": [
                "daily_herald",
                "sunday_herald",
                "herald_weekly",
                "herald_online"
            ],
            "monthly_tickets": 1200,
            "special_features": {
                "digital_archive_access": True,
                "epaper_support": True,
                "home_delivery_management": True,
                "vacation_hold": True,
                "gift_subscriptions": True,
                "subscriber_benefits": True
            },
            "content_types": [
                "news",
                "sports",
                "business",
                "entertainment",
                "opinion",
                "lifestyle",
                "obituaries"
            ],
            "compliance": {
                "journalism_ethics": True,
                "ftc_advertising": True,
                "copyright": True
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
