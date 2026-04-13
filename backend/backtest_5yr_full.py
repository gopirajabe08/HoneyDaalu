"""
5-Year Full System Backtest — ALL market conditions, ALL strategies.
Tests: 2021 (bull), 2022 (bear), 2023 (recovery), 2024 (bull), 2025-26 (volatile).
20 liquid Nifty stocks × 5 years = real system performance across all conditions.
"""
import sys
sys.path.insert(0, ".")
import yfinance as yf
import pandas as pd
import numpy as np

STOCKS = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "BHARTIARTL",
          "ITC", "LT", "AXISBANK", "MARUTI", "SUNPHARMA", "WIPRO",
          "NTPC", "POWERGRID", "TATASTEEL", "BAJFINANCE", "TITAN", "HCLTECH", "KOTAKBANK"]

def supertrend(df, period=10, mult=2.0):
    hl2 = (df["High"] + df["Low"]) / 2
    atr = (df["High"] - df["Low"]).rolling(period).mean()
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
    try:
        ticker = yf.Ticker(symbol + ".NS")
        df = ticker.history(period="5y", interval="1d")
        if df is None or len(df) < 200:
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

        # Daily trend for MTF filter
        daily_bullish = (close > ema20) & (close > sma50)
        daily_bearish = (close < ema20) & (close < sma50)

        for i in range(60, len(df) - 1):
            price = close.iloc[i]
            date = df.index[i]
            vol_ratio = volume.iloc[i] / vol_sma.iloc[i] if vol_sma.iloc[i] > 0 else 0

            # Quality filters (matching our live system)
            if vol_ratio < 1.0:  # Volume filter
                continue
            if price < 50 or price > 5000:
                continue

            next_close = close.iloc[i + 1]
            next_high = high.iloc[i + 1]
            next_low = low.iloc[i + 1]
            atr_val = atr.iloc[i]
            if pd.isna(atr_val) or atr_val <= 0:
                continue
            sl_dist = atr_val * 2

            year = date.year

            # Supertrend BUY (only if daily trend bullish — MTF gate)
            if st_dir.iloc[i] == 1 and st_dir.iloc[i-1] == -1 and daily_bullish.iloc[i]:
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
                results.append({"strategy": "supertrend", "side": "BUY", "symbol": symbol,
                               "pnl": pnl * qty, "win": pnl > 0, "year": year, "date": str(date.date())})

            # Supertrend SELL (only if daily trend bearish — MTF gate)
            if st_dir.iloc[i] == -1 and st_dir.iloc[i-1] == 1 and daily_bearish.iloc[i]:
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
                               "pnl": pnl * qty, "win": pnl > 0, "year": year, "date": str(date.date())})

            # RSI Divergence BUY (oversold + bounce + daily not bearish)
            if rsi.iloc[i] < 35 and rsi.iloc[i] > rsi.iloc[i-1] and not daily_bearish.iloc[i]:
                if close.iloc[i] > close.iloc[i-1]:
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
                                   "pnl": pnl * qty, "win": pnl > 0, "year": year, "date": str(date.date())})

            # RSI Divergence SELL (overbought + drop + daily not bullish)
            if rsi.iloc[i] > 65 and rsi.iloc[i] < rsi.iloc[i-1] and not daily_bullish.iloc[i]:
                if close.iloc[i] < close.iloc[i-1]:
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
                    results.append({"strategy": "rsi_divergence", "side": "SELL", "symbol": symbol,
                                   "pnl": pnl * qty, "win": pnl > 0, "year": year, "date": str(date.date())})

            # BB Contra BUY (lower band bounce + daily not bearish)
            if close.iloc[i] <= bb_lower.iloc[i] * 1.01 and close.iloc[i] > close.iloc[i-1] and not daily_bearish.iloc[i]:
                entry = price
                sl = entry - sl_dist
                target = bb_mid.iloc[i]
                if next_low <= sl:
                    pnl = sl - entry
                elif next_high >= target:
                    pnl = target - entry
                else:
                    pnl = next_close - entry
                qty = max(1, int(capital_per_trade / entry))
                results.append({"strategy": "bb_contra", "side": "BUY", "symbol": symbol,
                               "pnl": pnl * qty, "win": pnl > 0, "year": year, "date": str(date.date())})

            # BB Contra SELL (upper band rejection + daily not bullish)
            if close.iloc[i] >= bb_upper.iloc[i] * 0.99 and close.iloc[i] < close.iloc[i-1] and not daily_bullish.iloc[i]:
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
                               "pnl": pnl * qty, "win": pnl > 0, "year": year, "date": str(date.date())})

            # BB Squeeze breakout (low BB width + breakout)
            if not pd.isna(bb_std.iloc[i]):
                bb_width = (2 * bb_std.iloc[i]) / bb_mid.iloc[i] * 100 if bb_mid.iloc[i] > 0 else 99
                bb_width_avg = ((2 * bb_std) / bb_mid * 100).rolling(50).mean().iloc[i]
                if not pd.isna(bb_width_avg) and bb_width < bb_width_avg * 0.6:
                    if close.iloc[i] > bb_upper.iloc[i] and daily_bullish.iloc[i]:
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
                        results.append({"strategy": "bb_squeeze", "side": "BUY", "symbol": symbol,
                                       "pnl": pnl * qty, "win": pnl > 0, "year": year, "date": str(date.date())})

        return results
    except Exception as e:
        print(f"  ERROR {symbol}: {e}")
        return None

