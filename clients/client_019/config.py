"""Client 019 Configuration - LegalEase Services"""

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
    clio: bool = False
    docusign: bool = False
    email: bool = False
    dropbox: bool = False
    quickbooks: bool = False


@dataclass
class VariantLimits:
    """Variant-specific limits"""
    refund_limit: float = 300.0
    escalation_threshold: float = 0.25
    concurrent_calls: int = 10
    session_timeout_minutes: int = 15  # Security


@dataclass
class ComplianceConfig:
    """Legal compliance configuration"""
    attorney_client_privilege: bool = True
    conflict_check: bool = True
    audit_trail: bool = True
    data_retention_years: int = 7
    encryption_required: bool = True


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
    compliance: ComplianceConfig = field(default_factory=ComplianceConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    """Load and return client 019 configuration.

    Client 019 is a Legal Services client using PARWA High variant.
    Clio, DocuSign integrations for law firm support.
    Attorney-client privilege compliance enforced.

    Returns:
        ClientConfig: The client configuration object
    """
    return ClientConfig(
        client_id="client_019",
        client_name="LegalEase Services",
        industry="legal_services",
        variant="high",
        timezone="America/New_York",
        business_hours=BusinessHours(
            start=time(8, 30),
            end=time(18, 30),
            timezone="America/New_York"
        ),
        escalation_contacts=EscalationContact(
            email="intake@legalease-services.law",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/LE019X",
            phone="+1-555-0119"
        ),
        paddle_account_id="acc_legalease019",
        feature_flags=FeatureFlags(
            shadow_mode=True,
            auto_escalation=True,
            sentiment_analysis=True,
            knowledge_base_search=True,
            multi_language=False,
            voice_support=True
        ),
        sla=SLAConfig(
            first_response_hours=1,  # Fast for legal
            resolution_hours=48,
            escalation_hours=1
        ),
        integrations=IntegrationConfig(
            clio=True,
            docusign=True,
            email=True,
            dropbox=True,
            quickbooks=True
        ),
        variant_limits=VariantLimits(
            refund_limit=300.0,
            escalation_threshold=0.25,
            concurrent_calls=10,
            session_timeout_minutes=15
        ),
        compliance=ComplianceConfig(
            attorney_client_privilege=True,
            conflict_check=True,
            audit_trail=True,
            data_retention_years=7,
            encryption_required=True
        ),
        metadata={
            "website": "https://legalease-services.law",
            "support_email": "intake@legalease-services.law",
            "billing_email": "billing@legalease-services.law",
            "founded": 2005,
            "employees": 75,
            "attorneys": 35,
            "practice_areas": [
                "corporate_law",
                "intellectual_property",
                "employment_law",
                "real_estate",
                "family_law",
                "estate_planning",
                "immigration",
                "litigation"
            ],
            "active_cases": 500,
            "monthly_tickets": 450,
            "client_types": ["individuals", "small_business", "corporations"],
            "special_features": {
                "virtual_consultations": True,
                "document_automation": True,
                "case_tracking_portal": True,
                "e_signature": True,
                "secure_messaging": True
            },
            "compliance": {
                "aba_model_rules": True,
                "state_bar_compliance": True,
                "iclief": True,
                " attorney_client_privilege": True
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
