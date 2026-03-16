"""Base strategy class and candlestick pattern helpers."""

import json
import os
import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import Optional

# ── Strategy Config (tunable parameters) ─────────────────────────────────

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "strategy_config.json")
_config_cache = {}
_config_mtime = 0


def get_strategy_config(strategy_key: str) -> dict:
    """Load tunable parameters for a strategy. Auto-reloads if file changed."""
    global _config_cache, _config_mtime
    try:
        mtime = os.path.getmtime(_CONFIG_PATH)
        if mtime != _config_mtime:
            with open(_CONFIG_PATH, "r") as f:
                _config_cache = json.load(f)
            _config_mtime = mtime
    except Exception:
        pass

    defaults = {"atr_mult": 1.5, "min_pct": 0.005, "atr_period": 14, "enabled": True, "preferred_timeframe": "15m"}
    cfg = _config_cache.get(strategy_key, {})
    return {**defaults, **cfg}


class BaseStrategy(ABC):
    """Base class for all playbook strategies."""

    name: str = ""
    description: str = ""
    category: str = ""
    indicators: list[str] = []
    timeframes: list[str] = []
    long_setup: str = ""
    short_setup: Optional[str] = None
    exit_rules: str = ""
    stop_loss_rules: str = ""

    @abstractmethod
    def scan(self, df: pd.DataFrame, symbol: str) -> Optional[dict]:
        """
        Scan a stock's OHLCV data for entry signals.

        Args:
            df: DataFrame with columns [Open, High, Low, Close, Volume]
            symbol: Stock symbol

        Returns:
            dict with signal details or None if no signal.
        """
        pass

    def info(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "indicators": self.indicators,
            "timeframes": self.timeframes,
            "long_setup": self.long_setup,
            "short_setup": self.short_setup,
            "exit_rules": self.exit_rules,
            "stop_loss_rules": self.stop_loss_rules,
        }


# ── Candlestick Pattern Helpers ────────────────────────────────────────────


def is_bullish_candle(row: pd.Series) -> bool:
    return row["Close"] > row["Open"]


def is_bearish_candle(row: pd.Series) -> bool:
    return row["Close"] < row["Open"]


def body_size(row: pd.Series) -> float:
    return abs(row["Close"] - row["Open"])


def candle_range(row: pd.Series) -> float:
    return row["High"] - row["Low"]


def lower_shadow(row: pd.Series) -> float:
    return min(row["Open"], row["Close"]) - row["Low"]


def upper_shadow(row: pd.Series) -> float:
    return row["High"] - max(row["Open"], row["Close"])


def is_hammer(row: pd.Series) -> bool:
    """Hammer: small body at top, lower shadow >= 2x body."""
    b = body_size(row)
    r = candle_range(row)
    if r == 0 or b == 0:
        return False
    ls = lower_shadow(row)
    us = upper_shadow(row)
    return ls >= 2 * b and us <= b * 0.5 and b / r <= 0.35


def is_bullish_engulfing(curr: pd.Series, prev: pd.Series) -> bool:
    """Current green candle body engulfs previous red candle body."""
    if not is_bearish_candle(prev) or not is_bullish_candle(curr):
        return False
    return curr["Open"] <= prev["Close"] and curr["Close"] >= prev["Open"]


def is_doji(row: pd.Series) -> bool:
    """Body size < 10% of total range."""
    r = candle_range(row)
    if r == 0:
        return True
    return body_size(row) / r < 0.10


def is_strong_green(row: pd.Series) -> bool:
    """Strong bullish candle: body > 50% of range and closes in top third."""
    r = candle_range(row)
    if r == 0:
        return False
    b = body_size(row)
    return is_bullish_candle(row) and b / r > 0.50


def has_bullish_reversal(curr: pd.Series, prev: pd.Series) -> bool:
    """Check for any bullish reversal pattern: hammer, engulfing, doji, strong green."""
    return (
        is_hammer(curr)
        or is_bullish_engulfing(curr, prev)
        or (is_doji(prev) and is_bullish_candle(curr))
        or is_strong_green(curr)
    )


# ── Bearish Reversal Patterns ────────────────────────────────────────────


def is_shooting_star(row: pd.Series) -> bool:
    """Shooting Star: small body at bottom, upper shadow >= 2x body."""
    b = body_size(row)
    r = candle_range(row)
    if r == 0 or b == 0:
        return False
    us = upper_shadow(row)
    ls = lower_shadow(row)
    return us >= 2 * b and ls <= b * 0.5 and b / r <= 0.35


