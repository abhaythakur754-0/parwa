"""
Auto-Scaler Module - Week 52, Builder 1
Automatic scaling decisions based on metrics and policies
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import asyncio
import logging
import math

logger = logging.getLogger(__name__)


class ScalingDirection(Enum):
    """Scaling direction enum"""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    NONE = "none"


class ScalingStatus(Enum):
    """Scaling operation status"""
    IDLE = "idle"
    SCALING = "scaling"
    COOLDOWN = "cooldown"
    ERROR = "error"


@dataclass
class ScalingDecision:
    """Scaling decision dataclass"""
    direction: ScalingDirection
    current_instances: int
    target_instances: int
    reason: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metrics: Dict[str, float] = field(default_factory=dict)
    policy_name: str = ""
    confidence: float = 1.0


@dataclass
class ScalingEvent:
    """Scaling event record"""
    decision: ScalingDecision
    executed: bool = False
    execution_time: Optional[datetime] = None
    error: Optional[str] = None


class AutoScaler:
    """
    Automatic scaling engine that makes scaling decisions
    based on metrics and policies.
    """

    def __init__(
        self,
        min_instances: int = 1,
        max_instances: int = 100,
        cooldown_period: int = 300,  # 5 minutes
        evaluation_interval: int = 60,  # 1 minute
    ):
        self.min_instances = min_instances
        self.max_instances = max_instances
        self.cooldown_period = cooldown_period
        self.evaluation_interval = evaluation_interval

        self.current_instances = min_instances
        self.status = ScalingStatus.IDLE
        self.last_scaling_time: Optional[datetime] = None
        self.policies: List[Dict[str, Any]] = []
        self.metrics: Dict[str, float] = {}
        self.events: List[ScalingEvent] = []
        self._scaling_handlers: List[Callable] = []

    def add_policy(
        self,
        name: str,
        metric_name: str,
        threshold_up: float,
        threshold_down: float,
        scale_up_factor: float = 1.5,
        scale_down_factor: float = 0.75,
        min_instances_override: Optional[int] = None,
        max_instances_override: Optional[int] = None,
    ) -> None:
        """Add a scaling policy"""
        policy = {
            "name": name,
            "metric_name": metric_name,
            "threshold_up": threshold_up,
            "threshold_down": threshold_down,
            "scale_up_factor": scale_up_factor,
            "scale_down_factor": scale_down_factor,
            "min_instances": min_instances_override or self.min_instances,
            "max_instances": max_instances_override or self.max_instances,
            "enabled": True,
        }
        self.policies.append(policy)
        logger.info(f"Added scaling policy: {name}")

    def remove_policy(self, name: str) -> bool:
        """Remove a scaling policy by name"""
        for i, policy in enumerate(self.policies):
            if policy["name"] == name:
                self.policies.pop(i)
                logger.info(f"Removed scaling policy: {name}")
                return True
        return False

    def enable_policy(self, name: str) -> bool:
        """Enable a policy"""
        for policy in self.policies:
            if policy["name"] == name:
                policy["enabled"] = True
                return True
        return False

    def disable_policy(self, name: str) -> bool:
        """Disable a policy"""
        for policy in self.policies:
            if policy["name"] == name:
                policy["enabled"] = False
                return True
        return False

    def update_metrics(self, metrics: Dict[str, float]) -> None:
        """Update current metrics"""
        self.metrics.update(metrics)

    def set_current_instances(self, count: int) -> None:
        """Set current instance count"""
        self.current_instances = max(self.min_instances, min(count, self.max_instances))

    def is_in_cooldown(self) -> bool:
        """Check if scaler is in cooldown period"""
        if self.last_scaling_time is None:
            return False

        elapsed = (datetime.utcnow() - self.last_scaling_time).total_seconds()
        return elapsed < self.cooldown_period

    def evaluate(self) -> Optional[ScalingDecision]:
        """
        Evaluate metrics against policies and return scaling decision.
        Returns None if no scaling needed or in cooldown.
        """
        if self.is_in_cooldown():
            logger.debug("In cooldown period, skipping evaluation")
            return None

        for policy in self.policies:
            if not policy["enabled"]:
                continue

            metric_name = policy["metric_name"]
            if metric_name not in self.metrics:
                continue

            current_value = self.metrics[metric_name]

            # Check scale up condition
            if current_value > policy["threshold_up"]:
                target = math.ceil(
                    self.current_instances * policy["scale_up_factor"]
                )
                target = min(target, policy["max_instances"])

                if target > self.current_instances:
                    return ScalingDecision(
                        direction=ScalingDirection.SCALE_UP,
                        current_instances=self.current_instances,
                        target_instances=target,
                        reason=f"{metric_name} ({current_value:.2f}) > threshold ({policy['threshold_up']:.2f})",
                        metrics={metric_name: current_value},
                        policy_name=policy["name"],
                    )

            # Check scale down condition
            elif current_value < policy["threshold_down"]:
                target = math.floor(
                    self.current_instances * policy["scale_down_factor"]
                )
                target = max(target, policy["min_instances"])

                if target < self.current_instances:
                    return ScalingDecision(
                        direction=ScalingDirection.SCALE_DOWN,
                        current_instances=self.current_instances,
                        target_instances=target,
                        reason=f"{metric_name} ({current_value:.2f}) < threshold ({policy['threshold_down']:.2f})",
                        metrics={metric_name: current_value},
                        policy_name=policy["name"],
                    )

        return None

    def scale(self, decision: ScalingDecision) -> ScalingEvent:
        """Execute a scaling decision"""
        event = ScalingEvent(decision=decision)

        try:
            self.status = ScalingStatus.SCALING

            # Simulate scaling operation
            old_count = self.current_instances
            self.current_instances = decision.target_instances
            self.last_scaling_time = datetime.utcnow()

            # Notify handlers
            for handler in self._scaling_handlers:
                try:
                    handler(decision)
                except Exception as e:
                    logger.error(f"Scaling handler error: {e}")

            event.executed = True
            event.execution_time = datetime.utcnow()
            self.status = ScalingStatus.COOLDOWN

            logger.info(
                f"Scaled from {old_count} to {decision.target_instances} instances"
            )

        except Exception as e:
            event.error = str(e)
            self.status = ScalingStatus.ERROR
            logger.error(f"Scaling failed: {e}")

        self.events.append(event)
        return event

    def add_scaling_handler(self, handler: Callable) -> None:
        """Add a handler to be called on scaling events"""
        self._scaling_handlers.append(handler)

    def get_events(
        self,
        limit: int = 100,
        direction: Optional[ScalingDirection] = None,
    ) -> List[ScalingEvent]:
        """Get scaling events with optional filtering"""
        events = self.events

        if direction:
            events = [e for e in events if e.decision.direction == direction]

        return events[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """Get scaling statistics"""
        scale_ups = len([e for e in self.events if e.decision.direction == ScalingDirection.SCALE_UP])
        scale_downs = len([e for e in self.events if e.decision.direction == ScalingDirection.SCALE_DOWN])

        return {
            "current_instances": self.current_instances,
            "status": self.status.value,
            "total_scale_ups": scale_ups,
            "total_scale_downs": scale_downs,
            "total_events": len(self.events),
            "policies_count": len(self.policies),
            "active_policies": len([p for p in self.policies if p["enabled"]]),
            "in_cooldown": self.is_in_cooldown(),
            "last_scaling_time": self.last_scaling_time.isoformat() if self.last_scaling_time else None,
        }

    async def run_evaluation_loop(self) -> None:
        """Run continuous evaluation loop"""
        while True:
            decision = self.evaluate()
            if decision:
                self.scale(decision)
            await asyncio.sleep(self.evaluation_interval)

    def reset(self) -> None:
        """Reset scaler to initial state"""
        self.current_instances = self.min_instances
        self.status = ScalingStatus.IDLE
        self.last_scaling_time = None
        self.events.clear()
        self.metrics.clear()


class PredictiveScaler(AutoScaler):
    """
    Predictive auto-scaler that uses historical data
    to anticipate scaling needs.
    """

    def __init__(
        self,
        prediction_window: int = 300,  # 5 minutes ahead
        history_size: int = 100,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.prediction_window = prediction_window
        self.history_size = history_size
        self.metric_history: Dict[str, List[tuple]] = {}

    def record_metric(self, name: str, value: float) -> None:
        """Record a metric value for prediction"""
        if name not in self.metric_history:
            self.metric_history[name] = []

        self.metric_history[name].append((datetime.utcnow(), value))

        # Keep only recent history
        if len(self.metric_history[name]) > self.history_size:
            self.metric_history[name] = self.metric_history[name][-self.history_size:]

    def predict_metric(self, name: str) -> Optional[float]:
        """Predict future metric value using linear regression"""
        if name not in self.metric_history or len(self.metric_history[name]) < 10:
            return None

        history = self.metric_history[name]
        timestamps = [(h[0] - history[0][0]).total_seconds() for h in history]
        values = [h[1] for h in history]

        # Simple linear regression
        n = len(values)
        sum_x = sum(timestamps)
        sum_y = sum(values)
        sum_xy = sum(t * v for t, v in zip(timestamps, values))
        sum_x2 = sum(t * t for t in timestamps)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        intercept = (sum_y - slope * sum_x) / n

        # Predict at prediction window
        future_time = timestamps[-1] + self.prediction_window
        predicted_value = slope * future_time + intercept

        return max(0, predicted_value)  # Ensure non-negative

    def evaluate_with_prediction(self) -> Optional[ScalingDecision]:
        """Evaluate with predictive scaling"""
        # First check current metrics
        current_decision = self.evaluate()
        if current_decision:
            return current_decision

        # Then check predictions
        for policy in self.policies:
            if not policy["enabled"]:
                continue

            metric_name = policy["metric_name"]
            predicted_value = self.predict_metric(metric_name)

            if predicted_value is None:
                continue

            # Scale preemptively if prediction exceeds threshold
            if predicted_value > policy["threshold_up"]:
                target = math.ceil(
                    self.current_instances * policy["scale_up_factor"]
                )
                target = min(target, policy["max_instances"])

                if target > self.current_instances:
                    return ScalingDecision(
                        direction=ScalingDirection.SCALE_UP,
                        current_instances=self.current_instances,
                        target_instances=target,
                        reason=f"Predicted {metric_name} ({predicted_value:.2f}) > threshold ({policy['threshold_up']:.2f})",
                        metrics={f"predicted_{metric_name}": predicted_value},
                        policy_name=policy["name"],
                    )

        return None
