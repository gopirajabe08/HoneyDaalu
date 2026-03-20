"""
Play #7: Opening Range Breakout (ORB)
────────────────────────────────
Timeframe : 15-min (first 2 candles = 30 min opening range, 9:15-9:45 AM)

"The Opening Range defines the battlefield.
 Breakout with volume tells you which side won."

Setup:
  1. Calculate Opening Range (OR): High and Low of first 2 candles (9:15-9:45 AM)
  2. OR must be meaningful: range > 0.5% of open price (filters tiny ranges)
  3. Wait for a candle to CLOSE above OR High (BUY) or below OR Low (SELL)
  4. Volume on breakout candle must be > 1.3x SMA20 volume
  5. Entry: Close of breakout candle

Long Setup:
  - Candle closes above OR High
  - Breakout candle body > 50% of candle range (strong candle, not a doji)
  - Volume confirmation: vol > 1.3x SMA20

Short Setup:
  - Candle closes below OR Low
  - Breakout candle body > 50% of candle range
  - Volume confirmation: vol > 1.3x SMA20

Risk Management:
  - SL: Opposite side of Opening Range (if BUY, SL = OR Low; if SELL, SL = OR High)
  - But SL must be at least 1.2% from entry (ATR-based floor)
  - Target: 1:2 R:R from entry to SL distance
"""

import pandas as pd
from typing import Optional

from .base import (
    BaseStrategy,
    body_size,
    candle_range,
    atr_stop_loss,
    get_strategy_config,
    calc_sma,
)

_KEY = "play7_orb"


