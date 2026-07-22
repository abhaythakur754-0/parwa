#!/bin/bash
# PARWA Infrastructure — Day 1 Test Runner
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOTAL_PASS=0
TOTAL_FAIL=0

echo "════════════════════════════════════════════════════════════"
echo "  PARWA Infrastructure — Day 1 Test Suite"
echo "════════════════════════════════════════════════════════════"
echo ""

run_test() {
    local name="$1"
    local cmd="$2"
    echo "── $name ──"
    if $cmd; then
        TOTAL_PASS=$((TOTAL_PASS + 1))
        echo "  -> Suite PASSED"
    else
        TOTAL_FAIL=$((TOTAL_FAIL + 1))
        echo "  -> Suite FAILED"
    fi
    echo ""
}

run_test "K8s Service Selectors" "python3 $SCRIPT_DIR/test_k8s_services.py"
run_test "K8s Secrets & ConfigMap" "python3 $SCRIPT_DIR/test_k8s_secrets_configmap.py"
run_test "K8s NetworkPolicies" "python3 $SCRIPT_DIR/test_k8s_networkpolicies.py"
run_test "K8s Deployments" "python3 $SCRIPT_DIR/test_k8s_deployments.py"
run_test "DB & Cache Configs" "python3 $SCRIPT_DIR/test_db_cache_configs.py"

TOTAL=$((TOTAL_PASS + TOTAL_FAIL))
echo "════════════════════════════════════════════════════════════"
echo "  DAY 1 TEST SUITE SUMMARY"
echo "  Suites passed: $TOTAL_PASS"
echo "  Suites failed: $TOTAL_FAIL"
echo "  Total suites:  $TOTAL"
echo "════════════════════════════════════════════════════════════"

[ $TOTAL_FAIL -eq 0 ] || exit 1
