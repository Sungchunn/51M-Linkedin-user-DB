#!/usr/bin/env python3
"""
INSIGHT - Streaming Extraction (Low Memory)

Alternative approach for limited disk space.
Processes data in small chunks instead of loading all 15GB at once.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment
load_dotenv(project_root / '.env')

from backend.duck import get_duckdb_conn, get_parquet_path

def main():
    print("=" * 70)
    print("🔍 INSIGHT - Streaming Extract (Low Memory)")
    print("=" * 70)
    print()
    print("This approach uses LESS disk space:")
    print("  - Processes data in small batches")
    print("  - No temp files needed")
    print("  - Directly writes to output")
    print()
    print("⏱️  Time: 15-20 minutes")
    print("💾 Disk: ~500 MB output only")
    print()

    response = input("Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled.")
        return

    print()
    print("=" * 70)
    print("Step 1: Connecting to S3...")
    print("=" * 70)

    conn = get_duckdb_conn()
    parquet_path = get_parquet_path()

    # Minimal DuckDB config - no temp files!
    print("Configuring DuckDB for streaming...")
    conn.execute("SET memory_limit='2GB';")
    conn.execute("SET threads=2;")
    conn.execute("SET preserve_insertion_order=false;")

    print(f"✅ Connected to: {parquet_path}")
    print("✅ Streaming mode (minimal memory)")
    print()

    # Create output directory
    output_dir = project_root / 'data'
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / 'top_500k_profiles.parquet'

    print("=" * 70)
    print("Step 2: Streaming extraction...")
    print("=" * 70)
    print()

    # Simpler query - just filter and limit, no complex windowing
    query = f"""
        COPY (
            SELECT *
            FROM read_parquet('{parquet_path}')
            WHERE
                "Full name" IS NOT NULL
                AND "Full name" != ''
                AND "Job title" IS NOT NULL
                AND "Job title" != ''
                AND "Location Country" IS NOT NULL
                AND "Skills" IS NOT NULL
                AND "Skills" != ''
            ORDER BY random()
            LIMIT 500000
        ) TO '{output_file}' (FORMAT PARQUET, COMPRESSION ZSTD);
    """

    print("Streaming 500K random profiles...")
    print("(This will take 15-20 minutes)")
    print()

    import threading
    import time as time_module

    # Progress indicator
    stop_indicator = threading.Event()
    start_time = time_module.time()

    def show_progress():
        chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        idx = 0
        estimated_duration = 18 * 60  # 18 minutes average

        while not stop_indicator.is_set():
            elapsed = int(time_module.time() - start_time)
            mins = elapsed // 60
            secs = elapsed % 60

            # Calculate estimated percentage (cap at 99%)
            percent = min(int((elapsed / estimated_duration) * 100), 99)

            # Create progress bar [=====>    ] 50%
            bar_width = 20
            filled = int(bar_width * percent / 100)
            bar = '=' * filled + '>' + ' ' * (bar_width - filled - 1)

            print(f"\r{chars[idx % len(chars)]} [{bar}] {percent:2d}% | {mins:02d}:{secs:02d} elapsed   ", end='', flush=True)
            idx += 1
            time_module.sleep(0.1)

    progress_thread = threading.Thread(target=show_progress, daemon=True)
    progress_thread.start()

    try:
        conn.execute(query)
        stop_indicator.set()
        progress_thread.join(timeout=1)

        elapsed = int(time_module.time() - start_time)
        mins = elapsed // 60
        secs = elapsed % 60
        # Show 100% completion
        bar = '=' * 20
        print(f"\r✅ [{bar}] 100% | {mins:02d}:{secs:02d} - Extraction complete!     ")
        print()

        # Verify
        print()
        print("=" * 70)
        print("✅ SUCCESS!")
        print("=" * 70)
        print()
        print(f"📁 Output: {output_file}")

        file_size_mb = output_file.stat().st_size / (1024 * 1024)
        print(f"💾 Size: {file_size_mb:.1f} MB")

        # Quick count
        count = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{output_file}')").fetchone()[0]
        print(f"📊 Profiles: {count:,}")

        print()
        print("=" * 70)
        print("Next Steps:")
        print("=" * 70)
        print()
        print("1. Load to PostgreSQL:")
        print(f"   poetry run load-parquet {output_file}")
        print()
        print("2. Transform to core:")
        print("   poetry run load-core")
        print()
        print("3. Build indexes:")
        print("   PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres \\")
        print("     -d profiles -f sql/03_indexes.sql")
        print()

    except Exception as e:
        stop_indicator.set()
        progress_thread.join(timeout=1)

        print()
        print()
        print("=" * 70)
        print("❌ EXTRACTION FAILED")
        print("=" * 70)
        print()
        print(f"Error: {e}")
        print()
        print("If still out of memory:")
        print("  1. Free up disk space (need 30GB free)")
        print("  2. Close other applications")
        print("  3. Or use PostgreSQL API without extraction")
        print()
        sys.exit(1)

if __name__ == '__main__':
    main()
