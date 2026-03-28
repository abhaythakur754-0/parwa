"""Client 030 Configuration - FitLife Sports"""

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
class IntegrationConfig:
    mindbody: bool = True
    stripe: bool = True
    email: bool = True


@dataclass
class VariantLimits:
    refund_limit: float = 100.0
    escalation_threshold: float = 0.40
    concurrent_calls: int = 5
    session_timeout_minutes: int = 30


@dataclass
class FitnessConfig:
    enabled: bool = True
    membership_management: bool = True
    class_booking: bool = True
    personal_training: bool = True
    equipment_support: bool = True
    nutrition_coaching: bool = True


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
    fitness: FitnessConfig = field(default_factory=FitnessConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    return ClientConfig(
        client_id="client_030",
        client_name="FitLife Sports",
        industry="sports_fitness",
        variant="parwa_junior",
        timezone="America/Denver",
        business_hours=BusinessHours(start=time(5, 0), end=time(23, 0), timezone="America/Denver"),
        escalation_contacts=EscalationContact(
            email="support@fitlife-sports.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/IH030X",
            phone="+1-555-0130"
        ),
        paddle_account_id="acc_fitlife030",
        feature_flags=FeatureFlags(),
        sla=SLAConfig(),
        integrations=IntegrationConfig(),
        variant_limits=VariantLimits(),
        fitness=FitnessConfig(),
        metadata={
            "website": "https://fitlife-sports.com",
            "support_email": "support@fitlife-sports.com",
            "founded": 2012,
            "employees": 200,
            "locations": 25,
            "members": 50000,
            "services": ["gym_membership", "group_classes", "personal_training", "nutrition", "spa"],
            "monthly_tickets": 1200,
            "special_features": {
                "class_schedule": True,
                "trainer_booking": True,
                "membership_portal": True,
                "progress_tracking": True,
                "equipment_tutorials": True
            }
        }
    )
