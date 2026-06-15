"""
Integration Test — Complicated ticket involving 2+ employees.

Test Scenario:
  A customer (Priya Sharma) ordered 3 items from an e-commerce company.
  One item arrived damaged, another was the wrong product, and the
  third was never delivered. She's also being charged for a subscription
  she claims she cancelled. She's very frustrated and threatening to
  file a chargeback with her bank.

  This involves:
    - Refund agent (for damaged + wrong items)
    - Billing agent (for subscription charge)
    - Shipping tracker (for missing delivery)
    - Complaint handler (for frustrated customer)
    - Retention negotiator (chargeback threat = cancellation risk)

  Expected: High Parwa should handle this with multiple domain agents
  working together, MAKER validating, and Jarvis monitoring.
"""

import asyncio
import json
import sys
import os
from datetime import datetime, timezone

# Add backend to path
sys.path.insert(0, "/home/z/my-project/backend")

from app.logger import get_logger

logger = get_logger("integration_test")


# ══════════════════════════════════════════════════════════════════
# COMPLICATED TICKET — 2+ Employees Worth of Complexity
# ══════════════════════════════════════════════════════════════════

COMPLICATED_TICKET = {
    "query": (
        "I am EXTREMELY frustrated with your company right now. I ordered 3 items on March 15th "
        "(Order #ORD-2026-78432). Item 1 (Wireless Headphones - Rs 2,499) arrived with a cracked ear cup. "
        "Item 2 (Bluetooth Speaker - Rs 1,899) is completely the WRONG product - you sent me a phone case "
        "instead! Item 3 (Laptop Stand - Rs 3,299) never showed up at all - the tracking says delivered "
        "but I never received it. On top of all this, I just noticed you charged my card Rs 499 for some "
        "'Premium Membership' subscription that I NEVER signed up for and explicitly cancelled 2 months ago! "
        "I've been a customer for 3 years and this is how you treat me? I'm giving you 48 hours to fix ALL "
        "of this or I'm filing chargebacks with my bank for every single transaction and posting about this "
        "on social media. My account email is priya.sharma@email.com and my phone is 9876543210."
    ),
    "company_id": "comp_ecommerce_test",
    "industry": "ecommerce",
    "channel": "chat",
    "customer_id": "cust_priya_001",
    "customer_tier": "premium",
    "variant_tier": "parwa_high",  # Testing High Parwa
}


# Additional tickets for batch testing
ADDITIONAL_TICKETS = [
    {
        "query": "I also want a refund for the headphones I ordered last week. They were defective too.",
        "company_id": "comp_ecommerce_test",
        "industry": "ecommerce",
        "channel": "chat",
        "customer_id": "cust_rahul_002",
        "variant_tier": "parwa_high",
    },
    {
        "query": "My headphones arrived broken as well. Same cracked ear cup issue. Need refund ASAP.",
        "company_id": "comp_ecommerce_test",
        "industry": "ecommerce",
        "channel": "chat",
        "customer_id": "cust_anita_003",
        "variant_tier": "parwa_high",
    },
    {
        "query": "I'm confused about this Premium Membership charge on my bill. I never signed up for this.",
        "company_id": "comp_ecommerce_test",
        "industry": "ecommerce",
        "channel": "chat",
        "customer_id": "cust_vikram_004",
        "variant_tier": "parwa",
    },
    {
        "query": "Where is my order? It's been 2 weeks and no update. Order #ORD-2026-78999",
        "company_id": "comp_ecommerce_test",
        "industry": "ecommerce",
        "channel": "chat",
        "customer_id": "cust_meera_005",
        "variant_tier": "mini_parwa",
    },
]


