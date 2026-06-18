"""
Wave 4 Build Script — Jarvis-PARWA Bidirectional Channel

This script applies all Wave 4 changes to the codebase:
1. jarvis_db.py — Add inbox table + training data methods to abstract, InMemory, Supabase
2. parwa_bridge.py — New bridge module: load_system_flags() + write quality/training
3. state_v2.py — Add system_flags, jarvis_guidance, quality_written fields
4. node_1_ingest_classify.py — Check global_shutdown at entry
5. node_2_smart_route.py — Check redirect_channel, force_mode, pause_action
6. node_3_knowledge_fetch.py — Read guidance flags for current ticket
7. node_5_act_verify.py — Check approval_override flags
8. node_6_quality_format.py — Write quality score to jarvis_db
9. node_8_super_node.py — Write to jarvis_inbox when stuck
10. graph_v2.py — Wire flag loading at graph entry
11. wave4_e2e_test.py — Comprehensive E2E test

Run: python /home/z/my-project/scripts/wave4_build.py
"""

import os
import re

BASE = "/home/z/my-project/parwa/backend/app/core"

# ───────────────────────────────────────────────────────
# 1. jarvis_db.py — Add jarvis_inbox table constant + abstract methods + InMemory + Supabase
# ───────────────────────────────────────────────────────

def patch_jarvis_db():
    db_path = os.path.join(BASE, "jarvis_pipeline/jarvis_db.py")
    with open(db_path) as f:
        content = f.read()

    # 1a. Add TABLE_INBOX constant after TABLE_BATCH_QUEUE
    if 'TABLE_INBOX' not in content:
        content = content.replace(
            'TABLE_BATCH_QUEUE = "jarvis_batch_queue"',
            'TABLE_BATCH_QUEUE = "jarvis_batch_queue"\nTABLE_INBOX = "jarvis_inbox"'
        )

    # 1b. Add abstract methods for inbox + training_data_record to StorageBackend
    inbox_abstract = '''
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
        ...'''

    # Insert before the Utility section
    if 'write_to_inbox' not in content:
        content = content.replace(
            '    # ── Utility ──────────────────────────────────────────────\n',
            inbox_abstract + '\n    # ── Utility ──────────────────────────────────────────────\n',
            1,  # only first occurrence (in abstract class)
        )

    # 1c. Add InMemory _inbox store and methods
    # Add _inbox to __init__
    if '_inbox' not in content.split('class InMemoryBackend')[1].split('class SupabaseBackend')[0]:
        content = content.replace(
            'self._outbox: List[Dict] = []  # Wave 3: outbox queue (recall/void)',
            'self._outbox: List[Dict] = []  # Wave 3: outbox queue (recall/void)\n        self._inbox: List[Dict] = []  # Wave 4: PARWA → Jarvis inbox\n        self._training_data_records: List[Dict] = []  # Wave 4: training data'
        )

    # Add InMemory write_to_inbox method - find the Utility section in InMemory
    inbox_inmemory = '''
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
        return sorted(records, key=lambda r: r["created_at"], reverse=True)[:limit]'''

    # Insert before the Utility section in InMemoryBackend
    # Find the right spot: look for the outbox status method then Utility
    if 'async def write_to_inbox' not in content:
        # Find the InMemory get_outbox_status method, insert after it
        idx = content.find('    async def get_notification_stats(self, tenant_id: str) -> Dict[str, Any]:')
        if idx > 0:
            # Find the previous method end
            # Insert before get_notification_stats
            content = content[:idx] + inbox_inmemory + '\n\n' + content[idx:]

    # 1d. Add Supabase inbox + training methods
    inbox_supabase = '''
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
        return await self._rest_get(TABLE_TRAINING_DATA, query)'''

    # Insert before the Utility section in SupabaseBackend
    if 'async def write_to_inbox' in content and content.count('async def write_to_inbox') < 2:
        # Find the Supabase get_notification_stats
        idx = content.find('    async def get_notification_stats(self, tenant_id: str) -> Dict[str, Any]:', content.find('class SupabaseBackend'))
        if idx > 0:
            content = content[:idx] + inbox_supabase + '\n\n' + content[idx:]

    with open(db_path, 'w') as f:
        f.write(content)
    print(f"  [OK] Patched jarvis_db.py — inbox + training_data methods")


# ───────────────────────────────────────────────────────
# 2. parwa_bridge.py — Bridge module for PARWA to read Jarvis flags
# ───────────────────────────────────────────────────────

