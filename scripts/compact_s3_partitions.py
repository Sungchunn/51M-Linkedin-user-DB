#!/usr/bin/env python3
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""
Compact the state-partitioned parquet warehouse on S3.

Athena CTAS wrote every partition of s3://<bucket>/curated/usa_profiles/state=<state>/
as 30 small files (Wyoming: 30 x 0.5MB). Each S3 GET costs round-trips, so per-file
overhead dominates small partitions. This script rewrites each state to one file
(or several ~--max-file-mb files for big states), sorted by --sort-by so parquet
row-group min/max statistics can prune on that column.

NEGATIVE SPACE CONTRACT:
- Never deletes originals until the compacted rows on S3 are verified equal
  (S3 originals count == local compacted count == uploaded compacted count)
- Only deletes the exact keys captured in the initial listing, never a recursive rm
- Re-runnable after a crash: leftover compact_* files are rebuilt from the
  originals while any originals remain; states with only compact_* files are skipped
- All S3 traffic flows through this machine: ~12GB down + ~12GB up for a full run

Data flow per state (smallest first):
  list originals -> count rows (S3 footers) -> DuckDB COPY to local tmp (sorted)
  -> verify local count -> upload compact_*.parquet -> verify uploaded count
  -> batch-delete originals

Usage:
  poetry run python scripts/compact_s3_partitions.py --dry-run
  poetry run python scripts/compact_s3_partitions.py --states wyoming "new york"
  poetry run python scripts/compact_s3_partitions.py               # everything
  poetry run python scripts/compact_s3_partitions.py --no-delete   # keep originals

Requires in .env: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION.
Uses the aws CLI for uploads/deletes and DuckDB httpfs for reads.
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import duckdb
from dotenv import load_dotenv

DEFAULT_BUCKET = "sungchunn-linkedin-db"
DEFAULT_PREFIX = "curated/usa_profiles"
DEFAULT_LOG_FILE = Path(__file__).resolve().parent.parent / ".tmp" / "compact_s3_partitions.log"
COMPACT_BASENAME = "compact"  # output files: compact_0.parquet, compact_1.parquet, ...
DELETE_BATCH_SIZE = 1000  # S3 DeleteObjects hard limit

logger = logging.getLogger("compact_s3")


def setup_logging(log_file: Path) -> None:
    """Console (HH:MM:SS) + append-mode log file (full timestamps) so long runs can be tailed."""
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S"))

    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))

    logger.setLevel(logging.INFO)
    logger.addHandler(console)
    logger.addHandler(file_handler)
    logger.info(f"Logging to {log_file}")


def fail(message: str) -> None:
    logger.error(f"❌ {message}")
    sys.exit(1)


def aws(args: list[str]) -> str:
    """Run an aws CLI command (list-args, no shell) and return stdout."""
    result = subprocess.run(["aws"] + args, capture_output=True, text=True)
    if result.returncode != 0:
        fail(f"aws {' '.join(args[:3])}... failed: {result.stderr.strip()}")
    return result.stdout


def list_states(bucket: str, prefix: str) -> list[str]:
    """Enumerate state=<name>/ partitions under the warehouse prefix."""
    out = aws(
        [
            "s3api",
            "list-objects-v2",
            "--bucket",
            bucket,
            "--prefix",
            f"{prefix}/",
            "--delimiter",
            "/",
            "--output",
            "json",
        ]
    )
    prefixes: list[str] = [p["Prefix"] for p in json.loads(out).get("CommonPrefixes", [])]
    states = [p.rstrip("/").split("state=", 1)[1] for p in prefixes if "state=" in p]
    if not states:
        fail(f"No state= partitions found under s3://{bucket}/{prefix}/")
    return states


def list_objects(bucket: str, state_prefix: str) -> list[dict[str, Any]]:
    """All objects in one partition as [{Key, Size}], paginated by the CLI."""
    out = aws(
        [
            "s3api",
            "list-objects-v2",
            "--bucket",
            bucket,
            "--prefix",
            state_prefix,
            "--output",
            "json",
        ]
    )
    contents: list[dict[str, Any]] = json.loads(out).get("Contents", [])
    return contents


def duckdb_connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(f"SET s3_region='{os.environ['AWS_REGION']}';")
    con.execute(f"SET s3_access_key_id='{os.environ['AWS_ACCESS_KEY_ID']}';")
    con.execute(f"SET s3_secret_access_key='{os.environ['AWS_SECRET_ACCESS_KEY']}';")
    con.execute("SET memory_limit='4GB';")
    return con


def sql_path_list(paths: list[str]) -> str:
    """SQL literal list of paths (keys may contain spaces; escape quotes)."""
    quoted = ", ".join("'" + p.replace("'", "''") + "'" for p in paths)
    return f"[{quoted}]"


def count_rows(con: duckdb.DuckDBPyConnection, paths: list[str]) -> int:
    """Row count via parquet footer metadata only — no data scan."""
    row: tuple[Any, ...] | None = con.execute(
        f"SELECT count(*) FROM read_parquet({sql_path_list(paths)}, hive_partitioning=false)"
    ).fetchone()
    assert row is not None, "count(*) query must return exactly one row"
    return int(row[0])


