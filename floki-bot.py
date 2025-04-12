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

PUSHOVER_USER_KEY = "your-user-key"
PUSHOVER_API_TOKEN = "your-app-token"
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
        "price": price,
        "amount": floki_amount,
        "euro": EURO_PER_TRADE
    }
    log_trade(trade)
    print(f"[BUY] €{EURO_PER_TRADE:.2f} of FLOKI at ${price:.8f}")
    send_push("FLOKI BOT – BUY", f"Bought €{EURO_PER_TRADE:.2f} at ${price:.8f}")

def simulate_sell(price):
    global portfolio, total_profit
    proceeds = portfolio["balance"] * price
    profit = proceeds - (EURO_PER_TRADE * len(portfolio["holdings"]))
    total_profit += profit

    trade = {
        "type": "SELL",
        "timestamp": datetime.now().isoformat(),
        "price": price,
        "amount": portfolio["balance"],
        "proceeds": proceeds,
        "profit": profit,
        "total_profit": total_profit
    }
    log_trade(trade)

    print(f"[SELL] {portfolio['balance']:.2f} FLOKI at ${price:.8f} → €{proceeds:.2f} (profit: €{profit:.2f})")
    print(f"💰 Total simulated profit: €{total_profit:.2f}")
    send_push("FLOKI BOT – SELL", f"Sold {portfolio['balance']:.2f} FLOKI at ${price:.8f}\nProfit: €{profit:.2f}")

    portfolio["holdings"].clear()
    portfolio["balance"] = 0
    portfolio["average_price"] = 0
    portfolio["last_buy_price"] = None

# --- Main Loop ---
def bot_loop():
    while True:
        price = get_floki_price()
        if price is None:
            time.sleep(CHECK_INTERVAL)
            continue

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Price: ${price:.8f}")

        if portfolio["last_buy_price"] is None:
            simulate_buy(price)
        else:
            drop = (portfolio["last_buy_price"] - price) / portfolio["last_buy_price"]
            rise = (price - portfolio["average_price"]) / portfolio["average_price"] if portfolio["average_price"] else 0

            if drop >= BUY_THRESHOLD:
                simulate_buy(price)

            if rise >= SELL_THRESHOLD:
                simulate_sell(price)

        time.sleep(CHECK_INTERVAL)

# --- Start Flask + Bot ---
if __name__ == "__main__":
    threading.Thread(target=start_server).start()
    bot_loop()
