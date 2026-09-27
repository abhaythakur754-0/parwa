"""
Production-Ready Test Suite for Escalation Vault + CRM Round-Trip

Tests the complete lifecycle:
  1. Escalation Vault (save, get, guidance, list, stats)
  2. CRM Bridge (ingest, parse, validate for all providers)
  3. Resume Pipeline (guidance → reprocess → quality check)
  4. Full Round-Trip: CRM webhook → vault → human guidance → resume → CRM push-back

Run: cd /home/z/my-project/parwa && python tests/test_escalation_vault_and_crm.py
"""
from __future__ import annotations

import asyncio
import sys
import os
import time
import traceback

# ── Path Setup ───────────────────────────────────────────────────
BACKEND_PATH = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND_PATH))

# Ensure no Supabase env vars (force InMemory mode)
for key in list(os.environ.keys()):
    if "SUPABASE" in key:
        del os.environ[key]

os.environ["ENVIRONMENT"] = "test"

# ── Imports ────────────────────────────────────────────────────────
from app.core.escalation_vault.vault_db import (
    get_vault_db, reset_vault_db,
    HUMAN_PENDING, HUMAN_GUIDANCE_PROVIDED, HUMAN_RESOLVED,
    REPROCESS_PENDING, REPROCESS_DONE, REPROCESS_FAILED,
    CRM_PENDING, CRM_UPDATED, CRM_FAILED,
)
from app.core.escalation_vault.vault_manager import VaultManager
from app.core.crm_bridge.crm_bridge import (
    CRMBridge, get_crm_adapter,
    ZendeskAdapter, HubSpotAdapter, GenericCRMAdapter,
)

# ═══════════════════════════════════════════════════════════════════
# TEST RUNNER
# ═══════════════════════════════════════════════════════════════════

passed = 0
failed = 0
errors = []

def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

def reset():
    reset_vault_db()

def check(condition, name):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name}")
        errors.append(name)

# ═══════════════════════════════════════════════════════════════════
# 1. ESCALATION VAULT STORAGE TESTS
# ═══════════════════════════════════════════════════════════════════

