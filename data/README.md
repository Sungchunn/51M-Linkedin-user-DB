# Data Directory

This directory contains the raw data files for the INSIGHT project.

## Structure

```text
data/
├── USA_filtered.parquet       # Main dataset (15GB, 51M+ rows)
├── batches/                   # Processing batches (gitignored)
└── analysis_output/           # Analysis results (gitignored)
```

## Files

### USA_filtered.parquet

- **Size**: ~15.15 GB
- **Rows**: 51,352,619
- **Columns**: 62
- **Format**: Apache Parquet (columnar, compressed)
- **Usage**: Source data for the semantic talent search system

## Notes

- All data files are gitignored (too large for version control)
- Place your parquet file here before running the ingestion pipeline
- The file path should be: `./data/USA_filtered.parquet` or configure in `.env`
