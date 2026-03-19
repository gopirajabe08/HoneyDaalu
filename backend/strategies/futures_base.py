"""
Base class for futures strategies.

Each futures strategy scans OHLCV data and optionally receives OI sentiment data.
The scan returns a signal dict (BUY/SELL) or None. Strategies support both
LONG and SHORT signals since futures allow shorting.
"""

import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import Optional


class FuturesBaseStrategy(ABC):
    """Base class for all futures screener strategies."""

    name: str = ""
    description: str = ""
    category: str = ""
    indicators: list[str] = []
    timeframes: list[str] = []
    long_setup: str = ""
    short_setup: str = ""
    exit_rules: str = ""
    stop_loss_rules: str = ""

    @abstractmethod
    def scan(self, df: pd.DataFrame, symbol: str, oi_data: Optional[dict] = None) -> Optional[dict]:
        """
        Scan a stock's OHLCV data for entry signals.

        Args:
            df: DataFrame with columns [Open, High, Low, Close, Volume]
            symbol: Stock symbol (e.g. "RELIANCE")
            oi_data: Optional OI sentiment dict from futures_oi_analyser
                     {"sentiment": "long_buildup", "conviction": 0.8, ...}

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


# ── Indicator Helpers (futures-specific) ──────────────────────────────────


def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calc_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def calc_sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def calc_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0):
    """Calculate Bollinger Bands. Returns (middle, upper, lower, bandwidth)."""
    middle = calc_sma(df["Close"], period)
    std = df["Close"].rolling(window=period).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    bandwidth = (upper - lower) / middle
    return middle, upper, lower, bandwidth


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
                  atr_mult: float = 2.5, atr_period: int = 14,
                  min_pct: float = 0.012) -> float:
    """ATR-based stop loss with minimum % floor."""
    atr = calc_atr(df, atr_period)
    atr_val = atr.iloc[-1] if pd.notna(atr.iloc[-1]) else entry * min_pct
    sl_distance = max(atr_val * atr_mult, entry * min_pct)

    if side == "BUY":
        return round(entry - sl_distance, 2)
    else:
        return round(entry + sl_distance, 2)
