"""
PARWA Phase 3 — OpenAPI Spec Importer

Parses OpenAPI v2.0 (Swagger) and v3.0/v3.1 specifications and auto-generates
connector definitions that can be stored as CustomConnector records.

Supports: OpenAPI 2.0 (Swagger), OpenAPI 3.0/3.1
Max 100 endpoints per spec.

CRITICAL RULES:
- BC-001: All queries scoped to company_id
- BC-008: Never crash — all external calls in try/except
- No mock data, no TODO/FIXME
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Maximum number of endpoints to import from a single spec
MAX_ENDPOINTS = 100

# HTTP methods to process (skip OPTIONS and HEAD)
PROCESSABLE_METHODS = {"get", "post", "put", "patch", "delete"}

# Auth type mapping from OpenAPI security schemes to PARWA auth types
SECURITY_SCHEME_MAP: Dict[str, str] = {
    "basic": "basic_auth",
    "apikey": "api_key_header",
    "oauth2": "oauth2",
    "bearer": "bearer",
}


class OpenAPIImporter:
    """Parse OpenAPI specs and auto-generate connector definitions.

    Supports: OpenAPI 2.0 (Swagger), OpenAPI 3.0/3.1
    Max 100 endpoints per spec.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def import_from_url(self, url: str, company_id: str) -> Dict[str, Any]:
        """Import OpenAPI spec from URL.

        Downloads the spec from the given URL and parses it.

        Parameters
        ----------
        url:
            The URL pointing to an OpenAPI spec (JSON or YAML).
        company_id:
            Tenant identifier (BC-001).

        Returns
        -------
        dict
            The generated connector definition.
        """
        try:
            content = self._fetch_url(url)
            if content is None:
                return {
                    "success": False,
                    "error": f"Failed to fetch spec from URL: {url}",
                    "company_id": company_id,
                }

            return self.import_from_file(content, "remote_spec", company_id)

        except Exception as exc:
            logger.error(
                "import_from_url failed for url=%s company_id=%s: %s",
                url,
                company_id,
                exc,
            )
            return {
                "success": False,
                "error": str(exc),
                "company_id": company_id,
                "url": url,
            }

    def import_from_file(
        self, file_content: str, filename: str, company_id: str
    ) -> Dict[str, Any]:
        """Import OpenAPI spec from file content (JSON or YAML).

        Parameters
        ----------
        file_content:
            Raw string content of the spec file.
        filename:
            Original filename (used for connector naming and format detection).
        company_id:
            Tenant identifier (BC-001).

        Returns
        -------
        dict
            The generated connector definition.
        """
        try:
            spec = self._parse_content(file_content, filename)
            if spec is None:
                return {
                    "success": False,
                    "error": "Failed to parse spec content — invalid JSON or YAML",
                    "company_id": company_id,
                    "filename": filename,
                }

            return self.parse_spec(spec, company_id)

        except Exception as exc:
            logger.error(
                "import_from_file failed for filename=%s company_id=%s: %s",
                filename,
                company_id,
                exc,
            )
            return {
                "success": False,
                "error": str(exc),
                "company_id": company_id,
                "filename": filename,
            }

    def parse_spec(
        self, spec: Dict[str, Any], company_id: str
    ) -> Dict[str, Any]:
        """Parse OpenAPI spec into connector definition.

        Steps:
        1. Extract base URL from servers/host
        2. Extract endpoints → convert to actions
        3. Auto-generate action names from operationId or summary
        4. Auto-generate descriptions from description/summary fields
        5. Auto-detect auth from securitySchemes
        6. Map parameters from parameters/requestBody

        Parameters
        ----------
        spec:
            Parsed OpenAPI spec as a dict.
        company_id:
            Tenant identifier (BC-001).

        Returns
        -------
        dict
            Generated connector definition compatible with CustomConnector model.
        """
        try:
            if not spec or not isinstance(spec, dict):
                return {
                    "success": False,
                    "error": "Invalid spec: must be a non-empty dictionary",
                    "company_id": company_id,
                }

            # Detect spec version
            version = self._detect_version(spec)

            # Step 1: Extract base URL
            base_url = self._extract_base_url(spec, version)

            if not base_url:
                return {
                    "success": False,
                    "error": "Could not determine base URL from spec (missing servers/host)",
                    "company_id": company_id,
                    "spec_version": version,
                }

            # Step 2: Extract endpoints → convert to actions
            paths = spec.get("paths", {})
            actions = self._extract_actions(paths)

            if not actions:
                return {
                    "success": False,
                    "error": "No processable endpoints found in spec",
                    "company_id": company_id,
                    "base_url": base_url,
                    "spec_version": version,
                }

            # Step 3: Auto-detect auth
            auth_config = self._detect_auth(spec)

            # Step 4: Extract spec metadata
            spec_info = spec.get("info", {})
            connector_name = (
                spec_info.get("title", "Imported API")
                .strip()
                .replace(" ", "_")
                .replace("-", "_")
            )
            # Clean connector name to be a valid identifier
            connector_name = re.sub(r"[^a-zA-Z0-9_]", "", connector_name) or "imported_api"
            description = spec_info.get("description", f"Imported from OpenAPI {version} spec")

            # Build connector definition
            connector_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()

            connector_def = {
                "success": True,
                "connector": {
                    "id": connector_id,
                    "company_id": company_id,
                    "name": connector_name,
                    "base_url": base_url,
                    "auth_type": auth_config.get("auth_type", "none"),
                    "auth_schema": auth_config.get("auth_schema", []),
                    "security_schemes": auth_config.get("security_schemes", {}),
                    "encrypted_auth": None,
                    "actions": actions,
                    "source": "openapi_import",
                    "is_active": True,
                    "spec_version": version,
                    "description": description,
                    "created_at": now,
                    "updated_at": now,
                },
                "stats": {
                    "total_endpoints": len(actions),
                    "auth_type": auth_config.get("auth_type", "none"),
                    "spec_version": version,
                    "base_url": base_url,
                },
                "company_id": company_id,
            }

            logger.info(
                "Parsed OpenAPI %s spec for company_id=%s: %d actions, base_url=%s",
                version,
                company_id,
                len(actions),
                base_url,
            )

            return connector_def

        except Exception as exc:
            logger.error(
                "parse_spec failed for company_id=%s: %s", company_id, exc
            )
            return {
                "success": False,
                "error": str(exc),
                "company_id": company_id,
            }

    # ------------------------------------------------------------------
    # Action extraction
    # ------------------------------------------------------------------

    def _extract_actions(self, paths: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract actions from spec paths.

        Skips OPTIONS, HEAD, and deprecated endpoints.
        Enforces MAX_ENDPOINTS limit.

        Parameters
        ----------
        paths:
            The "paths" section of the OpenAPI spec.

        Returns
        -------
        list[dict]
            List of action definitions.
        """
        try:
            actions: List[Dict[str, Any]] = []
            seen_names: set = set()

            for path, path_item in paths.items():
                if not isinstance(path_item, dict):
                    continue

                # Path-level parameters (shared across methods)
                path_level_params = path_item.get("parameters", [])

                for method in PROCESSABLE_METHODS:
                    if method not in path_item:
                        continue

                    operation = path_item[method]
                    if not isinstance(operation, dict):
                        continue

                    # Skip deprecated operations
                    if operation.get("deprecated", False):
                        continue

                    # Generate action name
                    action_name = self._generate_action_name(
                        method, path, operation
                    )

                    # Ensure unique action names
                    original_name = action_name
                    counter = 1
                    while action_name in seen_names:
                        action_name = f"{original_name}_{counter}"
                        counter += 1
                    seen_names.add(action_name)

                    # Generate description
                    description = self._generate_description(
                        method, path, operation
                    )

                    # Merge path-level and operation-level parameters
                    operation_params = operation.get("parameters", [])
                    all_params = self._merge_parameters(
                        path_level_params, operation_params
                    )

                    # Extract path, query, and body parameters
                    path_params = []
                    query_params = []
                    header_params = []

                    for param in all_params:
                        if not isinstance(param, dict):
                            continue

                        # Resolve $ref
                        param = self._resolve_ref_inline(param)

                        location = param.get("in", "query")
                        param_def = {
                            "name": param.get("name", ""),
                            "type": self._map_param_type(param),
                            "required": param.get("required", False),
                            "description": param.get("description", ""),
                        }

                        if param_def["name"]:
                            if location == "path":
                                path_params.append(param_def)
                            elif location == "query":
                                query_params.append(param_def)
                            elif location == "header":
                                header_params.append(param_def)

                    # Extract body parameters (OpenAPI 2.0)
                    body_params = self._extract_body_params_v2(operation)

                    # Extract requestBody (OpenAPI 3.0+)
                    request_body_params = self._extract_body_params_v3(operation)
                    if request_body_params:
                        body_params = request_body_params

                    # Extract response key hint from 2xx response schema
                    response_key = self._extract_response_key(operation)

                    # Build action
                    action = {
                        "name": action_name,
                        "description": description,
                        "method": method.upper(),
                        "path": path,
                        "path_params": path_params,
                        "query_params": query_params,
                        "header_params": header_params,
                        "body_params": body_params,
                        "response_key": response_key,
                        "deprecated": False,
                    }

                    # Add operation-level security override if present
                    if "security" in operation:
                        action["security"] = operation["security"]

                    # Add operationId if available
                    operation_id = operation.get("operationId")
                    if operation_id:
                        action["operation_id"] = operation_id

                    actions.append(action)

                    if len(actions) >= MAX_ENDPOINTS:
                        logger.warning(
                            "Reached MAX_ENDPOINTS (%d) — truncating import",
                            MAX_ENDPOINTS,
                        )
                        return actions

            return actions

        except Exception as exc:
            logger.error("_extract_actions failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Auth detection
    # ------------------------------------------------------------------

    def _detect_auth(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Auto-detect auth from securitySchemes.

        Checks both OpenAPI 3.0 (components.securitySchemes) and
        OpenAPI 2.0 (securityDefinitions).

        Parameters
        ----------
        spec:
            The full OpenAPI spec.

        Returns
        -------
        dict
            Auth configuration with auth_type, auth_schema, and security_schemes.
        """
        try:
            security_schemes: Dict[str, Any] = {}

            # OpenAPI 3.0: components.securitySchemes
            components = spec.get("components", {})
            if isinstance(components, dict):
                schemes = components.get("securitySchemes", {})
                if isinstance(schemes, dict):
                    security_schemes.update(schemes)

            # OpenAPI 2.0: securityDefinitions
            swagger_schemes = spec.get("securityDefinitions", {})
            if isinstance(swagger_schemes, dict):
                security_schemes.update(swagger_schemes)

            if not security_schemes:
                return {
                    "auth_type": "none",
                    "auth_schema": [],
                    "security_schemes": {},
                }

            # Pick the first security scheme as the primary auth type
            for scheme_name, scheme_def in security_schemes.items():
                if not isinstance(scheme_def, dict):
                    continue

                scheme_def = self._resolve_ref_inline(scheme_def)
                scheme_type = scheme_def.get("type", "").lower()

                if scheme_type == "http":
                    http_scheme = scheme_def.get("scheme", "").lower()
                    if http_scheme == "bearer":
                        return {
                            "auth_type": "bearer",
                            "auth_schema": ["token"],
                            "security_schemes": security_schemes,
                        }
                    elif http_scheme == "basic":
                        return {
                            "auth_type": "basic_auth",
                            "auth_schema": ["username", "password"],
                            "security_schemes": security_schemes,
                        }

                elif scheme_type == "apikey":
                    location = scheme_def.get("in", "header")
                    if location == "query":
                        return {
                            "auth_type": "api_key_query_param",
                            "auth_schema": ["param_name", "api_key"],
                            "security_schemes": security_schemes,
                        }
                    else:
                        return {
                            "auth_type": "api_key_header",
                            "auth_schema": ["header_name", "api_key"],
                            "security_schemes": security_schemes,
                        }

                elif scheme_type == "oauth2":
                    return {
                        "auth_type": "oauth2",
                        "auth_schema": [
                            "client_id",
                            "client_secret",
                            "redirect_uri",
                            "refresh_token",
                        ],
                        "security_schemes": security_schemes,
                    }

                elif scheme_type == "openiddiscovery" or scheme_type == "openidconnect":
                    return {
                        "auth_type": "oauth2",
                        "auth_schema": [
                            "client_id",
                            "client_secret",
                            "redirect_uri",
                            "refresh_token",
                        ],
                        "security_schemes": security_schemes,
                    }

            # Fallback: unknown scheme types
            return {
                "auth_type": "api_key_header",
                "auth_schema": ["header_name", "api_key"],
                "security_schemes": security_schemes,
            }

        except Exception as exc:
            logger.error("_detect_auth failed: %s", exc)
            return {
                "auth_type": "none",
                "auth_schema": [],
                "security_schemes": {},
            }

    # ------------------------------------------------------------------
    # Description generation
    # ------------------------------------------------------------------

    def _generate_description(
        self, method: str, path: str, spec_item: Dict[str, Any]
    ) -> str:
        """Generate natural language description for an action.

        Uses the operation's description, summary, or generates one
        from the method and path.

        Parameters
        ----------
        method:
            HTTP method (lowercase).
        path:
            URL path template.
        spec_item:
            The operation object from the spec.

        Returns
        -------
        str
            A human-readable description.
        """
        try:
            # Prefer explicit description
            desc = spec_item.get("description", "").strip()
            if desc:
                # Truncate very long descriptions
                if len(desc) > 200:
                    desc = desc[:197] + "..."
                return desc

            # Fall back to summary
            summary = spec_item.get("summary", "").strip()
            if summary:
                if len(summary) > 200:
                    summary = summary[:197] + "..."
                return summary

            # Generate from method + path
            readable_method = method.upper()
            readable_path = path

            # Convert path params to readable form
            readable_path = re.sub(r"\{(\w+)\}", r"<\1>", readable_path)

            return f"{readable_method} {readable_path}"

        except Exception as exc:
            logger.error("_generate_description failed: %s", exc)
            return f"{method.upper()} {path}"

    # ------------------------------------------------------------------
    # Spec version detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_version(spec: Dict[str, Any]) -> str:
        """Detect the OpenAPI spec version.

        Returns
        -------
        str
            "2.0", "3.0", "3.1", or "unknown"
        """
        try:
            # OpenAPI 3.x has "openapi" field
            openapi_version = spec.get("openapi", "")
            if openapi_version:
                if isinstance(openapi_version, str):
                    if openapi_version.startswith("3.1"):
                        return "3.1"
                    if openapi_version.startswith("3.0"):
                        return "3.0"
                    return f"3.x ({openapi_version})"
                return "3.x"

            # Swagger 2.0 has "swagger" field
            swagger_version = spec.get("swagger", "")
            if swagger_version:
                if isinstance(swagger_version, str) and swagger_version.startswith("2"):
                    return "2.0"
                return f"2.x ({swagger_version})"

            return "unknown"

        except Exception as exc:
            logger.error("_detect_version failed: %s", exc)
            return "unknown"

    # ------------------------------------------------------------------
    # Base URL extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_base_url(spec: Dict[str, Any], version: str) -> str:
        """Extract base URL from the spec.

        OpenAPI 3.x uses "servers" array.
        OpenAPI 2.0 uses "host" + "basePath" + optional "schemes".
        """
        try:
            # OpenAPI 3.x: servers
            if version.startswith("3"):
                servers = spec.get("servers", [])
                if isinstance(servers, list) and servers:
                    first_server = servers[0]
                    if isinstance(first_server, dict):
                        url = first_server.get("url", "")
                        if url:
                            # Remove trailing slash
                            return url.rstrip("/")
                    if isinstance(first_server, str):
                        return first_server.rstrip("/")

            # OpenAPI 2.0: host + basePath + schemes
            if version.startswith("2"):
                host = spec.get("host", "")
                if not host:
                    return ""

                base_path = spec.get("basePath", "")
                schemes = spec.get("schemes", ["https"])

                # Pick https if available
                scheme = "https" if "https" in schemes else schemes[0] if schemes else "https"

                # Build URL
                url = f"{scheme}://{host}"
                if base_path and base_path != "/":
                    url += base_path.rstrip("/")

                return url

            # Fallback: try servers anyway
            servers = spec.get("servers", [])
            if isinstance(servers, list) and servers:
                first_server = servers[0]
                if isinstance(first_server, dict):
                    return first_server.get("url", "").rstrip("/")
                if isinstance(first_server, str):
                    return first_server.rstrip("/")

            return ""

        except Exception as exc:
            logger.error("_extract_base_url failed: %s", exc)
            return ""

    # ------------------------------------------------------------------
    # Action name generation
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_action_name(
        method: str, path: str, operation: Dict[str, Any]
    ) -> str:
        """Generate a unique action name from operationId, summary, or path.

        Parameters
        ----------
        method:
            HTTP method (lowercase).
        path:
            URL path.
        operation:
            The operation object.

        Returns
        -------
        str
            A valid action name (lowercase, underscores, no special chars).
        """
        try:
            # Prefer operationId
            operation_id = operation.get("operationId", "").strip()
            if operation_id:
                # Clean to valid identifier
                name = re.sub(r"[^a-zA-Z0-9_]", "_", operation_id)
                name = re.sub(r"_+", "_", name).strip("_")
                if name:
                    return name.lower()

            # Build from method + path segments
            # e.g. GET /users/{id}/orders → get_users_orders
            segments = []
            segments.append(method.lower())

            for segment in path.strip("/").split("/"):
                if not segment:
                    continue
                # Skip path parameters like {id}
                if segment.startswith("{") and segment.endswith("}"):
                    param_name = segment[1:-1]
                    segments.append(f"by_{param_name}")
                else:
                    # Clean segment
                    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", segment)
                    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
                    if cleaned:
                        segments.append(cleaned.lower())

            name = "_".join(segments)
            name = re.sub(r"_+", "_", name).strip("_")

            return name if name else f"{method.lower()}_action"

        except Exception as exc:
            logger.error("_generate_action_name failed: %s", exc)
            return f"{method.lower()}_action"

    # ------------------------------------------------------------------
    # Parameter handling
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_parameters(
        path_params: List[Any], operation_params: List[Any]
    ) -> List[Any]:
        """Merge path-level and operation-level parameters.

        Operation-level parameters override path-level ones with the same
        name and location.
        """
        try:
            merged = list(path_params)

            for op_param in operation_params:
                if not isinstance(op_param, dict):
                    continue

                op_name = op_param.get("name", "")
                op_in = op_param.get("in", "")

                # Check if this param already exists at path level
                override = False
                for i, existing in enumerate(merged):
                    if isinstance(existing, dict):
                        if existing.get("name") == op_name and existing.get("in") == op_in:
                            merged[i] = op_param
                            override = True
                            break

                if not override:
                    merged.append(op_param)

            return merged

        except Exception as exc:
            logger.error("_merge_parameters failed: %s", exc)
            return list(path_params) + list(operation_params)

    @staticmethod
    def _map_param_type(param: Dict[str, Any]) -> str:
        """Map OpenAPI parameter type to a simplified type string.

        OpenAPI 2.0 uses "type" directly.
        OpenAPI 3.0 uses "schema.type".
        """
        try:
            # Direct type (OpenAPI 2.0)
            param_type = param.get("type", "")
            if param_type:
                type_map = {
                    "integer": "integer",
                    "number": "number",
                    "string": "string",
                    "boolean": "boolean",
                    "array": "array",
                    "object": "object",
                    "file": "string",
                }
                return type_map.get(param_type.lower(), "string")

            # Schema type (OpenAPI 3.0)
            schema = param.get("schema", {})
            if isinstance(schema, dict):
                schema_type = schema.get("type", "")
                if schema_type:
                    return schema_type

            return "string"

        except Exception:
            return "string"

    @staticmethod
    def _extract_body_params_v2(
        operation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract body parameters from OpenAPI 2.0 operation.

        OpenAPI 2.0 uses "parameters" with in: "body" + schema.
        """
        try:
            params = operation.get("parameters", [])
            body_params: Dict[str, Any] = {}

            for param in params:
                if not isinstance(param, dict):
                    continue
                if param.get("in") != "body":
                    continue

                schema = param.get("schema", {})
                if not isinstance(schema, dict):
                    continue

                # Extract properties from schema
                properties = schema.get("properties", {})
                required_fields = schema.get("required", [])

                if isinstance(properties, dict):
                    for prop_name, prop_def in properties.items():
                        if not isinstance(prop_def, dict):
                            continue

                        body_params[prop_name] = {
                            "type": prop_def.get("type", "string"),
                            "description": prop_def.get("description", ""),
                            "required": prop_name in required_fields,
                        }

            return body_params

        except Exception as exc:
            logger.error("_extract_body_params_v2 failed: %s", exc)
            return {}

    @staticmethod
    def _extract_body_params_v3(
        operation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract body parameters from OpenAPI 3.0+ operation.

        OpenAPI 3.0 uses "requestBody.content.*.schema".
        """
        try:
            request_body = operation.get("requestBody", {})
            if not isinstance(request_body, dict):
                return {}

            content = request_body.get("content", {})
            if not isinstance(content, dict):
                return {}

            # Try JSON content types first
            json_content = content.get("application/json", {})
            if not json_content:
                # Try any JSON-like content type
                for content_type, content_def in content.items():
                    if "json" in content_type:
                        json_content = content_def
                        break

            if not json_content:
                # Try form-urlencoded
                form_content = content.get("application/x-www-form-urlencoded", {})
                if form_content:
                    json_content = form_content
                else:
                    return {}

            schema = json_content.get("schema", {})
            if not isinstance(schema, dict):
                return {}

            # Resolve $ref if present
            if "$ref" in schema:
                # In a full implementation we'd resolve against components
                # For now, treat as opaque object
                return {"body": {"type": "object", "description": "Request body", "required": True}}

            # Handle allOf, oneOf, anyOf
            if "allOf" in schema:
                properties: Dict[str, Any] = {}
                required_fields: List[str] = []
                for sub_schema in schema.get("allOf", []):
                    if isinstance(sub_schema, dict):
                        sub_props = sub_schema.get("properties", {})
                        if isinstance(sub_props, dict):
                            for k, v in sub_props.items():
                                properties[k] = v
                        sub_required = sub_schema.get("required", [])
                        if isinstance(sub_required, list):
                            required_fields.extend(sub_required)
            else:
                properties = schema.get("properties", {})
                required_fields = schema.get("required", [])

            if not isinstance(properties, dict):
                return {}

            body_params: Dict[str, Any] = {}
            for prop_name, prop_def in properties.items():
                if not isinstance(prop_def, dict):
                    continue

                body_params[prop_name] = {
                    "type": prop_def.get("type", "string"),
                    "description": prop_def.get("description", ""),
                    "required": prop_name in required_fields if isinstance(required_fields, list) else False,
                }

            return body_params

        except Exception as exc:
            logger.error("_extract_body_params_v3 failed: %s", exc)
            return {}

    @staticmethod
    def _extract_response_key(operation: Dict[str, Any]) -> Optional[str]:
        """Extract a response_key hint from 2xx response schema.

        If a successful response wraps data in a key like
        {"data": {"items": [...]}} the response_key would be "data.items".
        """
        try:
            responses = operation.get("responses", {})
            if not isinstance(responses, dict):
                return None

            # Find a 2xx response
            for status_code, response_def in responses.items():
                status_str = str(status_code)
                if not status_str.startswith("2"):
                    continue

                if not isinstance(response_def, dict):
                    continue

                # OpenAPI 3.0: content → application/json → schema
                content = response_def.get("content", {})
                if isinstance(content, dict):
                    json_content = content.get("application/json", {})
                    if isinstance(json_content, dict):
                        schema = json_content.get("schema", {})
                        if isinstance(schema, dict):
                            # If schema has a "data" property, suggest that key
                            props = schema.get("properties", {})
                            if isinstance(props, dict):
                                if "data" in props:
                                    data_schema = props["data"]
                                    if isinstance(data_schema, dict):
                                        inner_props = data_schema.get("properties", {})
                                        if isinstance(inner_props, dict) and "items" in inner_props:
                                            return "data.items"
                                    return "data"

                # OpenAPI 2.0: schema directly
                schema = response_def.get("schema", {})
                if isinstance(schema, dict):
                    props = schema.get("properties", {})
                    if isinstance(props, dict):
                        if "data" in props:
                            data_schema = props["data"]
                            if isinstance(data_schema, dict):
                                inner_props = data_schema.get("properties", {})
                                if isinstance(inner_props, dict) and "items" in inner_props:
                                    return "data.items"
                            return "data"

            return None

        except Exception as exc:
            logger.error("_extract_response_key failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Content fetching and parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _fetch_url(url: str) -> Optional[str]:
        """Fetch content from a URL.

        Returns the raw string content or None on failure.
        """
        try:
            import urllib.request

            req = urllib.request.Request(url, headers={"Accept": "application/json, application/yaml, */*"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode("utf-8")
                return content

        except Exception as exc:
            logger.error("_fetch_url failed for url=%s: %s", url, exc)
            return None

    @staticmethod
    def _parse_content(content: str, filename: str) -> Optional[Dict[str, Any]]:
        """Parse JSON or YAML content into a dict.

        Tries JSON first, then YAML.
        """
        try:
            # Try JSON
            content_stripped = content.strip()
            if content_stripped.startswith("{") or content_stripped.startswith("["):
                try:
                    return json.loads(content_stripped)
                except (json.JSONDecodeError, ValueError):
                    pass

            # Try YAML
            try:
                import yaml  # type: ignore[import-untyped]

                result = yaml.safe_load(content_stripped)
                if isinstance(result, dict):
                    return result
                return None
            except ImportError:
                logger.warning("PyYAML not installed — cannot parse YAML specs")

                # Last attempt: maybe it's JSON with leading whitespace
                try:
                    return json.loads(content_stripped)
                except (json.JSONDecodeError, ValueError):
                    pass

                return None

        except Exception as exc:
            logger.error("_parse_content failed for filename=%s: %s", filename, exc)
            return None

    @staticmethod
    def _resolve_ref_inline(obj: Dict[str, Any]) -> Dict[str, Any]:
        """Attempt basic $ref resolution inline.

        For a full implementation this would resolve against the spec's
        components/definitions. In Phase 3 we just strip $ref and return
        the object as-is, logging a warning.
        """
        try:
            if "$ref" in obj:
                # In production we would resolve the reference
                # For Phase 3, return the object without the $ref key
                resolved = {k: v for k, v in obj.items() if k != "$ref"}
                if not resolved:
                    ref_path = obj.get("$ref", "")
                    # Extract the last segment as a name hint
                    name = ref_path.split("/")[-1] if "/" in ref_path else ref_path
                    resolved = {"name": name, "type": "string"}
                return resolved
            return obj
        except Exception:
            return obj
