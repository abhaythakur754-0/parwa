"""
Client 005 Configuration - PayFlow FinTech
Industry: FinTech
Variant: PARWA High
Compliance: PCI DSS, SOC2, GDPR
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class ClientConfig:
    """Client 005 - PayFlow FinTech Configuration"""
    
    client_id: str = "client_005"
    client_name: str = "PayFlow FinTech"
    industry: str = "fintech"
    variant: str = "parwa_high"
    timezone: str = "America/New_York"
    
    business_hours: Dict = field(default_factory=lambda: {
        "start": "09:00",
        "end": "18:00",
        "timezone": "America/New_York",
        "days": ["mon", "tue", "wed", "thu", "fri"],
        "is_24_7": False,
        "emergency_24_7": True
    })
    
    escalation_contacts: Dict = field(default_factory=lambda: {
        "email": "support@payflow.com",
        "slack": "#payflow-urgent",
        "phone": "+1-800-555-0200",
        "pagerduty": "payflow-critical-pd",
        "on_call": "oncall@payflow.com"
    })
    
    features: Dict = field(default_factory=lambda: {
        "payment_processing": True,
        "multi_currency": True,
        "instant_transfers": True,
        "recurring_billing": True,
        "api_access": True,
        "webhooks": True,
        "sandbox_mode": True
    })
    
    sla: Dict = field(default_factory=lambda: {
        "first_response_minutes": 15,
        "resolution_hours": 8,
        "escalation_minutes": 30,
        "critical_escalation_minutes": 10
    })
    
    compliance: Dict = field(default_factory=lambda: {
        "pci_dss_enabled": True,
        "soc2_enabled": True,
        "gdpr_enabled": True,
        "aml_kyc_enabled": True,
        "encryption_at_rest": True,
        "encryption_in_transit": True,
        "data_retention_years": 7
    })
    
    fraud_detection: Dict = field(default_factory=lambda: {
        "enabled": True,
        "real_time_monitoring": True,
        "velocity_checks": True,
        "device_fingerprinting": True,
        "alert_threshold": 0.85
    })
    
    knowledge_base_path: str = "clients/client_005/knowledge_base"
    
    payment: Dict = field(default_factory=lambda: {
        "supported_currencies": ["USD", "EUR", "GBP", "CAD", "AUD", "JPY"],
        "max_transaction_amount": 50000.00,
        "min_transaction_amount": 0.01,
        "instant_transfer_enabled": True
    })


def get_client_config() -> ClientConfig:
    return ClientConfig()


config = get_client_config()
