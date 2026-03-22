#!/bin/bash
#
# generate_coverage.sh - Generate coverage reports for PARWA
#
# This script generates comprehensive coverage reports for both
# Python backend and TypeScript frontend.
#
# Usage:
#   ./scripts/generate_coverage.sh [OPTIONS]
#
# Options:
#   --backend       Generate only backend coverage
#   --frontend      Generate only frontend coverage
#   --threshold N   Set minimum coverage threshold (default: 80)
#   --badge         Generate coverage badge
#   --merge         Merge backend and frontend coverage
#   --upload        Upload to coverage service
#   -h, --help      Show this help message

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
RUN_BACKEND=true
RUN_FRONTEND=true
THRESHOLD=80
GENERATE_BADGE=true
MERGE_REPORTS=true
UPLOAD_COVERAGE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --backend)
            RUN_FRONTEND=false
            shift
            ;;
        --frontend)
            RUN_BACKEND=false
            shift
            ;;
        --threshold)
            THRESHOLD="$2"
            shift 2
            ;;
        --badge)
            GENERATE_BADGE=true
            shift
            ;;
        --merge)
            MERGE_REPORTS=true
            shift
            ;;
        --upload)
            UPLOAD_COVERAGE=true
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
OUTPUT_DIR="${PROJECT_ROOT}/test-reports/coverage"
mkdir -p "$OUTPUT_DIR"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}PARWA Coverage Report Generator${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo "Threshold: ${THRESHOLD}%"
echo "Output: ${OUTPUT_DIR}"
echo ""

# Initialize coverage totals
BACKEND_COVERAGE=0
FRONTEND_COVERAGE=0
OVERALL_COVERAGE=0

# =============================================================================
# Backend Coverage (Python)
# =============================================================================
if [ "$RUN_BACKEND" = true ]; then
    echo -e "${YELLOW}Generating backend coverage...${NC}"
    
    cd "${PROJECT_ROOT}"
    
    # Run pytest with coverage
    python -m pytest tests/ \
        --cov=backend \
        --cov-report=term-missing \
        --cov-report=xml:"${OUTPUT_DIR}/backend_coverage.xml" \
        --cov-report=html:"${OUTPUT_DIR}/backend_html" \
        -q \
        --no-header || true
    
    # Extract coverage percentage from XML
    if [ -f "${OUTPUT_DIR}/backend_coverage.xml" ]; then
        BACKEND_COVERAGE=$(grep -oP 'line-rate="\K[^"]+' "${OUTPUT_DIR}/backend_coverage.xml" | head -1)
        BACKEND_COVERAGE=$(echo "$BACKEND_COVERAGE * 100" | bc -l | cut -c1-5)
        echo -e "Backend coverage: ${BACKEND_COVERAGE}%"
    fi
    
    cd "${PROJECT_ROOT}"
fi

# =============================================================================
# Frontend Coverage (TypeScript/React)
# =============================================================================
if [ "$RUN_FRONTEND" = true ]; then
    echo -e "${YELLOW}Generating frontend coverage...${NC}"
    
    FRONTEND_DIR="${PROJECT_ROOT}/frontend"
    
    if [ -d "$FRONTEND_DIR" ]; then
        cd "$FRONTEND_DIR"
        
        # Run vitest with coverage
        npm run test -- --coverage 2>&1 || true
        
        # Copy coverage reports to output directory
        if [ -d "coverage" ]; then
            cp -r coverage/* "${OUTPUT_DIR}/frontend_" 2>/dev/null || true
            
            # Extract coverage from coverage-summary.json
            if [ -f "coverage/coverage-summary.json" ]; then
                FRONTEND_COVERAGE=$(grep -oP '"lines":\s*\{\s*"pct":\s*\K[0-9.]+' coverage/coverage-summary.json | head -1)
                echo -e "Frontend coverage: ${FRONTEND_COVERAGE}%"
            fi
        fi
        
        cd "${PROJECT_ROOT}"
    else
        echo -e "${YELLOW}Frontend directory not found, skipping...${NC}"
    fi
fi

# =============================================================================
# Generate Combined Report
# =============================================================================
if [ "$MERGE_REPORTS" = true ]; then
    echo -e "${YELLOW}Generating combined coverage report...${NC}"
    
    # Calculate overall coverage
    if [ "$RUN_BACKEND" = true ] && [ "$RUN_FRONTEND" = true ]; then
        # Weighted average based on lines of code
        OVERALL_COVERAGE=$(echo "scale=2; ($BACKEND_COVERAGE + $FRONTEND_COVERAGE) / 2" | bc)
    elif [ "$RUN_BACKEND" = true ]; then
        OVERALL_COVERAGE=$BACKEND_COVERAGE
    elif [ "$RUN_FRONTEND" = true ]; then
        OVERALL_COVERAGE=$FRONTEND_COVERAGE
    fi
    
    # Generate combined JSON report
    cat > "${OUTPUT_DIR}/coverage_summary.json" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "threshold": $THRESHOLD,
    "backend": {
        "coverage": $BACKEND_COVERAGE,
        "passed": $(echo "$BACKEND_COVERAGE >= $THRESHOLD" | bc -l)
    },
    "frontend": {
        "coverage": $FRONTEND_COVERAGE,
        "passed": $(echo "$FRONTEND_COVERAGE >= $THRESHOLD" | bc -l)
    },
    "overall": {
        "coverage": $OVERALL_COVERAGE,
        "passed": $(echo "$OVERALL_COVERAGE >= $THRESHOLD" | bc -l)
    }
}
EOF
fi

# =============================================================================
# Generate Badge
# =============================================================================
if [ "$GENERATE_BADGE" = true ]; then
    echo -e "${YELLOW}Generating coverage badge...${NC}"
    
    # Determine badge color based on coverage
    if (( $(echo "$OVERALL_COVERAGE >= 90" | bc -l) )); then
        COLOR="#97CA00"  # Green
    elif (( $(echo "$OVERALL_COVERAGE >= 80" | bc -l) )); then
        COLOR="#a4a61d"  # Yellow-green
    elif (( $(echo "$OVERALL_COVERAGE >= 60" | bc -l) )); then
        COLOR="#dfb317"  # Yellow
    else
        COLOR="#e05d44"  # Red
    fi
    
    # Generate SVG badge
    cat > "${OUTPUT_DIR}/coverage.svg" << EOF
<svg xmlns="http://www.w3.org/2000/svg" width="104" height="20">
  <linearGradient id="a" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <rect rx="3" width="104" height="20" fill="#555"/>
  <rect rx="3" x="62" width="42" height="20" fill="${COLOR}"/>
  <path fill="url(#a)" d="M0 0h104v20H0z"/>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
    <text x="32" y="15">coverage</text>
    <text x="82" y="15">${OVERALL_COVERAGE}%</text>
  </g>
</svg>
EOF
    
    # Copy badge to README location if it exists
    if [ -f "${PROJECT_ROOT}/README.md" ]; then
        mkdir -p "${PROJECT_ROOT}/.github/badges"
        cp "${OUTPUT_DIR}/coverage.svg" "${PROJECT_ROOT}/.github/badges/"
    fi
fi

# =============================================================================
# Print Summary
# =============================================================================
echo ""
echo "============================================================"
echo "COVERAGE SUMMARY"
echo "============================================================"

if [ "$RUN_BACKEND" = true ]; then
    if (( $(echo "$BACKEND_COVERAGE >= $THRESHOLD" | bc -l) )); then
        echo -e "Backend:    ${GREEN}${BACKEND_COVERAGE}% ✓${NC}"
    else
        echo -e "Backend:    ${RED}${BACKEND_COVERAGE}% ✗ (below threshold)${NC}"
    fi
fi

if [ "$RUN_FRONTEND" = true ]; then
    if (( $(echo "$FRONTEND_COVERAGE >= $THRESHOLD" | bc -l) )); then
        echo -e "Frontend:   ${GREEN}${FRONTEND_COVERAGE}% ✓${NC}"
    else
        echo -e "Frontend:   ${RED}${FRONTEND_COVERAGE}% ✗ (below threshold)${NC}"
    fi
fi

echo ""
if (( $(echo "$OVERALL_COVERAGE >= $THRESHOLD" | bc -l) )); then
    echo -e "Overall:    ${GREEN}${OVERALL_COVERAGE}% ✓${NC}"
    echo -e "${GREEN}✓ Coverage threshold met!${NC}"
    EXIT_CODE=0
else
    echo -e "Overall:    ${RED}${OVERALL_COVERAGE}% ✗${NC}"
    echo -e "${RED}✗ Coverage below threshold (${THRESHOLD}%)${NC}"
    EXIT_CODE=1
fi

echo "============================================================"
echo "Reports saved to: ${OUTPUT_DIR}"

# =============================================================================
# Upload to Coverage Service (optional)
# =============================================================================
if [ "$UPLOAD_COVERAGE" = true ]; then
    echo -e "${YELLOW}Uploading coverage reports...${NC}"
    
    # Check for Codecov
    if command -v codecov &> /dev/null; then
        codecov -f "${OUTPUT_DIR}/backend_coverage.xml" -F backend
        echo -e "${GREEN}✓ Coverage uploaded to Codecov${NC}"
    else
        echo -e "${YELLOW}Codecov CLI not found, skipping upload${NC}"
    fi
fi

exit $EXIT_CODE