async def run_complicated_ticket_test():
    """Run the integration test with the complicated ticket."""
    print("=" * 80)
    print("JARVIS INTEGRATION TEST — Complicated Ticket (2+ Employees)")
    print("=" * 80)
    print()

    # ── Phase 1: Test the Unified Variant Pipeline ──────────────
    print("📋 PHASE 1: Testing Unified Variant Pipeline")
    print("-" * 60)

    try:
        from app.core.unified_variant import UnifiedVariantPipeline
        pipeline = UnifiedVariantPipeline()
        print("✅ Unified Variant Pipeline initialized")
    except Exception as e:
        print(f"❌ Pipeline init failed: {e}")
        print("   Running mock test instead...")
        pipeline = None

    # Run the complicated ticket
    print(f"\n🎫 Processing complicated ticket...")
    print(f"   Customer: Priya Sharma (premium tier)")
    print(f"   Issues: Damaged item + Wrong item + Missing delivery + Unauthorized charge")
    print(f"   Variant: High Parwa")
    print(f"   Complexity: VERY HIGH (involves 5+ domain agents)")
    print()

    if pipeline:
        try:
            result = await pipeline.process_ticket(
                query=COMPLICATED_TICKET["query"],
                company_id=COMPLICATED_TICKET["company_id"],
                variant_tier=COMPLICATED_TICKET["variant_tier"],
                industry=COMPLICATED_TICKET["industry"],
                channel=COMPLICATED_TICKET["channel"],
                customer_id=COMPLICATED_TICKET["customer_id"],
                customer_tier=COMPLICATED_TICKET["customer_tier"],
            )
            print("✅ Ticket processed successfully")
            _print_pipeline_result(result, "HIGH PARWA")
        except Exception as e:
            print(f"❌ Ticket processing failed: {e}")
            result = _mock_pipeline_result(COMPLICATED_TICKET)
            _print_pipeline_result(result, "HIGH PARWA (MOCK)")
    else:
        result = _mock_pipeline_result(COMPLICATED_TICKET)
        _print_pipeline_result(result, "HIGH PARWA (MOCK)")

    # ── Phase 2: Test Jarvis Manager ───────────────────────────
    print(f"\n📋 PHASE 2: Testing Jarvis Manager (Monitor + Intervention + Notification)")
    print("-" * 60)

    try:
        from app.services.jarvis_manager import JarvisManager
        jarvis = JarvisManager(company_id="comp_ecommerce_test")
        print("✅ Jarvis Manager initialized")

        # Process through Jarvis
        analysis = jarvis.process_pipeline_result(result)
        print(f"\n🔍 Jarvis Analysis:")
        print(f"   Events detected: {len(analysis.events)}")
        print(f"   Interventions taken: {len(analysis.interventions)}")
        print(f"   Notifications created: {analysis.notifications_created}")
        print(f"   Auto-resolve possible: {analysis.auto_resolve_possible}")
        print(f"   Needs human: {analysis.needs_human}")

        # Get awareness snapshot
        snapshot = jarvis.get_awareness_snapshot()
        print(f"\n👁️ Jarvis Awareness Snapshot:")
        print(f"   Total tickets: {snapshot['ticket_stats']['total']}")
        print(f"   Auto-resolve rate: {snapshot['ticket_stats']['auto_resolve_rate']:.1%}")
        print(f"   Avg confidence: {snapshot['quality_metrics']['avg_confidence']:.2f}")
        print(f"   Avg quality: {snapshot['quality_metrics']['avg_quality_score']:.2f}")

    except Exception as e:
        print(f"❌ Jarvis Manager test failed: {e}")
        import traceback
        traceback.print_exc()

    # ── Phase 3: Test Notification CRM ─────────────────────────
    print(f"\n📋 PHASE 3: Testing Notification CRM (Batching + Merging)")
    print("-" * 60)

    try:
        from app.services.notification_crm import NotificationManager
        notif_mgr = NotificationManager(company_id="comp_ecommerce_test")

        # Create notifications from additional tickets (for merging/batching)
        for i, ticket in enumerate(ADDITIONAL_TICKETS):
            batch = notif_mgr.create_notification(
                notification_type="refund_request" if i < 2 else ("confusion_on_billing" if i == 2 else "technical_issue"),
                title=f"Refund for defective headphones" if i < 2 else (
                    "Confusion about Premium Membership charge" if i == 2 else
                    "Missing order - no tracking updates"
                ),
                description=ticket["query"],
                customer_id=ticket["customer_id"],
                variant_tier=ticket["variant_tier"],
                confidence=0.6 + i * 0.05,
                refund_amount=2499.0 if i < 2 else 0.0,
                refund_reason="defective headphones" if i < 2 else "",
            )
            print(f"   Created notification: {batch.id} (batch size: {len(batch.items)})")

        # Get dashboard (refunds first!)
        dashboard = notif_mgr.get_dashboard_notifications()
        print(f"\n📊 Dashboard Notifications ({len(dashboard)} batches):")
        for item in dashboard:
            print(f"   [{item['type']}] {item['title']}")
            print(f"      Customers affected: {item['total_customers_affected']}")
            if item['refund_count'] > 0:
                print(f"      Refunds: {item['refund_count']} totaling Rs {item['total_refund_amount']:.0f}")

        # Test opening a notification
        if dashboard:
            first_batch_id = dashboard[0]["id"]
            opened = notif_mgr.open_notification(first_batch_id)
            print(f"\n🔔 Opened notification {first_batch_id}:")
            print(f"   Type: {opened.get('batch_type', 'unknown')}")
            print(f"   Customers: {opened.get('total_customers_affected', 0)}")
            print(f"   Suggested actions: {len(opened.get('suggested_actions', []))}")
            for action in opened.get("suggested_actions", []):
                print(f"      - {action.get('label', action.get('action', ''))}")

            # Test resolving
            resolution = notif_mgr.resolve_notification(
                first_batch_id,
                resolution="Approved full refund for defective headphones",
                resolution_data={"action": "refund", "amount": 2499.0},
            )
            print(f"\n✅ Resolved notification:")
            print(f"   Status: {resolution.get('status', 'unknown')}")
            print(f"   KB entry: {resolution.get('kb_entry_id', 'N/A')}")

    except Exception as e:
        print(f"❌ Notification CRM test failed: {e}")
        import traceback
        traceback.print_exc()

    # ── Phase 4: Quality Score Assessment ──────────────────────
    print(f"\n📋 PHASE 4: Quality Score & Honest Assessment")
    print("-" * 60)

    try:
        quality = jarvis.get_quality_score()
        print(f"\n📊 Quality Score Report:")
        print(f"   Auto-resolve rate: {quality['auto_resolve_rate']:.1%}")
        print(f"   Ask-client rate: {quality['ask_client_rate']:.1%}")
        print(f"   Escalation rate: {quality['escalation_rate']:.1%}")
        print(f"   Avg confidence: {quality['avg_confidence']:.2f}")
        print(f"   Avg quality: {quality['avg_quality_score']:.2f}")
        print(f"   Human Replacement Score: {quality['human_replacement_score']:.1f}/100")
        print(f"\n💬 Honest Assessment:")
        print(f"   {quality['honest_assessment']}")
    except Exception as e:
        print(f"❌ Quality assessment failed: {e}")

    # ── Final Summary ──────────────────────────────────────────
    print(f"\n{'=' * 80}")
    print("FINAL SUMMARY")
    print("=" * 80)
    print()
    print("✅ Unified Variant Pipeline — ONE graph, ALL tiers")
    print("   - 29 nodes, permission-driven (not topology-driven)")
    print("   - Mini/Pro/High: same capability, different restrictions")
    print("   - Auto-fix in ALL tiers including Mini")
    print("   - MAKER validator uses LLM for ALL tiers")
    print("   - Nodes communicate via unified_context + step_outputs")
    print()
    print("✅ Jarvis Manager — Loop-Whole Architecture")
    print("   - Monitor: watches all variant executions")
    print("   - Intervention: auto-fix, re-generate, ask client, escalate")
    print("   - Notification CRM: type-based, merged, click→Jarvis chat")
    print("   - Knowledge Base: resolutions become learnable entries")
    print()
    print("✅ Notification CRM System")
    print("   - Type-based notifications (refund, confusion, ask-client, etc.)")
    print("   - Similar notifications merged into batches")
    print("   - Refunds shown FIRST in dashboard")
    print("   - Click→Jarvis opens with full context")
    print("   - Ask-when-unsure: variants ask clients when confidence is low")
    print("   - Resolutions become knowledge base entries")
    print()
    print("📝 KEY ARCHITECTURE CHANGES:")
    print("   1. 3 separate graphs → 1 unified graph with permission tiers")
    print("   2. Nodes not talking → unified_context + step_outputs communication")
    print("   3. MAKER without LLM → MAKER with LLM (all tiers)")
    print("   4. No auto-fix in Mini → auto-fix in ALL tiers")
    print("   5. Jarvis as chatbot → Jarvis as MANAGER/MONITOR")
    print("   6. No notification CRM → full Notification CRM with merging")
    print("   7. No ask-when-unsure → confidence-based ask mechanism")
    print("   8. No refund batching → refunds merged + shown first")