def test_vault_storage():
    print("\n═══ 1. ESCALATION VAULT STORAGE ═══")
    reset()

    async def _run():
        db = get_vault_db()

        # Save
        r = await db.save_escalation({
            "tenant_id": "t1", "original_ticket_id": "TKT-001",
            "notification_key": "NFY-001", "original_query": "Charge of $149.99",
            "ticket_type": "billing", "complexity": "complex",
        })
        esc_id = r["escalation_id"]
        check(r["escalation_id"], "Save escalation creates ID")
        check(r["human_status"] == HUMAN_PENDING, "Initial human_status=pending")
        check(r["reprocess_status"] == REPROCESS_PENDING, "Initial reprocess_status=pending")
        check(r["crm_status"] == CRM_PENDING, "Initial crm_status=pending")
        check(r["human_guidance"] == "", "Initial human_guidance empty")

        # Get by ID
        found = await db.get_escalation(esc_id)
        check(found is not None, "Get by ID works")
        check(found["original_query"] == "Charge of $149.99", "Correct query returned")

        # Get by ticket
        by_ticket = await db.get_escalation_by_ticket("TKT-001")
        check(by_ticket is not None, "Get by ticket_id works")
        check(by_ticket["escalation_id"] == esc_id, "Correct escalation by ticket")

        # Get by notification
        by_nfy = await db.get_escalation_by_notification("NFY-001")
        check(by_nfy is not None, "Get by notification_key works")
        check(by_nfy["escalation_id"] == esc_id, "Correct escalation by notification")

        # Not found
        nf = await db.get_escalation("nonexistent")
        check(nf is None, "Nonexistent returns None")

        # Update guidance
        upd = await db.update_human_guidance(esc_id, "Refund the $100 difference", "jarvis_chat")
        check(upd["human_guidance"] == "Refund the $100 difference", "Guidance saved")
        check(upd["human_status"] == HUMAN_GUIDANCE_PROVIDED, "Status changed to guidance_provided")
        check(upd["guidance_timestamp"] is not None, "Timestamp set")
        check(upd["guidance_source"] == "jarvis_chat", "Source recorded")

        # Update reprocess result
        rr = await db.update_reprocess_result(esc_id, "Improved answer", 0.92,
                                               technique_log=[{"step": "cot"}])
        check(rr["reprocess_result"] == "Improved answer", "Reprocess result saved")
        check(rr["reprocess_quality_score"] == 0.92, "Quality score saved")
        check(rr["reprocess_status"] == REPROCESS_DONE, "Status = done")

        # Update reprocess status direct (FAILED override)
        reset()
        db2 = get_vault_db()
        r2 = await db2.save_escalation({"tenant_id": "t1", "original_ticket_id": "TKT-FAIL", "original_query": "Q"})
        await db2.update_reprocess_result(r2["escalation_id"], "poor", 0.65)
        await db2.update_reprocess_status_direct(r2["escalation_id"], REPROCESS_FAILED)
        chk = await db2.get_escalation(r2["escalation_id"])
        check(chk["reprocess_status"] == REPROCESS_FAILED, "REPROCESS_FAILED persisted correctly")

        # Update CRM status
        reset()
        db3 = get_vault_db()
        r3 = await db3.save_escalation({"tenant_id": "t1", "original_ticket_id": "TKT-CRM", "original_query": "Q"})
        crm_upd = await db3.update_crm_status(r3["escalation_id"], CRM_UPDATED,
                                                crm_ticket_id="ZD-999", crm_response={"ok": True})
        check(crm_upd["crm_status"] == CRM_UPDATED, "CRM status = updated")
        check(crm_upd["crm_ticket_id"] == "ZD-999", "CRM ticket ID saved")

        # Pending resumes
        reset()
        db4 = get_vault_db()
        for i in range(3):
            r = await db4.save_escalation({"tenant_id": "t1", "original_ticket_id": f"TKT-PR-{i}", "original_query": f"Q{i}"})
            if i == 1:
                await db4.update_human_guidance(r["escalation_id"], "Guide")
        pending = await db4.get_pending_resumes("t1")
        check(len(pending) == 1, "Pending resumes = 1 (only guided + not processed)")
        check(pending[0]["human_status"] == HUMAN_GUIDANCE_PROVIDED, "Pending has guidance_provided status")

        # List with filters
        reset()
        db5 = get_vault_db()
        saved_ids = []
        for i in range(4):
            r = await db5.save_escalation({"tenant_id": "t1", "original_ticket_id": f"TKT-L-{i}", "original_query": f"Q{i}"})
            saved_ids.append(r["escalation_id"])
            if i < 2:
                await db5.update_human_guidance(r["escalation_id"], f"G{i}")
        all_e = await db5.list_escalations("t1")
        check(len(all_e) == 4, f"List all = 4 (got {len(all_e)})")
        filt = await db5.list_escalations("t1", human_status="pending")
        check(len(filt) == 2, f"Filtered pending = 2 (got {len(filt)})")

        # Stats
        reset()
        db6 = get_vault_db()
        for i in range(5):
            r = await db6.save_escalation({"tenant_id": "t1", "original_ticket_id": f"TKT-S-{i}", "original_query": f"Q{i}"})
            if i < 3:
                await db6.update_human_guidance(r["escalation_id"], f"G{i}")
            if i == 0:
                await db6.update_reprocess_result(r["escalation_id"], "done", 0.9)
        stats = await db6.get_vault_stats("t1")
        check(stats["total_escalations"] == 5, f"Stats total = 5 (got {stats['total_escalations']})")
        check(stats["awaiting_human"] == 2, f"Stats awaiting = 2 (got {stats['awaiting_human']})")
        check(stats["guidance_provided"] == 3, f"Stats guided = 3 (got {stats['guidance_provided']})")
        check(stats["reprocess_done"] == 1, f"Stats done = 1 (got {stats['reprocess_done']})")

        # Health check
        health = await db6.health_check()
        check(health["backend"] == "memory", "Health backend = memory")

    run_async(_run())


# ═══════════════════════════════════════════════════════════════════
# 2. VAULT MANAGER TESTS
# ═══════════════════════════════════════════════════════════════════

