"""
Market Regime Detector — determines market conviction to auto-select options strategy.
Uses India VIX, PCR, and Nifty trend (price vs 20 EMA, 50 SMA).
"""

import logging
from datetime import datetime, timezone, timedelta

import yfinance as yf
import pandas as pd

from services.options_client import get_india_vix, get_spot_price, get_option_chain, calculate_pcr

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


def _get_nifty_trend() -> dict:
    """Analyze Nifty 50 trend using daily candles."""
    try:
        ticker = yf.Ticker("^NSEI")
        df = ticker.history(period="200d", interval="1d")
        if df is None or len(df) < 200:
            return {"trend": "neutral", "price": 0, "ema20": 0, "sma50": 0, "sma200": 0}

        close = df["Close"]
        price = float(close.iloc[-1])
        ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
        sma50 = float(close.rolling(50).mean().iloc[-1])
        sma200 = float(close.rolling(200).mean().iloc[-1])

        # Determine trend
        above_ema20 = price > ema20
        above_sma50 = price > sma50
        above_sma200 = price > sma200

        # Distance from moving averages (as percentage)
        dist_ema20 = (price - ema20) / ema20 * 100
        dist_sma50 = (price - sma50) / sma50 * 100

        if above_ema20 and above_sma50 and above_sma200:
            trend = "bullish"
        elif not above_ema20 and not above_sma50 and not above_sma200:
            trend = "bearish"
        elif above_sma200 and not above_ema20:
            trend = "pullback_in_uptrend"
        elif not above_sma200 and above_ema20:
            trend = "bounce_in_downtrend"
        else:
            trend = "neutral"

        return {
            "trend": trend,
            "price": round(price, 2),
            "ema20": round(ema20, 2),
            "sma50": round(sma50, 2),
            "sma200": round(sma200, 2),
            "dist_ema20_pct": round(dist_ema20, 2),
            "dist_sma50_pct": round(dist_sma50, 2),
            "above_ema20": above_ema20,
            "above_sma50": above_sma50,
            "above_sma200": above_sma200,
        }
    except Exception as e:
        logger.warning(f"[MarketRegime] Failed to get Nifty trend: {e}")
        return {"trend": "neutral", "price": 0, "ema20": 0, "sma50": 0, "sma200": 0}


def _get_intraday_direction() -> dict:
    """Check NIFTY intraday direction using current session data."""
    try:
        ticker = yf.Ticker("^NSEI")
        intra = ticker.history(period="1d", interval="5m")
        if intra is None or len(intra) < 5:
            return {"direction": "neutral", "change_pct": 0}

        session_open = float(intra["Open"].iloc[0])
        current = float(intra["Close"].iloc[-1])
        session_high = float(intra["High"].max())
        session_low = float(intra["Low"].min())

        change_pct = (current - session_open) / session_open * 100
        range_pct = (session_high - session_low) / session_open * 100

        if change_pct > 0.5:
            direction = "intraday_bullish"
        elif change_pct < -0.5:
            direction = "intraday_bearish"
        else:
            direction = "intraday_neutral"

        return {
            "direction": direction,
            "change_pct": round(change_pct, 2),
            "range_pct": round(range_pct, 2),
            "session_open": round(session_open, 2),
            "current": round(current, 2),
        }
    except Exception as e:
        logger.warning(f"[MarketRegime] Intraday direction error: {e}")
        return {"direction": "neutral", "change_pct": 0}


