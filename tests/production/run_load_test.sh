#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# PARWA Load Test Runner
# ─────────────────────────────────────────────────────────────────────────────
#
# Run PARWA load tests with different profiles.
# Usage: ./run_load_test.sh [smoke|load|stress|spike|soak|breakpoint|chaos]
#
# Prerequisites:
#   - locust installed (pip install locust)
#   - Target server running
#
# Environment variables:
#   LOCUST_HOST  - Target host (default: http://localhost:8000)
#   REPORTS_DIR  - Output directory for reports (default: ./reports/TIMESTAMP)
#
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────

LOCUST_HOST="${LOCUST_HOST:-http://localhost:8000}"
REPORTS_DIR="${REPORTS_DIR:-./reports/$(date +%Y%m%d_%H%M%S)}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ── Helper Functions ─────────────────────────────────────────────────────────

info() { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[PASS]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[FAIL]${NC} $*"; }

check_prerequisites() {
    if ! command -v locust &> /dev/null; then
        error "locust not found. Install with: pip install locust"
        exit 1
    fi

    # Check target host is reachable
    if ! curl -s -o /dev/null -w "%{http_code}" "${LOCUST_HOST}/health" 2>/dev/null | grep -qE "2[0-9]{2}|3[0-9]{2}"; then
        warn "Target host ${LOCUST_HOST} may not be reachable."
        warn "Continue anyway? (y/n)"
        read -r answer
        if [[ "$answer" != "y" ]]; then
            exit 0
        fi
    fi
}

create_reports_dir() {
    mkdir -p "$REPORTS_DIR"
    export REPORTS_DIR
    info "Reports will be saved to: ${REPORTS_DIR}"
}

run_locust() {
    local test_file="$1"
    shift
    local extra_args="$*"

    info "Running: locust -f ${test_file} --host=${LOCUST_HOST} ${extra_args}"

    cd "$PROJECT_ROOT"
    REPORTS_DIR="$REPORTS_DIR" locust \
        -f "$test_file" \
        --host="$LOCUST_HOST" \
        $extra_args

    local exit_code=$?
    if [[ $exit_code -eq 0 ]]; then
        success "Test completed successfully"
    else
        error "Test failed with exit code: ${exit_code}"
    fi
    return $exit_code
}

# ── Test Profiles ────────────────────────────────────────────────────────────

run_smoke() {
    info "═══════════════════════════════════════════════════"
    info "  SMOKE TEST: Quick validation (10 users, 1 min)"
    info "═══════════════════════════════════════════════════"
    run_locust \
        "tests/production/test_load.py" \
        "--headless --users 10 --spawn-rate 5 --run-time 1m \
         --html=${REPORTS_DIR}/smoke_test.html --csv=${REPORTS_DIR}/smoke"
}

run_load() {
    info "═══════════════════════════════════════════════════"
    info "  LOAD TEST: 500 concurrent users, 10 minutes"
    info "  Target: < 2s avg response time (NFR 3.1)"
    info "═══════════════════════════════════════════════════"
    run_locust \
        "tests/production/test_load.py" \
        "--headless --users 500 --spawn-rate 20 --run-time 10m \
         --html=${REPORTS_DIR}/load_test.html --csv=${REPORTS_DIR}/load"
}

run_stress() {
    info "═══════════════════════════════════════════════════"
    info "  STRESS TEST: 1000 users, push to limits"
    info "═══════════════════════════════════════════════════"
    run_locust \
        "tests/production/test_stress.py" \
        "SpikeTestUser --headless --users 1000 --spawn-rate 30 --run-time 5m \
         --html=${REPORTS_DIR}/stress_test.html --csv=${REPORTS_DIR}/stress"
}

run_spike() {
    info "═══════════════════════════════════════════════════"
    info "  SPIKE TEST: 50→500 users in 30 seconds"
    info "═══════════════════════════════════════════════════"
    run_locust \
        "tests/production/test_stress.py" \
        "SpikeTestUser --headless --users 500 --spawn-rate 15 --run-time 3m \
         --html=${REPORTS_DIR}/spike_test.html --csv=${REPORTS_DIR}/spike"
}

run_soak() {
    info "═══════════════════════════════════════════════════"
    info "  SOAK TEST: 200 users for 2 hours"
    info "  Detecting: memory leaks, connection pool exhaustion"
    info "═══════════════════════════════════════════════════"
    run_locust \
        "tests/production/test_stress.py" \
        "SoakTestUser --headless --users 200 --spawn-rate 5 --run-time 2h \
         --html=${REPORTS_DIR}/soak_test.html --csv=${REPORTS_DIR}/soak"
}

run_breakpoint() {
    info "═══════════════════════════════════════════════════"
    info "  BREAKPOINT TEST: 0→1000 users, find the limit"
    info "═══════════════════════════════════════════════════"
    run_locust \
        "tests/production/test_stress.py" \
        "BreakpointTestUser --headless --users 1000 --spawn-rate 1 --run-time 30m \
         --html=${REPORTS_DIR}/breakpoint_test.html --csv=${REPORTS_DIR}/breakpoint"
}

run_chaos() {
    info "═══════════════════════════════════════════════════"
    info "  CHAOS TEST: Load with simulated infra failures"
    info "  Validating: BC-008 (never crash)"
    info "═══════════════════════════════════════════════════"
    run_locust \
        "tests/production/test_stress.py" \
        "ChaosTestUser --headless --users 100 --spawn-rate 5 --run-time 10m \
         --html=${REPORTS_DIR}/chaos_test.html --csv=${REPORTS_DIR}/chaos"
}

# ── Main ─────────────────────────────────────────────────────────────────────

PROFILE="${1:-load}"

info "PARWA Load Test Runner"
info "  Profile:    ${PROFILE}"
info "  Target:     ${LOCUST_HOST}"
info "  Reports:    ${REPORTS_DIR}"
echo ""

check_prerequisites
create_reports_dir

case "$PROFILE" in
    smoke)
        run_smoke
        ;;
    load)
        run_load
        ;;
    stress)
        run_stress
        ;;
    spike)
        run_spike
        ;;
    soak)
        run_soak
        ;;
    breakpoint)
        run_breakpoint
        ;;
    chaos)
        run_chaos
        ;;
    all)
        info "Running ALL test profiles sequentially..."
        run_smoke
        echo ""
        run_spike
        echo ""
        run_load
        echo ""
        run_chaos
        ;;
    *)
        error "Unknown profile: ${PROFILE}"
        echo ""
        echo "Usage: $0 [smoke|load|stress|spike|soak|breakpoint|chaos|all]"
        echo ""
        echo "Profiles:"
        echo "  smoke       - Quick validation (10 users, 1 min)"
        echo "  load        - 500 concurrent users, 10 min (NFR 3.1)"
        echo "  stress      - Push to limits with 1000 users"
        echo "  spike       - 50→500 users in 30 seconds"
        echo "  soak        - 200 users for 2 hours (memory leak detection)"
        echo "  breakpoint  - Gradually increase until failure"
        echo "  chaos       - Load with simulated infra failures (BC-008)"
        echo "  all         - Run smoke, spike, load, and chaos sequentially"
        exit 1
        ;;
esac

info "Test complete. Reports saved to: ${REPORTS_DIR}"