def is_bearish_engulfing(curr: pd.Series, prev: pd.Series) -> bool:
    """Current red candle body engulfs previous green candle body."""
    if not is_bullish_candle(prev) or not is_bearish_candle(curr):
        return False
    return curr["Open"] >= prev["Close"] and curr["Close"] <= prev["Open"]


def is_strong_red(row: pd.Series) -> bool:
    """Strong bearish candle: body > 50% of range and closes in bottom third."""
    r = candle_range(row)
    if r == 0:
        return False
    b = body_size(row)
    return is_bearish_candle(row) and b / r > 0.50


def has_bearish_reversal(curr: pd.Series, prev: pd.Series) -> bool:
    """Check for any bearish reversal pattern: shooting star, engulfing, doji, strong red."""
    return (
        is_shooting_star(curr)
        or is_bearish_engulfing(curr, prev)
        or (is_doji(prev) and is_bearish_candle(curr))
        or is_strong_red(curr)
    )


# ── Indicator Helpers ──────────────────────────────────────────────────────


def calc_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def calc_sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def calc_vwap(df: pd.DataFrame) -> pd.Series:
    """Calculate session VWAP (assumes single-day session data)."""
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
    cum_tp_vol = (typical_price * df["Volume"]).cumsum()
    cum_vol = df["Volume"].cumsum()
    return cum_tp_vol / cum_vol


def calc_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0):
    """
    Calculate Supertrend indicator.
    Returns (supertrend_line, direction) where direction 1=up, -1=down.
    """
    hl2 = (df["High"] + df["Low"]) / 2

    # True Range
    prev_close = df["Close"].shift(1)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - prev_close).abs(),
        (df["Low"] - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr = tr.rolling(window=period).mean()

    upper_band = hl2 + multiplier * atr
    lower_band = hl2 - multiplier * atr

    supertrend = pd.Series(np.nan, index=df.index)
    direction = pd.Series(0, index=df.index, dtype=int)

    for i in range(period, len(df)):
        # Carry forward bands
        if i > period:
            if df["Close"].iat[i - 1] > upper_band.iat[i - 1]:
                direction.iat[i] = 1
            elif df["Close"].iat[i - 1] < lower_band.iat[i - 1]:
                direction.iat[i] = -1
            else:
                direction.iat[i] = direction.iat[i - 1]

            if direction.iat[i] == 1 and lower_band.iat[i] < lower_band.iat[i - 1]:
                lower_band.iat[i] = lower_band.iat[i - 1]
            if direction.iat[i] == -1 and upper_band.iat[i] > upper_band.iat[i - 1]:
                upper_band.iat[i] = upper_band.iat[i - 1]
        else:
            direction.iat[i] = 1 if df["Close"].iat[i] > upper_band.iat[i] else -1

        supertrend.iat[i] = lower_band.iat[i] if direction.iat[i] == 1 else upper_band.iat[i]

    return supertrend, direction


def calc_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0):
    """Calculate Bollinger Bands. Returns (middle, upper, lower, bandwidth)."""
    middle = calc_sma(df["Close"], period)
    std = df["Close"].rolling(window=period).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    bandwidth = (upper - lower) / middle
    return middle, upper, lower, bandwidth


def find_recent_swing_high(df: pd.DataFrame, lookback: int = 10) -> float:
    """Find the most recent swing high in the lookback window."""
    window = df.tail(lookback)
    return window["High"].max()


def find_recent_swing_low(df: pd.DataFrame, lookback: int = 10) -> float:
    """Find the most recent swing low in the lookback window."""
    window = df.tail(lookback)
    return window["Low"].min()


def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range."""
    prev_close = df["Close"].shift(1)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - prev_close).abs(),
        (df["Low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def atr_stop_loss(df: pd.DataFrame, entry: float, side: str = "BUY",
                  atr_mult: float = 1.5, atr_period: int = 14,
                  min_pct: float = 0.012) -> float:
    """
    Calculate ATR-based stop loss with a minimum % floor.

    Args:
        df: OHLCV DataFrame
        entry: entry price
        side: "BUY" or "SELL"
        atr_mult: ATR multiplier (1.5 = standard)
        atr_period: ATR lookback period
        min_pct: minimum SL distance as % of entry (1.2% default — prevents noise stops)
    """
    atr = calc_atr(df, atr_period)
    atr_val = atr.iloc[-1] if pd.notna(atr.iloc[-1]) else entry * min_pct
    sl_distance = max(atr_val * atr_mult, entry * min_pct)

    if side == "BUY":
        return round(entry - sl_distance, 2)
    else:
        return round(entry + sl_distance, 2)
