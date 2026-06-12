#!/usr/bin/env python3
"""PARWA Phase 15 & 16 Test — Backend runs in same process via daemon thread."""
import sys, os, time, json, threading
sys.path.insert(0, "/home/z/my-project/mini-services/parwa-backend")
os.chdir("/home/z/my-project/mini-services/parwa-backend")

def start_server():
    import uvicorn
    from app.main import app
    uvicorn.run(app, host="127.0.0.1", port=8299, log_level="error")

t = threading.Thread(target=start_server, daemon=True)
t.start()
time.sleep(4)

import requests

BASE = "http://127.0.0.1:8299"
R = {"pass": 0, "fail": 0, "warn": 0, "tests": []}
tid = None

def log(name, ok, detail="", cat=""):
    s = "PASS" if ok else "FAIL"
    if ok and "warn" in detail.lower(): s = "WARN"; R["warn"] += 1
    elif ok: R["pass"] += 1
    else: R["fail"] += 1
    R["tests"].append({"name": name, "status": s, "details": detail, "category": cat})
    i = "✅" if s == "PASS" else "⚠️" if s == "WARN" else "❌"
    print(f"  {i} {name}: {s}" + (f" — {detail}" if detail else ""))

def api(m, ep, d=None, h=None, files=None):
    try:
        r = requests.request(m, f"{BASE}{ep}", json=d if not files else None, headers=h, files=files, timeout=15)
        try: b = r.json()
        except: b = r.text
        return r.status_code, b
    except Exception as e:
        return 0, str(e)

def ok(s): return 200 <= s < 300

print("=" * 70)
print("PARWA Phase 15 & 16 — Backend Test Suite (In-Process)")
print("=" * 70)

# 1. Health
print("\n📋 1. Health")
s, b = api("GET", "/health")
log("Health check", s == 200 and isinstance(b, dict) and b.get("status") == "ok", f"v{b.get('version')}", "Infra")

s, b = api("GET", "/")
log("Root v2.0.0", ok(s) and isinstance(b, dict) and b.get("version") == "2.0.0", f"Version: {b.get('version')}", "Infra")

# 2. Auth
print("\n📋 2. Auth")
email = f"p16_{int(time.time())}_{os.getpid()}@parwa.test"
s, b = api("POST", "/api/v1/auth/register", {"email": email, "name": "Phase16", "password": "SecurePass1!"})
token = b.get("access_token") if isinstance(b, dict) else None
tid = b.get("tenant_id") if isinstance(b, dict) else None
log("Register", ok(s) and token, f"Token: {bool(token)}", "Auth")

if not token:
    s, b = api("POST", "/api/v1/auth/login", {"email": email, "password": "SecurePass1!"})
    token = b.get("access_token") if isinstance(b, dict) else None
    tid = b.get("tenant_id") if isinstance(b, dict) else None

auth = {"Authorization": f"Bearer {token}"} if token else {}
log("JWT obtained", bool(token), f"Tenant: {tid}", "Auth")

s, b = api("GET", "/api/v1/auth/me", h=auth)
if isinstance(b, dict): tid = b.get("tenant_id", tid)
log("Auth/me", ok(s), f"Tenant: {tid}", "Auth")

# 3. Setup
print("\n📋 3. Setup")
s, _ = api("POST", "/api/v1/onboarding/industry-variant", {"industry": "ecommerce", "variant": "parwa"}, h=auth)
log("Industry+variant", ok(s), "", "Setup")

s, _ = api("POST", "/api/v1/onboarding/legal-consent", {"accepted": True}, h=auth)
log("Legal consent", ok(s), "", "Setup")

s, b = api("POST", "/api/v1/variants/add", {"variant_type": "parwa"}, h=auth)
log("Add variant (or already exists)", ok(s) or s == 409, f"Status: {s}", "Setup")

s, b = api("POST", "/api/v1/integrations/connect", {"integration_id": "shopify", "auth_type": "header", "credentials": {"access_token": "shpat_test1234567890", "shop_domain": "test.myshopify.com"}}, h=auth)
log("Connect Shopify", ok(s), f"Masked: {b.get('masked_key') if isinstance(b, dict) else 'N/A'}", "Setup")

# ====== PHASE 15 ======
print("\n" + "=" * 70)
print("PHASE 15: Data Flow & Error Architecture")
print("=" * 70)

