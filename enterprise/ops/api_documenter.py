# API Documenter - Week 50 Builder 5
# API documentation generation

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class HttpMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class ParameterLocation(Enum):
    PATH = "path"
    QUERY = "query"
    HEADER = "header"
    BODY = "body"


@dataclass
class ApiParameter:
    name: str = ""
    location: ParameterLocation = ParameterLocation.QUERY
    data_type: str = "string"
    required: bool = True
    description: str = ""
    default: Optional[str] = None
    example: Optional[str] = None


@dataclass
class ApiResponse:
    status_code: int = 200
    description: str = "Success"
    content_type: str = "application/json"
    schema: Dict[str, Any] = field(default_factory=dict)
    example: Optional[str] = None


@dataclass
class ApiEndpoint:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    path: str = ""
    method: HttpMethod = HttpMethod.GET
    summary: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    parameters: List[ApiParameter] = field(default_factory=list)
    responses: List[ApiResponse] = field(default_factory=list)
    deprecated: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ApiDocument:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    version: str = "1.0.0"
    base_url: str = ""
    description: str = ""
    endpoints: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


class ApiDocumenter:
    """Generates API documentation"""

    def __init__(self):
        self._documents: Dict[str, ApiDocument] = {}
        self._endpoints: Dict[str, ApiEndpoint] = {}
        self._metrics = {
            "total_documents": 0,
            "total_endpoints": 0,
            "by_method": {}
        }

    def create_document(
        self,
        title: str,
        version: str = "1.0.0",
        base_url: str = "",
        description: str = ""
    ) -> ApiDocument:
        """Create an API document"""
        doc = ApiDocument(
            title=title,
            version=version,
            base_url=base_url,
            description=description
        )
        self._documents[doc.id] = doc
        self._metrics["total_documents"] += 1
        return doc

    def add_endpoint(
        self,
        document_id: str,
        path: str,
        method: HttpMethod,
        summary: str = "",
        description: str = "",
        tags: Optional[List[str]] = None
    ) -> Optional[ApiEndpoint]:
        """Add an endpoint to a document"""
        doc = self._documents.get(document_id)
        if not doc:
            return None

        endpoint = ApiEndpoint(
            path=path,
            method=method,
            summary=summary,
            description=description,
            tags=tags or []
        )
        self._endpoints[endpoint.id] = endpoint
        doc.endpoints.append(endpoint.id)
        self._metrics["total_endpoints"] += 1

        method_key = method.value
        self._metrics["by_method"][method_key] = self._metrics["by_method"].get(method_key, 0) + 1

        return endpoint

    def add_parameter(
        self,
        endpoint_id: str,
        name: str,
        location: ParameterLocation,
        data_type: str = "string",
        required: bool = True,
        description: str = "",
        default: Optional[str] = None,
        example: Optional[str] = None
    ) -> bool:
        """Add a parameter to an endpoint"""
        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint:
            return False

        param = ApiParameter(
            name=name,
            location=location,
            data_type=data_type,
            required=required,
            description=description,
            default=default,
            example=example
        )
        endpoint.parameters.append(param)
        return True

    def add_response(
        self,
        endpoint_id: str,
        status_code: int,
        description: str = "Success",
        content_type: str = "application/json",
        schema: Optional[Dict[str, Any]] = None,
        example: Optional[str] = None
    ) -> bool:
        """Add a response to an endpoint"""
        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint:
            return False

        response = ApiResponse(
            status_code=status_code,
            description=description,
            content_type=content_type,
            schema=schema or {},
            example=example
        )
        endpoint.responses.append(response)
        return True

    def get_endpoint(self, endpoint_id: str) -> Optional[ApiEndpoint]:
        """Get endpoint by ID"""
        return self._endpoints.get(endpoint_id)

    def get_document(self, document_id: str) -> Optional[ApiDocument]:
        """Get document by ID"""
        return self._documents.get(document_id)

    def get_endpoints_by_tag(self, tag: str) -> List[ApiEndpoint]:
        """Get all endpoints with a tag"""
        return [e for e in self._endpoints.values() if tag in e.tags]

    def get_endpoints_by_method(self, method: HttpMethod) -> List[ApiEndpoint]:
        """Get all endpoints of a method"""
        return [e for e in self._endpoints.values() if e.method == method]

    def deprecate_endpoint(self, endpoint_id: str) -> bool:
        """Mark endpoint as deprecated"""
        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint:
            return False
        endpoint.deprecated = True
        return True

    def generate_openapi_spec(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Generate OpenAPI specification"""
        doc = self._documents.get(document_id)
        if not doc:
            return None

        paths = {}
        for endpoint_id in doc.endpoints:
            endpoint = self._endpoints.get(endpoint_id)
            if not endpoint:
                continue

            if endpoint.path not in paths:
                paths[endpoint.path] = {}

            path_item = {
                "summary": endpoint.summary,
                "description": endpoint.description,
                "tags": endpoint.tags,
                "deprecated": endpoint.deprecated,
                "parameters": [
                    {
                        "name": p.name,
                        "in": p.location.value,
                        "required": p.required,
                        "schema": {"type": p.data_type},
                        "description": p.description
                    }
                    for p in endpoint.parameters
                ],
                "responses": {
                    str(r.status_code): {
                        "description": r.description,
                        "content": {
                            r.content_type: {
                                "schema": r.schema
                            }
                        }
                    }
                    for r in endpoint.responses
                }
            }

            paths[endpoint.path][endpoint.method.value.lower()] = path_item

        return {
            "openapi": "3.0.0",
            "info": {
                "title": doc.title,
                "version": doc.version,
                "description": doc.description
            },
            "servers": [{"url": doc.base_url}] if doc.base_url else [],
            "paths": paths
        }

    def generate_markdown_docs(self, document_id: str) -> Optional[str]:
        """Generate markdown documentation"""
        doc = self._documents.get(document_id)
        if not doc:
            return None

        md = f"# {doc.title}\n\n"
        md += f"Version: {doc.version}\n\n"
        md += f"{doc.description}\n\n"
        md += f"Base URL: `{doc.base_url}`\n\n"

        md += "## Endpoints\n\n"

        for endpoint_id in doc.endpoints:
            endpoint = self._endpoints.get(endpoint_id)
            if not endpoint:
                continue

            md += f"### {endpoint.method.value} {endpoint.path}\n\n"
            md += f"{endpoint.summary}\n\n"

            if endpoint.deprecated:
                md += "> ⚠️ **Deprecated**\n\n"

            if endpoint.parameters:
                md += "**Parameters:**\n\n"
                md += "| Name | Location | Type | Required | Description |\n"
                md += "|------|----------|------|----------|-------------|\n"
                for p in endpoint.parameters:
                    md += f"| {p.name} | {p.location.value} | {p.data_type} | {p.required} | {p.description} |\n"
                md += "\n"

            if endpoint.responses:
                md += "**Responses:**\n\n"
                for r in endpoint.responses:
                    md += f"- `{r.status_code}` - {r.description}\n"
                md += "\n"

        return md

    def search_endpoints(self, query: str) -> List[ApiEndpoint]:
        """Search endpoints by path or summary"""
        query_lower = query.lower()
        return [
            e for e in self._endpoints.values()
            if query_lower in e.path.lower() or query_lower in e.summary.lower()
        ]

    def get_metrics(self) -> Dict[str, Any]:
        return self._metrics.copy()
