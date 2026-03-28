"""
Data Governance Module

Provides data governance policies, classification, and compliance management
for multi-tenant environments.
"""

from typing import Dict, List, Optional, Any, Set, Callable
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import logging
import re

logger = logging.getLogger(__name__)


class DataClassification(str, Enum):
    """Data classification levels"""
    PUBLIC = "public"  # Publicly accessible
    INTERNAL = "internal"  # Internal use only
    CONFIDENTIAL = "confidential"  # Restricted access
    RESTRICTED = "restricted"  # Highly restricted
    PII = "pii"  # Personal identifiable information
    PHI = "phi"  # Protected health information
    FINANCIAL = "financial"  # Financial data


class GovernanceAction(str, Enum):
    """Actions for data governance"""
    ALLOW = "allow"
    DENY = "deny"
    MASK = "mask"
    REDACT = "redact"
    ENCRYPT = "encrypt"
    AUDIT = "audit"
    QUARANTINE = "quarantine"


class RetentionPolicy(str, Enum):
    """Data retention policies"""
    INDEFINITE = "indefinite"
    YEARS_7 = "7_years"  # Standard business
    YEARS_5 = "5_years"
    YEARS_3 = "3_years"
    YEARS_1 = "1_year"
    MONTHS_6 = "6_months"
    DAYS_90 = "90_days"
    DAYS_30 = "30_days"


@dataclass
class DataField:
    """Represents a data field with governance rules"""
    name: str
    classification: DataClassification
    description: str = ""
    is_encrypted: bool = False
    is_masked: bool = False
    mask_pattern: Optional[str] = None
    allowed_roles: List[str] = field(default_factory=list)
    retention_policy: RetentionPolicy = RetentionPolicy.INDEFINITE
    pii_type: Optional[str] = None  # e.g., "email", "ssn", "phone"
    compliance_tags: List[str] = field(default_factory=list)


@dataclass
class GovernancePolicy:
    """A data governance policy"""
    policy_id: str
    name: str
    description: str
    classification: DataClassification
    action: GovernanceAction
    conditions: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True


@dataclass
class GovernanceViolation:
    """A governance policy violation"""
    violation_id: str
    policy_id: str
    tenant_id: str
    field_name: str
    action_attempted: str
    classification: DataClassification
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False


