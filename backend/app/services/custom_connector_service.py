"""
PARWA Custom Connector Service (Tier 3)

Manages custom REST connectors for PARWA and PARWA High clients.
Per D4: Custom REST Connector = manually define base URL, auth, actions.
Per GAP 4: Custom API add-on = $49/month (PARWA/PARWA High only).
Per D13: No per-action charges, no per-call charges.

Storage: custom_connectors table with per-tenant isolation (BC-001).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.exceptions import ValidationError
from app.logger import get_logger
from database.models.integration import Integration, RESTConnector

logger = get_logger("custom_connector_service")

# Auth types supported (same as GAP 2)
VALID_AUTH_TYPES = {"bearer", "api_key_header", "api_key_query", "basic_auth", "oauth2"}

# Max actions per connector
MAX_ACTIONS_PER_CONNECTOR = 50

# Valid HTTP methods for custom actions
VALID_ACTION_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


class CustomConnectorService:
    """Service for managing custom REST connectors (Tier 3)."""

    def __init__(self, db: Session):
        self.db = db

    def create_connector(
        self,
        company_id: str,
        name: str,
        base_url: str,
        auth_type: str,
        auth_config: Dict[str, Any],
        actions: List[Dict[str, Any]],
        description: str = "",
        source: str = "custom",
        test_endpoint: str = "",
    ) -> Dict[str, Any]:
        """Create a custom REST connector.

        Creates both an Integration record and a RESTConnector record.

        Args:
            company_id: Tenant ID (BC-001).
            name: Display name (e.g. "Internal Billing API").
            base_url: Base URL for all API calls.
            auth_type: One of bearer, api_key_header, api_key_query, basic_auth, oauth2.
            auth_config: Dict with auth credentials (will be encrypted at rest).
            actions: List of action definitions.
            description: Optional description.
            source: "custom" for Tier 3, "openapi_import" for Tier 2.
            test_endpoint: Override test endpoint (default: GET {base_url}/health).

        Returns:
            Dict with connector details.
        """
        # Validate auth type
        if auth_type not in VALID_AUTH_TYPES:
            raise ValidationError(
                message=f"Invalid auth type: {auth_type}",
                details={"valid_types": sorted(VALID_AUTH_TYPES)},
            )

        # Validate base URL
        if not base_url or not base_url.startswith(("http://", "https://")):
            raise ValidationError(
                message="Base URL must start with http:// or https://",
                details={"base_url": base_url},
            )

        # Validate and cap actions
        if not actions:
            raise ValidationError(
                message="At least one action is required",
                details={},
            )

        if len(actions) > MAX_ACTIONS_PER_CONNECTOR:
            logger.warning(
                "custom_connector_actions_capped",
                original=len(actions),
                max=MAX_ACTIONS_PER_CONNECTOR,
            )
            actions = actions[:MAX_ACTIONS_PER_CONNECTOR]

        # Validate each action
        for i, action in enumerate(actions):
            method = action.get("method", "").upper()
            if method not in VALID_ACTION_METHODS:
                raise ValidationError(
                    message=f"Invalid method '{method}' in action {i}",
                    details={"action_index": i, "method": method},
                )
            if not action.get("name"):
                raise ValidationError(
                    message=f"Action {i} missing 'name'",
                    details={"action_index": i},
                )
            if not action.get("path"):
                raise ValidationError(
                    message=f"Action {i} missing 'path'",
                    details={"action_index": i},
                )

        # Test the connection before saving
        test_url = test_endpoint or f"{base_url.rstrip('/')}/health"
        test_result = self._test_connector_connection(
            base_url=base_url,
            auth_type=auth_type,
            auth_config=auth_config,
            test_url=test_url,
        )

        status = "active" if test_result.get("success") else "error"

        # Create Integration record (parent)
        integration = Integration(
            company_id=company_id,
            integration_type=f"custom_{source}",
            name=name,
            status=status,
            credentials_encrypted=json.dumps(auth_config),
            settings=json.dumps({
                "base_url": base_url,
                "auth_type": auth_type,
                "description": description,
                "source": source,
                "test_endpoint": test_endpoint,
            }),
            error_message=test_result.get("message") if not test_result.get("success") else None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(integration)
        self.db.flush()

        # Create RESTConnector record
        connector = RESTConnector(
            company_id=company_id,
            integration_id=integration.id,
            base_url=base_url.rstrip("/"),
            auth_type=auth_type,
            auth_config_encrypted=json.dumps(auth_config),
            headers=json.dumps(self._build_default_headers(auth_type)),
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(connector)
        self.db.flush()

        # Store actions as integration settings
        settings = json.loads(integration.settings)
        settings["actions"] = actions
        settings["connector_id"] = connector.id
        integration.settings = json.dumps(settings)
        self.db.flush()

        logger.info(
            "custom_connector_created",
            connector_id=connector.id,
            integration_id=integration.id,
            company_id=company_id,
            name=name,
            action_count=len(actions),
            status=status,
        )

        return self._to_dict(integration, connector, actions)

    def get_connectors(self, company_id: str) -> List[Dict[str, Any]]:
        """List all custom connectors for a company."""
        connectors = (
            self.db.query(RESTConnector)
            .filter(
                RESTConnector.company_id == company_id,
                RESTConnector.is_active == True,
            )
            .order_by(RESTConnector.created_at.desc())
            .all()
        )

        result = []
        for connector in connectors:
            integration = (
                self.db.query(Integration)
                .filter(Integration.id == connector.integration_id)
                .first()
            )
            if not integration:
                continue

            settings = json.loads(integration.settings) if integration.settings else {}
            actions = settings.get("actions", [])
            result.append(self._to_dict(integration, connector, actions))

        return result

    def get_connector(self, connector_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        """Get a single custom connector by ID."""
        connector = (
            self.db.query(RESTConnector)
            .filter(
                RESTConnector.id == connector_id,
                RESTConnector.company_id == company_id,
            )
            .first()
        )
        if not connector:
            return None

        integration = (
            self.db.query(Integration)
            .filter(Integration.id == connector.integration_id)
            .first()
        )
        if not integration:
            return None

        settings = json.loads(integration.settings) if integration.settings else {}
        actions = settings.get("actions", [])
        return self._to_dict(integration, connector, actions)

    def update_connector(
        self,
        connector_id: str,
        company_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update a custom connector's configuration."""
        connector = (
            self.db.query(RESTConnector)
            .filter(
                RESTConnector.id == connector_id,
                RESTConnector.company_id == company_id,
            )
            .first()
        )
        if not connector:
            raise ValidationError(
                message="Connector not found",
                details={"connector_id": connector_id},
            )

        integration = (
            self.db.query(Integration)
            .filter(Integration.id == connector.integration_id)
            .first()
        )
        if not integration:
            raise ValidationError(
                message="Associated integration not found",
                details={"connector_id": connector_id},
            )

        # Update allowed fields
        if "name" in updates:
            integration.name = updates["name"]
        if "base_url" in updates:
            connector.base_url = updates["base_url"].rstrip("/")
        if "auth_type" in updates:
            if updates["auth_type"] not in VALID_AUTH_TYPES:
                raise ValidationError(
                    message=f"Invalid auth type: {updates['auth_type']}",
                    details={"valid_types": sorted(VALID_AUTH_TYPES)},
                )
            connector.auth_type = updates["auth_type"]
        if "auth_config" in updates:
            connector.auth_config_encrypted = json.dumps(updates["auth_config"])
            integration.credentials_encrypted = json.dumps(updates["auth_config"])
        if "actions" in updates:
            if len(updates["actions"]) > MAX_ACTIONS_PER_CONNECTOR:
                updates["actions"] = updates["actions"][:MAX_ACTIONS_PER_CONNECTOR]
            settings = json.loads(integration.settings)
            settings["actions"] = updates["actions"]
            integration.settings = json.dumps(settings)

        connector.updated_at = datetime.now(timezone.utc)
        integration.updated_at = datetime.now(timezone.utc)
        self.db.flush()

        settings = json.loads(integration.settings)
        actions = settings.get("actions", [])
        return self._to_dict(integration, connector, actions)

    def delete_connector(self, connector_id: str, company_id: str) -> bool:
        """Delete a custom connector and its integration."""
        connector = (
            self.db.query(RESTConnector)
            .filter(
                RESTConnector.id == connector_id,
                RESTConnector.company_id == company_id,
            )
            .first()
        )
        if not connector:
            raise ValidationError(
                message="Connector not found",
                details={"connector_id": connector_id},
            )

        # Delete integration (cascades to RESTConnector via FK)
        integration = (
            self.db.query(Integration)
            .filter(Integration.id == connector.integration_id)
            .first()
        )
        if integration:
            self.db.delete(integration)
        else:
            self.db.delete(connector)

        self.db.flush()

        logger.info(
            "custom_connector_deleted",
            connector_id=connector_id,
            company_id=company_id,
        )
        return True

    def test_connector(self, connector_id: str, company_id: str) -> Dict[str, Any]:
        """Test a custom connector's connection."""
        connector = (
            self.db.query(RESTConnector)
            .filter(
                RESTConnector.id == connector_id,
                RESTConnector.company_id == company_id,
            )
            .first()
        )
        if not connector:
            raise ValidationError(
                message="Connector not found",
                details={"connector_id": connector_id},
            )

        integration = (
            self.db.query(Integration)
            .filter(Integration.id == connector.integration_id)
            .first()
        )
        if not integration:
            raise ValidationError(
                message="Associated integration not found",
                details={"connector_id": connector_id},
            )

        auth_config = json.loads(connector.auth_config_encrypted) if connector.auth_config_encrypted else {}
        settings = json.loads(integration.settings) if integration.settings else {}
        test_url = settings.get("test_endpoint") or f"{connector.base_url}/health"

        result = self._test_connector_connection(
            base_url=connector.base_url,
            auth_type=connector.auth_type,
            auth_config=auth_config,
            test_url=test_url,
        )

        # Update status
        new_status = "active" if result.get("success") else "error"
        integration.status = new_status
        integration.error_message = None if result.get("success") else result.get("message")
        integration.updated_at = datetime.now(timezone.utc)
        self.db.flush()

        return {
            "connector_id": connector_id,
            "success": result.get("success", False),
            "message": result.get("message", "Test not performed"),
            "status": new_status,
            "tested_at": datetime.now(timezone.utc).isoformat(),
        }

    def _test_connector_connection(
        self,
        base_url: str,
        auth_type: str,
        auth_config: Dict[str, Any],
        test_url: str,
    ) -> Dict[str, Any]:
        """Test a custom connector by making an HTTP request.

        Per D6: Pre-written HTTP test call — NO AI tokens spent.
        """
        headers = self._build_auth_headers(auth_type, auth_config)

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(test_url, headers=headers)

                if 200 <= response.status_code < 300:
                    return {"success": True, "message": f"Connected to {base_url}"}
                elif response.status_code in (401, 403):
                    return {"success": False, "message": f"Authentication failed (HTTP {response.status_code})"}
                else:
                    return {"success": False, "message": f"API returned HTTP {response.status_code}"}

        except httpx.TimeoutException:
            return {"success": False, "message": f"Connection timed out"}
        except httpx.ConnectError:
            return {"success": False, "message": f"Could not connect to {base_url}"}
        except Exception as e:
            return {"success": False, "message": f"Connection failed: {str(e)[:200]}"}

    def _build_auth_headers(self, auth_type: str, auth_config: Dict[str, Any]) -> Dict[str, str]:
        """Build HTTP headers based on auth type and config."""
        headers: Dict[str, str] = {"Content-Type": "application/json"}

        import base64

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
            # Query params handled in URL construction, not headers
            pass

        elif auth_type == "basic_auth":
            username = auth_config.get("username", "")
            password = auth_config.get("password", "")
            if username or password:
                encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
                headers["Authorization"] = f"Basic {encoded}"

        elif auth_type == "oauth2":
            token = auth_config.get("refresh_token", auth_config.get("access_token", ""))
            if token:
                headers["Authorization"] = f"Bearer {token}"

        return headers

    def _build_default_headers(self, auth_type: str) -> Dict[str, str]:
        """Build default headers for a connector (without actual credentials)."""
        headers = {"Content-Type": "application/json"}
        if auth_type == "bearer":
            headers["Authorization"] = "Bearer {api_key}"
        elif auth_type == "api_key_header":
            headers["X-API-Key"] = "{api_key}"
        return headers

    def _to_dict(
        self,
        integration: Integration,
        connector: RESTConnector,
        actions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Convert Integration + RESTConnector to response dict."""
        auth_config = json.loads(connector.auth_config_encrypted) if connector.auth_config_encrypted else {}
        settings = json.loads(integration.settings) if integration.settings else {}

        return {
            "id": integration.id,
            "connector_id": connector.id,
            "company_id": integration.company_id,
            "name": integration.name,
            "type": integration.integration_type,
            "status": integration.status,
            "base_url": connector.base_url,
            "auth_type": connector.auth_type,
            "auth_config": self._mask_config(auth_config),
            "actions": actions,
            "description": settings.get("description", ""),
            "source": settings.get("source", "custom"),
            "test_endpoint": settings.get("test_endpoint", ""),
            "is_active": connector.is_active,
            "error_message": integration.error_message,
            "created_at": integration.created_at.isoformat() if integration.created_at else None,
            "updated_at": integration.updated_at.isoformat() if integration.updated_at else None,
        }

    @staticmethod
    def _mask_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """Mask sensitive fields in auth config for API responses."""
        sensitive_keys = {
            "api_key", "token", "access_token", "secret",
            "password", "refresh_token", "client_secret",
            "consumer_secret", "private_api_key", "api_secret",
        }
        masked = {}
        for key, value in config.items():
            if any(s in key.lower() for s in sensitive_keys):
                if isinstance(value, str) and len(value) > 4:
                    masked[key] = value[:4] + "****"
                else:
                    masked[key] = "****"
            else:
                masked[key] = value
        return masked
