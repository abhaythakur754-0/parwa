"""
Scaling Policy Module - Week 52, Builder 1
Scaling policies and rules engine
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Union
import logging
import re

logger = logging.getLogger(__name__)


class PolicyType(Enum):
    """Policy type enum"""
    THRESHOLD = "threshold"
    SCHEDULE = "schedule"
    PREDICTIVE = "predictive"
    CUSTOM = "custom"


class PolicyAction(Enum):
    """Policy action enum"""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    SCALE_TO = "scale_to"
    NO_ACTION = "no_action"


class PolicyStatus(Enum):
    """Policy status enum"""
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


@dataclass
class ScalingRule:
    """Individual scaling rule"""
    name: str
    condition: str  # Expression to evaluate
    action: PolicyAction
    target_instances: Optional[int] = None
    scale_factor: Optional[float] = None
    priority: int = 100
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate the rule condition"""
        try:
            # Simple expression evaluation
            # Supports comparisons like "cpu > 80", "memory < 30"
            condition = self.condition

            # Replace context variables
            for key, value in context.items():
                if isinstance(value, (int, float)):
                    condition = re.sub(
                        rf'\b{key}\b',
                        str(value),
                        condition
                    )

            # Safely evaluate the condition
            result = eval(condition, {"__builtins__": {}}, {})
            return bool(result)
        except Exception as e:
            logger.error(f"Rule evaluation error: {e}")
            return False


