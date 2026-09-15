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

STRATEGIES = [
    ("EMA 9/21", 9, 21),
    ("EMA 12/26", 12, 26),
    ("EMA 20/50", 20, 50),
    ("EMA 20/100", 20, 100),
    ("EMA 50/200", 50, 200),
]


def get_historical_candles():
    candles = []

    for year, month in MONTHS:
        month_text = f"{month:02d}"

        url = (
            "https://data.binance.vision/data/spot/monthly/"
            f"klines/BTCUSDT/15m/"
            f"BTCUSDT-15m-{year}-{month_text}.zip"
        )

        print(f"Downloading {year}-{month_text}...")

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "BTC-Multi-Strategy-Backtest/1.0"
            }
        )

        with urllib.request.urlopen(request, timeout=60) as response:
            zip_data = response.read()

        with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
            csv_name = z.namelist()[0]

            with z.open(csv_name) as file:
                reader = csv.reader(
                    io.TextIOWrapper(
                        file,
                        encoding="utf-8"
                    )
                )

                for row in reader:
                    if not row:
                        continue

                    try:
                        open_price = float(row[1])
                        close_price = float(row[4])
                    except (ValueError, IndexError):
                        continue

                    candles.append({
                        "open": open_price,
                        "close": close_price
                    })

    return candles


def calculate_ema_series(prices, period):
    multiplier = 2 / (period + 1)

    ema_values = [None] * len(prices)

    if len(prices) < period:
        return ema_values

    ema = sum(prices[:period]) / period
    ema_values[period - 1] = ema

    for i in range(period, len(prices)):
        ema = (
            (prices[i] - ema) * multiplier
        ) + ema

        ema_values[i] = ema

    return ema_values


def run_strategy(candles, short_period, long_period):
    closes = [
        candle["close"]
        for candle in candles
    ]

    ema_short = calculate_ema_series(
        closes,
        short_period
    )

    ema_long = calculate_ema_series(
        closes,
        long_period
    )

    balance = START_BALANCE
    btc = 0.0

    trades = 0
    wins = 0
    losses = 0
    total_pnl = 0.0

    peak_value = START_BALANCE
    max_drawdown = 0.0

    for i in range(long_period, len(candles) - 1):

        if (
            ema_short[i - 1] is None
            or ema_long[i - 1] is None
            or ema_short[i] is None
            or ema_long[i] is None
        ):
            continue

        crossed_up = (
            ema_short[i - 1] <= ema_long[i - 1]
            and ema_short[i] > ema_long[i]
        )

        crossed_down = (
            ema_short[i - 1] >= ema_long[i - 1]
            and ema_short[i] < ema_long[i]
        )

        execution_price = candles[i + 1]["open"]

        # BUY at next candle OPEN
        if (
            crossed_up
            and btc == 0
            and balance >= TRADE_AMOUNT
        ):
            fee = TRADE_AMOUNT * FEE_RATE
            amount_after_fee = TRADE_AMOUNT - fee

            btc = (
                amount_after_fee
                / execution_price
            )

            balance -= TRADE_AMOUNT
            trades += 1

        # SELL at next candle OPEN
        elif crossed_down and btc > 0:

            sell_value = btc * execution_price
            fee = sell_value * FEE_RATE
            net_sell_value = sell_value - fee

            pnl = (
                net_sell_value
                - TRADE_AMOUNT
            )

            balance += net_sell_value
            btc = 0.0

            total_pnl += pnl
            trades += 1

            if pnl > 0:
                wins += 1
            else:
                losses += 1

        current_value = (
            balance
            + (btc * execution_price)
        )

        if current_value > peak_value:
            peak_value = current_value

        drawdown = peak_value - current_value

        if drawdown > max_drawdown:
            max_drawdown = drawdown

    # Close any remaining position
    # at the final candle close.
    if btc > 0:

        final_price = candles[-1]["close"]

        sell_value = btc * final_price
        fee = sell_value * FEE_RATE
        net_sell_value = sell_value - fee

        pnl = (
            net_sell_value
            - TRADE_AMOUNT
        )

        balance += net_sell_value
        btc = 0.0

        total_pnl += pnl
        trades += 1

        if pnl > 0:
            wins += 1
        else:
            losses += 1

    final_value = balance

    completed_trades = wins + losses

    if completed_trades > 0:
        win_rate = (
            wins / completed_trades
        ) * 100
    else:
        win_rate = 0.0

    return {
        "final_value": final_value,
        "pnl": total_pnl,
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "drawdown": max_drawdown
    }


def print_result(name, result):
    print(
        f"{name:<14} "
        f"P/L: ${result['pnl']:>8.2f} | "
        f"Value: ${result['final_value']:>8.2f} | "
        f"Win: {result['win_rate']:>6.2f}% | "
        f"DD: ${result['drawdown']:>8.2f}"
    )


def main():
    print("========================================")
    print("BTCUSDT MULTI-STRATEGY BACKTEST")
    print("12 MONTHS: SEP 2025 - AUG 2026")
    print("========================================")

    candles = get_historical_candles()

    print("----------------------------------------")
    print(f"Total candles: {len(candles)}")
    print("----------------------------------------")

    if len(candles) < 300:
        raise RuntimeError(
            "Not enough historical data."
        )

    # First 8 months = training
    split_index = len(candles) * 8 // 12

    train_candles = candles[:split_index]
    validation_candles = candles[split_index:]

    print("")
    print("TRAINING PERIOD: FIRST 8 MONTHS")
    print("----------------------------------------")

    train_results = []

    for name, short_period, long_period in STRATEGIES:

        result = run_strategy(
            train_candles,
            short_period,
            long_period
        )

        train_results.append({
            "name": name,
            "short": short_period,
            "long": long_period,
            "result": result
        })

        print_result(
            name,
            result
        )

    # Select best strategy using
    # training data only.
    best = max(
        train_results,
        key=lambda item: item["result"]["pnl"]
    )

    print("----------------------------------------")
    print(
        f"BEST TRAINING STRATEGY: "
        f"{best['name']}"
    )
    print("----------------------------------------")

    print("")
    print("VALIDATION PERIOD: LAST 4 MONTHS")
    print("----------------------------------------")

    validation_result = run_strategy(
        validation_candles,
        best["short"],
        best["long"]
    )

    print_result(
        best["name"],
        validation_result
    )

    print("----------------------------------------")
    print(
        f"Training P/L:   "
        f"${best['result']['pnl']:.2f}"
    )

    print(
        f"Validation P/L: "
        f"${validation_result['pnl']:.2f}"
    )

    print(
        f"Validation Win: "
        f"{validation_result['win_rate']:.2f}%"
    )

    print(
        f"Validation DD:  "
        f"${validation_result['drawdown']:.2f}"
    )

    print("----------------------------------------")
    print("EXECUTION: NEXT CANDLE OPEN")
    print("FEE: 0.40% PER SIDE")
    print("MODE: HISTORICAL BACKTEST")
    print("REAL MONEY: DISABLED")
    print("========================================")


if __name__ == "__main__":
    main()
