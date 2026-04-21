"""
12-month (or custom period) backtest of all 10 play strategies + winning_horse
composite, with realistic TradeJini MIS charges applied. Saves per-trade CSV
and a ranked summary CSV for auditability.

Matches live paper_trader.py cost model:
  brokerage = min(20, 0.03% turnover) x 2 legs
  STT       = 0.025% turnover (sell side)
  exchange  = 0.03% turnover (NSE + SEBI + stamp)

Usage:
  python backtest_with_charges.py                  # default: 1y, ₹12k/trade
  python backtest_with_charges.py --period 2y
  python backtest_with_charges.py --capital 15000 --period 6mo
  python backtest_with_charges.py --out /tmp/backtest
"""
import argparse
import csv
import os
import sys
from datetime import datetime

sys.path.insert(0, ".")

import numpy as np
import pandas as pd
import yfinance as yf

STOCKS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "BHARTIARTL",
    "ITC", "LT", "AXISBANK", "SUNPHARMA", "WIPRO", "NTPC", "POWERGRID",
    "TATASTEEL", "BAJFINANCE", "TITAN", "HCLTECH", "KOTAKBANK", "JSWSTEEL",
]


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
        if df["Close"].iloc[i] > upper.iloc[i - 1]:
            direction.iloc[i] = 1
        elif df["Close"].iloc[i] < lower.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]
        if direction.iloc[i] == 1:
            st.iloc[i] = max(lower.iloc[i], st.iloc[i - 1]) if direction.iloc[i - 1] == 1 else lower.iloc[i]
        else:
            st.iloc[i] = min(upper.iloc[i], st.iloc[i - 1]) if direction.iloc[i - 1] == -1 else upper.iloc[i]
    return direction


def round_trip_charges(turnover: float) -> float:
    # Matches services/paper_trader.py:651-658 exactly
    brokerage_per_leg = min(20, turnover * 0.0003)
    brokerage = brokerage_per_leg * 2
    stt = turnover * 0.00025
    exchange = turnover * 0.0003
    return round(brokerage + stt + exchange, 2)


def simulate_trade(entry, sl_dist, side, next_high, next_low, next_close, capital):
    qty = max(1, int(capital / entry))
    target_mult = 2.0

    if side == "BUY":
        sl = entry - sl_dist
        target = entry + sl_dist * target_mult
        if next_low <= sl:
            exit_price = sl
        elif next_high >= target:
            exit_price = target
        else:
            exit_price = next_close
        gross = (exit_price - entry) * qty
    else:
        sl = entry + sl_dist
        target = entry - sl_dist * target_mult
        if next_high >= sl:
            exit_price = sl
        elif next_low <= target:
            exit_price = target
        else:
            exit_price = next_close
        gross = (entry - exit_price) * qty

    turnover = qty * entry
    charges = round_trip_charges(turnover)
    net = round(gross - charges, 2)
    return {
        "qty": qty,
        "entry": round(entry, 2),
        "exit": round(exit_price, 2),
        "sl": round(sl, 2),
        "target": round(target, 2),
        "gross_pnl": round(gross, 2),
        "charges": charges,
        "net_pnl": net,
        "win": net > 0,
    }


