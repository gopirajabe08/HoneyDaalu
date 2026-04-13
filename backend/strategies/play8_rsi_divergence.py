"""
Play #8: RSI Divergence Reversal
────────────────────────────────
Timeframe : 15-min (intraday), 1h/1d (swing)
Indicators: RSI (14), Volume SMA (20).

"When price and RSI disagree, a reversal is near."

Setup Conditions (Bullish Divergence — BUY):
  - Price makes a LOWER LOW (last swing low < previous swing low).
  - RSI makes a HIGHER LOW (RSI at last swing low > RSI at previous swing low).
  - RSI is in oversold zone (< 35).
  - Current candle shows bullish reversal (hammer, engulfing, or strong green).
  - Volume confirmation: vol > 1.3x SMA20.

Setup Conditions (Bearish Divergence — SELL):
  - Price makes a HIGHER HIGH (last swing high > previous swing high).
  - RSI makes a LOWER HIGH (RSI at last swing high < RSI at previous swing high).
  - RSI is in overbought zone (> 65).
  - Current candle shows bearish reversal (shooting star, engulfing, or strong red).
  - Volume confirmation: vol > 1.3x SMA20.

Execution:
  Entry  : Close of signal candle.
  SL     : Beyond the last swing high/low (with ATR-based min floor of 1.2%).
  Targets: 1:2 Risk-Reward.
"""

import pandas as pd
import numpy as np
from typing import Optional

from .base import (
    BaseStrategy,
    calc_rsi,
    has_bullish_reversal,
    has_bearish_reversal,
    atr_stop_loss,
    get_strategy_config,
)

_KEY = "play8_rsi_divergence"


def _find_swing_highs(df: pd.DataFrame, lookback: int = 20, order: int = 2) -> list[tuple[int, float, float]]:
    """
    Find swing highs within the last `lookback` candles.

    A swing high at index i means df["High"].iat[i] is higher than the `order`
    candles before and after it.

    Returns list of (index, high_price, rsi_value) sorted by index ascending.
    """
    results = []
    end = len(df)
    start = max(0, end - lookback)
    for i in range(start + order, end - order):
        high_val = df["High"].iat[i]
        is_swing = True
        for j in range(1, order + 1):
            if df["High"].iat[i - j] >= high_val or df["High"].iat[i + j] >= high_val:
                is_swing = False
                break
        if is_swing and pd.notna(df["rsi"].iat[i]):
            results.append((i, high_val, df["rsi"].iat[i]))
    return results


def _find_swing_lows(df: pd.DataFrame, lookback: int = 20, order: int = 2) -> list[tuple[int, float, float]]:
    """
    Find swing lows within the last `lookback` candles.

    A swing low at index i means df["Low"].iat[i] is lower than the `order`
    candles before and after it.

    Returns list of (index, low_price, rsi_value) sorted by index ascending.
    """
    results = []
    end = len(df)
    start = max(0, end - lookback)
    for i in range(start + order, end - order):
        low_val = df["Low"].iat[i]
        is_swing = True
        for j in range(1, order + 1):
            if df["Low"].iat[i - j] <= low_val or df["Low"].iat[i + j] <= low_val:
                is_swing = False
                break
        if is_swing and pd.notna(df["rsi"].iat[i]):
            results.append((i, low_val, df["rsi"].iat[i]))
    return results