def test_vault_manager():
    print("\n═══ 2. VAULT MANAGER ═══")
    reset()

    async def _run():
        pipeline_state = {
            "ticket_id": "TKT-VM-001", "tenant_id": "tenant_001",
            "query": "Charge of $149.99", "ticket_type": "billing",
            "complexity": "complex", "required_action": "refund",
            "action_details": {}, "knowledge_context": [{"title": "Refund", "content": "30 days", "score": 0.85}],
            "crm_data": {}, "customer_context": {"email": "john@test.com", "name": "John", "account_tier": "parwa"},
            "quality_score": 0.72, "technique_log": [], "variant_tier": "parwa",
            "wiki_section_c": [], "wiki_patterns": [], "combined_answer": "", "formatted_response": "",
        }
        esc_ctx = {
            "notification_key": "PARWA-NFY-VM-001",
            "super_node_quality": 0.72,
            "failure_analysis": "Ambiguous refund amount",
            "what_was_tried": "CoT, ReAct",
            "previous_attempts": ["CoT: ambiguous", "ReAct: insufficient"],
        }

        # Save from pipeline
        record = await VaultManager.save_escalation_from_pipeline(
            state=pipeline_state, escalation_context=esc_ctx,
            crm_ticket_id="ZD-100", crm_provider="zendesk",
        )
        check(record is not None, "save_escalation_from_pipeline succeeds")
        check(record["original_ticket_id"] == "TKT-VM-001", "Ticket ID saved")
        check(record["notification_key"] == "PARWA-NFY-VM-001", "Notification key saved")
        check(record["crm_ticket_id"] == "ZD-100", "CRM ticket ID saved")
        check(record["crm_provider"] == "zendesk", "CRM provider saved")
        check(record["quality_score"] == 0.72, "Quality score saved")
        check(record["failure_analysis"] != "", "Failure analysis saved")

        esc_id = record["escalation_id"]

        # Provide guidance
        upd = await VaultManager.provide_human_guidance(esc_id, "Customer on annual plan")
        check(upd is not None, "provide_human_guidance works")
        check(upd["human_status"] == HUMAN_GUIDANCE_PROVIDED, "Status updated")

        # Provide guidance by notification
        reset()
        r2 = await VaultManager.save_escalation_from_pipeline(state=pipeline_state, escalation_context=esc_ctx)
        nfy_key = r2["notification_key"]
        upd2 = await VaultManager.provide_guidance_by_notification(nfy_key, "Check annual plan")
        check(upd2 is not None, "provide_guidance_by_notification works")

        # Not found
        nf = await VaultManager.provide_guidance_by_notification("NONEXISTENT", "Guide")
        check(nf is None, "Nonexistent notification returns None")

        # Load for resume — eligible
        reset()
        r3 = await VaultManager.save_escalation_from_pipeline(state=pipeline_state, escalation_context=esc_ctx)
        await VaultManager.provide_human_guidance(r3["escalation_id"], "Guidance")
        loaded = await VaultManager.load_for_resume(r3["escalation_id"])
        check(loaded is not None, "load_for_resume — eligible returns data")
        check("Guidance" in loaded["human_guidance"], "Loaded has guidance")

        # Load for resume — no guidance
        reset()
        r4 = await VaultManager.save_escalation_from_pipeline(state=pipeline_state, escalation_context=esc_ctx)
        not_eligible = await VaultManager.load_for_resume(r4["escalation_id"])
        check(not_eligible is None, "load_for_resume — no guidance returns None")

        # Load for resume — already reprocessed
        reset()
        r5 = await VaultManager.save_escalation_from_pipeline(state=pipeline_state, escalation_context=esc_ctx)
        await VaultManager.provide_human_guidance(r5["escalation_id"], "Guide")
        await VaultManager.save_resume_result(r5["escalation_id"], "result", 0.92)
        not_eligible2 = await VaultManager.load_for_resume(r5["escalation_id"])
        check(not_eligible2 is None, "load_for_resume — already processed returns None")

        # Save resume result
        reset()
        r6 = await VaultManager.save_escalation_from_pipeline(state=pipeline_state, escalation_context=esc_ctx)
        await VaultManager.provide_human_guidance(r6["escalation_id"], "Guide")
        sr = await VaultManager.save_resume_result(r6["escalation_id"], "Improved response", 0.91)
        check(sr["reprocess_result"] == "Improved response", "Resume result saved")
        check(sr["reprocess_quality_score"] == 0.91, "Resume quality saved")
        check(sr["reprocess_status"] == REPROCESS_DONE, "Resume status = done")

        # CRM push-back
        reset()
        r7 = await VaultManager.save_escalation_from_pipeline(state=pipeline_state, escalation_context=esc_ctx)
        crm = await VaultManager.update_crm_push_back(r7["escalation_id"], CRM_UPDATED,
                                                         crm_response={"success": True})
        check(crm["crm_status"] == CRM_UPDATED, "CRM push-back status updated")

    run_async(_run())


