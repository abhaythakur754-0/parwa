"""Tenant-scoped Superglue service-account provisioning.

The global Superglue key is an administrative credential used only to
provision service accounts and shared system/tool definitions. Customer
credentials and OAuth exchanges run with the tenant's own service-account key.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import superglue_client
from database.models.integration import SuperglueTenantAccount
from shared.utils.token_encryption import decrypt_token, encrypt_token

logger = logging.getLogger("parwa.superglue_tenant_accounts")


def get_tenant_api_key(db: Session, company_id: str) -> Optional[str]:
    """Return the decrypted service-account API key for exactly one tenant."""
    row = db.query(SuperglueTenantAccount).filter(
        SuperglueTenantAccount.company_id == str(company_id),
        SuperglueTenantAccount.status == "active",
    ).first()
    if not row or not row.api_key_encrypted:
        return None
    try:
        return decrypt_token(row.api_key_encrypted)
    except Exception as exc:
        logger.error(
            "superglue_tenant_key_decrypt_failed company=%s error=%s",
            str(company_id)[:12], str(exc)[:120],
        )
        return None


async def get_or_create_tenant_account(
    db: Session,
    company_id: str,
) -> Dict[str, Any]:
    """Provision one Superglue service account and persist its key encrypted."""
    tenant_id = str(company_id)
    existing_key = get_tenant_api_key(db, tenant_id)
    if existing_key:
        row = db.query(SuperglueTenantAccount).filter(
            SuperglueTenantAccount.company_id == tenant_id,
        ).first()
        return {
            "success": True,
            "api_key": existing_key,
            "service_account_id": row.service_account_id if row else None,
        }

    if not superglue_client.is_configured():
        return {"success": False, "error": "Superglue admin credentials are not configured"}

    # Serialize first-time provisioning across API workers on PostgreSQL.
    try:
        if db.bind and db.bind.dialect.name == "postgresql":
            db.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:tenant_id))"),
                {"tenant_id": f"superglue:{tenant_id}"},
            )
            existing_key = get_tenant_api_key(db, tenant_id)
            if existing_key:
                row = db.query(SuperglueTenantAccount).filter(
                    SuperglueTenantAccount.company_id == tenant_id,
                ).first()
                return {
                    "success": True,
                    "api_key": existing_key,
                    "service_account_id": row.service_account_id if row else None,
                }
    except Exception as exc:
        db.rollback()
        logger.error(
            "superglue_tenant_lock_failed company=%s error=%s",
            tenant_id[:12], str(exc)[:120],
        )
        return {"success": False, "error": "Could not safely provision tenant integration account"}

    api_url, admin_token = superglue_client._get_config()
    if not admin_token:
        return {"success": False, "error": "Superglue admin token is missing"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{api_url}/v1/service-accounts",
                headers={
                    "Authorization": f"Bearer {admin_token}",
                    "Content-Type": "application/json",
                    **superglue_client._session_headers(),
                },
                json={"name": f"PARWA tenant {tenant_id}"},
            )
        if response.status_code not in (200, 201):
            logger.error(
                "superglue_service_account_create_failed company=%s status=%s",
                tenant_id[:12], response.status_code,
            )
            db.rollback()
            return {
                "success": False,
                "error": f"Superglue service-account provisioning failed (HTTP {response.status_code})",
            }

        payload = response.json()
        data = payload.get("data", payload) if isinstance(payload, dict) else {}
        service_account = data.get("serviceAccount", {}) if isinstance(data, dict) else {}
        service_account_id = service_account.get("id") or data.get("id")
        api_key = data.get("apiKey") or data.get("api_key")
        if not service_account_id or not api_key:
            db.rollback()
            logger.error(
                "superglue_service_account_response_incomplete company=%s",
                tenant_id[:12],
            )
            return {
                "success": False,
                "error": "Superglue did not return a service-account ID and API key",
            }

        row = db.query(SuperglueTenantAccount).filter(
            SuperglueTenantAccount.company_id == tenant_id,
        ).first()
        if row:
            row.service_account_id = str(service_account_id)
            row.api_key_encrypted = encrypt_token(str(api_key))
            row.status = "active"
            row.error_message = None
        else:
            row = SuperglueTenantAccount(
                company_id=tenant_id,
                service_account_id=str(service_account_id),
                api_key_encrypted=encrypt_token(str(api_key)),
                status="active",
            )
            db.add(row)
        db.commit()
        db.refresh(row)
        return {
            "success": True,
            "api_key": str(api_key),
            "service_account_id": str(service_account_id),
        }
    except IntegrityError:
        db.rollback()
        existing_key = get_tenant_api_key(db, tenant_id)
        row = db.query(SuperglueTenantAccount).filter(
            SuperglueTenantAccount.company_id == tenant_id,
        ).first()
        if existing_key:
            return {
                "success": True,
                "api_key": existing_key,
                "service_account_id": row.service_account_id if row else None,
            }
        return {"success": False, "error": "Tenant integration account provisioning conflicted; retry"}
    except Exception as exc:
        db.rollback()
        logger.error(
            "superglue_service_account_provision_error company=%s error=%s",
            tenant_id[:12], str(exc)[:160],
        )
        return {"success": False, "error": "Could not provision tenant integration account"}
