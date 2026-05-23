from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import re
import requests
import os
import time
import threading

app = Flask(__name__)
CORS(app, origins="*", supports_credentials=True)

STRATEGY_FILE = "user_data/strategies/XRPStrategy.py"
FREQTRADE_URL = os.environ.get('FREQTRADE_URL', 'http://localhost:8081')
FT_USERNAME = "mano"
FT_PASSWORD = "Freqtrade2026"

def get_auth_headers():
    return {}

@app.route('/')
def index():
    return '''
    <html><body style="background:#1a1a2e;color:white;font-family:Arial;text-align:center;padding:50px">
    <h1>🤖 Freqtrade XRP Bot</h1>
    <p>Bot status: <b style="color:#00ff88">RUNNING</b></p>
    <a href="/api/v1/ping" style="color:#00aaff">API Ping</a> |
    <a href="/debug/token" style="color:#00aaff">Debug Token</a> |
    <a href="/debug/login" style="color:#00aaff">Debug Login</a>
    </body></html>
    '''

@app.route('/debug/token')
def debug_token():
    return jsonify({
        "auth_mode": "no-api-auth",
        "freqtrade_url": FREQTRADE_URL
    })

@app.route('/debug/login')
def debug_login():
    try:
        resp = requests.get(
            f"{FREQTRADE_URL}/api/v1/ping",
            timeout=5
        )
        return jsonify({
            "status_code": resp.status_code,
            "response": resp.json()
        })
    except Exception as e:
        return jsonify({"error": str(e), "type": type(e).__name__})

@app.route('/api/v1/<path:path>', methods=['GET', 'POST', 'DELETE', 'PUT', 'PATCH', 'OPTIONS'])
def proxy(path):
    if request.method == 'OPTIONS':
        return Response(status=200)

    url = f"{FREQTRADE_URL}/api/v1/{path}"
    headers = {'Content-Type': 'application/json'}

    resp = requests.request(
        method=request.method,
        url=url,
        headers=headers,
        json=request.get_json(silent=True),
        params=request.args,
        timeout=30
    )

    excluded = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
    response_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}
    return Response(resp.content, status=resp.status_code, headers=response_headers)

@app.route('/update_strategy', methods=['POST'])
def update_strategy():
    data = request.json
    rsi_entry = float(data.get('rsi_entry', 38))
    rsi_exit = float(data.get('rsi_exit', 62))
    stoploss = abs(float(data.get('stoploss', 5))) / 100
    roi = abs(float(data.get('roi', 4))) / 100

    with open(STRATEGY_FILE, 'r') as f:
        content = f.read()

    content = re.sub(r'stoploss = -[\d.]+', f'stoploss = -{stoploss}', content)
    content = re.sub(r'"0": [\d.]+', f'"0": {roi}', content)
    content = re.sub(
        r'buy_rsi_min = IntParameter\(30, 50, default=\d+',
        f'buy_rsi_min = IntParameter(30, 50, default={int(rsi_entry)}',
        content
    )
    content = re.sub(
        r'buy_rsi_max = IntParameter\(50, 70, default=\d+',
        f'buy_rsi_max = IntParameter(50, 70, default={int(rsi_exit)}',
        content
    )

    with open(STRATEGY_FILE, 'w') as f:
        f.write(content)

    try:
        requests.post(
            f"{FREQTRADE_URL}/api/v1/reload_config",
            timeout=10
        )
    except Exception:
        pass

    return jsonify({"status": "success", "message": "Strategy updated and reloaded!"})

if __name__ == '__main__':
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=False)