class DataGovernance:
    """
    Manages data governance for multi-tenant environments.

    Features:
    - Data classification and labeling
    - Access policy management
    - Retention policy enforcement
    - Compliance monitoring
    - PII/PHI handling
    """

    def __init__(self):
        # Field registry
        self._field_registry: Dict[str, DataField] = {}

        # Policy registry
        self._policies: Dict[str, GovernancePolicy] = {}

        # Violation tracking
        self._violations: List[GovernanceViolation] = []

        # PII patterns
        self._pii_patterns = {
            "email": r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            "ssn": r'^\d{3}-\d{2}-\d{4}$',
            "phone": r'^\+?1?\d{9,15}$',
            "credit_card": r'^\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}$',
            "zip_code": r'^\d{5}(-\d{4})?$',
        }

        # Compliance frameworks
        self._compliance_frameworks: Dict[str, Dict[str, Any]] = {}

        # Initialize default policies
        self._initialize_default_policies()

    def _initialize_default_policies(self) -> None:
        """Initialize default governance policies"""
        default_policies = [
            GovernancePolicy(
                policy_id="policy_pii_access",
                name="PII Access Control",
                description="Restrict access to PII data",
                classification=DataClassification.PII,
                action=GovernanceAction.AUDIT,
                conditions={"require_role": ["admin", "data_processor"]}
            ),
            GovernancePolicy(
                policy_id="policy_phi_access",
                name="PHI Access Control",
                description="Strict access control for PHI data",
                classification=DataClassification.PHI,
                action=GovernanceAction.DENY,
                conditions={"require_role": ["admin", "healthcare_provider"], "require_baa": True}
            ),
            GovernancePolicy(
                policy_id="policy_financial_access",
                name="Financial Data Access",
                description="Control access to financial data",
                classification=DataClassification.FINANCIAL,
                action=GovernanceAction.AUDIT,
                conditions={"require_role": ["admin", "finance"]}
            ),
            GovernancePolicy(
                policy_id="policy_restricted_mask",
                name="Restricted Data Masking",
                description="Mask restricted data for non-privileged users",
                classification=DataClassification.RESTRICTED,
                action=GovernanceAction.MASK,
                conditions={"mask_for_roles": ["user", "viewer"]}
            )
        ]

        for policy in default_policies:
            self._policies[policy.policy_id] = policy

    def register_field(
        self,
        name: str,
        classification: DataClassification,
        description: str = "",
        pii_type: Optional[str] = None,
        retention_policy: RetentionPolicy = RetentionPolicy.INDEFINITE,
        compliance_tags: Optional[List[str]] = None
    ) -> DataField:
        """
        Register a data field with governance rules.

        Args:
            name: Field name
            classification: Data classification level
            description: Field description
            pii_type: Type of PII if applicable
            retention_policy: Retention policy for the field
            compliance_tags: Compliance framework tags

        Returns:
            Registered DataField
        """
        field = DataField(
            name=name,
            classification=classification,
            description=description,
            pii_type=pii_type,
            retention_policy=retention_policy,
            compliance_tags=compliance_tags or []
        )

        self._field_registry[name] = field
        logger.info(f"Registered field '{name}' with classification {classification.value}")

        return field

    def get_field(self, name: str) -> Optional[DataField]:
        """Get a registered field"""
        return self._field_registry.get(name)

    def classify_data(
        self,
        data: Dict[str, Any],
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        Classify data fields automatically.

        Args:
            data: Data to classify
            tenant_id: Tenant ID

        Returns:
            Classification results
        """
        results = {
            "tenant_id": tenant_id,
            "classified_at": datetime.utcnow().isoformat(),
            "fields": {},
            "pii_detected": [],
            "classification_summary": {}
        }

        classification_counts: Dict[str, int] = {}

        for field_name, value in data.items():
            if value is None:
                continue

            # Check if field is registered
            registered_field = self._field_registry.get(field_name)
            if registered_field:
                classification = registered_field.classification.value
                results["fields"][field_name] = {
                    "classification": classification,
                    "source": "registered",
                    "pii_type": registered_field.pii_type
                }
            else:
                # Auto-classify based on content
                auto_classification = self._auto_classify_value(value, field_name)
                results["fields"][field_name] = {
                    "classification": auto_classification.value,
                    "source": "auto"
                }
                classification = auto_classification.value

            classification_counts[classification] = classification_counts.get(classification, 0) + 1

            # Check for PII
            if results["fields"][field_name].get("pii_type"):
                results["pii_detected"].append(field_name)

        results["classification_summary"] = classification_counts

        return results

    def _auto_classify_value(self, value: Any, field_name: str) -> DataClassification:
        """Auto-classify a value based on content and field name"""
        value_str = str(value)
        field_lower = field_name.lower()

        # Check for PII patterns
        for pii_type, pattern in self._pii_patterns.items():
            if re.match(pattern, value_str):
                return DataClassification.PII

        # Check field name hints
        pii_hints = ["email", "phone", "ssn", "address", "name", "dob", "birth"]
        if any(hint in field_lower for hint in pii_hints):
            return DataClassification.PII

        financial_hints = ["credit", "card", "account", "bank", "payment", "amount"]
        if any(hint in field_lower for hint in financial_hints):
            return DataClassification.FINANCIAL

        health_hints = ["patient", "diagnosis", "treatment", "medical", "health"]
        if any(hint in field_lower for hint in health_hints):
            return DataClassification.PHI

        restricted_hints = ["password", "secret", "token", "key", "credential"]
        if any(hint in field_lower for hint in restricted_hints):
            return DataClassification.RESTRICTED

        confidential_hints = ["internal", "private", "confidential"]
        if any(hint in field_lower for hint in confidential_hints):
            return DataClassification.CONFIDENTIAL

        return DataClassification.INTERNAL

    def check_access(
        self,
        tenant_id: str,
        field_name: str,
        action: str,
        user_roles: List[str],
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Check if access to a field is allowed.

        Args:
            tenant_id: Tenant ID
            field_name: Field being accessed
            action: Action being performed
            user_roles: User's roles
            additional_context: Additional context for policy evaluation

        Returns:
            Access check result
        """
        result = {
            "allowed": True,
            "action": action,
            "field": field_name,
            "tenant_id": tenant_id,
            "policies_applied": [],
            "required_actions": []
        }

        field = self._field_registry.get(field_name)
        if not field:
            # No policy for unregistered fields
            return result

        # Find applicable policies
        applicable_policies = [
            p for p in self._policies.values()
            if p.is_active and p.classification == field.classification
        ]

        for policy in applicable_policies:
            policy_result = self._evaluate_policy(
                policy, field, action, user_roles, additional_context
            )
            result["policies_applied"].append({
                "policy_id": policy.policy_id,
                "action": policy.action.value,
                "result": policy_result
            })

            if not policy_result["allowed"]:
                result["allowed"] = False

            if policy_result.get("required_action"):
                result["required_actions"].append(policy_result["required_action"])

        return result

    def _evaluate_policy(
        self,
        policy: GovernancePolicy,
        field: DataField,
        action: str,
        user_roles: List[str],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Evaluate a policy for access"""
        result = {"allowed": True}

        conditions = policy.conditions

        # Check role requirements
        required_roles = conditions.get("require_role", [])
        if required_roles:
            if not any(role in user_roles for role in required_roles):
                result["allowed"] = False
                result["reason"] = f"Missing required role: {required_roles}"
                return result

        # Check BAA requirement for PHI
        if conditions.get("require_baa"):
            if not context or not context.get("has_baa"):
                result["allowed"] = False
                result["reason"] = "BAA required for PHI access"
                return result

        # Handle action-specific logic
        if policy.action == GovernanceAction.DENY:
            result["allowed"] = False
            result["required_action"] = "deny"
        elif policy.action == GovernanceAction.MASK:
            mask_roles = conditions.get("mask_for_roles", [])
            if any(role in mask_roles for role in user_roles):
                result["allowed"] = True
                result["required_action"] = "mask"
        elif policy.action == GovernanceAction.AUDIT:
            result["allowed"] = True
            result["required_action"] = "audit"

        return result

    def mask_value(
        self,
        value: Any,
        pii_type: Optional[str] = None
    ) -> str:
        """
        Mask a value based on its PII type.

        Args:
            value: Value to mask
            pii_type: Type of PII

        Returns:
            Masked value
        """
        if value is None:
            return ""

        value_str = str(value)

        if pii_type == "email":
            parts = value_str.split("@")
            if len(parts) == 2:
                return f"{parts[0][:2]}***@{parts[1]}"

        if pii_type == "ssn":
            return f"***-**-{value_str[-4:]}" if len(value_str) >= 4 else "***-**-****"

        if pii_type == "phone":
            return f"***-***-{value_str[-4:]}" if len(value_str) >= 4 else "***-***-****"

        if pii_type == "credit_card":
            return f"****-****-****-{value_str[-4:]}" if len(value_str) >= 4 else "****-****-****-****"

        # Default masking
        if len(value_str) <= 4:
            return "*" * len(value_str)
        return value_str[:2] + "*" * (len(value_str) - 4) + value_str[-2:]

    def apply_retention_policy(
        self,
        tenant_id: str,
        field_name: str,
        created_at: datetime
    ) -> Dict[str, Any]:
        """
        Check if data should be retained or deleted based on policy.

        Args:
            tenant_id: Tenant ID
            field_name: Field name
            created_at: When the data was created

        Returns:
            Retention status
        """
        field = self._field_registry.get(field_name)
        if not field:
            return {"retain": True, "policy": "none"}

        now = datetime.utcnow()
        age_days = (now - created_at).days

        retention_days = {
            RetentionPolicy.DAYS_30: 30,
            RetentionPolicy.DAYS_90: 90,
            RetentionPolicy.MONTHS_6: 180,
            RetentionPolicy.YEARS_1: 365,
            RetentionPolicy.YEARS_3: 1095,
            RetentionPolicy.YEARS_5: 1825,
            RetentionPolicy.YEARS_7: 2555,
        }

        policy_days = retention_days.get(field.retention_policy)
        if policy_days is None:
            return {"retain": True, "policy": field.retention_policy.value}

        should_retain = age_days < policy_days

        return {
            "retain": should_retain,
            "policy": field.retention_policy.value,
            "age_days": age_days,
            "retention_days": policy_days,
            "days_until_expiry": max(0, policy_days - age_days)
        }

    def create_policy(
        self,
        name: str,
        description: str,
        classification: DataClassification,
        action: GovernanceAction,
        conditions: Optional[Dict[str, Any]] = None
    ) -> GovernancePolicy:
        """Create a new governance policy"""
        policy_id = f"policy_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        policy = GovernancePolicy(
            policy_id=policy_id,
            name=name,
            description=description,
            classification=classification,
            action=action,
            conditions=conditions or {}
        )

        self._policies[policy_id] = policy
        logger.info(f"Created policy '{name}' for classification {classification.value}")

        return policy

    def get_policy(self, policy_id: str) -> Optional[GovernancePolicy]:
        """Get a policy by ID"""
        return self._policies.get(policy_id)

    def list_policies(
        self,
        classification: Optional[DataClassification] = None,
        active_only: bool = True
    ) -> List[GovernancePolicy]:
        """List policies, optionally filtered"""
        policies = list(self._policies.values())

        if classification:
            policies = [p for p in policies if p.classification == classification]

        if active_only:
            policies = [p for p in policies if p.is_active]

        return policies

    def record_violation(
        self,
        policy_id: str,
        tenant_id: str,
        field_name: str,
        action_attempted: str,
        details: Optional[Dict[str, Any]] = None
    ) -> GovernanceViolation:
        """Record a governance violation"""
        policy = self._policies.get(policy_id)
        if not policy:
            raise ValueError(f"Policy {policy_id} not found")

        violation_id = f"viol_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{len(self._violations)}"

        violation = GovernanceViolation(
            violation_id=violation_id,
            policy_id=policy_id,
            tenant_id=tenant_id,
            field_name=field_name,
            action_attempted=action_attempted,
            classification=policy.classification,
            details=details or {}
        )

        self._violations.append(violation)
        logger.warning(
            f"Governance violation: policy={policy_id}, tenant={tenant_id}, "
            f"field={field_name}, action={action_attempted}"
        )

        return violation

    def get_violations(
        self,
        tenant_id: Optional[str] = None,
        policy_id: Optional[str] = None,
        unresolved_only: bool = False
    ) -> List[GovernanceViolation]:
        """Get violations, optionally filtered"""
        violations = self._violations

        if tenant_id:
            violations = [v for v in violations if v.tenant_id == tenant_id]

        if policy_id:
            violations = [v for v in violations if v.policy_id == policy_id]

        if unresolved_only:
            violations = [v for v in violations if not v.resolved]

        return violations

    def register_compliance_framework(
        self,
        name: str,
        requirements: Dict[str, Any]
    ) -> None:
        """Register a compliance framework"""
        self._compliance_frameworks[name] = {
            "name": name,
            "requirements": requirements,
            "registered_at": datetime.utcnow().isoformat()
        }
        logger.info(f"Registered compliance framework: {name}")

    def check_compliance(
        self,
        tenant_id: str,
        framework: str
    ) -> Dict[str, Any]:
        """Check compliance with a framework"""
        if framework not in self._compliance_frameworks:
            return {"error": f"Framework {framework} not found"}

        framework_data = self._compliance_frameworks[framework]
        requirements = framework_data["requirements"]

        results = {
            "tenant_id": tenant_id,
            "framework": framework,
            "checked_at": datetime.utcnow().isoformat(),
            "compliant": True,
            "requirements_checked": [],
            "issues": []
        }

        for req_name, req_config in requirements.items():
            req_result = self._check_requirement(tenant_id, req_name, req_config)
            results["requirements_checked"].append(req_result)

            if not req_result["met"]:
                results["compliant"] = False
                results["issues"].append(req_result["issue"])

        return results

    def _check_requirement(
        self,
        tenant_id: str,
        req_name: str,
        req_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check a single requirement"""
        # Simplified requirement check
        return {
            "requirement": req_name,
            "met": True,
            "details": req_config
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Get governance metrics"""
        return {
            "total_fields": len(self._field_registry),
            "fields_by_classification": self._count_by_classification(),
            "total_policies": len(self._policies),
            "active_policies": len([p for p in self._policies.values() if p.is_active]),
            "total_violations": len(self._violations),
            "unresolved_violations": len([v for v in self._violations if not v.resolved]),
            "compliance_frameworks": len(self._compliance_frameworks)
        }

    def _count_by_classification(self) -> Dict[str, int]:
        """Count fields by classification"""
        counts: Dict[str, int] = {}
        for field in self._field_registry.values():
            key = field.classification.value
            counts[key] = counts.get(key, 0) + 1
        return counts
