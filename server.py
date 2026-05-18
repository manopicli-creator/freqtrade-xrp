from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import re
import requests

app = Flask(__name__)
CORS(app)

STRATEGY_FILE = "user_data/strategies/XRPStrategy.py"
FREQTRADE_URL = "http://127.0.0.1:8080"

@app.route('/api/v1/<path:path>', methods=['GET', 'POST', 'DELETE'])
def proxy(path):
    url = f"{FREQTRADE_URL}/api/v1/{path}"
    resp = requests.request(
        method=request.method,
        url=url,
        headers={k: v for k, v in request.headers if k != 'Host'},
        json=request.get_json(silent=True),
        params=request.args
    )
    return Response(resp.content, status=resp.status_code, content_type=resp.headers.get('Content-Type'))

@app.route('/update_strategy', methods=['POST'])
def update_strategy():
    data = request.json
    rsi_entry = float(data.get('rsi_entry', 55))
    rsi_exit = float(data.get('rsi_exit', 72))
    stoploss = abs(float(data.get('stoploss', 3))) / 100
    roi = abs(float(data.get('roi', 1))) / 100

    with open(STRATEGY_FILE, 'r') as f:
        content = f.read()

    content = re.sub(r'stoploss = -[\d.]+', f'stoploss = -{stoploss}', content)
    content = re.sub(r"'0': [\d.]+", f"'0': {roi}", content)

    with open(STRATEGY_FILE, 'w') as f:
        f.write(content)

    return jsonify({"status": "success", "message": f"Strategy updated! RSI entry={rsi_entry}, RSI exit={rsi_exit}, stoploss=-{stoploss}, ROI={roi}"})

if __name__ == '__main__':
    app.run(port=5000)