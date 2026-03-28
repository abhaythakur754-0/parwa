"""Quality Validator Module - Week 55, Builder 3"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"


@dataclass
class ValidationRule:
    name: str
    condition: Callable[[str], bool]
    threshold: float = 0.7
    description: str = ""


@dataclass
class ValidationResult:
    rule_name: str
    status: ValidationStatus
    score: float
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    overall_status: ValidationStatus
    results: List[ValidationResult] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.results if r.status == ValidationStatus.PASS)

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.results if r.status == ValidationStatus.FAIL)


class QualityValidator:
    def __init__(self):
        self.rules: Dict[str, ValidationRule] = {}
        self._setup_default_rules()

    def _setup_default_rules(self) -> None:
        self.add_rule(ValidationRule(
            name="min_length",
            condition=lambda r: len(r) >= 10,
            description="Response must be at least 10 characters",
        ))
        self.add_rule(ValidationRule(
            name="max_length",
            condition=lambda r: len(r) <= 10000,
            description="Response must not exceed 10000 characters",
        ))
        self.add_rule(ValidationRule(
            name="no_empty",
            condition=lambda r: len(r.strip()) > 0,
            description="Response must not be empty",
        ))

    def add_rule(self, rule: ValidationRule) -> None:
        self.rules[rule.name] = rule

    def remove_rule(self, name: str) -> bool:
        if name in self.rules:
            del self.rules[name]
            return True
        return False

    def validate(self, response: str, rules: Optional[List[str]] = None) -> PipelineResult:
        results = []
        rules_to_check = rules if rules else list(self.rules.keys())

        for rule_name in rules_to_check:
            rule = self.rules.get(rule_name)
            if not rule:
                continue

            try:
                passed = rule.condition(response)
                status = ValidationStatus.PASS if passed else ValidationStatus.FAIL
                results.append(ValidationResult(
                    rule_name=rule_name,
                    status=status,
                    score=1.0 if passed else 0.0,
                    message=rule.description,
                ))
            except Exception as e:
                results.append(ValidationResult(
                    rule_name=rule_name,
                    status=ValidationStatus.WARNING,
                    score=0.0,
                    message=f"Error: {str(e)}",
                ))

        overall = ValidationStatus.PASS if all(r.status == ValidationStatus.PASS for r in results) else ValidationStatus.FAIL
        return PipelineResult(overall_status=overall, results=results)


class ValidationPipeline:
    def __init__(self, name: str):
        self.name = name
        self.stages: List[QualityValidator] = []

    def add_stage(self, validator: QualityValidator) -> None:
        self.stages.append(validator)

    def run(self, response: str) -> PipelineResult:
        all_results = []
        for stage in self.stages:
            result = stage.validate(response)
            all_results.extend(result.results)

        overall = ValidationStatus.PASS if all(r.status == ValidationStatus.PASS for r in all_results) else ValidationStatus.FAIL
        return PipelineResult(overall_status=overall, results=all_results)
