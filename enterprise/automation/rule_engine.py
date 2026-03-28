"""Rule Engine Module - Week 57, Builder 2"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import logging
import re

logger = logging.getLogger(__name__)


class ConditionOperator(Enum):
    EQ = "=="
    NE = "!="
    GT = ">"
    GE = ">="
    LT = "<"
    LE = "<="
    CONTAINS = "contains"
    MATCHES = "matches"
    IN = "in"


@dataclass
class Condition:
    field: str
    operator: ConditionOperator
    value: Any

    def evaluate(self, context: Dict) -> bool:
        actual = context.get(self.field)
        if actual is None:
            return False

        if self.operator == ConditionOperator.EQ:
            return actual == self.value
        elif self.operator == ConditionOperator.NE:
            return actual != self.value
        elif self.operator == ConditionOperator.GT:
            return actual > self.value
        elif self.operator == ConditionOperator.GE:
            return actual >= self.value
        elif self.operator == ConditionOperator.LT:
            return actual < self.value
        elif self.operator == ConditionOperator.LE:
            return actual <= self.value
        elif self.operator == ConditionOperator.CONTAINS:
            return self.value in str(actual)
        elif self.operator == ConditionOperator.MATCHES:
            return bool(re.match(self.value, str(actual)))
        elif self.operator == ConditionOperator.IN:
            return actual in self.value
        return False


@dataclass
class Rule:
    name: str
    conditions: List[Condition]
    actions: List[Callable]
    priority: int = 0
    enabled: bool = True


class RuleEngine:
    def __init__(self):
        self._rules: Dict[str, Rule] = {}

    def add_rule(self, rule: Rule) -> None:
        self._rules[rule.name] = rule

    def remove_rule(self, name: str) -> bool:
        return self._rules.pop(name, None) is not None

    def evaluate(self, context: Dict) -> List[str]:
        matched = []
        for rule in sorted(self._rules.values(), key=lambda r: -r.priority):
            if not rule.enabled:
                continue
            if all(c.evaluate(context) for c in rule.conditions):
                matched.append(rule.name)
        return matched

    def execute(self, context: Dict) -> Dict[str, Any]:
        results = {}
        matched = self.evaluate(context)
        for name in matched:
            rule = self._rules[name]
            for action in rule.actions:
                try:
                    results[name] = action(context)
                except Exception as e:
                    results[name] = {"error": str(e)}
        return results


class ConditionEvaluator:
    def __init__(self):
        self._custom_operators: Dict[str, Callable] = {}

    def register_operator(self, name: str, func: Callable) -> None:
        self._custom_operators[name] = func

    def evaluate_all(self, conditions: List[Condition], context: Dict, logic: str = "and") -> bool:
        results = [c.evaluate(context) for c in conditions]
        if logic == "and":
            return all(results)
        elif logic == "or":
            return any(results)
        return False


class ActionExecutor:
    def __init__(self):
        self._actions: Dict[str, Callable] = {}
        self._history: List[Dict] = []

    def register(self, name: str, action: Callable) -> None:
        self._actions[name] = action

    def execute(self, name: str, context: Dict = None) -> Any:
        action = self._actions.get(name)
        if not action:
            raise ValueError(f"Action not found: {name}")

        result = action(**(context or {}))
        self._history.append({
            "action": name,
            "timestamp": datetime.utcnow(),
            "context": context
        })
        return result

    def get_history(self, limit: int = 100) -> List[Dict]:
        return self._history[-limit:]