class RSIDivergence(BaseStrategy):
    name = "RSI Divergence Reversal"
    description = "Detects bullish/bearish divergence between price and RSI for reversal entries."
    category = "Intraday Precision (Session Trading)"
    indicators = ["RSI (14)", "Volume SMA (20)"]
    timeframes = ["15m", "1h", "1d"]
    long_setup = "Price makes LOWER LOW while RSI makes HIGHER LOW (oversold < 35), bullish reversal candle, volume > 1.3x SMA20."
    short_setup = "Price makes HIGHER HIGH while RSI makes LOWER HIGH (overbought > 65), bearish reversal candle, volume > 1.3x SMA20."
    exit_rules = "T1 at 1:2 Risk-Reward."
    stop_loss_rules = "Beyond the last swing high/low, with ATR-based floor of 1.2%."

    def scan(self, df: pd.DataFrame, symbol: str, **kwargs) -> Optional[dict]:
        import logging
        _logger = logging.getLogger(__name__)
        _logger.debug(f"[RSI_DIV] {symbol}: df_len={len(df)}, first_candle_time={df.index[0] if hasattr(df.index, '__getitem__') else 'unknown'}")

        if len(df) < 30:
            return None

        df = df.copy()
        df["rsi"] = calc_rsi(df["Close"], period=14)

        last = df.iloc[-1]
        if pd.isna(last["rsi"]):
            return None

        rsi_val = last["rsi"]

        # Timeframe-aware RSI thresholds:
        # Intraday (5m/15m): RSI rarely hits extreme zones, relax to 40/60
        # Swing/daily: keep strict 35/65
        timeframe = kwargs.get("timeframe", "1d")
        if timeframe in ("5m", "15m"):
            oversold_threshold = 40
            overbought_threshold = 60
        else:
            oversold_threshold = 35
            overbought_threshold = 65

        # Route based on RSI zone
        if rsi_val < oversold_threshold:
            return self._scan_long(df, symbol)
        elif rsi_val > overbought_threshold:
            return self._scan_short(df, symbol)
        return None

    def _scan_long(self, df: pd.DataFrame, symbol: str) -> Optional[dict]:
        """Scan for BULLISH divergence: price lower low + RSI higher low."""
        last = df.iloc[-1]
        prev = df.iloc[-2]

        # ── Bullish reversal candle confirmation (relaxed: green candle also qualifies) ──
        is_green = last["Close"] > last["Open"]
        if not is_green and not has_bullish_reversal(last, prev):
            return None

        # ── Volume confirmation — must have above-average volume ──
        if len(df) >= 20:
            vol_sma = df["Volume"].rolling(20).mean().iloc[-1]
            if not pd.isna(vol_sma) and vol_sma > 0:
                if df["Volume"].iloc[-1] < vol_sma * 1.0:  # Minimum 1x average volume
                    return None

        # ── Find at least 2 swing lows to compare ──
        swing_lows = _find_swing_lows(df, lookback=20, order=2)
        if len(swing_lows) < 2:
            return None

        # Compare last two swing lows
        prev_swing = swing_lows[-2]  # (index, price, rsi)
        last_swing = swing_lows[-1]

        # Bullish divergence: price lower low, RSI higher low
        price_lower_low = last_swing[1] < prev_swing[1]
        rsi_higher_low = last_swing[2] > prev_swing[2]

        if not (price_lower_low and rsi_higher_low):
            return None

        # ── Entry & Targets ──
        entry = last["Close"]
        cfg = get_strategy_config(_KEY)

        # SL beyond the last swing low, with ATR-based floor
        swing_sl = last_swing[1] - (entry * 0.002)  # slightly beyond swing low
        atr_sl = atr_stop_loss(df, entry, side="BUY", atr_mult=cfg["atr_mult"], min_pct=cfg["min_pct"])
        sl = min(swing_sl, atr_sl)  # take the wider (more protective) SL

        risk = entry - sl
        if risk <= 0:
            return None

        target1 = entry + risk * 2
        target2 = entry + risk * 3

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
            "strategy": "play8_rsi_divergence",
        }

    def _scan_short(self, df: pd.DataFrame, symbol: str) -> Optional[dict]:
        """Scan for BEARISH divergence: price higher high + RSI lower high."""
        last = df.iloc[-1]
        prev = df.iloc[-2]

        # ── Bearish reversal candle confirmation (relaxed: red candle also qualifies) ──
        is_red = last["Close"] < last["Open"]
        if not is_red and not has_bearish_reversal(last, prev):
            return None

        # ── Volume confirmation — relaxed for low-volume sessions ──
        if len(df) >= 20:
            vol_sma = df["Volume"].rolling(20).mean().iloc[-1]
            if not pd.isna(vol_sma) and vol_sma > 0:
                if df["Volume"].iloc[-1] < vol_sma * 1.0:  # Minimum 1x average volume
                    return None

        # ── Find at least 2 swing highs to compare ──
        swing_highs = _find_swing_highs(df, lookback=20, order=2)
        if len(swing_highs) < 2:
            return None

        # Compare last two swing highs
        prev_swing = swing_highs[-2]  # (index, price, rsi)
        last_swing = swing_highs[-1]

        # Bearish divergence: price higher high, RSI lower high
        price_higher_high = last_swing[1] > prev_swing[1]
        rsi_lower_high = last_swing[2] < prev_swing[2]

        if not (price_higher_high and rsi_lower_high):
            return None

        # ── Entry & Targets ──
        entry = last["Close"]
        cfg = get_strategy_config(_KEY)

        # SL beyond the last swing high, with ATR-based floor
        swing_sl = last_swing[1] + (entry * 0.002)  # slightly beyond swing high
        atr_sl = atr_stop_loss(df, entry, side="SELL", atr_mult=cfg["atr_mult"], min_pct=cfg["min_pct"])
        sl = max(swing_sl, atr_sl)  # take the wider (more protective) SL

        risk = sl - entry
        if risk <= 0:
            return None

        target1 = entry - risk * 2
        target2 = entry - risk * 3

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
            "strategy": "play8_rsi_divergence",
        }
