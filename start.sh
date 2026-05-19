#!/bin/bash
echo "=== Starting setup ==="
mkdir -p user_data/data user_data/logs user_data/strategies

echo "=== Copying config ==="
cp config.json user_data/config.json 2>/dev/null || echo "config already in place"

echo "=== Downloading data for backtest ==="
freqtrade download-data \
  --pairs XRP/USDT \
  --exchange binance \
  --timeframe 15m \
  --days 120 || echo "Download failed, continuing anyway..."

echo "=== Running backtest ==="
freqtrade backtesting \
  --strategy XRPStrategy \
  --config user_data/config.json \
  --datadir user_data/data/binance \
  --timerange 20260101-20260401 || echo "Backtest failed, continuing anyway..."

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
