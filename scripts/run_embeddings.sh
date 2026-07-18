#!/usr/bin/env bash
# Full embedding job: generate all missing embeddings, build the HNSW index, verify.
#
# - Resumable: rerun this script after any interruption — embedded profiles are
#   skipped automatically, the index build is a no-op if the index exists.
# - Concurrency: override with EMBED_CONCURRENCY=20 (default 12 parallel OpenAI calls).
# - Requires .env with PG_DSN and OPENAI_API_KEY.
set -euo pipefail
cd "$(dirname "$0")/.."

set -a
source .env
set +a

echo "=== 1/3 Generating embeddings (resumable; Ctrl-C safe) ==="
EMBED_CONCURRENCY="${EMBED_CONCURRENCY:-12}" poetry run generate-embeddings

echo
echo "=== 2/3 Building HNSW index (one-time, ~10-20 min; skipped if it exists) ==="
psql "$PG_DSN" \
  -c "SET maintenance_work_mem='2GB';" \
  -c "CREATE INDEX IF NOT EXISTS idx_profiles_embedding_hnsw
      ON profiles USING hnsw (embedding vector_cosine_ops)
      WITH (m=16, ef_construction=64);"

echo
echo "=== 3/3 Verification ==="
psql "$PG_DSN" \
  -c "SELECT count(*) AS total_profiles,
             count(embedding) AS embedded,
             count(*) - count(embedding) AS missing
      FROM profiles WHERE is_deleted = FALSE;" \
  -c "SELECT indexname FROM pg_indexes
      WHERE tablename = 'profiles' AND indexname = 'idx_profiles_embedding_hnsw';"

echo
echo "Done. If 'missing' is 0 and the index row is shown above, hybrid search is live —"
echo "restart the API (./start_api.sh) and /search will use vector + lexical scoring."
