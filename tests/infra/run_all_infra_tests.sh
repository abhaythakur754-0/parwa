#!/bin/bash
# ════════════════════════════════════════════════════════════════
# PARWA — Infrastructure Test Runner
# Runs all infrastructure test suites and produces a summary report
# ════════════════════════════════════════════════════════════════
# Usage:
#   chmod +x tests/infra/run_all_infra_tests.sh
#   ./tests/infra/run_all_infra_tests.sh
# ════════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REPORT_FILE="${SCRIPT_DIR}/infra_test_report.txt"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Counters
TOTAL_PASS=0
TOTAL_FAIL=0
TOTAL_SKIP=0
TOTAL_SUITES=0
FAILED_SUITES=""

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     PARWA Infrastructure — Full Test Suite Runner         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Project: ${PROJECT_ROOT}"
echo "Report:  ${REPORT_FILE}"
echo "Date:    $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo ""

# Start report
echo "PARWA Infrastructure Test Report" > "${REPORT_FILE}"
echo "Date: $(date -u '+%Y-%m-%d %H:%M:%S UTC')" >> "${REPORT_FILE}"
echo "================================" >> "${REPORT_FILE}"
echo "" >> "${REPORT_FILE}"

# Find all test files
TEST_FILES=$(find "${SCRIPT_DIR}" -name "test_*.py" -o -name "test_*.sh" | sort)

for test_file in ${TEST_FILES}; do
    suite_name=$(basename "${test_file}")
    TOTAL_SUITES=$((TOTAL_SUITES + 1))
    
    echo -n "Running ${suite_name}... "
    
    if [[ "${test_file}" == *.py ]]; then
        # Python pytest
        output=$(cd "${PROJECT_ROOT}" && python -m pytest "${test_file}" --tb=short --noconftest -p no:conftest -q 2>&1) || true
    else
        # Shell test
        output=$(bash "${test_file}" 2>&1) || true
    fi
    
    # Parse results
    passed=$(echo "${output}" | grep -oP '\d+(?= passed)' || echo "0")
    failed=$(echo "${output}" | grep -oP '\d+(?= failed)' || echo "0")
    skipped=$(echo "${output}" | grep -oP '\d+(?= skipped)' || echo "0")
    
    TOTAL_PASS=$((TOTAL_PASS + passed))
    TOTAL_FAIL=$((TOTAL_FAIL + failed))
    TOTAL_SKIP=$((TOTAL_SKIP + skipped))
    
    if [[ "${failed}" -gt 0 ]]; then
        echo -e "${RED}FAIL${NC} (${passed} passed, ${failed} failed)"
        FAILED_SUITES="${FAILED_SUITES}  - ${suite_name}\n"
        echo "[FAIL] ${suite_name}: ${passed} passed, ${failed} failed" >> "${REPORT_FILE}"
    else
        echo -e "${GREEN}PASS${NC} (${passed} passed)"
        echo "[PASS] ${suite_name}: ${passed} passed" >> "${REPORT_FILE}"
    fi
done

echo ""
echo "══════════════════════════════════════════════════════════════"
echo -e "  Suites:   ${TOTAL_SUITES}"
echo -e "  Passed:   ${GREEN}${TOTAL_PASS}${NC}"
echo -e "  Failed:   ${RED}${TOTAL_FAIL}${NC}"
echo -e "  Skipped:  ${YELLOW}${TOTAL_SKIP}${NC}"
echo "══════════════════════════════════════════════════════════════"

# Final report
echo "" >> "${REPORT_FILE}"
echo "SUMMARY" >> "${REPORT_FILE}"
echo "-------" >> "${REPORT_FILE}"
echo "Total suites:  ${TOTAL_SUITES}" >> "${REPORT_FILE}"
echo "Total passed:  ${TOTAL_PASS}" >> "${REPORT_FILE}"
echo "Total failed:  ${TOTAL_FAIL}" >> "${REPORT_FILE}"
echo "Total skipped: ${TOTAL_SKIP}" >> "${REPORT_FILE}"
echo "" >> "${REPORT_FILE}"

if [[ "${TOTAL_FAIL}" -eq 0 ]]; then
    echo "VERDICT: ALL TESTS PASSED ✅" >> "${REPORT_FILE}"
    echo -e "\n${GREEN}ALL ${TOTAL_PASS} TESTS PASSED! Infrastructure is PRODUCTION-READY ✅${NC}"
else
    echo "VERDICT: SOME TESTS FAILED ❌" >> "${REPORT_FILE}"
    echo -e "\n${RED}${TOTAL_FAIL} TESTS FAILED! Fix before production deployment.${NC}"
    echo -e "Failed suites:\n${FAILED_SUITES}"
fi

echo ""
echo "Report saved to: ${REPORT_FILE}"
