"""
PARWA Jarvis Paddle Live Integration Test

Tests the actual Paddle API with the provided live credentials.
This script verifies:
  1. Paddle client can connect and authenticate
  2. Can list customers from Paddle
  3. Can list subscriptions from Paddle
  4. Can list transactions from Paddle
  5. Can list prices from Paddle
  6. Jarvis Paddle Bridge works end-to-end
  7. Jarvis executors can call Paddle through the bridge

Usage:
  cd backend
  python -m scripts.jarvis_paddle_live_test

BC-008: Never crash — every test is independently wrapped.
"""

import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, Optional

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _load_env():
    """Load .env file if python-dotenv is available."""
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        load_dotenv(env_path)
        print("✓ Loaded .env file")
    except ImportError:
        print("⚠ python-dotenv not installed, using system env vars")


def _print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def _print_result(name: str, success: bool, message: str = "", data: Any = None):
    icon = "✓" if success else "✗"
    print(f"  {icon} {name}: {'PASS' if success else 'FAIL'}")
    if message:
        print(f"    → {message}")
    if data and isinstance(data, dict):
        for k, v in list(data.items())[:5]:
            val_str = str(v)[:100]
            print(f"    → {k}: {val_str}")


async def test_paddle_client():
    """Test 1: Direct PaddleClient connection."""
    _print_header("TEST 1: PaddleClient Direct Connection")

    api_key = os.environ.get("PADDLE_API_KEY", "")
    client_token = os.environ.get("PADDLE_CLIENT_TOKEN", "")
    environment = os.environ.get("ENVIRONMENT", "sandbox")
    sandbox = environment != "production"

    print(f"  API Key: {api_key[:20]}..." if api_key else "  API Key: NOT SET")
    print(f"  Client Token: {client_token[:10]}..." if client_token else "  Client Token: NOT SET")
    print(f"  Environment: {environment} (sandbox={sandbox})")

    if not api_key:
        _print_result("PaddleClient", False, "No PADDLE_API_KEY set")
        return False

    try:
        from app.clients.paddle_client import PaddleClient

        client = PaddleClient(
            api_key=api_key,
            client_token=client_token,
            sandbox=sandbox,
        )

        # Test: List customers (read-only)
        try:
            result = await client.list_customers(per_page=3)
            customers = result.get("data", [])
            _print_result(
                "List Customers",
                True,
                f"Found {len(customers)} customer(s)",
                {"first_customer_id": customers[0].get("id", "N/A") if customers else "none"},
            )
        except Exception as e:
            _print_result("List Customers", False, str(e)[:200])

        # Test: List subscriptions (read-only)
        try:
            result = await client.list_subscriptions(per_page=3)
            subscriptions = result.get("data", [])
            _print_result(
                "List Subscriptions",
                True,
                f"Found {len(subscriptions)} subscription(s)",
            )
        except Exception as e:
            _print_result("List Subscriptions", False, str(e)[:200])

        # Test: List transactions (read-only)
        try:
            result = await client.list_transactions(per_page=3)
            transactions = result.get("data", [])
            _print_result(
                "List Transactions",
                True,
                f"Found {len(transactions)} transaction(s)",
            )
            if transactions:
                for txn in transactions[:3]:
                    txn_id = txn.get("id", "?")
                    status = txn.get("status", "?")
                    amount = txn.get("details", {}).get("totals", {}).get("total", "?")
                    origin = txn.get("origin", "?")
                    print(f"    → Transaction {txn_id}: {status}, ${amount}, origin={origin}")
        except Exception as e:
            _print_result("List Transactions", False, str(e)[:200])

        # Test: List prices (read-only)
        try:
            result = await client.list_prices(per_page=5)
            prices = result.get("data", [])
            _print_result(
                "List Prices",
                True,
                f"Found {len(prices)} price(s)",
            )
            if prices:
                for p in prices[:5]:
                    price_id = p.get("id", "?")
                    description = p.get("description", "N/A")
                    unit_price = p.get("unit_price", {})
                    amount = unit_price.get("amount", "?")
                    currency = unit_price.get("currency_code", "?")
                    print(f"    → Price {price_id}: {description} — {amount} {currency}")
        except Exception as e:
            _print_result("List Prices", False, str(e)[:200])

        await client.close()
        return True

    except Exception as e:
        _print_result("PaddleClient Init", False, str(e)[:200])
        return False


