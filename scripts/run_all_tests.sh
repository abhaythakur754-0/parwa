#!/bin/bash
#
# run_all_tests.sh - Run all PARWA test suites
#
# This script runs all tests in parallel where possible and aggregates results.
#
# Usage:
#   ./scripts/run_all_tests.sh [OPTIONS]
#
# Options:
#   --unit          Run only unit tests
#   --integration   Run only integration tests
#   --e2e           Run only E2E tests
#   --ui            Run only UI tests
#   --bdd           Run only BDD tests
#   --coverage      Run with coverage collection
#   --parallel      Run test suites in parallel
#   --failfast      Stop on first failure
#   --verbose       Enable verbose output
#   -h, --help      Show this help message

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
RUN_UNIT=true
RUN_INTEGRATION=true
RUN_E2E=true
RUN_UI=true
RUN_BDD=true
RUN_COVERAGE=false
RUN_PARALLEL=false
FAIL_FAST=false
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --unit)
            RUN_INTEGRATION=false
            RUN_E2E=false
            RUN_UI=false
            RUN_BDD=false
            shift
            ;;
        --integration)
            RUN_UNIT=false
            RUN_E2E=false
            RUN_UI=false
            RUN_BDD=false
            shift
            ;;
        --e2e)
            RUN_UNIT=false
            RUN_INTEGRATION=false
            RUN_UI=false
            RUN_BDD=false
            shift
            ;;
        --ui)
            RUN_UNIT=false
            RUN_INTEGRATION=false
            RUN_E2E=false
            RUN_BDD=false
            shift
            ;;
        --bdd)
            RUN_UNIT=false
            RUN_INTEGRATION=false
            RUN_E2E=false
            RUN_UI=false
            shift
            ;;
        --coverage)
            RUN_COVERAGE=true
            shift
            ;;
        --parallel)
            RUN_PARALLEL=true
            shift
            ;;
        --failfast)
            FAIL_FAST=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            head -25 "$0" | tail -24
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Find project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Create output directory
OUTPUT_DIR="${PROJECT_ROOT}/test-reports"
mkdir -p "$OUTPUT_DIR"

# Initialize counters
TOTAL_TESTS=0
TOTAL_PASSED=0
TOTAL_FAILED=0
TOTAL_SKIPPED=0
TOTAL_ERRORS=0
START_TIME=$(date +%s)

# Function to run tests
run_test_suite() {
    local suite_name=$1
    local test_path=$2
    local output_file="${OUTPUT_DIR}/${suite_name}_results.xml"
    
    echo -e "${BLUE}Running ${suite_name} tests...${NC}"
    
    local pytest_args=(
        "$test_path"
        "--junitxml=${output_file}"
        "-q"
    )
    
    if [ "$VERBOSE" = true ]; then
        pytest_args+=("-v")
    fi
    
    if [ "$FAIL_FAST" = true ]; then
        pytest_args+=("-x")
    fi
    
    if [ "$RUN_COVERAGE" = true ]; then
        pytest_args+=(
            "--cov=backend"
            "--cov-report=xml:${OUTPUT_DIR}/coverage_${suite_name}.xml"
            "--cov-report=term-missing"
        )
    fi
    
    local exit_code=0
    if python -m pytest "${pytest_args[@]}" 2>&1 | tee "${OUTPUT_DIR}/${suite_name}_output.log"; then
        echo -e "${GREEN}✓ ${suite_name} tests passed${NC}"
    else
        exit_code=$?
        echo -e "${RED}✗ ${suite_name} tests failed (exit code: ${exit_code})${NC}"
    fi
    
    return $exit_code
}

# Function to extract results from JUnit XML
extract_results() {
    local xml_file=$1
    if [ -f "$xml_file" ]; then
        # Simple extraction using grep
        local tests=$(grep -oP 'tests="\K[^"]+' "$xml_file" | head -1)
        local failures=$(grep -oP 'failures="\K[^"]+' "$xml_file" | head -1)
        local errors=$(grep -oP 'errors="\K[^"]+' "$xml_file" | head -1)
        local skipped=$(grep -oP 'skipped="\K[^"]+' "$xml_file" | head -1)
        
        echo "$tests $failures $errors $skipped"
    else
        echo "0 0 0 0"
    fi
}

# Store PIDs for parallel execution
declare -a PIDS
declare -a SUITES

