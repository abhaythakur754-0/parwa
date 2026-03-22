"""Client 002 Configuration - TechStart SaaS"""

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
    pagerduty_key: Optional[str] = None
    phone: Optional[str] = None


@dataclass
class FeatureFlags:
    shadow_mode: bool = True
    auto_escalation: bool = True
    sentiment_analysis: bool = True
    knowledge_base_search: bool = True
    multi_language: bool = True
    voice_support: bool = False
    api_integration: bool = True
    advanced_analytics: bool = True


@dataclass
class SLAConfig:
    first_response_hours: int = 2
    resolution_hours: int = 8
    escalation_hours: int = 1


@dataclass
class ComplianceConfig:
    hipaa_enabled: bool = False
    gdpr_enabled: bool = True
    soc2_enabled: bool = True
    data_retention_days: int = 90


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
    compliance: ComplianceConfig
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    """Load and return client 002 configuration"""
    return ClientConfig(
        client_id="client_002",
        client_name="TechStart SaaS",
        industry="saas",
        variant="parwa_high",
        timezone="America/Los_Angeles",
        business_hours=BusinessHours(
            start=time(8, 0),
            end=time(20, 0),
            timezone="America/Los_Angeles"
        ),
        escalation_contacts=EscalationContact(
            email="support@techstart.io",
            slack_webhook="https://hooks.slack.com/services/TYYYYY/BYYYYY/YYYYY",
            pagerduty_key="pd_key_xyz789",
            phone="+1-555-0456"
        ),
        paddle_account_id="acc_def456uvw",
        feature_flags=FeatureFlags(
            shadow_mode=True,
            auto_escalation=True,
            sentiment_analysis=True,
            knowledge_base_search=True,
            multi_language=True,
            voice_support=False,
            api_integration=True,
            advanced_analytics=True
        ),
        sla=SLAConfig(
            first_response_hours=2,
            resolution_hours=8,
            escalation_hours=1
        ),
        compliance=ComplianceConfig(
            hipaa_enabled=False,
            gdpr_enabled=True,
            soc2_enabled=True,
            data_retention_days=90
        ),
        metadata={
            "website": "https://techstart.io",
            "support_email": "support@techstart.io",
            "api_docs": "https://docs.techstart.io",
            "status_page": "https://status.techstart.io",
            "founded": 2021,
            "employees": 120,
            "arr": "$5M"
        }
    )


def load_config_from_file(filepath: str) -> ClientConfig:
    """Load config from JSON file"""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")
    with open(path) as f:
        data = json.load(f)
    return ClientConfig(**data)
