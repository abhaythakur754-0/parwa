"""
Guidance Ticket Flow — Lightweight reprocessing of escalated tickets using human guidance.

Unlike the full Resume Pipeline (which uses KB + CoT + Reflexion with a high threshold),
the Guidance Ticket Flow treats human guidance as the PRIMARY input and has a LOWER
quality threshold. It is designed for cases where:
  - A human agent has provided clear, actionable guidance
  - The ticket has already failed a full resume attempt
  - A quick turnaround is preferred over exhaustive LLM reasoning

Flow:
  1. Validate escalation exists and is eligible (failed or guidance_provided)
  2. Validate guidance meets minimum requirements (>= 5 chars)
  3. Build guidance-centric context (guidance as primary, KB as supplementary)
  4. Generate response using guidance as anchor (1 LLM call)
  5. Non-LLM quality checks (guidance alignment, coherence, length)
  6. If quality >= threshold → save result, mark done, attempt CRM push
  7. If quality < threshold → mark reprocess_status as FAILED

Quality Threshold: 0.75 (lower than resume pipeline's 0.88)
  - Resume uses KB as primary + extensive LLM reasoning → high bar
  - Guidance uses human guidance as primary → lower bar, but guidance must be good

Idempotency:
  - If an escalation already has reprocess_status DONE or PROCESSING, skip it.
  - Multiple calls on the same eligible escalation: the first to set PROCESSING wins.
"""
from __future__ import annotations

import logging
import random
import re
import time
import threading
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("parwa.guidance_ticket_flow")

# Quality threshold — lower than Resume Pipeline's 0.88
# because guidance comes from a human who already understands the context
GUIDANCE_QUALITY_THRESHOLD = 0.75

# Minimum guidance length to be considered valid
MIN_GUIDANCE_LENGTH = 5

# Maximum guidance length (handled gracefully — truncated if exceeded)
MAX_GUIDANCE_LENGTH = 10000

# Lock for concurrent safety
_guidance_lock = threading.Lock()
_processing_set: set = set()  # Track escalations currently being processed

# BC-017: indirection so tests can monkeypatch backoff without affecting
# the real time.sleep used by other code paths.
_sleep = time.sleep


# ── BC-017 Gap 2 + Gap 3: CRM push helpers ──────────────────────────
# These mirror the Node 6.5 / Node 8 patterns: retry + exponential
# backoff + jitter + DLQ + metrics. Two operations:
#   1. push_resume_result      — fired when guidance quality passes
#   2. push_permanent_failure  — fired when GUIDANCE_MAX_RETRIES exceeded
# Both reuse the existing graph_execution_dlq table with distinct
# error_type values so ops can filter them in dashboards.


def _persist_crm_resume_failure_to_dlq(
    *,
    tenant_id: str,
    ticket_id: str,
    escalation_id: str,
    crm_provider: str,
    crm_ticket_id: str,
    response_text: str,
    quality_score: float,
    error_message: str,
) -> Optional[str]:
    """Persist a failed CRM resume push to the DLQ (BC-017 Gap 2)."""
    try:
        from app.core.parwa_pipeline.dlq import persist_to_dlq

        return persist_to_dlq(
            company_id=tenant_id,
            conversation_id=ticket_id,
            error=error_message,
            state_snapshot={
                "escalation_id": escalation_id,
                "crm_provider": crm_provider,
                "crm_ticket_id": crm_ticket_id,
                "quality_score": quality_score,
                "response_text_preview": response_text[:500],
                "operation": "push_resume_result",
            },
            error_type="crm_resume_push_failed",
        )
    except Exception as exc:
        logger.error(
            "Guidance flow resume DLQ persistence failed: escalation=%s err=%s",
            escalation_id, str(exc)[:200],
        )
        return None


