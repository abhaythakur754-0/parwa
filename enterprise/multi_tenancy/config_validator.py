"""
Configuration Validator

Validates tenant configurations against defined rules.
"""

from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import re
import logging

logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    """Validation severity levels"""
    ERROR = "error"  # Must be fixed
    WARNING = "warning"  # Should be reviewed
    INFO = "info"  # Informational


class ValidationRuleType(str, Enum):
    """Types of validation rules"""
    REQUIRED = "required"
    TYPE = "type"
    RANGE = "range"
    PATTERN = "pattern"
    ENUM = "enum"
    CUSTOM = "custom"


@dataclass
class ValidationRule:
    """A validation rule"""
    rule_id: str
    key_pattern: str  # Regex pattern for matching keys
    rule_type: ValidationRuleType
    severity: ValidationSeverity = ValidationSeverity.ERROR
    message: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    custom_validator: Optional[Callable[[Any], bool]] = None


@dataclass
class ValidationResult:
    """Result of configuration validation"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)
    validated_keys: List[str] = field(default_factory=list)


class ConfigValidator:
    """
    Validates tenant configurations.

    Features:
    - Type validation
    - Range validation
    - Pattern matching
    - Required field checks
    - Custom validators
    """

    def __init__(self):
        # Validation rules
        self._rules: List[ValidationRule] = []

        # Initialize default rules
        self._initialize_default_rules()

    def _initialize_default_rules(self) -> None:
        """Initialize default validation rules"""
        # Type rules
        self.add_rule(ValidationRule(
            rule_id="type_integer",
            key_pattern=r"^limits\.",
            rule_type=ValidationRuleType.TYPE,
            message="Must be an integer",
            parameters={"expected_type": "int"}
        ))

        self.add_rule(ValidationRule(
            rule_id="type_float",
            key_pattern=r"^ai\.temperature",
            rule_type=ValidationRuleType.TYPE,
            message="Must be a float",
            parameters={"expected_type": "float"}
        ))

        self.add_rule(ValidationRule(
            rule_id="type_boolean",
            key_pattern=r"^(features|notifications|security)\.",
            rule_type=ValidationRuleType.TYPE,
            message="Must be a boolean",
            parameters={"expected_type": "bool"}
        ))

        # Range rules
        self.add_rule(ValidationRule(
            rule_id="range_temperature",
            key_pattern=r"^ai\.temperature$",
            rule_type=ValidationRuleType.RANGE,
            message="Temperature must be between 0 and 2",
            parameters={"min": 0, "max": 2}
        ))

        self.add_rule(ValidationRule(
            rule_id="range_max_tokens",
            key_pattern=r"^ai\.max_tokens$",
            rule_type=ValidationRuleType.RANGE,
            message="Max tokens must be between 1 and 32000",
            parameters={"min": 1, "max": 32000}
        ))

        self.add_rule(ValidationRule(
            rule_id="range_positive",
            key_pattern=r"^limits\.",
            rule_type=ValidationRuleType.RANGE,
            message="Must be a positive number",
            parameters={"min": 1}
        ))

        self.add_rule(ValidationRule(
            rule_id="range_session_timeout",
            key_pattern=r"^security\.session_timeout_minutes$",
            rule_type=ValidationRuleType.RANGE,
            message="Session timeout must be between 5 and 1440 minutes",
            parameters={"min": 5, "max": 1440}
        ))

        # Pattern rules
        self.add_rule(ValidationRule(
            rule_id="pattern_model",
            key_pattern=r"^ai\.model$",
            rule_type=ValidationRuleType.PATTERN,
            message="Invalid model name",
            parameters={"pattern": r"^(gpt-4|gpt-3\.5-turbo|claude-|custom_)"}
        ))

    def add_rule(self, rule: ValidationRule) -> None:
        """Add a validation rule"""
        self._rules.append(rule)
        logger.debug(f"Added validation rule: {rule.rule_id}")

    def validate(
        self,
        config: Dict[str, Any]
    ) -> ValidationResult:
        """Validate a configuration dictionary"""
        result = ValidationResult(is_valid=True)

        for key, value in config.items():
            result.validated_keys.append(key)

            for rule in self._get_applicable_rules(key):
                rule_result = self._apply_rule(rule, key, value)

                if not rule_result["valid"]:
                    if rule.severity == ValidationSeverity.ERROR:
                        result.errors.append(f"{key}: {rule.message}")
                        result.is_valid = False
                    elif rule.severity == ValidationSeverity.WARNING:
                        result.warnings.append(f"{key}: {rule.message}")
                    else:
                        result.info.append(f"{key}: {rule.message}")

        return result

    def _get_applicable_rules(self, key: str) -> List[ValidationRule]:
        """Get rules that apply to a key"""
        return [
            rule for rule in self._rules
            if re.match(rule.key_pattern, key)
        ]

    def _apply_rule(
        self,
        rule: ValidationRule,
        key: str,
        value: Any
    ) -> Dict[str, Any]:
        """Apply a validation rule"""
        result = {"valid": True}

        if rule.rule_type == ValidationRuleType.REQUIRED:
            result["valid"] = value is not None and value != ""

        elif rule.rule_type == ValidationRuleType.TYPE:
            expected_type = rule.parameters.get("expected_type")
            result["valid"] = self._check_type(value, expected_type)

        elif rule.rule_type == ValidationRuleType.RANGE:
            min_val = rule.parameters.get("min")
            max_val = rule.parameters.get("max")

            if isinstance(value, (int, float)):
                if min_val is not None and value < min_val:
                    result["valid"] = False
                if max_val is not None and value > max_val:
                    result["valid"] = False
            else:
                result["valid"] = False

        elif rule.rule_type == ValidationRuleType.PATTERN:
            pattern = rule.parameters.get("pattern")
            if pattern:
                result["valid"] = bool(re.match(pattern, str(value)))
            else:
                result["valid"] = True

        elif rule.rule_type == ValidationRuleType.ENUM:
            allowed = rule.parameters.get("allowed_values", [])
            result["valid"] = value in allowed

        elif rule.rule_type == ValidationRuleType.CUSTOM:
            if rule.custom_validator:
                result["valid"] = rule.custom_validator(value)

        return result

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type"""
        type_map = {
            "str": str,
            "string": str,
            "int": int,
            "integer": int,
            "float": (int, float),
            "bool": bool,
            "boolean": bool,
            "list": list,
            "dict": dict,
            "json": (dict, list, str, int, float, bool, type(None))
        }

        expected = type_map.get(expected_type)
        if expected is None:
            return True  # Unknown type, skip check

        return isinstance(value, expected)

    def validate_key(
        self,
        key: str,
        value: Any
    ) -> ValidationResult:
        """Validate a single key-value pair"""
        return self.validate({key: value})

    def validate_value(
        self,
        value: Any,
        expected_type: Optional[str] = None,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
        pattern: Optional[str] = None,
        allowed_values: Optional[List[Any]] = None
    ) -> ValidationResult:
        """Validate a value with custom parameters"""
        result = ValidationResult(is_valid=True)

        # Type check
        if expected_type and not self._check_type(value, expected_type):
            result.errors.append(f"Expected type {expected_type}, got {type(value).__name__}")
            result.is_valid = False

        # Range check
        if isinstance(value, (int, float)):
            if min_val is not None and value < min_val:
                result.errors.append(f"Value {value} is below minimum {min_val}")
                result.is_valid = False
            if max_val is not None and value > max_val:
                result.errors.append(f"Value {value} exceeds maximum {max_val}")
                result.is_valid = False

        # Pattern check
        if pattern and not re.match(pattern, str(value)):
            result.errors.append(f"Value does not match pattern {pattern}")
            result.is_valid = False

        # Enum check
        if allowed_values and value not in allowed_values:
            result.errors.append(f"Value must be one of: {allowed_values}")
            result.is_valid = False

        return result

    def get_rules_for_key(self, key: str) -> List[ValidationRule]:
        """Get all rules applicable to a key"""
        return self._get_applicable_rules(key)

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a validation rule"""
        for i, rule in enumerate(self._rules):
            if rule.rule_id == rule_id:
                del self._rules[i]
                return True
        return False

    def get_all_rules(self) -> List[ValidationRule]:
        """Get all validation rules"""
        return self._rules.copy()