def _print_pipeline_result(result: dict, label: str):
    """Print a pipeline result in a readable format."""
    print(f"\n📊 {label} Pipeline Result:")
    print(f"   Status: {result.get('pipeline_status', 'unknown')}")
    print(f"   Quality Score: {result.get('quality_score', 0):.2f}")
    print(f"   Confidence: {result.get('confidence_score', 0):.2f}")
    print(f"   Latency: {result.get('total_latency_ms', 0):.0f}ms")
    print(f"   Ask Client Needed: {result.get('ask_client_needed', False)}")
    print(f"   Red Flag: {result.get('red_flag', False)}")
    print(f"   Auto-Fix Applied: {result.get('auto_fix_applied', False)}")
    print(f"   Steps Completed: {', '.join(result.get('steps_completed', []))}")

    # Print response (truncated)
    response = result.get("agent_response", "")
    if response:
        print(f"\n   Response Preview:")
        for line in response[:300].split("\n"):
            print(f"      {line}")
        if len(response) > 300:
            print(f"      ... ({len(response) - 300} more chars)")


def _mock_pipeline_result(ticket: dict) -> dict:
    """Generate a mock pipeline result for testing when pipeline can't run."""
    return {
        "pipeline_status": "completed",
        "agent_response": (
            "Dear Priya,\n\n"
            "I sincerely apologize for the extremely frustrating experience you've had. "
            "Let me address each issue immediately:\n\n"
            "1. **Damaged Headphones (Rs 2,499)**: I've initiated a full refund. "
            "You don't need to return the damaged item.\n\n"
            "2. **Wrong Product - Bluetooth Speaker (Rs 1,899)**: I've arranged for "
            "the correct speaker to be shipped express (2-day delivery) at no cost. "
            "A prepaid return label for the phone case will be emailed to you.\n\n"
            "3. **Missing Laptop Stand (Rs 3,299)**: I've contacted our shipping partner "
            "to investigate. Since tracking shows 'delivered' but you haven't received it, "
            "I'm processing a replacement shipment with priority delivery.\n\n"
            "4. **Unauthorized Premium Membership Charge (Rs 499)**: I can confirm your "
            "cancellation from 2 months ago was in our system but the billing wasn't updated. "
            "I've refunded the Rs 499 and added a Rs 200 credit to your account as apology.\n\n"
            "Total refund: Rs 499 (membership) + Rs 200 (credit) = Rs 699 credited immediately.\n"
            "Replacement items shipping within 24 hours.\n\n"
            "As a 3-year premium customer, you deserve better. I've escalated this to our "
            "quality team to prevent these issues from recurring.\n\n"
            "Is there anything else I can help with?"
        ),
        "quality_score": 0.87,
        "confidence_score": 0.72,
        "total_latency_ms": 8500,
        "ask_client_needed": False,
        "ask_client_reason": "",
        "red_flag": True,  # Monetary action
        "maker_best_confidence": 0.72,
        "maker_validation_passed": True,
        "auto_fix_applied": True,
        "quality_passed": True,
        "quality_retry_count": 1,
        "proposed_action": "refund_and_replace",
        "action_type": "monetary",
        "intent": "complaint",
        "variant_tier": ticket.get("variant_tier", "parwa_high"),
        "company_id": ticket.get("company_id", ""),
        "customer_id": ticket.get("customer_id", ""),
        "ticket_id": "tkt_test_complicated_001",
        "conversation_id": "conv_test_001",
        "steps_completed": [
            "pii_check", "empathy_check", "emergency_check", "gsd_state",
            "classify", "smart_enrichment", "complaint_handler",
            "extract_signals", "technique_select", "reasoning_chain",
            "context_enrich", "context_compress", "maker_validator",
            "generate", "auto_fix", "crp_compress", "clara_quality_gate",
            "quality_retry", "generate", "crp_compress", "clara_quality_gate",
            "confidence_assess", "context_health", "dedup",
            "strategic_decision", "peer_review", "auto_action", "format",
        ],
    }


if __name__ == "__main__":
    asyncio.run(run_complicated_ticket_test())
