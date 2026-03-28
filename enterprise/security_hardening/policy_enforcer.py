"""
Policy Enforcement Engine for Week 54 Advanced Security Hardening.

This module provides a comprehensive policy enforcement engine that evaluates
policies against requests and takes appropriate enforcement actions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any, Callable, Set
from datetime import datetime
import re


class EnforcementAction(Enum):
    """Actions that can be taken when a policy is evaluated."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    MODIFY = "MODIFY"
    ALERT = "ALERT"
    LOG = "LOG"
    QUARANTINE = "QUARANTINE"


class PolicyEffect(Enum):
    """Effect of a policy rule."""
    ALLOW = "ALLOW"
    DENY = "DENY"


class ConditionOperator(Enum):
    """Operators for condition evaluation."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    MATCHES = "matches"  # regex
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"


@dataclass
class Condition:
    """
    Represents a condition in a policy rule.
    
    Attributes:
        field: Field to check in the context
        operator: Comparison operator
        value: Value to compare against
    """
    field: str
    operator: ConditionOperator
    value: Any
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate the condition against a context."""
        field_value = self._get_field_value(context)
        
        if field_value is None:
            return False
        
        if self.operator == ConditionOperator.EQUALS:
            return field_value == self.value
        elif self.operator == ConditionOperator.NOT_EQUALS:
            return field_value != self.value
        elif self.operator == ConditionOperator.IN:
            return field_value in self.value
        elif self.operator == ConditionOperator.NOT_IN:
            return field_value not in self.value
        elif self.operator == ConditionOperator.CONTAINS:
            return self.value in field_value
        elif self.operator == ConditionOperator.NOT_CONTAINS:
            return self.value not in field_value
        elif self.operator == ConditionOperator.STARTS_WITH:
            return str(field_value).startswith(self.value)
        elif self.operator == ConditionOperator.ENDS_WITH:
            return str(field_value).endswith(self.value)
        elif self.operator == ConditionOperator.MATCHES:
            return bool(re.match(self.value, str(field_value)))
        elif self.operator == ConditionOperator.GREATER_THAN:
            return field_value > self.value
        elif self.operator == ConditionOperator.LESS_THAN:
            return field_value < self.value
        elif self.operator == ConditionOperator.GREATER_THAN_OR_EQUAL:
            return field_value >= self.value
        elif self.operator == ConditionOperator.LESS_THAN_OR_EQUAL:
            return field_value <= self.value
        
        return False
    
    def _get_field_value(self, context: Dict[str, Any]) -> Any:
        """Get field value from nested context using dot notation."""
        keys = self.field.split(".")
        value = context
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
            
            if value is None:
                return None
        
        return value


@dataclass
class PolicyRule:
    """
    Represents a single policy rule.
    
    Attributes:
        rule_id: Unique identifier for the rule
        name: Human-readable name
        description: Description of what the rule does
        effect: Whether this rule allows or denies
        conditions: List of conditions that must all be true
        actions: Actions to take when rule matches
        priority: Priority of the rule (higher = more important)
        enabled: Whether the rule is active
    """
    rule_id: str
    name: str
    description: str = ""
    effect: PolicyEffect = PolicyEffect.DENY
    conditions: List[Condition] = field(default_factory=list)
    actions: List[EnforcementAction] = field(default_factory=list)
    priority: int = 100
    enabled: bool = True
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate if all conditions match."""
        return all(condition.evaluate(context) for condition in self.conditions)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert rule to dictionary."""
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "effect": self.effect.value,
            "conditions": [
                {"field": c.field, "operator": c.operator.value, "value": c.value}
                for c in self.conditions
            ],
            "actions": [a.value for a in self.actions],
            "priority": self.priority,
            "enabled": self.enabled
        }