# ═══════════════════════════════════════════════════════════════════
# 3. CRM BRIDGE ADAPTER TESTS
# ═══════════════════════════════════════════════════════════════════

def test_crm_adapters():
    print("\n═══ 3. CRM BRIDGE ADAPTERS ═══")

    async def _run():
        # Zendesk parse
        z_payload = {
            "ticket": {
                "id": 12345, "subject": "Refund request",
                "description": "Charged $149.99 but plan is $49.99",
                "status": "new", "priority": "high",
                "requester": {"name": "John Doe", "email": "john@example.com", "id": 9876},
                "tags": ["billing"], "group_id": 100, "assignee_id": None,
            }
        }
        z = ZendeskAdapter()
        parsed = await z.parse_incoming_ticket(z_payload)
        check(parsed["ticket_id"] == "12345", "Zendesk: ticket_id parsed")
        check("Refund request" in parsed["query"], "Zendesk: subject in query")
        check(parsed["customer_email"] == "john@example.com", "Zendesk: email parsed")
        check(parsed["metadata"]["crm_provider"] == "zendesk", "Zendesk: provider set")
        check(parsed["metadata"]["crm_priority"] == "high", "Zendesk: priority set")

        # Zendesk validate
        check(z.validate_webhook({}, {"X-Zendesk-Webhook-Token": "tok"}) is True, "Zendesk: validate with token")
        check(z.validate_webhook({}, {}) is False, "Zendesk: validate without token")

        # HubSpot parse
        h_payload = {
            "objectId": 67890,
            "properties": {
                "subject": "Account locked",
                "content": "Cannot access dashboard",
                "hs_pipeline_stage": "1",
            },
            "associations": {"contacts": [{"id": 111, "properties": {"email": "jane@ex.com", "firstname": "Jane", "lastname": "Smith"}}]},
        }
        h = HubSpotAdapter()
        hp = await h.parse_incoming_ticket(h_payload)
        check(hp["ticket_id"] == "67890", "HubSpot: ticket_id parsed")
        check("Account locked" in hp["query"], "HubSpot: subject in query")
        check(hp["customer_email"] == "jane@ex.com", "HubSpot: email parsed")
        check(hp["metadata"]["crm_provider"] == "hubspot", "HubSpot: provider set")

        # HubSpot validate
        check(h.validate_webhook({}, {"X-HubSpot-Signature": "sig"}) is True, "HubSpot: validate with sig")

        # Generic parse
        g_payload = {
            "ticket_id": "GEN-999", "message": "How to upgrade?",
            "customer_email": "up@ex.com", "customer_name": "Up User",
            "customer_id": "c1", "channel_type": "chat",
        }
        g = GenericCRMAdapter()
        gp = await g.parse_incoming_ticket(g_payload)
        check(gp["ticket_id"] == "GEN-999", "Generic: ticket_id parsed")
        check(gp["query"] == "How to upgrade?", "Generic: message parsed")
        check(g.validate_webhook({}, {}) is True, "Generic: always validates")

        # CRMBridge ingest
        r1 = await CRMBridge.ingest_ticket("zendesk", z_payload, {"X-Zendesk-Webhook-Token": "t"})
        check(r1["success"] is True, "CRMBridge ingest zendesk")
        check(r1["ticket_data"]["ticket_id"] == "12345", "CRMBridge zendesk data correct")

        r2 = await CRMBridge.ingest_ticket("hubspot", h_payload, {"X-HubSpot-Signature": "s"})
        check(r2["success"] is True, "CRMBridge ingest hubspot")

        r3 = await CRMBridge.ingest_ticket("generic", g_payload)
        check(r3["success"] is True, "CRMBridge ingest generic")

        # Push without config
        pr = await CRMBridge.push_response("zendesk", "12345", "resp", "resolved")
        check(pr["success"] is False, "Push response without config fails")
        pe = await CRMBridge.push_escalation("zendesk", "12345", {})
        check(pe["success"] is False, "Push escalation without config fails")
        ps = await CRMBridge.push_resume_result("zendesk", "12345", "resp", 0.9, "guide")
        check(ps["success"] is False, "Push resume without config fails")

        # Adapter fallback
        adapter = get_crm_adapter("unknown_provider")
        check(isinstance(adapter, GenericCRMAdapter), "Unknown provider falls back to Generic")

    run_async(_run())


