#!/bin/bash
set -a
source .env
set +a
poetry run uvicorn backend.api.app:app --host 0.0.0.0 --port 8000 --reload
