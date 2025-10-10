#!/usr/bin/env python3
"""
INSIGHT - Extract Top 500K Profiles from S3

Extracts the highest quality profiles for fast PostgreSQL search.
Uses DuckDB to query S3 and save a local Parquet file.

Strategy:
- Select profiles with most complete data
- Prioritize profiles with skills, experience, location
- Stratify by country and industry for diversity
- Output: data/top_500k_profiles.parquet
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
    print("🔍 INSIGHT - Extract Top 500K Profiles")
    print("=" * 70)
    print()
    print("This will:")
    print("  1. Query S3 Parquet (51M profiles)")
    print("  2. Select top 500K by quality/completeness")
    print("  3. Stratify by country + industry")
    print("  4. Save to: data/top_500k_profiles.parquet")
    print()
    print("⏱️  Estimated time: 10-15 minutes")
    print("💾 Output size: ~500 MB")
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

    print(f"✅ Connected to: {parquet_path}")
    print()

    # Create output directory
    output_dir = project_root / 'data'
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / 'top_500k_profiles.parquet'

    print("=" * 70)
    print("Step 2: Extracting top 500K profiles...")
    print("=" * 70)
    print()
    print("Criteria:")
    print("  - Has full name")
    print("  - Has job title")
    print("  - Has location country")
    print("  - Stratified by country + industry")
    print("  - Ordered by data completeness")
    print()

    # Build quality score and extract query
    query = f"""
        COPY (
            SELECT *
            FROM (
                SELECT
                    *,
                    -- Calculate completeness score
                    (
                        (CASE WHEN "Full name" IS NOT NULL AND "Full name" != '' THEN 1 ELSE 0 END) +
                        (CASE WHEN "Job title" IS NOT NULL AND "Job title" != '' THEN 1 ELSE 0 END) +
                        (CASE WHEN "Company Name" IS NOT NULL AND "Company Name" != '' THEN 1 ELSE 0 END) +
                        (CASE WHEN "Industry" IS NOT NULL AND "Industry" != '' THEN 1 ELSE 0 END) +
                        (CASE WHEN "Location Country" IS NOT NULL AND "Location Country" != '' THEN 1 ELSE 0 END) +
                        (CASE WHEN "Skills" IS NOT NULL AND "Skills" != '' THEN 2 ELSE 0 END) +
                        (CASE WHEN "Years Experience" IS NOT NULL THEN 1 ELSE 0 END) +
                        (CASE WHEN "Locality" IS NOT NULL AND "Locality" != '' THEN 1 ELSE 0 END)
                    ) as quality_score,
                    ROW_NUMBER() OVER (
                        PARTITION BY "Location Country", "Industry"
                        ORDER BY (
                            (CASE WHEN "Full name" IS NOT NULL AND "Full name" != '' THEN 1 ELSE 0 END) +
                            (CASE WHEN "Job title" IS NOT NULL AND "Job title" != '' THEN 1 ELSE 0 END) +
                            (CASE WHEN "Skills" IS NOT NULL AND "Skills" != '' THEN 2 ELSE 0 END)
                        ) DESC, random()
                    ) as country_industry_rank
                FROM read_parquet('{parquet_path}')
                WHERE
                    "Full name" IS NOT NULL AND "Full name" != ''
                    AND "Job title" IS NOT NULL AND "Job title" != ''
                    AND "Location Country" IS NOT NULL AND "Location Country" != ''
            )
            WHERE quality_score >= 5  -- At least 5 out of 9 fields filled
            ORDER BY quality_score DESC, country_industry_rank ASC
            LIMIT 500000
        ) TO '{output_file}' (FORMAT PARQUET, COMPRESSION ZSTD);
    """

    print("Executing extraction query...")
    print("(This will take 10-15 minutes - downloading 15GB from S3)")
    print()
    print("Progress indicator (updates every 30 seconds):")
    print()

    import threading
    import time as time_module

    # Progress indicator
    stop_indicator = threading.Event()
    start_time = time_module.time()

    def show_progress():
        chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        idx = 0
        last_update = start_time

        while not stop_indicator.is_set():
            elapsed = int(time_module.time() - start_time)
            mins = elapsed // 60
            secs = elapsed % 60

            # Update every 30 seconds
            if time_module.time() - last_update >= 30:
                percent = min((elapsed / (15 * 60)) * 100, 99)
                print(f"\r{chars[idx % len(chars)]} Downloading... {mins:02d}:{secs:02d} elapsed ({percent:.0f}% est.)   ", end='', flush=True)
                last_update = time_module.time()
            else:
                print(f"\r{chars[idx % len(chars)]} Downloading... {mins:02d}:{secs:02d} elapsed   ", end='', flush=True)

            idx += 1
            time_module.sleep(0.1)

    # Start progress indicator
    progress_thread = threading.Thread(target=show_progress, daemon=True)
    progress_thread.start()

    try:
        conn.execute(query)
        stop_indicator.set()
        progress_thread.join(timeout=1)

        elapsed = int(time_module.time() - start_time)
        mins = elapsed // 60
        secs = elapsed % 60
        print(f"\r✅ Download complete! ({mins:02d}:{secs:02d})                    ")
        print()

        print()
        print("=" * 70)
        print("✅ SUCCESS!")
        print("=" * 70)
        print()
        print(f"📁 Output file: {output_file}")

        # Get file size
        file_size_mb = output_file.stat().st_size / (1024 * 1024)
        print(f"💾 File size: {file_size_mb:.1f} MB")

        # Quick stats
        print()
        print("Verifying extracted data...")
        stats_query = f"""
            SELECT
                COUNT(*) as total_profiles,
                COUNT(DISTINCT "Location Country") as countries,
                COUNT(DISTINCT "Industry") as industries,
                AVG(quality_score) as avg_quality
            FROM read_parquet('{output_file}')
        """
        stats = conn.execute(stats_query).fetchone()

        print()
        print("📊 Extracted Profile Stats:")
        print(f"   Total profiles: {stats[0]:,}")
        print(f"   Countries: {stats[1]:,}")
        print(f"   Industries: {stats[2]:,}")
        print(f"   Avg quality score: {stats[3]:.2f} / 9")

        print()
        print("=" * 70)
        print("Next Steps:")
        print("=" * 70)
        print()
        print("1. Load to PostgreSQL:")
        print(f"   poetry run load-parquet {output_file}")
        print()
        print("2. Transform to core schema:")
        print("   poetry run load-core")
        print()
        print("3. (Optional) Generate embeddings:")
        print("   poetry run generate-embeddings")
        print()
        print("4. Build indexes:")
        print("   PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres \\")
        print("     -d profiles -f sql/03_indexes.sql")
        print()
        print("5. Start PostgreSQL API:")
        print("   ./start_api.sh")
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
        print("Common issues:")
        print("  - Network timeout (retry)")
        print("  - Disk full (need ~500 MB free)")
        print("  - AWS credentials expired (rotate)")
        print()
        sys.exit(1)

if __name__ == '__main__':
    main()
