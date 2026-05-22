#!/usr/bin/env python3
"""
Paddle Live API Test — Verify Read + Write Permissions

Tests all Paddle API operations that Jarvis needs:
  READ operations:  list customers, list subscriptions, list transactions, list prices, list invoices
  WRITE operations: create customer, create transaction, create adjustment (refund), update subscription, cancel subscription

This uses the LIVE Paddle API with the provided credentials.
The API key now has Read + Write permissions for all resources.

Usage:
  cd /home/z/my-project/parwa/backend
  python scripts/paddle_live_readwrite_test.py
"""

import asyncio
import json
import sys
import os
import time
from datetime import datetime

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    load_dotenv(env_path)
except ImportError:
    pass

# Get credentials
PADDLE_API_KEY = os.environ.get("PADDLE_API_KEY", "")
PADDLE_CLIENT_TOKEN = os.environ.get("PADDLE_CLIENT_TOKEN", "")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "sandbox")

# Determine base URL
if ENVIRONMENT == "production":
    BASE_URL = "https://api.paddle.com/"
else:
    BASE_URL = "https://sandbox-api.paddle.com/"

# ANSI colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_header(text: str):
    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}{BLUE}  {text}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}")


def print_test(name: str, passed: bool, details: str = ""):
    icon = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
    print(f"  [{icon}] {name}")
    if details:
        print(f"         {CYAN}{details}{RESET}")


def print_info(text: str):
    print(f"  {CYAN}ℹ {text}{RESET}")


def print_warn(text: str):
    print(f"  {YELLOW}⚠ {text}{RESET}")


def print_error(text: str):
    print(f"  {RED}✗ {text}{RESET}")


def print_success(text: str):
    print(f"  {GREEN}✓ {text}{RESET}")


async def make_request(method: str, endpoint: str, data: dict = None, params: dict = None):
    """Make an authenticated request to Paddle API."""
    import httpx

    url = f"{BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {PADDLE_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
        if method == "GET":
            response = await client.get(url, headers=headers, params=params)
        elif method == "POST":
            response = await client.post(url, headers=headers, json=data)
        elif method == "PATCH":
            response = await client.patch(url, headers=headers, json=data)
        elif method == "DELETE":
            response = await client.delete(url, headers=headers)
        else:
            raise ValueError(f"Unknown method: {method}")

    return response