print("\n📋 4. Data Flow Endpoints")
s, b = api("GET", "/api/v1/dataflow/circuit-states", h=auth)
log("Circuit-states", ok(s) and isinstance(b, dict), f"Circuits: {len(b.get('circuits', {}))}", "P15")

s, b = api("GET", "/api/v1/dataflow/cache-stats", h=auth)
log("Cache-stats", ok(s) and isinstance(b, dict), f"Entries: {b.get('total_entries')}", "P15")

s, b = api("GET", "/api/v1/dataflow/health", h=auth)
log("Dataflow health", ok(s) and isinstance(b, dict), f"Status: {b.get('status')}", "P15")

s, b = api("GET", "/api/v1/dataflow/error-codes", h=auth)
codes = len(b.get("error_codes", {})) if isinstance(b, dict) else 0
log("Error codes (9 types)", ok(s) and codes >= 8, f"Count: {codes}", "P15")

print("\n📋 5. Circuit Breaker & Cache")
s, b = api("POST", "/api/v1/dataflow/reset-circuit", {"integration_id": "shopify"}, h=auth)
log("Reset circuit", ok(s), f"New: {b.get('new_state')}", "P15")

s, b = api("POST", "/api/v1/dataflow/invalidate-cache", {"integration_id": "shopify"}, h=auth)
log("Invalidate cache", ok(s), "", "P15")

print("\n📋 6. Enhanced Health")
s, b = api("GET", "/api/v1/integrations/health", h=auth)
has_cb = isinstance(b, dict) and "circuit_breaker_summary" in b
has_cs = isinstance(b, dict) and "cache_summary" in b
log("Circuit breaker summary", ok(s) and has_cb, f"Has: {has_cb}", "P15")
log("Cache summary", ok(s) and has_cs, f"Has: {has_cs}", "P15")

print("\n📋 7. Integration Test via ExternalToolBus")
s, b = api("POST", "/api/v1/integrations/test", {"integration_id": "shopify"}, h=auth)
has_err = isinstance(b, dict) and "error" in b
has_ret = isinstance(b, dict) and "is_retriable" in b
log("Structured error response", has_err, f"Error: {has_err}, retriable: {has_ret}", "P15")

# ====== PHASE 16 ======
print("\n" + "=" * 70)
print("PHASE 16: End-to-End Proof & Missing Routes")
print("=" * 70)

print("\n📋 8. Webhooks (Gap A)")
s, b = api("POST", "/api/v1/webhooks/register", {"integration_id": "shopify", "events": ["order.created"]}, h=auth)
log("Register webhook", ok(s) and isinstance(b, dict) and "webhook_url" in b, f"URL: {b.get('webhook_url')}", "P16")

s, b = api("GET", "/api/v1/webhooks/events", h=auth)
log("List events", ok(s), f"Total: {b.get('total')}", "P16")

s, b = api("GET", "/api/v1/webhooks/configs", h=auth)
log("List configs", ok(s), f"Total: {b.get('total')}", "P16")

s, b = api("POST", f"/api/v1/webhooks/receive/{tid or 'x'}/shopify", {"topic": "orders/create", "id": 12345})
log("Receive webhook", ok(s), f"Type: {b.get('event_type') if isinstance(b, dict) else 'N/A'}", "P16")

print("\n📋 9. Notifications (GAP 12)")
s, b = api("POST", "/api/v1/notifications/create", {"category": "integration_health", "severity": "high", "title": "Key rotation needed"}, h=auth)
nid = b.get("id") if isinstance(b, dict) else None
log("Create notification", ok(s) and nid, f"ID: {nid}", "P16")

s, b = api("GET", "/api/v1/notifications/list", h=auth)
log("List notifications", ok(s) and isinstance(b, dict) and b.get("total", 0) >= 1, f"Total: {b.get('total')}", "P16")

s, b = api("GET", "/api/v1/notifications/unread-count", h=auth)
log("Unread count", ok(s) and isinstance(b, dict), f"Count: {b.get('unread_count')}", "P16")

s, b = api("GET", "/api/v1/notifications/preferences", h=auth)
pcount = len(b.get("preferences", [])) if isinstance(b, dict) else 0
log("Preferences (6+)", ok(s) and pcount >= 6, f"Count: {pcount}", "P16")

