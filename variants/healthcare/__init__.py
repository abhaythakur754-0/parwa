"""
Healthcare Variant for PARWA.

HIPAA-compliant healthcare support automation with:
- PHI Detection & Sanitization
- HIPAA Compliance Automation
- BAA Management
- Medical Knowledge Base
- EHR Integration
"""

from variants.healthcare.phi_handler import (
    PHIHandler,
    PHIType,
    PHIDetectionResult,
    SanitizationMethod,
)
from variants.healthcare.hipaa_compliance import (
    HIPAAComplianceManager,
    ComplianceStatus,
    ComplianceCheck,
)
from variants.healthcare.baa_manager import (
    BAAManager,
    BAAStatus,
    BAARecord,
)
from variants.healthcare.medical_kb import (
    MedicalKnowledgeBase,
    MedicalTermCategory,
)
from variants.healthcare.ehr_integration import (
    EHRIntegration,
    EHRProvider,
)

__all__ = [
    # PHI Handler
    'PHIHandler',
    'PHIType',
    'PHIDetectionResult',
    'SanitizationMethod',
    # HIPAA Compliance
    'HIPAAComplianceManager',
    'ComplianceStatus',
    'ComplianceCheck',
    # BAA Manager
    'BAAManager',
    'BAAStatus',
    'BAARecord',
    # Medical KB
    'MedicalKnowledgeBase',
    'MedicalTermCategory',
    # EHR Integration
    'EHRIntegration',
    'EHRProvider',
]
