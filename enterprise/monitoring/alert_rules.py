"""
Alert Rules Module - Week 53, Builder 2
Alert rules engine for monitoring
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import logging
import re

logger = logging.getLogger(__name__)


class ComparisonOperator(Enum):
    """Comparison operators"""
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    EQ = "=="
    NEQ = "!="


class RuleState(Enum):
    """Rule state"""
    IDLE = "idle"
    FIRING = "firing"
    PENDING = "pending"


@dataclass
class AlertRule:
    """Alert rule definition"""
    name: str
    expression: str
    severity: str
    duration_seconds: int = 0
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    state: RuleState = RuleState.IDLE
    last_evaluated: Optional[datetime] = None
    firing_since: Optional[datetime] = None
    evaluation_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "expression": self.expression,
            "severity": self.severity,
            "duration_seconds": self.duration_seconds,
            "enabled": self.enabled,
            "state": self.state.value,
        }


@dataclass
class RuleResult:
    """Result of rule evaluation"""
    rule_name: str
    is_firing: bool
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    message: str = ""


class AlertRuleEngine:
    """
    Engine for evaluating alert rules.
    """

    def __init__(self):
        self.rules: Dict[str, AlertRule] = {}
        self._evaluators: Dict[str, Callable] = {}
        self._setup_default_evaluators()

    def _setup_default_evaluators(self) -> None:
        """Setup default metric evaluators"""
        pass  # Evaluators registered externally

    def add_rule(
        self,
        name: str,
        expression: str,
        severity: str = "warning",
        duration_seconds: int = 0,
        labels: Optional[Dict[str, str]] = None,
        annotations: Optional[Dict[str, str]] = None,
    ) -> AlertRule:
        """Add an alert rule"""
        rule = AlertRule(
            name=name,
            expression=expression,
            severity=severity,
            duration_seconds=duration_seconds,
            labels=labels or {},
            annotations=annotations or {},
        )
        self.rules[name] = rule
        logger.info(f"Added alert rule: {name}")
        return rule

    def remove_rule(self, name: str) -> bool:
        """Remove an alert rule"""
        if name in self.rules:
            del self.rules[name]
            return True
        return False

    def enable_rule(self, name: str) -> bool:
        """Enable a rule"""
        rule = self.rules.get(name)
        if rule:
            rule.enabled = True
            return True
        return False

    def disable_rule(self, name: str) -> bool:
        """Disable a rule"""
        rule = self.rules.get(name)
        if rule:
            rule.enabled = False
            return True
        return False

    def register_evaluator(
        self,
        metric_name: str,
        evaluator: Callable[[], float],
    ) -> None:
        """Register a metric evaluator"""
        self._evaluators[metric_name] = evaluator

    def evaluate(
        self,
        rule_name: str,
        metrics: Optional[Dict[str, float]] = None,
    ) -> Optional[RuleResult]:
        """Evaluate a single rule"""
        rule = self.rules.get(rule_name)
        if not rule or not rule.enabled:
            return None

        rule.last_evaluated = datetime.utcnow()
        rule.evaluation_count += 1

        # Parse and evaluate expression
        try:
            is_firing, value = self._evaluate_expression(
                rule.expression,
                metrics or {},
            )
        except Exception as e:
            logger.error(f"Rule evaluation error: {e}")
            return RuleResult(
                rule_name=rule_name,
                is_firing=False,
                value=0,
                message=f"Evaluation error: {e}",
            )

        # Handle duration
        if is_firing:
            if rule.state == RuleState.IDLE:
                rule.state = RuleState.PENDING
                rule.firing_since = datetime.utcnow()
            elif rule.state == RuleState.PENDING:
                if rule.duration_seconds > 0:
                    elapsed = (datetime.utcnow() - rule.firing_since).total_seconds()
                    if elapsed >= rule.duration_seconds:
                        rule.state = RuleState.FIRING
                else:
                    rule.state = RuleState.FIRING
        else:
            rule.state = RuleState.IDLE
            rule.firing_since = None

        return RuleResult(
            rule_name=rule_name,
            is_firing=rule.state == RuleState.FIRING,
            value=value,
        )

    def _evaluate_expression(
        self,
        expression: str,
        metrics: Dict[str, float],
    ) -> tuple:
        """Evaluate an alert expression"""
        # Simple expression parser: metric operator value
        # Examples: "cpu > 80", "memory >= 90", "errors > 100"

        operators = [">=", "<=", ">", "<", "==", "!="]
        op = None
        for o in operators:
            if o in expression:
                op = o
                break

        if not op:
            return False, 0

        parts = expression.split(op)
        if len(parts) != 2:
            return False, 0

        metric_name = parts[0].strip()
        threshold = float(parts[1].strip())

        # Get metric value
        value = metrics.get(metric_name, 0)
        if metric_name in self._evaluators:
            value = self._evaluators[metric_name]()

        # Compare
        if op == ">":
            return value > threshold, value
        elif op == "<":
            return value < threshold, value
        elif op == ">=":
            return value >= threshold, value
        elif op == "<=":
            return value <= threshold, value
        elif op == "==":
            return value == threshold, value
        elif op == "!=":
            return value != threshold, value

        return False, value

    def evaluate_all(
        self,
        metrics: Optional[Dict[str, float]] = None,
    ) -> List[RuleResult]:
        """Evaluate all rules"""
        results = []
        for rule_name in self.rules:
            result = self.evaluate(rule_name, metrics)
            if result:
                results.append(result)
        return results

    def get_firing_rules(self) -> List[AlertRule]:
        """Get all firing rules"""
        return [
            r for r in self.rules.values()
            if r.state == RuleState.FIRING
        ]

    def get_rule(self, name: str) -> Optional[AlertRule]:
        """Get a rule by name"""
        return self.rules.get(name)

    def get_all_rules(self) -> List[AlertRule]:
        """Get all rules"""
        return list(self.rules.values())
