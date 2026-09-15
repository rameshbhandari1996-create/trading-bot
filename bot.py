import csv
import io
import urllib.request
import zipfile

SHORT_EMA = 9
LONG_EMA = 21
TREND_EMA = 200

START_BALANCE = 1000.0
TRADE_AMOUNT = 100.0
FEE_RATE = 0.004

MONTHS = [
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
        month_text = f"{month:02d}"

        url = (
            "https://data.binance.vision/data/spot/monthly/"
            f"klines/BTCUSDT/15m/"
            f"BTCUSDT-15m-{year}-{month_text}.zip"
        )

        print(f"Downloading {year}-{month_text}...")

        request = urllib.request.Request(
            url,
            headers={"User-Agent": "BTC-EMA-Trend-Backtest/1.0"}
        )

        with urllib.request.urlopen(request, timeout=60) as response:
            zip_data = response.read()

        with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
            csv_name = z.namelist()[0]

            with z.open(csv_name) as file:
                reader = csv.reader(
                    io.TextIOWrapper(file, encoding="utf-8")
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


def calculate_ema(prices, period):
    multiplier = 2 / (period + 1)
    ema = prices[0]

    for price in prices[1:]:
        ema = ((price - ema) * multiplier) + ema

    return ema


def backtest(candles):
    closes = [candle["close"] for candle in candles]

    balance = START_BALANCE
    btc = 0.0

    trades = 0
    winning_trades = 0
    losing_trades = 0
    total_pnl = 0.0

    max_balance = START_BALANCE
    max_drawdown = 0.0

    previous_ema9 = None
    previous_ema21 = None

    for i in range(TREND_EMA, len(candles) - 1):
        history = closes[:i + 1]

        ema9 = calculate_ema(history, SHORT_EMA)
        ema21 = calculate_ema(history, LONG_EMA)
        ema200 = calculate_ema(history, TREND_EMA)

        current_close = closes[i]

        execution_price = candles[i + 1]["open"]

        if previous_ema9 is not None and previous_ema21 is not None:

            crossed_up = (
                previous_ema9 <= previous_ema21
                and ema9 > ema21
            )

            crossed_down = (
                previous_ema9 >= previous_ema21
                and ema9 < ema21
            )

            # BUY only when the larger trend is bullish
            if (
                crossed_up
                and current_close > ema200
                and btc == 0
                and balance >= TRADE_AMOUNT
            ):
                fee = TRADE_AMOUNT * FEE_RATE
                amount_after_fee = TRADE_AMOUNT - fee

                btc = amount_after_fee / execution_price
                balance -= TRADE_AMOUNT

                trades += 1

            # SELL on bearish crossover OR when price falls below EMA 200
            elif (
                btc > 0
                and (
                    crossed_down
                    or current_close < ema200
                )
            ):
                sell_value = btc * execution_price
                fee = sell_value * FEE_RATE
                net_sell_value = sell_value - fee

                pnl = net_sell_value - TRADE_AMOUNT

                balance += net_sell_value
                btc = 0.0

                total_pnl += pnl
                trades += 1

                if pnl > 0:
                    winning_trades += 1
                else:
                    losing_trades += 1

        current_value = balance + (btc * execution_price)

        if current_value > max_balance:
            max_balance = current_value

        drawdown = max_balance - current_value

        if drawdown > max_drawdown:
            max_drawdown = drawdown

        previous_ema9 = ema9
        previous_ema21 = ema21

    # Close any remaining position at the final candle close
    if btc > 0:
        final_price = candles[-1]["close"]

        sell_value = btc * final_price
        fee = sell_value * FEE_RATE
        net_sell_value = sell_value - fee

        pnl = net_sell_value - TRADE_AMOUNT

        balance += net_sell_value
        btc = 0.0

        total_pnl += pnl
        trades += 1

        if pnl > 0:
            winning_trades += 1
        else:
            losing_trades += 1

    final_value = balance

    completed_trades = winning_trades + losing_trades

    if completed_trades > 0:
        win_rate = (
            winning_trades / completed_trades
        ) * 100
    else:
        win_rate = 0.0

    return {
        "candles": len(candles),
        "final_value": final_value,
        "total_pnl": total_pnl,
        "trades": trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": win_rate,
        "max_drawdown": max_drawdown
    }


def main():
    print("========================================")
    print("BTCUSDT EMA 9/21 + EMA 200 FILTER")
    print("REALISTIC 6 MONTH BACKTEST")
    print("========================================")

    candles = get_historical_candles()

    if len(candles) < TREND_EMA + 10:
        raise RuntimeError("Not enough historical data.")

    result = backtest(candles)

    print("----------------------------------------")
    print(f"Candles tested:   {result['candles']}")
    print(f"Starting Balance: ${START_BALANCE:,.2f}")
    print(f"Final Value:      ${result['final_value']:,.2f}")
    print(f"Total P/L:        ${result['total_pnl']:,.2f}")
    print(f"Trades:           {result['trades']}")
    print(f"Winning Trades:   {result['winning_trades']}")
    print(f"Losing Trades:    {result['losing_trades']}")
    print(f"Win Rate:         {result['win_rate']:.2f}%")
    print(f"Max Drawdown:     ${result['max_drawdown']:,.2f}")
    print("----------------------------------------")
    print("ENTRY: EMA 9/21 CROSS + PRICE > EMA 200")
    print("EXIT: EMA 9/21 CROSS OR PRICE < EMA 200")
    print("EXECUTION: NEXT CANDLE OPEN")
    print("MODE: HISTORICAL BACKTEST")
    print("REAL MONEY: DISABLED")
    print("========================================")


if __name__ == "__main__":
    main()
