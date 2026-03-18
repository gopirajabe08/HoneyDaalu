"""
Equity Market Regime Detector — auto-selects which of the 6 equity strategies to activate.

Analyzes:
  1. NIFTY 50 trend (price vs 20 EMA, 50 SMA + ADX for trend strength)
  2. India VIX (volatility environment)
  3. NIFTY intraday range (gap/reversal detection)

Maps regime → recommended equity strategies:
  - Strong trend + Low VIX    → Play 1 (EMA), 2 (Triple MA), 3 (VWAP), 4 (Supertrend)
  - Strong trend + High VIX   → Play 1 (EMA), 2 (Triple MA) on 15m only
  - Pullback in trend          → Play 3 (VWAP), 6 (BB Contra)
  - Sideways + Low VIX         → Play 5 (BB Squeeze), 6 (BB Contra)
  - Sideways + High VIX        → Play 5 (BB Squeeze) only
  - Reversal / Whipsaw         → Play 6 (BB Contra) only
"""

import logging
from datetime import datetime, timezone, timedelta

import yfinance as yf
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))


def _get_nifty_analysis() -> dict:
    """Analyze NIFTY 50 trend + ADX + intraday range."""
    try:
        # Daily data for trend + ADX
        ticker = yf.Ticker("^NSEI")
        daily = ticker.history(period="60d", interval="1d")
        if daily is None or len(daily) < 50:
            return {"trend": "neutral", "strength": "weak", "adx": 0, "intraday_range_pct": 0}

        close = daily["Close"]
        price = float(close.iloc[-1])
        ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
        sma50 = float(close.rolling(50).mean().iloc[-1])

        # ADX
        adx = _calc_adx(daily, 14)
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
            strength = "weak"

        # Override to sideways if ADX is weak
        if strength == "weak" and trend in ("bullish", "bearish"):
            trend = "sideways"

        # Today's intraday range (for reversal detection)
        today_open = float(daily["Open"].iloc[-1])
        today_high = float(daily["High"].iloc[-1])
        today_low = float(daily["Low"].iloc[-1])
        today_close = float(daily["Close"].iloc[-1])
        intraday_range_pct = (today_high - today_low) / today_open * 100

        # Reversal detection: big range + close opposite to open direction
        opened_down = today_open > today_close * 1.005  # opened significantly higher than close
        closed_up = today_close > today_open  # but closed green
        is_reversal = intraday_range_pct > 1.5 and ((opened_down and closed_up) or (not opened_down and not closed_up and intraday_range_pct > 2.0))

        if is_reversal:
            trend = "reversal"

        return {
            "trend": trend,
            "strength": strength,
            "adx": round(adx_val, 1),
            "price": round(price, 2),
            "ema20": round(ema20, 2),
            "sma50": round(sma50, 2),
            "dist_ema20_pct": round(dist_ema20, 2),
            "intraday_range_pct": round(intraday_range_pct, 2),
            "is_reversal": is_reversal,
        }
    except Exception as e:
        logger.warning(f"[EquityRegime] Nifty analysis error: {e}")
        return {"trend": "neutral", "strength": "weak", "adx": 0, "intraday_range_pct": 0}


