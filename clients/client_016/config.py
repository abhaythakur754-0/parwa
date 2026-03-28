"""Client 016 Configuration - ManufacturePro B2B"""

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
    voice_support: bool = False


@dataclass
class SLAConfig:
    """SLA configuration"""
    first_response_hours: int = 4
    resolution_hours: int = 24
    escalation_hours: int = 2


@dataclass
class IntegrationConfig:
    """Third-party integrations"""
    sap: bool = False
    salesforce: bool = False
    email: bool = False
    slack: bool = False
    microsoft_dynamics: bool = False


@dataclass
class VariantLimits:
    """Variant-specific limits"""
    refund_limit: float = 500.0
    escalation_threshold: float = 0.25
    concurrent_calls: int = 10
    session_timeout_minutes: int = 30


@dataclass
class DepartmentRouting:
    """Multi-department routing configuration"""
    enabled: bool = True
    departments: List[str] = field(default_factory=list)
    auto_route: bool = True
    sla_minutes: int = 30


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
    department_routing: DepartmentRouting = field(default_factory=DepartmentRouting)
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    """Load and return client 016 configuration.

    Client 016 is a Manufacturing B2B client using PARWA High variant.
    SAP, Salesforce integrations for enterprise operations.
    Multi-department routing for complex B2B support.

    Returns:
        ClientConfig: The client configuration object
    """
    return ClientConfig(
        client_id="client_016",
        client_name="ManufacturePro B2B",
        industry="manufacturing_b2b",
        variant="high",
        timezone="America/Detroit",
        business_hours=BusinessHours(
            start=time(7, 0),
            end=time(19, 0),  # Extended B2B hours
            timezone="America/Detroit"
        ),
        escalation_contacts=EscalationContact(
            email="support@manufacturepro-b2b.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/MP016X",
            phone="+1-555-0116"
        ),
        paddle_account_id="acc_manufacturepro016",
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
            resolution_hours=48,  # B2B takes longer
            escalation_hours=1
        ),
        integrations=IntegrationConfig(
            sap=True,
            salesforce=True,
            email=True,
            slack=True,
            microsoft_dynamics=True
        ),
        variant_limits=VariantLimits(
            refund_limit=500.0,
            escalation_threshold=0.25,
            concurrent_calls=10,
            session_timeout_minutes=30
        ),
        department_routing=DepartmentRouting(
            enabled=True,
            departments=[
                "orders",
                "technical_support",
                "quality",
                "logistics",
                "accounts_payable",
                "engineering"
            ],
            auto_route=True,
            sla_minutes=30
        ),
        metadata={
            "website": "https://manufacturepro-b2b.com",
            "support_email": "support@manufacturepro-b2b.com",
            "billing_email": "ap@manufacturepro-b2b.com",
            "founded": 1998,
            "employees": 2500,
            "product_categories": [
                "industrial_equipment",
                "raw_materials",
                "components",
                "machinery",
                "tools"
            ],
            "annual_revenue": "500M",
            "b2b_customers": 500,
            "monthly_tickets": 1200,
            "average_order_value": 25000,
            "special_features": {
                "bulk_orders": True,
                "custom_manufacturing": True,
                "technical_documentation": True,
                "quality_certifications": True,
                "inventory_integration": True
            },
            "compliance": {
                "iso_9001": True,
                "iso_14001": True,
                "osha": True,
                "itar": False
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
