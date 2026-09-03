"""
CRM Webhook API Endpoints

Receives incoming webhooks from CRM systems (Zendesk, HubSpot, Generic)
and routes them into the PARWA pipeline.

Flow:
  CRM Webhook → Parse payload → Build pipeline state → Run PARWA pipeline
                                                    → Push response back to CRM

Endpoints:
  POST /api/crm/webhooks/zendesk   — Receive Zendesk ticket webhook
  POST /api/crm/webhooks/hubspot   — Receive HubSpot ticket webhook
  POST /api/crm/webhooks/generic   — Receive generic webhook

All endpoints:
  - Verify webhook signatures (fail-closed in production — see
    verify_crm_webhook below: zendesk/hubspot verify provider HMACs,
    generic requires the X-PARWA-Signature HMAC; if the matching
    secret is not configured, production REJECTS and non-production
    accepts with a warning)
  - Parse provider-specific payloads
  - Run full PARWA pipeline
  - Push response back to CRM (if configured)
  - Return 200 immediately with pipeline status
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.deps import get_company_id
from app.config import get_settings

logger = logging.getLogger("parwa.crm_webhook_api")

router = APIRouter(prefix="/api/crm/webhooks", tags=["CRM Webhooks"])


# ── Webhook Signature Verification (fail-closed in production) ──
# Every inbound CRM webhook reaches the FULL pipeline: one forged POST
# burns the tenant's LLM budget and can poison its ticket queue, so
# verification runs BEFORE the payload is parsed.


def _constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def _hmac_sha256_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _unverified_in_production(provider: str) -> bool:
    """Return True when an unverified webhook must be rejected.

    C-02 convention: without a configured secret, production fails
    CLOSED (reject) and non-production fails OPEN with a warning so
    local development keeps working.
    """
    settings = get_settings()
    if not settings.is_production:
        logger.warning(
            "%s webhook secret not configured — accepting unverified webhook "
            "(non-production only; set the secret before going live)",
            provider,
        )
        return False
    logger.error(
        "%s webhook secret not configured — rejecting webhook (fail-closed)",
        provider,
    )
    return True


def _verify_webhook_signature(provider: str, request: Request, raw_body: bytes) -> None:
    """Verify the inbound CRM webhook signature for one provider.

    Raises HTTPException(401) on any verification failure.
    """
    headers = request.headers
    settings = get_settings()

    if provider == "zendesk":
        secret = settings.ZENDESK_WEBHOOK_SECRET
        if not secret:
            if _unverified_in_production(provider):
                raise HTTPException(status_code=401, detail="Webhook verification not configured")
            return
        token = headers.get("X-Zendesk-Webhook-Token", "")
        signature = headers.get("X-Zendesk-Signature", "")
        token_ok = bool(token) and _constant_time_equals(token, secret)
        sig_ok = bool(signature) and _constant_time_equals(
            signature, _hmac_sha256_hex(secret, raw_body)
        )
        if not (token_ok or sig_ok):
            raise HTTPException(status_code=401, detail="Invalid webhook token")

    elif provider == "hubspot":
        secret = settings.HUBSPOT_CLIENT_SECRET
        if not secret:
            if _unverified_in_production(provider):
                raise HTTPException(status_code=401, detail="Webhook verification not configured")
            return
        provided = headers.get("X-HubSpot-Signature-v3", "") or headers.get(
            "X-HubSpot-Signature", ""
        )
        if not provided:
            raise HTTPException(status_code=401, detail="Missing webhook signature")
        # v2 signature = HMAC-SHA256(client secret, raw body)
        body_digest = _hmac_sha256_hex(secret, raw_body)
        # v3 signature = HMAC-SHA256(client secret, method + full URL + raw body)
        v3_message = (
            request.method + str(request.url) + raw_body.decode("utf-8", errors="replace")
        ).encode("utf-8")
        v3_digest = _hmac_sha256_hex(secret, v3_message)
        if not (
            _constant_time_equals(provided, body_digest)
            or _constant_time_equals(provided, v3_digest)
        ):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    else:  # generic
        secret = settings.CRM_WEBHOOK_SECRET
        if not secret:
            if _unverified_in_production(provider):
                raise HTTPException(status_code=401, detail="Webhook verification not configured")
            return
        provided = headers.get("X-PARWA-Signature", "")
        if not provided:
            raise HTTPException(status_code=401, detail="Missing webhook signature")
        if not _constant_time_equals(provided, _hmac_sha256_hex(secret, raw_body)):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")


async def verify_crm_webhook(request: Request) -> None:
    """FastAPI dependency: verify provider webhook signatures before ingress.

    Reads the raw request body first (Starlette caches it, so the
    endpoint's request.json() still works) and dispatches to the
    provider-specific HMAC check.
    """
    provider = request.url.path.rsplit("/", 1)[-1]
    raw_body = await request.body()
    if not raw_body:
        raise HTTPException(status_code=400, detail="Empty webhook payload")
    _verify_webhook_signature(provider, request, raw_body)


# ── Response Models ──────────────────────────────────────────

class CRMWebhookResponse(BaseModel):
    success: bool
    provider: str
    crm_ticket_id: str
    parwa_ticket_id: str
    pipeline_status: str  # resolved, escalated, error
    quality_score: float = 0.0
    escalation_key: Optional[str] = None
    vault_id: Optional[str] = None
    elapsed_ms: int = 0


class CRMIngestRequest(BaseModel):
    """Direct ticket ingestion (for testing or API-based CRM integration)."""
    provider: str = Field(default="generic", description="zendesk, hubspot, generic")
    payload: Dict[str, Any] = Field(..., description="Raw CRM ticket payload")
    # Deprecated: /ingest requires a JWT and always uses the authenticated
    # user's company as the tenant (BC-001). Kept for payload compatibility.
    tenant_id: str = Field(default="", description="Ignored — authenticated tenant is used")
    variant_tier: str = Field(default="parwa", description="Variant tier: mini, parwa, high")


# ── Pipeline Runner ──────────────────────────────────────────


async def _run_pipeline_from_crm(
    provider: str,
    ticket_data: Dict[str, Any],
    tenant_id: str = "tenant_001",
    variant_tier: str = "parwa",
) -> Dict[str, Any]:
    """Run the PARWA pipeline with CRM-sourced ticket data.

    Returns:
        Pipeline result dict with CRM-specific metadata added.
    """
    start = time.time()

    # Build pipeline state from CRM ticket data
    from app.core.parwa_pipeline.state_v2 import PipelineV2State

    initial_state: PipelineV2State = {
        "ticket_id": f"TKT-CRM-{ticket_data.get('ticket_id', str(int(time.time())))}",
        "tenant_id": tenant_id,
        "query": ticket_data.get("query", ""),
        "channel_type": ticket_data.get("channel_type", "email"),
        "customer_context": {
            "customer_id": ticket_data.get("customer_id", ""),
            "email": ticket_data.get("customer_email", ""),
            "name": ticket_data.get("customer_name", ""),
            "account_tier": "parwa",  # Default; could be enriched from CRM
        },
        "metadata": {
            "source": "crm_webhook",
            "crm_provider": provider,
            "crm_ticket_id": ticket_data.get("ticket_id", ""),
            "sender": ticket_data.get("customer_email", ""),
            **ticket_data.get("metadata", {}),
        },
    }

    # Run pipeline
    from app.core.parwa_pipeline.graph_v2 import run_parwa_pipeline

    result = await _run_pipeline_async(initial_state)

    elapsed = int((time.time() - start) * 1000)
    result["elapsed_ms"] = elapsed
    result["crm_provider"] = provider
    result["crm_ticket_id"] = ticket_data.get("ticket_id", "")

    return result


async def _run_pipeline_async(initial_state: Dict[str, Any]) -> Dict[str, Any]:
    """Run pipeline in async context."""
    import asyncio
    from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline

    graph = build_parwa_pipeline()
    compiled = graph.compile()

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Create new thread with its own event loop
        import concurrent.futures
        async def _run():
            return await compiled.ainvoke(initial_state)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(asyncio.run, _run()).result()
    else:
        result = asyncio.run(compiled.ainvoke(initial_state))

    return dict(result)


# ── Webhook Endpoints ────────────────────────────────────────


@router.post(
    "/zendesk",
    response_model=CRMWebhookResponse,
    dependencies=[Depends(verify_crm_webhook)],
)
async def receive_zendesk_webhook(request: Request) -> CRMWebhookResponse:
    """Receive incoming Zendesk ticket webhook.

    Zendesk sends ticket.created / ticket.updated events.
    PARWA processes the ticket and pushes response back.
    """
    from app.core.crm_bridge.crm_bridge import CRMBridge, ZendeskAdapter

    # Get raw payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Get headers for validation
    headers = dict(request.headers)

    # Parse and ingest
    ingest_result = await CRMBridge.ingest_ticket("zendesk", payload, headers)
    if not ingest_result.get("success"):
        raise HTTPException(status_code=400, detail=ingest_result.get("error", "Ingestion failed"))

    ticket_data = ingest_result["ticket_data"]
    logger.info("Zendesk webhook: ticket=%s", ticket_data.get("ticket_id", "?"))

    # Run pipeline
    try:
        result = await _run_pipeline_from_crm(
            provider="zendesk",
            ticket_data=ticket_data,
        )

        return CRMWebhookResponse(
            success=True,
            provider="zendesk",
            crm_ticket_id=ticket_data.get("ticket_id", ""),
            parwa_ticket_id=result.get("ticket_id", ""),
            pipeline_status=result.get("status", "error"),
            quality_score=result.get("quality_score", 0.0) or result.get("super_node_quality", 0.0),
            escalation_key=result.get("escalation_context", {}).get("notification_key"),
            elapsed_ms=result.get("elapsed_ms", 0),
        )
    except Exception as e:
        logger.error("Zendesk webhook pipeline failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)[:200]}")


@router.post(
    "/hubspot",
    response_model=CRMWebhookResponse,
    dependencies=[Depends(verify_crm_webhook)],
)
async def receive_hubspot_webhook(request: Request) -> CRMWebhookResponse:
    """Receive incoming HubSpot ticket webhook.

    HubSpot sends ticket.creation / ticket.status_change events.
    """
    from app.core.crm_bridge.crm_bridge import CRMBridge

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    headers = dict(request.headers)

    ingest_result = await CRMBridge.ingest_ticket("hubspot", payload, headers)
    if not ingest_result.get("success"):
        raise HTTPException(status_code=400, detail=ingest_result.get("error", "Ingestion failed"))

    ticket_data = ingest_result["ticket_data"]
    logger.info("HubSpot webhook: ticket=%s", ticket_data.get("ticket_id", "?"))

    try:
        result = await _run_pipeline_from_crm(provider="hubspot", ticket_data=ticket_data)

        return CRMWebhookResponse(
            success=True,
            provider="hubspot",
            crm_ticket_id=ticket_data.get("ticket_id", ""),
            parwa_ticket_id=result.get("ticket_id", ""),
            pipeline_status=result.get("status", "error"),
            quality_score=result.get("quality_score", 0.0) or result.get("super_node_quality", 0.0),
            escalation_key=result.get("escalation_context", {}).get("notification_key"),
            elapsed_ms=result.get("elapsed_ms", 0),
        )
    except Exception as e:
        logger.error("HubSpot webhook pipeline failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)[:200]}")


@router.post(
    "/generic",
    response_model=CRMWebhookResponse,
    dependencies=[Depends(verify_crm_webhook)],
)
async def receive_generic_webhook(request: Request) -> CRMWebhookResponse:
    """Receive generic webhook from any CRM system.

    Payload format:
    {
        "ticket_id": "...",
        "message": "Customer's question",
        "customer_email": "...",
        "customer_name": "...",
        "channel_type": "email"
    }
    """
    from app.core.crm_bridge.crm_bridge import CRMBridge

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    headers = dict(request.headers)

    ingest_result = await CRMBridge.ingest_ticket("generic", payload, headers)
    if not ingest_result.get("success"):
        raise HTTPException(status_code=400, detail=ingest_result.get("error", "Ingestion failed"))

    ticket_data = ingest_result["ticket_data"]
    logger.info("Generic webhook: ticket=%s", ticket_data.get("ticket_id", "?"))

    try:
        result = await _run_pipeline_from_crm(provider="generic", ticket_data=ticket_data)

        return CRMWebhookResponse(
            success=True,
            provider="generic",
            crm_ticket_id=ticket_data.get("ticket_id", ""),
            parwa_ticket_id=result.get("ticket_id", ""),
            pipeline_status=result.get("status", "error"),
            quality_score=result.get("quality_score", 0.0) or result.get("super_node_quality", 0.0),
            escalation_key=result.get("escalation_context", {}).get("notification_key"),
            elapsed_ms=result.get("elapsed_ms", 0),
        )
    except Exception as e:
        logger.error("Generic webhook pipeline failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)[:200]}")


@router.post("/ingest")
async def direct_ingest(
    req: CRMIngestRequest,
    company_id: str = Depends(get_company_id),
) -> Dict[str, Any]:
    """Direct ticket ingestion (for API-based CRM integration or testing).

    Accepts a pre-parsed ticket and runs it through the PARWA pipeline.
    Requires a JWT (BC-011) and always runs against the AUTHENTICATED
    user's company — a caller can never run tickets against another
    tenant (BC-001).
    """
    from app.core.crm_bridge.crm_bridge import CRMBridge

    ingest_result = await CRMBridge.ingest_ticket(req.provider, req.payload)
    if not ingest_result.get("success"):
        raise HTTPException(status_code=400, detail=ingest_result.get("error", "Ingestion failed"))

    ticket_data = ingest_result["ticket_data"]

    try:
        result = await _run_pipeline_from_crm(
            provider=req.provider,
            ticket_data=ticket_data,
            tenant_id=company_id,  # BC-001: authenticated tenant, not caller-supplied
            variant_tier=req.variant_tier,
        )

        return {
            "success": True,
            "provider": req.provider,
            "crm_ticket_id": ticket_data.get("ticket_id", ""),
            "parwa_ticket_id": result.get("ticket_id", ""),
            "pipeline_status": result.get("status", "error"),
            "quality_score": result.get("quality_score", 0.0),
            "final_response": result.get("final_response", ""),
            "escalation_key": result.get("escalation_context", {}).get("notification_key"),
            "elapsed_ms": result.get("elapsed_ms", 0),
        }
    except Exception as e:
        logger.error("Direct ingest pipeline failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)[:200]}")