def _persist_crm_permanent_failure_to_dlq(
    *,
    tenant_id: str,
    ticket_id: str,
    escalation_id: str,
    crm_provider: str,
    crm_ticket_id: str,
    attempts: int,
    failure_context: Dict[str, Any],
    error_message: str,
) -> Optional[str]:
    """Persist a failed permanent-failure push to the DLQ (BC-017 Gap 3).

    This is the worst-case DLQ: AI gave up AND we couldn't even tell CRM
    about it. Ops must manually reset the CRM ticket to "open" and notify
    the human team.
    """
    try:
        from app.core.parwa_pipeline.dlq import persist_to_dlq

        return persist_to_dlq(
            company_id=tenant_id,
            conversation_id=ticket_id,
            error=error_message,
            state_snapshot={
                "escalation_id": escalation_id,
                "crm_provider": crm_provider,
                "crm_ticket_id": crm_ticket_id,
                "attempts": attempts,
                "failure_context": failure_context,
                "operation": "push_permanent_failure",
                "manual_action_required": "Reset CRM ticket to open/new manually",
            },
            error_type="crm_permanent_failure_push_failed",
        )
    except Exception as exc:
        logger.error(
            "Guidance flow permanent-failure DLQ persistence failed: escalation=%s err=%s",
            escalation_id, str(exc)[:200],
        )
        return None


async def _push_resume_to_crm_with_retry(
    *,
    tenant_id: str,
    ticket_id: str,
    escalation_id: str,
    crm_provider: str,
    crm_ticket_id: str,
    response_text: str,
    quality_score: float,
    human_guidance: str,
    max_retries: int,
    backoff_base: float,
    backoff_max: float,
    metrics_enabled: bool,
    dlq_on_failure: bool,
) -> Tuple[str, Dict[str, Any], int, Optional[str], Optional[str]]:
    """Push resume result to CRM with retry + backoff (BC-017 Gap 2).

    Returns:
        (status, result, retries_used, error_message, dlq_entry_id)
    """
    from app.core.crm_bridge.crm_bridge import CRMBridge

    # ── Load REAL credentials from the integrations table (BC-MCP-Wiring) ──
    crm_config: Optional[Dict[str, Any]] = None
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
        logger.warning(
            "Guidance flow could not load CRM config tenant=%s provider=%s err=%s",
            tenant_id, crm_provider, str(exc)[:200],
        )

    if crm_config is None:
        logger.info(
            "Guidance flow CRM resume push skipped (no active integration) tenant=%s provider=%s",
            tenant_id, crm_provider,
        )
        return (
            "error",
            {"success": False, "error": f"No active {crm_provider} integration for tenant"},
            0,
            f"no_active_integration:{crm_provider}",
            None,
        )

    last_error: Optional[str] = None
    last_result: Dict[str, Any] = {}

    for attempt in range(max_retries + 1):
        attempt_start = time.time()
        try:
            result = await CRMBridge.push_resume_result(
                provider=crm_provider,
                ticket_id=crm_ticket_id,
                response=response_text,
                quality_score=quality_score,
                human_guidance=human_guidance,
                config=crm_config,
            )
            attempt_duration = time.time() - attempt_start

            if result.get("success"):
                if metrics_enabled:
                    from app.core.metrics import record_crm_escalation_push_attempt
                    record_crm_escalation_push_attempt(
                        crm_provider, "resume", "success", attempt_duration,
                    )
                return "success", result, attempt, None, None

            last_error = (result.get("error") or "crm_returned_success_false")[:200]
            last_result = result
            if metrics_enabled:
                from app.core.metrics import record_crm_escalation_push_attempt
                record_crm_escalation_push_attempt(
                    crm_provider, "resume", "soft_fail", attempt_duration,
                )
            logger.warning(
                "Guidance flow CRM resume soft-fail escalation=%s provider=%s attempt=%d/%d err=%s",
                escalation_id[:8], crm_provider, attempt + 1, max_retries + 1, last_error,
            )

        except Exception as exc:
            attempt_duration = time.time() - attempt_start
            last_error = str(exc)[:200]
            last_result = {"success": False, "error": last_error}
            if metrics_enabled:
                from app.core.metrics import record_crm_escalation_push_attempt
                record_crm_escalation_push_attempt(
                    crm_provider, "resume", "hard_fail", attempt_duration,
                )
            logger.error(
                "Guidance flow CRM resume exception escalation=%s provider=%s attempt=%d/%d err=%s",
                escalation_id[:8], crm_provider, attempt + 1, max_retries + 1, last_error,
            )

        if attempt < max_retries:
            delay = min(backoff_base * (2 ** attempt), backoff_max)
            jitter = delay * 0.25 * (random.random() * 2 - 1)
            _sleep(max(0, delay + jitter))

    # All retries exhausted → DLQ
    dlq_entry_id: Optional[str] = None
    if dlq_on_failure:
        dlq_entry_id = _persist_crm_resume_failure_to_dlq(
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            escalation_id=escalation_id,
            crm_provider=crm_provider,
            crm_ticket_id=crm_ticket_id,
            response_text=response_text,
            quality_score=quality_score,
            error_message=f"CRM resume push failed after {max_retries + 1} attempts: {last_error}",
        )
        if metrics_enabled:
            from app.core.metrics import record_crm_push_dlq
            record_crm_push_dlq(crm_provider)

    return "error", last_result, max_retries, last_error, dlq_entry_id


