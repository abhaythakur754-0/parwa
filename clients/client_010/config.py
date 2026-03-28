"""Client 010 Configuration - StreamPlus Media

Entertainment/Streaming client with 24/7 global support.
PARWA High variant for premium features.
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
    multi_language: bool = True  # Global streaming
    voice_support: bool = True  # PARWA High


@dataclass
class SLAConfig:
    """SLA configuration"""
    first_response_hours: int = 1  # Fast for streaming issues
    resolution_hours: int = 8
    escalation_hours: int = 1


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
    """Load and return client 010 configuration.

    Client 010 is a streaming/entertainment client using PARWA High variant.
    24/7 support for global subscribers across all time zones.

    Returns:
        ClientConfig: The client configuration object
    """
    return ClientConfig(
        client_id="client_010",
        client_name="StreamPlus Media",
        industry="entertainment",
        variant="parwa_high",
        timezone="America/Los_Angeles",
        business_hours=BusinessHours(
            start=time(0, 0),
            end=time(23, 59),  # 24/7 support
            timezone="America/Los_Angeles"
        ),
        escalation_contacts=EscalationContact(
            email="support@streamplusmedia.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/STMXXX",
            phone="+1-555-0160"
        ),
        paddle_account_id="acc_streamplus010",
        feature_flags=FeatureFlags(
            shadow_mode=True,
            auto_escalation=True,
            sentiment_analysis=True,
            knowledge_base_search=True,
            multi_language=True,
            voice_support=True
        ),
        sla=SLAConfig(
            first_response_hours=1,
            resolution_hours=8,
            escalation_hours=1
        ),
        metadata={
            "website": "https://streamplusmedia.com",
            "support_email": "support@streamplusmedia.com",
            "billing_email": "billing@streamplusmedia.com",
            "founded": 2019,
            "employees": 800,
            "subscribers": "5M+",
            "content_library": {
                "movies": 10000,
                "tv_shows": 5000,
                "documentaries": 2000,
                "originals": 150,
                "live_channels": 50
            },
            "supported_devices": [
                "Smart TVs",
                "Mobile (iOS/Android)",
                "Web Browser",
                "Gaming Consoles",
                "Streaming Devices",
                "Smart Home"
            ],
            "subscription_tiers": {
                "basic": {"price": 9.99, "resolution": "720p", "screens": 1},
                "standard": {"price": 14.99, "resolution": "1080p", "screens": 2},
                "premium": {"price": 19.99, "resolution": "4K HDR", "screens": 4}
            },
            "features": {
                "offline_download": True,
                "multiple_profiles": True,
                "kids_mode": True,
                "parental_controls": True,
                "live_sports": True,
                "ad_free": True
            },
            "content_partners": [
                "Major Hollywood Studios",
                "Independent Filmmakers",
                "International Distributors",
                "Sports Leagues"
            ]
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
