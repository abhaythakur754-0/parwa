"""
Phase 7 & 8: Complete End-to-End Test Suite (All 3 Levels)

Runs ALL tests in a single process:
- Level 1: Unit tests (no dependencies)
- Level 2: Integration tests (with fakeredis + SQLite)
- Level 3: API endpoint tests (with running backend)

Run with: python tests/test_phase7_8_complete.py
"""

import asyncio
import json
import sys
import time
import uuid
from datetime import datetime, timezone

sys.path.insert(0, '/home/z/my-project/parwa/backend')

# ═══════════════════════════════════════════════════════════════════════════
# LEVEL 1: UNIT TESTS
# ═══════════════════════════════════════════════════════════════════════════

def run_level1_tests():
    """Level 1: Unit tests — test each function/class independently."""
    print("\n" + "=" * 60)
    print("LEVEL 1: UNIT TESTS")
    print("=" * 60)
    results = {}

    # ── Phase 7 Unit Tests ────────────────────────────────────────────
    from app.services.integration_cache_service import (
        DataFreshness,
        FRESHNESS_TTL,
        INTEGRATION_DEFAULT_FRESHNESS,
        ENDPOINT_FRESHNESS_OVERRIDES,
        IntegrationCacheService,
    )

    # Test 1: Freshness enum
    assert DataFreshness.REALTIME.value == "realtime"
    assert DataFreshness.SEMI_STATIC.value == "semi_static"
    assert DataFreshness.RARELY_CHANGES.value == "rarely_changes"
    results["freshness_enum"] = "PASS"
    print("  freshness_enum: PASS")

    # Test 2: TTL values per D12
    assert FRESHNESS_TTL[DataFreshness.REALTIME] == 300       # 5 min
    assert FRESHNESS_TTL[DataFreshness.SEMI_STATIC] == 900    # 15 min
    assert FRESHNESS_TTL[DataFreshness.RARELY_CHANGES] == 3600  # 60 min
    results["d12_ttl_values"] = "PASS"
    print("  d12_ttl_values: PASS")

    # Test 3: Integration-to-freshness mapping
    assert INTEGRATION_DEFAULT_FRESHNESS["hubspot"] == DataFreshness.SEMI_STATIC
    assert INTEGRATION_DEFAULT_FRESHNESS["shopify"] == DataFreshness.REALTIME
    assert INTEGRATION_DEFAULT_FRESHNESS["google_analytics"] == DataFreshness.RARELY_CHANGES
    assert INTEGRATION_DEFAULT_FRESHNESS["custom"] == DataFreshness.REALTIME
    results["integration_freshness_map"] = "PASS"
    print("  integration_freshness_map: PASS")

    # Test 4: Endpoint overrides
    assert ENDPOINT_FRESHNESS_OVERRIDES["hubspot"]["contacts"] == DataFreshness.SEMI_STATIC
    assert ENDPOINT_FRESHNESS_OVERRIDES["shopify"]["orders"] == DataFreshness.REALTIME
    assert ENDPOINT_FRESHNESS_OVERRIDES["shopify"]["shop"] == DataFreshness.RARELY_CHANGES
    results["endpoint_overrides"] = "PASS"
    print("  endpoint_overrides: PASS")

    # Test 5: Cache key building
    svc = IntegrationCacheService(company_id="acme")
    assert svc._build_cache_key("hubspot", "contacts", "c1") == "int:hubspot:contacts:c1"
    results["cache_key_building"] = "PASS"
    print("  cache_key_building: PASS")

    # Test 6: TTL calculation
    assert svc._get_ttl("shopify", "orders") == 300      # realtime
    assert svc._get_ttl("hubspot", "contacts") == 900    # semi-static
    assert svc._get_ttl("hubspot", "companies") == 3600  # rarely changes
    results["ttl_calculation"] = "PASS"
    print("  ttl_calculation: PASS")

    # ── Phase 8 Unit Tests ────────────────────────────────────────────
    from app.services.cross_channel_service import CrossChannelService

    # Test 7: Channel type mapping
    assert CrossChannelService.CHANNEL_TYPE_MAP["email"] == "email"
    assert CrossChannelService.CHANNEL_TYPE_MAP["chat"] == "webchat"
    assert CrossChannelService.CHANNEL_TYPE_MAP["sms"] == "phone"
    assert CrossChannelService.CHANNEL_TYPE_MAP["voice"] == "phone"
    assert CrossChannelService.CHANNEL_TYPE_MAP["whatsapp"] == "whatsapp"
    results["channel_type_map"] = "PASS"
    print("  channel_type_map: PASS")

    return results