class ORBBreakout(BaseStrategy):
    name = "Opening Range Breakout (ORB)"
    description = "Breakout of the 30-min Opening Range (9:15-9:45 AM) with volume confirmation."
    category = "Intraday Precision (Session Trading)"
    indicators = ["Opening Range (first 2x 15m candles)", "SMA20 Volume"]
    timeframes = ["15m"]
    long_setup = "Candle CLOSES above OR High, body > 50% of candle range, volume > 1.3x SMA20."
    short_setup = "Candle CLOSES below OR Low, body > 50% of candle range, volume > 1.3x SMA20."
    exit_rules = "Target at 1:2 R:R from entry based on SL distance."
    stop_loss_rules = "Opposite side of Opening Range with 1.2% ATR-based floor."

    def scan(self, df: pd.DataFrame, symbol: str, **kwargs) -> Optional[dict]:
        import logging
        _logger = logging.getLogger(__name__)
        _logger.debug(f"[ORB] {symbol}: df_len={len(df)}, first_candle_time={df.index[0] if hasattr(df.index, '__getitem__') else 'unknown'}")

        # Need at least the 2 OR candles + a few candles after for signal
        if len(df) < 5:
            return None

        df = df.copy()

        # Filter to trading session only (exclude pre-market 9:00-9:15)
        try:
            if hasattr(df.index, 'time'):
                from datetime import time as dtime
                session_mask = df.index.time >= dtime(9, 15)
                df = df[session_mask]
                if len(df) < 5:
                    return None
        except Exception:
            pass

        # ── Calculate Opening Range from first 2 candles (9:15-9:45 AM) ──
        or_high = max(df["High"].iloc[0], df["High"].iloc[1])
        or_low = min(df["Low"].iloc[0], df["Low"].iloc[1])
        or_open = df["Open"].iloc[0]
        or_range = or_high - or_low

        # ── OR must be meaningful: range > 0.5% of open price ──
        if or_range < or_open * 0.005:
            return None

        # ── Check the last two completed candles for breakout signal ──
        # Check most recent candle first (iloc[-1]), then previous (iloc[-2])
        for idx in [-1, -2]:
            # Must be after OR candles (index >= 2)
            actual_idx = len(df) + idx
            if actual_idx < 2:
                continue

            candle = df.iloc[idx]
            prev = df.iloc[idx - 1] if (actual_idx - 1) >= 0 else None

            # ── Check for LONG breakout ──
            if candle["Close"] > or_high:
                signal = self._check_long(df, candle, symbol, or_high, or_low, or_range)
                if signal:
                    return signal

            # ── Check for SHORT breakout ──
            if candle["Close"] < or_low:
                signal = self._check_short(df, candle, symbol, or_high, or_low, or_range)
                if signal:
                    return signal

        return None

    def _check_long(self, df: pd.DataFrame, candle: pd.Series,
                    symbol: str, or_high: float, or_low: float,
                    or_range: float) -> Optional[dict]:
        """Check for valid LONG breakout above OR High."""

        # ── Strong candle check: body > 50% of candle range (not a doji) ──
        c_range = candle_range(candle)
        if c_range == 0:
            return None
        c_body = body_size(candle)
        if c_body / c_range < 0.50:
            return None

        # ── Volume confirmation: vol > 1.3x SMA20 ──
        if len(df) >= 20:
            vol_sma = df["Volume"].rolling(20).mean().iloc[-1]
            if candle["Volume"] < vol_sma * (0.8 if len(df) < 60 else 1.1):
                return None

        # ── Entry & Risk Management ──
        entry = round(candle["Close"], 2)

        # SL = OR Low (opposite side of opening range)
        sl = or_low

        # But SL must be at least 1.2% from entry (ATR-based floor)
        cfg = get_strategy_config(_KEY)
        min_pct = cfg.get("min_pct", 0.012)
        min_sl_distance = entry * min_pct
        if entry - sl < min_sl_distance:
            sl = round(entry - min_sl_distance, 2)

        sl = round(sl, 2)
        risk = entry - sl
        if risk <= 0:
            return None

        # Target: 1:2 R:R
        target1 = round(entry + risk * 2, 2)
        target2 = round(entry + risk * 3, 2)

        return {
            "symbol": symbol,
            "signal_type": "BUY",
            "entry_price": entry,
            "stop_loss": sl,
            "target_1": target1,
            "target_2": target2,
            "risk": round(risk, 2),
            "reward": round(risk * 2, 2),
            "risk_reward_ratio": "1:2",
            "current_price": round(df.iloc[-1]["Close"], 2),
            "strategy": "play7_orb",
        }

    def _check_short(self, df: pd.DataFrame, candle: pd.Series,
                     symbol: str, or_high: float, or_low: float,
                     or_range: float) -> Optional[dict]:
        """Check for valid SHORT breakout below OR Low."""

        # ── Strong candle check: body > 50% of candle range (not a doji) ──
        c_range = candle_range(candle)
        if c_range == 0:
            return None
        c_body = body_size(candle)
        if c_body / c_range < 0.50:
            return None

        # ── Volume confirmation: vol > 1.3x SMA20 ──
        if len(df) >= 20:
            vol_sma = df["Volume"].rolling(20).mean().iloc[-1]
            if candle["Volume"] < vol_sma * (0.8 if len(df) < 60 else 1.1):
                return None

        # ── Entry & Risk Management ──
        entry = round(candle["Close"], 2)

        # SL = OR High (opposite side of opening range)
        sl = or_high

        # But SL must be at least 1.2% from entry (ATR-based floor)
        cfg = get_strategy_config(_KEY)
        min_pct = cfg.get("min_pct", 0.012)
        min_sl_distance = entry * min_pct
        if sl - entry < min_sl_distance:
            sl = round(entry + min_sl_distance, 2)

        sl = round(sl, 2)
        risk = sl - entry
        if risk <= 0:
            return None

        # Target: 1:2 R:R
        target1 = round(entry - risk * 2, 2)
        target2 = round(entry - risk * 3, 2)

        return {
            "symbol": symbol,
            "signal_type": "SELL",
            "entry_price": entry,
            "stop_loss": sl,
            "target_1": target1,
            "target_2": target2,
            "risk": round(risk, 2),
            "reward": round(risk * 2, 2),
            "risk_reward_ratio": "1:2",
            "current_price": round(df.iloc[-1]["Close"], 2),
            "strategy": "play7_orb",
        }
