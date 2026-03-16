"""
Market data service — fetches OHLCV candles and Nifty 50 trend via yfinance.

Provides helpers for individual stock data, batch fetching with thread-pool
concurrency, and a cached Nifty 50 trend check used by strategies that
require broad-market confirmation (e.g. 200 SMA filter).
"""

import yfinance as yf
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from functools import lru_cache
from datetime import datetime, timezone, timedelta
import time

from nifty500 import get_yfinance_symbol
from config import INTERVAL_PERIOD_MAP

IST = timezone(timedelta(hours=5, minutes=30))


def _is_market_hours() -> bool:
    """Check if we're currently within NSE trading hours (9:15-15:30 IST)."""
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    t = now.time()
    from datetime import time as dtime
    return dtime(9, 15) <= t <= dtime(15, 30)


# Simple in-memory cache: {(symbol, interval): (timestamp, dataframe)}
_cache: dict[tuple, tuple[float, pd.DataFrame]] = {}
CACHE_TTL_SECONDS = 120  # 2 minutes


def _get_cached(symbol: str, interval: str) -> Optional[pd.DataFrame]:
    key = (symbol, interval)
    if key in _cache:
        ts, df = _cache[key]
        if time.time() - ts < CACHE_TTL_SECONDS:
            return df.copy()
    return None


def _set_cache(symbol: str, interval: str, df: pd.DataFrame):
    _cache[(symbol, interval)] = (time.time(), df)


def fetch_stock_data(
    nse_symbol: str,
    interval: str = "15m",
    period: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV data for a single NSE stock.

    Args:
        nse_symbol: NSE symbol (e.g., "RELIANCE")
        interval: Candle interval (e.g., "5m", "15m", "1d")
        period: Data period (e.g., "5d", "30d"). Auto-selected if None.

    Returns:
        DataFrame with [Open, High, Low, Close, Volume] or None on error.
    """
    cached = _get_cached(nse_symbol, interval)
    if cached is not None:
        return cached

    if period is None:
        period = INTERVAL_PERIOD_MAP.get(interval, "30d")

    yf_symbol = get_yfinance_symbol(nse_symbol)

    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=period, interval=interval)

        if df is None or df.empty:
            return None

        # Keep only OHLCV columns
        required = ["Open", "High", "Low", "Close", "Volume"]
        for col in required:
            if col not in df.columns:
                return None

        df = df[required].copy()
        df.dropna(inplace=True)

        # Drop incomplete daily candle during market hours.
        # yfinance includes today's in-progress candle for "1d" interval,
        # which produces unreliable indicator signals.
        if interval == "1d" and _is_market_hours() and len(df) > 1:
            df = df.iloc[:-1]

        if len(df) < 5:
            return None

        _set_cache(nse_symbol, interval, df)
        return df

    except Exception:
        return None


def get_nifty_trend(timeframe: str = "5m") -> str:
    """
    Check Nifty 50 trend direction using VWAP and 20 EMA.

    Returns:
        "BULLISH"  — Nifty above both VWAP and 20 EMA (favour longs)
        "BEARISH"  — Nifty below both VWAP and 20 EMA (favour shorts)
        "NEUTRAL"  — mixed signals (allow both)
        "UNKNOWN"  — data unavailable
    """
    try:
        # Nifty 50 index on yfinance: ^NSEI
        cached = _get_cached("^NSEI_TREND", timeframe)
        if cached is not None:
            # cached stores a 1-row DF with trend info
            return cached.iloc[0]["trend"]

        ticker = yf.Ticker("^NSEI")
        period = INTERVAL_PERIOD_MAP.get(timeframe, "5d")
        df = ticker.history(period=period, interval=timeframe)

        if df is None or df.empty or len(df) < 20:
            return "UNKNOWN"

        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.dropna(inplace=True)

        if len(df) < 20:
            return "UNKNOWN"

        # Calculate VWAP
        typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
        cum_tp_vol = (typical_price * df["Volume"]).cumsum()
        cum_vol = df["Volume"].cumsum()
        df["vwap"] = cum_tp_vol / cum_vol

        # Calculate 20 EMA
        df["ema20"] = df["Close"].ewm(span=20, adjust=False).mean()

        last = df.iloc[-1]
        above_vwap = last["Close"] > last["vwap"]
        above_ema = last["Close"] > last["ema20"]

        if above_vwap and above_ema:
            trend = "BULLISH"
        elif not above_vwap and not above_ema:
            trend = "BEARISH"
        else:
            trend = "NEUTRAL"

        # Cache the result (uses standard 2-min TTL)
        result_df = pd.DataFrame([{"trend": trend}])
        _set_cache("^NSEI_TREND", timeframe, result_df)

        return trend

    except Exception:
        return "UNKNOWN"


def fetch_bulk_data(
    symbols: list[str],
    interval: str = "15m",
    max_workers: int = 10,
) -> dict[str, pd.DataFrame]:
    """
    Fetch data for multiple symbols concurrently.

    Returns:
        dict mapping symbol -> DataFrame (only successful fetches).
    """
    results = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_symbol = {
            executor.submit(fetch_stock_data, sym, interval): sym
            for sym in symbols
        }

        for future in as_completed(future_to_symbol):
            symbol = future_to_symbol[future]
            try:
                df = future.result()
                if df is not None and not df.empty:
                    results[symbol] = df
            except Exception:
                pass

    return results


def get_stock_name(nse_symbol: str) -> str:
    """Get display name for a stock. Falls back to symbol."""
    try:
        ticker = yf.Ticker(get_yfinance_symbol(nse_symbol))
        info = ticker.info
        return info.get("longName", info.get("shortName", nse_symbol))
    except Exception:
        return nse_symbol