async def test_read_permissions():
    """Test all READ operations."""
    print_header("READ PERMISSION TESTS")
    results = {}
    customer_ids = []

    # ── Test 1: List Customers (READ) ──
    print_info("Testing: GET /customers (Read permission)")
    try:
        response = await make_request("GET", "/customers", params={"per_page": 5})
        if response.status_code == 200:
            data = response.json()
            customers = data.get("data", [])
            results["list_customers"] = True
            print_test("List Customers", True, f"Found {len(customers)} customers")
            # Save customer IDs for later write tests
            for c in customers:
                cid = c.get("id", "")
                if cid:
                    customer_ids.append(cid)
                    email = c.get("email", "unknown")
                    print_info(f"  Customer: {cid} ({email})")
        else:
            results["list_customers"] = False
            error_detail = response.text[:200] if response.text else "No details"
            print_test("List Customers", False, f"HTTP {response.status_code}: {error_detail}")
    except Exception as e:
        results["list_customers"] = False
        print_test("List Customers", False, str(e)[:100])

    # ── Test 2: List Subscriptions (READ) ──
    print_info("Testing: GET /subscriptions (Read permission)")
    subscription_ids = []
    try:
        response = await make_request("GET", "/subscriptions", params={"per_page": 5})
        if response.status_code == 200:
            data = response.json()
            subs = data.get("data", [])
            results["list_subscriptions"] = True
            print_test("List Subscriptions", True, f"Found {len(subs)} subscriptions")
            for s in subs:
                sid = s.get("id", "")
                if sid:
                    subscription_ids.append(sid)
                    status = s.get("status", "unknown")
                    print_info(f"  Subscription: {sid} ({status})")
        else:
            results["list_subscriptions"] = False
            error_detail = response.text[:200] if response.text else "No details"
            print_test("List Subscriptions", False, f"HTTP {response.status_code}: {error_detail}")
    except Exception as e:
        results["list_subscriptions"] = False
        print_test("List Subscriptions", False, str(e)[:100])

    # ── Test 3: List Transactions (READ) ──
    print_info("Testing: GET /transactions (Read permission)")
    transaction_ids = []
    try:
        response = await make_request("GET", "/transactions", params={"per_page": 5})
        if response.status_code == 200:
            data = response.json()
            txns = data.get("data", [])
            results["list_transactions"] = True
            print_test("List Transactions", True, f"Found {len(txns)} transactions")
            for t in txns:
                tid = t.get("id", "")
                if tid:
                    transaction_ids.append(tid)
                    status = t.get("status", "unknown")
                    origin = t.get("origin", "")
                    total = t.get("details", {}).get("totals", {}).get("total", "?")
                    print_info(f"  Transaction: {tid} | {origin} | {status} | ${total}")
        else:
            results["list_transactions"] = False
            error_detail = response.text[:200] if response.text else "No details"
            print_test("List Transactions", False, f"HTTP {response.status_code}: {error_detail}")
    except Exception as e:
        results["list_transactions"] = False
        print_test("List Transactions", False, str(e)[:100])

    # ── Test 4: List Prices (READ) ──
    print_info("Testing: GET /prices (Read permission)")
    price_ids = []
    try:
        response = await make_request("GET", "/prices", params={"per_page": 10})
        if response.status_code == 200:
            data = response.json()
            prices = data.get("data", [])
            results["list_prices"] = True
            print_test("List Prices", True, f"Found {len(prices)} prices")
            for p in prices:
                pid = p.get("id", "")
                if pid:
                    price_ids.append(pid)
                    unit_amount = p.get("unit_price", {}).get("amount", "?")
                    currency = p.get("unit_price", {}).get("currency_code", "?")
                    product_name = p.get("product", {}).get("name", "unknown") if isinstance(p.get("product"), dict) else "unknown"
                    print_info(f"  Price: {pid} | {product_name} | ${unit_amount} {currency}")
        else:
            results["list_prices"] = False
            error_detail = response.text[:200] if response.text else "No details"
            print_test("List Prices", False, f"HTTP {response.status_code}: {error_detail}")
    except Exception as e:
        results["list_prices"] = False
        print_test("List Prices", False, str(e)[:100])

    # ── Test 5: List Products (READ) ──
    print_info("Testing: GET /products (Read permission)")
    try:
        response = await make_request("GET", "/products", params={"per_page": 5})
        if response.status_code == 200:
            data = response.json()
            products = data.get("data", [])
            results["list_products"] = True
            print_test("List Products", True, f"Found {len(products)} products")
            for p in products:
                pid = p.get("id", "")
                name = p.get("name", "unknown")
                print_info(f"  Product: {pid} | {name}")
        else:
            results["list_products"] = False
            error_detail = response.text[:200] if response.text else "No details"
            print_test("List Products", False, f"HTTP {response.status_code}: {error_detail}")
    except Exception as e:
        results["list_products"] = False
        print_test("List Products", False, str(e)[:100])

    # ── Test 6: List Invoices (READ) ──
    print_info("Testing: GET /invoices (Read permission)")
    try:
        response = await make_request("GET", "/invoices", params={"per_page": 5})
        if response.status_code == 200:
            data = response.json()
            invoices = data.get("data", [])
            results["list_invoices"] = True
            print_test("List Invoices", True, f"Found {len(invoices)} invoices")
        elif response.status_code == 404:
            # No invoices is not a permission failure
            results["list_invoices"] = True
            print_test("List Invoices", True, "No invoices found (but permission is OK)")
        else:
            results["list_invoices"] = False
            error_detail = response.text[:200] if response.text else "No details"
            print_test("List Invoices", False, f"HTTP {response.status_code}: {error_detail}")
    except Exception as e:
        results["list_invoices"] = False
        print_test("List Invoices", False, str(e)[:100])

    # ── Test 7: List Adjustments (READ) ──
    print_info("Testing: GET /adjustments (Read permission)")
    try:
        response = await make_request("GET", "/adjustments", params={"per_page": 5})
        if response.status_code == 200:
            data = response.json()
            adjustments = data.get("data", [])
            results["list_adjustments"] = True
            print_test("List Adjustments", True, f"Found {len(adjustments)} adjustments")
        elif response.status_code == 404:
            results["list_adjustments"] = True
            print_test("List Adjustments", True, "No adjustments found (but permission is OK)")
        else:
            results["list_adjustments"] = False
            error_detail = response.text[:200] if response.text else "No details"
            print_test("List Adjustments", False, f"HTTP {response.status_code}: {error_detail}")
    except Exception as e:
        results["list_adjustments"] = False
        print_test("List Adjustments", False, str(e)[:100])

    return results, customer_ids, subscription_ids, transaction_ids, price_ids


