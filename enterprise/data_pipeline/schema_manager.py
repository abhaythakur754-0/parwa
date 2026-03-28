"""
Schema Management System for Week 56 Advanced Data Pipelines.
Provides schema definition, validation, and versioning support.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type, Union
from enum import Enum
from datetime import datetime
import copy

from .data_validator import (
    DataValidator, 
    ValidationRule, 
    ValidationResult, 
    RuleType
)


class FieldType(Enum):
    """Supported field types for schemas."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    LIST = "list"
    DICT = "dict"
    ANY = "any"


@dataclass
class SchemaField:
    """
    Definition of a schema field.
    
    Attributes:
        name: Field name
        type: Field data type
        required: Whether field is required
        constraints: Additional constraints (min, max, pattern, etc.)
        default: Default value if field is missing
        description: Field description
        nullable: Whether field can be null
    """
    name: str
    type: FieldType
    required: bool = True
    constraints: Dict[str, Any] = field(default_factory=dict)
    default: Any = None
    description: str = ""
    nullable: bool = True
    
    def __post_init__(self):
        """Validate and normalize field configuration."""
        if isinstance(self.type, str):
            self.type = FieldType(self.type)
    
    def to_validation_rules(self) -> List[ValidationRule]:
        """
        Convert field definition to validation rules.
        
        Returns:
            List of ValidationRule objects
        """
        rules = []
        
        # Required rule
        if self.required:
            rules.append(ValidationRule(
                field=self.name,
                rule_type=RuleType.REQUIRED,
                message=f"Field '{self.name}' is required"
            ))
        
        # Type rule
        type_mapping = {
            FieldType.STRING: "string",
            FieldType.INTEGER: "int",
            FieldType.FLOAT: "float",
            FieldType.BOOLEAN: "bool",
            FieldType.DATE: "date",
            FieldType.DATETIME: "datetime",
            FieldType.LIST: "list",
            FieldType.DICT: "dict",
            FieldType.ANY: None,
        }
        
        type_name = type_mapping.get(self.type)
        if type_name:
            rules.append(ValidationRule(
                field=self.name,
                rule_type=RuleType.TYPE,
                params={"type": type_name},
                message=f"Field '{self.name}' must be of type {type_name}"
            ))
        
        # Range constraints
        if "min" in self.constraints or "max" in self.constraints:
            rules.append(ValidationRule(
                field=self.name,
                rule_type=RuleType.RANGE,
                params={
                    "min": self.constraints.get("min"),
                    "max": self.constraints.get("max")
                },
                message=f"Field '{self.name}' is out of range"
            ))
        
        # Pattern constraint
        if "pattern" in self.constraints:
            rules.append(ValidationRule(
                field=self.name,
                rule_type=RuleType.PATTERN,
                params={"pattern": self.constraints["pattern"]},
                message=f"Field '{self.name}' does not match required pattern"
            ))
        
        # Min length constraint
        if "min_length" in self.constraints:
            rules.append(ValidationRule(
                field=self.name,
                rule_type=RuleType.MIN_LENGTH,
                params={"min": self.constraints["min_length"]},
                message=f"Field '{self.name}' is below minimum length"
            ))
        
        # Max length constraint
        if "max_length" in self.constraints:
            rules.append(ValidationRule(
                field=self.name,
                rule_type=RuleType.MAX_LENGTH,
                params={"max": self.constraints["max_length"]},
                message=f"Field '{self.name}' exceeds maximum length"
            ))
        
        # Enum constraint
        if "enum" in self.constraints:
            rules.append(ValidationRule(
                field=self.name,
                rule_type=RuleType.ENUM,
                params={"values": self.constraints["enum"]},
                message=f"Field '{self.name}' must be one of {self.constraints['enum']}"
            ))
        
        return rules


