#!/usr/bin/env python3
"""PARWA Infrastructure — K8s Secrets & ConfigMap Tests"""
import os, sys, yaml

K8S_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "infra", "k8s")
pass_count = 0
fail_count = 0

def test_secrets_has_required_keys():
    global pass_count, fail_count
    required = ["DB_PASSWORD", "REDIS_PASSWORD", "SECRET_KEY", "JWT_SECRET_KEY",
                "DATA_ENCRYPTION_KEY", "DATABASE_URL", "REDIS_URL",
                "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND",
                "GRAFANA_ADMIN_PASSWORD", "GRAFANA_ADMIN_USER", "POSTGRES_USER"]
    with open(os.path.join(K8S_DIR, "secrets.yaml")) as f:
        docs = list(yaml.safe_load_all(f))
    for doc in docs:
        if doc.get("kind") != "Secret":
            continue
        data = doc.get("stringData", {}) or doc.get("data", {})
        for key in required:
            if key in data:
                print(f"PASS  Secret has key: {key}")
                pass_count += 1
            else:
                print(f"FAIL  Secret missing key: {key}")
                fail_count += 1

def test_configmap_no_creds():
    global pass_count, fail_count
    forbidden = ["POSTGRES_USER", "POSTGRES_PASSWORD", "DB_PASSWORD", "SECRET_KEY"]
    with open(os.path.join(K8S_DIR, "configmap.yaml")) as f:
        docs = list(yaml.safe_load_all(f))
    for doc in docs:
        if doc.get("kind") != "ConfigMap":
            continue
        data = doc.get("data", {})
        for key in forbidden:
            if key in data:
                print(f"FAIL  ConfigMap has plaintext: {key}")
                fail_count += 1
            else:
                print(f"PASS  ConfigMap no plaintext: {key}")
                pass_count += 1

def test_redis_no_empty_requirepass():
    global pass_count, fail_count
    with open(os.path.join(K8S_DIR, "configmap.yaml")) as f:
        docs = list(yaml.safe_load_all(f))
    for doc in docs:
        if doc.get("kind") != "ConfigMap":
            continue
        redis_conf = doc.get("data", {}).get("redis.conf", "")
        if 'requirepass ""' in redis_conf:
            print(f"FAIL  Redis config: empty requirepass")
            fail_count += 1
        else:
            print(f"PASS  Redis config: no empty requirepass")
            pass_count += 1

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  PARWA — K8s Secrets & ConfigMap Tests")
    print("=" * 60 + "\n")
    test_secrets_has_required_keys()
    test_configmap_no_creds()
    test_redis_no_empty_requirepass()
    total = pass_count + fail_count
    print(f"\n{'=' * 60}\n  RESULTS: {pass_count} passed, {fail_count} failed out of {total}\n{'=' * 60}")
    sys.exit(1 if fail_count > 0 else 0)
