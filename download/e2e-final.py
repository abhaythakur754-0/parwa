#!/usr/bin/env python3
"""
PARWA Complete E2E Journey Test - FINAL VERSION
Runs everything in a single process with daemon servers
"""
import os, sys, json, time, subprocess, threading, traceback
from datetime import datetime

SCREENSHOT_DIR = "/home/z/my-project/download/journey-proof"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

results = {
    "test_name": "PARWA Complete E2E Journey",
    "timestamp": datetime.now().isoformat(),
    "steps": [],
    "total_passed": 0,
    "total_failed": 0,
    "console_errors": [],
    "api_tests": [],
}

def log_step(step_num, name, passed, details=""):
    icon = "✅" if passed else "❌"
    print(f"  {icon} Step {step_num}: {name} - {details}")
    results["steps"].append({"step": step_num, "name": name, "passed": passed, "details": details})
    if passed: results["total_passed"] += 1
    else: results["total_failed"] += 1

# Reset database
db_path = "/home/z/my-project/db/custom.db"
if os.path.exists(db_path): os.remove(db_path)
open(db_path, "w").close()

print("\n" + "=" * 60)
print("🚀 PARWA COMPLETE E2E JOURNEY TEST")
print("=" * 60)

# ============================================================
# Start Backend
# ============================================================
print("\n📦 Starting Backend...")
backend_proc = subprocess.Popen(
    ["/home/z/.local/bin/uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
    cwd="/home/z/my-project/mini-services/parwa-backend",
    env={**os.environ, "ENCRYPTION_MASTER_KEY": "parwa-prod-encryption-key-2024", "JWT_SECRET_KEY": "parwa-super-secret-jwt-key-change-in-production"},
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
)
time.sleep(4)

import urllib.request
try:
    resp = urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5)
    print(f"  ✅ Backend: {json.loads(resp.read())}")
except Exception as e:
    print(f"  ❌ Backend failed: {e}")
    sys.exit(1)

# ============================================================
# Start Frontend
# ============================================================
print("\n📦 Starting Frontend...")
frontend_proc = subprocess.Popen(
    ["node", "node_modules/.bin/next", "dev", "-p", "3000"],
    cwd="/home/z/my-project",
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
)
time.sleep(10)

try:
    resp = urllib.request.urlopen("http://127.0.0.1:3000", timeout=10)
    print(f"  ✅ Frontend: status={resp.status}")
except Exception as e:
    print(f"  ❌ Frontend failed: {e}")
    sys.exit(1)

# ============================================================
# Backend API Tests
# ============================================================
print("\n📦 Backend API Tests...")
import urllib.request

timestamp = int(time.time())
test_email = f"parwa-api-{timestamp}@test.io"

def api_call(method, path, data=None, token=None):
    url = f"http://127.0.0.1:8000{path}"
    headers = {"Content-Type": "application/json"}
    if token: headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read())

# Register
reg = api_call("POST", "/api/v1/auth/register", {"email": test_email, "name": "API Test", "password": "Testpass123!"})
token = reg["access_token"]
log_step(0, "API: Register", bool(token), f"email={test_email}")

# Login
login = api_call("POST", "/api/v1/auth/login", {"email": test_email, "password": "Testpass123!"})
log_step(0, "API: Login", bool(login.get("access_token")), f"type={login.get('token_type')}")

# Get Me
me = api_call("GET", "/api/v1/auth/me", token=token)
log_step(0, "API: Get Me", me.get("email") == test_email, f"name={me.get('name')}")

# Industry & Variant
iv = api_call("POST", "/api/v1/onboarding/industry-variant", {"industry": "saas", "variant": "parwa"}, token)
log_step(0, "API: Industry/Variant", iv.get("variant") == "parwa", f"industry={iv.get('industry')}")

# Legal Consent
lc = api_call("POST", "/api/v1/onboarding/legal-consent", {"accepted": True}, token)
log_step(0, "API: Legal Consent", lc.get("legal_accepted"), f"accepted={lc.get('legal_accepted')}")

