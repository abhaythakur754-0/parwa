"""Client 018 Configuration - FitLife Wellness"""

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
    mindbody: bool = False
    stripe: bool = False
    email: bool = False
    calendly: bool = False
    zoom: bool = False


@dataclass
class VariantLimits:
    """Variant-specific limits"""
    refund_limit: float = 150.0
    escalation_threshold: float = 0.40
    concurrent_calls: int = 5
    session_timeout_minutes: int = 30


@dataclass
class MembershipConfig:
    """Membership management configuration"""
    enabled: bool = True
    tiers: List[str] = field(default_factory=list)
    auto_renewal: bool = True
    freeze_allowed: bool = True
    cancellation_notice_days: int = 30


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
    membership: MembershipConfig = field(default_factory=MembershipConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    """Load and return client 018 configuration.

    Client 018 is a Fitness & Wellness client using PARWA Junior variant.
    Mindbody integration for class scheduling.
    Membership management with tier support.

    Returns:
        ClientConfig: The client configuration object
    """
    return ClientConfig(
        client_id="client_018",
        client_name="FitLife Wellness",
        industry="fitness_wellness",
        variant="junior",
        timezone="America/Denver",
        business_hours=BusinessHours(
            start=time(5, 0),  # Early morning workouts
            end=time(22, 0),
            timezone="America/Denver"
        ),
        escalation_contacts=EscalationContact(
            email="support@fitlife-wellness.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/FL018X",
            phone="+1-555-0118"
        ),
        paddle_account_id="acc_fitlife018",
        feature_flags=FeatureFlags(
            shadow_mode=True,
            auto_escalation=True,
            sentiment_analysis=True,
            knowledge_base_search=True,
            multi_language=False,
            voice_support=True
        ),
        sla=SLAConfig(
            first_response_hours=2,
            resolution_hours=24,
            escalation_hours=1
        ),
        integrations=IntegrationConfig(
            mindbody=True,
            stripe=True,
            email=True,
            calendly=True,
            zoom=True
        ),
        variant_limits=VariantLimits(
            refund_limit=150.0,
            escalation_threshold=0.40,
            concurrent_calls=5,
            session_timeout_minutes=30
        ),
        membership=MembershipConfig(
            enabled=True,
            tiers=["basic", "premium", "elite", "family"],
            auto_renewal=True,
            freeze_allowed=True,
            cancellation_notice_days=30
        ),
        metadata={
            "website": "https://fitlife-wellness.com",
            "support_email": "support@fitlife-wellness.com",
            "billing_email": "membership@fitlife-wellness.com",
            "founded": 2017,
            "employees": 100,
            "locations": 15,
            "active_members": 8000,
            "monthly_tickets": 900,
            "services": [
                "gym_access",
                "group_classes",
                "personal_training",
                "spa_services",
                "nutrition_coaching",
                "virtual_classes"
            ],
            "class_types": [
                "yoga",
                "pilates",
                "spinning",
                "hiit",
                "boxing",
                "dance",
                "meditation"
            ],
            "special_features": {
                "mobile_app": True,
                "online_booking": True,
                "virtual_classes": True,
                "personal_training_packages": True,
                "corporate_wellness": True
            },
            "compliance": {
                "hipaa": False,  # Not medical
                "payment_card": True
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
