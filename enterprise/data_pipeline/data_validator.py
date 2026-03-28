"""Data Validator Module - Week 56, Builder 2"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import logging
import re

logger = logging.getLogger(__name__)


class RuleType(Enum):
    REQUIRED = "required"
    TYPE = "type"
    RANGE = "range"
    PATTERN = "pattern"
    CUSTOM = "custom"
    MIN_LENGTH = "min_length"
    MAX_LENGTH = "max_length"


@dataclass
class ValidationRule:
    field: str
    rule_type: RuleType
    params: Dict[str, Any] = field(default_factory=dict)
    message: str = ""


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    validated_at: datetime = field(default_factory=datetime.utcnow)


class DataValidator:
    def __init__(self):
        self._rules: List[ValidationRule] = []
        self._custom_validators: Dict[str, Callable] = {}

    def add_rule(self, rule: ValidationRule) -> None:
        self._rules.append(rule)

    def add_custom_validator(self, name: str, validator: Callable) -> None:
        self._custom_validators[name] = validator

    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        errors = []
        warnings = []

        for rule in self._rules:
            field_value = data.get(rule.field)
            error = self._apply_rule(rule, field_value, data)
            if error:
                errors.append(error)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def _apply_rule(self, rule: ValidationRule, value: Any, data: Dict) -> Optional[str]:
        if rule.rule_type == RuleType.REQUIRED:
            if value is None or value == "":
                return rule.message or f"Field {rule.field} is required"

        elif rule.rule_type == RuleType.TYPE:
            expected_type = rule.params.get("type", str)
            if value is not None and not isinstance(value, expected_type):
                return rule.message or f"Field {rule.field} must be {expected_type}"

        elif rule.rule_type == RuleType.RANGE:
            min_val = rule.params.get("min")
            max_val = rule.params.get("max")
            if value is not None:
                if min_val is not None and value < min_val:
                    return f"Field {rule.field} below minimum {min_val}"
                if max_val is not None and value > max_val:
                    return f"Field {rule.field} exceeds maximum {max_val}"

        elif rule.rule_type == RuleType.PATTERN:
            pattern = rule.params.get("pattern", "")
            if value and not re.match(pattern, str(value)):
                return rule.message or f"Field {rule.field} doesn't match pattern"

        elif rule.rule_type == RuleType.MIN_LENGTH:
            min_len = rule.params.get("length", 0)
            if value and len(str(value)) < min_len:
                return f"Field {rule.field} below min length {min_len}"

        elif rule.rule_type == RuleType.MAX_LENGTH:
            max_len = rule.params.get("length", 1000)
            if value and len(str(value)) > max_len:
                return f"Field {rule.field} exceeds max length {max_len}"

        elif rule.rule_type == RuleType.CUSTOM:
            validator_name = rule.params.get("validator")
            if validator_name and validator_name in self._custom_validators:
                if not self._custom_validators[validator_name](value, data):
                    return rule.message or f"Custom validation failed for {rule.field}"

        return None

    def clear_rules(self) -> None:
        self._rules.clear()


@dataclass
class SchemaField:
    name: str
    type: type
    required: bool = True
    constraints: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SchemaDefinition:
    name: str
    fields: List[SchemaField] = field(default_factory=list)
    version: str = "1.0"

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "version": self.version,
            "fields": [{"name": f.name, "type": f.type.__name__, "required": f.required} for f in self.fields]
        }


class SchemaManager:
    def __init__(self):
        self._schemas: Dict[str, SchemaDefinition] = {}

    def register(self, schema: SchemaDefinition) -> None:
        self._schemas[schema.name] = schema

    def get(self, name: str) -> Optional[SchemaDefinition]:
        return self._schemas.get(name)

    def validate(self, schema_name: str, data: Dict) -> ValidationResult:
        schema = self._schemas.get(schema_name)
        if not schema:
            return ValidationResult(is_valid=False, errors=[f"Schema not found: {schema_name}"])

        validator = DataValidator()
        for field in schema.fields:
            validator.add_rule(ValidationRule(
                field=field.name,
                rule_type=RuleType.REQUIRED if field.required else RuleType.TYPE,
                params={"type": field.type}
            ))

        return validator.validate(data)

    def list_schemas(self) -> List[str]:
        return list(self._schemas.keys())


class DataCleaner:
    def __init__(self):
        self._rules: List[Dict] = []

    def add_rule(self, field: str, operation: str, params: Dict = None) -> None:
        self._rules.append({"field": field, "operation": operation, "params": params or {}})

    def clean(self, data: Dict[str, Any]) -> Dict[str, Any]:
        result = data.copy()

        for rule in self._rules:
            field = rule["field"]
            op = rule["operation"]
            params = rule["params"]

            if field not in result:
                continue

            if op == "trim":
                if isinstance(result[field], str):
                    result[field] = result[field].strip()

            elif op == "normalize":
                if isinstance(result[field], str):
                    result[field] = result[field].lower().strip()

            elif op == "fill":
                if result[field] is None:
                    result[field] = params.get("default")

            elif op == "drop":
                if result[field] is None or result[field] == "":
                    del result[field]

            elif op == "transform":
                func = params.get("function")
                if func and callable(func):
                    result[field] = func(result[field])

        return result

    def clean_batch(self, data_list: List[Dict]) -> List[Dict]:
        return [self.clean(item) for item in data_list]
