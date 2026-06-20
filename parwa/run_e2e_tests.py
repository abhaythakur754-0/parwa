#!/usr/bin/env python3
"""
Run Playwright tests against locally running servers.
Starts backend + frontend, waits for them, runs tests, reports results.
"""
import subprocess
import time
import sys
import os
import signal
import json

PROJECT_DIR = "/home/z/my-project/parwa"
BACKEND_DIR = f"{PROJECT_DIR}/backend"

def main():
    processes = []
    
    try:
        # Start backend
        print("🚀 Starting backend on port 8000...")
        env = os.environ.copy()
        env["PYTHONPATH"] = BACKEND_DIR
        backend = subprocess.Popen(
            ["/home/z/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "warning"],
            cwd=BACKEND_DIR,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        processes.append(("Backend", backend))
        
        # Start frontend
        print("🚀 Starting frontend on port 3000...")
        frontend = subprocess.Popen(
            ["npx", "next", "dev", "-p", "3000"],
            cwd=PROJECT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        processes.append(("Frontend", frontend))
        
        # Wait for servers
        print("⏳ Waiting for servers to start (20s)...")
        time.sleep(20)
        
        # Check if processes are still alive
        for name, proc in processes:
            if proc.poll() is not None:
                print(f"❌ {name} died during startup! Exit code: {proc.returncode}")
                return 1
        
        # Quick health check
        import urllib.request
        try:
            resp = urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5)
            print(f"✅ Backend health: {resp.status}")
        except Exception as e:
            print(f"⚠️ Backend health check failed: {e}")
        
        try:
            resp = urllib.request.urlopen("http://127.0.0.1:3000/", timeout=10)
            print(f"✅ Frontend: {resp.status}")
        except Exception as e:
            print(f"⚠️ Frontend check failed: {e}")
        
        # Run Playwright tests
        print("\n🧪 Running Playwright tests...\n")
        env = os.environ.copy()
        env["BASE_URL"] = "http://127.0.0.1:3000"
        
        result = subprocess.run(
            ["npx", "playwright", "test", 
             "tests/e2e/phase2-industry-integration.spec.ts",
             "tests/e2e/phase1-phase2-manual-testing.spec.ts",
             "--reporter=line"],
            cwd=PROJECT_DIR,
            env=env,
        )
        
        print(f"\n{'='*60}")
        print(f"Playwright exit code: {result.returncode}")
        print(f"{'='*60}")
        
        return result.returncode
        
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted!")
        return 130
    finally:
        # Kill servers
        print("\n🛑 Stopping servers...")
        for name, proc in processes:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                print(f"  Stopped {name}")

if __name__ == "__main__":
    sys.exit(main())
