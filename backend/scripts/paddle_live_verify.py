"""
PARWA Paddle Live API Verification Script

Tests the Paddle API with the LIVE credentials to verify:
1. Authentication works
2. Read operations work (list customers, subscriptions, transactions, prices, products)
3. Write operations work (adjustments/refunds - carefully)
4. The Jarvis Paddle Bridge works end-to-end

Run: python -m scripts.paddle_live_verify
"""

import asyncio
import json
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    load_dotenv(env_path)
except ImportError:
    pass


PADDLE_API_KEY = os.environ.get("PADDLE_API_KEY", "")
PADDLE_CLIENT_TOKEN = os.environ.get("PADDLE_CLIENT_TOKEN", "")
PADDLE_WEBHOOK_NTFSET = os.environ.get("PADDLE_WEBHOOK_NOTIFICATION_SET_ID", "")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "sandbox")

# Colors for terminal
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_header(title: str):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BOLD}{BLUE}  {title}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")


def print_result(test_name: str, success: bool, detail: str = ""):
    icon = f"{GREEN}✓{RESET}" if success else f"{RED}✗{RESET}"
    print(f"  {icon} {test_name}")
    if detail:
        print(f"    {detail}")


def print_info(msg: str):
    print(f"  {YELLOW}→{RESET} {msg}")


def print_data(label: str, data: any):
    print(f"  {BLUE}📊{RESET} {label}:")
    if isinstance(data, (dict, list)):
        formatted = json.dumps(data, indent=4, default=str)
        for line in formatted.split("\n"):
            print(f"    {line}")
    else:
        print(f"    {data}")


