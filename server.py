from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import re
import requests
import os
import time
import threading
import base64
import json

app = Flask(__name__)
CORS(app, origins="*", supports_credentials=True)

STRATEGY_FILE = "user_data/strategies/XRPStrategy.py"
STRATEGY_JSON = "user_data/strategies/XRPStrategy.json"
FREQTRADE_URL = os.environ.get('FREQTRADE_URL', 'http://localhost:8081')
FT_USERNAME = "mano"
FT_PASSWORD = "Freqtrade2026"

_jwt_token = None
_jwt_expiry = 0

def get_jwt_token():
    global _jwt_token, _jwt_expiry
    if _jwt_token and time.time() < _jwt_expiry:
        return _jwt_token
    try:
        resp = requests.post(
            f"{FREQTRADE_URL}/api/v1/token/login",
            json={"username": FT_USERNAME, "password": FT_PASSWORD},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            _jwt_token = data.get("access_token")
            _jwt_expiry = time.time() + 250
            return _jwt_token
    except Exception:
        pass
    return None

def get_auth_headers():
    token = get_jwt_token()
    if token:
        return {"Authorization": f"Bearer {token}"}
    credentials = base64.b64encode(f"{FT_USERNAME}:{FT_PASSWORD}".encode()).decode()
    return {"Authorization": f"Basic {credentials}"}

def get_mode_params(level):
    roi = {
        "0": 0.10,
        "480": 0.05,
        "960": 0.02,
        "1440": 0
    }
    if level <= 20:
        return {"adx": 25, "rsi_min": 48, "rsi_max": 53, "stoploss": -0.03, "roi": roi}
    elif level <= 40:
        return {"adx": 22, "rsi_min": 44, "rsi_max": 56, "stoploss": -0.035, "roi": roi}
    elif level <= 60:
        return {"adx": 20, "rsi_min": 40, "rsi_max": 60, "stoploss": -0.04, "roi": roi}
    elif level <= 80:
        return {"adx": 17, "rsi_min": 37, "rsi_max": 63, "stoploss": -0.05, "roi": roi}
    else:
        return {"adx": 10, "rsi_min": 30, "rsi_max": 70, "stoploss": -0.06, "roi": roi}

@app.route('/')
def index():
    return '''
    <html><body style="background:#1a1a2e;color:white;font-family:Arial;text-align:center;padding:50px">
    <h1>🤖 Freqtrade XRP Bot</h1>
    <p>Bot status: <b style="color:#00ff88">RUNNING</b></p>
    <a href="/api/v1/ping" style="color:#00aaff">API Ping</a> |
    <a href="/debug/basic" style="color:#00aaff">Debug Basic</a> |
    <a href="/public/profit" style="color:#00aaff">Public Profit</a>
    </body></html>
    '''

@app.route('/debug/basic')
def debug_basic():
    try:
        resp = requests.get(
            f"{FREQTRADE_URL}/api/v1/status",
            headers=get_auth_headers(),
            timeout=5
        )
        return jsonify({
            "status_code": resp.status_code,
            "response_text": resp.text[:200]
        })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/public/profit')
def public_profit():
    try:
        resp = requests.get(f"{FREQTRADE_URL}/api/v1/profit", headers=get_auth_headers(), timeout=10)
        return Response(resp.content, status=resp.status_code,
                       headers={'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/public/status')
def public_status():
    try:
        resp = requests.get(f"{FREQTRADE_URL}/api/v1/status", headers=get_auth_headers(), timeout=10)
        return Response(resp.content, status=resp.status_code,
                       headers={'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/public/trades')
def public_trades():
    try:
        resp = requests.get(f"{FREQTRADE_URL}/api/v1/trades?limit=20", headers=get_auth_headers(), timeout=10)
        return Response(resp.content, status=resp.status_code,
                       headers={'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/public/balance')
def public_balance():
    try:
        resp = requests.get(f"{FREQTRADE_URL}/api/v1/balance", headers=get_auth_headers(), timeout=10)
        return Response(resp.content, status=resp.status_code,
                       headers={'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/public/mode', methods=['GET'])
def get_mode():
    try:
        if os.path.exists('bot_mode.json'):
            with open('bot_mode.json', 'r') as f:
                return jsonify(json.load(f))
        return jsonify({"level": 50, "label": "Neutre"})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/set_mode', methods=['POST', 'OPTIONS'])
def set_mode():
    if request.method == 'OPTIONS':
        return Response(status=200)
    try:
        data = request.json
        level = int(data.get('level', 50))
        level = max(0, min(100, level))
        params = get_mode_params(level)

        if level <= 20:
            label = "🐻 Bear Market"
        elif level <= 40:
            label = "📉 Prudent"
        elif level <= 60:
            label = "⚖️ Neutre"
        elif level <= 80:
            label = "📈 Optimiste"
        else:
            label = "🚀 Bull Market"

        with open('bot_mode.json', 'w') as f:
            json.dump({"level": level, "label": label}, f)

        strategy_params = {
            "strategy_name": "XRPStrategy",
            "params": {
                "buy": {
                    "buy_rsi_min": params["rsi_min"],
                    "buy_rsi_max": params["rsi_max"],
                    "buy_adx_min": params["adx"]
                },
                "roi": params["roi"],
                "stoploss": {"stoploss": params["stoploss"]},
                "trailing": {
                    "trailing_stop": True,
                    "trailing_stop_positive": 0.01,
                    "trailing_stop_positive_offset": 0.02,
                    "trailing_only_offset_is_reached": True
                },
                "max_open_trades": {"max_open_trades": 5}
            },
            "ft_stratparam_v": 1
        }

        os.makedirs("user_data/strategies", exist_ok=True)
        with open(STRATEGY_JSON, 'w') as f:
            json.dump(strategy_params, f, indent=2)

        try:
            requests.post(f"{FREQTRADE_URL}/api/v1/reload_config", headers=get_auth_headers(), timeout=10)
        except Exception:
            pass

        return jsonify({"status": "success", "level": level, "label": label, "params": params})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/api/v1/<path:path>', methods=['GET', 'POST', 'DELETE', 'PUT', 'PATCH', 'OPTIONS'])
def proxy(path):
    if request.method == 'OPTIONS':
        return Response(status=200)

    url = f"{FREQTRADE_URL}/api/v1/{path}"
    headers = get_auth_headers()
    headers['Content-Type'] = 'application/json'

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
        f'buy_rsi_min = IntParameter(30, 50, default={int(rsi_entry)}', content)
    content = re.sub(
        r'buy_rsi_max = IntParameter\(50, 70, default=\d+',
        f'buy_rsi_max = IntParameter(50, 70, default={int(rsi_exit)}', content)

    with open(STRATEGY_FILE, 'w') as f:
        f.write(content)

    try:
        requests.post(f"{FREQTRADE_URL}/api/v1/reload_config", headers=get_auth_headers(), timeout=10)
    except Exception:
        pass

    return jsonify({"status": "success", "message": "Strategy updated and reloaded!"})

if __name__ == '__main__':
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=False)
