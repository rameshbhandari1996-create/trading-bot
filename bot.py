import csv
import io
import urllib.request
import zipfile

START_BALANCE = 1000.0
TRADE_AMOUNT = 100.0
FEE_RATE = 0.004

MONTHS = [
    (2025, 9),
    (2025, 10),
    (2025, 11),
    (2025, 12),
    (2026, 1),
    (2026, 2),
    (2026, 3),
    (2026, 4),
    (2026, 5),
    (2026, 6),
    (2026, 7),
    (2026, 8),
]


def get_historical_candles():
    candles = []

    for year, month in MONTHS:
        ym = f"{year}-{month:02d}"

        url = (
            "https://data.binance.vision/data/spot/monthly/"
            f"klines/BTCUSDT/15m/"
            f"BTCUSDT-15m-{ym}.zip"
        )

        print(f"Downloading {ym}...")

        request = urllib.request.Request(
            url,
            headers={"User-Agent": "BTC-Strategy-Backtest/1.0"},
        )

        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read()

        with zipfile.ZipFile(io.BytesIO(data)) as z:
            with z.open(z.namelist()[0]) as file:
                reader = csv.reader(
                    io.TextIOWrapper(file, encoding="utf-8")
                )

                for row in reader:
                    if len(row) < 6:
                        continue

                    try:
                        candles.append({
                            "open": float(row[1]),
                            "high": float(row[2]),
                            "low": float(row[3]),
                            "close": float(row[4]),
                        })
                    except ValueError:
                        continue

    return candles


def ema_series(values, period):
    result = [None] * len(values)

    if len(values) < period:
        return result

    ema = sum(values[:period]) / period
    result[period - 1] = ema

    multiplier = 2 / (period + 1)

    for i in range(period, len(values)):
        ema = (
            (values[i] - ema) * multiplier
        ) + ema

        result[i] = ema

    return result


def rsi_series(closes, period=14):
    result = [None] * len(closes)

    if len(closes) <= period:
        return result

    gains = []
    losses = []

    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100 - (100 / (1 + rs))

    for i in range(period + 1, len(closes)):
        change = closes[i] - closes[i - 1]

        gain = max(change, 0.0)
        loss = max(-change, 0.0)

        avg_gain = (
            (avg_gain * (period - 1)) + gain
        ) / period

        avg_loss = (
            (avg_loss * (period - 1)) + loss
        ) / period

        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100 - (100 / (1 + rs))

    return result


def atr_series(candles, period=14):
    result = [None] * len(candles)

    if len(candles) <= period:
        return result

    true_ranges = [0.0] * len(candles)

    true_ranges[0] = (
        candles[0]["high"] - candles[0]["low"]
    )

    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        previous_close = candles[i - 1]["close"]

        true_ranges[i] = max(
            high - low,
            abs(high - previous_close),
            abs(low - previous_close),
        )

    atr
