"""
PARWA Phase 3 — Integration API Routes

Endpoints for browsing the integration catalog, connecting/disconnecting
integrations, testing connections, and monitoring integration health.

CRITICAL RULES:
- BC-001: All endpoints use company_id from JWT/header for tenant isolation
- BC-008: Never crash — all route handlers in try/except
- Paddle is ONLY for PARWA's own subscription billing
- No mock data, no placeholder emails
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import (
    get_cache,
    get_credential_service,
    get_audit_trail,
    get_current_company_id,
    get_db,
)
from app.core.auth_schema import AUTH_SCHEMA_REGISTRY, AUTH_TYPE_MAP, IntegrationCatalogService
from app.core.integration_health import IntegrationHealthService
from database.models.integration import Integration

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/integrations", tags=["integrations"])

# ---------------------------------------------------------------------------
# Shared service instances (per-request in production, module-level for Phase 3)
# ---------------------------------------------------------------------------

_health_service = IntegrationHealthService()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ConnectIntegrationRequest(BaseModel):
    """Payload for connecting a new integration."""
    integration_type: str = Field(..., min_length=1, description="Integration type from catalog")
    name: str = Field(..., min_length=1, description="Human-readable name for this connection")
    credentials: Dict[str, Any] = Field(..., description="Auth credentials (will be encrypted)")
    settings: Optional[Dict[str, Any]] = Field(default=None, description="Optional integration settings")


class TestConnectionRequest(BaseModel):
    """Payload for testing an integration connection."""
    credentials: Optional[Dict[str, Any]] = Field(default=None, description="Optional override credentials for test")


# ---------------------------------------------------------------------------
# GET /integrations/catalog
# ---------------------------------------------------------------------------

@router.get("/catalog")
def list_integrations(
    industry: Optional[str] = Query(None, description="Filter by industry (ecommerce, saas, logistics, general)"),
    company_id: str = Depends(get_current_company_id),
) -> dict:
    """List all integrations in the catalog, optionally filtered by industry.

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        catalog_service = IntegrationCatalogService(company_id)
        entries = catalog_service.get_catalog(industry=industry)
        return {
            "status": "success",
            "total": len(entries),
            "industry_filter": industry,
            "integrations": entries,
            "company_id": company_id,
        }
    except Exception as exc:
        logger.error("list_integrations failed for company_id=%s: %s", company_id, exc)
        return {
            "status": "error",
            "error": str(exc),
            "integrations": [],
            "company_id": company_id,
        }


# ---------------------------------------------------------------------------
# GET /integrations/catalog/{integration_type}
# ---------------------------------------------------------------------------

