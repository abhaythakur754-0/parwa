"""Client 029 Configuration - Spark Marketing Agency"""

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
    first_response_hours: int = 4
    resolution_hours: int = 48
    escalation_hours: int = 2


@dataclass
class IntegrationConfig:
    hubspot: bool = True
    stripe: bool = True
    slack: bool = True
    email: bool = True


@dataclass
class VariantLimits:
    refund_limit: float = 75.0
    escalation_threshold: float = 0.55
    concurrent_calls: int = 5
    session_timeout_minutes: int = 30


@dataclass
class MarketingConfig:
    enabled: bool = True
    campaign_support: bool = True
    client_reporting: bool = True
    creative_requests: bool = True
    billing_inquiries: bool = True
    proposal_tracking: bool = True


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
    marketing: MarketingConfig = field(default_factory=MarketingConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    return ClientConfig(
        client_id="client_029",
        client_name="Spark Marketing Agency",
        industry="marketing_advertising",
        variant="parwa_junior",
        timezone="America/New_York",
        business_hours=BusinessHours(start=time(9, 0), end=time(18, 0), timezone="America/New_York"),
        escalation_contacts=EscalationContact(
            email="support@spark-marketing.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/IH029X",
            phone="+1-555-0129"
        ),
        paddle_account_id="acc_sparkmarketing029",
        feature_flags=FeatureFlags(),
        sla=SLAConfig(),
        integrations=IntegrationConfig(),
        variant_limits=VariantLimits(),
        marketing=MarketingConfig(),
        metadata={
            "website": "https://spark-marketing.com",
            "support_email": "support@spark-marketing.com",
            "founded": 2015,
            "employees": 75,
            "active_campaigns": 150,
            "services": ["digital_marketing", "seo", "ppc", "social_media", "content", "branding"],
            "monthly_tickets": 800,
            "special_features": {
                "campaign_dashboard": True,
                "creative_request_workflow": True,
                "client_portal": True,
                "reporting_automation": True,
                "proposal_generator": True
            }
        }
    )
