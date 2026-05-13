#!/usr/bin/env python3
"""
Quick API test script - starts backend, waits for it, then tests endpoints.
"""
import subprocess
import time
import json
import urllib.request
import urllib.error
import os
import sys

BACKEND_URL = "http://localhost:8000"
DOWNLOAD_DIR = "/home/z/my-project/download"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def start_backend():
    """Start the backend and wait for it to be ready."""
    env = os.environ.copy()
    env.update({
        "PYTHONPATH": "/home/z/my-project/parwa-app/backend:/home/z/my-project/parwa-app",
        "ENVIRONMENT": "development",
        "DEBUG": "true",
        "DATABASE_URL": "sqlite:////home/z/my-project/db/parwa_manual_test.db",
        "REDIS_URL": "",
        "TWILIO_ACCOUNT_SID": os.environ.get("TWILIO_ACCOUNT_SID", ""),
        "TWILIO_AUTH_TOKEN": os.environ.get("TWILIO_AUTH_TOKEN", ""),
        "TWILIO_PHONE_NUMBER": os.environ.get("TWILIO_PHONE_NUMBER", ""),
        "TWILIO_API_KEY": os.environ.get("TWILIO_API_KEY", ""),
        "PADDLE_CLIENT_TOKEN": os.environ.get("PADDLE_CLIENT_TOKEN", ""),
        "PADDLE_API_KEY": os.environ.get("PADDLE_API_KEY", ""),
    })
    
    proc = subprocess.Popen(
        ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd="/home/z/my-project/parwa-app/backend",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    # Wait for backend to be ready
    for i in range(30):
        time.sleep(1)
        try:
            req = urllib.request.Request(f"{BACKEND_URL}/health", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    print(f"  ✅ Backend ready after {i+1}s")
                    return proc
        except:
            pass
    
    print("  ❌ Backend failed to start")
    return None


def test_endpoint(method, path, data=None, headers=None, timeout=10):
    """Test a single endpoint."""
    url = f"{BACKEND_URL}{path}"
    body = None
    if data:
        body = json.dumps(data).encode()
    if headers is None:
        headers = {}
    if body and "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"
    
    try:
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            try:
                resp_data = json.loads(resp.read().decode())
            except:
                resp_data = None
            return {
                "status_code": resp.status,
                "response": resp_data,
                "test": "PASS",
            }
    except urllib.error.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode()[:500]
        except:
            pass
        return {
            "status_code": e.code,
            "body": body_text,
            "test": "FAIL" if e.code >= 500 else "EXPECTED_FAIL",
        }
    except Exception as e:
        return {
            "test": "FAIL",
            "error": str(e),
        }


def main():
    print("Starting backend...")
    proc = start_backend()
    if not proc:
        print("Cannot proceed without backend")
        return
    
    results = {}
    
    try:
        # 1. Health
        print("Testing /health...")
        results["health"] = test_endpoint("GET", "/health")
        
        # 2. Ready
        print("Testing /ready...")
        results["ready"] = test_endpoint("GET", "/ready")
        
        # 3. OpenAPI
        print("Testing /openapi.json...")
        results["openapi_docs"] = test_endpoint("GET", "/openapi.json")
        
        # 4. Auth login - try /api/auth/login
        print("Testing /api/auth/login...")
        results["auth_login"] = test_endpoint(
            "POST", "/api/auth/login",
            data={"email": "owner@technova.com", "password": "admin123"}
        )
        
        # 5. Try with more passwords
        if results["auth_login"]["test"] != "PASS":
            for pwd in ["password", "technova123", "parwa123", "Password123!", "demo1234", "Admin@123"]:
                r = test_endpoint(
                    "POST", "/api/auth/login",
                    data={"email": "owner@technova.com", "password": pwd}
                )
                if r["test"] == "PASS":
                    results["auth_login"] = r
                    results["auth_login"]["password_used"] = pwd
                    break
        
        # 6. Public endpoints (no auth needed)
        print("Testing /api/public/info...")
        results["public_info"] = test_endpoint("GET", "/api/public/info")
        
        # 7. Pricing
        print("Testing /api/v1/pricing...")
        results["pricing"] = test_endpoint("GET", "/api/v1/pricing")
        
        # 8. Jarvis CC (may need auth)
        print("Testing /api/jarvis-cc/sessions...")
        results["jarvis_cc_sessions"] = test_endpoint("GET", "/api/jarvis-cc/sessions")
        
        # 9. Jarvis CC awareness
        print("Testing /api/jarvis-cc/awareness...")
        results["jarvis_cc_awareness"] = test_endpoint("GET", "/api/jarvis-cc/awareness")
        
        # 10. Jarvis onboarding
        print("Testing /api/jarvis/chat...")
        results["jarvis_chat"] = test_endpoint(
            "POST", "/api/jarvis/chat",
            data={"message": "Hello", "session_id": "test-session"}
        )
        
    finally:
        # Kill the backend
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except:
            proc.kill()
    
    # Print results
    print("\n" + "=" * 60)
    print("  API TEST RESULTS")
    print("=" * 60)
    for endpoint, result in results.items():
        status_icon = "✅" if result.get("test") == "PASS" else ("⚠️" if result.get("test") == "EXPECTED_FAIL" else "❌")
        code = result.get("status_code", "N/A")
        print(f"  {status_icon} {endpoint}: {result.get('test', 'UNKNOWN')} (HTTP {code})")
        if result.get("response"):
            resp_str = json.dumps(result["response"])[:150]
            print(f"     Response: {resp_str}")
        if result.get("error"):
            print(f"     Error: {result['error'][:100]}")
    
    # Save results
    output_path = os.path.join(DOWNLOAD_DIR, "parwa_api_test_results.json")
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Saved to: {output_path}")
    
    return results


if __name__ == "__main__":
    main()
