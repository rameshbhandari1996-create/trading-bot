import json
import urllib.request

SYMBOL = "XBTUSDT"
INTERVAL = 15

SHORT_EMA = 9
LONG_EMA = 21

START_BALANCE = 1000.0
TRADE_AMOUNT = 100.0

FEE_RATE = 0.004


def get_candles():
    url = (
        f"https://api.kraken.com/0/public/OHLC"
        f"?pair={SYMBOL}&interval={INTERVAL}"
    )

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "BTC-Backtest-Bot/1.0"}
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        data = json.loads(response.read().decode())

    if data.get("error"):
        raise RuntimeError(data["error"])

    result = data["result"]
    pair_key = [key for key in result if key != "last"][0]

    candles = result[pair_key]

    # Remove the currently forming candle
    candles = candles[:-1]

    return [float(candle[4]) for candle in candles]


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

            # BUY when EMA 9 crosses above EMA 21
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

            # SELL when EMA 9 crosses below EMA 21
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

    # Close any open position at the final price
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

    win_rate = 0.0

    if winning_trades + losing_trades > 0:
        win_rate = (
            winning_trades
            / (winning_trades + losing_trades)
        ) * 100

    return {
        "final_value": final_value,
        "total_pnl": total_pnl,
        "trades": trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": win_rate,
        "max_drawdown": max_drawdown,
        "candles": len(prices)
    }


def main():
    print("\n================================")
    print("BTCUSDT EMA BACKTEST")
    print("================================")

    prices = get_candles()

    if len(prices) < LONG_EMA + 10:
        raise RuntimeError("Not enough candle data for backtest.")

    result = backtest(prices)

    print(f"Candles tested: {result['candles']}")
    print("--------------------------------")
    print(f"Starting Balance: ${START_BALANCE:,.2f}")
    print(f"Final Value:      ${result['final_value']:,.2f}")
    print(f"Total P/L:        ${result['total_pnl']:,.2f}")
    print(f"Trades:           {result['trades']}")
    print(f"Winning Trades:   {result['winning_trades']}")
    print(f"Losing Trades:    {result['losing_trades']}")
    print(f"Win Rate:         {result['win_rate']:.2f}%")
    print(f"Max Drawdown:     ${result['max_drawdown']:,.2f}")
    print("--------------------------------")
    print("MODE: BACKTEST")
    print("REAL MONEY: DISABLED")
    print("================================")


if __name__ == "__main__":
    main()
