"""
Strategy signal generation for backtest_v2.

CRITICAL DIFFERENCE from old backtest_with_charges.py:
- Signals are generated using ONLY data available at signal-bar close.
- Trade execution happens at NEXT-BAR OPEN (not signal-bar close).
- This eliminates the same-bar-close look-ahead bias (Audit Check 1 FAIL).

Each strategy outputs a list of Signal records:
    Signal(date, side, signal_close, sl_initial, target_initial, conviction)

The runner.py module then converts signals into Trade records by simulating
realistic execution at next-bar open + SL/target via OHLC walk-forward.

Strategies ported (from backtest_with_charges.py + strategies/):
- play1_ema_crossover (1d)
- play2_triple_ma (1d)

KILLED strategies (per 2026-05-04 audit) NOT ported:
- play3 (negative EV), play4 (negative EV), play5 (n=4 noise),
  play6 (n=2 noise), play7-10 + winning_horse.
"""
from __future__ import annotations
from dataclasses import dataclass
import pandas as pd


# ── Strategy parameters (fixed; sensitivity tested separately in audit.py) ──
EMA_FAST = 9
EMA_SLOW = 21
SMA_TREND = 50
SL_ATR_MULTIPLIER = 2.0
TARGET_RR = 2.0   # Risk:Reward ratio


@dataclass
class Signal:
    """A trade signal — points to entry intent + initial SL/target."""
    date: pd.Timestamp
    symbol: str
    strategy: str
    side: str            # "BUY" or "SELL"
    signal_close: float  # Close at signal bar (for diagnostic only — NOT entry price)
    sl_distance: float   # Initial SL distance (will become absolute SL after entry)
    target_rr: float     # Risk:Reward target multiplier
    conviction: float    # Optional ranking score


def _calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range — used for SL sizing."""
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add EMA9, EMA21, SMA50, ATR14 to df. Returns new df (does not mutate)."""
    out = df.copy()
    out["ema_fast"] = out["Close"].ewm(span=EMA_FAST, adjust=False).mean()
    out["ema_slow"] = out["Close"].ewm(span=EMA_SLOW, adjust=False).mean()
    out["sma_trend"] = out["Close"].rolling(SMA_TREND).mean()
    out["atr14"] = _calc_atr(out, 14)
    return out


def play1_ema_crossover(symbol: str, df: pd.DataFrame) -> list[Signal]:
    """
    Play 1: 9-EMA / 21-EMA crossover with 50-SMA trend filter.

    BUY  : EMA fast crosses above EMA slow AND price above SMA50 (trend confirmation)
    SELL : EMA fast crosses below EMA slow AND price below SMA50

    Critical: signal generated at bar i using indicators computed up to bar i.
    Entry happens at bar i+1 OPEN (handled by runner.py, not here).
    """
    if df is None or len(df) < SMA_TREND + 5:
        return []

    d = _add_indicators(df)
    signals: list[Signal] = []

    # Loop from where all indicators are valid; stop at penultimate bar
    # so runner.py has bar i+1 to execute against.
    start = SMA_TREND + 1
    end = len(d) - 1  # Need bar i+1 for execution
    for i in range(start, end):
        row = d.iloc[i]
        prev = d.iloc[i - 1]

        if pd.isna(row["ema_fast"]) or pd.isna(row["sma_trend"]) or pd.isna(row["atr14"]):
            continue
        if row["atr14"] <= 0:
            continue

        cross_up = (prev["ema_fast"] <= prev["ema_slow"]) and (row["ema_fast"] > row["ema_slow"])
        cross_dn = (prev["ema_fast"] >= prev["ema_slow"]) and (row["ema_fast"] < row["ema_slow"])
        bullish = row["Close"] > row["sma_trend"]
        bearish = row["Close"] < row["sma_trend"]

        if cross_up and bullish:
            signals.append(Signal(
                date=d.index[i],
                symbol=symbol,
                strategy="play1_ema_crossover",
                side="BUY",
                signal_close=float(row["Close"]),
                sl_distance=float(row["atr14"] * SL_ATR_MULTIPLIER),
                target_rr=TARGET_RR,
                conviction=0.0,
            ))
        elif cross_dn and bearish:
            signals.append(Signal(
                date=d.index[i],
                symbol=symbol,
                strategy="play1_ema_crossover",
                side="SELL",
                signal_close=float(row["Close"]),
                sl_distance=float(row["atr14"] * SL_ATR_MULTIPLIER),
                target_rr=TARGET_RR,
                conviction=0.0,
            ))

    return signals