@dataclass
class SchemaDefinition:
    """
    Complete schema definition with versioning support.
    
    Attributes:
        name: Schema name
        version: Schema version string
        fields: List of field definitions
        constraints: Schema-level constraints
        description: Schema description
        created_at: Creation timestamp
        deprecated: Whether schema is deprecated
    """
    name: str
    version: str = "1.0.0"
    fields: List[SchemaField] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    deprecated: bool = False
    
    def get_field(self, name: str) -> Optional[SchemaField]:
        """
        Get a field by name.
        
        Args:
            name: Field name to find
            
        Returns:
            SchemaField or None if not found
        """
        for field in self.fields:
            if field.name == name:
                return field
        return None
    
    def get_field_names(self) -> List[str]:
        """Get list of all field names."""
        return [f.name for f in self.fields]
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert schema to dictionary representation.
        
        Returns:
            Dictionary representation of schema
        """
        return {
            "name": self.name,
            "version": self.version,
            "fields": [
                {
                    "name": f.name,
                    "type": f.type.value,
                    "required": f.required,
                    "constraints": f.constraints,
                    "default": f.default,
                    "description": f.description,
                    "nullable": f.nullable
                }
                for f in self.fields
            ],
            "constraints": self.constraints,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "deprecated": self.deprecated
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SchemaDefinition':
        """
        Create SchemaDefinition from dictionary.
        
        Args:
            data: Dictionary with schema definition
            
        Returns:
            SchemaDefinition instance
        """
        fields = []
        for f in data.get("fields", []):
            fields.append(SchemaField(
                name=f["name"],
                type=FieldType(f["type"]),
                required=f.get("required", True),
                constraints=f.get("constraints", {}),
                default=f.get("default"),
                description=f.get("description", ""),
                nullable=f.get("nullable", True)
            ))
        
        return cls(
            name=data["name"],
            version=data.get("version", "1.0.0"),
            fields=fields,
            constraints=data.get("constraints", {}),
            description=data.get("description", ""),
            deprecated=data.get("deprecated", False)
        )


@dataclass
class SchemaVersion:
    """Represents a version of a schema."""
    version: str
    schema: SchemaDefinition
    created_at: datetime = field(default_factory=datetime.utcnow)
    migration_notes: str = ""


class SchemaManager:
    """
    Schema management system with versioning support.
    
    Features:
    - Register and manage schemas
    - Validate data against schemas
    - Schema versioning and migration support
    - Schema inheritance and composition
    
    Example:
        manager = SchemaManager()
        
        schema = SchemaDefinition(
            name="user",
            fields=[
                SchemaField("id", FieldType.INTEGER, required=True),
                SchemaField("name", FieldType.STRING, required=True),
                SchemaField("email", FieldType.STRING, constraints={"pattern": r".*@.*"})
            ]
        )
        manager.register(schema)
        
        result = manager.validate("user", {"id": 1, "name": "John", "email": "john@example.com"})
    """
    
    def __init__(self):
        """Initialize the schema manager."""
        self._schemas: Dict[str, SchemaDefinition] = {}
        self._versions: Dict[str, List[SchemaVersion]] = {}
        self._validators: Dict[str, DataValidator] = {}
    
    def register(self, schema: SchemaDefinition, set_as_current: bool = True) -> None:
        """
        Register a schema definition.
        
        Args:
            schema: SchemaDefinition to register
            set_as_current: Whether to set this as the current version
        """
        key = self._get_schema_key(schema.name, schema.version)
        
        # Store schema
        if set_as_current:
            self._schemas[schema.name] = schema
        
        # Store version history
        if schema.name not in self._versions:
            self._versions[schema.name] = []
        
        version = SchemaVersion(
            version=schema.version,
            schema=schema
        )
        self._versions[schema.name].append(version)
        
        # Build validator for this schema
        self._build_validator(key, schema)
    
    def register_from_dict(self, data: Dict[str, Any]) -> None:
        """
        Register a schema from dictionary definition.
        
        Args:
            data: Dictionary with schema definition
        """
        schema = SchemaDefinition.from_dict(data)
        self.register(schema)
    
    def get(self, name: str, version: Optional[str] = None) -> Optional[SchemaDefinition]:
        """
        Get a schema by name and optional version.
        
        Args:
            name: Schema name
            version: Optional version string
            
        Returns:
            SchemaDefinition or None if not found
        """
        if version is None:
            return self._schemas.get(name)
        
        for v in self._versions.get(name, []):
            if v.version == version:
                return v.schema
        
        return None
    
    def validate(self, schema_name: str, data: Dict[str, Any], 
                 version: Optional[str] = None) -> ValidationResult:
        """
        Validate data against a schema.
        
        Args:
            schema_name: Name of schema to validate against
            data: Data to validate
            version: Optional schema version
            
        Returns:
            ValidationResult with validation outcome
        """
        schema = self.get(schema_name, version)
        if schema is None:
            result = ValidationResult(is_valid=False)
            from .data_validator import ValidationError
            result.add_error(ValidationError(
                field="",
                rule_type="schema",
                message=f"Schema '{schema_name}' not found",
                value=None
            ))
            return result
        
        key = self._get_schema_key(schema_name, version or schema.version)
        validator = self._validators.get(key)
        
        if validator is None:
            validator = self._build_validator(key, schema)
        
        return validator.validate(data)
    
    def list_schemas(self) -> List[str]:
        """Get list of registered schema names."""
        return list(self._schemas.keys())
    
    def list_versions(self, name: str) -> List[str]:
        """
        Get list of versions for a schema.
        
        Args:
            name: Schema name
            
        Returns:
            List of version strings
        """
        return [v.version for v in self._versions.get(name, [])]
    
    def deprecate(self, name: str, version: Optional[str] = None) -> bool:
        """
        Mark a schema version as deprecated.
        
        Args:
            name: Schema name
            version: Optional version (current if not specified)
            
        Returns:
            True if successful, False if schema not found
        """
        schema = self.get(name, version)
        if schema is None:
            return False
        
        schema.deprecated = True
        return True
    
    def migrate_data(self, from_version: str, to_version: str, 
                     data: Dict[str, Any], schema_name: str) -> Dict[str, Any]:
        """
        Migrate data between schema versions.
        
        Args:
            from_version: Source version
            to_version: Target version
            data: Data to migrate
            schema_name: Schema name
            
        Returns:
            Migrated data dictionary
        """
        source_schema = self.get(schema_name, from_version)
        target_schema = self.get(schema_name, to_version)
        
        if source_schema is None or target_schema is None:
            return data
        
        migrated = copy.deepcopy(data)
        
        # Add default values for new required fields
        for field in target_schema.fields:
            if field.name not in migrated and field.default is not None:
                migrated[field.name] = field.default
        
        return migrated
    
    def _get_schema_key(self, name: str, version: str) -> str:
        """Get unique key for schema version."""
        return f"{name}:{version}"
    
    def _build_validator(self, key: str, schema: SchemaDefinition) -> DataValidator:
        """
        Build a validator for a schema.
        
        Args:
            key: Validator key
            schema: Schema definition
            
        Returns:
            Configured DataValidator
        """
        validator = DataValidator(name=f"SchemaValidator:{schema.name}")
        
        for field in schema.fields:
            for rule in field.to_validation_rules():
                validator.add_rule(rule)
        
        self._validators[key] = validator
        return validator
    
    def clear(self) -> None:
        """Clear all registered schemas."""
        self._schemas.clear()
        self._versions.clear()
        self._validators.clear()


def create_schema(name: str, fields: List[Dict[str, Any]], 
                  **kwargs) -> SchemaDefinition:
    """
    Factory function to create a schema definition.
    
    Args:
        name: Schema name
        fields: List of field configuration dictionaries
        **kwargs: Additional SchemaDefinition parameters
        
    Returns:
        SchemaDefinition instance
    """
    field_objects = []
    for f in fields:
        field_objects.append(SchemaField(
            name=f["name"],
            type=FieldType(f.get("type", "string")),
            required=f.get("required", True),
            constraints=f.get("constraints", {}),
            default=f.get("default"),
            description=f.get("description", ""),
            nullable=f.get("nullable", True)
        ))
    
    return SchemaDefinition(name=name, fields=field_objects, **kwargs)