print("=" * 70)
print("5-YEAR FULL SYSTEM BACKTEST")
print("20 Nifty Stocks | 2021-2026 | With MTF Gate + Volume Filter")
print("=" * 70)

all_trades = []
for stock in STOCKS:
    trades = backtest_stock(stock)
    if trades:
        all_trades.extend(trades)
        wins = sum(1 for t in trades if t["win"])
        pnl = sum(t["pnl"] for t in trades)
        print(f"  {stock:15s} | {len(trades):4d} trades | Win: {wins*100//max(len(trades),1):2d}% | P&L: Rs.{pnl:>8,.0f}")
    else:
        print(f"  {stock:15s} | FAILED")

df_t = pd.DataFrame(all_trades)
if len(df_t) == 0:
    print("NO TRADES!")
    sys.exit(1)

print(f"\nTotal: {len(df_t)} trades across {df_t['symbol'].nunique()} stocks")

# === YEAR-BY-YEAR (the real test) ===
print("\n" + "=" * 70)
print("YEAR-BY-YEAR PERFORMANCE (Does system work in ALL market conditions?)")
print("=" * 70)
market_context = {2021: "BULL (post-COVID rally)", 2022: "BEAR (global inflation)",
                  2023: "RECOVERY (steady climb)", 2024: "BULL (election rally)",
                  2025: "VOLATILE (tariff wars)", 2026: "CURRENT"}
for year in sorted(df_t["year"].unique()):
    subset = df_t[df_t["year"] == year]
    wins = subset["win"].sum()
    total = len(subset)
    pnl = subset["pnl"].sum()
    context = market_context.get(year, "")
    status = "PROFIT" if pnl > 0 else "LOSS"
    print(f"  {year} {context:30s} | {total:4d} trades | Win: {wins*100//max(total,1)}% | P&L: Rs.{pnl:>8,.0f} | {status}")

# === STRATEGY BY YEAR ===
print("\n" + "=" * 70)
print("STRATEGY × YEAR (Which strategy works in which market?)")
print("=" * 70)
for strat in sorted(df_t["strategy"].unique()):
    print(f"\n  {strat.upper()}:")
    for year in sorted(df_t["year"].unique()):
        subset = df_t[(df_t["strategy"] == strat) & (df_t["year"] == year)]
        if len(subset) > 0:
            wins = subset["win"].sum()
            pnl = subset["pnl"].sum()
            print(f"    {year}: {len(subset):3d} trades | Win: {wins*100//len(subset)}% | P&L: Rs.{pnl:>7,.0f}")

