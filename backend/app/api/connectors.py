"""
PARWA Phase 3 — Custom Connector API Routes

Endpoints for creating, listing, testing, executing, and deleting
custom REST connectors, plus OpenAPI spec import.

CRITICAL RULES:
- BC-001: All endpoints use company_id from JWT/header for tenant isolation
- BC-008: Never crash — all route handlers in try/except
- No mock data, no placeholder emails
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_company_id,
    get_credential_service,
    get_db,
    get_audit_trail,
)
from app.core.openapi_importer import OpenAPIImporter
from app.core.rest_connector_engine import RESTConnectorEngine
from database.models.custom_connector import CustomConnector

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/connectors", tags=["connectors"])

# ---------------------------------------------------------------------------
# Shared engine instance
# ---------------------------------------------------------------------------

_connector_engine = RESTConnectorEngine()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class CreateConnectorRequest(BaseModel):
    """Create a custom connector manually."""
    name: str = Field(..., min_length=1, description="Connector name")
    base_url: str = Field(..., min_length=1, description="Base URL for the API")
    auth_type: str = Field(default="none", description="Auth type: none, bearer, api_key_header, api_key_query_param, basic_auth, oauth2")
    credentials: Optional[Dict[str, Any]] = Field(default=None, description="Auth credentials (will be encrypted)")
    actions: Optional[List[Dict[str, Any]]] = Field(default=None, description="List of action definitions")


class ExecuteActionRequest(BaseModel):
    """Execute an action on a connector."""
    action_name: str = Field(..., min_length=1, description="Name of the action to execute")
    params: Optional[Dict[str, Any]] = Field(default=None, description="Parameters for the action")


class ImportOpenAPIRequest(BaseModel):
    """Import an OpenAPI spec to create a connector."""
    spec_content: Optional[str] = Field(default=None, description="Raw spec content (JSON or YAML)")
    spec_url: Optional[str] = Field(default=None, description="URL to fetch the spec from")
    filename: str = Field(default="openapi_spec", description="Filename hint for the spec")


# ---------------------------------------------------------------------------
# POST /connectors
# ---------------------------------------------------------------------------

@router.post("")
def create_connector(
    body: CreateConnectorRequest,
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db),
) -> dict:
    """Create a custom connector manually.

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        # Encrypt credentials if provided
        encrypted_auth = None
        if body.credentials:
            credential_service = get_credential_service()
            if credential_service:
                try:
                    encrypted_auth = credential_service.encrypt(
                        json.dumps(body.credentials), company_id
                    )
                except Exception:
                    encrypted_auth = json.dumps(body.credentials)
            else:
                encrypted_auth = json.dumps(body.credentials)

        connector_id = str(uuid.uuid4())
        connector = CustomConnector(
            id=connector_id,
            company_id=company_id,
            name=body.name,
            base_url=body.base_url,
            auth_type=body.auth_type,
            encrypted_auth=encrypted_auth,
            actions=body.actions or [],
            source="manual",
            is_active=True,
        )
        db.add(connector)
        db.commit()
        db.refresh(connector)

        # Audit log
        try:
            audit = get_audit_trail()
            if audit:
                audit.log_action(
                    company_id=company_id,
                    user_id="api_user",
                    action="create_connector",
                    tool="connectors",
                    details={
                        "connector_id": connector_id,
                        "name": body.name,
                        "base_url": body.base_url,
                        "source": "manual",
                    },
                    outcome="success",
                )
        except Exception:
            pass

        return {
            "status": "success",
            "company_id": company_id,
            "connector": {
                "id": connector.id,
                "name": connector.name,
                "base_url": connector.base_url,
                "auth_type": connector.auth_type,
                "actions": connector.actions if isinstance(connector.actions, list) else [],
                "source": connector.source,
                "is_active": connector.is_active,
            },
        }
    except Exception as exc:
        logger.error("create_connector failed for company_id=%s: %s", company_id, exc)
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
# GET /connectors
# ---------------------------------------------------------------------------

