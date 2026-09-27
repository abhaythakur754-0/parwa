"""
PARWA Integration Service

Business logic for third-party integration management.

Uses real database persistence via SQLAlchemy (Integration model).
Uses the unified integration catalog (app.core.integration_catalog)
for validation and test connections per D6 (pre-written HTTP calls, NO AI).

BC-001: All operations scoped to company_id.
"""

import json
import base64
import logging
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.exceptions import ValidationError
from app.logger import get_logger
from app.core.integration_catalog import (
    get_integration_by_key,
    get_catalog,
    get_catalog_for_industry,
    CATALOG,
)
from database.models.integration import Integration

logger = get_logger("integration_service")

# Status values for integrations
STATUS_PENDING = "pending"
STATUS_ACTIVE = "active"
STATUS_ERROR = "error"
STATUS_DISCONNECTED = "disconnected"


class IntegrationService:
    """Service for managing third-party integrations backed by real DB."""

    def __init__(self, db: Session):
        self.db = db

    # ── CRUD Operations ──────────────────────────────────────────

    def create_integration(
        self,
        company_id: str,
        integration_type: str,
        name: str,
        config: Dict[str, Any],
        validate: bool = True,
    ) -> Dict[str, Any]:
        """Create a new integration with optional credential validation.

        Uses the unified catalog for field validation and test connections.
        """
        # Validate integration type against catalog
        catalog_entry = get_integration_by_key(integration_type)
        if not catalog_entry:
            valid_keys = [i.key for i in CATALOG]
            raise ValidationError(
                message=f"Invalid integration type: {integration_type}",
                details={"valid_types": valid_keys},
            )

        # Validate required fields from catalog auth schema
        required_fields = [f.name for f in catalog_entry.auth_schema.fields if f.required]
        missing_fields = [f for f in required_fields if not config.get(f)]
        if missing_fields:
            raise ValidationError(
                message=f"Missing required fields: {', '.join(missing_fields)}",
                details={"missing_fields": missing_fields},
            )

        # Initial status
        status = STATUS_PENDING
        test_result = None

        # Validate credentials before saving
        if validate:
            test_result = self._test_credentials(integration_type, config)
            status = STATUS_ACTIVE if test_result.get("success") else STATUS_ERROR
        else:
            # User opted out of validation — trust the credentials and mark active.
            # This lets users connect providers whose test endpoints are IP-restricted
            # (e.g. Brevo IP allowlist) by skipping the test.
            status = STATUS_ACTIVE

        integration = Integration(
            company_id=company_id,
            integration_type=integration_type,
            name=name,
            status=status,
            credentials_encrypted=json.dumps(config),
            settings="{}",
            error_message=test_result.get("message") if test_result and not test_result.get("success") else None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Ensure table exists (Alembic may have failed on Render)
        try:
            from sqlalchemy import text as _ensure_text
            self.db.execute(_ensure_text("""
                CREATE TABLE IF NOT EXISTS integrations (
                    id VARCHAR(36) PRIMARY KEY,
                    company_id VARCHAR(36) NOT NULL,
                    integration_type VARCHAR(100) NOT NULL,
                    name VARCHAR(255),
                    status VARCHAR(50) DEFAULT 'disconnected',
                    credentials_encrypted TEXT,
                    settings TEXT DEFAULT '{}',
                    last_sync TIMESTAMP WITH TIME ZONE,
                    error_message TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """))
            self.db.execute(_ensure_text(
                "CREATE INDEX IF NOT EXISTS ix_integrations_company_id ON integrations (company_id)"
            ))
            self.db.commit()
        except Exception:
            pass  # Table may already exist

        self.db.add(integration)
        self.db.flush()

        logger.info("integration_created id=%s company=%s type=%s status=%s",
                     integration.id, company_id, integration_type, status)

        return self._to_dict(integration, mask_credentials=True)

    def get_integrations(
        self,
        company_id: str,
        status: Optional[str] = None,
        integration_type: Optional[str] = None,
        active_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """List integrations for a company with optional filters."""
        query = self.db.query(Integration).filter(
            Integration.company_id == company_id
        )

        if status:
            query = query.filter(Integration.status == status)

        if integration_type:
            query = query.filter(Integration.integration_type == integration_type.lower())

        if active_only:
            query = query.filter(Integration.status == STATUS_ACTIVE)

        integrations = query.order_by(Integration.created_at.desc()).all()

        return [self._to_dict(i, mask_credentials=True) for i in integrations]

    def get_integration(self, integration_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        """Get a single integration by ID, scoped to company."""
        integration = self.db.query(Integration).filter(
            and_(
                Integration.id == integration_id,
                Integration.company_id == company_id,
            )
        ).first()

        if not integration:
            return None

        return self._to_dict(integration, mask_credentials=True)

    def test_integration(
        self,
        integration_id: str,
        company_id: str,
    ) -> Dict[str, Any]:
        """Test an existing integration's connectivity."""
        integration = self.db.query(Integration).filter(
            and_(
                Integration.id == integration_id,
                Integration.company_id == company_id,
            )
        ).first()

        if not integration:
            raise ValidationError(
                message="Integration not found.",
                details={"integration_id": integration_id},
            )

        config = self._parse_json(integration.credentials_encrypted) or {}
        result = self._test_credentials(integration.integration_type, config)

        # Update status on the integration record
        new_status = STATUS_ACTIVE if result.get("success") else STATUS_ERROR
        integration.status = new_status
        integration.error_message = None if result.get("success") else result.get("message")
        integration.updated_at = datetime.now(timezone.utc)
        self.db.flush()

        logger.info("integration_tested id=%s company=%s success=%s",
                     integration_id, company_id, result.get("success"))

        return {
            "integration_id": integration_id,
            "success": result.get("success", False),
            "message": result.get("message", "Test not performed"),
            "status": new_status,
            "tested_at": datetime.now(timezone.utc).isoformat(),
        }

    def update_integration(
        self,
        integration_id: str,
        company_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update integration fields."""
        integration = self.db.query(Integration).filter(
            and_(
                Integration.id == integration_id,
                Integration.company_id == company_id,
            )
        ).first()

        if not integration:
            raise ValidationError(
                message="Integration not found.",
                details={"integration_id": integration_id},
            )

        allowed_fields = {"name", "status", "credentials_encrypted", "settings", "error_message"}
        for field, value in updates.items():
            if field in allowed_fields:
                if field == "credentials_encrypted" and isinstance(value, dict):
                    value = json.dumps(value)
                if field == "settings" and isinstance(value, dict):
                    value = json.dumps(value)
                setattr(integration, field, value)

        integration.updated_at = datetime.now(timezone.utc)
        self.db.flush()

        return self._to_dict(integration, mask_credentials=True)

    def delete_integration(
        self,
        integration_id: str,
        company_id: str,
    ) -> bool:
        """Delete an integration."""
        integration = self.db.query(Integration).filter(
            and_(
                Integration.id == integration_id,
                Integration.company_id == company_id,
            )
        ).first()

        if not integration:
            raise ValidationError(
                message="Integration not found.",
                details={"integration_id": integration_id},
            )

        self.db.delete(integration)
        self.db.flush()

        logger.info("integration_deleted id=%s company=%s", integration_id, company_id)

        return True

    def get_active_integrations(self, company_id: str) -> List[Dict[str, Any]]:
        """Get all active integrations for a company."""
        return self.get_integrations(company_id, status=STATUS_ACTIVE)

    def get_integrations_by_type(self, company_id: str, integration_type: str) -> List[Dict[str, Any]]:
        """Get integrations filtered by type."""
        return self.get_integrations(company_id, integration_type=integration_type)

    # ── Credential Lookup for Internal Pipeline Use (BC-MCP-Wiring) ─

    def get_credential_config(
        self,
        company_id: str,
        integration_type: str,
    ) -> Optional[Dict[str, Any]]:
        """Load DECRYPTED credentials for a single active integration.

        This is the internal-use counterpart to `_to_dict(mask_credentials=True)`.
        The pipeline nodes (node_6_5_deliver, node_8_super_node) need the REAL
        api_key / access_token to pass into CRMBridge / provider adapters —
        the masked form returned by get_integration() is useless for actually
        calling the provider API.

        Lookup rules:
          - Scope by company_id + integration_type + status=active
          - If multiple active rows exist (rare), return the most recently updated
          - Returns None if no active integration is found
          - NEVER expose this via a public API endpoint — internal callers only

        Args:
            company_id: Tenant scope
            integration_type: Catalog key, e.g. "hubspot", "zendesk", "shopify"

        Returns:
            Dict of real credential fields (e.g. {"access_token": "pat-..."}),
            or None if no active integration is connected.
        """
        integration = (
            self.db.query(Integration)
            .filter(
                and_(
                    Integration.company_id == company_id,
                    Integration.integration_type == integration_type,
                    Integration.status == STATUS_ACTIVE,
                )
            )
            .order_by(Integration.updated_at.desc())
            .first()
        )
        if not integration:
            return None
        return self._parse_json(integration.credentials_encrypted) or {}

    def get_crm_config_for_tenant(
        self,
        company_id: str,
        crm_provider: str,
    ) -> Optional[Dict[str, Any]]:
        """Convenience wrapper: load CRM credentials by provider name.

        Maps the `crm_provider` string carried in pipeline state
        (e.g. "hubspot", "zendesk") to the matching integration_type
        in the catalog and returns the decrypted config.

        Args:
            company_id: Tenant scope
            crm_provider: Lowercase provider name from state.metadata.crm_provider

        Returns:
            Decrypted config dict, or None if no active integration found.
        """
        if not company_id or not crm_provider:
            return None
        provider_key = crm_provider.lower().strip()
        # Catalog keys are lowercase provider names already (hubspot, zendesk, etc.)
        return self.get_credential_config(company_id, provider_key)

    # ── Connection Test Methods (D6 — Generic, Catalog-Driven) ────

    def _test_credentials(
        self,
        integration_type: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Test integration credentials using the catalog's pre-written test call.

        Per D6: Pre-written HTTP test calls — NO AI tokens spent.
        1-2 second response. Clear error messages.
        """
        # ── SMTP: special-case — test via real SMTP login, not HTTP ──
        if integration_type == "smtp":
            try:
                import smtplib
                smtp_host = config.get("smtp_host", "")
                smtp_port = int(config.get("smtp_port", 587))
                username = config.get("username", "")
                password = config.get("password", "")
                use_tls = str(config.get("use_tls", "true")).lower() in ("true", "1", "yes")
                with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                    server.ehlo()
                    if use_tls:
                        server.starttls()
                        server.ehlo()
                    if username and password:
                        server.login(username, password)
                return {"success": True, "message": "SMTP login successful — credentials verified."}
            except Exception as exc:
                return {"success": False, "message": f"SMTP login failed: {str(exc)[:200]}"}

        catalog_entry = get_integration_by_key(integration_type)
        if not catalog_entry:
            return {"success": False, "message": f"Unknown integration type: {integration_type}"}

        tc = catalog_entry.test_connection

        # Build URL by replacing {field_name} with config values
        url = tc.url_template
        for key, value in config.items():
            url = url.replace(f"{{{key}}}", str(value))

        # Build headers by replacing {field_name} with config values
        headers: Dict[str, str] = {}
        for hk, hv in tc.headers_template.items():
            for key, value in config.items():
                hv = hv.replace(f"{{{key}}}", str(value))
            headers[hk] = hv

        # Add auth headers based on auth type
        auth_schema = catalog_entry.auth_schema
        if auth_schema.auth_type.value == "basic_auth":
            # Build basic auth from the first text + first password fields
            text_fields = [f for f in auth_schema.fields if f.type == "text" and f.name not in ("subdomain", "domain", "store_url", "store_hash", "company_domain", "base_url")]
            pass_fields = [f for f in auth_schema.fields if f.type == "password"]
            if text_fields and pass_fields:
                username = config.get(text_fields[0].name, "")
                password = config.get(pass_fields[0].name, "")
                if username or password:
                    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
                    headers["Authorization"] = f"Basic {encoded}"

        try:
            with httpx.Client(timeout=10) as client:
                if tc.method == "POST":
                    response = client.post(url, headers=headers)
                else:
                    response = client.get(url, headers=headers)

                # Check success based on catalog config
                if tc.success_check == "json_ok_true":
                    try:
                        data = response.json()
                        if data.get("ok"):
                            return {"success": True, "message": tc.success_message}
                        else:
                            return {"success": False, "message": f"API returned error: {data.get('error', 'Unknown')}"}
                    except Exception:
                        return {"success": False, "message": f"Invalid JSON response (status {response.status_code})"}
                elif tc.success_check == "status_200_or_201":
                    if response.status_code in (200, 201):
                        return {"success": True, "message": tc.success_message}
                    else:
                        return {"success": False, "message": f"API returned {response.status_code}: {response.text[:200]}"}
                else:  # status_200
                    if response.status_code == 200:
                        return {"success": True, "message": tc.success_message}
                    else:
                        return {"success": False, "message": f"API returned {response.status_code}: {response.text[:200]}"}

        except httpx.TimeoutException:
            return {"success": False, "message": f"Connection to {catalog_entry.name} timed out"}
        except Exception as e:
            return {"success": False, "message": f"{catalog_entry.name} connection failed: {str(e)}"}

    # ── Helpers ───────────────────────────────────────────────────

    def _to_dict(self, integration: Integration, mask_credentials: bool = False) -> Dict[str, Any]:
        """Convert Integration ORM object to dict."""
        config = self._parse_json(integration.credentials_encrypted) or {}
        settings = self._parse_json(integration.settings) or {}

        if mask_credentials and config:
            config = _mask_config(config)

        return {
            "id": integration.id,
            "company_id": integration.company_id,
            "type": integration.integration_type,
            "name": integration.name,
            "status": integration.status,
            "config": config,
            "settings": settings,
            "last_test_at": integration.updated_at.isoformat() if integration.updated_at else None,
            "last_test_result": integration.error_message,
            "last_sync": integration.last_sync.isoformat() if integration.last_sync else None,
            "error_message": integration.error_message,
            "created_at": integration.created_at.isoformat() if integration.created_at else None,
            "updated_at": integration.updated_at.isoformat() if integration.updated_at else None,
        }

    @staticmethod
    def _parse_json(text_field: Optional[str]) -> Optional[Dict[str, Any]]:
        """Safely parse a JSON text field."""
        if not text_field:
            return None
        try:
            return json.loads(text_field)
        except (json.JSONDecodeError, TypeError):
            return None


# ── Module-level Helper Functions ───────────────────────────────────


def _mask_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive fields in config for API responses."""
    sensitive_keys = {
        "api_key", "api_token", "token", "access_token", "secret",
        "password", "refresh_token", "bot_token", "client_secret",
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
