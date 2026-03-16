"""
Play #1: The "EMA-EMA" Crossover Setup
───────────────────────────────────────
Timeframe : 15-min / Hourly / Daily
Indicators: 9 EMA (Fast) & 21 EMA (Slow). Optional Filter: 50 SMA.

Long  Setup: 9 EMA crosses ABOVE 21 EMA. Optional: Price above 50 SMA.
Short Setup: 9 EMA crosses BELOW 21 EMA. Optional: Price below 50 SMA.
Exit       : Opposite crossover (9 crosses back under/over 21).
             Alternative: Fixed Risk-Reward target (1:2).

Swing improvements:
  - Market regime filter (Nifty 50 SMA)
  - Crossover quality filter (minimum EMA gap)
  - ADX trend strength filter (ADX > 25)
  - ATR-based SL (tighter than swing low in weak markets)
  - SMA50 slope check (must be rising for BUY, falling for SELL)
  - Minimum distance from SMA50 (at least 1.5% above/below)
"""

import pandas as pd
import yfinance as yf
from typing import Optional

from .base import (
    BaseStrategy,
    calc_ema,
    calc_sma,
    calc_atr,
    find_recent_swing_low,
    find_recent_swing_high,
    atr_stop_loss,
    get_strategy_config,
)

_KEY = "play1_ema_crossover"

# ── Swing filter thresholds ──────────────────────────────────────────────
_MIN_EMA_GAP_PCT = 0.003       # 0.3% minimum gap between EMA9 and EMA21
_MIN_ADX = 25                   # Minimum ADX for trend confirmation
_SMA50_SLOPE_LOOKBACK = 5      # Days to check SMA50 slope
_MIN_SMA50_DISTANCE_PCT = 0.015  # 1.5% minimum distance from SMA50
_NIFTY_SMA_PERIOD = 50          # Nifty 50 SMA period for regime filter


