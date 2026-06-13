"""
PARWA OpenAPI Importer Service (Tier 2)

Parses OpenAPI/Swagger specs and auto-generates connector definitions.
PARWA High only — per D4/D5.

Supports:
- OpenAPI v3.0 and v3.1
- Swagger v2.0
- URL or file upload input
- Auto-detection of auth from securitySchemes
- Auto-generation of action names, descriptions, parameters

Per GAP 5: Max 100 endpoints per spec. Skip deprecated endpoints.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx
import yaml

from app.logger import get_logger

logger = get_logger("openapi_importer")

# Max endpoints per spec (GAP 5)
MAX_ENDPOINTS_PER_SPEC = 100

# HTTP methods we import
IMPORTABLE_METHODS = {"get", "post", "put", "patch", "delete"}


class OpenAPIImporterService:
    """Service to parse OpenAPI specs and generate connector action definitions."""

    def import_from_url(self, url: str) -> Dict[str, Any]:
        """Fetch and parse an OpenAPI spec from a URL.

        Args:
            url: URL to the OpenAPI spec (JSON or YAML).

        Returns:
            Parsed spec dict with auto-generated actions.
        """
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url)
                response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "yaml" in content_type or "yml" in content_type or url.endswith((".yaml", ".yml")):
                spec = yaml.safe_load(response.text)
            else:
                spec = response.json()

            return self._parse_spec(spec, source_url=url)

        except httpx.HTTPStatusError as e:
            raise ValueError(f"Failed to fetch spec from URL: HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            raise ValueError(f"Failed to fetch spec from URL: {str(e)}")
        except (yaml.YAMLError, json.JSONDecodeError) as e:
            raise ValueError(f"Failed to parse spec: invalid format — {str(e)}")

    def import_from_content(self, content: str, filename: str = "") -> Dict[str, Any]:
        """Parse an OpenAPI spec from uploaded file content.

        Args:
            content: Raw file content (JSON or YAML).
            filename: Original filename for context.

        Returns:
            Parsed spec dict with auto-generated actions.
        """
        if not content or not content.strip():
            raise ValueError("Empty spec provided")

        try:
            if filename.endswith((".yaml", ".yml")):
                spec = yaml.safe_load(content)
            else:
                spec = json.loads(content)

            return self._parse_spec(spec, source_file=filename)

        except (yaml.YAMLError, json.JSONDecodeError) as e:
            raise ValueError(f"Failed to parse spec: invalid format — {str(e)}")

    def _parse_spec(
        self,
        spec: Dict[str, Any],
        source_url: str = "",
        source_file: str = "",
    ) -> Dict[str, Any]:
        """Parse a raw OpenAPI spec into a structured connector definition.

        Returns a dict with:
        - name: Integration name (from info.title)
        - base_url: Base URL (from servers[0].url)
        - auth_type: Detected auth type
        - auth_fields: List of auth field definitions
        - actions: List of action definitions
        - source: "openapi_import"
        """
        if not spec:
            raise ValueError("Empty spec provided")

        # Detect spec version
        swagger_version = spec.get("swagger")
        openapi_version = spec.get("openapi")

        if not swagger_version and not openapi_version:
            raise ValueError("Not a valid OpenAPI/Swagger spec — missing 'swagger' or 'openapi' version field")

        # Extract metadata
        info = spec.get("info", {})
        name = info.get("title", "Imported API")
        description = info.get("description", "")

        # Extract base URL
        base_url = self._extract_base_url(spec)

        # Detect auth
        auth_type, auth_fields = self._detect_auth(spec)

        # Parse paths → actions
        actions = self._parse_paths(spec)

        if not actions:
            raise ValueError("No importable endpoints found in the spec")

        # Sort actions: GET first, then POST, PUT, PATCH, DELETE
        method_order = {"get": 0, "post": 1, "put": 2, "patch": 3, "delete": 4}
        actions.sort(key=lambda a: (method_order.get(a["method"], 5), a["path"]))

        return {
            "name": name,
            "description": description,
            "base_url": base_url,
            "auth_type": auth_type,
            "auth_fields": auth_fields,
            "actions": actions,
            "source": "openapi_import",
            "source_url": source_url,
            "source_file": source_file,
            "openapi_version": openapi_version or swagger_version,
            "endpoint_count": len(actions),
        }

    def _extract_base_url(self, spec: Dict[str, Any]) -> str:
        """Extract the base URL from the spec's servers field."""
        servers = spec.get("servers", [])
        if servers:
            first_server = servers[0]
            url = first_server.get("url", "")
            # Handle server variables
            variables = first_server.get("variables", {})
            for var_name, var_def in variables.items():
                default_val = var_def.get("default", "")
                if default_val:
                    url = url.replace(f"{{{var_name}}}", default_val)
            return url.rstrip("/")

        # Swagger v2 host + basePath
        host = spec.get("host", "")
        base_path = spec.get("basePath", "")
        schemes = spec.get("schemes", ["https"])
        if host:
            scheme = schemes[0] if schemes else "https"
            return f"{scheme}://{host}{base_path}".rstrip("/")

        return ""

    def _detect_auth(self, spec: Dict[str, Any]) -> tuple:
        """Detect authentication from the spec's securitySchemes.

        Returns (auth_type, auth_fields) tuple.
        auth_type is one of: bearer, api_key_header, api_key_query, basic_auth, oauth2
        """
        # OpenAPI v3: components.securitySchemes
        components = spec.get("components", {})
        security_schemes = components.get("securitySchemes", {})

        # Swagger v2: securityDefinitions
        if not security_schemes:
            security_schemes = spec.get("securityDefinitions", {})

        if not security_schemes:
            # No auth detected — default to bearer for custom connector
            return "bearer", [
                {"name": "api_key", "label": "API Key", "type": "password", "required": True, "placeholder": ""}
            ]

        # Use the first security scheme found
        for scheme_name, scheme_def in security_schemes.items():
            scheme_type = scheme_def.get("type", "").lower()

            if scheme_type == "http":
                http_scheme = scheme_def.get("scheme", "").lower()
                if http_scheme == "bearer":
                    return "bearer", [
                        {"name": "api_key", "label": f"Bearer Token ({scheme_name})", "type": "password", "required": True, "placeholder": ""}
                    ]
                elif http_scheme == "basic":
                    return "basic_auth", [
                        {"name": "username", "label": "Username", "type": "text", "required": True, "placeholder": ""},
                        {"name": "password", "label": "Password", "type": "password", "required": True, "placeholder": ""},
                    ]

            elif scheme_type == "apikey":
                api_key_in = scheme_def.get("in", "header")
                header_name = scheme_def.get("name", "X-API-Key")
                if api_key_in == "query":
                    return "api_key_query", [
                        {"name": "api_key", "label": f"API Key ({scheme_name})", "type": "password", "required": True, "placeholder": ""}
                    ]
                else:
                    return "api_key_header", [
                        {"name": "api_key", "label": f"API Key ({scheme_name})", "type": "password", "required": True, "placeholder": ""}
                    ]

            elif scheme_type == "oauth2":
                flows = scheme_def.get("flows", {})
                return "oauth2", [
                    {"name": "client_id", "label": "Client ID", "type": "text", "required": True, "placeholder": ""},
                    {"name": "client_secret", "label": "Client Secret", "type": "password", "required": True, "placeholder": ""},
                    {"name": "refresh_token", "label": "Refresh Token", "type": "password", "required": True, "placeholder": ""},
                ]

        # Fallback: bearer
        return "bearer", [
            {"name": "api_key", "label": "API Key", "type": "password", "required": True, "placeholder": ""}
        ]

    def _parse_paths(self, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse all paths from the spec into action definitions.

        Per GAP 5:
        - Only import GET, POST, PUT, PATCH, DELETE
        - Skip deprecated endpoints (mark but don't enable)
        - Max 100 endpoints
        """
        paths = spec.get("paths", {})
        actions: List[Dict[str, Any]] = []
        endpoint_count = 0

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            # Path-level parameters
            path_level_params = path_item.get("parameters", [])

            for method in IMPORTABLE_METHODS:
                operation = path_item.get(method)
                if not operation or not isinstance(operation, dict):
                    continue

                # Enforce max endpoints
                if endpoint_count >= MAX_ENDPOINTS_PER_SPEC:
                    logger.warning(
                        "openapi_import_max_endpoints_reached",
                        max=MAX_ENDPOINTS_PER_SPEC,
                    )
                    return actions

                # Skip deprecated (GAP 5)
                is_deprecated = operation.get("deprecated", False)
                if is_deprecated:
                    continue

                # Generate action name
                action_name = self._generate_action_name(operation, method, path)

                # Generate description
                action_desc = self._generate_description(operation, method, path)

                # Extract parameters
                required_params, optional_params = self._extract_params(
                    operation, path, path_level_params
                )

                # Extract response key
                response_key = self._extract_response_key(operation)

                actions.append({
                    "name": action_name,
                    "method": method.upper(),
                    "path": path,
                    "description": action_desc,
                    "params": {
                        "required": required_params,
                        "optional": optional_params,
                    },
                    "response_key": response_key,
                    "enabled": True,
                })

                endpoint_count += 1

        return actions

    def _generate_action_name(self, operation: Dict, method: str, path: str) -> str:
        """Generate a human-readable action name from operationId or path."""
        # Prefer operationId
        operation_id = operation.get("operationId")
        if operation_id:
            # Split camelCase: "listPets" → "list Pets", then replace hyphens/underscores
            name = re.sub(r"([a-z])([A-Z])", r"\1 \2", operation_id)
            name = re.sub(r"[-_]", " ", name)
            return name.title()

        # Fallback: Method + Path
        # e.g. GET /users/{id} → "Get User"
        summary = operation.get("summary")
        if summary:
            return summary.strip()

        # Generate from method + path segments
        path_parts = [p for p in path.split("/") if p and not p.startswith("{")]
        resource = path_parts[-1] if path_parts else "Resource"
        singular = resource.rstrip("s") if resource.endswith("s") and len(resource) > 2 else resource
        return f"{method.capitalize()} {singular.title()}"

    def _generate_description(self, operation: Dict, method: str, path: str) -> str:
        """Generate a description for an action from the spec."""
        desc = operation.get("description", "")
        summary = operation.get("summary", "")

        if desc:
            # Truncate very long descriptions
            if len(desc) > 500:
                desc = desc[:497] + "..."
            return desc

        if summary:
            return summary

        # Fallback: generate from method + path
        return f"Calls {method.upper()} {path}"

    def _extract_params(
        self,
        operation: Dict,
        path: str,
        path_level_params: List,
    ) -> tuple:
        """Extract required and optional parameters from an operation.

        Returns (required_params, optional_params) lists of param names.
        """
        required: List[str] = []
        optional: List[str] = []

        # Path parameters are always required
        path_params = re.findall(r"\{(\w+)\}", path)
        for p in path_params:
            if p not in required:
                required.append(p)

        # Operation parameters
        op_params = operation.get("parameters", [])
        all_params = path_level_params + op_params

        for param in all_params:
            if not isinstance(param, dict):
                continue
            name = param.get("name", "")
            if not name:
                continue
            param_in = param.get("in", "")
            required_flag = param.get("required", False)

            # Path params already captured
            if param_in == "path":
                continue

            if required_flag:
                if name not in required:
                    required.append(name)
            else:
                if name not in optional:
                    optional.append(name)

        # Request body parameters
        request_body = operation.get("requestBody", {})
        if request_body:
            content = request_body.get("content", {})
            json_content = content.get("application/json", {})
            schema = json_content.get("schema", {})
            required_body = schema.get("required", [])
            properties = schema.get("properties", {})

            for prop_name in required_body:
                if prop_name not in required:
                    required.append(prop_name)

            for prop_name in properties:
                if prop_name not in required and prop_name not in optional:
                    optional.append(prop_name)

        return required, optional

    def _extract_response_key(self, operation: Dict) -> str:
        """Extract the key path to the main data in the response."""
        responses = operation.get("responses", {})
        ok_response = responses.get("200") or responses.get("201") or responses.get("default", {})
        content = ok_response.get("content", {}) if isinstance(ok_response, dict) else {}
        json_content = content.get("application/json", {})
        schema = json_content.get("schema", {})

        # Try to find a common data wrapper
        properties = schema.get("properties", {})
        if "data" in properties:
            return "data"
        if "results" in properties:
            return "results"
        if "items" in properties:
            return "items"

        return ""
