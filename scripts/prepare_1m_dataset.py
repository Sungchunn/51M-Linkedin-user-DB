#!/usr/bin/env python3
"""
INSIGHT - Extract 1M Row Test Dataset
Creates a 1M row Parquet file from the full dataset for testing
"""

import os
import sys
from pathlib import Path
import pyarrow.parquet as pf

def main():
    # Paths
    input_file = Path("data/USA_filtered.parquet")
    output_file = Path("data/USA_1M_test.parquet")

    if not input_file.exists():
        print(f"❌ Input file not found: {input_file}")
        sys.exit(1)

    print("=" * 60)
    print("INSIGHT - Extracting 1M Row Test Dataset")
    print("=" * 60)
    print(f"Input:  {input_file}")
    print(f"Output: {output_file}")
    print("")

    # Read first 1M rows
    print("Reading first 1,000,000 rows from Parquet...")
    parquet_table = pf.read_table(input_file)
    total_rows = len(parquet_table)

    print(f"Total rows in file: {total_rows:,}")

    if total_rows < 1_000_000:
        print(f"⚠️  File has less than 1M rows, extracting all {total_rows:,} rows")
        rows_to_extract = total_rows
    else:
        rows_to_extract = 1_000_000

    # Extract subset
    subset_table = parquet_table.slice(0, rows_to_extract)

    # Write to new file
    print(f"Writing {rows_to_extract:,} rows to {output_file}...")
    pf.write_table(subset_table, output_file, compression='snappy')

    # Get file sizes
    input_size_mb = input_file.stat().st_size / (1024 * 1024)
    output_size_mb = output_file.stat().st_size / (1024 * 1024)

    print("")
    print("✅ Dataset extraction complete!")
    print(f"   Input:  {input_size_mb:,.1f} MB ({total_rows:,} rows)")
    print(f"   Output: {output_size_mb:,.1f} MB ({rows_to_extract:,} rows)")
    print(f"   Ratio:  {output_size_mb/input_size_mb*100:.1f}% of original size")
    print("")
    print("Ready to load with:")
    print(f"  python -m backend.data_pipeline.ingestion.load_incremental {output_file}")


if __name__ == '__main__':
    main()
