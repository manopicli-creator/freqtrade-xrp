#!/bin/bash
echo "=== Starting setup ==="
mkdir -p user_data/data user_data/logs user_data/strategies

echo "=== Copying config ==="
cp config.json user_data/config.json 2>/dev/null || echo "config already in place"

echo "=== Installing hyperopt dependencies ==="
pip install filelock scikit-learn joblib progressbar2 optuna --quiet

echo "=== Starting Flask first ==="
python server.py &
FLASKPID=$!
echo "Flask PID: $FLASKPID"

echo "=== Downloading data for backtest ==="
freqtrade download-data \
  --exchange bybit \
  --pairs BTC/USDT ETH/USDT XRP/USDT SOL/USDT \
    DOGE/USDT ADA/USDT TRX/USDT AVAX/USDT LINK/USDT \
    DOT/USDT SUI/USDT BCH/USDT LTC/USDT \
    NEAR/USDT APT/USDT UNI/USDT PEPE/USDT OP/USDT \
  --timeframes 15m 5m 1h \
  --days 240

echo "=== Removing old hyperopt params ==="
rm -f user_data/strategies/XRPStrategy.json

echo "=== Creating hyperopt config ==="
cat > user_data/config_hyperopt.json << 'EOF'
{
  "pairlists": [{"method": "StaticPairList"}],
  "stake_amount": 100
}
EOF

echo "=== Running Hyperopt ==="
freqtrade hyperopt \
  --strategy XRPStrategy \
  --config user_data/config.json \
  --config user_data/config_hyperopt.json \
  --datadir user_data/data/bybit \
  --hyperopt-loss ProfitDrawDownHyperOptLoss \
  --spaces buy roi stoploss \
  --epochs 200 \
  --job-workers 1 \
  --timerange 20251001-20260520 \
  --pairs BTC/USDT ETH/USDT XRP/USDT SOL/USDT \
    DOGE/USDT ADA/USDT TRX/USDT \
  || echo "Hyperopt failed, continuing anyway..."

echo "=== Starting Freqtrade ==="
freqtrade trade \
  --strategy XRPStrategy \
  --config user_data/config.json \
  --logfile user_data/logs/freqtrade.log &
FTPID=$!
echo "Freqtrade PID: $FTPID"

echo "=== Waiting for Freqtrade API ==="
sleep 30

echo "=== All systems running ==="
wait $FLASKPID