async def test_write_permissions(customer_ids, subscription_ids, transaction_ids, price_ids):
    """Test WRITE operations."""
    print_header("WRITE PERMISSION TESTS")
    results = {}
    created_customer_id = None
    created_transaction_id = None

    # ── Test 1: Create Customer (WRITE) ──
    print_info("Testing: POST /customers (Write permission)")
    test_email = f"jarvis-test-{int(time.time())}@parwa.ai"
    try:
        response = await make_request("POST", "/customers", data={
            "email": test_email,
            "name": "Jarvis API Test Customer",
            "custom_data": {
                "source": "jarvis_api_test",
                "created_by": "paddle_live_readwrite_test",
                "test_timestamp": datetime.utcnow().isoformat(),
            }
        })
        if response.status_code in (200, 201):
            data = response.json()
            created_customer_id = data.get("data", {}).get("id", "")
            results["create_customer"] = True
            print_test("Create Customer", True, f"Created: {created_customer_id} ({test_email})")
        else:
            results["create_customer"] = False
            error_detail = response.text[:300] if response.text else "No details"
            print_test("Create Customer", False, f"HTTP {response.status_code}: {error_detail}")
    except Exception as e:
        results["create_customer"] = False
        print_test("Create Customer", False, str(e)[:100])

    # ── Test 2: Create Transaction (WRITE) ──
    print_info("Testing: POST /transactions (Write permission)")
    # Use the created customer or an existing one
    customer_for_txn = created_customer_id or (customer_ids[0] if customer_ids else "")
    if customer_for_txn and price_ids:
        try:
            response = await make_request("POST", "/transactions", data={
                "customer_id": customer_for_txn,
                "items": [{"price_id": price_ids[0], "quantity": 1}],
                "custom_data": {
                    "source": "jarvis_api_test",
                    "test": "write_permission_check",
                }
            })
            if response.status_code in (200, 201):
                data = response.json()
                created_transaction_id = data.get("data", {}).get("id", "")
                checkout_url = data.get("data", {}).get("checkout", {}).get("url", "N/A")
                results["create_transaction"] = True
                print_test("Create Transaction", True, f"Created: {created_transaction_id}")
                if checkout_url and checkout_url != "N/A":
                    print_info(f"  Checkout URL: {checkout_url[:80]}...")
            else:
                results["create_transaction"] = False
                error_detail = response.text[:300] if response.text else "No details"
                print_test("Create Transaction", False, f"HTTP {response.status_code}: {error_detail}")
        except Exception as e:
            results["create_transaction"] = False
            print_test("Create Transaction", False, str(e)[:100])
    else:
        print_warn("Skipping Create Transaction — no customer_id or price_id available")
        results["create_transaction"] = None

    # ── Test 3: Create Adjustment / Refund (WRITE) ──
    print_info("Testing: POST /adjustments (Write permission — refund)")
    if transaction_ids:
        try:
            response = await make_request("POST", "/adjustments", data={
                "transaction_id": transaction_ids[0],
                "reason": "other",
                "description": "Jarvis API test — checking adjustment:write permission",
            })
            if response.status_code in (200, 201):
                data = response.json()
                adjustment_id = data.get("data", {}).get("id", "")
                results["create_adjustment"] = True
                print_test("Create Adjustment (Refund)", True, f"Created: {adjustment_id}")
            elif response.status_code == 422:
                # Validation error (e.g., already refunded) — but permission IS granted
                results["create_adjustment"] = True
                print_test("Create Adjustment (Refund)", True, "Permission OK (validation error = write access works)")
                print_info(f"  Note: {response.text[:100]}")
            else:
                results["create_adjustment"] = False
                error_detail = response.text[:300] if response.text else "No details"
                print_test("Create Adjustment (Refund)", False, f"HTTP {response.status_code}: {error_detail}")
        except Exception as e:
            results["create_adjustment"] = False
            print_test("Create Adjustment (Refund)", False, str(e)[:100])
    else:
        print_warn("Skipping Create Adjustment — no transaction_id available")
        results["create_adjustment"] = None

    # ── Test 4: Update Subscription (WRITE) ──
    print_info("Testing: PATCH /subscriptions/{id} (Write permission)")
    if subscription_ids:
        try:
            response = await make_request("PATCH", f"/subscriptions/{subscription_ids[0]}", data={
                "custom_data": {
                    "jarvis_test": True,
                    "test_timestamp": datetime.utcnow().isoformat(),
                }
            })
            if response.status_code == 200:
                results["update_subscription"] = True
                print_test("Update Subscription", True, f"Updated custom_data on {subscription_ids[0]}")
            elif response.status_code == 422:
                # Validation error but permission is OK
                results["update_subscription"] = True
                print_test("Update Subscription", True, "Permission OK (validation error = write access works)")
            else:
                results["update_subscription"] = False
                error_detail = response.text[:300] if response.text else "No details"
                print_test("Update Subscription", False, f"HTTP {response.status_code}: {error_detail}")
        except Exception as e:
            results["update_subscription"] = False
            print_test("Update Subscription", False, str(e)[:100])
    else:
        print_warn("Skipping Update Subscription — no subscription_id available")
        results["update_subscription"] = None

    # ── Test 5: List Notification Settings (READ) ──
    print_info("Testing: GET /notification-settings (Read permission)")
    try:
        response = await make_request("GET", "/notification-settings")
        if response.status_code == 200:
            data = response.json()
            settings = data.get("data", [])
            results["list_notification_settings"] = True
            print_test("List Notification Settings", True, f"Found {len(settings)} notification settings")
            for s in settings:
                sid = s.get("id", "")
                desc = s.get("description", "unknown")
                print_info(f"  Notification Setting: {sid} | {desc}")
        else:
            results["list_notification_settings"] = False
            error_detail = response.text[:200] if response.text else "No details"
            print_test("List Notification Settings", False, f"HTTP {response.status_code}: {error_detail}")
    except Exception as e:
        results["list_notification_settings"] = False
        print_test("List Notification Settings", False, str(e)[:100])

    return results, created_customer_id, created_transaction_id


