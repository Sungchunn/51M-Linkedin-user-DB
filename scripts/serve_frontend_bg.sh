#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT/frontend"

mkdir -p ../.tmp

LOG_FILE="../.tmp/frontend_http.log"
PID_FILE="../.tmp/frontend_http.pid"

echo "Serving frontend at http://localhost:5500 (from $(pwd))"
nohup python3 -m http.server 5500 > "$LOG_FILE" 2>&1 &
HTTP_PID=$!
echo "$HTTP_PID" > "$PID_FILE"
echo "Frontend server started with PID $HTTP_PID. Logs: $LOG_FILE"

