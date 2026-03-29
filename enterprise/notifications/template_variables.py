# Template Variables - Week 48 Builder 4
# Variable substitution and management for templates

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, date
from enum import Enum
import json
import re
import uuid


class VariableType(Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    LIST = "list"
    OBJECT = "object"


@dataclass
class VariableDefinition:
    name: str = ""
    var_type: VariableType = VariableType.STRING
    description: str = ""
    required: bool = False
    default_value: Optional[Any] = None
    validation_regex: Optional[str] = None
    allowed_values: List[Any] = field(default_factory=list)
    transform: Optional[str] = None  # Name of transform to apply


@dataclass
class VariableContext:
    tenant_id: str = ""
    user_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    environment: str = "production"
    custom_vars: Dict[str, Any] = field(default_factory=dict)


class VariableManager:
    """Manages template variables and substitution"""

    def __init__(self):
        self._definitions: Dict[str, VariableDefinition] = {}
        self._transforms: Dict[str, Callable] = {}
        self._context_providers: Dict[str, Callable] = {}
        self._register_default_transforms()
        self._register_default_definitions()

    def _register_default_transforms(self) -> None:
        """Register built-in transforms"""
        self._transforms["upper"] = lambda x: str(x).upper()
        self._transforms["lower"] = lambda x: str(x).lower()
        self._transforms["capitalize"] = lambda x: str(x).capitalize()
        self._transforms["title"] = lambda x: str(x).title()
        self._transforms["strip"] = lambda x: str(x).strip()
        self._transforms["reverse"] = lambda x: str(x)[::-1]
        self._transforms["json"] = lambda x: json.dumps(x) if isinstance(x, (dict, list)) else str(x)
        self._transforms["date_format"] = self._format_date
        self._transforms["currency"] = lambda x: f"${float(x):.2f}" if x else "$0.00"
        self._transforms["percentage"] = lambda x: f"{float(x) * 100:.1f}%" if x else "0%"
        self._transforms["truncate"] = self._truncate

    def _format_date(self, value: Any, fmt: str = "%Y-%m-%d") -> str:
        """Format date/datetime value"""
        if isinstance(value, (datetime, date)):
            return value.strftime(fmt)
        return str(value)

    def _truncate(self, value: Any, length: int = 50) -> str:
        """Truncate string to specified length"""
        s = str(value)
        if len(s) <= length:
            return s
        return s[:length - 3] + "..."

    def _register_default_definitions(self) -> None:
        """Register default variable definitions"""
        defaults = [
            VariableDefinition(
                name="user.name",
                var_type=VariableType.STRING,
                description="User's full name",
                required=True
            ),
            VariableDefinition(
                name="user.email",
                var_type=VariableType.STRING,
                description="User's email address",
                required=True,
                validation_regex=r'^[\w\.-]+@[\w\.-]+\.\w+$'
            ),
            VariableDefinition(
                name="user.first_name",
                var_type=VariableType.STRING,
                description="User's first name"
            ),
            VariableDefinition(
                name="user.last_name",
                var_type=VariableType.STRING,
                description="User's last name"
            ),
            VariableDefinition(
                name="tenant.name",
                var_type=VariableType.STRING,
                description="Tenant/company name"
            ),
            VariableDefinition(
                name="tenant.id",
                var_type=VariableType.STRING,
                description="Tenant ID"
            ),
            VariableDefinition(
                name="timestamp",
                var_type=VariableType.DATETIME,
                description="Current timestamp"
            ),
            VariableDefinition(
                name="date",
                var_type=VariableType.DATE,
                description="Current date"
            )
        ]

        for definition in defaults:
            self._definitions[definition.name] = definition

    def register_definition(self, definition: VariableDefinition) -> None:
        """Register a variable definition"""
        self._definitions[definition.name] = definition

    def register_transform(self, name: str, func: Callable) -> None:
        """Register a custom transform"""
        self._transforms[name] = func

    def register_context_provider(self, name: str, provider: Callable) -> None:
        """Register a context provider function"""
        self._context_providers[name] = provider

    def get_definition(self, name: str) -> Optional[VariableDefinition]:
        """Get variable definition by name"""
        return self._definitions.get(name)

    def get_all_definitions(self) -> List[VariableDefinition]:
        """Get all registered variable definitions"""
        return list(self._definitions.values())

    def validate_variable(
        self,
        name: str,
        value: Any
    ) -> Dict[str, Any]:
        """Validate a variable against its definition"""
        definition = self._definitions.get(name)
        if not definition:
            return {"valid": True, "warnings": [f"Unknown variable: {name}"]}

        errors = []
        warnings = []

        # Check type
        if not self._check_type(value, definition.var_type):
            errors.append(f"Invalid type for {name}: expected {definition.var_type.value}")

        # Check regex validation
        if definition.validation_regex and isinstance(value, str):
            if not re.match(definition.validation_regex, value):
                errors.append(f"Invalid format for {name}")

        # Check allowed values
        if definition.allowed_values and value not in definition.allowed_values:
            errors.append(f"Invalid value for {name}: must be one of {definition.allowed_values}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    def _check_type(self, value: Any, var_type: VariableType) -> bool:
        """Check if value matches expected type"""
        if value is None:
            return True

        type_checks = {
            VariableType.STRING: lambda v: isinstance(v, str),
            VariableType.NUMBER: lambda v: isinstance(v, (int, float)),
            VariableType.BOOLEAN: lambda v: isinstance(v, bool),
            VariableType.DATE: lambda v: isinstance(v, (date, str)),
            VariableType.DATETIME: lambda v: isinstance(v, (datetime, str)),
            VariableType.LIST: lambda v: isinstance(v, list),
            VariableType.OBJECT: lambda v: isinstance(v, dict)
        }

        return type_checks.get(var_type, lambda v: True)(value)

    def apply_transform(
        self,
        value: Any,
        transform_name: str,
        *args
    ) -> Any:
        """Apply a transform to a value"""
        transform = self._transforms.get(transform_name)
        if not transform:
            return value

        try:
            if args:
                return transform(value, *args)
            return transform(value)
        except Exception:
            return value

    def build_context(
        self,
        tenant_id: str,
        user_id: str,
        custom_vars: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build a complete variable context"""
        now = datetime.utcnow()
        context = {
            "tenant": {
                "id": tenant_id,
                "name": ""
            },
            "user": {
                "id": user_id,
                "name": "",
                "email": "",
                "first_name": "",
                "last_name": ""
            },
            "timestamp": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "datetime": now.strftime("%Y-%m-%d %H:%M:%S")
        }

        # Add custom variables
        if custom_vars:
            context.update(custom_vars)

        # Run context providers
        for name, provider in self._context_providers.items():
            try:
                context[name] = provider(tenant_id, user_id)
            except Exception:
                pass

        return context

    def merge_contexts(
        self,
        base: Dict[str, Any],
        override: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge two contexts, with override taking precedence"""
        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = {**result[key], **value}
            else:
                result[key] = value

        return result

    def extract_variables_from_template(
        self,
        template: str
    ) -> List[Dict[str, Any]]:
        """Extract all variables from a template string"""
        pattern = re.compile(r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)(?:\|([a-zA-Z_]+))?\s*\}\}')
        variables = []

        for match in pattern.finditer(template):
            var_name = match.group(1)
            transform = match.group(2)

            var_info = {
                "name": var_name,
                "full_match": match.group(0),
                "definition": self._definitions.get(var_name)
            }

            if transform:
                var_info["transform"] = transform

            variables.append(var_info)

        return variables

    def get_required_variables(self, template: str) -> List[str]:
        """Get list of required variables from a template"""
        variables = self.extract_variables_from_template(template)
        required = []

        for var in variables:
            definition = var.get("definition")
            if definition and definition.required:
                required.append(var["name"])

        return required
