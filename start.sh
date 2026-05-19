#!/bin/bash
echo "=== Starting setup ==="
mkdir -p user_data/data user_data/logs user_data/strategies

echo "=== Downloading data ==="
freqtrade download-data \
  --pairs XRP/USDT \
  --exchange kraken \
  --timeframe 5m \
  --days 7 || echo "Download failed, continuing anyway..."

echo "=== Starting Freqtrade ==="
freqtrade trade \
  --strategy XRPStrategy \
  --config user_data/config.json \
  --logfile user_data/logs/freqtrade.log &

FTPID=$!
echo "Freqtrade PID: $FTPID"

echo "=== Waiting for Freqtrade to start ==="
sleep 15

echo "=== Starting Flask ==="
python server.py
