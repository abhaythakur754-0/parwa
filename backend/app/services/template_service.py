"""
PARWA Template Service - Response Templates/Macros (Day 33: MF07)

Implements MF07: Response templates with:
- Template CRUD operations
- Variable substitution
- Intent-type filtering
- Template versioning

BC-001: All queries are tenant-isolated via company_id.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from app.exceptions import NotFoundError, ValidationError
from database.models.remaining import ResponseTemplate


class TemplateService:
    """Response template management operations."""

    # Maximum templates per company
    MAX_TEMPLATES_PER_COMPANY = 100

    # Valid variable pattern: {{variable_name}}
    VARIABLE_PATTERN = re.compile(r"\{\{(\w+)\}\}")

    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id

    # ── TEMPLATE CRUD ───────────────────────────────────────────────────────

    def create_template(
        self,
        name: str,
        template_text: str,
        intent_type: Optional[str] = None,
        variables: Optional[List[str]] = None,
        language: str = "en",
        created_by: Optional[str] = None,
    ) -> ResponseTemplate:
        """Create a new response template.

        Args:
            name: Template name
            template_text: Template content with {{variable}} placeholders
            intent_type: Optional intent type this template applies to
            variables: List of variable names (auto-extracted if not provided)
            language: Template language (default: en)
            created_by: User ID who created the template

        Returns:
            Created ResponseTemplate object

        Raises:
            ValidationError: If validation fails or limit exceeded
        """
        # Check limit
        current_count = (
            self.db.query(ResponseTemplate)
            .filter(
                ResponseTemplate.company_id == self.company_id,
                ResponseTemplate.is_active,
            )
            .count()
        )

        if current_count >= self.MAX_TEMPLATES_PER_COMPANY:
            raise ValidationError(f"Maximum {
                    self.MAX_TEMPLATES_PER_COMPANY} templates per company")

        # Validate name
        if not name or len(name.strip()) == 0:
            raise ValidationError("Template name is required")

        # Check for duplicate name
        existing = (
            self.db.query(ResponseTemplate)
            .filter(
                ResponseTemplate.company_id == self.company_id,
                ResponseTemplate.name == name.strip(),
                ResponseTemplate.is_active,
            )
            .first()
        )

        if existing:
            raise ValidationError(f"Template with name '{name}' already exists")

        # Extract variables from template if not provided
        if variables is None:
            variables = list(set(self.VARIABLE_PATTERN.findall(template_text)))

        # Validate variables are alphanumeric (allowing underscores but not
        # dunder)
        for var in variables:
            # Must start with letter or single underscore, contain only alphanumeric/underscore
            # Must not be a dunder (double underscore) pattern
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", var):
                raise ValidationError(f"Invalid variable name: {var}")
            if var.startswith("__") or "__" in var:
                raise ValidationError(f"Invalid variable name: {var}")

        template = ResponseTemplate(
            id=str(uuid.uuid4()),
            company_id=self.company_id,
            name=name.strip(),
            intent_type=intent_type,
            template_text=template_text,
            variables=json.dumps(variables),
            language=language,
            is_active=True,
            version=1,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)

        return template

    def get_template(self, template_id: str) -> ResponseTemplate:
        """Get a template by ID.

        Args:
            template_id: Template ID

        Returns:
            ResponseTemplate object

        Raises:
            NotFoundError: If template not found
        """
        template = (
            self.db.query(ResponseTemplate)
            .filter(
                ResponseTemplate.id == template_id,
                ResponseTemplate.company_id == self.company_id,
            )
            .first()
        )

        if not template:
            raise NotFoundError(f"Template {template_id} not found")

        return template

    def list_templates(
        self,
        intent_type: Optional[str] = None,
        language: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ResponseTemplate], int]:
        """List templates with filters.

        Args:
            intent_type: Filter by intent type
            language: Filter by language
            is_active: Filter by active status
            search: Search in name and template_text
            page: Page number
            page_size: Items per page

        Returns:
            Tuple of (templates list, total count)
        """
        query = self.db.query(ResponseTemplate).filter(
            ResponseTemplate.company_id == self.company_id,
        )

        # Apply filters
        if intent_type:
            query = query.filter(ResponseTemplate.intent_type == intent_type)

        if language:
            query = query.filter(ResponseTemplate.language == language)

        if is_active is not None:
            query = query.filter(ResponseTemplate.is_active == is_active)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    ResponseTemplate.name.ilike(search_pattern),
                    ResponseTemplate.template_text.ilike(search_pattern),
                )
            )

        # Count total
        total = query.count()

        # Sort and paginate
        query = query.order_by(desc(ResponseTemplate.created_at))
        offset = (page - 1) * page_size
        templates = query.offset(offset).limit(page_size).all()

        return templates, total

    def update_template(
        self,
        template_id: str,
        name: Optional[str] = None,
        template_text: Optional[str] = None,
        intent_type: Optional[str] = None,
        variables: Optional[List[str]] = None,
        language: Optional[str] = None,
    ) -> ResponseTemplate:
        """Update a template.

        Args:
            template_id: Template ID
            name: New name
            template_text: New template text
            intent_type: New intent type
            variables: New variables list
            language: New language

        Returns:
            Updated ResponseTemplate object

        Raises:
            NotFoundError: If template not found
            ValidationError: If validation fails
        """
        template = self.get_template(template_id)

        # Check for duplicate name if changing
        if name and name.strip() != template.name:
            existing = (
                self.db.query(ResponseTemplate)
                .filter(
                    ResponseTemplate.company_id == self.company_id,
                    ResponseTemplate.name == name.strip(),
                    ResponseTemplate.id != template_id,
                    ResponseTemplate.is_active,
                )
                .first()
            )

            if existing:
                raise ValidationError(f"Template with name '{name}' already exists")

            template.name = name.strip()

        if template_text is not None:
            # Extract variables if not provided
            if variables is None:
                variables = list(set(self.VARIABLE_PATTERN.findall(template_text)))

            # Validate variables
            for var in variables:
                if not var.isalnum():
                    raise ValidationError(f"Invalid variable name: {var}")

            template.template_text = template_text
            template.variables = json.dumps(variables)
            template.version = (template.version or 1) + 1

        if intent_type is not None:
            template.intent_type = intent_type

        if language is not None:
            template.language = language

        template.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(template)

        return template

    def delete_template(self, template_id: str) -> bool:
        """Soft delete a template.

        Args:
            template_id: Template ID

        Returns:
            True if deleted

        Raises:
            NotFoundError: If template not found
        """
        template = self.get_template(template_id)

        # Soft delete
        template.is_active = False
        template.updated_at = datetime.now(timezone.utc)

        self.db.commit()

        return True

    # ── TEMPLATE APPLICATION ─────────────────────────────────────────────────

    def apply_template(
        self,
        template_id: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Apply variables to a template and return the rendered text.

        Args:
            template_id: Template ID
            variables: Dictionary of variable values

        Returns:
            Rendered template text

        Raises:
            NotFoundError: If template not found
            ValidationError: If required variables missing
        """
        template = self.get_template(template_id)

        if not template.is_active:
            raise ValidationError(f"Template {template_id} is not active")

        variables = variables or {}
        template_vars = json.loads(template.variables or "[]")

        # Check for required variables
        missing_vars = []
        for var in template_vars:
            if var not in variables:
                missing_vars.append(var)

        if missing_vars:
            raise ValidationError(
                f"Missing required variables: {', '.join(missing_vars)}"
            )

        # Render template
        rendered = template.template_text
        for var_name, var_value in variables.items():
            rendered = rendered.replace(f"{{{{{var_name}}}}}", str(var_value))

        return rendered

    def get_template_variables(self, template_id: str) -> List[str]:
        """Get the variables defined in a template.

        Args:
            template_id: Template ID

        Returns:
            List of variable names
        """
        template = self.get_template(template_id)
        return json.loads(template.variables or "[]")

    def get_templates_by_intent(self, intent_type: str) -> List[ResponseTemplate]:
        """Get all active templates for an intent type.

        Args:
            intent_type: Intent type to filter by

        Returns:
            List of ResponseTemplate objects
        """
        return (
            self.db.query(ResponseTemplate)
            .filter(
                ResponseTemplate.company_id == self.company_id,
                ResponseTemplate.intent_type == intent_type,
                ResponseTemplate.is_active,
            )
            .order_by(ResponseTemplate.name)
            .all()
        )
