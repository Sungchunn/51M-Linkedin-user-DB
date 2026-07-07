#!/usr/bin/env python3
"""
PROSPECTIQ - Extract BEST 1M Profiles by Quality Score
Sorts by quality_score and takes top 1M for deployment
"""

import sys
from pathlib import Path
import pyarrow.parquet as pq
import pyarrow.compute as pc
from datetime import datetime

def main():
    # Paths
    input_file = Path("data/USA_filtered.parquet")
    output_file = Path("data/USA_1M_best.parquet")

    if not input_file.exists():
        print(f"❌ Input file not found: {input_file}")
        print(f"   Looking for: {input_file.absolute()}")
        sys.exit(1)

    print("=" * 70)
    print("PROSPECTIQ - Extract Top 1M Profiles by Quality Score")
    print("=" * 70)
    print(f"Input:  {input_file}")
    print(f"Output: {output_file}")
    print("")

    # Read parquet file
    print("📖 Reading parquet file...")
    start_time = datetime.now()
    table = pq.read_table(input_file)
    total_rows = len(table)
    read_time = (datetime.now() - start_time).total_seconds()

    print(f"✅ Loaded {total_rows:,} rows in {read_time:.1f}s")
    print("")

    # Check if quality_score column exists
    if 'quality_score' not in table.column_names:
        print("⚠️  Warning: quality_score column not found")
        print("   Available columns:", ", ".join(table.column_names))
        print("   Falling back to first 1M rows...")
        subset_table = table.slice(0, min(1_000_000, total_rows))
    else:
        # Sort by quality_score descending
        print("📊 Sorting by quality_score (highest first)...")
        start_time = datetime.now()

        # Get quality scores and sort indices
        quality_scores = table.column('quality_score')
        sorted_indices = pc.sort_indices(table, sort_keys=[("quality_score", "descending")])

        # Take top 1M
        rows_to_extract = min(1_000_000, total_rows)
        top_indices = sorted_indices.slice(0, rows_to_extract)
        subset_table = pc.take(table, top_indices)

        sort_time = (datetime.now() - start_time).total_seconds()
        print(f"✅ Sorted and extracted top {rows_to_extract:,} profiles in {sort_time:.1f}s")

        # Show quality score stats
        subset_scores = subset_table.column('quality_score')
        min_score = pc.min(subset_scores).as_py()
        max_score = pc.max(subset_scores).as_py()
        avg_score = pc.mean(subset_scores).as_py()

        print("")
        print("📈 Quality Score Statistics (Top 1M):")
        print(f"   Minimum: {min_score:.2f}")
        print(f"   Maximum: {max_score:.2f}")
        print(f"   Average: {avg_score:.2f}")

    print("")

    # Write to new file
    print(f"💾 Writing {len(subset_table):,} rows to {output_file}...")
    start_time = datetime.now()
    pq.write_table(subset_table, output_file, compression='snappy')
    write_time = (datetime.now() - start_time).total_seconds()

    print(f"✅ Written in {write_time:.1f}s")

    # Get file sizes
    input_size_mb = input_file.stat().st_size / (1024 * 1024)
    output_size_mb = output_file.stat().st_size / (1024 * 1024)

    print("")
    print("=" * 70)
    print("✅ EXTRACTION COMPLETE!")
    print("=" * 70)
    print(f"Input:  {input_size_mb:,.1f} MB ({total_rows:,} rows)")
    print(f"Output: {output_size_mb:,.1f} MB ({len(subset_table):,} rows)")
    print(f"Ratio:  {output_size_mb/input_size_mb*100:.1f}% of original size")
    print("")
    print("🚀 Ready to deploy! Next steps:")
    print("   1. Load locally to test:")
    print(f"      poetry run python -m backend.data_pipeline.ingestion.load_incremental {output_file}")
    print("")
    print("   2. Deploy to Render:")
    print("      - Upload to S3 or Render storage")
    print("      - Run load command in Render Shell")
    print("")


if __name__ == '__main__':
    main()