BRIDGE_CODE = '''"""
PARWA-Jarvis Bridge — Wave 4

Provides:
  - load_system_flags(tenant_id) — called by PARWA nodes to get active Jarvis flags
  - write_quality_score_to_jarvis(state) — called by Node 6 after scoring
  - write_to_jarvis_inbox(state, stuck_reason, what_was_tried) — called by Node 8 when stuck
  - record_training_signal(...) — called when human approves/rejects/edit

All methods are async and use the Jarvis DB backend.
The bridge is the SINGLE point of contact — PARWA nodes never import jarvis_db directly.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("parwa.jarvis_bridge")

# Cache TTL: flags are cached for 5 seconds to avoid DB hits on every node
_FLAG_CACHE: Dict[str, Dict[str, Any]] = {}  # tenant_id -> {flags, loaded_at}
_FLAG_CACHE_TTL = 5.0


async def load_system_flags(tenant_id: str) -> Dict[str, Any]:
    """Load all active Jarvis system flags for a tenant.

    Returns a dict organized by flag_type for O(1) lookups:
    {
        "global_shutdown": True/False,
        "paused_actions": ["refund", "account_change"],
        "redirected_channels": {"instagram": "ai", "calls": "human"},
        "force_mode": "supervised",
        "approval_overrides": ["address_change", "plan_change"],
        "guidance": {"TKT-123": "Check Shopify order..."},
        "all_flags": [...],  # raw flags for debugging
    }

    Cached for 5 seconds per tenant.
    """
    now = time.time()
    cached = _FLAG_CACHE.get(tenant_id)

    # Return cached if fresh
    if cached and (now - cached["loaded_at"]) < _FLAG_CACHE_TTL:
        return cached["result"]

    # Load from DB
    from app.core.jarvis_pipeline.jarvis_db import get_db
    db = get_db()
    flags = await db.get_active_flags(tenant_id)

    result = {
        "global_shutdown": False,
        "paused_actions": [],
        "redirected_channels": {},
        "force_mode": None,
        "approval_overrides": [],
        "guidance": {},
        "all_flags": flags,
    }

    for flag in flags:
        ftype = flag.get("flag_type", "")
        fval = flag.get("flag_value", "")
        target_id = flag.get("target_id")

        if ftype == "global_shutdown":
            result["global_shutdown"] = True

        elif ftype == "pause_action":
            if fval not in result["paused_actions"]:
                result["paused_actions"].append(fval)

        elif ftype == "redirect_channel":
            # flag_value format: "channel:route_to" e.g. "instagram:ai"
            parts = fval.split(":", 1)
            if len(parts) == 2:
                result["redirected_channels"][parts[0]] = parts[1]

        elif ftype == "force_mode":
            result["force_mode"] = fval

        elif ftype == "approval_override":
            if fval not in result["approval_overrides"]:
                result["approval_overrides"].append(fval)

        elif ftype == "guidance":
            # target_id is the ticket_id for guidance flags
            if target_id:
                result["guidance"][target_id] = fval

    _FLAG_CACHE[tenant_id] = {"result": result, "loaded_at": now}
    return result


def invalidate_flag_cache(tenant_id: Optional[str] = None):
    """Invalidate flag cache (called after flag changes)."""
    if tenant_id:
        _FLAG_CACHE.pop(tenant_id, None)
    else:
        _FLAG_CACHE.clear()


async def write_quality_score_to_jarvis(
    tenant_id: str,
    ticket_id: str,
    quality_score: float,
    resolution_path: str = "",
    nodes_reached: Optional[List[str]] = None,
    llm_calls: int = 0,
    tokens_used: int = 0,
) -> Optional[Dict[str, Any]]:
    """Write quality score from PARWA Node 6 to Jarvis DB.

    Non-blocking. Failures are logged but don't affect pipeline flow.
    Returns the score record or None on failure.
    """
    try:
        from app.core.jarvis_pipeline.jarvis_db import get_db
        db = get_db()
        record = await db.write_quality_score(
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            overall_score=quality_score,
            resolution_path=resolution_path,
            nodes_reached=nodes_reached or [],
            llm_calls=llm_calls,
            tokens_used=tokens_used,
        )
        logger.info(
            "Quality score written: tenant=%s ticket=%s score=%.4f path=%s",
            tenant_id, ticket_id, quality_score, resolution_path,
        )
        return record
    except Exception as e:
        logger.warning("Failed to write quality score to Jarvis: %s", e)
        return None


async def write_to_jarvis_inbox(
    tenant_id: str,
    ticket_id: str,
    stuck_reason: str,
    quality_score: float,
    what_was_tried: str,
) -> Optional[Dict[str, Any]]:
    """PARWA writes to Jarvis inbox when stuck (Node 8 escalation).

    Non-blocking. Failures logged but don't affect pipeline.
    """
    try:
        from app.core.jarvis_pipeline.jarvis_db import get_db
        db = get_db()
        msg = await db.write_to_inbox(
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            stuck_reason=stuck_reason,
            quality_score=quality_score,
            what_was_tried=what_was_tried,
            inbox_type="parwa_stuck",
        )
        logger.info(
            "Inbox message written: tenant=%s ticket=%s reason=%s",
            tenant_id, ticket_id, stuck_reason,
        )
        return msg
    except Exception as e:
        logger.warning("Failed to write to Jarvis inbox: %s", e)
        return None


async def record_training_signal(
    tenant_id: str,
    ticket_id: str,
    signal_type: str,
    original_response: str = "",
    corrected_response: str = "",
    quality_score: float = 0.0,
    ticket_type: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Record training data from human approval/rejection/edit.

    signal_type: "approved", "rejected", "edited"
    """
    try:
        from app.core.jarvis_pipeline.jarvis_db import get_db
        db = get_db()
        record = await db.record_training_data(
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            signal_type=signal_type,
            original_response=original_response,
            corrected_response=corrected_response,
            quality_score=quality_score,
            ticket_type=ticket_type,
            metadata=metadata,
        )
        logger.info(
            "Training data recorded: tenant=%s ticket=%s signal=%s",
            tenant_id, ticket_id, signal_type,
        )
        return record
    except Exception as e:
        logger.warning("Failed to record training data: %s", e)
        return None
'''


def create_parwa_bridge():
    path = os.path.join(BASE, "parwa_pipeline/parwa_bridge.py")
    with open(path, 'w') as f:
        f.write(BRIDGE_CODE)
    print(f"  [OK] Created parwa_bridge.py")


# ───────────────────────────────────────────────────────
# 3. state_v2.py — Add system_flags + jarvis_guidance fields
# ───────────────────────────────────────────────────────

def patch_state_v2():
    path = os.path.join(BASE, "parwa_pipeline/state_v2.py")
    with open(path) as f:
        content = f.read()

    if 'system_flags' in content and 'jarvis_guidance' in content:
        print("  [SKIP] state_v2.py already has Wave 4 fields")
        return

    # Add after the OBSERVABILITY section
    new_fields = '''
    # ── WAVE 4: Jarvis Integration ────────────────────────────────
    system_flags: Dict[str, Any]          # loaded by graph entry, consumed by nodes
    jarvis_guidance: str                  # guidance text from Jarvis for this ticket (Node 3)
    quality_written_to_jarvis: bool       # True once Node 6 writes quality score
    inbox_message_id: Optional[str]       # ID of inbox message if Node 8 wrote to Jarvis
'''

    content = content.replace(
        '    # ── OBSERVABILITY ──────────────────────────────────────\n',
        '    # ── WAVE 4: Jarvis Integration ────────────────────────────────\n'
        '    system_flags: Dict[str, Any]          # loaded by graph entry, consumed by nodes\n'
        '    jarvis_guidance: str                  # guidance text from Jarvis for this ticket (Node 3)\n'
        '    quality_written_to_jarvis: bool       # True once Node 6 writes quality score\n'
        '    inbox_message_id: Optional[str]       # ID of inbox message if Node 8 wrote to Jarvis\n'
        '\n'
        '    # ── OBSERVABILITY ──────────────────────────────────────\n'
    )

    with open(path, 'w') as f:
        f.write(content)
    print(f"  [OK] Patched state_v2.py — Wave 4 fields added")


# ───────────────────────────────────────────────────────
# 4. node_1_ingest_classify.py — Check global_shutdown
# ───────────────────────────────────────────────────────

