"""
Market data service — fetches OHLCV candles via broker API (primary) with yfinance fallback.

Broker provides real-time data with 10 req/sec rate limit.
yfinance is used as fallback when broker is not authenticated or fails.
All consumers get the same DataFrame format: [Open, High, Low, Close, Volume].
"""

import yfinance as yf
import pandas as pd
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from datetime import datetime, timezone, timedelta
import time

from nifty500 import get_yfinance_symbol
from config import INTERVAL_PERIOD_MAP

logger = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))

# Broker interval mapping: our interval → broker resolution string
BROKER_INTERVAL_MAP = {
    "1m": "1",
    "3m": "3",
    "5m": "5",
    "10m": "10",
    "15m": "15",
    "30m": "30",
    "1h": "60",
    "1d": "D",
}

# How many calendar days of data to request per interval
BROKER_DAYS_MAP = {
    "5m": 30,
    "15m": 60,
    "30m": 60,
    "1h": 90,
    "1d": 365,
}


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


# Rate limiter for broker API (max 10 req/sec)
_last_broker_call = 0.0
_BROKER_MIN_INTERVAL = 0.1  # 100ms between calls = 10/sec


def _rate_limit_broker():
    """Ensure we don't exceed broker rate limit."""
    global _last_broker_call
    now = time.time()
    elapsed = now - _last_broker_call
    if elapsed < _BROKER_MIN_INTERVAL:
        time.sleep(_BROKER_MIN_INTERVAL - elapsed)
    _last_broker_call = time.time()


def _fetch_via_broker(nse_symbol: str, interval: str) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV data from broker history API.
    Returns DataFrame with [Open, High, Low, Close, Volume] or None.
    """
    try:
        from services.broker_client import get_fyers, is_authenticated, format_broker_symbol

        if not is_authenticated():
            return None

        broker = get_fyers()
        if broker is None:
            return None

        broker_resolution = BROKER_INTERVAL_MAP.get(interval)
        if not broker_resolution:
            return None

        # Calculate date range
        days = BROKER_DAYS_MAP.get(interval, 30)
        now = datetime.now(IST)
        date_from = (now - timedelta(days=days)).strftime("%Y-%m-%d")
        date_to = now.strftime("%Y-%m-%d")

        broker_symbol = format_broker_symbol(nse_symbol)

        _rate_limit_broker()

        data = {
            "symbol": broker_symbol,
            "resolution": broker_resolution,
            "date_format": "1",
            "range_from": date_from,
            "range_to": date_to,
            "cont_flag": "1",
        }

        response = broker.history(data=data)

        if not response or response.get("s") != "ok":
            return None

        candles = response.get("candles", [])
        if not candles or len(candles) < 5:
            return None

        # Broker candle format: [timestamp, open, high, low, close, volume]
        df = pd.DataFrame(candles, columns=["Timestamp", "Open", "High", "Low", "Close", "Volume"])
        df["Datetime"] = pd.to_datetime(df["Timestamp"], unit="s", utc=True).dt.tz_convert(IST)
        df.set_index("Datetime", inplace=True)
        df.drop(columns=["Timestamp"], inplace=True)

        # Ensure correct types
        for col in ["Open", "High", "Low", "Close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0).astype(int)

        df.dropna(subset=["Open", "High", "Low", "Close"], inplace=True)

        # Drop incomplete daily candle during market hours
        if interval == "1d" and _is_market_hours() and len(df) > 1:
            df = df.iloc[:-1]

        if len(df) < 5:
            return None

        return df[["Open", "High", "Low", "Close", "Volume"]]

    except Exception as e:
        logger.debug(f"[MarketData] Broker fetch failed for {nse_symbol} ({interval}): {e}")
        return None


def _fetch_via_yfinance(nse_symbol: str, interval: str, period: Optional[str] = None) -> Optional[pd.DataFrame]:
    """Fallback: Fetch via yfinance (15-min delayed)."""
    if period is None:
        period = INTERVAL_PERIOD_MAP.get(interval, "30d")

    yf_symbol = get_yfinance_symbol(nse_symbol)

    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=period, interval=interval)

        if df is None or df.empty:
            return None

        required = ["Open", "High", "Low", "Close", "Volume"]
        for col in required:
            if col not in df.columns:
                return None

        df = df[required].copy()
        df.dropna(inplace=True)

        if interval == "1d" and _is_market_hours() and len(df) > 1:
            df = df.iloc[:-1]

        if len(df) < 5:
            return None

        return df

    except Exception:
        return None


def fetch_stock_data(
    nse_symbol: str,
    interval: str = "15m",
    period: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV data for a single NSE stock.
    Primary: broker API (real-time). Fallback: yfinance (delayed).

    Args:
        nse_symbol: NSE symbol (e.g., "RELIANCE")
        interval: Candle interval (e.g., "5m", "15m", "1d")
        period: Data period — used for yfinance fallback only.

    Returns:
        DataFrame with [Open, High, Low, Close, Volume] or None on error.
    """
    cached = _get_cached(nse_symbol, interval)
    if cached is not None:
        return cached

    # Try broker first (real-time)
    df = _fetch_via_broker(nse_symbol, interval)

    # Fallback to yfinance if broker fails
    if df is None:
        df = _fetch_via_yfinance(nse_symbol, interval, period)

    if df is not None and not df.empty:
        _set_cache(nse_symbol, interval, df)
        return df

    return None


def get_nifty_trend(timeframe: str = "5m") -> str:
    """
    Check Nifty 50 trend direction using VWAP and 20 EMA.

    Returns:
        "BULLISH"  — Nifty above both VWAP and 20 EMA
        "BEARISH"  — Nifty below both
        "NEUTRAL"  — mixed signals
        "UNKNOWN"  — data unavailable
    """
    try:
        cached = _get_cached("^NSEI_TREND", timeframe)
        if cached is not None:
            return cached.iloc[0]["trend"]

        # Try broker for NIFTY index
        df = None
        try:
            from services.broker_client import get_fyers, is_authenticated
            if is_authenticated():
                broker = get_fyers()
                if broker:
                    broker_resolution = BROKER_INTERVAL_MAP.get(timeframe, "15")
                    now = datetime.now(IST)
                    data = {
                        "symbol": "NSE:NIFTY50-INDEX",
                        "resolution": broker_resolution,
                        "date_format": "1",
                        "range_from": (now - timedelta(days=30)).strftime("%Y-%m-%d"),
                        "range_to": now.strftime("%Y-%m-%d"),
                        "cont_flag": "1",
                    }
                    _rate_limit_broker()
                    response = broker.history(data=data)
                    if response and response.get("s") == "ok":
                        candles = response.get("candles", [])
                        if candles and len(candles) >= 20:
                            df = pd.DataFrame(candles, columns=["Timestamp", "Open", "High", "Low", "Close", "Volume"])
                            df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        except Exception:
            pass

        # Fallback to yfinance
        if df is None or len(df) < 20:
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

        result_df = pd.DataFrame([{"trend": trend}])
        _set_cache("^NSEI_TREND", timeframe, result_df)

        return trend

    except Exception:
        return "UNKNOWN"


def fetch_bulk_data(
    symbols: list[str],
    interval: str = "15m",
    max_workers: int = 8,
) -> dict[str, pd.DataFrame]:
    """
    Fetch data for multiple symbols concurrently.
    Uses broker with rate limiting, falls back to yfinance per-symbol.

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