# Run tests
if [ "$RUN_PARALLEL" = true ]; then
    echo -e "${YELLOW}Running test suites in parallel...${NC}"
    
    [ "$RUN_UNIT" = true ] && {
        run_test_suite "unit" "tests/unit/" &
        PIDS+=($!)
        SUITES+=("unit")
    }
    
    [ "$RUN_INTEGRATION" = true ] && {
        run_test_suite "integration" "tests/integration/" &
        PIDS+=($!)
        SUITES+=("integration")
    }
    
    [ "$RUN_E2E" = true ] && {
        run_test_suite "e2e" "tests/e2e/" &
        PIDS+=($!)
        SUITES+=("e2e")
    }
    
    [ "$RUN_UI" = true ] && {
        run_test_suite "ui" "tests/ui/" &
        PIDS+=($!)
        SUITES+=("ui")
    }
    
    [ "$RUN_BDD" = true ] && {
        run_test_suite "bdd" "tests/bdd/" &
        PIDS+=($!)
        SUITES+=("bdd")
    }
    
    # Wait for all tests to complete
    EXIT_CODE=0
    for i in "${!PIDS[@]}"; do
        if ! wait "${PIDS[$i]}"; then
            EXIT_CODE=1
            echo -e "${RED}${SUITES[$i]} tests failed${NC}"
        fi
    done
else
    echo -e "${YELLOW}Running test suites sequentially...${NC}"
    EXIT_CODE=0
    
    [ "$RUN_UNIT" = true ] && ! run_test_suite "unit" "tests/unit/" && EXIT_CODE=1
    [ "$RUN_INTEGRATION" = true ] && ! run_test_suite "integration" "tests/integration/" && EXIT_CODE=1
    [ "$RUN_E2E" = true ] && ! run_test_suite "e2e" "tests/e2e/" && EXIT_CODE=1
    [ "$RUN_UI" = true ] && ! run_test_suite "ui" "tests/ui/" && EXIT_CODE=1
    [ "$RUN_BDD" = true ] && ! run_test_suite "bdd" "tests/bdd/" && EXIT_CODE=1
fi

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Aggregate results
for suite in unit integration e2e ui bdd; do
    xml_file="${OUTPUT_DIR}/${suite}_results.xml"
    if [ -f "$xml_file" ]; then
        read -r tests failures errors skipped <<< "$(extract_results "$xml_file")"
        TOTAL_TESTS=$((TOTAL_TESTS + tests))
        TOTAL_FAILED=$((TOTAL_FAILED + failures))
        TOTAL_ERRORS=$((TOTAL_ERRORS + errors))
        TOTAL_SKIPPED=$((TOTAL_SKIPPED + skipped))
    fi
done

TOTAL_PASSED=$((TOTAL_TESTS - TOTAL_FAILED - TOTAL_ERRORS - TOTAL_SKIPPED))
PASS_RATE=0
if [ "$TOTAL_TESTS" -gt 0 ]; then
    PASS_RATE=$(echo "scale=2; $TOTAL_PASSED * 100 / $TOTAL_TESTS" | bc)
fi

# Generate summary
SUMMARY_FILE="${OUTPUT_DIR}/test_summary.json"
cat > "$SUMMARY_FILE" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "total_tests": $TOTAL_TESTS,
    "passed": $TOTAL_PASSED,
    "failed": $TOTAL_FAILED,
    "errors": $TOTAL_ERRORS,
    "skipped": $TOTAL_SKIPPED,
    "pass_rate": $PASS_RATE,
    "duration_seconds": $DURATION,
    "all_passed": $([ $EXIT_CODE -eq 0 ] && echo "true" || echo "false")
}
EOF

# Print summary
echo ""
echo "============================================================"
echo "TEST SUMMARY"
echo "============================================================"
echo -e "Total Tests:    ${TOTAL_TESTS}"
echo -e "Passed:         ${GREEN}${TOTAL_PASSED}${NC}"
echo -e "Failed:         ${RED}${TOTAL_FAILED}${NC}"
echo -e "Errors:         ${RED}${TOTAL_ERRORS}${NC}"
echo -e "Skipped:        ${YELLOW}${TOTAL_SKIPPED}${NC}"
echo -e "Pass Rate:      ${PASS_RATE}%"
echo -e "Duration:       ${DURATION}s"
echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ ALL TESTS PASSED${NC}"
else
    echo -e "${RED}✗ SOME TESTS FAILED${NC}"
fi
echo "============================================================"
echo "Results saved to: ${OUTPUT_DIR}"

exit $EXIT_CODE
