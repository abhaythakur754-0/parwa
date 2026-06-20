"""
PARWA Phase 9 — Onboarding & Auth Routes

Complete multi-step onboarding flow for new tenants:
  Step 1: Account Setup (create tenant + admin user + initial API key)
  Step 2: Tier / Variant Selection
  Step 3: Integration Connect
  Step 4: Knowledge Base Upload
  Step 5: Policy Configuration
  Step 6: Key Generation + First Victory (test ticket)

Auth routes for login, key management, and JWT/API-key middleware.

Router variable is ``router = APIRouter()`` — mounted at ``/api`` prefix in main.py,
so all paths here are relative (e.g. ``/onboarding/account-setup`` → ``/api/onboarding/account-setup``).
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.models import (
    AccountSetupRequest,
    ConnectIntegrationRequest,
    GenerateKeyRequest,
    LoginRequest,
    RegisterKeyRequest,
    RevokeKeyRequest,
    SelectTierRequest,
    SetPolicyRequest,
    TestTicketRequest,
    UploadKBRequest,
)
from app.core.auth.access_control import (
    register_key,
    validate_request,
    create_jwt_session,
    list_keys,
    revoke_key,
)
from app.api.utils import _err, _hash_password, _verify_password
from app.core.tenant.isolation import (
    create_tenant,
    get_tenant,
    update_tenant,
    get_tier_permissions,
)

logger = logging.getLogger("parwa.onboarding")

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# In-Memory Stores (Phase 9 — production moves to DB)
# ═══════════════════════════════════════════════════════════════

# Users store — keyed by user_id
_users: Dict[str, Dict[str, Any]] = {}

# Email → user_id lookup for login
_email_index: Dict[str, str] = {}

# Onboarding progress tracker — keyed by tenant_id
_onboarding_progress: Dict[str, Dict[str, Any]] = {}


# ═══════════════════════════════════════════════════════════════
# Helpers (onboarding-specific)
# ═══════════════════════════════════════════════════════════════


def _get_or_create_progress(tenant_id: str) -> Dict[str, Any]:
    """Get or create onboarding progress tracker for a tenant."""
    if tenant_id not in _onboarding_progress:
        _onboarding_progress[tenant_id] = {
            "tenant_id": tenant_id,
            "completed_steps": [],
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
    return _onboarding_progress[tenant_id]


def _mark_step(tenant_id: str, step: int) -> None:
    """Mark an onboarding step as completed."""
    progress = _get_or_create_progress(tenant_id)
    if step not in progress["completed_steps"]:
        progress["completed_steps"].append(step)
    progress["last_updated"] = datetime.now(timezone.utc).isoformat()


def _require_tenant(tenant_id: str):
    """Validate tenant exists and is active, or raise 404."""
    tenant = get_tenant(tenant_id)
    if not tenant:
        raise _err(f"Tenant not found: {tenant_id}", 404)
    if tenant["status"] != "active":
        raise _err(f"Tenant is {tenant['status']}. Cannot proceed.", 403)
    return tenant


# ═══════════════════════════════════════════════════════════════
# Auth Middleware (FastAPI Dependency)
# ═══════════════════════════════════════════════════════════════

async def get_auth_context(request: Request) -> Dict[str, Any]:
    """FastAPI dependency that extracts and validates auth from request.

    Checks Authorization header for:
      - ``Bearer <jwt_token>``
      - ``Bearer pk_live_...`` or ``Bearer pk_test_...``

    Returns a context dict with tenant_id, user_id, auth_method, etc.
    Raises HTTPException 401 if invalid.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise _err(
            "Missing or invalid Authorization header. "
            "Use: Bearer <jwt_token> or Bearer <api_key>",
            401,
        )

    token = auth_header[7:].strip()  # Strip "Bearer " prefix
    if not token:
        raise _err("Empty authorization token", 401)

    # Determine token type
    if token.startswith("pk_live_") or token.startswith("pk_test_"):
        # API key authentication
        is_valid, context, error_msg = await validate_request(
            api_key=token,
            client_ip=request.client.host if request.client else "unknown",
        )
    else:
        # JWT authentication
        is_valid, context, error_msg = await validate_request(
            jwt_token=token,
            client_ip=request.client.host if request.client else "unknown",
        )

    if not is_valid:
        raise _err(error_msg or "Authentication failed", 401)

    logger.debug(
        "Auth context resolved: method=%s tenant=%s",
        context.get("auth_method"),
        context.get("tenant_id"),
    )
    return context


