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


# ── Default strategy parameters ──
EMA_FAST = 9
EMA_SLOW = 21
SMA_TREND = 50
SL_ATR_MULTIPLIER = 2.0
TARGET_RR = 2.0   # Risk:Reward ratio


@dataclass
class StrategyParams:
    """Configurable parameters for parameter sweep / sensitivity testing."""
    ema_fast: int = EMA_FAST
    ema_slow: int = EMA_SLOW
    sma_trend: int = SMA_TREND
    sl_atr_mult: float = SL_ATR_MULTIPLIER
    target_rr: float = TARGET_RR
    require_volume_filter: bool = False  # signal vol > 1.5x avg
    volume_filter_mult: float = 1.5
    require_regime_filter: bool = False  # only BUY when bullish, SELL when bearish

    def label(self) -> str:
        parts = [f"({self.ema_fast},{self.ema_slow},{self.sma_trend})"]
        parts.append(f"sl{self.sl_atr_mult:g}rr{self.target_rr:g}")
        if self.require_volume_filter:
            parts.append(f"vol{self.volume_filter_mult:g}")
        if self.require_regime_filter:
            parts.append("regime")
        return "-".join(parts)


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


def _add_indicators(df: pd.DataFrame, params: StrategyParams = None) -> pd.DataFrame:
    """Add EMAs, SMA, ATR, and volume average. Returns new df (does not mutate)."""
    p = params or StrategyParams()
    out = df.copy()
    out["ema_fast"] = out["Close"].ewm(span=p.ema_fast, adjust=False).mean()
    out["ema_slow"] = out["Close"].ewm(span=p.ema_slow, adjust=False).mean()
    out["sma_trend"] = out["Close"].rolling(p.sma_trend).mean()
    out["atr14"] = _calc_atr(out, 14)
    if "Volume" in out.columns:
        out["vol_avg20"] = out["Volume"].rolling(20).mean()
    return out


def play1_ema_crossover(symbol: str, df: pd.DataFrame, params: StrategyParams = None) -> list[Signal]:
    """
    Play 1: EMA-fast / EMA-slow crossover with SMA-trend filter.
    Optional regime + volume filters.
    """
    p = params or StrategyParams()
    if df is None or len(df) < p.sma_trend + 5:
        return []

    d = _add_indicators(df, p)
    signals: list[Signal] = []
    label = f"play1_ema_crossover[{p.label()}]"

    start = p.sma_trend + 1
    end = len(d) - 1
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

        if p.require_volume_filter and "vol_avg20" in d.columns:
            if pd.isna(row["vol_avg20"]) or row["vol_avg20"] <= 0:
                continue
            if row["Volume"] < row["vol_avg20"] * p.volume_filter_mult:
                continue

        sig_kwargs = dict(
            date=d.index[i],
            symbol=symbol,
            strategy=label,
            signal_close=float(row["Close"]),
            sl_distance=float(row["atr14"] * p.sl_atr_mult),
            target_rr=p.target_rr,
            conviction=0.0,
        )

        if cross_up and bullish:
            signals.append(Signal(side="BUY", **sig_kwargs))
        elif cross_dn and bearish:
            if p.require_regime_filter:
                continue  # only allow SELL in bearish regime; already checked
            signals.append(Signal(side="SELL", **sig_kwargs))

    return signals


