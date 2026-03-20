"""
Play #6: Bollinger Band "Contra" (Mean Reversion)
─────────────────────────────────────────────────
Timeframe : 5-min / 15-min or Daily
Indicators: Bollinger Bands (20, 2 Std Dev) and 200 SMA.

Trend Filter (Mandatory):
  - Price must be strictly > 200 SMA.
  - 200 SMA must be visibly sloping upward.

Setup Conditions:
  - Price pulls back from recent highs and touches/pierces Lower Band.
  - Reversal candle forms at the lower band
    (long lower wick, doji, or bullish engulfing).

Execution:
  Entry : Buy above the high of the reversal candle.
  SL    : Below the low of the reversal candle.
  Target: The Middle Band (20 SMA).
"""

import pandas as pd
from typing import Optional

from .base import (
    BaseStrategy,
    calc_bollinger_bands,
    calc_sma,
    is_hammer,
    is_shooting_star,
    is_doji,
    is_bullish_engulfing,
    is_bearish_engulfing,
    is_bullish_candle,
    is_bearish_candle,
    atr_stop_loss,
    get_strategy_config,
)

_KEY = "play6_bb_contra"


class BBContra(BaseStrategy):
    name = 'Bollinger Band "Contra" (Mean Reversion)'
    description = "Mean reversion buy at the lower Bollinger Band in a confirmed macro uptrend (price > 200 SMA)."
    category = "Volatility & Reversals (Bollinger Dynamics)"
    indicators = ["Bollinger Bands (20, 2 Std Dev)", "200 SMA"]
    timeframes = ["5m", "15m", "1d"]
    long_setup = "Price > 200 SMA (sloping up). Price pulls back and touches/pierces Lower Band. Reversal candle at lower band (long lower wick, doji, bullish engulfing)."
    short_setup = "Price < 200 SMA (sloping down). Price rallies and touches/pierces Upper Band. Reversal candle at upper band (shooting star, doji, bearish engulfing)."
    exit_rules = "Target: The Middle Band (20 SMA)."
    stop_loss_rules = "Below the low of the reversal candle."

    def scan(self, df: pd.DataFrame, symbol: str) -> Optional[dict]:
        if len(df) < 210:
            return None

        df = df.copy()
        df["bb_mid"], df["bb_upper"], df["bb_lower"], df["bb_bw"] = calc_bollinger_bands(df)
        df["sma200"] = calc_sma(df["Close"], 200)

        last = df.iloc[-1]
        prev = df.iloc[-2]

        if pd.isna(last["sma200"]) or pd.isna(last["bb_mid"]) or pd.isna(last["bb_lower"]) or pd.isna(last["bb_upper"]):
            return None

        # Try long first, then short
        result = self._scan_long(df, last, prev, symbol)
        if result:
            return result
        return self._scan_short(df, last, prev, symbol)

    def _scan_long(self, df, last, prev, symbol) -> Optional[dict]:
        """Long: mean reversion buy at lower BB. Relaxed in oversold markets."""
        # ── Trend Filter: Price > 200 SMA in normal conditions ──
        # BUT: skip trend filter if RSI is extremely oversold (< 30)
        # Rationale: in crash markets, oversold bounces work even without uptrend
        rsi_val = 50
        try:
            from .base import calc_rsi
            rsi = calc_rsi(df, 14)
            rsi_val = float(rsi.iloc[-1]) if len(rsi) > 0 and not pd.isna(rsi.iloc[-1]) else 50
        except Exception:
            pass

        extremely_oversold = rsi_val < 30

        if not extremely_oversold:
            if last["Close"] <= last["sma200"]:
                return None
            sma200_now = last["sma200"]
            sma200_prev = df["sma200"].iloc[-10]
            if pd.isna(sma200_prev) or sma200_now <= sma200_prev:
                return None

        # ── Price touches/pierces Lower Band ──
        if pd.isna(last["bb_lower"]):
            return None

        touched_lower = (
            last["Low"] <= last["bb_lower"] * 1.002
            or prev["Low"] <= prev["bb_lower"] * 1.002
        )
        if not touched_lower:
            return None

        # ── Reversal candle at the lower band (relaxed: green candle also qualifies) ──
        is_green = last["Close"] > last["Open"]
        has_reversal = (
            is_green
            or is_hammer(last)
            or is_doji(last)
            or is_bullish_engulfing(last, prev)
            or (is_hammer(prev) and is_bullish_candle(last))
            or (is_doji(prev) and is_bullish_candle(last))
        )
        if not has_reversal:
            return None

        # Volume confirmation — relaxed for low-volume sessions
        if len(df) >= 20:
            vol_sma = df["Volume"].rolling(20).mean().iloc[-1]
            threshold = 0.8 if len(df) < 60 else 1.1
            # If market-wide volume is extremely low (<50% avg), don't filter
            if vol_sma > 0 and df["Volume"].iloc[-1] / vol_sma > 0.5:
                if df["Volume"].iloc[-1] < vol_sma * threshold:
                    return None

        if is_hammer(last) or is_doji(last) or is_bullish_engulfing(last, prev):
            reversal = last
        else:
            reversal = prev

        entry = reversal["High"]
        candle_sl = reversal["Low"]
        cfg = get_strategy_config(_KEY)
        atr_sl = atr_stop_loss(df, entry, side="BUY", atr_mult=cfg["atr_mult"], min_pct=cfg["min_pct"])
        sl = min(candle_sl, atr_sl)
        target1 = last["bb_mid"]

        risk = entry - sl
        if risk <= 0:
            return None

        reward = target1 - entry
        if reward <= 0:
            return None

        rr = round(reward / risk, 1) if risk > 0 else 0

        return {
            "symbol": symbol,
            "signal_type": "BUY",
            "entry_price": round(entry, 2),
            "stop_loss": round(sl, 2),
            "target_1": round(target1, 2),
            "target_2": None,
            "risk": round(risk, 2),
            "reward": round(reward, 2),
            "risk_reward_ratio": f"1:{rr}",
            "current_price": round(last["Close"], 2),
            "strategy": "play6_bb_contra",
        }

    def _scan_short(self, df, last, prev, symbol) -> Optional[dict]:
        """Short: mean reversion sell at upper BB in macro downtrend."""
        # ── Trend Filter: Price < 200 SMA, sloping down ──
        if last["Close"] >= last["sma200"]:
            return None

        sma200_now = last["sma200"]
        sma200_prev = df["sma200"].iloc[-10]
        if pd.isna(sma200_prev) or sma200_now >= sma200_prev:
            return None

        # ── Price touches/pierces Upper Band ──
        if pd.isna(last["bb_upper"]):
            return None

        touched_upper = (
            last["High"] >= last["bb_upper"] * 0.998
            or prev["High"] >= prev["bb_upper"] * 0.998
        )
        if not touched_upper:
            return None

        # ── Bearish reversal candle at the upper band (relaxed: red candle also qualifies) ──
        is_red = last["Close"] < last["Open"]
        has_reversal = (
            is_red
            or is_shooting_star(last)
            or is_doji(last)
            or is_bearish_engulfing(last, prev)
            or (is_shooting_star(prev) and is_bearish_candle(last))
            or (is_doji(prev) and is_bearish_candle(last))
        )
        if not has_reversal:
            return None

        # Volume confirmation — relaxed for low-volume sessions
        if len(df) >= 20:
            vol_sma = df["Volume"].rolling(20).mean().iloc[-1]
            threshold = 0.8 if len(df) < 60 else 1.1
            # If market-wide volume is extremely low (<50% avg), don't filter
            if vol_sma > 0 and df["Volume"].iloc[-1] / vol_sma > 0.5:
                if df["Volume"].iloc[-1] < vol_sma * threshold:
                    return None

        if is_shooting_star(last) or is_doji(last) or is_bearish_engulfing(last, prev):
            reversal = last
        else:
            reversal = prev

        entry = reversal["Low"]
        candle_sl = reversal["High"]
        cfg = get_strategy_config(_KEY)
        atr_sl = atr_stop_loss(df, entry, side="SELL", atr_mult=cfg["atr_mult"], min_pct=cfg["min_pct"])
        sl = max(candle_sl, atr_sl)
        target1 = last["bb_mid"]  # middle band

        risk = sl - entry
        if risk <= 0:
            return None

        reward = entry - target1
        if reward <= 0:
            return None

        rr = round(reward / risk, 1) if risk > 0 else 0

        return {
            "symbol": symbol,
            "signal_type": "SELL",
            "entry_price": round(entry, 2),
            "stop_loss": round(sl, 2),
            "target_1": round(target1, 2),
            "target_2": None,
            "risk": round(risk, 2),
            "reward": round(reward, 2),
            "risk_reward_ratio": f"1:{rr}",
            "current_price": round(last["Close"], 2),
            "strategy": "play6_bb_contra",
        }
