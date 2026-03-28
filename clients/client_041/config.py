"""Client 041 Configuration - PeopleFirst HR"""

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
        client_id="client_041",
        client_name="PeopleFirst HR",
        industry="hr_software",
        variant="parwa_junior",
        timezone="America/New_York",
        business_hours=BusinessHours(start=time(8, 0), end=time(20, 0), timezone="America/New_York"),
        escalation_contacts=EscalationContact(
            email="support@peoplefirsthr.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/IH041",
            phone="+1-555-041",
        ),
        paddle_account_id="acc_client041",
        feature_flags=FeatureFlags(),
        sla=SLAConfig(),
        metadata={
            "website": "https://peoplefirsthr.com",
            "support_email": "support@peoplefirsthr.com",
            "founded": 2019,
            "employees": 120,
            "users": 30000,
            "monthly_tickets": 450,
        },
    )
