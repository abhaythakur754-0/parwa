#!/usr/bin/env python3
"""
FakeCRM Server Test Script
Starts server, runs tests, reports results
"""

import subprocess
import time
import requests
import json
import sys
import signal

def main():
    print("=" * 60)
    print("  🎭 FAKECRM SERVER - AUTOMATED TEST")
    print("=" * 60)
    print()
    
    # Start server
    print("🚀 Starting FakeCRM Server...")
    server_process = subprocess.Popen(
        [sys.executable, "-c", "import uvicorn; from fake_crm import app; uvicorn.run(app, host='127.0.0.1', port=8888)"],
        cwd="/home/z/my-project/fake-crm-server",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for startup
    time.sleep(5)
    
    # Test endpoints
    base_url = "http://127.0.0.1:8888"
    auth_header = {"Authorization": "Bearer test-token-123"}
    
    tests = [
        ("Health Check", f"{base_url}/health", "GET", None),
        ("Analytics Overview", f"{base_url}/analytics/overview", "GET", auth_header),
        ("Contacts (3)", f"{base_url}/crm/v3/objects/contacts?limit=3", "GET", auth_header),
        ("Tickets (5)", f"{base_url}/api/v2/tickets?per_page=5", "GET", auth_header),
        ("Deals (5)", f"{base_url}/crm/v3/objects/deals?limit=5", "GET", auth_header),
        ("Orders (5)", f"{base_url}/admin/api/2024-01/orders.json?limit=5", "GET", auth_header),
        ("OAuth Page", f"{base_url}/oauth/authorize?client_id=test&redirect_uri=http://test.com", "GET", None),
    ]
    
    results = []
    
    for name, url, method, headers in tests:
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if name == "Health Check":
                        stats = data.get("data_stats", {})
                        print(f"✅ {name}: {stats}")
                    elif name == "Analytics Overview":
                        summary = data.get("summary", {})
                        print(f"✅ {name}: {summary.get('total_contacts', 0)} contacts, {summary.get('total_tickets', 0)} tickets")
                    else:
                        if "results" in data:
                            print(f"✅ {name}: Found {len(data['results'])} items")
                        elif "tickets" in data:
                            print(f"✅ {name}: Found {len(data['tickets'])} tickets")
                        elif "orders" in data:
                            print(f"✅ {name}: Found {data.get('count', 0)} orders")
                        else:
                            print(f"✅ {name}: OK")
                except:
                    print(f"✅ {name}: HTTP {response.status_code}")
                results.append(("PASS", name))
            else:
                print(f"❌ {name}: HTTP {response.status_code}")
                results.append(("FAIL", name))
                
        except Exception as e:
            print(f"❌ {name}: Error - {str(e)[:50]}")
            results.append(("ERROR", name))
    
    # Cleanup
    print()
    server_process.terminate()
    server_process.wait(timeout=5)
    
    # Summary
    print("=" * 60)
    passed = sum(1 for r, _ in results if r == "PASS")
    total = len(results)
    print(f"  📊 RESULTS: {passed}/{total} TESTS PASSED")
    
    if passed == total:
        print("  🎉 ALL TESTS PASSED - FakeCRM is WORKING!")
    else:
        print("  ⚠️ SOME TESTS FAILED - Check output above")
    
    print("=" * 60)
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