async def _push_permanent_failure_to_crm_with_retry(
    *,
    tenant_id: str,
    ticket_id: str,
    escalation_id: str,
    crm_provider: str,
    crm_ticket_id: str,
    attempts: int,
    failure_context: Dict[str, Any],
    max_retries: int,
    backoff_base: float,
    backoff_max: float,
    metrics_enabled: bool,
    dlq_on_failure: bool,
) -> Tuple[str, Dict[str, Any], int, Optional[str], Optional[str]]:
    """Push permanent-failure reset to CRM with retry + backoff (BC-017 Gap 3).

    Returns:
        (status, result, retries_used, error_message, dlq_entry_id)

    On success: CRM ticket is reset to "open"/"new", human queue picks
    it up fresh. On failure: persisted to DLQ with
    error_type=crm_permanent_failure_push_failed — ops MUST manually
    reset the CRM ticket and notify the human team.
    """
    from app.core.crm_bridge.crm_bridge import CRMBridge

    # ── Load REAL credentials from the integrations table (BC-MCP-Wiring) ──
    crm_config: Optional[Dict[str, Any]] = None
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
        logger.warning(
            "Guidance flow could not load CRM config tenant=%s provider=%s err=%s",
            tenant_id, crm_provider, str(exc)[:200],
        )

    if crm_config is None:
        logger.info(
            "Guidance flow CRM permanent-failure push skipped (no active integration) tenant=%s provider=%s",
            tenant_id, crm_provider,
        )
        return (
            "error",
            {"success": False, "error": f"No active {crm_provider} integration for tenant"},
            0,
            f"no_active_integration:{crm_provider}",
            None,
        )

    last_error: Optional[str] = None
    last_result: Dict[str, Any] = {}

    for attempt in range(max_retries + 1):
        attempt_start = time.time()
        try:
            result = await CRMBridge.push_permanent_failure(
                provider=crm_provider,
                ticket_id=crm_ticket_id,
                attempts=attempts,
                failure_context=failure_context,
                config=crm_config,
            )
            attempt_duration = time.time() - attempt_start

            if result.get("success"):
                if metrics_enabled:
                    from app.core.metrics import record_crm_escalation_push_attempt
                    record_crm_escalation_push_attempt(
                        crm_provider, "permanent_failure", "success", attempt_duration,
                    )
                    from app.core.metrics import record_crm_permanent_failure
                    record_crm_permanent_failure(crm_provider)
                return "success", result, attempt, None, None

            last_error = (result.get("error") or "crm_returned_success_false")[:200]
            last_result = result
            if metrics_enabled:
                from app.core.metrics import record_crm_escalation_push_attempt
                record_crm_escalation_push_attempt(
                    crm_provider, "permanent_failure", "soft_fail", attempt_duration,
                )
            logger.warning(
                "Guidance flow CRM permanent-failure soft-fail escalation=%s provider=%s attempt=%d/%d err=%s",
                escalation_id[:8], crm_provider, attempt + 1, max_retries + 1, last_error,
            )

        except Exception as exc:
            attempt_duration = time.time() - attempt_start
            last_error = str(exc)[:200]
            last_result = {"success": False, "error": last_error}
            if metrics_enabled:
                from app.core.metrics import record_crm_escalation_push_attempt
                record_crm_escalation_push_attempt(
                    crm_provider, "permanent_failure", "hard_fail", attempt_duration,
                )
            logger.error(
                "Guidance flow CRM permanent-failure exception escalation=%s provider=%s attempt=%d/%d err=%s",
                escalation_id[:8], crm_provider, attempt + 1, max_retries + 1, last_error,
            )

        if attempt < max_retries:
            delay = min(backoff_base * (2 ** attempt), backoff_max)
            jitter = delay * 0.25 * (random.random() * 2 - 1)
            _sleep(max(0, delay + jitter))

    # All retries exhausted → DLQ (this is the worst-case DLQ)
    dlq_entry_id: Optional[str] = None
    if dlq_on_failure:
        dlq_entry_id = _persist_crm_permanent_failure_to_dlq(
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            escalation_id=escalation_id,
            crm_provider=crm_provider,
            crm_ticket_id=crm_ticket_id,
            attempts=attempts,
            failure_context=failure_context,
            error_message=f"CRM permanent-failure push failed after {max_retries + 1} attempts: {last_error}",
        )
        if metrics_enabled:
            from app.core.metrics import record_crm_push_dlq
            record_crm_push_dlq(crm_provider)

    return "error", last_result, max_retries, last_error, dlq_entry_id


