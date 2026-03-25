"""Client 007 Configuration - EduLearn Academy

Education client with FERPA compliance enabled.
"""

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
class ComplianceConfig:
    """Compliance configuration for education"""
    ferpa_enabled: bool = True
    coppa_enabled: bool = False  # Children under 13
    gdpr_enabled: bool = False
    data_retention_days: int = 365


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
    compliance: ComplianceConfig
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    """Load and return client 007 configuration.

    Client 007 is an education client using PARWA Junior variant.
    FERPA compliance is enabled for student data protection.

    Returns:
        ClientConfig: The client configuration object
    """
    return ClientConfig(
        client_id="client_007",
        client_name="EduLearn Academy",
        industry="education",
        variant="parwa_junior",
        timezone="America/New_York",
        business_hours=BusinessHours(
            start=time(8, 0),
            end=time(20, 0),  # Extended hours for student support
            timezone="America/New_York"
        ),
        escalation_contacts=EscalationContact(
            email="support@edulearn-academy.edu",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/EDUXXX",
            phone="+1-555-0157"
        ),
        paddle_account_id="acc_edulearn007",
        feature_flags=FeatureFlags(
            shadow_mode=True,
            auto_escalation=True,
            sentiment_analysis=True,
            knowledge_base_search=True,
            multi_language=True,  # International students
            voice_support=False
        ),
        sla=SLAConfig(
            first_response_hours=2,  # Faster for students
            resolution_hours=24,
            escalation_hours=1
        ),
        compliance=ComplianceConfig(
            ferpa_enabled=True,
            coppa_enabled=False,
            gdpr_enabled=False,
            data_retention_days=365
        ),
        metadata={
            "website": "https://edulearn-academy.edu",
            "support_email": "support@edulearn-academy.edu",
            "billing_email": "billing@edulearn-academy.edu",
            "founded": 2015,
            "employees": 150,
            "student_count": 15000,
            "course_count": 500,
            "institution_type": "Online Education Platform",
            "accreditation": "DEAC Accredited",
            "programs": [
                "Business Administration",
                "Computer Science",
                "Data Science",
                "Digital Marketing",
                "Project Management"
            ],
            "features": {
                "live_classes": True,
                "self_paced_courses": True,
                "certificates": True,
                "career_services": True,
                "student_forum": True
            }
        }
    )


def load_config_from_file(filepath: str) -> ClientConfig:
    """Load config from JSON file.

    Args:
        filepath: Path to the JSON config file

    Returns:
        ClientConfig: The loaded configuration

    Raises:
        FileNotFoundError: If the config file doesn't exist
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")
    with open(path) as f:
        data = json.load(f)
    return ClientConfig(**data)