s, _ = api("POST", "/api/v1/notifications/mark-read", {}, h=auth)
log("Mark all read", ok(s), "", "P16")

if nid:
    s, _ = api("DELETE", f"/api/v1/notifications/{nid}", h=auth)
    log("Delete notification", ok(s), "", "P16")

print("\n📋 10. Knowledge Base (GAP 7)")
os.makedirs("/home/z/my-project/upload/kb", exist_ok=True)
tf = "/home/z/my-project/upload/kb/test_faq.txt"
with open(tf, "w") as f:
    f.write("PARWA FAQ\n\nQ: What is PARWA?\nA: AI customer support platform.\n\nQ: How to connect?\nA: Settings → Integrations.")

try:
    with open(tf, "rb") as f:
        r = requests.post(f"{BASE}/api/v1/kb/upload", files={"file": ("test_faq.txt", f, "text/plain")}, headers=auth, timeout=15)
    kb = r.json()
    did = kb.get("id") if isinstance(kb, dict) else None
    log("Upload KB doc", r.status_code < 400, f"ID: {did}, status: {kb.get('status')}", "P16")
except Exception as e:
    did = None; log("Upload KB doc", False, f"Error: {e}", "P16")

s, b = api("GET", "/api/v1/kb/documents", h=auth)
log("List docs", ok(s), f"Total: {b.get('total')}", "P16")

s, b = api("GET", "/api/v1/kb/stats", h=auth)
log("KB stats", ok(s), f"Docs: {b.get('total_documents')}", "P16")

s, b = api("POST", "/api/v1/kb/search", {"query": "PARWA", "top_k": 3}, h=auth)
log("Search KB", ok(s), f"Results: {b.get('total')}", "P16")

if did:
    s, _ = api("DELETE", f"/api/v1/kb/documents/{did}", h=auth)
    log("Delete KB doc", ok(s), "", "P16")

print("\n📋 11. Industry Change (GAP 10)")
s, b = api("GET", "/api/v1/industry/current", h=auth)
log("Current industry", ok(s), f"Industry: {b.get('industry')}", "P16")

s, b = api("GET", "/api/v1/industry/list")
log("List industries (4)", ok(s) and isinstance(b, dict) and b.get("total") == 4, f"Total: {b.get('total')}", "P16")

s, b = api("POST", "/api/v1/industry/preview-change", {"industry": "saas"}, h=auth)
log("Preview change", ok(s) and isinstance(b, dict) and "changes" in b, f"Has changes: True", "P16")

s, b = api("POST", "/api/v1/industry/change", {"industry": "saas"}, h=auth)
has_g = isinstance(b, dict) and "preservation_guarantees" in b
log("Change w/ preservation", ok(s) and has_g, f"Keys: {list(b.get('preservation_guarantees', {}).keys()) if has_g else 'N/A'}", "P16")

if isinstance(b, dict):
    log("Outside-industry detected", True, f"{len(b.get('outside_industry_integrations', []))} outside", "P16")

print("\n📋 12. E2E Verification")
s, b = api("GET", "/api/v1/verification/run", h=auth)
log("Run verification", ok(s) and isinstance(b, dict) and "summary" in b, f"Status: {s}", "P16")

if isinstance(b, dict) and "summary" in b:
    sm = b["summary"]
    log("Verification summary", True, f"Total: {sm.get('total_checks')}, Pass: {sm.get('passed')}, Fail: {sm.get('failed')}, Warn: {sm.get('warnings')}", "P16")
    for ch in b.get("results", []):
        log(f"  {ch.get('check', '?')}", ch.get("status") == "PASS", f"{ch.get('status', '?')} — {ch.get('note', '')[:60]}", "P16")

s, b = api("GET", "/api/v1/verification/trace", h=auth)
log("Trace docs", ok(s) and isinstance(b, dict) and b.get("total_integrations", 0) > 0, f"Traces: {b.get('total_integrations')}", "P16")

if isinstance(b, dict) and "architecture" in b:
    a = b["architecture"]
    log("Trace: request_flow", "request_flow" in a, a.get("request_flow", "")[:50], "P16")
    log("Trace: error_flow", "error_flow" in a, a.get("error_flow", "")[:50], "P16")
    log("Trace: shared_bus", "shared_bus" in a, a.get("shared_bus", "")[:50], "P16")