def patch_node_1():
    path = os.path.join(BASE, "parwa_pipeline/nodes/node_1_ingest_classify.py")
    with open(path) as f:
        content = f.read()

    if 'global_shutdown' in content:
        print("  [SKIP] node_1 already has shutdown check")
        return

    # Add shutdown check at the top of the main function, after the start timer
    shutdown_check = '''
    # ── Wave 4: Check Jarvis system flags (shutdown) ───────
    system_flags = state.get("system_flags", {})
    if system_flags.get("global_shutdown"):
        logger.warning("Node 1: GLOBAL SHUTDOWN active — rejecting ticket %s", state["ticket_id"])
        return {
            "status": "rejected",
            "final_response": "System is currently under maintenance. Your request cannot be processed at this time.",
            "technique_log": [{"node": 1, "technique": "JARVIS_SHUTDOWN_CHECK", "duration_ms": 0, "result_summary": "rejected_due_to_shutdown"}],
            "errors": [{"node": "node_1", "error": "global_shutdown_active", "details": "Ticket rejected due to emergency shutdown flag"}],
            "total_token_usage": state.get("total_token_usage", 0),
        }

'''

    # Insert after "start = time.time()" line
    content = content.replace(
        '    start = time.time()\n    query = state["query"]',
        '    start = time.time()' + shutdown_check + '    query = state["query"]'
    )

    with open(path, 'w') as f:
        f.write(content)
    print(f"  [OK] Patched node_1_ingest_classify.py — global_shutdown check")


# ───────────────────────────────────────────────────────
# 5. node_2_smart_route.py — Check redirect, mode, pause flags
# ───────────────────────────────────────────────────────

def patch_node_2():
    path = os.path.join(BASE, "parwa_pipeline/nodes/node_2_smart_route.py")
    with open(path) as f:
        content = f.read()

    if 'system_flags' in content and 'paused_actions' in content:
        print("  [SKIP] node_2 already has flag checks")
        return

    # Add flag checks after the start/log init, before Variant Registry
    flag_check = '''
    # ── Wave 4: Check Jarvis system flags ──────────────────
    system_flags = state.get("system_flags", {})

    # Check pause_action: if this action type is paused, reject
    paused_actions = system_flags.get("paused_actions", [])
    if action in paused_actions or "all" in paused_actions:
        logs.append({"node": 2, "technique": "JARVIS_PAUSE_CHECK", "duration_ms": 0, "result_summary": f"action={action} PAUSED"})
        logger.warning("Node 2: Action '%s' is paused by Jarvis for tenant %s", action, tenant_id)
        return {
            "route_decision": "simple_path",
            "current_path": "simple_path",
            "variant_tier": "parwa",
            "quota_remaining": {},
            "variant_capabilities": [],
            "status": "paused",
            "final_response": f"The action '{action}' is currently paused by your administrator. Your request has been noted but cannot be processed until the pause is lifted.",
            "technique_log": logs,
            "total_token_usage": state.get("total_token_usage", 0),
        }

    # Check redirect_channel: if this channel is redirected to human, override path
    channel = state.get("channel_type", "")
    redirected = system_flags.get("redirected_channels", {})
    if channel and channel in redirected:
        route_to = redirected[channel]
        logs.append({"node": 2, "technique": "JARVIS_REDIRECT_CHECK", "duration_ms": 0, "result_summary": f"channel={channel} redirected to {route_to}"})
        logger.info("Node 2: Channel '%s' redirected to '%s' by Jarvis", channel, route_to)
        if route_to == "human":
            return {
                "route_decision": "simple_path",
                "current_path": "simple_path",
                "variant_tier": "parwa",
                "quota_remaining": {},
                "variant_capabilities": [],
                "status": "escalated",
                "escalation_context": {"reason": f"Channel '{channel}' redirected to human by Jarvis"},
                "technique_log": logs,
                "total_token_usage": state.get("total_token_usage", 0),
            }

    # Check force_mode: if Jarvis forced a mode, log it for downstream
    force_mode = system_flags.get("force_mode")
    if force_mode:
        logs.append({"node": 2, "technique": "JARVIS_MODE_CHECK", "duration_ms": 0, "result_summary": f"mode={force_mode}"})

'''

    # Insert after "logs = []" in the main function
    content = content.replace(
        '    logs = []\n\n    # 1. Variant Registry check',
        '    logs = []\n' + flag_check + '\n    # 1. Variant Registry check'
    )

    with open(path, 'w') as f:
        f.write(content)
    print(f"  [OK] Patched node_2_smart_route.py — redirect/mode/pause checks")


# ───────────────────────────────────────────────────────
# 6. node_3_knowledge_fetch.py — Read guidance flags
# ───────────────────────────────────────────────────────

def patch_node_3():
    path = os.path.join(BASE, "parwa_pipeline/nodes/node_3_knowledge_fetch.py")
    with open(path) as f:
        content = f.read()

    if 'jarvis_guidance' in content:
        print("  [SKIP] node_3 already has guidance injection")
        return

    # Read the main function signature area
    guidance_code = '''
    # ── Wave 4: Inject Jarvis guidance for this ticket ─────
    system_flags = state.get("system_flags", {})
    guidance_map = system_flags.get("guidance", {})
    ticket_id = state.get("ticket_id", "")
    jarvis_guidance = guidance_map.get(ticket_id, "")
    logs = state.get("technique_log", [])  # We'll append to existing logs
    if jarvis_guidance:
        logs.append({"node": 3, "technique": "JARVIS_GUIDANCE", "duration_ms": 0,
                     "result_summary": f"guidance_len={len(jarvis_guidance)}"})

'''

    # Insert after the start time and query extraction
    # Find the main function and insert guidance check early
    content = content.replace(
        '    start = time.time()\n    query = state.get("query", "")',
        '    start = time.time()\n    query = state.get("query", "")' + guidance_code
    )

    # Also need to inject the guidance into knowledge_context at the end
    # Find where knowledge_context is returned and add guidance
    # Look for the return statement of the main function
    guidance_inject = '''
    # Wave 4: Inject Jarvis guidance as additional knowledge
    if jarvis_guidance:
        knowledge_docs.append({
            "source": "jarvis_guidance",
            "content": jarvis_guidance,
            "relevance": 1.0,
            "is_jarvis_guidance": True,
        })
        logger.info("Node 3: Injected Jarvis guidance for ticket %s (%d chars)", ticket_id, len(jarvis_guidance))

'''

    # Insert before the final return of node_3_knowledge_fetch
    # Find the return dict in the main function - it returns knowledge_context
    content = content.replace(
        '    return {\n        "knowledge_context": knowledge_docs,',
        guidance_inject + '    return {\n        "knowledge_context": knowledge_docs,',
        1  # only first occurrence
    )

    # Also add jarvis_guidance to the return
    if '"jarvis_guidance":' not in content:
        # Add to the return dict
        content = content.replace(
            '"knowledge_sufficient": knowledge_sufficient,\n        "knowledge_contradictory": knowledge_contradictory,',
            '"knowledge_sufficient": knowledge_sufficient,\n        "knowledge_contradictory": knowledge_contradictory,\n        "jarvis_guidance": jarvis_guidance,'
        )

    with open(path, 'w') as f:
        f.write(content)
    print(f"  [OK] Patched node_3_knowledge_fetch.py — guidance injection")


