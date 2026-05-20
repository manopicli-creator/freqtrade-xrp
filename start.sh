#!/bin/bash
echo "=== Starting setup ==="
mkdir -p user_data/data user_data/logs user_data/strategies

echo "=== Copying config ==="
cp config.json user_data/config.json 2>/dev/null || echo "config already in place"

echo "=== Downloading data for backtest ==="
freqtrade download-data \
  --exchange binance \
  --pairs BTC/USDT ETH/USDT XRP/USDT SOL/USDT \
    BNB/USDT ADA/USDT DOGE/USDT AVAX/USDT \
    LINK/USDT DOT/USDT LTC/USDT BCH/USDT \
    ATOM/USDT UNI/USDT NEAR/USDT APT/USDT \
    SUI/USDT ARB/USDT OP/USDT INJ/USDT \
    PEPE/USDT FET/USDT RENDER/USDT TRX/USDT \
  --timeframes 15m 5m \
  --days 240

echo "=== Running backtest ==="
freqtrade backtesting \
  --strategy XRPStrategy \
  --config user_data/config.json \
  --datadir user_data/data/binance \
  --pairs BTC/USDT ETH/USDT XRP/USDT SOL/USDT \
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
