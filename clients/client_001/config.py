"""Client 001 Configuration - Acme E-commerce"""

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
    resolution_hours: int = 24
    escalation_hours: int = 2

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
    metadata: Dict[str, Any] = field(default_factory=dict)

def get_client_config() -> ClientConfig:
    """Load and return client 001 configuration"""
    return ClientConfig(
        client_id="client_001",
        client_name="Acme E-commerce",
        industry="ecommerce",
        variant="parwa",
        timezone="America/New_York",
        business_hours=BusinessHours(
            start=time(9, 0),
            end=time(18, 0),
            timezone="America/New_York"
        ),
        escalation_contacts=EscalationContact(
            email="support@acme-ecommerce.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/XXXXX",
            phone="+1-555-0123"
        ),
        paddle_account_id="acc_abc123xyz",
        feature_flags=FeatureFlags(
            shadow_mode=True,
            auto_escalation=True,
            sentiment_analysis=True,
            knowledge_base_search=True,
            multi_language=False,
            voice_support=False
        ),
        sla=SLAConfig(
            first_response_hours=4,
            resolution_hours=24,
            escalation_hours=2
        ),
        metadata={
            "website": "https://acme-ecommerce.com",
            "support_email": "support@acme-ecommerce.com",
            "billing_email": "billing@acme-ecommerce.com",
            "founded": 2020,
            "employees": 50
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
