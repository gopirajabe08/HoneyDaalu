"""
ALL 10 strategies backtested on 5 years of NSE data.
No shortcuts. Every strategy gets a fair test.
"""
import sys
sys.path.insert(0, ".")
import yfinance as yf
import pandas as pd
import numpy as np

STOCKS = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "BHARTIARTL",
          "ITC", "LT", "AXISBANK", "SUNPHARMA", "WIPRO",
          "NTPC", "POWERGRID", "TATASTEEL", "BAJFINANCE", "TITAN", "HCLTECH",
          "KOTAKBANK", "JSWSTEEL"]

def calc_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def supertrend_dir(df, period=10, mult=2.0):
    hl2 = (df["High"] + df["Low"]) / 2
    atr = (df["High"] - df["Low"]).rolling(period).mean()
    upper = hl2 + mult * atr
    lower = hl2 - mult * atr
    direction = pd.Series(index=df.index, dtype=int)
    st = pd.Series(index=df.index, dtype=float)
    direction.iloc[0] = -1
    st.iloc[0] = upper.iloc[0]
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

def simulate_trade(entry, sl_dist, side, next_high, next_low, next_close, capital=12000):
    """Simulate a single trade with SL and target. Returns P&L."""
    qty = max(1, int(capital / entry))
    target_mult = 2.0  # R:R = 1:2

    if side == "BUY":
        sl = entry - sl_dist
        target = entry + sl_dist * target_mult
        if next_low <= sl:
            pnl = (sl - entry) * qty
        elif next_high >= target:
            pnl = (target - entry) * qty
        else:
            pnl = (next_close - entry) * qty
    else:  # SELL
        sl = entry + sl_dist
        target = entry - sl_dist * target_mult
        if next_high >= sl:
            pnl = (entry - sl) * qty
        elif next_low <= target:
            pnl = (entry - target) * qty
        else:
            pnl = (entry - next_close) * qty

    return round(pnl, 2), pnl > 0

