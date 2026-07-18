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

# Run a command in the background, showing a spinner + elapsed seconds.
# Output is buffered and printed once the command finishes.
run_with_spinner() {
    local label=$1
    shift
    local out
    out=$(mktemp)
    "$@" > "$out" 2>&1 &
    local pid=$! start=$SECONDS frames='|/-\' i=0
    while kill -0 "$pid" 2>/dev/null; do
        printf '\r   %s %s [%ds]  ' "${frames:$((i++ % 4)):1}" "$label" $((SECONDS - start))
        sleep 1
    done
    local rc=0
    wait "$pid" || rc=$?
    printf '\r%*s\r' 60 ''
    cat "$out"
    rm -f "$out"
    return $rc
}

echo "=== 1/3 Generating embeddings (resumable; Ctrl-C safe) ==="
EMBED_CONCURRENCY="${EMBED_CONCURRENCY:-12}" poetry run generate-embeddings

echo
echo "=== 2/3 Building HNSW index (one-time, ~10-20 min; skipped if it exists) ==="
if [ -n "$(psql "$PG_DSN" -t -A -c "SELECT 1 FROM pg_indexes WHERE tablename='profiles' AND indexname='idx_profiles_embedding_hnsw'")" ]; then
    echo "   ✅ Index already exists — skipping build."
else
    # Serial build with 4GB local memory: the ~3.5GB HNSW graph for 497K vectors
    # stays in RAM (a 2GB parallel build spilled to disk at 314K tuples and
    # crawled). Serial = no shared-memory allocation, so the shm cap is moot.
    # ON_ERROR_STOP makes psql exit nonzero on failure instead of reporting success.
    psql "$PG_DSN" -q -v ON_ERROR_STOP=1 \
      -c "SET maintenance_work_mem='4GB';" \
      -c "SET max_parallel_maintenance_workers=0;" \
      -c "CREATE INDEX IF NOT EXISTS idx_profiles_embedding_hnsw
          ON profiles USING hnsw (embedding vector_cosine_ops)
          WITH (m=16, ef_construction=64);" &
    build_pid=$!
    build_start=$SECONDS
    sleep 2
    # Live progress from Postgres itself (phase + % done when counters are exposed)
    while kill -0 "$build_pid" 2>/dev/null; do
        prog=$(psql "$PG_DSN" -t -A -c "
            SELECT phase || coalesce(': ' ||
                CASE WHEN blocks_total > 0 THEN round(100.0 * blocks_done / blocks_total, 1) || '%'
                     WHEN tuples_total > 0 THEN round(100.0 * tuples_done / tuples_total, 1) || '%'
                END, '')
            FROM pg_stat_progress_create_index LIMIT 1" 2>/dev/null || true)
        printf '\r   ⏳ %-50s [%dm%02ds elapsed]  ' \
            "${prog:-waiting for build to start...}" \
            $(((SECONDS - build_start) / 60)) $(((SECONDS - build_start) % 60))
        sleep 3
    done
    printf '\n'
    wait "$build_pid"
    echo "   ✅ Index built in $(((SECONDS - build_start) / 60))m$(((SECONDS - build_start) % 60))s"
fi

echo
echo "=== 3/3 Verification ==="
run_with_spinner "running verification queries..." psql "$PG_DSN" \
  -c "SELECT count(*) AS total_profiles,
             count(embedding) AS embedded,
             count(*) - count(embedding) AS missing
      FROM profiles WHERE is_deleted = FALSE;" \
  -c "SELECT indexname FROM pg_indexes
      WHERE tablename = 'profiles' AND indexname = 'idx_profiles_embedding_hnsw';"

echo
echo "Done. If 'missing' is 0 and the index row is shown above, hybrid search is live —"
echo "restart the API (./start_api.sh) and /search will use vector + lexical scoring."