# === QUANT REPORT ===
print("\n" + "=" * 70)
print("QUANT ANALYST — Strategy Rankings (5 Years)")
print("=" * 70)
for strat in df_t["strategy"].unique():
    s = df_t[df_t["strategy"] == strat]
    wins = s["win"].sum()
    total = len(s)
    pnl = s["pnl"].sum()
    avg_w = s[s["win"]]["pnl"].mean() if wins > 0 else 0
    avg_l = s[~s["win"]]["pnl"].mean() if total - wins > 0 else 0
    rr = abs(avg_w / avg_l) if avg_l != 0 else 0
    print(f"  {strat:20s} | {total:4d} trades | Win: {wins*100//total}% | R:R: {rr:.2f} | Net: Rs.{pnl:>8,.0f}")

# === RISK REPORT ===
print("\n" + "=" * 70)
print("RISK MANAGER — Portfolio Level (5 Years)")
print("=" * 70)
wins = df_t["win"].sum()
total = len(df_t)
pnl = df_t["pnl"].sum()
avg_w = df_t[df_t["win"]]["pnl"].mean()
avg_l = df_t[~df_t["win"]]["pnl"].mean()
cum = df_t["pnl"].cumsum()
peak = cum.cummax()
dd = (cum - peak).min()
pf = abs(df_t[df_t["win"]]["pnl"].sum() / df_t[~df_t["win"]]["pnl"].sum()) if df_t[~df_t["win"]]["pnl"].sum() != 0 else 0

print(f"  Total trades:      {total}")
print(f"  Win rate:          {wins*100//total}%")
print(f"  Total P&L:         Rs.{pnl:,.0f}")
print(f"  Avg win:           Rs.{avg_w:,.0f}")
print(f"  Avg loss:          Rs.{avg_l:,.0f}")
print(f"  Reward/Risk:       {abs(avg_w/avg_l):.2f}")
print(f"  Profit factor:     {pf:.2f}")
print(f"  Max drawdown:      Rs.{dd:,.0f}")
print(f"  Max single loss:   Rs.{df_t['pnl'].min():,.0f}")

# === BUY vs SELL ===
print("\n" + "=" * 70)
print("PORTFOLIO MANAGER — Direction Performance (5 Years)")
print("=" * 70)
for side in ["BUY", "SELL"]:
    s = df_t[df_t["side"] == side]
    if len(s) > 0:
        w = s["win"].sum()
        print(f"  {side:5s} | {len(s):4d} trades | Win: {w*100//len(s)}% | P&L: Rs.{s['pnl'].sum():>8,.0f}")

# === VERDICT ===
print("\n" + "=" * 70)
print("FINAL VERDICT — ALL ROLES")
print("=" * 70)
edge = pnl / total
yearly = edge * 240  # ~240 trading days, assume 1 trade/day avg
annual_pct = yearly / 26882 * 100
profitable_years = sum(1 for y in df_t["year"].unique() if df_t[df_t["year"]==y]["pnl"].sum() > 0)
total_years = len(df_t["year"].unique())

print(f"  Edge per trade:        Rs.{edge:,.0f}")
print(f"  Trades per year avg:   {total // total_years}")
print(f"  Expected annual P&L:   Rs.{pnl // total_years:,.0f}")
print(f"  On Rs.26,882 capital:  {(pnl // total_years) / 26882 * 100:.0f}% annual return")
print(f"  Profitable years:      {profitable_years}/{total_years}")
print(f"  System survives bear:  {'YES' if df_t[df_t['year']==2022]['pnl'].sum() > 0 else 'NEEDS REVIEW'}")
print(f"  System works in bull:  {'YES' if df_t[df_t['year']==2024]['pnl'].sum() > 0 else 'NEEDS REVIEW'}")