def _calc_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate ADX (Average Directional Index) for trend strength."""
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)

    # True Range
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    # Directional Movement
    plus_dm = high - prev_high
    minus_dm = prev_low - low
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    # Smoothed TR, +DM, -DM
    atr = tr.ewm(alpha=1/period, min_periods=period).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, min_periods=period).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, min_periods=period).mean() / atr)

    # ADX
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di) * 100
    adx = dx.ewm(alpha=1/period, min_periods=period).mean()
    return adx


def _get_nifty_sma50_regime() -> str:
    """
    Check if Nifty 50 is above or below its 50 SMA.
    Returns 'BULLISH', 'BEARISH', or 'NEUTRAL'.
    """
    try:
        ticker = yf.Ticker("^NSEI")
        df = ticker.history(period="3mo", interval="1d")
        if df is None or df.empty or len(df) < 55:
            return "NEUTRAL"
        df["sma50"] = df["Close"].rolling(50).mean()
        last = df.iloc[-1]
        if pd.isna(last["sma50"]):
            return "NEUTRAL"
        close = float(last["Close"])
        sma50 = float(last["sma50"])
        gap_pct = (close - sma50) / sma50
        if gap_pct > 0.01:   # > 1% above
            return "BULLISH"
        elif gap_pct < -0.01:  # > 1% below
            return "BEARISH"
        return "NEUTRAL"
    except Exception:
        return "NEUTRAL"


class EMA_Crossover(BaseStrategy):
    name = "EMA-EMA Crossover"
    description = "Buy/sell when 9 EMA crosses 21 EMA, filtered by 50 SMA trend direction."
    category = "Trend Following (Momentum Capture)"
    indicators = ["9 EMA (Fast)", "21 EMA (Slow)", "50 SMA (Trend Filter)", "ADX (Trend Strength)"]
    timeframes = ["15m", "1h", "1d"]
    long_setup = "9 EMA crosses ABOVE 21 EMA. Price above 50 SMA (confirms broad uptrend)."
    short_setup = "9 EMA crosses BELOW 21 EMA. Price below 50 SMA."
    exit_rules = "Exit when opposite crossover occurs (9 crosses back under/over 21). Alternative: Fixed 1:2 Risk-Reward target."
    stop_loss_rules = "Below recent swing low for long, above recent swing high for short. ATR-based SL used for swing trades."

    def scan(self, df: pd.DataFrame, symbol: str) -> Optional[dict]:
        if len(df) < 55:
            return None

        df = df.copy()
        df["ema9"] = calc_ema(df["Close"], 9)
        df["ema21"] = calc_ema(df["Close"], 21)
        df["sma50"] = calc_sma(df["Close"], 50)

        last = df.iloc[-1]
        prev = df.iloc[-2]

        # ── Validate indicators ──
        if pd.isna(last["ema9"]) or pd.isna(last["ema21"]) or pd.isna(prev["ema9"]) or pd.isna(prev["ema21"]):
            return None

        # Detect timeframe from data frequency
        is_daily = self._is_daily_timeframe(df)

        # ── BUY signal: 9 EMA crosses above 21 EMA ──
        buy_crossover = prev["ema9"] <= prev["ema21"] and last["ema9"] > last["ema21"]
        # 50 SMA filter
        sma50_ok = pd.notna(last["sma50"]) and last["Close"] > last["sma50"]

        if buy_crossover and sma50_ok:
            # Apply swing filters for daily timeframe
            if is_daily:
                rejection = self._swing_filters(df, last, "BUY")
                if rejection:
                    return None

            entry = last["Close"]
            cfg = get_strategy_config(_KEY)

            if is_daily:
                # Swing: use ATR-based SL (tighter, more responsive)
                sl = atr_stop_loss(df, entry, side="BUY", atr_mult=1.5, min_pct=cfg["min_pct"])
            else:
                # Intraday: use wider of swing low and ATR
                swing_sl = find_recent_swing_low(df, lookback=10)
                atr_sl = atr_stop_loss(df, entry, side="BUY", atr_mult=cfg["atr_mult"], min_pct=cfg["min_pct"])
                sl = min(swing_sl, atr_sl)

            risk = entry - sl
            if risk <= 0:
                return None
            target1 = entry + risk * 2  # 1:2 R:R

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
                "strategy": "play1_ema_crossover",
            }

        # ── SELL signal: 9 EMA crosses below 21 EMA ──
        sell_crossover = prev["ema9"] >= prev["ema21"] and last["ema9"] < last["ema21"]
        sma50_sell_ok = pd.notna(last["sma50"]) and last["Close"] < last["sma50"]

        if sell_crossover and sma50_sell_ok:
            # Apply swing filters for daily timeframe
            if is_daily:
                rejection = self._swing_filters(df, last, "SELL")
                if rejection:
                    return None

            entry = last["Close"]
            cfg = get_strategy_config(_KEY)

            if is_daily:
                # Swing: use ATR-based SL (tighter)
                sl = atr_stop_loss(df, entry, side="SELL", atr_mult=1.5, min_pct=cfg["min_pct"])
            else:
                # Intraday: use wider of swing high and ATR
                swing_sl = find_recent_swing_high(df, lookback=10)
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
                "strategy": "play1_ema_crossover",
            }

        return None

    def _is_daily_timeframe(self, df: pd.DataFrame) -> bool:
        """Detect if the DataFrame is daily data based on index frequency."""
        if len(df) < 2:
            return False
        try:
            diff = (df.index[-1] - df.index[-2]).total_seconds()
            return diff > 3600 * 12  # > 12 hours = daily
        except Exception:
            return False

    def _swing_filters(self, df: pd.DataFrame, last: pd.Series, side: str) -> Optional[str]:
        """
        Apply additional swing trade filters. Returns rejection reason or None if passed.

        Filters:
          1. Market regime (Nifty 50 SMA) — don't BUY in bearish market
          2. Crossover quality (minimum EMA gap)
          3. ADX trend strength (> 25)
          4. SMA50 slope (must be rising for BUY, falling for SELL)
          5. Minimum distance from SMA50 (1.5%)
        """
        price = float(last["Close"])
        ema9 = float(last["ema9"])
        ema21 = float(last["ema21"])
        sma50 = float(last["sma50"]) if pd.notna(last["sma50"]) else 0

        # ── Filter 1: Market regime (Nifty above/below 50 SMA) ──
        nifty_regime = _get_nifty_sma50_regime()
        if side == "BUY" and nifty_regime == "BEARISH":
            return "Nifty below 50 SMA — skip BUY in bearish market"
        if side == "SELL" and nifty_regime == "BULLISH":
            return "Nifty above 50 SMA — skip SELL in bullish market"

        # ── Filter 2: Crossover quality (minimum EMA gap) ──
        ema_gap_pct = abs(ema9 - ema21) / price if price > 0 else 0
        if ema_gap_pct < _MIN_EMA_GAP_PCT:
            return f"EMA gap too small ({ema_gap_pct:.4f} < {_MIN_EMA_GAP_PCT}) — likely whipsaw"

        # ── Filter 3: ADX trend strength ──
        adx = _calc_adx(df, period=14)
        adx_val = float(adx.iloc[-1]) if pd.notna(adx.iloc[-1]) else 0
        if adx_val < _MIN_ADX:
            return f"ADX too low ({adx_val:.1f} < {_MIN_ADX}) — no clear trend"

        # ── Filter 4: SMA50 slope (must be trending in signal direction) ──
        if sma50 > 0 and len(df) > _SMA50_SLOPE_LOOKBACK:
            sma50_prev = float(df["sma50"].iloc[-_SMA50_SLOPE_LOOKBACK - 1]) if pd.notna(df["sma50"].iloc[-_SMA50_SLOPE_LOOKBACK - 1]) else 0
            if sma50_prev > 0:
                sma50_slope = (sma50 - sma50_prev) / sma50_prev
                if side == "BUY" and sma50_slope < 0:
                    return f"SMA50 declining ({sma50_slope:.4f}) — weak trend for BUY"
                if side == "SELL" and sma50_slope > 0:
                    return f"SMA50 rising ({sma50_slope:.4f}) — weak trend for SELL"

        # ── Filter 5: Minimum distance from SMA50 ──
        if sma50 > 0:
            distance_pct = (price - sma50) / sma50
            if side == "BUY" and distance_pct < _MIN_SMA50_DISTANCE_PCT:
                return f"Price too close to SMA50 ({distance_pct:.3f} < {_MIN_SMA50_DISTANCE_PCT}) — weak conviction"
            if side == "SELL" and distance_pct > -_MIN_SMA50_DISTANCE_PCT:
                return f"Price too close to SMA50 ({distance_pct:.3f} > -{_MIN_SMA50_DISTANCE_PCT}) — weak conviction"

        return None  # All filters passed