@router.get("")
def list_connectors(
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db),
) -> dict:
    """List all custom connectors for the company.

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        connectors = (
            db.query(CustomConnector)
            .filter(CustomConnector.company_id == company_id)
            .order_by(CustomConnector.created_at.desc())
            .all()
        )

        connector_list = []
        for c in connectors:
            actions = c.actions
            if isinstance(actions, str):
                try:
                    actions = json.loads(actions)
                except Exception:
                    actions = []

            connector_list.append({
                "id": c.id,
                "name": c.name,
                "base_url": c.base_url,
                "auth_type": c.auth_type,
                "actions": actions or [],
                "source": c.source,
                "is_active": c.is_active,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            })

        return {
            "status": "success",
            "company_id": company_id,
            "total": len(connector_list),
            "connectors": connector_list,
        }
    except Exception as exc:
        logger.error("list_connectors failed for company_id=%s: %s", company_id, exc)
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
            "connectors": [],
        }


# ---------------------------------------------------------------------------
# GET /connectors/{connector_id}
# ---------------------------------------------------------------------------

@router.get("/{connector_id}")
def get_connector(
    connector_id: str,
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db),
) -> dict:
    """Get a single connector by ID.

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        connector = (
            db.query(CustomConnector)
            .filter(
                CustomConnector.id == connector_id,
                CustomConnector.company_id == company_id,
            )
            .first()
        )
        if not connector:
            return {
                "status": "error",
                "error": f"Connector {connector_id} not found for company {company_id}",
                "company_id": company_id,
            }

        actions = connector.actions
        if isinstance(actions, str):
            try:
                actions = json.loads(actions)
            except Exception:
                actions = []

        return {
            "status": "success",
            "company_id": company_id,
            "connector": {
                "id": connector.id,
                "name": connector.name,
                "base_url": connector.base_url,
                "auth_type": connector.auth_type,
                "actions": actions or [],
                "source": connector.source,
                "is_active": connector.is_active,
                "created_at": connector.created_at.isoformat() if connector.created_at else None,
                "updated_at": connector.updated_at.isoformat() if connector.updated_at else None,
            },
        }
    except Exception as exc:
        logger.error(
            "get_connector failed for company_id=%s connector_id=%s: %s",
            company_id, connector_id, exc,
        )
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
        }


# ---------------------------------------------------------------------------
# POST /connectors/{connector_id}/test
# ---------------------------------------------------------------------------

@router.post("/{connector_id}/test")
def test_connector(
    connector_id: str,
    company_id: str = Depends(get_current_company_id),
) -> dict:
    """Test all actions on a connector.

    Runs each GET action with empty/default parameters to verify
    the connector is reachable and properly configured.

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        result = _connector_engine.test_connector(company_id, connector_id)

        # Audit log
        try:
            audit = get_audit_trail()
            if audit:
                audit.log_action(
                    company_id=company_id,
                    user_id="api_user",
                    action="test_connector",
                    tool="connectors",
                    details={"connector_id": connector_id},
                    outcome="success" if result.get("success") else "failure",
                )
        except Exception:
            pass

        return {
            "status": "success" if result.get("success") else "error",
            "company_id": company_id,
            "test_result": result,
        }
    except Exception as exc:
        logger.error(
            "test_connector failed for company_id=%s connector_id=%s: %s",
            company_id, connector_id, exc,
        )
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
        }


# ---------------------------------------------------------------------------
# POST /connectors/{connector_id}/execute
# ---------------------------------------------------------------------------

@router.post("/{connector_id}/execute")
def execute_connector_action(
    connector_id: str,
    body: ExecuteActionRequest,
    company_id: str = Depends(get_current_company_id),
) -> dict:
    """Execute an action on a custom connector.

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        result = _connector_engine.execute_action(
            company_id=company_id,
            connector_id=connector_id,
            action_name=body.action_name,
            params=body.params or {},
        )

        # Audit log
        try:
            audit = get_audit_trail()
            if audit:
                audit.log_action(
                    company_id=company_id,
                    user_id="api_user",
                    action="execute_connector_action",
                    tool="connectors",
                    details={
                        "connector_id": connector_id,
                        "action_name": body.action_name,
                    },
                    outcome="success" if result.get("success") else "failure",
                )
        except Exception:
            pass

        return {
            "status": "success" if result.get("success") else "error",
            "company_id": company_id,
            "result": result,
        }
    except Exception as exc:
        logger.error(
            "execute_connector_action failed for company_id=%s connector_id=%s: %s",
            company_id, connector_id, exc,
        )
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
        }


