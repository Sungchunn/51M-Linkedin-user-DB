#!/usr/bin/env python3
"""
Extract test datasets from USA_filtered.parquet
Creates multiple test files of different sizes
"""

import pyarrow.parquet as pq
from pathlib import Path
import sys

parquet_file = Path("/Users/chromatrical/CAREER/Side Projects/WebApplication/data/USA_filtered.parquet")
output_dir = Path("/Users/chromatrical/CAREER/Side Projects/WebApplication/data")

# Test dataset sizes
test_sizes = [5000, 10000]

print("=" * 80)
print("EXTRACTING TEST DATASETS")
print("=" * 80)
print(f"Source: {parquet_file.name}")
print()

# Read metadata
pf = pq.ParquetFile(str(parquet_file))
total_rows = pf.metadata.num_rows

print(f"Total rows available: {total_rows:,}")
print()

for size in test_sizes:
    if size > total_rows:
        print(f"⚠️  Skipping {size:,} rows (exceeds total)")
        continue

    output_file = output_dir / f"test_{size}_rows.parquet"

    print(f"Extracting {size:,} rows...")

    # Read first N rows using streaming
    batch_iterator = pf.iter_batches(batch_size=size)
    first_batch = next(batch_iterator)
    df = first_batch.to_pandas()

    # Save to parquet
    df.to_parquet(output_file, engine='pyarrow', index=False)

    file_size_kb = output_file.stat().st_size / 1024
    file_size_mb = file_size_kb / 1024

    print(f"  ✅ Created: {output_file.name}")
    print(f"     Size: {file_size_mb:.2f} MB")
    print(f"     Rows: {len(df):,}")
    print()

print("=" * 80)
print("✅ EXTRACTION COMPLETE")
print("=" * 80)
print()
print("Available test files:")
print("  - test_500_rows.parquet (already exists)")
print("  - test_5000_rows.parquet")
print("  - test_10000_rows.parquet")
print()
print("To test with 10K rows:")
print('  ./scripts/test_pipeline_10k.sh')
