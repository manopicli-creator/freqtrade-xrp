#!/bin/bash
mkdir -p user_data/data user_data/logs user_data/strategies

# Télécharger les données
freqtrade download-data --pairs XRP/USDT --exchange gateio --timeframe 5m --days 30

# Lance Freqtrade en arrière-plan
freqtrade trade --strategy XRPStrategy &

# Lance Flask
python server.py
