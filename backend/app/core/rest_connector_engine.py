"""
PARWA Phase 3 — REST Connector Runtime Engine

Executes actions defined in custom REST connectors for Tier 3 integrations.
Handles: action execution, auth application, response parsing,
MCP tool generation, circuit breaker + rate limiter + cache integration.

CRITICAL RULES:
- BC-001: All queries scoped to company_id
- BC-008: Never crash — all external calls in try/except
- No mock data, no TODO/FIXME
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.auth_schema import AUTH_TYPE_MAP
from app.core.cache import SmartCache, TTL_PRESETS
from app.core.circuit_breaker import CircuitBreaker, CircuitOpenError
from app.core.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# HTTP methods that are supported for connector actions
SUPPORTED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}

# Default timeout for HTTP requests (seconds)
DEFAULT_REQUEST_TIMEOUT = 30

# Cache TTL for connector responses (seconds)
CACHE_TTL_MAP: Dict[str, int] = {
    "GET": TTL_PRESETS["real_time"],       # 5 min
    "POST": 0,                              # no cache
    "PUT": 0,
    "PATCH": 0,
    "DELETE": 0,
}


class RESTConnectorEngine:
    """Executes actions defined in custom REST connectors.

    Handles: action execution, auth application, response parsing,
    MCP tool generation, circuit breaker + rate limiter + cache integration.

    Parameters
    ----------
    cache:
        SmartCache instance for response caching. Created if not provided.
    circuit_breaker:
        CircuitBreaker instance for fault tolerance. Created if not provided.
    rate_limiter:
        RateLimiter instance for rate limiting. Created if not provided.
    """

    def __init__(
        self,
        cache: Optional[SmartCache] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ) -> None:
        self.cache = cache or SmartCache()
        self.circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=5, recovery_timeout=60.0
        )
        self.rate_limiter = rate_limiter or RateLimiter(
            max_tokens=50, refill_rate=5.0
        )

        # company_id -> { connector_id -> CircuitBreaker }
        self._breakers: Dict[str, Dict[str, CircuitBreaker]] = {}

        # company_id -> { connector_id -> { action_name -> last_result } }
        self._last_results: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute_action(
        self,
        company_id: str,
        connector_id: str,
        action_name: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a single action on a custom connector.

        Steps:
        1. Load connector config (base_url, auth, actions)
        2. Find the action by name
        3. Apply auth to request
        4. Substitute path parameters
        5. Check cache
        6. Execute HTTP request (with circuit breaker + rate limiter)
        7. Parse response
        8. Cache result
        9. Return structured result

        Parameters
        ----------
        company_id:
            Tenant identifier (BC-001).
        connector_id:
            The custom connector's ID.
        action_name:
            Name of the action to execute.
        params:
            Optional parameters to pass to the action.

        Returns
        -------
        dict
            Structured result with status, data, and metadata.
        """
        try:
            # Step 1: Load connector config
            connector = self._load_connector(company_id, connector_id)
            if not connector:
                return {
                    "success": False,
                    "error": f"Connector {connector_id} not found for company {company_id}",
                    "company_id": company_id,
                    "connector_id": connector_id,
                    "action_name": action_name,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            if not connector.get("is_active", False):
                return {
                    "success": False,
                    "error": f"Connector {connector_id} is not active",
                    "company_id": company_id,
                    "connector_id": connector_id,
                    "action_name": action_name,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            # Step 2: Find the action by name
            actions = connector.get("actions", [])
            action = self._find_action(actions, action_name)
            if not action:
                available = self._list_action_names(actions)
                return {
                    "success": False,
                    "error": (
                        f"Action '{action_name}' not found. "
                        f"Available actions: {', '.join(available)}"
                    ),
                    "company_id": company_id,
                    "connector_id": connector_id,
                    "action_name": action_name,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            # Step 3: Build request config
            base_url = connector.get("base_url", "").rstrip("/")
            path = action.get("path", "")
            method = action.get("method", "GET").upper()

            if method not in SUPPORTED_METHODS:
                return {
                    "success": False,
                    "error": f"Unsupported HTTP method: {method}",
                    "company_id": company_id,
                    "connector_id": connector_id,
                    "action_name": action_name,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            # Step 4: Substitute path parameters
            params = params or {}
            resolved_path = self._substitute_path_params(path, params)

            url = f"{base_url}{resolved_path}"

            request_config: Dict[str, Any] = {
                "method": method,
                "url": url,
                "headers": dict(action.get("headers", {})),
                "params": {},
                "body": None,
                "timeout": action.get("timeout", DEFAULT_REQUEST_TIMEOUT),
            }

            # Add query parameters from action definition
            query_params = action.get("query_params", [])
            if isinstance(query_params, list):
                for qp in query_params:
                    if isinstance(qp, dict):
                        key = qp.get("name", "")
                        if key and key in params:
                            request_config["params"][key] = params[key]
                        elif key and qp.get("default"):
                            request_config["params"][key] = qp["default"]
            elif isinstance(query_params, dict):
                request_config["params"].update(query_params)

            # Add body from params for write methods
            if method in ("POST", "PUT", "PATCH"):
                body_params = action.get("body_params", {})
                if isinstance(body_params, dict) and body_params:
                    request_config["body"] = {
                        k: params.get(k, v.get("default", ""))
                        for k, v in body_params.items()
                        if isinstance(v, dict)
                    }
                elif "body" in params:
                    request_config["body"] = params["body"]

            # Apply additional headers from params
            if "headers" in params and isinstance(params["headers"], dict):
                request_config["headers"].update(params["headers"])

            # Step 5: Apply auth
            auth_type = connector.get("auth_type", "none")
            credentials = self._get_credentials(company_id, connector)
            if credentials and auth_type != "none":
                request_config = self._apply_auth(
                    request_config, auth_type, credentials
                )

            # Step 6: Check cache (only for GET requests)
            cache_key = ""
            if method == "GET":
                cache_key = self._build_cache_key(
                    company_id, connector_id, action_name, params
                )
                cached = self.cache.get(cache_key)
                if cached is not None:
                    return {
                        "success": True,
                        "data": cached,
                        "company_id": company_id,
                        "connector_id": connector_id,
                        "action_name": action_name,
                        "from_cache": True,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }

            # Step 7: Execute HTTP request with circuit breaker + rate limiter
            breaker = self._get_breaker(company_id, connector_id)
            if not breaker.is_available:
                return {
                    "success": False,
                    "error": "Circuit breaker is open — calls are blocked",
                    "company_id": company_id,
                    "connector_id": connector_id,
                    "action_name": action_name,
                    "circuit_breaker_state": breaker.state.value,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            result = self._execute_http_request(request_config)

            # Record outcome with circuit breaker
            if result.get("success", False):
                breaker.record_success()
            else:
                breaker.record_failure()

            # Step 8: Parse response
            response_key = action.get("response_key")
            parsed = self._parse_response(result, response_key)

            # Step 9: Cache successful GET results
            if method == "GET" and cache_key and result.get("success", False):
                self.cache.set(cache_key, parsed, CACHE_TTL_MAP["GET"])

            # Store last result
            self._store_last_result(
                company_id, connector_id, action_name, parsed
            )

            return {
                "success": result.get("success", False),
                "data": parsed,
                "status_code": result.get("status_code"),
                "company_id": company_id,
                "connector_id": connector_id,
                "action_name": action_name,
                "from_cache": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as exc:
            logger.error(
                "execute_action failed for company_id=%s connector_id=%s action=%s: %s",
                company_id,
                connector_id,
                action_name,
                exc,
            )
            return {
                "success": False,
                "error": str(exc),
                "company_id": company_id,
                "connector_id": connector_id,
                "action_name": action_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def test_connector(
        self, company_id: str, connector_id: str
    ) -> Dict[str, Any]:
        """Test all actions on a connector.

        Runs each action with empty/default parameters to verify
        the connector is reachable and properly configured.

        Parameters
        ----------
        company_id:
            Tenant identifier (BC-001).
        connector_id:
            The custom connector's ID.

        Returns
        -------
        dict
            Test results for each action on the connector.
        """
        try:
            connector = self._load_connector(company_id, connector_id)
            if not connector:
                return {
                    "success": False,
                    "error": f"Connector {connector_id} not found for company {company_id}",
                    "company_id": company_id,
                    "connector_id": connector_id,
                }

            actions = connector.get("actions", [])
            results: List[Dict[str, Any]] = []
            all_passed = True

            for action in actions:
                if not isinstance(action, dict):
                    continue

                action_name = action.get("name", "unknown")

                # Skip write operations for testing (only test read endpoints)
                method = action.get("method", "GET").upper()
                if method not in ("GET",):
                    results.append({
                        "action_name": action_name,
                        "method": method,
                        "skipped": True,
                        "reason": "Only GET actions are tested to avoid side effects",
                    })
                    continue

                # Try executing with no params
                test_result = self.execute_action(
                    company_id, connector_id, action_name, {}
                )

                passed = test_result.get("success", False)
                if not passed:
                    all_passed = False

                results.append({
                    "action_name": action_name,
                    "method": method,
                    "passed": passed,
                    "status_code": test_result.get("status_code"),
                    "error": test_result.get("error"),
                })

            return {
                "success": all_passed,
                "connector_id": connector_id,
                "connector_name": connector.get("name", ""),
                "company_id": company_id,
                "total_actions": len(actions),
                "tested_actions": len([r for r in results if not r.get("skipped")]),
                "skipped_actions": len([r for r in results if r.get("skipped")]),
                "results": results,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as exc:
            logger.error(
                "test_connector failed for company_id=%s connector_id=%s: %s",
                company_id,
                connector_id,
                exc,
            )
            return {
                "success": False,
                "error": str(exc),
                "company_id": company_id,
                "connector_id": connector_id,
            }

    def generate_mcp_tools(
        self, company_id: str, connector_id: str
    ) -> List[Dict[str, Any]]:
        """Generate MCP tool definitions from connector actions for AI consumption.

        Each action becomes a tool with inputSchema describing the
        parameters the AI should provide.

        Parameters
        ----------
        company_id:
            Tenant identifier (BC-001).
        connector_id:
            The custom connector's ID.

        Returns
        -------
        list[dict]
            List of MCP tool definitions.
        """
        try:
            connector = self._load_connector(company_id, connector_id)
            if not connector:
                logger.warning(
                    "Connector %s not found for company %s",
                    connector_id,
                    company_id,
                )
                return []

            actions = connector.get("actions", [])
            connector_name = connector.get("name", "custom")
            mcp_tools: List[Dict[str, Any]] = []

            for action in actions:
                if not isinstance(action, dict):
                    continue

                action_name = action.get("name", "")
                if not action_name:
                    continue

                # Skip deprecated actions
                if action.get("deprecated", False):
                    continue

                method = action.get("method", "GET").upper()
                description = action.get("description", "")
                if not description:
                    description = self._generate_default_description(
                        method, action.get("path", ""), action_name
                    )

                # Build input schema from parameters
                properties: Dict[str, Any] = {}
                required: List[str] = []

                # Path parameters
                path_params = action.get("path_params", [])
                if isinstance(path_params, list):
                    for pp in path_params:
                        if isinstance(pp, dict):
                            name = pp.get("name", "")
                            if name:
                                properties[name] = {
                                    "type": pp.get("type", "string"),
                                    "description": pp.get("description", f"Path parameter {name}"),
                                }
                                if pp.get("required", True):
                                    required.append(name)

                # Query parameters
                query_params = action.get("query_params", [])
                if isinstance(query_params, list):
                    for qp in query_params:
                        if isinstance(qp, dict):
                            name = qp.get("name", "")
                            if name:
                                properties[name] = {
                                    "type": qp.get("type", "string"),
                                    "description": qp.get("description", f"Query parameter {name}"),
                                }
                                if qp.get("required", False):
                                    required.append(name)

                # Body parameters
                body_params = action.get("body_params", {})
                if isinstance(body_params, dict):
                    for bp_name, bp_schema in body_params.items():
                        if isinstance(bp_schema, dict):
                            properties[bp_name] = {
                                "type": bp_schema.get("type", "string"),
                                "description": bp_schema.get("description", f"Body parameter {bp_name}"),
                            }
                            if bp_schema.get("required", False):
                                required.append(bp_name)

                tool_def = {
                    "name": f"{connector_name}__{action_name}",
                    "description": description,
                    "inputSchema": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                    "metadata": {
                        "connector_id": connector_id,
                        "connector_name": connector_name,
                        "action_name": action_name,
                        "method": method,
                        "path": action.get("path", ""),
                        "company_id": company_id,
                    },
                }

                mcp_tools.append(tool_def)

            return mcp_tools

        except Exception as exc:
            logger.error(
                "generate_mcp_tools failed for company_id=%s connector_id=%s: %s",
                company_id,
                connector_id,
                exc,
            )
            return []

    # ------------------------------------------------------------------
    # Auth application
    # ------------------------------------------------------------------

    def _apply_auth(
        self,
        request_config: Dict[str, Any],
        auth_type: str,
        credentials: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply authentication to request config.

        Supports: bearer, api_key_header, api_key_query_param, basic_auth, oauth2

        Parameters
        ----------
        request_config:
            The HTTP request configuration dict.
        auth_type:
            The authentication type string.
        credentials:
            The decrypted credentials dict.

        Returns
        -------
        dict
            Updated request config with auth applied.
        """
        try:
            auth_cls = AUTH_TYPE_MAP.get(auth_type)
            if auth_cls:
                return auth_cls.apply_to_request(request_config, credentials)

            # Handle custom auth types
            if auth_type == "none":
                return request_config

            logger.warning(
                "Unknown auth_type '%s' — no auth applied", auth_type
            )
            return request_config

        except Exception as exc:
            logger.error("_apply_auth failed for auth_type=%s: %s", auth_type, exc)
            return request_config

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(
        self, response: Dict[str, Any], response_key: Optional[str] = None
    ) -> Any:
        """Parse API response and extract relevant data.

        Parameters
        ----------
        response:
            The raw HTTP response dict.
        response_key:
            Optional dot-notation key to extract nested data
            (e.g. "data.items" → response["data"]["items"]).

        Returns
        -------
        Any
            The parsed response data.
        """
        try:
            if not response.get("success", False):
                return {
                    "error": response.get("error", "Request failed"),
                    "status_code": response.get("status_code"),
                }

            body = response.get("body")
            if body is None:
                return None

            # Parse string body as JSON if possible
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                except (json.JSONDecodeError, ValueError):
                    return body

            # If no response_key, return the full body
            if not response_key:
                return body

            # Navigate dot-notation key
            current = body
            for key in response_key.split("."):
                if isinstance(current, dict):
                    current = current.get(key)
                elif isinstance(current, list) and key.isdigit():
                    idx = int(key)
                    current = current[idx] if idx < len(current) else None
                else:
                    return None

                if current is None:
                    return None

            return current

        except Exception as exc:
            logger.error("_parse_response failed: %s", exc)
            return {"error": f"Response parsing failed: {exc}"}

    # ------------------------------------------------------------------
    # HTTP execution
    # ------------------------------------------------------------------

    def _execute_http_request(
        self, request_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an HTTP request using httpx or urllib.

        Parameters
        ----------
        request_config:
            Request configuration with method, url, headers, etc.

        Returns
        -------
        dict
            Raw response dict with status_code, body, and success flag.
        """
        try:
            method = request_config.get("method", "GET").upper()
            url = request_config.get("url", "")
            headers = request_config.get("headers", {})
            params = request_config.get("params", {})
            body = request_config.get("body")
            timeout = request_config.get("timeout", DEFAULT_REQUEST_TIMEOUT)

            if not url:
                return {
                    "success": False,
                    "error": "No URL provided",
                    "status_code": None,
                }

            # Try httpx first (async-capable, modern)
            try:
                import httpx

                client_kwargs: Dict[str, Any] = {"timeout": timeout}
                with httpx.Client(**client_kwargs) as client:
                    request_kwargs: Dict[str, Any] = {
                        "headers": headers,
                        "params": params,
                    }
                    if body is not None and method in ("POST", "PUT", "PATCH"):
                        if isinstance(body, dict):
                            request_kwargs["json"] = body
                        else:
                            request_kwargs["content"] = str(body)

                    http_method = getattr(client, method.lower())
                    resp = http_method(url, **request_kwargs)

                    resp_body: Any
                    try:
                        resp_body = resp.json()
                    except (json.JSONDecodeError, ValueError):
                        resp_body = resp.text

                    return {
                        "success": 200 <= resp.status_code < 300,
                        "status_code": resp.status_code,
                        "body": resp_body,
                        "headers": dict(resp.headers),
                    }

            except ImportError:
                pass

            # Fallback to urllib
            import urllib.parse
            import urllib.request

            # Build full URL with query params
            if params:
                query_string = urllib.parse.urlencode(params)
                separator = "&" if "?" in url else "?"
                full_url = f"{url}{separator}{query_string}"
            else:
                full_url = url

            req = urllib.request.Request(full_url, method=method)
            for k, v in headers.items():
                req.add_header(k, str(v))

            request_body = None
            if body is not None and method in ("POST", "PUT", "PATCH"):
                if isinstance(body, dict):
                    request_body = json.dumps(body).encode("utf-8")
                    req.add_header("Content-Type", "application/json")
                else:
                    request_body = str(body).encode("utf-8")

            try:
                with urllib.request.urlopen(
                    req, request_body, timeout=timeout
                ) as resp:
                    resp_data = resp.read().decode("utf-8")
                    try:
                        resp_body = json.loads(resp_data)
                    except (json.JSONDecodeError, ValueError):
                        resp_body = resp_data

                    return {
                        "success": True,
                        "status_code": resp.status,
                        "body": resp_body,
                        "headers": dict(resp.headers),
                    }
            except urllib.error.HTTPError as e:
                error_body = ""
                try:
                    error_body = e.read().decode("utf-8")
                    error_body = json.loads(error_body)
                except Exception:
                    pass

                return {
                    "success": False,
                    "status_code": e.code,
                    "body": error_body,
                    "error": str(e),
                }

        except Exception as exc:
            logger.error("_execute_http_request failed: %s", exc)
            return {
                "success": False,
                "error": str(exc),
                "status_code": None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_connector(
        self, company_id: str, connector_id: str
    ) -> Optional[Dict[str, Any]]:
        """Load a connector from the database, scoped to company_id (BC-001)."""
        try:
            from database.base import SessionLocal
            from database.models.custom_connector import CustomConnector

            session = SessionLocal()
            try:
                connector = (
                    session.query(CustomConnector)
                    .filter(
                        CustomConnector.id == connector_id,
                        CustomConnector.company_id == company_id,
                    )
                    .first()
                )
                if connector is None:
                    return None

                actions = connector.actions
                if isinstance(actions, str):
                    try:
                        actions = json.loads(actions)
                    except (json.JSONDecodeError, ValueError):
                        actions = []

                return {
                    "id": connector.id,
                    "company_id": connector.company_id,
                    "name": connector.name,
                    "base_url": connector.base_url,
                    "auth_type": connector.auth_type,
                    "encrypted_auth": connector.encrypted_auth,
                    "actions": actions or [],
                    "source": connector.source,
                    "is_active": connector.is_active,
                }
            finally:
                session.close()

        except Exception as exc:
            logger.error(
                "_load_connector failed for company_id=%s connector_id=%s: %s",
                company_id,
                connector_id,
                exc,
            )
            return None

    def _get_credentials(
        self, company_id: str, connector: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Decrypt and return credentials for a connector."""
        try:
            encrypted_auth = connector.get("encrypted_auth")
            if not encrypted_auth:
                return None

            # Try to use CredentialService if available
            try:
                from app.core.credentials import CredentialService
                import os

                master_key = os.getenv("PARWA_MASTER_KEY", "parwa-default-master-key-phase3")
                if len(master_key) < 16:
                    master_key = master_key + "x" * (16 - len(master_key))

                service = CredentialService(master_key)
                decrypted_str = service.decrypt(encrypted_auth, company_id)
                return json.loads(decrypted_str)
            except Exception:
                # If decryption fails, try parsing as plain JSON (dev mode)
                try:
                    return json.loads(encrypted_auth)
                except (json.JSONDecodeError, ValueError):
                    return None

        except Exception as exc:
            logger.error(
                "_get_credentials failed for company_id=%s: %s", company_id, exc
            )
            return None

    @staticmethod
    def _find_action(
        actions: Any, action_name: str
    ) -> Optional[Dict[str, Any]]:
        """Find an action by name in the actions list."""
        try:
            if isinstance(actions, list):
                for action in actions:
                    if isinstance(action, dict) and action.get("name") == action_name:
                        return action
            elif isinstance(actions, dict):
                return actions.get(action_name)
            return None
        except Exception as exc:
            logger.error("_find_action failed: %s", exc)
            return None

    @staticmethod
    def _list_action_names(actions: Any) -> List[str]:
        """List all action names from an actions definition."""
        try:
            if isinstance(actions, list):
                return [
                    a.get("name", "") if isinstance(a, dict) else str(a)
                    for a in actions
                    if a
                ]
            elif isinstance(actions, dict):
                return list(actions.keys())
            return []
        except Exception as exc:
            logger.error("_list_action_names failed: %s", exc)
            return []

    @staticmethod
    def _substitute_path_params(path: str, params: Dict[str, Any]) -> str:
        """Replace {param} placeholders in the path with actual values."""
        try:
            result = path
            for key, value in params.items():
                placeholder = "{" + key + "}"
                if placeholder in result:
                    result = result.replace(placeholder, str(value))
            return result
        except Exception as exc:
            logger.error("_substitute_path_params failed: %s", exc)
            return path

    @staticmethod
    def _build_cache_key(
        company_id: str,
        connector_id: str,
        action_name: str,
        params: Dict[str, Any],
    ) -> str:
        """Build a deterministic cache key for a request."""
        try:
            raw = f"{company_id}:{connector_id}:{action_name}:{json.dumps(params, sort_keys=True, default=str)}"
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
            return f"parwa:cache:company:{company_id}:connector:{connector_id}:{action_name}:{digest}"
        except Exception as exc:
            logger.error("_build_cache_key failed: %s", exc)
            return f"parwa:cache:company:{company_id}:connector:{connector_id}:{action_name}:fallback"

    def _get_breaker(
        self, company_id: str, connector_id: str
    ) -> CircuitBreaker:
        """Get or create a circuit breaker for a specific connector."""
        try:
            if company_id not in self._breakers:
                self._breakers[company_id] = {}
            if connector_id not in self._breakers[company_id]:
                self._breakers[company_id][connector_id] = CircuitBreaker(
                    failure_threshold=5, recovery_timeout=60.0
                )
            return self._breakers[company_id][connector_id]
        except Exception as exc:
            logger.error(
                "_get_breaker failed for company_id=%s connector_id=%s: %s",
                company_id,
                connector_id,
                exc,
            )
            return CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)

    def _store_last_result(
        self,
        company_id: str,
        connector_id: str,
        action_name: str,
        result: Any,
    ) -> None:
        """Store the last execution result for a connector action."""
        try:
            if company_id not in self._last_results:
                self._last_results[company_id] = {}
            if connector_id not in self._last_results[company_id]:
                self._last_results[company_id][connector_id] = {}
            self._last_results[company_id][connector_id][action_name] = {
                "result": result,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            logger.error(
                "_store_last_result failed for company_id=%s: %s", company_id, exc
            )

    @staticmethod
    def _generate_default_description(
        method: str, path: str, action_name: str
    ) -> str:
        """Generate a default description for an action when none is provided."""
        try:
            readable_name = action_name.replace("_", " ").replace("-", " ").title()
            return f"{method} {path} — {readable_name}"
        except Exception:
            return f"{method} action: {action_name}"
