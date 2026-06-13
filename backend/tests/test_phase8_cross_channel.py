"""
Phase 8: Cross-Channel Customer Recognition Integration Tests

Tests the complete Phase 8 implementation with the real SQLite database.

Run with: python tests/test_phase8_cross_channel.py
"""

import json
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, '/home/z/my-project/parwa/backend')

# Use the actual SQLite dev database
DB_PATH = '/home/z/my-project/parwa/backend/parwa_dev.db'


def test_cross_channel_service():
    """Comprehensive test for Phase 8 cross-channel service."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database.models.tickets import Customer, CustomerChannel, Ticket, TicketMessage
    from app.services.cross_channel_service import CrossChannelService

    engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
    Session = sessionmaker(bind=engine)
    db = Session()

    company_id = "0d848b18-17ce-46fb-ab42-38f60534d0ab"  # Our test company
    svc = CrossChannelService(db, company_id)
    results = {}

    try:
        # ── TEST 1: Resolve from email channel ────────────────────────
        print("\n=== TEST 1: Resolve from email channel ===")
        test_email = f"phase8_test_{uuid.uuid4().hex[:8]}@example.com"
        result = svc.resolve_from_channel(
            channel_type="email",
            identifier=test_email,
            auto_create=True,
        )
        customer_id = result.get("matched_customer_id") or result.get("customer_id")
        assert customer_id is not None, f"Failed to resolve/create customer: {result}"
        print(f"  Created/resolved customer: {customer_id}")
        results["resolve_email"] = "PASS"

        # ── TEST 2: Cross-channel recognition ─────────────────────────
        print("\n=== TEST 2: Cross-channel recognition ===")
        # Add phone to the same customer
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if customer and not customer.phone:
            customer.phone = "+1234567890"
            phone_ch = CustomerChannel(
                id=str(uuid.uuid4()),
                customer_id=customer_id,
                company_id=company_id,
                channel_type="phone",
                external_id="+1234567890",
                is_verified=False,
            )
            db.add(phone_ch)
            db.commit()

        result = svc.resolve_from_channel(
            channel_type="sms",
            identifier="+1234567890",
        )
        resolved_id = result.get("customer_id") or result.get("matched_customer_id")
        assert resolved_id == customer_id, f"Expected {customer_id}, got {resolved_id}"
        print(f"  Cross-channel match: SMS -> same customer {resolved_id}")
        results["cross_channel_recognition"] = "PASS"

        # ── TEST 3: Create tickets on different channels ──────────────
        print("\n=== TEST 3: Create tickets on different channels ===")
        email_ticket = Ticket(
            id=str(uuid.uuid4()),
            company_id=company_id,
            customer_id=customer_id,
            channel="email",
            status="open",
            subject="Refund request for order #123",
        )
        chat_ticket = Ticket(
            id=str(uuid.uuid4()),
            company_id=company_id,
            customer_id=customer_id,
            channel="chat",
            status="open",
            subject="Where is my order #123?",
        )
        db.add(email_ticket)
        db.add(chat_ticket)
        db.commit()

        msg1 = TicketMessage(
            id=str(uuid.uuid4()),
            ticket_id=email_ticket.id,
            company_id=company_id,
            role="customer",
            content="I want a refund for order #123",
            channel="email",
            is_internal=False,
        )
        msg2 = TicketMessage(
            id=str(uuid.uuid4()),
            ticket_id=chat_ticket.id,
            company_id=company_id,
            role="customer",
            content="Where is my order #123?",
            channel="chat",
            is_internal=False,
        )
        db.add(msg1)
        db.add(msg2)
        db.commit()
        results["create_tickets"] = "PASS"
        print(f"  Created email + chat tickets")

        # ── TEST 4: Unified thread view ───────────────────────────────
        print("\n=== TEST 4: Unified thread view ===")
        thread = svc.get_unified_thread(customer_id)
        assert thread["total_tickets"] >= 2, f"Expected >= 2 tickets, got {thread['total_tickets']}"
        assert thread["customer"]["id"] == customer_id
        channels_seen = {t["channel"] for t in thread["tickets"]}
        assert "email" in channels_seen, f"Missing email in {channels_seen}"
        assert "chat" in channels_seen, f"Missing chat in {channels_seen}"
        print(f"  Tickets: {thread['total_tickets']}, Channels: {channels_seen}")
        results["unified_thread"] = "PASS"

        # ── TEST 5: Cross-channel AI context ──────────────────────────
        print("\n=== TEST 5: Cross-channel AI context ===")
        context = svc.get_cross_channel_context(customer_id)
        assert context["customer"]["id"] == customer_id
        assert context["active_tickets_count"] >= 2
        assert isinstance(context["context_summary"], str)
        print(f"  Active: {context['active_tickets_count']}, Channels: {list(context['channel_summaries'].keys())}")
        print(f"  Summary: {context['context_summary'][:100]}...")
        results["ai_context"] = "PASS"

        # ── TEST 6: Find related tickets ──────────────────────────────
        print("\n=== TEST 6: Find related tickets ===")
        related = svc.find_related_tickets(customer_id, subject="order #123")
        assert len(related) >= 1, f"Expected >= 1 related ticket"
        print(f"  Found {len(related)} related tickets")
        results["related_tickets"] = "PASS"

        # ── TEST 7: Resolve unknown creates new customer ──────────────
        print("\n=== TEST 7: Resolve unknown identifier ===")
        result = svc.resolve_from_channel(
            channel_type="email",
            identifier=f"newuser_{uuid.uuid4().hex[:8]}@example.com",
            auto_create=True,
        )
        assert result["matched_customer_id"] is not None
        assert result["action_taken"] == "created"
        print(f"  Created new customer: {result['matched_customer_id']}")
        results["resolve_new"] = "PASS"

    finally:
        db.close()
        engine.dispose()

    # Summary
    print("\n" + "=" * 60)
    print("PHASE 8 CROSS-CHANNEL TEST RESULTS")
    print("=" * 60)
    all_pass = True
    for name, status in results.items():
        print(f"  {name}: {status}")
        if status != "PASS":
            all_pass = False

    print(f"\nAll tests: {'PASSED' if all_pass else 'FAILED'}")
    return all_pass


if __name__ == "__main__":
    success = test_cross_channel_service()
    sys.exit(0 if success else 1)