# Complete Steps
for s in [3, 4, 5]:
    cs = api_call("POST", "/api/v1/onboarding/complete-step", {"step": s}, token)
    log_step(0, f"API: Complete Step {s}", True, f"current_step={cs.get('current_step')}")

# Get State
state = api_call("GET", "/api/v1/onboarding/state", token=token)
log_step(0, "API: Onboarding State", True, f"step={state.get('current_step')}, kb={state.get('kb_uploaded')}, ai={state.get('ai_configured')}")

# Activate
try:
    act = api_call("POST", "/api/v1/onboarding/activate", {}, token)
    log_step(0, "API: Activate", act.get("onboarding_complete"), f"msg={act.get('message')}")
except Exception as e:
    log_step(0, "API: Activate", False, str(e)[:80])

# Variants
try:
    v = api_call("GET", "/api/v1/variants/list", token=token)
    log_step(0, "API: Variants", True, f"count={len(v.get('variants', []))}")
except Exception as e:
    log_step(0, "API: Variants", False, str(e)[:80])

# Audit
try:
    a = api_call("GET", "/api/v1/audit/entries?limit=5", token=token)
    log_step(0, "API: Audit", True, f"entries={len(a.get('entries', []))}")
except Exception as e:
    log_step(0, "API: Audit", False, str(e)[:80])

# ============================================================
# Playwright E2E
# ============================================================
print("\n📦 Playwright Frontend E2E Tests...")