@dataclass
class Policy:
    """
    Represents a complete policy with multiple rules.
    
    Attributes:
        policy_id: Unique identifier for the policy
        name: Human-readable name
        description: Description of the policy
        rules: List of policy rules
        default_effect: Default effect if no rules match
        created_at: When the policy was created
        updated_at: When the policy was last updated
        tags: Tags for categorization
    """
    policy_id: str
    name: str
    description: str = ""
    rules: List[PolicyRule] = field(default_factory=list)
    default_effect: PolicyEffect = PolicyEffect.DENY
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    tags: Set[str] = field(default_factory=set)
    
    def add_rule(self, rule: PolicyRule) -> None:
        """Add a rule to the policy."""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
        self.updated_at = datetime.utcnow()
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule from the policy."""
        for i, rule in enumerate(self.rules):
            if rule.rule_id == rule_id:
                self.rules.pop(i)
                self.updated_at = datetime.utcnow()
                return True
        return False
    
    def get_rule(self, rule_id: str) -> Optional[PolicyRule]:
        """Get a rule by ID."""
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert policy to dictionary."""
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "rules": [r.to_dict() for r in self.rules],
            "default_effect": self.default_effect.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tags": list(self.tags)
        }


@dataclass
class PolicyViolation:
    """
    Represents a policy violation.
    
    Attributes:
        violation_id: Unique identifier
        policy_id: ID of the violated policy
        rule_id: ID of the violated rule
        context: Context when violation occurred
        timestamp: When the violation occurred
        severity: Severity of the violation
        message: Human-readable message
    """
    violation_id: str
    policy_id: str
    rule_id: str
    context: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    severity: str = "HIGH"
    message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert violation to dictionary."""
        return {
            "violation_id": self.violation_id,
            "policy_id": self.policy_id,
            "rule_id": self.rule_id,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity,
            "message": self.message
        }


@dataclass
class EnforcementResult:
    """
    Result of policy enforcement.
    
    Attributes:
        allowed: Whether the action was allowed
        effect: The effect that was applied
        actions: Actions that were taken
        matched_rules: Rules that matched
        violations: Violations that occurred
        modifications: Modifications made to the request
        timestamp: When enforcement occurred
    """
    allowed: bool
    effect: PolicyEffect
    actions: List[EnforcementAction] = field(default_factory=list)
    matched_rules: List[PolicyRule] = field(default_factory=list)
    violations: List[PolicyViolation] = field(default_factory=list)
    modifications: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "allowed": self.allowed,
            "effect": self.effect.value,
            "actions": [a.value for a in self.actions],
            "matched_rules": [r.rule_id for r in self.matched_rules],
            "violations": [v.to_dict() for v in self.violations],
            "modifications": self.modifications,
            "timestamp": self.timestamp.isoformat()
        }


class PolicyEnforcer:
    """
    Main policy enforcement engine.
    
    Manages policies, evaluates requests against policies, and tracks violations.
    """
    
    def __init__(self):
        """Initialize the policy enforcer."""
        self.policies: Dict[str, Policy] = {}
        self.violations: List[PolicyViolation] = []
        self._violation_counter = 0
        self._initialize_default_policies()
    
    def _initialize_default_policies(self) -> None:
        """Initialize default security policies."""
        # Data access policy
        data_policy = Policy(
            policy_id="POLICY-DATA-001",
            name="Data Access Control",
            description="Controls access to sensitive data",
            tags={"security", "data", "access"}
        )
        
        data_policy.add_rule(PolicyRule(
            rule_id="RULE-DATA-001",
            name="Prevent unauthorized data access",
            description="Deny access to sensitive data for unauthorized users",
            effect=PolicyEffect.DENY,
            conditions=[
                Condition(
                    field="resource.sensitivity",
                    operator=ConditionOperator.IN,
                    value=["HIGH", "CRITICAL"]
                ),
                Condition(
                    field="user.role",
                    operator=ConditionOperator.NOT_IN,
                    value=["admin", "data_steward", "security_analyst"]
                )
            ],
            actions=[EnforcementAction.DENY, EnforcementAction.ALERT],
            priority=100
        ))
        
        data_policy.add_rule(PolicyRule(
            rule_id="RULE-DATA-002",
            name="Allow read access for analysts",
            description="Allow read-only access for data analysts",
            effect=PolicyEffect.ALLOW,
            conditions=[
                Condition(
                    field="resource.sensitivity",
                    operator=ConditionOperator.EQUALS,
                    value="MEDIUM"
                ),
                Condition(
                    field="user.role",
                    operator=ConditionOperator.EQUALS,
                    value="analyst"
                ),
                Condition(
                    field="action",
                    operator=ConditionOperator.EQUALS,
                    value="READ"
                )
            ],
            actions=[EnforcementAction.ALLOW, EnforcementAction.LOG],
            priority=90
        ))
        
        self.add_policy(data_policy)
        
        # API rate limiting policy
        rate_policy = Policy(
            policy_id="POLICY-RATE-001",
            name="API Rate Limiting",
            description="Enforces rate limits on API calls",
            tags={"security", "api", "rate-limiting"}
        )
        
        rate_policy.add_rule(PolicyRule(
            rule_id="RULE-RATE-001",
            name="Enforce rate limit",
            description="Deny requests exceeding rate limit",
            effect=PolicyEffect.DENY,
            conditions=[
                Condition(
                    field="request.rate",
                    operator=ConditionOperator.GREATER_THAN,
                    value=1000
                )
            ],
            actions=[EnforcementAction.DENY, EnforcementAction.ALERT],
            priority=100
        ))
        
        self.add_policy(rate_policy)
        
        # Time-based access policy
        time_policy = Policy(
            policy_id="POLICY-TIME-001",
            name="Time-Based Access",
            description="Restricts access based on time",
            tags={"security", "time", "access"}
        )
        
        time_policy.add_rule(PolicyRule(
            rule_id="RULE-TIME-001",
            name="Deny access outside business hours",
            description="Deny sensitive operations outside business hours",
            effect=PolicyEffect.DENY,
            conditions=[
                Condition(
                    field="resource.sensitivity",
                    operator=ConditionOperator.IN,
                    value=["HIGH", "CRITICAL"]
                ),
                Condition(
                    field="context.is_business_hours",
                    operator=ConditionOperator.EQUALS,
                    value=False
                )
            ],
            actions=[EnforcementAction.DENY, EnforcementAction.ALERT],
            priority=80
        ))
        
        self.add_policy(time_policy)
    
    def add_policy(self, policy: Policy) -> None:
        """Add a policy to the enforcer."""
        self.policies[policy.policy_id] = policy
    
    def remove_policy(self, policy_id: str) -> bool:
        """Remove a policy from the enforcer."""
        if policy_id in self.policies:
            del self.policies[policy_id]
            return True
        return False
    
    def get_policy(self, policy_id: str) -> Optional[Policy]:
        """Get a policy by ID."""
        return self.policies.get(policy_id)
    
    def enforce(
        self,
        context: Dict[str, Any],
        policy_ids: Optional[List[str]] = None
    ) -> EnforcementResult:
        """
        Enforce policies against a request context.
        
        Args:
            context: The request context to evaluate
            policy_ids: Optional list of specific policies to check
            
        Returns:
            EnforcementResult with the enforcement decision
        """
        policies_to_check = (
            [self.policies[pid] for pid in policy_ids if pid in self.policies]
            if policy_ids
            else list(self.policies.values())
        )
        
        matched_rules: List[PolicyRule] = []
        violations: List[PolicyViolation] = []
        actions: List[EnforcementAction] = []
        modifications: Dict[str, Any] = {}
        final_effect = None
        
        for policy in policies_to_check:
            for rule in policy.rules:
                if not rule.enabled:
                    continue
                
                if rule.evaluate(context):
                    matched_rules.append(rule)
                    
                    if rule.effect == PolicyEffect.DENY:
                        # Create violation record
                        violation = self._create_violation(
                            policy.policy_id,
                            rule.rule_id,
                            context
                        )
                        violations.append(violation)
                        
                        # DENY takes precedence
                        if final_effect is None or final_effect == PolicyEffect.ALLOW:
                            final_effect = PolicyEffect.DENY
                            actions = rule.actions.copy()
                    
                    elif rule.effect == PolicyEffect.ALLOW:
                        # ALLOW only if no DENY has been found
                        if final_effect is None or final_effect == PolicyEffect.ALLOW:
                            final_effect = PolicyEffect.ALLOW
                            actions = rule.actions.copy()
        
        # Apply default effect if no rules matched
        if final_effect is None:
            # Check default effects from policies
            has_deny_default = any(
                p.default_effect == PolicyEffect.DENY
                for p in policies_to_check
            )
            final_effect = PolicyEffect.DENY if has_deny_default else PolicyEffect.ALLOW
        
        allowed = final_effect == PolicyEffect.ALLOW
        
        # Store violations
        self.violations.extend(violations)
        
        return EnforcementResult(
            allowed=allowed,
            effect=final_effect,
            actions=actions,
            matched_rules=matched_rules,
            violations=violations,
            modifications=modifications
        )
    
    def _create_violation(
        self,
        policy_id: str,
        rule_id: str,
        context: Dict[str, Any]
    ) -> PolicyViolation:
        """Create a policy violation record."""
        self._violation_counter += 1
        violation_id = f"VIOL-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{self._violation_counter:06d}"
        
        return PolicyViolation(
            violation_id=violation_id,
            policy_id=policy_id,
            rule_id=rule_id,
            context=context,
            severity="HIGH",
            message=f"Policy violation: {policy_id}/{rule_id}"
        )
    
    def get_violations(
        self,
        policy_id: Optional[str] = None,
        rule_id: Optional[str] = None,
        limit: int = 100
    ) -> List[PolicyViolation]:
        """
        Get policy violations.
        
        Args:
            policy_id: Filter by policy ID
            rule_id: Filter by rule ID
            limit: Maximum number of violations to return
            
        Returns:
            List of violations
        """
        violations = self.violations.copy()
        
        if policy_id:
            violations = [v for v in violations if v.policy_id == policy_id]
        if rule_id:
            violations = [v for v in violations if v.rule_id == rule_id]
        
        violations.sort(key=lambda v: v.timestamp, reverse=True)
        return violations[:limit]
    
    def clear_violations(self) -> int:
        """Clear all stored violations."""
        count = len(self.violations)
        self.violations.clear()
        return count
    
    def get_violation_count(self) -> int:
        """Get total number of violations."""
        return len(self.violations)
    
    def get_violation_statistics(self) -> Dict[str, Any]:
        """Get statistics about policy violations."""
        if not self.violations:
            return {
                "total": 0,
                "by_policy": {},
                "by_rule": {}
            }
        
        by_policy: Dict[str, int] = {}
        by_rule: Dict[str, int] = {}
        
        for violation in self.violations:
            by_policy[violation.policy_id] = by_policy.get(violation.policy_id, 0) + 1
            by_rule[violation.rule_id] = by_rule.get(violation.rule_id, 0) + 1
        
        return {
            "total": len(self.violations),
            "by_policy": by_policy,
            "by_rule": by_rule
        }
    
    def create_policy_from_dict(self, data: Dict[str, Any]) -> Policy:
        """
        Create a policy from a dictionary representation.
        
        Args:
            data: Dictionary containing policy data
            
        Returns:
            Created Policy object
        """
        policy = Policy(
            policy_id=data["policy_id"],
            name=data["name"],
            description=data.get("description", ""),
            default_effect=PolicyEffect(data.get("default_effect", "DENY")),
            tags=set(data.get("tags", []))
        )
        
        for rule_data in data.get("rules", []):
            rule = PolicyRule(
                rule_id=rule_data["rule_id"],
                name=rule_data["name"],
                description=rule_data.get("description", ""),
                effect=PolicyEffect(rule_data.get("effect", "DENY")),
                actions=[EnforcementAction(a) for a in rule_data.get("actions", [])],
                priority=rule_data.get("priority", 100),
                enabled=rule_data.get("enabled", True)
            )
            
            for cond_data in rule_data.get("conditions", []):
                condition = Condition(
                    field=cond_data["field"],
                    operator=ConditionOperator(cond_data["operator"]),
                    value=cond_data["value"]
                )
                rule.conditions.append(condition)
            
            policy.add_rule(rule)
        
        return policy
    
    def get_policies_by_tag(self, tag: str) -> List[Policy]:
        """Get all policies with a specific tag."""
        return [p for p in self.policies.values() if tag in p.tags]
    
    def get_all_policies(self) -> List[Policy]:
        """Get all policies."""
        return list(self.policies.values())
    
    def export_policies(self) -> str:
        """Export all policies to JSON."""
        import json
        policies_data = [p.to_dict() for p in self.policies.values()]
        return json.dumps(policies_data, indent=2)
