#!/usr/bin/env python3
"""PARWA Infrastructure — K8s Service Selector Tests"""
import os, sys, yaml

K8S_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "infra", "k8s")
SERVICE_FILES = [
    "backend/service.yaml", "frontend/service.yaml", "mcp/service.yaml",
    "postgres/service.yaml", "redis/service.yaml",
    "monitoring/prometheus/service.yaml", "monitoring/grafana/service.yaml",
    "monitoring/alertmanager/service.yaml",
]
pass_count = 0
fail_count = 0

def test_service_flat_selector():
    global pass_count, fail_count
    for svc_path in SERVICE_FILES:
        full_path = os.path.join(K8S_DIR, svc_path)
        if not os.path.exists(full_path):
            continue
        with open(full_path) as f:
            docs = list(yaml.safe_load_all(f))
        for doc in docs:
            if doc.get("kind") != "Service":
                continue
            selector = doc.get("spec", {}).get("selector", {})
            test_name = f"Flat selector: {svc_path}"
            if "matchLabels" in selector:
                print(f"FAIL  {test_name} — uses matchLabels (invalid for Services)")
                fail_count += 1
            elif selector and "app.kubernetes.io/name" in selector:
                print(f"PASS  {test_name} — {selector.get('app.kubernetes.io/name', '?')}")
                pass_count += 1
            else:
                print(f"WARN  {test_name}")
                pass_count += 1

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  PARWA — K8s Service Selector Tests")
    print("=" * 60 + "\n")
    test_service_flat_selector()
    total = pass_count + fail_count
    print(f"\n{'=' * 60}\n  RESULTS: {pass_count} passed, {fail_count} failed out of {total}\n{'=' * 60}")
    sys.exit(1 if fail_count > 0 else 0)
