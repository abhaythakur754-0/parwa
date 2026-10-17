"""Phase 2 — Learn from CRM history (admin-triggered backfill).

The tenant's CRM already knows how past problems were solved. This
service pulls batches of RESOLVED tickets from the CRM (read-only),
distills each into a (question → resolution) pattern, and writes it to
the AI Wiki (Section A) — the exact store Node 1/3/7 and Node 3.5
already recall via find_similar_patterns. From then on the agent
answers that ticket type from memory; CoVe still verifies before
anything reaches a customer.

Design constraints (512MB Render plan):
  - Retrieval-augmented memory, NOT model training: one wiki row per
    resolution, no embeddings infra, no local models.
  - Batch of 50–100 per run, cursor-paginated: the admin presses the
    button again ("Import next batch") until history is exhausted.
  - Dedupe: the wiki entry key is a deterministic hash of the question
    text — already-learned tickets are skipped on every re-run.
  - Guardrails: only solved/closed tickets are fetched; the state
    machine allows nothing else into the wiki from this path.

Job state lives on the CRM Integration row's `settings` JSON under the
"history_backfill" key — restart-safe without a new table, and scoped
to the tenant automatically.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("parwa.services.crm_backfill")

STATE_KEY = "history_backfill"
DEFAULT_BATCH_SIZE = 50
MAX_BATCH_SIZE = 100
# A "running" state older than this is a dead job (process restart) — allow a new run.
STALE_RUNNING_MINUTES = 10

# Single-process Render backend: an in-memory guard stops double-clicks.
# Cross-restart safety comes from the staleness window on the persisted state.
_running: Dict[str, float] = {}


def get_backfill_state(db, company_id: str) -> Dict[str, Any]:
    """Read the persisted backfill state (for the status endpoint/UI)."""
    provider, integration = _find_crm_integration(db, company_id)
    if not integration:
        return {"supported": False, "provider": None, "state": None,
                "reason": "no_crm_integration"}
    if provider == "generic":
        return {"supported": False, "provider": provider, "state": None,
                "reason": "webhook_only_crm_no_read_api"}
    state = _read_state(integration)
    return {"supported": True, "provider": provider, "state": state,
            "reason": None}


def run_backfill_batch(
    db,
    company_id: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> Dict[str, Any]:
    """Fetch one batch of resolved CRM tickets and learn each into the wiki.

    Called from the admin endpoint (background task opens its OWN session —
    the request's session closes when the response returns).

    Returns a summary dict: {status, fetched, learned, duplicates_skipped,
    has_more, provider, error}.
    """
    import time as _time

    now = datetime.now(timezone.utc)

    # ── Concurrency guard ────────────────────────────────────────────
    started_at = _running.get(company_id)
    if started_at and (_time.time() - started_at) < STALE_RUNNING_MINUTES * 60:
        return {"status": "already_running", "provider": None, "fetched": 0,
                "learned": 0, "duplicates_skipped": 0, "has_more": False,
                "error": None}
    _running[company_id] = _time.time()

    try:
        provider, integration = _find_crm_integration(db, company_id)
        if not integration:
            return _summary("no_crm_integration", provider, 0, 0, 0, False,
                            "no CRM integration connected")
        if provider == "generic":
            return _summary("unsupported", provider, 0, 0, 0, False,
                            "webhook-only CRM has no read API — connect Zendesk or HubSpot")

        state = _read_state(integration)
        if state.get("status") == "running":
            try:
                last = datetime.fromisoformat(str(state.get("last_run_at")))
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                if now - last < timedelta(minutes=STALE_RUNNING_MINUTES):
                    return _summary("already_running", provider, 0, 0, 0, False, None)
            except (TypeError, ValueError):
                pass  # unreadable timestamp — treat as not running

        # ── Fetch one batch from the CRM ─────────────────────────────
        from app.core.crm_bridge.crm_bridge import CRMBridge
        from app.services.integration_service import IntegrationService

        size = max(1, min(int(batch_size or DEFAULT_BATCH_SIZE), MAX_BATCH_SIZE))
        config = IntegrationService(db).get_credential_config(company_id, provider) or {}
        result = _run_async(
            CRMBridge.fetch_resolved_tickets(
                provider=provider, limit=size,
                cursor=state.get("cursor"), config=config,
            )
        )
        if not result.get("success"):
            _write_state(db, integration, _merge_state(state, {
                "status": "error",
                "error": str(result.get("error", "fetch_failed"))[:300],
                "last_run_at": now.isoformat(),
            }))
            return _summary("error", provider, 0, 0, 0, False,
                            str(result.get("error", "fetch_failed"))[:300])

        tickets = result.get("tickets", []) or []
        learned, skipped = _learn_tickets(db, company_id, tickets)
        has_more = bool(result.get("next_cursor"))

        _write_state(db, integration, _merge_state(state, {
            "status": "done" if has_more else "complete",
            "provider": provider,
            "cursor": result.get("next_cursor"),
            "batches_done": int(state.get("batches_done", 0) or 0) + 1,
            "tickets_fetched": int(state.get("tickets_fetched", 0) or 0) + len(tickets),
            "patterns_learned": int(state.get("patterns_learned", 0) or 0) + learned,
            "duplicates_skipped": int(state.get("duplicates_skipped", 0) or 0) + skipped,
            "last_run_at": now.isoformat(),
            "error": None,
        }))

        logger.info(
            "crm_history_backfill_batch company=%s provider=%s fetched=%d "
            "learned=%d skipped=%d has_more=%s",
            str(company_id)[:8], provider, len(tickets), learned, skipped, has_more,
        )
        return _summary("done" if has_more else "complete", provider,
                        len(tickets), learned, skipped, has_more, None)
    except Exception as exc:  # noqa: BLE001 — never crash the caller
        logger.error("crm_history_backfill_failed company=%s err=%s",
                     str(company_id)[:8], str(exc)[:200])
        return _summary("error", None, 0, 0, 0, False, str(exc)[:300])
    finally:
        _running.pop(company_id, None)


def _learn_tickets(db, company_id: str, tickets: list) -> tuple:
    """Distill each fetched CRM ticket into a wiki pattern (with dedupe)."""
    from database.models.ai_pipeline import AIWikiEntry
    from app.core.parwa_pipeline.ai_wiki_store import (
        get_wiki_store,
        ticket_pattern_entry_key,
    )

    store = get_wiki_store()
    learned = 0
    skipped = 0
    for t in tickets:
        try:
            subject = str(t.get("subject", "") or "").strip()
            description = str(t.get("description", "") or "").strip()
            resolution = str(t.get("resolution_text", "") or "").strip()
            crm_id = str(t.get("crm_ticket_id", "") or "")

            # A ticket needs a question side; a missing resolution still
            # teaches what the request LOOKED like, but a completely empty
            # record teaches nothing.
            if not (subject or description) or not crm_id:
                skipped += 1
                continue

            query_text = f"{subject} {description}".strip()[:1000]
            ticket_type = str(t.get("ticket_type", "") or "").strip() or "general"

            # Dedupe: deterministic key — skip tickets already learned.
            entry_key = ticket_pattern_entry_key(ticket_type, query_text)
            exists = (
                db.query(AIWikiEntry.id)
                .filter(
                    AIWikiEntry.company_id == company_id,
                    AIWikiEntry.section == "A",
                    AIWikiEntry.entry_key == entry_key,
                )
                .first()
            )
            if exists:
                skipped += 1
                continue

            entry = store.write_ticket_pattern(
                tenant_id=company_id,
                ticket_type=ticket_type,
                query=query_text,
                complexity="medium",
                techniques_used=["CRM_History_Backfill", "CRM_Learning"],
                quality_score=0.8,  # team-verified history, not live-verified
                answer_summary=(resolution or description)[:500],
                tier="parwa",
            )
            if entry:
                learned += 1
            else:
                skipped += 1
        except Exception as exc:  # noqa: BLE001 — one bad row never stops the batch
            logger.warning("crm_backfill_row_failed crm_ticket=%s err=%s",
                           str(t.get("crm_ticket_id", ""))[:16], str(exc)[:150])
            skipped += 1
    return learned, skipped


def _find_crm_integration(db, company_id: str):
    """Find the tenant's active CRM integration (same order as dispatcher)."""
    from database.models.integration import Integration

    for provider in ("hubspot", "zendesk", "generic"):
        row = (
            db.query(Integration)
            .filter(
                Integration.company_id == company_id,
                Integration.integration_type == provider,
                Integration.status == "active",
            )
            .order_by(Integration.updated_at.desc())
            .first()
        )
        if row:
            return provider, row
    return None, None


def _read_state(integration) -> Dict[str, Any]:
    import json

    try:
        settings = json.loads(integration.settings or "{}")
        if isinstance(settings, dict):
            state = settings.get(STATE_KEY)
            if isinstance(state, dict):
                return state
    except (json.JSONDecodeError, TypeError):
        pass
    return {}


def _merge_state(old: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(old)
    merged.update(update)
    return merged


def _write_state(db, integration, state: Dict[str, Any]) -> None:
    """Persist state onto the CRM Integration row (merge, never clobber)."""
    import json

    try:
        settings: Dict[str, Any] = {}
        try:
            raw = json.loads(integration.settings or "{}")
            if isinstance(raw, dict):
                settings = raw
        except (json.JSONDecodeError, TypeError):
            settings = {}
        settings[STATE_KEY] = state
        integration.settings = json.dumps(settings)
        integration.updated_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:  # noqa: BLE001 — state is best-effort
        logger.warning("crm_backfill_state_write_failed err=%s", str(exc)[:150])
        db.rollback()


def _summary(status: str, provider, fetched, learned, skipped, has_more, error) -> Dict[str, Any]:
    return {
        "status": status,
        "provider": provider,
        "fetched": fetched,
        "learned": learned,
        "duplicates_skipped": skipped,
        "has_more": has_more,
        "error": error,
    }


def _run_async(coro):
    """Run a coroutine from sync code (same convention as pipeline_dispatcher)."""
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result(timeout=120)
    return asyncio.run(coro)
