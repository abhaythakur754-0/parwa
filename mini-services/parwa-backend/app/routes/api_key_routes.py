"""API key management routes for PARWA backend (PHASE 13 - GAP 2 + GAP 6)."""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, IntegrationCredential, AuditLog
from app.auth import get_current_user
from app.encryption import encrypt_data, decrypt_data, mask_key

router = APIRouter(prefix="/api/v1/api-keys", tags=["api-keys"])


# --- Pydantic Models ---

class StoreAPIKeyRequest(BaseModel):
    integration_id: str
    auth_type: str
    credentials: dict


class RotateAPIKeyRequest(BaseModel):
    integration_id: str
    new_credentials: dict


class RevokeAPIKeyRequest(BaseModel):
    integration_id: str


class TestAPIKeyRequest(BaseModel):
    integration_id: str


# --- Routes ---

@router.post("/store")
def store_api_key(
    req: StoreAPIKeyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Store an encrypted API key for an integration."""
    # Encrypt credentials
    creds_json = json.dumps(req.credentials)
    encrypted = encrypt_data(creds_json)

    # Determine last 4 chars from the first credential value
    first_value = next(iter(req.credentials.values()), "")
    last_4 = first_value[-4:] if len(first_value) >= 4 else first_value

    # Check if already exists
    existing = (
        db.query(IntegrationCredential)
        .filter(
            IntegrationCredential.tenant_id == current_user.tenant_id,
            IntegrationCredential.integration_id == req.integration_id,
        )
        .first()
    )

    if existing:
        existing.encrypted_data = encrypted
        existing.auth_type = req.auth_type
        existing.last_4_chars = last_4
        existing.status = "active"
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        credential_id = existing.id
    else:
        cred = IntegrationCredential(
            tenant_id=current_user.tenant_id,
            integration_id=req.integration_id,
            integration_name=req.integration_id.replace("_", " ").title(),
            auth_type=req.auth_type,
            encrypted_data=encrypted,
            status="active",
            last_4_chars=last_4,
        )
        db.add(cred)
        db.commit()
        db.refresh(cred)
        credential_id = cred.id

    # Log audit event
    audit = AuditLog(
        tenant_id=current_user.tenant_id,
        action="api_key.stored",
        actor=current_user.email,
        resource_type="api_key",
        resource_id=req.integration_id,
        details=json.dumps({"masked_key": mask_key(first_value)}),
        severity="info",
    )
    db.add(audit)
    db.commit()

    return {
        "message": "API key stored successfully",
        "credential_id": credential_id,
        "integration_id": req.integration_id,
        "masked_key": mask_key(first_value),
        "last_4_chars": last_4,
    }


@router.post("/rotate")
def rotate_api_key(
    req: RotateAPIKeyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Rotate an API key - replace encrypted data and mark rotated_at."""
    cred = (
        db.query(IntegrationCredential)
        .filter(
            IntegrationCredential.tenant_id == current_user.tenant_id,
            IntegrationCredential.integration_id == req.integration_id,
        )
        .first()
    )

    if not cred:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found for this integration",
        )

    # Encrypt new credentials
    creds_json = json.dumps(req.new_credentials)
    encrypted = encrypt_data(creds_json)

    # Update
    first_value = next(iter(req.new_credentials.values()), "")
    last_4 = first_value[-4:] if len(first_value) >= 4 else first_value

    old_masked = mask_key(cred.last_4_chars or "")

    cred.encrypted_data = encrypted
    cred.last_4_chars = last_4
    cred.rotated_at = datetime.utcnow()
    cred.status = "active"
    cred.updated_at = datetime.utcnow()
    db.commit()

    # Log audit
    audit = AuditLog(
        tenant_id=current_user.tenant_id,
        action="api_key.rotated",
        actor=current_user.email,
        resource_type="api_key",
        resource_id=req.integration_id,
        details=json.dumps({
            "old_masked": old_masked,
            "new_masked": mask_key(first_value),
        }),
        severity="warning",
    )
    db.add(audit)
    db.commit()

    return {
        "message": "API key rotated successfully",
        "integration_id": req.integration_id,
        "masked_key": mask_key(first_value),
        "rotated_at": cred.rotated_at.isoformat(),
    }


