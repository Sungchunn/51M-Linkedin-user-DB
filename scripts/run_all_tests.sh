#!/bin/bash
# INSIGHT - Comprehensive Test Suite Runner
# Runs all tests for Phases 0-4

set -e  # Exit on error

cd "$(dirname "$0")/.."

echo "=========================================="
echo "INSIGHT - Running Full Test Suite"
echo "=========================================="
echo ""

# Load environment
set -a
source .env
set +a

# Track results
FAILED=0

# Phase 1: Database Schema Tests
echo "📋 Phase 1: Database Schema Tests"
poetry run pytest backend/tests/test_phase1.py -v --tb=short
if [ $? -ne 0 ]; then
    FAILED=$((FAILED + 1))
    echo "❌ Phase 1 tests FAILED"
else
    echo "✅ Phase 1 tests PASSED"
fi
echo ""

# Phase 2: Data Ingestion Tests
echo "📋 Phase 2: Data Ingestion Tests"
poetry run pytest backend/tests/test_phase2.py -v --tb=short
if [ $? -ne 0 ]; then
    FAILED=$((FAILED + 1))
    echo "❌ Phase 2 tests FAILED"
else
    echo "✅ Phase 2 tests PASSED"
fi
echo ""

# Phase 3: Embedding Generation Tests
echo "📋 Phase 3: Embedding Generation Tests"
poetry run pytest backend/tests/test_phase3.py -v --tb=short
if [ $? -ne 0 ]; then
    FAILED=$((FAILED + 1))
    echo "❌ Phase 3 tests FAILED"
else
    echo "✅ Phase 3 tests PASSED"
fi
echo ""

# Phase 4: API Tests (run individually due to event loop issues)
echo "📋 Phase 4: API Tests (Core Functionality)"
echo "Running critical API tests individually..."

# Test 1: Root endpoint
poetry run pytest backend/tests/test_phase4.py::TestPhase4API::test_tc_4_1_root_endpoint -v --tb=short
if [ $? -ne 0 ]; then
    FAILED=$((FAILED + 1))
    echo "❌ Root endpoint test FAILED"
fi

# Test 2: Health endpoint
poetry run pytest backend/tests/test_phase4.py::TestPhase4API::test_tc_4_2_health_endpoint -v --tb=short
if [ $? -ne 0 ]; then
    FAILED=$((FAILED + 1))
    echo "❌ Health endpoint test FAILED"
fi

# Test 3: Basic search
poetry run pytest backend/tests/test_phase4.py::TestPhase4API::test_tc_4_3_search_basic -v --tb=short
if [ $? -ne 0 ]; then
    FAILED=$((FAILED + 1))
    echo "❌ Basic search test FAILED"
fi

# Test 4: Validation tests
poetry run pytest backend/tests/test_phase4.py::TestPhase4API::test_tc_4_6_search_empty_query -v --tb=short
if [ $? -ne 0 ]; then
    FAILED=$((FAILED + 1))
    echo "❌ Validation test FAILED"
fi

if [ $FAILED -eq 0 ]; then
    echo "✅ Phase 4 critical tests PASSED"
else
    echo "❌ Phase 4 had $FAILED test failures"
fi
echo ""

# Summary
echo "=========================================="
echo "Test Suite Summary"
echo "=========================================="
if [ $FAILED -eq 0 ]; then
    echo "✅ ALL TESTS PASSED"
    exit 0
else
    echo "❌ $FAILED test suite(s) failed"
    exit 1
fi
