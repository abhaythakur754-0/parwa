"""
Escalation → Owner Notification Bridge.

Conveys variant escalation asks to the owner through the standard
notification system (in-app bell + email). This closes the loop the
product is built around:

    Variant (AI employee) cannot resolve
      → structured ask lands on the ticket + Escalation Vault
      → OWNER IS TOLD (in-app notification + email)

Jarvis is the in-product layer that conveys messages from the variants
to the owner — this module is the escalation leg of that path.

BC-008: never raise — a notification failure must never break the
escalation flow itself. Best-effort by design.
BC-012: all timestamps UTC.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger("parwa.escalation_notify")

# Idempotence marker written into ticket.metadata_json after a
# successful dispatch so repeated pipeline events for the same
# escalation never spam the owner.
METADATA_KEY = "owner_notified_at"


def _load_metadata(ticket: Any) -> Dict[str, Any]:
    """Parse ticket.metadata_json defensively (BC-008)."""
    raw = getattr(ticket, "metadata_json", None)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _write_metadata(ticket: Any, metadata: Dict[str, Any]) -> None:
    """Persist metadata back on the ticket (caller commits)."""
    try:
        ticket.metadata_json = json.dumps(metadata)
    except Exception:  # noqa: BLE001 — best-effort, never raise
        logger.debug("escalation_notify metadata_write_failed")


def build_owner_summary(
    metadata: Dict[str, Any],
    reason: str = "",
    extra_summary: str = "",
) -> tuple:
    """Human-readable summary from the structured ask.

    Returns (summary_text, escalation_reason).
    """
    ask = metadata.get("escalation_ask") or {}
    if not isinstance(ask, dict):
        ask = {}

    problem = str(ask.get("problem") or reason or "AI could not resolve this ticket")
    needed = str(ask.get("needed_from_team") or "")
    after = str(ask.get("after_that") or "")

    parts = [f"Problem: {problem}"]
    if needed:
        parts.append(f"Needed from team: {needed}")
    if after:
        parts.append(f"After that: {after}")
    if extra_summary:
        parts.append(str(extra_summary)[:300])

    escalation_reason = (
        reason
        or str(ask.get("escalation_type") or "")
        or str(metadata.get("escalation_reason") or "")
        or "escalation"
    )
    return "\n".join(parts), escalation_reason


def notify_owner_of_escalation(
    db: Any,
    ticket: Any,
    reason: str = "",
    extra_summary: str = "",
) -> Dict[str, Any]:
    """Dispatch ONE owner notification for a ticket's escalation ask.

    Idempotent per ticket: once metadata_json[owner_notified_at] is set,
    later calls are no-ops. Uses the standard NotificationService human
    queue (channels: email + in_app) so the ask lands in the owner's
    notification bell and inbox.

    Returns {"dispatched": bool, "detail": str} — never raises.
    """
    try:
        ticket_id = str(getattr(ticket, "id", "") or "")
        company_id = str(getattr(ticket, "company_id", "") or "")
        if not ticket_id or not company_id:
            return {"dispatched": False, "detail": "missing ticket identity"}

        metadata = _load_metadata(ticket)
        if metadata.get(METADATA_KEY):
            return {"dispatched": False, "detail": "already notified"}

        summary, escalation_reason = build_owner_summary(
            metadata, reason=reason, extra_summary=extra_summary,
        )

        # Lazy import: keeps this module light and avoids import cycles.
        from app.services.notification_service import NotificationService

        service = NotificationService(db, company_id)
        result = service.notify_human_queue(
            ticket_id=ticket_id,
            summary=summary,
            escalation_reason=escalation_reason,
        ) or {}

        dispatched = bool(result.get("success"))
        detail = str(result.get("error") or "ok")

        if dispatched:
            metadata[METADATA_KEY] = datetime.now(timezone.utc).isoformat()
            _write_metadata(ticket, metadata)

        logger.info(
            "escalation_owner_notify ticket=%s dispatched=%s detail=%s",
            ticket_id[:8], dispatched, detail[:120],
        )
        return {"dispatched": dispatched, "detail": detail}

    except Exception as exc:  # noqa: BLE001 — BC-008: never break escalation
        logger.warning("escalation_owner_notify_failed: %s", str(exc)[:200])
        return {"dispatched": False, "detail": str(exc)[:200]}