def backtest_stock(symbol):
    try:
        df = yf.Ticker(symbol + ".NS").history(period="5y", interval="1d")
        if df is None or len(df) < 200:
            return None
    except:
        return None

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    opn = df["Open"]
    volume = df["Volume"]
    vol_sma = volume.rolling(20).mean()
    rsi = calc_rsi(close)
    ema9 = close.ewm(span=9).mean()
    ema20 = close.ewm(span=20).mean()
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    bb_width = (2 * bb_std / bb_mid * 100)
    bb_width_avg = bb_width.rolling(50).mean()
    st_dir = supertrend_dir(df)
    atr = (high - low).rolling(14).mean()

    # VWAP approximation (cumulative for each day — simplified as daily typical price)
    typical = (high + low + close) / 3

    trades = []

    for i in range(200, len(df) - 1):
        price = close.iloc[i]
        if price < 50 or price > 5000:
            continue
        vol_ratio = volume.iloc[i] / vol_sma.iloc[i] if vol_sma.iloc[i] > 0 else 0
        if vol_ratio < 1.0:
            continue
        atr_val = atr.iloc[i]
        if pd.isna(atr_val) or atr_val <= 0:
            continue
        sl_dist = atr_val * 2

        nh = high.iloc[i+1]
        nl = low.iloc[i+1]
        nc = close.iloc[i+1]
        year = df.index[i].year
        bullish = close.iloc[i] > ema20.iloc[i] and close.iloc[i] > sma50.iloc[i]
        bearish = close.iloc[i] < ema20.iloc[i] and close.iloc[i] < sma50.iloc[i]

        def add(strat, side):
            pnl, win = simulate_trade(price, sl_dist, side, nh, nl, nc)
            trades.append({"strategy": strat, "side": side, "symbol": symbol,
                          "pnl": pnl, "win": win, "year": year})

        # PLAY 1: EMA Crossover (9 EMA crosses 20 EMA)
        if not pd.isna(ema9.iloc[i-1]):
            if ema9.iloc[i] > ema20.iloc[i] and ema9.iloc[i-1] <= ema20.iloc[i-1] and bullish:
                add("play1_ema_crossover", "BUY")
            if ema9.iloc[i] < ema20.iloc[i] and ema9.iloc[i-1] >= ema20.iloc[i-1] and bearish:
                add("play1_ema_crossover", "SELL")

        # PLAY 2: Triple MA (9 > 20 > 50 alignment)
        if not pd.isna(sma50.iloc[i]):
            if ema9.iloc[i] > ema20.iloc[i] > sma50.iloc[i] and not (ema9.iloc[i-1] > ema20.iloc[i-1] > sma50.iloc[i-1]):
                add("play2_triple_ma", "BUY")
            if ema9.iloc[i] < ema20.iloc[i] < sma50.iloc[i] and not (ema9.iloc[i-1] < ema20.iloc[i-1] < sma50.iloc[i-1]):
                add("play2_triple_ma", "SELL")

        # PLAY 3: VWAP Pullback (price pulls back to VWAP/typical in trend)
        vwap_dist = abs(price - typical.iloc[i]) / typical.iloc[i] * 100
        if vwap_dist < 0.3 and bullish and close.iloc[i] > close.iloc[i-1]:
            add("play3_vwap_pullback", "BUY")
        if vwap_dist < 0.3 and bearish and close.iloc[i] < close.iloc[i-1]:
            add("play3_vwap_pullback", "SELL")

        # PLAY 4: Supertrend
        if st_dir.iloc[i] == 1 and st_dir.iloc[i-1] == -1 and bullish:
            add("play4_supertrend", "BUY")
        if st_dir.iloc[i] == -1 and st_dir.iloc[i-1] == 1 and bearish:
            add("play4_supertrend", "SELL")

        # PLAY 5: BB Squeeze (width < 60% of avg, breakout)
        if not pd.isna(bb_width_avg.iloc[i]):
            if bb_width.iloc[i] < bb_width_avg.iloc[i] * 0.6:
                if close.iloc[i] > bb_upper.iloc[i] and bullish:
                    add("play5_bb_squeeze", "BUY")
                if close.iloc[i] < bb_lower.iloc[i] and bearish:
                    add("play5_bb_squeeze", "SELL")

        # PLAY 6: BB Contra (touch band + reversal)
        if close.iloc[i] <= bb_lower.iloc[i] * 1.01 and close.iloc[i] > close.iloc[i-1] and not bearish:
            add("play6_bb_contra", "BUY")
        if close.iloc[i] >= bb_upper.iloc[i] * 0.99 and close.iloc[i] < close.iloc[i-1] and not bullish:
            add("play6_bb_contra", "SELL")

        # PLAY 7: ORB (Opening Range Breakout — first candle high/low break)
        day_range = high.iloc[i] - low.iloc[i]
        if day_range > 0:
            orb_break_up = close.iloc[i] > opn.iloc[i] and (close.iloc[i] - opn.iloc[i]) > day_range * 0.6
            orb_break_down = close.iloc[i] < opn.iloc[i] and (opn.iloc[i] - close.iloc[i]) > day_range * 0.6
            if orb_break_up and bullish:
                add("play7_orb", "BUY")
            if orb_break_down and bearish:
                add("play7_orb", "SELL")

        # PLAY 8: RSI Divergence
        if rsi.iloc[i] < 35 and rsi.iloc[i] > rsi.iloc[i-1] and close.iloc[i] > close.iloc[i-1] and not bearish:
            add("play8_rsi_divergence", "BUY")
        if rsi.iloc[i] > 65 and rsi.iloc[i] < rsi.iloc[i-1] and close.iloc[i] < close.iloc[i-1] and not bullish:
            add("play8_rsi_divergence", "SELL")

        # PLAY 9: Gap Analysis (gap up/down > 1% from prev close)
        prev_close = close.iloc[i-1]
        gap_pct = (opn.iloc[i] - prev_close) / prev_close * 100
        if gap_pct > 1.0 and close.iloc[i] > opn.iloc[i] and bullish:
            add("play9_gap_analysis", "BUY")
        if gap_pct < -1.0 and close.iloc[i] < opn.iloc[i] and bearish:
            add("play9_gap_analysis", "SELL")

        # PLAY 10: Momentum Rank (strong relative move + volume)
        ret_5d = (close.iloc[i] - close.iloc[i-5]) / close.iloc[i-5] * 100 if i >= 5 else 0
        if ret_5d > 3 and vol_ratio > 1.5 and bullish:
            add("play10_momentum_rank", "BUY")
        if ret_5d < -3 and vol_ratio > 1.5 and bearish:
            add("play10_momentum_rank", "SELL")

    return trades

# Run
print("=" * 70)
print("ALL 10 STRATEGIES — 5-YEAR BACKTEST — 20 NIFTY STOCKS")
print("With Volume Filter (>=1x) + MTF Gate (trend aligned)")
print("=" * 70)
print()

