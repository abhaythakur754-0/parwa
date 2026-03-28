"""Client 012 Configuration - EduLearn Platform"""

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
    stripe: bool = False
    intercom: bool = False
    slack: bool = False
    zoom: bool = False
    canvas: bool = False
    moodle: bool = False


@dataclass
class VariantLimits:
    """Variant-specific limits"""
    refund_limit: float = 200.0
    escalation_threshold: float = 0.35
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
    """Load and return client 012 configuration.

    Client 012 is an EdTech SaaS client using PARWA Junior variant.
    24/7 global support for international students across all time zones.
    Stripe, Intercom, Slack integrations for learning platform.

    Returns:
        ClientConfig: The client configuration object
    """
    return ClientConfig(
        client_id="client_012",
        client_name="EduLearn Platform",
        industry="edtech_saas",
        variant="junior",
        timezone="UTC",  # Global platform
        business_hours=BusinessHours(
            start=time(0, 0),  # 24/7 support
            end=time(23, 59),
            timezone="UTC"
        ),
        escalation_contacts=EscalationContact(
            email="support@edulearn-platform.io",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/EL012X",
            phone="+1-555-0112"
        ),
        paddle_account_id="acc_edulearn012",
        feature_flags=FeatureFlags(
            shadow_mode=True,
            auto_escalation=True,
            sentiment_analysis=True,
            knowledge_base_search=True,
            multi_language=True,  # Global students - 15+ languages
            voice_support=True
        ),
        sla=SLAConfig(
            first_response_hours=1,  # Fast response for students
            resolution_hours=12,  # Quick resolution for learning issues
            escalation_hours=1
        ),
        integrations=IntegrationConfig(
            stripe=True,
            intercom=True,
            slack=True,
            zoom=True,
            canvas=True,
            moodle=True
        ),
        variant_limits=VariantLimits(
            refund_limit=200.0,
            escalation_threshold=0.35,
            concurrent_calls=5,
            session_timeout_minutes=30
        ),
        metadata={
            "website": "https://edulearn-platform.io",
            "support_email": "support@edulearn-platform.io",
            "billing_email": "billing@edulearn-platform.io",
            "founded": 2020,
            "employees": 80,
            "supported_languages": [
                "en", "es", "fr", "de", "pt", "zh", "ja", "ko",
                "ar", "hi", "it", "ru", "nl", "pl", "tr"
            ],
            "course_categories": [
                "Technology",
                "Business",
                "Design",
                "Marketing",
                "Data Science",
                "Languages",
                "Personal Development"
            ],
            "subscription_tiers": ["free", "basic", "pro", "enterprise"],
            "active_students": 50000,
            "monthly_tickets": 2500,
            "peak_periods": ["enrollment_season", "exam_period", "new_year"],
            "special_features": {
                "live_classes": True,
                "certificates": True,
                "corporate_training": True,
                "scholarships": True,
                "mobile_learning": True
            },
            "compliance": {
                "ferpa": True,  # US student privacy
                "gdpr": True,   # EU students
                "coppa": True   # Under-13 protection
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
