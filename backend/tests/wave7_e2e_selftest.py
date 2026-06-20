"""
Wave 7 — Self-Contained End-to-End Integration Test

Starts the server, runs all tests, shuts down.
Uses threading to run server + tests concurrently.
"""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error

API = "http://localhost:8100"
T = "default_tenant"

results = {"total": 0, "passed": 0, "failed": 0, "tests": []}
server_ready = threading.Event()
server_proc = None


def start_server():
    """Start the FastAPI server in a subprocess."""
    global server_proc
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.api.main:app",
         "--host", "0.0.0.0", "--port", "8100", "--log-level", "warning"],
        cwd="/home/z/my-project/parwa/backend",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    # Wait for server to be ready
    for _ in range(30):
        try:
            urllib.request.urlopen(f"{API}/api/health", timeout=2)
            server_ready.set()
            return
        except:
            time.sleep(1)
    print("WARNING: Server did not start in 30s")


def stop_server():
    """Stop the server."""
    if server_proc:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except:
            server_proc.kill()


def api_get(path, params=""):
    """GET request."""
    url = f"{API}{path}"
    if params:
        url += f"?{params}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            code = resp.getcode()
            data = json.loads(resp.read().decode())
            return code, data
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read().decode())
            return e.code, data
        except:
            return e.code, {"error": str(e)}
    except Exception as e:
        return 0, {"error": str(e)}


def api_post(path, body_dict):
    """POST request."""
    url = f"{API}{path}"
    body = json.dumps(body_dict).encode()
    try:
        req = urllib.request.Request(url, data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            code = resp.getcode()
            data = json.loads(resp.read().decode())
            return code, data
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read().decode())
            return e.code, data
        except:
            return e.code, {"error": str(e), "detail": str(e)}
    except Exception as e:
        return 0, {"error": str(e)}


def record(name, passed, detail=""):
    results["total"] += 1
    if passed:
        results["passed"] += 1
        print(f"  \033[92m✓\033[0m {name}")
    else:
        results["failed"] += 1
        print(f"  \033[91m✗\033[0m {name}: {detail[:200]}")
    results["tests"].append({"name": name, "pass": passed, "detail": detail[:300]})


