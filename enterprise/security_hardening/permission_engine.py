"""
Permission Engine - Week 54 Advanced Security Hardening
Builder 4: Permission Evaluation Engine

Provides advanced permission evaluation with complex rules,
condition evaluation (time-based, attribute-based, context-based),
and bulk permission checking.
"""

from dataclasses import dataclass, field
from typing import Any, Optional, List, Dict, Callable, Union
from datetime import datetime, time
from enum import Enum
import threading
import logging
import re
import fnmatch

logger = logging.getLogger(__name__)


class ConditionType(Enum):
    """Types of permission conditions."""
    TIME_BASED = "time_based"
    ATTRIBUTE_BASED = "attribute_based"
    CONTEXT_BASED = "context_based"
    EXPRESSION = "expression"
    CUSTOM = "custom"


class PermissionResult(Enum):
    """Result of permission evaluation."""
    ALLOW = "allow"
    DENY = "deny"
    ABSTAIN = "abstain"  # No opinion, defer to other rules


@dataclass
class Condition:
    """
    Represents a condition for permission evaluation.
    
    Attributes:
        type: Type of condition
        config: Configuration for the condition
        description: Human-readable description
    """
    type: ConditionType
    config: dict = field(default_factory=dict)
    description: str = ""
    
    def evaluate(self, context: dict) -> bool:
        """Evaluate the condition against the context."""
        if self.type == ConditionType.TIME_BASED:
            return self._evaluate_time_condition(context)
        elif self.type == ConditionType.ATTRIBUTE_BASED:
            return self._evaluate_attribute_condition(context)
        elif self.type == ConditionType.CONTEXT_BASED:
            return self._evaluate_context_condition(context)
        elif self.type == ConditionType.EXPRESSION:
            return self._evaluate_expression(context)
        elif self.type == ConditionType.CUSTOM:
            return self._evaluate_custom(context)
        return True
    
    def _evaluate_time_condition(self, context: dict) -> bool:
        """Evaluate time-based conditions."""
        now = context.get("current_time", datetime.utcnow())
        if isinstance(now, str):
            now = datetime.fromisoformat(now)
        
        # Check business hours
        if "business_hours" in self.config:
            bh = self.config["business_hours"]
            start_time = time.fromisoformat(bh.get("start", "09:00"))
            end_time = time.fromisoformat(bh.get("end", "17:00"))
            current_time = now.time()
            
            if not (start_time <= current_time <= end_time):
                return False
        
        # Check allowed days
        if "allowed_days" in self.config:
            allowed_days = self.config["allowed_days"]
            # 0 = Monday, 6 = Sunday
            if now.weekday() not in allowed_days:
                return False
        
        # Check date range
        if "start_date" in self.config:
            start_date = datetime.fromisoformat(self.config["start_date"])
            if now < start_date:
                return False
        
        if "end_date" in self.config:
            end_date = datetime.fromisoformat(self.config["end_date"])
            if now > end_date:
                return False
        
        return True
    
    def _evaluate_attribute_condition(self, context: dict) -> bool:
        """Evaluate attribute-based conditions."""
        attributes = context.get("attributes", context.get("user_attributes", {}))
        
        for key, requirement in self.config.items():
            if key in ["type", "description"]:
                continue
            
            actual = attributes.get(key)
            
            if isinstance(requirement, dict):
                # Complex requirement
                if "equals" in requirement and actual != requirement["equals"]:
                    return False
                if "not_equals" in requirement and actual == requirement["not_equals"]:
                    return False
                if "in" in requirement and actual not in requirement["in"]:
                    return False
                if "not_in" in requirement and actual in requirement["not_in"]:
                    return False
                if "contains" in requirement and requirement["contains"] not in (actual or []):
                    return False
                if "matches" in requirement:
                    if not re.match(requirement["matches"], str(actual or "")):
                        return False
            elif actual != requirement:
                return False
        
        return True
    
    def _evaluate_context_condition(self, context: dict) -> bool:
        """Evaluate context-based conditions."""
        for key, requirement in self.config.items():
            if key in ["type", "description"]:
                continue
            
            actual = context.get(key)
            
            # IP address checking
            if key == "ip_address":
                if "allowed_ips" in requirement:
                    if actual not in requirement["allowed_ips"]:
                        return False
                elif "allowed_ranges" in requirement:
                    # Simple IP range check (for CIDR, use ipaddress module)
                    if not any(actual.startswith(r.rstrip('*')) for r in requirement["allowed_ranges"]):
                        return False
            
            # Location checking
            elif key == "location":
                if "allowed_countries" in requirement:
                    if actual not in requirement["allowed_countries"]:
                        return False
            
            # Device checking
            elif key == "device_type":
                if isinstance(requirement, list) and actual not in requirement:
                    return False
            
            # Session checking
            elif key == "session_type":
                if requirement == "mfa_required":
                    if not context.get("mfa_verified", False):
                        return False
            
            elif actual != requirement:
                return False
        
        return True
    
    def _evaluate_expression(self, context: dict) -> bool:
        """Evaluate an expression-based condition."""
        expression = self.config.get("expression", "true")
        
        # Safe evaluation of simple expressions
        # Only allow basic comparisons and logical operators
        try:
            # Create a safe evaluation context
            safe_context = {
                "user": context.get("user", ""),
                "resource": context.get("resource", ""),
                "action": context.get("action", ""),
                "context": context,
                "True": True,
                "False": False,
                "and": lambda a, b: a and b,
                "or": lambda a, b: a or b,
                "not": lambda a: not a,
            }
            # This is a simplified expression evaluator
            # In production, use a proper expression language
            result = self._safe_eval(expression, context)
            return bool(result)
        except Exception as e:
            logger.error(f"Expression evaluation error: {e}")
            return False
    
    def _safe_eval(self, expression: str, context: dict) -> Any:
        """Safely evaluate an expression."""
        # Replace context references
        result = expression
        for key, value in context.items():
            placeholder = f"${key}"
            if placeholder in result:
                result = result.replace(placeholder, repr(value))
        
        # Only allow safe operations
        allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.'\" ==!=<>andornot() ")
        if not all(c in allowed_chars for c in result):
            raise ValueError("Unsafe expression")
        
        # Use eval with restricted globals
        return eval(result, {"__builtins__": {}}, context)
    
    def _evaluate_custom(self, context: dict) -> bool:
        """Evaluate a custom condition function."""
        func = self.config.get("function")
        if callable(func):
            return func(context)
        return True


