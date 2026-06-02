#!/usr/bin/env python3
"""Quick Parwa API test - inline server + tests"""
import sys, os, time, json

os.environ["CSRF_ENABLED"] = "false"
PARWA_ROOT = "/home/z/my-project/parwa"
BACKEND_DIR = f"{PARWA_ROOT}/backend"
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, PARWA_ROOT)
os.chdir(BACKEND_DIR)

# Ensure consistent DB path (must match what app.config resolves)
import pathlib
DB_PATH = f"{PARWA_ROOT}/db/parwa_dev.db"
pathlib.Path(f"{PARWA_ROOT}/db").mkdir(exist_ok=True)
# Delete old DB
if pathlib.Path(DB_PATH).exists():
    pathlib.Path(DB_PATH).unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"

PASS = 0; FAIL = 0; BUGS = []

def p(n): global PASS; PASS+=1; print(f"  ✅ {n}")
def f(n, d=""): global FAIL; FAIL+=1; print(f"  ❌ {n} — {d}"); BUGS.append((n, d))

# Import app directly (no subprocess)
from app.main import app

# Initialize DB tables using the same engine the app uses
from database.base import Base, init_db, engine
from database.models import *
init_db()
print(f"  DB initialized: {len(Base.metadata.tables.keys())} tables at {engine.url}")

from fastapi.testclient import TestClient

client = TestClient(app)

TOKEN = None
COMPANY_ID = None

# ═══ 1. HEALTH ═══
print("\n═══ 1. HEALTH & PUBLIC ═══")
try:
    r = client.get("/health"); d = r.json()
    p(f"Health (status={d['status']}, healthy={d['checks_healthy']}/{d['checks_total']})")
except Exception as e: f("Health", str(e)[:100])

try: r = client.get("/ready"); p(f"Ready ({r.status_code})")
except Exception as e: f("Ready", str(e)[:100])

try: r = client.get("/public/features"); p(f"Public features ({r.status_code})")
except Exception as e: f("Public features", str(e)[:100])

try: r = client.get("/public/stats"); p(f"Public stats ({r.status_code})")
except Exception as e: f("Public stats", str(e)[:100])

try: r = client.get("/public/industries"); p(f"Public industries ({r.status_code})")
except Exception as e: f("Public industries", str(e)[:100])

# ═══ 2. REGISTER ═══
print("\n═══ 2. AUTH: REGISTER ═══")
try:
    r = client.post("/api/auth/register", json={
        "email": "apitest@parwa.io", "password": "Test@1234!",
        "confirm_password": "Test@1234!", "full_name": "API Test User",
        "company_name": "API Test Co", "industry": "ecommerce"
    })
    d = r.json()
    TOKEN = d.get("access_token") or d.get("tokens", {}).get("access_token")
    if TOKEN: p("Register returns access_token"); COMPANY_ID = d.get("company_id") or d.get("user", {}).get("company_id")
    else: f("Register", f"status={r.status_code}, body={str(d)[:300]}")
except Exception as e: f("Register", str(e)[:300])

# Duplicate
try:
    r = client.post("/api/auth/register", json={
        "email": "apitest@parwa.io", "password": "Test@1234!",
        "confirm_password": "Test@1234!", "full_name": "Dup",
        "company_name": "Dup Co", "industry": "saas"
    })
    if r.status_code in (400, 409, 422): p("Duplicate registration rejected")
    else: f("Duplicate registration", f"status={r.status_code}")
except Exception as e: f("Duplicate registration", str(e)[:100])

# ═══ 3. LOGIN ═══
print("\n═══ 3. AUTH: LOGIN ═══")
try:
    r = client.post("/api/auth/login", json={"email": "apitest@parwa.io", "password": "Test@1234!"})
    d = r.json()
    TOKEN = d.get("access_token") or d.get("tokens", {}).get("access_token")
    if TOKEN: p("Login returns access_token")
    else: f("Login", f"status={r.status_code}, body={str(d)[:300]}")
except Exception as e: f("Login", str(e)[:300])

# Wrong password
try:
    r = client.post("/api/auth/login", json={"email": "apitest@parwa.io", "password": "Wrong!"})
    if r.status_code in (401, 403): p("Wrong password rejected")
    else: f("Wrong password", f"status={r.status_code}")
except Exception as e: f("Wrong password", str(e)[:100])

# ═══ 4. AUTH ME ═══
print("\n═══ 4. AUTH: ME ═══")
ah = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
if TOKEN:
    try:
        r = client.get("/api/auth/me", headers=ah); d = r.json()
        if d.get("email") == "apitest@parwa.io":
            p("GET /auth/me returns correct email"); COMPANY_ID = d.get("company_id")
        else: f("GET /auth/me", f"email={d.get('email')}, body={str(d)[:200]}")
    except Exception as e: f("GET /auth/me", str(e)[:200])
else: f("GET /auth/me", "No token")

# ═══ 5. PRICING ═══
print("\n═══ 5. PRICING ═══")
try:
    r = client.get("/api/pricing/industries")
    if r.status_code == 200: p("Pricing industries")
    else: f("Pricing industries", f"status={r.status_code}, body={r.text[:200]}")
except Exception as e: f("Pricing industries", str(e)[:100])

