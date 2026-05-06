"""Client 026 Configuration - PharmaCare Solutions"""

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
    voice_support: bool = True


@dataclass
class SLAConfig:
    first_response_hours: int = 2
    resolution_hours: int = 24
    escalation_hours: int = 1


@dataclass
class IntegrationConfig:
    veeva: bool = True
    salesforce: bool = True
    sap: bool = True
    email: bool = True


@dataclass
class VariantLimits:
    refund_limit: float = 200.0
    escalation_threshold: float = 0.25
    concurrent_calls: int = 15
    session_timeout_minutes: int = 45


@dataclass
class PharmaConfig:
    enabled: bool = True
    drug_information: bool = True
    adverse_event_reporting: bool = True
    clinical_trial_support: bool = True
    regulatory_compliance: bool = True
    patient_support_programs: bool = True


@dataclass
class ComplianceConfig:
    fda: bool = True
    hipaa: bool = True
    gdpr: bool = True
    dea: bool = True


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
    pharma: PharmaConfig = field(default_factory=PharmaConfig)
    compliance: ComplianceConfig = field(default_factory=ComplianceConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    return ClientConfig(
        client_id="client_026",
        client_name="PharmaCare Solutions",
        industry="pharmaceutical",
        variant="parwa_high",
        timezone="America/New_York",
        business_hours=BusinessHours(start=time(8, 0), end=time(20, 0), timezone="America/New_York"),
        escalation_contacts=EscalationContact(
            email="support@pharmacare-solutions.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/IH026X",
            phone="+1-555-0126"
        ),
        paddle_account_id="acc_pharmacare026",
        feature_flags=FeatureFlags(shadow_mode=True, auto_escalation=True, sentiment_analysis=True, knowledge_base_search=True, multi_language=False, voice_support=True),
        sla=SLAConfig(first_response_hours=2, resolution_hours=24, escalation_hours=1),
        integrations=IntegrationConfig(veeva=True, salesforce=True, sap=True, email=True),
        variant_limits=VariantLimits(refund_limit=200.0, escalation_threshold=0.25, concurrent_calls=15, session_timeout_minutes=45),
        pharma=PharmaConfig(enabled=True, drug_information=True, adverse_event_reporting=True, clinical_trial_support=True, regulatory_compliance=True, patient_support_programs=True),
        compliance=ComplianceConfig(fda=True, hipaa=True, gdpr=True, dea=True),
        metadata={
            "website": "https://pharmacare-solutions.com",
            "support_email": "support@pharmacare-solutions.com",
            "medical_info_email": "medical@pharmacare-solutions.com",
            "founded": 1995,
            "employees": 5000,
            "therapeutic_areas": ["oncology", "cardiology", "neurology", "immunology", "rare_diseases"],
            "monthly_tickets": 1500,
            "special_features": {
                "drug_info_lookup": True,
                "adverse_event_tracking": True,
                "clinical_trial_info": True,
                "patient_assistance_programs": True,
                "healthcare_provider_portal": True
            },
            "compliance_notes": "No medical advice - information only. All adverse events escalated immediately."
        }
    )
