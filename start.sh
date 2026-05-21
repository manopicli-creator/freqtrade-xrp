#!/bin/bash
echo "=== Starting setup ==="
mkdir -p user_data/data user_data/logs user_data/strategies

echo "=== Copying config ==="
cp config.json user_data/config.json 2>/dev/null || echo "config already in place"

echo "=== Downloading data for backtest ==="
freqtrade download-data \
  --exchange binance \
  --pairs BTC/USDT ETH/USDT XRP/USDT BNB/USDT SOL/USDT \
    DOGE/USDT ADA/USDT TRX/USDT AVAX/USDT LINK/USDT \
    DOT/USDT SHIB/USDT SUI/USDT BCH/USDT LTC/USDT \
    NEAR/USDT APT/USDT UNI/USDT PEPE/USDT OP/USDT \
  --timeframes 15m 5m 1h \
  --days 240

echo "=== Running backtest ==="
freqtrade backtesting \
  --strategy XRPStrategy \
  --config user_data/config.json \
  --datadir user_data/data/binance \
  --pairs BTC/USDT ETH/USDT XRP/USDT BNB/USDT SOL/USDT \
    DOGE/USDT ADA/USDT TRX/USDT AVAX/USDT LINK/USDT \
    DOT/USDT SHIB/USDT SUI/USDT BCH/USDT LTC/USDT \
    NEAR/USDT APT/USDT UNI/USDT PEPE/USDT OP/USDT \
  --timerange 20251001-20260101 || echo "Backtest failed, continuing anyway..."

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
