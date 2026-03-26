"""Client 027 Configuration - EventHorizon Management"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import time
import json
from pathlib import Path


@dataclass
class BusinessHours:
    start: time
    end: time
    timezone: str


@dataclass
class EscalationContact:
    email: str
    slack_webhook: Optional[str] = None
    phone: Optional[str] = None


@dataclass
class FeatureFlags:
    shadow_mode: bool = True
    auto_escalation: bool = True
    sentiment_analysis: bool = True
    knowledge_base_search: bool = True
    multi_language: bool = False
    voice_support: bool = False


@dataclass
class SLAConfig:
    first_response_hours: int = 2
    resolution_hours: int = 24
    escalation_hours: int = 1


@dataclass
class IntegrationConfig:
    eventbrite: bool = True
    stripe: bool = True
    mailchimp: bool = True
    email: bool = True


@dataclass
class VariantLimits:
    refund_limit: float = 150.0
    escalation_threshold: float = 0.35
    concurrent_calls: int = 5
    session_timeout_minutes: int = 30


@dataclass
class EventConfig:
    enabled: bool = True
    ticket_support: bool = True
    vendor_management: bool = True
    schedule_changes: bool = True
    refund_processing: bool = True
    vip_support: bool = True


@dataclass
class ClientConfig:
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
    event: EventConfig = field(default_factory=EventConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    return ClientConfig(
        client_id="client_027",
        client_name="EventHorizon Management",
        industry="event_management",
        variant="parwa_junior",
        timezone="America/Los_Angeles",
        business_hours=BusinessHours(start=time(9, 0), end=time(21, 0), timezone="America/Los_Angeles"),
        escalation_contacts=EscalationContact(
            email="support@eventhorizon-mgmt.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/IH027X",
            phone="+1-555-0127"
        ),
        paddle_account_id="acc_eventhorizon027",
        feature_flags=FeatureFlags(),
        sla=SLAConfig(),
        integrations=IntegrationConfig(),
        variant_limits=VariantLimits(),
        event=EventConfig(),
        metadata={
            "website": "https://eventhorizon-mgmt.com",
            "support_email": "support@eventhorizon-mgmt.com",
            "founded": 2010,
            "employees": 120,
            "events_per_year": 500,
            "event_types": ["corporate", "weddings", "concerts", "conferences", "festivals"],
            "monthly_tickets": 2000,
            "special_features": {
                "real_time_schedule": True,
                "attendee_tracking": True,
                "vendor_coordination": True,
                "weather_contingency": True,
                "live_chat_during_events": True
            }
        }
    )
