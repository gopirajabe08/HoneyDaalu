"""
Futures Market Regime Detector — auto-selects which futures strategies to activate.

Analyzes 3 components:
  1. NIFTY trend (price vs MAs, ADX for trend strength)
  2. India VIX (volatility environment)
  3. Aggregate F&O OI sentiment (net long buildup vs short buildup)

Maps regime → recommended futures strategies:
  - Strong trend + High VIX    → Volume Breakout (momentum in volatility)
  - Strong trend + Normal VIX  → Volume Breakout + EMA RSI Pullback (trend continuation)
  - Pullback in trend          → EMA RSI Pullback + Candlestick Reversal (pullback entries)
  - Sideways + Low VIX         → Mean Reversion (range-bound plays)
  - Sideways + High VIX        → Volume Breakout (breakout from range with vol)
  - Bearish trend              → All SHORT strategies enabled
"""

import logging
from datetime import timezone, timedelta

import yfinance as yf
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))


def _get_nifty_trend() -> dict:
    """Analyze Nifty 50 trend using daily candles + ADX for trend strength."""
    try:
        ticker = yf.Ticker("^NSEI")
        df = ticker.history(period="100d", interval="1d")
        if df is None or len(df) < 50:
            return {"trend": "neutral", "strength": "weak", "adx": 0}

        close = df["Close"]
        price = float(close.iloc[-1])
        ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
        sma50 = float(close.rolling(50).mean().iloc[-1])

        # ADX calculation for trend strength
        adx = _calc_adx(df, 14)
        adx_val = float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 15

        above_ema20 = price > ema20
        above_sma50 = price > sma50
        dist_ema20 = (price - ema20) / ema20 * 100

        # Trend classification
        if above_ema20 and above_sma50:
            trend = "bullish"
        elif not above_ema20 and not above_sma50:
            trend = "bearish"
        elif above_sma50 and not above_ema20:
            trend = "pullback_in_uptrend"
        elif not above_sma50 and above_ema20:
            trend = "bounce_in_downtrend"
        else:
            trend = "sideways"

        # Strength from ADX
        if adx_val > 30:
            strength = "strong"
        elif adx_val > 20:
            strength = "moderate"
        else:
            strength = "weak"  # sideways / range-bound

        return {
            "trend": trend,
            "strength": strength,
            "adx": round(adx_val, 1),
            "price": round(price, 2),
            "ema20": round(ema20, 2),
            "sma50": round(sma50, 2),
            "dist_ema20_pct": round(dist_ema20, 2),
        }
    except Exception as e:
        logger.warning(f"[FuturesRegime] Nifty trend error: {e}")
        return {"trend": "neutral", "strength": "weak", "adx": 0}