@dataclass
class PermissionRule:
    """
    Represents a permission rule with conditions.
    
    Attributes:
        id: Unique rule identifier
        name: Human-readable name
        resource_pattern: Pattern for matching resources
        action_pattern: Pattern for matching actions
        result: Result when rule matches
        conditions: List of conditions that must all pass
        priority: Rule priority (higher = evaluated first)
        enabled: Whether the rule is active
    """
    id: str
    name: str
    resource_pattern: str
    action_pattern: str
    result: PermissionResult
    conditions: List[Condition] = field(default_factory=list)
    priority: int = 0
    enabled: bool = True
    
    def matches(self, resource: str, action: str) -> bool:
        """Check if this rule matches the resource and action."""
        resource_match = fnmatch.fnmatch(resource, self.resource_pattern)
        action_match = fnmatch.fnmatch(action, self.action_pattern)
        return resource_match and action_match
    
    def evaluate(self, context: dict) -> PermissionResult:
        """
        Evaluate this rule against the context.
        
        Returns ABSTAIN if conditions don't pass, otherwise returns the result.
        """
        if not self.enabled:
            return PermissionResult.ABSTAIN
        
        # All conditions must pass
        for condition in self.conditions:
            if not condition.evaluate(context):
                return PermissionResult.ABSTAIN
        
        return self.result