def detect_regime(underlying: str = "NIFTY") -> dict:
    """
    Detect current market regime using daily trend + VIX + PCR + intraday direction.

    Returns:
        {
            "conviction": str,
            "score": float (-1 to 1),
            "recommended_strategies": list[str],
            "components": {vix, pcr, trend, intraday}
        }
    """
    vix = get_india_vix()
    nifty_trend = _get_nifty_trend()
    intraday = _get_intraday_direction()

    # Try to get PCR
    pcr = 1.0
    try:
        chain = get_option_chain(underlying, "weekly")
        if "error" not in chain:
            pcr = calculate_pcr(chain)
    except Exception:
        pass

    # ── Score calculation ──

    # VIX component
    if vix < 13:
        vix_score = 0.0
    elif vix < 16:
        vix_score = 0.0
    elif vix < 20:
        vix_score = -0.1
    else:
        vix_score = -0.15  # High VIX — slight bearish bias but no longer overrides everything

    # PCR component
    if pcr > 1.2:
        pcr_score = 0.3
    elif pcr > 0.8:
        pcr_score = 0.0
    elif pcr > 0.5:
        pcr_score = -0.3
    else:
        pcr_score = -0.5

    # Daily trend component
    trend = nifty_trend.get("trend", "neutral")
    dist_ema = nifty_trend.get("dist_ema20_pct", 0)

    if trend == "bullish":
        trend_score = 0.4 if dist_ema > 1 else 0.2
    elif trend == "pullback_in_uptrend":
        trend_score = 0.1
    elif trend == "bearish":
        trend_score = -0.4 if dist_ema < -1 else -0.2
    elif trend == "bounce_in_downtrend":
        trend_score = -0.1
    else:
        trend_score = 0.0

    # Intraday direction component (NEW — overrides daily trend when they conflict)
    intraday_dir = intraday.get("direction", "neutral")
    intraday_change = intraday.get("change_pct", 0)

    if intraday_dir == "intraday_bullish":
        intraday_score = 0.3  # Strong bullish intraday signal
    elif intraday_dir == "intraday_bearish":
        intraday_score = -0.3
    else:
        intraday_score = 0.0

    # RSI divergence on NIFTY — enhances reversal detection for options
    rsi_score = 0.0
    try:
        from services.market_data import fetch_stock_data
        nifty_df = fetch_stock_data("NIFTY 50", "15m")
        if nifty_df is None:
            nifty_df = fetch_stock_data("^NSEI", "15m")
        if nifty_df is not None and len(nifty_df) >= 20:
            from strategies.base import calc_rsi
            rsi = calc_rsi(nifty_df, 14)
            rsi_val = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50
            if rsi_val > 70:
                rsi_score = -0.15  # Overbought — slight bearish bias for options
            elif rsi_val < 30:
                rsi_score = 0.15   # Oversold — slight bullish bias
    except Exception:
        pass

    # Gap detection on NIFTY — morning gaps influence option premium direction
    gap_score = 0.0
    try:
        gap_pct = intraday.get("change_pct", 0)
        if abs(gap_pct) > 1.0:
            # Large gap — strong directional signal for options
            gap_score = 0.2 if gap_pct > 0 else -0.2
    except Exception:
        pass

    score = vix_score + pcr_score + trend_score + intraday_score + rsi_score + gap_score

    # ── Map score to conviction ──
    if vix > 22 and abs(intraday_change) < 0.3:
        # Very high VIX + no clear intraday direction → straddle
        conviction = "high_volatility"
        strategies = ["long_straddle"]
    elif score > 0.5:
        conviction = "strongly_bullish"
        strategies = ["bull_call_spread"]
    elif score > 0.15:
        conviction = "mildly_bullish"
        strategies = ["bull_put_spread"]
    elif score > -0.15:
        conviction = "neutral"
        strategies = ["iron_condor"]
    elif score > -0.5:
        conviction = "mildly_bearish"
        strategies = ["bear_call_spread"]
    else:
        conviction = "strongly_bearish"
        strategies = ["bear_put_spread"]

    return {
        "conviction": conviction,
        "score": round(score, 3),
        "recommended_strategies": strategies,
        "components": {
            "vix": round(vix, 2),
            "vix_signal": "LOW" if vix < 13 else "NORMAL" if vix < 16 else "ELEVATED" if vix < 20 else "HIGH",
            "pcr": pcr,
            "pcr_signal": "BULLISH" if pcr > 1.2 else "NEUTRAL" if pcr > 0.8 else "BEARISH",
            "nifty_trend": nifty_trend,
            "intraday": intraday,
            "score_breakdown": {
                "vix_score": round(vix_score, 3),
                "pcr_score": round(pcr_score, 3),
                "trend_score": round(trend_score, 3),
                "intraday_score": round(intraday_score, 3),
                "rsi_score": round(rsi_score, 3),
                "gap_score": round(gap_score, 3),
            }
        }
    }
