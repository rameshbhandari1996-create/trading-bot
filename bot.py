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

    atr = sum(true_ranges[1:period + 1]) / period
    result[period] = atr

    for i in range(period + 1, len(candles)):
        atr = (
            (atr * (period - 1)) + true_ranges[i]
        ) / period

        result[i] = atr

    return result


def run_strategy(candles, strategy):
    closes = [candle["close"] for candle in candles]

    ema20 = ema_series(closes, 20)
    ema50 = ema_series(closes, 50)
    ema100 = ema_series(closes, 100)
    ema200 = ema_series(closes, 200)

    rsi = rsi_series(closes, 14)
    atr = atr_series(candles, 14)

    balance = START_BALANCE
    btc = 0.0

    stop_price = 0.0
    target_price = 0.0

    trades = 0
    wins = 0
    losses = 0
    total_pnl = 0.0

    peak_value = START_BALANCE
    max_drawdown = 0.0

    def close_position(price):
        nonlocal balance
        nonlocal btc
        nonlocal stop_price
        nonlocal target_price
        nonlocal trades
        nonlocal wins
        nonlocal losses
        nonlocal total_pnl

        sell_value = btc * price
        fee = sell_value * FEE_RATE
        net_value = sell_value - fee

        pnl = net_value - TRADE_AMOUNT

        balance += net_value
        btc = 0.0

        stop_price = 0.0
        target_price = 0.0

        trades += 1
        total_pnl += pnl

        if pnl > 0:
            wins += 1
        else:
            losses += 1

    for i in range(201, len(candles) - 1):

        if any(
            value is None
            for value in (
                ema20[i],
                ema50[i],
                ema100[i],
                ema200[i],
                rsi[i],
                atr[i],
            )
        ):
            continue

        # Manage open position.
        if btc > 0:

            low = candles[i]["low"]
            high = candles[i]["high"]

            if strategy in (
                "EMA20/50 + RSI + ATR",
                "Donchian50 + EMA200",
            ):

                if low <= stop_price:
                    close_position(stop_price)

                elif high >= target_price:
                    close_position(target_price)

        # Entry signals from completed candle.
        if btc == 0:

            cross20_50 = (
                ema20[i - 1] <= ema50[i - 1]
                and ema20[i] > ema50[i]
            )

            cross50_200 = (
                ema50[i - 1] <= ema200[i - 1]
                and ema50[i] > ema200[i]
            )

            trend_up = ema50[i] > ema200[i]

            recent_high = max(
                closes[i - 50:i]
            )

            breakout = closes[i] > recent_high

            if strategy == "EMA20/50 + RSI":
                buy = (
                    cross20_50
                    and rsi[i] >= 55
                    and trend_up
                )

            elif strategy == "EMA20/100 + RSI":
                buy = (
                    ema20[i] > ema100[i]
                    and cross20_50
                    and rsi[i] >= 55
                )

            elif strategy == "EMA50/200 + RSI":
                buy = (
                    cross50_200
                    and rsi[i] >= 50
                )

            elif strategy == "EMA20/50 + RSI + ATR":
                buy = (
                    cross20_50
                    and rsi[i] >= 55
                    and trend_up
                )

            else:
                buy = (
                    breakout
                    and trend_up
                    and rsi[i] >= 55
                )

            if buy and balance >= TRADE_AMOUNT:

                execution_price = candles[i + 1]["open"]

                fee = TRADE_AMOUNT * FEE_RATE
                amount_after_fee = (
                    TRADE_AMOUNT - fee
                )

                btc = (
                    amount_after_fee
                    / execution_price
                )

                balance -= TRADE_AMOUNT

                if strategy == "EMA20/50 + RSI + ATR":
                    stop_price = (
                        execution_price
                        - (2.0 * atr[i])
                    )

                    target_price = (
                        execution_price
                        + (4.0 * atr[i])
                    )

                elif strategy == "Donchian50 + EMA200":
                    stop_price = (
                        execution_price
                        - (2.5 * atr[i])
                    )

                    target_price = (
                        execution_price
                        + (5.0 * atr[i])
                    )

        # EMA/RSI exit rules.
        if (
            btc > 0
            and strategy not in (
                "EMA20/50 + RSI + ATR",
                "Donchian50 + EMA200",
            )
        ):

            down20_50 = (
                ema20[i - 1] >= ema50[i - 1]
                and ema20[i] < ema50[i]
            )

            down50_200 = (
                ema50[i - 1] >= ema200[i - 1]
                and ema50[i] < ema200[i]
            )

            if strategy == "EMA20/50 + RSI":
                exit_signal = (
                    down20_50
                    or rsi[i] < 45
                )

            elif strategy == "EMA20/100 + RSI":
                exit_signal = (
                    ema20[i] < ema100[i]
                    or rsi[i] < 45
                )

            else:
                exit_signal = (
                    down50_200
                    or rsi[i] < 45
                )

            if exit_signal:
                close_position(
                    candles[i + 1]["open"]
                )

        # ATR strategy trend exit.
        if (
            btc > 0
            and strategy == "EMA20/50 + RSI + ATR"
        ):

            if (
                ema20[i] < ema50[i]
                or rsi[i] < 45
            ):
                close_position(
                    candles[i + 1]["open"]
                )

        # Donchian trend exit.
        if (
            btc > 0
            and strategy == "Donchian50 + EMA200"
        ):

            if closes[i] < ema200[i]:
                close_position(
                    candles[i + 1]["open"]
                )

        # Drawdown calculation.
        current_value = (
            balance
            + (btc * candles[i]["close"])
        )

        peak_value = max(
            peak_value,
            current_value
        )

        drawdown = (
            peak_value - current_value
        )

        max_drawdown = max(
            max_drawdown,
            drawdown
        )

    # Close remaining position.
    if btc > 0:
        close_position(
            candles[-1]["close"]
        )

    completed_trades = wins + losses

    if completed_trades > 0:
        win_rate = (
            wins / completed_trades
        ) * 100
    else:
        win_rate = 0.0

    return {
        "final": balance,
        "pnl": total_pnl,
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "win": win_rate,
        "dd": max_drawdown,
    }


