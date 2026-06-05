#!/usr/bin/env python3
"""
PARWA Local Development Test Script
Starts the backend, runs comprehensive API tests, and reports results.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

# ── Setup environment ──
os.chdir('/home/z/my-project/parwa/backend')
sys.path.insert(0, '/home/z/my-project/parwa/backend')
sys.path.insert(0, '/home/z/my-project/parwa')

# Load .env manually
with open('.env') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ[key] = value

# Override for local dev
os.environ['DATABASE_URL'] = 'sqlite:///./db/parwa_dev.db'
os.environ['REDIS_URL'] = ''
os.environ['CSRF_ENABLED'] = 'false'
os.environ['PYTHONPATH'] = '/home/z/my-project/parwa/backend:/home/z/my-project/parwa'

# ── Start backend ──
print("=" * 60)
print("  PARWA Local Development Test Suite")
print("=" * 60)

proc = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000', '--no-access-log'],
    env=os.environ.copy(),
    stdout=open('/tmp/parwa_backend.log', 'w'),
    stderr=subprocess.STDOUT,
)

print(f"Backend PID: {proc.pid}")
print("Waiting for startup...")
time.sleep(10)

# ── Test functions ──
def api_call(method, path, data=None, token=None, origin='http://localhost:3000'):
    url = f'http://localhost:8000{path}'
    headers = {'Content-Type': 'application/json'}
    if origin:
        headers['Origin'] = origin
    if token:
        headers['Authorization'] = f'Bearer {token}'
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read())
        except Exception:
            body = {'raw': str(e)}
        return e.code, body
    except Exception as e:
        return 0, {'error': str(e)}

results = []

def test(name, status, expected_status, response):
    passed = status == expected_status
    results.append((name, passed, status, expected_status))
    icon = "✅" if passed else "❌"
    print(f"  {icon} {name}: HTTP {status} (expected {expected_status})")
    if not passed and isinstance(response, dict):
        err = response.get('error', response.get('detail', str(response)[:200]))
        print(f"      Error: {err}")

# ── Run tests ──
print("\n1. Health & System Endpoints")
status, resp = api_call('GET', '/health')
test("Health Check", status, 200, resp)

status, resp = api_call('GET', '/openapi.json')
test("OpenAPI Schema", status, 200, resp)

print("\n2. Authentication")
status, resp = api_call('POST', '/api/auth/login', {
    'email': 'admin@parwa.ai',
    'password': 'admin123'
})
test("Admin Login", status, 200, resp)
admin_token = resp.get('tokens', {}).get('access_token', '') if status == 200 else ''

status, resp = api_call('POST', '/api/auth/login', {
    'email': 'agent@parwa.ai',
    'password': 'agent123'
})
test("Agent Login", status, 200, resp)
agent_token = resp.get('tokens', {}).get('access_token', '') if status == 200 else ''

status, resp = api_call('POST', '/api/auth/login', {
    'email': 'admin@parwa.ai',
    'password': 'wrongpassword'
})
test("Login with wrong password", status, 401, resp)

print("\n3. Protected Endpoints (Admin)")
if admin_token:
    status, resp = api_call('GET', '/api/user/details', token=admin_token)
    test("Get User Details", status, 200, resp)

    status, resp = api_call('GET', '/api/v1/tickets', token=admin_token)
    test("List Tickets", status, 200, resp)

    status, resp = api_call('GET', '/api/pricing')
    test("Public Pricing", status, 200, resp)

    status, resp = api_call('GET', '/api/v1/customers', token=admin_token)
    test("List Customers", status, 200, resp)

    status, resp = api_call('GET', '/api/v1/notifications', token=admin_token)
    test("List Notifications", status, 200, resp)

    status, resp = api_call('GET', '/api/v1/sla', token=admin_token)
    test("SLA Policies", status, 200, resp)

    status, resp = api_call('GET', '/api/leads', token=admin_token)
    test("Lead Stats", status, 200, resp)

print("\n4. Ticket Creation")
if admin_token:
    status, resp = api_call('POST', '/api/v1/tickets', {
        'subject': 'Test ticket from local dev',
        'description': 'This is a test ticket created during local development testing.',
        'priority': 'medium',
        'channel': 'web',
    }, token=admin_token)
    test("Create Ticket", status, 201, resp)
    ticket_id = resp.get('id', '') if status in (200, 201) else ''

    if ticket_id:
        status, resp = api_call('GET', f'/api/v1/tickets/{ticket_id}', token=admin_token)
        test("Get Ticket Detail", status, 200, resp)

print("\n5. Auth Required Endpoints (No Token)")
status, resp = api_call('GET', '/api/v1/tickets')
test("Tickets without auth", status, 401, resp)

status, resp = api_call('GET', '/api/user/details')
test("User details without auth", status, 401, resp)

print("\n6. Signup / Registration")
status, resp = api_call('POST', '/api/auth/register', {
    'email': f'test{int(time.time())}@parwa.ai',
    'password': 'TestPass123!',
    'full_name': 'Test User',
    'company_name': 'Test Company',
    'industry': 'technology',
})
test("Register New User", status, 201, resp)

print("\n7. Jarvis / AI Endpoints")
if admin_token:
    status, resp = api_call('GET', '/api/jarvis/health', token=admin_token)
    test("Jarvis Health", status, 200, resp)

print("\n8. Knowledge Base")
if admin_token:
    status, resp = api_call('GET', '/api/knowledge-base', token=admin_token)
    test("Knowledge Base List", status, 200, resp)

# ── Summary ──
print("\n" + "=" * 60)
passed = sum(1 for _, p, _, _, _ in results if p)
failed = sum(1 for _, p, _, _, _ in results if not p)
print(f"  RESULTS: {passed} passed, {failed} failed, {len(results)} total")
print("=" * 60)

if failed > 0:
    print("\nFailed tests:")
    for name, p, s, e, _ in results:
        if not p:
            print(f"  ❌ {name} (got {s}, expected {e})")

print(f"\nBackend still running: {proc.poll() is None}")
print(f"Log file: /tmp/parwa_backend.log")

# Keep backend running for manual testing
print(f"\nBackend PID: {proc.pid}")
print("The backend is still running at http://localhost:8000")
print("To stop it: kill", proc.pid)

# Write PID file
with open('/tmp/parwa_backend.pid', 'w') as f:
    f.write(str(proc.pid))