def play2_triple_ma(symbol: str, df: pd.DataFrame, params: StrategyParams = None) -> list[Signal]:
    """Play 2: Triple-MA alignment crossover. Now parameter-configurable."""
    p = params or StrategyParams()
    if df is None or len(df) < p.sma_trend + 5:
        return []

    d = _add_indicators(df, p)
    signals: list[Signal] = []
    label = f"play2_triple_ma[{p.label()}]"

    start = p.sma_trend + 1
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

        if p.require_volume_filter and "vol_avg20" in d.columns:
            if pd.isna(row["vol_avg20"]) or row["vol_avg20"] <= 0:
                continue
            if row["Volume"] < row["vol_avg20"] * p.volume_filter_mult:
                continue

        sig_kwargs = dict(
            date=d.index[i],
            symbol=symbol,
            strategy=label,
            signal_close=float(row["Close"]),
            sl_distance=float(row["atr14"] * p.sl_atr_mult),
            target_rr=p.target_rr,
            conviction=0.0,
        )

        if bull_now and not bull_prev:
            signals.append(Signal(side="BUY", **sig_kwargs))
        elif bear_now and not bear_prev:
            if p.require_regime_filter:
                continue
            signals.append(Signal(side="SELL", **sig_kwargs))

    return signals


@dataclass
class HrvmParams:
    """HRVM-specific tunable filters (separate from generic StrategyParams)."""
    min_rvol: float = 2.0          # min relative volume
    min_close_pos: float = 0.7     # close must be in upper N% of day range
    min_annual_range: float = 1.3  # year_high / year_low >=
    min_pct_of_yr_high: float = 0.7  # close >= N% of 52-week high

    sl_atr_mult: float = 2.0
    target_rr: float = 2.0

    def label(self) -> str:
        return (
            f"rvol{self.min_rvol:g}-clp{self.min_close_pos:g}-"
            f"yr{self.min_annual_range:g}-yh{self.min_pct_of_yr_high:g}-"
            f"sl{self.sl_atr_mult:g}rr{self.target_rr:g}"
        )


def hrvm(symbol: str, df: pd.DataFrame, params=None) -> list[Signal]:
    """
    HRVM — High Relative Volume Momentum (candidate proposed 2026-04-29).

    Now accepts HrvmParams for filter tuning. Defaults match original spec.
    """
    if params is None:
        p = HrvmParams()
    elif isinstance(params, StrategyParams):
        # Caller passed generic params; bridge to HRVM defaults using sl/rr only
        p = HrvmParams(sl_atr_mult=params.sl_atr_mult, target_rr=params.target_rr)
    else:
        p = params

    if df is None or len(df) < 252 + 5:
        return []

    d = df.copy()
    d["vol_avg20"] = d["Volume"].rolling(20).mean()
    d["yr_high"] = d["High"].rolling(252).max()
    d["yr_low"] = d["Low"].rolling(252).min()
    d["atr14"] = _calc_atr(d, 14)

    signals: list[Signal] = []
    label = f"hrvm[{p.label()}]"

    start = 252 + 1
    end = len(d) - 1
    for i in range(start, end):
        row = d.iloc[i]
        prev = d.iloc[i - 1]

        if pd.isna(row["vol_avg20"]) or pd.isna(row["yr_high"]) or pd.isna(row["atr14"]):
            continue
        if row["vol_avg20"] <= 0 or row["yr_low"] <= 0 or row["atr14"] <= 0:
            continue

        rvol = row["Volume"] / row["vol_avg20"]
        if rvol < p.min_rvol:
            continue

        day_range = row["High"] - row["Low"]
        if day_range <= 0:
            continue
        close_pos = (row["Close"] - row["Low"]) / day_range
        if close_pos < p.min_close_pos:
            continue

        if row["Close"] <= prev["Close"]:
            continue

        annual_range = row["yr_high"] / row["yr_low"]
        if annual_range < p.min_annual_range:
            continue

        pct_of_yr_high = row["Close"] / row["yr_high"]
        if pct_of_yr_high < p.min_pct_of_yr_high:
            continue

        signals.append(Signal(
            date=d.index[i],
            symbol=symbol,
            strategy=label,
            side="BUY",
            signal_close=float(row["Close"]),
            sl_distance=float(row["atr14"] * p.sl_atr_mult),
            target_rr=p.target_rr,
            conviction=float(rvol),
        ))

    return signals


