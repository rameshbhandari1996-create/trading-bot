import csv
import io
import urllib.request
import zipfile

SHORT_EMA = 9
LONG_EMA = 21

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


def get_historical_prices():
    prices = []

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
            headers={"User-Agent": "BTC-EMA-Backtest/1.0"}
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

                    # Binance kline format:
                    # 0=open time, 1=open, 2=high, 3=low, 4=close
                    try:
                        close_price = float(row[4])
                    except (ValueError, IndexError):
                        continue

                    prices.append(close_price)

    return prices


def calculate_ema(prices, period):
    multiplier = 2 / (period + 1)
    ema = prices[0]

    for price in prices[1:]:
        ema = ((price - ema) * multiplier) + ema

    return ema


def backtest(prices):
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

    for i in range(LONG_EMA, len(prices)):
        history = prices[:i + 1]

        ema9 = calculate_ema(history, SHORT_EMA)
        ema21 = calculate_ema(history, LONG_EMA)

        price = prices[i]

        if previous_ema9 is not None and previous_ema21 is not None:

            # BUY: EMA 9 crosses above EMA 21
            if (
                previous_ema9 <= previous_ema21
                and ema9 > ema21
                and btc == 0
                and balance >= TRADE_AMOUNT
            ):
                fee = TRADE_AMOUNT * FEE_RATE
                amount_after_fee = TRADE_AMOUNT - fee

                btc = amount_after_fee / price
                balance -= TRADE_AMOUNT

                trades += 1

            # SELL: EMA 9 crosses below EMA 21
            elif (
                previous_ema9 >= previous_ema21
                and ema9 < ema21
                and btc > 0
            ):
                sell_value = btc * price
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

        current_value = balance + (btc * price)

        if current_value > max_balance:
            max_balance = current_value

        drawdown = max_balance - current_value

        if drawdown > max_drawdown:
            max_drawdown = drawdown

        previous_ema9 = ema9
        previous_ema21 = ema21

    # Close open position at final price
    if btc > 0:
        final_price = prices[-1]

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
        "final_value": final_value,
        "total_pnl": total_pnl,
        "trades": trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": win_rate,
        "max_drawdown": max_drawdown,
        "candles": len(prices),
    }


def main():
    print("========================================")
    print("BTCUSDT EMA 9/21 - 6 MONTH BACKTEST")
    print("========================================")

    prices = get_historical_prices()

    if len(prices) < LONG_EMA + 10:
        raise RuntimeError("Not enough historical data.")

    print("----------------------------------------")
    print(f"Total candles: {len(prices)}")
    print("----------------------------------------")

    result = backtest(prices)

    print(f"Starting Balance: ${START_BALANCE:,.2f}")
    print(f"Final Value:      ${result['final_value']:,.2f}")
    print(f"Total P/L:        ${result['total_pnl']:,.2f}")
    print(f"Trades:           {result['trades']}")
    print(f"Winning Trades:   {result['winning_trades']}")
    print(f"Losing Trades:    {result['losing_trades']}")
    print(f"Win Rate:         {result['win_rate']:.2f}%")
    print(f"Max Drawdown:     ${result['max_drawdown']:,.2f}")
    print("----------------------------------------")
    print("MODE: HISTORICAL BACKTEST")
    print("REAL MONEY: DISABLED")
    print("========================================")


if __name__ == "__main__":
    main()
