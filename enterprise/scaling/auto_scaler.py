# Auto Scaler - Week 52 Builder 1
# Automatic scaling decisions

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class ScalingAction(Enum):
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    SCALE_OUT = "scale_out"
    SCALE_IN = "scale_in"
    NONE = "none"


class ScalingStatus(Enum):
    IDLE = "idle"
    SCALING = "scaling"
    COOLDOWN = "cooldown"
    DISABLED = "disabled"


@dataclass
class ScalingEvent:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action: ScalingAction = ScalingAction.NONE
    resource_type: str = ""
    current_capacity: int = 0
    target_capacity: int = 0
    reason: str = ""
    triggered_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    status: str = "pending"


@dataclass
class ScalingTarget:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    resource_type: str = ""
    min_capacity: int = 1
    max_capacity: int = 100
    current_capacity: int = 1
    target_capacity: int = 1
    status: ScalingStatus = ScalingStatus.IDLE
    created_at: datetime = field(default_factory=datetime.utcnow)


class AutoScaler:
    """Automatic scaling decision engine"""

    def __init__(self):
        self._targets: Dict[str, ScalingTarget] = {}
        self._events: List[ScalingEvent] = []
        self._cooldown_until: Dict[str, datetime] = {}
        self._metrics = {
            "total_scale_events": 0,
            "scale_up_count": 0,
            "scale_down_count": 0,
            "by_resource_type": {}
        }

    def register_target(
        self,
        name: str,
        resource_type: str,
        min_capacity: int = 1,
        max_capacity: int = 100,
        initial_capacity: int = 1
    ) -> ScalingTarget:
        """Register a scaling target"""
        target = ScalingTarget(
            name=name,
            resource_type=resource_type,
            min_capacity=min_capacity,
            max_capacity=max_capacity,
            current_capacity=initial_capacity,
            target_capacity=initial_capacity
        )
        self._targets[target.id] = target

        type_key = resource_type
        self._metrics["by_resource_type"][type_key] = \
            self._metrics["by_resource_type"].get(type_key, 0) + 1

        return target

    def deregister_target(self, target_id: str) -> bool:
        """Deregister a scaling target"""
        if target_id in self._targets:
            del self._targets[target_id]
            return True
        return False

    def evaluate_scaling(
        self,
        target_id: str,
        current_metrics: Dict[str, float],
        policies: List[Dict[str, Any]]
    ) -> Optional[ScalingEvent]:
        """Evaluate if scaling is needed"""
        target = self._targets.get(target_id)
        if not target or target.status == ScalingStatus.DISABLED:
            return None

        # Check cooldown
        if target_id in self._cooldown_until:
            if datetime.utcnow() < self._cooldown_until[target_id]:
                return None

        # Evaluate policies
        for policy in policies:
            metric_name = policy.get("metric", "")
            threshold = policy.get("threshold", 0)
            comparison = policy.get("comparison", "greater")
            action = policy.get("action", ScalingAction.NONE)
            scale_by = policy.get("scale_by", 1)

            current_value = current_metrics.get(metric_name, 0)

            should_scale = False
            if comparison == "greater" and current_value > threshold:
                should_scale = True
            elif comparison == "less" and current_value < threshold:
                should_scale = True
            elif comparison == "greater_equal" and current_value >= threshold:
                should_scale = True
            elif comparison == "less_equal" and current_value <= threshold:
                should_scale = True

            if should_scale:
                return self._create_scaling_event(target, action, scale_by, policy.get("reason", ""))

        return None

    def _create_scaling_event(
        self,
        target: ScalingTarget,
        action: ScalingAction,
        scale_by: int,
        reason: str
    ) -> ScalingEvent:
        """Create a scaling event"""
        new_capacity = target.current_capacity

        if action in [ScalingAction.SCALE_UP, ScalingAction.SCALE_OUT]:
            new_capacity = min(target.max_capacity, target.current_capacity + scale_by)
        elif action in [ScalingAction.SCALE_DOWN, ScalingAction.SCALE_IN]:
            new_capacity = max(target.min_capacity, target.current_capacity - scale_by)

        event = ScalingEvent(
            action=action,
            resource_type=target.resource_type,
            current_capacity=target.current_capacity,
            target_capacity=new_capacity,
            reason=reason
        )

        self._events.append(event)
        target.target_capacity = new_capacity
        target.status = ScalingStatus.SCALING

        self._metrics["total_scale_events"] += 1
        if action in [ScalingAction.SCALE_UP, ScalingAction.SCALE_OUT]:
            self._metrics["scale_up_count"] += 1
        elif action in [ScalingAction.SCALE_DOWN, ScalingAction.SCALE_IN]:
            self._metrics["scale_down_count"] += 1

        return event

    def complete_scaling(
        self,
        target_id: str,
        event_id: str,
        success: bool = True,
        cooldown_seconds: int = 300
    ) -> bool:
        """Mark scaling event as complete"""
        target = self._targets.get(target_id)
        if not target:
            return False

        for event in self._events:
            if event.id == event_id and event.status == "pending":
                event.status = "completed" if success else "failed"
                event.completed_at = datetime.utcnow()

                if success:
                    target.current_capacity = event.target_capacity
                    target.status = ScalingStatus.COOLDOWN
                    self._cooldown_until[target_id] = \
                        datetime.utcnow() + __import__('datetime').timedelta(seconds=cooldown_seconds)

                return True
        return False

    def get_target(self, target_id: str) -> Optional[ScalingTarget]:
        """Get target by ID"""
        return self._targets.get(target_id)

    def get_target_by_name(self, name: str) -> Optional[ScalingTarget]:
        """Get target by name"""
        for target in self._targets.values():
            if target.name == name:
                return target
        return None

    def get_targets_by_type(self, resource_type: str) -> List[ScalingTarget]:
        """Get all targets of a type"""
        return [t for t in self._targets.values() if t.resource_type == resource_type]

    def get_event(self, event_id: str) -> Optional[ScalingEvent]:
        """Get event by ID"""
        for event in self._events:
            if event.id == event_id:
                return event
        return None

    def get_events_by_target(
        self,
        target_id: str,
        limit: int = 100
    ) -> List[ScalingEvent]:
        """Get events for a target"""
        target = self._targets.get(target_id)
        if not target:
            return []
        events = [e for e in self._events if e.resource_type == target.resource_type]
        return events[-limit:]

    def get_active_events(self) -> List[ScalingEvent]:
        """Get all pending events"""
        return [e for e in self._events if e.status == "pending"]

    def enable_target(self, target_id: str) -> bool:
        """Enable scaling for target"""
        target = self._targets.get(target_id)
        if not target:
            return False
        target.status = ScalingStatus.IDLE
        return True

    def disable_target(self, target_id: str) -> bool:
        """Disable scaling for target"""
        target = self._targets.get(target_id)
        if not target:
            return False
        target.status = ScalingStatus.DISABLED
        return True

    def force_scale(
        self,
        target_id: str,
        action: ScalingAction,
        scale_by: int,
        reason: str = "Manual scaling"
    ) -> Optional[ScalingEvent]:
        """Force scaling action"""
        target = self._targets.get(target_id)
        if not target:
            return None

        # Clear cooldown for forced scaling
        if target_id in self._cooldown_until:
            del self._cooldown_until[target_id]

        return self._create_scaling_event(target, action, scale_by, reason)

    def get_metrics(self) -> Dict[str, Any]:
        """Get scaler metrics"""
        return {
            **self._metrics,
            "active_targets": len([t for t in self._targets.values() if t.status != ScalingStatus.DISABLED]),
            "pending_events": len(self.get_active_events())
        }
