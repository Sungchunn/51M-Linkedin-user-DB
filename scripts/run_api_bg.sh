#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

mkdir -p .tmp

# Load env if present
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

# Ensure PG_DSN points to local Docker Postgres (profiles DB on 5433)
export PG_DSN="${PG_DSN:-}"
if [[ -z "${PG_DSN}" ]] || [[ "${PG_DSN}" == *"semantic_talent"* ]]; then
  export PG_DSN="postgresql://postgres:postgres@127.0.0.1:5433/profiles"
fi

LOG_FILE=".tmp/uvicorn.log"
PID_FILE=".tmp/uvicorn.pid"

echo "Starting FastAPI on :8000 (PG_DSN=$PG_DSN)"
nohup poetry run uvicorn backend.api.app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  > "$LOG_FILE" 2>&1 &

API_PID=$!
echo "$API_PID" > "$PID_FILE"
echo "FastAPI started with PID $API_PID. Logs: $LOG_FILE"
