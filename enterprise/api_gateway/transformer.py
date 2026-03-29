"""Request/Response Transformer"""
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import logging
import json
import copy

logger = logging.getLogger(__name__)

class TransformPhase(str, Enum):
    REQUEST = "request"
    RESPONSE = "response"
    BOTH = "both"

@dataclass
class TransformRule:
    name: str
    phase: TransformPhase
    transformer: Callable[[Dict], Dict]
    priority: int = 0
    enabled: bool = True

class Transformer:
    def __init__(self):
        self._rules: List[TransformRule] = []
        self._metrics = {"requests_transformed": 0, "responses_transformed": 0, "errors": 0}

    def add_rule(self, name: str, transformer: Callable[[Dict], Dict], phase: TransformPhase = TransformPhase.BOTH, priority: int = 0) -> None:
        rule = TransformRule(name=name, phase=phase, transformer=transformer, priority=priority)
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def transform_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        transformed = copy.deepcopy(request)
        for rule in self._rules:
            if rule.enabled and rule.phase in [TransformPhase.REQUEST, TransformPhase.BOTH]:
                try:
                    transformed = rule.transformer(transformed)
                except Exception as e:
                    self._metrics["errors"] += 1
                    logger.error(f"Transform error in {rule.name}: {e}")
        self._metrics["requests_transformed"] += 1
        return transformed

    def transform_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        transformed = copy.deepcopy(response)
        for rule in self._rules:
            if rule.enabled and rule.phase in [TransformPhase.RESPONSE, TransformPhase.BOTH]:
                try:
                    transformed = rule.transformer(transformed)
                except Exception as e:
                    self._metrics["errors"] += 1
                    logger.error(f"Transform error in {rule.name}: {e}")
        self._metrics["responses_transformed"] += 1
        return transformed

    def add_header_transform(self, header_name: str, header_value: str, phase: TransformPhase = TransformPhase.REQUEST) -> None:
        def add_header(data: Dict) -> Dict:
            if "headers" not in data:
                data["headers"] = {}
            data["headers"][header_name] = header_value
            return data
        self.add_rule(f"add_header_{header_name}", add_header, phase)

    def remove_header_transform(self, header_name: str, phase: TransformPhase = TransformPhase.BOTH) -> None:
        def remove_header(data: Dict) -> Dict:
            if "headers" in data and header_name in data["headers"]:
                del data["headers"][header_name]
            return data
        self.add_rule(f"remove_header_{header_name}", remove_header, phase)

    def add_field_transform(self, field_name: str, field_value: Any, phase: TransformPhase = TransformPhase.REQUEST) -> None:
        def add_field(data: Dict) -> Dict:
            if "body" not in data:
                data["body"] = {}
            if isinstance(data["body"], dict):
                data["body"][field_name] = field_value
            return data
        self.add_rule(f"add_field_{field_name}", add_field, phase)

    def remove_rule(self, name: str) -> bool:
        for i, rule in enumerate(self._rules):
            if rule.name == name:
                del self._rules[i]
                return True
        return False

    def enable_rule(self, name: str) -> bool:
        for rule in self._rules:
            if rule.name == name:
                rule.enabled = True
                return True
        return False

    def disable_rule(self, name: str) -> bool:
        for rule in self._rules:
            if rule.name == name:
                rule.enabled = False
                return True
        return False

    def get_rules(self) -> List[Dict[str, Any]]:
        return [{"name": r.name, "phase": r.phase.value, "priority": r.priority, "enabled": r.enabled} for r in self._rules]

    def get_metrics(self) -> Dict[str, Any]:
        return {**self._metrics, "total_rules": len(self._rules), "enabled_rules": sum(1 for r in self._rules if r.enabled)}

    def clear_rules(self) -> int:
        count = len(self._rules)
        self._rules.clear()
        return count