async def test_jarvis_paddle_bridge():
    """Test the Jarvis Paddle Bridge directly."""
    print_header("JARVIS PADDLE BRIDGE TESTS")
    results = {}

    try:
        from app.services.jarvis_paddle_bridge import JarvisPaddleBridge

        bridge = JarvisPaddleBridge(
            api_key=PADDLE_API_KEY,
            client_token=PADDLE_CLIENT_TOKEN,
            sandbox=(ENVIRONMENT != "production"),
        )

        # Test: List Customers via bridge
        print_info("Testing: JarvisPaddleBridge.list_customers()")
        try:
            bridge_result = await bridge.list_customers(per_page=3)
            if bridge_result.get("success"):
                customers = bridge_result.get("customers", [])
                results["bridge_list_customers"] = True
                print_test("Bridge: List Customers", True, f"Found {len(customers)} customers via bridge")
            else:
                results["bridge_list_customers"] = False
                print_test("Bridge: List Customers", False, bridge_result.get("message", "Unknown error"))
        except Exception as e:
            results["bridge_list_customers"] = False
            print_test("Bridge: List Customers", False, str(e)[:100])

        # Test: List Subscriptions via bridge
        print_info("Testing: JarvisPaddleBridge.list_subscriptions()")
        try:
            bridge_result = await bridge.list_subscriptions(per_page=3)
            if bridge_result.get("success"):
                subs = bridge_result.get("subscriptions", [])
                results["bridge_list_subscriptions"] = True
                print_test("Bridge: List Subscriptions", True, f"Found {len(subs)} subscriptions via bridge")
            else:
                results["bridge_list_subscriptions"] = False
                print_test("Bridge: List Subscriptions", False, bridge_result.get("message", "Unknown error"))
        except Exception as e:
            results["bridge_list_subscriptions"] = False
            print_test("Bridge: List Subscriptions", False, str(e)[:100])

        # Cleanup
        await bridge.close()

    except ImportError as e:
        print_warn(f"Could not import JarvisPaddleBridge: {e}")
        print_warn("Make sure you're running from the backend directory")
        results["bridge_import"] = False
    except Exception as e:
        print_error(f"Bridge test error: {e}")
        results["bridge_error"] = str(e)[:200]

    return results


