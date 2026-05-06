"""Client 008 Configuration - TravelEase

Global travel client with 24/7 support.
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
    multi_language: bool = True  # Global travel - multiple languages
    voice_support: bool = True  # PARWA High feature


@dataclass
class SLAConfig:
    """SLA configuration"""
    first_response_hours: int = 1  # Fast for travel emergencies
    resolution_hours: int = 12
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
    """Load and return client 008 configuration.

    Client 008 is a global travel client using PARWA High variant.
    24/7 support for international travelers across all time zones.

    Returns:
        ClientConfig: The client configuration object
    """
    return ClientConfig(
        client_id="client_008",
        client_name="TravelEase",
        industry="travel",
        variant="parwa_high",
        timezone="UTC",  # Global - use UTC
        business_hours=BusinessHours(
            start=time(0, 0),
            end=time(23, 59),  # 24/7 support
            timezone="UTC"
        ),
        escalation_contacts=EscalationContact(
            email="support@travelease.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/TVLXXX",
            phone="+1-555-0158"
        ),
        paddle_account_id="acc_travelease008",
        feature_flags=FeatureFlags(
            shadow_mode=True,
            auto_escalation=True,
            sentiment_analysis=True,
            knowledge_base_search=True,
            multi_language=True,
            voice_support=True
        ),
        sla=SLAConfig(
            first_response_hours=1,  # 1 hour - travel is time-sensitive
            resolution_hours=12,
            escalation_hours=1
        ),
        metadata={
            "website": "https://travelease.com",
            "support_email": "support@travelease.com",
            "billing_email": "billing@travelease.com",
            "founded": 2012,
            "employees": 500,
            "annual_bookings": "2M+",
            "destinations": 190,  # Countries served
            "partners": {
                "airlines": 50,
                "hotels": 10000,
                "car_rentals": 20,
                "tours": 500
            },
            "languages_supported": [
                "English", "Spanish", "French", "German",
                "Italian", "Portuguese", "Japanese", "Chinese",
                "Korean", "Arabic"
            ],
            "features": {
                "flight_booking": True,
                "hotel_booking": True,
                "car_rental": True,
                "vacation_packages": True,
                "travel_insurance": True,
                "loyalty_program": True,
                "concierge_service": True,
                "visa_assistance": True
            },
            "emergency_support": {
                "available": True,
                "phone": "+1-555-TRAVEL-911",
                "response_time_minutes": 15
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
