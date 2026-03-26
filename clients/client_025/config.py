"""Client 025 Configuration - ConnectTel Communications"""

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
    multi_language: bool = True
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
    salesforce: bool = True
    sap: bool = True
    twilio: bool = True
    email: bool = True


@dataclass
class VariantLimits:
    """Variant-specific limits for PARWA High"""
    refund_limit: float = 300.0
    escalation_threshold: float = 0.30
    concurrent_calls: int = 20
    session_timeout_minutes: int = 60


@dataclass
class TelecomConfig:
    """Telecommunications specific configuration"""
    enabled: bool = True
    technical_support: bool = True
    billing_support: bool = True
    service_provisioning: bool = True
    network_troubleshooting: bool = True
    equipment_support: bool = True
    plan_changes: bool = True
    number_porting: bool = True


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
    telecom: TelecomConfig = field(default_factory=TelecomConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    """Load and return client 025 configuration.

    Client 025 is a Telecommunications company using PARWA High variant.
    Technical support routing, service credits, FCC compliance.
    Mobile and internet services.

    Returns:
        ClientConfig: The client configuration object
    """
    return ClientConfig(
        client_id="client_025",
        client_name="ConnectTel Communications",
        industry="telecommunications",
        variant="parwa_high",
        timezone="America/Chicago",
        business_hours=BusinessHours(
            start=time(0, 0),  # 24/7 for telecom
            end=time(23, 59),
            timezone="America/Chicago"
        ),
        escalation_contacts=EscalationContact(
            email="support@connecttel-comms.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/IH025X",
            phone="+1-555-0125"
        ),
        paddle_account_id="acc_connecttel025",
        feature_flags=FeatureFlags(
            shadow_mode=True,
            auto_escalation=True,
            sentiment_analysis=True,
            knowledge_base_search=True,
            multi_language=True,  # Diverse customer base
            voice_support=True
        ),
        sla=SLAConfig(
            first_response_hours=1,  # Fast for telecom
            resolution_hours=24,
            escalation_hours=0.5
        ),
        integrations=IntegrationConfig(
            salesforce=True,
            sap=True,
            twilio=True,
            email=True
        ),
        variant_limits=VariantLimits(
            refund_limit=300.0,  # Service credits
            escalation_threshold=0.30,
            concurrent_calls=20,
            session_timeout_minutes=60
        ),
        telecom=TelecomConfig(
            enabled=True,
            technical_support=True,
            billing_support=True,
            service_provisioning=True,
            network_troubleshooting=True,
            equipment_support=True,
            plan_changes=True,
            number_porting=True
        ),
        metadata={
            "website": "https://connecttel-comms.com",
            "support_email": "support@connecttel-comms.com",
            "technical_support": "1-800-CONNECT-1",
            "founded": 1998,
            "employees": 8500,
            "customers": 5000000,
            "service_area": "Nationwide",
            "description": "National telecommunications provider offering mobile, internet, and business solutions",
            "services": [
                "mobile_voice",
                "mobile_data",
                "fiber_internet",
                "cable_internet",
                "voip",
                "business_solutions",
                "iot_connectivity"
            ],
            "monthly_tickets": 8500,
            "special_features": {
                "network_status_dashboard": True,
                "coverage_map": True,
                "data_usage_tracker": True,
                "plan_comparison_tool": True,
                "equipment_tracker": True,
                "outage_notifications": True,
                "self_service_portal": True
            },
            "network_stats": {
                "lte_coverage": "98%",
                "5g_cities": 250,
                "data_centers": 15,
                "cell_towers": 50000
            },
            "compliance": {
                "fcc": True,
                "ftc": True,
                "cpni": True,  # Customer Proprietary Network Information
                "ecal": True,  # Emergency Call Alerting
                "wireless_emergency_alerts": True
            },
            "supported_languages": ["en", "es", "zh", "vi", "ko", "tagalog"],
            "customer_segments": [
                "consumer_mobile",
                "consumer_internet",
                "small_business",
                "enterprise",
                "government",
                "wholesale"
            ]
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