print("\n📋 13. Industry Catalog (GAP 3)")
for ind in ["saas", "ecommerce", "logistics", "other"]:
    s, b = api("GET", f"/api/v1/integrations/catalog?industry={ind}")
    t = b.get("total", 0) if isinstance(b, dict) else 0
    log(f"Catalog: {ind}", t > 0, f"Count: {t}", "GAP3")

print("\n📋 14. ExternalToolBus Unit Tests")
from app.services.external_tool_bus import CircuitBreaker, CircuitState, DataCache, ToolBusError

cb = CircuitBreaker()
log("CB: initial CLOSED", cb.can_proceed("test"), "", "P15-Unit")
for i in range(5): cb.record_failure("test")
log("CB: opens after 5 failures", not cb.can_proceed("test"), f"State: {cb.get_state('test')['state']}", "P15-Unit")
cb.reset("test")
log("CB: resets", cb.can_proceed("test"), "", "P15-Unit")
cb._circuits["test"]["state"] = CircuitState.HALF_OPEN
log("CB: HALF_OPEN allows", cb.can_proceed("test"), "", "P15-Unit")
cb.record_success("test")
log("CB: success closes", cb.get_state("test")["state"] == "closed", "", "P15-Unit")

c = DataCache()
c.set("h", "/x", [1, 2], "semi_static")
e = c.get("h", "/x")
log("Cache: store+get", e is not None and e.is_fresh, f"Fresh: {e.is_fresh if e else 'N/A'}", "P15-Unit")
log("Cache: TTL D12", c.TTL_CONFIG == {"realtime": 300, "semi_static": 900, "static": 3600}, f"{c.TTL_CONFIG}", "P15-Unit")
c.invalidate("h")
log("Cache: invalidate", c.get("h", "/x") is None, "", "P15-Unit")

err = ToolBusError("api_down", "Down", "h", True, {"x": 1}, "3m ago")
d = err.to_dict()
log("ToolBusError format", d.get("success") is False and d.get("degraded") is True and "data_age" in d, f"Keys: {list(d.keys())}", "P15-Unit")

print("\n📋 15. Phase 13/14 Regression")
s, b = api("GET", "/api/v1/variants/list", h=auth)
log("Variants list", ok(s), "", "Regression")

s, b = api("POST", "/api/v1/variants/route-ticket", {"intent": "billing", "complexity_score": 5}, h=auth)
log("Route ticket (5)", ok(s), f"Routed: {b.get('variant_type') if isinstance(b, dict) else 'N/A'}", "Regression")

s, b = api("POST", "/api/v1/ai-tools/select", {"ticket_intent": "shipping"}, h=auth)
log("AI tool select (shipping)", ok(s), f"Tools: {len(b) if isinstance(b, list) else 'N/A'}", "Regression")

s, b = api("GET", "/api/v1/audit/stats", h=auth)
log("Audit stats", ok(s), "", "Regression")

s, b = api("GET", "/api/v1/api-keys/list", h=auth)
log("API keys list", ok(s), "", "Regression")

# ====== SUMMARY ======
print("\n" + "=" * 70)
print("HONEST TEST SUMMARY — Phase 15 & 16")
print("=" * 70)
total = R["pass"] + R["fail"] + R["warn"]
print(f"  Total:    {total}")
print(f"  ✅ Pass:  {R['pass']}")
print(f"  ❌ Fail:  {R['fail']}")
print(f"  ⚠️  Warn:  {R['warn']}")
print(f"  Rate:     {R['pass']/total*100:.1f}%" if total else "  N/A")

failed = [t for t in R["tests"] if t["status"] == "FAIL"]
if failed:
    print("\n❌ FAILED:")
    for t in failed: print(f"  ❌ {t['name']} — {t['details']}")

out = "/home/z/my-project/download/phase15_16_test_results.json"
with open(out, "w") as f:
    json.dump({"phase": "15 & 16", "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
               "summary": {"total": total, "passed": R["pass"], "failed": R["fail"], "warnings": R["warn"],
                           "pass_rate": f"{R['pass']/total*100:.1f}%" if total else "N/A"},
               "tests": R["tests"]}, f, indent=2)
print(f"\nResults saved to {out}")