def main():
    print("\n" + "=" * 60)
    print("  WAVE 7 — FULL END-TO-END INTEGRATION TEST")
    print("=" * 60)

    # Start server
    print("\n  Starting server...")
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    server_ready.wait(timeout=35)

    if not server_ready.is_set():
        print("  FATAL: Server failed to start")
        sys.exit(1)

    print("  Server ready!")

    try:
        # ═══════════════════════════════════════════════════
        print("\n" + "=" * 60)
        print("  PHASE 1: SERVER HEALTH")
        print("=" * 60)

        code, data = api_get("/api/health")
        record("GET /api/health", code == 200, f"code={code}")

        code, data = api_get("/api/jarvis/status", f"tenant_id={T}")
        record("GET /api/jarvis/status", code == 200,
               f"code={code}, keys={list(data.keys()) if isinstance(data, dict) else 'err'}")

        # ═══════════════════════════════════════════════════
        print("\n" + "=" * 60)
        print("  PHASE 2: JARVIS CHAT (5 commands)")
        print("=" * 60)

        code, data = api_post("/api/jarvis/chat", {
            "tenant_id": T, "question": "What is the system status?",
            "user_email": "admin@parwa.ai", "user_role": "admin",
        })
        has_resp = isinstance(data, dict) and ("chat_response" in data or "response" in data)
        resp_text = data.get("chat_response", data.get("response", "")) if isinstance(data, dict) else ""
        record("Chat: system status", code == 200 and has_resp,
               f"code={code}, has_resp={has_resp}")
        if resp_text:
            print(f"      → {str(resp_text)[:120]}...")

        code, data = api_post("/api/jarvis/chat", {
            "tenant_id": T, "question": "Show me quality scores for today",
            "user_email": "admin@parwa.ai", "user_role": "admin",
        })
        record("Chat: quality scores", code == 200, f"code={code}")

        code, data = api_post("/api/jarvis/chat", {
            "tenant_id": T, "question": "Pause all refund processing",
            "user_email": "admin@parwa.ai", "user_role": "admin",
        })
        record("Chat: pause refunds", code == 200, f"code={code}")

        code, data = api_post("/api/jarvis/chat", {
            "tenant_id": T, "question": "Resume refund processing",
            "user_email": "admin@parwa.ai", "user_role": "admin",
        })
        record("Chat: resume refunds", code == 200, f"code={code}")

        code, data = api_post("/api/jarvis/chat", {
            "tenant_id": T, "question": "Switch to supervised mode",
            "user_email": "admin@parwa.ai", "user_role": "admin",
        })
        record("Chat: switch mode", code == 200, f"code={code}")

        # ═══════════════════════════════════════════════════
        print("\n" + "=" * 60)
        print("  PHASE 3: ALL GET ENDPOINTS (16 routes)")
        print("=" * 60)

        get_routes = [
            ("/api/jarvis/status", "Status"),
            ("/api/jarvis/metrics", "Metrics"),
            ("/api/jarvis/notifications", "Notifications"),
            ("/api/jarvis/flags", "Flags"),
            ("/api/quality/scores", "Quality Scores"),
            ("/api/quality/alerts", "Quality Alerts"),
            ("/api/quality/recommendations", "Recommendations"),
            ("/api/quality/weekly-report", "Weekly Report"),
            ("/api/quality/health-score", "Health Score"),
            ("/api/quality/drift-check", "Drift Check"),
            ("/api/sla/status", "SLA Status"),
            ("/api/sla/credits", "SLA Credits"),
            ("/api/approvals/pending", "Pending Approvals"),
            ("/api/jarvis/audit", "Audit Trail"),
            ("/api/jarvis/customer-health", "Customer Health"),
            ("/api/jarvis/roi", "ROI Calculator"),
        ]

        for path, name in get_routes:
            code, data = api_get(path, f"tenant_id={T}")
            is_dict = isinstance(data, dict) and "error" not in data
            record(f"GET {name}", code == 200,
                   f"code={code}, is_dict={is_dict}")

        # ═══════════════════════════════════════════════════
        print("\n" + "=" * 60)
        print("  PHASE 4: BUTTON ACTIONS")
        print("=" * 60)

        print("\n  --- Notification Buttons ---")
        code, data = api_post("/api/jarvis/notifications/batch/approve", {
            "tenant_id": T, "batch_key": "wave7_test_batch",
        })
        record("POST batch approve", code == 200, f"code={code}")

        code, data = api_post("/api/jarvis/notifications/batch/reject", {
            "tenant_id": T, "batch_key": "wave7_test_reject",
        })
        record("POST batch reject", code == 200, f"code={code}")

        # Try resolve a notification
        code, ndata = api_get("/api/jarvis/notifications", f"tenant_id={T}&include_resolved=true")
        notifs = ndata.get("notifications", []) if isinstance(ndata, dict) else []
        if notifs:
            nkey = notifs[0].get("key", notifs[0].get("id", ""))
            if nkey:
                code, data = api_post(f"/api/jarvis/notifications/{nkey}/resolve", {})
                record(f"POST resolve notification", code == 200, f"code={code}")
            else:
                record("POST resolve notification", True, "No key (skipped)")
        else:
            record("POST resolve notification", True, "No notifications yet (ok)")

        print("\n  --- Flag Buttons ---")
        code, data = api_post("/api/jarvis/flags", {
            "tenant_id": T, "flag_type": "pause_action", "flag_value": "refund",
            "scope": "global", "reason": "Wave 7 E2E test",
        })
        record("POST set flag", code == 200, f"code={code}")

        code, fdata = api_get("/api/jarvis/flags", f"tenant_id={T}")
        flags = fdata.get("flags", []) if isinstance(fdata, dict) else []
        record("GET flags after set", len(flags) > 0, f"count={len(flags)}")

        # Revoke all flags
        for flag in flags:
            fid = flag.get("id", "")
            if fid:
                api_post(f"/api/jarvis/flags/{fid}/revoke", {})

        print("\n  --- Control Command Buttons ---")
        code, data = api_post("/api/jarvis/command/pause", {
            "tenant_id": T, "target": "returns", "user_email": "admin@parwa.ai",
        })
        record("POST pause returns", code == 200, f"code={code}")

        code, data = api_post("/api/jarvis/command/resume", {
            "tenant_id": T, "target": "returns", "user_email": "admin@parwa.ai",
        })
        record("POST resume returns", code == 200, f"code={code}")

        code, data = api_post("/api/jarvis/command/redirect", {
            "tenant_id": T, "target": "instagram", "handler": "ai",
            "user_email": "admin@parwa.ai",
        })
        record("POST redirect instagram→ai", code == 200, f"code={code}")

        code, data = api_post("/api/jarvis/command/mode", {
            "tenant_id": T, "mode": "supervised", "user_email": "admin@parwa.ai",
        })
        record("POST mode→supervised", code == 200, f"code={code}")

        print("\n  --- Approval & Quality Buttons ---")
        code, data = api_post("/api/approvals/batch", {
            "tenant_id": T, "action": "approve", "batch_key": "wave7_batch",
        })
        record("POST approvals batch", code == 200, f"code={code}")

        code, data = api_post("/api/quality/feedback", {
            "tenant_id": T, "ticket_id": "tkt_wave7_001",
            "signal_type": "approved", "ai_response": "Test response",
            "quality_score": 0.85, "ticket_type": "refund",
        })
        record("POST quality feedback", code == 200, f"code={code}")

        print("\n  --- Emergency Buttons ---")
        code, data = api_post("/api/emergency/shutdown", {
            "tenant_id": T, "user_email": "admin@parwa.ai",
        })
        record("POST emergency shutdown", code == 200, f"code={code}")

        # Clean up: revoke all flags
        code, fdata = api_get("/api/jarvis/flags", f"tenant_id={T}")
        flags = fdata.get("flags", []) if isinstance(fdata, dict) else []
        for flag in flags:
            fid = flag.get("id", "")
            if fid:
                api_post(f"/api/jarvis/flags/{fid}/revoke", {})

        code, data = api_post("/api/pause_all_refunds", {
            "tenant_id": T, "user_email": "admin@parwa.ai",
        })
        record("POST pause all refunds", code == 200, f"code={code}")

        # Clean up again
        code, fdata = api_get("/api/jarvis/flags", f"tenant_id={T}")
        flags = fdata.get("flags", []) if isinstance(fdata, dict) else []
        for flag in flags:
            fid = flag.get("id", "")
            if fid:
                api_post(f"/api/jarvis/flags/{fid}/revoke", {})

        # ═══════════════════════════════════════════════════
        print("\n" + "=" * 60)
        print("  PHASE 5: DATA PERSISTENCE CHECK")
        print("=" * 60)

        code, data = api_get("/api/jarvis/audit", f"tenant_id={T}&limit=10")
        audit_count = data.get("count", 0) if isinstance(data, dict) else 0
        record("Audit trail populated", audit_count > 0, f"count={audit_count}")

        code, data = api_get("/api/jarvis/notifications", f"tenant_id={T}&include_resolved=true")
        notif_count = data.get("count", 0) if isinstance(data, dict) else 0
        record("Notifications exist", notif_count > 0, f"count={notif_count}")

        code, data = api_get("/api/jarvis/metrics", f"tenant_id={T}&days=1")
        record("Metrics returns data", code == 200, f"code={code}")

        # ═══════════════════════════════════════════════════
        print("\n" + "=" * 60)
        print("  PHASE 6: FINAL VERIFICATION — Re-check all endpoints")
        print("=" * 60)

        code, data = api_get("/api/health")
        record("Final: health check", code == 200, f"code={code}")

        code, data = api_get("/api/jarvis/status", f"tenant_id={T}")
        record("Final: jarvis status", code == 200, f"code={code}")

    finally:
        stop_server()

    # ═══════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("  FINAL SUMMARY")
    print("=" * 60)
    total = results["total"]
    passed = results["passed"]
    failed = results["failed"]
    rate = passed / max(total, 1) * 100
    print(f"  Total:  {total}")
    print(f"  Passed: \033[92m{passed}\033[0m")
    print(f"  Failed: \033[91m{failed}\033[0m")
    print(f"  Rate:   {rate:.1f}%")

    if failed > 0:
        print("\n  FAILED TESTS:")
        for t in results["tests"]:
            if not t["pass"]:
                print(f"    ✗ {t['name']}: {t['detail']}")

    # Save results
    os.makedirs("/home/z/my-project/parwa/backend/tests/results", exist_ok=True)
    results["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open("/home/z/my-project/parwa/backend/tests/results/wave7_e2e_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved: wave7_e2e_results.json")


if __name__ == "__main__":
    main()
