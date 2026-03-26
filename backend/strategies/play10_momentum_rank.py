"""
Play #10: Momentum Ranking Strategy
────────────────────────────────────
Timeframe : 5-min or 15-min
Indicators: Rate of Change (ROC 10), Volume SMA (20), 20 EMA, RSI (14).

"Momentum stocks move in waves.
 Catch the strongest wave with volume confirmation."

Setup Conditions (Long / BUY):
  - ROC over last 10 candles > +2% (strong upward momentum).
  - Volume surge: current volume > 1.3x the 20-period SMA of volume.
  - Price is above the 20 EMA (trend filter).
  - RSI between 50 and 75 (strong momentum, not overbought).

Setup Conditions (Short / SELL):
  - ROC over last 10 candles < -2% (strong downward momentum).
  - Volume surge: current volume > 1.3x the 20-period SMA of volume.
  - Price is below the 20 EMA (trend filter).
  - RSI between 25 and 50 (weak momentum, not oversold).

Execution:
  Entry  : Current close price.
  SL     : ATR-based stop loss (via atr_stop_loss).
  Target : 2x SL distance (Risk-Reward 1:2).
"""

import pandas as pd
import numpy as np
from typing import Optional

from .base import (
    BaseStrategy,
    calc_ema,
    calc_sma,
    calc_rsi,
    atr_stop_loss,
    get_strategy_config,
)

_KEY = "play10_momentum_rank"


class MomentumRank(BaseStrategy):
    name = "Momentum Ranking"
    description = (
        "Ranks stocks by Rate of Change (ROC) with volume surge confirmation, "
        "20 EMA trend filter, and RSI momentum band."
    )
    category = "Intraday Momentum"
    indicators = ["ROC (10)", "Volume SMA (20)", "20 EMA", "RSI (14)"]
    timeframes = ["5m", "15m"]
    long_setup = (
        "ROC > +2%, volume > 1.3x 20-period avg, price above 20 EMA, "
        "RSI between 50-75 (strong but not overbought)."
    )
    short_setup = (
        "ROC < -2%, volume > 1.3x 20-period avg, price below 20 EMA, "
        "RSI between 25-50 (weak but not oversold)."
    )
    exit_rules = "Target at 2x SL distance (Risk-Reward 1:2)."
    stop_loss_rules = "ATR-based stop loss with minimum percentage floor."

    # ── Minimum candle requirement ──
    MIN_CANDLES = 25

    def scan(self, df: pd.DataFrame, symbol: str, **kwargs) -> Optional[dict]:
        if len(df) < self.MIN_CANDLES:
            return None

        df = df.copy()

        # ── Calculate indicators ──
        df["ema20"] = calc_ema(df["Close"], 20)
        df["rsi"] = calc_rsi(df["Close"], 14)
        df["vol_sma20"] = calc_sma(df["Volume"], 20)

        # Rate of Change over last 10 candles
        df["roc"] = (df["Close"] - df["Close"].shift(10)) / df["Close"].shift(10) * 100

        last = df.iloc[-1]

        # ── Validate indicators are computed ──
        if (
            pd.isna(last["ema20"])
            or pd.isna(last["rsi"])
            or pd.isna(last["vol_sma20"])
            or pd.isna(last["roc"])
        ):
            return None

        # ── Volume surge check (common to both sides) ──
        if last["vol_sma20"] <= 0:
            return None
        volume_ratio = last["Volume"] / last["vol_sma20"]
        if volume_ratio < 1.3:
            return None

        roc_val = last["roc"]
        rsi_val = last["rsi"]
        close = last["Close"]
        ema20 = last["ema20"]

        # ── ROC threshold — adaptive by timeframe ──
        timeframe = kwargs.get("timeframe", "15m")
        if timeframe in ("3m", "5m"):
            roc_thresh = 0.8   # 5m: smaller moves are significant
        elif timeframe == "15m":
            roc_thresh = 1.2   # 15m: ~10 candles = 2.5 hours
        else:
            roc_thresh = 2.0   # daily or higher

        # ── Route to long or short ──
        if roc_val > roc_thresh and close > ema20 and 50 <= rsi_val <= 75:
            return self._build_signal(df, symbol, "BUY", close, roc_val, volume_ratio)
        elif roc_val < -roc_thresh and close < ema20 and 25 <= rsi_val <= 50:
            return self._build_signal(df, symbol, "SELL", close, roc_val, volume_ratio)

        return None

    def _build_signal(
        self,
        df: pd.DataFrame,
        symbol: str,
        side: str,
        entry: float,
        roc_val: float,
        volume_ratio: float,
    ) -> Optional[dict]:
        """Build the signal dict for a BUY or SELL entry."""
        cfg = get_strategy_config(_KEY)
        sl = atr_stop_loss(
            df, entry, side=side,
            atr_mult=cfg["atr_mult"],
            min_pct=cfg["min_pct"],
        )

        if side == "BUY":
            risk = entry - sl
            if risk <= 0:
                return None
            target1 = entry + risk * 2
            target2 = entry + risk * 3
        else:  # SELL
            risk = sl - entry
            if risk <= 0:
                return None
            target1 = entry - risk * 2
            target2 = entry - risk * 3

        # ── Conviction score (0-100) based on ROC strength + volume ratio ──
        # ROC component: abs(roc) mapped from 2-10% -> 0-50 points
        roc_score = min(50, max(0, (abs(roc_val) - 2) / 8 * 50))
        # Volume component: volume_ratio mapped from 1.3-3.0x -> 0-50 points
        vol_score = min(50, max(0, (volume_ratio - 1.3) / 1.7 * 50))
        conviction = round(roc_score + vol_score)

        return {
            "symbol": symbol,
            "signal_type": side,
            "entry_price": round(entry, 2),
            "stop_loss": round(sl, 2),
            "target_1": round(target1, 2),
            "target_2": round(target2, 2),
            "risk": round(risk, 2),
            "reward": round(target1 - entry if side == "BUY" else entry - target1, 2),
            "risk_reward_ratio": "1:2",
            "current_price": round(entry, 2),
            "strategy": _KEY,
            "conviction": conviction,
            "roc": round(roc_val, 2),
            "volume_ratio": round(volume_ratio, 2),
        }