try:
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        console_errors = []
        
        page = context.new_page()
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: console_errors.append(err.message))
        
        BASE = "http://127.0.0.1:3000"
        
        # STEP 1: Landing Page
        print("  🖥️ Landing Page...")
        try:
            page.goto(BASE, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)
            page.screenshot(path=f"{SCREENSHOT_DIR}/01-landing-page.png", full_page=True)
            h1 = page.locator("h1").first.text_content(timeout=5000) or ""
            log_step(1, "Landing Page", "Transform Support" in h1 and page.locator('a[href="/signup"]').count() > 0, f"heading={h1[:50]}")
        except Exception as e:
            log_step(1, "Landing Page", False, str(e)[:80])
        
        # STEP 2: Signup Page
        print("  🖥️ Signup Page...")
        try:
            page.click('a[href="/signup"]', timeout=10000)
            page.wait_for_url("**/signup", timeout=10000)
            page.wait_for_timeout(1000)
            page.screenshot(path=f"{SCREENSHOT_DIR}/02-signup-page.png", full_page=True)
            log_step(2, "Signup Page", page.locator('input#name').count() > 0 and page.locator('input#email').count() > 0, "Form fields present")
        except Exception as e:
            log_step(2, "Signup Page", False, str(e)[:80])
        
        # STEP 3: Fill & Submit Signup
        print("  🖥️ Signup Submit...")
        try:
            ts = int(time.time())
            email = f"e2e-{ts}@test.io"
            page.fill('input#name', 'E2E User')
            page.fill('input#email', email)
            page.fill('input#password', 'Testpass123!')
            page.screenshot(path=f"{SCREENSHOT_DIR}/03-signup-filled.png", full_page=True)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)
            url = page.url
            page.screenshot(path=f"{SCREENSHOT_DIR}/04-after-signup.png", full_page=True)
            log_step(3, "Signup → Redirect", "/onboarding" in url or "/dashboard" in url, f"url={url}")
        except Exception as e:
            log_step(3, "Signup Submit", False, str(e)[:80])
        
        # STEP 4: Onboarding Step 1 - Industry & Variant
        print("  🖥️ Onboarding Step 1...")
        try:
            if "/onboarding" not in page.url:
                page.goto(f"{BASE}/onboarding", wait_until="networkidle", timeout=15000)
                page.wait_for_timeout(3000)
            page.screenshot(path=f"{SCREENSHOT_DIR}/05-step1-initial.png", full_page=True)
            
            # Select SaaS
            page.locator('text=SaaS').first.click()
            page.wait_for_timeout(500)
            page.screenshot(path=f"{SCREENSHOT_DIR}/06-step1-saas.png", full_page=True)
            
            # Select PARWA
            page.locator('text=PARWA').first.click()
            page.wait_for_timeout(1500)
            page.screenshot(path=f"{SCREENSHOT_DIR}/07-step1-parwa.png", full_page=True)
            
            # Click Continue
            page.locator('button:has-text("Continue")').first.click()
            page.wait_for_timeout(1000)
            page.screenshot(path=f"{SCREENSHOT_DIR}/08-step1-done.png", full_page=True)
            log_step(4, "Step 1: Industry & Variant", True, "SaaS + PARWA")
        except Exception as e:
            log_step(4, "Step 1", False, str(e)[:80])
        
        # STEP 5: Legal Consent
        print("  🖥️ Onboarding Step 2...")
        try:
            page.screenshot(path=f"{SCREENSHOT_DIR}/09-step2-legal.png", full_page=True)
            page.locator('button:has-text("Accept All")').first.click()
            page.wait_for_timeout(500)
            page.screenshot(path=f"{SCREENSHOT_DIR}/10-step2-checked.png", full_page=True)
            page.locator('button:has-text("Confirm & Continue")').first.click()
            page.wait_for_timeout(2000)
            page.screenshot(path=f"{SCREENSHOT_DIR}/11-step2-accepted.png", full_page=True)
            page.locator('button:has-text("Continue")').last.click()
            page.wait_for_timeout(1000)
            log_step(5, "Step 2: Legal Consent", True, "Accepted")
        except Exception as e:
            log_step(5, "Step 2", False, str(e)[:80])
        
        # STEP 6: Integrations
        print("  🖥️ Onboarding Step 3...")
        try:
            page.screenshot(path=f"{SCREENSHOT_DIR}/12-step3-integrations.png", full_page=True)
            connect_count = page.locator('button:has-text("Connect")').count()
            page.locator('button:has-text("Continue")').last.click()
            page.wait_for_timeout(1000)
            log_step(6, "Step 3: Integrations", True, f"connect_btns={connect_count}")
        except Exception as e:
            log_step(6, "Step 3", False, str(e)[:80])
        
        # STEP 7: Knowledge Base
        print("  🖥️ Onboarding Step 4...")
        try:
            page.screenshot(path=f"{SCREENSHOT_DIR}/13-step4-knowledge.png", full_page=True)
            page.locator('button:has-text("Add FAQ")').first.click()
            page.wait_for_timeout(500)
            q = page.locator('input[placeholder="Question"]').first
            a = page.locator('textarea[placeholder="Answer"]').first
            if q.count() > 0: q.fill("What is PARWA?")
            if a.count() > 0: a.fill("PARWA is an AI-powered customer support platform.")
            page.screenshot(path=f"{SCREENSHOT_DIR}/14-step4-faq-filled.png", full_page=True)
            page.locator('button:has-text("Save FAQ")').first.click()
            page.wait_for_timeout(500)
            page.screenshot(path=f"{SCREENSHOT_DIR}/15-step4-faq-added.png", full_page=True)
            
            # Click KB Continue (the step's own button)
            page.locator('button:has-text("Continue")').first.click()
            page.wait_for_timeout(2000)
            page.screenshot(path=f"{SCREENSHOT_DIR}/16-step4-complete.png", full_page=True)
            
            # Click wizard Continue
            page.locator('button:has-text("Continue")').last.click()
            page.wait_for_timeout(1000)
            log_step(7, "Step 4: Knowledge Base", True, "FAQ added")
        except Exception as e:
            log_step(7, "Step 4", False, str(e)[:80])
        
        # STEP 8: AI Config
        print("  🖥️ Onboarding Step 5...")
        try:
            page.screenshot(path=f"{SCREENSHOT_DIR}/17-step5-ai.png", full_page=True)
            page.locator('text=Friendly').first.click()
            page.wait_for_timeout(500)
            page.locator('text=Detailed').first.click()
            page.wait_for_timeout(500)
            ta = page.locator('textarea').first
            if ta.count() > 0: ta.fill("Always greet customers by name.")
            page.screenshot(path=f"{SCREENSHOT_DIR}/18-step5-configured.png", full_page=True)
            page.locator('button:has-text("Continue")').first.click()
            page.wait_for_timeout(2000)
            page.screenshot(path=f"{SCREENSHOT_DIR}/19-step5-done.png", full_page=True)
            page.locator('button:has-text("Continue")').last.click()
            page.wait_for_timeout(1000)
            log_step(8, "Step 5: AI Config", True, "Friendly + Detailed")
        except Exception as e:
            log_step(8, "Step 5", False, str(e)[:80])
        
        # STEP 9: Cost Breakdown
        print("  🖥️ Onboarding Step 6...")
        try:
            page.screenshot(path=f"{SCREENSHOT_DIR}/20-step6-cost.png", full_page=True)
            has_total = page.locator('text=Total Monthly Cost').count() > 0
            has_savings = page.locator('text=Save').count() > 0
            page.locator('button:has-text("Continue")').last.click()
            page.wait_for_timeout(1000)
            page.screenshot(path=f"{SCREENSHOT_DIR}/21-step6-done.png", full_page=True)
            log_step(9, "Step 6: Cost Breakdown", has_total or has_savings, f"total={has_total}, savings={has_savings}")
        except Exception as e:
            log_step(9, "Step 6", False, str(e)[:80])
        
        # STEP 10: Go Live / Activate
        print("  🖥️ Onboarding Step 7 - Go Live...")
        try:
            page.screenshot(path=f"{SCREENSHOT_DIR}/22-step7-golive.png", full_page=True)
            activate = page.locator('button:has-text("Activate")').first
            if activate.count() > 0:
                activate.click()
                page.wait_for_timeout(8000)  # Wait longer for activation + redirect
            url = page.url
            page.screenshot(path=f"{SCREENSHOT_DIR}/23-after-activate.png", full_page=True)
            on_dashboard = "/dashboard" in url
            log_step(10, "Step 7: Go Live", on_dashboard, f"url={url}")
            
            # If activation failed, navigate manually
            if not on_dashboard:
                print("  ⚠️ Activation redirect failed, navigating manually...")
                page.goto(f"{BASE}/dashboard", wait_until="networkidle", timeout=15000)
                page.wait_for_timeout(3000)
                page.screenshot(path=f"{SCREENSHOT_DIR}/23b-manual-dashboard.png", full_page=True)
        except Exception as e:
            log_step(10, "Step 7", False, str(e)[:80])
        
        # STEP 11: Dashboard
        print("  🖥️ Dashboard...")
        try:
            if "/dashboard" not in page.url:
                page.goto(f"{BASE}/dashboard", wait_until="networkidle", timeout=15000)
                page.wait_for_timeout(5000)
            page.wait_for_timeout(3000)  # Extra wait for auth check + rendering
            page.screenshot(path=f"{SCREENSHOT_DIR}/24-dashboard.png", full_page=True)
            
            # Check for dashboard elements - use flexible selectors
            page_text = page.locator("body").text_content(timeout=10000) or ""
            has_welcome = "Welcome" in page_text
            has_cards = "Active Variants" in page_text or "Tickets Today" in page_text or "AI Accuracy" in page_text
            has_quick = "Quick Actions" in page_text
            has_sidebar = "PARWA" in page_text
            
            page.screenshot(path=f"{SCREENSHOT_DIR}/25-dashboard-detailed.png", full_page=True)
            log_step(11, "Dashboard Overview", has_welcome and has_cards and has_quick, f"welcome={has_welcome}, cards={has_cards}, quick={has_quick}, sidebar={has_sidebar}")
        except Exception as e:
            log_step(11, "Dashboard", False, str(e)[:80])
        
        # STEP 12: Settings Page
        print("  🖥️ Settings...")
        try:
            page.goto(f"{BASE}/dashboard/settings", wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(2000)
            page.screenshot(path=f"{SCREENSHOT_DIR}/26-settings.png", full_page=True)
            log_step(12, "Dashboard Settings", True, "Page loaded")
        except Exception as e:
            log_step(12, "Settings", False, str(e)[:80])
        
        # STEP 13: Login Page
        print("  🖥️ Login Page...")
        try:
            page.goto(f"{BASE}/login", wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(1000)
            page.screenshot(path=f"{SCREENSHOT_DIR}/27-login.png", full_page=True)
            has_email = page.locator('input#email').count() > 0
            has_pw = page.locator('input#password').count() > 0
            has_signin = page.locator('button:has-text("Sign In")').count() > 0
            log_step(13, "Login Page", has_email and has_pw and has_signin, f"email={has_email}, pw={has_pw}, signin={has_signin}")
        except Exception as e:
            log_step(13, "Login Page", False, str(e)[:80])
        
        # STEP 14: Login with existing user
        print("  🖥️ Login with existing user...")
        try:
            # Use the E2E user we created
            ts = int(time.time())  # We need the same email from step 3
            # Instead, use the API test user
            page.fill('input#email', test_email)
            page.fill('input#password', 'Testpass123!')
            page.screenshot(path=f"{SCREENSHOT_DIR}/28-login-filled.png", full_page=True)
            page.click('button[type="submit"]')
            page.wait_for_timeout(5000)
            url = page.url
            page.screenshot(path=f"{SCREENSHOT_DIR}/29-after-login.png", full_page=True)
            log_step(14, "Login → Dashboard/Onboarding", "/dashboard" in url or "/onboarding" in url, f"url={url}")
        except Exception as e:
            log_step(14, "Login Submit", False, str(e)[:80])
        
        results["console_errors"] = console_errors[:20]
        browser.close()

except ImportError:
    print("  ⚠️ Playwright not available")
    log_step(1, "Playwright", False, "Not installed")
except Exception as e:
    print(f"  ❌ Playwright error: {e}")
    traceback.print_exc()
    log_step(1, "Playwright", False, str(e)[:80])

# ============================================================
# Cleanup
# ============================================================
try:
    backend_proc.terminate()
    frontend_proc.terminate()
except: pass

# ============================================================
# Report
# ============================================================
report_path = f"{SCREENSHOT_DIR}/test-results.json"
with open(report_path, "w") as f:
    json.dump(results, f, indent=2)

api_tests = [s for s in results["steps"] if s["step"] == 0]
ui_tests = [s for s in results["steps"] if s["step"] > 0]
api_p = sum(1 for t in api_tests if t["passed"])
api_f = sum(1 for t in api_tests if not t["passed"])
ui_p = sum(1 for t in ui_tests if t["passed"])
ui_f = sum(1 for t in ui_tests if not t["passed"])

print("\n" + "=" * 60)
print("📊 PARWA COMPLETE E2E JOURNEY TEST - FINAL RESULTS")
print("=" * 60)
print(f"\n🔢 Backend API: {api_p}/{api_p+api_f} PASSED")
for t in api_tests:
    print(f"  {'✅' if t['passed'] else '❌'} {t['name']}: {t['details']}")

print(f"\n🖥️ Frontend UI: {ui_p}/{ui_p+ui_f} PASSED")
for t in ui_tests:
    print(f"  {'✅' if t['passed'] else '❌'} Step {t['step']}: {t['name']} - {t['details']}")

print(f"\n📸 Screenshots: {SCREENSHOT_DIR}/")
print(f"📄 Report: {report_path}")
print(f"⚠️ Console Errors: {len(results.get('console_errors', []))}")

if results.get("console_errors"):
    print("\n🔴 Console Errors (top 5):")
    for i, err in enumerate(results["console_errors"][:5]):
        print(f"  {i+1}. {str(err)[:120]}")

total = results["total_passed"] + results["total_failed"]
pct = (results["total_passed"] / total * 100) if total > 0 else 0
print(f"\n📈 OVERALL: {results['total_passed']}/{total} ({pct:.0f}%) PASSED")
print("=" * 60)