def _calc_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average Directional Index for trend strength."""
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr = tr.ewm(span=period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(span=period, adjust=False).mean()
    return adx


def _get_vix() -> float:
    """Get India VIX level."""
    try:
        ticker = yf.Ticker("^INDIAVIX")
        hist = ticker.history(period="5d", interval="1d")
        if hist is not None and len(hist) > 0:
            return float(hist["Close"].iloc[-1])
        return 15.0  # default neutral
    except Exception:
        return 15.0


def _get_oi_sentiment_summary(oi_data: dict | None = None) -> dict:
    """
    Summarize OI sentiment across all F&O stocks.
    Returns aggregate counts and dominant sentiment.
    """
    if not oi_data:
        return {"dominant": "neutral", "counts": {}, "bullish_pct": 50}

    counts = {"long_buildup": 0, "short_covering": 0, "short_buildup": 0, "long_unwinding": 0}
    for sym, data in oi_data.items():
        sentiment = data.get("sentiment", "")
        if sentiment in counts:
            counts[sentiment] += 1

    total = sum(counts.values()) or 1
    bullish = counts["long_buildup"] + counts["short_covering"]
    bearish = counts["short_buildup"] + counts["long_unwinding"]
    bullish_pct = round(bullish / total * 100, 1)

    if bullish_pct > 60:
        dominant = "bullish"
    elif bullish_pct < 40:
        dominant = "bearish"
    else:
        dominant = "neutral"

    return {
        "dominant": dominant,
        "counts": counts,
        "bullish_pct": bullish_pct,
        "bearish_pct": round(bearish / total * 100, 1),
    }


# ── Regime → Strategy Mapping ─────────────────────────────────────────────

REGIME_STRATEGY_MAP = {
    # (trend_type, vol_level) → [strategies]
    # Strong trending markets → momentum + trend continuation
    ("bullish", "high_vol"): ["futures_volume_breakout"],
    ("bullish", "normal"):   ["futures_volume_breakout", "futures_ema_rsi_pullback"],
    ("bullish", "low_vol"):  ["futures_ema_rsi_pullback"],

    ("bearish", "high_vol"): ["futures_volume_breakout"],
    ("bearish", "normal"):   ["futures_volume_breakout", "futures_ema_rsi_pullback"],
    ("bearish", "low_vol"):  ["futures_ema_rsi_pullback"],

    # Pullback in trend → pullback + reversal strategies
    ("pullback_in_uptrend", "high_vol"):  ["futures_ema_rsi_pullback", "futures_candlestick_reversal"],
    ("pullback_in_uptrend", "normal"):    ["futures_ema_rsi_pullback", "futures_candlestick_reversal"],
    ("pullback_in_uptrend", "low_vol"):   ["futures_ema_rsi_pullback", "futures_mean_reversion"],

    ("bounce_in_downtrend", "high_vol"):  ["futures_ema_rsi_pullback", "futures_candlestick_reversal"],
    ("bounce_in_downtrend", "normal"):    ["futures_ema_rsi_pullback", "futures_candlestick_reversal"],
    ("bounce_in_downtrend", "low_vol"):   ["futures_ema_rsi_pullback", "futures_mean_reversion"],

    # Sideways / range-bound → mean reversion + breakout (for breakout from range)
    ("sideways", "high_vol"):  ["futures_volume_breakout", "futures_candlestick_reversal"],
    ("sideways", "normal"):    ["futures_mean_reversion", "futures_candlestick_reversal"],
    ("sideways", "low_vol"):   ["futures_mean_reversion"],

    # Neutral fallback
    ("neutral", "high_vol"):  ["futures_volume_breakout", "futures_candlestick_reversal"],
    ("neutral", "normal"):    ["futures_ema_rsi_pullback", "futures_mean_reversion"],
    ("neutral", "low_vol"):   ["futures_mean_reversion"],
}

# Default timeframes per strategy for auto mode
AUTO_TIMEFRAMES = {
    "futures_volume_breakout": "15m",
    "futures_candlestick_reversal": "15m",
    "futures_mean_reversion": "1h",
    "futures_ema_rsi_pullback": "15m",
}

AUTO_SWING_TIMEFRAMES = {
    "futures_volume_breakout": "1h",
    "futures_candlestick_reversal": "1h",
    "futures_mean_reversion": "1d",
    "futures_ema_rsi_pullback": "1h",
}


def detect_futures_regime(oi_data: dict | None = None) -> dict:
    """
    Detect market regime and auto-select futures strategies.

    Returns:
        {
            "regime": "trending_bullish" | "trending_bearish" | "pullback" | "sideways" | etc,
            "strategies": [{"strategy": key, "timeframe": tf}, ...],
            "swing_strategies": [{"strategy": key, "timeframe": tf}, ...],
            "components": {nifty_trend, vix, oi_summary},
            "reasoning": str
        }
    """
    nifty = _get_nifty_trend()
    vix = _get_vix()
    oi_summary = _get_oi_sentiment_summary(oi_data)

    trend = nifty.get("trend", "neutral")
    strength = nifty.get("strength", "weak")

    # Classify volatility
    if vix > 20:
        vol_level = "high_vol"
    elif vix < 13:
        vol_level = "low_vol"
    else:
        vol_level = "normal"

    # Override trend to sideways if ADX is weak regardless of MA position
    if strength == "weak" and trend in ("bullish", "bearish"):
        trend = "sideways"

    # Get strategies from map
    key = (trend, vol_level)
    strategy_ids = REGIME_STRATEGY_MAP.get(key, ["futures_ema_rsi_pullback", "futures_mean_reversion"])

    # Build strategy selections with timeframes
    intraday_strats = [
        {"strategy": s, "timeframe": AUTO_TIMEFRAMES.get(s, "15m")}
        for s in strategy_ids
    ]
    swing_strats = [
        {"strategy": s, "timeframe": AUTO_SWING_TIMEFRAMES.get(s, "1h")}
        for s in strategy_ids
    ]

    # Build regime label
    regime_label = f"{trend}_{vol_level}"
    if oi_summary["dominant"] != "neutral":
        regime_label += f"_oi_{oi_summary['dominant']}"

    # Build reasoning
    reasoning_parts = [
        f"NIFTY: {trend} (ADX {nifty.get('adx', 0)}, strength: {strength})",
        f"VIX: {vix:.1f} ({vol_level.replace('_', ' ')})",
        f"OI: {oi_summary['dominant']} ({oi_summary['bullish_pct']}% bullish)",
        f"Selected: {', '.join(strategy_ids)}",
    ]

    return {
        "regime": regime_label,
        "strategies": intraday_strats,
        "swing_strategies": swing_strats,
        "strategy_ids": strategy_ids,
        "components": {
            "nifty_trend": nifty,
            "vix": round(vix, 1),
            "vix_level": vol_level,
            "oi_summary": oi_summary,
        },
        "reasoning": " | ".join(reasoning_parts),
    }