@dataclass
class ScalingPolicy:
    """Complete scaling policy with rules"""
    name: str
    policy_type: PolicyType
    rules: List[ScalingRule] = field(default_factory=list)
    min_instances: int = 1
    max_instances: int = 100
    default_instances: int = 1
    cooldown_seconds: int = 300
    status: PolicyStatus = PolicyStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)
    schedule: Optional[Dict[str, Any]] = None  # For schedule-based policies

    def add_rule(self, rule: ScalingRule) -> None:
        """Add a rule to the policy"""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
        self.updated_at = datetime.utcnow()

    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name"""
        for i, rule in enumerate(self.rules):
            if rule.name == name:
                self.rules.pop(i)
                self.updated_at = datetime.utcnow()
                return True
        return False

    def evaluate(self, context: Dict[str, Any]) -> Optional[ScalingRule]:
        """Evaluate all rules and return the first matching one"""
        if self.status != PolicyStatus.ACTIVE:
            return None

        for rule in self.rules:
            if rule.enabled and rule.evaluate(context):
                return rule
        return None


class PolicyEngine:
    """
    Central policy engine for managing and evaluating scaling policies.
    """

    def __init__(self):
        self.policies: Dict[str, ScalingPolicy] = {}
        self._evaluators: Dict[str, Callable] = {}
        self._hooks: Dict[str, List[Callable]] = {
            "before_evaluate": [],
            "after_evaluate": [],
            "on_action": [],
        }

    def create_policy(
        self,
        name: str,
        policy_type: PolicyType,
        min_instances: int = 1,
        max_instances: int = 100,
        cooldown_seconds: int = 300,
        tags: Optional[Dict[str, str]] = None,
    ) -> ScalingPolicy:
        """Create a new scaling policy"""
        policy = ScalingPolicy(
            name=name,
            policy_type=policy_type,
            min_instances=min_instances,
            max_instances=max_instances,
            cooldown_seconds=cooldown_seconds,
            tags=tags or {},
        )
        self.policies[name] = policy
        logger.info(f"Created policy: {name}")
        return policy

    def get_policy(self, name: str) -> Optional[ScalingPolicy]:
        """Get a policy by name"""
        return self.policies.get(name)

    def delete_policy(self, name: str) -> bool:
        """Delete a policy"""
        if name in self.policies:
            del self.policies[name]
            logger.info(f"Deleted policy: {name}")
            return True
        return False

    def list_policies(
        self,
        policy_type: Optional[PolicyType] = None,
        status: Optional[PolicyStatus] = None,
    ) -> List[ScalingPolicy]:
        """List policies with optional filtering"""
        policies = list(self.policies.values())

        if policy_type:
            policies = [p for p in policies if p.policy_type == policy_type]
        if status:
            policies = [p for p in policies if p.status == status]

        return policies

    def pause_policy(self, name: str) -> bool:
        """Pause a policy"""
        policy = self.get_policy(name)
        if policy:
            policy.status = PolicyStatus.PAUSED
            policy.updated_at = datetime.utcnow()
            logger.info(f"Paused policy: {name}")
            return True
        return False

    def resume_policy(self, name: str) -> bool:
        """Resume a paused policy"""
        policy = self.get_policy(name)
        if policy:
            policy.status = PolicyStatus.ACTIVE
            policy.updated_at = datetime.utcnow()
            logger.info(f"Resumed policy: {name}")
            return True
        return False

    def disable_policy(self, name: str) -> bool:
        """Disable a policy"""
        policy = self.get_policy(name)
        if policy:
            policy.status = PolicyStatus.DISABLED
            policy.updated_at = datetime.utcnow()
            logger.info(f"Disabled policy: {name}")
            return True
        return False

    def add_rule_to_policy(
        self,
        policy_name: str,
        rule_name: str,
        condition: str,
        action: PolicyAction,
        target_instances: Optional[int] = None,
        scale_factor: Optional[float] = None,
        priority: int = 100,
    ) -> bool:
        """Add a rule to a policy"""
        policy = self.get_policy(policy_name)
        if not policy:
            return False

        rule = ScalingRule(
            name=rule_name,
            condition=condition,
            action=action,
            target_instances=target_instances,
            scale_factor=scale_factor,
            priority=priority,
        )
        policy.add_rule(rule)
        return True

    def evaluate_all(
        self,
        context: Dict[str, Any],
        current_instances: int,
    ) -> Dict[str, Optional[ScalingRule]]:
        """
        Evaluate all policies against the context.
        Returns dict of policy_name -> matched_rule.
        """
        results = {}

        # Call before_evaluate hooks
        for hook in self._hooks["before_evaluate"]:
            hook(context)

        for name, policy in self.policies.items():
            # Check instance bounds
            context_copy = context.copy()
            context_copy["current_instances"] = current_instances
            context_copy["min_instances"] = policy.min_instances
            context_copy["max_instances"] = policy.max_instances

            matched_rule = policy.evaluate(context_copy)
            results[name] = matched_rule

        # Call after_evaluate hooks
        for hook in self._hooks["after_evaluate"]:
            hook(results)

        return results

    def get_recommended_action(
        self,
        context: Dict[str, Any],
        current_instances: int,
    ) -> Dict[str, Any]:
        """
        Get the recommended scaling action based on all policies.
        Returns the highest priority action.
        """
        results = self.evaluate_all(context, current_instances)

        best_rule: Optional[ScalingRule] = None
        best_policy: Optional[str] = None

        for policy_name, rule in results.items():
            if rule is None:
                continue

            if best_rule is None or rule.priority > best_rule.priority:
                best_rule = rule
                best_policy = policy_name

        if best_rule is None:
            return {
                "action": PolicyAction.NO_ACTION,
                "target_instances": current_instances,
                "policy": None,
                "rule": None,
            }

        # Calculate target instances
        policy = self.policies[best_policy]
        target = current_instances

        if best_rule.action == PolicyAction.SCALE_UP:
            if best_rule.scale_factor:
                target = int(current_instances * best_rule.scale_factor)
            elif best_rule.target_instances:
                target = best_rule.target_instances
            else:
                target = current_instances + 1

        elif best_rule.action == PolicyAction.SCALE_DOWN:
            if best_rule.scale_factor:
                target = int(current_instances * best_rule.scale_factor)
            elif best_rule.target_instances:
                target = best_rule.target_instances
            else:
                target = current_instances - 1

        elif best_rule.action == PolicyAction.SCALE_TO:
            target = best_rule.target_instances or current_instances

        # Enforce bounds
        target = max(policy.min_instances, min(target, policy.max_instances))

        return {
            "action": best_rule.action,
            "target_instances": target,
            "policy": best_policy,
            "rule": best_rule.name,
        }

    def register_hook(self, event: str, callback: Callable) -> None:
        """Register a hook callback"""
        if event in self._hooks:
            self._hooks[event].append(callback)

    def create_threshold_policy(
        self,
        name: str,
        metric_name: str,
        scale_up_threshold: float,
        scale_down_threshold: float,
        scale_up_factor: float = 1.5,
        scale_down_factor: float = 0.75,
        min_instances: int = 1,
        max_instances: int = 100,
    ) -> ScalingPolicy:
        """Create a simple threshold-based policy"""
        policy = self.create_policy(
            name=name,
            policy_type=PolicyType.THRESHOLD,
            min_instances=min_instances,
            max_instances=max_instances,
        )

        # Add scale up rule
        policy.add_rule(ScalingRule(
            name="scale_up_rule",
            condition=f"{metric_name} > {scale_up_threshold}",
            action=PolicyAction.SCALE_UP,
            scale_factor=scale_up_factor,
            priority=100,
        ))

        # Add scale down rule
        policy.add_rule(ScalingRule(
            name="scale_down_rule",
            condition=f"{metric_name} < {scale_down_threshold}",
            action=PolicyAction.SCALE_DOWN,
            scale_factor=scale_down_factor,
            priority=90,
        ))

        return policy

    def create_schedule_policy(
        self,
        name: str,
        schedules: List[Dict[str, Any]],
        min_instances: int = 1,
        max_instances: int = 100,
    ) -> ScalingPolicy:
        """Create a schedule-based policy"""
        policy = self.create_policy(
            name=name,
            policy_type=PolicyType.SCHEDULE,
            min_instances=min_instances,
            max_instances=max_instances,
        )

        for schedule in schedules:
            policy.add_rule(ScalingRule(
                name=schedule.get("name", "schedule_rule"),
                condition=schedule.get("condition", "True"),
                action=PolicyAction.SCALE_TO,
                target_instances=schedule.get("instances", min_instances),
                priority=schedule.get("priority", 100),
            ))

        return policy

    def export_policies(self) -> Dict[str, Any]:
        """Export all policies as a dictionary"""
        export_data = {
            "policies": {},
            "exported_at": datetime.utcnow().isoformat(),
        }

        for name, policy in self.policies.items():
            policy_data = {
                "name": policy.name,
                "type": policy.policy_type.value,
                "status": policy.status.value,
                "min_instances": policy.min_instances,
                "max_instances": policy.max_instances,
                "cooldown_seconds": policy.cooldown_seconds,
                "rules": [
                    {
                        "name": r.name,
                        "condition": r.condition,
                        "action": r.action.value,
                        "target_instances": r.target_instances,
                        "scale_factor": r.scale_factor,
                        "priority": r.priority,
                        "enabled": r.enabled,
                    }
                    for r in policy.rules
                ],
                "tags": policy.tags,
            }
            export_data["policies"][name] = policy_data

        return export_data

    def import_policies(self, data: Dict[str, Any]) -> int:
        """Import policies from a dictionary"""
        imported = 0

        for name, policy_data in data.get("policies", {}).items():
            try:
                policy = self.create_policy(
                    name=name,
                    policy_type=PolicyType(policy_data["type"]),
                    min_instances=policy_data.get("min_instances", 1),
                    max_instances=policy_data.get("max_instances", 100),
                    cooldown_seconds=policy_data.get("cooldown_seconds", 300),
                    tags=policy_data.get("tags", {}),
                )

                for rule_data in policy_data.get("rules", []):
                    rule = ScalingRule(
                        name=rule_data["name"],
                        condition=rule_data["condition"],
                        action=PolicyAction(rule_data["action"]),
                        target_instances=rule_data.get("target_instances"),
                        scale_factor=rule_data.get("scale_factor"),
                        priority=rule_data.get("priority", 100),
                        enabled=rule_data.get("enabled", True),
                    )
                    policy.add_rule(rule)

                policy.status = PolicyStatus(policy_data.get("status", "active"))
                imported += 1

            except Exception as e:
                logger.error(f"Failed to import policy {name}: {e}")

        logger.info(f"Imported {imported} policies")
        return imported
