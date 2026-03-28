# Compliance Rules - Week 49 Builder 2
# Compliance rule engine for automated checks

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import uuid


class RuleSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RuleStatus(Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    DEPRECATED = "deprecated"


class RuleType(Enum):
    ACCESS_CONTROL = "access_control"
    DATA_PROTECTION = "data_protection"
    RETENTION = "retention"
    ENCRYPTION = "encryption"
    AUDIT = "audit"
    CONSENT = "consent"
    BREACH_DETECTION = "breach_detection"


@dataclass
class ComplianceRule:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    description: str = ""
    rule_type: RuleType = RuleType.ACCESS_CONTROL
    severity: RuleSeverity = RuleSeverity.MEDIUM
    status: RuleStatus = RuleStatus.ENABLED
    framework: str = ""
    requirement_id: str = ""
    condition: Dict[str, Any] = field(default_factory=dict)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    exceptions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_evaluated: Optional[datetime] = None
    evaluation_count: int = 0


@dataclass
class RuleEvaluationResult:
    rule_id: str = ""
    passed: bool = False
    score: float = 0.0
    findings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    evaluated_at: datetime = field(default_factory=datetime.utcnow)


class ComplianceRuleEngine:
    """Rule engine for compliance checks"""

    def __init__(self):
        self._rules: Dict[str, ComplianceRule] = {}
        self._rules_by_type: Dict[RuleType, List[str]] = {rt: [] for rt in RuleType}
        self._evaluation_handlers: Dict[str, Callable] = {}
        self._metrics = {
            "total_rules": 0,
            "total_evaluations": 0,
            "passed_evaluations": 0,
            "failed_evaluations": 0
        }

    def create_rule(
        self,
        tenant_id: str,
        name: str,
        rule_type: RuleType,
        severity: RuleSeverity = RuleSeverity.MEDIUM,
        description: str = "",
        framework: str = "",
        requirement_id: str = "",
        condition: Optional[Dict[str, Any]] = None,
        actions: Optional[List[Dict[str, Any]]] = None
    ) -> ComplianceRule:
        """Create a new compliance rule"""
        rule = ComplianceRule(
            tenant_id=tenant_id,
            name=name,
            description=description,
            rule_type=rule_type,
            severity=severity,
            framework=framework,
            requirement_id=requirement_id,
            condition=condition or {},
            actions=actions or []
        )

        self._rules[rule.id] = rule
        self._rules_by_type[rule_type].append(rule.id)
        self._metrics["total_rules"] += 1

        return rule

    def register_evaluation_handler(
        self,
        rule_type: RuleType,
        handler: Callable
    ) -> None:
        """Register a handler for rule evaluation"""
        self._evaluation_handlers[rule_type.value] = handler

    def evaluate_rule(
        self,
        rule_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[RuleEvaluationResult]:
        """Evaluate a single rule"""
        rule = self._rules.get(rule_id)
        if not rule or rule.status != RuleStatus.ENABLED:
            return None

        result = RuleEvaluationResult(rule_id=rule.id)
        context = context or {}

        # Get handler for rule type
        handler = self._evaluation_handlers.get(rule.rule_type.value)

        if handler:
            try:
                handler_result = handler(rule, context)
                result.passed = handler_result.get("passed", False)
                result.score = handler_result.get("score", 0.0)
                result.findings = handler_result.get("findings", [])
                result.recommendations = handler_result.get("recommendations", [])
            except Exception as e:
                result.passed = False
                result.findings.append(f"Evaluation error: {str(e)}")
        else:
            # Default evaluation logic
            result.passed = self._default_evaluate(rule, context)

        # Update rule stats
        rule.last_evaluated = datetime.utcnow()
        rule.evaluation_count += 1

        # Update metrics
        self._metrics["total_evaluations"] += 1
        if result.passed:
            self._metrics["passed_evaluations"] += 1
        else:
            self._metrics["failed_evaluations"] += 1

        return result

    def _default_evaluate(
        self,
        rule: ComplianceRule,
        context: Dict[str, Any]
    ) -> bool:
        """Default evaluation logic"""
        # Simple condition checking
        condition = rule.condition

        for key, expected_value in condition.items():
            actual_value = context.get(key)
            if actual_value != expected_value:
                return False

        return True

    def evaluate_all_rules(
        self,
        tenant_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[RuleEvaluationResult]:
        """Evaluate all rules for a tenant"""
        results = []
        for rule in self._rules.values():
            if rule.tenant_id == tenant_id and rule.status == RuleStatus.ENABLED:
                result = self.evaluate_rule(rule.id, context)
                if result:
                    results.append(result)
        return results

    def evaluate_rules_by_type(
        self,
        tenant_id: str,
        rule_type: RuleType,
        context: Optional[Dict[str, Any]] = None
    ) -> List[RuleEvaluationResult]:
        """Evaluate rules of a specific type"""
        results = []
        rule_ids = self._rules_by_type.get(rule_type, [])

        for rule_id in rule_ids:
            rule = self._rules.get(rule_id)
            if rule and rule.tenant_id == tenant_id:
                result = self.evaluate_rule(rule_id, context)
                if result:
                    results.append(result)

        return results

    def get_rule(self, rule_id: str) -> Optional[ComplianceRule]:
        """Get a rule by ID"""
        return self._rules.get(rule_id)

    def get_rules_by_tenant(
        self,
        tenant_id: str,
        rule_type: Optional[RuleType] = None
    ) -> List[ComplianceRule]:
        """Get all rules for a tenant"""
        rules = [r for r in self._rules.values() if r.tenant_id == tenant_id]
        if rule_type:
            rules = [r for r in rules if r.rule_type == rule_type]
        return rules

    def update_rule(
        self,
        rule_id: str,
        **kwargs
    ) -> Optional[ComplianceRule]:
        """Update a rule"""
        rule = self._rules.get(rule_id)
        if not rule:
            return None

        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)

        rule.updated_at = datetime.utcnow()
        return rule

    def enable_rule(self, rule_id: str) -> bool:
        """Enable a rule"""
        rule = self._rules.get(rule_id)
        if not rule:
            return False
        rule.status = RuleStatus.ENABLED
        rule.updated_at = datetime.utcnow()
        return True

    def disable_rule(self, rule_id: str) -> bool:
        """Disable a rule"""
        rule = self._rules.get(rule_id)
        if not rule:
            return False
        rule.status = RuleStatus.DISABLED
        rule.updated_at = datetime.utcnow()
        return True

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule"""
        rule = self._rules.get(rule_id)
        if not rule:
            return False

        # Remove from type index
        if rule.rule_type in self._rules_by_type:
            self._rules_by_type[rule.rule_type] = [
                rid for rid in self._rules_by_type[rule.rule_type]
                if rid != rule_id
            ]

        del self._rules[rule_id]
        self._metrics["total_rules"] -= 1
        return True

    def add_exception(
        self,
        rule_id: str,
        exception: str
    ) -> bool:
        """Add an exception to a rule"""
        rule = self._rules.get(rule_id)
        if not rule:
            return False
        if exception not in rule.exceptions:
            rule.exceptions.append(exception)
            rule.updated_at = datetime.utcnow()
        return True

    def remove_exception(
        self,
        rule_id: str,
        exception: str
    ) -> bool:
        """Remove an exception from a rule"""
        rule = self._rules.get(rule_id)
        if not rule:
            return False
        if exception in rule.exceptions:
            rule.exceptions.remove(exception)
            rule.updated_at = datetime.utcnow()
        return True

    def get_compliance_score(
        self,
        tenant_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Calculate overall compliance score"""
        results = self.evaluate_all_rules(tenant_id, context)

        if not results:
            return {"score": 100.0, "passed": 0, "failed": 0, "total": 0}

        passed = len([r for r in results if r.passed])
        failed = len([r for r in results if not r.passed])
        total = len(results)
        score = (passed / total) * 100 if total > 0 else 100.0

        return {
            "score": round(score, 2),
            "passed": passed,
            "failed": failed,
            "total": total
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Get rule engine metrics"""
        return {
            **self._metrics,
            "rules_by_type": {
                rt.value: len(ids) for rt, ids in self._rules_by_type.items()
            }
        }
