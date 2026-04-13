"""
Scanner service — runs selected strategies across the Nifty 500 universe.

Fetches OHLCV data via yfinance, applies each strategy's signal logic, and
returns ranked BUY/SELL signals with position-sizing (2% risk per trade).
Supports both intraday and swing timeframes, and uses thread-pool
concurrency to scan ~500 stocks in under a minute.
"""

import time
import math
import logging
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf
import pandas as pd
from nifty500 import get_nifty500_symbols
from strategies import STRATEGY_MAP
from services.market_data import fetch_stock_data, get_nifty_trend
from config import (
    STRATEGY_TIMEFRAMES, SWING_STRATEGY_TIMEFRAMES,
    INTRADAY_MIN_PRICE, INTRADAY_MAX_PRICE, SWING_MIN_PRICE, SWING_MAX_PRICE,
    INTERVAL_PERIOD_MAP, NSE_HOLIDAYS,
)

logger = logging.getLogger(__name__)

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

# NSE market hours
MARKET_OPEN_HOUR, MARKET_OPEN_MIN = 9, 15
MARKET_CLOSE_HOUR, MARKET_CLOSE_MIN = 15, 30

# Weekdays: Monday=0 to Friday=4
TRADING_DAYS = {0, 1, 2, 3, 4}

# ── Multi-timeframe daily trend cache ────────────────────────────────────────
# Key: (symbol, date_str) → value: "BULLISH" | "BEARISH" | "NEUTRAL"
# Cached per symbol per calendar day to avoid redundant daily data fetches.
_daily_trend_cache: dict[tuple[str, str], str] = {}

# Intraday timeframes eligible for multi-timeframe boost
_MTF_INTRADAY_INTERVALS = {"3m", "5m", "15m", "30m"}

# Boost / penalty multipliers for trend alignment
_MTF_ALIGNED_BOOST = 1.4
_MTF_COUNTER_PENALTY = 0.7


def _get_daily_trend(symbol: str) -> str:
    """
    Fetch daily chart for *symbol* and return trend based on 20 EMA vs 50 EMA.

    Returns:
        "BULLISH"  — daily 20 EMA > 50 EMA (uptrend)
        "BEARISH"  — daily 20 EMA < 50 EMA (downtrend)
        "NEUTRAL"  — data insufficient or EMAs equal
    """
    today_str = datetime.now(IST).strftime("%Y-%m-%d")
    cache_key = (symbol, today_str)
    if cache_key in _daily_trend_cache:
        return _daily_trend_cache[cache_key]

    try:
        df = fetch_stock_data(symbol, interval="1d", period="3mo")
        if df is None or len(df) < 50:
            _daily_trend_cache[cache_key] = "NEUTRAL"
            return "NEUTRAL"

        ema20 = df["Close"].ewm(span=20, adjust=False).mean().iloc[-1]
        ema50 = df["Close"].ewm(span=50, adjust=False).mean().iloc[-1]

        if ema20 > ema50:
            trend = "BULLISH"
        elif ema20 < ema50:
            trend = "BEARISH"
        else:
            trend = "NEUTRAL"

        _daily_trend_cache[cache_key] = trend
        return trend
    except Exception:
        _daily_trend_cache[cache_key] = "NEUTRAL"
        return "NEUTRAL"


def is_market_open() -> bool:
    """Check if NSE market is currently open (handles weekends + holidays)."""
    now = datetime.now(IST)
    if now.weekday() not in TRADING_DAYS:
        return False
    if now.strftime("%Y-%m-%d") in NSE_HOLIDAYS:
        return False
    market_open = now.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MIN, second=0)
    market_close = now.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MIN, second=0)
    return market_open <= now <= market_close


def _next_trading_day(from_date) -> tuple:
    """Find the next trading day (skips weekends + holidays). Returns (date, str)."""
    d = from_date + timedelta(days=1)
    for _ in range(30):  # safety limit
        if d.weekday() in TRADING_DAYS and d.strftime("%Y-%m-%d") not in NSE_HOLIDAYS:
            return d, d.strftime("%a, %b %d")
        d += timedelta(days=1)
    return d, d.strftime("%a, %b %d")


def _upcoming_holidays(from_date, count=3) -> list:
    """Return next `count` upcoming NSE holidays from from_date."""
    upcoming = []
    for date_str in sorted(NSE_HOLIDAYS.keys()):
        try:
            hdate = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if hdate >= from_date:
            upcoming.append({
                "date": date_str,
                "label": hdate.strftime("%a, %b %d"),
                "name": NSE_HOLIDAYS[date_str],
            })
            if len(upcoming) >= count:
                break
    return upcoming


