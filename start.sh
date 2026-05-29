#!/bin/bash
echo "=== Starting setup ==="
mkdir -p user_data/data user_data/logs user_data/strategies
echo "=== Copying config ==="
cp config.json user_data/config.json 2>/dev/null || echo "config already in place"
echo "=== Installing hyperopt dependencies ==="
pip install filelock scikit-learn joblib progressbar2 optuna flask flask-cors requests --quiet
echo "=== Downloading data (30 days only) ==="
freqtrade download-data \
  --exchange kucoin \
  --pairs BTC/USDT ETH/USDT XRP/USDT SOL/USDT \
    DOGE/USDT ADA/USDT TRX/USDT AVAX/USDT LINK/USDT \
    DOT/USDT SUI/USDT BCH/USDT LTC/USDT \
    NEAR/USDT APT/USDT UNI/USDT PEPE/USDT OP/USDT \
  --timeframes 15m 5m 1h \
  --days 30
echo "=== Removing old database ==="
rm -f /app/tradesv3.dryrun.sqlite
rm -f /app/user_data/tradesv3.dryrun.sqlite
rm -f tradesv3.dryrun.sqlite
find /app -name "*.sqlite" -delete 2>/dev/null
find /app -name "*.sqlite-wal" -delete 2>/dev/null
find /app -name "*.sqlite-shm" -delete 2>/dev/null
echo "=== Starting Freqtrade ==="
freqtrade trade \
  --strategy XRPStrategy \
  --config user_data/config.json \
  --logfile user_data/logs/freqtrade.log &
FTPID=$!
echo "Freqtrade PID: $FTPID"
echo "=== Waiting for Freqtrade to be ready ==="
for i in $(seq 1 60); do
    if curl -s http://localhost:8081/api/v1/ping > /dev/null 2>&1; then
        echo "Freqtrade ready after ${i} attempts!"
        break
    fi
    echo "Attempt $i/60 - waiting..."
    sleep 3
done
echo "=== Starting Flask ==="
python server.py