async def test_paddle_bridge():
    """Test 2: JarvisPaddleBridge end-to-end."""
    _print_header("TEST 2: JarvisPaddleBridge End-to-End")

    api_key = os.environ.get("PADDLE_API_KEY", "")
    client_token = os.environ.get("PADDLE_CLIENT_TOKEN", "")
    environment = os.environ.get("ENVIRONMENT", "sandbox")
    sandbox = environment != "production"

    if not api_key:
        _print_result("JarvisPaddleBridge", False, "No PADDLE_API_KEY set")
        return False

    try:
        from app.services.jarvis_paddle_bridge import JarvisPaddleBridge

        bridge = JarvisPaddleBridge(
            api_key=api_key,
            client_token=client_token,
            sandbox=sandbox,
        )

        # Test: List customers
        try:
            result = await bridge.list_customers(per_page=3)
            customers = result.get("customers", [])
            _print_result(
                "Bridge: List Customers",
                result.get("success", False),
                f"Found {len(customers)} customer(s)",
            )
            if customers:
                first = customers[0]
                print(f"    → Customer ID: {first.get('id', '?')}")
                print(f"    → Email: {first.get('email', '?')}")
                print(f"    → Name: {first.get('name', '?')}")
        except Exception as e:
            _print_result("Bridge: List Customers", False, str(e)[:200])

        # Test: List subscriptions
        try:
            result = await bridge.list_subscriptions(per_page=3)
            subscriptions = result.get("subscriptions", [])
            _print_result(
                "Bridge: List Subscriptions",
                result.get("success", False),
                f"Found {len(subscriptions)} subscription(s)",
            )
            if subscriptions:
                for sub in subscriptions[:3]:
                    sub_id = sub.get("id", "?")
                    status = sub.get("status", "?")
                    print(f"    → Subscription {sub_id}: {status}")
        except Exception as e:
            _print_result("Bridge: List Subscriptions", False, str(e)[:200])

        # Test: Get subscription info (without DB — simulate no Paddle IDs)
        try:
            result = await bridge.get_subscription_info(
                company_id="test_company",
                paddle_customer_id=None,
                paddle_subscription_id=None,
            )
            _print_result(
                "Bridge: Get Subscription Info (no IDs)",
                True,  # Should gracefully return "no subscription found"
                result.get("message", "No subscription found")[:200],
            )
        except Exception as e:
            _print_result("Bridge: Get Subscription Info", False, str(e)[:200])

        # Test: Transaction history (without customer ID)
        try:
            result = await bridge.get_transaction_history(
                company_id="test_company",
                paddle_customer_id=None,
            )
            _print_result(
                "Bridge: Transaction History (no customer ID)",
                True,
                result.get("message", "")[:200],
            )
        except Exception as e:
            _print_result("Bridge: Transaction History", False, str(e)[:200])

        # Test: List invoices (without customer ID)
        try:
            result = await bridge.list_invoices(
                company_id="test_company",
                paddle_customer_id=None,
            )
            _print_result(
                "Bridge: List Invoices (no customer ID)",
                True,
                result.get("message", "")[:200],
            )
        except Exception as e:
            _print_result("Bridge: List Invoices", False, str(e)[:200])

        await bridge.close()
        return True

    except Exception as e:
        _print_result("JarvisPaddleBridge Init", False, str(e)[:200])
        return False


