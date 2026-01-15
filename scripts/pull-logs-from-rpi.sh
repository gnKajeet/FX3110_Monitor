#!/bin/bash
# Pull log files from Raspberry Pi to local machine

# Configuration
RPI_HOST="inseego@192.168.86.38"
RPI_LOG_DIR="~/FX3110_Monitor/logs"
LOCAL_LOG_DIR="./logs_from_rpi"

# Create local directory if it doesn't exist
mkdir -p "$LOCAL_LOG_DIR"

# Get timestamp for backup
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "Pulling logs from Rpi ($RPI_HOST)..."

# Copy the main log file
echo "  - Copying fx3110_log.tsv..."
scp "${RPI_HOST}:${RPI_LOG_DIR}/fx3110_log.tsv" "${LOCAL_LOG_DIR}/fx3110_log.tsv"

# Create a timestamped backup
if [ -f "${LOCAL_LOG_DIR}/fx3110_log.tsv" ]; then
    cp "${LOCAL_LOG_DIR}/fx3110_log.tsv" "${LOCAL_LOG_DIR}/fx3110_log_${TIMESTAMP}.tsv"
    echo "  - Backup saved as fx3110_log_${TIMESTAMP}.tsv"
fi

# Show file info
if [ -f "${LOCAL_LOG_DIR}/fx3110_log.tsv" ]; then
    LINES=$(wc -l < "${LOCAL_LOG_DIR}/fx3110_log.tsv")
    SIZE=$(du -h "${LOCAL_LOG_DIR}/fx3110_log.tsv" | cut -f1)
    echo ""
    echo "Download complete!"
    echo "  File: ${LOCAL_LOG_DIR}/fx3110_log.tsv"
    echo "  Size: ${SIZE}"
    echo "  Lines: ${LINES}"
else
    echo "Error: Failed to download log file"
    exit 1
fi
