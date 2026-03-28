"""Client 023 Configuration - PowerGrid Utilities"""

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
    first_response_hours: int = 1
    resolution_hours: int = 24
    escalation_hours: int = 0.5


@dataclass
class IntegrationConfig:
    """Third-party integrations"""
    oracle: bool = True
    salesforce: bool = True
    email: bool = True


@dataclass
class VariantLimits:
    """Variant-specific limits for PARWA High"""
    refund_limit: float = 200.0
    escalation_threshold: float = 0.30
    concurrent_calls: int = 15
    session_timeout_minutes: int = 45


@dataclass
class EnergyConfig:
    """Energy/Utilities specific configuration"""
    enabled: bool = True
    outage_management: bool = True
    billing_inquiry: bool = True
    service_requests: bool = True
    meter_reading: bool = True
    energy_programs: bool = True
    emergency_protocols: bool = True


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
    energy: EnergyConfig = field(default_factory=EnergyConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    """Load and return client 023 configuration.

    Client 023 is an Energy & Utilities company using PARWA High variant.
    Outage communication, billing adjustments, service requests.
    Energy regulation compliance.

    Returns:
        ClientConfig: The client configuration object
    """
    return ClientConfig(
        client_id="client_023",
        client_name="PowerGrid Utilities",
        industry="energy_utilities",
        variant="parwa_high",
        timezone="America/Chicago",
        business_hours=BusinessHours(
            start=time(0, 0),  # 24/7 for utilities
            end=time(23, 59),
            timezone="America/Chicago"
        ),
        escalation_contacts=EscalationContact(
            email="customerservice@powergrid-utilities.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/IH023X",
            phone="+1-555-0123"
        ),
        paddle_account_id="acc_powergrid023",
        feature_flags=FeatureFlags(
            shadow_mode=True,
            auto_escalation=True,
            sentiment_analysis=True,
            knowledge_base_search=True,
            multi_language=False,
            voice_support=True
        ),
        sla=SLAConfig(
            first_response_hours=1,  # Faster for utilities
            resolution_hours=24,
            escalation_hours=0.5
        ),
        integrations=IntegrationConfig(
            oracle=True,
            salesforce=True,
            email=True
        ),
        variant_limits=VariantLimits(
            refund_limit=200.0,  # Billing adjustments
            escalation_threshold=0.30,
            concurrent_calls=15,
            session_timeout_minutes=45
        ),
        energy=EnergyConfig(
            enabled=True,
            outage_management=True,
            billing_inquiry=True,
            service_requests=True,
            meter_reading=True,
            energy_programs=True,
            emergency_protocols=True
        ),
        metadata={
            "website": "https://powergrid-utilities.com",
            "support_email": "customerservice@powergrid-utilities.com",
            "outage_hotline": "1-800-POWER-911",
            "founded": 1952,
            "employees": 3500,
            "customers": 1200000,
            "service_area": "Midwest United States",
            "description": "Regional electric utility serving residential and commercial customers",
            "power_sources": [
                "natural_gas",
                "solar",
                "wind",
                "nuclear",
                "hydro"
            ],
            "monthly_tickets": 3200,
            "special_features": {
                "outage_map": True,
                "usage_dashboard": True,
                "paperless_billing": True,
                "autopay": True,
                "budget_billing": True,
                "smart_meter_support": True,
                "renewable_programs": True
            },
            "compliance": {
                "ferc": True,
                "nerc": True,
                "epa": True,
                "state_public_utility_commission": True
            },
            "peak_hours": {
                "summer": ["14:00", "19:00"],
                "winter": ["06:00", "09:00", "17:00", "20:00"]
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
