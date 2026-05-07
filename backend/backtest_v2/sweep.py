"""
Parameter sensitivity sweep for play1 / play2.

Runs all parameter combinations through the v2 pipeline and ranks results.
Day 7-9 of Path C — addresses Audit Check 7 (parameter stability) AND
gives us our best shot at finding any positive-expectancy variant of the
existing strategies before falling back to new strategy families.
"""
from __future__ import annotations
import sys
from pathlib import Path
from itertools import product

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest_v2.data import fetch_universe
from backtest_v2.strategies import StrategyParams, play1_ema_crossover, play2_triple_ma
from backtest_v2.runner import simulate_all


# ── Sweep grid ──
EMA_PAIRS = [
    (5, 15),
    (9, 21),     # original
    (12, 26),
    (20, 50),
]
SMA_TRENDS = [50, 100, 200]
SL_MULTS = [1.5, 2.0, 2.5]
TARGET_RRS = [1.5, 2.0, 3.0]
VOLUME_FILTER = [False, True]
REGIME_FILTER = [False, True]


def build_param_grid() -> list[StrategyParams]:
    grid = []
    for (ef, es), st, sl, rr, vf, rf in product(
        EMA_PAIRS, SMA_TRENDS, SL_MULTS, TARGET_RRS, VOLUME_FILTER, REGIME_FILTER
    ):
        if ef >= es:
            continue
        grid.append(StrategyParams(
            ema_fast=ef, ema_slow=es, sma_trend=st,
            sl_atr_mult=sl, target_rr=rr,
            require_volume_filter=vf,
            require_regime_filter=rf,
        ))
    return grid


def run_sweep(symbols: list[str], period: str = "12mo", capital: float = 15000):
    print(f"Fetching {len(symbols)} symbols, period={period}...")
    df_by_symbol = fetch_universe(symbols, period=period, interval="1d", use_cache=True)
    print(f"Fetched {len(df_by_symbol)}/{len(symbols)} OK\n")

    grid = build_param_grid()
    print(f"Sweeping {len(grid)} parameter combinations × 2 strategies = {len(grid)*2} configurations\n")

    rows = []
    for strat_name, strat_fn in [("play1", play1_ema_crossover), ("play2", play2_triple_ma)]:
        print(f"\n=== {strat_name} sweep ===")
        for k, params in enumerate(grid):
            signals = []
            for sym, df in df_by_symbol.items():
                signals.extend(strat_fn(sym, df, params))
            if not signals:
                continue
            trades = simulate_all(
                signals, df_by_symbol,
                capital_per_trade=capital,
                is_intraday=False,
                liquidity_tier="mid_cap",
            )
            if not trades:
                continue
            n = len(trades)
            wins = sum(1 for t in trades if t.win)
            wr = wins / n * 100
            net = sum(t.net_pnl for t in trades)
            epp = net / n
            rows.append({
                "strategy": strat_name,
                "label": params.label(),
                "n": n,
                "wr": round(wr, 1),
                "net_pnl": round(net, 0),
                "edge_per_trade": round(epp, 1),
            })
            if (k + 1) % 25 == 0:
                print(f"  {k+1}/{len(grid)} configs done...")

    # Rank by edge_per_trade
    rows.sort(key=lambda r: r["edge_per_trade"], reverse=True)

    print("\n" + "=" * 100)
    print(f"{'Strategy':<8} {'Params':<55} {'n':>5} {'WR':>5} {'Net':>10} {'Edge/T':>8}")
    print("=" * 100)
    for r in rows[:30]:
        flag = "🟢" if r["edge_per_trade"] > 0 and r["n"] >= 100 else ("🟡" if r["edge_per_trade"] > 0 else "🔴")
        print(f"{r['strategy']:<8} {r['label']:<55} {r['n']:>5} {r['wr']:>4.1f}% ₹{r['net_pnl']:>9,.0f} ₹{r['edge_per_trade']:>7,.0f} {flag}")

    print("=" * 100)
    print(f"\nTotal configs tested: {len(rows)}")
    positives = [r for r in rows if r["edge_per_trade"] > 0 and r["n"] >= 100]
    print(f"Positive-edge configs (n>=100): {len(positives)}")
    if positives:
        best = positives[0]
        print(f"\n🏆 BEST: {best['strategy']} {best['label']}")
        print(f"   n={best['n']}  WR={best['wr']}%  Net=₹{best['net_pnl']:,.0f}  Edge=₹{best['edge_per_trade']:,.0f}/trade")
    else:
        print("\n🔴 NO POSITIVE-EXPECTANCY VARIANT FOUND across the parameter grid.")
        print("   Track 1 (parameter sensitivity) does not save play1/play2.")
        print("   Move to Track 2: new strategy families.")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=20, help="Number of stocks (default 20 large caps)")
    p.add_argument("--period", default="12mo")
    args = p.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from nifty500 import get_nifty500_symbols
    symbols = get_nifty500_symbols()[:args.n]
    run_sweep(symbols, period=args.period)
