# Email Templates - Week 48 Builder 2
# Email template processor and management

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import re
import uuid


class TemplateType(Enum):
    WELCOME = "welcome"
    PASSWORD_RESET = "password_reset"
    VERIFICATION = "verification"
    NOTIFICATION = "notification"
    ALERT = "alert"
    REPORT = "report"
    CUSTOM = "custom"


@dataclass
class EmailTemplate:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    template_type: TemplateType = TemplateType.CUSTOM
    subject: str = ""
    body_text: str = ""
    body_html: Optional[str] = None
    variables: List[str] = field(default_factory=list)
    required_vars: List[str] = field(default_factory=list)
    default_values: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    version: int = 1
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RenderedTemplate:
    template_id: str
    subject: str
    body_text: str
    body_html: Optional[str] = None
    variables_used: List[str] = field(default_factory=list)
    missing_vars: List[str] = field(default_factory=list)


class EmailTemplateProcessor:
    """Processes email templates with variable substitution"""

    def __init__(self):
        self._templates: Dict[str, EmailTemplate] = {}
        self._templates_by_name: Dict[str, str] = {}
        self._variable_pattern = re.compile(r'\{\{\s*(\w+)\s*\}\}')

    def create_template(
        self,
        tenant_id: str,
        name: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        template_type: TemplateType = TemplateType.CUSTOM,
        required_vars: Optional[List[str]] = None,
        default_values: Optional[Dict[str, Any]] = None
    ) -> EmailTemplate:
        """Create a new email template"""
        # Extract variables from subject and body
        variables = self._extract_variables(subject, body_text, body_html)

        template = EmailTemplate(
            tenant_id=tenant_id,
            name=name,
            template_type=template_type,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            variables=variables,
            required_vars=required_vars or [],
            default_values=default_values or {}
        )

        self._templates[template.id] = template
        key = f"{tenant_id}:{name}"
        self._templates_by_name[key] = template.id

        return template

    def _extract_variables(
        self,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None
    ) -> List[str]:
        """Extract variable names from template content"""
        content = f"{subject} {body_text}"
        if body_html:
            content += f" {body_html}"

        variables = set(self._variable_pattern.findall(content))
        return list(variables)

    def get_template(self, template_id: str) -> Optional[EmailTemplate]:
        """Get template by ID"""
        return self._templates.get(template_id)

    def get_template_by_name(
        self,
        tenant_id: str,
        name: str
    ) -> Optional[EmailTemplate]:
        """Get template by tenant and name"""
        key = f"{tenant_id}:{name}"
        template_id = self._templates_by_name.get(key)
        if template_id:
            return self._templates.get(template_id)
        return None

    def render(
        self,
        template_id: str,
        variables: Dict[str, Any]
    ) -> Optional[RenderedTemplate]:
        """Render a template with variables"""
        template = self._templates.get(template_id)
        if not template:
            return None

        # Merge with defaults
        merged_vars = {**template.default_values, **variables}

        # Check required variables
        missing = [v for v in template.required_vars if v not in merged_vars]

        # Substitute variables
        def replace_vars(text: str) -> str:
            def replacer(match):
                var_name = match.group(1)
                return str(merged_vars.get(var_name, match.group(0)))
            return self._variable_pattern.sub(replacer, text)

        rendered = RenderedTemplate(
            template_id=template_id,
            subject=replace_vars(template.subject),
            body_text=replace_vars(template.body_text),
            body_html=replace_vars(template.body_html) if template.body_html else None,
            variables_used=list(set(merged_vars.keys()) & set(template.variables)),
            missing_vars=missing
        )

        return rendered

    def render_by_name(
        self,
        tenant_id: str,
        name: str,
        variables: Dict[str, Any]
    ) -> Optional[RenderedTemplate]:
        """Render template by name"""
        template = self.get_template_by_name(tenant_id, name)
        if template:
            return self.render(template.id, variables)
        return None

    def update_template(
        self,
        template_id: str,
        subject: Optional[str] = None,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None
    ) -> Optional[EmailTemplate]:
        """Update a template"""
        template = self._templates.get(template_id)
        if not template:
            return None

        if subject is not None:
            template.subject = subject
        if body_text is not None:
            template.body_text = body_text
        if body_html is not None:
            template.body_html = body_html

        # Re-extract variables
        template.variables = self._extract_variables(
            template.subject,
            template.body_text,
            template.body_html
        )

        template.version += 1
        template.updated_at = datetime.utcnow()

        return template

    def delete_template(self, template_id: str) -> bool:
        """Delete a template"""
        template = self._templates.get(template_id)
        if not template:
            return False

        key = f"{template.tenant_id}:{template.name}"
        if key in self._templates_by_name:
            del self._templates_by_name[key]

        del self._templates[template_id]
        return True

    def get_templates_by_tenant(self, tenant_id: str) -> List[EmailTemplate]:
        """Get all templates for a tenant"""
        return [t for t in self._templates.values() if t.tenant_id == tenant_id]

    def get_templates_by_type(
        self,
        template_type: TemplateType
    ) -> List[EmailTemplate]:
        """Get all templates of a type"""
        return [t for t in self._templates.values() 
                if t.template_type == template_type]

    def validate_variables(
        self,
        template_id: str,
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate variables for a template"""
        template = self._templates.get(template_id)
        if not template:
            return {"valid": False, "errors": ["Template not found"]}

        errors = []
        warnings = []

        # Check required variables
        for var in template.required_vars:
            if var not in variables and var not in template.default_values:
                errors.append(f"Missing required variable: {var}")

        # Check for unknown variables
        for var in variables:
            if var not in template.variables:
                warnings.append(f"Unknown variable: {var}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    def duplicate_template(
        self,
        template_id: str,
        new_name: str
    ) -> Optional[EmailTemplate]:
        """Duplicate a template with a new name"""
        original = self._templates.get(template_id)
        if not original:
            return None

        return self.create_template(
            tenant_id=original.tenant_id,
            name=new_name,
            subject=original.subject,
            body_text=original.body_text,
            body_html=original.body_html,
            template_type=original.template_type,
            required_vars=original.required_vars.copy(),
            default_values=original.default_values.copy()
        )

    def get_all_templates(self) -> List[EmailTemplate]:
        """Get all templates"""
        return list(self._templates.values())
