"""
Play #3: VWAP Intraday Trend-Pullback
─────────────────────────────────────
Timeframe : 3-min or 5-min chart
Indicators: Session VWAP
Filter    : Trade 15 mins after open to 1 hour before close.

Setup Conditions (Long):
  Trend   : Price remains consistently above VWAP for at least 3-5 candles.
  Pullback: Price dips toward VWAP (tags it or slightly dips below).
  Trigger : Bullish reversal candle forms near VWAP.

Setup Conditions (Short):
  Trend   : Price remains consistently below VWAP for at least 3-5 candles.
  Pullback: Price rises toward VWAP (tags it or slightly exceeds).
  Trigger : Bearish reversal candle forms near VWAP.

Execution:
  Entry  : Buy/Sell on the break of the trigger candle's high/low.
  SL     : Just beyond the swing extreme of the pullback.
  Targets: T1 at the last intraday swing extreme.
           T2 at a fixed 1:2 or 1:3 risk-reward ratio.
"""

import pandas as pd
from typing import Optional

from .base import (
    BaseStrategy,
    calc_vwap,
    has_bullish_reversal,
    has_bearish_reversal,
    find_recent_swing_high,
    find_recent_swing_low,
    atr_stop_loss,
    get_strategy_config,
)

_KEY = "play3_vwap_pullback"


class VWAPPullback(BaseStrategy):
    name = "VWAP Intraday Trend-Pullback"
    description = "Pullback to VWAP in an intraday uptrend with bullish reversal confirmation."
    category = "Intraday Precision (Session Trading)"
    indicators = ["Session VWAP"]
    timeframes = ["3m", "5m"]
    long_setup = "Price above VWAP for 3-5 candles, then dips to VWAP. Bullish reversal candle near VWAP (Hammer, Engulfing, strong green)."
    short_setup = "Price below VWAP for 3-5 candles, then rises to VWAP. Bearish reversal candle near VWAP (Shooting Star, Engulfing, strong red)."
    exit_rules = "T1 at last intraday swing high. T2 at 1:2 or 1:3 risk-reward."
    stop_loss_rules = "Just below the swing low of the pullback (a few ticks below VWAP zone)."

    def scan(self, df: pd.DataFrame, symbol: str) -> Optional[dict]:
        if len(df) < 15:
            return None

        df = df.copy()
        df["vwap"] = calc_vwap(df)

        if len(df) < 8:
            return None

        # ── Validate VWAP is computed ──
        if pd.isna(df["vwap"].iloc[-1]):
            return None

        # Try long first, then short
        result = self._scan_long(df, symbol)
        if result:
            return result
        return self._scan_short(df, symbol)

    def _scan_long(self, df: pd.DataFrame, symbol: str) -> Optional[dict]:
        """Scan for LONG (buy) signal: pullback DOWN to VWAP in an uptrend."""
        last = df.iloc[-1]
        prev = df.iloc[-2]

        # ── Trend: Price was consistently above VWAP for 3-5 candles before pullback ──
        trending_candles = df.iloc[-8:-3]
        above_vwap_count = (trending_candles["Close"] > trending_candles["vwap"]).sum()
        if above_vwap_count < 3:
            return None

        # ── Pullback: Recent candle(s) dip toward VWAP ──
        pullback_zone = df.iloc[-3:-1]
        touched_vwap = any(
            row["Low"] <= row["vwap"] * 1.002
            for _, row in pullback_zone.iterrows()
        )
        if not touched_vwap:
            return None

        # ── Trigger: Bullish reversal candle near VWAP ──
        if not has_bullish_reversal(last, prev):
            return None

        # Last candle should be near VWAP (within 0.5%)
        if last["Low"] > last["vwap"] * 1.005:
            return None

        # ── Entry & Targets ──
        entry = last["High"]  # break of trigger candle's high
        swing_sl = find_recent_swing_low(df.tail(10), lookback=10)
        vwap_sl = last["vwap"] * 0.998  # a few ticks below VWAP
        cfg = get_strategy_config(_KEY)
        atr_sl = atr_stop_loss(df, entry, side="BUY", atr_mult=cfg["atr_mult"], min_pct=cfg["min_pct"])
        sl = min(swing_sl, vwap_sl, atr_sl)  # use the widest (most protective) SL

        risk = entry - sl
        if risk <= 0:
            return None

        target1 = find_recent_swing_high(df.iloc[:-3], lookback=15)
        if target1 <= entry:
            target1 = entry + risk * 2
        target2 = entry + risk * 3  # 1:3 R:R

        return {
            "symbol": symbol,
            "signal_type": "BUY",
            "entry_price": round(entry, 2),
            "stop_loss": round(sl, 2),
            "target_1": round(target1, 2),
            "target_2": round(target2, 2),
            "risk": round(risk, 2),
            "reward": round(target1 - entry, 2),
            "risk_reward_ratio": "1:2",
            "current_price": round(last["Close"], 2),
            "strategy": "play3_vwap_pullback",
        }

    def _scan_short(self, df: pd.DataFrame, symbol: str) -> Optional[dict]:
        """Scan for SHORT (sell) signal: pullback UP to VWAP in a downtrend."""
        last = df.iloc[-1]
        prev = df.iloc[-2]

        # ── Trend: Price was consistently below VWAP for 3-5 candles ──
        trending_candles = df.iloc[-8:-3]
        below_vwap_count = (trending_candles["Close"] < trending_candles["vwap"]).sum()
        if below_vwap_count < 3:
            return None

        # ── Pullback: Recent candle(s) rise toward VWAP ──
        pullback_zone = df.iloc[-3:-1]
        touched_vwap = any(
            row["High"] >= row["vwap"] * 0.998
            for _, row in pullback_zone.iterrows()
        )
        if not touched_vwap:
            return None

        # ── Trigger: Bearish reversal candle near VWAP ──
        if not has_bearish_reversal(last, prev):
            return None

        # Last candle should be near VWAP (within 0.5%)
        if last["High"] < last["vwap"] * 0.995:
            return None

        # ── Entry & Targets ──
        entry = last["Low"]  # break of trigger candle's low
        swing_sl = find_recent_swing_high(df.tail(10), lookback=10)
        vwap_sl = last["vwap"] * 1.002  # a few ticks above VWAP
        cfg = get_strategy_config(_KEY)
        atr_sl = atr_stop_loss(df, entry, side="SELL", atr_mult=cfg["atr_mult"], min_pct=cfg["min_pct"])
        sl = max(swing_sl, vwap_sl, atr_sl)  # use the widest (most protective) SL

        risk = sl - entry
        if risk <= 0:
            return None

        target1 = find_recent_swing_low(df.iloc[:-3], lookback=15)
        if target1 >= entry:
            target1 = entry - risk * 2
        target2 = entry - risk * 3  # 1:3 R:R

        return {
            "symbol": symbol,
            "signal_type": "SELL",
            "entry_price": round(entry, 2),
            "stop_loss": round(sl, 2),
            "target_1": round(target1, 2),
            "target_2": round(target2, 2),
            "risk": round(risk, 2),
            "reward": round(entry - target1, 2),
            "risk_reward_ratio": "1:2",
            "current_price": round(last["Close"], 2),
            "strategy": "play3_vwap_pullback",
        }
