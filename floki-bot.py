import json
import time
import threading
import requests
from datetime import datetime
from flask import Flask

# --- CONFIG ---
BUY_THRESHOLD = 0.01     # 1% price drop triggers buy
SELL_THRESHOLD = 0.02    # 2% rise triggers sell
EURO_PER_TRADE = 1
CHECK_INTERVAL = 15      # 15 seconds between checks

PUSHOVER_USER_KEY = "ufz9mrfs1yzzicun13m42ztdx55pd4"
PUSHOVER_API_TOKEN = "a3defywpn6sneh9gc3vfn27eifvfnm"
TRADE_LOG_FILE = "trades.json"

# --- Flask Server for Render ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Floki Bot is alive!"

def start_server():
    app.run(host='0.0.0.0', port=10000)

# --- Bot State ---
portfolio = {
    "holdings": [],
    "balance": 0,
    "average_price": 0,
    "last_buy_price": None
}

total_profit = 0
try:
    with open(TRADE_LOG_FILE, "r") as f:
        trades = json.load(f)
        total_profit = sum(t.get("profit", 0) for t in trades if t["type"] == "SELL")
except FileNotFoundError:
    trades = []

# --- Notification ---
def send_push(title, message):
    try:
        requests.post("https://api.pushover.net/1/messages.json", data={
            "token": PUSHOVER_API_TOKEN,
            "user": PUSHOVER_USER_KEY,
            "title": title,
            "message": message
        })
    except Exception as e:
        print(f"[ERROR] Push failed: {e}")

# --- Price Fetch ---
def get_floki_price():
    try:
        response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=floki&vs_currencies=usd", timeout=10)
        response.raise_for_status()
        return response.json()["floki"]["usd"]
    except Exception as e:
        print(f"[WARN] Could not fetch price: {e}")
        return None

# --- Trade Logger ---
def log_trade(trade):
    trades.append(trade)
    with open(TRADE_LOG_FILE, "w") as f:
        json.dump(trades, f, indent=2)

# --- Trade Logic ---
def simulate_buy(price):
    global portfolio
    floki_amount = EURO_PER_TRADE / price
    portfolio["holdings"].append({"amount": floki_amount, "price": price})
    portfolio["balance"] += floki_amount
    portfolio["last_buy_price"] = price
    total_value = sum(h["amount"] * h["price"] for h in portfolio["holdings"])
    portfolio["average_price"] = total_value / portfolio["balance"]

    trade = {
        "type": "BUY",
        "timestamp": datetime.now().isoformat(),
        "price":