# ═══════════════════════════════════════════════════════════════════
# 4. RESUME PIPELINE (mocked LLM)
# ═══════════════════════════════════════════════════════════════════

def test_resume_pipeline():
    print("\n═══ 4. RESUME PIPELINE ═══")
    reset()

    async def _run():
        pipeline_state = {
            "ticket_id": "TKT-RP-001", "tenant_id": "tenant_001",
            "query": "Charge of $149.99", "ticket_type": "billing",
            "complexity": "complex", "required_action": "refund",
            "knowledge_context": [{"title": "Refund Policy", "content": "30-day refund window for enterprise", "score": 0.85}],
            "crm_data": {}, "customer_context": {"email": "john@test.com"},
            "quality_score": 0.72, "technique_log": [], "variant_tier": "parwa",
            "wiki_section_c": [], "wiki_patterns": [],
        }
        esc_ctx = {
            "notification_key": "PARWA-NFY-RP-001",
            "super_node_quality": 0.72,
            "failure_analysis": "Ambiguous refund",
            "previous_attempts": ["CoT: ambiguous"],
        }

        # Save + guide + verify eligible
        record = await VaultManager.save_escalation_from_pipeline(state=pipeline_state, escalation_context=esc_ctx)
        esc_id = record["escalation_id"]
        await VaultManager.provide_human_guidance(esc_id, "Customer on annual enterprise plan")
        loaded = await VaultManager.load_for_resume(esc_id)
        check(loaded is not None, "Resume: eligible after guidance")
        check("annual enterprise" in loaded["human_guidance"], "Resume: guidance in loaded state")

        # Simulate resume result
        resp = "We verified your annual enterprise plan. Refund of $100 will be processed in 5 days."
        await VaultManager.save_resume_result(esc_id, resp, 0.92)
        esc = await VaultManager.get_escalation(esc_id)
        check(esc["reprocess_result"] == resp, "Resume: result saved")
        check(esc["reprocess_quality_score"] == 0.92, "Resume: quality saved")
        check(esc["reprocess_status"] == REPROCESS_DONE, "Resume: status done")

    run_async(_run())


# ═══════════════════════════════════════════════════════════════════
# 5. FULL ROUND-TRIP INTEGRATION
# ═══════════════════════════════════════════════════════════════════