@router.get("/catalog/{integration_type}")
def get_integration(
    integration_type: str,
    company_id: str = Depends(get_current_company_id),
) -> dict:
    """Get a single integration's catalog entry.

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        catalog_service = IntegrationCatalogService(company_id)
        entry = catalog_service.get_integration(integration_type)
        if "error" in entry:
            return {
                "status": "error",
                "error": entry["error"],
                "company_id": company_id,
            }
        return {
            "status": "success",
            "integration": entry,
            "company_id": company_id,
        }
    except Exception as exc:
        logger.error(
            "get_integration failed for company_id=%s type=%s: %s",
            company_id, integration_type, exc,
        )
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
        }


# ---------------------------------------------------------------------------
# POST /integrations/connect
# ---------------------------------------------------------------------------

@router.post("/connect")
def connect_integration(
    body: ConnectIntegrationRequest,
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db),
) -> dict:
    """Connect a new integration for the company.

    Validates credentials against the catalog auth schema, encrypts them,
    and persists the Integration record. BC-001 + BC-008 compliant.
    """
    try:
        # Validate integration_type exists in catalog
        catalog_entry = AUTH_SCHEMA_REGISTRY.get(body.integration_type)
        if not catalog_entry:
            return {
                "status": "error",
                "error": f"Integration type '{body.integration_type}' not found in catalog",
                "company_id": company_id,
            }

        # Validate credentials
        auth_type_str = catalog_entry.get("auth_type", "")
        auth_cls = AUTH_TYPE_MAP.get(auth_type_str)
        if auth_cls:
            is_valid, msg = auth_cls.validate(body.credentials)
            if not is_valid:
                return {
                    "status": "error",
                    "error": f"Credential validation failed: {msg}",
                    "company_id": company_id,
                }

        # Encrypt credentials
        credential_service = get_credential_service()
        encrypted_creds = ""
        if credential_service:
            try:
                encrypted_creds = credential_service.encrypt(
                    json.dumps(body.credentials), company_id
                )
            except Exception as enc_exc:
                logger.warning("Credential encryption failed, storing as JSON: %s", enc_exc)
                encrypted_creds = json.dumps(body.credentials)
        else:
            encrypted_creds = json.dumps(body.credentials)

        # Create Integration record
        integration_id = str(uuid.uuid4())
        integration = Integration(
            id=integration_id,
            company_id=company_id,
            integration_type=body.integration_type,
            name=body.name,
            category=catalog_entry.get("category", "other"),
            auth_type=auth_type_str,
            encrypted_credentials=encrypted_creds,
            settings=body.settings or {},
            is_active=True,
        )
        db.add(integration)
        db.commit()
        db.refresh(integration)

        # Audit log
        try:
            audit = get_audit_trail()
            if audit:
                audit.log_action(
                    company_id=company_id,
                    user_id="api_user",
                    action="connect_integration",
                    tool=body.integration_type,
                    details={"integration_id": integration_id, "name": body.name},
                    outcome="success",
                )
        except Exception:
            pass

        return {
            "status": "success",
            "integration_id": integration_id,
            "integration_type": body.integration_type,
            "name": body.name,
            "category": catalog_entry.get("category", "other"),
            "auth_type": auth_type_str,
            "company_id": company_id,
        }
    except Exception as exc:
        logger.error("connect_integration failed for company_id=%s: %s", company_id, exc)
        try:
            db.rollback()
        except Exception:
            pass
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
        }


# ---------------------------------------------------------------------------
# POST /integrations/{integration_id}/test
# ---------------------------------------------------------------------------

@router.post("/{integration_id}/test")
def test_integration_connection(
    integration_id: str,
    body: Optional[TestConnectionRequest] = None,
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db),
) -> dict:
    """Test the connection for an existing integration.

    Validates stored credentials and attempts a test call. BC-001 + BC-008.
    """
    try:
        # Load integration
        integration = (
            db.query(Integration)
            .filter(
                Integration.id == integration_id,
                Integration.company_id == company_id,
            )
            .first()
        )
        if not integration:
            return {
                "status": "error",
                "error": f"Integration {integration_id} not found for company {company_id}",
                "company_id": company_id,
            }

        # Get catalog service and test
        catalog_service = IntegrationCatalogService(company_id)

        # Decrypt credentials if we have an encryption service
        credentials = {}
        if integration.encrypted_credentials:
            credential_service = get_credential_service()
            if credential_service:
                try:
                    decrypted = credential_service.decrypt(
                        integration.encrypted_credentials, company_id
                    )
                    credentials = json.loads(decrypted)
                except Exception:
                    try:
                        credentials = json.loads(integration.encrypted_credentials)
                    except Exception:
                        credentials = {}
            else:
                try:
                    credentials = json.loads(integration.encrypted_credentials)
                except Exception:
                    credentials = {}

        # Override with provided credentials if any
        if body and body.credentials:
            credentials = body.credentials

        result = catalog_service.test_connection(
            integration.integration_type, credentials
        )

        # Update test status
        test_status = "success" if result.get("success") else "failure"
        integration.last_tested_at = datetime.now(timezone.utc)
        integration.last_test_status = test_status
        db.commit()

        return {
            "status": "success" if result.get("success") else "error",
            "integration_id": integration_id,
            "integration_type": integration.integration_type,
            "test_result": result,
            "company_id": company_id,
        }
    except Exception as exc:
        logger.error(
            "test_integration_connection failed for company_id=%s integration_id=%s: %s",
            company_id, integration_id, exc,
        )
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
        }


# ---------------------------------------------------------------------------
# DELETE /integrations/{integration_id}
# ---------------------------------------------------------------------------

@router.delete("/{integration_id}")
def disconnect_integration(
    integration_id: str,
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db),
) -> dict:
    """Disconnect (deactivate) an integration.

    Marks the integration as inactive. BC-001 + BC-008 compliant.
    """
    try:
        integration = (
            db.query(Integration)
            .filter(
                Integration.id == integration_id,
                Integration.company_id == company_id,
            )
            .first()
        )
        if not integration:
            return {
                "status": "error",
                "error": f"Integration {integration_id} not found for company {company_id}",
                "company_id": company_id,
            }

        integration.is_active = False
        integration.updated_at = datetime.now(timezone.utc)
        settings = integration.settings or {}
        settings["disconnected_at"] = datetime.now(timezone.utc).isoformat()
        integration.settings = settings
        db.commit()

        # Audit log
        try:
            audit = get_audit_trail()
            if audit:
                audit.log_action(
                    company_id=company_id,
                    user_id="api_user",
                    action="disconnect_integration",
                    tool=integration.integration_type,
                    details={"integration_id": integration_id, "name": integration.name},
                    outcome="success",
                )
        except Exception:
            pass

        return {
            "status": "success",
            "integration_id": integration_id,
            "message": f"Integration '{integration.name}' disconnected",
            "company_id": company_id,
        }
    except Exception as exc:
        logger.error(
            "disconnect_integration failed for company_id=%s integration_id=%s: %s",
            company_id, integration_id, exc,
        )
        try:
            db.rollback()
        except Exception:
            pass
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
        }


# ---------------------------------------------------------------------------
# GET /integrations/health
# ---------------------------------------------------------------------------

@router.get("/health")
def get_all_integration_health(
    company_id: str = Depends(get_current_company_id),
) -> dict:
    """Get health status for all company integrations.

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        report = _health_service.get_all_health(company_id)
        return {
            "status": "success",
            "company_id": company_id,
            "health": report,
        }
    except Exception as exc:
        logger.error(
            "get_all_integration_health failed for company_id=%s: %s",
            company_id, exc,
        )
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
            "health": {},
        }


