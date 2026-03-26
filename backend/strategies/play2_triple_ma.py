"""
Play #2: Triple Moving Average Trend Filter
────────────────────────────────────────────
Timeframe : Multi-timeframe applicable
Indicators: 20 EMA (Fast), 50 SMA (Medium), 200 SMA (Slow).

Long Trend Condition:
  Strong Uptrend: 20 EMA > 50 SMA > 200 SMA, sloping upward.
  Pullback to 20 EMA or 50 SMA, bullish reversal confirmation.

Short Trend Condition:
  Strong Downtrend: 20 EMA < 50 SMA < 200 SMA, sloping downward.
  Pullback UP to 20 EMA or 50 SMA, bearish reversal confirmation.

Stop-Loss: Beyond the swing extreme of the pullback.
Exit: When 20 EMA crosses the 50 SMA in the opposite direction.
"""

import pandas as pd
from typing import Optional

from .base import (
    BaseStrategy,
    calc_ema,
    calc_sma,
    has_bullish_reversal,
    has_bearish_reversal,
    find_recent_swing_low,
    find_recent_swing_high,
    atr_stop_loss,
    get_strategy_config,
)

_KEY = "play2_triple_ma"


class TripleMA(BaseStrategy):
    name = "Triple Moving Average Trend Filter"
    description = "Pullback entries in strong uptrends where 20 EMA > 50 SMA > 200 SMA are stacked."
    category = "Trend Following (Momentum Capture)"
    indicators = ["20 EMA (Fast)", "50 SMA (Medium)", "200 SMA (Slow)"]
    timeframes = ["15m", "1h", "1d"]
    long_setup = "20 EMA > 50 SMA > 200 SMA stacked upward. Wait for pullback to 20 EMA or 50 SMA. Confirm with bullish candle (Hammer, Engulfing)."
    short_setup = "20 EMA < 50 SMA < 200 SMA stacked downward. Wait for pullback UP to 20 EMA or 50 SMA. Confirm with bearish candle (Shooting Star, Engulfing)."
    exit_rules = "Close when 20 EMA crosses the 50 SMA in the opposite direction."
    stop_loss_rules = "Beyond the swing extreme of the pullback."

    def scan(self, df: pd.DataFrame, symbol: str, **kwargs) -> Optional[dict]:
        if len(df) < 210:
            return None

        df = df.copy()
        df["ema20"] = calc_ema(df["Close"], 20)
        df["sma50"] = calc_sma(df["Close"], 50)
        df["sma200"] = calc_sma(df["Close"], 200)

        last = df.iloc[-1]
        prev = df.iloc[-2]
        ago = df.iloc[-4]

        # ── Validate indicators ──
        if pd.isna(last["ema20"]) or pd.isna(last["sma50"]) or pd.isna(last["sma200"]):
            return None

        # Try long first, then short
        result = self._scan_long(df, last, prev, ago, symbol)
        if result:
            return result
        return self._scan_short(df, last, prev, ago, symbol)

    def _scan_long(self, df, last, prev, ago, symbol) -> Optional[dict]:
        # ── Trend condition: 20 EMA > 50 SMA > 200 SMA ──
        if not (last["ema20"] > last["sma50"] > last["sma200"]):
            return None

        # ── MAs must be sloping upward ──
        if not (last["ema20"] > ago["ema20"] and last["sma50"] > ago["sma50"]):
            return None

        # ── Pullback to 20 EMA or 50 SMA ──
        near_ema20 = last["Low"] <= last["ema20"] * 1.005
        near_sma50 = last["Low"] <= last["sma50"] * 1.005
        if not (near_ema20 or near_sma50):
            return None

        # ── Confirm with bullish candlestick pattern (relaxed: green candle also qualifies) ──
        is_green = last["Close"] > last["Open"]
        if not is_green and not has_bullish_reversal(last, prev):
            return None

        # Volume confirmation — relaxed for low-volume sessions
        if len(df) >= 20:
            vol_sma = df["Volume"].rolling(20).mean().iloc[-1]
            threshold = 0.8 if len(df) < 60 else 1.1
            # If market-wide volume is extremely low (<50% avg), don't filter
            if vol_sma > 0 and df["Volume"].iloc[-1] / vol_sma > 0.5:
                if df["Volume"].iloc[-1] < vol_sma * threshold:
                    return None

        entry = last["Close"]
        swing_sl = find_recent_swing_low(df, lookback=8)
        cfg = get_strategy_config(_KEY)
        atr_sl = atr_stop_loss(df, entry, side="BUY", atr_mult=cfg["atr_mult"], min_pct=cfg["min_pct"])
        sl = min(swing_sl, atr_sl)
        risk = entry - sl
        if risk <= 0:
            return None

        target1 = entry + risk * 2

        return {
            "symbol": symbol,
            "signal_type": "BUY",
            "entry_price": round(entry, 2),
            "stop_loss": round(sl, 2),
            "target_1": round(target1, 2),
            "target_2": None,
            "risk": round(risk, 2),
            "reward": round(target1 - entry, 2),
            "risk_reward_ratio": "1:2",
            "current_price": round(last["Close"], 2),
            "strategy": "play2_triple_ma",
        }

    def _scan_short(self, df, last, prev, ago, symbol) -> Optional[dict]:
        # ── Trend condition: 20 EMA < 50 SMA < 200 SMA (stacked downward) ──
        if not (last["ema20"] < last["sma50"] < last["sma200"]):
            return None

        # ── MAs must be sloping downward ──
        if not (last["ema20"] < ago["ema20"] and last["sma50"] < ago["sma50"]):
            return None

        # ── Pullback UP to 20 EMA or 50 SMA ──
        near_ema20 = last["High"] >= last["ema20"] * 0.995
        near_sma50 = last["High"] >= last["sma50"] * 0.995
        if not (near_ema20 or near_sma50):
            return None

        # ── Confirm with bearish candlestick pattern (relaxed: red candle also qualifies) ──
        is_red = last["Close"] < last["Open"]
        if not is_red and not has_bearish_reversal(last, prev):
            return None

        # Volume confirmation — relaxed for low-volume sessions
        if len(df) >= 20:
            vol_sma = df["Volume"].rolling(20).mean().iloc[-1]
            threshold = 0.8 if len(df) < 60 else 1.1
            # If market-wide volume is extremely low (<50% avg), don't filter
            if vol_sma > 0 and df["Volume"].iloc[-1] / vol_sma > 0.5:
                if df["Volume"].iloc[-1] < vol_sma * threshold:
                    return None

        entry = last["Close"]
        swing_sl = find_recent_swing_high(df, lookback=8)
        cfg = get_strategy_config(_KEY)
        atr_sl = atr_stop_loss(df, entry, side="SELL", atr_mult=cfg["atr_mult"], min_pct=cfg["min_pct"])
        sl = max(swing_sl, atr_sl)
        risk = sl - entry
        if risk <= 0:
            return None

        target1 = entry - risk * 2

        return {
            "symbol": symbol,
            "signal_type": "SELL",
            "entry_price": round(entry, 2),
            "stop_loss": round(sl, 2),
            "target_1": round(target1, 2),
            "target_2": None,
            "risk": round(risk, 2),
            "reward": round(entry - target1, 2),
            "risk_reward_ratio": "1:2",
            "current_price": round(last["Close"], 2),
            "strategy": "play2_triple_ma",
        }