def print_result(name, result):
    print(
        f"{name:<24} "
        f"P/L: ${result['pnl']:>8.2f} | "
        f"Value: ${result['final']:>8.2f} | "
        f"Win: {result['win']:>6.2f}% | "
        f"DD: ${result['dd']:>7.2f}"
    )


def main():
    print("========================================")
    print("BTCUSDT SMART STRATEGY BACKTEST")
    print("12 MONTHS: SEP 2025 - AUG 2026")
    print("========================================")

    candles = get_historical_candles()

    print("----------------------------------------")
    print(f"Total candles: {len(candles)}")
    print("----------------------------------------")

    if len(candles) < 1000:
        raise RuntimeError(
            "Not enough historical data."
        )

    # First 8 months = training.
    split_index = len(candles) * 8 // 12

    training = candles[:split_index]
    validation = candles[split_index:]

    strategies = [
        "EMA20/50 + RSI",
        "EMA20/100 + RSI",
        "EMA50/200 + RSI",
        "EMA20/50 + RSI + ATR",
        "Donchian50 + EMA200",
    ]

    print("")
    print("TRAINING: FIRST 8 MONTHS")
    print("----------------------------------------")

    training_results = []

    for strategy in strategies:

        result = run_strategy(
            training,
            strategy
        )

        training_results.append(
            (strategy, result)
        )

        print_result(
            strategy,
            result
        )

    # Pick best training strategy.
    best_strategy, best_training = max(
        training_results,
        key=lambda item: item[1]["pnl"]
    )

    print("----------------------------------------")
    print(
        f"BEST TRAINING STRATEGY: "
        f"{best_strategy}"
    )
    print("----------------------------------------")

    print("")
    print("VALIDATION: LAST 4 MONTHS")
    print("----------------------------------------")

    validation_result = run_strategy(
        validation,
        best_strategy
    )

    print_result(
        best_strategy,
        validation_result
    )

    print("----------------------------------------")
    print(
        f"Training P/L:   "
        f"${best_training['pnl']:.2f}"
    )

    print(
        f"Validation P/L: "
        f"${validation_result['pnl']:.2f}"
    )

    print(
        f"Validation Win: "
        f"{validation_result['win']:.2f}%"
    )

    print(
        f"Validation DD:  "
        f"${validation_result['dd']:.2f}"
    )

    print("----------------------------------------")
    print("EXECUTION: NEXT CANDLE OPEN")
    print("FEE: 0.40% PER SIDE")
    print("MODE: HISTORICAL BACKTEST")
    print("REAL MONEY: DISABLED")
    print("========================================")


if __name__ == "__main__":
    main()
