"""
PARWA Compliance Module.

Provides comprehensive compliance functionality for customer data handling
including jurisdiction-based rules, SLA management, GDPR compliance, and
healthcare-specific protections.

Components:
- JurisdictionManager: Jurisdiction-based compliance rules (TCPA, GDPR, etc.)
- SLACalculator: SLA breach detection and calculation
- GDPREngine: GDPR data export and erasure
- HealthcareGuard: HIPAA compliance and PHI protection
"""
from shared.compliance.jurisdiction import (
    JurisdictionManager,
    JurisdictionCode,
    JurisdictionRules,
    JurisdictionResult,
    ConsentType,
    CommunicationType,
    TimeWindow,
    get_jurisdiction_manager,
)
from shared.compliance.sla_calculator import (
    SLACalculator,
    SLATier,
    SLAType,
    SLABreachStatus,
    SLAPolicy,
    SLAResult,
    SLASummary,
    get_sla_calculator,
)
from shared.compliance.gdpr_engine import (
    GDPREngine,
    GDPRRequestType,
    GDPRRequestStatus,
    GDPRRequest,
    DataExport,
    ErasureResult,
    PIIFieldType,
    DataCategory,
    GDPREngineConfig,
    get_gdpr_engine,
)
from shared.compliance.healthcare_guard import (
    HealthcareGuard,
    BAAStatus,
    BAARecord,
    PHIType,
    PHICheckResult,
    AccessPurpose,
    HealthcareClientType,
    HealthcareGuardConfig,
    get_healthcare_guard,
)


__all__ = [
    # Jurisdiction
    "JurisdictionManager",
    "JurisdictionCode",
    "JurisdictionRules",
    "JurisdictionResult",
    "ConsentType",
    "CommunicationType",
    "TimeWindow",
    "get_jurisdiction_manager",
    # SLA
    "SLACalculator",
    "SLATier",
    "SLAType",
    "SLABreachStatus",
    "SLAPolicy",
    "SLAResult",
    "SLASummary",
    "get_sla_calculator",
    # GDPR
    "GDPREngine",
    "GDPRRequestType",
    "GDPRRequestStatus",
    "GDPRRequest",
    "DataExport",
    "ErasureResult",
    "PIIFieldType",
    "DataCategory",
    "GDPREngineConfig",
    "get_gdpr_engine",
    # Healthcare
    "HealthcareGuard",
    "BAAStatus",
    "BAARecord",
    "PHIType",
    "PHICheckResult",
    "AccessPurpose",
    "HealthcareClientType",
    "HealthcareGuardConfig",
    "get_healthcare_guard",
]