# ═══════════════════════════════════════════════════════════════
# Public: Tier Configuration (single source of truth)
# ═══════════════════════════════════════════════════════════════

@router.get(
    "/tiers",
    summary="Return all tier configurations (public, no auth required)",
)
async def get_tiers():
    """Return the full tier capability matrix.

    Frontend should fetch this on the tier selection step instead of
    hardcoding prices/features. This is the single source of truth.
    """
    from app.core.tenant.isolation import TIER_CAPABILITIES

    return {
        "tiers": {
            tier_id: {
                "id": tier_id,
                "role": caps["role"],
                "monthly_price": caps["monthly_price"],
                "annual_price": int(caps["monthly_price"] * 10),  # 2 months free on annual
                "tickets_per_day": caps["tickets_per_day"],
                "overage_per_ticket": caps["overage_per_ticket"],
                "decision_making": caps["decision_making"],
                "refund_execution": caps["refund_execution"],
                "peer_review": caps["peer_review"],
                "voice_calls": caps["voice_calls"],
                "can_use_super_node": caps["can_use_super_node"],
                "max_kb_documents": caps["max_kb_documents"],
                "wiki_access": caps["wiki_access"],
            }
            for tier_id, caps in TIER_CAPABILITIES.items()
        }
    }


# ═══════════════════════════════════════════════════════════════
# Step 1: Account Setup
# ═══════════════════════════════════════════════════════════════

