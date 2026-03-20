"""
Play #4: The "Power Trend" Setup
────────────────────────────────
Timeframe : 5-min or 15-min
Indicators: Supertrend (ATR 10, Mult 3) and 20 EMA.

"Supertrend tells us who's in control.
 The 20 EMA tells us exactly where to enter."

Setup Conditions (Long):
  - Supertrend is GREEN (direction == 1, plotted below price).
  - Price is above the 20 EMA.
  - Price pulls back into the "Power Zone" (near 20 EMA / Supertrend).
  - Bullish trigger candle (Hammer, Engulfing, or strong green).

Setup Conditions (Short):
  - Supertrend is RED (direction == -1, plotted above price).
  - Price is below the 20 EMA.
  - Price pulls back UP into the "Power Zone" (near 20 EMA / Supertrend).
  - Bearish trigger candle (Shooting Star, Engulfing, or strong red).

Execution:
  Entry  : Buy/Sell on the break of the signal candle's high/low.
  SL     : ATR-based, beyond the signal candle extreme.
  Targets: T1 at the recent swing extreme.
           T2 at 1:2 or 1:3 Risk-Reward.
"""

import pandas as pd
from typing import Optional

from .base import (
    BaseStrategy,
    calc_ema,
    calc_supertrend,
    has_bullish_reversal,
    has_bearish_reversal,
    find_recent_swing_high,
    find_recent_swing_low,
    atr_stop_loss,
    get_strategy_config,
)

_KEY = "play4_supertrend"


class SupertrendPowerTrend(BaseStrategy):
    name = 'Supertrend "Power Trend"'
    description = "Pullback into the Power Zone (20 EMA / Supertrend) with bullish reversal in an uptrend."
    category = "Intraday Precision (Session Trading)"
    indicators = ["Supertrend (ATR 10, Multiplier 3)", "20 EMA"]
    timeframes = ["5m", "15m"]
    long_setup = "Supertrend GREEN, price above 20 EMA, pullback into Power Zone (near 20 EMA/Supertrend), trigger candle (Hammer, Engulfing, strong green)."
    short_setup = "Supertrend RED, price below 20 EMA, pullback into Power Zone (near 20 EMA/Supertrend), trigger candle (Shooting Star, Engulfing, strong red)."
    exit_rules = "T1 at recent swing high. T2 at 1:2 or 1:3 Risk-Reward."
    stop_loss_rules = "Strictly below the low of the signal candle."

    def scan(self, df: pd.DataFrame, symbol: str, **kwargs) -> Optional[dict]:
        if len(df) < 25:
            return None

        df = df.copy()
        df["ema20"] = calc_ema(df["Close"], 20)
        df["supertrend"], df["st_direction"] = calc_supertrend(df, period=10, multiplier=3.0)

        last = df.iloc[-1]

        # Route to long or short based on Supertrend direction
        if last["st_direction"] == 1:
            return self._scan_long(df, symbol)
        elif last["st_direction"] == -1:
            return self._scan_short(df, symbol)
        return None

    def _scan_long(self, df: pd.DataFrame, symbol: str) -> Optional[dict]:
        """Scan for LONG: Supertrend GREEN, pullback into Power Zone, bullish trigger."""
        last = df.iloc[-1]
        prev = df.iloc[-2]

        # ── Validate indicators ──
        if pd.isna(last["ema20"]) or pd.isna(last["supertrend"]):
            return None

        # ── Price must be above 20 EMA ──
        if last["Close"] <= last["ema20"]:
            return None

        # ── Pullback into "Power Zone": between Supertrend line and 20 EMA ──
        ema20_val = last["ema20"]
        st_val = last["supertrend"]
        power_zone_high = ema20_val * 1.005

        # Check if price recently touched the power zone (last 3 candles)
        # Price must be near 20 EMA AND above the Supertrend line (the actual Power Zone)
        recent = df.iloc[-3:]
        touched_power_zone = any(
            row["Low"] <= power_zone_high and row["Low"] >= row["supertrend"]
            for _, row in recent.iterrows()
        )
        if not touched_power_zone:
            return None

        # ── Trigger candle: bullish close OR reversal pattern ──
        # Relaxed: any green candle (close > open) qualifies, not just hammer/engulfing
        is_green = last["Close"] > last["Open"]
        if not is_green and not has_bullish_reversal(last, prev):
            return None

        # Volume confirmation — relaxed: skip filter if volume data is very low (Friday afternoon etc.)
        if len(df) >= 20:
            vol_sma = df["Volume"].rolling(20).mean().iloc[-1]
            threshold = 0.8 if len(df) < 60 else 1.1
            # If market-wide volume is extremely low (<50% avg), don't filter
            if vol_sma > 0 and df["Volume"].iloc[-1] / vol_sma > 0.5:
                if df["Volume"].iloc[-1] < vol_sma * threshold:
                    return None

        # ── Entry & Targets ──
        entry = last["High"]
        cfg = get_strategy_config(_KEY)
        sl = atr_stop_loss(df, entry, side="BUY", atr_mult=cfg["atr_mult"], min_pct=cfg["min_pct"])

        risk = entry - sl
        if risk <= 0:
            return None

        target1 = find_recent_swing_high(df.iloc[:-3], lookback=15)
        if target1 <= entry:
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
            "strategy": "play4_supertrend",
        }

    def _scan_short(self, df: pd.DataFrame, symbol: str) -> Optional[dict]:
        """Scan for SHORT: Supertrend RED, pullback into Power Zone, bearish trigger."""
        last = df.iloc[-1]
        prev = df.iloc[-2]

        # ── Validate indicators ──
        if pd.isna(last["ema20"]) or pd.isna(last["supertrend"]):
            return None

        # ── Price must be below 20 EMA ──
        if last["Close"] >= last["ema20"]:
            return None

        # ── Pullback UP into "Power Zone": between 20 EMA and Supertrend line ──
        ema20_val = last["ema20"]
        st_val = last["supertrend"]
        power_zone_low = ema20_val * 0.995

        # Check if price recently touched the power zone from below (last 3 candles)
        # Price must be near 20 EMA AND below the Supertrend line (the actual Power Zone)
        recent = df.iloc[-3:]
        touched_power_zone = any(
            row["High"] >= power_zone_low and row["High"] <= row["supertrend"]
            for _, row in recent.iterrows()
        )
        if not touched_power_zone:
            return None

        # ── Trigger candle: bearish close OR reversal pattern ──
        is_red = last["Close"] < last["Open"]
        if not is_red and not has_bearish_reversal(last, prev):
            return None

        # Volume confirmation — relaxed for low-volume sessions
        if len(df) >= 20:
            vol_sma = df["Volume"].rolling(20).mean().iloc[-1]
            threshold = 0.8 if len(df) < 60 else 1.1
            if vol_sma > 0 and df["Volume"].iloc[-1] / vol_sma > 0.5:
                if df["Volume"].iloc[-1] < vol_sma * threshold:
                    return None

        # ── Entry & Targets ──
        entry = last["Low"]  # break of signal candle's low
        cfg = get_strategy_config(_KEY)
        sl = atr_stop_loss(df, entry, side="SELL", atr_mult=cfg["atr_mult"], min_pct=cfg["min_pct"])

        risk = sl - entry
        if risk <= 0:
            return None

        target1 = find_recent_swing_low(df.iloc[:-3], lookback=15)
        if target1 >= entry:
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
            "strategy": "play4_supertrend",
        }
