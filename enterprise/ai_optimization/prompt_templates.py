"""Prompt Templates Module - Week 55, Builder 5"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import logging
import re

logger = logging.getLogger(__name__)


class TemplateType(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FEW_SHOT = "few_shot"


@dataclass
class TemplateVariable:
    name: str
    type: str = "str"
    default: Any = None
    required: bool = True
    description: str = ""

    def validate(self, value: Any) -> bool:
        if value is None:
            return not self.required or self.default is not None
        return True


@dataclass
class PromptTemplate:
    name: str
    template: str
    variables: List[TemplateVariable] = field(default_factory=list)
    template_type: TemplateType = TemplateType.USER
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def render(self, **kwargs) -> str:
        result = self.template
        for var in self.variables:
            value = kwargs.get(var.name, var.default)
            if value is None and var.required:
                raise ValueError(f"Missing required variable: {var.name}")
            if value is not None:
                result = result.replace(f"{{{var.name}}}", str(value))
        return result

    def extract_variables(self) -> List[str]:
        return re.findall(r'\{(\w+)\}', self.template)


class TemplateRegistry:
    def __init__(self):
        self.templates: Dict[str, PromptTemplate] = {}
        self._setup_defaults()

    def _setup_defaults(self) -> None:
        # Add default templates
        self.register(PromptTemplate(
            name="chat",
            template="You are a helpful assistant.\n\nUser: {input}\nAssistant:",
            variables=[TemplateVariable(name="input", description="User input")],
            template_type=TemplateType.SYSTEM,
        ))
        self.register(PromptTemplate(
            name="qa",
            template="Question: {question}\n\nAnswer:",
            variables=[TemplateVariable(name="question", description="Question to answer")],
        ))
        self.register(PromptTemplate(
            name="summarize",
            template="Please summarize the following text:\n\n{text}\n\nSummary:",
            variables=[TemplateVariable(name="text", description="Text to summarize")],
        ))

    def register(self, template: PromptTemplate) -> None:
        self.templates[template.name] = template
        logger.info(f"Registered template: {template.name}")

    def unregister(self, name: str) -> bool:
        if name in self.templates:
            del self.templates[name]
            return True
        return False

    def get(self, name: str) -> Optional[PromptTemplate]:
        return self.templates.get(name)

    def render(self, name: str, **kwargs) -> str:
        template = self.get(name)
        if not template:
            raise KeyError(f"Template not found: {name}")
        return template.render(**kwargs)

    def list_templates(self) -> List[str]:
        return list(self.templates.keys())

    def get_by_type(self, template_type: TemplateType) -> List[PromptTemplate]:
        return [t for t in self.templates.values() if t.template_type == template_type]


def create_template(name: str, template: str, variables: Optional[Dict[str, Any]] = None) -> PromptTemplate:
    var_list = []
    if variables:
        for var_name, var_config in variables.items():
            if isinstance(var_config, dict):
                var_list.append(TemplateVariable(name=var_name, **var_config))
            else:
                var_list.append(TemplateVariable(name=var_name, default=var_config))

    # Extract variables from template if not provided
    if not var_list:
        found_vars = re.findall(r'\{(\w+)\}', template)
        var_list = [TemplateVariable(name=v) for v in found_vars]

    return PromptTemplate(name=name, template=template, variables=var_list)