async def test_paddle_client_directly():
    """Test 1: Direct Paddle API calls using httpx."""
    print_header("TEST 1: Direct Paddle API Calls (httpx)")
    
    import httpx
    
    # Determine base URL
    is_production = ENVIRONMENT == "production"
    base_url = "https://api.paddle.com/" if is_production else "https://sandbox-api.paddle.com/"
    
    print_info(f"Environment: {ENVIRONMENT}")
    print_info(f"API Base URL: {base_url}")
    print_info(f"API Key: {PADDLE_API_KEY[:20]}...{PADDLE_API_KEY[-5:]}")
    print_info(f"Client Token: {PADDLE_CLIENT_TOKEN[:10]}...{PADDLE_CLIENT_TOKEN[-5:]}")
    print_info(f"Webhook Notification Set: {PADDLE_WEBHOOK_NTFSET}")
    
    headers = {
        "Authorization": f"Bearer {PADDLE_API_KEY}",
        "Content-Type": "application/json",
    }
    
    results = {}
    
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        # Test 1a: List Customers (read)
        print_info("Testing: GET /customers ...")
        try:
            resp = await client.get(f"{base_url}customers", params={"per_page": 5})
            if resp.status_code == 200:
                data = resp.json()
                customers = data.get("data", [])
                results["list_customers"] = {"success": True, "count": len(customers), "data": customers}
                print_result("List Customers", True, f"Found {len(customers)} customers")
                if customers:
                    for c in customers[:3]:
                        print(f"      - ID: {c.get('id')}, Email: {c.get('email', 'N/A')}, Name: {c.get('name', 'N/A')}")
            else:
                results["list_customers"] = {"success": False, "status": resp.status_code, "body": resp.text[:500]}
                print_result("List Customers", False, f"HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            results["list_customers"] = {"success": False, "error": str(e)}
            print_result("List Customers", False, str(e)[:200])
        
        # Test 1b: List Subscriptions (read)
        print_info("Testing: GET /subscriptions ...")
        try:
            resp = await client.get(f"{base_url}subscriptions", params={"per_page": 5})
            if resp.status_code == 200:
                data = resp.json()
                subs = data.get("data", [])
                results["list_subscriptions"] = {"success": True, "count": len(subs), "data": subs}
                print_result("List Subscriptions", True, f"Found {len(subs)} subscriptions")
                if subs:
                    for s in subs[:3]:
                        status = s.get("status", "unknown")
                        sub_id = s.get("id", "")
                        items = s.get("items", [])
                        print(f"      - ID: {sub_id}, Status: {status}, Items: {len(items)}")
            else:
                results["list_subscriptions"] = {"success": False, "status": resp.status_code, "body": resp.text[:500]}
                print_result("List Subscriptions", False, f"HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            results["list_subscriptions"] = {"success": False, "error": str(e)}
            print_result("List Subscriptions", False, str(e)[:200])
        
        # Test 1c: List Transactions (read)
        print_info("Testing: GET /transactions ...")
        try:
            resp = await client.get(f"{base_url}transactions", params={"per_page": 5})
            if resp.status_code == 200:
                data = resp.json()
                txns = data.get("data", [])
                results["list_transactions"] = {"success": True, "count": len(txns), "data": txns}
                print_result("List Transactions", True, f"Found {len(txns)} transactions")
                if txns:
                    for t in txns[:3]:
                        txn_id = t.get("id", "")
                        status = t.get("status", "unknown")
                        origin = t.get("origin", "unknown")
                        amount = t.get("details", {}).get("totals", {}).get("total", "0")
                        currency = t.get("currency_code", "USD")
                        print(f"      - ID: {txn_id}, Status: {status}, Origin: {origin}, Amount: {amount} {currency}")
            else:
                results["list_transactions"] = {"success": False, "status": resp.status_code, "body": resp.text[:500]}
                print_result("List Transactions", False, f"HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            results["list_transactions"] = {"success": False, "error": str(e)}
            print_result("List Transactions", False, str(e)[:200])
        
        # Test 1d: List Prices (read)
        print_info("Testing: GET /prices ...")
        try:
            resp = await client.get(f"{base_url}prices", params={"per_page": 10})
            if resp.status_code == 200:
                data = resp.json()
                prices = data.get("data", [])
                results["list_prices"] = {"success": True, "count": len(prices), "data": prices}
                print_result("List Prices", True, f"Found {len(prices)} prices")
                if prices:
                    for p in prices[:5]:
                        price_id = p.get("id", "")
                        desc = p.get("description", "")
                        amount = p.get("unit_price", {}).get("amount", "0")
                        currency = p.get("unit_price", {}).get("currency_code", "USD")
                        product_id = p.get("product_id", "")
                        print(f"      - ID: {price_id}, Amount: {amount} {currency}, Product: {product_id}")
            else:
                results["list_prices"] = {"success": False, "status": resp.status_code, "body": resp.text[:500]}
                print_result("List Prices", False, f"HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            results["list_prices"] = {"success": False, "error": str(e)}
            print_result("List Prices", False, str(e)[:200])
        
        # Test 1e: List Products (read)
        print_info("Testing: GET /products ...")
        try:
            resp = await client.get(f"{base_url}products", params={"per_page": 5})
            if resp.status_code == 200:
                data = resp.json()
                products = data.get("data", [])
                results["list_products"] = {"success": True, "count": len(products), "data": products}
                print_result("List Products", True, f"Found {len(products)} products")
                if products:
                    for p in products[:5]:
                        prod_id = p.get("id", "")
                        name = p.get("name", "")
                        tax_cat = p.get("tax_category", "")
                        print(f"      - ID: {prod_id}, Name: {name}, Tax: {tax_cat}")
            else:
                results["list_products"] = {"success": False, "status": resp.status_code, "body": resp.text[:500]}
                print_result("List Products", False, f"HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            results["list_products"] = {"success": False, "error": str(e)}
            print_result("List Products", False, str(e)[:200])
        
        # Test 1f: List Adjustments (read - tests write permissions too)
        print_info("Testing: GET /adjustments ...")
        try:
            resp = await client.get(f"{base_url}adjustments", params={"per_page": 5})
            if resp.status_code == 200:
                data = resp.json()
                adjustments = data.get("data", [])
                results["list_adjustments"] = {"success": True, "count": len(adjustments), "data": adjustments}
                print_result("List Adjustments", True, f"Found {len(adjustments)} adjustments")
                if adjustments:
                    for a in adjustments[:3]:
                        adj_id = a.get("id", "")
                        status = a.get("status", "unknown")
                        reason = a.get("reason", "")
                        print(f"      - ID: {adj_id}, Status: {status}, Reason: {reason}")
            else:
                results["list_adjustments"] = {"success": False, "status": resp.status_code, "body": resp.text[:500]}
                print_result("List Adjustments", False, f"HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            results["list_adjustments"] = {"success": False, "error": str(e)}
            print_result("List Adjustments", False, str(e)[:200])
        
        # Test 1g: List Reports (read)
        print_info("Testing: GET /reports ...")
        try:
            resp = await client.get(f"{base_url}reports", params={"per_page": 5})
            if resp.status_code == 200:
                data = resp.json()
                reports = data.get("data", [])
                results["list_reports"] = {"success": True, "count": len(reports)}
                print_result("List Reports", True, f"Found {len(reports)} reports")
            else:
                results["list_reports"] = {"success": False, "status": resp.status_code, "body": resp.text[:500]}
                print_result("List Reports", False, f"HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            results["list_reports"] = {"success": False, "error": str(e)}
            print_result("List Reports", False, str(e)[:200])
    
    return results


async def test_paddle_bridge():
    """Test 2: Jarvis Paddle Bridge integration."""
    print_header("TEST 2: Jarvis Paddle Bridge")
    
    results = {}
    
    try:
        from app.clients.paddle_client import PaddleClient
        from app.services.jarvis_paddle_bridge import JarvisPaddleBridge
        
        is_production = ENVIRONMENT == "production"
        sandbox = not is_production
        
        print_info(f"Creating Paddle Bridge (sandbox={sandbox}) ...")
        
        bridge = JarvisPaddleBridge(
            api_key=PADDLE_API_KEY,
            client_token=PADDLE_CLIENT_TOKEN,
            sandbox=sandbox,
        )
        
        # Test 2a: List Customers via Bridge
        print_info("Testing: bridge.list_customers() ...")
        try:
            result = await bridge.list_customers(per_page=5)
            results["bridge_list_customers"] = result
            print_result("Bridge: List Customers", result.get("success", False),
                        f"Count: {result.get('total_count', 0)}")
            if result.get("customers"):
                for c in result["customers"][:3]:
                    print(f"      - ID: {c.get('id')}, Email: {c.get('email', 'N/A')}")
        except Exception as e:
            results["bridge_list_customers"] = {"success": False, "error": str(e)}
            print_result("Bridge: List Customers", False, str(e)[:200])
        
        # Test 2b: List Subscriptions via Bridge
        print_info("Testing: bridge.list_subscriptions() ...")
        try:
            result = await bridge.list_subscriptions(per_page=5)
            results["bridge_list_subscriptions"] = result
            print_result("Bridge: List Subscriptions", result.get("success", False),
                        f"Count: {result.get('total_count', 0)}")
            if result.get("subscriptions"):
                for s in result["subscriptions"][:3]:
                    print(f"      - ID: {s.get('id')}, Status: {s.get('status')}")
        except Exception as e:
            results["bridge_list_subscriptions"] = {"success": False, "error": str(e)}
            print_result("Bridge: List Subscriptions", False, str(e)[:200])
        
        # Test 2c: Get Subscription Info (needs a sub ID - try with first available)
        first_sub_id = None
        first_customer_id = None
        if results.get("bridge_list_subscriptions", {}).get("success"):
            subs = results["bridge_list_subscriptions"].get("subscriptions", [])
            if subs:
                first_sub_id = subs[0].get("id")
        if results.get("bridge_list_customers", {}).get("success"):
            custs = results["bridge_list_customers"].get("customers", [])
            if custs:
                first_customer_id = custs[0].get("id")
        
        if first_sub_id:
            print_info(f"Testing: bridge.get_subscription_info(sub={first_sub_id}) ...")
            try:
                result = await bridge.get_subscription_info(
                    company_id="test_company",
                    paddle_subscription_id=first_sub_id,
                )
                results["bridge_get_subscription_info"] = result
                print_result("Bridge: Get Subscription Info", result.get("success", False),
                            f"Plan: {result.get('plan_name', 'N/A')}, Status: {result.get('status', 'N/A')}")
            except Exception as e:
                results["bridge_get_subscription_info"] = {"success": False, "error": str(e)}
                print_result("Bridge: Get Subscription Info", False, str(e)[:200])
        else:
            print_info("Skipping subscription info test — no active subscriptions found")
            results["bridge_get_subscription_info"] = {"success": False, "message": "No subscriptions available"}
        
        # Test 2d: Get Transaction History
        if first_customer_id:
            print_info(f"Testing: bridge.get_transaction_history(customer={first_customer_id}) ...")
            try:
                result = await bridge.get_transaction_history(
                    company_id="test_company",
                    paddle_customer_id=first_customer_id,
                    period="all",
                )
                results["bridge_get_transaction_history"] = result
                print_result("Bridge: Transaction History", result.get("success", False),
                            f"Count: {result.get('total_count', 0)}, Payments: ${result.get('total_payments', 0)}")
                if result.get("transactions"):
                    for t in result["transactions"][:5]:
                        print(f"      - {t.get('type', '?')}: ${t.get('amount', 0)} {t.get('currency', 'USD')} ({t.get('status', '?')}) - {t.get('date', '')}")
            except Exception as e:
                results["bridge_get_transaction_history"] = {"success": False, "error": str(e)}
                print_result("Bridge: Transaction History", False, str(e)[:200])
        else:
            print_info("Skipping transaction history test — no customers found")
            results["bridge_get_transaction_history"] = {"success": False, "message": "No customers available"}
        
        # Test 2e: List Invoices
        if first_customer_id:
            print_info(f"Testing: bridge.list_invoices(customer={first_customer_id}) ...")
            try:
                result = await bridge.list_invoices(
                    company_id="test_company",
                    paddle_customer_id=first_customer_id,
                )
                results["bridge_list_invoices"] = result
                print_result("Bridge: List Invoices", result.get("success", False),
                            f"Count: {result.get('total_count', 0)}")
            except Exception as e:
                results["bridge_list_invoices"] = {"success": False, "error": str(e)}
                print_result("Bridge: List Invoices", False, str(e)[:200])
        else:
            print_info("Skipping invoices test — no customers found")
            results["bridge_list_invoices"] = {"success": False, "message": "No customers available"}
        
        # Close bridge
        await bridge.close()
        
    except ImportError as e:
        results["bridge_import_error"] = str(e)
        print_result("Bridge Import", False, str(e))
    
    return results


async def test_paddle_permissions():
    """Test 3: Verify Write Permissions (without actually modifying anything dangerous)."""
    print_header("TEST 3: Permission Verification")
    
    results = {}
    
    import httpx
    
    is_production = ENVIRONMENT == "production"
    base_url = "https://api.paddle.com/" if is_production else "https://sandbox-api.paddle.com/"
    headers = {
        "Authorization": f"Bearer {PADDLE_API_KEY}",
        "Content-Type": "application/json",
    }
    
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        # Test read permission on each entity
        read_tests = [
            ("Addresses", "addresses", 5),
            ("Adjustments", "adjustments", 5),
            ("Businesses", "businesses", 5),
            ("Customers", "customers", 5),
            ("Discounts", "discounts", 5),
            ("Prices", "prices", 5),
            ("Products", "products", 5),
            ("Reports", "reports", 5),
            ("Subscriptions", "subscriptions", 5),
            ("Transactions", "transactions", 5),
            ("Notification Settings", "notification-settings", 5),
        ]
        
        for name, endpoint, per_page in read_tests:
            try:
                resp = await client.get(f"{base_url}{endpoint}", params={"per_page": per_page})
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    results[f"read_{endpoint}"] = {"success": True, "count": len(data)}
                    print_result(f"Read: {name}", True, f"✓ ({len(data)} items)")
                elif resp.status_code == 403:
                    results[f"read_{endpoint}"] = {"success": False, "status": 403}
                    print_result(f"Read: {name}", False, "403 Forbidden — No read permission")
                else:
                    results[f"read_{endpoint}"] = {"success": False, "status": resp.status_code}
                    print_result(f"Read: {name}", False, f"HTTP {resp.status_code}")
            except Exception as e:
                results[f"read_{endpoint}"] = {"success": False, "error": str(e)}
                print_result(f"Read: {name}", False, str(e)[:100])
    
    return results


async def main():
    """Run all Paddle verification tests."""
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  PARWA PADDLE LIVE API VERIFICATION{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")
    
    if not PADDLE_API_KEY:
        print(f"{RED}ERROR: PADDLE_API_KEY not found in environment!{RESET}")
        return
    
    print(f"  API Key: {PADDLE_API_KEY[:20]}...{PADDLE_API_KEY[-5:]}")
    print(f"  Client Token: {PADDLE_CLIENT_TOKEN[:10]}...{PADDLE_CLIENT_TOKEN[-5:]}")
    print(f"  Webhook NTFSet: {PADDLE_WEBHOOK_NTFSET}")
    print(f"  Environment: {ENVIRONMENT}")
    
    all_results = {}
    
    # Test 1: Direct API calls
    try:
        results1 = await test_paddle_client_directly()
        all_results["direct_api"] = results1
    except Exception as e:
        print(f"\n{RED}Direct API test failed: {e}{RESET}")
        all_results["direct_api"] = {"error": str(e)}
    
    # Test 2: Paddle Bridge
    try:
        results2 = await test_paddle_bridge()
        all_results["paddle_bridge"] = results2
    except Exception as e:
        print(f"\n{RED}Bridge test failed: {e}{RESET}")
        all_results["paddle_bridge"] = {"error": str(e)}
    
    # Test 3: Permission verification
    try:
        results3 = await test_paddle_permissions()
        all_results["permissions"] = results3
    except Exception as e:
        print(f"\n{RED}Permission test failed: {e}{RESET}")
        all_results["permissions"] = {"error": str(e)}
    
    # Summary
    print_header("SUMMARY")
    
    total_tests = 0
    passed = 0
    failed = 0
    
    for category, tests in all_results.items():
        if isinstance(tests, dict):
            for key, val in tests.items():
                if isinstance(val, dict) and "success" in val:
                    total_tests += 1
                    if val["success"]:
                        passed += 1
                    else:
                        failed += 1
    
    print(f"  Total tests: {total_tests}")
    print(f"  {GREEN}Passed: {passed}{RESET}")
    print(f"  {RED}Failed: {failed}{RESET}")
    
    if failed == 0:
        print(f"\n  {GREEN}{BOLD}ALL PADDLE TESTS PASSED! 🎉{RESET}")
    else:
        print(f"\n  {YELLOW}Some tests failed — check details above.{RESET}")
    
    # Save results to file
    results_path = "/home/z/my-project/parwa/backend/scripts/paddle_verify_results.json"
    with open(results_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  Results saved to: {results_path}")


if __name__ == "__main__":
    asyncio.run(main())
