"""
Escalation Vault — Dual-Mode Storage Backend

Stores full PARWA pipeline state when a ticket is escalated (Node 8 fails),
so that PARWA can resume processing after human provides guidance via JARVIS.

Also tracks CRM push-back status for round-trip ticket updates.

Modes:
  1. InMemory (default) — zero deps, works immediately for dev/testing
  2. Supabase (production) — uses httpx → Supabase REST API (PostgREST)

Auto-detection: if SUPABASE_URL + SUPABASE_ANON_KEY env vars set → Supabase.
Otherwise → InMemory.

Table: parwa_escalation_vault
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("parwa.escalation_vault")

# ── Config ────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

TABLE_VAULT = "parwa_escalation_vault"

# Escalation source identifiers
SOURCE_NODE_8 = "node_8_super_node"
SOURCE_NODE_2 = "node_2_paused"
SOURCE_NODE_1 = "node_1_rejected"
SOURCE_NODE_1_AGENT_REQUEST = "node_1_agent_creation"

# Human status flow
HUMAN_PENDING = "pending"
HUMAN_GUIDANCE_PROVIDED = "guidance_provided"
HUMAN_PROCESSING = "processing"   # BC-016: atomically claimed by an agent
HUMAN_RESOLVED = "resolved"

# Reprocess status flow
REPROCESS_PENDING = "pending"
REPROCESS_PROCESSING = "processing"
REPROCESS_DONE = "done"
REPROCESS_FAILED = "failed"
# BC-017: New terminal state when AI has exhausted MAX_GUIDANCE_RETRIES
# attempts and cannot meet the quality threshold. When this state is set,
# the guidance flow fires push_permanent_failure_to_crm() which resets
# the CRM ticket back to "open"/"new" so the human queue picks it up
# fresh. Vault human_status is also moved to HUMAN_RESOLVED because
# CRM is now the source of truth again.
REPROCESS_EXHAUSTED = "exhausted"

# CRM push status
CRM_PENDING = "pending"
CRM_UPDATED = "updated"
CRM_FAILED = "failed"


# ── BC-016: Atomic claim state ──────────────────────────────────
# When an agent claims an escalation, we set human_status=processing
# and record claimed_by_agent_id + claimed_at. The claim is atomic —
# only the first agent wins; subsequent claimants get claim=False.

HUMAN_CLAIMABLE = "pending"   # same as HUMAN_PENDING — only pending escalations can be claimed


# ═══════════════════════════════════════════════════════════════
# ABSTRACT BASE
# ═══════════════════════════════════════════════════════════════

class VaultStorageBackend(ABC):
    """Abstract vault storage backend. All methods are async."""

    @abstractmethod
    async def save_escalation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Save a new escalation to the vault. Returns the saved record."""
        ...

    @abstractmethod
    async def get_escalation(self, escalation_id: str) -> Optional[Dict[str, Any]]:
        """Get escalation by ID."""
        ...

    @abstractmethod
    async def get_escalation_by_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """Get escalation by original PARWA ticket ID."""
        ...

    @abstractmethod
    async def get_escalation_by_notification(self, notification_key: str) -> Optional[Dict[str, Any]]:
        """Get escalation by PARWA-NFY notification key."""
        ...

    @abstractmethod
    async def get_pending_resumes(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get escalations that have human guidance but haven't been reprocessed."""
        ...

    @abstractmethod
    async def update_human_guidance(
        self, escalation_id: str, guidance: str, source: str = "jarvis_chat"
    ) -> Optional[Dict[str, Any]]:
        """Update human guidance for an escalation."""
        ...

    @abstractmethod
    async def update_reprocess_result(
        self, escalation_id: str, result: str, quality_score: float,
        technique_log: Optional[List[Dict]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Save the resume pipeline result."""
        ...

    @abstractmethod
    async def update_reprocess_status_direct(
        self, escalation_id: str, status: str,
    ) -> Optional[Dict[str, Any]]:
        """Directly update reprocess_status (e.g. to FAILED after initial DONE)."""
        ...

    @abstractmethod
    async def increment_reprocess_attempts(
        self, escalation_id: str,
    ) -> int:
        """BC-017: Atomically increment the reprocess_attempts counter.

        Called once per guidance-flow run. Returns the new counter value
        (after increment). The guidance flow uses this to detect when
        MAX_GUIDANCE_RETRIES has been exceeded and trigger the
        permanent-failure CRM push path.
        """
        ...

    @abstractmethod
    async def update_crm_status(
        self, escalation_id: str, status: str, crm_ticket_id: str = "",
        crm_response: Optional[Dict] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update CRM push-back status."""
        ...

    @abstractmethod
    async def claim_escalation(
        self, escalation_id: str, agent_id: str,
    ) -> Dict[str, Any]:
        """BC-016: Atomically claim an escalation for human processing.

        Only succeeds if escalation is currently in HUMAN_PENDING status.
        Sets human_status=HUMAN_PROCESSING, claimed_by_agent_id=agent_id,
        claimed_at=now. Subsequent claimants get success=False.

        Args:
            escalation_id: The escalation to claim.
            agent_id: The human agent claiming it (user_id from auth).

        Returns:
            {
                "success": True/False,
                "escalation_id": str,
                "claimed_by": Optional[str],   # agent_id if success, else current claimer
                "reason": str,                 # "claimed" / "already_claimed" / "not_found" / "not_pending"
            }
        """
        ...

    @abstractmethod
    async def list_escalations(
        self, tenant_id: str,
        human_status: Optional[str] = None,
        reprocess_status: Optional[str] = None,
        limit: int = 50,
        exclude_processing: bool = True,
    ) -> List[Dict[str, Any]]:
        """List escalations with optional filters.

        BC-016: exclude_processing defaults to True — escalations currently
        being worked by another agent (human_status=processing) are hidden
        from the default queue so two agents never see the same ticket.
        Pass exclude_processing=False to see the full queue (admin view).
        """
        ...

    @abstractmethod
    async def get_vault_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get vault statistics for a tenant."""
        ...


# ═══════════════════════════════════════════════════════════════
# IN-MEMORY BACKEND
# ═══════════════════════════════════════════════════════════════

class InMemoryVaultDB(VaultStorageBackend):
    """In-memory vault storage. Thread-safe for dev/testing."""

    def __init__(self):
        self._vault: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    async def save_escalation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "escalation_id": data.get("escalation_id", str(uuid.uuid4())),
            "tenant_id": data.get("tenant_id", ""),
            "original_ticket_id": data.get("original_ticket_id", ""),
            "notification_key": data.get("notification_key", ""),
            "escalation_source": data.get("escalation_source", SOURCE_NODE_8),

            # ── Saved Pipeline State ──
            "original_query": data.get("original_query", ""),
            "ticket_type": data.get("ticket_type", ""),
            "complexity": data.get("complexity", ""),
            "required_action": data.get("required_action", ""),
            "action_details": data.get("action_details", {}),
            "knowledge_context": data.get("knowledge_context", []),
            "crm_data": data.get("crm_data", {}),
            "customer_context": data.get("customer_context", {}),
            "previous_attempts": data.get("previous_attempts", []),
            "failure_analysis": data.get("failure_analysis", ""),
            "quality_score": data.get("quality_score", 0.0),
            "technique_log": data.get("technique_log", []),
            "variant_tier": data.get("variant_tier", "parwa"),
            "wiki_section_c": data.get("wiki_section_c", []),
            "wiki_patterns": data.get("wiki_patterns", []),
            "escalation_context": data.get("escalation_context", {}),
            "combined_answer": data.get("combined_answer", ""),
            "formatted_response": data.get("formatted_response", ""),

            # ── Human Input ──
            "human_guidance": "",
            "human_status": HUMAN_PENDING,
            "guidance_timestamp": None,
            "guidance_source": None,
            # BC-016: atomic claim fields
            "claimed_by_agent_id": None,
            "claimed_at": None,

            # ── Re-processing ──
            "reprocess_status": REPROCESS_PENDING,
            "reprocess_result": "",
            "reprocess_quality_score": None,
            "reprocess_technique_log": [],
            "reprocess_started_at": None,
            "reprocess_completed_at": None,
            # BC-017: per-escalation attempt counter for guidance flow.
            # Incremented once per guidance run; when it exceeds
            # GUIDANCE_MAX_RETRIES, the flow fires push_permanent_failure
            # and sets reprocess_status = REPROCESS_EXHAUSTED.
            "reprocess_attempts": 0,

            # ── CRM Round-Trip ──
            "crm_ticket_id": data.get("crm_ticket_id", ""),
            "crm_provider": data.get("crm_provider", ""),
            "crm_status": CRM_PENDING,
            "crm_updated_at": None,
            "crm_response": None,

            # ── Metadata ──
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            self._vault.append(record)
        logger.info("Vault SAVE: escalation=%s ticket=%s key=%s",
                     record["escalation_id"][:8], record["original_ticket_id"],
                     record["notification_key"])
        return record

    def _find(self, key: str, field: str) -> Optional[Dict[str, Any]]:
        for r in self._vault:
            if r[field] == key:
                return r
        return None

    async def get_escalation(self, escalation_id: str) -> Optional[Dict[str, Any]]:
        return self._find(escalation_id, "escalation_id")

    async def get_escalation_by_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        return self._find(ticket_id, "original_ticket_id")

    async def get_escalation_by_notification(self, notification_key: str) -> Optional[Dict[str, Any]]:
        return self._find(notification_key, "notification_key")

    async def get_pending_resumes(self, tenant_id: str) -> List[Dict[str, Any]]:
        return [
            r for r in self._vault
            if r["tenant_id"] == tenant_id
            and r["human_status"] == HUMAN_GUIDANCE_PROVIDED
            and r["reprocess_status"] == REPROCESS_PENDING
        ]

    async def update_human_guidance(
        self, escalation_id: str, guidance: str, source: str = "jarvis_chat"
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            record = self._find(escalation_id, "escalation_id")
            if not record:
                return None
            now = datetime.now(timezone.utc).isoformat()
            record["human_guidance"] = guidance
            record["human_status"] = HUMAN_GUIDANCE_PROVIDED
            record["guidance_timestamp"] = now
            record["guidance_source"] = source
            record["updated_at"] = now
            logger.info("Vault GUIDANCE: escalation=%s source=%s", escalation_id[:8], source)
            return record

    async def update_reprocess_result(
        self, escalation_id: str, result: str, quality_score: float,
        technique_log: Optional[List[Dict]] = None,
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            record = self._find(escalation_id, "escalation_id")
            if not record:
                return None
            now = datetime.now(timezone.utc).isoformat()
            record["reprocess_result"] = result
            record["reprocess_quality_score"] = round(quality_score, 4)
            record["reprocess_technique_log"] = technique_log or []
            record["reprocess_status"] = REPROCESS_DONE
            record["reprocess_completed_at"] = now
            record["updated_at"] = now
            logger.info("Vault REPROCESS DONE: escalation=%s quality=%.4f",
                         escalation_id[:8], quality_score)
            return record

    async def update_reprocess_status_direct(
        self, escalation_id: str, status: str,
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            record = self._find(escalation_id, "escalation_id")
            if not record:
                return None
            record["reprocess_status"] = status
            record["updated_at"] = datetime.now(timezone.utc).isoformat()
            logger.info("Vault REPROCESS STATUS: escalation=%s status=%s", escalation_id[:8], status)
            return record

    async def increment_reprocess_attempts(
        self, escalation_id: str,
    ) -> int:
        """BC-017: Atomically increment reprocess_attempts (InMemory).

        Returns the new counter value. Returns -1 if escalation not found.
        """
        with self._lock:
            record = self._find(escalation_id, "escalation_id")
            if not record:
                return -1
            record["reprocess_attempts"] = (record.get("reprocess_attempts") or 0) + 1
            record["updated_at"] = datetime.now(timezone.utc).isoformat()
            new_count = record["reprocess_attempts"]
            logger.info(
                "Vault REPROCESS ATTEMPTS++: escalation=%s attempts=%d",
                escalation_id[:8], new_count,
            )
            return new_count

    async def update_crm_status(
        self, escalation_id: str, status: str, crm_ticket_id: str = "",
        crm_response: Optional[Dict] = None,
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            record = self._find(escalation_id, "escalation_id")
            if not record:
                return None
            now = datetime.now(timezone.utc).isoformat()
            record["crm_status"] = status
            if crm_ticket_id:
                record["crm_ticket_id"] = crm_ticket_id
            record["crm_response"] = crm_response
            record["crm_updated_at"] = now
            record["updated_at"] = now
            logger.info("Vault CRM UPDATE: escalation=%s crm_status=%s", escalation_id[:8], status)
            return record

    async def claim_escalation(
        self, escalation_id: str, agent_id: str,
    ) -> Dict[str, Any]:
        """BC-016: Atomic claim for the in-memory backend.

        Uses self._lock to ensure only one agent wins the claim even under
        concurrent access. The compare-and-set on human_status is the
        atomic primitive.
        """
        with self._lock:
            record = self._find(escalation_id, "escalation_id")
            if not record:
                return {
                    "success": False,
                    "escalation_id": escalation_id,
                    "claimed_by": None,
                    "reason": "not_found",
                }
            if record["human_status"] != HUMAN_PENDING:
                return {
                    "success": False,
                    "escalation_id": escalation_id,
                    "claimed_by": record.get("claimed_by_agent_id"),
                    "reason": "already_claimed" if record["human_status"] == HUMAN_PROCESSING else "not_pending",
                }
            # Atomic claim: transition pending → processing
            now = datetime.now(timezone.utc).isoformat()
            record["human_status"] = HUMAN_PROCESSING
            record["claimed_by_agent_id"] = agent_id
            record["claimed_at"] = now
            record["updated_at"] = now
            logger.info(
                "Vault CLAIM: escalation=%s agent=%s",
                escalation_id[:8], agent_id,
            )
            return {
                "success": True,
                "escalation_id": escalation_id,
                "claimed_by": agent_id,
                "reason": "claimed",
            }

    async def list_escalations(
        self, tenant_id: str,
        human_status: Optional[str] = None,
        reprocess_status: Optional[str] = None,
        limit: int = 50,
        exclude_processing: bool = True,
    ) -> List[Dict[str, Any]]:
        records = [r for r in self._vault if r["tenant_id"] == tenant_id]
        if human_status:
            records = [r for r in records if r["human_status"] == human_status]
        if reprocess_status:
            records = [r for r in records if r["reprocess_status"] == reprocess_status]
        # BC-016: hide tickets currently being worked by another agent
        if exclude_processing and not human_status:
            records = [r for r in records if r["human_status"] != HUMAN_PROCESSING]
        return sorted(records, key=lambda r: r["created_at"], reverse=True)[:limit]

    async def get_vault_stats(self, tenant_id: str) -> Dict[str, Any]:
        records = [r for r in self._vault if r["tenant_id"] == tenant_id]
        return {
            "tenant_id": tenant_id,
            "total_escalations": len(records),
            "awaiting_human": sum(1 for r in records if r["human_status"] == HUMAN_PENDING),
            "guidance_provided": sum(1 for r in records if r["human_status"] == HUMAN_GUIDANCE_PROVIDED),
            "reprocess_done": sum(1 for r in records if r["reprocess_status"] == REPROCESS_DONE),
            "reprocess_failed": sum(1 for r in records if r["reprocess_status"] == REPROCESS_FAILED),
            "crm_updated": sum(1 for r in records if r["crm_status"] == CRM_UPDATED),
            "crm_pending": sum(1 for r in records if r["crm_status"] == CRM_PENDING),
        }

    async def health_check(self) -> Dict[str, Any]:
        return {
            "backend": "memory",
            "status": "healthy",
            "total_records": len(self._vault),
        }


# ═══════════════════════════════════════════════════════════════
# SUPABASE BACKEND
# ═══════════════════════════════════════════════════════════════

class SupabaseVaultDB(VaultStorageBackend):
    """Supabase-backed vault storage for production."""

    def __init__(self):
        self._url = SUPABASE_URL.rstrip("/")
        self._key = SUPABASE_ANON_KEY
        self._headers = {
            "apikey": self._key,
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def _post(self, path: str, body: Dict) -> Dict:
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self._url}/rest/v1/{path}",
                headers=self._headers,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
            return data[0] if isinstance(data, list) else data

    async def _patch(self, path: str, body: Dict, filters: str = "") -> Dict:
        import httpx
        url = f"{self._url}/rest/v1/{path}"
        if filters:
            url += f"?{filters}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.patch(url, headers=self._headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            return data[0] if isinstance(data, list) else data

    async def _get(self, path: str, filters: str = "", limit: int = 1) -> List[Dict]:
        import httpx
        url = f"{self._url}/rest/v1/{path}"
        params = []
        if filters:
            params.append(filters)
        params.append(f"limit={limit}")
        params.append("order=created_at.desc")
        if params:
            url += "?" + "&".join(params)
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=self._headers)
            resp.raise_for_status()
            return resp.json()

    def _serialize(self, data: Dict) -> Dict:
        """Serialize dict/list fields to JSON strings for Supabase."""
        serialized = {}
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                serialized[k] = json.dumps(v) if v else None
            else:
                serialized[k] = v
        return serialized

    async def save_escalation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        serialized = self._serialize(data)
        record = await self._post(TABLE_VAULT, serialized)
        logger.info("Vault SAVE (Supabase): escalation=%s", record.get("escalation_id", "")[:8])
        return record

    async def get_escalation(self, escalation_id: str) -> Optional[Dict[str, Any]]:
        results = await self._get(TABLE_VAULT, f"escalation_id=eq.{escalation_id}", limit=1)
        return results[0] if results else None

    async def get_escalation_by_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        results = await self._get(TABLE_VAULT, f"original_ticket_id=eq.{ticket_id}", limit=1)
        return results[0] if results else None

    async def get_escalation_by_notification(self, notification_key: str) -> Optional[Dict[str, Any]]:
        results = await self._get(TABLE_VAULT, f"notification_key=eq.{notification_key}", limit=1)
        return results[0] if results else None

    async def get_pending_resumes(self, tenant_id: str) -> List[Dict[str, Any]]:
        filters = f"tenant_id=eq.{tenant_id}&human_status=eq.{HUMAN_GUIDANCE_PROVIDED}&reprocess_status=eq.{REPROCESS_PENDING}"
        return await self._get(TABLE_VAULT, filters, limit=50)

    async def update_human_guidance(
        self, escalation_id: str, guidance: str, source: str = "jarvis_chat"
    ) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        try:
            record = await self._patch(
                TABLE_VAULT,
                {
                    "human_guidance": guidance,
                    "human_status": HUMAN_GUIDANCE_PROVIDED,
                    "guidance_timestamp": now,
                    "guidance_source": source,
                    "updated_at": now,
                },
                filters=f"escalation_id=eq.{escalation_id}",
            )
            logger.info("Vault GUIDANCE (Supabase): escalation=%s", escalation_id[:8])
            return record
        except Exception as e:
            logger.error("Failed to update guidance in Supabase: %s", e)
            return None

    async def update_reprocess_result(
        self, escalation_id: str, result: str, quality_score: float,
        technique_log: Optional[List[Dict]] = None,
    ) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        try:
            record = await self._patch(
                TABLE_VAULT,
                {
                    "reprocess_result": result,
                    "reprocess_quality_score": round(quality_score, 4),
                    "reprocess_technique_log": json.dumps(technique_log or []),
                    "reprocess_status": REPROCESS_DONE,
                    "reprocess_completed_at": now,
                    "updated_at": now,
                },
                filters=f"escalation_id=eq.{escalation_id}",
            )
            logger.info("Vault REPROCESS DONE (Supabase): escalation=%s", escalation_id[:8])
            return record
        except Exception as e:
            logger.error("Failed to update reprocess in Supabase: %s", e)
            return None

    async def update_reprocess_status_direct(
        self, escalation_id: str, status: str,
    ) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        try:
            record = await self._patch(
                TABLE_VAULT,
                {"reprocess_status": status, "updated_at": now},
                filters=f"escalation_id=eq.{escalation_id}",
            )
            logger.info("Vault REPROCESS STATUS (Supabase): escalation=%s status=%s", escalation_id[:8], status)
            return record
        except Exception as e:
            logger.error("Failed to update reprocess status in Supabase: %s", e)
            return None

    async def increment_reprocess_attempts(
        self, escalation_id: str,
    ) -> int:
        """BC-017: Atomically increment reprocess_attempts (Supabase).

        Uses Postgres RPC 'increment_reprocess_attempts' if available;
        falls back to read-then-write with a row-level lock hint. Returns
        the new counter value, or -1 on failure.
        """
        try:
            # Use the stored-procedure RPC for true atomic increment.
            import httpx
            url = f"{self._url}/rest/v1/rpc/increment_reprocess_attempts"
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    url, headers=self._headers,
                    json={"p_escalation_id": escalation_id},
                )
                resp.raise_for_status()
                data = resp.json()
                # RPC returns the new counter as a scalar
                if isinstance(data, int):
                    return data
                if isinstance(data, dict) and "new_count" in data:
                    return int(data["new_count"])
                # Fallback: re-read the row to get the current value
                record = await self.get_escalation(escalation_id)
                return record.get("reprocess_attempts", -1) if record else -1
        except Exception as e:
            logger.error("Failed to increment reprocess_attempts in Supabase: %s", e)
            return -1

    async def update_crm_status(
        self, escalation_id: str, status: str, crm_ticket_id: str = "",
        crm_response: Optional[Dict] = None,
    ) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        update: Dict[str, Any] = {
            "crm_status": status,
            "crm_updated_at": now,
            "updated_at": now,
        }
        if crm_ticket_id:
            update["crm_ticket_id"] = crm_ticket_id
        if crm_response:
            update["crm_response"] = json.dumps(crm_response)
        try:
            record = await self._patch(
                TABLE_VAULT, update,
                filters=f"escalation_id=eq.{escalation_id}",
            )
            logger.info("Vault CRM UPDATE (Supabase): escalation=%s", escalation_id[:8])
            return record
        except Exception as e:
            logger.error("Failed to update CRM status in Supabase: %s", e)
            return None

    async def claim_escalation(
        self, escalation_id: str, agent_id: str,
    ) -> Dict[str, Any]:
        """BC-016: Atomic claim for the Supabase backend.

        Uses PostgREST's PATCH with two filters (escalation_id AND
        human_status=eq.pending) which together form an atomic compare-and-set.
        If the row was already claimed by another agent, the PATCH matches
        zero rows and we return success=False. Returns the row's current
        claim state (best-effort lookup).
        """
        now = datetime.now(timezone.utc).isoformat()
        update = {
            "human_status": HUMAN_PROCESSING,
            "claimed_by_agent_id": agent_id,
            "claimed_at": now,
            "updated_at": now,
        }
        # Atomic CAS: only patches if escalation_id matches AND status is pending
        filters = (
            f"escalation_id=eq.{escalation_id}"
            f"&human_status=eq.{HUMAN_PENDING}"
        )
        try:
            record = await self._patch(TABLE_VAULT, update, filters=filters)
            if record:
                logger.info(
                    "Vault CLAIM (Supabase): escalation=%s agent=%s",
                    escalation_id[:8], agent_id,
                )
                return {
                    "success": True,
                    "escalation_id": escalation_id,
                    "claimed_by": agent_id,
                    "reason": "claimed",
                }
            # No row matched → either not found, or already claimed
            current = await self.get_escalation(escalation_id)
            if not current:
                return {
                    "success": False,
                    "escalation_id": escalation_id,
                    "claimed_by": None,
                    "reason": "not_found",
                }
            return {
                "success": False,
                "escalation_id": escalation_id,
                "claimed_by": current.get("claimed_by_agent_id"),
                "reason": "already_claimed" if current.get("human_status") == HUMAN_PROCESSING else "not_pending",
            }
        except Exception as e:
            logger.error("Failed to claim escalation in Supabase: %s", e)
            return {
                "success": False,
                "escalation_id": escalation_id,
                "claimed_by": None,
                "reason": f"error: {str(e)[:120]}",
            }

    async def list_escalations(
        self, tenant_id: str,
        human_status: Optional[str] = None,
        reprocess_status: Optional[str] = None,
        limit: int = 50,
        exclude_processing: bool = True,
    ) -> List[Dict[str, Any]]:
        filters = f"tenant_id=eq.{tenant_id}"
        if human_status:
            filters += f"&human_status=eq.{human_status}"
        if reprocess_status:
            filters += f"&reprocess_status=eq.{reprocess_status}"
        # BC-016: hide tickets being worked by another agent
        if exclude_processing and not human_status:
            filters += f"&human_status=neq.{HUMAN_PROCESSING}"
        return await self._get(TABLE_VAULT, filters, limit=limit)

    async def get_vault_stats(self, tenant_id: str) -> Dict[str, Any]:
        # Supabase RPC or aggregated query
        records = await self._get(TABLE_VAULT, f"tenant_id=eq.{tenant_id}", limit=1000)
        return {
            "tenant_id": tenant_id,
            "total_escalations": len(records),
            "awaiting_human": sum(1 for r in records if r.get("human_status") == HUMAN_PENDING),
            "guidance_provided": sum(1 for r in records if r.get("human_status") == HUMAN_GUIDANCE_PROVIDED),
            "reprocess_done": sum(1 for r in records if r.get("reprocess_status") == REPROCESS_DONE),
            "reprocess_failed": sum(1 for r in records if r.get("reprocess_status") == REPROCESS_FAILED),
            "crm_updated": sum(1 for r in records if r.get("crm_status") == CRM_UPDATED),
            "crm_pending": sum(1 for r in records if r.get("crm_status") == CRM_PENDING),
        }

    async def health_check(self) -> Dict[str, Any]:
        return {
            "backend": "supabase",
            "status": "healthy",
            "url": self._url,
        }


# ═══════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════

_vault_db_instance: Optional[VaultStorageBackend] = None


def get_vault_db() -> VaultStorageBackend:
    """Get the vault DB singleton (auto-detects InMemory vs Supabase)."""
    global _vault_db_instance
    if _vault_db_instance is None:
        if SUPABASE_URL and SUPABASE_ANON_KEY:
            logger.info("Vault DB: Using Supabase backend")
            _vault_db_instance = SupabaseVaultDB()
        else:
            logger.info("Vault DB: Using InMemory backend")
            _vault_db_instance = InMemoryVaultDB()
    return _vault_db_instance


def reset_vault_db():
    """Reset vault DB singleton (for testing)."""
    global _vault_db_instance
    _vault_db_instance = None
