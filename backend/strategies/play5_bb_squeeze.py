"""
Play #5: Bollinger Band "Squeeze Breakout"
──────────────────────────────────────────
Timeframe : 15-min / 30-min or Daily
Indicators: Bollinger Bands (Period: 20, Std Dev: 2).

Setup Conditions (The Squeeze):
  - Upper and lower bands are visibly "pinched" together.
  - Bandwidth is narrower than the recent past.
  - Price action is moving sideways with small, overlapping candles.

Trigger Rules (Bullish):
  - Wait for a decisive strong bullish candle to close explicitly
    above the upper band.
  - Breakout candle body must be relatively large compared to the
    previous squeeze candles.

Execution:
  Entry : Buy on next candle if price trades above high of breakout candle.
  SL    : Mechanical stop below the Middle Band (20 SMA).
  Target: First target at 1:1.5 or 1:2 Risk-Reward ratio.
"""

import pandas as pd
import numpy as np
from typing import Optional

from .base import (
    BaseStrategy,
    calc_bollinger_bands,
    is_bullish_candle,
    is_bearish_candle,
    body_size,
    atr_stop_loss,
    get_strategy_config,
)

_KEY = "play5_bb_squeeze"


class BBSqueeze(BaseStrategy):
    name = 'Bollinger Band "Squeeze Breakout"'
    description = "Breakout from a Bollinger Band squeeze with a strong bullish candle closing above the upper band."
    category = "Volatility & Reversals (Bollinger Dynamics)"
    indicators = ["Bollinger Bands (Period 20, Std Dev 2)"]
    timeframes = ["15m", "30m", "1d"]
    long_setup = "BB squeeze (narrow bandwidth), then decisive bullish candle closes above upper band with large body."
    short_setup = "BB squeeze (narrow bandwidth), then decisive bearish candle closes below lower band with large body."
    exit_rules = "First target at 1:1.5 or 1:2 Risk-Reward ratio."
    stop_loss_rules = "Mechanical stop below the Middle Band (20 SMA)."

    def scan(self, df: pd.DataFrame, symbol: str) -> Optional[dict]:
        if len(df) < 30:
            return None

        df = df.copy()
        df["bb_mid"], df["bb_upper"], df["bb_lower"], df["bb_bw"] = calc_bollinger_bands(df)

        last = df.iloc[-1]
        prev = df.iloc[-2]

        # ── Validate indicators ──
        if pd.isna(last["bb_mid"]) or pd.isna(last["bb_upper"]) or pd.isna(last["bb_lower"]):
            return None

        # ── Squeeze detection (shared) ──
        squeeze_window = df.iloc[-12:-2]
        if squeeze_window["bb_bw"].isna().all():
            return None

        recent_bw = squeeze_window["bb_bw"].mean()
        longer_bw = df["bb_bw"].iloc[-30:-10].mean()

        if pd.isna(recent_bw) or pd.isna(longer_bw):
            return None

        if recent_bw >= longer_bw * 0.85:
            return None

        squeeze_bodies = squeeze_window.apply(body_size, axis=1)
        avg_squeeze_body = squeeze_bodies.mean()

        # Try long first, then short
        result = self._scan_long(df, last, prev, avg_squeeze_body, symbol)
        if result:
            return result
        return self._scan_short(df, last, prev, avg_squeeze_body, symbol)

    def _scan_long(self, df, last, prev, avg_squeeze_body, symbol) -> Optional[dict]:
        """Bullish breakout above upper band."""
        if not is_bullish_candle(prev):
            return None
        if prev["Close"] <= prev["bb_upper"]:
            return None

        breakout_body = body_size(prev)
        if breakout_body <= avg_squeeze_body * 1.5:
            return None

        if last["High"] < prev["High"]:
            return None

        # Volume confirmation — reject low-conviction signals
        if len(df) >= 20:
            vol_sma = df["Volume"].rolling(20).mean().iloc[-1]
            if df["Volume"].iloc[-1] < vol_sma * 1.3:
                return None  # Low volume — skip

        entry = last["High"]  # Use confirmation candle's high (not stale breakout bar)
        bb_sl = last["bb_mid"]
        cfg = get_strategy_config(_KEY)
        atr_sl = atr_stop_loss(df, entry, side="BUY", atr_mult=cfg["atr_mult"], min_pct=cfg["min_pct"])
        sl = min(bb_sl, atr_sl)

        risk = entry - sl
        if risk <= 0:
            return None

        target1 = entry + risk * 1.5
        target2 = entry + risk * 2

        return {
            "symbol": symbol,
            "signal_type": "BUY",
            "entry_price": round(entry, 2),
            "stop_loss": round(sl, 2),
            "target_1": round(target1, 2),
            "target_2": round(target2, 2),
            "risk": round(risk, 2),
            "reward": round(target1 - entry, 2),
            "risk_reward_ratio": "1:1.5",
            "current_price": round(last["Close"], 2),
            "strategy": "play5_bb_squeeze",
        }

    def _scan_short(self, df, last, prev, avg_squeeze_body, symbol) -> Optional[dict]:
        """Bearish breakout below lower band."""
        if not is_bearish_candle(prev):
            return None
        if prev["Close"] >= prev["bb_lower"]:
            return None

        breakout_body = body_size(prev)
        if breakout_body <= avg_squeeze_body * 1.5:
            return None

        if last["Low"] > prev["Low"]:
            return None

        # Volume confirmation — reject low-conviction signals
        if len(df) >= 20:
            vol_sma = df["Volume"].rolling(20).mean().iloc[-1]
            if df["Volume"].iloc[-1] < vol_sma * 1.3:
                return None  # Low volume — skip

        entry = last["Low"]  # Use confirmation candle's low (not stale breakout bar)
        bb_sl = last["bb_mid"]  # above middle band
        cfg = get_strategy_config(_KEY)
        atr_sl = atr_stop_loss(df, entry, side="SELL", atr_mult=cfg["atr_mult"], min_pct=cfg["min_pct"])
        sl = max(bb_sl, atr_sl)

        risk = sl - entry
        if risk <= 0:
            return None

        target1 = entry - risk * 1.5
        target2 = entry - risk * 2

        return {
            "symbol": symbol,
            "signal_type": "SELL",
            "entry_price": round(entry, 2),
            "stop_loss": round(sl, 2),
            "target_1": round(target1, 2),
            "target_2": round(target2, 2),
            "risk": round(risk, 2),
            "reward": round(entry - target1, 2),
            "risk_reward_ratio": "1:1.5",
            "current_price": round(last["Close"], 2),
            "strategy": "play5_bb_squeeze",
        }