def validate_sort_column(con: duckdb.DuckDBPyConnection, s3_paths: list[str], sort_by: str) -> None:
    columns: list[str] = [
        r[0]
        for r in con.execute(
            f"DESCRIBE SELECT * FROM read_parquet({sql_path_list(s3_paths[:1])}, hive_partitioning=false)"
        ).fetchall()
    ]
    if sort_by not in columns:
        fail(
            f"--sort-by '{sort_by}' not in parquet schema. Available: {', '.join(sorted(columns))}"
        )


def compact_state(
    con: duckdb.DuckDBPyConnection,
    bucket: str,
    prefix: str,
    state: str,
    sort_by: str,
    max_file_bytes: int,
    delete_originals: bool,
) -> dict[str, Any]:
    """Compact one partition. Returns a stats dict for the summary table."""
    started = time.time()
    state_prefix = f"{prefix}/state={state}/"
    objects = list_objects(bucket, state_prefix)

    originals = [o for o in objects if not o["Key"].rsplit("/", 1)[-1].startswith(COMPACT_BASENAME)]
    stale_compact = [o for o in objects if o["Key"].rsplit("/", 1)[-1].startswith(COMPACT_BASENAME)]

    if not originals:
        return {"state": state, "skipped": True, "files_before": len(stale_compact)}

    original_bytes = sum(o["Size"] for o in originals)
    s3_paths = [f"s3://{bucket}/{o['Key']}" for o in originals]
    logger.info(
        f"state={state}: {len(originals)} original files, {original_bytes / 1048576:.1f} MB "
        f"— counting rows on S3..."
    )
    step = time.time()
    expected_rows = count_rows(con, s3_paths)
    if expected_rows == 0:
        fail(f"state={state}: originals contain 0 rows — refusing to compact an empty partition")
    logger.info(
        f"state={state}: {expected_rows:,} rows in originals ({time.time() - step:.1f}s) "
        f"— downloading, sorting by {sort_by}, writing local compacted file(s)..."
    )

    with tempfile.TemporaryDirectory(prefix=f"compact_{state.replace(' ', '_')}_") as tmp:
        con.execute(f"SET temp_directory='{tmp}';")
        source = (
            f"SELECT * FROM read_parquet({sql_path_list(s3_paths)}, hive_partitioning=false) "
            f'ORDER BY "{sort_by}"'
        )
        step = time.time()
        if original_bytes > max_file_bytes:
            con.execute(
                f"COPY ({source}) TO '{tmp}' (FORMAT PARQUET, COMPRESSION zstd, "
                f"FILE_SIZE_BYTES {max_file_bytes}, FILENAME_PATTERN '{COMPACT_BASENAME}_{{i}}')"
            )
        else:
            con.execute(
                f"COPY ({source}) TO '{tmp}/{COMPACT_BASENAME}_0.parquet' "
                f"(FORMAT PARQUET, COMPRESSION zstd)"
            )

        local_files = sorted(Path(tmp).glob(f"{COMPACT_BASENAME}_*.parquet"))
        assert local_files, f"state={state}: DuckDB COPY produced no output files"
        compacted_bytes = sum(f.stat().st_size for f in local_files)
        logger.info(
            f"state={state}: wrote {len(local_files)} local file(s), "
            f"{compacted_bytes / 1048576:.1f} MB ({time.time() - step:.1f}s) — verifying..."
        )

        local_rows = count_rows(con, [str(f) for f in local_files])
        assert local_rows == expected_rows, (
            f"state={state}: local compacted rows ({local_rows}) != originals ({expected_rows}) "
            f"— aborting before any upload"
        )

        # Stale compact_* files from a crashed run are superseded by this rebuild
        if stale_compact:
            logger.info(
                f"state={state}: removing {len(stale_compact)} stale compact file(s) "
                f"from a previous interrupted run"
            )
            delete_keys(bucket, [o["Key"] for o in stale_compact])

        uploaded_keys: list[str] = []
        for n, f in enumerate(local_files, 1):
            key = f"{state_prefix}{f.name}"
            logger.info(
                f"state={state}: uploading {f.name} "
                f"({f.stat().st_size / 1048576:.1f} MB) [{n}/{len(local_files)}]"
            )
            step = time.time()
            aws(["s3", "cp", str(f), f"s3://{bucket}/{key}", "--only-show-errors"])
            logger.info(f"state={state}: uploaded {f.name} ({time.time() - step:.1f}s)")
            uploaded_keys.append(key)

    logger.info(f"state={state}: verifying uploaded row count...")
    uploaded_rows = count_rows(con, [f"s3://{bucket}/{k}" for k in uploaded_keys])
    assert uploaded_rows == expected_rows, (
        f"state={state}: uploaded rows ({uploaded_rows}) != originals ({expected_rows}) "
        f"— originals NOT deleted; remove s3://{bucket}/{state_prefix}{COMPACT_BASENAME}_* "
        f"before retrying"
    )
    logger.info(f"state={state}: upload verified ({uploaded_rows:,} rows)")

    if delete_originals:
        logger.info(f"state={state}: deleting {len(originals)} verified originals...")
        delete_keys(bucket, [o["Key"] for o in originals])

    return {
        "state": state,
        "skipped": False,
        "rows": expected_rows,
        "files_before": len(originals),
        "files_after": len(uploaded_keys),
        "mb_before": original_bytes / 1048576,
        "mb_after": compacted_bytes / 1048576,
        "seconds": time.time() - started,
        "originals_deleted": delete_originals,
    }