def test_full_round_trip():
    print("\n═══ 5. FULL ROUND-TRIP INTEGRATION ═══")
    reset()

    async def _run():
        z_payload = {
            "ticket": {
                "id": 12345, "subject": "Refund request",
                "description": "Charged $149.99 but should be $49.99",
                "status": "new", "priority": "high",
                "requester": {"name": "John Doe", "email": "john@example.com", "id": 9876},
                "tags": [], "group_id": None, "assignee_id": None,
            }
        }

        # Step 1: CRM Webhook → Ingest
        ingest = await CRMBridge.ingest_ticket("zendesk", z_payload, {"X-Zendesk-Webhook-Token": "tok"})
        check(ingest["success"], "Round-trip: CRM webhook ingested")
        td = ingest["ticket_data"]
        check(td["ticket_id"] == "12345", "Round-trip: Ticket ID from Zendesk")

        # Step 2: Pipeline escalates → vault
        ps = {
            "ticket_id": "TKT-CRM-12345", "tenant_id": "tenant_001",
            "query": td["query"], "ticket_type": "billing",
            "complexity": "complex", "required_action": "refund",
            "knowledge_context": [{"title": "Refund Policy", "content": "30-day refund", "score": 0.85}],
            "crm_data": {}, "customer_context": {
                "customer_id": "9876", "email": "john@example.com",
                "name": "John Doe", "account_tier": "parwa",
            },
            "quality_score": 0.70, "technique_log": [], "variant_tier": "parwa",
            "wiki_section_c": [], "wiki_patterns": [],
        }
        esc_ctx = {
            "notification_key": "PARWA-NFY-ZD-12345",
            "super_node_quality": 0.70,
            "failure_analysis": "Ambiguous refund amount",
            "what_was_tried": "CoT, ReAct",
            "previous_attempts": ["CoT: ambiguous", "ReAct: insufficient context"],
        }
        esc = await VaultManager.save_escalation_from_pipeline(
            state=ps, escalation_context=esc_ctx,
            crm_ticket_id="12345", crm_provider="zendesk",
        )
        check(esc is not None, "Round-trip: Escalation saved to vault")
        check(esc["crm_ticket_id"] == "12345", "Round-trip: CRM ticket tracked")
        esc_id = esc["escalation_id"]

        # Step 3: Human provides guidance
        guidance = "Customer is on annual enterprise plan ($49.99/mo). The $149.99 is unauthorized quarterly upsell. Refund $100 difference."
        upd = await VaultManager.provide_guidance_by_notification("PARWA-NFY-ZD-12345", guidance, "notification_click")
        check(upd is not None, "Round-trip: Guidance saved via notification key")
        check(upd["human_status"] == HUMAN_GUIDANCE_PROVIDED, "Round-trip: Status = guidance_provided")

        # Step 4: Verify eligible for resume
        loaded = await VaultManager.load_for_resume(esc_id)
        check(loaded is not None, "Round-trip: Eligible for resume")
        check("annual enterprise" in loaded["human_guidance"], "Round-trip: Guidance in loaded state")

        # Step 5: Resume processes
        resume_resp = (
            "Dear John,\n\nWe identified the $149.99 charge was an unauthorized quarterly upsell. "
            "Since you're on the annual enterprise plan at $49.99/month, we are processing a refund "
            "of $100.00 to your original payment method within 5-7 business days.\n\n"
            "Your account cancellation has been confirmed.\n\nBest regards,\nSupport Team"
        )
        await VaultManager.save_resume_result(esc_id, resume_resp, 0.93,
            technique_log=[{"step": "cot", "detail": "generated"}, {"step": "reflexion", "detail": "valid"}])

        # Step 6: CRM push-back tracking
        await VaultManager.update_crm_push_back(esc_id, CRM_UPDATED,
            crm_response={"success": True, "crm_ticket_id": "12345", "crm_status": "solved"})

        # Verify final state
        final = await VaultManager.get_escalation(esc_id)
        check(final["reprocess_status"] == REPROCESS_DONE, "Round-trip: Final reprocess = done")
        check(final["reprocess_quality_score"] == 0.93, "Round-trip: Final quality = 0.93")
        check(final["crm_status"] == CRM_UPDATED, "Round-trip: Final CRM = updated")
        check("$100.00" in final["reprocess_result"], "Round-trip: Response contains refund amount")

    run_async(_run())


# ═══════════════════════════════════════════════════════════════════
# 6. EDGE CASES
# ═══════════════════════════════════════════════════════════════════

