"""
Limit Enforcer

Enforces resource limits and blocks violations in real-time.
"""

from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import logging
import threading
import time

from .quota_manager import QuotaManager, ResourceType

logger = logging.getLogger(__name__)


class EnforcementAction(str, Enum):
    """Actions to take when limit exceeded"""
    BLOCK = "block"
    THROTTLE = "throttle"
    QUEUE = "queue"
    DEGRADE = "degrade"  # Reduce quality/features


class ViolationSeverity(str, Enum):
    """Severity of limit violations"""
    WARNING = "warning"
    SOFT_LIMIT = "soft_limit"
    HARD_LIMIT = "hard_limit"
    CRITICAL = "critical"


@dataclass
class LimitViolation:
    """Record of a limit violation"""
    violation_id: str
    tenant_id: str
    resource_type: ResourceType
    limit: int
    attempted: int
    severity: ViolationSeverity
    action_taken: EnforcementAction
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ThrottleState:
    """Throttling state for a tenant"""
    tenant_id: str
    resource_type: ResourceType
    requests_blocked: int = 0
    throttle_until: Optional[datetime] = None
    backoff_seconds: float = 1.0
    last_violation: Optional[datetime] = None


class LimitEnforcer:
    """
    Enforces resource limits in real-time.

    Features:
    - Real-time limit checking
    - Multiple enforcement actions
    - Throttling with backoff
    - Violation tracking
    """

    def __init__(
        self,
        quota_manager: QuotaManager,
        default_action: EnforcementAction = EnforcementAction.BLOCK
    ):
        self.quota_manager = quota_manager
        self.default_action = default_action

        # Violation tracking
        self._violations: List[LimitViolation] = []

        # Throttle states
        self._throttle_states: Dict[str, ThrottleState] = {}
        self._throttle_lock = threading.Lock()

        # Enforcement rules
        self._enforcement_rules: Dict[ResourceType, EnforcementAction] = {}

        # Callbacks
        self._on_violation: Optional[Callable[[LimitViolation], None]] = None

        # Metrics
        self._metrics = {
            "total_checks": 0,
            "violations_blocked": 0,
            "violations_throttled": 0,
            "total_violations": 0
        }

    def set_enforcement_rule(
        self,
        resource_type: ResourceType,
        action: EnforcementAction
    ) -> None:
        """Set enforcement action for a resource type"""
        self._enforcement_rules[resource_type] = action

    def enforce(
        self,
        tenant_id: str,
        resource_type: ResourceType,
        amount: int = 1,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Enforce limit for a resource request.

        Args:
            tenant_id: Tenant making request
            resource_type: Resource type
            amount: Amount being requested
            context: Additional context

        Returns:
            Enforcement result
        """
        self._metrics["total_checks"] += 1

        result = {
            "allowed": True,
            "tenant_id": tenant_id,
            "resource_type": resource_type.value,
            "amount": amount
        }

        # Check if throttled
        if self._is_throttled(tenant_id, resource_type):
            result["allowed"] = False
            result["reason"] = "throttled"
            result["retry_after"] = self._get_throttle_remaining(tenant_id, resource_type)
            return result

        # Check quota
        quota_check = self.quota_manager.check_quota(tenant_id, resource_type, amount)

        if not quota_check.get("allowed", True):
            # Determine enforcement action
            action = self._get_enforcement_action(resource_type)

            # Record violation
            violation = self._record_violation(
                tenant_id=tenant_id,
                resource_type=resource_type,
                limit=quota_check.get("limit", 0),
                attempted=amount,
                action=action
            )

            result["allowed"] = action != EnforcementAction.BLOCK
            result["reason"] = "limit_exceeded"
            result["action"] = action.value
            result["violation_id"] = violation.violation_id

            # Apply enforcement
            if action == EnforcementAction.THROTTLE:
                self._apply_throttle(tenant_id, resource_type)
                self._metrics["violations_throttled"] += 1
            elif action == EnforcementAction.BLOCK:
                self._metrics["violations_blocked"] += 1

            # Callback
            if self._on_violation:
                self._on_violation(violation)

        return result

    def _get_enforcement_action(self, resource_type: ResourceType) -> EnforcementAction:
        """Get enforcement action for resource type"""
        return self._enforcement_rules.get(resource_type, self.default_action)

    def _is_throttled(self, tenant_id: str, resource_type: ResourceType) -> bool:
        """Check if tenant is throttled"""
        key = f"{tenant_id}:{resource_type.value}"

        with self._throttle_lock:
            state = self._throttle_states.get(key)
            if not state:
                return False

            if state.throttle_until and datetime.utcnow() < state.throttle_until:
                return True

            return False

    def _get_throttle_remaining(self, tenant_id: str, resource_type: ResourceType) -> float:
        """Get remaining throttle time in seconds"""
        key = f"{tenant_id}:{resource_type.value}"

        with self._throttle_lock:
            state = self._throttle_states.get(key)
            if not state or not state.throttle_until:
                return 0

            remaining = (state.throttle_until - datetime.utcnow()).total_seconds()
            return max(0, remaining)

    def _apply_throttle(self, tenant_id: str, resource_type: ResourceType) -> None:
        """Apply throttling to tenant"""
        key = f"{tenant_id}:{resource_type.value}"

        with self._throttle_lock:
            state = self._throttle_states.get(key)

            if not state:
                state = ThrottleState(
                    tenant_id=tenant_id,
                    resource_type=resource_type
                )
                self._throttle_states[key] = state

            # Exponential backoff
            state.backoff_seconds = min(60, state.backoff_seconds * 2)
            state.throttle_until = datetime.utcnow() + timedelta(seconds=state.backoff_seconds)
            state.requests_blocked += 1
            state.last_violation = datetime.utcnow()

    def _record_violation(
        self,
        tenant_id: str,
        resource_type: ResourceType,
        limit: int,
        attempted: int,
        action: EnforcementAction
    ) -> LimitViolation:
        """Record a limit violation"""
        violation_id = f"viol_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{len(self._violations)}"

        severity = ViolationSeverity.HARD_LIMIT
        if action == EnforcementAction.THROTTLE:
            severity = ViolationSeverity.SOFT_LIMIT

        violation = LimitViolation(
            violation_id=violation_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            limit=limit,
            attempted=attempted,
            severity=severity,
            action_taken=action
        )

        self._violations.append(violation)
        self._metrics["total_violations"] += 1

        return violation

    def clear_throttle(self, tenant_id: str, resource_type: ResourceType) -> bool:
        """Clear throttle for a tenant"""
        key = f"{tenant_id}:{resource_type.value}"

        with self._throttle_lock:
            if key in self._throttle_states:
                del self._throttle_states[key]
                return True
        return False

    def get_violations(
        self,
        tenant_id: Optional[str] = None,
        resource_type: Optional[ResourceType] = None,
        limit: int = 100
    ) -> List[LimitViolation]:
        """Get violations, optionally filtered"""
        violations = self._violations

        if tenant_id:
            violations = [v for v in violations if v.tenant_id == tenant_id]

        if resource_type:
            violations = [v for v in violations if v.resource_type == resource_type]

        return sorted(violations, key=lambda x: x.timestamp, reverse=True)[:limit]

    def get_throttle_status(self, tenant_id: str) -> Dict[str, Any]:
        """Get throttle status for tenant"""
        status = {"tenant_id": tenant_id, "throttled": [], "active": False}

        with self._throttle_lock:
            for key, state in self._throttle_states.items():
                if state.tenant_id == tenant_id:
                    remaining = 0
                    if state.throttle_until:
                        remaining = max(0, (state.throttle_until - datetime.utcnow()).total_seconds())

                    if remaining > 0:
                        status["throttled"].append({
                            "resource": state.resource_type.value,
                            "remaining_seconds": remaining,
                            "requests_blocked": state.requests_blocked
                        })
                        status["active"] = True

        return status

    def set_violation_callback(
        self,
        callback: Callable[[LimitViolation], None]
    ) -> None:
        """Set callback for violations"""
        self._on_violation = callback

    def get_metrics(self) -> Dict[str, Any]:
        """Get enforcer metrics"""
        return {
            **self._metrics,
            "active_throttles": len([
                s for s in self._throttle_states.values()
                if s.throttle_until and s.throttle_until > datetime.utcnow()
            ])
        }


# Import timedelta for throttle calculations
from datetime import timedelta
