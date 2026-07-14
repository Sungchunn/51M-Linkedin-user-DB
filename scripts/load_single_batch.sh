#!/bin/bash
# Load single batch file to test pipeline

BATCH_FILE="/Users/chromatrical/CAREER/Side Projects/51M-Linkedin-user-DB/data/batches/batch_0000.parquet"

echo "Loading: $BATCH_FILE"
echo ""

# Check if file exists
if [ ! -f "$BATCH_FILE" ]; then
    echo "❌ File not found: $BATCH_FILE"
    echo ""
    echo "Available files:"
    ls -lh "/Users/chromatrical/CAREER/Side Projects/51M-Linkedin-user-DB/data/batches/" | head -5
    exit 1
fi

echo "✅ File exists, loading..."
poetry run load-parquet "$BATCH_FILE"
