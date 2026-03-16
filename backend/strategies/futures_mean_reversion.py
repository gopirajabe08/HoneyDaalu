"""
Futures Strategy #3: Mean Reversion
─────────────────────────────────────
Timeframe : 15m / 1h / 1d
Indicators: Bollinger Bands (20, 2), RSI(14), 200 EMA

LONG Setup (Value):
  - COMPLETED candle within bottom 15% of BB width
  - RSI < 40 (relaxed from 35)
  - Price > 200 EMA (macro uptrend filter)
  - OI sentiment: soft filter

SHORT Setup (Value):
  - COMPLETED candle within top 15% of BB width
  - RSI > 60 (relaxed from 65)
  - Price < 200 EMA (macro downtrend filter)
  - OI sentiment: soft filter

Execution:
  Entry : Signal bar close
  SL    : Beyond BB band or ATR-based (tighter wins)
  Target: Middle BB (20 SMA)
"""

import pandas as pd
from typing import Optional

from .futures_base import (
    FuturesBaseStrategy,
    calc_rsi,
    calc_ema,
    calc_bollinger_bands,
    atr_stop_loss,
)

_KEY = "futures_mean_reversion"

LONG_OI = {"short_covering", "long_buildup"}
SHORT_OI = {"long_unwinding", "short_buildup"}


class FuturesMeanReversion(FuturesBaseStrategy):
    name = "Mean Reversion"
    description = "Price near BB extreme + RSI extreme + 200 EMA trend filter. Relaxed thresholds for more signals."
    category = "Mean Reversion"
    indicators = ["Bollinger Bands (20, 2)", "RSI(14)", "200 EMA"]
    timeframes = ["15m", "1h", "1d"]
    long_setup = "Completed candle in bottom 15% of BB + RSI < 40 + Price > 200 EMA + OI soft filter"
    short_setup = "Completed candle in top 15% of BB + RSI > 60 + Price < 200 EMA + OI soft filter"
    exit_rules = "Target at Middle BB (20 SMA) — mean reversion."
    stop_loss_rules = "Beyond BB band or ATR-based (whichever tighter)."

    def scan(self, df: pd.DataFrame, symbol: str, oi_data: dict | None = None) -> dict | None:
        if len(df) < 210:
            return None

        df = df.copy()
        df["rsi"] = calc_rsi(df["Close"], 14)
        df["ema_200"] = calc_ema(df["Close"], 200)
        df["bb_mid"], df["bb_upper"], df["bb_lower"], _ = calc_bollinger_bands(df)

        signal_bar = df.iloc[-2]

        if pd.isna(signal_bar["rsi"]) or pd.isna(signal_bar["ema_200"]) or pd.isna(signal_bar["bb_mid"]):
            return None

        sentiment = oi_data.get("sentiment", "") if oi_data else ""

        bb_width = signal_bar["bb_upper"] - signal_bar["bb_lower"]
        if bb_width <= 0:
            return None

        # ── LONG: near lower BB, RSI < 40, above 200 EMA ──
        lower_dist = signal_bar["Close"] - signal_bar["bb_lower"]
        lower_dist_pct = lower_dist / bb_width

        if lower_dist_pct <= 0.15 and signal_bar["rsi"] < 40 and signal_bar["Close"] > signal_bar["ema_200"]:
            oi_aligned = (not sentiment) or (sentiment in LONG_OI)

            entry = round(signal_bar["Close"], 2)
            sl = round(signal_bar["bb_lower"] - bb_width * 0.05, 2)
            atr_sl = atr_stop_loss(df.iloc[:-1], entry, side="BUY", atr_mult=1.5)
            sl = max(sl, atr_sl)

            risk = entry - sl
            if risk <= 0:
                return None
            target = round(signal_bar["bb_mid"], 2)
            reward = target - entry
            if reward <= 0:
                return None

            rr = round(reward / risk, 1) if risk > 0 else 0

            return {
                "symbol": symbol,
                "signal_type": "BUY",
                "entry_price": entry,
                "stop_loss": sl,
                "target_1": target,
                "risk": round(risk, 2),
                "reward": round(reward, 2),
                "risk_reward_ratio": f"1:{rr}",
                "current_price": round(df.iloc[-1]["Close"], 2),
                "rsi": round(signal_bar["rsi"], 1),
                "oi_sentiment": sentiment,
                "oi_aligned": oi_aligned,
                "strategy": _KEY,
            }

        # ── SHORT: near upper BB, RSI > 60, below 200 EMA ──
        upper_dist = signal_bar["bb_upper"] - signal_bar["Close"]
        upper_dist_pct = upper_dist / bb_width

        if upper_dist_pct <= 0.15 and signal_bar["rsi"] > 60 and signal_bar["Close"] < signal_bar["ema_200"]:
            oi_aligned = (not sentiment) or (sentiment in SHORT_OI)

            entry = round(signal_bar["Close"], 2)
            sl = round(signal_bar["bb_upper"] + bb_width * 0.05, 2)
            atr_sl = atr_stop_loss(df.iloc[:-1], entry, side="SELL", atr_mult=1.5)
            sl = min(sl, atr_sl)

            risk = sl - entry
            if risk <= 0:
                return None
            target = round(signal_bar["bb_mid"], 2)
            reward = entry - target
            if reward <= 0:
                return None

            rr = round(reward / risk, 1) if risk > 0 else 0

            return {
                "symbol": symbol,
                "signal_type": "SELL",
                "entry_price": entry,
                "stop_loss": sl,
                "target_1": target,
                "risk": round(risk, 2),
                "reward": round(reward, 2),
                "risk_reward_ratio": f"1:{rr}",
                "current_price": round(df.iloc[-1]["Close"], 2),
                "rsi": round(signal_bar["rsi"], 1),
                "oi_sentiment": sentiment,
                "oi_aligned": oi_aligned,
                "strategy": _KEY,
            }

        return None
