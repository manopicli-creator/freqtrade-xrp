#!/bin/bash
echo "=== Starting setup ==="
mkdir -p user_data/data user_data/logs user_data/strategies

echo "=== Downloading data ==="
freqtrade download-data --pairs XRP/USDT --exchange gateio --timeframe 5m --days 7

echo "=== Starting Freqtrade ==="
freqtrade trade --strategy XRPStrategy --logfile user_data/logs/freqtrade.log &
FTPID=$!
echo "Freqtrade PID: $FTPID"

echo "=== Waiting for Freqtrade to start ==="
sleep 15

echo "=== Starting Flask ==="
python server.py