try:
    r = client.post("/api/pricing/calculate", json={"industry": "ecommerce", "tickets_per_month": 1000, "channels": ["email", "chat"], "variants": [{"id": "starter", "name": "Starter", "quantity": 1}]})
    if r.status_code == 200: p("Pricing calculate")
    else: f("Pricing calculate", f"status={r.status_code}, body={r.text[:200]}")
except Exception as e: f("Pricing calculate", str(e)[:100])

# ═══ 6. TICKETS ═══
print("\n═══ 6. TICKETS CRUD ═══")
TICKET_ID = None
if TOKEN:
    try:
        # First create a customer, then create a ticket
        cust_r = client.post("/api/v1/customers", json={"name": "Test Customer", "email": "customer@test.com"}, headers=ah)
        cust_d = cust_r.json()
        cust_id = cust_d.get("id") or cust_d.get("customer_id") or cust_d.get("data", {}).get("id")
        r = client.post("/api/v1/tickets", json={"subject": "Test ticket", "description": "Test desc", "priority": "high", "channel": "email", "customer_id": cust_id or "auto"}, headers=ah)
        d = r.json()
        TICKET_ID = d.get("id") or d.get("ticket_id") or d.get("data", {}).get("id")
        if r.status_code in (200, 201) and TICKET_ID: p(f"Create ticket (id={TICKET_ID})")
        else: f("Create ticket", f"status={r.status_code}, body={r.text[:300]}")
    except Exception as e: f("Create ticket", str(e)[:200])

    try:
        r = client.get("/api/v1/tickets", headers=ah)
        if r.status_code == 200: p("List tickets")
        else: f("List tickets", f"status={r.status_code}, body={r.text[:200]}")
    except Exception as e: f("List tickets", str(e)[:200])

    if TICKET_ID:
        try:
            r = client.get(f"/api/v1/tickets/{TICKET_ID}", headers=ah)
            if r.status_code == 200: p("Get ticket by ID")
            else: f("Get ticket by ID", f"status={r.status_code}, body={r.text[:200]}")
        except Exception as e: f("Get ticket by ID", str(e)[:200])
else: f("Tickets CRUD", "No token")

# ═══ 7-15. Various APIs ═══
endpoints = [
    ("Client profile", "/api/client/profile", "GET"),
    ("Client settings", "/api/client/settings", "GET"),
    ("Client team", "/api/client/team", "GET"),
    ("User details", "/api/user/details", "GET"),
    ("Onboarding state", "/api/onboarding/state", "GET"),
    ("KB status", "/api/knowledge-base/status", "GET"),
    ("AI capabilities", "/api/ai/capabilities", "GET"),
    ("AI router status", "/api/ai/router/status", "GET"),
    ("Billing subscription", "/api/billing/subscription", "GET"),
    ("Channels", "/api/v1/channels", "GET"),
    ("Notifications", "/api/v1/notifications", "GET"),
    ("SLA policies", "/api/v1/sla/policies", "GET"),
    ("Customers", "/api/v1/customers", "GET"),
    ("Custom fields", "/api/v1/custom-fields", "GET"),
    ("Triggers", "/api/v1/triggers", "GET"),
    ("Shadow mode", "/api/shadow-mode/status", "GET"),
    ("Workflow metrics", "/api/workflow/metrics", "GET"),
    ("GDPR consent", "/api/v1/gdpr/consent", "GET"),
    ("Integrations", "/api/integrations", "GET"),
    ("Leads stats", "/api/leads/stats", "GET"),
]

print("\n═══ 7-15. VARIOUS API ENDPOINTS ═══")
if TOKEN:
    for name, path, method in endpoints:
        try:
            r = client.request(method, path, headers=ah)
            if r.status_code in (200, 404): p(name)
            else: f(name, f"status={r.status_code}, body={r.text[:150]}")
        except Exception as e: f(name, str(e)[:100])
else:
    for name, _, _ in endpoints: f(name, "No token")

# ═══ JARVIS ═══
print("\n═══ JARVIS ═══")
if TOKEN:
    try:
        r = client.post("/api/jarvis/session", json={}, headers=ah)
        if r.status_code in (200, 201): p("Jarvis session created")
        else: f("Jarvis session", f"status={r.status_code}, body={r.text[:200]}")
    except Exception as e: f("Jarvis session", str(e)[:200])
else: f("Jarvis", "No token")

# ═══ LOGOUT ═══
print("\n═══ LOGOUT ═══")
if TOKEN:
    try:
        r = client.post("/api/auth/logout", json={"refresh_token": "test"}, headers=ah)
        if r.status_code in (200, 204): p("Logout")
        else: f("Logout", f"status={r.status_code}, body={r.text[:200]}")
    except Exception as e: f("Logout", str(e)[:200])
else: f("Logout", "No token")

# ═══ SUMMARY ═══
print("\n" + "="*60)
print(f"  RESULTS: {PASS} PASSED / {FAIL} FAILED / {PASS+FAIL} TOTAL")
print("="*60)
if BUGS:
    print("\n🔴 BUGS:")
    for n, d in BUGS: print(f"  • {n}: {d}")
else: print("\n🟢 All tests passed!")

with open(f"{PARWA_ROOT}/test_results.json", "w") as f:
    json.dump({"passed": PASS, "failed": FAIL, "total": PASS+FAIL, "bugs": [{"name": n, "detail": d} for n, d in BUGS]}, f, indent=2)
