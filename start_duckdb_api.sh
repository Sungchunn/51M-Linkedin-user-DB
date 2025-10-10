#!/bin/bash
# INSIGHT - Start DuckDB-Only API Server
# Queries 51M profiles from S3 with zero local disk usage

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "🚀 Starting INSIGHT DuckDB API"
echo "============================================================"
echo ""
echo "API Features:"
echo "  ✅ Browse 51M+ profiles from S3"
echo "  ✅ Zero local disk usage"
echo "  ✅ Keyword search + filters"
echo "  ✅ Country, industry, experience filters"
echo ""
echo "API will be available at: http://localhost:8000"
echo "API docs: http://localhost:8000/docs"
echo ""
echo "Frontend: Open frontend/index.html in your browser"
echo ""
echo "Press Ctrl+C to stop"
echo ""
echo "============================================================"
echo ""

# Start the API server
poetry run python3 -m backend.api.duckdb_app