# ───────────────────────────────────────────────────────
# 7. node_5_act_verify.py — Check approval_override flags
# ───────────────────────────────────────────────────────

def patch_node_5():
    path = os.path.join(BASE, "parwa_pipeline/nodes/node_5_act_verify.py")
    with open(path) as f:
        content = f.read()

    if 'approval_overrides' in content:
        print("  [SKIP] node_5 already has approval override check")
        return

    # Add approval override check after the rule-based check
    approval_code = '''
    # ── Wave 4: Check Jarvis approval_overrides ─────────────
    system_flags = state.get("system_flags", {})
    approval_overrides = system_flags.get("approval_overrides", [])
    ticket_type = state.get("ticket_type", "")
    required_action = state.get("required_action", "")

    # If this action type has an approval override, auto-approve
    is_auto_approved = (
        required_action in approval_overrides
        or ticket_type in approval_overrides
        or "all" in approval_overrides
    )
    if is_auto_approved:
        logs.append({"node": 5, "technique": "JARVIS_APPROVAL_OVERRIDE", "duration_ms": 0,
                     "result_summary": f"auto_approved action={required_action} type={ticket_type}"})
        logger.info("Node 5: Auto-approved by Jarvis override: action=%s type=%s", required_action, ticket_type)

'''

    # Insert after ZeroShotValidator log entry
    content = content.replace(
        '    if zsv["flagged"]:\n        for flag in zsv["flags"]:\n            logs.append({"node": 5, "technique": "ZeroShotValidator", "duration_ms": 0, "result_summary": f"flag: {flag}"})\n',
        '    if zsv["flagged"]:\n        for flag in zsv["flags"]:\n            logs.append({"node": 5, "technique": "ZeroShotValidator", "duration_ms": 0, "result_summary": f"flag: {flag}"})\n\n' + approval_code
    )

    # Modify the UCB execute step to skip verification if auto-approved
    # Replace the UCB comment to include approval override note
    content = content.replace(
        '    # 7. UCB execute (mock — wired in Phase 7)\n    logs.append({"node": 5, "technique": "UCB", "duration_ms": 0, "result_summary": "action_executed"})',
        '    # 7. UCB execute (mock — wired in Phase 7)\n    logs.append({"node": 5, "technique": "UCB", "duration_ms": 0, "result_summary": f"action_executed auto_approved={is_auto_approved}"})'
    )

    with open(path, 'w') as f:
        f.write(content)
    print(f"  [OK] Patched node_5_act_verify.py — approval override check")


# ───────────────────────────────────────────────────────
# 8. node_6_quality_format.py — Write quality score to Jarvis
# ───────────────────────────────────────────────────────

def patch_node_6():
    path = os.path.join(BASE, "parwa_pipeline/nodes/node_6_quality_format.py")
    with open(path) as f:
        content = f.read()

    if 'write_quality_score_to_jarvis' in content:
        print("  [SKIP] node_6 already has quality write-back")
        return

    # Add import at the top (after existing imports)
    content = content.replace(
        'from app.core.parwa_pipeline.state_v2 import PipelineV2State',
        'from app.core.parwa_pipeline.state_v2 import PipelineV2State\nfrom app.core.parwa_pipeline.parwa_bridge import write_quality_score_to_jarvis'
    )

    # Add quality write-back before the final return
    writeback_code = '''
    # ── Wave 4: Write quality score to Jarvis DB ────────────
    try:
        await write_quality_score_to_jarvis(
            tenant_id=state.get("tenant_id", ""),
            ticket_id=state.get("ticket_id", ""),
            quality_score=quality_score,
            resolution_path=state.get("current_path", "unknown"),
            nodes_reached=[log.get("node") for log in logs if "node" in log],
            llm_calls=llm_calls,
            tokens_used=state.get("total_token_usage", 0),
        )
    except Exception as e:
        logger.warning("Wave 4 quality write-back failed (non-fatal): %s", e)

'''

    # Insert before the final return statement of node_6
    content = content.replace(
        '    return {\n        "quality_score": quality_score,\n        "quality_details": quality_result["details"],',
        writeback_code + '    return {\n        "quality_score": quality_score,\n        "quality_details": quality_result["details"],',
        1
    )

    with open(path, 'w') as f:
        f.write(content)
    print(f"  [OK] Patched node_6_quality_format.py — quality write-back")


# ───────────────────────────────────────────────────────
# 9. node_8_super_node.py — Write to Jarvis inbox when escalating
# ───────────────────────────────────────────────────────

