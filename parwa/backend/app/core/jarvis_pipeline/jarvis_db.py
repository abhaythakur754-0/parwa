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

    def clear_all(self):
        """Clear all data (for testing)."""
        self._notifications.clear()
        self._flags.clear()
        self._audit.clear()
        self._quality_scores.clear()
        self._batches.clear()
        self._batch_metas.clear()
        self._next_nfy_id = 1


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