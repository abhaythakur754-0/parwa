# Template Engine - Week 48 Builder 4
# Template processing for notifications

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import re
import uuid


class TemplateFormat(Enum):
    PLAIN_TEXT = "plain_text"
    HTML = "html"
    MARKDOWN = "markdown"
    JSON = "json"


class TemplateCategory(Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"


@dataclass
class Template:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    category: TemplateCategory = TemplateCategory.EMAIL
    format: TemplateFormat = TemplateFormat.PLAIN_TEXT
    subject: Optional[str] = None
    content: str = ""
    variables: List[str] = field(default_factory=list)
    required_vars: List[str] = field(default_factory=list)
    default_values: Dict[str, Any] = field(default_factory=dict)
    version: int = 1
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RenderedContent:
    template_id: str
    subject: Optional[str] = None
    content: str = ""
    format: TemplateFormat = TemplateFormat.PLAIN_TEXT
    variables_used: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class TemplateEngine:
    """Template processing engine for notifications"""

    def __init__(self):
        self._templates: Dict[str, Template] = {}
        self._templates_by_name: Dict[str, str] = {}
        self._filters: Dict[str, Callable] = {}
        self._variable_pattern = re.compile(r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*(?:\|[a-zA-Z_]+)?)\s*\}\}')
        self._condition_pattern = re.compile(r'\{%\s*if\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*%\}(.*?)\{%\s*endif\s*%\}', re.DOTALL)
        self._loop_pattern = re.compile(r'\{%\s*for\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+in\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*%\}(.*?)\{%\s*endfor\s*%\}', re.DOTALL)

        # Register default filters
        self._register_default_filters()

    def _register_default_filters(self) -> None:
        """Register built-in filters"""
        self._filters["upper"] = lambda x: str(x).upper()
        self._filters["lower"] = lambda x: str(x).lower()
        self._filters["capitalize"] = lambda x: str(x).capitalize()
        self._filters["title"] = lambda x: str(x).title()
        self._filters["strip"] = lambda x: str(x).strip()
        self._filters["default"] = lambda x, d="": x if x else d

    def register_filter(self, name: str, func: Callable) -> None:
        """Register a custom filter"""
        self._filters[name] = func

    def create_template(
        self,
        tenant_id: str,
        name: str,
        content: str,
        category: TemplateCategory = TemplateCategory.EMAIL,
        format: TemplateFormat = TemplateFormat.PLAIN_TEXT,
        subject: Optional[str] = None,
        required_vars: Optional[List[str]] = None,
        default_values: Optional[Dict[str, Any]] = None
    ) -> Template:
        """Create a new template"""
        variables = self._extract_variables(content)
        if subject:
            variables.extend(self._extract_variables(subject))

        template = Template(
            tenant_id=tenant_id,
            name=name,
            category=category,
            format=format,
            subject=subject,
            content=content,
            variables=list(set(variables)),
            required_vars=required_vars or [],
            default_values=default_values or {}
        )

        self._templates[template.id] = template
        key = f"{tenant_id}:{name}"
        self._templates_by_name[key] = template.id

        return template

    def _extract_variables(self, content: str) -> List[str]:
        """Extract variable names from template content"""
        variables = []
        for match in self._variable_pattern.finditer(content):
            var_expr = match.group(1)
            # Remove filter part if present
            var_name = var_expr.split('|')[0].strip()
            variables.append(var_name)
        return variables

    def get_template(self, template_id: str) -> Optional[Template]:
        """Get template by ID"""
        return self._templates.get(template_id)

    def get_template_by_name(self, tenant_id: str, name: str) -> Optional[Template]:
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
    ) -> Optional[RenderedContent]:
        """Render a template with variables"""
        template = self._templates.get(template_id)
        if not template:
            return None

        # Merge with defaults
        merged_vars = {**template.default_values, **variables}

        # Check required variables
        warnings = []
        for var in template.required_vars:
            if var not in merged_vars:
                warnings.append(f"Missing required variable: {var}")

        # Render subject and content
        rendered_subject = None
        if template.subject:
            rendered_subject = self._render_string(template.subject, merged_vars)

        rendered_content = self._render_string(template.content, merged_vars)

        # Track variables used
        used_vars = [v for v in merged_vars.keys() if v in template.variables]

        return RenderedContent(
            template_id=template_id,
            subject=rendered_subject,
            content=rendered_content,
            format=template.format,
            variables_used=used_vars,
            warnings=warnings
        )

    def _render_string(self, template_str: str, variables: Dict[str, Any]) -> str:
        """Render a template string with variables"""
        result = template_str

        # Process conditions first
        result = self._process_conditions(result, variables)

        # Process loops
        result = self._process_loops(result, variables)

        # Replace variables
        def replace_var(match):
            var_expr = match.group(1)
            parts = var_expr.split('|')
            var_name = parts[0].strip()

            # Handle nested variables (e.g., user.name)
            value = self._get_nested_value(variables, var_name)

            # Apply filters
            for filter_expr in parts[1:]:
                filter_name = filter_expr.strip()
                if filter_name in self._filters:
                    value = self._filters[filter_name](value)

            return str(value) if value is not None else match.group(0)

        result = self._variable_pattern.sub(replace_var, result)
        return result

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get nested value from dict using dot notation"""
        keys = path.split('.')
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value

    def _process_conditions(self, content: str, variables: Dict[str, Any]) -> str:
        """Process conditional blocks"""
        def replace_condition(match):
            var_name = match.group(1)
            content_block = match.group(2)
            value = variables.get(var_name)
            if value:
                return content_block
            return ""

        return self._condition_pattern.sub(replace_condition, content)

    def _process_loops(self, content: str, variables: Dict[str, Any]) -> str:
        """Process loop blocks"""
        def replace_loop(match):
            item_var = match.group(1)
            list_var = match.group(2)
            content_template = match.group(3)

            items = variables.get(list_var, [])
            if not isinstance(items, list):
                return ""

            result = []
            for item in items:
                item_vars = {**variables, item_var: item}
                rendered = self._render_string(content_template, item_vars)
                result.append(rendered)

            return "".join(result)

        return self._loop_pattern.sub(replace_loop, content)

    def update_template(
        self,
        template_id: str,
        content: Optional[str] = None,
        subject: Optional[str] = None
    ) -> Optional[Template]:
        """Update a template"""
        template = self._templates.get(template_id)
        if not template:
            return None

        if content is not None:
            template.content = content
        if subject is not None:
            template.subject = subject

        template.variables = self._extract_variables(template.content)
        if template.subject:
            template.variables.extend(self._extract_variables(template.subject))
        template.variables = list(set(template.variables))

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

    def get_templates_by_tenant(self, tenant_id: str) -> List[Template]:
        """Get all templates for a tenant"""
        return [t for t in self._templates.values() if t.tenant_id == tenant_id]

    def get_templates_by_category(self, category: TemplateCategory) -> List[Template]:
        """Get all templates of a category"""
        return [t for t in self._templates.values() if t.category == category]

    def validate_template(self, content: str) -> Dict[str, Any]:
        """Validate template syntax"""
        errors = []
        warnings = []

        # Check for unclosed tags
        open_tags = content.count('{{')
        close_tags = content.count('}}')
        if open_tags != close_tags:
            errors.append(f"Unmatched variable tags: {open_tags} opening, {close_tags} closing")

        # Check condition blocks
        if_count = len(re.findall(r'\{%\s*if\s+', content))
        endif_count = len(re.findall(r'\{%\s*endif\s*%\}', content))
        if if_count != endif_count:
            errors.append(f"Unmatched condition blocks: {if_count} if, {endif_count} endif")

        # Check loop blocks
        for_count = len(re.findall(r'\{%\s*for\s+', content))
        endfor_count = len(re.findall(r'\{%\s*endfor\s*%\}', content))
        if for_count != endfor_count:
            errors.append(f"Unmatched loop blocks: {for_count} for, {endfor_count} endfor")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
