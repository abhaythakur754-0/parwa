"""Client 036 Configuration - PropTech Realty"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import time


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
    first_response_hours: int = 1
    resolution_hours: int = 8
    escalation_hours: int = 1


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
    feature_flags: FeatureFlags = field(default_factory=FeatureFlags)
    sla: SLAConfig = field(default_factory=SLAConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    return ClientConfig(
        client_id="client_036",
        client_name="PropTech Realty",
        industry="real_estate",
        variant="parwa_junior",
        timezone="America/New_York",
        business_hours=BusinessHours(start=time(8, 0), end=time(20, 0), timezone="America/New_York"),
        escalation_contacts=EscalationContact(
            email="support@proptechrealty.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/IH036",
            phone="+1-555-036",
        ),
        paddle_account_id="acc_client036",
        feature_flags=FeatureFlags(),
        sla=SLAConfig(),
        metadata={
            "website": "https://proptechrealty.com",
            "support_email": "support@proptechrealty.com",
            "founded": 2019,
            "employees": 100,
            "users": 10000,
            "monthly_tickets": 400,
        },
    )