@dataclass
class PermissionPolicy:
    """
    Represents a collection of permission rules.
    
    Attributes:
        id: Unique policy identifier
        name: Human-readable name
        description: Policy description
        rules: List of permission rules
        default_result: Default result when no rules match
        version: Policy version
        created_at: When the policy was created
        updated_at: When the policy was last updated
    """
    id: str
    name: str
    description: str = ""
    rules: List[PermissionRule] = field(default_factory=list)
    default_result: PermissionResult = PermissionResult.DENY
    version: str = "1.0"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def add_rule(self, rule: PermissionRule) -> None:
        """Add a rule to the policy."""
        self.rules.append(rule)
        self._sort_rules()
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule from the policy."""
        for i, rule in enumerate(self.rules):
            if rule.id == rule_id:
                del self.rules[i]
                return True
        return False
    
    def _sort_rules(self) -> None:
        """Sort rules by priority (descending)."""
        self.rules.sort(key=lambda r: r.priority, reverse=True)


@dataclass
class BulkCheckRequest:
    """Request for bulk permission checking."""
    user: str
    checks: List[Dict[str, str]]  # List of {"resource": ..., "action": ...}
    context: dict = field(default_factory=dict)


@dataclass
class BulkCheckResult:
    """Result of bulk permission checking."""
    user: str
    results: Dict[str, Dict[str, bool]]  # {"resource:action": {"allowed": bool, ...}}
    timestamp: datetime = field(default_factory=datetime.utcnow)


class PermissionEngine:
    """
    Permission Evaluation Engine.
    
    Provides:
    - Complex permission rule evaluation
    - Multiple condition types (time, attribute, context)
    - Policy management
    - Bulk permission checking
    - Caching for performance
    """
    
    def __init__(self, default_result: PermissionResult = PermissionResult.DENY):
        """
        Initialize the permission engine.
        
        Args:
            default_result: Default result when no rules match
        """
        self._policies: Dict[str, PermissionPolicy] = {}
        self._user_policies: Dict[str, List[str]] = {}  # user_id -> policy_ids
        self._condition_registry: Dict[str, Callable] = {}
        self._cache: Dict[str, dict] = {}
        self._default_result = default_result
        self._lock = threading.RLock()
        
        # Register built-in condition evaluators
        self._register_builtin_conditions()
    
    def _register_builtin_conditions(self) -> None:
        """Register built-in condition evaluator functions."""
        self._condition_registry["is_business_hours"] = self._is_business_hours
        self._condition_registry["is_weekday"] = self._is_weekday
        self._condition_registry["ip_in_range"] = self._ip_in_range
        self._condition_registry["has_mfa"] = self._has_mfa
    
    def _is_business_hours(self, context: dict, start: str = "09:00", end: str = "17:00") -> bool:
        """Check if current time is within business hours."""
        now = context.get("current_time", datetime.utcnow())
        if isinstance(now, str):
            now = datetime.fromisoformat(now)
        
        start_time = time.fromisoformat(start)
        end_time = time.fromisoformat(end)
        return start_time <= now.time() <= end_time
    
    def _is_weekday(self, context: dict) -> bool:
        """Check if current day is a weekday."""
        now = context.get("current_time", datetime.utcnow())
        if isinstance(now, str):
            now = datetime.fromisoformat(now)
        return now.weekday() < 5  # Monday = 0, Friday = 4
    
    def _ip_in_range(self, context: dict, allowed_ips: List[str]) -> bool:
        """Check if IP is in allowed list."""
        ip = context.get("ip_address", "")
        return ip in allowed_ips
    
    def _has_mfa(self, context: dict) -> bool:
        """Check if user has MFA verified."""
        return context.get("mfa_verified", False)
    
    def create_policy(
        self,
        policy_id: str,
        name: str,
        description: str = "",
        default_result: PermissionResult = PermissionResult.DENY
    ) -> PermissionPolicy:
        """
        Create a new permission policy.
        
        Args:
            policy_id: Unique policy identifier
            name: Human-readable name
            description: Policy description
            default_result: Default result for this policy
            
        Returns:
            The created PermissionPolicy
        """
        with self._lock:
            policy = PermissionPolicy(
                id=policy_id,
                name=name,
                description=description,
                default_result=default_result
            )
            self._policies[policy_id] = policy
            logger.info(f"Created policy: {policy_id}")
            return policy
    
    def get_policy(self, policy_id: str) -> Optional[PermissionPolicy]:
        """Get a policy by ID."""
        return self._policies.get(policy_id)
    
    def delete_policy(self, policy_id: str) -> bool:
        """Delete a policy."""
        with self._lock:
            if policy_id in self._policies:
                del self._policies[policy_id]
                # Remove from user assignments
                for user_id in list(self._user_policies.keys()):
                    self._user_policies[user_id] = [
                        pid for pid in self._user_policies[user_id] if pid != policy_id
                    ]
                return True
            return False
    
    def add_rule_to_policy(
        self,
        policy_id: str,
        rule: PermissionRule
    ) -> bool:
        """Add a rule to a policy."""
        with self._lock:
            policy = self._policies.get(policy_id)
            if not policy:
                return False
            policy.add_rule(rule)
            policy.updated_at = datetime.utcnow()
            return True
    
    def assign_policy_to_user(self, user_id: str, policy_id: str) -> bool:
        """Assign a policy to a user."""
        with self._lock:
            if policy_id not in self._policies:
                return False
            
            if user_id not in self._user_policies:
                self._user_policies[user_id] = []
            
            if policy_id not in self._user_policies[user_id]:
                self._user_policies[user_id].append(policy_id)
            
            return True
    
    def unassign_policy_from_user(self, user_id: str, policy_id: str) -> bool:
        """Remove a policy assignment from a user."""
        with self._lock:
            if user_id not in self._user_policies:
                return False
            
            if policy_id in self._user_policies[user_id]:
                self._user_policies[user_id].remove(policy_id)
                return True
            return False
    
    def evaluate(
        self,
        user: str,
        resource: str,
        action: str,
        context: Optional[dict] = None
    ) -> PermissionResult:
        """
        Evaluate permissions for a user on a resource/action.
        
        Args:
            user: User identifier
            resource: Resource being accessed
            action: Action being performed
            context: Additional context for evaluation
            
        Returns:
            PermissionResult (ALLOW, DENY, or ABSTAIN)
        """
        context = context or {}
        context["user"] = user
        context["resource"] = resource
        context["action"] = action
        
        # Get user's policies
        policy_ids = self._user_policies.get(user, [])
        
        # Check each policy's rules
        for policy_id in policy_ids:
            policy = self._policies.get(policy_id)
            if not policy:
                continue
            
            for rule in policy.rules:
                if rule.matches(resource, action):
                    result = rule.evaluate(context)
                    if result != PermissionResult.ABSTAIN:
                        return result
        
        # Return default result if no rules matched
        return self._default_result
    
    def check(
        self,
        user: str,
        resource: str,
        action: str,
        context: Optional[dict] = None
    ) -> dict:
        """
        Comprehensive permission check with detailed response.
        
        Args:
            user: User identifier
            resource: Resource being accessed
            action: Action being performed
            context: Additional context for evaluation
            
        Returns:
            Dict with decision, reasons, and matched rules
        """
        context = context or {}
        context["user"] = user
        context["resource"] = resource
        context["action"] = action
        
        reasons = []
        matched_rules = []
        
        policy_ids = self._user_policies.get(user, [])
        
        for policy_id in policy_ids:
            policy = self._policies.get(policy_id)
            if not policy:
                continue
            
            for rule in policy.rules:
                if rule.matches(resource, action):
                    result = rule.evaluate(context)
                    if result == PermissionResult.ALLOW:
                        matched_rules.append(rule.id)
                        reasons.append(f"Allowed by rule '{rule.name}' in policy '{policy.name}'")
                        return {
                            "decision": PermissionResult.ALLOW,
                            "reasons": reasons,
                            "matched_rules": matched_rules,
                            "matched_permissions": matched_rules
                        }
                    elif result == PermissionResult.DENY:
                        matched_rules.append(rule.id)
                        reasons.append(f"Denied by rule '{rule.name}' in policy '{policy.name}'")
                        return {
                            "decision": PermissionResult.DENY,
                            "reasons": reasons,
                            "matched_rules": matched_rules,
                            "matched_permissions": []
                        }
        
        return {
            "decision": self._default_result,
            "reasons": ["No matching permission rules"],
            "matched_rules": [],
            "matched_permissions": []
        }
    
    def is_allowed(
        self,
        user: str,
        resource: str,
        action: str,
        context: Optional[dict] = None
    ) -> bool:
        """Check if access is allowed."""
        result = self.evaluate(user, resource, action, context)
        return result == PermissionResult.ALLOW
    
    def bulk_check(self, request: BulkCheckRequest) -> BulkCheckResult:
        """
        Perform bulk permission checking.
        
        Args:
            request: BulkCheckRequest with user and list of checks
            
        Returns:
            BulkCheckResult with all check results
        """
        results = {}
        
        for check in request.checks:
            resource = check["resource"]
            action = check["action"]
            key = f"{resource}:{action}"
            
            result = self.evaluate(
                request.user,
                resource,
                action,
                request.context
            )
            
            results[key] = {
                "allowed": result == PermissionResult.ALLOW,
                "result": result.value
            }
        
        return BulkCheckResult(
            user=request.user,
            results=results
        )
    
    def register_condition(
        self,
        name: str,
        evaluator: Callable[[dict], bool]
    ) -> None:
        """
        Register a custom condition evaluator.
        
        Args:
            name: Condition name
            evaluator: Function that takes context and returns bool
        """
        self._condition_registry[name] = evaluator
    
    def create_time_based_rule(
        self,
        rule_id: str,
        name: str,
        resource_pattern: str,
        action_pattern: str,
        result: PermissionResult,
        business_hours: Optional[dict] = None,
        allowed_days: Optional[List[int]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> PermissionRule:
        """
        Create a time-based permission rule.
        
        Args:
            rule_id: Unique rule identifier
            name: Human-readable name
            resource_pattern: Resource pattern
            action_pattern: Action pattern
            result: Permission result
            business_hours: Dict with 'start' and 'end' times
            allowed_days: List of weekday numbers (0=Monday)
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            
        Returns:
            PermissionRule instance
        """
        config = {}
        if business_hours:
            config["business_hours"] = business_hours
        if allowed_days:
            config["allowed_days"] = allowed_days
        if start_date:
            config["start_date"] = start_date
        if end_date:
            config["end_date"] = end_date
        
        condition = Condition(
            type=ConditionType.TIME_BASED,
            config=config,
            description="Time-based access restriction"
        )
        
        return PermissionRule(
            id=rule_id,
            name=name,
            resource_pattern=resource_pattern,
            action_pattern=action_pattern,
            result=result,
            conditions=[condition]
        )
    
    def create_attribute_based_rule(
        self,
        rule_id: str,
        name: str,
        resource_pattern: str,
        action_pattern: str,
        result: PermissionResult,
        attributes: dict
    ) -> PermissionRule:
        """
        Create an attribute-based permission rule.
        
        Args:
            rule_id: Unique rule identifier
            name: Human-readable name
            resource_pattern: Resource pattern
            action_pattern: Action pattern
            result: Permission result
            attributes: Required attribute values
            
        Returns:
            PermissionRule instance
        """
        condition = Condition(
            type=ConditionType.ATTRIBUTE_BASED,
            config=attributes,
            description="Attribute-based access control"
        )
        
        return PermissionRule(
            id=rule_id,
            name=name,
            resource_pattern=resource_pattern,
            action_pattern=action_pattern,
            result=result,
            conditions=[condition]
        )
    
    def create_context_based_rule(
        self,
        rule_id: str,
        name: str,
        resource_pattern: str,
        action_pattern: str,
        result: PermissionResult,
        context_requirements: dict
    ) -> PermissionRule:
        """
        Create a context-based permission rule.
        
        Args:
            rule_id: Unique rule identifier
            name: Human-readable name
            resource_pattern: Resource pattern
            action_pattern: Action pattern
            result: Permission result
            context_requirements: Required context values
            
        Returns:
            PermissionRule instance
        """
        condition = Condition(
            type=ConditionType.CONTEXT_BASED,
            config=context_requirements,
            description="Context-based access control"
        )
        
        return PermissionRule(
            id=rule_id,
            name=name,
            resource_pattern=resource_pattern,
            action_pattern=action_pattern,
            result=result,
            conditions=[condition]
        )
    
    @property
    def policy_count(self) -> int:
        """Get the number of policies."""
        return len(self._policies)
    
    @property
    def rule_count(self) -> int:
        """Get the total number of rules across all policies."""
        return sum(len(p.rules) for p in self._policies.values())
    
    def get_user_policies(self, user_id: str) -> List[PermissionPolicy]:
        """Get all policies assigned to a user."""
        policy_ids = self._user_policies.get(user_id, [])
        return [self._policies[pid] for pid in policy_ids if pid in self._policies]