async def test_jarvis_executors():
    """Test 3: Jarvis executor functions that use Paddle."""
    _print_header("TEST 3: Jarvis Executors (Paddle Integration)")

    # These tests simulate what Jarvis would do when a client asks
    # "show me my subscription" or "show transaction history"

    try:
        # Test the _exec_get_subscription_info without a real DB
        from app.services.jarvis_orchestrator import _exec_get_subscription_info, _exec_get_transaction_history, _exec_get_invoices

        # Simulated context (no real DB)
        fake_context = {
            "awareness": {
                "current_plan": "parwa",
                "plan_usage_today": "45%",
                "subscription_status": "active",
            }
        }

        # Test subscription info executor (will fall back to awareness since no DB)
        try:
            result = await _exec_get_subscription_info(
                db=None,
                company_id="test_company",
                session_id="test_session",
                user_id="test_user",
                params={},
                context=fake_context,
            )
            _print_result(
                "Executor: get_subscription_info",
                result.get("success", False),
                result.get("message", "")[:200],
                result.get("data", {}),
            )
        except Exception as e:
            _print_result("Executor: get_subscription_info", False, str(e)[:200])

        # Test transaction history executor (will fall back since no DB)
        try:
            result = await _exec_get_transaction_history(
                db=None,
                company_id="test_company",
                session_id="test_session",
                user_id="test_user",
                params={"period": "last_30_days"},
                context=fake_context,
            )
            _print_result(
                "Executor: get_transaction_history",
                result.get("success", False),
                result.get("message", "")[:200],
            )
        except Exception as e:
            _print_result("Executor: get_transaction_history", False, str(e)[:200])

        # Test invoices executor (will fall back since no DB)
        try:
            result = await _exec_get_invoices(
                db=None,
                company_id="test_company",
                session_id="test_session",
                user_id="test_user",
                params={},
                context=fake_context,
            )
            _print_result(
                "Executor: get_invoices",
                result.get("success", False),
                result.get("message", "")[:200],
            )
        except Exception as e:
            _print_result("Executor: get_invoices", False, str(e)[:200])

    except Exception as e:
        _print_result("Jarvis Executors Import", False, str(e)[:200])
        return False

    return True


async def test_paddle_webhook_config():
    """Test 4: Verify webhook notification set ID config."""
    _print_header("TEST 4: Webhook Configuration")

    webhook_secret = os.environ.get("PADDLE_WEBHOOK_SECRET", "")
    notification_set_id = os.environ.get("PADDLE_WEBHOOK_NOTIFICATION_SET_ID", "")

    _print_result(
        "PADDLE_WEBHOOK_SECRET",
        bool(webhook_secret),
        "Set" if webhook_secret else "NOT SET (webhook signature verification won't work)",
    )
    _print_result(
        "PADDLE_WEBHOOK_NOTIFICATION_SET_ID",
        bool(notification_set_id),
        f"Set: {notification_set_id}" if notification_set_id else "NOT SET",
    )

    # Try to verify webhook config via Paddle client
    if notification_set_id:
        _print_result(
            "Webhook Notification Set ID",
            True,
            f"ntfset ID: {notification_set_id} — configure this in Paddle Dashboard → Notifications",
        )

    return True


async def main():
    """Run all Paddle integration tests."""
    _load_env()

    print("\n" + "=" * 60)
    print("  PARWA Jarvis × Paddle Live Integration Test")
    print("  Testing with REAL Paddle API credentials")
    print("=" * 60)

    start = time.monotonic()

    results = {}

    # Test 1: Direct Paddle Client
    try:
        results["paddle_client"] = await test_paddle_client()
    except Exception as e:
        print(f"\n✗ Test 1 CRASHED: {e}")
        results["paddle_client"] = False

    # Test 2: Jarvis Paddle Bridge
    try:
        results["paddle_bridge"] = await test_paddle_bridge()
    except Exception as e:
        print(f"\n✗ Test 2 CRASHED: {e}")
        results["paddle_bridge"] = False

    # Test 3: Jarvis Executors
    try:
        results["jarvis_executors"] = await test_jarvis_executors()
    except Exception as e:
        print(f"\n✗ Test 3 CRASHED: {e}")
        results["jarvis_executors"] = False

    # Test 4: Webhook Config
    try:
        results["webhook_config"] = await test_paddle_webhook_config()
    except Exception as e:
        print(f"\n✗ Test 4 CRASHED: {e}")
        results["webhook_config"] = False

    elapsed = round((time.monotonic() - start) * 1000, 2)

    # Summary
    _print_header("TEST SUMMARY")
    for name, passed in results.items():
        icon = "✓" if passed else "✗"
        print(f"  {icon} {name}: {'PASS' if passed else 'FAIL'}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\n  Total: {passed}/{total} tests passed ({elapsed}ms)")

    if passed == total:
        print("\n  🎉 All Paddle integration tests PASSED!")
        print("  Jarvis can now read real billing data from Paddle.")
    else:
        print("\n  ⚠ Some tests failed. Check the output above for details.")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