# ═══════════════════════════════════════════════════════════════════════════
# LEVEL 2: INTEGRATION TESTS (Redis + SQLite)
# ═══════════════════════════════════════════════════════════════════════════

async def run_level2_tests():
    """Level 2: Integration tests with fakeredis + SQLite DB."""
    print("\n" + "=" * 60)
    print("LEVEL 2: INTEGRATION TESTS")
    print("=" * 60)
    results = {}

    from app.services.integration_cache_service import IntegrationCacheService
    from database.models.tickets import Customer, CustomerChannel, Ticket, TicketMessage
    from app.services.cross_channel_service import CrossChannelService
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database.base import Base

    # ── Phase 7 Cache Integration Tests ───────────────────────────────
    cache_svc = IntegrationCacheService(company_id="test_company")

    # Test: Cache set + get
    await cache_svc.set("hubspot", "contacts", "c1", {"name": "John"})
    cached = await cache_svc.get("hubspot", "contacts", "c1")
    assert cached is not None
    assert cached["data"]["name"] == "John"
    assert cached["_cache_meta"]["integration"] == "hubspot"
    results["cache_set_get"] = "PASS"
    print("  cache_set_get: PASS")

    # Test: Cache miss
    assert await cache_svc.get("hubspot", "contacts", "nonexistent") is None
    results["cache_miss"] = "PASS"
    print("  cache_miss: PASS")

    # Test: Cache invalidation (specific)
    await cache_svc.set("hubspot", "contacts", "c2", {"name": "B"})
    await cache_svc.invalidate("hubspot", "contacts", "c1")
    assert await cache_svc.get("hubspot", "contacts", "c1") is None
    assert (await cache_svc.get("hubspot", "contacts", "c2"))["data"]["name"] == "B"
    results["cache_invalidate_specific"] = "PASS"
    print("  cache_invalidate_specific: PASS")

    # Test: Cache invalidation on disconnect
    await cache_svc.set("hubspot", "deals", "d1", {"name": "D"})
    await cache_svc.invalidate_on_disconnect("hubspot")
    assert await cache_svc.get("hubspot", "contacts", "c2") is None
    assert await cache_svc.get("hubspot", "deals", "d1") is None
    results["cache_invalidate_disconnect"] = "PASS"
    print("  cache_invalidate_disconnect: PASS")

    # Test: get_or_fetch cache hit
    await cache_svc.set("shopify", "orders", "o1", {"id": "1"})
    fetch_called = False
    async def mock_fetch():
        nonlocal fetch_called
        fetch_called = True
        return {"id": "fresh"}
    result, hit = await cache_svc.get_or_fetch("shopify", "orders", "o1", mock_fetch)
    assert hit is True
    assert not fetch_called
    results["get_or_fetch_hit"] = "PASS"
    print("  get_or_fetch_hit: PASS")

    # Test: get_or_fetch cache miss
    async def mock_fetch2():
        return {"id": "fresh2"}
    result, hit = await cache_svc.get_or_fetch("shopify", "orders", "o99", mock_fetch2)
    assert hit is False
    assert result["data"]["id"] == "fresh2"
    results["get_or_fetch_miss"] = "PASS"
    print("  get_or_fetch_miss: PASS")

    # Test: Different TTLs per data type
    await cache_svc.set("shopify", "orders", "o2", {"id": "2"})
    await cache_svc.set("shopify", "shop", "info", {"name": "My Shop"})
    cached_order = await cache_svc.get("shopify", "orders", "o2")
    cached_shop = await cache_svc.get("shopify", "shop", "info")
    assert cached_order["_cache_meta"]["freshness"] == "realtime"
    assert cached_shop["_cache_meta"]["freshness"] == "rarely_changes"
    results["different_ttls"] = "PASS"
    print("  different_ttls: PASS")

    # Test: Cache stats
    stats = await cache_svc.get_cache_stats("shopify")
    assert stats["integration"] == "shopify"
    results["cache_stats"] = "PASS"
    print("  cache_stats: PASS")

    # ── Phase 8 Cross-Channel Integration Tests ───────────────────────
    # Use the real SQLite DB
    engine = create_engine("sqlite:////home/z/my-project/parwa/backend/parwa_dev.db", echo=False)
    Session = sessionmaker(bind=engine)
    db = Session()

    company_id = "0d848b18-17ce-46fb-ab42-38f60534d0ab"
    svc = CrossChannelService(db, company_id)

    # Test: Resolve from email
    test_email = f"l2test_{uuid.uuid4().hex[:8]}@example.com"
    result = svc.resolve_from_channel(channel_type="email", identifier=test_email, auto_create=True)
    customer_id = result.get("matched_customer_id") or result.get("customer_id")
    assert customer_id is not None
    results["resolve_email"] = "PASS"
    print("  resolve_email: PASS")

    # Test: Cross-channel recognition
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if customer and not customer.phone:
        customer.phone = "+9876543210"
        ch = CustomerChannel(
            id=str(uuid.uuid4()), customer_id=customer_id,
            company_id=company_id, channel_type="phone",
            external_id="+9876543210", is_verified=False,
        )
        db.add(ch)
        db.commit()

    result = svc.resolve_from_channel(channel_type="sms", identifier="+9876543210")
    resolved_id = result.get("customer_id") or result.get("matched_customer_id")
    assert resolved_id == customer_id
    results["cross_channel_recognition"] = "PASS"
    print("  cross_channel_recognition: PASS")

    # Test: Create multi-channel tickets
    t1 = Ticket(id=str(uuid.uuid4()), company_id=company_id, customer_id=customer_id,
                 channel="email", status="open", subject="Refund for order #456")
    t2 = Ticket(id=str(uuid.uuid4()), company_id=company_id, customer_id=customer_id,
                 channel="chat", status="open", subject="Order #456 status")
    db.add(t1)
    db.add(t2)
    db.commit()

    m1 = TicketMessage(id=str(uuid.uuid4()), ticket_id=t1.id, company_id=company_id,
                        role="customer", content="Refund please", channel="email", is_internal=False)
    m2 = TicketMessage(id=str(uuid.uuid4()), ticket_id=t2.id, company_id=company_id,
                        role="customer", content="Where is order?", channel="chat", is_internal=False)
    db.add(m1)
    db.add(m2)
    db.commit()

    # Test: Unified thread
    thread = svc.get_unified_thread(customer_id)
    assert thread["total_tickets"] >= 2
    channels_seen = {t["channel"] for t in thread["tickets"]}
    assert "email" in channels_seen
    assert "chat" in channels_seen
    results["unified_thread"] = "PASS"
    print("  unified_thread: PASS")

    # Test: AI context
    context = svc.get_cross_channel_context(customer_id)
    assert context["customer"]["id"] == customer_id
    assert context["active_tickets_count"] >= 2
    assert isinstance(context["context_summary"], str)
    results["ai_context"] = "PASS"
    print("  ai_context: PASS")

    # Test: Related tickets
    related = svc.find_related_tickets(customer_id, subject="order #456")
    assert len(related) >= 1
    results["related_tickets"] = "PASS"
    print("  related_tickets: PASS")

    db.close()
    engine.dispose()

    return results


