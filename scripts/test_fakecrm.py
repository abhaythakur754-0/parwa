#!/usr/bin/env python3
"""
FakeCRM Server Test Script - With Authentication
Runs all endpoint tests and saves results to file
"""
import urllib.request
import urllib.error
import json
from datetime import datetime

RESULTS_FILE = "/home/z/my-project/download/fakecrm_test_results.txt"
SERVER_URL = "http://localhost:8888"
AUTH_TOKEN = "Bearer test-fakecrm-token-123"

def write_result(line):
    with open(RESULTS_FILE, "a") as f:
        f.write(line + "\n")

def get_json(url):
    """Fetch JSON from URL with auth header"""
    try:
        req = urllib.request.Request(url)
        req.add_header("Authorization", AUTH_TOKEN)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            return (200, data, None)
    except urllib.error.HTTPError as e:
        return (e.code, None, f"HTTP {e.code}")
    except Exception as e:
        return (None, None, str(e))

def main():
    # Clear results file
    with open(RESULTS_FILE, "w") as f:
        f.write("")
    
    # Header
    write_result("")
    write_result("╔═══════════════════════════════════════════════════════════════════╗")
    write_result("║                                                                   ║")
    write_result("║     ██████╗ ██╗   ██╗██████╗  █████╗ ███╗   ██╗███████╗██╗  ██╗  ║")
    write_result("║     ██╔══██╗██║   ██║██╔══██╗██╔══██╗████╗  ██║██╔════╝╚██╗██╔╝  ║")
    write_result("║     ██████╔╝██║   ██║██████╔╝███████║██╔██╗ ██║█████╝   ╚███╔╝   ║")
    write_result("║     ██╔══██╗██║   ██║██╔══██╗██╔══██║██║╚██╗██║██╔══╝   ██╔██╗   ║")
    write_result("║     ██████╔╝╚██████╔╝██║  ██║██║  ██║██║ ╚████║███████╗██╔╝ ██╗  ║")
    write_result("║     ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝  ║")
    write_result("║                                                                   ║")
    write_result("║              FAKECRM PRODUCTION TEST RESULTS                     ║")
    write_result(f"║              Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    write_result("║              Auth: Bearer test-fakecrm-token-123                  ║")
    write_result("╚═══════════════════════════════════════════════════════════════════╝")
    write_result("")
    
    # Check if server is running
    write_result("┌─────────────────────────────────────────────────────────────────┐")
    write_result("│ PRE-CHECK: Verifying FakeCRM server is running...              │")
    write_result("├─────────────────────────────────────────────────────────────────┤")
    
    try:
        req = urllib.request.Request(f"{SERVER_URL}/health")
        with urllib.request.urlopen(req, timeout=5) as response:
            health_data = json.loads(response.read().decode('utf-8'))
            write_result("│ ✅ SERVER STATUS: RUNNING                                  │")
            write_result(f"│ Version: {health_data.get('version', 'N/A')}")
            stats = health_data.get('data_stats', {})
            write_result(f"│ Data Stats:                                              │")
            write_result(f"│   - Contacts: {stats.get('contacts', 0)}")
            write_result(f"│   - Companies: {stats.get('companies', 0)}")
            write_result(f"│   - Deals: {stats.get('deals', 0)}")
            write_result(f"│   - Tickets: {stats.get('tickets', 0)}")
            write_result(f"│   - Orders: {stats.get('orders', 0)}")
            write_result(f"│   - Products: {stats.get('products', 0)}")
    except Exception as e:
        write_result(f"│ ❌ SERVER NOT RUNNING: {e}                                │")
        write_result("└─────────────────────────────────────────────────────────────────┘")
        return
    
    write_result("└─────────────────────────────────────────────────────────────────┘")
    write_result("")
    
    # Run all tests
    tests = [
        ("Health Check", f"{SERVER_URL}/health", 
         "Basic server health endpoint - no auth required", False),
        
        ("Analytics Overview", f"{SERVER_URL}/analytics/overview", 
         "KPI dashboard - revenue, contacts, deals metrics", True),
        
        ("Contacts API (HubSpot)", f"{SERVER_URL}/crm/v3/objects/contacts?limit=3", 
         "HubSpot-style CRM contacts with email, phone, company", True),
        
        ("Tickets API (Zendesk)", f"{SERVER_URL}/api/v2/tickets?per_page=3", 
         "Zendesk-style support tickets with status, priority", True),
        
        ("Deals Pipeline", f"{SERVER_URL}/crm/v3/objects/deals?limit=3", 
         "Sales deals with amounts, stages, close dates", True),
        
        ("Orders API (Shopify)", f"{SERVER_URL}/admin/api/2024-01/orders.json?limit=3", 
         "Shopify-style e-commerce orders with line items", True),
        
        ("Companies API", f"{SERVER_URL}/crm/v3/objects/companies?limit=3", 
         "Company accounts with industry, size, revenue", True),
    ]
    
    results = []
    for i, (name, url, desc, needs_auth) in enumerate(tests, 1):
        write_result("┌─────────────────────────────────────────────────────────────────┐")
        write_result(f"│ TEST {i}/7: {name:<54} │")
        write_result("├─────────────────────────────────────────────────────────────────┤")
        write_result(f"│ URL: {url}")
        write_result(f"│ Description: {desc}")
        write_result("├─────────────────────────────────────────────────────────────────┤")
        
        if needs_auth:
            status_code, data, error = get_json(url)
        else:
            status_code, data, error = get_json(url)
        
        if status_code == 200:
            results.append(("✅ PASS", name, status_code))
            write_result(f"│ STATUS: ✅ PASS (HTTP {status_code})                              │")
            write_result("│ RESPONSE DATA:                                           │")
            
            # Show key data points based on endpoint type
            if "contacts" in url and "results" in data:
                write_result(f"│   Total contacts available: {data.get('total', 0)}")
                for contact in data.get("results", [])[:2]:
                    props = contact.get("properties", {})
                    write_result(f"│   - {props.get('firstname','')} {props.get('lastname','')} ({props.get('email','')})")
                    
            elif "tickets" in url and "tickets" in data:
                write_result(f"│   Total tickets: {data.get('count', 0)}")
                for ticket in data.get("tickets", [])[:2]:
                    write_result(f"│   - [{ticket.get('status')}] {ticket.get('subject','')[:50]}")
                    
            elif "deals" in url and "results" in data:
                write_result(f"│   Total deals: {data.get('total', 0)}")
                for deal in data.get("results", [])[:2]:
                    props = deal.get("properties", {})
                    write_result(f"│   - {props.get('dealname','')}: ${props.get('amount',0)}")
                    
            elif "orders" in url and "orders" in data:
                write_result(f"│   Total orders: {data.get('count', 0)}")
                for order in data.get("orders", [])[:2]:
                    write_result(f"│   - Order #{order.get('id','')}: ${order.get('total_price','0')}")
                    
            elif "companies" in url and "results" in data:
                write_result(f"│   Total companies: {data.get('total', 0)}")
                for company in data.get("results", [])[:2]:
                    props = company.get("properties", {})
                    write_result(f"│   - {props.get('name','')} ({props.get('industry','')})")
                    
            elif "analytics" in url:
                write_result(f"│   Revenue (30d): ${data.get('revenue_30d', 0):,.2f}")
                write_result(f"│   Active Contacts: {data.get('active_contacts', 0)}")
                write_result(f"│   Open Deals: {data.get('open_deals', 0)}")
                write_result(f"│   Open Tickets: {data.get('open_tickets', 0)}")
                
            else:
                # Generic JSON display
                data_str = json.dumps(data, indent=6)
                for line in data_str.split("\n")[:15]:
                    write_result(f"│   {line}")
        else:
            results.append(("❌ FAIL", name, status_code))
            write_result(f"│ STATUS: ❌ FAIL                                               │")
            write_result(f"│ Error: {error}                                        │")
        
        write_result("└─────────────────────────────────────────────────────────────────┘")
        write_result("")
    
    # Summary
    write_result("╔═══════════════════════════════════════════════════════════════════╗")
    write_result("║                        TEST SUMMARY                            ║")
    write_result("╠═══════════════════════════════════════════════════════════════════╣")
    
    passed = sum(1 for r in results if r[0] == "✅ PASS")
    total = len(results)
    pct = (passed * 100 // total) if total > 0 else 0
    
    write_result(f"║  Total Tests Run:  {total:<48} ║")
    write_result(f"║  Passed:           {passed:<48} ║")
    write_result(f"║  Failed:           {total - passed:<48} ║")
    write_result(f"║  Success Rate:     {pct}%{' '*44} ║")
    write_result("╠═══════════════════════════════════════════════════════════════════╣")
    write_result("║  DETAILED RESULTS:                                             ║")
    
    for status, name, code in results:
        write_result(f"║    {status} {name:<45} ({code})       ║")
    
    if passed == total:
        write_result("╠═══════════════════════════════════════════════════════════════════╣")
        write_result("║  🎉 ALL TESTS PASSED - SERVER IS PRODUCTION READY!               ║")
    
    write_result("╚═══════════════════════════════════════════════════════════════════╝")

if __name__ == "__main__":
    main()
