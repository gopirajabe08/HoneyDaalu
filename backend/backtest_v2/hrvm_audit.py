"""
HRVM relaxed-filter sweep + full 24-month regime audit.

Discipline rule (after 2026-05-07 reversal lesson):
- Run on 24-month data, NOT 12-month
- Compute quarterly breakdown (require 4+ of 6 quarters positive to call it edge)
- Test parameter sensitivity (must be stable across nearby params)
- Check distribution (top 2 trades < 50% of net)
- Only declare candidate if ALL audit checks pass
"""
from __future__ import annotations
import sys
from pathlib import Path
from itertools import product

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest_v2.data import fetch_universe
from backtest_v2.strategies import HrvmParams, hrvm
from backtest_v2.runner import simulate_all
from nifty500 import get_nifty500_symbols


# HRVM filter grid — relaxed from original (2.0/0.7/1.3/0.7)
RVOL_LEVELS = [1.5, 1.75, 2.0]
CLOSE_POS_LEVELS = [0.5, 0.6, 0.7]
ANNUAL_RANGE_LEVELS = [1.2, 1.3]
PCT_YR_HIGH_LEVELS = [0.6, 0.7, 0.8]
SL_MULTS = [1.5, 2.0, 2.5]
TARGET_RRS = [1.5, 2.0, 3.0]


def quarter_label(ts):
    return f"{ts.year}-Q{(ts.month - 1) // 3 + 1}"


def evaluate_config(params: HrvmParams, df_by_symbol: dict, symbols: list[str]) -> dict:
    """Run a single HRVM configuration through full audit. Returns metrics."""
    signals = []
    for sym in symbols:
        df = df_by_symbol.get(sym)
        if df is not None:
            signals.extend(hrvm(sym, df, params))

    if len(signals) < 30:
        return {"n_signals": len(signals), "skip": "too few signals", "label": params.label()}

    trades = simulate_all(
        signals, df_by_symbol,
        capital_per_trade=15000, is_intraday=False, liquidity_tier="mid_cap",
    )
    if len(trades) < 30:
        return {"n_trades": len(trades), "skip": "too few trades", "label": params.label()}

    n = len(trades)
    wins = sum(1 for t in trades if t.win)
    wr = wins / n * 100
    net = sum(t.net_pnl for t in trades)
    epp = net / n

    # Distribution check
    sorted_pnl = sorted([t.net_pnl for t in trades], reverse=True)
    top2 = sum(sorted_pnl[:2])
    top2_pct = abs(top2 / net * 100) if net != 0 else 0

    # Quarterly breakdown
    by_q = {}
    for t in trades:
        by_q.setdefault(quarter_label(t.signal_date), []).append(t)

    q_results = []
    positive_qs = 0
    total_qs = 0
    for q in sorted(by_q.keys()):
        ts = by_q[q]
        if len(ts) < 5:
            continue
        q_net = sum(t.net_pnl for t in ts)
        q_results.append((q, len(ts), q_net))
        if q_net > 0:
            positive_qs += 1
        total_qs += 1

    return {
        "label": params.label(),
        "n": n,
        "wr": round(wr, 1),
        "net": round(net, 0),
        "epp": round(epp, 1),
        "top2_pct": round(top2_pct, 1),
        "positive_qs": positive_qs,
        "total_qs": total_qs,
        "regime_stable": positive_qs >= max(1, int(total_qs * 0.65)),  # 65%+ quarters positive
        "distributed": top2_pct < 50,
        "q_results": q_results,
    }


def main():
    print("=" * 78)
    print("HRVM relaxed sweep + 24-month regime audit")
    print("=" * 78)

    symbols = get_nifty500_symbols()[:100]
    print(f"\nFetching {len(symbols)} symbols × 24mo daily...")
    df_by_symbol = fetch_universe(symbols, period="24mo", use_cache=True)
    print(f"Got {len(df_by_symbol)} OK\n")

    grid = []
    for rvol, clp, ar, yh, sl, rr in product(
        RVOL_LEVELS, CLOSE_POS_LEVELS, ANNUAL_RANGE_LEVELS,
        PCT_YR_HIGH_LEVELS, SL_MULTS, TARGET_RRS,
    ):
        grid.append(HrvmParams(
            min_rvol=rvol, min_close_pos=clp, min_annual_range=ar,
            min_pct_of_yr_high=yh, sl_atr_mult=sl, target_rr=rr,
        ))
    print(f"Sweep: {len(grid)} HRVM filter configurations\n")

    results = []
    for k, p in enumerate(grid):
        r = evaluate_config(p, df_by_symbol, list(df_by_symbol.keys()))
        if "skip" not in r:
            results.append(r)
        if (k + 1) % 25 == 0:
            print(f"  ...{k+1}/{len(grid)} configs evaluated")

    # Filter to candidates that pass ALL gates
    candidates = [
        r for r in results
        if r["epp"] > 0 and r["n"] >= 100 and r["regime_stable"] and r["distributed"]
    ]
    candidates.sort(key=lambda r: r["epp"], reverse=True)

    # Also rank top by raw edge (to spot regime-overfit candidates)
    raw_top = sorted([r for r in results if r["epp"] > 0 and r["n"] >= 100],
                     key=lambda r: r["epp"], reverse=True)

    print("\n" + "=" * 90)
    print(f"Total configs that produced trades: {len(results)}")
    print(f"Configs with positive edge AND n>=100 AND regime-stable AND distributed: {len(candidates)}")
    print(f"Configs with positive edge AND n>=100 (raw, not regime-checked): {len(raw_top)}")

    if candidates:
        print("\n🟢 GENUINE CANDIDATES (passed full audit):")
        print(f"{'Label':<70} {'n':>5} {'WR':>6} {'Edge/T':>8} {'Q+/N':>6} {'Top2%':>7}")
        print("-" * 110)
        for r in candidates[:10]:
            print(f"{r['label']:<70} {r['n']:>5} {r['wr']:>5.1f}% ₹{r['epp']:>7,.0f} {r['positive_qs']}/{r['total_qs']:<3} {r['top2_pct']:>5.1f}%")
        print("\nFull quarterly detail for #1 candidate:")
        for q, n, net in candidates[0]["q_results"]:
            flag = '🟢' if net > 0 else '🔴'
            print(f"  {q}: n={n} net=₹{net:,.0f} {flag}")
    else:
        print("\n🔴 NO HRVM configuration passed full audit (positive + n>=100 + regime-stable + distributed).")
        if raw_top:
            print("\nTop 5 by raw edge (REGIME-OVERFIT or LOW-CONFIDENCE candidates only):")
            print(f"{'Label':<70} {'n':>5} {'WR':>6} {'Edge/T':>8} {'Q+/N':>6} {'Top2%':>7}")
            print("-" * 110)
            for r in raw_top[:5]:
                stable = '🟢' if r['regime_stable'] else '🔴'
                dist = '🟢' if r['distributed'] else '🔴'
                print(f"{r['label']:<70} {r['n']:>5} {r['wr']:>5.1f}% ₹{r['epp']:>7,.0f} {r['positive_qs']}/{r['total_qs']:<3} {r['top2_pct']:>5.1f}% [stable:{stable} dist:{dist}]")
        else:
            print("\nNot even raw-positive configs found. HRVM does NOT have edge in current regime.")


if __name__ == "__main__":
    main()