# ═══════════════════════════════════════════════════════════════════════════
# LEVEL 3: API ENDPOINT TESTS (Backend running)
# ═══════════════════════════════════════════════════════════════════════════

async def run_level3_tests():
    """Level 3: Test backend API endpoints directly."""
    print("\n" + "=" * 60)
    print("LEVEL 3: API ENDPOINT TESTS")
    print("=" * 60)
    results = {}

    import httpx

    # Check if backend is running
    try:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=5.0) as client:
            resp = await client.get("/api/v1/health")
            # If we get here, backend is running (even if 403)
    except Exception as e:
        print(f"  Backend not running: {e}")
        print("  Skipping Level 3 tests (run backend first)")
        return {"level3": "SKIPPED (backend not running)"}

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=10.0, follow_redirects=True) as client:
        # Login first
        print("  Logging in...")
        try:
            resp = await client.post(
                "/api/v1/auth/login",
                json={"email": "phase78@parwa.io", "password": "Test1234!"},
            )
            print(f"  Login status: {resp.status_code}")

            if resp.status_code not in (200, 201):
                # Try alternate approach - check cookies
                print(f"  Login response: {resp.text[:200]}")
                results["api_login"] = f"FAIL ({resp.status_code})"
                return results

            # Extract token
            data = resp.json()
            token = data.get("access_token") or data.get("data", {}).get("access_token")
            if not token:
                # Check cookies
                for name, value in resp.cookies.items():
                    if "token" in name.lower() or "at" in name.lower():
                        token = value
                        break

            if not token:
                results["api_login"] = "FAIL (no token)"
                return results

            client.headers["Authorization"] = f"Bearer {token}"
            results["api_login"] = "PASS"
            print("  Login successful")
        except Exception as e:
            results["api_login"] = f"ERROR ({str(e)[:100]})"
            return results

        # Test Phase 7 endpoints
        try:
            resp = await client.get("/api/v1/integration-cache/health")
            if resp.status_code == 200:
                results["api_cache_health"] = "PASS"
                print("  api_cache_health: PASS")
            else:
                results["api_cache_health"] = f"FAIL ({resp.status_code})"
        except Exception as e:
            results["api_cache_health"] = f"ERROR ({str(e)[:50]})"

        try:
            resp = await client.get("/api/v1/integration-cache/stats/hubspot")
            if resp.status_code == 200:
                results["api_cache_stats"] = "PASS"
                print("  api_cache_stats: PASS")
            else:
                results["api_cache_stats"] = f"FAIL ({resp.status_code})"
        except Exception as e:
            results["api_cache_stats"] = f"ERROR ({str(e)[:50]})"

        try:
            resp = await client.post(
                "/api/v1/integration-cache/invalidate",
                json={"integration_type": "hubspot"},
            )
            if resp.status_code == 200:
                results["api_cache_invalidate"] = "PASS"
                print("  api_cache_invalidate: PASS")
            else:
                results["api_cache_invalidate"] = f"FAIL ({resp.status_code})"
        except Exception as e:
            results["api_cache_invalidate"] = f"ERROR ({str(e)[:50]})"

        # Test Phase 8 endpoints
        test_email = f"l3test_{uuid.uuid4().hex[:8]}@example.com"
        try:
            resp = await client.post(
                "/api/v1/cross-channel/resolve",
                json={"channel_type": "email", "identifier": test_email, "auto_create": True},
            )
            if resp.status_code == 200:
                data = resp.json()
                customer_id = data.get("matched_customer_id") or data.get("customer_id")
                results["api_cross_channel_resolve"] = "PASS"
                print("  api_cross_channel_resolve: PASS")

                # Test thread
                resp2 = await client.get(f"/api/v1/cross-channel/thread/{customer_id}")
                results["api_unified_thread"] = "PASS" if resp2.status_code == 200 else f"FAIL ({resp2.status_code})"
                print(f"  api_unified_thread: {results['api_unified_thread']}")

                # Test context
                resp3 = await client.get(f"/api/v1/cross-channel/context/{customer_id}")
                results["api_ai_context"] = "PASS" if resp3.status_code == 200 else f"FAIL ({resp3.status_code})"
                print(f"  api_ai_context: {results['api_ai_context']}")

                # Test related
                resp4 = await client.get(f"/api/v1/cross-channel/related/{customer_id}")
                results["api_related_tickets"] = "PASS" if resp4.status_code == 200 else f"FAIL ({resp4.status_code})"
                print(f"  api_related_tickets: {results['api_related_tickets']}")
            else:
                results["api_cross_channel_resolve"] = f"FAIL ({resp.status_code})"
        except Exception as e:
            results["api_cross_channel_resolve"] = f"ERROR ({str(e)[:50]})"

    return results


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

