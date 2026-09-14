import json
import urllib.request

SYMBOL = "XBTUSDT"
INTERVAL = 15

SHORT_EMA = 9
LONG_EMA = 21


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

    pair_key = [key for key in result.keys() if key != "last"][0]

    # Closing prices
    prices = [float(candle[4]) for candle in result[pair_key]]

    return prices[-100:]


def calculate_ema(prices, period):
    multiplier = 2 / (period + 1)

    ema = prices[0]

    for price in prices[1:]:
        ema = ((price - ema) * multiplier) + ema

    return ema


def check_signal(prices):
    short_ema = calculate_ema(prices, SHORT_EMA)
    long_ema = calculate_ema(prices, LONG_EMA)

    if short_ema > long_ema:
        signal = "BUY"
    elif short_ema < long_ema:
        signal = "SELL"
    else:
        signal = "HOLD"

    return short_ema, long_ema, signal


def paper_trade():
    prices = get_candles()

    price = prices[-1]

    short_ema, long_ema, signal = check_signal(prices)

    print("\n==============================")
    print("BTCUSDT PAPER TRADING BOT")
    print("==============================")
    print(f"BTC Price: ${price:,.2f}")
    print(f"EMA {SHORT_EMA}: ${short_ema:,.2f}")
    print(f"EMA {LONG_EMA}: ${long_ema:,.2f}")
    print(f"Signal: {signal}")
    print("Mode: PAPER TRADING")
    print("REAL MONEY: DISABLED")
    print("==============================")


try:
    paper_trade()

except Exception as e:
    print("\nBOT ERROR:")
    print(str(e))
    raise