all_trades = []
for stock in STOCKS:
    t = backtest_stock(stock)
    if t:
        all_trades.extend(t)
        w = sum(1 for x in t if x["win"])
        p = sum(x["pnl"] for x in t)
        print(f"  {stock:15s} | {len(t):4d} trades | Win: {w*100//max(len(t),1):2d}% | P&L: Rs.{p:>8,.0f}")
    else:
        print(f"  {stock:15s} | FAILED")

df = pd.DataFrame(all_trades)
print(f"\nTotal: {len(df)} trades across {df['symbol'].nunique()} stocks")

# === ALL 10 STRATEGIES RANKED ===
print("\n" + "=" * 70)
print("ALL 10 STRATEGIES — RANKED BY PROFIT (5 Years)")
print("=" * 70)
strat_results = []
for strat in sorted(df["strategy"].unique()):
    s = df[df["strategy"] == strat]
    wins = s["win"].sum()
    total = len(s)
    pnl = s["pnl"].sum()
    avg_w = s[s["win"]]["pnl"].mean() if wins > 0 else 0
    avg_l = s[~s["win"]]["pnl"].mean() if total - wins > 0 else 0
    rr = abs(avg_w / avg_l) if avg_l != 0 else 0
    edge = pnl / total if total > 0 else 0
    strat_results.append((strat, total, wins, pnl, avg_w, avg_l, rr, edge))

strat_results.sort(key=lambda x: x[3], reverse=True)
print(f"  {'Strategy':25s} {'Trades':>6s} {'Win%':>5s} {'R:R':>5s} {'AvgWin':>8s} {'AvgLoss':>8s} {'Edge/Trade':>10s} {'Net P&L':>10s} {'Verdict':>10s}")
print("  " + "-" * 95)
for strat, total, wins, pnl, avg_w, avg_l, rr, edge in strat_results:
    wr = wins * 100 // total if total > 0 else 0
    verdict = "WINNER" if pnl > 0 and wr >= 50 else "MARGINAL" if pnl > 0 else "LOSER"
    print(f"  {strat:25s} {total:6d} {wr:4d}% {rr:5.2f} Rs.{avg_w:>6,.0f} Rs.{avg_l:>6,.0f} Rs.{edge:>8,.0f} Rs.{pnl:>8,.0f} {verdict:>10s}")

# === YEAR BY YEAR PER STRATEGY ===
print("\n" + "=" * 70)
print("STRATEGY × YEAR — WHERE EACH STRATEGY WINS/LOSES")
print("=" * 70)
for strat, _, _, _, _, _, _, _ in strat_results:
    yearly = []
    for year in sorted(df["year"].unique()):
        s = df[(df["strategy"] == strat) & (df["year"] == year)]
        if len(s) > 0:
            yearly.append(f"{year}:{'+'if s['pnl'].sum()>0 else ''}{s['pnl'].sum():,.0f}({s['win'].sum()*100//len(s)}%)")
    print(f"  {strat:25s} | {' | '.join(yearly)}")

# === BUY vs SELL per strategy ===
print("\n" + "=" * 70)
print("BUY vs SELL — PER STRATEGY")
print("=" * 70)
for strat, _, _, _, _, _, _, _ in strat_results:
    for side in ["BUY", "SELL"]:
        s = df[(df["strategy"] == strat) & (df["side"] == side)]
        if len(s) > 0:
            w = s["win"].sum()
            p = s["pnl"].sum()
            print(f"  {strat:25s} {side:5s} | {len(s):4d} trades | Win: {w*100//len(s)}% | P&L: Rs.{p:>8,.0f}")

# === OVERALL ===
print("\n" + "=" * 70)
print("PORTFOLIO SUMMARY")
print("=" * 70)
wins = df["win"].sum()
total = len(df)
pnl = df["pnl"].sum()
avg_w = df[df["win"]]["pnl"].mean()
avg_l = df[~df["win"]]["pnl"].mean()
cum = df["pnl"].cumsum()
dd = (cum - cum.cummax()).min()
pf = abs(df[df["win"]]["pnl"].sum() / df[~df["win"]]["pnl"].sum()) if df[~df["win"]]["pnl"].sum() != 0 else 0

print(f"  Total trades:    {total}")
print(f"  Win rate:        {wins*100//total}%")
print(f"  Total P&L:       Rs.{pnl:,.0f}")
print(f"  Profit factor:   {pf:.2f}")
print(f"  Avg win:         Rs.{avg_w:,.0f}")
print(f"  Avg loss:        Rs.{avg_l:,.0f}")
print(f"  R:R ratio:       {abs(avg_w/avg_l):.2f}")
print(f"  Max drawdown:    Rs.{dd:,.0f}")
print(f"  Edge per trade:  Rs.{pnl/total:,.0f}")
