"""Client 050 Configuration - GlobalShip Enterprise"""

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
    voice_support: bool = True


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
        client_id="client_050",
        client_name="GlobalShip Enterprise",
        industry="logistics",
        variant="parwa_high",
        timezone="UTC",
        business_hours=BusinessHours(start=time(8, 0), end=time(20, 0), timezone="UTC"),
        escalation_contacts=EscalationContact(
            email="support@globalshipenterprise.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/IH050",
            phone="+1-555-050",
        ),
        paddle_account_id="acc_client050",
        feature_flags=FeatureFlags(),
        sla=SLAConfig(),
        metadata={
            "website": "https://globalshipenterprise.com",
            "support_email": "support@globalshipenterprise.com",
            "founded": 2019,
            "employees": 600,
            "users": 45000,
            "monthly_tickets": 900,
        },
    )
