#!/usr/bin/env python3
"""PARWA Infrastructure — K8s NetworkPolicy Tests"""
import os, sys, yaml

K8S_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "infra", "k8s")
pass_count = 0
fail_count = 0

def _has_external_egress(netpol_name):
    with open(os.path.join(K8S_DIR, "networkpolicy.yaml")) as f:
        docs = list(yaml.safe_load_all(f))
    for doc in docs:
        if doc.get("kind") != "NetworkPolicy" or doc.get("metadata", {}).get("name") != netpol_name:
            continue
        for rule in doc.get("spec", {}).get("egress", []):
            for target in rule.get("to", []):
                if "ipBlock" in target and target["ipBlock"].get("cidr") == "0.0.0.0/0":
                    return True
    return False

def test_backend_external_egress():
    global pass_count, fail_count
    if _has_external_egress("backend-netpol"):
        print(f"PASS  Backend: external HTTPS egress allowed")
        pass_count += 1
    else:
        print(f"FAIL  Backend: no external egress (Paddle, Twilio, AI APIs blocked)")
        fail_count += 1

def test_mcp_external_egress():
    global pass_count, fail_count
    if _has_external_egress("mcp-netpol"):
        print(f"PASS  MCP: external HTTPS egress allowed")
        pass_count += 1
    else:
        print(f"FAIL  MCP: no external egress (AI APIs blocked)")
        fail_count += 1

def test_worker_no_port_8000_ingress():
    global pass_count, fail_count
    with open(os.path.join(K8S_DIR, "networkpolicy.yaml")) as f:
        docs = list(yaml.safe_load_all(f))
    for doc in docs:
        if doc.get("kind") != "NetworkPolicy" or doc.get("metadata", {}).get("name") != "worker-netpol":
            continue
        for rule in doc.get("spec", {}).get("ingress", []):
            for port in rule.get("ports", []):
                if port.get("port") == 8000:
                    print(f"FAIL  Worker: port 8000 ingress (workers don't expose HTTP)")
                    fail_count += 1
                    return
    print(f"PASS  Worker: no port 8000 ingress")
    pass_count += 1

def test_monitoring_pod_selector():
    global pass_count, fail_count
    with open(os.path.join(K8S_DIR, "networkpolicy.yaml")) as f:
        docs = list(yaml.safe_load_all(f))
    for doc in docs:
        if doc.get("kind") != "NetworkPolicy" or doc.get("metadata", {}).get("name") != "monitoring-netpol":
            continue
        for rule in doc.get("spec", {}).get("egress", []):
            for target in rule.get("to", []):
                if "podSelector" in target:
                    print(f"PASS  Monitoring: uses podSelector for scraping")
                    pass_count += 1
                    return
    print(f"FAIL  Monitoring: no podSelector for same-namespace scraping")
    fail_count += 1

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  PARWA — K8s NetworkPolicy Tests")
    print("=" * 60 + "\n")
    test_backend_external_egress()
    test_mcp_external_egress()
    test_worker_no_port_8000_ingress()
    test_monitoring_pod_selector()
    total = pass_count + fail_count
    print(f"\n{'=' * 60}\n  RESULTS: {pass_count} passed, {fail_count} failed out of {total}\n{'=' * 60}")
    sys.exit(1 if fail_count > 0 else 0)
