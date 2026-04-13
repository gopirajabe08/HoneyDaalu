"""
Full system backtest — run our actual strategies on 5 years of real NSE data.
Reports from all institutional roles: Quant, Risk, Operations, Portfolio Manager.
"""
import sys
sys.path.insert(0, ".")
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Top 20 liquid Nifty stocks for backtest
STOCKS = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "BHARTIARTL",
          "ITC", "LT", "AXISBANK", "MARUTI", "SUNPHARMA", "TATAMOTORS", "WIPRO",
          "NTPC", "POWERGRID", "TATASTEEL", "BAJFINANCE", "TITAN", "HCLTECH"]

def supertrend(df, period=10, mult=2.0):
    """Calculate Supertrend indicator."""
    hl2 = (df["High"] + df["Low"]) / 2
    atr = df["High"].sub(df["Low"]).rolling(period).mean()
    upper = hl2 + mult * atr
    lower = hl2 - mult * atr
    st = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=int)
    st.iloc[0] = upper.iloc[0]
    direction.iloc[0] = -1
    for i in range(1, len(df)):
        if df["Close"].iloc[i] > upper.iloc[i-1]:
            direction.iloc[i] = 1
        elif df["Close"].iloc[i] < lower.iloc[i-1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i-1]
        if direction.iloc[i] == 1:
            st.iloc[i] = max(lower.iloc[i], st.iloc[i-1]) if direction.iloc[i-1] == 1 else lower.iloc[i]
        else:
            st.iloc[i] = min(upper.iloc[i], st.iloc[i-1]) if direction.iloc[i-1] == -1 else upper.iloc[i]
    return direction

def calc_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    return 100 - (100 / (1 + gain / loss))

def backtest_stock(symbol, capital_per_trade=10000):
    """Backtest all strategies on a single stock using 15m candles (1 year)."""
    try:
        ticker = yf.Ticker(symbol + ".NS")
        df = ticker.history(period="1y", interval="1d")
        if df is None or len(df) < 100:
            return None

        results = []
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]
        vol_sma = volume.rolling(20).mean()
        rsi = calc_rsi(close)
        ema20 = close.ewm(span=20).mean()
        sma50 = close.rolling(50).mean()
        bb_mid = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        bb_upper = bb_mid + 2 * bb_std
        bb_lower = bb_mid - 2 * bb_std
        st_dir = supertrend(df)
        atr = (high - low).rolling(14).mean()

        for i in range(60, len(df) - 1):
            price = close.iloc[i]
            vol_ratio = volume.iloc[i] / vol_sma.iloc[i] if vol_sma.iloc[i] > 0 else 0
            if vol_ratio < 1.0:  # Volume filter
                continue
            if price < 50 or price > 5000:  # Price filter
                continue

            next_close = close.iloc[i + 1]
            next_high = high.iloc[i + 1]
            next_low = low.iloc[i + 1]
            atr_val = atr.iloc[i]
            sl_dist = atr_val * 2

            # Strategy 1: Supertrend BUY
            if st_dir.iloc[i] == 1 and st_dir.iloc[i-1] == -1:
                entry = price
                sl = entry - sl_dist
                target = entry + sl_dist * 2
                # Check next day
                if next_low <= sl:
                    pnl = sl - entry
                elif next_high >= target:
                    pnl = target - entry
                else:
                    pnl = next_close - entry
                qty = max(1, int(capital_per_trade / entry))
                results.append({"strategy": "supertrend", "side": "BUY", "symbol": symbol,
                               "pnl": pnl * qty, "win": pnl > 0, "entry": entry})

            # Strategy 2: Supertrend SELL
            if st_dir.iloc[i] == -1 and st_dir.iloc[i-1] == 1:
                entry = price
                sl = entry + sl_dist
                target = entry - sl_dist * 2
                if next_high >= sl:
                    pnl = entry - sl
                elif next_low <= target:
                    pnl = entry - target
                else:
                    pnl = entry - next_close
                qty = max(1, int(capital_per_trade / entry))
                results.append({"strategy": "supertrend", "side": "SELL", "symbol": symbol,
                               "pnl": pnl * qty, "win": pnl > 0, "entry": entry})

            # Strategy 3: RSI Divergence BUY (oversold + reversal)
            if rsi.iloc[i] < 35 and rsi.iloc[i] > rsi.iloc[i-1] and close.iloc[i] > close.iloc[i-1]:
                if close.iloc[i] > ema20.iloc[i] or close.iloc[i] < bb_lower.iloc[i] * 1.01:
                    entry = price
                    sl = entry - sl_dist
                    target = entry + sl_dist * 2
                    if next_low <= sl:
                        pnl = sl - entry
                    elif next_high >= target:
                        pnl = target - entry
                    else:
                        pnl = next_close - entry
                    qty = max(1, int(capital_per_trade / entry))
                    results.append({"strategy": "rsi_divergence", "side": "BUY", "symbol": symbol,
                                   "pnl": pnl * qty, "win": pnl > 0, "entry": entry})

            # Strategy 4: BB Contra BUY (touch lower BB + bounce)
            if close.iloc[i] <= bb_lower.iloc[i] * 1.01 and close.iloc[i] > close.iloc[i-1]:
                entry = price
                sl = entry - sl_dist
                target = bb_mid.iloc[i]  # Target = middle band
                if next_low <= sl:
                    pnl = sl - entry
                elif next_high >= target:
                    pnl = target - entry
                else:
                    pnl = next_close - entry
                qty = max(1, int(capital_per_trade / entry))
                results.append({"strategy": "bb_contra", "side": "BUY", "symbol": symbol,
                               "pnl": pnl * qty, "win": pnl > 0, "entry": entry})

            # Strategy 5: BB Contra SELL (touch upper BB + rejection)
            if close.iloc[i] >= bb_upper.iloc[i] * 0.99 and close.iloc[i] < close.iloc[i-1]:
                entry = price
                sl = entry + sl_dist
                target = bb_mid.iloc[i]
                if next_high >= sl:
                    pnl = entry - sl
                elif next_low <= target:
                    pnl = entry - target
                else:
                    pnl = entry - next_close
                qty = max(1, int(capital_per_trade / entry))
                results.append({"strategy": "bb_contra", "side": "SELL", "symbol": symbol,
                               "pnl": pnl * qty, "win": pnl > 0, "entry": entry})

        return results
    except Exception as e:
        return None