def patch_node_8():
    path = os.path.join(BASE, "parwa_pipeline/nodes/node_8_super_node.py")
    with open(path) as f:
        content = f.read()

    if 'write_to_jarvis_inbox' in content:
        print("  [SKIP] node_8 already has inbox write")
        return

    # Add import
    content = content.replace(
        'from app.core.parwa_pipeline.state_v2 import PipelineV2State',
        'from app.core.parwa_pipeline.state_v2 import PipelineV2State\nfrom app.core.parwa_pipeline.parwa_bridge import write_to_jarvis_inbox'
    )

    # Add inbox write when escalating (after the notification_key block)
    inbox_code = '''
        # ── Wave 4: Write to Jarvis inbox ──────────────────
        try:
            attempts_summary = "; ".join(previous_answers[:2]) if previous_answers else "No previous answers"
            inbox_msg = await write_to_jarvis_inbox(
                tenant_id=state.get("tenant_id", ""),
                ticket_id=state.get("ticket_id", ""),
                stuck_reason=f"Super Node quality {super_quality:.2f} <= {QUALITY_SUPER_THRESHOLD} after all techniques",
                quality_score=super_quality,
                what_was_tried=f"Techniques: Reflexion, SelfConsistency(2), ToT, ReverseThinking, CRP, CoT + 11 non-LLM. Previous attempts: {attempts_summary[:500]}",
            )
            if inbox_msg:
                inbox_msg_id = inbox_msg.get("id")
                logs.append({"node": 8, "technique": "JARVIS_INBOX_WRITE", "duration_ms": 0,
                             "result_summary": f"inbox_id={inbox_msg_id}"})
        except Exception as e:
            logger.warning("Wave 4 inbox write failed (non-fatal): %s", e)

'''

    # Insert after the escalation_context block
    content = content.replace(
        '        logs.append({"node": 8, "technique": "Escalation", "duration_ms": 0, "result_summary": f"key={notification_key}"})\n',
        '        logs.append({"node": 8, "technique": "Escalation", "duration_ms": 0, "result_summary": f"key={notification_key}"})\n' + inbox_code
    )

    with open(path, 'w') as f:
        f.write(content)
    print(f"  [OK] Patched node_8_super_node.py — inbox write on escalation")


# ───────────────────────────────────────────────────────
# 10. graph_v2.py — Wire flag loading at graph entry
# ───────────────────────────────────────────────────────

def patch_graph_v2():
    path = os.path.join(BASE, "parwa_pipeline/graph_v2.py")
    with open(path) as f:
        content = f.read()

    if 'load_system_flags' in content:
        print("  [SKIP] graph_v2.py already has flag loading")
        return

    # Add a pre-graph node that loads system flags
    flag_node_code = '''

# ── Wave 4: Load Jarvis flags at graph entry ────────────────

async def _load_jarvis_flags(state: PipelineV2State) -> dict:
    """Load all active Jarvis system flags into state.

    Called as the first node in the graph so all subsequent nodes
    have access to the flags without individual DB calls.
    """
    from app.core.parwa_pipeline.parwa_bridge import load_system_flags

    tenant_id = state.get("tenant_id", "")
    flags = await load_system_flags(tenant_id)

    return {
        "system_flags": flags,
        "technique_log": [{"node": 0, "technique": "JARVIS_FLAG_LOAD", "duration_ms": 0,
                           "result_summary": f"flags={len(flags.get('all_flags', []))} shutdown={flags.get('global_shutdown')}"}],
    }

'''

    # Insert after the state updater for quality loop section
    content = content.replace(
        'def _finalize_simple(state: PipelineV2State) -> dict:',
        flag_node_code + 'def _finalize_simple(state: PipelineV2State) -> dict:'
    )

    # Change entry point from node_1 to _load_jarvis_flags
    content = content.replace(
        '    graph.set_entry_point("node_1")',
        '    graph.add_node("load_flags", _load_jarvis_flags)\n    graph.set_entry_point("load_flags")'
    )

    # Add edge from load_flags to node_1
    content = content.replace(
        '    # Node 1 → Node 2\n    graph.add_edge("node_1", "node_2")',
        '    # Load flags → Node 1\n    graph.add_edge("load_flags", "node_1")\n\n    # Node 1 → Node 2\n    graph.add_edge("node_1", "node_2")'
    )

    with open(path, 'w') as f:
        f.write(content)
    print(f"  [OK] Patched graph_v2.py — flag loading at graph entry")


# ───────────────────────────────────────────────────────
# 11. wave4_e2e_test.py — Comprehensive E2E test
# ───────────────────────────────────────────────────────

