"""
backtest_v2 CLI — orchestrates data fetch + signal generation + simulation.

Usage:
    python -m backtest_v2.cli                       # default: top-20 large caps, 12mo
    python -m backtest_v2.cli --period 24mo
    python -m backtest_v2.cli --symbols RELIANCE,TCS,HDFCBANK
    python -m backtest_v2.cli --capital 15000 --out /tmp/bt2

Output:
    summary.csv  — per-strategy aggregates
    trades.csv   — every executed trade with full cost breakdown
"""
from __future__ import annotations
import argparse
import csv
import logging
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest_v2.data import fetch_universe
from backtest_v2.strategies import run_all_strategies, STRATEGIES
from backtest_v2.runner import simulate_all


# Default universe — same 20 large-caps as old backtest_with_charges.py
# for direct comparability. CLI can override.
DEFAULT_SYMBOLS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "BHARTIARTL",
    "ITC", "LT", "AXISBANK", "SUNPHARMA", "WIPRO", "NTPC", "POWERGRID",
    "TATASTEEL", "BAJFINANCE", "TITAN", "HCLTECH", "KOTAKBANK", "JSWSTEEL",
]


def main():
    p = argparse.ArgumentParser(description="backtest_v2 — walk-forward backtest with realistic execution")
    p.add_argument("--period", default="12mo", help="yfinance period (default 12mo)")
    p.add_argument("--capital", type=float, default=15000, help="capital per trade (default 15000)")
    p.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS), help="comma-separated NSE symbols")
    p.add_argument("--intraday", action="store_true", help="treat as intraday (no DP charges, MIS rates)")
    p.add_argument("--liquidity", default="large_cap", choices=["large_cap", "mid_cap", "small_cap"])
    p.add_argument("--out", default="backtest_v2/results", help="output directory")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
    )

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    trades_csv = out_dir / f"trades_{stamp}.csv"
    summary_csv = out_dir / f"summary_{stamp}.csv"
    interval = "1h" if args.intraday else "1d"

    print("=" * 78)
    print(f"backtest_v2 — period={args.period} interval={interval} capital=₹{args.capital:,.0f} symbols={len(symbols)}")
    print(f"strategies: {', '.join(STRATEGIES.keys())}")
    print(f"liquidity tier: {args.liquidity} | mode: {'intraday' if args.intraday else 'delivery/swing'}")
    print("=" * 78)

    print("Fetching data...")
    df_by_symbol = fetch_universe(symbols, period=args.period, interval=interval, use_cache=True)
    print(f"Fetched {len(df_by_symbol)}/{len(symbols)} symbols\n")

    print("Generating signals...")
    all_signals = []
    for sym, df in df_by_symbol.items():
        all_signals.extend(run_all_strategies(sym, df))
    print(f"Total signals: {len(all_signals)}\n")

    print("Simulating trades...")
    trades = simulate_all(
        all_signals,
        df_by_symbol,
        capital_per_trade=args.capital,
        is_intraday=args.intraday,
        liquidity_tier=args.liquidity,
    )
    print(f"Trades executed: {len(trades)}\n")

    # ── Aggregates ──
    by_strat: dict[str, list] = {}
    for t in trades:
        by_strat.setdefault(t.strategy, []).append(t)

    print("=" * 78)
    print(f"{'Strategy':<25} {'Trades':>6} {'WR%':>6} {'Gross':>10} {'Charges':>10} {'Net':>10} {'EdgePerTrade':>12}")
    print("=" * 78)

    summary_rows = []
    for strat, ts in sorted(by_strat.items()):
        wins = sum(1 for t in ts if t.win)
        wr = (wins / len(ts) * 100) if ts else 0
        gross = sum(t.gross_pnl for t in ts)
        charges = sum(t.charges for t in ts)
        net = sum(t.net_pnl for t in ts)
        epp = (net / len(ts)) if ts else 0
        verdict = "WINNER" if net > 0 else "LOSER"
        print(f"{strat:<25} {len(ts):>6} {wr:>5.1f}% ₹{gross:>9.0f} ₹{charges:>9.0f} ₹{net:>9.0f} ₹{epp:>11.0f}  [{verdict}]")
        summary_rows.append({
            "strategy": strat,
            "trades": len(ts),
            "wins": wins,
            "win_pct": round(wr, 1),
            "gross_pnl": round(gross, 2),
            "charges": round(charges, 2),
            "net_pnl": round(net, 2),
            "edge_per_trade": round(epp, 2),
            "verdict": verdict,
        })

    print("=" * 78)
    total_n = len(trades)
    total_wins = sum(1 for t in trades if t.win)
    total_wr = (total_wins / total_n * 100) if total_n else 0
    total_gross = sum(t.gross_pnl for t in trades)
    total_charges = sum(t.charges for t in trades)
    total_net = sum(t.net_pnl for t in trades)
    print(f"{'TOTAL':<25} {total_n:>6} {total_wr:>5.1f}% ₹{total_gross:>9.0f} ₹{total_charges:>9.0f} ₹{total_net:>9.0f}")
    print()

    # ── Distribution check (Audit Check 8) ──
    print("Distribution check — top 2 trades as % of total P&L:")
    for strat, ts in sorted(by_strat.items()):
        if not ts:
            continue
        sorted_pnl = sorted([t.net_pnl for t in ts], reverse=True)
        top2 = sum(sorted_pnl[:2])
        total = sum(sorted_pnl)
        if total != 0:
            pct = abs(top2 / total) * 100
            flag = "🔴 LOTTERY" if pct >= 75 else "🟡 CONCENTRATED" if pct >= 50 else "🟢 DISTRIBUTED"
            print(f"  {strat:<25} top2/total = {pct:5.1f}%  {flag}")
    print()

    # ── Sample size check (Audit Check 6) ──
    print("Sample size check — n>=100 institutional minimum:")
    for strat, ts in sorted(by_strat.items()):
        n = len(ts)
        flag = "🟢 OK" if n >= 100 else "🟡 LOW" if n >= 30 else "🔴 INSUFFICIENT"
        print(f"  {strat:<25} n={n}  {flag}")
    print()

    # ── Write CSVs ──
    if trades:
        with open(trades_csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=trades[0].as_dict().keys())
            w.writeheader()
            for t in trades:
                w.writerow(t.as_dict())
        print(f"Trades CSV: {trades_csv}")

    if summary_rows:
        with open(summary_csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
            w.writeheader()
            w.writerows(summary_rows)
        print(f"Summary CSV: {summary_csv}")


if __name__ == "__main__":
    main()
