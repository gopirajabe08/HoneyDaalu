"""
Futures Strategy #1: Volume Breakout
─────────────────────────────────────
Timeframe : 15m / 1h / 1d
Indicators: 20-day High, Volume (20-period SMA), ATR(14)

LONG Setup:
  - COMPLETED candle closes above 20-period high
  - Volume > 1.5x average (relaxed from 2x)
  - Breakout magnitude > 0.3 ATR (relaxed from 0.5)
  - OI sentiment: HARD filter — blocks trade if sentiment conflicts

SHORT Setup:
  - COMPLETED candle closes below 20-period low
  - Volume > 1.5x average
  - Breakdown magnitude > 0.3 ATR
  - OI sentiment: HARD filter — blocks trade if sentiment conflicts

Execution:
  Entry : Signal bar close (no confirmation bar wait for intraday)
  SL    : ATR-based (1.5x ATR)
  Target: 1:2 Risk-Reward ratio
"""

import pandas as pd
from typing import Optional

from .futures_base import (
    FuturesBaseStrategy,
    calc_sma,
    calc_atr,
    atr_stop_loss,
)

_KEY = "futures_volume_breakout"

LONG_OI = {"long_buildup", "short_covering"}
SHORT_OI = {"short_buildup", "long_unwinding"}


class FuturesVolumeBreakout(FuturesBaseStrategy):
    name = "Volume Breakout"
    description = "Breakout to 20-period high/low with volume surge (>1.5x average) and ATR-confirmed magnitude."
    category = "Momentum"
    indicators = ["20-period High/Low", "Volume SMA(20)", "ATR(14)"]
    timeframes = ["15m", "1h", "1d"]
    long_setup = "Completed candle breaks 20-period high + Volume > 1.5x SMA(20) + breakout > 0.3 ATR + OI hard filter"
    short_setup = "Completed candle breaks 20-period low + Volume > 1.5x SMA(20) + breakdown > 0.3 ATR + OI hard filter"
    exit_rules = "Target at 1:2 R:R ratio."
    stop_loss_rules = "ATR-based stop loss (1.5x ATR)."

    def scan(self, df: pd.DataFrame, symbol: str, oi_data: Optional[dict] = None) -> Optional[dict]:
        if len(df) < 25:
            return None

        df = df.copy()
        df["vol_sma"] = calc_sma(df["Volume"], 20)
        df["atr"] = calc_atr(df, 14)

        # Use COMPLETED candle (iloc[-2]) for signal
        signal_bar = df.iloc[-2]
        prev_bar = df.iloc[-3]

        # 20-period high/low EXCLUDING the signal bar
        lookback = df.iloc[-22:-2]
        if len(lookback) < 20:
            return None

        high_20 = lookback["High"].max()
        low_20 = lookback["Low"].min()

        if pd.isna(signal_bar["vol_sma"]) or pd.isna(signal_bar["atr"]):
            return None

        vol_ratio = signal_bar["Volume"] / signal_bar["vol_sma"] if signal_bar["vol_sma"] > 0 else 0
        if vol_ratio < 1.5:
            return None

        atr_val = signal_bar["atr"]
        if pd.isna(atr_val) or atr_val <= 0:
            return None

        sentiment = oi_data.get("sentiment", "") if oi_data else ""
        oi_aligned = False

        # ── LONG ──
        if signal_bar["Close"] > high_20 and signal_bar["Close"] > prev_bar["Close"]:
            breakout_mag = signal_bar["Close"] - high_20
            if breakout_mag < atr_val * 0.3:
                return None

            # P1-003: OI is HARD filter — block BUY when sentiment conflicts
            if sentiment and sentiment in SHORT_OI:
                return None

            oi_aligned = (not sentiment) or (sentiment in LONG_OI)

            entry = round(signal_bar["Close"], 2)
            sl = atr_stop_loss(df.iloc[:-1], entry, side="BUY", atr_mult=1.5)
            risk = entry - sl
            if risk <= 0:
                return None
            target = round(entry + risk * 2, 2)

            return {
                "symbol": symbol,
                "signal_type": "BUY",
                "entry_price": entry,
                "stop_loss": sl,
                "target_1": target,
                "risk": round(risk, 2),
                "reward": round(target - entry, 2),
                "risk_reward_ratio": "1:2",
                "current_price": round(df.iloc[-1]["Close"], 2),
                "volume_ratio": round(vol_ratio, 1),
                "oi_sentiment": sentiment,
                "oi_aligned": oi_aligned,
                "strategy": _KEY,
            }

        # ── SHORT ──
        if signal_bar["Close"] < low_20 and signal_bar["Close"] < prev_bar["Close"]:
            breakdown_mag = low_20 - signal_bar["Close"]
            if breakdown_mag < atr_val * 0.3:
                return None

            # P1-003: OI is HARD filter — block SELL when sentiment conflicts
            if sentiment and sentiment in LONG_OI:
                return None

            oi_aligned = (not sentiment) or (sentiment in SHORT_OI)

            entry = round(signal_bar["Close"], 2)
            sl = atr_stop_loss(df.iloc[:-1], entry, side="SELL", atr_mult=1.5)
            risk = sl - entry
            if risk <= 0:
                return None
            target = round(entry - risk * 2, 2)

            return {
                "symbol": symbol,
                "signal_type": "SELL",
                "entry_price": entry,
                "stop_loss": sl,
                "target_1": target,
                "risk": round(risk, 2),
                "reward": round(entry - target, 2),
                "risk_reward_ratio": "1:2",
                "current_price": round(df.iloc[-1]["Close"], 2),
                "volume_ratio": round(vol_ratio, 1),
                "oi_sentiment": sentiment,
                "oi_aligned": oi_aligned,
                "strategy": _KEY,
            }

        return None
