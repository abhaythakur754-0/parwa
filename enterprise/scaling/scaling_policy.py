# Scaling Policy - Week 52 Builder 1
# Scaling policies and rules

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class PolicyType(Enum):
    THRESHOLD = "threshold"
    SCHEDULE = "schedule"
    PREDICTIVE = "predictive"
    CUSTOM = "custom"


class PolicyStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"


class ComparisonOperator(Enum):
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_EQUAL = "greater_equal"
    LESS_EQUAL = "less_equal"
    EQUAL = "equal"


@dataclass
class ScalingRule:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    metric_name: str = ""
    operator: ComparisonOperator = ComparisonOperator.GREATER_THAN
    threshold: float = 0.0
    action: str = "scale_up"
    scale_by: int = 1
    cooldown_seconds: int = 300
    evaluation_periods: int = 1
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ScalingPolicy:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    policy_type: PolicyType = PolicyType.THRESHOLD
    status: PolicyStatus = PolicyStatus.ACTIVE
    target_id: str = ""
    rules: List[str] = field(default_factory=list)
    schedule: Optional[Dict[str, Any]] = None
    min_capacity: int = 1
    max_capacity: int = 100
    default_cooldown: int = 300
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class ScalingPolicyManager:
    """Manages scaling policies and rules"""

    def __init__(self):
        self._policies: Dict[str, ScalingPolicy] = {}
        self._rules: Dict[str, ScalingRule] = {}
        self._metrics = {
            "total_policies": 0,
            "total_rules": 0,
            "by_type": {},
            "by_status": {}
        }

    def create_policy(
        self,
        name: str,
        policy_type: PolicyType,
        target_id: str,
        min_capacity: int = 1,
        max_capacity: int = 100,
        default_cooldown: int = 300
    ) -> ScalingPolicy:
        """Create a scaling policy"""
        policy = ScalingPolicy(
            name=name,
            policy_type=policy_type,
            target_id=target_id,
            min_capacity=min_capacity,
            max_capacity=max_capacity,
            default_cooldown=default_cooldown
        )
        self._policies[policy.id] = policy
        self._metrics["total_policies"] += 1

        type_key = policy_type.value
        self._metrics["by_type"][type_key] = \
            self._metrics["by_type"].get(type_key, 0) + 1

        status_key = policy.status.value
        self._metrics["by_status"][status_key] = \
            self._metrics["by_status"].get(status_key, 0) + 1

        return policy

    def add_rule(
        self,
        policy_id: str,
        name: str,
        metric_name: str,
        operator: ComparisonOperator,
        threshold: float,
        action: str = "scale_up",
        scale_by: int = 1,
        cooldown_seconds: int = 300,
        evaluation_periods: int = 1
    ) -> Optional[ScalingRule]:
        """Add a rule to a policy"""
        policy = self._policies.get(policy_id)
        if not policy:
            return None

        rule = ScalingRule(
            name=name,
            metric_name=metric_name,
            operator=operator,
            threshold=threshold,
            action=action,
            scale_by=scale_by,
            cooldown_seconds=cooldown_seconds,
            evaluation_periods=evaluation_periods
        )

        self._rules[rule.id] = rule
        policy.rules.append(rule.id)
        self._metrics["total_rules"] += 1
        return rule

    def remove_rule(self, policy_id: str, rule_id: str) -> bool:
        """Remove a rule from a policy"""
        policy = self._policies.get(policy_id)
        if not policy or rule_id not in policy.rules:
            return False

        policy.rules.remove(rule_id)
        if rule_id in self._rules:
            del self._rules[rule_id]
        self._metrics["total_rules"] -= 1
        return True

    def update_policy(
        self,
        policy_id: str,
        **kwargs
    ) -> bool:
        """Update policy settings"""
        policy = self._policies.get(policy_id)
        if not policy:
            return False

        old_status = policy.status.value
        for key, value in kwargs.items():
            if hasattr(policy, key):
                setattr(policy, key, value)
        policy.updated_at = datetime.utcnow()

        if "status" in kwargs:
            self._metrics["by_status"][old_status] -= 1
            new_status = kwargs["status"].value
            self._metrics["by_status"][new_status] = \
                self._metrics["by_status"].get(new_status, 0) + 1

        return True

    def set_schedule(
        self,
        policy_id: str,
        schedule: Dict[str, Any]
    ) -> bool:
        """Set schedule for scheduled policy"""
        policy = self._policies.get(policy_id)
        if not policy:
            return False

        policy.schedule = schedule
        policy.updated_at = datetime.utcnow()
        return True

    def activate_policy(self, policy_id: str) -> bool:
        """Activate a policy"""
        return self.update_policy(policy_id, status=PolicyStatus.ACTIVE)

    def deactivate_policy(self, policy_id: str) -> bool:
        """Deactivate a policy"""
        return self.update_policy(policy_id, status=PolicyStatus.INACTIVE)

    def pause_policy(self, policy_id: str) -> bool:
        """Pause a policy"""
        return self.update_policy(policy_id, status=PolicyStatus.PAUSED)

    def get_policy(self, policy_id: str) -> Optional[ScalingPolicy]:
        """Get policy by ID"""
        return self._policies.get(policy_id)

    def get_policy_by_name(self, name: str) -> Optional[ScalingPolicy]:
        """Get policy by name"""
        for policy in self._policies.values():
            if policy.name == name:
                return policy
        return None

    def get_policies_by_target(self, target_id: str) -> List[ScalingPolicy]:
        """Get all policies for a target"""
        return [p for p in self._policies.values() if p.target_id == target_id]

    def get_policies_by_type(self, policy_type: PolicyType) -> List[ScalingPolicy]:
        """Get all policies of a type"""
        return [p for p in self._policies.values() if p.policy_type == policy_type]

    def get_active_policies(self) -> List[ScalingPolicy]:
        """Get all active policies"""
        return [p for p in self._policies.values() if p.status == PolicyStatus.ACTIVE]

    def get_rule(self, rule_id: str) -> Optional[ScalingRule]:
        """Get rule by ID"""
        return self._rules.get(rule_id)

    def get_rules_for_policy(self, policy_id: str) -> List[ScalingRule]:
        """Get all rules for a policy"""
        policy = self._policies.get(policy_id)
        if not policy:
            return []
        return [self._rules[rid] for rid in policy.rules if rid in self._rules]

    def evaluate_rules(
        self,
        policy_id: str,
        metrics: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Evaluate rules against metrics"""
        policy = self._policies.get(policy_id)
        if not policy or policy.status != PolicyStatus.ACTIVE:
            return []

        results = []
        for rule_id in policy.rules:
            rule = self._rules.get(rule_id)
            if not rule:
                continue

            metric_value = metrics.get(rule.metric_name)
            if metric_value is None:
                continue

            triggered = False
            if rule.operator == ComparisonOperator.GREATER_THAN:
                triggered = metric_value > rule.threshold
            elif rule.operator == ComparisonOperator.LESS_THAN:
                triggered = metric_value < rule.threshold
            elif rule.operator == ComparisonOperator.GREATER_EQUAL:
                triggered = metric_value >= rule.threshold
            elif rule.operator == ComparisonOperator.LESS_EQUAL:
                triggered = metric_value <= rule.threshold
            elif rule.operator == ComparisonOperator.EQUAL:
                triggered = metric_value == rule.threshold

            results.append({
                "rule_id": rule.id,
                "rule_name": rule.name,
                "metric_name": rule.metric_name,
                "metric_value": metric_value,
                "threshold": rule.threshold,
                "operator": rule.operator.value,
                "triggered": triggered,
                "action": rule.action,
                "scale_by": rule.scale_by
            })

        return results

    def delete_policy(self, policy_id: str) -> bool:
        """Delete a policy"""
        if policy_id not in self._policies:
            return False

        policy = self._policies[policy_id]
        for rule_id in policy.rules:
            if rule_id in self._rules:
                del self._rules[rule_id]
                self._metrics["total_rules"] -= 1

        self._metrics["total_policies"] -= 1
        self._metrics["by_type"][policy.policy_type.value] -= 1
        self._metrics["by_status"][policy.status.value] -= 1
        del self._policies[policy_id]
        return True

    def get_metrics(self) -> Dict[str, Any]:
        """Get policy manager metrics"""
        return self._metrics.copy()
