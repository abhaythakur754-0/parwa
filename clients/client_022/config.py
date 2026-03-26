"""Client 022 Configuration - AutoDrive Motors"""

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
    voice_support: bool = True


@dataclass
class SLAConfig:
    """SLA configuration"""
    first_response_hours: int = 2
    resolution_hours: int = 48
    escalation_hours: int = 1


@dataclass
class IntegrationConfig:
    """Third-party integrations"""
    salesforce: bool = True
    sap: bool = True
    twilio: bool = True
    email: bool = True


@dataclass
class VariantLimits:
    """Variant-specific limits for PARWA High"""
    refund_limit: float = 500.0
    escalation_threshold: float = 0.30
    concurrent_calls: int = 10
    session_timeout_minutes: int = 60


@dataclass
class AutomotiveConfig:
    """Automotive specific configuration"""
    enabled: bool = True
    service_appointment_handling: bool = True
    parts_ordering: bool = True
    warranty_claims: bool = True
    recall_management: bool = True
    financing_support: bool = True
    roadside_assistance: bool = True


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
    automotive: AutomotiveConfig = field(default_factory=AutomotiveConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    """Load and return client 022 configuration.

    Client 022 is an Automotive company using PARWA High variant.
    Service appointments, parts ordering, warranty claims.
    Roadside assistance coordination.

    Returns:
        ClientConfig: The client configuration object
    """
    return ClientConfig(
        client_id="client_022",
        client_name="AutoDrive Motors",
        industry="automotive",
        variant="parwa_high",
        timezone="America/Detroit",
        business_hours=BusinessHours(
            start=time(7, 0),
            end=time(19, 0),
            timezone="America/Detroit"
        ),
        escalation_contacts=EscalationContact(
            email="customerservice@autodrive-motors.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/IH022X",
            phone="+1-555-0122"
        ),
        paddle_account_id="acc_autodrive022",
        feature_flags=FeatureFlags(
            shadow_mode=True,
            auto_escalation=True,
            sentiment_analysis=True,
            knowledge_base_search=True,
            multi_language=False,
            voice_support=True
        ),
        sla=SLAConfig(
            first_response_hours=2,
            resolution_hours=48,
            escalation_hours=1
        ),
        integrations=IntegrationConfig(
            salesforce=True,
            sap=True,
            twilio=True,
            email=True
        ),
        variant_limits=VariantLimits(
            refund_limit=500.0,  # Parts/service refunds
            escalation_threshold=0.30,
            concurrent_calls=10,
            session_timeout_minutes=60
        ),
        automotive=AutomotiveConfig(
            enabled=True,
            service_appointment_handling=True,
            parts_ordering=True,
            warranty_claims=True,
            recall_management=True,
            financing_support=True,
            roadside_assistance=True
        ),
        metadata={
            "website": "https://autodrive-motors.com",
            "support_email": "customerservice@autodrive-motors.com",
            "parts_email": "parts@autodrive-motors.com",
            "service_email": "service@autodrive-motors.com",
            "founded": 2005,
            "employees": 2500,
            "dealerships": 45,
            "annual_sales": 50000,
            "description": "Full-service automotive dealership network with parts and service centers",
            "brands": [
                "autodrive_sedan",
                "autodrive_suv",
                "autodrive_truck",
                "autodrive_electric"
            ],
            "monthly_tickets": 1800,
            "service_bays": 150,
            "special_features": {
                "online_appointment_booking": True,
                "parts_inventory_lookup": True,
                "warranty_tracking": True,
                "financing_calculator": True,
                "trade_in_estimator": True
            },
            "compliance": {
                "ftc_used_car_rule": True,
                "state_licensing": True,
                "recall_notifications": True
            }
        }
    )


def load_config_from_file(filepath: str) -> ClientConfig:
    """Load config from JSON file."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")
    with open(path) as f:
        data = json.load(f)
    return ClientConfig(**data)
