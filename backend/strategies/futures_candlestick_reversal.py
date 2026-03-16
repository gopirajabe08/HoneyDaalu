"""
Futures Strategy #2: Candlestick Reversal
──────────────────────────────────────────
Timeframe : 15m / 1h / 1d
Indicators: Trend detection, Candlestick patterns, Volume

LONG Setup (Pivot):
  - At least 3 of the last 5 COMPLETED candles have lower closes
  - Reversal candle: Hammer, Bullish Engulfing, or Strong Green
  - Volume > average (1.0x SMA20 — relaxed, reversals often have normal volume)
  - OI sentiment: soft filter (boosts priority)

SHORT Setup (Pivot):
  - At least 3 of the last 5 COMPLETED candles have higher closes
  - Reversal candle: Shooting Star, Bearish Engulfing, or Strong Red
  - Volume > average
  - OI sentiment: soft filter

Execution:
  Entry : Signal bar close (no confirmation wait for intraday)
  SL    : Below/Above reversal candle extreme + ATR buffer
  Target: 1:1.5 Risk-Reward ratio
"""

import pandas as pd
from typing import Optional

from .futures_base import (
    FuturesBaseStrategy,
    calc_sma,
    atr_stop_loss,
)
from .base import (
    is_hammer,
    is_shooting_star,
    is_bullish_engulfing,
    is_bearish_engulfing,
    is_strong_green,
    is_strong_red,
)

_KEY = "futures_candlestick_reversal"

LONG_OI = {"short_covering", "long_buildup"}
SHORT_OI = {"long_unwinding", "short_buildup"}


class FuturesCandlestickReversal(FuturesBaseStrategy):
    name = "Candlestick Reversal"
    description = "Downtrend (3-of-5 lower closes) + Hammer/Engulfing reversal. Volume above average."
    category = "Reversal"
    indicators = ["5-bar trend (3-of-5)", "Hammer/Shooting Star", "Engulfing patterns", "Volume SMA(20)"]
    timeframes = ["15m", "1h", "1d"]
    long_setup = "3-of-5 lower closes + Hammer/Bullish Engulfing + Volume > avg + OI soft filter"
    short_setup = "3-of-5 higher closes + Shooting Star/Bearish Engulfing + Volume > avg + OI soft filter"
    exit_rules = "Target at 1:1.5 R:R ratio."
    stop_loss_rules = "Below reversal candle low + ATR buffer (BUY) / Above reversal candle high + ATR buffer (SELL)."

    def scan(self, df: pd.DataFrame, symbol: str, oi_data: dict | None = None) -> dict | None:
        if len(df) < 25:
            return None

        df = df.copy()
        df["vol_sma"] = calc_sma(df["Volume"], 20)

        # Use COMPLETED candle: signal_bar = iloc[-2]
        signal_bar = df.iloc[-2]
        prev_bar = df.iloc[-3]

        if pd.isna(signal_bar["vol_sma"]) or signal_bar["vol_sma"] <= 0:
            return None

        # Volume above average (relaxed from 1.2x)
        vol_ratio = signal_bar["Volume"] / signal_bar["vol_sma"]
        if vol_ratio < 1.0:
            return None

        sentiment = oi_data.get("sentiment", "") if oi_data else ""

        # Trend: 5 bars before signal bar
        trend_closes = df["Close"].iloc[-7:-2]
        if len(trend_closes) < 5:
            return None

        diffs = trend_closes.diff().dropna()
        down_count = (diffs < 0).sum()
        up_count = (diffs > 0).sum()

        has_downtrend = down_count >= 3
        has_uptrend = up_count >= 3

        # ── LONG reversal ──
        if has_downtrend:
            is_reversal = (
                is_hammer(signal_bar)
                or is_bullish_engulfing(signal_bar, prev_bar)
                or is_strong_green(signal_bar)
            )
            if not is_reversal:
                return None

            oi_aligned = (not sentiment) or (sentiment in LONG_OI)

            entry = round(signal_bar["Close"], 2)
            sl = round(min(signal_bar["Low"], prev_bar["Low"]), 2)
            atr_sl = atr_stop_loss(df.iloc[:-1], entry, side="BUY", atr_mult=1.5)
            sl = max(sl, atr_sl)

            risk = entry - sl
            if risk <= 0:
                return None
            target = round(entry + risk * 1.5, 2)

            return {
                "symbol": symbol,
                "signal_type": "BUY",
                "entry_price": entry,
                "stop_loss": sl,
                "target_1": target,
                "risk": round(risk, 2),
                "reward": round(target - entry, 2),
                "risk_reward_ratio": "1:1.5",
                "current_price": round(df.iloc[-1]["Close"], 2),
                "volume_ratio": round(vol_ratio, 1),
                "oi_sentiment": sentiment,
                "oi_aligned": oi_aligned,
                "strategy": _KEY,
            }

        # ── SHORT reversal ──
        if has_uptrend:
            is_reversal = (
                is_shooting_star(signal_bar)
                or is_bearish_engulfing(signal_bar, prev_bar)
                or is_strong_red(signal_bar)
            )
            if not is_reversal:
                return None

            oi_aligned = (not sentiment) or (sentiment in SHORT_OI)

            entry = round(signal_bar["Close"], 2)
            sl = round(max(signal_bar["High"], prev_bar["High"]), 2)
            atr_sl = atr_stop_loss(df.iloc[:-1], entry, side="SELL", atr_mult=1.5)
            sl = min(sl, atr_sl)

            risk = sl - entry
            if risk <= 0:
                return None
            target = round(entry - risk * 1.5, 2)

            return {
                "symbol": symbol,
                "signal_type": "SELL",
                "entry_price": entry,
                "stop_loss": sl,
                "target_1": target,
                "risk": round(risk, 2),
                "reward": round(entry - target, 2),
                "risk_reward_ratio": "1:1.5",
                "current_price": round(df.iloc[-1]["Close"], 2),
                "volume_ratio": round(vol_ratio, 1),
                "oi_sentiment": sentiment,
                "oi_aligned": oi_aligned,
                "strategy": _KEY,
            }

        return None