@router.delete("/revoke")
def revoke_api_key(
    req: RevokeAPIKeyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke an API key - delete record for instant stop."""
    cred = (
        db.query(IntegrationCredential)
        .filter(
            IntegrationCredential.tenant_id == current_user.tenant_id,
            IntegrationCredential.integration_id == req.integration_id,
        )
        .first()
    )

    if not cred:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found for this integration",
        )

    # Log audit before deletion
    audit = AuditLog(
        tenant_id=current_user.tenant_id,
        action="api_key.revoked",
        actor=current_user.email,
        resource_type="api_key",
        resource_id=req.integration_id,
        details=json.dumps({
            "integration_name": cred.integration_name,
            "last_4_chars": cred.last_4_chars,
        }),
        severity="critical",
    )
    db.add(audit)

    # Delete for instant stop
    db.delete(cred)
    db.commit()

    return {
        "message": "API key revoked and deleted (instant stop)",
        "integration_id": req.integration_id,
    }


@router.post("/test")
async def test_api_key(
    req: TestAPIKeyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Test an API key by decrypting on backend and making an HTTP test call."""
    import httpx

    cred = (
        db.query(IntegrationCredential)
        .filter(
            IntegrationCredential.tenant_id == current_user.tenant_id,
            IntegrationCredential.integration_id == req.integration_id,
        )
        .first()
    )

    if not cred:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found for this integration",
        )

    # Decrypt credentials
    try:
        creds_json = decrypt_data(cred.encrypted_data)
        credentials = json.loads(creds_json)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to decrypt credentials: {str(e)}",
        }

    # Build test URL based on integration
    # Try to find in the integration catalog
    from app.routes.integration_routes import INTEGRATION_CATALOG
    integration = next((i for i in INTEGRATION_CATALOG if i["id"] == req.integration_id), None)

    if not integration:
        return {
            "success": False,
            "error": "Integration not found in catalog - cannot generate test request",
            "credentials_valid": True,
            "decrypted": True,
        }

    # Build test request
    test_config = integration.get("test_config", {})
    method = test_config.get("method", "GET")
    url_template = test_config.get("url", "")
    headers_template = test_config.get("headers", {})

    # Replace placeholders
    url = url_template
    for key, value in credentials.items():
        url = url.replace(f"{{{key}}}", str(value))

    headers = {}
    for h_key, h_val in headers_template.items():
        val = h_val
        for c_key, c_value in credentials.items():
            val = val.replace(f"{{{c_key}}}", str(c_value))
        headers[h_key] = val

    auth = None
    auth_config = test_config.get("auth")
    if auth_config:
        auth_user = auth_config.get("username", "")
        auth_pass = auth_config.get("password", "")
        for c_key, c_value in credentials.items():
            auth_user = auth_user.replace(f"{{{c_key}}}", str(c_value))
            auth_pass = auth_pass.replace(f"{{{c_key}}}", str(c_value))
        auth = (auth_user, auth_pass) if auth_user else None

    # Make test call
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if method.upper() == "GET":
                resp = await client.get(url, headers=headers, auth=auth)
            elif method.upper() == "POST":
                body = test_config.get("body", "")
                for c_key, c_value in credentials.items():
                    body = body.replace(f"{{{c_key}}}", str(c_value))
                resp = await client.post(url, headers=headers, content=body, auth=auth)
            else:
                resp = await client.request(method, url, headers=headers, auth=auth)

        success = 200 <= resp.status_code < 300

        # Update last tested
        cred.last_tested_at = datetime.utcnow()
        cred.status = "active" if success else "error"
        db.commit()

        # Log audit
        audit = AuditLog(
            tenant_id=current_user.tenant_id,
            action="api_key.tested",
            actor=current_user.email,
            resource_type="api_key",
            resource_id=req.integration_id,
            details=json.dumps({
                "success": success,
                "status_code": resp.status_code,
            }),
            severity="info" if success else "warning",
        )
        db.add(audit)
        db.commit()

        return {
            "success": success,
            "status_code": resp.status_code,
            "message": "API key test passed" if success else f"API key test failed with status {resp.status_code}",
        }

    except Exception as e:
        cred.status = "error"
        cred.last_tested_at = datetime.utcnow()
        db.commit()

        return {
            "success": False,
            "error": str(e),
            "message": f"API key test failed: {str(e)}",
        }


@router.get("/list")
def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List API keys for tenant (masked values only, never full key)."""
    creds = (
        db.query(IntegrationCredential)
        .filter(IntegrationCredential.tenant_id == current_user.tenant_id)
        .all()
    )

    keys = []
    for cred in creds:
        keys.append({
            "id": cred.id,
            "integration_id": cred.integration_id,
            "integration_name": cred.integration_name,
            "auth_type": cred.auth_type,
            "status": cred.status,
            "masked_key": f"••••••••{cred.last_4_chars}" if cred.last_4_chars else "••••••••",
            "last_4_chars": cred.last_4_chars,
            "last_tested_at": cred.last_tested_at.isoformat() if cred.last_tested_at else None,
            "rotated_at": cred.rotated_at.isoformat() if cred.rotated_at else None,
            "created_at": cred.created_at.isoformat() if cred.created_at else None,
        })

    return {"api_keys": keys, "total": len(keys)}