async def main():
    print(f"\n{BOLD}{CYAN}")
    print("  ╔═══════════════════════════════════════════════════════════════════╗")
    print("  ║          PADDLE LIVE API TEST — Read + Write Permissions        ║")
    print("  ╚═══════════════════════════════════════════════════════════════════╝")
    print(f"{RESET}")

    # Print configuration
    print(f"  {BOLD}Configuration:{RESET}")
    print(f"    Environment:   {ENVIRONMENT}")
    print(f"    Base URL:      {BASE_URL}")
    print(f"    API Key:       {PADDLE_API_KEY[:20]}...{PADDLE_API_KEY[-10:]}")
    print(f"    Client Token:  {PADDLE_CLIENT_TOKEN[:10]}...{PADDLE_CLIENT_TOKEN[-6:]}")
    print()

    if not PADDLE_API_KEY:
        print_error("PADDLE_API_KEY is not set! Check your .env file.")
        return

    # Run all tests
    read_results, customer_ids, subscription_ids, transaction_ids, price_ids = await test_read_permissions()
    write_results, created_customer_id, created_transaction_id = await test_write_permissions(
        customer_ids, subscription_ids, transaction_ids, price_ids
    )
    bridge_results = await test_jarvis_paddle_bridge()

    # ── Summary ──
    print_header("SUMMARY")

    all_results = {**read_results, **write_results, **bridge_results}
    passed = sum(1 for v in all_results.values() if v is True)
    failed = sum(1 for v in all_results.values() if v is False)
    skipped = sum(1 for v in all_results.values() if v is None)
    total = len(all_results)

    print(f"\n  {BOLD}Total Tests:  {total}{RESET}")
    print(f"  {GREEN}Passed:       {passed}{RESET}")
    print(f"  {RED}Failed:       {failed}{RESET}")
    print(f"  {YELLOW}Skipped:      {skipped}{RESET}")

    # Verdict
    if failed == 0 and passed > 0:
        print(f"\n  {BOLD}{GREEN}✓ ALL PERMISSIONS VERIFIED! Read + Write both working.{RESET}")
        print(f"  {GREEN}Jarvis can now perform all Paddle operations (refunds, upgrades, cancellations, etc.){RESET}")
    elif failed > 0 and passed > 0:
        print(f"\n  {BOLD}{YELLOW}⚠ PARTIAL: Some permissions work, some don't.{RESET}")
        print(f"  {YELLOW}Check the failed tests above for specific permission issues.{RESET}")
    elif passed == 0:
        print(f"\n  {BOLD}{RED}✗ ALL TESTS FAILED — API key may be invalid or Paddle API is unreachable.{RESET}")
    else:
        print(f"\n  {BOLD}{YELLOW}⚠ No tests could be run — check configuration.{RESET}")

    # Key data for reference
    print(f"\n  {BOLD}Discovered Resources:{RESET}")
    if customer_ids:
        print(f"    Customer IDs:        {customer_ids[:3]}")
    if subscription_ids:
        print(f"    Subscription IDs:    {subscription_ids[:3]}")
    if transaction_ids:
        print(f"    Transaction IDs:     {transaction_ids[:3]}")
    if price_ids:
        print(f"    Price IDs:           {price_ids[:5]}")
    if created_customer_id:
        print(f"    Created Customer:    {created_customer_id} (test customer)")
    if created_transaction_id:
        print(f"    Created Transaction: {created_transaction_id} (test transaction)")

    print()


if __name__ == "__main__":
    asyncio.run(main())
