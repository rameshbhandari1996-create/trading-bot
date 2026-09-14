import json
import os
import urllib.request

SYMBOL = "XBTUSDT"
INTERVAL = 15

SHORT_EMA = 9
LONG_EMA = 21

START_BALANCE = 1000.0
TRADE_AMOUNT = 100.0

STATE_FILE = "paper_state.json"


def get_candles():
    url = (
        f"https://api.kraken.com/0/public/OHLC"
        f"?pair={SYMBOL}&interval={INTERVAL}"
    )

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "BTC-Paper-Trading-Bot/1.0"}
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        data = json.loads(response.read().decode())

    if data.get("error"):
        raise RuntimeError(data["error"])

    result = data["result"]
    pair_key = [key for key in result if key != "last"][0]

    return [float(candle[4]) for candle in result[pair_key]][-100:]


def calculate_ema(prices, period):
    multiplier = 2 / (period + 1)
    ema = prices[0]

    for price in prices[1:]:
        ema = ((price - ema) * multiplier) + ema

    return ema


def load_state():
    if not os.path.exists(STATE_FILE):
        return {
            "balance": START_BALANCE,
            "btc": 0.0,
            "entry_price": 0.0,
            "total_pnl": 0.0,
            "trades": 0
        }

    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def paper_trade():
    prices = get_candles()

    price = prices[-1]

    ema9 = calculate_ema(prices, SHORT_EMA)
    ema21 = calculate_ema(prices, LONG_EMA)

    if ema9 > ema21:
        signal = "BUY"
    elif ema9 < ema21:
        signal = "SELL"
    else:
        signal = "HOLD"

    state = load_state()

    # BUY: open a paper position
    if signal == "BUY" and state["btc"] == 0:
        state["btc"] = TRADE_AMOUNT / price
        state["balance"] -= TRADE_AMOUNT
        state["entry_price"] = price
        state["trades"] += 1
        action = "PAPER BUY"

    # SELL: close paper position
    elif signal == "SELL" and state["btc"] > 0:
        sell_value = state["btc"] * price
        pnl = sell_value - TRADE_AMOUNT

        state["balance"] += sell_value
        state["total_pnl"] += pnl
        state["btc"] = 0.0
        state["entry_price"] = 0.0
        state["trades"] += 1
        action = f"PAPER SELL | P/L: ${pnl:.2f}"

    else:
        action = "NO TRADE"

    save_state(state)

    unrealized = 0.0

    if state["btc"] > 0:
        unrealized = (state["btc"] * price) - TRADE_AMOUNT

    total_value = state["balance"] + (state["btc"] * price)

    print("\n==============================")
    print("BTCUSDT PAPER TRADING BOT")
    print("==============================")
    print(f"BTC Price: ${price:,.2f}")
    print(f"EMA 9:     ${ema9:,.2f}")
    print(f"EMA 21:    ${ema21:,.2f}")
    print(f"Signal:    {signal}")
    print(f"Action:    {action}")
    print("------------------------------")
    print(f"Balance:   ${state['balance']:,.2f}")
    print(f"BTC Held:  {state['btc']:.8f}")
    print(f"Total P/L: ${state['total_pnl']:,.2f}")
    print(f"Open P/L:  ${unrealized:,.2f}")
    print(f"Value:     ${total_value:,.2f}")
    print(f"Trades:    {state['trades']}")
    print("------------------------------")
    print("MODE: PAPER TRADING")
    print("REAL MONEY: DISABLED")
    print("==============================")


paper_trade()
