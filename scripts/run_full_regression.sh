#!/bin/bash
# Full Regression Script for Week 30

set -e

echo "=== WEEK 30 FULL REGRESSION TEST ==="
echo "Running all test suites..."

# Run all tests
echo "1. Running client tests..."
pytest tests/clients/ -v --tb=short

echo "2. Running regression tests..."
pytest tests/regression/ -v --tb=short

echo "3. Running compliance tests..."
pytest tests/compliance/ -v --tb=short

echo ""
echo "=== REGRESSION COMPLETE ==="
echo "All tests passed!"
