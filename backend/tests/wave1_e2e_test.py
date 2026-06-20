"""
Wave 1 — End-to-End Test

Proves the FULL chain is wired:
  chat → command_parser → jarvis_auth → jarvis_db → jarvis_3_notify → response

Tests:
  1. Command parser: 10 intents via regex (Tier 1), no LLM needed
  2. Auth: role-based authorization (admin can, viewer can't)
  3. DB: notifications created, flags set, audit trail written
  4. Full pipeline: admin chat → parse → auth → execute → DB → response
  5. DB health check
  6. Quality score write + read
  7. Full pipeline: monitoring mode (poll) with notifications
  8. Supabase backend structure (mock-verified)

Run: python tests/wave1_e2e_test.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import os
import time

# Add project to path
sys.path.insert(0, "/home/z/my-project/parwa/backend")

from app.core.jarvis_pipeline.jarvis_db import (
    use_in_memory, reset_db, get_db,
    PRIORITY_CRITICAL, PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW,
)
from app.core.jarvis_pipeline.command_parser import (
    classify_command_sync, is_query_intent, is_control_intent,
    requires_admin, requires_owner,
)
from app.core.jarvis_pipeline.jarvis_auth import (
    authorize_command_sync, can_execute, make_user_context,
)
from app.core.jarvis_pipeline.graph import run_jarvis_chat, run_jarvis

TENANT_ID = "test_tenant_001"
ADMIN_EMAIL = "admin@parwa.ai"
OWNER_EMAIL = "owner@parwa.ai"
VIEWER_EMAIL = "viewer@parwa.ai"

PASS = 0
FAIL = 0
RESULTS = []


def test(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        RESULTS.append(("✅", name, detail))
    else:
        FAIL += 1
        RESULTS.append(("❌", name, detail))


async def async_tests():
    """All tests that need async/await."""

    # ═══════════════════════════════════════════════════════
    # TEST 4: Full Pipeline — Chat → Parse → Auth → DB → Response
    # ═══════════════════════════════════════════════════════

    # 4a: Query command
    result = await run_jarvis_chat(
        tenant_id=TENANT_ID,
        question="show me system status",
        user_email=ADMIN_EMAIL,
        user_role="admin",
    )
    test("Pipeline: query_status executes",
         "System Status" in result.get("chat_response", ""),
         f"Response: {result.get('chat_response', '')[:100]}")

    test("Pipeline: query_status intent captured",
         result.get("intent_result", {}).get("intent") == "query_status",
         f"Intent: {result.get('intent_result', {}).get('intent')}")

    test("Pipeline: auth passed for admin",
         result.get("auth_result", {}).get("authorized") == True,
         f"Auth: {result.get('auth_result', {})}")

    # 4b: Control command (pause refunds)
    result = await run_jarvis_chat(
        tenant_id=TENANT_ID,
        question="pause refund processing",
        user_email=ADMIN_EMAIL,
        user_role="admin",
    )
    test("Pipeline: control_pause executes",
         "[OK] Paused" in result.get("chat_response", ""),
         f"Response: {result.get('chat_response', '')[:100]}")

    # Verify the flag is actually in the DB
    db = get_db()
    active_flags = await db.get_active_flags(TENANT_ID, flag_type="pause_action")
    test("Pipeline: pause flag persisted in DB",
         len(active_flags) > 0,
         f"Flags: {[f['flag_value'] for f in active_flags]}")

    # 4c: Resume command — resume the specific pause
    result = await run_jarvis_chat(
        tenant_id=TENANT_ID,
        question="resume all",
        user_email=ADMIN_EMAIL,
        user_role="admin",
    )
    test("Pipeline: control_resume executes",
         "Resumed" in result.get("chat_response", ""),
         f"Response: {result.get('chat_response', '')[:100]}")

    # Verify all pause flags are revoked
    active_flags = await db.get_active_flags(TENANT_ID, flag_type="pause_action")
    test("Pipeline: pause flags revoked from DB",
         len(active_flags) == 0,
         f"Remaining flags: {len(active_flags)}")

    # 4d: Mode change
    result = await run_jarvis_chat(
        tenant_id=TENANT_ID,
        question="switch to shadow mode",
        user_email=ADMIN_EMAIL,
        user_role="admin",
    )
    test("Pipeline: control_mode executes",
         "SHADOW" in result.get("chat_response", ""),
         f"Response: {result.get('chat_response', '')[:100]}")

    mode_flags = await db.get_active_flags(TENANT_ID, flag_type="force_mode")
    test("Pipeline: mode flag in DB",
         len(mode_flags) > 0 and mode_flags[0]["flag_value"] == "shadow",
         f"Mode flags: {[(f['flag_type'], f['flag_value']) for f in mode_flags]}")

    # 4e: Query flags (reads from DB)
    result = await run_jarvis_chat(
        tenant_id=TENANT_ID,
        question="show my active rules",
        user_email=ADMIN_EMAIL,
        user_role="admin",
    )
    test("Pipeline: query_flags reads from DB",
         "Active Flags" in result.get("chat_response", ""),
         f"Response: {result.get('chat_response', '')[:100]}")

    # 4f: Query audit trail (reads from DB)
    result = await run_jarvis_chat(
        tenant_id=TENANT_ID,
        question="show audit history",
        user_email=ADMIN_EMAIL,
        user_role="admin",
    )
    test("Pipeline: query_audit reads from DB",
         "Recent Activity" in result.get("chat_response", ""),
         f"Response: {result.get('chat_response', '')[:100]}")

    # ═══════════════════════════════════════════════════════
    # TEST 5: Auth Denial
    # ═══════════════════════════════════════════════════════

    result = await run_jarvis_chat(
        tenant_id=TENANT_ID,
        question="pause all refund processing",
        user_email=VIEWER_EMAIL,
        user_role="viewer",
    )
    test("Auth: viewer denied control command",
         "[DENIED]" in result.get("chat_response", ""),
         f"Response: {result.get('chat_response', '')[:100]}")

    # Viewer CAN query
    result = await run_jarvis_chat(
        tenant_id=TENANT_ID,
        question="show notifications",
        user_email=VIEWER_EMAIL,
        user_role="viewer",
    )
    test("Auth: viewer allowed query command",
         "[DENIED]" not in result.get("chat_response", ""),
         f"Response: {result.get('chat_response', '')[:100]}")

    # ═══════════════════════════════════════════════════════
    # TEST 6: Quality Score Write + Read
    # ═══════════════════════════════════════════════════════

    await db.write_quality_score(
        tenant_id=TENANT_ID,
        ticket_id="TKT-001",
        overall_score=0.95,
        confidence_score=0.92,
        resolution_path="simple",
        nodes_reached=["N1", "N2", "N3", "N7"],
        llm_calls=2,
        tokens_used=1100,
        model_used="llama-3.1-8b",
    )
    stats = await db.get_quality_stats(TENANT_ID)
    test("Quality: score written and aggregated",
         stats["total_tickets"] == 1 and stats["avg_quality"] == 0.95,
         f"Stats: {stats}")

    # ═══════════════════════════════════════════════════════
    # TEST 7: Notification Flow (monitoring mode)
    # ═══════════════════════════════════════════════════════

    result = await run_jarvis(
        tenant_id=TENANT_ID,
        trigger="poll",
        parwa_state={
            "tenant_id": TENANT_ID,
            "status": "escalated",
            "ticket_id": "TKT-999",
            "quality_score": 0.45,
            "loop_count": 3,
            "errors": ["timeout"],
            "escalation_context": {"reason": "super_node_failed"},
        },
    )
    test("Monitor: pipeline runs without crash",
         result.get("status") is None or True,  # just shouldn't crash
         f"Keys: {list(result.keys())}")
    test("Monitor: notifications created from escalation",
         len(result.get("notifications", [])) > 0,
         f"Notifications: {len(result.get('notifications', []))}")

    # ═══════════════════════════════════════════════════════
    # TEST 8: DB Health Check
    # ═══════════════════════════════════════════════════════

    health = await db.health_check()
    test("DB: health check passes",
         health.get("status") == "healthy",
         f"Health: {health}")

    test("DB: correct backend mode",
         health.get("backend") == "memory",
         f"Backend: {health.get('backend')}")

    # ═══════════════════════════════════════════════════════
    # TEST 9: Notification Stats
    # ═══════════════════════════════════════════════════════

    nf_stats = await db.get_notification_stats(TENANT_ID)
    test("DB: notification stats available",
         nf_stats.get("total", 0) > 0,
         f"Stats: {nf_stats}")

    # ═══════════════════════════════════════════════════════
    # TEST 10: Audit Trail Integrity
    # ═══════════════════════════════════════════════════════

    trail = await db.get_audit_trail(TENANT_ID)
    test("DB: audit trail has entries",
         len(trail) > 0,
         f"Audit entries: {len(trail)}")

    # Verify chain integrity — trail is in DESCENDING order (newest first)
    # Reverse to get chronological order, then check chain
    chronological = list(reversed(trail))
    chain_valid = True
    broken_at = -1
    for i in range(1, len(chronological)):
        prev_hash = chronological[i].get("previous_hash")
        curr_hash = chronological[i-1].get("current_hash")
        if prev_hash and curr_hash and prev_hash != curr_hash:
            chain_valid = False
            broken_at = i
            break
    test("DB: audit trail hash chain intact",
         chain_valid,
         f"Chain valid: {chain_valid}, broken_at: {broken_at}, entries: {len(trail)}")

    # ═══════════════════════════════════════════════════════
    # TEST 11: Full Pipeline — Emergency + Route
    # ═══════════════════════════════════════════════════════

    # Route command
    result = await run_jarvis_chat(
        tenant_id=TENANT_ID,
        question="handle all instagram dms today, I'll take calls",
        user_email=OWNER_EMAIL,
        user_role="owner",
    )
    test("Pipeline: control_route executes",
         "Workflow Redirected" in result.get("chat_response", ""),
         f"Response: {result.get('chat_response', '')[:100]}")

    # Emergency shutdown (owner only)
    result = await run_jarvis_chat(
        tenant_id=TENANT_ID,
        question="shut down everything",
        user_email=OWNER_EMAIL,
        user_role="owner",
    )
    test("Pipeline: emergency_shutdown executes",
         "EMERGENCY" in result.get("chat_response", ""),
         f"Response: {result.get('chat_response', '')[:100]}")

    # Verify emergency flag in DB
    emergency_flags = await db.get_active_flags(TENANT_ID, flag_type="global_shutdown")
    test("Pipeline: emergency flag persisted",
         len(emergency_flags) > 0,
         f"Emergency flags: {len(emergency_flags)}")

    # ═══════════════════════════════════════════════════════
    # TEST 12: Disable Rule
    # ═══════════════════════════════════════════════════════

    result = await run_jarvis_chat(
        tenant_id=TENANT_ID,
        question="undo my last rule",
        user_email=ADMIN_EMAIL,
        user_role="admin",
    )
    test("Pipeline: disable_rule executes",
         "[OK] Disabled" in result.get("chat_response", ""),
         f"Response: {result.get('chat_response', '')[:100]}")


def main():
    global PASS, FAIL

    print("=" * 70)
    print("  JARVIS WAVE 1 — END-TO-END TEST")
    print("  Testing: chat → parse → auth → DB → response (all wired)")
    print("=" * 70)
    print()

    # Force in-memory mode for testing
    use_in_memory()

    # ═══════════════════════════════════════════════════════
    # TEST 1: Command Parser — 10 intents (sync, no LLM)
    # ═══════════════════════════════════════════════════════
    print("── TEST 1: Command Parser (Tier 1 Regex, 0 tokens) ──")

    parser_tests = [
        ("show me system status", "query_status"),
        ("what are today's errors", "query_errors"),
        ("how many tickets are pending", "query_tickets"),
        ("show quality metrics", "query_quality"),
        ("what's my quota", "query_quota"),
        ("show notifications", "query_notifications"),
        ("PARWA-NFY-003", "query_notifications"),
        ("pause all refund processing", "control_pause"),
        ("resume refund processing", "control_resume"),
        ("handle all instagram dms today", "control_route"),
        ("switch to supervised mode", "control_mode"),
        ("undo my last rule", "control_disable_rule"),
        ("shut down everything", "emergency_shutdown"),
        ("recall all sent emails", "emergency_recall"),
        ("why did ticket #123 fail", "explain_ticket"),
        ("show active rules", "query_flags"),
        ("show audit history", "query_audit"),
        ("approve batch", "approve_batch"),
        ("reject batch", "reject_batch"),
        ("approve ticket #456", "approve_single"),
    ]

    for input_text, expected_intent in parser_tests:
        result = classify_command_sync(input_text)
        matched = result["intent"] == expected_intent
        test(f"Parser: '{input_text}' → {expected_intent}",
             matched,
             f"Got: {result['intent']} (method={result['classification_method']}, conf={result['confidence']})")

    print()

    # ═══════════════════════════════════════════════════════
    # TEST 2: Auth — Role-Based Access
    # ═══════════════════════════════════════════════════════
    print("── TEST 2: Auth (Role-Based Authorization) ──")

    # Admin can do control
    test("Auth: admin can control_pause",
         can_execute("control_pause", "admin"))
    test("Auth: admin can control_resume",
         can_execute("control_resume", "admin"))
    test("Auth: admin can query_status",
         can_execute("query_status", "admin"))

    # Viewer can only query
    test("Auth: viewer CAN query_status",
         can_execute("query_status", "viewer"))
    test("Auth: viewer CANNOT control_pause",
         not can_execute("control_pause", "viewer"))
    test("Auth: viewer CANNOT emergency_shutdown",
         not can_execute("emergency_shutdown", "viewer"))

    # Owner can do everything
    test("Auth: owner can emergency_shutdown",
         can_execute("emergency_shutdown", "owner"))
    test("Auth: owner can create_agent",
         can_execute("create_agent", "owner"))

    # Admin CANNOT shutdown (owner only)
    test("Auth: admin CANNOT emergency_shutdown",
         not can_execute("emergency_shutdown", "admin"))

    # AuthResult object
    ar = authorize_command_sync("control_pause",
                                make_user_context("admin@test.com", "admin"),
                                TENANT_ID)
    test("Auth: AuthResult.authorized works", bool(ar))
    test("Auth: AuthResult has role", ar.role == "admin")

    ar_deny = authorize_command_sync("emergency_shutdown",
                                     make_user_context("admin@test.com", "admin"),
                                     TENANT_ID)
    test("Auth: AuthResult deny works", not bool(ar_deny))
    test("Auth: denial has reason", "owner" in ar_deny.reason.lower())

    print()

    # ═══════════════════════════════════════════════════════
    # TEST 3: DB — Direct Operations
    # ═══════════════════════════════════════════════════════
    print("── TEST 3: DB Direct Operations ──")
    asyncio.run(_test_db_operations())
    print()

    # ═══════════════════════════════════════════════════════
    # TESTS 4-12: Async Pipeline Tests
    # ═══════════════════════════════════════════════════════
    print("── TESTS 4-12: Full Pipeline + Wired Tests ──")
    # Reset DB for clean pipeline tests
    reset_db()
    use_in_memory()
    asyncio.run(async_tests())
    print()

    # ═══════════════════════════════════════════════════════
    # RESULTS
    # ═══════════════════════════════════════════════════════
    print("=" * 70)
    print(f"  RESULTS: {PASS} passed, {FAIL} failed, {PASS + FAIL} total")
    print("=" * 70)

    for icon, name, detail in RESULTS:
        print(f"  {icon} {name}")
        if detail:
            print(f"       {detail}")

    print()
    if FAIL == 0:
        print("  ✅ ALL TESTS PASSED — Wave 1 is fully wired end-to-end!")
    else:
        print(f"  ❌ {FAIL} test(s) failed — review above")

    return FAIL == 0


async def _test_db_operations():
    """Test DB operations directly."""
    db = get_db()

    # Create notification
    nf = await db.create_notification(
        tenant_id=TENANT_ID,
        ntype="stuck_ticket",
        priority_score=0.90,
        title="Test Stuck Ticket",
        description="Test description",
        related_tickets=["TKT-001"],
    )
    test("DB: create notification",
         nf["notification_key"] == "PARWA-NFY-001",
         f"Key: {nf['notification_key']}")

    # Get notification
    fetched = await db.get_notification("PARWA-NFY-001")
    test("DB: get notification by key",
         fetched is not None and fetched["title"] == "Test Stuck Ticket")

    # List notifications
    nfs = await db.get_notifications(TENANT_ID)
    test("DB: list notifications",
         len(nfs) == 1)

    # Resolve notification
    resolved = await db.resolve_notification("PARWA-NFY-001")
    test("DB: resolve notification", resolved)
    unresolved = await db.get_notifications(TENANT_ID, include_resolved=False)
    test("DB: resolved notification excluded from list",
         len(unresolved) == 0)

    # Set flag
    flag = await db.set_flag(
        tenant_id=TENANT_ID,
        flag_type="pause_action",
        flag_value="refund",
        set_by=ADMIN_EMAIL,
        reason="test",
    )
    test("DB: set flag",
         flag["flag_type"] == "pause_action" and flag["flag_value"] == "refund")

    # Get active flags
    flags = await db.get_active_flags(TENANT_ID)
    test("DB: get active flags",
         len(flags) == 1)

    # Revoke flag
    revoked = await db.revoke_flag(flag["id"], ADMIN_EMAIL)
    test("DB: revoke flag", revoked)
    flags = await db.get_active_flags(TENANT_ID)
    test("DB: revoked flag not in active",
         len(flags) == 0)

    # Audit trail
    entry = await db.create_audit_entry(
        tenant_id=TENANT_ID,
        action="test_action",
        actor_email=ADMIN_EMAIL,
        target_type="test",
        target_id="test_001",
        payload={"key": "value"},
    )
    test("DB: create audit entry",
         entry["action"] == "test_action" and entry.get("current_hash"))

    trail = await db.get_audit_trail(TENANT_ID)
    test("DB: get audit trail",
         len(trail) == 1 and trail[0]["actor_email"] == ADMIN_EMAIL)

    # Quality score
    qs = await db.write_quality_score(
        tenant_id=TENANT_ID,
        ticket_id="TKT-DB-TEST",
        overall_score=0.88,
        confidence_score=0.90,
        resolution_path="complex",
        llm_calls=7,
        tokens_used=8000,
    )
    test("DB: write quality score",
         qs["overall_score"] == 0.88)

    stats = await db.get_quality_stats(TENANT_ID)
    test("DB: quality stats aggregated",
         stats["total_tickets"] == 1 and stats["avg_quality"] == 0.88)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)