def delete_keys(bucket: str, keys: list[str]) -> None:
    for i in range(0, len(keys), DELETE_BATCH_SIZE):
        batch = keys[i : i + DELETE_BATCH_SIZE]
        payload = json.dumps({"Objects": [{"Key": k} for k in batch], "Quiet": True})
        aws(["s3api", "delete-objects", "--bucket", bucket, "--delete", payload])


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[1])
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument(
        "--states", nargs="*", help="Only these states (default: all, smallest first)"
    )
    parser.add_argument(
        "--sort-by",
        default="company_industry",
        help="Column to sort by for row-group pruning (default: company_industry)",
    )
    parser.add_argument(
        "--max-file-mb", type=int, default=512, help="Split output above this size (default: 512)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="List and plan only — no reads/writes"
    )
    parser.add_argument(
        "--no-delete",
        action="store_true",
        help="Keep originals (WARNING: readers will double-count until they are removed)",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=DEFAULT_LOG_FILE,
        help=f"Append step-level logs here (default: {DEFAULT_LOG_FILE})",
    )
    args = parser.parse_args()

    setup_logging(args.log_file)
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION"):
        if not os.getenv(var):
            fail(f"{var} missing from environment/.env")

    all_states = list_states(args.bucket, args.prefix)
    if args.states:
        unknown = sorted(set(args.states) - set(all_states))
        if unknown:
            fail(f"Unknown states: {unknown}. Available: {sorted(all_states)}")
        selected = args.states
    else:
        selected = all_states

    # Smallest first: quick wins early, the big uploads last
    sizes: dict[str, tuple[int, int]] = {}
    for state in selected:
        objects = list_objects(args.bucket, f"{args.prefix}/state={state}/")
        originals = [
            o for o in objects if not o["Key"].rsplit("/", 1)[-1].startswith(COMPACT_BASENAME)
        ]
        sizes[state] = (len(originals), sum(o["Size"] for o in originals))
    selected = sorted(selected, key=lambda s: sizes[s][1])

    total_bytes = sum(sizes[s][1] for s in selected)
    logger.info(
        f"Plan: {len(selected)} states, {sum(sizes[s][0] for s in selected)} original files, "
        f"{total_bytes / 1073741824:.2f} GB to move (down + up), sorted smallest-first"
    )

    if args.dry_run:
        for state in selected:
            n, size = sizes[state]
            target = max(1, -(-size // (args.max_file_mb * 1048576)))  # ceil div
            status = "already compacted" if n == 0 else f"{n:3d} files -> {target}"
            logger.info(f"  state={state:<22} {size / 1048576:9.1f} MB  {status}")
        logger.info("Dry run — nothing was read, written, or deleted.")
        return

    con = duckdb_connect()
    first_with_files = next((s for s in selected if sizes[s][0] > 0), None)
    if first_with_files is None:
        logger.info("All selected states are already compacted — nothing to do.")
        return
    probe = list_objects(args.bucket, f"{args.prefix}/state={first_with_files}/")
    probe_paths = [
        f"s3://{args.bucket}/{o['Key']}"
        for o in probe
        if not o["Key"].rsplit("/", 1)[-1].startswith(COMPACT_BASENAME)
    ]
    validate_sort_column(con, probe_paths, args.sort_by)

    results: list[dict[str, Any]] = []
    for i, state in enumerate(selected, 1):
        result = compact_state(
            con,
            args.bucket,
            args.prefix,
            state,
            args.sort_by,
            args.max_file_mb * 1048576,
            not args.no_delete,
        )
        results.append(result)
        if result["skipped"]:
            logger.info(f"[{i:2d}/{len(selected)}] state={state:<22} already compacted — skipped")
        else:
            logger.info(
                f"[{i:2d}/{len(selected)}] state={state:<22} "
                f"{result['files_before']:3d} -> {result['files_after']} files  "
                f"{result['mb_before']:8.1f} -> {result['mb_after']:8.1f} MB  "
                f"{result['rows']:>10,} rows  {result['seconds']:6.1f}s"
            )

    done = [r for r in results if not r["skipped"]]
    logger.info(
        f"Done: {len(done)} states compacted, {len(results) - len(done)} skipped. "
        f"{sum(r['files_before'] for r in done)} files -> {sum(r['files_after'] for r in done)}, "
        f"{sum(r['mb_before'] for r in done) / 1024:.2f} GB -> "
        f"{sum(r['mb_after'] for r in done) / 1024:.2f} GB."
    )
    if args.no_delete:
        logger.warning(
            "⚠️  --no-delete: originals are still on S3 alongside compact files — "
            "readers will double-count until you delete them."
        )


if __name__ == "__main__":
    main()
