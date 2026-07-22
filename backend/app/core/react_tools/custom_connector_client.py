"""
Custom Connector Client for React Tools — wires Node 5 BillingTool
(and future tools) to the tenant's custom REST connectors.

When a tenant has created a custom connector (via onboarding →
CustomConnectorService), this client looks up the connector's actions,
finds one matching the requested operation (e.g. "get_invoice",
"get_payment"), and calls the real API.

When no matching connector exists, returns None — the caller (BillingTool)
then returns an honest "not connected" error instead of mock data.

Reuses:
  - RESTConnector + Integration models for storage
  - Same auth header patterns as CustomConnectorService._build_auth_headers
"""
from __future__ import annotations

import base64
import json
import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("parwa.react_tools.custom_connector_client")

HTTP_TIMEOUT = 15.0


def _get_db_session():
    """Lazy import + create a DB session."""
    from database.base import SessionLocal
    return SessionLocal()


def _build_auth_headers(auth_type: str, auth_config: Dict[str, Any]) -> Dict[str, str]:
    """Build HTTP headers based on auth type.

    Mirrors CustomConnectorService._build_auth_headers so the client
    uses the same auth patterns the connector was created with.
    """
    headers: Dict[str, str] = {"Content-Type": "application/json"}

    if auth_type == "bearer":
        token = auth_config.get("api_key", auth_config.get("token", ""))
        if token:
            headers["Authorization"] = f"Bearer {token}"

    elif auth_type == "api_key_header":
        header_name = auth_config.get("header_name", "X-API-Key")
        api_key = auth_config.get("api_key", "")
        if api_key:
            headers[header_name] = api_key

    elif auth_type == "api_key_query":
        # Query params handled by caller via _build_query_params
        pass

    elif auth_type == "basic_auth":
        username = auth_config.get("username", "")
        password = auth_config.get("password", "")
        if username or password:
            encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"

    elif auth_type == "oauth2":
        token = auth_config.get("access_token", auth_config.get("refresh_token", ""))
        if token:
            headers["Authorization"] = f"Bearer {token}"

    return headers


def _build_query_params(auth_type: str, auth_config: Dict[str, Any]) -> Dict[str, str]:
    """Build query params for api_key_query auth type."""
    if auth_type == "api_key_query":
        param_name = auth_config.get("param_name", "api_key")
        api_key = auth_config.get("api_key", "")
        if api_key:
            return {param_name: api_key}
    return {}


def _find_action(
    connectors: list, action_name: str
) -> Optional[tuple]:
    """Find a connector + action matching the requested action name.

    Returns (connector_dict, action_dict) or None.
    """
    for connector in connectors:
        for action in connector.get("actions", []):
            if action.get("name") == action_name:
                return connector, action
    return None


def _substitute_path(path_template: str, params: Dict[str, Any]) -> str:
    """Substitute {param} placeholders in a path template.

    e.g. "/payments/{id}" + {"id": "pay_123"} → "/payments/pay_123"
    """
    result = path_template
    for key, value in params.items():
        result = result.replace(f"{{{key}}}", str(value))
    return result


def _list_connectors(company_id: str) -> list:
    """List all active custom connectors for a tenant.

    Returns a list of connector dicts, each with:
      - base_url, auth_type, auth_config, actions
    """
    try:
        from database.models.integration import RESTConnector, Integration

        db = _get_db_session()
        try:
            connectors_orm = (
                db.query(RESTConnector)
                .filter(
                    RESTConnector.company_id == company_id,
                    RESTConnector.is_active == True,
                )
                .all()
            )

            result = []
            for conn in connectors_orm:
                integration = (
                    db.query(Integration)
                    .filter(Integration.id == conn.integration_id)
                    .first()
                )
                if not integration:
                    continue

                settings = json.loads(integration.settings) if integration.settings else {}
                actions = settings.get("actions", [])
                auth_config = json.loads(conn.auth_config_encrypted) if conn.auth_config_encrypted else {}

                result.append({
                    "connector_id": conn.id,
                    "name": integration.name,
                    "base_url": conn.base_url,
                    "auth_type": conn.auth_type,
                    "auth_config": auth_config,
                    "actions": actions,
                })
            return result
        finally:
            db.close()
    except Exception as exc:
        logger.warning("list_connectors_failed company_id=%s error=%s", company_id, str(exc)[:200])
        return []


async def call_custom_action(
    company_id: str,
    action_name: str,
    params: Optional[Dict[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Call a custom connector action by name.

    Args:
        company_id: Tenant ID (BC-001 isolation).
        action_name: The action to find (e.g. "get_invoice", "get_payment",
            "process_refund"). Must match an action defined in one of the
            tenant's custom connectors.
        params: Path/query parameters. Path params ({id}) are substituted
            into the action's path template. Remaining params become query
            string params.
        body: JSON body for POST/PUT/PATCH actions.

    Returns:
        - Dict with the API response on HTTP 2xx
        - None when no matching connector/action exists OR the API call fails
    """
    params = params or {}
    connectors = _list_connectors(company_id)
    if not connectors:
        return None

    found = _find_action(connectors, action_name)
    if not found:
        return None

    connector, action = found
    base_url = connector["base_url"].rstrip("/")
    path = _substitute_path(action.get("path", ""), params)
    method = action.get("method", "GET").upper()
    url = f"{base_url}{path}"

    headers = _build_auth_headers(connector["auth_type"], connector["auth_config"])
    # Add Origin header for CSRF middleware when calling self-hosted endpoints
    headers["Origin"] = "https://parwa.buzz"
    query_params = _build_query_params(connector["auth_type"], connector["auth_config"])

    # Remaining params (not used in path) become query params for GET
    # or are merged into body for POST/PUT/PATCH
    path_param_keys = set()
    template = action.get("path", "")
    import re
    for match in re.finditer(r"\{(\w+)\}", template):
        path_param_keys.add(match.group(1))

    extra_params = {k: v for k, v in params.items() if k not in path_param_keys}

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            if method == "GET":
                merged_params = {**query_params, **extra_params}
                resp = await client.get(url, headers=headers, params=merged_params)
            elif method == "POST":
                resp = await client.post(url, headers=headers, params=query_params, json=body or extra_params)
            elif method == "PUT":
                resp = await client.put(url, headers=headers, params=query_params, json=body or extra_params)
            elif method == "PATCH":
                resp = await client.patch(url, headers=headers, params=query_params, json=body or extra_params)
            elif method == "DELETE":
                resp = await client.delete(url, headers=headers, params=query_params)
            else:
                logger.warning("unsupported_method method=%s", method)
                return None

        if 200 <= resp.status_code < 300:
            try:
                return resp.json()
            except Exception:
                return {"raw_response": resp.text[:2000]}
        logger.warning(
            "custom_action_failed action=%s status=%s body=%s",
            action_name, resp.status_code, resp.text[:200],
        )
        return None
    except Exception as exc:
        logger.warning("custom_call_failed action=%s error=%s", action_name, str(exc)[:200])
        return None


async def has_action(company_id: str, action_name: str) -> bool:
    """Check if the tenant has a custom connector with the given action."""
    connectors = _list_connectors(company_id)
    return _find_action(connectors, action_name) is not None


async def has_any_connector(company_id: str) -> bool:
    """Check if the tenant has ANY custom connector configured."""
    return len(_list_connectors(company_id)) > 0
