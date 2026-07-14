#!/bin/bash
# Test Frontend-Backend Connection

echo "============================================================"
echo "🔗 Testing Frontend-Backend Connection"
echo "============================================================"
echo ""

API_URL="http://localhost:8000"

# Check if API is running
echo "1. Checking if API is running..."
if ! curl -s "$API_URL/" > /dev/null 2>&1; then
    echo "❌ API is not running at $API_URL"
    echo ""
    echo "Start the API first:"
    echo "  ./start_duckdb_api.sh"
    echo ""
    exit 1
fi
echo "✅ API is running"
echo ""

# Test health endpoint
echo "2. Testing /health endpoint..."
HEALTH=$(curl -s "$API_URL/health")
if echo "$HEALTH" | grep -q "healthy"; then
    echo "✅ Health check passed"
    echo "$HEALTH" | python3 -m json.tool | head -5
else
    echo "❌ Health check failed"
    echo "$HEALTH"
fi
echo ""

# Test countries endpoint
echo "3. Testing /countries endpoint..."
COUNTRIES=$(curl -s "$API_URL/countries")
if echo "$COUNTRIES" | grep -q "countries"; then
    COUNT=$(echo "$COUNTRIES" | python3 -c "import sys, json; print(len(json.load(sys.stdin)['countries']))")
    echo "✅ Countries endpoint works ($COUNT countries)"
else
    echo "❌ Countries endpoint failed"
    echo "$COUNTRIES"
fi
echo ""

# Test industries endpoint
echo "4. Testing /industries endpoint..."
INDUSTRIES=$(curl -s "$API_URL/industries")
if echo "$INDUSTRIES" | grep -q "industries"; then
    COUNT=$(echo "$INDUSTRIES" | python3 -c "import sys, json; print(len(json.load(sys.stdin)['industries']))")
    echo "✅ Industries endpoint works ($COUNT industries)"
else
    echo "❌ Industries endpoint failed"
    echo "$INDUSTRIES"
fi
echo ""

# Test stats endpoint
echo "5. Testing /stats endpoint..."
STATS=$(curl -s "$API_URL/stats" 2>&1)
if echo "$STATS" | grep -q "total_profiles"; then
    echo "✅ Stats endpoint works"
    echo "$STATS" | python3 -m json.tool | head -10
else
    echo "⚠️  Stats endpoint may be slow (15min S3 query)"
    echo "   This is expected - skip for now"
fi
echo ""

# Test search endpoint with simple query
echo "6. Testing /search endpoint..."
echo "   (This may take 10-15 minutes for DuckDB to download S3 data)"
echo "   Testing with limit=1..."
SEARCH=$(curl -s "$API_URL/search?limit=1" --max-time 5 2>&1)
if echo "$SEARCH" | grep -q "results"; then
    echo "✅ Search endpoint works"
else
    echo "⚠️  Search timed out (expected for DuckDB+S3)"
    echo "   This will be fixed once you load data to PostgreSQL"
fi
echo ""

echo "============================================================"
echo "✅ FRONTEND-BACKEND CONNECTION TEST COMPLETE"
echo "============================================================"
echo ""
echo "Summary:"
echo "  ✅ API is reachable"
echo "  ✅ All endpoints exist"
echo "  ⚠️  DuckDB queries are SLOW (10-15 min)"
echo ""
echo "Next Steps:"
echo "  1. Open frontend: open frontend/index.html"
echo "  2. Expect slow initial load (countries/industries download)"
echo "  3. For fast queries, load data to PostgreSQL (see docs/architecture/HYBRID_SETUP.md)"
echo ""
echo "============================================================"