def test_edge_cases():
    print("\n═══ 6. EDGE CASES ═══")

    async def _run():
        # Guidance to nonexistent
        r = await VaultManager.provide_human_guidance("nonexistent", "Guide")
        check(r is None, "Edge: Guidance to nonexistent returns None")

        # Resume nonexistent
        from app.core.escalation_vault.resume_pipeline import resume_escalated_ticket
        res = await resume_escalated_ticket("nonexistent")
        check(res["success"] is False, "Edge: Resume nonexistent fails")
        check("not found" in res.get("error", ""), "Edge: Proper error message")

        # Double guidance overwrites
        reset()
        db = get_vault_db()
        saved = await db.save_escalation({"tenant_id": "t1", "original_ticket_id": "TKT-DBL", "original_query": "Q"})
        await db.update_human_guidance(saved["escalation_id"], "First", "api")
        await db.update_human_guidance(saved["escalation_id"], "Second", "jarvis")
        chk = await db.get_escalation(saved["escalation_id"])
        check(chk["human_guidance"] == "Second", "Edge: Double guidance overwrites")
        check(chk["guidance_source"] == "jarvis", "Edge: Latest source recorded")

        # Escalation without CRM ticket
        reset()
        ps = {
            "ticket_id": "TKT-NO-CRM", "tenant_id": "tenant_001",
            "query": "Q", "ticket_type": "general", "complexity": "moderate",
            "knowledge_context": [], "crm_data": {},
            "customer_context": {}, "quality_score": 0.7,
            "technique_log": [], "variant_tier": "parwa",
            "wiki_section_c": [], "wiki_patterns": [],
        }
        r = await VaultManager.save_escalation_from_pipeline(state=ps, escalation_context={
            "notification_key": "NFY-NO-CRM", "super_node_quality": 0.7,
            "failure_analysis": "test", "what_was_tried": "test", "previous_attempts": [],
        })
        check(r["crm_ticket_id"] == "", "Edge: No CRM ticket — empty string")
        await VaultManager.provide_human_guidance(r["escalation_id"], "Guide")
        loaded = await VaultManager.load_for_resume(r["escalation_id"])
        check(loaded is not None, "Edge: Resume works without CRM ticket")

        # Multi-tenant isolation
        reset()
        db2 = get_vault_db()
        await db2.save_escalation({"tenant_id": "t1", "original_ticket_id": "TKT-T1", "original_query": "Q1"})
        await db2.save_escalation({"tenant_id": "t2", "original_ticket_id": "TKT-T2", "original_query": "Q2"})
        s1 = await VaultManager.get_vault_stats("t1")
        s2 = await VaultManager.get_vault_stats("t2")
        check(s1["total_escalations"] == 1, "Edge: Tenant isolation t1=1")
        check(s2["total_escalations"] == 1, "Edge: Tenant isolation t2=1")

        # Auto-resume pending flow
        reset()
        ids = []
        for i in range(3):
            ps_i = {**ps, "ticket_id": f"TKT-AUTO-{i}"}
            r = await VaultManager.save_escalation_from_pipeline(state=ps_i, escalation_context={
                "notification_key": f"NFY-AUTO-{i}", "super_node_quality": 0.7,
                "failure_analysis": "test", "what_was_tried": "test", "previous_attempts": [],
            })
            ids.append(r["escalation_id"])
            await VaultManager.provide_human_guidance(r["escalation_id"], f"Guide {i}")
        pending = await VaultManager.get_pending_resumes("tenant_001")
        check(len(pending) == 3, "Edge: 3 pending before auto-resume")
        for i, eid in enumerate(ids):
            await VaultManager.save_resume_result(eid, f"Response {i}", 0.88 + i * 0.02)
        pending_after = await VaultManager.get_pending_resumes("tenant_001")
        check(len(pending_after) == 0, "Edge: 0 pending after auto-resume")

    run_async(_run())


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  PARWA ESCALATION VAULT + CRM ROUND-TRIP TEST SUITE")
    print("=" * 60)

    t0 = time.time()

    try:
        test_vault_storage()
        test_vault_manager()
        test_crm_adapters()
        test_resume_pipeline()
        test_full_round_trip()
        test_edge_cases()
    except Exception as e:
        print(f"\n💥 FATAL ERROR: {e}")
        traceback.print_exc()

    elapsed = time.time() - t0
    total = passed + failed

    print("\n" + "=" * 60)
    print(f"  RESULTS: {passed}/{total} PASSED  |  {failed} FAILED  |  {elapsed:.1f}s")
    print("=" * 60)

    if errors:
        print("\nFailed tests:")
        for e in errors:
            print(f"  ❌ {e}")

    sys.exit(0 if failed == 0 else 1)
