"""
HRVM out-of-sample test — Day 10 Phase 1.

After 2026-05-11 audit, top-5 configs passed the full 24mo audit (44 candidates total).
This script splits those signals into TRAIN (pre-2026) and TEST (2026 only) and reports
edge per period for each top config.

Pass criteria for 2026 standalone:
- n >= 30 (relaxed from n>=100 because 2026 is partial year)
- Positive edge per trade (after Indian retail charges)
- Top-2 trades < 50% of net (distribution check)

Fail = HRVM is curve-fit to 2024-25 regimes. Escalate Path 2/3 to owner.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest_v2.data import fetch_universe
from backtest_v2.strategies import HrvmParams, hrvm
from backtest_v2.runner import simulate_all
from nifty500 import get_nifty500_symbols


# Top-5 candidates from 2026-05-11 audit (in order by edge)
TOP5_CONFIGS = [
    HrvmParams(min_rvol=2.0, min_close_pos=0.5, min_annual_range=1.3, min_pct_of_yr_high=0.7, sl_atr_mult=2.5, target_rr=3.0),
    HrvmParams(min_rvol=2.0, min_close_pos=0.5, min_annual_range=1.2, min_pct_of_yr_high=0.7, sl_atr_mult=2.5, target_rr=3.0),
    HrvmParams(min_rvol=2.0, min_close_pos=0.6, min_annual_range=1.3, min_pct_of_yr_high=0.7, sl_atr_mult=2.5, target_rr=3.0),
    HrvmParams(min_rvol=2.0, min_close_pos=0.6, min_annual_range=1.2, min_pct_of_yr_high=0.7, sl_atr_mult=2.5, target_rr=3.0),
    HrvmParams(min_rvol=2.0, min_close_pos=0.5, min_annual_range=1.3, min_pct_of_yr_high=0.6, sl_atr_mult=2.5, target_rr=3.0),
]

# Test boundary: signals with date >= TEST_START are OOS test
import pandas as pd
TEST_START = pd.Timestamp("2026-01-01")


def _metrics(trades, label):
    if not trades:
        return {"label": label, "n": 0, "skip": "no trades"}
    n = len(trades)
    wins = sum(1 for t in trades if t.win)
    wr = wins / n * 100
    net = sum(t.net_pnl for t in trades)
    epp = net / n
    sorted_pnl = sorted([t.net_pnl for t in trades], reverse=True)
    top2 = sum(sorted_pnl[:2])
    top2_pct = abs(top2 / net * 100) if net != 0 else 0
    return {
        "label": label,
        "n": n,
        "wr": round(wr, 1),
        "net": round(net, 0),
        "epp": round(epp, 1),
        "top2_pct": round(top2_pct, 1),
    }


def evaluate_config(params: HrvmParams, df_by_symbol: dict, symbols: list[str]) -> dict:
    # Generate signals on FULL 36mo data (signal generation uses warmup correctly)
    all_signals = []
    for sym in symbols:
        df = df_by_symbol.get(sym)
        if df is not None:
            all_signals.extend(hrvm(sym, df, params))

    # Split signals by date (handle tz-aware vs tz-naive cleanly)
    def _is_train(sig_date):
        boundary = TEST_START.tz_localize(sig_date.tz) if sig_date.tz is not None else TEST_START
        return sig_date < boundary

    train_sigs = [s for s in all_signals if _is_train(s.date)]
    test_sigs = [s for s in all_signals if not _is_train(s.date)]

    train_trades = simulate_all(
        train_sigs, df_by_symbol,
        capital_per_trade=15000, is_intraday=False, liquidity_tier="mid_cap",
    )
    test_trades = simulate_all(
        test_sigs, df_by_symbol,
        capital_per_trade=15000, is_intraday=False, liquidity_tier="mid_cap",
    )

    return {
        "label": params.label(),
        "train": _metrics(train_trades, "train (pre-2026)"),
        "test": _metrics(test_trades, "test (2026 only)"),
    }


def _passes_oos(test_metrics: dict) -> tuple[bool, str]:
    """Pass criteria for 2026 standalone."""
    if test_metrics.get("skip"):
        return False, "no test trades"
    if test_metrics["n"] < 30:
        return False, f"n={test_metrics['n']} < 30"
    if test_metrics["epp"] <= 0:
        return False, f"edge ₹{test_metrics['epp']} <= 0"
    if test_metrics["top2_pct"] >= 50:
        return False, f"top2 {test_metrics['top2_pct']}% >= 50%"
    return True, "PASS"


def main():
    print("=" * 80)
    print("HRVM out-of-sample test — top-5 configs, train pre-2026 / test 2026")
    print("=" * 80)

    symbols = get_nifty500_symbols()[:100]
    print(f"\nFetching {len(symbols)} symbols × 3y daily (yfinance max-per-period)...")
    # 3y = 36mo, gives ~24mo train + 12mo test with warmup space
    df_by_symbol = fetch_universe(symbols, period="3y", use_cache=True)
    print(f"Got {len(df_by_symbol)} OK\n")

    # Check data coverage
    sample = next(iter(df_by_symbol.values()))
    print(f"Data range sample: {sample.index[0].date()} -> {sample.index[-1].date()}\n")

    results = []
    for k, p in enumerate(TOP5_CONFIGS, 1):
        print(f"[{k}/5] Evaluating {p.label()}...")
        r = evaluate_config(p, df_by_symbol, list(df_by_symbol.keys()))
        results.append(r)
        train = r["train"]
        test = r["test"]
        passed, reason = _passes_oos(test)
        print(f"     TRAIN: n={train.get('n', 0):>4} | edge ₹{train.get('epp', 0):>+6} | WR {train.get('wr', 0):>5}%")
        print(f"     TEST:  n={test.get('n', 0):>4} | edge ₹{test.get('epp', 0):>+6} | WR {test.get('wr', 0):>5}% | top2 {test.get('top2_pct', 0):>5}% | {'PASS' if passed else 'FAIL'} ({reason})")
        print()

    # Verdict summary
    print("=" * 80)
    print("VERDICT SUMMARY")
    print("=" * 80)
    passing_configs = []
    for r in results:
        passed, reason = _passes_oos(r["test"])
        status = "🟢 PASS" if passed else "🔴 FAIL"
        print(f"  {status}  {r['label']:<70} {reason}")
        if passed:
            passing_configs.append(r)

    print()
    if passing_configs:
        best = max(passing_configs, key=lambda r: r["test"]["epp"])
        print(f"🟢 OOS PASS — {len(passing_configs)}/{len(results)} configs survived 2026 isolation.")
        print(f"\nBest OOS config: {best['label']}")
        print(f"  Test n={best['test']['n']}, WR {best['test']['wr']}%, edge ₹{best['test']['epp']}/trade, top2 {best['test']['top2_pct']}%")
        print(f"  Train n={best['train']['n']}, WR {best['train']['wr']}%, edge ₹{best['train']['epp']}/trade")
        print(f"\nNext: walk-forward + cost-stress on this config (Day 11 Wed).")
    else:
        print("🔴 OOS FAIL — 0/5 configs survived 2026 isolation.")
        print("\nThe 2026-05-11 audit pass was driven by 2024-25 regimes; 2026 is structurally different.")
        print("HRVM does NOT have edge that generalizes. Escalate Path 2 (options) vs Path 3 (abandon) to owner.")


if __name__ == "__main__":
    main()
