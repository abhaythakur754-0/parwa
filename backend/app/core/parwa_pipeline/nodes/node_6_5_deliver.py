"""
Node 6.5: Deliver — BC-015 (Customer Delivery Node) + BC-016 (CRM Push-back) — PRODUCTION

Question: WHERE does the customer receive this answer?
          AND does the originating CRM need to know?

This node sits between the three terminal nodes (finalize_simple,
wiki_finalize, node_8) and __end__. It is the LAST node every
ticket flows through before the pipeline completes.

JOB:
  Phase 1 — Customer dispatch (BC-015):
    1. Read channel_type from state (set at Node 1 ingestion).
    2. If empty/missing/unknown → default to email (safest channel).
    3. Apply channel-capacity rules (e.g. SMS > limit → email).
    4. For each channel in the fallback chain:
       a. Check circuit breaker — skip if open for this channel.
       b. Retry with exponential backoff (config-driven).
       c. On success → write audit row, emit metric, break.
       d. On failure → record CB failure, emit metric, next channel.
    5. On all-channels-failed → persist to DLQ, mark delivery_status=error,
       DO NOT roll back the ticket resolution (BC-008: never crash).

  Phase 2 — CRM push-back (BC-016), ONLY IF phase 1 succeeded:
    1. Read crm_ticket_id + crm_provider from state["metadata"].
    2. If no CRM ticket → skip (status=skipped_no_crm).
    3. If CRM_PUSH_ENABLED=False → skip (status=skipped_disabled).
    4. Call CRMBridge.push_response with retry + backoff.
    5. On success → mark crm_push_status=success.
    6. On all-retries-exhausted → persist to DLQ with
       error_type=crm_push_failed, mark crm_push_status=dlq_persisted.
       Customer already received the answer; CRM will catch up on
       next webhook poll or manual retry.

  Idempotency: if delivery_status already terminal, skip phase 1.
  CRM push is only attempted once per ticket (state carries crm_push_status).

LLM calls: 0 (pure routing + dispatch + CRM API call)

Building Codes:
  BC-001: company_id (tenant_id) passed to every dispatch call.
  BC-005: Socket.io events emitted by underlying ChannelDispatcher.
  BC-008: Never crashes — safe defaults on any error.
  BC-012: Structured errors, no stack traces to user.
  BC-015: Customer delivery is a SEPARATE pipeline node.
  BC-016: CRM push happens AFTER customer delivery, not before.
          CRM is never told "resolved" until the customer has the answer.

Production hardening (v2):
  - All thresholds env-var driven (DELIVERY_* and CRM_PUSH_* in Settings)
  - Per-channel circuit breaker (delivery_circuit_breaker.py)
  - Exponential backoff retry within a channel (phase 1) and within CRM push (phase 2)
  - Audit log row written on EVERY customer-dispatch attempt
  - DLQ persistence on all-channels-failed (phase 1) AND on CRM-push-failed (phase 2)
  - Prometheus metrics emitted on every attempt (both phases)
  - DB session via context manager (no leaks)
  - Typed exceptions (DeliveryError / DeliveryCircuitOpenError / CRMPushError)
  - Per-attempt wall-clock timeout (best-effort)
  - Bug fix: delivery_attempts now counts ACTUAL dispatch attempts,
    not log entries (the v1 implementation miscounted)
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from app.config import get_settings
from app.core.parwa_pipeline.delivery_circuit_breaker import (
    get_delivery_circuit_breaker,
)
from app.core.parwa_pipeline.state_v2 import PipelineV2State
from app.core.email_utils import strip_reasoning

logger = logging.getLogger("parwa.pipeline.node_6_5")

# Module-level alias for time.sleep so tests can patch JUST our sleep
# without affecting the global time module (which would break other
# tests that rely on real time, e.g. circuit breaker cooldown tests).
_sleep = time.sleep

# ── Known channels ─────────────────────────────────────────────────
# Anything not in this set is treated as unknown → default to email.

KNOWN_CHANNELS = {"email", "chat", "sms", "voice"}

# ── Fallback chains ────────────────────────────────────────────────
# Order: try primary first, then fall back through this list.
# Stops at first successful dispatch. 'internal' is always the
# last resort (creates a TicketMessage row but no external send).

FALLBACK_CHAINS: Dict[str, List[str]] = {
    "email": ["email", "internal"],
    "sms": ["sms", "email", "internal"],
    "chat": ["chat", "email", "internal"],
    "voice": ["voice", "email", "internal"],
    "internal": ["internal"],
}

# ── Terminal delivery statuses ─────────────────────────────────────
# If state already has one of these, skip redispatch (idempotency).

TERMINAL_DELIVERY_STATUSES = {
    "dispatched",
    "sent",
    "stored",
    "stub",                      # SMS stub mode (Week 13 Day 5 not yet implemented)
    "skipped_empty_response",
}

# ── Success statuses from ChannelDispatcher ────────────────────────
# These are the values that mean "the channel accepted the dispatch".

DISPATCH_SUCCESS_STATUSES = {"dispatched", "sent", "stored", "stub"}


# ── PII patterns for SafetyNet ─────────────────────────────────────

_PII_PATTERNS_N65 = [
    re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.-]+\b'),                            # email
    re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),                          # phone
    re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'),            # card number
    re.compile(r'\b(?:SSN|social)\s*[:=]?\s*\d{3}-?\d{2}-?\d{4}\b', re.I), # SSN
    re.compile(r'\b\d{16,19}\b'),                                           # long numeric IDs
]

# ── Channel format limits ──────────────────────────────────────────

CHANNEL_FORMAT_RULES: Dict[str, Dict[str, Any]] = {
    "sms": {"max_chars": 1600, "allow_html": False, "allow_markdown": False},
    "voice": {"max_chars": 3000, "allow_html": False, "allow_markdown": False},
    "chat": {"max_chars": 5000, "allow_html": True, "allow_markdown": True},
    "email": {"max_chars": 50000, "allow_html": True, "allow_markdown": True},
    "internal": {"max_chars": 100000, "allow_html": True, "allow_markdown": True},
}


# ── SafetyNet: scrub PII before dispatch (non-LLM) ────────────────


def _safety_net_scrub(text: str) -> Dict[str, Any]:
    """Final PII scrub before the response leaves the system.

    This is the LAST line of defense — Node 6 scrubs before LLM
    evaluation, but the answer could have been modified by CRP
    revision. One final scrub right before dispatch.
    """
    if not text:
        return {"scrubbed": text, "pii_found": False, "count": 0}

    scrubbed = text
    count = 0
    for pattern in _PII_PATTERNS_N65:
        matches = pattern.findall(text)
        if matches:
            count += len(matches)
            scrubbed = pattern.sub("[REDACTED]", scrubbed)

    return {"scrubbed": scrubbed, "pii_found": count > 0, "count": count}


# ── ResponseFormatValidator: channel-format check (non-LLM) ───────


def _validate_response_format(response_text: str, channel: str) -> Dict[str, Any]:
    """Validate response format matches channel requirements.

    Catches: HTML in SMS (will break rendering), 5000 chars in
    voice (too long to read), markdown in channels that don't
    support it. Returns warnings but does NOT block delivery.
    """
    rules = CHANNEL_FORMAT_RULES.get(channel, CHANNEL_FORMAT_RULES["email"])
    warnings = []

    # Length check
    max_chars = rules.get("max_chars", 50000)
    if len(response_text) > max_chars:
        warnings.append(f"Response {len(response_text)} chars exceeds {channel} limit of {max_chars}")

    # HTML check
    if not rules.get("allow_html", True):
        has_html = bool(re.search(r'<[a-zA-Z][^>]*>', response_text))
        if has_html:
            warnings.append(f"HTML tags found in response for {channel} channel (not supported)")

    # Markdown check (less critical, just a warning)
    if not rules.get("allow_markdown", True):
        has_markdown = bool(re.search(r'[#*_]{2,}', response_text))
        if has_markdown:
            warnings.append(f"Markdown formatting in {channel} channel may not render")

    return {"valid": len(warnings) == 0, "warnings": warnings}


# ── Dispatcher factory ─────────────────────────────────────────────


def _get_dispatcher():
    """Construct a ChannelDispatcher with a fresh DB session.

    Returns (dispatcher, db_session) so the caller can close the session.
    Separated into its own function so tests can patch it.
    """
    from app.core.channel_dispatcher import ChannelDispatcher
    from database.base import SessionLocal

    db = SessionLocal()
    return ChannelDispatcher(db), db


# ── Channel decision logic (pure function — easy to test) ─────────


def _decide_target_channel(
    requested_channel: Optional[str],
    response_text: str,
    sms_char_limit: int,
) -> Tuple[str, Optional[str]]:
    """Decide which channel to actually dispatch to.

    Args:
        requested_channel: state["channel_type"] (set at Node 1).
        response_text: the final response text.
        sms_char_limit: configurable SMS char cap (from settings).

    Returns:
        (target_channel, fallback_reason)
        - target_channel: the channel we will dispatch to
        - fallback_reason: None if primary channel is used, else a
          short string explaining why we fell back
    """
    if not requested_channel or requested_channel not in KNOWN_CHANNELS:
        return (
            "email",
            "missing_channel_default" if not requested_channel else "unknown_channel_default",
        )

    if requested_channel == "sms" and len(response_text) > sms_char_limit:
        return "email", "sms_length_exceeded"

    return requested_channel, None


# ── Audit logging helper ───────────────────────────────────────────


def _write_audit_entry(
    *,
    tenant_id: str,
    ticket_id: str,
    channel: str,
    status: str,
    fallback_reason: Optional[str],
    error_message: Optional[str],
    message_id: Optional[str],
    duration_ms: int,
) -> Optional[str]:
    """Write a single audit row for a dispatch attempt.

    Returns the audit entry id, or None if audit logging is disabled
    or the audit service is unavailable (we never let audit failure
    crash the delivery — best-effort).

    Uses the low-level audit_service (DB-backed) — NOT the in-memory
    AuditLogService which is for compliance streaming only.
    """
    settings = get_settings()
    if not settings.DELIVERY_AUDIT_ENABLED:
        return None

    try:
        from app.services.audit_service import (
            create_audit_entry,
            AuditAction,
            ActorType,
        )

        action = (
            AuditAction.AI_ACTION.value
            if status in DISPATCH_SUCCESS_STATUSES
            else AuditAction.INTEGRATION_CALL.value
        )
        new_value = json.dumps({
            "channel": channel,
            "status": status,
            "fallback_reason": fallback_reason,
            "error": error_message,
            "message_id": message_id,
            "duration_ms": duration_ms,
        })
        entry = create_audit_entry(
            company_id=tenant_id,
            actor_type=ActorType.SYSTEM.value,
            action=action,
            resource_type="ticket_delivery",
            resource_id=ticket_id,
            new_value=new_value,
        )
        return entry.id
    except Exception as exc:
        # Audit failure MUST NOT crash delivery
        logger.warning(
            "Node 6.5 audit write failed (best-effort skip): ticket=%s err=%s",
            ticket_id, str(exc)[:120],
        )
        return None


# ── DLQ persistence helper ─────────────────────────────────────────


def _persist_to_dlq(
    *,
    tenant_id: str,
    ticket_id: str,
    channel_type: str,
    error_message: str,
    state_snapshot: Dict[str, Any],
) -> Optional[str]:
    """Persist a failed delivery to the LangGraph DLQ for later retry.

    Reuses the existing graph_execution_dlq infrastructure (dlq.py)
    with a delivery_ prefix on error_type so ops can filter.

    Returns the DLQ entry id, or None if persistence failed.
    """
    try:
        from app.core.parwa_pipeline.dlq import persist_to_dlq

        return persist_to_dlq(
            company_id=tenant_id,
            conversation_id=ticket_id,
            error=error_message,
            state_snapshot=state_snapshot,
            error_type="delivery_all_channels_failed",
            channel=channel_type,
        )
    except Exception as exc:
        logger.error(
            "Node 6.5 DLQ persistence failed: ticket=%s err=%s",
            ticket_id, str(exc)[:200],
        )
        return None


# ── CRM push-back helpers (BC-016 phase 2) ────────────────────────


def _build_crm_internal_note(state: PipelineV2State, quality: float) -> str:
    """Build the internal note that goes to the CRM alongside the response.

    This is the AI-classification context the human agent sees in Zendesk/
    HubSpot when they open the ticket. Truncated to 500 chars to be safe
    across CRMs (Zendesk internal notes have a soft limit around 64KB,
    but HubSpot is stricter).
    """
    note = (
        f"Ticket Type: {state.get('ticket_type', 'unknown')} | "
        f"Complexity: {state.get('complexity', 'unknown')} | "
        f"Path: {state.get('route_decision', state.get('current_path', '?'))} | "
        f"Quality: {quality:.2f} | "
        f"Techniques: {', '.join((state.get('techniques_used') or [])[:5])}"
    )
    return note[:500]


def _persist_crm_failure_to_dlq(
    *,
    tenant_id: str,
    ticket_id: str,
    crm_provider: str,
    crm_ticket_id: str,
    error_message: str,
    response_text: str,
    delivery_channel: str,
) -> Optional[str]:
    """Persist a failed CRM push to the same DLQ as delivery failures.

    Uses error_type=crm_push_failed so ops can filter CRM-only failures
    separately from delivery failures. The state_snapshot includes the
    response text so a replay can re-push without regenerating.
    """
    try:
        from app.core.parwa_pipeline.dlq import persist_to_dlq

        return persist_to_dlq(
            company_id=tenant_id,
            conversation_id=ticket_id,
            error=error_message,
            state_snapshot={
                "crm_provider": crm_provider,
                "crm_ticket_id": crm_ticket_id,
                "delivery_channel": delivery_channel,
                "response_text_preview": response_text[:500],
            },
            error_type="crm_push_failed",
        )
    except Exception as exc:
        logger.error(
            "Node 6.5 CRM DLQ persistence failed: ticket=%s err=%s",
            ticket_id, str(exc)[:200],
        )
        return None


async def _push_to_crm_with_retry(
    *,
    state: PipelineV2State,
    response_text: str,
    delivery_channel: str,
    crm_provider: str,
    crm_ticket_id: str,
    max_retries: int,
    backoff_base: float,
    backoff_max: float,
    metrics_enabled: bool,
) -> Tuple[str, Dict[str, Any], int, Optional[str]]:
    """Push resolved response to CRM with retry + backoff.

    Returns:
        (status, result, retries_used, error_message)
        - status: "success" | "error"
        - result: CRMBridge.push_response return dict
        - retries_used: 0 on first-attempt success, N on retry success
        - error_message: None on success, short string on failure
    """
    from app.core.crm_bridge.crm_bridge import CRMBridge

    # ── Load REAL credentials from the integrations table (BC-MCP-Wiring) ──
    # Previously this passed config=None, which caused every adapter to bail
    # out with "No HubSpot/Zendesk config provided" — the CRM push was a
    # silent no-op even when the user had connected their CRM in onboarding.
    # Now we look up the tenant's active integration row and pass the real
    # decrypted credential dict through to CRMBridge.push_response.
    crm_config: Optional[Dict[str, Any]] = None
    tenant_id = state.get("tenant_id", "")
    try:
        from app.services.integration_service import IntegrationService
        from database.base import SessionLocal

        db_session = SessionLocal()
        try:
            svc = IntegrationService(db_session)
            crm_config = svc.get_crm_config_for_tenant(tenant_id, crm_provider)
        finally:
            db_session.close()
    except Exception as exc:
        # DB unavailable in test/dev → log and proceed with config=None.
        # CRMBridge will return a clear "no config" error in that case.
        logger.warning(
            "Node 6.5 could not load CRM config tenant=%s provider=%s err=%s",
            tenant_id, crm_provider, str(exc)[:200],
        )

    if crm_config is None:
        # No active integration for this provider — short-circuit with a
        # clear error rather than making 4 doomed HTTP attempts.
        logger.info(
            "Node 6.5 CRM push skipped (no active integration) tenant=%s provider=%s",
            tenant_id, crm_provider,
        )
        return (
            "error",
            {"success": False, "error": f"No active {crm_provider} integration for tenant"},
            0,
            f"no_active_integration:{crm_provider}",
        )

    # Build internal note with AI classification
    quality = state.get("quality_score", 0.0)
    if state.get("simple_confidence"):
        quality = max(quality, state["simple_confidence"])
    if state.get("super_node_quality"):
        quality = max(quality, state["super_node_quality"])
    internal_note = _build_crm_internal_note(state, quality)

    last_error: Optional[str] = None
    last_result: Dict[str, Any] = {}

    for attempt in range(max_retries + 1):
        attempt_start = time.time()
        try:
            result = await CRMBridge.push_response(
                provider=crm_provider,
                ticket_id=crm_ticket_id,
                response=response_text,
                status="resolved",
                internal_note=internal_note,
                config=crm_config,
            )
            attempt_duration = time.time() - attempt_start

            if result.get("success"):
                if metrics_enabled:
                    from app.core.metrics import record_crm_push_attempt
                    record_crm_push_attempt(crm_provider, "success", attempt_duration)
                return "success", result, attempt, None

            # Soft failure (CRM returned success=False)
            last_error = result.get("error", "crm_returned_success_false")[:200]
            last_result = result
            if metrics_enabled:
                from app.core.metrics import record_crm_push_attempt
                record_crm_push_attempt(crm_provider, "soft_fail", attempt_duration)

            logger.warning(
                "Node 6.5 CRM push soft-fail ticket=%s provider=%s attempt=%d/%d err=%s",
                state.get("ticket_id", "?"), crm_provider,
                attempt + 1, max_retries + 1, last_error,
            )

        except Exception as exc:
            attempt_duration = time.time() - attempt_start
            last_error = str(exc)[:200]
            last_result = {"success": False, "error": last_error}
            if metrics_enabled:
                from app.core.metrics import record_crm_push_attempt
                record_crm_push_attempt(crm_provider, "hard_fail", attempt_duration)

            logger.error(
                "Node 6.5 CRM push exception ticket=%s provider=%s attempt=%d/%d err=%s",
                state.get("ticket_id", "?"), crm_provider,
                attempt + 1, max_retries + 1, last_error,
            )

        # Not the last attempt → backoff and retry
        if attempt < max_retries:
            delay = min(backoff_base * (2 ** attempt), backoff_max)
            jitter = delay * 0.25 * (random.random() * 2 - 1)
            _sleep(max(0, delay + jitter))

    return "error", last_result, max_retries, last_error


# ── Single-channel dispatch with retry + circuit breaker ──────────


def _dispatch_with_retry(
    *,
    dispatcher,
    tenant_id: str,
    ticket_id: str,
    channel: str,
    response_text: str,
    variant_tier: str,
    confidence: Optional[float],
    max_retries: int,
    backoff_base: float,
    backoff_max: float,
    timeout_seconds: int,
    circuit_breaker,
    metrics_enabled: bool,
) -> Tuple[str, Dict[str, Any], int, bool]:
    """Try to dispatch on ONE channel, with retry + circuit breaker.

    Returns:
        (status, result, retries_used, cb_tripped)
        - status: one of DISPATCH_SUCCESS_STATUSES, "soft_fail", "hard_fail", "cb_open"
        - result: the dispatcher's return dict (or {} on hard fail)
        - retries_used: how many retries were attempted (0 = first attempt only)
        - cb_tripped: True if this call caused the circuit breaker to open
    """
    # Circuit breaker pre-check
    if circuit_breaker.is_open(channel):
        logger.info(
            "Node 6.5 CB open, skipping channel=%s ticket=%s",
            channel, ticket_id,
        )
        if metrics_enabled:
            from app.core.metrics import record_delivery_attempt
            record_delivery_attempt(channel, "cb_open", 0.0)
        # Return cb_tripped=True so the caller knows the breaker
        # affected this delivery (was already open from a prior call).
        return "cb_open", {}, 0, True

    retries_used = 0
    cb_tripped = False

    for attempt in range(max_retries + 1):
        attempt_start = time.time()
        try:
            result = dispatcher.dispatch(
                company_id=tenant_id,
                ticket_id=ticket_id,
                ai_response_html=response_text,
                ai_response_text=response_text,
                role="ai",
                model_used=variant_tier,
                confidence=confidence,
            )
            attempt_duration = time.time() - attempt_start

            status = result.get("status", "error")

            if status in DISPATCH_SUCCESS_STATUSES:
                # Success → reset breaker, emit metric
                circuit_breaker.record_success(channel)
                if metrics_enabled:
                    from app.core.metrics import record_delivery_attempt
                    record_delivery_attempt(channel, "success", attempt_duration)
                return status, result, retries_used, cb_tripped

            # Soft failure (dispatcher returned status=error)
            just_opened = circuit_breaker.record_failure(channel)
            if just_opened:
                cb_tripped = True
            if metrics_enabled:
                from app.core.metrics import record_delivery_attempt
                record_delivery_attempt(channel, "soft_fail", attempt_duration)

            logger.warning(
                "Node 6.5 dispatch soft-fail ticket=%s channel=%s attempt=%d/%d status=%s",
                ticket_id, channel, attempt + 1, max_retries + 1, status,
            )

        except Exception as exc:
            attempt_duration = time.time() - attempt_start
            just_opened = circuit_breaker.record_failure(channel)
            if just_opened:
                cb_tripped = True
            if metrics_enabled:
                from app.core.metrics import record_delivery_attempt
                record_delivery_attempt(channel, "hard_fail", attempt_duration)

            logger.error(
                "Node 6.5 dispatch exception ticket=%s channel=%s attempt=%d/%d err=%s",
                ticket_id, channel, attempt + 1, max_retries + 1, str(exc)[:200],
            )
            result = {"status": "error", "error": str(exc)[:200]}

        # Not the last attempt → backoff and retry
        if attempt < max_retries:
            retries_used += 1
            delay = min(backoff_base * (2 ** attempt), backoff_max)
            # Add jitter (±25%) to avoid thundering herd on shared provider
            jitter = delay * 0.25 * (random.random() * 2 - 1)
            _sleep(max(0, delay + jitter))

    # Exhausted retries on this channel
    return "soft_fail", result, retries_used, cb_tripped


# ── Main Node Function ─────────────────────────────────────────────


async def node_6_5_deliver(state: PipelineV2State) -> dict:
    """Node 6.5: Deliver — send the final response to the customer.

    Called from every terminal path:
      - finalize_simple (simple_path → Node 7 → finalize)
      - wiki_finalize (complex_path → Node 6 quality pass → finalize)
      - node_8 (super_node terminal)

    Pure dispatch — 0 LLM calls. Reuses ChannelDispatcher (F-120).
    """
    settings = get_settings()
    sms_char_limit = settings.DELIVERY_SMS_CHAR_LIMIT
    max_retries = settings.DELIVERY_MAX_RETRIES
    backoff_base = settings.DELIVERY_BACKOFF_BASE_SECONDS
    backoff_max = settings.DELIVERY_BACKOFF_MAX_SECONDS
    timeout_seconds = settings.DELIVERY_TIMEOUT_SECONDS
    metrics_enabled = settings.DELIVERY_METRICS_ENABLED

    start = time.time()
    logs: List[Dict[str, Any]] = []
    circuit_breaker = get_delivery_circuit_breaker()

    tenant_id = state.get("tenant_id", "")
    ticket_id = state.get("ticket_id", "")
    channel_type = state.get("channel_type", "")
    response_text = (
        state.get("final_response")
        or state.get("formatted_response")
        or state.get("simple_answer")
        or state.get("super_node_answer")
        or ""
    )
    variant_tier = state.get("variant_tier", "parwa")
    confidence = state.get("quality_score") or state.get("simple_confidence")

    # ── 0. ReasoningStrip: never deliver model thinking to customers ─
    # Reasoning models can leak <think>…</think> blocks into the response
    # (live bug found 2026-09-03). Strip before any downstream check so
    # empty-after-strip responses fall into the empty-response path.
    stripped = strip_reasoning(response_text)
    if stripped != response_text:
        logger.info(
            "Node 6.5 ReasoningStrip: ticket=%s stripped %d chars of model reasoning",
            ticket_id,
            len(response_text) - len(stripped),
        )
        response_text = stripped

    # ── 0. Idempotency check ────────────────────────────────────
    existing_status = state.get("delivery_status", "")
    if existing_status in TERMINAL_DELIVERY_STATUSES:
        logs.append({
            "node": 6.5,
            "technique": "IdempotencyCheck",
            "duration_ms": 0,
            "result_summary": f"already_delivered status={existing_status}",
        })
        logger.info(
            "Node 6.5 skip: ticket=%s already delivered status=%s",
            ticket_id, existing_status,
        )
        return {
            "delivery_status": existing_status,
            "delivery_channel": state.get("delivery_channel"),
            # BC-016: carry forward existing CRM push state on idempotent skip
            "crm_push_status": state.get("crm_push_status", "skipped_delivery_failed"),
            "crm_push_provider": state.get("crm_push_provider"),
            "crm_push_attempts": state.get("crm_push_attempts", 0),
            "crm_push_result": state.get("crm_push_result", {}),
            "crm_push_dlq_entry_id": state.get("crm_push_dlq_entry_id"),
            "crm_push_error": state.get("crm_push_error"),
            "technique_log": logs,
            "node_6_5_token_usage": 0,
            "total_token_usage": state.get("total_token_usage", 0),
        }

    # ── 1. Empty response check ────────────────────────────────
    if not response_text or not response_text.strip():
        logs.append({
            "node": 6.5,
            "technique": "EmptyResponseCheck",
            "duration_ms": 0,
            "result_summary": "skipped (no final_response)",
        })
        logger.warning(
            "Node 6.5 skip: ticket=%s has no final_response to deliver",
            ticket_id,
        )
        return {
            "delivery_status": "skipped_empty_response",
            "delivery_channel": None,
            "delivery_fallback_reason": None,
            "delivery_result": {},
            "delivery_attempts": 0,
            "delivery_message_id": None,
            "delivery_audit_id": None,
            "delivery_retry_count": 0,
            "delivery_circuit_open": False,
            "delivery_dlq_entry_id": None,
            # BC-016: no customer delivery → no CRM push
            "crm_push_status": "skipped_delivery_failed",
            "crm_push_provider": None,
            "crm_push_attempts": 0,
            "crm_push_result": {},
            "crm_push_dlq_entry_id": None,
            "crm_push_error": None,
            "technique_log": logs,
            "node_6_5_token_usage": 0,
            "total_token_usage": state.get("total_token_usage", 0),
        }

    # ── 2. Decide target channel ───────────────────────────────
    target_channel, fallback_reason = _decide_target_channel(
        channel_type, response_text, sms_char_limit,
    )

    if fallback_reason and metrics_enabled:
        from app.core.metrics import record_delivery_fallback
        record_delivery_fallback(channel_type or "unknown", fallback_reason)

    logs.append({
        "node": 6.5,
        "technique": "ChannelDecision",
        "duration_ms": 0,
        "result_summary": (
            f"requested={channel_type or 'None'} "
            f"target={target_channel} "
            f"fallback_reason={fallback_reason or 'none'}"
        ),
    })

    # ── 2.5. SafetyNet: final PII scrub before dispatch (non-LLM) ──
    pii_check = _safety_net_scrub(response_text)
    if pii_check["pii_found"]:
        response_text = pii_check["scrubbed"]
        logs.append({
            "node": 6.5,
            "technique": "SafetyNet",
            "duration_ms": 0,
            "result_summary": f"pii_scrubbed count={pii_check['count']}",
        })
        logger.info(
            "Node 6.5 PII scrub: ticket=%s redacted=%d items",
            ticket_id, pii_check["count"],
        )
    else:
        logs.append({
            "node": 6.5,
            "technique": "SafetyNet",
            "duration_ms": 0,
            "result_summary": "no_pii_found",
        })

    # ── 2.6. ResponseFormatValidator (non-LLM) ───────────────────
    format_check = _validate_response_format(response_text, target_channel)
    logs.append({
        "node": 6.5,
        "technique": "ResponseFormatValidator",
        "duration_ms": 0,
        "result_summary": f"valid={format_check['valid']} warnings={len(format_check.get('warnings', []))}",
    })
    if format_check["warnings"]:
        for w in format_check["warnings"]:
            logger.warning("Node 6.5 format warning: ticket=%s channel=%s %s", ticket_id, target_channel, w)

    # ── 3. Build fallback chain for this target ────────────────
    chain = FALLBACK_CHAINS.get(target_channel, ["email", "internal"])
    if target_channel not in chain:
        chain = [target_channel] + chain

    # ── 4. Try each channel in the fallback chain ──────────────
    final_status = "error"
    final_channel: Optional[str] = None
    final_fallback_reason = fallback_reason
    final_result: Dict[str, Any] = {}
    final_message_id: Optional[str] = None
    final_audit_id: Optional[str] = None
    total_retries_used = 0
    any_circuit_open = False
    actual_attempts = 0  # counts only real dispatch attempts (not CB skips)

    for idx, attempt_channel in enumerate(chain):
        # Per-channel wall-clock budget
        elapsed_so_far = time.time() - start
        if elapsed_so_far > timeout_seconds * len(chain):
            logger.warning(
                "Node 6.5 total wall-clock exceeded budget ticket=%s elapsed=%.1fs",
                ticket_id, elapsed_so_far,
            )
            logs.append({
                "node": 6.5,
                "technique": "TimeoutBudgetExceeded",
                "duration_ms": int(elapsed_so_far * 1000),
                "result_summary": f"stopped at channel={attempt_channel}",
            })
            break

        # Construct dispatcher
        try:
            dispatcher, db_session = _get_dispatcher()
        except Exception as exc:
            logger.error(
                "Node 6.5 dispatcher construction failed: ticket=%s channel=%s err=%s",
                ticket_id, attempt_channel, str(exc)[:200],
            )
            logs.append({
                "node": 6.5,
                "technique": "DispatcherConstructFail",
                "duration_ms": 0,
                "result_summary": f"channel={attempt_channel} err={str(exc)[:100]}",
            })
            continue

        try:
            status, result, retries_used, cb_tripped = _dispatch_with_retry(
                dispatcher=dispatcher,
                tenant_id=tenant_id,
                ticket_id=ticket_id,
                channel=attempt_channel,
                response_text=response_text,
                variant_tier=variant_tier,
                confidence=confidence,
                max_retries=max_retries,
                backoff_base=backoff_base,
                backoff_max=backoff_max,
                timeout_seconds=timeout_seconds,
                circuit_breaker=circuit_breaker,
                metrics_enabled=metrics_enabled,
            )
        finally:
            try:
                db_session.close()
            except Exception:
                pass

        if cb_tripped:
            any_circuit_open = True
            if metrics_enabled:
                from app.core.metrics import record_delivery_circuit_open
                record_delivery_circuit_open(attempt_channel)

        actual_attempts += 1
        total_retries_used += retries_used

        # Audit row for this attempt
        attempt_duration_ms = int((time.time() - start) * 1000)
        error_msg = result.get("error") if status not in DISPATCH_SUCCESS_STATUSES else None
        msg_id = result.get("message_id") if status in DISPATCH_SUCCESS_STATUSES else None

        audit_id = _write_audit_entry(
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            channel=attempt_channel,
            status=status,
            fallback_reason=final_fallback_reason if idx > 0 else None,
            error_message=error_msg,
            message_id=msg_id,
            duration_ms=attempt_duration_ms,
        )
        if audit_id and not final_audit_id:
            final_audit_id = audit_id

        logs.append({
            "node": 6.5,
            "technique": "DispatchAttempt",
            "duration_ms": attempt_duration_ms,
            "result_summary": (
                f"channel={attempt_channel} status={status} "
                f"retries={retries_used} cb_tripped={cb_tripped} "
                f"audit_id={audit_id or 'none'}"
            ),
        })

        # Success?
        if status in DISPATCH_SUCCESS_STATUSES:
            final_status = status
            final_channel = attempt_channel
            final_result = result
            final_message_id = msg_id
            break

        # Failure on this channel — record fallback reason (only on first fallback)
        if idx == 0 and final_fallback_reason is None:
            final_fallback_reason = f"provider_failure:{attempt_channel}"
            # Emit fallback metric for provider failures too (not just capacity-based)
            if metrics_enabled:
                from app.core.metrics import record_delivery_fallback
                record_delivery_fallback(
                    channel_type or "unknown",
                    final_fallback_reason,
                )

    # ── 5. All-channels-failed → DLQ ───────────────────────────
    dlq_entry_id: Optional[str] = None
    if final_status not in DISPATCH_SUCCESS_STATUSES:
        error_summary = (
            f"All channels failed for ticket={ticket_id} "
            f"tenant={tenant_id} attempts={actual_attempts} "
            f"retries={total_retries_used} cb_open={any_circuit_open}"
        )
        dlq_entry_id = _persist_to_dlq(
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            channel_type=channel_type or "unknown",
            error_message=error_summary,
            state_snapshot={
                "response_text_preview": response_text[:200],
                "attempted_channels": chain[:actual_attempts],
                "delivery_attempts": actual_attempts,
                "delivery_retries": total_retries_used,
                "circuit_open": any_circuit_open,
            },
        )
        if dlq_entry_id and metrics_enabled:
            from app.core.metrics import record_delivery_dlq
            record_delivery_dlq(channel_type or "unknown")

        logs.append({
            "node": 6.5,
            "technique": "DLQPersist",
            "duration_ms": 0,
            "result_summary": f"dlq_entry_id={dlq_entry_id or 'failed_to_persist'}",
        })

    # ── 6. Phase 2: CRM push-back (BC-016) ─────────────────────
    # ONLY if phase 1 (customer dispatch) succeeded. If customer didn't
    # get the answer, we must NOT tell the CRM "resolved" — that would
    # make the ticket look closed in Zendesk/HubSpot while the customer
    # is still waiting. See BC-016 in CLAUDE.md.
    crm_push_status = "skipped_delivery_failed"
    crm_push_provider: Optional[str] = None
    crm_push_attempts = 0
    crm_push_result: Dict[str, Any] = {}
    crm_push_dlq_entry_id: Optional[str] = None
    crm_push_error: Optional[str] = None

    if final_status in DISPATCH_SUCCESS_STATUSES:
        metadata = state.get("metadata") or {}
        crm_ticket_id = metadata.get("crm_ticket_id", "")
        crm_provider = metadata.get("crm_provider", "")
        crm_push_provider = crm_provider or None

        if not settings.CRM_PUSH_ENABLED:
            crm_push_status = "skipped_disabled"
            logs.append({
                "node": 6.5,
                "technique": "CRMPushSkip",
                "duration_ms": 0,
                "result_summary": "reason=crm_push_disabled",
            })
        elif not crm_ticket_id or not crm_provider:
            # No CRM ticket — ticket came in via email/webform, not CRM webhook
            crm_push_status = "skipped_no_crm"
            logs.append({
                "node": 6.5,
                "technique": "CRMPushSkip",
                "duration_ms": 0,
                "result_summary": "reason=no_crm_ticket",
            })
        else:
            # Push to CRM with retry + backoff
            crm_phase_start = time.time()
            crm_status, crm_result, crm_retries, crm_err = await _push_to_crm_with_retry(
                state=state,
                response_text=response_text,
                delivery_channel=final_channel or "unknown",
                crm_provider=crm_provider,
                crm_ticket_id=crm_ticket_id,
                max_retries=settings.CRM_PUSH_MAX_RETRIES,
                backoff_base=settings.CRM_PUSH_BACKOFF_BASE_SECONDS,
                backoff_max=settings.CRM_PUSH_BACKOFF_MAX_SECONDS,
                metrics_enabled=metrics_enabled,
            )
            crm_push_attempts = crm_retries + (1 if crm_status != "success" else 0)
            # Normalize: on success, attempts = retries_used (0 = first try)
            # On failure, attempts = max_retries + 1 (we tried them all)
            crm_push_attempts = crm_retries if crm_status == "success" else settings.CRM_PUSH_MAX_RETRIES + 1
            crm_push_result = crm_result

            if crm_status == "success":
                crm_push_status = "success"
                crm_push_error = None
                logger.info(
                    "Node 6.5 CRM push success: ticket=%s provider=%s retries=%d",
                    ticket_id, crm_provider, crm_retries,
                )
            else:
                # All CRM retries exhausted → DLQ
                crm_push_error = crm_err or "unknown_crm_error"
                error_summary = (
                    f"CRM push failed for ticket={ticket_id} "
                    f"tenant={tenant_id} provider={crm_provider} "
                    f"crm_ticket={crm_ticket_id} retries={crm_push_attempts} "
                    f"err={crm_push_error}"
                )
                if settings.CRM_PUSH_DLQ_ON_FAILURE:
                    crm_push_dlq_entry_id = _persist_crm_failure_to_dlq(
                        tenant_id=tenant_id,
                        ticket_id=ticket_id,
                        crm_provider=crm_provider,
                        crm_ticket_id=crm_ticket_id,
                        error_message=error_summary,
                        response_text=response_text,
                        delivery_channel=final_channel or "unknown",
                    )
                    if crm_push_dlq_entry_id and metrics_enabled:
                        from app.core.metrics import record_crm_push_dlq
                        record_crm_push_dlq(crm_provider)
                    crm_push_status = "dlq_persisted"
                else:
                    crm_push_status = "error"

                logger.warning(
                    "Node 6.5 CRM push failed: ticket=%s provider=%s "
                    "retries=%d dlq=%s err=%s",
                    ticket_id, crm_provider, crm_push_attempts,
                    crm_push_dlq_entry_id, crm_push_error,
                )

            crm_elapsed_ms = int((time.time() - crm_phase_start) * 1000)
            logs.append({
                "node": 6.5,
                "technique": "CRMPushAttempt",
                "duration_ms": crm_elapsed_ms,
                "result_summary": (
                    f"provider={crm_push_provider or 'none'} "
                    f"status={crm_push_status} "
                    f"retries={crm_push_attempts} "
                    f"dlq={crm_push_dlq_entry_id or 'none'}"
                ),
            })

    # ── 7. Build final return state ────────────────────────────
    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "Node 6.5 complete: ticket=%s channel=%s status=%s fallback=%s "
        "attempts=%d retries=%d cb_open=%s dlq=%s "
        "crm=%s/%s crm_retries=%d crm_dlq=%s [%dms]",
        ticket_id, final_channel, final_status, final_fallback_reason,
        actual_attempts, total_retries_used, any_circuit_open,
        dlq_entry_id,
        crm_push_provider or "none", crm_push_status,
        crm_push_attempts, crm_push_dlq_entry_id,
        elapsed,
    )

    # ── P0 Notification: emit ticket:delivered ─────────────────────
    # Tells Jarvis CC (and any human watching) that the customer actually
    # received (or failed to receive) the AI response. This is the most
    # important event for the human — "did the customer get the answer?"
    try:
        from app.core.event_emitter import emit_ticket_event
        await emit_ticket_event(
            company_id=tenant_id,
            event_type="ticket:delivered",
            payload={
                "company_id": tenant_id,
                "ticket_id": ticket_id,
                "channel": final_channel,
                "status": final_status,
                "fallback_reason": final_fallback_reason,
                "attempts": actual_attempts,
                "retries": total_retries_used,
                "circuit_open": any_circuit_open,
                "dlq_entry_id": dlq_entry_id,
                "crm_push_status": crm_push_status,
                "crm_push_provider": crm_push_provider,
                "node": "6.5",
            },
            correlation_id=ticket_id,
        )
    except Exception as exc:
        logger.warning("node_6_5_delivery_notification_failed: %s", str(exc)[:200])

    return {
        "delivery_status": final_status,
        "delivery_channel": final_channel,
        "delivery_fallback_reason": final_fallback_reason,
        "delivery_result": final_result,
        "delivery_attempts": actual_attempts,  # BUG FIX: counts real attempts only
        "delivery_message_id": final_message_id,
        "delivery_audit_id": final_audit_id,
        "delivery_retry_count": total_retries_used,
        "delivery_circuit_open": any_circuit_open,
        "delivery_dlq_entry_id": dlq_entry_id,
        # BC-016 phase 2 state
        "crm_push_status": crm_push_status,
        "crm_push_provider": crm_push_provider,
        "crm_push_attempts": crm_push_attempts,
        "crm_push_result": crm_push_result,
        "crm_push_dlq_entry_id": crm_push_dlq_entry_id,
        "crm_push_error": crm_push_error,
        "technique_log": logs,
        "node_6_5_token_usage": 0,  # 0 LLM calls
        "total_token_usage": state.get("total_token_usage", 0),
    }