def backtest_stock(symbol: str, period: str, capital: float):
    try:
        df = yf.Ticker(symbol + ".NS").history(period=period, interval="1d")
        if df is None or len(df) < 60:
            return None
    except Exception:
        return None

    close, high, low, opn, volume = df["Close"], df["High"], df["Low"], df["Open"], df["Volume"]
    vol_sma = volume.rolling(20).mean()
    rsi = calc_rsi(close)
    ema9 = close.ewm(span=9).mean()
    ema20 = close.ewm(span=20).mean()
    sma50 = close.rolling(50).mean()
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    bb_width = (2 * bb_std / bb_mid * 100)
    bb_width_avg = bb_width.rolling(50).mean()
    st_dir = supertrend_dir(df)
    atr = (high - low).rolling(14).mean()
    typical = (high + low + close) / 3

    # Nifty-up days approximation: use RELIANCE as market proxy if loading NIFTY fails;
    # simpler: treat a stock's own prior-day positive close as "market up" signal.
    trades = []
    start = min(200, len(df) - 2)
    for i in range(start, len(df) - 1):
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
        nh, nl, nc = high.iloc[i + 1], low.iloc[i + 1], close.iloc[i + 1]
        year = df.index[i].year
        bullish = close.iloc[i] > ema20.iloc[i] and close.iloc[i] > sma50.iloc[i]
        bearish = close.iloc[i] < ema20.iloc[i] and close.iloc[i] < sma50.iloc[i]
        market_up = close.iloc[i] > close.iloc[i - 1]  # proxy for Nifty UP day

        def add(strat, side, score=0.0):
            r = simulate_trade(price, sl_dist, side, nh, nl, nc, capital)
            r.update({
                "strategy": strat,
                "side": side,
                "symbol": symbol,
                "date": df.index[i].strftime("%Y-%m-%d"),
                "year": year,
                "score": round(score, 2),
            })
            trades.append(r)

        # Play 1: EMA Crossover
        if not pd.isna(ema9.iloc[i - 1]):
            if ema9.iloc[i] > ema20.iloc[i] and ema9.iloc[i - 1] <= ema20.iloc[i - 1] and bullish:
                add("play1_ema_crossover", "BUY")
            if ema9.iloc[i] < ema20.iloc[i] and ema9.iloc[i - 1] >= ema20.iloc[i - 1] and bearish:
                add("play1_ema_crossover", "SELL")

        # Play 2: Triple MA
        if not pd.isna(sma50.iloc[i]):
            if ema9.iloc[i] > ema20.iloc[i] > sma50.iloc[i] and not (ema9.iloc[i - 1] > ema20.iloc[i - 1] > sma50.iloc[i - 1]):
                add("play2_triple_ma", "BUY")
            if ema9.iloc[i] < ema20.iloc[i] < sma50.iloc[i] and not (ema9.iloc[i - 1] < ema20.iloc[i - 1] < sma50.iloc[i - 1]):
                add("play2_triple_ma", "SELL")

        # Play 3: VWAP Pullback
        vwap_dist = abs(price - typical.iloc[i]) / typical.iloc[i] * 100
        if vwap_dist < 0.3 and bullish and close.iloc[i] > close.iloc[i - 1]:
            add("play3_vwap_pullback", "BUY")
        if vwap_dist < 0.3 and bearish and close.iloc[i] < close.iloc[i - 1]:
            add("play3_vwap_pullback", "SELL")

        # Play 4: Supertrend
        if st_dir.iloc[i] == 1 and st_dir.iloc[i - 1] == -1 and bullish:
            add("play4_supertrend", "BUY")
        if st_dir.iloc[i] == -1 and st_dir.iloc[i - 1] == 1 and bearish:
            add("play4_supertrend", "SELL")

        # Play 5: BB Squeeze
        if not pd.isna(bb_width_avg.iloc[i]):
            if bb_width.iloc[i] < bb_width_avg.iloc[i] * 0.6:
                if close.iloc[i] > bb_upper.iloc[i] and bullish:
                    add("play5_bb_squeeze", "BUY")
                if close.iloc[i] < bb_lower.iloc[i] and bearish:
                    add("play5_bb_squeeze", "SELL")

        # Play 6: BB Contra
        if close.iloc[i] <= bb_lower.iloc[i] * 1.01 and close.iloc[i] > close.iloc[i - 1] and not bearish:
            add("play6_bb_contra", "BUY")
        if close.iloc[i] >= bb_upper.iloc[i] * 0.99 and close.iloc[i] < close.iloc[i - 1] and not bullish:
            add("play6_bb_contra", "SELL")

        # Play 7: ORB
        day_range = high.iloc[i] - low.iloc[i]
        if day_range > 0:
            up = close.iloc[i] > opn.iloc[i] and (close.iloc[i] - opn.iloc[i]) > day_range * 0.6
            down = close.iloc[i] < opn.iloc[i] and (opn.iloc[i] - close.iloc[i]) > day_range * 0.6
            if up and bullish:
                add("play7_orb", "BUY")
            if down and bearish:
                add("play7_orb", "SELL")

        # Play 8: RSI Divergence
        if rsi.iloc[i] < 35 and rsi.iloc[i] > rsi.iloc[i - 1] and close.iloc[i] > close.iloc[i - 1] and not bearish:
            add("play8_rsi_divergence", "BUY")
        if rsi.iloc[i] > 65 and rsi.iloc[i] < rsi.iloc[i - 1] and close.iloc[i] < close.iloc[i - 1] and not bullish:
            add("play8_rsi_divergence", "SELL")

        # Play 9: Gap Analysis
        prev_close = close.iloc[i - 1]
        gap_pct = (opn.iloc[i] - prev_close) / prev_close * 100
        if gap_pct > 1.0 and close.iloc[i] > opn.iloc[i] and bullish:
            add("play9_gap_analysis", "BUY")
        if gap_pct < -1.0 and close.iloc[i] < opn.iloc[i] and bearish:
            add("play9_gap_analysis", "SELL")

        # Play 10: Momentum Rank
        ret_5d = (close.iloc[i] - close.iloc[i - 5]) / close.iloc[i - 5] * 100 if i >= 5 else 0
        if ret_5d > 3 and vol_ratio > 1.5 and bullish:
            add("play10_momentum_rank", "BUY")
        if ret_5d < -3 and vol_ratio > 1.5 and bearish:
            add("play10_momentum_rank", "SELL")

        # Winning Horse composite: market up + bullish + strong 5-day momentum + VWAP pullback setup
        if market_up and bullish and ret_5d > 2 and vol_ratio > 1.2 and vwap_dist < 0.5:
            score = (ret_5d * vol_ratio) + (1 / max(vwap_dist, 0.1))
            add("winning_horse", "BUY", score=score)

    return trades