def _calc_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate ADX for trend strength."""
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
        return 15.0
    except Exception:
        return 15.0


# ── Regime → Strategy + Timeframe Mapping ─────────────────────────────────

REGIME_STRATEGY_MAP = {
    # Strong trending — use trend-following strategies
    ("bullish", "low_vol"):     [("play1_ema_crossover", "15m"), ("play2_triple_ma", "15m"), ("play3_vwap_pullback", "5m"), ("play4_supertrend", "5m")],
    ("bullish", "normal"):      [("play1_ema_crossover", "15m"), ("play2_triple_ma", "15m"), ("play3_vwap_pullback", "5m"), ("play4_supertrend", "15m")],
    ("bullish", "high_vol"):    [("play1_ema_crossover", "15m"), ("play2_triple_ma", "15m")],

    ("bearish", "low_vol"):     [("play1_ema_crossover", "15m"), ("play2_triple_ma", "15m"), ("play3_vwap_pullback", "5m"), ("play4_supertrend", "5m")],
    ("bearish", "normal"):      [("play1_ema_crossover", "15m"), ("play2_triple_ma", "15m"), ("play3_vwap_pullback", "5m"), ("play4_supertrend", "15m")],
    ("bearish", "high_vol"):    [("play1_ema_crossover", "15m"), ("play2_triple_ma", "15m")],

    # Pullback — VWAP catches bounce + BB Contra fades overextension
    ("pullback_in_uptrend", "low_vol"):   [("play3_vwap_pullback", "5m"), ("play6_bb_contra", "15m")],
    ("pullback_in_uptrend", "normal"):    [("play3_vwap_pullback", "5m"), ("play6_bb_contra", "15m")],
    ("pullback_in_uptrend", "high_vol"):  [("play6_bb_contra", "15m")],

    ("bounce_in_downtrend", "low_vol"):   [("play3_vwap_pullback", "5m"), ("play6_bb_contra", "15m")],
    ("bounce_in_downtrend", "normal"):    [("play3_vwap_pullback", "5m"), ("play6_bb_contra", "15m")],
    ("bounce_in_downtrend", "high_vol"):  [("play6_bb_contra", "15m")],

    # Sideways — BB strategies thrive
    ("sideways", "low_vol"):    [("play5_bb_squeeze", "15m"), ("play6_bb_contra", "15m")],
    ("sideways", "normal"):     [("play5_bb_squeeze", "15m"), ("play6_bb_contra", "15m")],
    ("sideways", "high_vol"):   [("play5_bb_squeeze", "15m")],

    # Reversal / Whipsaw — only mean reversion
    ("reversal", "low_vol"):    [("play6_bb_contra", "15m")],
    ("reversal", "normal"):     [("play6_bb_contra", "15m")],
    ("reversal", "high_vol"):   [("play6_bb_contra", "15m")],

    # Neutral fallback
    ("neutral", "low_vol"):     [("play1_ema_crossover", "15m"), ("play5_bb_squeeze", "15m"), ("play6_bb_contra", "15m")],
    ("neutral", "normal"):      [("play1_ema_crossover", "15m"), ("play6_bb_contra", "15m")],
    ("neutral", "high_vol"):    [("play6_bb_contra", "15m")],
}


def _get_intraday_direction() -> dict:
    """Check NIFTY intraday direction — is today bullish or bearish from open?"""
    try:
        ticker = yf.Ticker("^NSEI")
        intra = ticker.history(period="1d", interval="5m")
        if intra is None or len(intra) < 5:
            return {"direction": "neutral", "change_pct": 0}

        session_open = float(intra["Open"].iloc[0])
        current = float(intra["Close"].iloc[-1])
        change_pct = (current - session_open) / session_open * 100

        if change_pct > 0.3:
            direction = "intraday_bullish"
        elif change_pct < -0.3:
            direction = "intraday_bearish"
        else:
            direction = "intraday_neutral"

        return {
            "direction": direction,
            "change_pct": round(change_pct, 2),
            "session_open": round(session_open, 2),
            "current": round(current, 2),
        }
    except Exception as e:
        logger.warning(f"[EquityRegime] Intraday direction error: {e}")
        return {"direction": "neutral", "change_pct": 0}


def detect_equity_regime() -> dict:
    """
    Detect market regime and auto-select equity strategies + timeframes.
    Uses daily trend + VIX + ADX + INTRADAY DIRECTION.

    Intraday direction overrides daily trend when they conflict:
    - Daily bearish but intraday bullish → mixed (use BB Contra + VWAP, not trend strategies)
    - Daily bullish but intraday bearish → mixed
    - Both agree → strong conviction, use trend strategies
    """
    nifty = _get_nifty_analysis()
    vix = _get_vix()
    intraday = _get_intraday_direction()

    daily_trend = nifty.get("trend", "neutral")
    intraday_dir = intraday.get("direction", "neutral")
    intraday_change = intraday.get("change_pct", 0)

    # VIX classification
    if vix > 20:
        vol_level = "high_vol"
    elif vix < 14:
        vol_level = "low_vol"
    else:
        vol_level = "normal"

    # Determine effective trend — intraday direction can override daily
    if daily_trend in ("bearish",) and intraday_dir == "intraday_bullish":
        # Daily says bearish but today is green — CONFLICT
        # Don't trust bearish SELL signals — use neutral/reversal strategies
        effective_trend = "bounce_in_downtrend"
    elif daily_trend in ("bullish",) and intraday_dir == "intraday_bearish":
        # Daily says bullish but today is red — CONFLICT
        effective_trend = "pullback_in_uptrend"
    elif nifty.get("is_reversal", False):
        effective_trend = "reversal"
    else:
        # Daily and intraday agree, or intraday is neutral
        effective_trend = daily_trend

    # Get strategies from map
    key = (effective_trend, vol_level)
    strat_list = REGIME_STRATEGY_MAP.get(key, [("play1_ema_crossover", "15m"), ("play6_bb_contra", "15m")])

    strategies = [{"strategy": s, "timeframe": tf} for s, tf in strat_list]
    strategy_ids = [s for s, _ in strat_list]

    regime_label = f"{effective_trend}_{vol_level}"
    if effective_trend != daily_trend:
        regime_label += f"_override_{intraday_dir}"

    STRAT_NAMES = {
        "play1_ema_crossover": "EMA Crossover",
        "play2_triple_ma": "Triple MA",
        "play3_vwap_pullback": "VWAP Pullback",
        "play4_supertrend": "Supertrend",
        "play5_bb_squeeze": "BB Squeeze",
        "play6_bb_contra": "BB Contra",
    }

    reasoning_parts = [
        f"Daily: {daily_trend} (ADX {nifty.get('adx', 0)})",
        f"Intraday: {intraday_dir} ({intraday_change:+.2f}%)",
        f"Effective: {effective_trend}",
        f"VIX: {vix:.1f} ({vol_level.replace('_', ' ')})",
        f"Selected: {', '.join(STRAT_NAMES.get(s, s) for s in strategy_ids)}",
    ]

    return {
        "regime": regime_label,
        "strategies": strategies,
        "strategy_ids": strategy_ids,
        "components": {
            "nifty": nifty,
            "vix": round(vix, 1),
            "vix_level": vol_level,
            "intraday": intraday,
        },
        "reasoning": " | ".join(reasoning_parts),
    }
