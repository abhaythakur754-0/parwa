# Doc Generator - Week 50 Builder 5
# Auto documentation generation

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class DocType(Enum):
    README = "readme"
    API = "api"
    GUIDE = "guide"
    REFERENCE = "reference"
    CHANGELOG = "changelog"


class DocFormat(Enum):
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"


@dataclass
class DocSection:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    content: str = ""
    order: int = 0
    parent_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Document:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    doc_type: DocType = DocType.README
    format: DocFormat = DocFormat.MARKDOWN
    version: str = "1.0.0"
    sections: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


class DocGenerator:
    """Generates documentation automatically"""

    def __init__(self):
        self._documents: Dict[str, Document] = {}
        self._sections: Dict[str, DocSection] = {}
        self._templates: Dict[str, str] = {}
        self._metrics = {
            "total_documents": 0,
            "total_sections": 0,
            "by_type": {}
        }

    def create_document(
        self,
        title: str,
        doc_type: DocType,
        version: str = "1.0.0",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Document:
        """Create a new document"""
        doc = Document(
            title=title,
            doc_type=doc_type,
            version=version,
            metadata=metadata or {}
        )
        self._documents[doc.id] = doc
        self._metrics["total_documents"] += 1

        type_key = doc_type.value
        self._metrics["by_type"][type_key] = self._metrics["by_type"].get(type_key, 0) + 1

        return doc

    def add_section(
        self,
        document_id: str,
        title: str,
        content: str,
        parent_id: Optional[str] = None,
        order: int = 0
    ) -> Optional[DocSection]:
        """Add a section to a document"""
        doc = self._documents.get(document_id)
        if not doc:
            return None

        section = DocSection(
            title=title,
            content=content,
            parent_id=parent_id,
            order=order
        )
        self._sections[section.id] = section
        doc.sections.append(section.id)
        self._metrics["total_sections"] += 1

        return section

    def get_section(self, section_id: str) -> Optional[DocSection]:
        """Get section by ID"""
        return self._sections.get(section_id)

    def update_section(self, section_id: str, content: str) -> bool:
        """Update section content"""
        section = self._sections.get(section_id)
        if not section:
            return False
        section.content = content
        return True

    def remove_section(self, document_id: str, section_id: str) -> bool:
        """Remove a section from a document"""
        doc = self._documents.get(document_id)
        if not doc or section_id not in doc.sections:
            return False

        doc.sections.remove(section_id)
        if section_id in self._sections:
            del self._sections[section_id]

        return True

    def generate_document(self, document_id: str) -> Optional[str]:
        """Generate document content"""
        doc = self._documents.get(document_id)
        if not doc:
            return None

        sections = []
        for section_id in doc.sections:
            section = self._sections.get(section_id)
            if section:
                sections.append(section)

        # Sort by order
        sections.sort(key=lambda s: s.order)

        # Generate markdown
        content = f"# {doc.title}\n\n"
        content += f"Version: {doc.version}\n\n"

        for section in sections:
            content += f"## {section.title}\n\n"
            content += f"{section.content}\n\n"

        doc.generated_at = datetime.utcnow()
        return content

    def set_template(self, name: str, template: str) -> None:
        """Set a document template"""
        self._templates[name] = template

    def get_template(self, name: str) -> Optional[str]:
        """Get a template by name"""
        return self._templates.get(name)

    def apply_template(
        self,
        document_id: str,
        template_name: str,
        variables: Dict[str, str]
    ) -> bool:
        """Apply a template to a document"""
        template = self._templates.get(template_name)
        if not template:
            return False

        content = template
        for key, value in variables.items():
            content = content.replace(f"{{{{{key}}}}}", value)

        doc = self._documents.get(document_id)
        if not doc:
            return False

        self.add_section(document_id, "Generated", content)
        return True

    def get_document(self, document_id: str) -> Optional[Document]:
        """Get document by ID"""
        return self._documents.get(document_id)

    def get_documents_by_type(self, doc_type: DocType) -> List[Document]:
        """Get all documents of a type"""
        return [d for d in self._documents.values() if d.doc_type == doc_type]

    def search_sections(self, query: str) -> List[DocSection]:
        """Search sections by content"""
        query_lower = query.lower()
        return [
            s for s in self._sections.values()
            if query_lower in s.title.lower() or query_lower in s.content.lower()
        ]

    def export_document(self, document_id: str, format: DocFormat) -> Optional[str]:
        """Export document in specified format"""
        content = self.generate_document(document_id)
        if not content:
            return None

        if format == DocFormat.MARKDOWN:
            return content
        elif format == DocFormat.HTML:
            # Simple markdown to HTML conversion
            html = content.replace("\n#", "\n<h1>").replace("# ", "</h1>\n")
            html = html.replace("## ", "<h2>").replace("\n\n", "</h2>\n<p>")
            return f"<html><body>{html}</p></body></html>"
        elif format == DocFormat.JSON:
            import json
            doc = self._documents.get(document_id)
            return json.dumps({
                "title": doc.title,
                "version": doc.version,
                "sections": [
                    {"title": self._sections[sid].title, "content": self._sections[sid].content}
                    for sid in doc.sections if sid in self._sections
                ]
            })

        return content

    def get_metrics(self) -> Dict[str, Any]:
        return self._metrics.copy()
