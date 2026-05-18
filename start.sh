#!/bin/bash
# Lance Freqtrade en arrière-plan
freqtrade trade --strategy XRPStrategy --logfile /app/user_data/logs/freqtrade.log &

# Lance Flask
python server.py