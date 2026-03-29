"""
Week 60 - Builder 1: Documentation Generator Module
Documentation generation, API documentation, and validation
"""

import time
import json
import re
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class DocType(Enum):
    """Documentation types"""
    API = "api"
    README = "readme"
    CHANGELOG = "changelog"
    GUIDE = "guide"
    REFERENCE = "reference"


class DocFormat(Enum):
    """Output formats"""
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"
    OPENAPI = "openapi"


@dataclass
class DocSection:
    """Documentation section"""
    title: str
    content: str
    level: int = 1
    subsections: List["DocSection"] = field(default_factory=list)


@dataclass
class APIEndpoint:
    """API endpoint documentation"""
    path: str
    method: str
    description: str = ""
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    responses: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class GeneratedDoc:
    """Generated documentation"""
    doc_type: DocType
    format: DocFormat
    content: str
    sections: List[str] = field(default_factory=list)
    generated_at: float = field(default_factory=time.time)


class DocGenerator:
    """
    Documentation generator for API docs, README, and changelogs
    """

    def __init__(self):
        self.documents: Dict[str, GeneratedDoc] = {}
        self.templates: Dict[str, str] = {}
        self.lock = threading.Lock()

    def generate_readme(self, title: str, description: str,
                        sections: List[DocSection] = None) -> GeneratedDoc:
        """Generate README documentation"""
        content = f"# {title}\n\n{description}\n\n"

        for section in (sections or []):
            content += self._render_section(section)

        doc = GeneratedDoc(
            doc_type=DocType.README,
            format=DocFormat.MARKDOWN,
            content=content,
            sections=[s.title for s in (sections or [])]
        )

        with self.lock:
            self.documents[f"readme-{int(time.time())}"] = doc

        return doc

    def generate_changelog(self, changes: List[Dict[str, Any]],
                           version: str = None) -> GeneratedDoc:
        """Generate changelog"""
        content = "# Changelog\n\n"

        if version:
            content += f"## [{version}]\n\n"

        for change in changes:
            change_type = change.get("type", "changed")
            description = change.get("description", "")
            content += f"- **{change_type.title()}**: {description}\n"

        doc = GeneratedDoc(
            doc_type=DocType.CHANGELOG,
            format=DocFormat.MARKDOWN,
            content=content,
            sections=["Changelog"]
        )

        with self.lock:
            self.documents[f"changelog-{int(time.time())}"] = doc

        return doc

    def generate_guide(self, title: str, steps: List[str],
                       prerequisites: List[str] = None) -> GeneratedDoc:
        """Generate user guide"""
        content = f"# {title}\n\n"

        if prerequisites:
            content += "## Prerequisites\n\n"
            for prereq in prerequisites:
                content += f"- {prereq}\n"
            content += "\n"

        content += "## Steps\n\n"
        for i, step in enumerate(steps, 1):
            content += f"{i}. {step}\n"

        doc = GeneratedDoc(
            doc_type=DocType.GUIDE,
            format=DocFormat.MARKDOWN,
            content=content,
            sections=["Prerequisites", "Steps"]
        )

        with self.lock:
            self.documents[f"guide-{int(time.time())}"] = doc

        return doc

    def _render_section(self, section: DocSection, level: int = 1) -> str:
        """Render a documentation section"""
        prefix = "#" * (section.level + level)
        content = f"{prefix} {section.title}\n\n{section.content}\n\n"

        for subsection in section.subsections:
            content += self._render_section(subsection, level + 1)

        return content

    def register_template(self, name: str, template: str) -> None:
        """Register a documentation template"""
        with self.lock:
            self.templates[name] = template

    def get_document(self, doc_id: str) -> Optional[GeneratedDoc]:
        """Get generated document"""
        return self.documents.get(doc_id)

    def list_documents(self) -> List[str]:
        """List all documents"""
        return list(self.documents.keys())