TEST_CODE = '''"""
Wave 4 E2E Test — Jarvis-PARWA Bidirectional Channel

Tests all 5 Wave 4 deliverables:
  4A: PARWA reads Jarvis flags (shutdown, pause, redirect, mode, approval_override)
  4B: PARWA writes to Jarvis inbox when stuck
  4C: Jarvis guidance injection in Node 3
  4D: Quality score write-back from Node 6
  4E: Training data collection

All tests use InMemory backend — no external services needed.
Run: python -m pytest backend/tests/wave4_e2e_test.py -v
"""

import asyncio
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.core.jarvis_pipeline.jarvis_db import reset_db, use_in_memory, get_db
from app.core.parwa_pipeline.parwa_bridge import (
    load_system_flags,
    write_quality_score_to_jarvis,
    write_to_jarvis_inbox,
    record_training_signal,
    invalidate_flag_cache,
)
from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline


TENANT = "wave4_test_tenant"


@pytest.fixture(autouse=True)
def _reset():
    """Reset DB and caches before each test."""
    reset_db()
    use_in_memory()
    invalidate_flag_cache(TENANT)
    yield
    reset_db()


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _run_graph(state: dict) -> dict:
    """Build and run the PARWA pipeline graph."""
    graph = build_parwa_pipeline()
    compiled = graph.compile()
    return _run(compiled.ainvoke(state))


# ═══════════════════════════════════════════════════════════════
# 4A: PARWA Reads Jarvis Flags
# ═══════════════════════════════════════════════════════════════

class Test4A_ParwaReadsFlags:
    """PARWA nodes must read and obey Jarvis system flags."""

    def test_4a_1_global_shutdown_rejects_ticket(self):
        """Node 1 should reject tickets when global_shutdown is active."""
        # Set shutdown flag
        db = get_db()
        _run(db.set_flag(
            tenant_id=TENANT, flag_type="global_shutdown",
            flag_value="emergency", set_by="admin@test.com",
            reason="Emergency shutdown test",
        ))
        invalidate_flag_cache(TENANT)

        # Run a ticket through the pipeline
        result = _run_graph({
            "ticket_id": "TKT-SHUTDOWN-1",
            "tenant_id": TENANT,
            "query": "I want a refund of $50",
            "channel_type": "email",
            "customer_context": {},
            "metadata": {},
        })

        # Should be rejected immediately
        assert result["status"] == "rejected", f"Expected rejected, got {result['status']}"
        assert "shutdown" in result.get("final_response", "").lower() or "maintenance" in result.get("final_response", "").lower()

    def test_4a_2_pause_action_blocks_refund(self):
        """Node 2 should block paused action types."""
        db = get_db()
        _run(db.set_flag(
            tenant_id=TENANT, flag_type="pause_action",
            flag_value="refund", set_by="admin@test.com",
            reason="Pause refunds test",
        ))
        invalidate_flag_cache(TENANT)

        result = _run_graph({
            "ticket_id": "TKT-PAUSE-1",
            "tenant_id": TENANT,
            "query": "I want a refund of $100",
            "channel_type": "email",
            "customer_context": {},
            "metadata": {},
        })

        # Should be paused
        assert result.get("status") == "paused", f"Expected paused, got {result.get('status')}"

    def test_4a_3_pause_all_blocks_everything(self):
        """Node 2 should block all actions when 'all' is paused."""
        db = get_db()
        _run(db.set_flag(
            tenant_id=TENANT, flag_type="pause_action",
            flag_value="all", set_by="admin@test.com",
            reason="Pause all test",
        ))
        invalidate_flag_cache(TENANT)

        result = _run_graph({
            "ticket_id": "TKT-PAUSE-ALL",
            "tenant_id": TENANT,
            "query": "What is my account balance?",
            "channel_type": "email",
            "customer_context": {},
            "metadata": {},
        })

        assert result.get("status") == "paused"

    def test_4a_4_redirect_channel_to_human(self):
        """Node 2 should escalate when channel is redirected to human."""
        db = get_db()
        _run(db.set_flag(
            tenant_id=TENANT, flag_type="redirect_channel",
            flag_value="email:human", set_by="admin@test.com",
            reason="Redirect email to human",
        ))
        invalidate_flag_cache(TENANT)

        result = _run_graph({
            "ticket_id": "TKT-REDIRECT-1",
            "tenant_id": TENANT,
            "query": "Help me with my order",
            "channel_type": "email",
            "customer_context": {},
            "metadata": {},
        })

        # Should be escalated to human
        assert result.get("status") == "escalated", f"Expected escalated, got {result.get('status')}"

    def test_4a_5_force_mode_logged(self):
        """Node 2 should log force_mode flag in technique_log."""
        db = get_db()
        _run(db.set_flag(
            tenant_id=TENANT, flag_type="force_mode",
            flag_value="supervised", set_by="admin@test.com",
            reason="Force supervised mode",
        ))
        invalidate_flag_cache(TENANT)

        result = _run_graph({
            "ticket_id": "TKT-MODE-1",
            "tenant_id": TENANT,
            "query": "How do I reset my password?",
            "channel_type": "chat",
            "customer_context": {},
            "metadata": {},
        })

        # Check that force mode was logged
        tech_log = result.get("technique_log", [])
        mode_checks = [t for t in tech_log if t.get("technique") == "JARVIS_MODE_CHECK"]
        assert len(mode_checks) >= 1, "Force mode check should be in technique_log"

    def test_4a_6_approval_override_in_node5(self):
        """Node 5 should detect approval override flags."""
        db = get_db()
        _run(db.set_flag(
            tenant_id=TENANT, flag_type="approval_override",
            flag_value="execute_refund", set_by="admin@test.com",
            reason="Auto-approve refunds",
        ))
        invalidate_flag_cache(TENANT)

        result = _run_graph({
            "ticket_id": "TKT-APPROVAL-1",
            "tenant_id": TENANT,
            "query": "Please refund my $25 purchase",
            "channel_type": "email",
            "customer_context": {"account_tier": "paid"},
            "metadata": {},
        })

        # Check that approval override was detected in technique_log
        tech_log = result.get("technique_log", [])
        approval_checks = [t for t in tech_log if t.get("technique") == "JARVIS_APPROVAL_OVERRIDE"]
        assert len(approval_checks) >= 1, "Approval override check should be in technique_log"

    def test_4a_7_no_flags_normal_flow(self):
        """Without any flags, pipeline should work normally."""
        result = _run_graph({
            "ticket_id": "TKT-NORMAL-1",
            "tenant_id": TENANT,
            "query": "What is your return policy?",
            "channel_type": "chat",
            "customer_context": {},
            "metadata": {},
        })

        # Should resolve normally
        assert result.get("status") in ("resolved", "stuck"), f"Expected resolved/stuck, got {result.get('status')}"
        # Should have gone through the full pipeline
        tech_log = result.get("technique_log", [])
        nodes_hit = set(t.get("node") for t in tech_log)
        assert 1 in nodes_hit, "Node 1 should be in technique_log"


# ═══════════════════════════════════════════════════════════════
# 4B: PARWA Writes to Jarvis Inbox
# ═══════════════════════════════════════════════════════════════

class Test4B_InboxCommunication:
    """PARWA → Jarvis communication via inbox."""

    def test_4b_1_write_to_inbox_direct(self):
        """Direct inbox write via bridge works."""
        msg = _run(write_to_jarvis_inbox(
            tenant_id=TENANT,
            ticket_id="TKT-INBOX-1",
            stuck_reason="Quality too low after 3 attempts",
            quality_score=0.45,
            what_was_tried="Reflexion, SelfConsistency, ToT, CRP",
        ))

        assert msg is not None
        assert msg["ticket_id"] == "TKT-INBOX-1"
        assert msg["status"] == "pending"
        assert msg["inbox_type"] == "parwa_stuck"
        assert msg["id"] is not None

    def test_4b_2_read_inbox_messages(self):
        """Jarvis can read inbox messages."""
        db = get_db()
        _run(db.write_to_inbox(
            tenant_id=TENANT,
            ticket_id="TKT-INBOX-2",
            stuck_reason="Complex billing dispute",
            quality_score=0.60,
            what_was_tried="Standard reasoning failed",
        ))

        messages = _run(db.get_inbox_messages(TENANT))
        assert len(messages) >= 1
        assert messages[0]["ticket_id"] == "TKT-INBOX-2"
        assert messages[0]["status"] == "pending"

    def test_4b_3_resolve_inbox_message(self):
        """Jarvis can mark inbox message as resolved."""
        db = get_db()
        msg = _run(db.write_to_inbox(
            tenant_id=TENANT,
            ticket_id="TKT-INBOX-3",
            stuck_reason="Need human review",
            quality_score=0.30,
            what_was_tried="All techniques exhausted",
        ))

        resolved = _run(db.resolve_inbox_message(msg["id"]))
        assert resolved is True

        # Should no longer appear in pending
        pending = _run(db.get_inbox_messages(TENANT, include_resolved=False))
        assert not any(m["id"] == msg["id"] for m in pending)

    def test_4b_4_inbox_filters_by_tenant(self):
        """Inbox messages are tenant-scoped."""
        db = get_db()
        _run(db.write_to_inbox(
            tenant_id="other_tenant",
            ticket_id="TKT-OTHER-1",
            stuck_reason="Other tenant issue",
            quality_score=0.5,
            what_was_tried="N/A",
        ))

        messages = _run(db.get_inbox_messages(TENANT))
        assert not any(m["tenant_id"] == "other_tenant" for m in messages)


# ═══════════════════════════════════════════════════════════════
# 4C: Jarvis Guidance Injection
# ═══════════════════════════════════════════════════════════════

class Test4C_GuidanceInjection:
    """Jarvis writes guidance flags, Node 3 injects them."""

    def test_4c_1_guidance_injected_into_knowledge(self):
        """Node 3 should inject Jarvis guidance into knowledge_context."""
        db = get_db()
        # Write a guidance flag for a specific ticket
        _run(db.set_flag(
            tenant_id=TENANT,
            flag_type="guidance",
            flag_value="Check Shopify order #1234 — customer already received replacement per ticket TKT-850",
            set_by="jarvis_auto",
            target_id="TKT-GUIDE-1",
            reason="Auto-guidance from Jarvis",
        ))
        invalidate_flag_cache(TENANT)

        result = _run_graph({
            "ticket_id": "TKT-GUIDE-1",
            "tenant_id": TENANT,
            "query": "Where is my refund for order #1234?",
            "channel_type": "email",
            "customer_context": {},
            "metadata": {},
        })

        # Check that guidance was loaded and injected
        jarvis_guidance = result.get("jarvis_guidance", "")
        assert len(jarvis_guidance) > 0, "Jarvis guidance should be in state"
        assert "Shopify" in jarvis_guidance or "replacement" in jarvis_guidance

        # Check technique_log for guidance injection
        tech_log = result.get("technique_log", [])
        guidance_logs = [t for t in tech_log if t.get("technique") == "JARVIS_GUIDANCE"]
        assert len(guidance_logs) >= 1, "Guidance injection should be in technique_log"

    def test_4c_2_no_guidance_for_unmatched_ticket(self):
        """Node 3 should not inject guidance for tickets without guidance."""
        db = get_db()
        _run(db.set_flag(
            tenant_id=TENANT,
            flag_type="guidance",
            flag_value="Some guidance",
            set_by="jarvis_auto",
            target_id="TKT-OTHER-999",  # Different ticket
            reason="Test",
        ))
        invalidate_flag_cache(TENANT)

        result = _run_graph({
            "ticket_id": "TKT-GUIDE-2",
            "tenant_id": TENANT,
            "query": "What is the pricing?",
            "channel_type": "chat",
            "customer_context": {},
            "metadata": {},
        })

        jarvis_guidance = result.get("jarvis_guidance", "")
        assert len(jarvis_guidance) == 0, "No guidance should be injected for unmatched ticket"


# ═══════════════════════════════════════════════════════════════
# 4D: Quality Score Write-Back
# ═══════════════════════════════════════════════════════════════

class Test4D_QualityWriteBack:
    """Node 6 writes quality scores to Jarvis DB."""

    def test_4d_1_quality_score_written_after_pipeline(self):
        """After a normal pipeline run, quality score should be in Jarvis DB."""
        db = get_db()

        # Run a simple ticket through
        result = _run_graph({
            "ticket_id": "TKT-QWB-1",
            "tenant_id": TENANT,
            "query": "What is your refund policy?",
            "channel_type": "chat",
            "customer_context": {},
            "metadata": {},
        })

        # Check that quality score was written to DB
        stats = _run(db.get_quality_stats(TENANT))
        assert stats["total_tickets"] >= 1, f"Expected >=1 quality score, got {stats['total_tickets']}"

    def test_4d_2_direct_quality_write(self):
        """Direct quality write via bridge works."""
        record = _run(write_quality_score_to_jarvis(
            tenant_id=TENANT,
            ticket_id="TKT-QWB-2",
            quality_score=0.95,
            resolution_path="simple",
            nodes_reached=["1", "2", "3", "7"],
            llm_calls=1,
            tokens_used=500,
        ))

        assert record is not None
        assert record["ticket_id"] == "TKT-QWB-2"
        assert record["overall_score"] == 0.95

    def test_4d_3_quality_stats_aggregation(self):
        """Quality stats should aggregate correctly."""
        db = get_db()

        # Write multiple scores
        for i, score in enumerate([0.90, 0.85, 0.95, 0.92]):
            _run(db.write_quality_score(
                tenant_id=TENANT,
                ticket_id=f"TKT-STATS-{i}",
                overall_score=score,
                resolution_path="complex" if i % 2 == 0 else "simple",
            ))

        stats = _run(db.get_quality_stats(TENANT))
        assert stats["total_tickets"] >= 4
        assert 0.88 <= stats["avg_quality"] <= 0.93  # avg of 0.90, 0.85, 0.95, 0.92 = 0.905


# ═══════════════════════════════════════════════════════════════
# 4E: Training Data Collection
# ═══════════════════════════════════════════════════════════════

class Test4E_TrainingDataCollection:
    """Training data from human approval/rejection/edit."""

    def test_4e_1_record_approval(self):
        """Positive training signal from human approval."""
        record = _run(record_training_signal(
            tenant_id=TENANT,
            ticket_id="TKT-TRAIN-1",
            signal_type="approved",
            original_response="Your refund of $50 has been processed.",
            quality_score=0.92,
            ticket_type="refund_request",
        ))

        assert record is not None
        assert record["signal_type"] == "approved"
        assert record["ticket_id"] == "TKT-TRAIN-1"

    def test_4e_2_record_rejection_with_correction(self):
        """Negative training signal with human correction."""
        record = _run(record_training_signal(
            tenant_id=TENANT,
            ticket_id="TKT-TRAIN-2",
            signal_type="rejected",
            original_response="We cannot help you with this.",
            corrected_response="I apologize for the inconvenience. Let me look into this further and get back to you within 24 hours.",
            quality_score=0.45,
            ticket_type="complaint",
        ))

        assert record["signal_type"] == "rejected"
        assert len(record["corrected_response"]) > 0

    def test_4e_3_record_edit(self):
        """Training signal from human editing AI draft."""
        record = _run(record_training_signal(
            tenant_id=TENANT,
            ticket_id="TKT-TRAIN-3",
            signal_type="edited",
            original_response="Refund approved.",
            corrected_response="Great news! Your refund of $25.99 has been approved and will appear on your statement within 5-7 business days.",
            quality_score=0.70,
            ticket_type="refund_request",
            metadata={"edit_reason": "too_brief"},
        ))

        assert record["signal_type"] == "edited"
        assert record["metadata"].get("edit_reason") == "too_brief"

    def test_4e_4_retrieve_training_data(self):
        """Can retrieve training data from DB."""
        db = get_db()
        _run(db.record_training_data(
            tenant_id=TENANT,
            ticket_id="TKT-TRAIN-4",
            signal_type="approved",
            quality_score=0.88,
        ))

        records = _run(db.get_training_data(TENANT))
        assert len(records) >= 1
        assert records[0]["signal_type"] == "approved"

    def test_4e_5_filter_training_by_signal_type(self):
        """Can filter training data by signal type."""
        db = get_db()
        _run(db.record_training_data(tenant_id=TENANT, ticket_id="TKT-F1", signal_type="approved"))
        _run(db.record_training_data(tenant_id=TENANT, ticket_id="TKT-F2", signal_type="rejected"))
        _run(db.record_training_data(tenant_id=TENANT, ticket_id="TKT-F3", signal_type="approved"))

        approved = _run(db.get_training_data(TENANT, signal_type="approved"))
        assert all(r["signal_type"] == "approved" for r in approved)
        assert len(approved) >= 2


# ═══════════════════════════════════════════════════════════════
# INTEGRATION: Full E2E — Flag Set → Pipeline Obeys
# ═══════════════════════════════════════════════════════════════

class Test4_Integration:
    """Full E2E: Jarvis sets flag → PARWA obeys → verify in DB."""

    def test_integration_pause_refund_then_resume(self):
        """Jarvis pauses refunds → ticket gets paused → Jarvis resumes → ticket flows."""
        db = get_db()

        # 1. Pause refunds
        _run(db.set_flag(
            tenant_id=TENANT, flag_type="pause_action",
            flag_value="refund", set_by="admin@test.com",
        ))
        invalidate_flag_cache(TENANT)

        result_paused = _run_graph({
            "ticket_id": "TKT-INT-1",
            "tenant_id": TENANT,
            "query": "I need a refund of $75",
            "channel_type": "email",
            "customer_context": {},
            "metadata": {},
        })
        assert result_paused.get("status") == "paused"

        # 2. Resume refunds (revoke the pause)
        flags = _run(db.get_active_flags(TENANT, flag_type="pause_action"))
        for f in flags:
            _run(db.revoke_flag(f["id"], revoked_by="admin@test.com"))
        invalidate_flag_cache(TENANT)

        # 3. Run same query again — should flow normally
        result_normal = _run_graph({
            "ticket_id": "TKT-INT-2",
            "tenant_id": TENANT,
            "query": "I need a refund of $75",
            "channel_type": "email",
            "customer_context": {"account_tier": "paid"},
            "metadata": {},
        })
        assert result_normal.get("status") in ("resolved", "stuck")

    def test_integration_full_cycle_with_training(self):
        """Full cycle: pipeline resolves → quality written → human approves → training recorded."""
        db = get_db()

        # 1. Run pipeline
        result = _run_graph({
            "ticket_id": "TKT-CYCLE-1",
            "tenant_id": TENANT,
            "query": "What is your return policy for electronics?",
            "channel_type": "chat",
            "customer_context": {},
            "metadata": {},
        })

        # 2. Verify quality was written
        stats = _run(db.get_quality_stats(TENANT))
        assert stats["total_tickets"] >= 1

        # 3. Human approves the response
        training = _run(record_training_signal(
            tenant_id=TENANT,
            ticket_id="TKT-CYCLE-1",
            signal_type="approved",
            original_response=result.get("final_response", result.get("formatted_response", "")),
            quality_score=result.get("quality_score", 0),
            ticket_type=result.get("ticket_type", ""),
        ))
        assert training is not None

        # 4. Verify training data is retrievable
        training_data = _run(db.get_training_data(TENANT, signal_type="approved"))
        assert any(t["ticket_id"] == "TKT-CYCLE-1" for t in training_data)

    def test_integration_shutdown_overrides_everything(self):
        """Global shutdown should reject even simple info queries."""
        db = get_db()
        _run(db.set_flag(
            tenant_id=TENANT, flag_type="global_shutdown",
            flag_value="emergency", set_by="admin@test.com",
        ))
        invalidate_flag_cache(TENANT)

        result = _run_graph({
            "ticket_id": "TKT-SHUTDOWN-2",
            "tenant_id": TENANT,
            "query": "What are your business hours?",
            "channel_type": "chat",
            "customer_context": {},
            "metadata": {},
        })

        assert result["status"] == "rejected"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''


def create_test_file():
    path = "/home/z/my-project/parwa/backend/tests/wave4_e2e_test.py"
    with open(path, 'w') as f:
        f.write(TEST_CODE)
    print(f"  [OK] Created wave4_e2e_test.py")


# ───────────────────────────────────────────────────────
# MAIN
# ───────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("WAVE 4 BUILD — Jarvis-PARWA Bidirectional Channel")
    print("=" * 60)
    print()
    print("[1/8] Patching jarvis_db.py...")
    patch_jarvis_db()
    print()
    print("[2/8] Creating parwa_bridge.py...")
    create_parwa_bridge()
    print()
    print("[3/8] Patching state_v2.py...")
    patch_state_v2()
    print()
    print("[4/8] Patching node_1_ingest_classify.py...")
    patch_node_1()
    print()
    print("[5/8] Patching node_2_smart_route.py...")
    patch_node_2()
    print()
    print("[6/8] Patching node_3_knowledge_fetch.py...")
    patch_node_3()
    print()
    print("[7/8] Patching node_5_act_verify.py...")
    patch_node_5()
    print()
    print("[8a] Patching node_6_quality_format.py...")
    patch_node_6()
    print()
    print("[8b] Patching node_8_super_node.py...")
    patch_node_8()
    print()
    print("[9] Patching graph_v2.py...")
    patch_graph_v2()
    print()
    print("[10] Creating wave4_e2e_test.py...")
    create_test_file()
    print()
    print("=" * 60)
    print("WAVE 4 BUILD COMPLETE")
    print("=" * 60)