@router.post(
    "/onboarding/account-setup",
    summary="Step 1 — Create tenant, admin user, initial API key and JWT",
)
async def account_setup(req: AccountSetupRequest):
    """Create a new tenant account with admin user and initial credentials."""
    # Validate unique email
    if req.admin_email.lower() in _email_index:
        raise _err(f"Email already registered: {req.admin_email}", 409)

    # Generate slug from company name
    slug = req.company_name.lower().replace(" ", "-").replace("_", "-")
    slug = "".join(c for c in slug if c.isalnum() or c == "-")
    slug = slug[:50].strip("-")

    # Create tenant
    try:
        tenant = create_tenant(
            name=req.company_name,
            slug=slug,
            tier="mini_parwa",
            settings={
                "industry": req.industry,
                "company_size": req.company_size,
                "onboarding_step": 1,
            },
        )
    except ValueError as e:
        raise _err(str(e), 409)

    tenant_id = tenant["id"]

    # Create admin user
    user_id = str(uuid.uuid4())
    password_hash = _hash_password(req.password)
    admin_user = {
        "user_id": user_id,
        "email": req.admin_email.lower(),
        "password_hash": password_hash,
        "role": "admin",
        "tenant_id": tenant_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _users[user_id] = admin_user
    _email_index[admin_user["email"]] = user_id

    # Generate initial API key
    key_result = register_key(
        tenant_id=tenant_id,
        key_type="live",
        name=f"{req.company_name} — Initial Key",
        user_id=user_id,
    )

    # Create JWT session
    jwt_token = create_jwt_session(
        tenant_id=tenant_id,
        user_id=user_id,
        extra_claims={"role": "admin", "email": req.admin_email},
    )

    # Track onboarding progress
    _mark_step(tenant_id, 1)

    logger.info(
        "Account created: tenant=%s (%s) admin=%s",
        tenant_id, req.company_name, req.admin_email,
    )

    return {
        "tenant_id": tenant_id,
        "tenant_name": req.company_name,
        "admin_email": req.admin_email,
        "api_key": key_result["full_key"],  # Shown ONCE
        "jwt_token": jwt_token,
        "tier": "mini_parwa",
    }


# ═══════════════════════════════════════════════════════════════
# Step 2: Tier / Variant Selection
# ═══════════════════════════════════════════════════════════════

@router.post(
    "/onboarding/select-tier",
    summary="Step 2 — Select pricing tier and billing cycle",
)
async def select_tier(req: SelectTierRequest):
    """Select a tier (mini_parwa / parwa / parwa_high) and billing cycle."""
    # Validate tier
    valid_tiers = ("mini_parwa", "parwa", "parwa_high")
    if req.tier not in valid_tiers:
        raise _err(f"Invalid tier: '{req.tier}'. Must be one of: {valid_tiers}", 400)

    # Validate billing cycle
    valid_cycles = ("monthly", "annual")
    if req.billing_cycle not in valid_cycles:
        raise _err(
            f"Invalid billing_cycle: '{req.billing_cycle}'. Must be: {valid_cycles}",
            400,
        )

    # Require tenant exists
    _require_tenant(req.tenant_id)

    # Update tenant tier
    current_settings = get_tenant(req.tenant_id).get("settings", {})
    updated_settings = {
        **current_settings,
        "billing_cycle": req.billing_cycle,
        "tier_selected_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        tenant = update_tenant(
            req.tenant_id,
            tier=req.tier,
            settings=updated_settings,
        )
    except ValueError as e:
        raise _err(str(e), 400)

    _mark_step(req.tenant_id, 2)

    capabilities = get_tier_permissions(req.tier)

    logger.info("Tier selected: tenant=%s tier=%s cycle=%s", req.tenant_id, req.tier, req.billing_cycle)

    return {
        "tenant_id": req.tenant_id,
        "tier": req.tier,
        "capabilities": capabilities,
        "billing_cycle": req.billing_cycle,
    }


# ═══════════════════════════════════════════════════════════════
# Step 3: Integration Setup
# ═══════════════════════════════════════════════════════════════

@router.post(
    "/onboarding/connect-integration",
    summary="Step 3 — Connect a third-party integration",
)
async def connect_integration(req: ConnectIntegrationRequest):
    """Connect an external integration (Shopify, Zendesk, Gorgias, etc.)."""
    _require_tenant(req.tenant_id)

    tenant = get_tenant(req.tenant_id)
    settings = tenant.get("settings", {})

    # Initialize integrations list if not present
    integrations: List[Dict[str, Any]] = settings.get("integrations", [])

    # Check for duplicate integration type
    for existing in integrations:
        if existing.get("integration_type") == req.integration_type:
            raise _err(
                f"Integration '{req.integration_type}' is already connected. "
                "Disconnect it first or use a different type.",
                409,
            )

    integration_entry = {
        "integration_id": str(uuid.uuid4()),
        "integration_type": req.integration_type,
        "status": "connected",
        "health": "healthy",
        "credentials": req.credentials,
        "connected_at": datetime.now(timezone.utc).isoformat(),
        "last_health_check": datetime.now(timezone.utc).isoformat(),
    }

    integrations.append(integration_entry)
    settings["integrations"] = integrations

    update_tenant(req.tenant_id, settings=settings)
    _mark_step(req.tenant_id, 3)

    logger.info(
        "Integration connected: tenant=%s type=%s",
        req.tenant_id, req.integration_type,
    )

    return {
        "tenant_id": req.tenant_id,
        "integration_type": req.integration_type,
        "status": "connected",
        "health": "healthy",
    }


@router.get(
    "/onboarding/integrations",
    summary="Step 3 — List connected integrations",
)
async def list_integrations(tenant_id: str = Query(...)):
    """Return all connected integrations for a tenant."""
    _require_tenant(tenant_id)

    tenant = get_tenant(tenant_id)
    settings = tenant.get("settings", {})
    integrations = settings.get("integrations", [])

    # Sanitize — remove raw credentials from the response
    safe_integrations = []
    for integ in integrations:
        safe = {
            k: v for k, v in integ.items()
            if k != "credentials"
        }
        safe["has_credentials"] = bool(integ.get("credentials"))
        safe_integrations.append(safe)

    return {
        "tenant_id": tenant_id,
        "integrations": safe_integrations,
        "count": len(safe_integrations),
    }


# ═══════════════════════════════════════════════════════════════
# Step 4: Knowledge Base Upload
# ═══════════════════════════════════════════════════════════════

@router.post(
    "/onboarding/upload-kb",
    summary="Step 4 — Upload a knowledge base entry",
)
async def upload_kb(req: UploadKBRequest):
    """Store a knowledge base article / document for the tenant."""
    _require_tenant(req.tenant_id)

    tenant = get_tenant(req.tenant_id)
    settings = tenant.get("settings", {})

    kb_entries: List[Dict[str, Any]] = settings.get("knowledge_base", [])

    entry_id = str(uuid.uuid4())
    entry = {
        "entry_id": entry_id,
        "title": req.title,
        "category": req.category,
        "content": req.content,
        "status": "indexed",
        "word_count": len(req.content.split()),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "indexed_at": datetime.now(timezone.utc).isoformat(),
    }

    kb_entries.append(entry)
    settings["knowledge_base"] = kb_entries

    update_tenant(req.tenant_id, settings=settings)
    _mark_step(req.tenant_id, 4)

    logger.info(
        "KB uploaded: tenant=%s entry=%s title='%s' category=%s",
        req.tenant_id, entry_id, req.title, req.category,
    )

    return {
        "tenant_id": req.tenant_id,
        "entry_id": entry_id,
        "title": req.title,
        "category": req.category,
        "status": "indexed",
    }


@router.get(
    "/onboarding/knowledge-base",
    summary="Step 4 — List knowledge base entries",
)
async def list_knowledge_base(tenant_id: str = Query(...)):
    """Return all knowledge base entries for a tenant."""
    _require_tenant(tenant_id)

    tenant = get_tenant(tenant_id)
    settings = tenant.get("settings", {})
    kb_entries = settings.get("knowledge_base", [])

    # Return metadata only, not full content
    summaries = [
        {
            "entry_id": e["entry_id"],
            "title": e["title"],
            "category": e["category"],
            "status": e["status"],
            "word_count": e.get("word_count", 0),
            "uploaded_at": e.get("uploaded_at"),
            "content_preview": e["content"][:200] + "..." if len(e.get("content", "")) > 200 else e.get("content", ""),
        }
        for e in kb_entries
    ]

    return {
        "tenant_id": tenant_id,
        "entries": summaries,
        "count": len(summaries),
    }


# ═══════════════════════════════════════════════════════════════
# Step 5: Policy Configuration
# ═══════════════════════════════════════════════════════════════

@router.post(
    "/onboarding/set-policy",
    summary="Step 5 — Configure business policies",
)
async def set_policy(req: SetPolicyRequest):
    """Store business policies (refund rules, escalation, tone, etc.)."""
    _require_tenant(req.tenant_id)

    tenant = get_tenant(req.tenant_id)
    settings = tenant.get("settings", {})

    policies = req.policies

    settings["policies"] = policies
    settings["policy_configured_at"] = datetime.now(timezone.utc).isoformat()

    update_tenant(req.tenant_id, settings=settings)
    _mark_step(req.tenant_id, 5)

    logger.info(
        "Policies configured: tenant=%s keys=%s",
        req.tenant_id, list(policies.keys()),
    )

    return {
        "tenant_id": req.tenant_id,
        "policies_count": len(policies),
        "status": "configured",
    }


@router.get(
    "/onboarding/policies",
    summary="Step 5 — Get current policies",
)
async def get_policies(tenant_id: str = Query(...)):
    """Return the current policy configuration for a tenant."""
    _require_tenant(tenant_id)

    tenant = get_tenant(tenant_id)
    settings = tenant.get("settings", {})
    policies = settings.get("policies", {})

    return {
        "tenant_id": tenant_id,
        "policies": policies,
        "configured_at": settings.get("policy_configured_at"),
    }


# ═══════════════════════════════════════════════════════════════
# Step 6: Key Generation + First Victory
# ═══════════════════════════════════════════════════════════════

@router.post(
    "/onboarding/generate-key",
    summary="Step 6 — Generate an additional API key",
)
async def generate_key(req: GenerateKeyRequest):
    """Generate a new live or test API key for the tenant."""
    _require_tenant(req.tenant_id)

    # Validate key type
    if req.key_type not in ("live", "test"):
        raise _err("key_type must be 'live' or 'test'", 400)

    key_result = register_key(
        tenant_id=req.tenant_id,
        key_type=req.key_type,
        name=req.name,
    )

    logger.info(
        "Key generated: tenant=%s type=%s prefix=%s",
        req.tenant_id, req.key_type, key_result["key_prefix"],
    )

    return {
        "key_id": key_result["key_id"],
        "full_key": key_result["full_key"],  # Shown ONCE
        "key_prefix": key_result["key_prefix"],
    }


@router.post(
    "/onboarding/test-ticket",
    summary="Step 6 — Submit a test ticket through the PARWA pipeline",
)
async def test_ticket(req: TestTicketRequest):
    """Submit a test ticket to verify the pipeline is working."""
    _require_tenant(req.tenant_id)

    tenant = get_tenant(req.tenant_id)
    tier = tenant.get("tier", "mini_parwa")

    try:
        from app.core.parwa_pipeline.graph_v2 import run_parwa_pipeline

        ticket_id = f"test_{secrets.token_urlsafe(8)}"

        result = await run_parwa_pipeline(
            tenant_id=req.tenant_id,
            query=req.query,
            channel_type="test",
            variant_tier=tier,
            customer_context={"is_test": True},
            sender="onboarding_test@parwa.ai",
        )

        _mark_step(req.tenant_id, 6)

        logger.info(
            "Test ticket processed: tenant=%s ticket=%s status=%s",
            req.tenant_id, ticket_id, result.get("status"),
        )

        return {
            "ticket_id": ticket_id,
            "status": result.get("status", "completed"),
            "resolution": result.get("final_response", result.get("response", ""))[:500],
            "confidence": result.get("quality_score", result.get("confidence", 0.0)),
        }

    except ImportError:
        logger.warning("PARWA pipeline not available, returning simulated test ticket")
        _mark_step(req.tenant_id, 6)

        ticket_id = f"test_{secrets.token_urlsafe(8)}"

        return {
            "ticket_id": ticket_id,
            "status": "completed",
            "resolution": (
                f"[Simulated] Thank you for your test query: '{req.query[:100]}'. "
                "Your PARWA AI assistant is configured and ready to handle support tickets."
            ),
            "confidence": 0.92,
        }

    except Exception as exc:
        logger.error("Test ticket failed for tenant %s: %s", req.tenant_id, exc)
        raise _err(f"Test ticket failed: {exc}", 500)


@router.get(
    "/onboarding/status",
    summary="Step 6 — Get full onboarding status and readiness score",
)
async def onboarding_status(tenant_id: str = Query(...)):
    """Return the current onboarding progress, tenant info, and readiness score."""
    _require_tenant(tenant_id)

    tenant = get_tenant(tenant_id)
    settings = tenant.get("settings", {})
    progress = _get_or_create_progress(tenant_id)

    completed_steps = sorted(progress.get("completed_steps", []))

    # Count resources
    integration_count = len(settings.get("integrations", []))
    kb_count = len(settings.get("knowledge_base", []))
    policies = settings.get("policies", {})
    policy_count = len(policies)

    # Calculate readiness score (0–100)
    # Each completed step is worth ~16 points (6 steps = 96, bonus for resources)
    step_score = len(completed_steps) * 16
    resource_bonus = 0

    if integration_count > 0:
        resource_bonus += 1
    if kb_count >= 3:
        resource_bonus += 1
    if policy_count >= 3:
        resource_bonus += 2

    readiness_score = min(100, step_score + resource_bonus)

    # Determine current step
    current_step = (max(completed_steps) + 1) if completed_steps else 1
    if current_step > 6:
        current_step = 6

    logger.debug(
        "Onboarding status: tenant=%s steps=%s readiness=%d",
        tenant_id, completed_steps, readiness_score,
    )

    return {
        "step": current_step,
        "completed_steps": completed_steps,
        "tenant": {
            "tenant_id": tenant_id,
            "name": tenant.get("name"),
            "tier": tenant.get("tier"),
            "status": tenant.get("status"),
        },
        "integration_count": integration_count,
        "kb_count": kb_count,
        "policy_count": policy_count,
        "readiness_score": readiness_score,
    }


# ═══════════════════════════════════════════════════════════════
# Auth Routes
# ═══════════════════════════════════════════════════════════════

@router.post(
    "/auth/login",
    summary="Authenticate with email + password, receive JWT",
)
async def login(req: LoginRequest):
    """Verify credentials and return a JWT session token."""
    email = req.email.lower().strip()
    user_id = _email_index.get(email)

    if not user_id:
        raise _err("Invalid email or password", 401)

    user = _users.get(user_id)
    if not user:
        raise _err("Invalid email or password", 401)

    # Verify password
    if not _verify_password(req.password, user["password_hash"]):
        raise _err("Invalid email or password", 401)

    # Check tenant is active
    tenant = get_tenant(user["tenant_id"])
    if not tenant:
        raise _err("Tenant not found. Contact support.", 401)
    if tenant["status"] != "active":
        raise _err(f"Account suspended. Status: {tenant['status']}", 403)

    # Generate JWT
    jwt_token = create_jwt_session(
        tenant_id=user["tenant_id"],
        user_id=user_id,
        extra_claims={"role": user["role"], "email": email},
    )

    # Find the first active API key for this tenant (for dashboard use)
    tenant_keys = list_keys(user["tenant_id"])
    active_key_prefix = tenant_keys[0]["key_prefix"] if tenant_keys else ""

    logger.info("Login successful: email=%s tenant=%s", email, user["tenant_id"])

    return {
        "jwt_token": jwt_token,
        "tenant_id": user["tenant_id"],
        "company_name": tenant.get("name", ""),
        "user_email": email,
        "role": user["role"],
        "tier": tenant.get("tier", ""),
        "api_key": active_key_prefix,  # Safe prefix only; full key never returned on login
    }


@router.post(
    "/auth/register-key",
    summary="Generate a new API key (requires auth)",
)
async def register_new_key(
    req: RegisterKeyRequest,
    auth: Dict[str, Any] = Depends(get_auth_context),
):
    """Generate a new API key for the authenticated tenant."""
    if req.key_type not in ("live", "test"):
        raise _err("key_type must be 'live' or 'test'", 400)

    # Verify tenant matches
    if auth.get("tenant_id") != req.tenant_id:
        raise _err("Cannot generate key for a different tenant", 403)

    key_result = register_key(
        tenant_id=req.tenant_id,
        key_type=req.key_type,
        name=req.name,
        user_id=auth.get("user_id"),
    )

    logger.info(
        "Key registered via auth: tenant=%s type=%s prefix=%s",
        req.tenant_id, req.key_type, key_result["key_prefix"],
    )

    return {
        "full_key": key_result["full_key"],  # Shown ONCE
        "key_prefix": key_result["key_prefix"],
        "key_id": key_result["key_id"],
    }


@router.get(
    "/auth/keys",
    summary="List API keys for a tenant (requires auth)",
)
async def get_keys(
    tenant_id: str = Query(...),
    auth: Dict[str, Any] = Depends(get_auth_context),
):
    """Return all API keys (safe info only) for the authenticated tenant."""
    if auth.get("tenant_id") != tenant_id:
        raise _err("Cannot view keys for a different tenant", 403)

    keys = list_keys(tenant_id)

    return {
        "tenant_id": tenant_id,
        "keys": keys,
        "count": len(keys),
    }


@router.post(
    "/auth/revoke-key",
    summary="Revoke an API key (requires auth)",
)
async def revoke_key_endpoint(
    req: RevokeKeyRequest,
    auth: Dict[str, Any] = Depends(get_auth_context),
):
    """Revoke (deactivate) an API key."""
    if auth.get("tenant_id") != req.tenant_id:
        raise _err("Cannot revoke key for a different tenant", 403)

    success = revoke_key(req.key_id)
    if not success:
        raise _err(f"Key not found: {req.key_id}", 404)

    logger.info("Key revoked: key_id=%s tenant=%s", req.key_id, req.tenant_id)

    return {
        "ok": True,
        "message": f"Key {req.key_id} has been revoked",
        "key_id": req.key_id,
    }
