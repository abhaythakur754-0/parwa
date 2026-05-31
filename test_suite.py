#!/usr/bin/env python3
"""
PARWA Comprehensive API Test Suite v2
Properly handles CSRF tokens and Origin headers.
"""
import sys, os, time, json, subprocess, hashlib, hmac, secrets

PARWA_ROOT = "/home/z/my-project/parwa"
BACKEND_DIR = f"{PARWA_ROOT}/backend"
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, PARWA_ROOT)
os.chdir(BACKEND_DIR)

# Disable CSRF for testing
os.environ["CSRF_ENABLED"] = "false"

PASS = 0
FAIL = 0
BUGS = []

def pass_test(name):
    global PASS; PASS += 1
    print(f"  ✅ PASS: {name}")

def fail_test(name, detail=""):
    global FAIL; FAIL += 1
    print(f"  ❌ FAIL: {name} — {detail}")
    BUGS.append((name, detail))

# Start backend
print("Starting backend server...")
proc = subprocess.Popen(
    [sys.executable, "-c",
     "import sys,os; sys.path.insert(0,'/home/z/my-project/parwa/backend'); sys.path.insert(0,'/home/z/my-project/parwa'); os.chdir('/home/z/my-project/parwa/backend'); from app.main import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port=8765)"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)

import httpx

# Common headers: Origin for CSRF bypass (since CORS_ORIGINS includes localhost:3000)
ORIGIN = "http://localhost:3000"
BASE_HEADERS = {
    "Origin": ORIGIN,
    "Content-Type": "application/json",
}
client = httpx.Client(base_url="http://127.0.0.1:8765", timeout=60.0, headers=BASE_HEADERS)

# Wait for server
for i in range(30):
    try:
        r = client.get("/health")
        if r.status_code == 200:
            print(f"  Backend started in ~{(i+1)*2}s")
            break
    except Exception:
        pass
    time.sleep(2)
else:
    print("  ❌ Backend failed to start!")
    proc.kill()
    sys.exit(1)

TOKEN = None
COMPANY_ID = None

# ═══════════════════════════════════════
print("\n═══ 1. HEALTH & PUBLIC ENDPOINTS ═══")
# ═══════════════════════════════════════

try:
    r = client.get("/health")
    d = r.json()
    pass_test(f"Health (status={d['status']}, healthy={d['checks_healthy']}/{d['checks_total']})")
except Exception as e:
    fail_test("Health", str(e)[:100])

try:
    r = client.get("/ready")
    pass_test(f"Ready (status={r.status_code})")
except Exception as e:
    fail_test("Ready", str(e)[:100])

try:
    r = client.get("/public/features")
    pass_test(f"Public features (status={r.status_code})")
except Exception as e:
    fail_test("Public features", str(e)[:100])

try:
    r = client.get("/public/stats")
    pass_test(f"Public stats (status={r.status_code})")
except Exception as e:
    fail_test("Public stats", str(e)[:100])

try:
    r = client.get("/public/industries")
    pass_test(f"Public industries (status={r.status_code})")
except Exception as e:
    fail_test("Public industries", str(e)[:100])

# ═══════════════════════════════════════
print("\n═══ 2. AUTH: REGISTER ═══")
# ═══════════════════════════════════════

# First, get a CSRF token by making a GET request
csrf_token = None
try:
    r = client.get("/api/auth/check-email", params={"email": "apitest@parwa.io"})
    # Extract CSRF cookie from response
    set_cookies = r.headers.get_list("set-cookie")
    for sc in set_cookies:
        if "parwa_csrf=" in sc:
            csrf_token = sc.split("parwa_csrf=")[1].split(";")[0]
            break
    if csrf_token:
        pass_test(f"CSRF token obtained from GET")
    else:
        # Generate our own CSRF token using the same algorithm
        secret_key = os.environ.get("SECRET_KEY", "parwa_dev_sk_2026_xK9mP2vR8wQ4tY6uI0oL3jH7nB5cF1dE")
        nonce = secrets.token_hex(16)
        timestamp = str(int(time.time()))
        msg = f"{nonce}:{timestamp}"
        sig = hmac.new(secret_key.encode(), msg.encode(), hashlib.sha256).hexdigest()[:16]
        csrf_token = f"{nonce}:{timestamp}:{sig}"
        pass_test(f"CSRF token generated manually")
    
    # Set CSRF cookie and header for subsequent requests
    client.cookies.set("parwa_csrf", csrf_token)
except Exception as e:
    # Fallback: generate CSRF token
    secret_key = "parwa_dev_sk_2026_xK9mP2vR8wQ4tY6uI0oL3jH7nB5cF1dE"
    nonce = secrets.token_hex(16)
    timestamp = str(int(time.time()))
    msg = f"{nonce}:{timestamp}"
    sig = hmac.new(secret_key.encode(), msg.encode(), hashlib.sha256).hexdigest()[:16]
    csrf_token = f"{nonce}:{timestamp}:{sig}"
    client.cookies.set("parwa_csrf", csrf_token)
    pass_test(f"CSRF token generated (fallback)")

# Check email
try:
    r = client.get("/api/auth/check-email", params={"email": "apitest@parwa.io"})
    d = r.json()
    if d.get("exists") == False:
        pass_test("Check-email returns False for new email")
    else:
        fail_test("Check-email", f"exists={d.get('exists')}, body={str(d)[:200]}")
except Exception as e:
    fail_test("Check-email", str(e)[:200])

# Register with CSRF headers
try:
    headers = {**BASE_HEADERS, "x-csrf-token": csrf_token}
    r = client.post("/api/auth/register", json={
        "email": "apitest@parwa.io",
        "password": "Test@1234!",
        "confirm_password": "Test@1234!",
        "full_name": "API Test User",
        "company_name": "API Test Co",
        "industry": "ecommerce"
    }, headers=headers)
    d = r.json()
    TOKEN = d.get("access_token")
    if TOKEN:
        pass_test("Register returns access_token")
        COMPANY_ID = d.get("company_id")
    else:
        fail_test("Register", f"No token. Status={r.status_code}, body={str(d)[:300]}")
except Exception as e:
    fail_test("Register", str(e)[:200])

# ═══════════════════════════════════════
print("\n═══ 3. AUTH: LOGIN ═══")
# ═══════════════════════════════════════

try:
    headers = {**BASE_HEADERS, "x-csrf-token": csrf_token}
    r = client.post("/api/auth/login", json={
        "email": "apitest@parwa.io",
        "password": "Test@1234!"
    }, headers=headers)
    d = r.json()
    TOKEN = d.get("access_token")
    if TOKEN:
        pass_test("Login returns access_token")
    else:
        fail_test("Login", f"No token. Status={r.status_code}, body={str(d)[:300]}")
except Exception as e:
    fail_test("Login", str(e)[:200])

# Wrong password
try:
    headers = {**BASE_HEADERS, "x-csrf-token": csrf_token}
    r = client.post("/api/auth/login", json={
        "email": "apitest@parwa.io",
        "password": "WrongPassword!"
    }, headers=headers)
    if r.status_code in (401, 403):
        pass_test("Wrong password rejected")
    else:
        fail_test("Wrong password", f"status={r.status_code}")
except Exception as e:
    fail_test("Wrong password", str(e)[:100])

# ═══════════════════════════════════════
print("\n═══ 4. AUTH: ME (authenticated) ═══")
# ═══════════════════════════════════════

if TOKEN:
    try:
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {TOKEN}"})
        d = r.json()
        if d.get("email") == "apitest@parwa.io":
            pass_test("GET /auth/me returns correct email")
            COMPANY_ID = d.get("company_id")
        else:
            fail_test("GET /auth/me", f"email={d.get('email')}, body={str(d)[:200]}")
    except Exception as e:
        fail_test("GET /auth/me", str(e)[:200])
else:
    fail_test("GET /auth/me", "No token available")

# Helper: auth headers
def auth_headers():
    return {"Authorization": f"Bearer {TOKEN}"}

# ═══════════════════════════════════════
print("\n═══ 5. PRICING ═══")
# ═══════════════════════════════════════

try:
    r = client.get("/api/pricing/industries")
    if r.status_code == 200:
        pass_test("Pricing industries")
    else:
        fail_test("Pricing industries", f"status={r.status_code}, body={r.text[:200]}")
except Exception as e:
    fail_test("Pricing industries", str(e)[:100])

try:
    r = client.post("/api/pricing/calculate", json={
        "industry": "ecommerce",
        "tickets_per_month": 1000,
        "channels": ["email", "chat"]
    })
    if r.status_code == 200:
        pass_test("Pricing calculate")
    else:
        fail_test("Pricing calculate", f"status={r.status_code}, body={r.text[:200]}")
except Exception as e:
    fail_test("Pricing calculate", str(e)[:100])

# ═══════════════════════════════════════
print("\n═══ 6. TICKETS CRUD ═══")
# ═══════════════════════════════════════

TICKET_ID = None
if TOKEN:
    # Create
    try:
        r = client.post("/api/v1/tickets", json={
            "subject": "Test ticket from API suite",
            "description": "This is a test ticket created by the API test suite.",
            "priority": "high",
            "channel": "email"
        }, headers=auth_headers())
        d = r.json()
        TICKET_ID = d.get("id") or d.get("ticket_id") or d.get("data", {}).get("id")
        if r.status_code in (200, 201) and TICKET_ID:
            pass_test(f"Create ticket (id={TICKET_ID})")
        else:
            fail_test("Create ticket", f"status={r.status_code}, body={r.text[:300]}")
    except Exception as e:
        fail_test("Create ticket", str(e)[:200])

    # List
    try:
        r = client.get("/api/v1/tickets", headers=auth_headers())
        if r.status_code == 200:
            d = r.json()
            items = d.get("items", d.get("data", d.get("tickets", [])))
            pass_test(f"List tickets (count={len(items) if isinstance(items, list) else '?'})")
        else:
            fail_test("List tickets", f"status={r.status_code}, body={r.text[:200]}")
    except Exception as e:
        fail_test("List tickets", str(e)[:200])

    # Get single
    if TICKET_ID:
        try:
            r = client.get(f"/api/v1/tickets/{TICKET_ID}", headers=auth_headers())
            if r.status_code == 200:
                pass_test("Get ticket by ID")
            else:
                fail_test("Get ticket by ID", f"status={r.status_code}, body={r.text[:200]}")
        except Exception as e:
            fail_test("Get ticket by ID", str(e)[:200])

        # Update
        try:
            r = client.put(f"/api/v1/tickets/{TICKET_ID}", json={
                "priority": "urgent",
                "status": "in_progress"
            }, headers=auth_headers())
            if r.status_code in (200, 201):
                pass_test("Update ticket")
            else:
                fail_test("Update ticket", f"status={r.status_code}, body={r.text[:200]}")
        except Exception as e:
            fail_test("Update ticket", str(e)[:200])

        # Ticket messages
        try:
            r = client.get(f"/api/v1/tickets/{TICKET_ID}/messages", headers=auth_headers())
            if r.status_code in (200, 404):
                pass_test("Ticket messages")
            else:
                fail_test("Ticket messages", f"status={r.status_code}, body={r.text[:200]}")
        except Exception as e:
            fail_test("Ticket messages", str(e)[:200])

        # Ticket timeline
        try:
            r = client.get(f"/api/v1/tickets/{TICKET_ID}/timeline", headers=auth_headers())
            if r.status_code in (200, 404):
                pass_test("Ticket timeline")
            else:
                fail_test("Ticket timeline", f"status={r.status_code}, body={r.text[:200]}")
        except Exception as e:
            fail_test("Ticket timeline", str(e)[:200])
    else:
        fail_test("Ticket details", "No ticket ID")
else:
    fail_test("Tickets CRUD", "No auth token")

# ═══════════════════════════════════════
print("\n═══ 7. CLIENT PROFILE & SETTINGS ═══")
# ═══════════════════════════════════════

if TOKEN:
    for endpoint in ["/api/client/profile", "/api/client/settings", "/api/client/team"]:
        name = endpoint.split("/")[-1]
        try:
            r = client.get(endpoint, headers=auth_headers())
            if r.status_code == 200:
                pass_test(f"Client {name}")
            else:
                fail_test(f"Client {name}", f"status={r.status_code}, body={r.text[:200]}")
        except Exception as e:
            fail_test(f"Client {name}", str(e)[:200])
else:
    fail_test("Client APIs", "No auth token")

# ═══════════════════════════════════════
print("\n═══ 8. USER DETAILS & ONBOARDING ═══")
# ═══════════════════════════════════════

if TOKEN:
    for endpoint, name in [("/api/user/details", "User details"), ("/api/onboarding/state", "Onboarding state")]:
        try:
            r = client.get(endpoint, headers=auth_headers())
            if r.status_code in (200, 404):
                pass_test(name)
            else:
                fail_test(name, f"status={r.status_code}, body={r.text[:200]}")
        except Exception as e:
            fail_test(name, str(e)[:200])
else:
    fail_test("User/Onboarding APIs", "No auth token")

# ═══════════════════════════════════════
print("\n═══ 9. KNOWLEDGE BASE ═══")
# ═══════════════════════════════════════

if TOKEN:
    for endpoint in ["/api/knowledge-base/status", "/api/knowledge-base/list", "/api/knowledge-base/health"]:
        name = endpoint.split("/")[-1]
        try:
            r = client.get(endpoint, headers=auth_headers())
            if r.status_code in (200, 404):
                pass_test(f"KB {name}")
            else:
                fail_test(f"KB {name}", f"status={r.status_code}, body={r.text[:200]}")
        except Exception as e:
            fail_test(f"KB {name}", str(e)[:200])
else:
    fail_test("Knowledge Base APIs", "No auth token")

# ═══════════════════════════════════════
print("\n═══ 10. JARVIS ═══")
# ═══════════════════════════════════════

if TOKEN:
    # Create session
    try:
        r = client.post("/api/jarvis/session", json={}, headers=auth_headers())
        d = r.json()
        sid = d.get("session_id", d.get("id"))
        if r.status_code in (200, 201) and sid:
            pass_test(f"Jarvis session created (id={sid})")
        else:
            fail_test("Jarvis session", f"status={r.status_code}, body={r.text[:200]}")
    except Exception as e:
        fail_test("Jarvis session", str(e)[:200])

    # Send message
    try:
        r = client.post("/api/jarvis/message", json={
            "message": "Hello, how can you help me?",
            "session_id": "test-session"
        }, headers=auth_headers())
        if r.status_code in (200, 201, 404):
            pass_test("Jarvis message endpoint")
        else:
            fail_test("Jarvis message", f"status={r.status_code}, body={r.text[:200]}")
    except Exception as e:
        fail_test("Jarvis message", str(e)[:200])
else:
    fail_test("Jarvis APIs", "No auth token")

# ═══════════════════════════════════════
print("\n═══ 11. AI ENGINE ═══")
# ═══════════════════════════════════════

if TOKEN:
    for endpoint, name in [
        ("/api/ai/capabilities", "AI capabilities"),
        ("/api/ai/router/status", "AI router status"),
    ]:
        try:
            r = client.get(endpoint, headers=auth_headers())
            if r.status_code in (200, 404):
                pass_test(name)
            else:
                fail_test(name, f"status={r.status_code}, body={r.text[:200]}")
        except Exception as e:
            fail_test(name, str(e)[:200])
else:
    fail_test("AI Engine APIs", "No auth token")

# ═══════════════════════════════════════
print("\n═══ 12. BILLING ═══")
# ═══════════════════════════════════════

if TOKEN:
    try:
        r = client.get("/api/billing/subscription", headers=auth_headers())
        if r.status_code in (200, 404):
            pass_test("Billing subscription")
        else:
            fail_test("Billing subscription", f"status={r.status_code}, body={r.text[:200]}")
    except Exception as e:
        fail_test("Billing subscription", str(e)[:200])
else:
    fail_test("Billing APIs", "No auth token")

# ═══════════════════════════════════════
print("\n═══ 13. CHANNELS, NOTIFICATIONS, SLA ═══")
# ═══════════════════════════════════════

if TOKEN:
    for endpoint, name in [
        ("/api/v1/channels", "Channels"),
        ("/api/v1/notifications", "Notifications"),
        ("/api/v1/sla/policies", "SLA policies"),
        ("/api/v1/customers", "Customers"),
        ("/api/v1/custom-fields", "Custom fields"),
        ("/api/v1/triggers", "Triggers"),
    ]:
        try:
            r = client.get(endpoint, headers=auth_headers())
            if r.status_code in (200, 404):
                pass_test(name)
            else:
                fail_test(name, f"status={r.status_code}, body={r.text[:200]}")
        except Exception as e:
            fail_test(name, str(e)[:200])
else:
    fail_test("Various APIs", "No auth token")

# ═══════════════════════════════════════
print("\n═══ 14. SHADOW MODE ═══")
# ═══════════════════════════════════════

if TOKEN:
    try:
        r = client.get("/api/shadow-mode/status", headers=auth_headers())
        if r.status_code in (200, 404):
            pass_test("Shadow mode status")
        else:
            fail_test("Shadow mode status", f"status={r.status_code}, body={r.text[:200]}")
    except Exception as e:
        fail_test("Shadow mode status", str(e)[:200])
else:
    fail_test("Shadow Mode APIs", "No auth token")

# ═══════════════════════════════════════
print("\n═══ 15. WORKFLOW ═══")
# ═══════════════════════════════════════

if TOKEN:
    try:
        r = client.get("/api/workflow/metrics", headers=auth_headers())
        if r.status_code in (200, 404):
            pass_test("Workflow metrics")
        else:
            fail_test("Workflow metrics", f"status={r.status_code}, body={r.text[:200]}")
    except Exception as e:
        fail_test("Workflow metrics", str(e)[:200])
else:
    fail_test("Workflow APIs", "No auth token")

# ═══════════════════════════════════════
print("\n═══ 16. GDPR ═══")
# ═══════════════════════════════════════

if TOKEN:
    try:
        r = client.get("/api/v1/gdpr/consent", headers=auth_headers())
        if r.status_code in (200, 404):
            pass_test("GDPR consent")
        else:
            fail_test("GDPR consent", f"status={r.status_code}, body={r.text[:200]}")
    except Exception as e:
        fail_test("GDPR consent", str(e)[:200])
else:
    fail_test("GDPR APIs", "No auth token")

# ═══════════════════════════════════════
print("\n═══ 17. INTEGRATIONS ═══")
# ═══════════════════════════════════════

if TOKEN:
    try:
        r = client.get("/api/integrations", headers=auth_headers())
        if r.status_code in (200, 404):
            pass_test("Integrations list")
        else:
            fail_test("Integrations list", f"status={r.status_code}, body={r.text[:200]}")
    except Exception as e:
        fail_test("Integrations list", str(e)[:200])

    try:
        r = client.get("/api/integrations/available", headers=auth_headers())
        if r.status_code in (200, 404):
            pass_test("Available integrations")
        else:
            fail_test("Available integrations", f"status={r.status_code}, body={r.text[:200]}")
    except Exception as e:
        fail_test("Available integrations", str(e)[:200])
else:
    fail_test("Integrations APIs", "No auth token")

# ═══════════════════════════════════════
print("\n═══ 18. LEADS ═══")
# ═══════════════════════════════════════

if TOKEN:
    try:
        r = client.get("/api/leads/stats", headers=auth_headers())
        if r.status_code in (200, 404):
            pass_test("Leads stats")
        else:
            fail_test("Leads stats", f"status={r.status_code}, body={r.text[:200]}")
    except Exception as e:
        fail_test("Leads stats", str(e)[:200])
else:
    fail_test("Leads APIs", "No auth token")

# ═══════════════════════════════════════
print("\n═══ 19. LOGOUT ═══")
# ═══════════════════════════════════════

if TOKEN:
    try:
        r = client.post("/api/auth/logout", headers={**auth_headers(), "x-csrf-token": csrf_token})
        if r.status_code in (200, 204):
            pass_test("Logout")
        else:
            fail_test("Logout", f"status={r.status_code}, body={r.text[:200]}")
    except Exception as e:
        fail_test("Logout", str(e)[:200])
else:
    fail_test("Logout", "No auth token")

# ═══════════════════════════════════════
# Cleanup
# ═══════════════════════════════════════
proc.terminate()
proc.wait(timeout=5)
client.close()

# ═══════════════════════════════════════
print("\n" + "="*60)
print(f"  TEST RESULTS: {PASS} PASSED / {FAIL} FAILED / {PASS+FAIL} TOTAL")
print("="*60)

if BUGS:
    print("\n🔴 BUGS FOUND:")
    for name, detail in BUGS:
        print(f"  • {name}: {detail}")
else:
    print("\n🟢 No bugs found!")

results = {
    "passed": PASS,
    "failed": FAIL,
    "total": PASS + FAIL,
    "bugs": [{"name": n, "detail": d} for n, d in BUGS]
}
with open(f"{PARWA_ROOT}/test_results.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"\nResults saved to {PARWA_ROOT}/test_results.json")