class APIDocumenter:
    """
    API documentation generator for OpenAPI specs
    """

    def __init__(self):
        self.endpoints: Dict[str, APIEndpoint] = {}
        self.schemas: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

    def register_endpoint(self, endpoint: APIEndpoint) -> None:
        """Register an API endpoint"""
        key = f"{endpoint.method}:{endpoint.path}"
        with self.lock:
            self.endpoints[key] = endpoint

    def register_schema(self, name: str, schema: Dict[str, Any]) -> None:
        """Register a schema definition"""
        with self.lock:
            self.schemas[name] = schema

    def generate_openapi(self, title: str = "API",
                         version: str = "1.0.0",
                         description: str = "") -> Dict[str, Any]:
        """Generate OpenAPI specification"""
        paths = {}

        for key, endpoint in self.endpoints.items():
            if endpoint.path not in paths:
                paths[endpoint.path] = {}

            paths[endpoint.path][endpoint.method.lower()] = {
                "summary": endpoint.description,
                "parameters": endpoint.parameters,
                "responses": endpoint.responses,
                "tags": endpoint.tags
            }

        return {
            "openapi": "3.0.0",
            "info": {
                "title": title,
                "version": version,
                "description": description
            },
            "paths": paths,
            "components": {
                "schemas": self.schemas
            }
        }

    def generate_markdown_docs(self) -> str:
        """Generate markdown API documentation"""
        content = "# API Documentation\n\n"

        for key, endpoint in self.endpoints.items():
            content += f"## {endpoint.method} {endpoint.path}\n\n"
            content += f"{endpoint.description}\n\n"

            if endpoint.parameters:
                content += "### Parameters\n\n"
                for param in endpoint.parameters:
                    name = param.get("name", "")
                    desc = param.get("description", "")
                    content += f"- **{name}**: {desc}\n"
                content += "\n"

            if endpoint.responses:
                content += "### Responses\n\n"
                for code, response in endpoint.responses.items():
                    content += f"- **{code}**: {response}\n"
                content += "\n"

        return content

    def get_endpoint(self, method: str, path: str) -> Optional[APIEndpoint]:
        """Get endpoint by method and path"""
        key = f"{method}:{path}"
        return self.endpoints.get(key)

    def list_endpoints(self) -> List[APIEndpoint]:
        """List all registered endpoints"""
        return list(self.endpoints.values())


class DocValidator:
    """
    Documentation validator for coverage, links, and examples
    """

    def __init__(self):
        self.validation_results: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

    def validate_coverage(self, code_elements: List[str],
                          documented: List[str]) -> Dict[str, Any]:
        """Validate documentation coverage"""
        covered = set(documented)
        total = set(code_elements)
        uncovered = total - covered

        coverage_pct = len(covered) / len(total) * 100 if total else 0

        return {
            "total_elements": len(total),
            "documented": len(covered),
            "uncovered": list(uncovered),
            "coverage_percentage": coverage_pct
        }

    def validate_links(self, content: str) -> Dict[str, Any]:
        """Validate links in documentation"""
        # Find markdown links
        link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
        links = re.findall(link_pattern, content)

        broken = []
        valid = []

        for text, url in links:
            # Simple validation (in real impl, check if URL exists)
            if url.startswith("http") or url.startswith("/"):
                valid.append({"text": text, "url": url})
            elif url.startswith("#"):
                valid.append({"text": text, "url": url})
            else:
                broken.append({"text": text, "url": url})

        return {
            "total_links": len(links),
            "valid_links": len(valid),
            "broken_links": len(broken),
            "broken": broken
        }

    def validate_examples(self, doc: GeneratedDoc) -> Dict[str, Any]:
        """Validate code examples in documentation"""
        # Find code blocks
        code_pattern = r"```(\w+)?\n([\s\S]*?)```"
        examples = re.findall(code_pattern, doc.content)

        results = []
        for lang, code in examples:
            results.append({
                "language": lang or "unknown",
                "has_content": len(code.strip()) > 0,
                "line_count": len(code.strip().split("\n"))
            })

        return {
            "total_examples": len(examples),
            "examples": results
        }

    def validate_doc(self, doc_id: str, doc: GeneratedDoc,
                     code_elements: List[str] = None,
                     documented: List[str] = None) -> Dict[str, Any]:
        """Run all validations on a document"""
        results = {
            "doc_id": doc_id,
            "doc_type": doc.doc_type.value,
            "validated_at": time.time()
        }

        # Link validation
        results["links"] = self.validate_links(doc.content)

        # Example validation
        results["examples"] = self.validate_examples(doc)

        # Coverage validation (if provided)
        if code_elements and documented:
            results["coverage"] = self.validate_coverage(code_elements, documented)

        with self.lock:
            self.validation_results[doc_id] = results

        return results

    def get_result(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get validation result"""
        return self.validation_results.get(doc_id)
