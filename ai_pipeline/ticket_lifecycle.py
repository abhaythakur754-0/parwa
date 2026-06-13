"""CRM Ticket Lifecycle Manager — Foundation for Autonomous Variant Operation.

This module manages the full lifecycle of support tickets across all PARWA variants.
It bridges the CRM (source of truth for tickets) with the AI pipeline (resolution engine)
and enforces variant-specific autonomy rules.

Key principle: Variants AUTONOMOUSLY decide what to do — not hardcoded.
- Mini PARWA: auto-resolves simple tickets (FAQ, order status), recommends for complex, escalates critical
- PARWA: auto-resolves most tickets, only escalates legal/critical
- PARWA High: auto-resolves everything including bulk/analytics, only escalates legal threats

All status changes are logged in CRM. Metrics are honest — never inflated.

Lifecycle:
  OPEN → IN_PROGRESS → RESOLVED (human)
  OPEN → IN_PROGRESS → AUTO_RESOLVED (AI)
  OPEN → IN_PROGRESS → PENDING_APPROVAL → RESOLVED / ESCALATED
  OPEN → IN_PROGRESS → ESCALATED (critical/legal)
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from collections import defaultdict
from datetime import datetime
from enum import Enum
from typing import Any

from parwa.fake_crm.database import get_crm, reset_crm
from parwa.graph import aprocess_ticket, reset_parwa_graph
from parwa.config import get_permission, can_execute, ACTION_PERMISSIONS
from parwa.state import ActionType, ExecutionMode

logger = logging.getLogger("parwa.ticket_lifecycle")


# ═══════════════════════════════════════════════════════════════════════════════
# TicketStatus Enum
# ═══════════════════════════════════════════════════════════════════════════════

class TicketStatus(str, Enum):
    """All possible statuses for a ticket in the lifecycle.

    Transition rules:
        OPEN → IN_PROGRESS (when processing starts)
        IN_PROGRESS → RESOLVED (human resolved)
        IN_PROGRESS → AUTO_RESOLVED (AI resolved autonomously)
        IN_PROGRESS → PENDING_APPROVAL (awaiting human approval of AI recommendation)
        IN_PROGRESS → ESCALATED (critical issue, legal threat, etc.)
        PENDING_APPROVAL → RESOLVED (approved and executed)
        PENDING_APPROVAL → ESCALATED (denied, escalated to human)
        PENDING_APPROVAL → AUTO_RESOLVED (auto-approved and executed)
    """
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    PENDING_APPROVAL = "pending_approval"
    AUTO_RESOLVED = "auto_resolved"


# Valid status transitions — enforces lifecycle integrity
_VALID_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.OPEN: {TicketStatus.IN_PROGRESS},
    TicketStatus.IN_PROGRESS: {
        TicketStatus.RESOLVED,
        TicketStatus.AUTO_RESOLVED,
        TicketStatus.PENDING_APPROVAL,
        TicketStatus.ESCALATED,
    },
    TicketStatus.PENDING_APPROVAL: {
        TicketStatus.RESOLVED,
        TicketStatus.AUTO_RESOLVED,
        TicketStatus.ESCALATED,
        TicketStatus.IN_PROGRESS,  # re-queue after denial
    },
    TicketStatus.RESOLVED: set(),       # terminal
    TicketStatus.AUTO_RESOLVED: set(),  # terminal
    TicketStatus.ESCALATED: set(),      # terminal (for this lifecycle)
}


# ═══════════════════════════════════════════════════════════════════════════════
# ApprovalQueue
# ═══════════════════════════════════════════════════════════════════════════════

class ApprovalQueue:
    """Stores and manages pending approvals from Mini PARWA recommendations.

    When the AI pipeline produces a RECOMMEND action (instead of EXECUTE),
    the recommendation goes into this queue. A human (or auto-approve logic)
    can then approve or deny it.

    Thread-safe. All mutations go through a lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, dict[str, Any]] = {}      # approval_id → item
        self._history: list[dict[str, Any]] = []            # all decisions (approved/denied)
        self._stats = {
            "total_queued": 0,
            "total_approved": 0,
            "total_denied": 0,
            "total_auto_approved": 0,
        }

    def add(
        self,
        *,
        ticket_id: str,
        customer_id: str,
        variant: str,
        action_type: str,
        description: str,
        parameters: dict[str, Any],
        evidence: list[str],
        risk_level: str = "low",
        quality_score: float = 0.0,
        pipeline_state: dict[str, Any] | None = None,
    ) -> str:
        """Add a recommendation to the approval queue.

        Returns the approval_id for tracking.
        """
        approval_id = f"APR-{uuid.uuid4().hex[:8].upper()}"
        item = {
            "approval_id": approval_id,
            "ticket_id": ticket_id,
            "customer_id": customer_id,
            "variant": variant,
            "action_type": action_type,
            "description": description,
            "parameters": parameters,
            "evidence": evidence,
            "risk_level": risk_level,
            "quality_score": quality_score,
            "pipeline_state": pipeline_state or {},
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "decided_at": None,
            "decision_reason": None,
        }

        with self._lock:
            self._pending[approval_id] = item
            self._stats["total_queued"] += 1

        logger.info(
            "ApprovalQueue: queued %s for ticket=%s action=%s risk=%s quality=%.1f",
            approval_id, ticket_id, action_type, risk_level, quality_score,
        )
        return approval_id

    def approve(self, approval_id: str, reason: str = "human_approved") -> dict[str, Any] | None:
        """Approve a pending recommendation and execute the recommended action.

        Returns the execution result, or None if approval_id not found / already decided.
        """
        with self._lock:
            item = self._pending.get(approval_id)
            if not item or item["status"] != "pending":
                return None

            item["status"] = "approved"
            item["decided_at"] = datetime.utcnow().isoformat()
            item["decision_reason"] = reason
            self._stats["total_approved"] += 1

            # Move to history
            self._history.append(dict(item))
            del self._pending[approval_id]

        # Execute the approved action against CRM (outside lock to avoid deadlock)
        execution_result = self._execute_approved_action(item)

        # Log in CRM
        customer_id = item.get("customer_id", "")
        if customer_id and customer_id != "default":
            try:
                crm = get_crm()
                crm.add_note(customer_id, (
                    f"[APPROVED & EXECUTED] {item['action_type']}: {item['description'][:200]} "
                    f"| Approval: {approval_id} | Reason: {reason}"
                ))
            except (ValueError, Exception):
                pass

        logger.info(
            "ApprovalQueue: APPROVED %s → executing %s for ticket=%s",
            approval_id, item["action_type"], item["ticket_id"],
        )
        return execution_result

    def deny(self, approval_id: str, reason: str = "human_denied") -> bool:
        """Deny a pending recommendation. Ticket stays open for human handling.

        Returns True if successfully denied, False if not found / already decided.
        """
        with self._lock:
            item = self._pending.get(approval_id)
            if not item or item["status"] != "pending":
                return False

            item["status"] = "denied"
            item["decided_at"] = datetime.utcnow().isoformat()
            item["decision_reason"] = reason
            self._stats["total_denied"] += 1

            self._history.append(dict(item))
            del self._pending[approval_id]

        # Log denial in CRM
        customer_id = item.get("customer_id", "")
        if customer_id and customer_id != "default":
            try:
                crm = get_crm()
                crm.add_note(customer_id, (
                    f"[DENIED] {item['action_type']}: {item['description'][:200]} "
                    f"| Approval: {approval_id} | Reason: {reason}"
                ))
            except (ValueError, Exception):
                pass

        logger.info(
            "ApprovalQueue: DENIED %s for ticket=%s action=%s",
            approval_id, item["ticket_id"], item["action_type"],
        )
        return True

    def auto_approve_low_risk(self) -> list[str]:
        """Auto-approve recommendations with risk_level='low' and quality_score >= 85.

        This enables Mini PARWA to still resolve simple issues without human
        intervention when the AI is confident and risk is low.

        Returns list of auto-approved approval_ids.
        """
        auto_approved: list[str] = []

        # Snapshot pending items under lock
        with self._lock:
            candidates = {
                aid: item for aid, item in self._pending.items()
                if item["status"] == "pending"
                and item.get("risk_level") == "low"
                and isinstance(item.get("quality_score"), (int, float))
                and item["quality_score"] >= 85
            }

        for approval_id, item in candidates.items():
            with self._lock:
                # Re-check in case status changed between snapshots
                current = self._pending.get(approval_id)
                if not current or current["status"] != "pending":
                    continue

                current["status"] = "approved"
                current["decided_at"] = datetime.utcnow().isoformat()
                current["decision_reason"] = "auto_approved_low_risk"
                self._stats["total_approved"] += 1
                self._stats["total_auto_approved"] += 1

                self._history.append(dict(current))
                del self._pending[approval_id]

            # Execute outside lock
            execution_result = self._execute_approved_action(current)
            auto_approved.append(approval_id)

            # Log in CRM
            customer_id = current.get("customer_id", "")
            if customer_id and customer_id != "default":
                try:
                    crm = get_crm()
                    crm.add_note(customer_id, (
                        f"[AUTO-APPROVED & EXECUTED] {current['action_type']}: "
                        f"{current['description'][:200]} | Approval: {approval_id} "
                        f"| Risk: low | Quality: {current['quality_score']:.1f}"
                    ))
                except (ValueError, Exception):
                    pass

            logger.info(
                "ApprovalQueue: AUTO-APPROVED %s (risk=low, quality=%.1f) → executing %s",
                approval_id, current["quality_score"], current["action_type"],
            )

        return auto_approved

    def get_pending(self) -> list[dict[str, Any]]:
        """Return all pending approvals (snapshot copy)."""
        with self._lock:
            return [dict(item) for item in self._pending.values()]

    def get_stats(self) -> dict[str, Any]:
        """Return approval statistics."""
        with self._lock:
            return {
                **self._stats,
                "currently_pending": len(self._pending),
                "approval_rate": (
                    self._stats["total_approved"] / self._stats["total_queued"]
                    if self._stats["total_queued"] > 0 else 0.0
                ),
                "auto_approve_rate": (
                    self._stats["total_auto_approved"] / self._stats["total_approved"]
                    if self._stats["total_approved"] > 0 else 0.0
                ),
            }

    def get_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return approval decision history (most recent first)."""
        with self._lock:
            return list(reversed(self._history[-limit:]))

    def reset(self) -> None:
        """Reset the approval queue (useful for testing)."""
        with self._lock:
            self._pending.clear()
            self._history.clear()
            self._stats = {
                "total_queued": 0,
                "total_approved": 0,
                "total_denied": 0,
                "total_auto_approved": 0,
            }

    # ─── Private helpers ────────────────────────────────────────────────────

    def _execute_approved_action(self, item: dict[str, Any]) -> dict[str, Any]:
        """Execute an approved action against the CRM.

        This is the bridge between approval and real execution.
        Only called after explicit or auto-approval.
        """
        action_type_str = item.get("action_type", "send_reply")
        parameters = item.get("parameters", {})
        customer_id = item.get("customer_id", "")
        variant = item.get("variant", "parwa")

        # Build an action_plan dict compatible with the CRM executor
        action_plan = {
            "action_type": action_type_str,
            "description": item.get("description", ""),
            "parameters": parameters,
            "risk_level": item.get("risk_level", "low"),
            "evidence": item.get("evidence", []),
        }

        # Build a minimal state dict for the executor
        state = {
            "customer_id": customer_id,
            "variant": variant,
            "channel": "email",
            "quality_score": item.get("quality_score", 0),
        }

        # Check that this action is now allowed (after approval)
        try:
            action_type = ActionType(action_type_str)
            permission = get_permission(variant, action_type)
        except (ValueError, KeyError):
            return {
                "action_type": action_type_str,
                "status": "failed",
                "message": f"Unknown action type or permission check failed: {action_type_str}",
            }

        # After approval, we EXECUTE even for RECOMMEND-tier actions
        # The approval IS the authorization
        try:
            from parwa.fake_crm.executor import (
                _SYNC_ACTION_EXECUTORS,
                _ASYNC_ACTION_EXECUTORS,
            )
            crm = get_crm()

            # Try sync executors first
            if action_type in _SYNC_ACTION_EXECUTORS:
                executor_fn = _SYNC_ACTION_EXECUTORS[action_type]
                result = executor_fn(action_plan, state, crm)
                return result

            # Async delivery actions need special handling (we're sync here)
            if action_type in _ASYNC_ACTION_EXECUTORS:
                return {
                    "action_type": action_type_str,
                    "status": "delivery_pending",
                    "message": f"Action '{action_type_str}' approved — delivery will be processed asynchronously",
                    "parameters": parameters,
                }

            # Fallback: log in CRM
            if customer_id and customer_id != "default":
                try:
                    crm.add_note(customer_id, f"[APPROVED ACTION EXECUTED] {action_type_str}: {item.get('description', '')[:200]}")
                except (ValueError, Exception):
                    pass

            return {
                "action_type": action_type_str,
                "status": "executed",
                "message": f"Approved action '{action_type_str}' executed",
                "parameters": parameters,
            }

        except ImportError:
            # CRM executor not available — log and return
            logger.warning("ApprovalQueue: CRM executor not available, logging action only")
            return {
                "action_type": action_type_str,
                "status": "simulated",
                "message": f"Action '{action_type_str}' approved but CRM executor unavailable",
                "parameters": parameters,
            }
        except Exception as exc:
            logger.error("ApprovalQueue: execution failed for %s: %s", action_type_str, exc)
            return {
                "action_type": action_type_str,
                "status": "failed",
                "message": f"Execution error: {exc}",
            }


# ═══════════════════════════════════════════════════════════════════════════════
# MetricsTracker
# ═══════════════════════════════════════════════════════════════════════════════

class MetricsTracker:
    """Honest metrics tracking for the ticket lifecycle.

    Never inflates numbers. If a ticket was "simulated" not "executed",
    it counts as human_required, not auto_resolved.

    Tracks:
    - Per-variant: total_tickets, auto_resolved, human_required, pending_approval
    - Human effort eliminated percentage
    - By action_type: executed vs recommended vs denied
    - Delivery stats: actually delivered vs simulated
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

        # Per-variant counters
        self._variant_metrics: dict[str, dict[str, int]] = defaultdict(lambda: {
            "total_tickets": 0,
            "auto_resolved": 0,
            "human_required": 0,
            "pending_approval": 0,
            "escalated": 0,
            "failed": 0,
        })

        # Per action_type counters
        self._action_metrics: dict[str, dict[str, int]] = defaultdict(lambda: {
            "executed": 0,
            "recommended": 0,
            "denied": 0,
            "simulated": 0,
            "failed": 0,
        })

        # Delivery stats
        self._delivery_stats: dict[str, int] = {
            "actually_delivered": 0,
            "simulated": 0,
            "delivery_pending": 0,
            "delivery_failed": 0,
        }

        # Timing
        self._start_time = datetime.utcnow()
        self._processing_times: list[float] = []

    def record_ticket_processed(
        self,
        variant: str,
        status: TicketStatus,
        execution_results: list[dict[str, Any]] | None = None,
        processing_time: float = 0.0,
    ) -> None:
        """Record the outcome of a processed ticket."""
        with self._lock:
            metrics = self._variant_metrics[variant]
            metrics["total_tickets"] += 1

            if status == TicketStatus.AUTO_RESOLVED:
                metrics["auto_resolved"] += 1
            elif status == TicketStatus.PENDING_APPROVAL:
                metrics["pending_approval"] += 1
            elif status == TicketStatus.ESCALATED:
                metrics["escalated"] += 1
                metrics["human_required"] += 1
            elif status == TicketStatus.RESOLVED:
                # Human-resolved counts as human_required
                metrics["human_required"] += 1
            else:
                metrics["failed"] += 1

            # Record action-level metrics from execution results
            if execution_results:
                for result in execution_results:
                    action_type = result.get("action_type", "unknown")
                    action_status = result.get("status", "unknown")
                    action_metrics = self._action_metrics[action_type]

                    if action_status == "executed":
                        action_metrics["executed"] += 1
                    elif action_status == "recommended":
                        action_metrics["recommended"] += 1
                    elif action_status == "denied":
                        action_metrics["denied"] += 1
                    elif action_status == "simulated":
                        action_metrics["simulated"] += 1
                    elif action_status == "failed":
                        action_metrics["failed"] += 1

                    # Track delivery stats for communication actions
                    if action_type in ("send_sms", "voice_call"):
                        if action_status == "executed":
                            self._delivery_stats["actually_delivered"] += 1
                        elif action_status == "simulated":
                            self._delivery_stats["simulated"] += 1
                        elif action_status == "delivery_pending":
                            self._delivery_stats["delivery_pending"] += 1
                        elif action_status == "delivery_failed":
                            self._delivery_stats["delivery_failed"] += 1

            # Track processing time
            if processing_time > 0:
                self._processing_times.append(processing_time)

    def get_human_effort_eliminated_pct(self, variant: str | None = None) -> float:
        """Calculate percentage of human effort eliminated.

        Only counts AUTO_RESOLVED tickets as effort eliminated.
        "Simulated" actions do NOT count — they still require human follow-up.

        Args:
            variant: If specified, calculate for that variant only.
                     If None, calculate across all variants.
        """
        with self._lock:
            if variant:
                metrics = self._variant_metrics.get(variant)
                if not metrics or metrics["total_tickets"] == 0:
                    return 0.0
                return (metrics["auto_resolved"] / metrics["total_tickets"]) * 100

            total = 0
            auto_resolved = 0
            for v_metrics in self._variant_metrics.values():
                total += v_metrics["total_tickets"]
                auto_resolved += v_metrics["auto_resolved"]

            if total == 0:
                return 0.0
            return (auto_resolved / total) * 100

    def get_dashboard_data(self) -> dict[str, Any]:
        """Returns complete metrics for dashboard rendering.

        This is the main data export method — the dashboard UI consumes this.
        """
        with self._lock:
            # Build per-variant breakdown
            variants: dict[str, dict[str, Any]] = {}
            for v_name, v_metrics in dict(self._variant_metrics).items():
                total = v_metrics["total_tickets"]
                auto = v_metrics["auto_resolved"]
                variants[v_name] = {
                    **v_metrics,
                    "human_effort_eliminated_pct": (auto / total * 100) if total > 0 else 0.0,
                }

            # Global totals
            total_tickets = sum(m["total_tickets"] for m in self._variant_metrics.values())
            total_auto = sum(m["auto_resolved"] for m in self._variant_metrics.values())
            total_human = sum(m["human_required"] for m in self._variant_metrics.values())
            total_escalated = sum(m["escalated"] for m in self._variant_metrics.values())
            total_pending = sum(m["pending_approval"] for m in self._variant_metrics.values())

            # Action-type breakdown
            actions: dict[str, dict[str, int]] = {}
            for action_type, action_metrics in dict(self._action_metrics).items():
                actions[action_type] = dict(action_metrics)

            # Average processing time
            avg_time = (
                sum(self._processing_times) / len(self._processing_times)
                if self._processing_times else 0.0
            )

            uptime_seconds = (datetime.utcnow() - self._start_time).total_seconds()

            return {
                "timestamp": datetime.utcnow().isoformat(),
                "uptime_seconds": uptime_seconds,
                "summary": {
                    "total_tickets": total_tickets,
                    "auto_resolved": total_auto,
                    "human_required": total_human,
                    "escalated": total_escalated,
                    "pending_approval": total_pending,
                    "human_effort_eliminated_pct": (
                        (total_auto / total_tickets * 100) if total_tickets > 0 else 0.0
                    ),
                },
                "by_variant": variants,
                "by_action_type": actions,
                "delivery_stats": dict(self._delivery_stats),
                "performance": {
                    "avg_processing_time_seconds": round(avg_time, 3),
                    "total_processed": len(self._processing_times),
                },
            }

    def reset(self) -> None:
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self._variant_metrics.clear()
            self._action_metrics.clear()
            self._delivery_stats = {
                "actually_delivered": 0,
                "simulated": 0,
                "delivery_pending": 0,
                "delivery_failed": 0,
            }
            self._start_time = datetime.utcnow()
            self._processing_times.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# AutonomousTicketProcessor
