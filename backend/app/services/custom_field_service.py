"""
PARWA Custom Field Service - Custom Ticket Fields (Day 33: MF09)

Implements MF09: Custom ticket fields with:
- Custom field CRUD operations
- Field type validation
- Category-specific fields
- Field value storage in ticket metadata

BC-001: All queries are tenant-isolated via company_id.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.exceptions import NotFoundError, ValidationError
from database.models.tickets import CustomField, TicketCategory


class CustomFieldService:
    """Custom field management operations."""

    # Maximum custom fields per company
    MAX_FIELDS_PER_COMPANY = 50

    # Valid field types
    VALID_FIELD_TYPES = [
        "text",
        "number",
        "dropdown",
        "multi_select",
        "date",
        "checkbox",
    ]

    # Valid field key pattern
    FIELD_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id

    # ── CUSTOM FIELD CRUD ───────────────────────────────────────────────────

    def create_field(
        self,
        name: str,
        field_key: str,
        field_type: str,
        config: Optional[Dict[str, Any]] = None,
        applicable_categories: Optional[List[str]] = None,
        is_required: bool = False,
        sort_order: int = 0,
    ) -> CustomField:
        """Create a new custom field.

        Args:
            name: Display name for the field
            field_key: Unique key for the field (used in metadata_json)
            field_type: Type of field (text, number, dropdown, etc.)
            config: Field configuration (options, default, etc.)
            applicable_categories: Categories this field applies to (empty = all)
            is_required: Whether the field is required
            sort_order: Display order

        Returns:
            Created CustomField object

        Raises:
            ValidationError: If validation fails or limit exceeded
        """
        # Check limit
        current_count = (
            self.db.query(CustomField)
            .filter(
                CustomField.company_id == self.company_id,
                CustomField.is_active,
            )
            .count()
        )

        if current_count >= self.MAX_FIELDS_PER_COMPANY:
            raise ValidationError(f"Maximum {
                    self.MAX_FIELDS_PER_COMPANY} custom fields per company")

        # Validate name
        if not name or len(name.strip()) == 0:
            raise ValidationError("Field name is required")

        # Validate field_key
        if not field_key:
            raise ValidationError("Field key is required")

        if not self.FIELD_KEY_PATTERN.match(field_key):
            raise ValidationError(
                "Field key must start with lowercase letter and contain only lowercase letters, numbers, and underscores"
            )

        # Check for duplicate field_key
        existing = (
            self.db.query(CustomField)
            .filter(
                CustomField.company_id == self.company_id,
                CustomField.field_key == field_key,
                CustomField.is_active,
            )
            .first()
        )

        if existing:
            raise ValidationError(f"Field with key '{field_key}' already exists")

        # Validate field_type
        if field_type not in self.VALID_FIELD_TYPES:
            raise ValidationError(f"Invalid field type: {field_type}. Valid types: {
                    ', '.join(
                        self.VALID_FIELD_TYPES)}")

        # Validate config based on field_type
        config = config or {}
        self._validate_config(field_type, config)

        # Validate applicable_categories
        if applicable_categories:
            valid_categories = [c.value for c in TicketCategory]
            for cat in applicable_categories:
                if cat not in valid_categories:
                    raise ValidationError(f"Invalid category: {cat}")

        field = CustomField(
            id=str(uuid.uuid4()),
            company_id=self.company_id,
            name=name.strip(),
            field_key=field_key,
            field_type=field_type,
            config=json.dumps(config),
            applicable_categories=json.dumps(applicable_categories or []),
            is_required=is_required,
            is_active=True,
            sort_order=sort_order,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.db.add(field)
        self.db.commit()
        self.db.refresh(field)

        return field

    def _validate_config(self, field_type: str, config: Dict[str, Any]) -> None:
        """Validate field config based on type."""
        if field_type in ["dropdown", "multi_select"]:
            options = config.get("options", [])
            if not isinstance(options, list):
                raise ValidationError("Options must be a list")

            if len(options) == 0:
                raise ValidationError(
                    f"{field_type} field requires at least one option"
                )

            for opt in options:
                if not isinstance(opt, str):
                    raise ValidationError("All options must be strings")

        if field_type == "number":
            min_val = config.get("min")
            max_val = config.get("max")

            if min_val is not None and not isinstance(min_val, (int, float)):
                raise ValidationError("Min must be a number")

            if max_val is not None and not isinstance(max_val, (int, float)):
                raise ValidationError("Max must be a number")

            if min_val is not None and max_val is not None and min_val > max_val:
                raise ValidationError("Min cannot be greater than max")

    def get_field(self, field_id: str) -> CustomField:
        """Get a custom field by ID.

        Args:
            field_id: Field ID

        Returns:
            CustomField object

        Raises:
            NotFoundError: If field not found
        """
        field = (
            self.db.query(CustomField)
            .filter(
                CustomField.id == field_id,
                CustomField.company_id == self.company_id,
            )
            .first()
        )

        if not field:
            raise NotFoundError(f"Custom field {field_id} not found")

        return field

    def get_field_by_key(self, field_key: str) -> Optional[CustomField]:
        """Get a custom field by key.

        Args:
            field_key: Field key

        Returns:
            CustomField object or None
        """
        return (
            self.db.query(CustomField)
            .filter(
                CustomField.company_id == self.company_id,
                CustomField.field_key == field_key,
                CustomField.is_active,
            )
            .first()
        )

    def list_fields(
        self,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[CustomField], int]:
        """List custom fields with filters.

        Args:
            category: Filter by applicable category
            is_active: Filter by active status
            page: Page number
            page_size: Items per page

        Returns:
            Tuple of (fields list, total count)
        """
        query = self.db.query(CustomField).filter(
            CustomField.company_id == self.company_id,
        )

        # Apply filters
        if is_active is not None:
            query = query.filter(CustomField.is_active == is_active)

        # Count total
        total = query.count()

        # Sort by sort_order then name
        query = query.order_by(
            CustomField.sort_order,
            CustomField.name,
        )

        # Paginate
        offset = (page - 1) * page_size
        fields = query.offset(offset).limit(page_size).all()

        # Filter by category (need to do in Python due to JSON)
        if category:
            filtered = []
            for field in fields:
                applicable = json.loads(field.applicable_categories or "[]")
                if not applicable or category in applicable:
                    filtered.append(field)
            return filtered, len(filtered)

        return fields, total

    def update_field(
        self,
        field_id: str,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        applicable_categories: Optional[List[str]] = None,
        is_required: Optional[bool] = None,
        sort_order: Optional[int] = None,
    ) -> CustomField:
        """Update a custom field.

        Args:
            field_id: Field ID
            name: New name
            config: New config
            applicable_categories: New applicable categories
            is_required: New required status
            sort_order: New sort order

        Returns:
            Updated CustomField object
        """
        field = self.get_field(field_id)

        if name is not None:
            if not name.strip():
                raise ValidationError("Field name cannot be empty")
            field.name = name.strip()

        if config is not None:
            self._validate_config(field.field_type, config)
            field.config = json.dumps(config)

        if applicable_categories is not None:
            # Validate categories
            valid_categories = [c.value for c in TicketCategory]
            for cat in applicable_categories:
                if cat not in valid_categories:
                    raise ValidationError(f"Invalid category: {cat}")
            field.applicable_categories = json.dumps(applicable_categories)

        if is_required is not None:
            field.is_required = is_required

        if sort_order is not None:
            field.sort_order = sort_order

        field.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(field)

        return field

    def delete_field(self, field_id: str) -> bool:
        """Delete a custom field (soft delete).

        Args:
            field_id: Field ID

        Returns:
            True if deleted
        """
        field = self.get_field(field_id)

        field.is_active = False
        field.updated_at = datetime.now(timezone.utc)

        self.db.commit()

        return True

    # ── FIELD VALIDATION ─────────────────────────────────────────────────────

    def validate_field_value(
        self,
        field_key: str,
        value: Any,
    ) -> Tuple[bool, Optional[str]]:
        """Validate a value against a field's type and config.

        Args:
            field_key: Field key
            value: Value to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        field = self.get_field_by_key(field_key)

        if not field:
            return False, f"Field '{field_key}' not found"

        config = json.loads(field.config or "{}")

        # Check required
        if field.is_required and value is None:
            return False, f"Field '{field_key}' is required"

        if value is None:
            return True, None

        # Type-specific validation
        if field.field_type == "text":
            if not isinstance(value, str):
                return False, f"Field '{field_key}' must be a string"

            max_length = config.get("max_length", 500)
            if len(value) > max_length:
                return False, f"Field '{field_key}' exceeds max length of {max_length}"

        elif field.field_type == "number":
            if not isinstance(value, (int, float)):
                return False, f"Field '{field_key}' must be a number"

            min_val = config.get("min")
            max_val = config.get("max")

            if min_val is not None and value < min_val:
                return False, f"Field '{field_key}' must be >= {min_val}"

            if max_val is not None and value > max_val:
                return False, f"Field '{field_key}' must be <= {max_val}"

        elif field.field_type == "dropdown":
            options = config.get("options", [])
            if value not in options:
                return False, f"Field '{field_key}' must be one of: {
                    ', '.join(options)}"

        elif field.field_type == "multi_select":
            if not isinstance(value, list):
                return False, f"Field '{field_key}' must be a list"

            options = config.get("options", [])
            for v in value:
                if v not in options:
                    return False, f"Invalid option '{v}' for field '{field_key}'"

        elif field.field_type == "date":
            # Accept ISO format dates
            try:
                if isinstance(value, str):
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                return False, f"Field '{field_key}' must be a valid ISO date"

        elif field.field_type == "checkbox":
            if not isinstance(value, bool):
                return False, f"Field '{field_key}' must be a boolean"

        return True, None

    def get_fields_for_category(
        self,
        category: Optional[str] = None,
    ) -> List[CustomField]:
        """Get all active fields applicable to a category.

        Args:
            category: Category to filter by (None = all fields)

        Returns:
            List of CustomField objects
        """
        fields = (
            self.db.query(CustomField)
            .filter(
                CustomField.company_id == self.company_id,
                CustomField.is_active,
            )
            .order_by(CustomField.sort_order)
            .all()
        )

        if not category:
            return fields

        # Filter by category
        result = []
        for field in fields:
            applicable = json.loads(field.applicable_categories or "[]")
            if not applicable or category in applicable:
                result.append(field)

        return result

    def validate_ticket_fields(
        self,
        category: Optional[str],
        field_values: Dict[str, Any],
    ) -> Tuple[bool, List[str]]:
        """Validate all custom field values for a ticket.

        Args:
            category: Ticket category
            field_values: Dict of field_key -> value

        Returns:
            Tuple of (is_valid, list of errors)
        """
        fields = self.get_fields_for_category(category)
        errors = []

        # Check required fields
        field_keys = {f.field_key for f in fields}
        for field in fields:
            if field.is_required and field.field_key not in field_values:
                errors.append(f"Required field '{field.field_key}' is missing")

        # Validate provided values
        for field_key, value in field_values.items():
            if field_key in field_keys:
                is_valid, error = self.validate_field_value(field_key, value)
                if not is_valid and error:
                    errors.append(error)

        return len(errors) == 0, errors
