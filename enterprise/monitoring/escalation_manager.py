"""
Escalation Manager Module - Week 53, Builder 3
Incident escalation engine
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import logging

logger = logging.getLogger(__name__)


class EscalationLevel(Enum):
    """Escalation levels"""
    L1 = "l1"  # First line support
    L2 = "l2"  # Second line
    L3 = "l3"  # Third line
    MANAGEMENT = "management"
    EXECUTIVE = "executive"


class EscalationTrigger(Enum):
    """Escalation triggers"""
    TIMEOUT = "timeout"
    SEVERITY = "severity"
    MANUAL = "manual"
    REPEAT = "repeat"


@dataclass
class EscalationRule:
    """Escalation rule definition"""
    name: str
    trigger: EscalationTrigger
    level_from: EscalationLevel
    level_to: EscalationLevel
    delay_seconds: int = 0
    conditions: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class EscalationEvent:
    """Escalation event"""
    incident_id: str
    from_level: EscalationLevel
    to_level: EscalationLevel
    reason: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    triggered_by: str = ""


class EscalationManager:
    """
    Manages incident escalation policies.
    """

    def __init__(self):
        self.rules: List[EscalationRule] = []
        self.escalations: List[EscalationEvent] = []
        self._current_levels: Dict[str, EscalationLevel] = {}
        self._escalation_times: Dict[str, datetime] = {}
        self._callbacks: List[Callable] = []
        self._setup_default_rules()

    def _setup_default_rules(self) -> None:
        """Setup default escalation rules"""
        # Timeout-based escalations
        self.add_rule(EscalationRule(
            name="l1_to_l2_timeout",
            trigger=EscalationTrigger.TIMEOUT,
            level_from=EscalationLevel.L1,
            level_to=EscalationLevel.L2,
            delay_seconds=900,  # 15 minutes
        ))

        self.add_rule(EscalationRule(
            name="l2_to_l3_timeout",
            trigger=EscalationTrigger.TIMEOUT,
            level_from=EscalationLevel.L2,
            level_to=EscalationLevel.L3,
            delay_seconds=1800,  # 30 minutes
        ))

        self.add_rule(EscalationRule(
            name="l3_to_management_timeout",
            trigger=EscalationTrigger.TIMEOUT,
            level_from=EscalationLevel.L3,
            level_to=EscalationLevel.MANAGEMENT,
            delay_seconds=3600,  # 1 hour
        ))

        # Severity-based escalations
        self.add_rule(EscalationRule(
            name="critical_auto_l3",
            trigger=EscalationTrigger.SEVERITY,
            level_from=EscalationLevel.L1,
            level_to=EscalationLevel.L3,
            conditions={"severity": "critical"},
        ))

    def add_rule(self, rule: EscalationRule) -> None:
        """Add an escalation rule"""
        self.rules.append(rule)
        logger.info(f"Added escalation rule: {rule.name}")

    def remove_rule(self, name: str) -> bool:
        """Remove an escalation rule"""
        for i, rule in enumerate(self.rules):
            if rule.name == name:
                self.rules.pop(i)
                return True
        return False

    def start_tracking(
        self,
        incident_id: str,
        initial_level: EscalationLevel = EscalationLevel.L1,
    ) -> None:
        """Start tracking an incident for escalation"""
        self._current_levels[incident_id] = initial_level
        self._escalation_times[incident_id] = datetime.utcnow()

    def check_escalation(
        self,
        incident_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[EscalationEvent]:
        """Check if incident should be escalated"""
        current_level = self._current_levels.get(incident_id)
        if not current_level:
            return None

        escalation_time = self._escalation_times.get(incident_id)
        if not escalation_time:
            return None

        context = context or {}
        now = datetime.utcnow()
        elapsed = (now - escalation_time).total_seconds()

        for rule in self.rules:
            if not rule.enabled:
                continue

            if rule.level_from != current_level:
                continue

            should_escalate = False

            if rule.trigger == EscalationTrigger.TIMEOUT:
                if elapsed >= rule.delay_seconds:
                    should_escalate = True

            elif rule.trigger == EscalationTrigger.SEVERITY:
                severity = context.get("severity", "")
                if rule.conditions.get("severity") == severity:
                    should_escalate = True

            elif rule.trigger == EscalationTrigger.REPEAT:
                repeat_count = context.get("repeat_count", 0)
                if repeat_count >= rule.conditions.get("repeat_threshold", 3):
                    should_escalate = True

            if should_escalate:
                return self._escalate(incident_id, rule)

        return None

    def _escalate(
        self,
        incident_id: str,
        rule: EscalationRule,
    ) -> EscalationEvent:
        """Perform escalation"""
        from_level = self._current_levels.get(incident_id, EscalationLevel.L1)

        event = EscalationEvent(
            incident_id=incident_id,
            from_level=from_level,
            to_level=rule.level_to,
            reason=f"Rule triggered: {rule.name}",
        )

        self._current_levels[incident_id] = rule.level_to
        self._escalation_times[incident_id] = datetime.utcnow()
        self.escalations.append(event)

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Escalation callback error: {e}")

        logger.info(
            f"Escalated {incident_id} from {from_level.value} to {rule.level_to.value}"
        )

        return event

    def manual_escalate(
        self,
        incident_id: str,
        to_level: EscalationLevel,
        reason: str = "",
        user: str = "",
    ) -> EscalationEvent:
        """Manually escalate an incident"""
        from_level = self._current_levels.get(incident_id, EscalationLevel.L1)

        event = EscalationEvent(
            incident_id=incident_id,
            from_level=from_level,
            to_level=to_level,
            reason=reason,
            triggered_by=user,
        )

        self._current_levels[incident_id] = to_level
        self._escalation_times[incident_id] = datetime.utcnow()
        self.escalations.append(event)

        return event

    def get_current_level(self, incident_id: str) -> Optional[EscalationLevel]:
        """Get current escalation level"""
        return self._current_levels.get(incident_id)

    def get_escalation_history(
        self,
        incident_id: str,
    ) -> List[EscalationEvent]:
        """Get escalation history for incident"""
        return [
            e for e in self.escalations
            if e.incident_id == incident_id
        ]

    def add_callback(self, callback: Callable) -> None:
        """Add escalation callback"""
        self._callbacks.append(callback)

    def get_statistics(self) -> Dict[str, Any]:
        """Get escalation statistics"""
        return {
            "total_escalations": len(self.escalations),
            "by_level": {
                level.value: len([
                    e for e in self.escalations
                    if e.to_level == level
                ])
                for level in EscalationLevel
            },
            "rules_count": len(self.rules),
            "active_rules": len([r for r in self.rules if r.enabled]),
        }

    def reset(self, incident_id: str) -> None:
        """Reset escalation tracking for incident"""
        self._current_levels.pop(incident_id, None)
        self._escalation_times.pop(incident_id, None)