async def create_guidance_ticket(
    escalation_id: str,
    guidance: str,
    knowledge_context: Optional[List[Dict]] = None,
    tenant_id: str = "",
) -> Dict[str, Any]:
    """Create and process a guidance ticket for an escalated ticket.

    This is the main entry point. Uses human guidance as the primary input
    to generate an improved response.

    Args:
        escalation_id: The vault escalation ID
        guidance: Human agent's guidance text (>= 5 chars)
        knowledge_context: Optional additional KB docs (supplements guidance)
        tenant_id: Tenant ID (fallback from escalation if not provided)

    Returns:
        {
            "success": True/False,
            "escalation_id": "...",
            "flow": "guidance_ticket",
            "reprocess_result": "improved response" or "",
            "reprocess_quality": 0.82,
            "quality_passed": True/False,
            "error": "error message" or None,
            "technique_log": [...],
            "crm_push": {"success": True/False},
            "elapsed_ms": 42,
        }
    """
    start = time.time()
    logs: List[Dict[str, Any]] = []

    # ── Step 1: Validate guidance ───────────────────────────
    if not guidance or len(guidance.strip()) < MIN_GUIDANCE_LENGTH:
        return {
            "success": False,
            "escalation_id": escalation_id,
            "flow": "guidance_ticket",
            "error": f"Guidance too short (minimum {MIN_GUIDANCE_LENGTH} characters)",
            "reprocess_result": "",
            "reprocess_quality": 0.0,
            "quality_passed": False,
            "technique_log": logs,
            "crm_push": {"success": False, "reason": "invalid_guidance"},
            "elapsed_ms": 0,
        }

    # Truncate excessively long guidance gracefully
    guidance_text = guidance[:MAX_GUIDANCE_LENGTH]
    if len(guidance) > MAX_GUIDANCE_LENGTH:
        logs.append({
            "step": "validate",
            "duration_ms": 0,
            "result": f"guidance truncated from {len(guidance)} to {MAX_GUIDANCE_LENGTH} chars",
        })

    logs.append({"step": "validate", "duration_ms": 0, "result": f"guidance_len={len(guidance_text)}"})

    # ── Step 2: Load escalation from vault ──────────────────
    from app.core.escalation_vault.vault_manager import VaultManager

    escalation = await VaultManager.get_escalation(escalation_id)
    if not escalation:
        return {
            "success": False,
            "escalation_id": escalation_id,
            "flow": "guidance_ticket",
            "error": f"Escalation {escalation_id} not found",
            "reprocess_result": "",
            "reprocess_quality": 0.0,
            "quality_passed": False,
            "technique_log": logs,
            "crm_push": {"success": False, "reason": "not_found"},
            "elapsed_ms": 0,
        }

    tenant_id = tenant_id or escalation.get("tenant_id", "")
    original_quality = escalation.get("quality_score", 0.0)
    original_query = escalation.get("original_query", "")

    if not original_query:
        logs.append({"step": "load", "duration_ms": 0, "result": "warning: no original_query"})
        original_query = escalation.get("ticket_type", "general inquiry")

    logs.append({
        "step": "load",
        "duration_ms": 0,
        "result": f"loaded escalation={escalation_id[:8]} original_quality={original_quality:.2f}",
    })

    # ── Step 3: Idempotency check ───────────────────────────
    reprocess_status = escalation.get("reprocess_status", "pending")
    with _guidance_lock:
        if escalation_id in _processing_set:
            return {
                "success": False,
                "escalation_id": escalation_id,
                "flow": "guidance_ticket",
                "error": "Escalation is already being processed by another guidance ticket",
                "reprocess_result": "",
                "reprocess_quality": 0.0,
                "quality_passed": False,
                "technique_log": logs,
                "crm_push": {"success": False, "reason": "already_processing"},
                "elapsed_ms": 0,
            }
        if reprocess_status == "done":
            return {
                "success": False,
                "escalation_id": escalation_id,
                "flow": "guidance_ticket",
                "error": "Escalation already has a completed reprocess result (idempotency)",
                "reprocess_result": escalation.get("reprocess_result", ""),
                "reprocess_quality": escalation.get("reprocess_quality_score", 0.0),
                "quality_passed": True,
                "technique_log": logs,
                "crm_push": {"success": False, "reason": "already_done"},
                "elapsed_ms": 0,
            }
        _processing_set.add(escalation_id)

    try:
        # ── Step 4: Update guidance in vault ────────────────
        await VaultManager.provide_human_guidance(
            escalation_id, guidance_text, source="guidance_ticket"
        )
        logs.append({"step": "update_guidance", "duration_ms": 0, "result": "guidance_saved"})

        # ── Step 5: Build guidance-centric context ─────────
        from app.core.escalation_vault.vault_db import (
            REPROCESS_PROCESSING, REPROCESS_EXHAUSTED, get_vault_db,
        )
        vault_db = get_vault_db()
        await vault_db.update_reprocess_status_direct(escalation_id, REPROCESS_PROCESSING)

        # BC-017: increment the per-escalation attempt counter. When this
        # exceeds GUIDANCE_MAX_RETRIES, we fire push_permanent_failure and
        # set reprocess_status=REPROCESS_EXHAUSTED (terminal state). The
        # CRM ticket is reset to "open"/"new" so the human queue picks it
        # up fresh, exactly like before PARWA touched it.
        from app.config import get_settings
        _settings = get_settings()
        _max_retries = _settings.GUIDANCE_MAX_RETRIES
        attempt_count = await VaultManager.increment_reprocess_attempts(escalation_id)
        if attempt_count < 0:
            # lookup failed — treat as attempt 1
            attempt_count = 1
        logs.append({
            "step": "increment_attempts",
            "duration_ms": 0,
            "result": f"attempt_count={attempt_count} max={_max_retries}",
        })

        # Knowledge context: use provided or escalation's stored KB
        kb_docs = knowledge_context or escalation.get("knowledge_context", [])
        kb_str = "\n".join(
            d.get("content", "") if isinstance(d, dict) else str(d) for d in kb_docs
        )[:2000]

        ticket_type = escalation.get("ticket_type", "general")
        complexity = escalation.get("complexity", "moderate")
        customer_ctx = escalation.get("customer_context", {})

        guidance_context = f"""HUMAN AGENT GUIDANCE (PRIMARY — TRUST THIS):
{guidance_text}

SUPPORTING KNOWLEDGE BASE (for cross-reference only):
{kb_str if kb_str else "No additional knowledge base context available."}

TICKET TYPE: {ticket_type}
COMPLEXITY: {complexity}
CUSTOMER: {str(customer_ctx)[:300]}
"""

        logs.append({"step": "build_context", "duration_ms": 0, "result": "guidance_centric_context_built"})

        # ── Step 6: Generate response (1 LLM call) ────────
        llm_calls = 0
        try:
            from app.core.parwa_pipeline.llm_client import llm_call

            generation_prompt = f"""You are a customer support AI. A human support agent has provided
direct guidance for handling this ticket. Their guidance is the PRIMARY source of truth.

Customer's Question: "{original_query}"

{guidance_context}

Instructions:
1. Follow the human agent's guidance as your primary direction
2. Use the knowledge base only to verify dates, amounts, or specific details
3. Write a clear, professional response that addresses the customer's question
4. Be specific with any amounts, dates, or steps mentioned in the guidance
5. Keep the tone empathetic and professional

Write the complete customer response:"""

            improved_response = await llm_call(generation_prompt, max_tokens=500)
            logs.append({"step": "llm_generate", "duration_ms": 0, "result": "response_generated"})
            llm_calls = 1
        except Exception as e:
            logger.error("Guidance Ticket: LLM generation failed: %s", e)
            # Fallback: craft response directly from guidance
            improved_response = (
                f"Thank you for your patience. Based on our review:\n\n"
                f"{guidance_text}\n\n"
                f"If you need further assistance, please don't hesitate to reach out."
            )
            logs.append({
                "step": "llm_generate", "duration_ms": 0,
                "result": f"fallback_used: {str(e)[:100]}",
            })

        # ── Step 7: Non-LLM quality checks ────────────────

        # Guidance alignment (highest weight — this is guidance-driven)
        guide_words = set(guidance_text.lower().split())
        ans_words = set(improved_response.lower().split())
        guidance_alignment = len(guide_words & ans_words) / max(len(guide_words), 1)

        # KB alignment (lower weight — supplementary)
        kb_words = set(kb_str.lower().split())
        kb_alignment = len(kb_words & ans_words) / max(len(ans_words), 1)

        # Structural coherence: sentences with >= 3 words
        sentences = [s.strip() for s in improved_response.replace("!", ".").split(".") if s.strip()]
        coherence = 1.0 if sentences and sum(len(s.split()) for s in sentences) / len(sentences) >= 3 else 0.7

        # Substantive content: paragraphs >= 20 chars
        parts = [p.strip() for p in improved_response.split("\n\n") if p.strip()]
        substance = sum(1.0 for p in parts if len(p) >= 20) / max(len(parts), 1)

        # Length check
        length_ok = 1.0 if len(improved_response) >= 50 else 0.5

        logs.append({
            "step": "quality_checks",
            "duration_ms": 0,
            "result": (
                f"guidance_align={guidance_alignment:.2f} "
                f"kb_align={kb_alignment:.2f} "
                f"coherence={coherence:.2f} "
                f"substance={substance:.2f} "
                f"length_ok={length_ok:.2f}"
            ),
        })

        # ── Step 8: Calculate quality score ───────────────
        # Guidance alignment gets 35% weight (primary signal)
        # Coherence gets 20%, Substance 20%, KB 15%, Length 10%
        guidance_quality = (
            guidance_alignment * 0.35 +
            coherence * 0.20 +
            substance * 0.20 +
            kb_alignment * 0.15 +
            length_ok * 0.10
        )

        passed = guidance_quality >= GUIDANCE_QUALITY_THRESHOLD

        logs.append({
            "step": "quality_result",
            "duration_ms": 0,
            "result": f"quality={guidance_quality:.4f} threshold={GUIDANCE_QUALITY_THRESHOLD} passed={passed}",
        })

        elapsed = int((time.time() - start) * 1000)

        # ── Step 9: Save result to vault ───────────────────
        # BC-017: three possible terminal states:
        #   - passed → REPROCESS_DONE
        #   - not passed AND under MAX_RETRIES → REPROCESS_FAILED (still retryable)
        #   - not passed AND at/over MAX_RETRIES → REPROCESS_EXHAUSTED (terminal)
        is_exhausted = (not passed) and (attempt_count >= _max_retries)

        if passed:
            await VaultManager.save_resume_result(
                escalation_id=escalation_id,
                result=improved_response,
                quality_score=guidance_quality,
                technique_log=logs,
            )
        elif is_exhausted:
            # BC-017 Gap 3: terminal state — AI gave up. Mark exhausted so
            # batch_guidance_tickets stops re-queuing this escalation.
            await vault_db.update_reprocess_result(
                escalation_id, improved_response, guidance_quality, logs
            )
            await vault_db.update_reprocess_status_direct(escalation_id, REPROCESS_EXHAUSTED)
            logs.append({
                "step": "exhausted",
                "duration_ms": 0,
                "result": f"attempts={attempt_count} >= max={_max_retries} → permanent_failure",
            })
        else:
            # Still under the retry limit — mark as failed so batch can re-queue.
            from app.core.escalation_vault.vault_db import REPROCESS_FAILED
            await vault_db.update_reprocess_result(
                escalation_id, improved_response, guidance_quality, logs
            )
            await vault_db.update_reprocess_status_direct(escalation_id, REPROCESS_FAILED)

        # ── Step 10: CRM push (3 paths) ───────────────────
        #   - passed → push_resume_result (BC-017 Gap 2: retry + DLQ)
        #   - exhausted → push_permanent_failure (BC-017 Gap 3: reset CRM to open/new)
        #   - failed-but-retryable → no CRM push yet (wait for next attempt)
        crm_push = {"success": False, "reason": "no_crm_ticket"}
        crm_ticket_id = escalation.get("crm_ticket_id", "")
        crm_provider = escalation.get("crm_provider", "")

        if crm_ticket_id and crm_provider and passed:
            # BC-017 Gap 2: resume push with retry + backoff + DLQ
            try:
                crm_status, crm_result, crm_retries, crm_err, crm_dlq = (
                    await _push_resume_to_crm_with_retry(
                        tenant_id=tenant_id or escalation.get("tenant_id", ""),
                        ticket_id=escalation.get("original_ticket_id", escalation_id),
                        escalation_id=escalation_id,
                        crm_provider=crm_provider,
                        crm_ticket_id=crm_ticket_id,
                        response_text=improved_response,
                        quality_score=guidance_quality,
                        human_guidance=guidance_text,
                        max_retries=_settings.CRM_PUSH_MAX_RETRIES,
                        backoff_base=_settings.CRM_PUSH_BACKOFF_BASE_SECONDS,
                        backoff_max=_settings.CRM_PUSH_BACKOFF_MAX_SECONDS,
                        metrics_enabled=_settings.DELIVERY_METRICS_ENABLED,
                        dlq_on_failure=_settings.GUIDANCE_CRM_DLQ_ON_FAILURE,
                    )
                )
                crm_push = crm_result
                if crm_dlq:
                    crm_push["dlq_entry_id"] = crm_dlq
                await VaultManager.update_crm_push_back(
                    escalation_id=escalation_id,
                    status="updated" if crm_status == "success" else "failed",
                    crm_response=crm_push,
                )
            except Exception as e:
                logger.error("Guidance Ticket: CRM resume push failed: %s", e)
                crm_push = {"success": False, "reason": str(e)}

        elif crm_ticket_id and crm_provider and is_exhausted:
            # BC-017 Gap 3: AI gave up → reset CRM to "open"/"new"
            try:
                failure_context = {
                    "last_quality": guidance_quality,
                    "failure_analysis": escalation.get("escalation_context", {}).get(
                        "failure_analysis", "Quality threshold not met after retries",
                    ),
                    "what_was_tried": escalation.get("escalation_context", {}).get(
                        "what_was_tried", "Guidance flow with human-provided guidance",
                    ),
                    "ticket_type": escalation.get("ticket_type", "unknown"),
                    "complexity": escalation.get("complexity", "unknown"),
                }
                pf_status, pf_result, pf_retries, pf_err, pf_dlq = (
                    await _push_permanent_failure_to_crm_with_retry(
                        tenant_id=tenant_id or escalation.get("tenant_id", ""),
                        ticket_id=escalation.get("original_ticket_id", escalation_id),
                        escalation_id=escalation_id,
                        crm_provider=crm_provider,
                        crm_ticket_id=crm_ticket_id,
                        attempts=attempt_count,
                        failure_context=failure_context,
                        max_retries=_settings.CRM_PUSH_MAX_RETRIES,
                        backoff_base=_settings.CRM_PUSH_BACKOFF_BASE_SECONDS,
                        backoff_max=_settings.CRM_PUSH_BACKOFF_MAX_SECONDS,
                        metrics_enabled=_settings.DELIVERY_METRICS_ENABLED,
                        dlq_on_failure=_settings.GUIDANCE_CRM_DLQ_ON_FAILURE,
                    )
                )
                crm_push = pf_result
                if pf_dlq:
                    crm_push["dlq_entry_id"] = pf_dlq
                    crm_push["manual_action_required"] = (
                        "CRM ticket must be manually reset to open/new"
                    )
                await VaultManager.update_crm_push_back(
                    escalation_id=escalation_id,
                    status="updated" if pf_status == "success" else "failed",
                    crm_response=crm_push,
                )
                # Vault stays in REPROCESS_EXHAUSTED (already set above) so
                # batch_guidance_tickets stops re-queuing this escalation.
                # CRM is now the source of truth — human agent will work it
                # from the CRM side as a fresh "open"/"new" ticket.
            except Exception as e:
                logger.error("Guidance Ticket: CRM permanent-failure push failed: %s", e)
                crm_push = {"success": False, "reason": str(e)}

        return {
            "success": passed,
            "escalation_id": escalation_id,
            "flow": "guidance_ticket",
            "reprocess_result": improved_response if passed else "",
            "reprocess_quality": round(guidance_quality, 4),
            "quality_passed": passed,
            "reprocess_attempts": attempt_count,
            "exhausted": is_exhausted,
            "error": None if passed else (
                "Quality threshold not met (exhausted)" if is_exhausted
                else f"Quality threshold not met (attempt {attempt_count}/{_max_retries})"
            ),
            "technique_log": logs,
            "crm_push": crm_push,
            "crm_ticket_id": crm_ticket_id,
            "elapsed_ms": elapsed,
        }

    finally:
        # Always clean up processing set
        with _guidance_lock:
            _processing_set.discard(escalation_id)