# Run backtest
print("=" * 60)
print("FULL SYSTEM BACKTEST — 20 Nifty Stocks × 1 Year Daily")
print("=" * 60)

all_trades = []
for stock in STOCKS:
    trades = backtest_stock(stock)
    if trades:
        all_trades.extend(trades)
        wins = sum(1 for t in trades if t["win"])
        total_pnl = sum(t["pnl"] for t in trades)
        print(f"  {stock:15s} | {len(trades):3d} trades | Win: {wins}/{len(trades)} ({wins*100//len(trades) if trades else 0}%) | P&L: Rs.{total_pnl:,.0f}")

if not all_trades:
    print("No trades generated!")
    sys.exit(1)

df_trades = pd.DataFrame(all_trades)

print("\n" + "=" * 60)
print("QUANT ANALYST REPORT — Strategy Performance")
print("=" * 60)
for strat in df_trades["strategy"].unique():
    subset = df_trades[df_trades["strategy"] == strat]
    wins = subset["win"].sum()
    total = len(subset)
    total_pnl = subset["pnl"].sum()
    avg_win = subset[subset["win"]]["pnl"].mean() if wins > 0 else 0
    avg_loss = subset[~subset["win"]]["pnl"].mean() if total - wins > 0 else 0
    print(f"  {strat:20s} | {total:4d} trades | Win: {wins*100//total}% | Avg Win: Rs.{avg_win:,.0f} | Avg Loss: Rs.{avg_loss:,.0f} | Net: Rs.{total_pnl:,.0f}")

print("\n" + "=" * 60)
print("RISK MANAGER REPORT")
print("=" * 60)
wins = df_trades["win"].sum()
total = len(df_trades)
total_pnl = df_trades["pnl"].sum()
avg_win = df_trades[df_trades["win"]]["pnl"].mean()
avg_loss = df_trades[~df_trades["win"]]["pnl"].mean()
max_loss = df_trades["pnl"].min()
max_win = df_trades["pnl"].max()
# Drawdown
cumulative = df_trades["pnl"].cumsum()
peak = cumulative.cummax()
drawdown = (cumulative - peak).min()

print(f"  Total trades:      {total}")
print(f"  Win rate:          {wins*100//total}%")
print(f"  Total P&L:         Rs.{total_pnl:,.0f}")
print(f"  Average win:       Rs.{avg_win:,.0f}")
print(f"  Average loss:      Rs.{avg_loss:,.0f}")
print(f"  Reward/Risk ratio: {abs(avg_win/avg_loss):.2f}")
print(f"  Largest win:       Rs.{max_win:,.0f}")
print(f"  Largest loss:      Rs.{max_loss:,.0f}")
print(f"  Max drawdown:      Rs.{drawdown:,.0f}")
print(f"  Profit factor:     {abs(df_trades[df_trades['win']]['pnl'].sum() / df_trades[~df_trades['win']]['pnl'].sum()):.2f}")

print("\n" + "=" * 60)
print("PORTFOLIO MANAGER REPORT — BUY vs SELL")
print("=" * 60)
for side in ["BUY", "SELL"]:
    subset = df_trades[df_trades["side"] == side]
    if len(subset) > 0:
        w = subset["win"].sum()
        t = len(subset)
        p = subset["pnl"].sum()
        print(f"  {side:5s} | {t:4d} trades | Win: {w*100//t}% | Net P&L: Rs.{p:,.0f}")

print("\n" + "=" * 60)
print("OPERATIONS REPORT — Monthly Breakdown")
print("=" * 60)
# Simulate monthly
monthly_pnl = []
trades_per_month = max(1, len(all_trades) // 12)
for i in range(0, len(all_trades), trades_per_month):
    chunk = all_trades[i:i+trades_per_month]
    month_pnl = sum(t["pnl"] for t in chunk)
    month_wins = sum(1 for t in chunk if t["win"])
    month_total = len(chunk)
    monthly_pnl.append(month_pnl)
    status = "PROFIT" if month_pnl > 0 else "LOSS"
    print(f"  Month {i//trades_per_month + 1:2d}: {month_total:3d} trades | Win: {month_wins*100//month_total}% | P&L: Rs.{month_pnl:,.0f} | {status}")

profitable_months = sum(1 for p in monthly_pnl if p > 0)
print(f"\n  Profitable months: {profitable_months}/{len(monthly_pnl)} ({profitable_months*100//len(monthly_pnl)}%)")

print("\n" + "=" * 60)
print("FINAL VERDICT")
print("=" * 60)
edge = (wins/total * avg_win) + ((total-wins)/total * avg_loss)
print(f"  Edge per trade: Rs.{edge:,.0f}")
print(f"  Expected monthly (40 trades): Rs.{edge * 40:,.0f}")
print(f"  Expected yearly: Rs.{edge * 40 * 12:,.0f}")
print(f"  On Rs.26,882 capital: {edge * 40 * 12 / 26882 * 100:.0f}% annual return")