async def main():
    print("=" * 60)
    print("PHASE 7 & 8: COMPLETE TEST SUITE (ALL 3 LEVELS)")
    print("Phase 7: Data Caching & Smart Refresh")
    print("Phase 8: Cross-Channel Customer Recognition")
    print("=" * 60)

    all_results = {}

    # Level 1
    try:
        l1_results = run_level1_tests()
        all_results.update(l1_results)
    except Exception as e:
        print(f"\n  Level 1 FAILED: {e}")
        all_results["level1_error"] = str(e)[:100]

    # Level 2
    try:
        l2_results = await run_level2_tests()
        all_results.update(l2_results)
    except Exception as e:
        print(f"\n  Level 2 FAILED: {e}")
        all_results["level2_error"] = str(e)[:100]

    # Level 3
    try:
        l3_results = await run_level3_tests()
        all_results.update(l3_results)
    except Exception as e:
        print(f"\n  Level 3 FAILED: {e}")
        all_results["level3_error"] = str(e)[:100]

    # Summary
    print("\n" + "=" * 60)
    print("FINAL RESULTS SUMMARY")
    print("=" * 60)

    phase7_keys = [
        "freshness_enum", "d12_ttl_values", "integration_freshness_map",
        "endpoint_overrides", "cache_key_building", "ttl_calculation",
        "cache_set_get", "cache_miss", "cache_invalidate_specific",
        "cache_invalidate_disconnect", "get_or_fetch_hit", "get_or_fetch_miss",
        "different_ttls", "cache_stats",
        "api_cache_health", "api_cache_stats", "api_cache_invalidate",
    ]
    phase8_keys = [
        "channel_type_map", "resolve_email", "cross_channel_recognition",
        "unified_thread", "ai_context", "related_tickets",
        "api_cross_channel_resolve", "api_unified_thread",
        "api_ai_context", "api_related_tickets",
    ]

    print("\nPhase 7 — Data Caching & Smart Refresh:")
    p7_pass = 0
    for k in phase7_keys:
        v = all_results.get(k, "NOT RUN")
        if v == "PASS":
            p7_pass += 1
        print(f"  {k}: {v}")

    print("\nPhase 8 — Cross-Channel Customer Recognition:")
    p8_pass = 0
    for k in phase8_keys:
        v = all_results.get(k, "NOT RUN")
        if v == "PASS":
            p8_pass += 1
        print(f"  {k}: {v}")

    other_keys = [k for k in all_results if k not in phase7_keys and k not in phase8_keys]
    if other_keys:
        print("\nOther tests:")
        for k in other_keys:
            print(f"  {k}: {all_results[k]}")

    pass_count = sum(1 for v in all_results.values() if v == "PASS")
    fail_count = sum(1 for v in all_results.values() if "FAIL" in str(v))
    error_count = sum(1 for v in all_results.values() if "ERROR" in str(v))

    print(f"\nTotal: {pass_count} PASSED, {fail_count} FAILED, {error_count} ERRORS")
    print(f"Phase 7: {p7_pass}/{len(phase7_keys)} passed")
    print(f"Phase 8: {p8_pass}/{len(phase8_keys)} passed")

    return fail_count == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