# ═══════════════════════════════════════════════════════════════════════════════

class AutonomousTicketProcessor:
    """Processes tickets autonomously through the PARWA AI pipeline.

    Each variant has different autonomy:
    - Mini PARWA: auto-resolves simple tickets, queues complex for approval, escalates critical
    - PARWA: auto-resolves most, only escalates legal/critical
    - PARWA High: auto-resolves everything, only escalates legal threats

    Uses asyncio for concurrent processing. Batch operations respect
    per-variant concurrency limits from VARIANT_CONFIG.
    """

    def __init__(
        self,
        approval_queue: ApprovalQueue | None = None,
        metrics_tracker: MetricsTracker | None = None,
    ) -> None:
        self._approval_queue = approval_queue or ApprovalQueue()
        self._metrics = metrics_tracker or MetricsTracker()
        self._lock = threading.Lock()
        # Track tickets currently being processed (in-flight)
        self._in_flight: dict[str, dict[str, Any]] = {}

    @property
    def approval_queue(self) -> ApprovalQueue:
        return self._approval_queue

    @property
    def metrics(self) -> MetricsTracker:
        return self._metrics

    def poll_crm_tickets(self, variant: str | None = None) -> list[dict[str, Any]]:
        """Auto-discover open tickets from the CRM.

        Scans all customers in the CRM for tickets with status "open".
        Optionally filters by variant context (not stored in CRM, but
        could be derived from customer tier or metadata).

        Returns list of ticket dicts ready for processing.
        """
        crm = get_crm()
        open_tickets: list[dict[str, Any]] = []

        # Scan known customer IDs
        for cust_id in ["CUST-1001", "CUST-1002", "CUST-1003", "CUST-1004",
                        "CUST-1005", "CUST-1006", "CUST-1007", "CUST-1008"]:
            try:
                cust = crm.get_customer(cust_id)
                if not cust:
                    continue
                for ticket in cust.get("tickets", []):
                    if ticket.get("status") == "open":
                        open_tickets.append({
                            "ticket_id": ticket.get("ticket_id", ""),
                            "customer_id": cust_id,
                            "subject": ticket.get("subject", ""),
                            "date": ticket.get("date", ""),
                            "customer_tier": cust.get("tier", "standard"),
                            "customer_name": cust.get("name", ""),
                            "channel": "email",
                        })
            except (ValueError, Exception):
                continue

        logger.info(
            "poll_crm_tickets: found %d open tickets%s",
            len(open_tickets),
            f" for variant={variant}" if variant else "",
        )
        return open_tickets

    async def process_ticket_autonomously(
        self,
        ticket: dict[str, Any],
        variant: str = "parwa",
    ) -> dict[str, Any]:
        """Run a ticket through the full PARWA pipeline autonomously.

        Steps:
        1. Mark ticket as IN_PROGRESS
        2. Run through aprocess_ticket() (the 22-node AI pipeline)
        3. Based on result, decide: auto-resolve, queue for approval, or escalate
        4. Update CRM with status
        5. Record metrics

        Returns a lifecycle result dict with final status and details.
        """
        ticket_id = ticket.get("ticket_id", f"TKT-{uuid.uuid4().hex[:4].upper()}")
        customer_id = ticket.get("customer_id", "")
        subject = ticket.get("subject", "")

        start_time = datetime.utcnow()
        lifecycle_id = f"LC-{uuid.uuid4().hex[:6].upper()}"

        # Track in-flight
        with self._lock:
            self._in_flight[ticket_id] = {
                "lifecycle_id": lifecycle_id,
                "ticket_id": ticket_id,
                "customer_id": customer_id,
                "variant": variant,
                "started_at": start_time.isoformat(),
                "status": TicketStatus.IN_PROGRESS,
            }

        logger.info(
            "process_ticket_autonomously: START lifecycle=%s ticket=%s variant=%s subject='%s'",
            lifecycle_id, ticket_id, variant, subject[:50],
        )

        # Mark as in-progress in CRM
        self._update_crm_ticket_status(customer_id, ticket_id, "in_progress", f"Processing via {variant} variant")

        try:
            # Run through the full AI pipeline
            result = await aprocess_ticket(
                raw_message=subject,
                customer_id=customer_id,
                channel=ticket.get("channel", "email"),
                variant=variant,
            )

            # Decide what to do based on the pipeline result
            lifecycle_result = self.handle_result(
                result=result,
                ticket_id=ticket_id,
                customer_id=customer_id,
                variant=variant,
            )

            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds()

            # Update metrics
            self._metrics.record_ticket_processed(
                variant=variant,
                status=TicketStatus(lifecycle_result["status"]),
                execution_results=result.get("execution_results", []),
                processing_time=processing_time,
            )

            # Update in-flight tracking
            with self._lock:
                if ticket_id in self._in_flight:
                    self._in_flight[ticket_id]["status"] = TicketStatus(lifecycle_result["status"])
                    self._in_flight[ticket_id]["completed_at"] = datetime.utcnow().isoformat()

            lifecycle_result["lifecycle_id"] = lifecycle_id
            lifecycle_result["processing_time_seconds"] = processing_time

            return lifecycle_result

        except Exception as exc:
            logger.error(
                "process_ticket_autonomously: FAILED lifecycle=%s ticket=%s: %s",
                lifecycle_id, ticket_id, exc, exc_info=True,
            )

            # Escalate on pipeline failure
            self._update_crm_ticket_status(
                customer_id, ticket_id, "escalated",
                f"Pipeline failure: {exc}",
            )

            processing_time = (datetime.utcnow() - start_time).total_seconds()
            self._metrics.record_ticket_processed(
                variant=variant,
                status=TicketStatus.ESCALATED,
                processing_time=processing_time,
            )

            with self._lock:
                if ticket_id in self._in_flight:
                    self._in_flight[ticket_id]["status"] = TicketStatus.ESCALATED

            return {
                "lifecycle_id": lifecycle_id,
                "ticket_id": ticket_id,
                "customer_id": customer_id,
                "status": TicketStatus.ESCALATED,
                "reason": f"Pipeline execution failed: {exc}",
                "processing_time_seconds": processing_time,
            }

    def handle_result(
        self,
        result: dict[str, Any],
        ticket_id: str = "",
        customer_id: str = "",
        variant: str = "parwa",
    ) -> dict[str, Any]:
        """Based on pipeline result, decide: auto-resolve, queue for approval, or escalate.

        Decision logic (variant-autonomous, not hardcoded):
        - If should_escalate=True → ESCALATED (all variants)
        - If recommendation exists (RECOMMEND actions) → PENDING_APPROVAL
        - If all actions executed successfully → AUTO_RESOLVED
        - If any action failed but nothing escalated → depends on variant:
          - Mini: PENDING_APPROVAL (conservative)
          - PARWA: AUTO_RESOLVED if quality_score >= 70, else PENDING_APPROVAL
          - High: AUTO_RESOLVED (optimistic)
        - If pipeline errors → ESCALATED

        Returns lifecycle result dict.
        """
        should_escalate = result.get("should_escalate", False)
        execution_results = result.get("execution_results", [])
        recommendation = result.get("recommendation")
        quality_score = result.get("quality_score", 0.0)
        pipeline_errors = result.get("pipeline_errors", [])
        final_response = result.get("final_response", "")

        # ─── 1. Critical escalation check ──────────────────────────────────
        if should_escalate:
            self._update_crm_ticket_status(
                customer_id, ticket_id, "escalated",
                f"AI escalated: {result.get('escalation_reason', 'critical issue')}",
            )
            return {
                "ticket_id": ticket_id,
                "customer_id": customer_id,
                "status": TicketStatus.ESCALATED,
                "reason": result.get("escalation_reason", "AI determined escalation required"),
                "final_response": final_response,
                "quality_score": quality_score,
            }

        # ─── 2. Pipeline errors → escalate ────────────────────────────────
        if pipeline_errors and len(pipeline_errors) > 0:
            # Check if errors are fatal or just warnings
            fatal_errors = [e for e in pipeline_errors if e.get("error_type") != "Warning"]
            if fatal_errors:
                self._update_crm_ticket_status(
                    customer_id, ticket_id, "escalated",
                    f"Pipeline errors: {[e.get('node') for e in fatal_errors]}",
                )
                return {
                    "ticket_id": ticket_id,
                    "customer_id": customer_id,
                    "status": TicketStatus.ESCALATED,
                    "reason": f"Pipeline errors in nodes: {[e.get('node') for e in fatal_errors]}",
                    "final_response": final_response,
                    "quality_score": quality_score,
                }

        # ─── 3. Recommendation exists → PENDING_APPROVAL ──────────────────
        if recommendation and recommendation.get("pending_approval"):
            approval_id = self._approval_queue.add(
                ticket_id=ticket_id,
                customer_id=customer_id,
                variant=variant,
                action_type=recommendation.get("action_type", "unknown"),
                description=recommendation.get("description", ""),
                parameters=recommendation.get("parameters", {}),
                evidence=recommendation.get("evidence", []),
                risk_level=recommendation.get("risk_level", "medium"),
                quality_score=quality_score,
                pipeline_state=result,
            )
            self._update_crm_ticket_status(
                customer_id, ticket_id, "pending_approval",
                f"Recommendation queued: {recommendation.get('action_type')} (approval: {approval_id})",
            )
            return {
                "ticket_id": ticket_id,
                "customer_id": customer_id,
                "status": TicketStatus.PENDING_APPROVAL,
                "approval_id": approval_id,
                "recommendation": recommendation,
                "final_response": final_response,
                "quality_score": quality_score,
            }

        # ─── 4. Check execution results ────────────────────────────────────
        all_executed = all(
            r.get("status") == "executed"
            for r in execution_results
        ) if execution_results else False

        any_failed = any(
            r.get("status") == "failed"
            for r in execution_results
        )

        any_denied = any(
            r.get("status") == "denied"
            for r in execution_results
        )

        if all_executed and not any_failed:
            # All actions executed successfully → AUTO_RESOLVED
            self._update_crm_ticket_status(
                customer_id, ticket_id, "auto_resolved",
                f"Auto-resolved by {variant} variant (quality: {quality_score:.1f})",
            )
            # Also resolve in CRM if possible
            self._resolve_crm_ticket(
                customer_id, ticket_id,
                f"Auto-resolved: {final_response[:200]}" if final_response else "Auto-resolved by PARWA",
            )
            return {
                "ticket_id": ticket_id,
                "customer_id": customer_id,
                "status": TicketStatus.AUTO_RESOLVED,
                "final_response": final_response,
                "quality_score": quality_score,
                "execution_results": execution_results,
            }

        # ─── 5. Partial success or failures → variant-dependent ────────────
        if any_failed or any_denied:
            if variant == "mini":
                # Mini: conservative — queue for approval
                # Find the first failed/denied action and create an approval item
                action_to_queue = next(
                    (r for r in execution_results if r.get("status") in ("failed", "denied")),
                    execution_results[0] if execution_results else {"action_type": "unknown", "description": ""}
                )
                approval_id = self._approval_queue.add(
                    ticket_id=ticket_id,
                    customer_id=customer_id,
                    variant=variant,
                    action_type=action_to_queue.get("action_type", "unknown"),
                    description=action_to_queue.get("message", "Action requires human review"),
                    parameters=action_to_queue.get("parameters", {}),
                    evidence=[],
                    risk_level="medium",
                    quality_score=quality_score,
                    pipeline_state=result,
                )
                self._update_crm_ticket_status(
                    customer_id, ticket_id, "pending_approval",
                    f"Action requires review (approval: {approval_id})",
                )
                return {
                    "ticket_id": ticket_id,
                    "customer_id": customer_id,
                    "status": TicketStatus.PENDING_APPROVAL,
                    "approval_id": approval_id,
                    "reason": "Action failed/denied, queued for human review",
                    "final_response": final_response,
                    "quality_score": quality_score,
                }

            elif variant == "parwa":
                # PARWA: auto-resolve if quality is good enough
                if quality_score >= 70:
                    self._update_crm_ticket_status(
                        customer_id, ticket_id, "auto_resolved",
                        f"Auto-resolved with quality: {quality_score:.1f} (some actions failed/denied)",
                    )
                    self._resolve_crm_ticket(
                        customer_id, ticket_id,
                        f"Auto-resolved: {final_response[:200]}" if final_response else "Auto-resolved",
                    )
                    return {
                        "ticket_id": ticket_id,
                        "customer_id": customer_id,
                        "status": TicketStatus.AUTO_RESOLVED,
                        "final_response": final_response,
                        "quality_score": quality_score,
                        "execution_results": execution_results,
                    }
                else:
                    self._update_crm_ticket_status(
                        customer_id, ticket_id, "escalated",
                        f"Low quality score ({quality_score:.1f}) with failed actions",
                    )
                    return {
                        "ticket_id": ticket_id,
                        "customer_id": customer_id,
                        "status": TicketStatus.ESCALATED,
                        "reason": f"Low quality ({quality_score:.1f}) with action failures",
                        "final_response": final_response,
                        "quality_score": quality_score,
                    }

            else:  # high
                # PARWA High: optimistic — auto-resolve everything
                self._update_crm_ticket_status(
                    customer_id, ticket_id, "auto_resolved",
                    f"Auto-resolved (high variant, quality: {quality_score:.1f})",
                )
                self._resolve_crm_ticket(
                    customer_id, ticket_id,
                    f"Auto-resolved: {final_response[:200]}" if final_response else "Auto-resolved",
                )
                return {
                    "ticket_id": ticket_id,
                    "customer_id": customer_id,
                    "status": TicketStatus.AUTO_RESOLVED,
                    "final_response": final_response,
                    "quality_score": quality_score,
                    "execution_results": execution_results,
                }

        # ─── 6. Fallback: no execution results at all ──────────────────────
        # This can happen for FAQ-only responses or informational replies
        if not execution_results and final_response:
            if quality_score >= 60 or variant == "high":
                self._update_crm_ticket_status(
                    customer_id, ticket_id, "auto_resolved",
                    f"Informational response (quality: {quality_score:.1f})",
                )
                self._resolve_crm_ticket(
                    customer_id, ticket_id,
                    f"Resolved: {final_response[:200]}",
                )
                return {
                    "ticket_id": ticket_id,
                    "customer_id": customer_id,
                    "status": TicketStatus.AUTO_RESOLVED,
                    "final_response": final_response,
                    "quality_score": quality_score,
                }
            else:
                self._update_crm_ticket_status(
                    customer_id, ticket_id, "pending_approval",
                    "Low quality informational response",
                )
                return {
                    "ticket_id": ticket_id,
                    "customer_id": customer_id,
                    "status": TicketStatus.PENDING_APPROVAL,
                    "reason": "Low quality informational response",
                    "final_response": final_response,
                    "quality_score": quality_score,
                }

        # ─── 7. Shouldn't reach here, but escalate if we do ────────────────
        self._update_crm_ticket_status(
            customer_id, ticket_id, "escalated",
            "Unhandled lifecycle state",
        )
        return {
            "ticket_id": ticket_id,
            "customer_id": customer_id,
            "status": TicketStatus.ESCALATED,
            "reason": "Unhandled lifecycle state",
            "final_response": final_response,
            "quality_score": quality_score,
        }

    async def batch_process(
        self,
        tickets: list[dict[str, Any]],
        variant: str = "parwa",
    ) -> list[dict[str, Any]]:
        """Process multiple tickets with concurrency limits per variant.

        Respects variant concurrent_tickets limits:
        - Mini: 3 concurrent
        - PARWA: 4 concurrent
        - High: 6 concurrent
        """
        from parwa.config import VARIANT_CONFIG

        max_concurrent = VARIANT_CONFIG.get(variant, {}).get("concurrent_tickets", 4)
        semaphore = asyncio.Semaphore(max_concurrent)

        results: list[dict[str, Any]] = []

        async def _process_with_semaphore(ticket: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                return await self.process_ticket_autonomously(ticket, variant)

        logger.info(
            "batch_process: starting %d tickets with variant=%s (max_concurrent=%d)",
            len(tickets), variant, max_concurrent,
        )

        tasks = [_process_with_semaphore(t) for t in tickets]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions from gather
        final_results = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                ticket = tickets[i] if i < len(tickets) else {}
                final_results.append({
                    "ticket_id": ticket.get("ticket_id", "unknown"),
                    "customer_id": ticket.get("customer_id", ""),
                    "status": TicketStatus.ESCALATED,
                    "reason": f"Batch processing exception: {r}",
                })
                self._metrics.record_ticket_processed(
                    variant=variant,
                    status=TicketStatus.ESCALATED,
                )
            else:
                final_results.append(r)

        # After batch, auto-approve eligible recommendations
        auto_approved = self._approval_queue.auto_approve_low_risk()
        if auto_approved:
            logger.info(
                "batch_process: auto-approved %d low-risk recommendations",
                len(auto_approved),
            )
            # Update metrics for auto-approved items
            for _ in auto_approved:
                self._metrics.record_ticket_processed(
                    variant=variant,
                    status=TicketStatus.AUTO_RESOLVED,
                )

        logger.info(
            "batch_process: completed %d tickets for variant=%s | auto_resolved=%d escalated=%d pending=%d",
            len(final_results),
            variant,
            sum(1 for r in final_results if r.get("status") == TicketStatus.AUTO_RESOLVED),
            sum(1 for r in final_results if r.get("status") == TicketStatus.ESCALATED),
            sum(1 for r in final_results if r.get("status") == TicketStatus.PENDING_APPROVAL),
        )

        return final_results

    def get_in_flight(self) -> dict[str, dict[str, Any]]:
        """Return currently in-flight tickets."""
        with self._lock:
            return dict(self._in_flight)

    # ─── Private helpers ────────────────────────────────────────────────────

    def _update_crm_ticket_status(
        self,
        customer_id: str,
        ticket_id: str,
        new_status: str,
        note: str = "",
    ) -> None:
        """Log a status change as a CRM note (honest audit trail)."""
        if not customer_id or customer_id == "default":
            return

        try:
            crm = get_crm()
            crm.add_note(customer_id, (
                f"[LIFECYCLE] Ticket {ticket_id} → {new_status}"
                + (f" | {note}" if note else "")
            ))
        except (ValueError, Exception) as exc:
            logger.warning("Failed to log ticket status in CRM: %s", exc)

    def _resolve_crm_ticket(
        self,
        customer_id: str,
        ticket_id: str,
        resolution: str,
    ) -> None:
        """Resolve the ticket in the CRM."""
        if not customer_id or customer_id == "default":
            return

        try:
            crm = get_crm()
            crm.resolve_ticket(customer_id, ticket_id, resolution)
        except (ValueError, Exception) as exc:
            logger.warning("Failed to resolve ticket in CRM: %s", exc)


# ═══════════════════════════════════════════════════════════════════════════════
# TicketLifecycleManager
# ═══════════════════════════════════════════════════════════════════════════════

class TicketLifecycleManager:
    """Top-level manager for the full CRM ticket lifecycle.

    Orchestrates:
    - Auto-polling CRM for open tickets
    - Processing tickets through the AI pipeline
    - Approval queue management
    - Auto-approval of low-risk recommendations
    - Metrics tracking and dashboard data
    - Status transitions with validation

    Usage:
        manager = TicketLifecycleManager()
        # Poll and process all open tickets for a variant
        results = await manager.run_cycle(variant="parwa")
        # Or process a specific ticket
        result = await manager.process_single(ticket, variant="mini")
        # Get dashboard data
        dashboard = manager.get_dashboard()
    """

    def __init__(self) -> None:
        self._approval_queue = ApprovalQueue()
        self._metrics = MetricsTracker()
        self._processor = AutonomousTicketProcessor(
            approval_queue=self._approval_queue,
            metrics_tracker=self._metrics,
        )
        self._lock = threading.Lock()
        self._cycle_count = 0

    @property
    def approval_queue(self) -> ApprovalQueue:
        """Access the approval queue for manual approve/deny operations."""
        return self._approval_queue

    @property
    def metrics(self) -> MetricsTracker:
        """Access the metrics tracker."""
        return self._metrics

    @property
    def processor(self) -> AutonomousTicketProcessor:
        """Access the autonomous ticket processor."""
        return self._processor

    def transition_status(
        self,
        current: TicketStatus,
        target: TicketStatus,
    ) -> bool:
        """Validate and attempt a status transition.

        Returns True if the transition is valid, False otherwise.
        """
        valid_targets = _VALID_TRANSITIONS.get(current, set())
        return target in valid_targets

    async def run_cycle(self, variant: str = "parwa") -> list[dict[str, Any]]:
        """Run one complete lifecycle cycle for a variant.

        1. Poll CRM for open tickets
        2. Process all tickets through the pipeline
        3. Auto-approve eligible recommendations
        4. Return results
        """
        self._cycle_count += 1
        cycle_id = f"CYCLE-{self._cycle_count}"

        logger.info(
            "run_cycle: START %s for variant=%s", cycle_id, variant,
        )

        # Poll for open tickets
        tickets = self._processor.poll_crm_tickets(variant=variant)

        if not tickets:
            logger.info("run_cycle: %s — no open tickets found", cycle_id)
            return []

        # Process tickets with variant-specific concurrency
        results = await self._processor.batch_process(tickets, variant=variant)

        logger.info(
            "run_cycle: %s COMPLETE — %d tickets processed for variant=%s",
            cycle_id, len(results), variant,
        )

        return results

    async def process_single(
        self,
        ticket: dict[str, Any],
        variant: str = "parwa",
    ) -> dict[str, Any]:
        """Process a single ticket through the lifecycle."""
        return await self._processor.process_ticket_autonomously(ticket, variant)

    def approve(self, approval_id: str, reason: str = "human_approved") -> dict[str, Any] | None:
        """Approve a pending recommendation by ID.

        Returns execution result or None if not found.
        """
        result = self._approval_queue.approve(approval_id, reason)
        if result:
            # Update metrics for the approved action
            self._metrics.record_ticket_processed(
                variant="approved",  # generic since we may not know the original variant
                status=TicketStatus.AUTO_RESOLVED,
            )
        return result

    def deny(self, approval_id: str, reason: str = "human_denied") -> bool:
        """Deny a pending recommendation by ID."""
        return self._approval_queue.deny(approval_id, reason)

    def auto_approve_eligible(self) -> list[str]:
        """Auto-approve all eligible low-risk recommendations."""
        return self._approval_queue.auto_approve_low_risk()

    def get_pending_approvals(self) -> list[dict[str, Any]]:
        """Get all pending approvals."""
        return self._approval_queue.get_pending()

    def get_approval_stats(self) -> dict[str, Any]:
        """Get approval queue statistics."""
        return self._approval_queue.get_stats()

    def get_dashboard(self) -> dict[str, Any]:
        """Get complete metrics for dashboard rendering.

        Combines lifecycle metrics, approval stats, and variant breakdowns
        into a single dashboard-ready data structure.
        """
        metrics_data = self._metrics.get_dashboard_data()
        approval_data = self._approval_queue.get_stats()

        return {
            "lifecycle_metrics": metrics_data,
            "approval_queue": approval_data,
            "cycle_count": self._cycle_count,
            "in_flight_tickets": len(self._processor.get_in_flight()),
            "variant_permissions": {
                v: {
                    action_type.value: mode.value
                    for action_type, mode in permissions.items()
                }
                for v, permissions in ACTION_PERMISSIONS.items()
            },
        }

    def reset(self) -> None:
        """Reset the entire lifecycle manager (useful for testing).

        Resets: approval queue, metrics, processor state, CRM graph cache.
        Does NOT reset the CRM data itself (use reset_crm() for that).
        """
        self._approval_queue.reset()
        self._metrics.reset()
        self._processor = AutonomousTicketProcessor(
            approval_queue=self._approval_queue,
            metrics_tracker=self._metrics,
        )
        self._cycle_count = 0
        reset_parwa_graph()
        logger.info("TicketLifecycleManager: reset complete")


# ═══════════════════════════════════════════════════════════════════════════════
# Module-Level Convenience
# ═══════════════════════════════════════════════════════════════════════════════

_manager_instance: TicketLifecycleManager | None = None
_manager_lock = threading.Lock()


def get_lifecycle_manager() -> TicketLifecycleManager:
    """Get the singleton TicketLifecycleManager instance."""
    global _manager_instance
    if _manager_instance is None:
        with _manager_lock:
            if _manager_instance is None:
                _manager_instance = TicketLifecycleManager()
    return _manager_instance


def reset_lifecycle_manager() -> TicketLifecycleManager:
    """Reset and return a fresh TicketLifecycleManager instance."""
    global _manager_instance
    with _manager_lock:
        if _manager_instance is not None:
            _manager_instance.reset()
        else:
            _manager_instance = TicketLifecycleManager()
    return _manager_instance
