"""
Client 004 Configuration - FastFreight Logistics
Industry: Logistics
Variant: PARWA Junior
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ClientConfig:
    """Client 004 - FastFreight Logistics Configuration"""
    
    client_id: str = "client_004"
    client_name: str = "FastFreight Logistics"
    industry: str = "logistics"
    variant: str = "parwa_junior"
    timezone: str = "America/Chicago"
    
    business_hours: Dict = field(default_factory=lambda: {
        "start": "06:00",
        "end": "22:00",
        "timezone": "America/Chicago",
        "days": ["mon", "tue", "wed", "thu", "fri", "sat"],
        "is_24_7": False
    })
    
    escalation_contacts: Dict = field(default_factory=lambda: {
        "email": "ops@fastfreight.com",
        "slack": "#freight-ops",
        "phone": "+1-800-555-0199",
        "pagerduty": "fastfreight-ops-pd"
    })
    
    features: Dict = field(default_factory=lambda: {
        "tracking_integration": True,
        "shipment_apis": True,
        "international_shipping": True,
        "claims_processing": True,
        "real_time_updates": True
    })
    
    sla: Dict = field(default_factory=lambda: {
        "first_response_minutes": 30,
        "resolution_hours": 24,
        "escalation_minutes": 60
    })
    
    knowledge_base_path: str = "clients/client_004/knowledge_base"
    
    tracking: Dict = field(default_factory=lambda: {
        "tracking_number_formats": ["FF\\d{10}", "FFINT\\d{12}"],
        "tracking_api_enabled": True,
        "real_time_updates": True
    })


def get_client_config() -> ClientConfig:
    return ClientConfig()


config = get_client_config()
