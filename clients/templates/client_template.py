"""
Client Template Generator
Generate client configurations from templates
"""

from dataclasses import dataclass
from typing import Dict, List, Any
from datetime import datetime
import json


INDUSTRY_PRESETS: Dict[str, Dict[str, Any]] = {
    "ecommerce": {
        "business_hours": {"start": "09:00", "end": "21:00", "timezone": "America/New_York", "is_24_7": False},
        "features": {"order_tracking": True, "returns_processing": True, "inventory_check": True},
        "sla": {"first_response_minutes": 15, "resolution_hours": 24},
        "knowledge_categories": ["Orders", "Shipping", "Returns", "Products", "Payments"]
    },
    "saas": {
        "business_hours": {"start": "09:00", "end": "18:00", "timezone": "America/Los_Angeles", "is_24_7": False},
        "features": {"account_management": True, "billing_support": True, "technical_support": True},
        "sla": {"first_response_minutes": 30, "resolution_hours": 48},
        "knowledge_categories": ["Account", "Billing", "Features", "Technical"]
    },
    "healthcare": {
        "business_hours": {"start": "00:00", "end": "23:59", "timezone": "America/New_York", "is_24_7": True},
        "features": {"appointment_scheduling": True, "prescription_refill": True, "hipaa_compliance": True},
        "sla": {"first_response_minutes": 5, "resolution_hours": 4},
        "knowledge_categories": ["Appointments", "Billing", "Insurance", "Prescriptions"]
    },
    "logistics": {
        "business_hours": {"start": "06:00", "end": "22:00", "timezone": "America/Chicago", "is_24_7": False},
        "features": {"tracking_integration": True, "shipment_apis": True, "claims_processing": True},
        "sla": {"first_response_minutes": 30, "resolution_hours": 24},
        "knowledge_categories": ["Shipping", "Tracking", "Returns", "International", "Claims"]
    },
    "fintech": {
        "business_hours": {"start": "09:00", "end": "18:00", "timezone": "America/New_York", "is_24_7": False, "emergency_24_7": True},
        "features": {"payment_processing": True, "multi_currency": True, "fraud_detection": True},
        "sla": {"first_response_minutes": 15, "resolution_hours": 8},
        "knowledge_categories": ["Payments", "Security", "Accounts", "Fees", "Transfers"]
    }
}

VARIANT_CONFIGS: Dict[str, Dict[str, Any]] = {
    "parwa_junior": {"features": {"basic_support": True, "email_support": True}, "limits": {"monthly_tickets": 500}},
    "parwa_mid": {"features": {"basic_support": True, "email_support": True, "phone_support": True}, "limits": {"monthly_tickets": 2000}},
    "parwa_high": {"features": {"basic_support": True, "email_support": True, "phone_support": True, "api_access": True}, "limits": {"monthly_tickets": -1}}
}


@dataclass
class ClientTemplate:
    client_id: str
    client_name: str
    industry: str
    variant: str
    timezone: str = "America/New_York"
    
    def generate_config(self) -> Dict[str, Any]:
        industry_config = INDUSTRY_PRESETS.get(self.industry, INDUSTRY_PRESETS["ecommerce"])
        variant_config = VARIANT_CONFIGS.get(self.variant, VARIANT_CONFIGS["parwa_junior"])
        
        return {
            "client_id": self.client_id,
            "client_name": self.client_name,
            "industry": self.industry,
            "variant": self.variant,
            "timezone": self.timezone,
            "business_hours": industry_config["business_hours"],
            "features": {**industry_config.get("features", {}), **variant_config.get("features", {})},
            "sla": industry_config["sla"],
            "limits": variant_config.get("limits", {}),
            "created_at": datetime.now().isoformat()
        }
    
    def generate_faq_template(self) -> List[Dict[str, Any]]:
        categories = INDUSTRY_PRESETS.get(self.industry, {}).get("knowledge_categories", ["General"])
        
        return [
            {"id": f"faq_{i+1:03d}", "category": cat, "question": f"Sample question about {cat.lower()}", "answer": f"Sample answer for {cat.lower()}.", "keywords": [cat.lower()]}
            for i, cat in enumerate(categories[:5])
        ]


class ClientTemplateGenerator:
    @staticmethod
    def create_from_params(client_id: str, client_name: str, industry: str, variant: str, timezone: str = "America/New_York") -> ClientTemplate:
        return ClientTemplate(client_id=client_id, client_name=client_name, industry=industry, variant=variant, timezone=timezone)
    
    @staticmethod
    def get_available_industries() -> List[str]:
        return list(INDUSTRY_PRESETS.keys())
    
    @staticmethod
    def get_available_variants() -> List[str]:
        return list(VARIANT_CONFIGS.keys())


def create_client(client_id: str, client_name: str, industry: str, variant: str) -> Dict[str, Any]:
    template = ClientTemplate(client_id=client_id, client_name=client_name, industry=industry, variant=variant)
    return template.generate_config()
