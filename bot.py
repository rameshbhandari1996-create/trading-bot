import json
import time
from urllib.request import urlopen

SYMBOL = "BTCUSDT"
INTERVAL = "15m"

SHORT_EMA = 9
LONG_EMA = 21

START_BALANCE = 1000.0
TRADE_AMOUNT = 100.0

balance = START_BALANCE
position = None
entry_price = 0.0


def get_price():
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={SYMBOL}"

    with urlopen(url) as response:
        data = json.loads(response.read().decode())

    return float(data["price"])


def get_candles():
    url = (
        "https://api.binance.com/api/v3/klines"
        f"?symbol={SYMBOL}&interval={INTERVAL}&limit=100"
    )

    with urlopen(url) as response:
        data = json.loads(response.read().decode())

    return [float(candle[4]) for candle in data]


def calculate_ema(prices, period):
    multiplier = 2 / (period + 1)

    ema = prices[0]

    for price in prices[1:]:
        ema = (price - ema) * multiplier + ema

    return ema


def check_signal():
    prices = get_candles()

    short_ema = calculate_ema(prices[-SHORT_EMA * 3:], SHORT_EMA)
    long_ema = calculate_ema(prices[-LONG_EMA * 3:], LONG_EMA)

    print(f"Short EMA: {short_ema:.2f}")
    print(f"Long EMA:  {long_ema:.2f}")

    if short_ema > long_ema:
        return "BUY"

    if short_ema < long_ema:
        return "SELL"

    return "HOLD"


def paper_trade():
    global balance
    global position
    global entry_price

    price = get_price()
    signal = check_signal()

    print("\n----------------------------")
    print(f"BTC Price: ${price:.2f}")
    print(f"Signal: {signal}")
    print(f"Balance: ${balance:.2f}")
    print(f"Position: {position}")

    if signal == "BUY" and position is None:

        position = "LONG"
        entry_price = price

        print(f"🟢 PAPER BUY at ${price:.2f}")

    elif signal == "SELL" and position == "LONG":

        profit_percent = (
            (price - entry_price) / entry_price
        ) * 100

        profit = TRADE_AMOUNT * profit_percent / 100

        balance += profit

        print(f"🔴 PAPER SELL at ${price:.2f}")
        print(f"Profit/Loss: ${profit:.2f}")

        position = None
        entry_price = 0.0

    else:
        print("⏳ No trade")


print("================================")
print("BTCUSDT AUTOMATED PAPER TRADING BOT")
print("Strategy: EMA 9 / EMA 21")
print("Timeframe: 15 minutes")
print("REAL MONEY: DISABLED")
print("================================")


while True:

    try:
        paper_trade()

    except Exception as error:
        print("Error:", error)

    print("\nWaiting 15 minutes...\n")

    time.sleep(900)