def get_market_status() -> dict:
    """Return current market status with timing info, next trading day, and upcoming holidays."""
    now = datetime.now(IST)
    today_str = now.strftime("%Y-%m-%d")
    is_holiday = today_str in NSE_HOLIDAYS
    holiday_name = NSE_HOLIDAYS.get(today_str, "")

    _, next_day_label = _next_trading_day(now.date())
    upcoming = _upcoming_holidays(now.date())

    base = {
        "next_trading_day": next_day_label,
        "upcoming_holidays": upcoming,
    }

    is_open = is_market_open()
    if is_open:
        close_time = now.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MIN, second=0)
        mins_left = int((close_time - now).total_seconds() / 60)
        return {**base, "is_open": True, "message": f"Market open \u2022 {mins_left} min left"}

    # Market closed — find next open
    if not is_holiday and now.weekday() in TRADING_DAYS and (now.hour < MARKET_OPEN_HOUR or (now.hour == MARKET_OPEN_HOUR and now.minute < MARKET_OPEN_MIN)):
        open_time = now.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MIN, second=0)
        mins_until = int((open_time - now).total_seconds() / 60)
        return {**base, "is_open": False, "message": f"Market opens in {mins_until} min (9:15 AM IST)"}

    # After close, weekend, or holiday
    day_name = now.strftime('%A')
    if now.weekday() >= 5:
        return {**base, "is_open": False, "message": f"Market closed \u2022 Weekend ({day_name})"}
    if is_holiday:
        return {**base, "is_open": False, "message": f"Market closed \u2022 {holiday_name}"}
    return {**base, "is_open": False, "message": "Market closed \u2022 Opens 9:15 AM IST"}


def _calc_conviction(signal: dict) -> float:
    """Score signal quality: higher = more conviction."""
    score = 1.0

    # Volume strength (if available in signal)
    vol_ratio = signal.get("volume_ratio", 1.0)
    if vol_ratio >= 2.0:
        score *= 1.5  # Strong volume
    elif vol_ratio >= 1.5:
        score *= 1.2  # Decent volume

    # R:R ratio bonus
    risk = max(signal.get("risk", 1), 0.01)
    reward = signal.get("reward", 0)
    rr = reward / risk
    if rr >= 2.5:
        score *= 1.3
    elif rr >= 2.0:
        score *= 1.1

    # Price range preference (₹200-₹2000 stocks move better intraday)
    entry = signal.get("entry_price", 0)
    if 200 <= entry <= 2000:
        score *= 1.2  # Sweet spot for intraday momentum
    elif entry < 100:
        score *= 0.6  # Too cheap, won't move enough
    elif entry > 3000:
        score *= 0.8  # Expensive, needs more capital

    # Strategy preference (based on 30-day performance data)
    strategy = signal.get("_strategy", "")
    strategy_boost = {
        "play4_supertrend": 0.8,
        "play7_orb": 1.0,
        "play9_gap_analysis": 1.0,
        "play3_vwap_pullback": 1.0,
        "play8_rsi_divergence": 1.4,
        "play6_bb_contra": 1.1,
        "play5_bb_squeeze": 1.0,
        "play1_ema_crossover": 1.0,
        "play2_triple_ma": 1.0,
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    }
    score *= strategy_boost.get(strategy, 1.0)

    # Pivot alignment bonus — entry near pivot level = higher conviction
    pivots = signal.get("pivot_points", {})
    if pivots and entry > 0:
        pivot = pivots.get("pivot", 0)
        s1 = pivots.get("s1", 0)
        r1 = pivots.get("r1", 0)
        if pivot > 0:
            # Check if entry is within 0.5% of any key level
            for level in [pivot, s1, r1]:
                if level > 0 and abs(entry - level) / level < 0.005:
                    score *= 1.1  # Near pivot level = higher conviction
                    break

    # Multi-timeframe confirmation: daily trend alignment
    # HARD GATE: counter-trend signals are BLOCKED (score = 0), not just penalized
    # Aligned signals get 1.4x boost
    sig_tf = signal.get("timeframe", "")
    sig_type = signal.get("signal_type", "")
    symbol = signal.get("symbol", "") or signal.get("name", "")
    if sig_tf in _MTF_INTRADAY_INTERVALS and symbol and sig_type in ("BUY", "SELL"):
        try:
            daily_trend = _get_daily_trend(symbol)
            if daily_trend == "BULLISH":
                if sig_type == "BUY":
                    score *= _MTF_ALIGNED_BOOST  # Aligned — boost
                else:
                    score = 0  # Counter-trend — BLOCK
            elif daily_trend == "BEARISH":
                if sig_type == "SELL":
                    score *= _MTF_ALIGNED_BOOST  # Aligned — boost
                else:
                    score = 0  # Counter-trend — BLOCK
            # NEUTRAL → no boost, no penalty (either direction OK)
        except Exception:
            pass  # Skip on error — fail open

    return round(score, 3)


