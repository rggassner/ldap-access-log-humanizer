#!/bin/bash

# Exit on error
set -e

# Check for test name
if [ -z "$1" ]; then
    echo "Usage: $0 <test_name>"
    exit 1
fi

TEST_NAME="$1"
SRC_LOG="../logs/mylogtest.log"
SCRIPT="./humanizer.py"
LINE_COUNTS=(1 10 100 1000 10000 100000 200000 300000 400000)

# Ensure output directory exists
OUT_DIR="../humanized/${TEST_NAME}"
mkdir -p "$OUT_DIR"

# Loop through each test size
for COUNT in "${LINE_COUNTS[@]}"; do
    echo "Running with $COUNT lines..."

    TEMP_INPUT="/tmp/temp_input_${TEST_NAME}_${COUNT}.log"
    OUTPUT_FILE="${OUT_DIR}/mylogtest.log.${COUNT}lines"

    # Prepare input file
    head -n "$COUNT" "$SRC_LOG" > "$TEMP_INPUT"

    # Time execution
    START=$(date +%s.%N)
    cat "$TEMP_INPUT" | $SCRIPT \
        --input_type stdin \
        --output_file \
        --output_file_name "$OUTPUT_FILE"
    END=$(date +%s.%N)

    # Compute duration
    DURATION=$(echo "$END - $START" | bc)
    echo "Lines: $COUNT — Duration: $DURATION seconds"
    echo
done

