"""
Jarvis Storage Backend — Dual Mode

Modes:
  1. InMemory (default) — zero deps, works immediately for dev/testing
  2. Supabase (production) — uses httpx → Supabase REST API (PostgREST)

Auto-detection: if SUPABASE_URL + SUPABASE_ANON_KEY env vars are set → Supabase.
Otherwise → InMemory.

No new dependencies required. Uses only httpx (already installed).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("jarvis.db")

# ── Config ────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

# Table name prefix — all Jarvis tables start with jarvis_
TABLE_NOTIFICATIONS = "jarvis_notifications"
TABLE_FLAGS = "jarvis_system_flags"
TABLE_AUDIT = "jarvis_audit_trail"
TABLE_QUALITY_SCORES = "jarvis_quality_scores"
TABLE_QUALITY_ALERTS = "jarvis_quality_alerts"
TABLE_TRAINING_SUGGESTIONS = "jarvis_training_suggestions"
TABLE_AGENT_CONFIGS = "jarvis_agent_configs"
TABLE_CLIENT_SKILLS = "jarvis_client_skills"
TABLE_FEATURE_FLAGS = "jarvis_feature_flags"
TABLE_CLIENT_LEGAL = "jarvis_client_legal"
TABLE_PROVISIONING_LOGS = "jarvis_provisioning_logs"
TABLE_TRAINING_DATA = "jarvis_training_data"
TABLE_BATCH_QUEUE = "jarvis_batch_queue"
TABLE_INBOX = "jarvis_inbox"

# Priority constants
PRIORITY_CRITICAL = "CRITICAL"
PRIORITY_HIGH = "HIGH"
PRIORITY_MEDIUM = "MEDIUM"
PRIORITY_LOW = "LOW"

PRIORITY_THRESHOLDS = {
    PRIORITY_CRITICAL: 0.85,
    PRIORITY_HIGH: 0.65,
    PRIORITY_MEDIUM: 0.40,
}

# Notification types
TYPE_STUCK_TICKET = "stuck_ticket"
TYPE_QUOTA_LOW = "quota_low"
TYPE_INTEGRATION_DOWN = "integration_down"
TYPE_ACCURACY_DROP = "accuracy_drop"
TYPE_POLICY_CHANGE = "policy_change"
TYPE_SLA_RISK = "sla_risk"

# Roles that can execute admin commands
ADMIN_ROLES = {"admin", "owner", "supervisor"}
ALL_ROLES = {"admin", "owner", "supervisor", "team_member", "viewer"}


# ═══════════════════════════════════════════════════════════════
# ABSTRACT BASE
# ═══════════════════════════════════════════════════════════════

class StorageBackend(ABC):
    """Abstract storage backend. All methods are async."""

    # ── Notifications ────────────────────────────────────────

    @abstractmethod
    async def create_notification(
        self,
        tenant_id: str,
        ntype: str,
        priority_score: float,
        title: str,
        description: str,
        related_tickets: Optional[List[str]] = None,
        batch_key: Optional[str] = None,
        source_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Create a notification. Returns the full notification dict."""
        ...

    @abstractmethod
    async def get_notification(self, key: str) -> Optional[Dict[str, Any]]:
        """Get notification by key (PARWA-NFY-XXX)."""
        ...

    @abstractmethod
    async def get_notifications(
        self,
        tenant_id: str,
        include_resolved: bool = False,
        min_priority: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get notifications for tenant, sorted by priority."""
        ...

    @abstractmethod
    async def resolve_notification(self, key: str) -> bool:
        """Mark notification as resolved."""
        ...

    @abstractmethod
    async def dismiss_notification(self, key: str) -> bool:
        """Mark notification as read."""
        ...

    # ── System Flags ─────────────────────────────────────────

    @abstractmethod
    async def set_flag(
        self,
        tenant_id: str,
        flag_type: str,
        flag_value: str,
        set_by: str,
        scope: str = "global",
        target_id: Optional[str] = None,
        reason: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set a system flag. Returns the flag dict."""
        ...

    @abstractmethod
    async def get_active_flags(
        self, tenant_id: str, flag_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get active (non-revoked, non-expired) flags."""
        ...

    @abstractmethod
    async def revoke_flag(self, flag_id: str, revoked_by: str) -> bool:
        """Revoke a system flag."""
        ...

    # ── Audit Trail ──────────────────────────────────────────

    @abstractmethod
    async def create_audit_entry(
        self,
        tenant_id: str,
        action: str,
        actor_email: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        payload: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Create an audit trail entry (immutable)."""
        ...

    @abstractmethod
    async def get_audit_trail(
        self,
        tenant_id: str,
        action: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get audit trail for tenant."""
        ...

    # ── Quality Scores ───────────────────────────────────────

    @abstractmethod
    async def write_quality_score(
        self,
        tenant_id: str,
        ticket_id: str,
        overall_score: float,
        confidence_score: Optional[float] = None,
        resolution_path: Optional[str] = None,
        nodes_reached: Optional[List[str]] = None,
        llm_calls: int = 0,
        tokens_used: int = 0,
        model_used: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Write a quality score (from PARWA Node 6)."""
        ...

    @abstractmethod
    async def get_quality_stats(
        self, tenant_id: str, days: int = 7
    ) -> Dict[str, Any]:
        """Get aggregated quality stats for a tenant."""
        ...

    # ── Batch Queue ──────────────────────────────────────────

    @abstractmethod
    async def add_to_batch(
        self,
        tenant_id: str,
        batch_key: str,
        ticket_id: str,
        confidence: float,
    ) -> Optional[Dict[str, Any]]:
        """Add ticket to batch. Returns batch if window expired, else None."""
        ...

    @abstractmethod
    async def flush_batches(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Force-flush all pending batches."""
        ...

    # ── Integration Health (Wave 2) ─────────────────────────

    @abstractmethod
    async def write_integration_ping(
        self,
        tenant_id: str,
        service_name: str,
        is_healthy: bool,
        response_ms: Optional[float] = None,
        error_detail: Optional[str] = None,
        status_code: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Record an integration health ping."""
        ...

    @abstractmethod
    async def get_integration_health(self, tenant_id: str) -> Dict[str, Any]:
        """Get current integration health summary (uptime, last error, etc.)."""
        ...

    # ── LLM Cost Tracking (Wave 2) ───────────────────────────

    @abstractmethod
    async def record_llm_cost(
        self,
        tenant_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        call_type: str = "parwa_pipeline",
    ) -> Dict[str, Any]:
        """Record a single LLM call's cost."""
        ...

    @abstractmethod
    async def get_llm_cost_summary(
        self, tenant_id: str, days: int = 7
    ) -> Dict[str, Any]:
        """Get aggregated LLM cost stats for a tenant."""
        ...

    # ── Stuck Ticket Tracking (Wave 2) ───────────────────────

    @abstractmethod
    async def record_stuck_ticket_check(
        self,
        tenant_id: str,
        ticket_id: str,
        stuck_reason: str,
        hours_stuck: float,
        escalation_tier: str,
    ) -> Dict[str, Any]:
        """Record a stuck ticket detection event."""
        ...

    @abstractmethod
    async def get_stuck_tickets(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get all currently tracked stuck tickets."""
        ...

    # ── Drift Detection (Wave 2) ─────────────────────────────

    @abstractmethod
    async def check_quality_drift(
        self, tenant_id: str,
    ) -> Dict[str, Any]:
        """Analyze quality scores for drift.

        Returns: {drift_detected, drift_severity, accuracy_7d, accuracy_yesterday,
                  accuracy_today, trend_direction, trigger_reason}
        """
        ...

    # ── Ticket Flow Aggregation (Wave 2) ─────────────────────

    @abstractmethod
    async def get_ticket_flow_summary(
        self, tenant_id: str, hours: int = 24
    ) -> Dict[str, Any]:
        """Get aggregated ticket flow metrics.

        Returns: {total, auto_resolved, batched, escalated, by_type, by_node, avg_llm_calls}
        """
        ...

    # ── Load Balancing (Wave 2) ──────────────────────────────

    @abstractmethod
    async def get_load_status(self, tenant_id: str) -> Dict[str, Any]:
        """Get current load/concurrency status per variant.

        Returns: {variants: [{name, concurrent, max_concurrent, utilization_pct, status}]}
        """
        ...

    # ── Agent Config Management (Wave 3) ─────────────────

    @abstractmethod
    async def get_agent_config(
        self, tenant_id: str, agent_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get agent config by name."""
        ...

    @abstractmethod
    async def update_agent_config(
        self, tenant_id: str, agent_name: str, **updates
    ) -> Optional[Dict[str, Any]]:
        """Update agent config fields (skills, max_concurrent, etc.)."""
        ...

    # ── Outbox Queue (Wave 3 — recall/void) ────────────────

    @abstractmethod
    async def add_to_outbox(
        self,
        tenant_id: str,
        channel: str,
        recipient: str,
        subject: str,
        body: str,
        message_type: str = "email",
        related_ticket: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a message to the outbox queue."""
        ...

    @abstractmethod
    async def recall_outbox_messages(
        self, tenant_id: str, match_filter: Optional[str] = None
    ) -> int:
        """Mark pending outbox messages as recalled. Returns count."""
        ...

    @abstractmethod
    async def void_outbox_messages(
        self, tenant_id: str, match_filter: Optional[str] = None
    ) -> int:
        """Remove pending outbox messages. Returns count removed."""
        ...

    @abstractmethod
    async def get_outbox_status(
        self, tenant_id: str
    ) -> Dict[str, Any]:
        """Get outbox queue status (pending, sent, recalled, voided counts)."""
        ...


    # ── Jarvis Inbox (Wave 4 — PARWA → Jarvis) ──────────

    @abstractmethod
    async def write_to_inbox(
        self,
        tenant_id: str,
        ticket_id: str,
        stuck_reason: str,
        quality_score: float,
        what_was_tried: str,
        inbox_type: str = "parwa_stuck",
    ) -> Dict[str, Any]:
        """PARWA writes to Jarvis inbox when it needs help."""
        ...

    @abstractmethod
    async def get_inbox_messages(
        self, tenant_id: str, include_resolved: bool = False
    ) -> List[Dict[str, Any]]:
        """Get inbox messages for Jarvis to process."""
        ...

    @abstractmethod
    async def resolve_inbox_message(self, message_id: str) -> bool:
        """Mark inbox message as resolved."""
        ...

    # ── Training Data Collection (Wave 4) ────────────────

    @abstractmethod
    async def record_training_data(
        self,
        tenant_id: str,
        ticket_id: str,
        signal_type: str,  # "approved", "rejected", "edited"
        original_response: str = "",
        corrected_response: str = "",
        quality_score: float = 0.0,
        ticket_type: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record training data from human approval/rejection/edit."""
        ...
    # ── Utility ──────────────────────────────────────────────

    @abstractmethod
    async def get_notification_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get notification counts by priority and type."""
        ...

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check if the storage backend is healthy."""
        ...


# ═══════════════════════════════════════════════════════════════
# IN-MEMORY BACKEND (works immediately, no deps)
# ═══════════════════════════════════════════════════════════════

class InMemoryBackend(StorageBackend):
    """In-memory storage. Data lost on restart. Perfect for dev/testing."""

    def __init__(self):
        self._notifications: Dict[str, Dict] = {}
        self._flags: List[Dict] = []
        self._audit: List[Dict] = []
        self._quality_scores: List[Dict] = []
        self._batches: Dict[str, List[Dict]] = {}
        self._batch_metas: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        self._next_nfy_id = 1
        # Wave 2 stores
        self._integration_pings: List[Dict] = []
        self._llm_costs: List[Dict] = []
        self._stuck_ticket_events: List[Dict] = []
        self._load_status: Dict[str, Dict] = {}  # tenant_id -> {variant -> {concurrent, max_concurrent}}
        self._agent_configs: List[Dict] = []  # Wave 3: agent config store
        self._outbox: List[Dict] = []  # Wave 3: outbox queue (recall/void)
        self._inbox: List[Dict] = []  # Wave 4: PARWA → Jarvis inbox
        self._training_data_records: List[Dict] = []  # Wave 4: training data

    # ── Helpers ───────────────────────────────────────────────

    def _next_notification_number(self) -> int:
        with self._lock:
            n = self._next_nfy_id
            self._next_nfy_id += 1
            return n

    @staticmethod
    def _priority_from_score(score: float) -> str:
        if score >= PRIORITY_THRESHOLDS[PRIORITY_CRITICAL]:
            return PRIORITY_CRITICAL
        elif score >= PRIORITY_THRESHOLDS[PRIORITY_HIGH]:
            return PRIORITY_HIGH
        elif score >= PRIORITY_THRESHOLDS[PRIORITY_MEDIUM]:
            return PRIORITY_MEDIUM
        return PRIORITY_LOW

    # ── Notifications ────────────────────────────────────────

    async def create_notification(
        self,
        tenant_id: str,
        ntype: str,
        priority_score: float,
        title: str,
        description: str,
        related_tickets: Optional[List[str]] = None,
        batch_key: Optional[str] = None,
        source_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        num = self._next_notification_number()
        key = f"PARWA-NFY-{num:03d}"
        now = time.time()
        nf = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "notification_key": key,
            "type": ntype,
            "priority": self._priority_from_score(priority_score),
            "priority_score": round(priority_score, 4),
            "title": title,
            "description": description,
            "related_tickets": related_tickets or [],
            "batch_key": batch_key,
            "source_data": source_data or {},
            "is_read": False,
            "is_resolved": False,
            "created_at": now,
            "resolved_at": None,
            "backend": "memory",
        }
        self._notifications[key] = nf
        logger.info("NFY created: %s type=%s score=%.3f [%s]", key, ntype, priority_score, tenant_id)
        return nf

    async def get_notification(self, key: str) -> Optional[Dict[str, Any]]:
        return self._notifications.get(key)

    async def get_notifications(
        self,
        tenant_id: str,
        include_resolved: bool = False,
        min_priority: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        priority_order = {PRIORITY_CRITICAL: 0, PRIORITY_HIGH: 1, PRIORITY_MEDIUM: 2, PRIORITY_LOW: 3}
        min_rank = priority_order.get(min_priority, 99) if min_priority else 99
        results = []
        for n in self._notifications.values():
            if n["tenant_id"] != tenant_id:
                continue
            if not include_resolved and n["is_resolved"]:
                continue
            if priority_order.get(n["priority"], 99) > min_rank:
                continue
            results.append(n)
        results.sort(key=lambda x: (-priority_order.get(x["priority"], 99), -x["created_at"]))
        return results

    async def resolve_notification(self, key: str) -> bool:
        n = self._notifications.get(key)
        if n and not n["is_resolved"]:
            n["is_resolved"] = True
            n["resolved_at"] = time.time()
            return True
        return False

    async def dismiss_notification(self, key: str) -> bool:
        n = self._notifications.get(key)
        if n:
            n["is_read"] = True
            return True
        return False

    # ── System Flags ─────────────────────────────────────────

    async def set_flag(
        self,
        tenant_id: str,
        flag_type: str,
        flag_value: str,
        set_by: str,
        scope: str = "global",
        target_id: Optional[str] = None,
        reason: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        flag = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "flag_type": flag_type,
            "flag_value": flag_value,
            "scope": scope,
            "target_id": target_id,
            "set_by": set_by,
            "reason": reason,
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "revoked_at": None,
            "backend": "memory",
        }
        self._flags.append(flag)
        logger.info("FLAG set: %s=%s scope=%s [%s]", flag_type, flag_value, scope, tenant_id)
        return flag

    async def get_active_flags(
        self, tenant_id: str, flag_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        now = datetime.now(timezone.utc)
        active = []
        for f in self._flags:
            if f["tenant_id"] != tenant_id:
                continue
            if f["revoked_at"] is not None:
                continue
            if f["expires_at"]:
                exp = datetime.fromisoformat(f["expires_at"]) if isinstance(f["expires_at"], str) else f["expires_at"]
                if exp < now:
                    continue
            if flag_type and f["flag_type"] != flag_type:
                continue
            active.append(f)
        return active

    async def revoke_flag(self, flag_id: str, revoked_by: str) -> bool:
        for f in self._flags:
            if f["id"] == flag_id and f["revoked_at"] is None:
                f["revoked_at"] = datetime.now(timezone.utc).isoformat()
                logger.info("FLAG revoked: %s by %s", flag_id, revoked_by)
                return True
        return False

    # ── Audit Trail ──────────────────────────────────────────

    async def create_audit_entry(
        self,
        tenant_id: str,
        action: str,
        actor_email: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        payload: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        payload_json = json.dumps(payload or {}, sort_keys=True)
        current_hash = hashlib.sha256(
            f"{tenant_id}:{action}:{payload_json}:{time.time()}".encode()
        ).hexdigest()[:64]

        entry = {
            "id": len(self._audit) + 1,
            "tenant_id": tenant_id,
            "action": action,
            "actor_email": actor_email,
            "target_type": target_type,
            "target_id": target_id,
            "payload": payload or {},
            "current_hash": current_hash,
            "previous_hash": self._audit[-1]["current_hash"] if self._audit else None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "backend": "memory",
        }
        self._audit.append(entry)
        return entry

    async def get_audit_trail(
        self,
        tenant_id: str,
        action: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        results = [e for e in self._audit if e["tenant_id"] == tenant_id]
        if action:
            results = [e for e in results if e["action"] == action]
        results.sort(key=lambda x: x["id"], reverse=True)
        return results[:limit]

    # ── Quality Scores ───────────────────────────────────────

    async def write_quality_score(
        self,
        tenant_id: str,
        ticket_id: str,
        overall_score: float,
        confidence_score: Optional[float] = None,
        resolution_path: Optional[str] = None,
        nodes_reached: Optional[List[str]] = None,
        llm_calls: int = 0,
        tokens_used: int = 0,
        model_used: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        score = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "ticket_id": ticket_id,
            "overall_score": round(overall_score, 2),
            "confidence_score": round(confidence_score, 2) if confidence_score else None,
            "resolution_path": resolution_path,
            "nodes_reached": nodes_reached or [],
            "llm_calls": llm_calls,
            "tokens_used": tokens_used,
            "model_used": model_used,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "backend": "memory",
        }
        self._quality_scores.append(score)
        return score

    async def get_quality_stats(self, tenant_id: str, days: int = 7) -> Dict[str, Any]:
        tenant_scores = [s for s in self._quality_scores if s["tenant_id"] == tenant_id]
        total = len(tenant_scores)
        if total == 0:
            return {
                "tenant_id": tenant_id, "total_tickets": 0,
                "avg_quality": 0, "avg_confidence": 0,
                "auto_resolved": 0, "escalated": 0, "stuck": 0,
            }
        avg_q = sum(s["overall_score"] for s in tenant_scores) / total
        avg_c_vals = [s["confidence_score"] for s in tenant_scores if s.get("confidence_score")]
        avg_c = sum(avg_c_vals) / len(avg_c_vals) if avg_c_vals else 0
        paths = {}
        for s in tenant_scores:
            p = s.get("resolution_path", "unknown")
            paths[p] = paths.get(p, 0) + 1
        return {
            "tenant_id": tenant_id,
            "total_tickets": total,
            "avg_quality": round(avg_q, 4),
            "avg_confidence": round(avg_c, 4),
            "by_path": paths,
            "auto_resolved": paths.get("simple", 0) + paths.get("complex", 0),
            "escalated": paths.get("escalated", 0),
            "stuck": paths.get("stuck", 0),
        }

    # ── Batch Queue ──────────────────────────────────────────

    async def add_to_batch(
        self,
        tenant_id: str,
        batch_key: str,
        ticket_id: str,
        confidence: float,
    ) -> Optional[Dict[str, Any]]:
        BATCH_WINDOW_S = 300
        now = time.time()

        if tenant_id not in self._batch_metas:
            self._batch_metas[tenant_id] = {}

        # Find existing batch with same key within window
        existing_key = None
        for bk, meta in self._batch_metas[tenant_id].items():
            if bk == batch_key and (now - meta["batch_start"]) < BATCH_WINDOW_S:
                existing_key = bk
                break

        if existing_key:
            meta = self._batch_metas[tenant_id][existing_key]
            meta["ticket_ids"].append(ticket_id)
            meta["signal_count"] = len(meta["ticket_ids"])
            meta["confidence_min"] = min(meta.get("confidence_min", 1.0), confidence)
            meta["confidence_max"] = max(meta.get("confidence_max", 0.0), confidence)
            # Don't flush yet — still within window
            return None
        else:
            meta = {
                "batch_key": batch_key,
                "tenant_id": tenant_id,
                "batch_start": now,
                "ticket_ids": [ticket_id],
                "signal_count": 1,
                "confidence_min": confidence,
                "confidence_max": confidence,
                "status": "pending",
            }
            self._batch_metas[tenant_id][batch_key] = meta
            return None

    async def flush_batches(self, tenant_id: str) -> List[Dict[str, Any]]:
        results = list(self._batch_metas.get(tenant_id, {}).values())
        self._batch_metas[tenant_id] = {}
        return results

    # ── Jarvis Inbox (Wave 4) ─────────────────────────────

    async def write_to_inbox(
        self,
        tenant_id: str,
        ticket_id: str,
        stuck_reason: str,
        quality_score: float,
        what_was_tried: str,
        inbox_type: str = "parwa_stuck",
    ) -> Dict[str, Any]:
        msg = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "ticket_id": ticket_id,
            "stuck_reason": stuck_reason,
            "quality_score": round(quality_score, 4),
            "what_was_tried": what_was_tried[:1000],
            "inbox_type": inbox_type,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "resolved_at": None,
            "jarvis_response": None,
        }
        self._inbox.append(msg)
        return msg

    async def get_inbox_messages(
        self, tenant_id: str, include_resolved: bool = False
    ) -> List[Dict[str, Any]]:
        msgs = [m for m in self._inbox if m["tenant_id"] == tenant_id]
        if not include_resolved:
            msgs = [m for m in msgs if m["status"] == "pending"]
        return sorted(msgs, key=lambda m: m["created_at"], reverse=True)

    async def resolve_inbox_message(self, message_id: str) -> bool:
        for m in self._inbox:
            if m["id"] == message_id and m["status"] == "pending":
                m["status"] = "resolved"
                m["resolved_at"] = datetime.now(timezone.utc).isoformat()
                return True
        return False

    # ── Training Data (Wave 4) ─────────────────────────────

    async def record_training_data(
        self,
        tenant_id: str,
        ticket_id: str,
        signal_type: str,
        original_response: str = "",
        corrected_response: str = "",
        quality_score: float = 0.0,
        ticket_type: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        record = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "ticket_id": ticket_id,
            "signal_type": signal_type,
            "original_response": original_response[:2000],
            "corrected_response": corrected_response[:2000],
            "quality_score": round(quality_score, 4),
            "ticket_type": ticket_type,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._training_data_records.append(record)
        return record

    async def get_training_data(
        self, tenant_id: str, signal_type: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        records = [r for r in self._training_data_records if r["tenant_id"] == tenant_id]
        if signal_type:
            records = [r for r in records if r["signal_type"] == signal_type]
        return sorted(records, key=lambda r: r["created_at"], reverse=True)[:limit]

    # ── Utility ──────────────────────────────────────────────

    async def get_notification_stats(self, tenant_id: str) -> Dict[str, Any]:
        tenant_nfs = [n for n in self._notifications.values() if n["tenant_id"] == tenant_id]
        by_priority = {}
        for p in [PRIORITY_CRITICAL, PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW]:
            by_priority[p] = sum(1 for n in tenant_nfs if n["priority"] == p)
        return {
            "total": len(tenant_nfs),
            "unread": sum(1 for n in tenant_nfs if not n["is_read"]),
            "unresolved": sum(1 for n in tenant_nfs if not n["is_resolved"]),
            "by_priority": by_priority,
        }

    async def health_check(self) -> Dict[str, Any]:
        return {
            "backend": "memory",
            "status": "healthy",
            "notifications": len(self._notifications),
            "flags": len(self._flags),
            "audit_entries": len(self._audit),
            "quality_scores": len(self._quality_scores),
        }

    # ── Integration Health (Wave 2) ─────────────────────────

    async def write_integration_ping(
        self, tenant_id, service_name, is_healthy,
        response_ms=None, error_detail=None, status_code=None,
    ) -> Dict[str, Any]:
        ping = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "service_name": service_name,
            "is_healthy": is_healthy,
            "response_ms": response_ms,
            "error_detail": error_detail,
            "status_code": status_code,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "backend": "memory",
        }
        self._integration_pings.append(ping)
        return ping

    async def get_integration_health(self, tenant_id: str) -> Dict[str, Any]:
        """Compute health from recent pings (last 30 per service)."""
        tenant_pings = [p for p in self._integration_pings if p["tenant_id"] == tenant_id]
        services: Dict[str, List[Dict]] = {}
        for p in tenant_pings:
            services.setdefault(p["service_name"], []).append(p)

        result = {"services": {}, "degraded_count": 0, "healthy_count": 0}
        for svc, pings in services.items():
            recent = pings[-30:]  # last 30 pings
            if not recent:
                continue
            healthy = sum(1 for p in recent if p["is_healthy"])
            total = len(recent)
            uptime_pct = round(healthy / max(total, 1) * 100, 1)
            last_ping = recent[-1]
            avg_ms = (sum(p["response_ms"] or 0 for p in recent) / total) if total else 0
            last_error = None
            last_error_time = None
            for p in reversed(recent):
                if not p["is_healthy"]:
                    last_error = p.get("error_detail")
                    last_error_time = p["created_at"]
                    break

            status = "healthy" if uptime_pct >= 90 else ("degraded" if uptime_pct >= 50 else "down")
            if status != "healthy":
                result["degraded_count"] += 1
            else:
                result["healthy_count"] += 1

            result["services"][svc] = {
                "status": status,
                "uptime_pct": uptime_pct,
                "total_pings": total,
                "healthy_pings": healthy,
                "avg_response_ms": round(avg_ms, 1),
                "last_ping_at": last_ping["created_at"],
                "last_healthy_at": next(
                    (p["created_at"] for p in reversed(recent) if p["is_healthy"]),
                    None,
                ),
                "last_error": last_error,
                "last_error_at": last_error_time,
                "last_status_code": last_ping.get("status_code"),
            }
        return result

    # ── LLM Cost Tracking (Wave 2) ───────────────────────────

    async def record_llm_cost(
        self, tenant_id, model, prompt_tokens, completion_tokens,
        cost_usd, call_type="parwa_pipeline",
    ) -> Dict[str, Any]:
        entry = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cost_usd": round(cost_usd, 6),
            "call_type": call_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "backend": "memory",
        }
        self._llm_costs.append(entry)
        return entry

    async def get_llm_cost_summary(self, tenant_id: str, days: int = 7) -> Dict[str, Any]:
        tenant_costs = [c for c in self._llm_costs if c["tenant_id"] == tenant_id]
        if not tenant_costs:
            return {
                "tenant_id": tenant_id, "total_cost_usd": 0.0,
                "total_tokens": 0, "total_calls": 0,
                "by_model": {}, "by_type": {},
                "daily_breakdown": [],
            }
        total_cost = sum(c["cost_usd"] for c in tenant_costs)
        total_tokens = sum(c["total_tokens"] for c in tenant_costs)
        total_calls = len(tenant_costs)
        by_model: Dict[str, Dict] = {}
        by_type: Dict[str, Dict] = {}
        for c in tenant_costs:
            m = c["model"]
            by_model.setdefault(m, {"cost": 0.0, "tokens": 0, "calls": 0})
            by_model[m]["cost"] += c["cost_usd"]
            by_model[m]["tokens"] += c["total_tokens"]
            by_model[m]["calls"] += 1
            t = c["call_type"]
            by_type.setdefault(t, {"cost": 0.0, "tokens": 0, "calls": 0})
            by_type[t]["cost"] += c["cost_usd"]
            by_type[t]["tokens"] += c["total_tokens"]
            by_type[t]["calls"] += 1
        return {
            "tenant_id": tenant_id,
            "total_cost_usd": round(total_cost, 4),
            "total_tokens": total_tokens,
            "total_calls": total_calls,
            "by_model": by_model,
            "by_type": by_type,
        }

    # ── Stuck Ticket Tracking (Wave 2) ───────────────────────

    async def record_stuck_ticket_check(
        self, tenant_id, ticket_id, stuck_reason, hours_stuck, escalation_tier,
    ) -> Dict[str, Any]:
        event = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "ticket_id": ticket_id,
            "stuck_reason": stuck_reason,
            "hours_stuck": round(hours_stuck, 2),
            "escalation_tier": escalation_tier,
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "resolved": False,
            "backend": "memory",
        }
        self._stuck_ticket_events.append(event)
        return event

    async def get_stuck_tickets(self, tenant_id: str) -> List[Dict[str, Any]]:
        return [
            e for e in self._stuck_ticket_events
            if e["tenant_id"] == tenant_id and not e["resolved"]
        ]

    # ── Drift Detection (Wave 2) ─────────────────────────────

    async def check_quality_drift(self, tenant_id: str) -> Dict[str, Any]:
        """Analyze quality_scores for drift using day-over-day comparison."""
        tenant_scores = [s for s in self._quality_scores if s["tenant_id"] == tenant_id]
        if len(tenant_scores) < 3:
            return {
                "tenant_id": tenant_id, "drift_detected": False,
                "drift_severity": "none", "accuracy_7d": None,
                "accuracy_yesterday": None, "accuracy_today": None,
                "trend_direction": "stable", "trigger_reason": "insufficient_data",
                "total_scores": len(tenant_scores),
            }
        # Group by date (ISO date portion)
        by_date: Dict[str, List[float]] = {}
        for s in tenant_scores:
            date_str = s["created_at"][:10]  # YYYY-MM-DD
            by_date.setdefault(date_str, []).append(s["overall_score"])

        dates_sorted = sorted(by_date.keys())

        def _avg(scores: List[float]) -> float:
            return round(sum(scores) / len(scores), 4) if scores else 0.0

        accuracy_7d = _avg([s for d in dates_sorted[-7:] for s in by_date[d]]) if len(dates_sorted) >= 1 else None
        accuracy_yesterday = _avg(by_date[dates_sorted[-2]]) if len(dates_sorted) >= 2 else None
        accuracy_today = _avg(by_date[dates_sorted[-1]]) if dates_sorted else None

        # Drift detection: >5% drop for 3+ days
        drift_detected = False
        drift_severity = "none"
        trigger_reason = None
        trend_direction = "stable"

        if len(dates_sorted) >= 3 and accuracy_7d is not None and accuracy_today is not None:
            recent_3 = dates_sorted[-3:]
            daily_avgs = [_avg(by_date[d]) for d in recent_3]
            # Check if declining 3+ consecutive days
            declining = all(daily_avgs[i] > daily_avgs[i + 1] for i in range(len(daily_avgs) - 1))
            drop_7d = accuracy_7d - accuracy_today

            if declining and drop_7d > 0.05:
                drift_detected = True
                trend_direction = "declining"
                trigger_reason = f"accuracy_dropped_{drop_7d:.1%}_over_3_days"
                drift_severity = "critical" if drop_7d > 0.10 else ("warning" if drop_7d > 0.05 else "none")
            elif drop_7d > 0.03:
                drift_detected = True
                trend_direction = "slight_decline"
                trigger_reason = f"accuracy_dropped_{drop_7d:.1%}_from_7d_avg"
                drift_severity = "warning"
            elif accuracy_today and accuracy_7d and accuracy_today > accuracy_7d + 0.03:
                trend_direction = "improving"
            else:
                trend_direction = "stable"

        # Check for repeated errors (same low score pattern)
        if not drift_detected and tenant_scores:
            low_scores = [s for s in tenant_scores if s["overall_score"] < 0.7]
            if len(low_scores) >= 3:
                # Check if same resolution_path failing
                paths: Dict[str, int] = {}
                for s in low_scores:
                    p = s.get("resolution_path", "unknown")
                    paths[p] = paths.get(p, 0) + 1
                worst_path = max(paths.items(), key=lambda x: x[1])
                if worst_path[1] >= 3:
                    drift_detected = True
                    drift_severity = "warning"
                    trend_direction = "declining"
                    trigger_reason = f"path_{worst_path[0]}_failed_{worst_path[1]}_times"

        return {
            "tenant_id": tenant_id,
            "drift_detected": drift_detected,
            "drift_severity": drift_severity,
            "accuracy_7d": accuracy_7d,
            "accuracy_yesterday": accuracy_yesterday,
            "accuracy_today": accuracy_today,
            "trend_direction": trend_direction,
            "trigger_reason": trigger_reason,
            "total_scores": len(tenant_scores),
        }

    # ── Ticket Flow Aggregation (Wave 2) ─────────────────────

    async def get_ticket_flow_summary(self, tenant_id: str, hours: int = 24) -> Dict[str, Any]:
        tenant_scores = [s for s in self._quality_scores if s["tenant_id"] == tenant_id]
        total = len(tenant_scores)
        if total == 0:
            return {
                "tenant_id": tenant_id, "total": 0, "auto_resolved": 0,
                "batched": 0, "escalated": 0, "stuck": 0,
                "by_type": {}, "by_node": {}, "avg_llm_calls": 0,
                "avg_quality": 0,
            }
        auto_resolved = sum(1 for s in tenant_scores if s.get("overall_score", 0) >= 0.85)
        escalated = sum(1 for s in tenant_scores if s.get("resolution_path") == "escalated")
        stuck = sum(1 for s in tenant_scores if s.get("resolution_path") == "stuck")
        batched = sum(1 for s in tenant_scores if s.get("resolution_path") == "batched")
        by_type: Dict[str, int] = {}
        by_node: Dict[str, int] = {}
        total_llm = 0
        total_q = 0
        for s in tenant_scores:
            path = s.get("resolution_path", "unknown")
            by_type[path] = by_type.get(path, 0) + 1
            for node in (s.get("nodes_reached") or []):
                by_node[node] = by_node.get(node, 0) + 1
            total_llm += s.get("llm_calls", 0)
            total_q += s.get("overall_score", 0)
        return {
            "tenant_id": tenant_id,
            "total": total,
            "auto_resolved": auto_resolved,
            "batched": batched,
            "escalated": escalated,
            "stuck": stuck,
            "by_type": by_type,
            "by_node": by_node,
            "avg_llm_calls": round(total_llm / max(total, 1), 1),
            "avg_quality": round(total_q / max(total, 1), 4),
        }

    # ── Load Balancing (Wave 2) ──────────────────────────────

    async def get_load_status(self, tenant_id: str) -> Dict[str, Any]:
        """Return load status. In memory: uses stored concurrent counts."""
        load = self._load_status.get(tenant_id, {})
        variants = []
        total_concurrent = 0
        for vname, vdata in load.items():
            conc = vdata.get("concurrent", 0)
            maxc = vdata.get("max_concurrent", 5)
            util = round(conc / max(maxc, 1) * 100, 1)
            status = "at_capacity" if util >= 100 else ("high" if util >= 80 else ("moderate" if util >= 50 else "low"))
            variants.append({
                "name": vname, "concurrent": conc, "max_concurrent": maxc,
                "utilization_pct": util, "status": status,
            })
            total_concurrent += conc
        return {
            "tenant_id": tenant_id,
            "variants": variants,
            "total_concurrent": total_concurrent,
            "vip_overflow_risk": any(v["status"] == "at_capacity" for v in variants),
        }

    def set_load(self, tenant_id: str, variant: str, concurrent: int, max_concurrent: int = 5):
        """Set load data for testing."""
        if tenant_id not in self._load_status:
            self._load_status[tenant_id] = {}
        self._load_status[tenant_id][variant] = {
            "concurrent": concurrent, "max_concurrent": max_concurrent,
        }

    # ── Agent Config Management (Wave 3) ─────────────────

    async def get_agent_config(self, tenant_id: str, agent_name: str) -> Optional[Dict[str, Any]]:
        for c in self._agent_configs:
            if c["tenant_id"] == tenant_id and c["agent_name"] == agent_name:
                return c
        return None

    async def update_agent_config(self, tenant_id: str, agent_name: str, **updates) -> Optional[Dict[str, Any]]:
        for c in self._agent_configs:
            if c["tenant_id"] == tenant_id and c["agent_name"] == agent_name:
                c.update(updates)
                c["updated_at"] = datetime.now(timezone.utc).isoformat()
                return c
        # Auto-create if not found
        new_config = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "agent_name": agent_name,
            "is_active": True,
            "max_concurrent": 5,
            "skills": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "backend": "memory",
        }
        new_config.update(updates)
        self._agent_configs.append(new_config)
        return new_config

    # ── Outbox Queue (Wave 3 — recall/void) ────────────────

    async def add_to_outbox(
        self, tenant_id, channel, recipient, subject, body,
        message_type="email", related_ticket=None,
    ) -> Dict[str, Any]:
        msg = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "channel": channel,
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "message_type": message_type,
            "related_ticket": related_ticket,
            "status": "pending",  # pending, sent, recalled, voided
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sent_at": None,
            "recalled_at": None,
            "backend": "memory",
        }
        self._outbox.append(msg)
        return msg

    async def recall_outbox_messages(self, tenant_id: str, match_filter: Optional[str] = None) -> int:
        count = 0
        now = datetime.now(timezone.utc).isoformat()
        for msg in self._outbox:
            if msg["tenant_id"] != tenant_id or msg["status"] != "pending":
                continue
            if match_filter is not None:
                filter_lower = match_filter.lower()
                if filter_lower not in msg.get("subject", "").lower() and filter_lower not in msg.get("body", "").lower():
                    continue
            msg["status"] = "recalled"
            msg["recalled_at"] = now
            count += 1
        return count

    async def void_outbox_messages(self, tenant_id: str, match_filter: Optional[str] = None) -> int:
        voided = 0
        now = datetime.now(timezone.utc).isoformat()
        for msg in self._outbox:
            if msg["tenant_id"] != tenant_id or msg["status"] != "pending":
                continue
            if match_filter is not None:
                filter_lower = match_filter.lower()
                if filter_lower not in msg.get("subject", "").lower() and filter_lower not in msg.get("body", "").lower():
                    continue
            msg["status"] = "voided"
            voided += 1
        return voided

    async def get_outbox_status(self, tenant_id: str) -> Dict[str, Any]:
        tenant_msgs = [m for m in self._outbox if m["tenant_id"] == tenant_id]
        by_status: Dict[str, int] = {}
        for m in tenant_msgs:
            s = m.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1
        return {
            "tenant_id": tenant_id,
            "total": len(tenant_msgs),
            "pending": by_status.get("pending", 0),
            "sent": by_status.get("sent", 0),
            "recalled": by_status.get("recalled", 0),
            "voided": by_status.get("voided", 0),
        }

    def clear_all(self):
        """Clear all data (for testing)."""
        self._notifications.clear()
        self._flags.clear()
        self._audit.clear()
        self._quality_scores.clear()
        self._batches.clear()
        self._batch_metas.clear()
        self._next_nfy_id = 1
        self._integration_pings.clear()
        self._llm_costs.clear()
        self._stuck_ticket_events.clear()
        self._load_status.clear()
        self._agent_configs.clear()
        self._outbox.clear()


# ═══════════════════════════════════════════════════════════════
# SUPABASE BACKEND (httpx → PostgREST, no new deps)
# ═══════════════════════════════════════════════════════════════

class SupabaseBackend(StorageBackend):
    """Supabase storage via REST API (PostgREST). Uses httpx.

    Requires env vars: SUPABASE_URL, SUPABASE_ANON_KEY
    """

    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set")
        self._url = SUPABASE_URL.rstrip("/")
        self._headers = {
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        self._client = None  # Lazy init on first use

    async def _get_client(self):
        if self._client is None or self._client.is_closed:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=self._url,
                headers=self._headers,
                timeout=15.0,
            )
        return self._client

    async def _rest_get(self, table: str, query: str = "") -> List[Dict]:
        client = await self._get_client()
        url = f"/rest/v1/{table}"
        if query:
            url += f"?{query}"
        r = await client.get(url)
        r.raise_for_status()
        return r.json() if r.text else []

    async def _rest_post(self, table: str, data: Dict) -> Dict:
        client = await self._get_client()
        r = await client.post(f"/rest/v1/{table}", json=data)
        r.raise_for_status()
        result = r.json()
        if isinstance(result, list) and result:
            return result[0]
        return result

    async def _rest_patch(self, table: str, filter_query: str, data: Dict) -> List[Dict]:
        client = await self._get_client()
        r = await client.patch(f"/rest/v1/{table}?{filter_query}", json=data)
        r.raise_for_status()
        return r.json() if r.text else []

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── Notifications ────────────────────────────────────────

    async def create_notification(
        self,
        tenant_id: str,
        ntype: str,
        priority_score: float,
        title: str,
        description: str,
        related_tickets: Optional[List[str]] = None,
        batch_key: Optional[str] = None,
        source_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        # Generate key locally to avoid race conditions
        existing = await self._rest_get(
            TABLE_NOTIFICATIONS,
            f"tenant_id=eq.{tenant_id}&select=notification_key&order=created_at.desc&limit=1"
        )
        next_num = 1
        if existing:
            import re
            m = re.search(r"PARWA-NFY-(\d+)", existing[0].get("notification_key", ""))
            if m:
                next_num = int(m.group(1)) + 1
        key = f"PARWA-NFY-{next_num:03d}"

        priority = PRIORITY_LOW
        for pname, pthresh in PRIORITY_THRESHOLDS.items():
            if priority_score >= pthresh:
                priority = pname
                break

        row = await self._rest_post(TABLE_NOTIFICATIONS, {
            "tenant_id": tenant_id,
            "notification_key": key,
            "type": ntype,
            "priority": priority,
            "priority_score": priority_score,
            "title": title,
            "description": description,
            "related_tickets": related_tickets or [],
            "batch_key": batch_key,
            "source_data": source_data or {},
        })
        row["backend"] = "supabase"
        return row

    async def get_notification(self, key: str) -> Optional[Dict[str, Any]]:
        results = await self._rest_get(
            TABLE_NOTIFICATIONS,
            f"notification_key=eq.{key}&limit=1"
        )
        if results:
            results[0]["backend"] = "supabase"
            return results[0]
        return None

    async def get_notifications(
        self,
        tenant_id: str,
        include_resolved: bool = False,
        min_priority: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query = f"tenant_id=eq.{tenant_id}"
        if not include_resolved:
            query += "&is_resolved=eq.false"
        query += "&order=priority.asc,created_at.desc&limit=100"
        results = await self._rest_get(TABLE_NOTIFICATIONS, query)
        for r in results:
            r["backend"] = "supabase"
        return results

    async def resolve_notification(self, key: str) -> bool:
        results = await self._rest_patch(
            TABLE_NOTIFICATIONS,
            f"notification_key=eq.{key}&is_resolved=eq.false",
            {"is_resolved": True, "resolved_at": datetime.now(timezone.utc).isoformat()},
        )
        return len(results) > 0

    async def dismiss_notification(self, key: str) -> bool:
        results = await self._rest_patch(
            TABLE_NOTIFICATIONS,
            f"notification_key=eq.{key}",
            {"is_read": True},
        )
        return len(results) > 0

    # ── System Flags ─────────────────────────────────────────

    async def set_flag(
        self,
        tenant_id: str,
        flag_type: str,
        flag_value: str,
        set_by: str,
        scope: str = "global",
        target_id: Optional[str] = None,
        reason: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        row = await self._rest_post(TABLE_FLAGS, {
            "tenant_id": tenant_id,
            "flag_type": flag_type,
            "flag_value": flag_value,
            "scope": scope,
            "target_id": target_id,
            "set_by": set_by,
            "reason": reason,
            "expires_at": expires_at,
        })
        row["backend"] = "supabase"
        return row

    async def get_active_flags(
        self, tenant_id: str, flag_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = f"tenant_id=eq.{tenant_id}&revoked_at=is.null"
        if flag_type:
            query += f"&flag_type=eq.{flag_type}"
        # Note: expires_at filtering done client-side (PostgREST can't do complex date comparisons easily)
        results = await self._rest_get(TABLE_FLAGS, query)
        now = datetime.now(timezone.utc)
        active = []
        for f in results:
            if f.get("expires_at"):
                exp = datetime.fromisoformat(f["expires_at"].replace("Z", "+00:00"))
                if exp < now:
                    continue
            f["backend"] = "supabase"
            active.append(f)
        return active

    async def revoke_flag(self, flag_id: str, revoked_by: str) -> bool:
        results = await self._rest_patch(
            TABLE_FLAGS,
            f"id=eq.{flag_id}&revoked_at=is.null",
            {"revoked_at": datetime.now(timezone.utc).isoformat()},
        )
        return len(results) > 0

    # ── Audit Trail ──────────────────────────────────────────

    async def create_audit_entry(
        self,
        tenant_id: str,
        action: str,
        actor_email: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        payload: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        payload_json = json.dumps(payload or {}, sort_keys=True)
        current_hash = hashlib.sha256(
            f"{tenant_id}:{action}:{payload_json}:{time.time()}".encode()
        ).hexdigest()[:64]

        # Get previous hash
        prev = await self._rest_get(
            TABLE_AUDIT,
            f"tenant_id=eq.{tenant_id}&select=current_hash&order=created_at.desc&limit=1"
        )
        prev_hash = prev[0]["current_hash"] if prev else None

        row = await self._rest_post(TABLE_AUDIT, {
            "tenant_id": tenant_id,
            "action": action,
            "actor_email": actor_email,
            "target_type": target_type,
            "target_id": target_id,
            "payload": payload or {},
            "previous_hash": prev_hash,
            "current_hash": current_hash,
        })
        row["backend"] = "supabase"
        return row

    async def get_audit_trail(
        self,
        tenant_id: str,
        action: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        query = f"tenant_id=eq.{tenant_id}"
        if action:
            query += f"&action=eq.{action}"
        query += f"&order=created_at.desc&limit={limit}"
        results = await self._rest_get(TABLE_AUDIT, query)
        for r in results:
            r["backend"] = "supabase"
        return results

    # ── Quality Scores ───────────────────────────────────────

    async def write_quality_score(
        self,
        tenant_id: str,
        ticket_id: str,
        overall_score: float,
        confidence_score: Optional[float] = None,
        resolution_path: Optional[str] = None,
        nodes_reached: Optional[List[str]] = None,
        llm_calls: int = 0,
        tokens_used: int = 0,
        model_used: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        row = await self._rest_post(TABLE_QUALITY_SCORES, {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "ticket_id": ticket_id,
            "overall_score": overall_score,
            "confidence_score": confidence_score,
            "resolution_path": resolution_path,
            "nodes_reached": nodes_reached or [],
            "llm_calls": llm_calls,
            "tokens_used": tokens_used,
            "model_used": model_used,
        })
        row["backend"] = "supabase"
        return row

    async def get_quality_stats(self, tenant_id: str, days: int = 7) -> Dict[str, Any]:
        # Supabase RPC would be ideal, but for now use REST + client-side agg
        results = await self._rest_get(
            TABLE_QUALITY_SCORES,
            f"tenant_id=eq.{tenant_id}&select=overall_score,confidence_score,resolution_path&limit=1000"
        )
        total = len(results)
        if total == 0:
            return {
                "tenant_id": tenant_id, "total_tickets": 0,
                "avg_quality": 0, "avg_confidence": 0,
                "auto_resolved": 0, "escalated": 0, "stuck": 0,
            }
        avg_q = sum(float(s.get("overall_score", 0)) for s in results) / total
        c_vals = [float(s["confidence_score"]) for s in results if s.get("confidence_score")]
        avg_c = sum(c_vals) / len(c_vals) if c_vals else 0
        paths = {}
        for s in results:
            p = s.get("resolution_path", "unknown")
            paths[p] = paths.get(p, 0) + 1
        return {
            "tenant_id": tenant_id,
            "total_tickets": total,
            "avg_quality": round(avg_q, 4),
            "avg_confidence": round(avg_c, 4),
            "by_path": paths,
            "auto_resolved": paths.get("simple", 0) + paths.get("complex", 0),
            "escalated": paths.get("escalated", 0),
            "stuck": paths.get("stuck", 0),
        }

    # ── Batch Queue ──────────────────────────────────────────

    async def add_to_batch(
        self,
        tenant_id: str,
        batch_key: str,
        ticket_id: str,
        confidence: float,
    ) -> Optional[Dict[str, Any]]:
        # Check for existing batch
        existing = await self._rest_get(
            TABLE_BATCH_QUEUE,
            f"tenant_id=eq.{tenant_id}&batch_key=eq.{batch_key}&status=eq.pending"
            f"&expires_at=gt.{datetime.now(timezone.utc).isoformat()}"
        )
        if existing:
            batch = existing[0]
            ticket_ids = batch.get("ticket_ids", [])
            ticket_ids.append(ticket_id)
            await self._rest_patch(
                TABLE_BATCH_QUEUE,
                f"id=eq.{batch['id']}",
                {
                    "ticket_ids": ticket_ids,
                    "confidence_min": min(float(batch.get("confidence_min", 1.0)), confidence),
                    "confidence_max": max(float(batch.get("confidence_max", 0.0)), confidence),
                },
            )
            return None

        # Create new batch
        await self._rest_post(TABLE_BATCH_QUEUE, {
            "tenant_id": tenant_id,
            "batch_key": batch_key,
            "ticket_ids": [ticket_id],
            "confidence_min": confidence,
            "confidence_max": confidence,
        })
        return None

    async def flush_batches(self, tenant_id: str) -> List[Dict[str, Any]]:
        results = await self._rest_get(
            TABLE_BATCH_QUEUE,
            f"tenant_id=eq.{tenant_id}&status=eq.pending"
        )
        # Mark all as flushed
        for batch in results:
            await self._rest_patch(
                TABLE_BATCH_QUEUE,
                f"id=eq.{batch['id']}",
                {"status": "flushed"},
            )
        return results

    # ── Integration Health (Wave 2) ─────────────────────────
    # Uses jarvis_integration_pings table (stores last 30 pings per service).

    async def write_integration_ping(
        self, tenant_id, service_name, is_healthy,
        response_ms=None, error_detail=None, status_code=None,
    ) -> Dict[str, Any]:
        row = await self._rest_post("jarvis_integration_pings", {
            "tenant_id": tenant_id, "service_name": service_name,
            "is_healthy": is_healthy, "response_ms": response_ms,
            "error_detail": error_detail, "status_code": status_code,
        })
        row["backend"] = "supabase"
        return row

    async def get_integration_health(self, tenant_id: str) -> Dict[str, Any]:
        """Fetch recent pings and compute health server-side."""
        pings = await self._rest_get(
            "jarvis_integration_pings",
            f"tenant_id=eq.{tenant_id}&order=created_at.desc&limit=300"
        )
        services: Dict[str, List[Dict]] = {}
        for p in pings:
            services.setdefault(p.get("service_name", ""), []).append(p)

        result = {"services": {}, "degraded_count": 0, "healthy_count": 0}
        for svc, sp in services.items():
            recent = sp[:30]
            healthy = sum(1 for p in recent if p.get("is_healthy"))
            total = len(recent)
            uptime_pct = round(healthy / max(total, 1) * 100, 1)
            last_ping = recent[0]
            avg_ms = sum(p.get("response_ms") or 0 for p in recent) / max(total, 1)
            last_error = None
            for p in recent:
                if not p.get("is_healthy"):
                    last_error = p.get("error_detail")
                    break
            status = "healthy" if uptime_pct >= 90 else ("degraded" if uptime_pct >= 50 else "down")
            if status != "healthy":
                result["degraded_count"] += 1
            else:
                result["healthy_count"] += 1
            result["services"][svc] = {
                "status": status, "uptime_pct": uptime_pct,
                "total_pings": total, "healthy_pings": healthy,
                "avg_response_ms": round(avg_ms, 1),
                "last_ping_at": last_ping.get("created_at"),
                "last_error": last_error,
                "last_status_code": last_ping.get("status_code"),
            }
        return result

    # ── LLM Cost Tracking (Wave 2) ───────────────────────────

    async def record_llm_cost(
        self, tenant_id, model, prompt_tokens, completion_tokens,
        cost_usd, call_type="parwa_pipeline",
    ) -> Dict[str, Any]:
        row = await self._rest_post("jarvis_llm_costs", {
            "tenant_id": tenant_id, "model": model,
            "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
            "cost_usd": cost_usd, "call_type": call_type,
        })
        row["backend"] = "supabase"
        return row

    async def get_llm_cost_summary(self, tenant_id: str, days: int = 7) -> Dict[str, Any]:
        costs = await self._rest_get(
            "jarvis_llm_costs",
            f"tenant_id=eq.{tenant_id}&select=model,prompt_tokens,completion_tokens,cost_usd,call_type,created_at&limit=5000"
        )
        if not costs:
            return {"tenant_id": tenant_id, "total_cost_usd": 0.0, "total_tokens": 0, "total_calls": 0, "by_model": {}, "by_type": {}}
        total_cost = sum(float(c.get("cost_usd", 0)) for c in costs)
        total_tokens = sum(int(c.get("prompt_tokens", 0)) + int(c.get("completion_tokens", 0)) for c in costs)
        by_model: Dict[str, Dict] = {}
        by_type: Dict[str, Dict] = {}
        for c in costs:
            m = c.get("model", "unknown")
            by_model.setdefault(m, {"cost": 0.0, "tokens": 0, "calls": 0})
            by_model[m]["cost"] += float(c.get("cost_usd", 0))
            by_model[m]["tokens"] += int(c.get("prompt_tokens", 0)) + int(c.get("completion_tokens", 0))
            by_model[m]["calls"] += 1
            t = c.get("call_type", "unknown")
            by_type.setdefault(t, {"cost": 0.0, "tokens": 0, "calls": 0})
            by_type[t]["cost"] += float(c.get("cost_usd", 0))
            by_type[t]["tokens"] += int(c.get("prompt_tokens", 0)) + int(c.get("completion_tokens", 0))
            by_type[t]["calls"] += 1
        return {
            "tenant_id": tenant_id, "total_cost_usd": round(total_cost, 4),
            "total_tokens": total_tokens, "total_calls": len(costs),
            "by_model": by_model, "by_type": by_type,
        }

    # ── Stuck Ticket Tracking (Wave 2) ───────────────────────

    async def record_stuck_ticket_check(
        self, tenant_id, ticket_id, stuck_reason, hours_stuck, escalation_tier,
    ) -> Dict[str, Any]:
        row = await self._rest_post("jarvis_stuck_ticket_events", {
            "tenant_id": tenant_id, "ticket_id": ticket_id,
            "stuck_reason": stuck_reason, "hours_stuck": hours_stuck,
            "escalation_tier": escalation_tier,
        })
        row["backend"] = "supabase"
        return row

    async def get_stuck_tickets(self, tenant_id: str) -> List[Dict[str, Any]]:
        return await self._rest_get(
            "jarvis_stuck_ticket_events",
            f"tenant_id=eq.{tenant_id}&resolved=eq.false&order=detected_at.desc"
        )

    # ── Drift Detection (Wave 2) ─────────────────────────────

    async def check_quality_drift(self, tenant_id: str) -> Dict[str, Any]:
        # Fetch scores + client-side drift analysis (same logic as InMemory)
        scores = await self._rest_get(
            TABLE_QUALITY_SCORES,
            f"tenant_id=eq.{tenant_id}&select=overall_score,resolution_path,created_at&order=created_at.asc&limit=5000"
        )
        if len(scores) < 3:
            return {"tenant_id": tenant_id, "drift_detected": False, "drift_severity": "none",
                    "accuracy_7d": None, "accuracy_yesterday": None, "accuracy_today": None,
                    "trend_direction": "stable", "trigger_reason": "insufficient_data", "total_scores": len(scores)}
        by_date: Dict[str, List[float]] = {}
        for s in scores:
            d = (s.get("created_at") or "")[:10]
            by_date.setdefault(d, []).append(float(s.get("overall_score", 0)))
        dates_sorted = sorted(by_date.keys())
        def _avg(vals): return round(sum(vals) / len(vals), 4) if vals else 0.0
        accuracy_7d = _avg([v for d in dates_sorted[-7:] for v in by_date[d]])
        accuracy_today = _avg(by_date[dates_sorted[-1]])
        accuracy_yesterday = _avg(by_date[dates_sorted[-2]]) if len(dates_sorted) >= 2 else None
        drift_detected = False; drift_severity = "none"; trigger_reason = None; trend_direction = "stable"
        if len(dates_sorted) >= 3:
            daily_avgs = [_avg(by_date[d]) for d in dates_sorted[-3:]]
            declining = all(daily_avgs[i] > daily_avgs[i+1] for i in range(len(daily_avgs)-1))
            drop = accuracy_7d - accuracy_today
            if declining and drop > 0.05:
                drift_detected = True; trend_direction = "declining"
                trigger_reason = f"accuracy_dropped_{drop:.1%}_over_3_days"
                drift_severity = "critical" if drop > 0.10 else "warning"
            elif drop > 0.03:
                drift_detected = True; trend_direction = "slight_decline"
                trigger_reason = f"accuracy_dropped_{drop:.1%}_from_7d_avg"; drift_severity = "warning"
            elif accuracy_today > accuracy_7d + 0.03:
                trend_direction = "improving"
        return {"tenant_id": tenant_id, "drift_detected": drift_detected, "drift_severity": drift_severity,
                "accuracy_7d": accuracy_7d, "accuracy_yesterday": accuracy_yesterday,
                "accuracy_today": accuracy_today, "trend_direction": trend_direction,
                "trigger_reason": trigger_reason, "total_scores": len(scores)}

    # ── Ticket Flow Aggregation (Wave 2) ─────────────────────

    async def get_ticket_flow_summary(self, tenant_id: str, hours: int = 24) -> Dict[str, Any]:
        scores = await self._rest_get(
            TABLE_QUALITY_SCORES,
            f"tenant_id=eq.{tenant_id}&select=overall_score,resolution_path,nodes_reached,llm_calls&limit=5000"
        )
        total = len(scores)
        if total == 0:
            return {"tenant_id": tenant_id, "total": 0, "auto_resolved": 0, "batched": 0,
                    "escalated": 0, "stuck": 0, "by_type": {}, "by_node": {}, "avg_llm_calls": 0, "avg_quality": 0}
        auto_resolved = sum(1 for s in scores if float(s.get("overall_score", 0)) >= 0.85)
        escalated = sum(1 for s in scores if s.get("resolution_path") == "escalated")
        stuck = sum(1 for s in scores if s.get("resolution_path") == "stuck")
        batched = sum(1 for s in scores if s.get("resolution_path") == "batched")
        by_type: Dict[str, int] = {}; by_node: Dict[str, int] = {}; total_llm = 0; total_q = 0
        for s in scores:
            p = s.get("resolution_path", "unknown"); by_type[p] = by_type.get(p, 0) + 1
            for node in (s.get("nodes_reached") or []): by_node[node] = by_node.get(node, 0) + 1
            total_llm += int(s.get("llm_calls", 0)); total_q += float(s.get("overall_score", 0))
        return {"tenant_id": tenant_id, "total": total, "auto_resolved": auto_resolved,
                "batched": batched, "escalated": escalated, "stuck": stuck,
                "by_type": by_type, "by_node": by_node,
                "avg_llm_calls": round(total_llm / max(total, 1), 1),
                "avg_quality": round(total_q / max(total, 1), 4)}

    # ── Load Balancing (Wave 2) ──────────────────────────────

    async def get_load_status(self, tenant_id: str) -> Dict[str, Any]:
        # Read agent_configs for variant capacity info
        configs = await self._rest_get(
            TABLE_AGENT_CONFIGS,
            f"tenant_id=eq.{tenant_id}&select=agent_name,max_concurrent,is_active&is_active=eq.true"
        )
        variants = []
        for c in configs:
            name = c.get("agent_name", "unknown")
            maxc = c.get("max_concurrent", 5) or 5
            # In production, concurrent count would come from a real-time counter
            # For now, use 0 as baseline — PARWA would update this
            variants.append({"name": name, "concurrent": 0, "max_concurrent": maxc,
                            "utilization_pct": 0, "status": "low"})
        return {"tenant_id": tenant_id, "variants": variants, "total_concurrent": 0, "vip_overflow_risk": False}

    # ── Agent Config Management (Wave 3) ─────────────────

    async def get_agent_config(self, tenant_id: str, agent_name: str) -> Optional[Dict[str, Any]]:
        results = await self._rest_get(
            TABLE_AGENT_CONFIGS,
            f"tenant_id=eq.{tenant_id}&agent_name=eq.{agent_name}&limit=1"
        )
        if results:
            results[0]["backend"] = "supabase"
            return results[0]
        return None

    async def update_agent_config(self, tenant_id: str, agent_name: str, **updates) -> Optional[Dict[str, Any]]:
        existing = await self._rest_get(
            TABLE_AGENT_CONFIGS,
            f"tenant_id=eq.{tenant_id}&agent_name=eq.{agent_name}&limit=1"
        )
        if existing:
            result = await self._rest_patch(
                TABLE_AGENT_CONFIGS,
                f"id=eq.{existing[0]['id']}",
                updates,
            )
            if result:
                result[0]["backend"] = "supabase"
                return result[0]
        else:
            # Auto-create
            row = await self._rest_post(TABLE_AGENT_CONFIGS, {
                "tenant_id": tenant_id,
                "agent_name": agent_name,
                "is_active": True,
                "max_concurrent": 5,
                "skills": [],
                **updates,
            })
            row["backend"] = "supabase"
            return row
        return None

    # ── Outbox Queue (Wave 3 — recall/void) ────────────────

    async def add_to_outbox(
        self, tenant_id, channel, recipient, subject, body,
        message_type="email", related_ticket=None,
    ) -> Dict[str, Any]:
        row = await self._rest_post("jarvis_outbox_queue", {
            "tenant_id": tenant_id, "channel": channel,
            "recipient": recipient, "subject": subject, "body": body,
            "message_type": message_type, "related_ticket": related_ticket,
            "status": "pending",
        })
        row["backend"] = "supabase"
        return row

    async def recall_outbox_messages(self, tenant_id: str, match_filter: Optional[str] = None) -> int:
        query = f"tenant_id=eq.{tenant_id}&status=eq.pending"
        if match_filter:
            query += f"&subject=ilike.*{match_filter}*"
        results = await self._rest_get("jarvis_outbox_queue", query)
        count = 0
        now = datetime.now(timezone.utc).isoformat()
        for msg in results:
            await self._rest_patch(
                "jarvis_outbox_queue",
                f"id=eq.{msg['id']}",
                {"status": "recalled", "recalled_at": now},
            )
            count += 1
        return count

    async def void_outbox_messages(self, tenant_id: str, match_filter: Optional[str] = None) -> int:
        query = f"tenant_id=eq.{tenant_id}&status=eq.pending"
        if match_filter:
            query += f"&subject=ilike.*{match_filter}*"
        results = await self._rest_get("jarvis_outbox_queue", query)
        count = 0
        for msg in results:
            await self._rest_patch(
                "jarvis_outbox_queue",
                f"id=eq.{msg['id']}",
                {"status": "voided"},
            )
            count += 1
        return count

    async def get_outbox_status(self, tenant_id: str) -> Dict[str, Any]:
        all_msgs = await self._rest_get(
            "jarvis_outbox_queue",
            f"tenant_id=eq.{tenant_id}&select=status"
        )
        by_status = {}
        for m in all_msgs:
            s = m.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1
        return {
            "tenant_id": tenant_id,
            "total": len(all_msgs),
            "pending": by_status.get("pending", 0),
            "sent": by_status.get("sent", 0),
            "recalled": by_status.get("recalled", 0),
            "voided": by_status.get("voided", 0),
        }

    # ── Jarvis Inbox (Wave 4) ─────────────────────────────

    async def write_to_inbox(
        self,
        tenant_id: str,
        ticket_id: str,
        stuck_reason: str,
        quality_score: float,
        what_was_tried: str,
        inbox_type: str = "parwa_stuck",
    ) -> Dict[str, Any]:
        payload = {
            "tenant_id": tenant_id,
            "ticket_id": ticket_id,
            "stuck_reason": stuck_reason,
            "quality_score": quality_score,
            "what_was_tried": what_was_tried[:1000],
            "inbox_type": inbox_type,
            "status": "pending",
        }
        return await self._rest_post(TABLE_INBOX, payload)

    async def get_inbox_messages(
        self, tenant_id: str, include_resolved: bool = False
    ) -> List[Dict[str, Any]]:
        query = f"tenant_id=eq.{tenant_id}&order=created_at.desc"
        if not include_resolved:
            query += "&status=eq.pending"
        return await self._rest_get(TABLE_INBOX, query)

    async def resolve_inbox_message(self, message_id: str) -> bool:
        await self._rest_patch(
            TABLE_INBOX,
            f"id=eq.{message_id}",
            {"status": "resolved", "resolved_at": datetime.now(timezone.utc).isoformat()},
        )
        return True

    # ── Training Data (Wave 4) ─────────────────────────────

    async def record_training_data(
        self,
        tenant_id: str,
        ticket_id: str,
        signal_type: str,
        original_response: str = "",
        corrected_response: str = "",
        quality_score: float = 0.0,
        ticket_type: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "tenant_id": tenant_id,
            "ticket_id": ticket_id,
            "signal_type": signal_type,
            "original_response": original_response[:2000],
            "corrected_response": corrected_response[:2000],
            "quality_score": quality_score,
            "ticket_type": ticket_type,
            "metadata": metadata or {},
        }
        return await self._rest_post(TABLE_TRAINING_DATA, payload)

    async def get_training_data(
        self, tenant_id: str, signal_type: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        query = f"tenant_id=eq.{tenant_id}&order=created_at.desc&limit={limit}"
        if signal_type:
            query += f"&signal_type=eq.{signal_type}"
        return await self._rest_get(TABLE_TRAINING_DATA, query)

    # ── Utility ──────────────────────────────────────────────

    async def get_notification_stats(self, tenant_id: str) -> Dict[str, Any]:
        all_nfs = await self._rest_get(
            TABLE_NOTIFICATIONS,
            f"tenant_id=eq.{tenant_id}&select=priority,is_read,is_resolved"
        )
        by_priority = {}
        for p in [PRIORITY_CRITICAL, PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW]:
            by_priority[p] = sum(1 for n in all_nfs if n.get("priority") == p)
        return {
            "total": len(all_nfs),
            "unread": sum(1 for n in all_nfs if not n.get("is_read")),
            "unresolved": sum(1 for n in all_nfs if not n.get("is_resolved")),
            "by_priority": by_priority,
        }

    async def health_check(self) -> Dict[str, Any]:
        try:
            client = await self._get_client()
            r = await client.get("/rest/v1/jarvis_notifications?select=id&limit=1")
            return {
                "backend": "supabase",
                "status": "healthy" if r.status_code == 200 else "degraded",
                "url": self._url,
            }
        except Exception as e:
            return {"backend": "supabase", "status": "error", "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# GLOBAL INSTANCE — auto-detect mode
# ═══════════════════════════════════════════════════════════════

_backend: Optional[StorageBackend] = None


def get_db() -> StorageBackend:
    """Get the active storage backend. Singleton.

    Auto-detects:
      - SUPABASE_URL + SUPABASE_ANON_KEY set → SupabaseBackend
      - Otherwise → InMemoryBackend
    """
    global _backend
    if _backend is None:
        if SUPABASE_URL and SUPABASE_ANON_KEY:
            logger.info("Jarvis DB: Using Supabase backend (%s)", SUPABASE_URL[:40])
            _backend = SupabaseBackend()
        else:
            logger.info("Jarvis DB: Using InMemory backend (set SUPABASE_URL for production)")
            _backend = InMemoryBackend()
    return _backend


def reset_db():
    """Reset the global backend (for testing)."""
    global _backend
    if isinstance(_backend, SupabaseBackend):
        import asyncio
        asyncio.get_event_loop().run_until_complete(_backend.close())
    _backend = None


def use_in_memory():
    """Force in-memory mode (for testing)."""
    global _backend
    _backend = InMemoryBackend()
    logger.info("Jarvis DB: Forced to InMemory mode")