def calculate_quantity(capital: float, entry_price: float, risk_per_share: float) -> int:
    """
    Calculate position size based on capital.
    Risk 2% of capital per trade.
    """
    risk_amount = capital * 0.02
    if risk_per_share <= 0:
        return 0
    qty = math.floor(risk_amount / risk_per_share)
    # Also ensure we can afford the shares
    max_qty = math.floor(capital / entry_price) if entry_price > 0 else 0
    return min(qty, max_qty)


# Cache for Nifty 50 SMA check (refreshed every 30 min)
_nifty_50sma_cache: dict = {"value": None, "ts": 0}


def _is_nifty_below_50sma() -> bool:
    """Check if Nifty 50 is below its 50-day SMA (genuine market weakness).
    Returns False (allow BUY) if data is unavailable — fail open."""
    now = time.time()
    if _nifty_50sma_cache["value"] is not None and now - _nifty_50sma_cache["ts"] < 1800:
        return _nifty_50sma_cache["value"]
    try:
        ticker = yf.Ticker("^NSEI")
        df = ticker.history(period="200d", interval="1d")
        if df is None or len(df) < 50:
            return False
        close = float(df["Close"].iloc[-1])
        sma50 = float(df["Close"].rolling(50).mean().iloc[-1])
        result = close < sma50
        _nifty_50sma_cache["value"] = result
        _nifty_50sma_cache["ts"] = now
        return result
    except Exception:
        return False


def scan_single_stock(symbol: str, strategy_key: str, timeframe: str, capital: float, mode: str = "intraday"):
    """Scan a single stock with a given strategy. Returns signal dict or None."""
    strategy = STRATEGY_MAP.get(strategy_key)
    if strategy is None:
        return None

    df = fetch_stock_data(symbol, interval=timeframe)
    if df is None:
        return None

    # Price range filter — skip stocks outside configured range
    if len(df) > 0:
        last_price = float(df["Close"].iloc[-1])
        if mode == "swing":
            if last_price < SWING_MIN_PRICE or last_price > SWING_MAX_PRICE:
                return None
        else:
            if last_price < INTRADAY_MIN_PRICE or last_price > INTRADAY_MAX_PRICE:
                return None

    signal = strategy.scan(df, symbol, timeframe=timeframe)
    if signal is None:
        return None

    # Circuit limit check — skip stocks at circuit (can't trade)
    if signal and df is not None and len(df) >= 2:
        last = df.iloc[-1]
        prev = df.iloc[-2]
        last_close = float(last["Close"])
        prev_close = float(prev["Close"])
        if prev_close > 0:
            change_pct = abs(last_close - prev_close) / prev_close * 100
            # If price moved > 19% in one candle, likely at circuit
            if change_pct > 19:
                return None
        # Also check if high == low == close (frozen at circuit)
        if float(last["High"]) == float(last["Low"]) == float(last["Close"]):
            return None

    # Enrich signal with volume ratio for conviction scoring
    if len(df) >= 20:
        vol_sma = df["Volume"].rolling(20).mean().iloc[-1]
        current_vol = df["Volume"].iloc[-1]
        signal["volume_ratio"] = round(current_vol / vol_sma, 2) if vol_sma > 0 else 1.0

    # Unusual volume filter — skip stocks with extreme volume (news-driven, unpredictable)
    vol_ratio = signal.get("volume_ratio", 1.0)
    if vol_ratio > 5.0:
        return None  # Skip — likely news-driven move, high reversal risk

    # Add pivot point levels for enhanced SL/target
    from strategies.base import calc_pivot_points
    pivots = calc_pivot_points(df)
    if pivots and signal:
        signal["pivot_points"] = pivots

    # Calculate quantity based on capital
    risk = signal.get("risk", 0)
    entry = signal.get("entry_price", 0)
    qty = calculate_quantity(capital, entry, risk)
    if qty <= 0:
        return None

    signal["quantity"] = qty
    signal["capital_required"] = round(qty * entry, 2)
    signal["name"] = symbol  # will be enriched later if needed
    signal["timeframe"] = timeframe

    return signal