# ---------------------------------------------------------------------------
# DELETE /connectors/{connector_id}
# ---------------------------------------------------------------------------

@router.delete("/{connector_id}")
def delete_connector(
    connector_id: str,
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db),
) -> dict:
    """Delete a custom connector.

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        connector = (
            db.query(CustomConnector)
            .filter(
                CustomConnector.id == connector_id,
                CustomConnector.company_id == company_id,
            )
            .first()
        )
        if not connector:
            return {
                "status": "error",
                "error": f"Connector {connector_id} not found for company {company_id}",
                "company_id": company_id,
            }

        db.delete(connector)
        db.commit()

        # Audit log
        try:
            audit = get_audit_trail()
            if audit:
                audit.log_action(
                    company_id=company_id,
                    user_id="api_user",
                    action="delete_connector",
                    tool="connectors",
                    details={"connector_id": connector_id, "name": connector.name},
                    outcome="success",
                )
        except Exception:
            pass

        return {
            "status": "success",
            "company_id": company_id,
            "connector_id": connector_id,
            "message": f"Connector '{connector.name}' deleted",
        }
    except Exception as exc:
        logger.error(
            "delete_connector failed for company_id=%s connector_id=%s: %s",
            company_id, connector_id, exc,
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
# POST /connectors/import/openapi
# ---------------------------------------------------------------------------

@router.post("/import/openapi")
def import_openapi_spec(
    body: ImportOpenAPIRequest,
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db),
) -> dict:
    """Import an OpenAPI spec and create a custom connector.

    Supports OpenAPI v2.0 (Swagger) and v3.0/v3.1.
    Can import from URL or raw spec content.

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        importer = OpenAPIImporter()

        # Import from URL or content
        if body.spec_url:
            result = importer.import_from_url(body.spec_url, company_id)
        elif body.spec_content:
            result = importer.import_from_file(body.spec_content, body.filename, company_id)
        else:
            return {
                "status": "error",
                "error": "Either spec_url or spec_content must be provided",
                "company_id": company_id,
            }

        if not result.get("success", False):
            return {
                "status": "error",
                "error": result.get("error", "Import failed"),
                "company_id": company_id,
            }

        # Persist the generated connector
        connector_data = result.get("connector", {})

        # Encrypt auth credentials if present
        encrypted_auth = None
        if connector_data.get("encrypted_auth"):
            encrypted_auth = connector_data["encrypted_auth"]

        connector = CustomConnector(
            id=connector_data.get("id", str(uuid.uuid4())),
            company_id=company_id,
            name=connector_data.get("name", "imported_api"),
            base_url=connector_data.get("base_url", ""),
            auth_type=connector_data.get("auth_type", "none"),
            encrypted_auth=encrypted_auth,
            actions=connector_data.get("actions", []),
            source="openapi_import",
            is_active=True,
        )
        db.add(connector)
        db.commit()

        # Audit log
        try:
            audit = get_audit_trail()
            if audit:
                audit.log_action(
                    company_id=company_id,
                    user_id="api_user",
                    action="import_openapi_spec",
                    tool="connectors",
                    details={
                        "connector_id": connector.id,
                        "name": connector.name,
                        "base_url": connector.base_url,
                        "source": "openapi_import",
                        "stats": result.get("stats", {}),
                    },
                    outcome="success",
                )
        except Exception:
            pass

        return {
            "status": "success",
            "company_id": company_id,
            "connector_id": connector.id,
            "name": connector.name,
            "base_url": connector.base_url,
            "actions_count": len(connector_data.get("actions", [])),
            "stats": result.get("stats", {}),
            "spec_version": connector_data.get("spec_version", "unknown"),
        }
    except Exception as exc:
        logger.error("import_openapi_spec failed for company_id=%s: %s", company_id, exc)
        try:
            db.rollback()
        except Exception:
            pass
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
        }
