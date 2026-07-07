#!/usr/bin/env python3
"""
PROSPECTIQ - Extract BEST 10M Profiles by Quality Score
Sorts by quality_score and takes top 10M for production deployment
"""

import sys
from pathlib import Path
import pyarrow.parquet as pq
import pyarrow.compute as pc
from datetime import datetime

def main():
    # Paths
    input_file = Path("data/USA_filtered.parquet")
    output_file = Path("data/USA_10M_best.parquet")

    if not input_file.exists():
        print(f"❌ Input file not found: {input_file}")
        print(f"   Looking for: {input_file.absolute()}")
        sys.exit(1)

    print("=" * 70)
    print("PROSPECTIQ - Extract Top 10M Profiles by Quality Score")
    print("=" * 70)
    print(f"Input:  {input_file}")
    print(f"Output: {output_file}")
    print("")

    # Read parquet file
    print("📖 Reading parquet file (this may take a few minutes for 15GB file)...")
    start_time = datetime.now()
    table = pq.read_table(input_file)
    total_rows = len(table)
    read_time = (datetime.now() - start_time).total_seconds()

    print(f"✅ Loaded {total_rows:,} rows in {read_time:.1f}s")
    print(f"   File size: {input_file.stat().st_size / (1024**3):.2f} GB")
    print("")

    # Check if quality_score column exists
    if 'quality_score' not in table.column_names:
        print("⚠️  Warning: quality_score column not found")
        print("   Available columns:", ", ".join(table.column_names[:10]), "...")
        print("   Falling back to first 10M rows...")
        subset_table = table.slice(0, min(10_000_000, total_rows))
    else:
        # Sort by quality_score descending
        print("📊 Sorting 96M rows by quality_score (this will take 5-10 minutes)...")
        start_time = datetime.now()

        # Sort and get indices
        sorted_indices = pc.sort_indices(table, sort_keys=[("quality_score", "descending")])

        # Take top 10M
        rows_to_extract = min(10_000_000, total_rows)
        print(f"   Taking top {rows_to_extract:,} profiles...")
        top_indices = sorted_indices.slice(0, rows_to_extract)
        subset_table = pc.take(table, top_indices)

        sort_time = (datetime.now() - start_time).total_seconds()
        print(f"✅ Sorted and extracted top {rows_to_extract:,} profiles in {sort_time:.1f}s ({sort_time/60:.1f} minutes)")

        # Show quality score stats
        subset_scores = subset_table.column('quality_score')
        min_score = pc.min(subset_scores).as_py()
        max_score = pc.max(subset_scores).as_py()
        avg_score = pc.mean(subset_scores).as_py()
        median_score = pc.quantile(subset_scores, q=0.5).as_py()

        print("")
        print("📈 Quality Score Statistics (Top 10M):")
        print(f"   Minimum: {min_score:.2f}")
        print(f"   Median:  {median_score:.2f}")
        print(f"   Average: {avg_score:.2f}")
        print(f"   Maximum: {max_score:.2f}")
        print("")
        print(f"   These are the top {rows_to_extract/total_rows*100:.1f}% highest quality profiles")

    print("")

    # Write to new file
    print(f"💾 Writing {len(subset_table):,} rows to {output_file}...")
    print("   (This may take 2-3 minutes)...")
    start_time = datetime.now()
    pq.write_table(subset_table, output_file, compression='snappy')
    write_time = (datetime.now() - start_time).total_seconds()

    print(f"✅ Written in {write_time:.1f}s ({write_time/60:.1f} minutes)")

    # Get file sizes
    input_size_gb = input_file.stat().st_size / (1024**3)
    output_size_gb = output_file.stat().st_size / (1024**3)

    print("")
    print("=" * 70)
    print("✅ EXTRACTION COMPLETE!")
    print("=" * 70)
    print(f"Input:  {input_size_gb:.2f} GB ({total_rows:,} rows)")
    print(f"Output: {output_size_gb:.2f} GB ({len(subset_table):,} rows)")
    print(f"Ratio:  {output_size_gb/input_size_gb*100:.1f}% of original size")
    print("")
    print("🚀 Next Steps for Production Deployment:")
    print("")
    print("   1. Test locally (optional):")
    print(f"      poetry run python -m backend.data_pipeline.ingestion.load_incremental {output_file}")
    print("")
    print("   2. Upload to cloud storage:")
    print("      aws s3 cp data/USA_10M_best.parquet s3://your-bucket/")
    print("")
    print("   3. Load on Render/AWS:")
    print("      - Use Render Shell or SSH")
    print("      - Download from S3")
    print("      - Run incremental loader")
    print("")
    print("   4. Estimated load time: 30-45 minutes")
    print("")


if __name__ == '__main__':
    main()
