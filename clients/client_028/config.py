"""Client 028 Configuration - PayrollPro HR"""

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
    workday: bool = True
    adp: bool = True
    salesforce: bool = True
    email: bool = True


@dataclass
class VariantLimits:
    refund_limit: float = 100.0
    escalation_threshold: float = 0.25
    concurrent_calls: int = 15
    session_timeout_minutes: int = 45


@dataclass
class HRConfig:
    enabled: bool = True
    payroll_inquiries: bool = True
    benefits_support: bool = True
    time_tracking: bool = True
    employee_self_service: bool = True
    compliance_reporting: bool = True


@dataclass
class ComplianceConfig:
    pii_protection: bool = True
    employment_laws: bool = True
    sox: bool = True
    gdpr: bool = True


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
    hr: HRConfig = field(default_factory=HRConfig)
    compliance: ComplianceConfig = field(default_factory=ComplianceConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    return ClientConfig(
        client_id="client_028",
        client_name="PayrollPro HR",
        industry="hr_payroll",
        variant="parwa_high",
        timezone="America/Chicago",
        business_hours=BusinessHours(start=time(7, 0), end=time(19, 0), timezone="America/Chicago"),
        escalation_contacts=EscalationContact(
            email="support@payrollpro-hr.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/IH028X",
            phone="+1-555-0128"
        ),
        paddle_account_id="acc_payrollpro028",
        feature_flags=FeatureFlags(),
        sla=SLAConfig(),
        integrations=IntegrationConfig(),
        variant_limits=VariantLimits(),
        hr=HRConfig(),
        compliance=ComplianceConfig(),
        metadata={
            "website": "https://payrollpro-hr.com",
            "support_email": "support@payrollpro-hr.com",
            "founded": 2008,
            "employees": 800,
            "clients_served": 2000,
            "employees_managed": 500000,
            "monthly_tickets": 3000,
            "special_features": {
                "payroll_calculator": True,
                "tax_filing_support": True,
                "benefits_enrollment": True,
                "time_clock_integration": True,
                "direct_deposit_management": True,
                "w2_1099_generation": True
            },
            "compliance_notes": "Strict PII protection. Employment law compliance by state."
        }
    )
