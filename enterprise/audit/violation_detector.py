# Violation Detector - Week 49 Builder 5
# Compliance violation detection

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class ViolationType(Enum):
    ACCESS_VIOLATION = "access"
    DATA_VIOLATION = "data"
    POLICY_VIOLATION = "policy"
    SECURITY_VIOLATION = "security"


class ViolationSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Violation:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    type: ViolationType = ViolationType.POLICY_VIOLATION
    severity: ViolationSeverity = ViolationSeverity.MEDIUM
    description: str = ""
    source: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    detected_at: datetime = field(default_factory=datetime.utcnow)


class ViolationDetector:
    """Detects compliance violations"""

    def __init__(self):
        self._violations: List[Violation] = []
        self._rules: Dict[str, Any] = {}
        self._metrics = {
            "total_violations": 0,
            "resolved_violations": 0,
            "by_severity": {},
            "by_type": {}
        }

    def add_rule(self, rule_id: str, rule: Any) -> None:
        """Add a detection rule"""
        self._rules[rule_id] = rule

    def detect(
        self,
        tenant_id: str,
        type: ViolationType,
        severity: ViolationSeverity,
        description: str,
        source: str = "",
        details: Optional[Dict[str, Any]] = None
    ) -> Violation:
        """Record a detected violation"""
        violation = Violation(
            tenant_id=tenant_id,
            type=type,
            severity=severity,
            description=description,
            source=source,
            details=details or {}
        )

        self._violations.append(violation)
        self._metrics["total_violations"] += 1

        sev_key = severity.value
        self._metrics["by_severity"][sev_key] = self._metrics["by_severity"].get(sev_key, 0) + 1

        type_key = type.value
        self._metrics["by_type"][type_key] = self._metrics["by_type"].get(type_key, 0) + 1

        return violation

    def resolve_violation(self, violation_id: str) -> bool:
        """Mark a violation as resolved"""
        for v in self._violations:
            if v.id == violation_id:
                v.resolved = True
                v.resolved_at = datetime.utcnow()
                self._metrics["resolved_violations"] += 1
                return True
        return False

    def get_violations_by_tenant(
        self,
        tenant_id: str,
        resolved: Optional[bool] = None
    ) -> List[Violation]:
        """Get violations for a tenant"""
        violations = [v for v in self._violations if v.tenant_id == tenant_id]
        if resolved is not None:
            violations = [v for v in violations if v.resolved == resolved]
        return violations

    def get_critical_violations(self, tenant_id: str) -> List[Violation]:
        """Get all critical unresolved violations"""
        return [
            v for v in self._violations
            if v.tenant_id == tenant_id
            and v.severity == ViolationSeverity.CRITICAL
            and not v.resolved
        ]

    def get_metrics(self) -> Dict[str, Any]:
        return self._metrics.copy()