async def batch_guidance_tickets(
    tenant_id: str,
    guidance_map: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Batch-process guidance tickets for all eligible escalations.

    Eligible escalations are those with:
      - human_status == guidance_provided (already have guidance)
      - OR reprocess_status == failed (previous attempt failed)
      - AND reprocess_status != done (not already successfully processed)

    If guidance_map is provided, it maps escalation_id -> guidance text to use
    (overriding the stored guidance).

    Returns:
        {
            "tenant_id": "...",
            "total_eligible": 3,
            "total_processed": 2,
            "total_skipped": 1,
            "results": [...],
        }
    """
    from app.core.escalation_vault.vault_manager import VaultManager
    from app.core.escalation_vault.vault_db import (
        HUMAN_GUIDANCE_PROVIDED, REPROCESS_FAILED, REPROCESS_DONE,
        REPROCESS_EXHAUSTED,
    )

    results = []
    skipped = 0

    # Get all escalations for tenant
    all_escalations = await VaultManager.list_escalations(tenant_id, limit=200)

    for esc in all_escalations:
        esc_id = esc["escalation_id"]
        human_status = esc.get("human_status", "")
        reprocess_status = esc.get("reprocess_status", "")

        # Skip non-eligible
        is_guided = human_status == HUMAN_GUIDANCE_PROVIDED
        is_failed = reprocess_status == REPROCESS_FAILED
        is_done = reprocess_status == REPROCESS_DONE
        is_exhausted = reprocess_status == REPROCESS_EXHAUSTED  # BC-017

        # BC-017: EXHAUSTED is terminal — AI gave up, CRM has been reset
        # to open/new, human agent is handling it from the CRM side.
        # Never re-queue.
        if is_done or is_exhausted:
            skipped += 1
            continue
        if not (is_guided or is_failed):
            skipped += 1
            continue

        # Determine guidance to use
        guidance = ""
        if guidance_map and esc_id in guidance_map:
            guidance = guidance_map[esc_id]
        elif esc.get("human_guidance"):
            guidance = esc["human_guidance"]

        if not guidance or len(guidance) < MIN_GUIDANCE_LENGTH:
            skipped += 1
            results.append({
                "escalation_id": esc_id,
                "success": False,
                "reason": "insufficient_guidance",
            })
            continue

        result = await create_guidance_ticket(
            escalation_id=esc_id,
            guidance=guidance,
            tenant_id=tenant_id,
        )
        results.append(result)

    return {
        "tenant_id": tenant_id,
        "total_eligible": len(all_escalations),
        "total_processed": len(results),
        "total_skipped": skipped,
        "resolved": sum(1 for r in results if r.get("success")),
        "failed": sum(1 for r in results if not r.get("success")),
        "results": results,
    }


def reset_guidance_state():
    """Reset the processing set (for testing)."""
    global _processing_set
    with _guidance_lock:
        _processing_set = set()