# ---------------------------------------------------------------------------
# GET /integrations/health/{integration_id}
# ---------------------------------------------------------------------------

@router.get("/health/{integration_id}")
def get_integration_health(
    integration_id: str,
    company_id: str = Depends(get_current_company_id),
) -> dict:
    """Get health status for a single integration.

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        report = _health_service.check_health(company_id, integration_id)
        return {
            "status": "success",
            "company_id": company_id,
            "health": report,
        }
    except Exception as exc:
        logger.error(
            "get_integration_health failed for company_id=%s integration_id=%s: %s",
            company_id, integration_id, exc,
        )
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
            "health": {},
        }


# ---------------------------------------------------------------------------
# POST /integrations/health/{integration_id}/check
# ---------------------------------------------------------------------------

@router.post("/health/{integration_id}/check")
def run_integration_health_check(
    integration_id: str,
    company_id: str = Depends(get_current_company_id),
) -> dict:
    """Run a health check on an integration and return results.

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        report = _health_service.check_health(company_id, integration_id)

        # Record the call outcome
        is_healthy = report.get("status") in ("healthy", "degraded")
        _health_service.record_call(
            company_id=company_id,
            integration_id=integration_id,
            success=is_healthy,
            error_message="" if is_healthy else f"Health check status: {report.get('status')}",
        )

        return {
            "status": "success",
            "company_id": company_id,
            "health": report,
        }
    except Exception as exc:
        logger.error(
            "run_integration_health_check failed for company_id=%s integration_id=%s: %s",
            company_id, integration_id, exc,
        )
        _health_service.record_call(
            company_id=company_id,
            integration_id=integration_id,
            success=False,
            error_message=str(exc),
        )
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
            "health": {},
        }