def play2_triple_ma(symbol: str, df: pd.DataFrame) -> list[Signal]:
    """
    Play 2: Triple-MA alignment.

    BUY  : EMA9 > EMA21 > SMA50 (just crossed into this state) — bullish alignment
    SELL : EMA9 < EMA21 < SMA50 (just crossed into this state) — bearish alignment

    Same execution rules as play1 (signal at bar i, entry at bar i+1 open).
    """
    if df is None or len(df) < SMA_TREND + 5:
        return []

    d = _add_indicators(df)
    signals: list[Signal] = []

    start = SMA_TREND + 1
    end = len(d) - 1
    for i in range(start, end):
        row = d.iloc[i]
        prev = d.iloc[i - 1]

        if pd.isna(row["ema_fast"]) or pd.isna(row["sma_trend"]) or pd.isna(row["atr14"]):
            continue
        if row["atr14"] <= 0:
            continue

        bull_now = (row["ema_fast"] > row["ema_slow"]) and (row["ema_slow"] > row["sma_trend"])
        bull_prev = (prev["ema_fast"] > prev["ema_slow"]) and (prev["ema_slow"] > prev["sma_trend"])
        bear_now = (row["ema_fast"] < row["ema_slow"]) and (row["ema_slow"] < row["sma_trend"])
        bear_prev = (prev["ema_fast"] < prev["ema_slow"]) and (prev["ema_slow"] < prev["sma_trend"])

        if bull_now and not bull_prev:
            signals.append(Signal(
                date=d.index[i],
                symbol=symbol,
                strategy="play2_triple_ma",
                side="BUY",
                signal_close=float(row["Close"]),
                sl_distance=float(row["atr14"] * SL_ATR_MULTIPLIER),
                target_rr=TARGET_RR,
                conviction=0.0,
            ))
        elif bear_now and not bear_prev:
            signals.append(Signal(
                date=d.index[i],
                symbol=symbol,
                strategy="play2_triple_ma",
                side="SELL",
                signal_close=float(row["Close"]),
                sl_distance=float(row["atr14"] * SL_ATR_MULTIPLIER),
                target_rr=TARGET_RR,
                conviction=0.0,
            ))

    return signals


# ── Strategy registry ──
STRATEGIES = {
    "play1_ema_crossover": play1_ema_crossover,
    "play2_triple_ma": play2_triple_ma,
}


def run_all_strategies(symbol: str, df: pd.DataFrame) -> list[Signal]:
    """Convenience: run every registered strategy, return combined signal list."""
    out = []
    for name, fn in STRATEGIES.items():
        out.extend(fn(symbol, df))
    return out


# ── Self-test ──
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from backtest_v2.data import fetch_one

    sym = "RELIANCE"
    df = fetch_one(sym, period="12mo")
    if df is None:
        print(f"FAIL: no data for {sym}")
        sys.exit(1)

    p1 = play1_ema_crossover(sym, df)
    p2 = play2_triple_ma(sym, df)
    print(f"=== {sym} 12mo signal counts ===")
    print(f"play1_ema_crossover: {len(p1)} signals")
    print(f"play2_triple_ma:     {len(p2)} signals")
    if p1:
        print(f"\nFirst play1 signal: {p1[0]}")
    if p2:
        print(f"First play2 signal: {p2[0]}")
