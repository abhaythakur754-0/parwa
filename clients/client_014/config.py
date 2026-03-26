"""Client 014 Configuration - TravelEase Hospitality"""

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
    amadeus_gds: bool = False
    stripe: bool = False
    whatsapp: bool = False
    booking_com: bool = False
    expedia: bool = False
    airbnb: bool = False


@dataclass
class VariantLimits:
    """Variant-specific limits"""
    refund_limit: float = 300.0
    escalation_threshold: float = 0.30
    concurrent_calls: int = 5
    session_timeout_minutes: int = 30


@dataclass
class PeakHoursConfig:
    """Peak hours handling configuration"""
    enabled: bool = True
    morning_peak_start: time = field(default_factory=lambda: time(8, 0))
    morning_peak_end: time = field(default_factory=lambda: time(10, 0))
    evening_peak_start: time = field(default_factory=lambda: time(17, 0))
    evening_peak_end: time = field(default_factory=lambda: time(20, 0))
    additional_staffing: bool = True


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
    peak_hours: PeakHoursConfig = field(default_factory=PeakHoursConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    """Load and return client 014 configuration.

    Client 014 is a Travel & Hospitality client using PARWA Junior variant.
    Amadeus GDS integration for booking management.
    Peak hours handling for travel rush periods.
    $300 refund limit for bookings.

    Returns:
        ClientConfig: The client configuration object
    """
    return ClientConfig(
        client_id="client_014",
        client_name="TravelEase Hospitality",
        industry="travel_hospitality",
        variant="junior",
        timezone="America/Los_Angeles",
        business_hours=BusinessHours(
            start=time(6, 0),  # Early start for travel industry
            end=time(22, 0),   # 10 PM
            timezone="America/Los_Angeles"
        ),
        escalation_contacts=EscalationContact(
            email="bookings@travelease-hospitality.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/TE014X",
            phone="+1-555-0114"
        ),
        paddle_account_id="acc_travelease014",
        feature_flags=FeatureFlags(
            shadow_mode=True,
            auto_escalation=True,
            sentiment_analysis=True,
            knowledge_base_search=True,
            multi_language=True,  # International travelers
            voice_support=True
        ),
        sla=SLAConfig(
            first_response_hours=1,  # Urgent travel issues
            resolution_hours=8,  # Same-day resolution preferred
            escalation_hours=1
        ),
        integrations=IntegrationConfig(
            amadeus_gds=True,
            stripe=True,
            whatsapp=True,
            booking_com=True,
            expedia=True,
            airbnb=False
        ),
        variant_limits=VariantLimits(
            refund_limit=300.0,
            escalation_threshold=0.30,
            concurrent_calls=5,
            session_timeout_minutes=30
        ),
        peak_hours=PeakHoursConfig(
            enabled=True,
            morning_peak_start=time(8, 0),
            morning_peak_end=time(10, 0),
            evening_peak_start=time(17, 0),
            evening_peak_end=time(20, 0),
            additional_staffing=True
        ),
        metadata={
            "website": "https://travelease-hospitality.com",
            "support_email": "bookings@travelease-hospitality.com",
            "billing_email": "payments@travelease-hospitality.com",
            "founded": 2015,
            "employees": 200,
            "service_types": [
                "flight_bookings",
                "hotel_reservations",
                "car_rentals",
                "vacation_packages",
                "cruises",
                "travel_insurance"
            ],
            "destinations_served": 150,
            "monthly_bookings": 8000,
            "monthly_tickets": 2200,
            "average_booking_value": 650,
            "peak_seasons": ["summer", "spring_break", "christmas", "thanksgiving"],
            "special_features": {
                "last_minute_deals": True,
                "group_bookings": True,
                "loyalty_program": True,
                "price_match_guarantee": True,
                "24_7_emergency_support": True
            },
            "compliance": {
                "pci_dss": True,
                "gdpr": True,
                "iata_certified": True
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
