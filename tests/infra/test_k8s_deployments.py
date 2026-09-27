#!/usr/bin/env python3
"""PARWA Infrastructure — K8s Deployment & StatefulSet Tests"""
import os, sys, yaml

K8S_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "infra", "k8s")
pass_count = 0
fail_count = 0
DEPLOY_FILES = ["backend/deployment.yaml", "frontend/deployment.yaml", "worker/deployment.yaml", "mcp/deployment.yaml"]

def test_no_latest_tags():
    global pass_count, fail_count
    for fpath in DEPLOY_FILES:
        with open(os.path.join(K8S_DIR, fpath)) as f:
            doc = yaml.safe_load(f)
        for c in doc["spec"]["template"]["spec"]["containers"]:
            img = c.get("image", "")
            if img.endswith(":latest"):
                print(f"FAIL  No :latest: {fpath} uses {img}")
                fail_count += 1
            else:
                print(f"PASS  No :latest: {fpath}")
                pass_count += 1

def test_always_pull():
    global pass_count, fail_count
    for fpath in DEPLOY_FILES:
        with open(os.path.join(K8S_DIR, fpath)) as f:
            doc = yaml.safe_load(f)
        for c in doc["spec"]["template"]["spec"]["containers"]:
            if c.get("imagePullPolicy") == "Always":
                print(f"PASS  Always pull: {fpath}")
                pass_count += 1
            else:
                print(f"FAIL  Always pull: {fpath} — {c.get('imagePullPolicy')}")
                fail_count += 1

def test_service_accounts():
    global pass_count, fail_count
    expected = {"backend": "parwa-backend", "frontend": "parwa-frontend", "worker": "parwa-worker", "mcp": "parwa-mcp"}
    for fpath in DEPLOY_FILES:
        with open(os.path.join(K8S_DIR, fpath)) as f:
            doc = yaml.safe_load(f)
        name = doc["metadata"]["name"]
        sa = doc["spec"]["template"]["spec"].get("serviceAccountName", "")
        if sa == expected.get(name, ""):
            print(f"PASS  ServiceAccount: {name} = {sa}")
            pass_count += 1
        elif sa:
            print(f"WARN  ServiceAccount: {name} = {sa}")
            pass_count += 1
        else:
            print(f"FAIL  ServiceAccount: {name} — none assigned")
            fail_count += 1

def test_postgres_non_root():
    global pass_count, fail_count
    with open(os.path.join(K8S_DIR, "postgres/statefulset.yaml")) as f:
        doc = yaml.safe_load(f)
    ctx = doc["spec"]["template"]["spec"].get("securityContext", {})
    if ctx.get("runAsNonRoot"):
        print(f"PASS  Postgres: runAsNonRoot=true")
        pass_count += 1
    else:
        print(f"FAIL  Postgres: runAsNonRoot not set")
        fail_count += 1

def test_redis_auth_probes():
    global pass_count, fail_count
    with open(os.path.join(K8S_DIR, "redis/statefulset.yaml")) as f:
        doc = yaml.safe_load(f)
    for c in doc["spec"]["template"]["spec"]["containers"]:
        if c["name"] != "redis":
            continue
        liv = " ".join(c.get("livenessProbe", {}).get("exec", {}).get("command", []))
        rd = " ".join(c.get("readinessProbe", {}).get("exec", {}).get("command", []))
        if "REDIS_PASSWORD" in liv or "-a" in liv:
            print(f"PASS  Redis liveness: uses auth")
            pass_count += 1
        else:
            print(f"FAIL  Redis liveness: no auth")
            fail_count += 1
        if "REDIS_PASSWORD" in rd or "-a" in rd:
            print(f"PASS  Redis readiness: uses auth")
            pass_count += 1
        else:
            print(f"FAIL  Redis readiness: no auth")
            fail_count += 1

def test_mcp_replicas():
    global pass_count, fail_count
    with open(os.path.join(K8S_DIR, "mcp/deployment.yaml")) as f:
        doc = yaml.safe_load(f)
    r = doc["spec"].get("replicas", 0)
    if r >= 2:
        print(f"PASS  MCP replicas={r}")
        pass_count += 1
    else:
        print(f"FAIL  MCP replicas={r} (SPOF)")
        fail_count += 1

def test_frontend_liveness_path():
    global pass_count, fail_count
    with open(os.path.join(K8S_DIR, "frontend/deployment.yaml")) as f:
        doc = yaml.safe_load(f)
    for c in doc["spec"]["template"]["spec"]["containers"]:
        if c["name"] != "frontend":
            continue
        path = c.get("livenessProbe", {}).get("httpGet", {}).get("path", "/")
        if path != "/":
            print(f"PASS  Frontend liveness: {path}")
            pass_count += 1
        else:
            print(f"FAIL  Frontend liveness: / (expensive SSR)")
            fail_count += 1

def test_backend_startup_probe():
    global pass_count, fail_count
    with open(os.path.join(K8S_DIR, "backend/deployment.yaml")) as f:
        doc = yaml.safe_load(f)
    for c in doc["spec"]["template"]["spec"]["containers"]:
        if c["name"] != "backend":
            continue
        if "startupProbe" in c:
            print(f"PASS  Backend: has startupProbe")
            pass_count += 1
        else:
            print(f"FAIL  Backend: no startupProbe")
            fail_count += 1

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  PARWA — K8s Deployment Tests")
    print("=" * 60 + "\n")
    test_no_latest_tags()
    test_always_pull()
    test_service_accounts()
    test_postgres_non_root()
    test_redis_auth_probes()
    test_mcp_replicas()
    test_frontend_liveness_path()
    test_backend_startup_probe()
    total = pass_count + fail_count
    print(f"\n{'=' * 60}\n  RESULTS: {pass_count} passed, {fail_count} failed out of {total}\n{'=' * 60}")
    sys.exit(1 if fail_count > 0 else 0)
