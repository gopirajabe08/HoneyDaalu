"""
Futures Strategy #4: EMA & RSI Pullback
────────────────────────────────────────
Timeframe : 15m / 1h / 1d
Indicators: 50 EMA, RSI(14), Volume SMA(20)

LONG Setup (Trend Pullback):
  - COMPLETED candle Close > 50 EMA (uptrend)
  - Price within 5% of 50 EMA (relaxed from 3%)
  - RSI between 35-60 (relaxed from 40-55)
  - Volume > average (1.0x SMA20 — relaxed from 1.5x)
  - OI sentiment: HARD filter — blocks trade if sentiment conflicts

SHORT Setup:
  - COMPLETED candle Close < 50 EMA (downtrend)
  - Price within 5% of 50 EMA
  - RSI between 40-65 (relaxed from 45-60)
  - Volume > average
  - OI sentiment: HARD filter — blocks trade if sentiment conflicts

Execution:
  Entry : Signal bar close
  SL    : ATR-based (1.5x ATR)
  Target: 1:2 Risk-Reward ratio
"""

import pandas as pd
from typing import Optional

from .futures_base import (
    FuturesBaseStrategy,
    calc_rsi,
    calc_ema,
    calc_sma,
    atr_stop_loss,
)

_KEY = "futures_ema_rsi_pullback"

LONG_OI = {"long_buildup", "short_covering"}
SHORT_OI = {"short_buildup", "long_unwinding"}


class FuturesEmaRsiPullback(FuturesBaseStrategy):
    name = "EMA & RSI Pullback"
    description = "Price within 5% of 50 EMA (pullback) + RSI in pullback zone + Volume above avg. Trend continuation."
    category = "Trend"
    indicators = ["50 EMA", "RSI(14)", "Volume SMA(20)"]
    timeframes = ["15m", "1h", "1d"]
    long_setup = "Close > 50 EMA + within 5% of EMA + RSI 35-60 + Volume > avg + OI hard filter"
    short_setup = "Close < 50 EMA + within 5% of EMA + RSI 40-65 + Volume > avg + OI hard filter"
    exit_rules = "Target at 1:2 R:R ratio."
    stop_loss_rules = "ATR-based stop loss (1.5x ATR)."

    def scan(self, df: pd.DataFrame, symbol: str, oi_data: dict | None = None) -> dict | None:
        if len(df) < 55:
            return None

        df = df.copy()
        df["ema_50"] = calc_ema(df["Close"], 50)
        df["rsi"] = calc_rsi(df["Close"], 14)
        df["vol_sma"] = calc_sma(df["Volume"], 20)

        signal_bar = df.iloc[-2]

        if pd.isna(signal_bar["ema_50"]) or pd.isna(signal_bar["rsi"]) or pd.isna(signal_bar["vol_sma"]):
            return None

        # Volume above average (relaxed from 1.5x)
        vol_ratio = signal_bar["Volume"] / signal_bar["vol_sma"] if signal_bar["vol_sma"] > 0 else 0
        if vol_ratio < 1.0:
            return None

        rsi = signal_bar["rsi"]
        ema_50 = signal_bar["ema_50"]
        close = signal_bar["Close"]

        # EMA proximity — within 5% (relaxed from 3%)
        ema_dist_pct = abs(close - ema_50) / ema_50 if ema_50 > 0 else 1
        if ema_dist_pct > 0.05:
            return None

        sentiment = oi_data.get("sentiment", "") if oi_data else ""

        # ── LONG: price above 50 EMA, RSI 35-60 ──
        if close > ema_50 and 35 <= rsi <= 60:
            # P1-003: OI is HARD filter — block BUY when sentiment conflicts
            if sentiment and sentiment in SHORT_OI:
                return None

            oi_aligned = (not sentiment) or (sentiment in LONG_OI)

            entry = round(close, 2)
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
                "rsi": round(rsi, 1),
                "volume_ratio": round(vol_ratio, 1),
                "oi_sentiment": sentiment,
                "oi_aligned": oi_aligned,
                "strategy": _KEY,
            }

        # ── SHORT: price below 50 EMA, RSI 40-65 ──
        if close < ema_50 and 40 <= rsi <= 65:
            # P1-003: OI is HARD filter — block SELL when sentiment conflicts
            if sentiment and sentiment in LONG_OI:
                return None

            oi_aligned = (not sentiment) or (sentiment in SHORT_OI)

            entry = round(close, 2)
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
                "rsi": round(rsi, 1),
                "volume_ratio": round(vol_ratio, 1),
                "oi_sentiment": sentiment,
                "oi_aligned": oi_aligned,
                "strategy": _KEY,
            }

        return None
