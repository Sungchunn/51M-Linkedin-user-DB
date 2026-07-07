#!/usr/bin/env python3
"""
Inspect USA_filtered.parquet and extract first 500 rows
"""

import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path

parquet_file = Path("/Users/chromatrical/CAREER/Side Projects/WebApplication/data/USA_filtered.parquet")

print("=" * 80)
print("INSPECTING: USA_filtered.parquet")
print("=" * 80)

# Read metadata
pf = pq.ParquetFile(str(parquet_file))
print(f"Total rows: {pf.metadata.num_rows:,}")
print(f"Total columns: {len(pf.schema)}")
print()

print("Column names:")
print("-" * 80)
for i, field in enumerate(pf.schema, 1):
    print(f"{i:3d}. {field.name}")

print()
print("=" * 80)
print("READING FIRST 500 ROWS (streaming mode)")
print("=" * 80)

# Read ONLY first 500 rows without loading entire file
# Use PyArrow streaming to avoid loading all 15GB
batch_iterator = pf.iter_batches(batch_size=500)
first_batch = next(batch_iterator)
df_head = first_batch.to_pandas()

print(f"Loaded: {len(df_head)} rows")
print()

# Show sample
print("Sample data (first 3 rows):")
print("-" * 80)
print(df_head.head(3).to_string())
print()

# Show data types
print("Column data types:")
print("-" * 80)
print(df_head.dtypes)
print()

# Show null counts
print("Null value counts:")
print("-" * 80)
null_counts = df_head.isnull().sum()
print(null_counts[null_counts > 0])
print()

# Save to smaller Parquet file for testing
output_file = Path("/Users/chromatrical/CAREER/Side Projects/WebApplication/data/test_500_rows.parquet")
df_head.to_parquet(output_file, engine='pyarrow', index=False)

print("=" * 80)
print(f"✅ Saved first 500 rows to: {output_file.name}")
print("=" * 80)
print()
print(f"File size: {output_file.stat().st_size / 1024:.2f} KB")
print()
print("You can now use this file for testing:")
print(f'poetry run load-parquet "{output_file}"')