def run_backtest(period: str, capital: float, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    trades_csv = os.path.join(out_dir, f"trades_{stamp}.csv")
    summary_csv = os.path.join(out_dir, f"summary_{stamp}.csv")

    print("=" * 78)
    print(f"BACKTEST WITH CHARGES — period={period} capital=₹{capital:,.0f} stocks={len(STOCKS)}")
    print("Cost model: brokerage min(20, 0.03% turnover) x 2 + STT 0.025% + exchange 0.03%")
    print("=" * 78)

    all_trades = []
    for symbol in STOCKS:
        t = backtest_stock(symbol, period, capital)
        if t:
            all_trades.extend(t)
            w = sum(1 for x in t if x["win"])
            p = sum(x["net_pnl"] for x in t)
            print(f"  {symbol:15s} | {len(t):4d} trades | Win: {w*100//max(len(t),1):2d}% | Net P&L: ₹{p:>9,.0f}")
        else:
            print(f"  {symbol:15s} | FAILED (no data)")

    if not all_trades:
        print("\nNo trades generated — check data source.")
        return

    # Write per-trade CSV
    keys = ["date", "year", "strategy", "symbol", "side", "qty", "entry", "exit",
            "sl", "target", "gross_pnl", "charges", "net_pnl", "win", "score"]
    with open(trades_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for t in all_trades:
            w.writerow({k: t.get(k, "") for k in keys})

    df = pd.DataFrame(all_trades)

    # Per-strategy summary
    print("\n" + "=" * 78)
    print("STRATEGY RANKING — NET P&L AFTER CHARGES")
    print("=" * 78)
    print(f"  {'Strategy':25s} {'Trades':>7s} {'Win%':>5s} {'AvgWin':>9s} {'AvgLoss':>9s} {'R:R':>5s} {'Edge':>9s} {'Net P&L':>12s}  Verdict")
    print("  " + "-" * 106)

    rows = []
    for strat in sorted(df["strategy"].unique()):
        s = df[df["strategy"] == strat]
        wins = int(s["win"].sum())
        total = len(s)
        net = float(s["net_pnl"].sum())
        gross = float(s["gross_pnl"].sum())
        chg = float(s["charges"].sum())
        avg_w = s[s["win"]]["net_pnl"].mean() if wins > 0 else 0
        avg_l = s[~s["win"]]["net_pnl"].mean() if total - wins > 0 else 0
        rr = abs(avg_w / avg_l) if avg_l != 0 else 0
        edge = net / total if total > 0 else 0
        verdict = "WINNER" if net > 0 and wins * 100 / max(total, 1) >= 50 else ("MARGINAL" if net > 0 else "LOSER")
        rows.append({
            "strategy": strat, "trades": total, "wins": wins,
            "win_pct": round(wins * 100 / max(total, 1), 1),
            "gross_pnl": round(gross, 2), "charges": round(chg, 2),
            "net_pnl": round(net, 2), "avg_win": round(avg_w, 2),
            "avg_loss": round(avg_l, 2), "rr": round(rr, 2),
            "edge_per_trade": round(edge, 2), "verdict": verdict,
        })

    rows.sort(key=lambda r: r["net_pnl"], reverse=True)
    for r in rows:
        print(f"  {r['strategy']:25s} {r['trades']:>7d} {r['win_pct']:>4.0f}% "
              f"₹{r['avg_win']:>7,.0f} ₹{r['avg_loss']:>7,.0f} {r['rr']:>5.2f} "
              f"₹{r['edge_per_trade']:>7,.0f} ₹{r['net_pnl']:>10,.0f}  {r['verdict']}")

    with open(summary_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # Portfolio summary
    print("\n" + "=" * 78)
    print("PORTFOLIO TOTAL (all strategies combined, before dedup)")
    print("=" * 78)
    total_trades = len(df)
    total_wins = int(df["win"].sum())
    total_gross = float(df["gross_pnl"].sum())
    total_chg = float(df["charges"].sum())
    total_net = float(df["net_pnl"].sum())
    print(f"  Total trades:    {total_trades}")
    print(f"  Win rate:        {total_wins * 100 // max(total_trades, 1)}%")
    print(f"  Gross P&L:       ₹{total_gross:,.0f}")
    print(f"  Charges:         ₹{total_chg:,.0f} ({total_chg / max(total_gross, 1) * 100:.1f}% of gross)")
    print(f"  Net P&L:         ₹{total_net:,.0f}")
    print(f"  Edge per trade:  ₹{total_net / max(total_trades, 1):,.1f}")

    print(f"\nOutput files:")
    print(f"  per-trade: {trades_csv}")
    print(f"  summary:   {summary_csv}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", default="1y", help="yfinance period (1y, 2y, 6mo, 5y, etc.)")
    ap.add_argument("--capital", type=float, default=12000, help="capital per trade in ₹")
    ap.add_argument("--out", default="backtest_results", help="output directory")
    args = ap.parse_args()
    run_backtest(args.period, args.capital, args.out)