def run_scan(strategy_key: str, timeframe: str, capital: float = 100000, max_workers: int = 10, mode: str = "intraday"):
    """
    Run a full scan of Nifty 500 stocks for a given strategy.

    Args:
        mode: "intraday" or "swing" — determines which timeframes are valid.

    Returns:
        dict with scan results.
    """
    symbols = get_nifty500_symbols()
    start_time = time.time()

    # Block intraday scans outside market hours (1h/1d work anytime)
    intraday_timeframes = {"3m", "5m", "15m", "30m"}
    if timeframe in intraday_timeframes and not is_market_open():
        status = get_market_status()
        return {
            "strategy": strategy_key,
            "timeframe": timeframe,
            "capital": capital,
            "signals": [],
            "stocks_scanned": 0,
            "stocks_eligible": 0,
            "scan_time_seconds": 0,
            "market_status": status,
            "error": f"{status['message']}. Intraday scans are only available during market hours (9:15 AM \u2013 3:30 PM IST).",
        }

    # Validate strategy and timeframe
    if strategy_key not in STRATEGY_MAP:
        return {
            "strategy": strategy_key,
            "timeframe": timeframe,
            "capital": capital,
            "signals": [],
            "stocks_scanned": 0,
            "stocks_eligible": 0,
            "scan_time_seconds": 0,
            "error": f"Unknown strategy: {strategy_key}",
        }

    if mode == "swing":
        valid_timeframes = SWING_STRATEGY_TIMEFRAMES.get(strategy_key, [])
    else:
        valid_timeframes = STRATEGY_TIMEFRAMES.get(strategy_key, [])
    if timeframe not in valid_timeframes:
        return {
            "strategy": strategy_key,
            "timeframe": timeframe,
            "capital": capital,
            "signals": [],
            "stocks_scanned": 0,
            "stocks_eligible": 0,
            "scan_time_seconds": 0,
            "error": f"Invalid timeframe '{timeframe}' for {strategy_key}. Valid: {valid_timeframes}",
        }

    signals = []
    scanned = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_symbol = {
            executor.submit(scan_single_stock, sym, strategy_key, timeframe, capital, mode): sym
            for sym in symbols
        }

        for future in as_completed(future_to_symbol):
            scanned += 1
            try:
                result = future.result()
                if result is not None:
                    signals.append(result)
            except Exception:
                pass

    # ── Swing mode: CNC only supports BUY (no short selling in delivery) ──
    if mode == "swing":
        signals = [s for s in signals if s.get("signal_type") == "BUY"]

    # ── Nifty trend filter ──
    if mode == "swing":
        # Swing: only block BUY if Nifty is below 50 SMA (genuine weakness)
        # A single bearish day in an uptrend shouldn't block multi-day BUY setups
        nifty_below_50sma = _is_nifty_below_50sma()
        if nifty_below_50sma:
            signals = [s for s in signals if s.get("signal_type") != "BUY"]
    else:
        # Intraday: use VWAP + 20 EMA trend as before
        nifty_trend = get_nifty_trend(timeframe)
        if nifty_trend == "BULLISH":
            signals = [s for s in signals if s.get("signal_type") != "SELL"]
        elif nifty_trend == "BEARISH":
            signals = [s for s in signals if s.get("signal_type") != "BUY"]

    # Sort by conviction score (best first)
    for s in signals:
        s["conviction"] = _calc_conviction(s)
    signals.sort(key=lambda s: s.get("conviction", 0), reverse=True)

    # ── INSTITUTIONAL QUALITY GATE: minimum conviction threshold ──
    # Only trade signals with conviction >= 1.2 (volume + trend + R:R aligned)
    # Prevents weak signals from reaching auto_trader
    MIN_CONVICTION = 1.2
    before = len(signals)
    signals = [s for s in signals if s.get("conviction", 0) >= MIN_CONVICTION]
    if before > 0 and len(signals) < before:
        logger.info(f"[Scanner] Conviction filter: {before} → {len(signals)} signals (min={MIN_CONVICTION})")

    elapsed = round(time.time() - start_time, 2)

    return {
        "strategy": strategy_key,
        "timeframe": timeframe,
        "capital": capital,
        "signals": signals,
        "stocks_scanned": scanned,
        "stocks_eligible": len(signals),
        "scan_time_seconds": elapsed,
    }
