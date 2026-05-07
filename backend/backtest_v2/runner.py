"""
Trade simulation runner — converts Signal records into realistic Trade records.

CRITICAL FIXES vs old backtest_with_charges.py:
1. Entry at NEXT-BAR OPEN (not signal-bar close) — closes Audit Check 1 (look-ahead)
2. Realistic slippage applied to entry (cost_model.compute_realistic_slippage)
3. Full Indian retail cost model (cost_model.compute_round_trip)
4. SL/target evaluated via walk-forward OHLC, not next_bar single check
5. Max holding period (default 20 bars for swing) — closes if neither SL nor target hit
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional

import pandas as pd

try:
    from .strategies import Signal
    from .cost_model import compute_round_trip, compute_realistic_slippage
except ImportError:
    # Allow running as standalone script: `python runner.py`
    from strategies import Signal
    from cost_model import compute_round_trip, compute_realistic_slippage


MAX_SWING_HOLDING_BARS = 20    # ~ 1 month for daily candles
DEFAULT_LIQUIDITY_TIER = "mid_cap"  # safe middle-of-road slippage assumption


@dataclass
class Trade:
    symbol: str
    strategy: str
    side: str
    signal_date: pd.Timestamp
    entry_date: pd.Timestamp
    entry_price: float       # After slippage applied
    qty: int
    stop_loss: float
    target: float
    exit_date: pd.Timestamp
    exit_price: float
    exit_reason: str         # "TARGET" | "SL" | "TIME" | "EOD"
    holding_bars: int
    gross_pnl: float
    charges: float
    net_pnl: float
    win: bool
    is_intraday: bool

    def as_dict(self) -> dict:
        d = asdict(self)
        d["signal_date"] = str(d["signal_date"])
        d["entry_date"] = str(d["entry_date"])
        d["exit_date"] = str(d["exit_date"])
        return d


def _quantity_for(capital: float, entry_price: float) -> int:
    """Cash-only sizing: floor(capital / entry_price). Min 1 share."""
    if entry_price <= 0:
        return 0
    return max(1, int(capital // entry_price))


def simulate_signal(
    signal: Signal,
    df: pd.DataFrame,
    capital: float,
    is_intraday: bool = False,
    liquidity_tier: str = DEFAULT_LIQUIDITY_TIER,
    max_holding_bars: int = MAX_SWING_HOLDING_BARS,
) -> Optional[Trade]:
    """
    Simulate execution of a single signal.

    Returns None if signal can't be executed (e.g., signal at last bar).
    """
    # Locate signal bar in df
    try:
        signal_idx = df.index.get_loc(signal.date)
    except KeyError:
        return None

    if signal_idx + 1 >= len(df):
        return None  # No next bar to enter on

    # ENTRY at next bar's OPEN (no look-ahead)
    entry_bar = df.iloc[signal_idx + 1]
    raw_entry = float(entry_bar["Open"])
    if raw_entry <= 0:
        return None

    slippage = compute_realistic_slippage(raw_entry, liquidity_tier=liquidity_tier)
    if signal.side == "BUY":
        entry_price = raw_entry + slippage
        sl = entry_price - signal.sl_distance
        target = entry_price + (signal.sl_distance * signal.target_rr)
    else:  # SELL
        entry_price = raw_entry - slippage
        sl = entry_price + signal.sl_distance
        target = entry_price - (signal.sl_distance * signal.target_rr)

    qty = _quantity_for(capital, entry_price)
    if qty <= 0:
        return None

    # Walk forward bar by bar from entry+1 to find exit
    exit_price = None
    exit_reason = None
    exit_date = None
    holding_bars = 0
    for j in range(signal_idx + 1, min(signal_idx + 1 + max_holding_bars, len(df))):
        bar = df.iloc[j]
        bar_high = float(bar["High"])
        bar_low = float(bar["Low"])
        bar_close = float(bar["Close"])
        holding_bars = j - signal_idx
        if signal.side == "BUY":
            if bar_low <= sl:
                exit_price = sl
                exit_reason = "SL"
                exit_date = df.index[j]
                break
            if bar_high >= target:
                exit_price = target
                exit_reason = "TARGET"
                exit_date = df.index[j]
                break
        else:  # SELL
            if bar_high >= sl:
                exit_price = sl
                exit_reason = "SL"
                exit_date = df.index[j]
                break
            if bar_low <= target:
                exit_price = target
                exit_reason = "TARGET"
                exit_date = df.index[j]
                break

    if exit_price is None:
        # Time-based exit at last bar's close (or final bar of holding window)
        last_idx = min(signal_idx + max_holding_bars, len(df) - 1)
        exit_price = float(df.iloc[last_idx]["Close"])
        exit_reason = "TIME"
        exit_date = df.index[last_idx]
        holding_bars = last_idx - signal_idx

    # Compute P&L
    if signal.side == "BUY":
        gross_pnl = (exit_price - entry_price) * qty
    else:
        gross_pnl = (entry_price - exit_price) * qty

    charges_obj = compute_round_trip(qty, entry_price, exit_price, is_intraday=is_intraday)
    net_pnl = gross_pnl - charges_obj.total

    return Trade(
        symbol=signal.symbol,
        strategy=signal.strategy,
        side=signal.side,
        signal_date=signal.date,
        entry_date=df.index[signal_idx + 1],
        entry_price=round(entry_price, 2),
        qty=qty,
        stop_loss=round(sl, 2),
        target=round(target, 2),
        exit_date=exit_date,
        exit_price=round(exit_price, 2),
        exit_reason=exit_reason,
        holding_bars=holding_bars,
        gross_pnl=round(gross_pnl, 2),
        charges=round(charges_obj.total, 2),
        net_pnl=round(net_pnl, 2),
        win=net_pnl > 0,
        is_intraday=is_intraday,
    )


def simulate_all(
    signals: list[Signal],
    df_by_symbol: dict[str, pd.DataFrame],
    capital_per_trade: float,
    is_intraday: bool = False,
    liquidity_tier: str = DEFAULT_LIQUIDITY_TIER,
    max_holding_bars: int = MAX_SWING_HOLDING_BARS,
) -> list[Trade]:
    """Simulate all signals across all symbols. Returns list of completed trades."""
    trades: list[Trade] = []
    for sig in signals:
        df = df_by_symbol.get(sig.symbol)
        if df is None:
            continue
        t = simulate_signal(
            sig, df,
            capital=capital_per_trade,
            is_intraday=is_intraday,
            liquidity_tier=liquidity_tier,
            max_holding_bars=max_holding_bars,
        )
        if t:
            trades.append(t)
    return trades


# ── Self-test ──
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from backtest_v2.data import fetch_one
    from backtest_v2.strategies import play1_ema_crossover, play2_triple_ma

    sym = "RELIANCE"
    df = fetch_one(sym, period="12mo")
    if df is None:
        sys.exit("no data")

    p1_signals = play1_ema_crossover(sym, df)
    p2_signals = play2_triple_ma(sym, df)
    all_signals = p1_signals + p2_signals
    df_by_sym = {sym: df}

    trades = simulate_all(all_signals, df_by_sym, capital_per_trade=15000, is_intraday=False)

    print(f"=== {sym} 12mo backtest_v2 ===")
    print(f"Signals: {len(all_signals)} | Trades executed: {len(trades)}")
    print()
    total_gross = sum(t.gross_pnl for t in trades)
    total_charges = sum(t.charges for t in trades)
    total_net = sum(t.net_pnl for t in trades)
    wins = sum(1 for t in trades if t.win)
    losses = len(trades) - wins
    win_rate = (wins / len(trades) * 100) if trades else 0
    print(f"Gross P&L: ₹{total_gross:.2f}")
    print(f"Charges:   ₹{total_charges:.2f}")
    print(f"Net P&L:   ₹{total_net:.2f}")
    print(f"Win rate:  {win_rate:.1f}% ({wins}W / {losses}L)")
    print()
    print("Per strategy:")
    by_strat: dict[str, list[Trade]] = {}
    for t in trades:
        by_strat.setdefault(t.strategy, []).append(t)
    for s, ts in by_strat.items():
        net = sum(t.net_pnl for t in ts)
        wins_s = sum(1 for t in ts if t.win)
        wr_s = (wins_s / len(ts) * 100) if ts else 0
        print(f"  {s}: n={len(ts)} | net=₹{net:.2f} | WR={wr_s:.1f}%")
    print()
    print("Trade detail:")
    for t in trades:
        print(f"  {t.signal_date.date()} {t.side:4} entry=₹{t.entry_price:.2f} exit=₹{t.exit_price:.2f} ({t.exit_reason:6}) net=₹{t.net_pnl:+8.2f} | {t.strategy}")