def atr_breakout(symbol: str, df: pd.DataFrame, params: StrategyParams = None) -> list[Signal]:
    """
    ATR Breakout — Donchian-channel-style 20-day high/low breakout.

    BUY  : Close above 20-day high
    SELL : Close below 20-day low
    Entry next bar open with ATR-based SL.
    """
    p = params or StrategyParams()
    if df is None or len(df) < 25:
        return []

    d = df.copy()
    d["dc_high"] = d["High"].rolling(20).max().shift(1)  # exclude today
    d["dc_low"] = d["Low"].rolling(20).min().shift(1)
    d["atr14"] = _calc_atr(d, 14)
    if "Volume" in d.columns:
        d["vol_avg20"] = d["Volume"].rolling(20).mean()

    signals: list[Signal] = []
    label = f"atr_breakout[{p.label()}]"

    start = 22
    end = len(d) - 1
    for i in range(start, end):
        row = d.iloc[i]

        if pd.isna(row["dc_high"]) or pd.isna(row["atr14"]) or row["atr14"] <= 0:
            continue

        if p.require_volume_filter and "vol_avg20" in d.columns:
            if pd.isna(row["vol_avg20"]) or row["vol_avg20"] <= 0:
                continue
            if row["Volume"] < row["vol_avg20"] * p.volume_filter_mult:
                continue

        broke_up = row["Close"] > row["dc_high"]
        broke_dn = row["Close"] < row["dc_low"]

        sig_kwargs = dict(
            date=d.index[i],
            symbol=symbol,
            strategy=label,
            signal_close=float(row["Close"]),
            sl_distance=float(row["atr14"] * p.sl_atr_mult),
            target_rr=p.target_rr,
            conviction=0.0,
        )

        if broke_up:
            signals.append(Signal(side="BUY", **sig_kwargs))
        elif broke_dn:
            signals.append(Signal(side="SELL", **sig_kwargs))

    return signals


def rsi2_mean_reversion(symbol: str, df: pd.DataFrame, params: StrategyParams = None) -> list[Signal]:
    """
    RSI-2 Mean Reversion — Larry Connors-style 2-period RSI extremes.

    BUY  : RSI(2) < 10 AND price > SMA200 (buy-the-dip in uptrend)
    SELL : RSI(2) > 90 AND price < SMA200 (short-the-rip in downtrend)
    """
    p = params or StrategyParams()
    if df is None or len(df) < 205:
        return []

    d = df.copy()
    delta = d["Close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    rs = gain.rolling(2).mean() / loss.rolling(2).mean()
    d["rsi2"] = 100 - (100 / (1 + rs))
    d["sma200"] = d["Close"].rolling(200).mean()
    d["atr14"] = _calc_atr(d, 14)

    signals: list[Signal] = []
    label = f"rsi2_mean_reversion[{p.label()}]"

    start = 202
    end = len(d) - 1
    for i in range(start, end):
        row = d.iloc[i]

        if pd.isna(row["rsi2"]) or pd.isna(row["sma200"]) or pd.isna(row["atr14"]):
            continue
        if row["atr14"] <= 0:
            continue

        sig_kwargs = dict(
            date=d.index[i],
            symbol=symbol,
            strategy=label,
            signal_close=float(row["Close"]),
            sl_distance=float(row["atr14"] * p.sl_atr_mult),
            target_rr=p.target_rr,
            conviction=0.0,
        )

        if row["rsi2"] < 10 and row["Close"] > row["sma200"]:
            signals.append(Signal(side="BUY", **sig_kwargs))
        elif row["rsi2"] > 90 and row["Close"] < row["sma200"]:
            signals.append(Signal(side="SELL", **sig_kwargs))

    return signals


# ── Strategy registry ──
STRATEGIES = {
    "play1_ema_crossover": play1_ema_crossover,
    "play2_triple_ma": play2_triple_ma,
    "hrvm": hrvm,
    "atr_breakout": atr_breakout,
    "rsi2_mean_reversion": rsi2_mean_reversion,
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
